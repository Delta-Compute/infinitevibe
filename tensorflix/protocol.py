from __future__ import annotations

import json
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from tensorflix.config import CONFIG
from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadata,
    InstagramPostMetadata,
)
from tensorflix.models.brief import BriefCommitMessage

Metric = YoutubeVideoMetadata | InstagramPostMetadata


# ────────────────────── Performance ─────────────────


class Performance(BaseModel):
    hotkey: str
    content_id: str
    platform_metrics_by_interval: dict[str, Metric]

    def get_score(self, *, alpha: float = 0.95) -> float:
        logger.info(f"EMA calculation for {self.hotkey[:8]}/{self.content_id}... ({len(self.platform_metrics_by_interval)} intervals)")
        
        score = 0.0
        prev_metric_value = None
        processed_intervals = 0
        skipped_intervals = 0
        reset_count = 0
        
        for interval_key in sorted(self.platform_metrics_by_interval):
            metric = self.platform_metrics_by_interval[interval_key]
            
            # Check platform allowlist
            if metric.platform_name not in CONFIG.allowed_platforms:
                skipped_intervals += 1
                continue
            
            # Validate metric
            signature_valid = metric.check_signature(self.hotkey)
            ai_score_valid = metric.ai_score > CONFIG.ai_generated_score_threshold
            
            if signature_valid and ai_score_valid:
                current_metric_value = metric.to_scalar()
                
                if prev_metric_value is not None:
                    # Calculate incremental improvement (only score when we have multiple intervals)
                    incremental_score = current_metric_value - prev_metric_value
                    score = incremental_score * alpha + score * (1 - alpha)
                    
                    improvement_type = "↗" if incremental_score > 0 else "↘" if incremental_score < 0 else "→"
                    logger.info(f"{interval_key}: {improvement_type} {incremental_score:.4f} (EMA: {score:.4f})")
                else:
                    # First valid metric - establish baseline but don't score
                    logger.info(f"{interval_key}: baseline {current_metric_value:.4f} (no score)")
                
                prev_metric_value = current_metric_value
                processed_intervals += 1
                
            else:
                # Reset chain on validation failure
                logger.info(f"{interval_key}: validation failed - resetting chain")
                score = 0.0
                prev_metric_value = None
                reset_count += 1
                skipped_intervals += 1
        
        logger.info(f"Final score: {score:.4f} ({processed_intervals} processed, {skipped_intervals} skipped, {reset_count} resets)")
        return score
# ────────────────────── Submissions ─────────────────


class Submission(BaseModel):
    content_id: str
    platform: Literal["youtube/video", "instagram/reel", "instagram/post"]
    direct_video_url: str
    checked_for_ai: bool = False
    checked_for_content_matching: bool = False
    contains_subnet_tag: bool = True

    def __hash__(self) -> int:
        return hash((self.platform, self.content_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Submission):
            return False
        return (self.platform, self.content_id) == (other.platform, other.content_id)


# ────────────────────── Peer metadata ───────────────


class PeerMetadata(BaseModel):
    uid: int
    hotkey: str
    commit: str
    submissions: list[Submission] = Field(default_factory=list)
    brief_commit: BriefCommitMessage | None = Field(default=None)

    def __repr__(self) -> str:  # noqa: D401
        return (
            f"PeerMetadata(uid={self.uid}, hotkey={self.hotkey[:8]}…, "
            f"commit={self.commit}, submissions={len(self.submissions)}, "
            f"brief={'Yes' if self.brief_commit else 'No'})"
        )

    @model_validator(mode="after")
    def _validate_commit(cls, v: "PeerMetadata") -> "PeerMetadata":
        # First check if it's a brief submission format
        brief_commit = BriefCommitMessage.parse(v.commit)
        if brief_commit:
            v.brief_commit = brief_commit
            logger.info(f"Brief submission detected: {brief_commit.brief_id} - {brief_commit.submission_type}")
            return v
        
        # Otherwise validate as normal gist format
        if ":" not in v.commit:
            logger.warning(f"commit_format_error: {v.commit}")
            v.commit = ""
        return v

    async def update_submissions(self) -> None:
        # Skip if this is a brief submission
        if self.brief_commit:
            logger.debug(f"Skipping gist fetch for brief submission {self.brief_commit.brief_id}")
            return
            
        try:
            username, gist_id = self.commit.split(":", 1)
            url = f"https://gist.githubusercontent.com/{username}/{gist_id}/raw"
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url)
                r.raise_for_status()

            new_subs: list[Submission] = []
            for line in r.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    sub = Submission.model_validate_json(line)
                except Exception as exc:
                    logger.warning(
                        "submission_parse_error",
                        exc_info=exc,
                        extra={"uid": self.uid, "raw": line},
                    )
                    continue
                if sub.platform not in CONFIG.allowed_platforms:
                    logger.trace("submission_platform_ignored", extra=sub.model_dump())
                    continue
                new_subs.append(sub)

            self.submissions = new_subs
        except Exception as exc:
            logger.warning(
                "peer_submissions_refresh_error",
                exc_info=exc,
                extra={"uid": self.uid},
            )
            self.submissions = []
