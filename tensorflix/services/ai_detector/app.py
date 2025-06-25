import os
import tempfile
import random
import shutil
import requests
import cv2
import hashlib
import json
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from starlette.responses import JSONResponse
from loguru import logger
import redis
from redis.exceptions import RedisError

SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = 60 * 60 * 24 * 7

if not (SIGHTENGINE_USER and SIGHTENGINE_SECRET):
    raise RuntimeError("Set SIGHTENGINE_USER and SIGHTENGINE_SECRET env vars")

app = FastAPI()

# Redis client setup
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
    redis_client = None


class DetectResult(BaseModel):
    mean_ai_generated: float
    per_frame: List[float]
    cached: bool = False


def generate_cache_key(url: str, num_frames: int = 10) -> str:
    """Generate a cache key based on URL and parameters"""
    cache_data = f"{url}:{num_frames}"
    return f"video_detect:{hashlib.md5(cache_data.encode()).hexdigest()}"


def get_from_cache(cache_key: str) -> Optional[DetectResult]:
    """Retrieve cached result"""
    if not redis_client:
        return None
    
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            logger.info(f"Cache hit for key: {cache_key}")
            return DetectResult(**data, cached=True)
    except (RedisError, json.JSONDecodeError) as e:
        logger.error(f"Cache retrieval error: {e}")
    
    return None


def set_cache(cache_key: str, result: DetectResult) -> None:
    """Store result in cache"""
    if not redis_client:
        return
    
    try:
        # Don't store the 'cached' flag in cache
        cache_data = {
            "mean_ai_generated": result.mean_ai_generated,
            "per_frame": result.per_frame
        }
        redis_client.setex(
            cache_key, 
            CACHE_TTL, 
            json.dumps(cache_data)
        )
        logger.info(f"Cached result for key: {cache_key}")
    except RedisError as e:
        logger.error(f"Cache storage error: {e}")


def generate_frame_cache_key(frame_hash: str) -> str:
    """Generate cache key for individual frame analysis"""
    return f"frame_detect:{frame_hash}"


def get_frame_hash(frame) -> str:
    """Generate hash for a frame to use as cache key"""
    # Convert frame to bytes and hash
    frame_bytes = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))[1].tobytes()
    return hashlib.md5(frame_bytes).hexdigest()


def get_frame_from_cache(frame_hash: str) -> Optional[float]:
    """Get cached frame analysis result"""
    if not redis_client:
        return None
    
    try:
        cache_key = generate_frame_cache_key(frame_hash)
        cached_prob = redis_client.get(cache_key)
        if cached_prob is not None:
            logger.info(f"Frame cache hit: {frame_hash}")
            return float(cached_prob)
    except (RedisError, ValueError) as e:
        logger.error(f"Frame cache retrieval error: {e}")
    
    return None


def set_frame_cache(frame_hash: str, prob: float) -> None:
    """Cache individual frame analysis result"""
    if not redis_client:
        return
    
    try:
        cache_key = generate_frame_cache_key(frame_hash)
        redis_client.setex(cache_key, CACHE_TTL, str(prob))
        logger.info(f"Cached frame result: {frame_hash}")
    except RedisError as e:
        logger.error(f"Frame cache storage error: {e}")


def download_video(url: str, dest_path: str):
    r = requests.get(url, stream=True, timeout=180)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(r.raw, f)


def get_random_frames(video_path: str, num_frames: int = 10):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video file")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        cap.release()
        raise RuntimeError("No frames in video")

    # Use a fixed seed for reproducible frame selection for same video
    # This ensures same frames are selected for caching consistency
    random.seed(hash(video_path) % (2**32))
    frame_indices = sorted(
        random.sample(range(total_frames), min(num_frames, total_frames))
    )
    frames = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        # Convert BGR to RGB for consistency
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(frame)
    cap.release()
    return frames


