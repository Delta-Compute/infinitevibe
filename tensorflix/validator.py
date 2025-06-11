from __future__ import annotations

import asyncio
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
        self._submissions: AsyncIOMotorCollection = db["submissions"]
        self._performances: AsyncIOMotorCollection = db["performances"]

        asyncio.get_event_loop().create_task(self._ensure_indexes())

    async def _ensure_indexes(self) -> None:
        await self._submissions.create_index("hotkey")
        await self._performances.create_index([("hotkey", 1), ("content_id", 1)])

    # ─────────────────── Submissions ─────────────
    async def _peer_metadata(self) -> list[PeerMetadata]:
        logger.info(f"chain_fetch_peer_commitments, netuid: {self.netuid}")
        commitments = await self.subtensor.get_all_commitments(netuid=self.netuid)
        peers = [
            PeerMetadata(
                uid=self._uid_of_hotkey[hk],
                hotkey=hk,
                commit=commit,
            )
            for hk, commit in commitments.items()
            if hk in self._uid_of_hotkey
        ]
        logger.info(
            f"commitments_fetched, peers-sample: {[p for p in peers[:5] if len(p.submissions) > 0]}"
        )
        return peers

    async def _refresh_peer_submissions(self, peer: PeerMetadata) -> None:
        await peer.update_submissions()
        self._active_content_ids.update((sub.content_id for sub in peer.submissions))

        if not peer.submissions:
            await self._submissions.delete_many({"hotkey": peer.hotkey})
            return

        await self._submissions.update_one(
            {"hotkey": peer.hotkey},
            {"$set": {"submissions": [s.model_dump() for s in peer.submissions]}},
            upsert=True,
        )

    async def update_all_submissions(self) -> None:
        peers = await self._peer_metadata()
        sem = asyncio.Semaphore(32)

        async def _guarded(p: PeerMetadata) -> None:
            async with sem:
                await self._refresh_peer_submissions(p)

        await asyncio.gather(*[_guarded(p) for p in peers])
        logger.success("submissions_update_complete")

    # ─────────────────── Metrics ────────────────
    async def _fetch_metrics(self, sub: Submission) -> Metric | None:
        url = f"{CONFIG.service_platform_tracker_url}/get_metrics"
        try:
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
            logger.error(
                f"metrics_fetch_failed- {sub.platform} {sub.content_id} - {r.text}",
                exc_info=exc,
            )
            return None

    async def _update_hotkey_performances(
        self,
        hotkey: str,
        submissions: Iterable[Submission],
        interval_key: str,
    ) -> None:
        for sub in submissions:
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
            if not sub.checked_for_ai:
                logger.info(f"Checking for AI in {sub.direct_video_url}")
                async with httpx.AsyncClient(timeout=32.0) as client:
                    try:
                        r = await client.post(
                            f"{CONFIG.service_ai_detector_url}/detect?url={sub.direct_video_url}"
                        )
                        metric.ai_score = r.json()["mean_ai_generated"]
                        sub.checked_for_ai = True
                    except Exception as exc:
                        logger.warning(
                            "ai_detection_failed",
                            exc_info=exc,
                            extra={"url": sub.direct_video_url},
                        )
                        metric.ai_score = 0.0
                    await self._submissions.update_one(
                        {"hotkey": hotkey, "content_id": sub.content_id},
                        {"$set": {"checked_for_ai": True}},
                        upsert=True,
                    )
                logger.info(f"AI score: {metric.ai_score}")
            if metric is None:
                continue

            perf.platform_metrics_by_interval[interval_key] = metric
            await self._performances.update_one(
                {"hotkey": hotkey, "content_id": sub.content_id},
                {"$set": perf.model_dump()},
                upsert=True,
            )

    async def update_performance_metrics(self, active_content_ids: list[str]) -> None:
        interval_key = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        docs = await self._submissions.find(
            {"submissions.content_id": {"$in": list(active_content_ids)}}
        ).to_list(None)

        logger.info(f"active submissions: {docs}")

        grouped: dict[str, list[Submission]] = defaultdict(list)
        for doc in docs:
            grouped[doc["hotkey"]].extend(
                Submission(**d) for d in doc.get("submissions", [])
            )

        await asyncio.gather(
            *[
                self._update_hotkey_performances(hk, subs, interval_key)
                for hk, subs in grouped.items()
            ]
        )
        logger.success("performance_update_complete", extra={"interval": interval_key})

    # ─────────────────── Scoring / Weights ───────
    async def _hotkey_scores(self) -> Dict[str, float]:
        perfs = await self._performances.find().to_list(None)
        logger.info(f"perfs: {perfs}")
        grouped: dict[str, list[Performance]] = defaultdict(list)
        for doc in perfs:
            grouped[doc["hotkey"]].append(Performance(**doc))

        scores = {hk: sum(p.get_score() for p in pl) for hk, pl in grouped.items()}
        logger.info(f"scores: {scores}")
        return scores

    async def calculate_and_set_weights(self) -> None:
        try:
            scores = await self._hotkey_scores()
            if not scores:
                logger.warning("no_scores_skipping_weight_set")
                return
    
            uids, weights = zip(
                *[
                    (self._uid_of_hotkey[hk], sc)
                    for hk, sc in scores.items()
                    if hk in self._uid_of_hotkey
                ]
            )
    
            uint_uids, uint_weights = (
                bt.utils.weight_utils.convert_weights_and_uids_for_emit(
                    uids=np.fromiter(uids, dtype=np.int32),
                    weights=np.fromiter(weights, dtype=np.float32),
                )
            )
            logger.info(f"UIDS: {uint_uids}, WEIGHTS: {uint_weights}")
            result = await self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.netuid,
                uids=uint_uids,
                weights=uint_weights,
                version_key=CONFIG.version_key,
            )
            (
                logger.success(f"weights_set_success: {result}")
                if result[0]
                else logger.error(f"weights_set_failed: {result}")
            )
        except Exception as e:
            logger.error(f"Got error: {e}")

    # ─────────────────── Main loop ───────────────
    async def run(self) -> None:
        logger.info(
            "validator_loop_start",
            extra={
                "update_interval": CONFIG.submission_update_interval,
                "set_weights_interval": CONFIG.set_weights_interval,
            },
        )

        async def _periodical_task() -> None:
            while True:
                await self.calculate_and_set_weights()
                await asyncio.sleep(CONFIG.set_weights_interval)

        asyncio.create_task(_periodical_task())

        while True:
            cycle_start = datetime.utcnow()
            try:
                await self.update_all_submissions()
                logger.info(f"active content ids: {self._active_content_ids}")
                await self.update_performance_metrics(self._active_content_ids)
                self._active_content_ids.clear()
            except Exception as exc:
                logger.exception("validator_cycle_error", exc_info=exc)

            elapsed = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info("validator_cycle_complete", extra={"seconds": elapsed})
            await asyncio.sleep(CONFIG.submission_update_interval)
