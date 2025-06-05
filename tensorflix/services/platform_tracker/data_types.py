from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional
from utils import filter_AI_video, filter_caption_video, download_video


class InstagramPostMetadata(BaseModel):
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
    published_at: datetime
    type: str
    url: str
    video_duration: int = Field(alias="videoDuration")
    video_play_count: int = Field(alias="videoPlayCount")
    video_view_count: int = Field(alias="videoViewCount")
    video_play_url: str = Field(alias="videoUrl")

    @field_validator("video_duration", mode="before")
    @classmethod
    def convert_video_duration(cls, v):
        if isinstance(v, float):
            return int(v)
        return v

    @classmethod
    def from_response(cls, response: dict) -> "InstagramPostMetadata":
        # Convert timestamp string to datetime
        response["published_at"] = datetime.strptime(
            response["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        return cls.model_validate(response)

    def to_response(self) -> dict:
        """Convert to response dict without alias keys."""
        return self.model_dump(exclude_none=True, by_alias=False)

    def to_scalar(self) -> float:
        return (self.comment_count + self.like_count + self.video_view_count) / 3
    def validate_caption(self) -> bool:
        return filter_caption_video(self.caption)

class InstagramPostMetadataRequest(BaseModel):
    content_id: str

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
    def get_video(self):
        video_url = f"https://www.instagram.com/reel/{self.content_id}"
        return download_video(video_url)
    def get_instagram_metadata(self):
        #Todo: get metadata from instagram
        pass

class YoutubeVideoMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    description: str
    thumbnail_url: str
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    tags: Optional[list[str]] = None

    @classmethod
    def from_response(cls, response: dict) -> "YoutubeVideoMetadata":
        """Extract data from nested YouTube API response structure."""
        if not response.get("items") or len(response["items"]) == 0:
            raise ValueError("No video data found in response")

        video_data = response["items"][0]
        snippet = video_data.get("snippet", {})
        statistics = video_data.get("statistics", {})

        # Extract the nested data
        extracted_data = {
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "thumbnail_url": snippet.get("thumbnails", {})
            .get("default", {})
            .get("url"),
            "published_at": datetime.strptime(
                snippet.get("publishedAt", ""), "%Y-%m-%dT%H:%M:%SZ"
            ),
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
            "tags": snippet.get("tags", []),
        }

        return cls.model_validate(extracted_data)

    def to_response(self) -> dict:
        """Convert to response dict."""
        return self.model_dump(exclude_none=True)

    def to_scalar(self) -> float:
        return (self.view_count + self.like_count + self.comment_count) / 3

    def validate_caption(self) -> bool:
        return filter_caption_video(self.description)


class YoutubeVideoMetadataRequest(BaseModel):
    content_id: str

    def get_request_url(self, api_key: str) -> str:
        return f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={self.content_id}&key={api_key}"
    def get_video(self):
        video_url = f"https://www.youtube.com/watch?v={self.content_id}"
        return download_video(video_url)
        
    def get_youtube_metadata(self):
        #Todo: get metadata from youtube
        pass
