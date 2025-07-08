from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime
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
        asyncio.get_event_loop().create_task(self._ensure_indexes())

    async def _ensure_indexes(self) -> None:
        await self._submissions.create_index("hotkey")
        await self._performances.create_index([("hotkey", 1), ("content_id", 1)])

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
    async def _hotkey_scores(self) -> Dict[str, float]:
        perfs = await self._performances.find({"hotkey": {"$in": self.metagraph.hotkeys}}).to_list(None)
        grouped: dict[str, list[Performance]] = defaultdict(list)
        for doc in perfs:
            grouped[doc["hotkey"]].append(Performance(**doc))

        scores = {hk: sum(p.get_score() for p in pl) for hk, pl in grouped.items()}
        return scores

    async def calculate_and_set_weights(self) -> None:
        """Calculate weights based on top 5 engagement rates and set them on subnet"""
        try:
            # Calculate engagement rates for ranking
            engagement_rates = await self._calculate_miner_engagement_rates()
            if not engagement_rates:
                logger.warning("No engagement rates calculated - skipping weight update")
                return

            # Get top 5 miners by engagement rate
            sorted_miners = sorted(engagement_rates.items(), key=lambda item: item[1], reverse=True)
            top_5_hotkeys = {hk for hk, _ in sorted_miners[:5]}
            
            # Get content scores for top miners only
            all_content_scores = await self._hotkey_scores()
            scores_for_weights = {hk: max(0.0, score) for hk, score in all_content_scores.items() if hk in top_5_hotkeys}
            
            # Build weights array
            uids, weights = [], []
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                uids.append(uid)
                weights.append(scores_for_weights.get(hotkey, 0.0))

            # Normalize weights
            weights_array = np.array(weights, dtype=np.float32)
            if np.sum(weights_array) > 0:
                weights_array /= np.sum(weights_array)

            uint_uids, uint_weights = bt.utils.weight_utils.convert_weights_and_uids_for_emit(
                uids=np.array(uids, dtype=np.int32),
                weights=weights_array,
            )
            if np.sum(uint_weights) == 0:
                logger.info(f"Empty weights array, setting top 5 miners to 65535")
                uint_weights = []
                uint_uids = []
                for hotkey in top_5_hotkeys:
                    uint_weights.append(65535)
                    uint_uids.append(self.metagraph.hotkeys.index(hotkey))
                    logger.info(f"Setting weight for {hotkey} to 65535")

            logger.info(f"Full Weights: {tabulate(list(zip(uint_uids, uint_weights)), headers=['UID', 'Weight'], tablefmt='grid')}")
            # Summary logging
            top_miners_summary = [
                {"hotkey": hk[:8], "engagement_rate": f"{rate:.2f}%", "content_score": scores_for_weights.get(hk, 0.0)}
                for hk, rate in sorted_miners
            ]
            top_miners_summary = [str(item) for item in top_miners_summary]
            summary_text = '\n'.join(top_miners_summary)
            logger.info(f"Sorted miners by engagement:\n{summary_text}")

            
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
