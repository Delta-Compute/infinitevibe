import os
import json
import hashlib
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from apify_client import ApifyClientAsync
from loguru import logger
import redis
from redis.exceptions import RedisError
from typing import Optional

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

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 60 * 60  # 1 hour in seconds

# Redis client setup
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established for platform tracker")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
    redis_client = None

# Global registry instance
tracker_registry = PlatformTrackerRegistry()


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle other non-serializable objects by converting to string
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def generate_cache_key(request: MetricsRequest) -> str:
    """Generate a cache key based on platform, content type, content ID, and get_direct_url flag"""
    cache_data = f"{request.platform}:{request.content_type}:{request.content_id}"
    return f"tracker_metrics:{hashlib.md5(cache_data.encode()).hexdigest()}"


def get_from_cache(cache_key: str) -> Optional[dict]:
    """Retrieve cached result"""
    if not redis_client:
        return None
    
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            logger.info(f"Cache hit for key: {cache_key}")
            return data
    except (RedisError, json.JSONDecodeError) as e:
        logger.error(f"Cache retrieval error: {e}")
    
    return None


def set_cache(cache_key: str, result: dict) -> None:
    """Store result in cache"""
    if not redis_client:
        return
    
    try:
        redis_client.setex(
            cache_key, 
            CACHE_TTL, 
            json.dumps(result, cls=DateTimeEncoder)
        )
        logger.info(f"Cached result for key: {cache_key}")
    except RedisError as e:
        logger.error(f"Cache storage error: {e}")
    except Exception as e:
        logger.error(f"JSON serialization error: {e}")


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
        # Check cache first
        cache_key = generate_cache_key(request)
        cached_result = get_from_cache(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for {request.platform}/{request.content_type}/{request.content_id}")
            return cached_result

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
        
        result = metadata.to_response()
        
        # Cache the result
        set_cache(cache_key, result)
        
        return result

    except Exception as e:
        logger.error(
            f"Error getting metadata for {request.platform}/{request.content_type}/{request.content_id}: {str(e)}"
        )

        traceback.print_exc()
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
        "redis_connected": redis_client is not None,
    }


@app.get("/cache/stats")
def cache_stats():
    """Get cache statistics"""
    if not redis_client:
        return {"error": "Redis not available"}
    
    try:
        info = redis_client.info()
        tracker_keys = len(redis_client.keys("tracker_metrics:*"))
        
        return {
            "redis_connected": True,
            "total_keys": info.get("db0", {}).get("keys", 0),
            "tracker_cache_entries": tracker_keys,
            "memory_usage": info.get("used_memory_human", "N/A"),
            "cache_ttl_seconds": CACHE_TTL
        }
    except RedisError as e:
        return {"error": f"Redis error: {e}"}


@app.delete("/cache/clear")
def clear_cache():
    """Clear all cache entries for tracker service"""
    if not redis_client:
        return {"error": "Redis not available"}
    
    try:
        tracker_keys = redis_client.keys("tracker_metrics:*")
        
        if tracker_keys:
            deleted = redis_client.delete(*tracker_keys)
            return {"message": f"Cleared {deleted} tracker cache entries"}
        else:
            return {"message": "No tracker cache entries to clear"}
    except RedisError as e:
        return {"error": f"Redis error: {e}"}
