from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional
from tensorflix.config import CONFIG
from dateutil import parser


def get_platform_link(platform: str, content_id: str, content_type: str) -> str:
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={content_id}"
    elif platform == "instagram":
        if content_type == "post":
            return f"https://www.instagram.com/p/{content_id}"
        elif content_type == "reel":
            return f"https://www.instagram.com/reel/{content_id}"
        elif content_type == "story":
            return f"https://www.instagram.com/stories/{content_id}"
        else:
            raise ValueError(f"Invalid content type: {content_type}")
    else:
        raise ValueError(f"Invalid platform: {platform}")


class InstagramPostMetadata(BaseModel):
    platform_name: str = "instagram/reel"
    model_config = ConfigDict(populate_by_name=True)
    caption: str
    comment_count: int = Field(alias="commentsCount")
    like_count: int = Field(alias="likesCount")
    dimension_height: int = Field(alias="dimensionsHeight")
    dimension_width: int = Field(alias="dimensionsWidth")
    display_url: str = Field(alias="displayUrl")
    first_comment: str = Field(alias="firstComment")
    is_comment_disabled: bool = Field(alias="isCommentsDisabled")
    owner_username: str = Field(alias="ownerUsername")
    product_type: str = Field(alias="productType")
    published_at: datetime = Field(alias="timestamp")
    type: str
    url: str
    video_duration: int = Field(alias="videoDuration")
    video_play_count: int = Field(alias="videoPlayCount")
    video_view_count: int = Field(alias="videoViewCount")
    crawl_video_url: str = Field(alias="videoUrl", default="")

    ai_score: float = 0.0

    @field_validator("video_duration", mode="before")
    @classmethod
    def convert_video_duration(cls, v):
        if isinstance(v, float):
            return int(v)
        return v

    @classmethod
    def from_response(cls, response: dict) -> "InstagramPostMetadata":
        # Convert timestamp string to datetime
        dt = response.get("published_at") or response.get("timestamp")
        response["published_at"] = parser.parse(dt)
        return cls.model_validate(response)

    def to_response(self) -> dict:
        """Convert to response dict without alias keys."""
        return self.model_dump(exclude_none=True, by_alias=False)

    def to_scalar(self) -> float:
        return self.video_play_count

    def check_signature(self, hotkey: str) -> bool:
        return CONFIG.get_signature_post(hotkey).lower() in self.caption.lower()


class InstagramPostMetadataRequest(BaseModel):
    content_id: str
    get_direct_url: bool = False

    def get_apify_payload(self) -> dict:
        return {
            "addParentData": False,
            "directUrls": [f"https://www.instagram.com/reel/{self.content_id}"],
            "enhanceUserSearchWithFacebookPage": False,
            "isUserReelFeedURL": False,
            "isUserTaggedFeedURL": False,
            "resultsLimit": 1,
            "resultsType": "details",
            "searchLimit": 1,
            "searchType": "hashtag",
        }


class YoutubeVideoMetadata(BaseModel):
    platform_name: str = "youtube/video"
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(alias="title")
    caption: str = Field(alias="text")
    thumbnail_url: str = Field(alias="thumbnailUrl")
    published_at: datetime = Field(alias="date")
    view_count: int = Field(alias="viewCount")
    like_count: int = Field(alias="likes")
    comment_count: int = Field(alias="commentsCount")
    crawl_video_url: str = ""

    ai_score: float = 0.0

    @classmethod
    def from_response(cls, response: dict) -> "YoutubeVideoMetadata":
        # Convert timestamp string to datetime
        dt = response.get("published_at") or response.get("date")
        response["published_at"] = parser.parse(dt)
        return cls.model_validate(response)

    def to_response(self) -> dict:
        """Convert to response dict."""
        return self.model_dump(exclude_none=True)

    def to_scalar(self) -> float:
        return self.view_count

    def check_signature(self, hotkey: str) -> bool:
        return CONFIG.get_signature_post(hotkey).lower() in self.caption.lower()


class YoutubeVideoMetadataRequest(BaseModel):
    content_id: str
    get_direct_url: bool = False

    def get_apify_payload(self) -> dict:
        return {
            "maxResults": 1,
            "startUrls": [
                {
                    "url": f"https://www.youtube.com/watch?v={self.content_id}",
                    "method": "GET",
                }
            ],
        }


class MetricsRequest(BaseModel):
    """Base model for metrics request."""

    platform: str
    content_type: str
    content_id: str
    get_direct_url: bool = False
