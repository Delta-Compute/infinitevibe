from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class PlatformTrackerConfig(BaseSettings):
    """Configuration for the platform tracker service."""

    # API Keys
    apify_api_key: Optional[str] = Field(default=None, env="APIFY_API_KEY")

    # Service configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    timeout_seconds: int = Field(default=30, env="TIMEOUT_SECONDS")

    # Instagram specific settings
    instagram_actor_id: str = Field(
        default="RB9HEZitC8hIUXAha", env="INSTAGRAM_ACTOR_ID"
    )
    instagram_follower_count_actor_id: str = Field(
        default="7RQ4RlfRihUhflQtJ", env="INSTAGRAM_FOLLOWER_COUNT_ACTOR_ID"
    )
    youtube_actor_id: str = Field(default="h7sDV53CddomktSi5", env="YOUTUBE_ACTOR_ID")
    downloader_actor_id: str = Field(
        default="iZbsVYT4VfdMxoIPL", env="DOWNLOADER_ACTOR_ID"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


# Global config instance
config = PlatformTrackerConfig()
