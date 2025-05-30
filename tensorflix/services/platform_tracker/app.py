from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadataRequest,
    YoutubeVideoMetadata,
    InstagramPostMetadataRequest,
    InstagramPostMetadata,
)
from fastapi import FastAPI
import os
import httpx
from apify_client import ApifyClientAsync
from loguru import logger

app = FastAPI()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
APIFY_API_KEY = os.getenv("APIFY_API_KEY")

INSTA_APIFY_ACT_ID = "RB9HEZitC8hIUXAha"

APIFY_CLIENT = ApifyClientAsync(APIFY_API_KEY)


@app.get("/youtube/video/{video_id}")
async def get_youtube_video_metadata(video_id: str) -> dict:
    logger.info(f"Getting YouTube video metadata for {video_id}")
    request = YoutubeVideoMetadataRequest(video_id=video_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(request.get_request_url(YOUTUBE_API_KEY), timeout=1)

    logger.info(response.json())
    return YoutubeVideoMetadata.from_response(response.json()).to_response()


@app.get("/instagram/reel/{reel_id}")
async def get_instagram_reel_metadata(reel_id: str) -> dict:
    logger.info(f"Getting Instagram reel metadata for {reel_id}")
    request = InstagramPostMetadataRequest(reel_id=reel_id)
    apify_payload = request.get_apify_payload()
    run = await APIFY_CLIENT.actor("RB9HEZitC8hIUXAha").call(run_input=apify_payload)
    response = await APIFY_CLIENT.dataset(run["defaultDatasetId"]).list_items()
    logger.info(response.items[0])
    response = InstagramPostMetadata.from_response(response.items[0])
    return response.to_response()
