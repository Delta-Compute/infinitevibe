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

app = FastAPI()

# Global registry instance
tracker_registry = PlatformTrackerRegistry()


def setup_trackers():
    """Initialize and register all platform trackers."""
    # Initialize YouTube tracker
    if config.is_youtube_enabled():
        youtube_tracker = YouTubeTracker(api_key=config.youtube_api_key)
        tracker_registry.register("youtube", youtube_tracker)
    else:
        logger.warning("YouTube API key not found - YouTube tracking disabled")

    # Initialize Instagram tracker
    if config.is_instagram_enabled():
        apify_client = ApifyClientAsync(config.apify_api_key)
        instagram_tracker = InstagramTracker(apify_client=apify_client)
        tracker_registry.register("instagram", instagram_tracker)
    else:
        logger.warning("Apify API key not found - Instagram tracking disabled")


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


@app.get("/get_metrics/{platform}/{content_type}/{content_id}")
async def get_content_metadata(
    platform: str,
    content_type: str,
    content_id: str,
    tracker: PlatformTracker = Depends(get_tracker_for_platform),
) -> dict:
    """
    Get metadata for content from any supported platform.

    Args:
        platform: The platform name (e.g., 'youtube', 'instagram')
        content_type: The type of content (e.g., 'video', 'post', 'reel')
        content_id: The unique identifier for the content

    Returns:
        Dictionary containing content metadata
    """
    try:
        # Validate content type is supported by the platform
        supported_types = tracker.get_supported_content_types()
        if content_type not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Content type '{content_type}' not supported for platform '{platform}'. "
                f"Supported types: {supported_types}",
            )

        # Get metadata using the appropriate tracker
        metadata = await tracker.get_metadata(content_id)
        return metadata

    except Exception as e:
        logger.error(
            f"Error getting metadata for {platform}/{content_type}/{content_id}: {str(e)}"
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
