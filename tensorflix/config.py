from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # ─────────────────── General ────────────────────
    netuid: int = 89
    allowed_platforms: tuple[str] = ("youtube/video",)
    submission_update_interval: int = Field(60 * 60 * 2, description="seconds")
    set_weights_interval: int = Field(60 * 20, description="seconds")
    max_int_weight: int = 65_535
    version_key: int = 0  # bump on scoring-logic changes
    ai_generated_score_threshold: float = 0.3

    # ─────────────────── Services ───────────────────
    service_platform_tracker_url: str = "http://localhost:12001"
    service_ai_detector_url: str = "http://localhost:12002"

    # ─────────────────── MongoDB  ───────────────────
    mongodb_uri: str = Field(default="mongodb://localhost:27017/", env="MONGODB_URI")

    # ─────────────────── Derived helpers ────────────
    @property
    def substrate_url(self) -> str:
        return {
            "finney": "wss://entrypoint-finney.opentensor.ai:443",
            "testnet": "wss://test.finney.opentensor.ai:443",
        }[self.subtensor_network]

    def get_signature_post(self, hotkey: str) -> str:
        return f"Made with @infinitevibe.ai on #bittensor --- {hotkey[-5:]}"


CONFIG = Config()

print(CONFIG)
