import os
from typing import Optional
from pydantic import BaseSettings, Field


class PlatformTrackerConfig(BaseSettings):
    """Configuration for the platform tracker service."""

    # API Keys
    youtube_api_key: Optional[str] = Field(default=None, env="YOUTUBE_API_KEY")
    apify_api_key: Optional[str] = Field(default=None, env="APIFY_API_KEY")

    # Service configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    timeout_seconds: int = Field(default=30, env="TIMEOUT_SECONDS")

    # Instagram specific settings
    instagram_actor_id: str = Field(
        default="RB9HEZitC8hIUXAha", env="INSTAGRAM_ACTOR_ID"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False

    def is_youtube_enabled(self) -> bool:
        """Check if YouTube tracking is enabled."""
        return self.youtube_api_key is not None

    def is_instagram_enabled(self) -> bool:
        """Check if Instagram tracking is enabled."""
        return self.apify_api_key is not None


# Global config instance
config = PlatformTrackerConfig()
