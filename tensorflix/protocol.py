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

Metric = YoutubeVideoMetadata | InstagramPostMetadata


# ────────────────────── Performance ─────────────────


class Performance(BaseModel):
    hotkey: str
    content_id: str
    platform_metrics_by_interval: dict[str, Metric]

    def get_score(self, *, alpha: float = 0.95) -> float:
        score = 0.0
        for interval_key in sorted(self.platform_metrics_by_interval):
            score = self.platform_metrics_by_interval[
                interval_key
            ].to_scalar() * alpha + score * (1 - alpha)
        return score


# ────────────────────── Submissions ─────────────────


class Submission(BaseModel):
    content_id: str
    platform: Literal["youtube/video", "instagram/reel", "instagram/post"]
    direct_video_url: str

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

    def __repr__(self) -> str:  # noqa: D401
        return (
            f"PeerMetadata(uid={self.uid}, hotkey={self.hotkey[:8]}…, "
            f"commit={self.commit}, submissions={len(self.submissions)})"
        )

    @model_validator(mode="after")
    def _validate_commit(cls, v: "PeerMetadata") -> "PeerMetadata":
        if ":" not in v.commit:
            raise ValueError("commit must be in <username>:<gist_id> format")
        return v

    async def update_submissions(self) -> None:
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
            logger.debug(
                f"peer_submissions_refreshed: {self.uid} {len(self.submissions)}, sample: {self.submissions[:3]}"
            )
        except Exception as exc:
            logger.warning(
                "peer_submissions_refresh_error",
                exc_info=exc,
                extra={"uid": self.uid},
            )
            self.submissions = []
