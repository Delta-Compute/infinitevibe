from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadataRequest,
    YoutubeVideoMetadata,
)
from fastapi import FastAPI
import os
import httpx


app = FastAPI()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


@app.get("/youtube/video/{video_id}")
async def get_youtube_video_metadata(video_id: str):
    request = YoutubeVideoMetadataRequest(video_id=video_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(request.get_request_url(YOUTUBE_API_KEY), timeout=1)
    return YoutubeVideoMetadata.from_response(response.json())
