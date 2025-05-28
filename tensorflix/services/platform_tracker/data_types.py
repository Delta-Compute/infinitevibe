from pydantic import BaseModel
from datetime import datetime


class YoutubeVideoMetadata(BaseModel):
    title: str
    description: str
    thumbnail_url: str
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    tags: list[str]

    @classmethod
    def from_response(cls, response: dict) -> "YoutubeVideoMetadata":
        return cls(
            title=response["items"][0]["snippet"]["title"],
            description=response["items"][0]["snippet"]["description"],
            thumbnail_url=response["items"][0]["snippet"]["thumbnails"]["default"][
                "url"
            ],
            published_at=datetime.strptime(
                response["items"][0]["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            view_count=response["items"][0]["statistics"]["viewCount"],
            like_count=response["items"][0]["statistics"]["likeCount"],
            comment_count=response["items"][0]["statistics"]["commentCount"],
            tags=response["items"][0]["snippet"]["tags"],
        )


class YoutubeVideoMetadataRequest(BaseModel):
    video_id: str

    def get_request_url(self, api_key: str) -> str:
        return f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={self.video_id}&key={api_key}"


if __name__ == "__main__":
    import requests
    import os

    api_key = os.getenv("YOUTUBE_API_KEY")
    request = YoutubeVideoMetadataRequest(video_id="4Y4YSpF6d6w")
    url = request.get_request_url(api_key)
    response = requests.get(url)
    metadata = YoutubeVideoMetadata.from_response(response.json())
    print(metadata)
