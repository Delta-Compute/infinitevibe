from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List

import bittensor as bt
import httpx
import numpy as np
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from tensorflix.config import CONFIG
from tensorflix.protocol import (
    Metric,
    PeerMetadata,
    Performance,
    Submission,
)
from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadata,
    InstagramPostMetadata,
)
from tensorflix.models.brief import (
    Brief, BriefSubmission, BriefStatus, 
    SubmissionType, ValidationStatus
)
from tensorflix.db.brief_ops import BriefDatabase
from tensorflix.storage.r2_client import R2StorageClient
from tensorflix.utils.ids import generate_submission_id
from tabulate import tabulate



class TensorFlixValidator:
    __slots__ = (
        "wallet",
        "subtensor",
        "metagraph",
        "netuid",
        "_active_content_ids",
        "_uid_of_hotkey",
        "_submissions",
        "_performances",
        "_fetch_metrics_semaphore",
        "_brief_db",
        "_r2_client",
    )

    # ─────────────────── Init ────────────────────
    def __init__(
        self,
        wallet: bt.Wallet,
        subtensor: bt.AsyncSubtensor,
        metagraph: bt.Metagraph,
        db_client: AsyncIOMotorClient,
        netuid: int,
    ) -> None:
        self.wallet = wallet
        self.subtensor = subtensor
        self.metagraph = metagraph
        self.netuid = netuid
        self._uid_of_hotkey: dict[str, int] = {
            hk: int(uid) for hk, uid in zip(metagraph.hotkeys, metagraph.uids)
        }
        self._active_content_ids: set[str] = set()

        db = db_client["tensorflix"]
        self._submissions: AsyncIOMotorCollection = db[f"submissions-{CONFIG.version}"]
        self._performances: AsyncIOMotorCollection = db[f"performances-{CONFIG.version}"]
        self._fetch_metrics_semaphore = asyncio.Semaphore(4)
        
        # Initialize brief database and R2 client
        self._brief_db = BriefDatabase(db_client)
        try:
            self._r2_client = R2StorageClient()
        except ValueError as e:
            logger.warning(f"R2 client not initialized: {e}")
            self._r2_client = None
        
        asyncio.get_event_loop().create_task(self._ensure_indexes())

    async def _ensure_indexes(self) -> None:
        await self._submissions.create_index("hotkey")
        await self._performances.create_index([("hotkey", 1), ("content_id", 1)])
        await self._brief_db.create_indexes()

    # ─────────────────── Submissions ─────────────
    async def _peer_metadata(self) -> list[PeerMetadata]:
        commitments = await self.subtensor.get_all_commitments(netuid=self.netuid)
        peers = [
            PeerMetadata(
                uid=self._uid_of_hotkey[hk],
                hotkey=hk,
                commit=commit,
            )
            for hk, commit in commitments.items()
            if hk in self._uid_of_hotkey and ":" in commit
        ]
        peers = [p for p in peers if p.commit]
        return peers

    async def _refresh_peer_submissions(self, peer: PeerMetadata) -> dict:
        """Returns summary stats for this peer's submission refresh"""
        # Check if this is a brief submission
        if peer.brief_commit:
            return await self._process_brief_submission(peer)
        else:
            # Handle traditional gist submissions
            await peer.update_submissions()
            self._active_content_ids.update((sub.content_id for sub in peer.submissions))

            if not peer.submissions:
                await self._submissions.delete_many({"hotkey": peer.hotkey})
                return {"hotkey": peer.hotkey[:8], "submissions": 0, "action": "deleted"}

            await self._submissions.update_one(
                {"hotkey": peer.hotkey},
                {"$set": {"submissions": [s.model_dump() for s in peer.submissions]}},
                upsert=True,
            )
            return {
                "hotkey": peer.hotkey[:8], 
                "submissions": len(peer.submissions),
                "action": "updated"
            }

    async def update_all_submissions(self) -> None:
        peers = await self._peer_metadata()
        sem = asyncio.Semaphore(32)
        
        results = []

        async def _guarded(p: PeerMetadata) -> None:
            async with sem:
                result = await self._refresh_peer_submissions(p)
                results.append(result)

        await asyncio.gather(*[_guarded(p) for p in peers])
        
        # Summary logging
        total_peers = len(peers)
        total_submissions = sum(r["submissions"] for r in results)
        active_peers = len([r for r in results if r["submissions"] > 0])
        
        logger.info("Submissions Update Complete", extra={
            "summary": {
                "total_peers": total_peers,
                "active_peers": active_peers,
                "total_submissions": total_submissions,
                "active_content_ids": len(self._active_content_ids)
            }
        })

    # ─────────────────── Brief Submissions ────────────────
    async def _process_brief_submission(self, peer: PeerMetadata) -> dict:
        """Process a brief submission from a miner"""
        brief_commit = peer.brief_commit
        
        # Validate brief exists and is active
        brief = await self._brief_db.get_brief(brief_commit.brief_id)
        if not brief:
            logger.warning(f"Brief not found: {brief_commit.brief_id} from {peer.hotkey[:8]}")
            return {"hotkey": peer.hotkey[:8], "submissions": 0, "action": "invalid_brief"}
        
        if not brief.is_active():
            logger.warning(f"Brief expired: {brief_commit.brief_id} from {peer.hotkey[:8]}")
            return {"hotkey": peer.hotkey[:8], "submissions": 0, "action": "brief_expired"}
        
        # Check if sub_2 is allowed (miner must be in top 10)
        if brief_commit.submission_type == SubmissionType.SUB_2:
            if not brief.can_submit_revision(peer.hotkey):
                logger.warning(f"Unauthorized sub_2: {peer.hotkey[:8]} not in top 10")
                return {"hotkey": peer.hotkey[:8], "submissions": 0, "action": "unauthorized_revision"}
        
        # Validate R2 link
        validation_status = ValidationStatus.PENDING
        validation_message = None
        
        if self._r2_client:
            if await self._validate_r2_submission(brief_commit.r2_link):
                validation_status = ValidationStatus.VALID
                validation_message = "R2 video validated"
            else:
                validation_status = ValidationStatus.INVALID
                validation_message = "R2 video not found or invalid"
        else:
            logger.warning("R2 client not available, skipping validation")
        
        # Create submission record
        submission_id = generate_submission_id(
            brief_commit.brief_id, 
            peer.hotkey, 
            brief_commit.submission_type.value
        )
        
        submission = BriefSubmission(
            submission_id=submission_id,
            brief_id=brief_commit.brief_id,
            miner_hotkey=peer.hotkey,
            submission_type=brief_commit.submission_type,
            r2_link=brief_commit.r2_link,
            validation_status=validation_status,
            validation_message=validation_message
        )
        
        # Store submission
        success = await self._brief_db.create_submission(submission)
        
        if success:
            logger.info(f"Brief submission processed: {brief_commit.brief_id} - {peer.hotkey[:8]} - {brief_commit.submission_type}")
            
            # Trigger GCP processing if valid
            if validation_status == ValidationStatus.VALID:
                asyncio.create_task(self._trigger_video_processing(submission))
            
            return {
                "hotkey": peer.hotkey[:8],
                "submissions": 1,
                "action": "brief_submission",
                "brief_id": brief_commit.brief_id,
                "type": brief_commit.submission_type.value
            }
        else:
            return {"hotkey": peer.hotkey[:8], "submissions": 0, "action": "duplicate_submission"}
    
    async def _validate_r2_submission(self, r2_link: str) -> bool:
        """Validate that the R2 submission exists and is a valid video"""
        if not self._r2_client:
            return False
        
        try:
            # Check if file exists
            if not self._r2_client.validate_r2_link(r2_link):
                return False
            
            # Get metadata to verify it's a video
            metadata = self._r2_client.get_object_metadata(r2_link)
            if not metadata:
                return False
            
            # Check content type
            content_type = metadata.get('content_type', '').lower()
            if not any(video_type in content_type for video_type in ['video/', 'mp4', 'webm']):
                logger.warning(f"Invalid content type: {content_type} for {r2_link}")
                return False
            
            # Check file size (reject if too small/large)
            size_mb = metadata.get('size', 0) / (1024 * 1024)
            if size_mb < 0.1 or size_mb > 500:  # 100KB - 500MB
                logger.warning(f"Invalid file size: {size_mb:.2f}MB for {r2_link}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating R2 submission: {e}")
            return False
    
    async def _trigger_video_processing(self, submission: BriefSubmission):
        """Trigger GCP video processing pipeline (placeholder for integration)"""
        logger.info(f"Would trigger GCP processing for {submission.submission_id}")
        # TODO: Integrate with John's Cloud Run job for video processing
        # This would send the submission to the GCP pipeline
    
    async def _check_brief_deadlines(self):
        """Check for briefs needing deadline reminders"""
        # Get briefs approaching deadline (2 hours before)
        briefs_needing_reminder = await self._brief_db.get_briefs_needing_deadline_reminder(hours_before=2)
        
        for brief in briefs_needing_reminder:
            # Get miners who haven't submitted
            submissions = await self._brief_db.get_brief_submissions(brief.brief_id)
            submitted_miners = {sub.miner_hotkey for sub in submissions}
            
            # Get all active miners
            active_miners = set(self.metagraph.hotkeys)
            miners_without_submission = active_miners - submitted_miners
            
            if miners_without_submission:
                logger.info(f"Brief {brief.brief_id} deadline approaching - {len(miners_without_submission)} miners haven't submitted")
                # TODO: Trigger email notifications via SendGrid/AWS SES
                # This would send reminder emails to miners
                
                # For now, just log the information
                for miner in list(miners_without_submission)[:10]:  # Log first 10
                    logger.info(f"  - Miner {miner[:8]}... needs reminder for brief {brief.brief_id}")

    # ─────────────────── Metrics ────────────────
    async def _fetch_metrics(self, sub: Submission) -> Metric | None:
        url = f"{CONFIG.service_platform_tracker_url}/get_metrics"
        try:
            async with self._fetch_metrics_semaphore:
                async with httpx.AsyncClient(timeout=64.0) as client:
                    r = await client.post(
                        url,
                        json={
                            "platform": sub.platform.split("/")[0],
                            "content_type": sub.platform.split("/")[1],
                            "content_id": sub.content_id,
                            "get_direct_url": True,
                        },
                    )
            data = r.json()
            if sub.platform == "youtube/video":
                return YoutubeVideoMetadata.from_response(data)
            elif sub.platform in ("instagram/reel", "instagram/post"):
                return InstagramPostMetadata.from_response(data)
            else:
                raise ValueError(f"Unknown platform: {sub.platform}")
        except Exception as exc:
            logger.error(f"Metrics fetch failed for {sub.platform}:{sub.content_id}\n{exc}\n{r.text if r else 'No response'}")
            return None

    async def _update_hotkey_performances(
        self,
        hotkey: str,
        submissions: Iterable[Submission],
        interval_key: str,
    ) -> dict:
        """Returns summary stats for this hotkey's performance update"""
        processed = 0
        ai_checked = 0
        errors = 0
        
        total = len(submissions)
        index = 1
        for sub in submissions[:CONFIG.max_submissions_per_hotkey]:
            try:
                perf_doc = await self._performances.find_one(
                    {"hotkey": hotkey, "content_id": sub.content_id}
                )
                perf = (
                    Performance(**perf_doc)
                    if perf_doc
                    else Performance(
                        hotkey=hotkey,
                        content_id=sub.content_id,
                        platform_metrics_by_interval={},
                    )
                )
                
                metric = await self._fetch_metrics(sub)
                if metric is None:
                    errors += 1
                    continue
                
                logger.info(f"Fetched metrics for {sub.platform}:{sub.content_id}")

                # AI detection check
                if not sub.checked_for_ai:
                    async with httpx.AsyncClient(timeout=192.0) as client:
                        try:
                            r = await client.post(
                                f"{CONFIG.service_ai_detector_url}/detect?url={sub.direct_video_url}"
                            )
                            metric.ai_score = r.json()["mean_ai_generated"]
                            sub.checked_for_ai = True
                            ai_checked += 1
                        except Exception:
                            metric.ai_score = 0.0
                        
                        await self._submissions.update_one(
                            {"hotkey": hotkey, "content_id": sub.content_id},
                            {"$set": {"checked_for_ai": True}},
                            upsert=True,
                        )

                perf.platform_metrics_by_interval[interval_key] = metric
                await self._performances.update_one(
                    {"hotkey": hotkey, "content_id": sub.content_id},
                    {"$set": perf.model_dump()},
                    upsert=True,
                )
                processed += 1
                
            except Exception as exc:
                logger.error(f"Performance update failed for {hotkey[:8]}:{sub.content_id}")
                errors += 1

        return {
            "hotkey": hotkey[:8],
            "processed": processed,
            "ai_checked": ai_checked,
            "errors": errors
        }

    async def _calculate_miner_engagement_rates(self) -> dict[str, float]:
        """Calculate engagement rate for all active miners"""
        engagement_rates = {}
        active_hotkeys = []

        # Get active miners (excluding validators)
        for uid, hotkey in enumerate(self.metagraph.hotkeys):
            is_active_miner = (
                self.metagraph.S[uid] > 0 and not self.metagraph.validator_permit[uid]
            )
            if is_active_miner:
                active_hotkeys.append(hotkey)

        for hotkey in active_hotkeys:
            perf_docs = await self._performances.find({"hotkey": hotkey}).to_list(None)
            if not perf_docs:
                engagement_rates[hotkey] = 0
                continue
            
            total_likes, total_comments, follower_count, valid_posts = 0.0, 0.0, 0, 0

            for doc in perf_docs:
                perf = Performance(**doc)
                if not perf.platform_metrics_by_interval: 
                    continue
                    
                latest_metric = perf.platform_metrics_by_interval[sorted(perf.platform_metrics_by_interval.keys())[-1]]
                
                if hasattr(latest_metric, 'owner_follower_count') and latest_metric.owner_follower_count > 0:
                    follower_count = latest_metric.owner_follower_count

                is_valid = (
                    latest_metric.check_signature(hotkey) 
                    and latest_metric.ai_score > CONFIG.ai_generated_score_threshold
                )
                if not is_valid: 
                    continue

                total_likes += latest_metric.like_count
                total_comments += latest_metric.comment_count
                valid_posts += 1

            if valid_posts > 0 and follower_count > 0:
                avg_engagement = (total_likes + total_comments) / valid_posts
                rate = (avg_engagement / follower_count) * 100
                engagement_rates[hotkey] = rate
            else:
                engagement_rates[hotkey] = 0

        return engagement_rates

    async def _calculate_brief_scores(self) -> dict[str, float]:
        """Calculate normalized scores for brief submissions"""
        brief_score_data = {}  # {hotkey: {"total": sum, "count": count}}
        
        # Get all active and recently completed briefs
        active_briefs = await self._brief_db.get_active_briefs()
        
        # Also get briefs completed in last 24 hours for scoring
        all_briefs = await self._brief_db.briefs_collection.find({
            "created_at": {"$gte": datetime.utcnow() - timedelta(days=1)}
        }).to_list(None)
        
        for brief_doc in all_briefs:
            brief = Brief(**brief_doc)
            submissions = await self._brief_db.get_brief_submissions(brief.brief_id)
            
            for submission in submissions:
                if submission.validation_status != ValidationStatus.VALID:
                    continue
                
                # Calculate raw score
                raw_score = submission.calculate_total_score(brief)
                
                # Normalize to 0-100 scale similar to engagement rates
                # Max possible score is 100 (30 speed + 70 selection)
                normalized_score = raw_score
                
                # Properly accumulate scores for averaging
                if submission.miner_hotkey not in brief_score_data:
                    brief_score_data[submission.miner_hotkey] = {"total": 0.0, "count": 0}
                
                brief_score_data[submission.miner_hotkey]["total"] += normalized_score
                brief_score_data[submission.miner_hotkey]["count"] += 1
        
        # Calculate final averages
        brief_scores = {}
        for hotkey, data in brief_score_data.items():
            brief_scores[hotkey] = data["total"] / data["count"]
        
        logger.info(f"Calculated brief scores for {len(brief_scores)} miners")
        return brief_scores

    async def update_performance_metrics(self, active_content_ids: list[str]) -> None:
        interval_key = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        docs = await self._submissions.find(
            {"submissions.content_id": {"$in": list(active_content_ids)}}
        ).to_list(None)

        grouped: dict[str, list[Submission]] = defaultdict(list)
        for doc in docs:
            grouped[doc["hotkey"]].extend(
                Submission(**d) for d in doc.get("submissions", [])
            )
        
        for k, v in grouped.items():
            logger.info(f"Hotkey: {k}, Submissions: {len(v)}")

        total_submissions = sum(len(v[:CONFIG.max_submissions_per_hotkey]) for v in grouped.values())
        logger.info(f"Total submissions: {total_submissions}")

        # Process all hotkeys and collect results
        tasks = [
            self._update_hotkey_performances(hk, subs, interval_key)
            for hk, subs in grouped.items()
        ]
        results = await asyncio.gather(*tasks)

        # Summary logging
        total_processed = sum(r["processed"] for r in results)
        total_ai_checked = sum(r["ai_checked"] for r in results)
        total_errors = sum(r["errors"] for r in results)
        
        logger.info("Performance Metrics Update Complete", extra={
            "summary": {
                "interval": interval_key,
                "hotkeys_processed": len(results),
                "total_submissions_processed": total_processed,
                "ai_detections_performed": total_ai_checked,
                "errors": total_errors
            }
        })

    # ─────────────────── Scoring / Weights ───────
    async def _get_active_miners(self) -> set[str]:
        """Get miners who have made valid submissions in the last 7 days"""
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        active_miners = set()
        
        # Check traditional submissions
        recent_submissions = await self._submissions.find({
            "submissions": {"$exists": True, "$ne": []}
        }).to_list(None)
        
        for doc in recent_submissions:
            # Note: We don't have timestamp in traditional submissions, so we include all for now
            # In a real implementation, we'd need to add timestamps to track this properly
            active_miners.add(doc["hotkey"])
        
        # Check brief submissions
        recent_brief_submissions = await self._brief_db.submissions_collection.find({
            "submitted_at": {"$gte": cutoff_date},
            "validation_status": ValidationStatus.VALID
        }).to_list(None)
        
        for doc in recent_brief_submissions:
            active_miners.add(doc["miner_hotkey"])
        
        # Filter to only include current network participants
        network_miners = set(self.metagraph.hotkeys)
        active_miners = active_miners.intersection(network_miners)
        
        logger.info(f"Found {len(active_miners)} active miners in last 7 days")
        return active_miners

    async def _get_last_completed_brief(self) -> Brief | None:
        """Get the most recently completed brief"""
        completed_briefs = await self._brief_db.briefs_collection.find({
            "status": BriefStatus.COMPLETED
        }).sort("created_at", -1).limit(1).to_list(1)
        
        if completed_briefs:
            return Brief(**completed_briefs[0])
        return None

    async def _calculate_legacy_content_scores(self) -> Dict[str, float]:
        """
        LEGACY METHOD: Calculate traditional content performance scores.
        
        Note: This method is no longer used in the main weight calculation flow.
        The new two-path system uses engagement rates and brief scores directly.
        Keeping this method for potential backward compatibility or debugging.
        
        TODO: Remove this method if confirmed obsolete in production.
        """
        perfs = await self._performances.find({"hotkey": {"$in": self.metagraph.hotkeys}}).to_list(None)
        grouped: dict[str, list[Performance]] = defaultdict(list)
        for doc in perfs:
            grouped[doc["hotkey"]].append(Performance(**doc))

        scores = {hk: sum(p.get_score() for p in pl) for hk, pl in grouped.items()}
        return scores

    async def calculate_and_set_weights(self) -> None:
        """Calculate weights using the new two-path eligibility system"""
        try:
            # Step 1: Identify Active Miners
            active_miners = await self._get_active_miners()
            if not active_miners:
                logger.warning("No active miners found - skipping weight update")
                return
            
            # Step 2: Calculate All Scores for active miners only
            engagement_rates = await self._calculate_miner_engagement_rates()
            brief_scores = await self._calculate_brief_scores()
            
            # Filter scores to only active miners
            active_engagement_rates = {hk: score for hk, score in engagement_rates.items() if hk in active_miners}
            active_brief_scores = {hk: score for hk, score in brief_scores.items() if hk in active_miners}
            
            # Step 3: Determine Eligibility Thresholds (75th percentile = top 25%)
            if active_engagement_rates:
                engagement_scores = list(active_engagement_rates.values())
                # Handle edge case: with very few miners, percentile calculation may exclude everyone
                if len(engagement_scores) < 4:
                    engagement_threshold = 0  # Include all when population is small
                    logger.info(f"Small engagement pool ({len(engagement_scores)} miners), setting threshold to 0")
                else:
                    engagement_threshold = np.percentile(engagement_scores, 75)
            else:
                engagement_threshold = 0
            
            if active_brief_scores:
                brief_score_values = list(active_brief_scores.values())
                # Handle edge case: with very few miners, percentile calculation may exclude everyone  
                if len(brief_score_values) < 4:
                    brief_threshold = 0  # Include all when population is small
                    logger.info(f"Small brief pool ({len(brief_score_values)} miners), setting threshold to 0")
                else:
                    brief_threshold = np.percentile(brief_score_values, 75)
            else:
                brief_threshold = 0
            
            logger.info(f"Eligibility thresholds - Engagement: {engagement_threshold:.2f}, Brief: {brief_threshold:.2f}")
            
            # Step 4: Identify Eligible Miners
            path_a_miners = {hk for hk, score in active_brief_scores.items() if score >= brief_threshold}
            path_b_miners = {hk for hk, score in active_engagement_rates.items() if score >= engagement_threshold}
            
            preliminary_eligible = path_a_miners.union(path_b_miners)
            
            # Step 5: Apply Disqualification for unresponsive engagement specialists
            final_eligible = set(preliminary_eligible)
            last_brief = await self._get_last_completed_brief()
            
            if last_brief:
                # Get miners who only qualify through Path B (engagement only)
                engagement_only_miners = path_b_miners - path_a_miners
                
                # Get miners who submitted to the last brief
                last_brief_submissions = await self._brief_db.get_brief_submissions(last_brief.brief_id)
                submitted_to_last_brief = {sub.miner_hotkey for sub in last_brief_submissions}
                
                # Disqualify engagement-only miners who didn't submit to last brief
                for miner in engagement_only_miners:
                    if miner not in submitted_to_last_brief:
                        # Check if they were active for at least 50% of brief duration
                        brief_duration = last_brief.deadline_24hr - last_brief.created_at
                        required_active_time = brief_duration * 0.5
                        
                        # PRODUCTION TODO: Track miner "first seen" timestamps to ensure fairness
                        # Current limitation: assumes miner was active for entire brief duration
                        # This could unfairly penalize miners who joined mid-brief
                        
                        # For now, only disqualify if brief was recent (last 48 hours)
                        # This reduces unfairness for new miners
                        brief_age = datetime.utcnow() - last_brief.created_at
                        if brief_age <= timedelta(hours=48) and miner in active_miners:
                            final_eligible.discard(miner)
                            logger.info(f"Disqualified engagement-only miner {miner[:8]} for not submitting to recent brief")
                        else:
                            logger.info(f"Skipping disqualification for {miner[:8]} - brief too old or miner inactive")
            
            if not final_eligible:
                logger.warning("No eligible miners after disqualification - skipping weight update")
                return
            
            # Step 6: Calculate Combined Scores and Normalize
            combined_scores = {}
            for hotkey in final_eligible:
                engagement_score = active_engagement_rates.get(hotkey, 0)
                brief_score = active_brief_scores.get(hotkey, 0)
                combined_scores[hotkey] = (engagement_score * 0.7) + (brief_score * 0.3)
            
            # Build weights array for all miners (eligible get proportional weights, others get 0)
            uids, weights = [], []
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                uids.append(uid)
                weights.append(combined_scores.get(hotkey, 0.0))

            # Normalize weights
            weights_array = np.array(weights, dtype=np.float32)
            if np.sum(weights_array) > 0:
                weights_array /= np.sum(weights_array)

            uint_uids, uint_weights = bt.utils.weight_utils.convert_weights_and_uids_for_emit(
                uids=np.array(uids, dtype=np.int32),
                weights=weights_array,
            )
            
            # Summary logging
            logger.info(f"Weight Distribution Summary:")
            logger.info(f"  Active miners: {len(active_miners)}")
            logger.info(f"  Path A (brief) eligible: {len(path_a_miners)}")
            logger.info(f"  Path B (engagement) eligible: {len(path_b_miners)}")
            logger.info(f"  Final eligible: {len(final_eligible)}")
            logger.info(f"  Receiving weights: {len([w for w in uint_weights if w > 0])}")
            
            # Detailed top miners summary
            sorted_miners = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
            top_miners_summary = []
            for hk, combined_score in sorted_miners[:10]:  # Show top 10
                path = []
                if hk in path_a_miners:
                    path.append("Brief")
                if hk in path_b_miners:
                    path.append("Engagement")
                
                summary = {
                    "hotkey": hk[:8],
                    "combined_score": f"{combined_score:.2f}",
                    "engagement_rate": f"{active_engagement_rates.get(hk, 0):.2f}%",
                    "brief_score": f"{active_brief_scores.get(hk, 0):.2f}",
                    "path": "+".join(path),
                    "eligible": hk in final_eligible
                }
                top_miners_summary.append(summary)
            
            logger.info(f"Top 10 miners: {top_miners_summary}")
            
            # Set weights on subnet
            result = await self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.netuid,
                uids=uint_uids,
                weights=uint_weights,
                version_key=CONFIG.version_key,
            )
            
            logger.info(f"Weights set result: {result}")
            
        except Exception as e:
            logger.error(f"Weight calculation failed: {str(e)}")

    # ─────────────────── Main loop ───────────────
    async def run(self) -> None:
        logger.info("Validator Started", extra={
            "config": {
                "submission_update_interval": CONFIG.submission_update_interval,
                "set_weights_interval": CONFIG.set_weights_interval,
                "netuid": self.netuid
            }
        })

        async def _periodical_task() -> None:
            while True:
                await self.calculate_and_set_weights()
                await asyncio.sleep(CONFIG.set_weights_interval)

        async def _deadline_monitor_task() -> None:
            """Monitor briefs for deadline reminders"""
            while True:
                try:
                    await self._check_brief_deadlines()
                except Exception as e:
                    logger.error(f"Deadline monitoring error: {e}")
                # Check every 30 minutes
                await asyncio.sleep(1800)

        warm_up = True


        while True:
            cycle_start = datetime.utcnow()
            try:
                await self.metagraph.sync()
                self._uid_of_hotkey = {
                    hk: int(uid)
                    for hk, uid in zip(self.metagraph.hotkeys, self.metagraph.uids)
                }
                await self.update_all_submissions()
                await self.update_performance_metrics(self._active_content_ids)
                if warm_up:
                    warm_up = False
                    asyncio.create_task(_periodical_task())
                    asyncio.create_task(_deadline_monitor_task())
                self._active_content_ids.clear()
            except Exception as exc:
                logger.exception("Validator cycle failed", exc_info=exc)

            elapsed = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info("Validator Cycle Complete", extra={
                "performance": {
                    "duration_seconds": round(elapsed, 2),
                    "metagraph_size": len(self.metagraph.hotkeys)
                }
            })
            await asyncio.sleep(CONFIG.submission_update_interval)
