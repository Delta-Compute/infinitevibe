from fastapi import FastAPI, HTTPException, Depends
from apify_client import ApifyClientAsync
from loguru import logger

from tensorflix.services.platform_tracker.trackers import (
    PlatformTrackerRegistry,
    YouTubeTracker,
    InstagramTracker,
    PlatformTracker,
)
from tensorflix.services.platform_tracker.config import config
from tensorflix.services.platform_tracker.data_types import (
    MetricsRequest,
    get_platform_link,
)

app = FastAPI()

# Global registry instance
tracker_registry = PlatformTrackerRegistry()


def setup_trackers():
    """Initialize and register all platform trackers."""
    apify_client = ApifyClientAsync(config.apify_api_key)
    youtube_tracker = YouTubeTracker(apify_client=apify_client)
    tracker_registry.register("youtube", youtube_tracker)
    instagram_tracker = InstagramTracker(apify_client=apify_client)
    tracker_registry.register("instagram", instagram_tracker)


def get_tracker_for_platform(platform: str) -> PlatformTracker:
    """Dependency to get tracker for a specific platform."""
    if not tracker_registry.is_platform_supported(platform):
        raise HTTPException(
            status_code=400,
            detail=f"Platform '{platform}' is not supported. "
            f"Supported platforms: {tracker_registry.get_supported_platforms()}",
        )
    return tracker_registry.get_tracker(platform)


@app.on_event("startup")
async def startup_event():
    """Initialize trackers on startup."""
    setup_trackers()
    logger.info(
        f"Platform tracker service started. Supported platforms: {tracker_registry.get_supported_platforms()}"
    )


@app.post("/get_metrics")
async def get_content_metadata(
    request: MetricsRequest,
) -> dict:
    """
    Get metadata for content from any supported platform.

    Args:
        request: The metrics request containing platform, content type, and content ID

    Returns:
        Dictionary containing content metadata
    """
    try:
        tracker = tracker_registry.get_tracker(request.platform)
        supported_types = tracker.get_supported_content_types()
        if request.content_type not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Content type '{request.content_type}' not supported for platform '{request.platform}'. "
                f"Supported types: {supported_types}",
            )

        metadata = await tracker.get_metadata(request.content_id)
        if request.get_direct_url:
            metadata.crawl_video_url = await tracker.get_direct_url(
                get_platform_link(
                    request.platform, request.content_id, request.content_type
                ),
                tracker.apify_client,
            )
        return metadata.to_response()

    except Exception as e:
        logger.error(
            f"Error getting metadata for {request.platform}/{request.content_type}/{request.content_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")


@app.get("/platforms")
async def get_supported_platforms() -> dict:
    """Get list of supported platforms and their content types."""
    platforms_info = {}
    for platform in tracker_registry.get_supported_platforms():
        tracker = tracker_registry.get_tracker(platform)
        platforms_info[platform] = {
            "supported_content_types": tracker.get_supported_content_types()
        }
    return {"supported_platforms": platforms_info}


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "supported_platforms": tracker_registry.get_supported_platforms(),
    }
