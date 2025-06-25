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
        logger.info(f"🔗 Starting EMA chain calculation for hotkey: {self.hotkey}")
        logger.info(f"📊 Alpha (smoothing factor): {alpha}")
        logger.info(f"📈 Total intervals to process: {len(self.platform_metrics_by_interval)}")
        
        score = 0.0
        prev_metric_value = None
        processed_intervals = 0
        skipped_intervals = 0
        reset_count = 0
        
        # Track EMA evolution
        ema_history = []
        
        for interval_key in sorted(self.platform_metrics_by_interval):
            metric = self.platform_metrics_by_interval[interval_key]
            
            logger.info(f"⏰ Processing interval: {interval_key}")
            logger.info(f"🔧 Platform: {metric.platform_name}")
            
            # Check platform allowlist
            if metric.platform_name not in CONFIG.allowed_platforms:
                logger.info(f"⚠️  Platform '{metric.platform_name}' not in allowed platforms - SKIPPING")
                skipped_intervals += 1
                continue
            
            # Validate metric
            signature_valid = metric.check_signature(self.hotkey)
            ai_score_valid = metric.ai_score > CONFIG.ai_generated_score_threshold
            
            logger.info(f"✅ Signature valid: {signature_valid}")
            logger.info(f"🤖 AI score ({metric.ai_score}) > threshold ({CONFIG.ai_generated_score_threshold}): {ai_score_valid}")
            
            if signature_valid and ai_score_valid:
                current_metric_value = metric.to_scalar()
                logger.info(f"📊 Current metric value: {current_metric_value:.6f}")
                
                old_score = score
                
                if prev_metric_value is not None:
                    # Calculate incremental improvement
                    incremental_score = current_metric_value - prev_metric_value
                    logger.info(f"📈 Incremental improvement: {incremental_score:.6f}")
                    logger.info(f"🔄 EMA calculation: {incremental_score:.6f} * {alpha} + {score:.6f} * {1-alpha:.3f}")
                    
                    score = incremental_score * alpha + score * (1 - alpha)
                    
                    improvement_type = "📈 IMPROVEMENT" if incremental_score > 0 else "📉 DECLINE" if incremental_score < 0 else "➡️  STABLE"
                    logger.info(f"{improvement_type}: {abs(incremental_score):.6f}")
                    
                else:
                    logger.info(f"🆕 First valid metric - initializing EMA")
                    logger.info(f"🔄 EMA calculation: {current_metric_value:.6f} * {alpha} + {score:.6f} * {1-alpha:.3f}")
                    score = current_metric_value * alpha + score * (1 - alpha)
                
                # Log EMA evolution
                score_change = score - old_score
                logger.info(f"📊 EMA Score: {old_score:.6f} → {score:.6f} (Δ: {score_change:+.6f})")
                
                # Track history for trend analysis
                ema_history.append({
                    'interval': interval_key,
                    'metric_value': current_metric_value,
                    'incremental': incremental_score if prev_metric_value is not None else None,
                    'ema_score': score,
                    'score_change': score_change
                })
                
                prev_metric_value = current_metric_value
                processed_intervals += 1
                
            else:
                logger.info(f"❌ Metric validation failed - RESETTING EMA chain")
                logger.info(f"🔄 Score reset: {score:.6f} → 0.0")
                score = 0.0
                prev_metric_value = None
                reset_count += 1
                skipped_intervals += 1
        
        # Final summary
        logger.info(f"🏁 EMA Chain Summary:")
        logger.info(f"   📊 Final EMA Score: {score:.6f}")
        logger.info(f"   ✅ Processed intervals: {processed_intervals}")
        logger.info(f"   ⏭️  Skipped intervals: {skipped_intervals}")
        logger.info(f"   🔄 Chain resets: {reset_count}")
        logger.info(f"   📈 Chain efficiency: {(processed_intervals / len(self.platform_metrics_by_interval) * 100):.1f}%")
        
        # Log trend analysis if we have history
        if len(ema_history) > 1:
            logger.info(f"📊 EMA Trend Analysis:")
            
            # Calculate trend metrics
            positive_changes = sum(1 for h in ema_history if h['score_change'] > 0)
            negative_changes = sum(1 for h in ema_history if h['score_change'] < 0)
            
            logger.info(f"   📈 Positive EMA changes: {positive_changes}")
            logger.info(f"   📉 Negative EMA changes: {negative_changes}")
            
            # Show volatility
            score_changes = [h['score_change'] for h in ema_history]
            volatility = sum(abs(change) for change in score_changes) / len(score_changes)
            logger.info(f"   📊 Average volatility: {volatility:.6f}")
            
            # Show recent trend (last 3 intervals)
            recent_changes = score_changes[-3:]
            recent_trend = sum(recent_changes) / len(recent_changes)
            trend_direction = "📈 UPWARD" if recent_trend > 0 else "📉 DOWNWARD" if recent_trend < 0 else "➡️  FLAT"
            logger.info(f"   🎯 Recent trend: {trend_direction} ({recent_trend:+.6f})")
        
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

    def __repr__(self) -> str:  # noqa: D401
        return (
            f"PeerMetadata(uid={self.uid}, hotkey={self.hotkey[:8]}…, "
            f"commit={self.commit}, submissions={len(self.submissions)})"
        )

    @model_validator(mode="after")
    def _validate_commit(cls, v: "PeerMetadata") -> "PeerMetadata":
        if ":" not in v.commit:
            logger.warning(f"commit_format_error: {v.commit}")
            v.commit = ""
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