def save_temp_image(frame):
    temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    cv2.imwrite(temp_img.name, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    return temp_img.name


def query_sightengine(image_path: str):
    url = "https://api.sightengine.com/1.0/check.json"
    files = {"media": open(image_path, "rb")}
    data = {
        "models": "genai",
        "api_user": SIGHTENGINE_USER,
        "api_secret": SIGHTENGINE_SECRET,
    }
    resp = requests.post(url, files=files, data=data)
    files["media"].close()
    if resp.status_code != 200:
        raise RuntimeError(f"API error: {resp.text}")
    result = resp.json()
    if result.get("status") != "success":
        raise RuntimeError(f"API failure: {result}")
    prob = float(result["type"].get("ai_generated", 0.0))
    return prob


@app.post("/detect", response_model=DetectResult)
def detect(url: str = Query(..., description="URL to video"), num_frames: int = Query(10, description="Number of frames to analyze")):
    url = url.replace("https://pub-https://pub-", "https://pub-")
    logger.info(f"Detecting {url}")
    
    # Check cache first
    cache_key = generate_cache_key(url, num_frames)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        logger.info("Returning cached result")
        return cached_result
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
        try:
            download_video(url, tmp_video.name)
            logger.info(f"Downloaded video to {tmp_video.name}")
            frames = get_random_frames(tmp_video.name, num_frames)
            logger.info(f"Got {len(frames)} frames")
            
            ai_probs = []
            cache_hits = 0
            
            for frame in frames:
                # Check if this frame has been analyzed before
                frame_hash = get_frame_hash(frame)
                cached_prob = get_frame_from_cache(frame_hash)
                
                if cached_prob is not None:
                    ai_probs.append(cached_prob)
                    cache_hits += 1
                    continue
                
                # Analyze frame with SightEngine API
                img_path = save_temp_image(frame)
                try:
                    prob = query_sightengine(img_path)
                    logger.info(f"Got prob {prob}")
                    ai_probs.append(prob)
                    
                    # Cache the frame result
                    set_frame_cache(frame_hash, prob)
                    
                except Exception as e:
                    logger.error(f"Got error: {e}")
                    continue
                finally:
                    os.unlink(img_path)
            
            logger.info(f"Frame cache hits: {cache_hits}/{len(frames)}")
            
            if not ai_probs:
                mean_prob = 0.969
            else:
                mean_prob = sum(ai_probs) / len(ai_probs)
            
            logger.info(f"Mean prob {mean_prob}")
            
            result = DetectResult(mean_ai_generated=mean_prob, per_frame=ai_probs, cached=False)
            
            # Cache the final result
            set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            try:
                os.unlink(tmp_video.name)
            except Exception:
                pass


@app.get("/cache/stats")
def cache_stats():
    """Get cache statistics"""
    if not redis_client:
        return {"error": "Redis not available"}
    
    try:
        info = redis_client.info()
        video_keys = len(redis_client.keys("video_detect:*"))
        frame_keys = len(redis_client.keys("frame_detect:*"))
        
        return {
            "redis_connected": True,
            "total_keys": info.get("db0", {}).get("keys", 0),
            "video_cache_entries": video_keys,
            "frame_cache_entries": frame_keys,
            "memory_usage": info.get("used_memory_human", "N/A")
        }
    except RedisError as e:
        return {"error": f"Redis error: {e}"}


@app.delete("/cache/clear")
def clear_cache():
    """Clear all cache entries"""
    if not redis_client:
        return {"error": "Redis not available"}
    
    try:
        video_keys = redis_client.keys("video_detect:*")
        frame_keys = redis_client.keys("frame_detect:*")
        all_keys = video_keys + frame_keys
        
        if all_keys:
            deleted = redis_client.delete(*all_keys)
            return {"message": f"Cleared {deleted} cache entries"}
        else:
            return {"message": "No cache entries to clear"}
    except RedisError as e:
        return {"error": f"Redis error: {e}"}