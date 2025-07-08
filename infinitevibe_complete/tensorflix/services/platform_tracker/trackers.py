from abc import ABC, abstractmethod
from typing import Dict, Any, Type
import httpx
from apify_client import ApifyClientAsync
from loguru import logger

from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadataRequest,
    YoutubeVideoMetadata,
    InstagramPostMetadataRequest,
    InstagramPostMetadata,
)
from tensorflix.services.platform_tracker.config import config


class PlatformTracker(ABC):
    """Abstract base class for platform content trackers."""

    @abstractmethod
    async def get_metadata(self, content_id: str) -> Dict[str, Any]:
        """Get metadata for a piece of content."""
        pass

    @abstractmethod
    def get_supported_content_types(self) -> list[str]:
        """Return list of supported content types for this platform."""
        pass

    async def get_direct_url(
        self, platform_link: str, apify_client: ApifyClientAsync
    ) -> str:
        """Get direct url for a piece of content."""
        payload = {
            "link": platform_link,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }
        run = await apify_client.actor(config.downloader_actor_id).call(
            run_input=payload
        )
        response = await apify_client.dataset(run["defaultDatasetId"]).list_items()
        item = response.items[0]
        medias = item["result"]["medias"]
        for media in medias:
            if media["type"] == "video":
                return media["url"]
        return None


class YouTubeTracker(PlatformTracker):
    """YouTube platform tracker implementation."""

    def __init__(self, apify_client: ApifyClientAsync):
        self.apify_client = apify_client
        self.actor_id = config.youtube_actor_id
        self.actor = self.apify_client.actor(self.actor_id)

    async def get_metadata(self, content_id: str) -> YoutubeVideoMetadata:
        """Get YouTube video metadata."""
        logger.info(f"Getting YouTube video metadata for {content_id}")

        request = YoutubeVideoMetadataRequest(content_id=content_id)
        apify_payload = request.get_apify_payload()
        print(apify_payload)

        run = await self.actor.call(run_input=apify_payload)
        response = await self.apify_client.dataset(run["defaultDatasetId"]).list_items()

        logger.info(response.items[0])
        return YoutubeVideoMetadata.from_response(response.items[0])

    def get_supported_content_types(self) -> list[str]:
        return ["video"]


class InstagramTracker(PlatformTracker):
    """Instagram platform tracker implementation."""

    def __init__(self, apify_client: ApifyClientAsync):
        self.apify_client = apify_client
        self.actor_id = config.instagram_actor_id
        self.follower_count_actor_id = config.instagram_follower_count_actor_id
        self.actor = self.apify_client.actor(self.actor_id)
    async def get_metadata(self, content_id: str) -> InstagramPostMetadata:
        """Get Instagram post metadata."""
        logger.info(f"Getting Instagram post metadata for {content_id}")

        request = InstagramPostMetadataRequest(content_id=content_id)
        apify_payload = request.get_apify_payload()

        run = await self.apify_client.actor(self.actor_id).call(run_input=apify_payload)
        response = await self.apify_client.dataset(run["defaultDatasetId"]).list_items()
        post_data = response.items[0]
        owner_username = post_data.get("ownerUsername")

        follower_count = 0 
        if owner_username:
            logger.info(f"Getting follower count for owner: {owner_username}")
            try:
                follower_payload = {"usernames": [owner_username]}
                
                follower_run = await self.apify_client.actor(self.follower_count_actor_id).call(run_input=follower_payload)
                follower_response = await self.apify_client.dataset(follower_run["defaultDatasetId"]).list_items()
                if follower_response.items:
                    follower_count = follower_response.items[0].get("followerCount", 0)

            except Exception as e:
                logger.error(f"Failed to fetch follower count for {owner_username}: {e}")
        
        post_data["ownerFollowersCount"] = follower_count

        logger.info(post_data)
        metadata = InstagramPostMetadata.from_response(post_data)
        return metadata

    def get_supported_content_types(self) -> list[str]:
        return ["post", "reel", "story"]


class PlatformTrackerRegistry:
    """Registry for managing platform trackers."""

    def __init__(self):
        self._trackers: Dict[str, PlatformTracker] = {}

    def register(self, platform: str, tracker: PlatformTracker) -> None:
        """Register a tracker for a platform."""
        self._trackers[platform.lower()] = tracker
        logger.info(f"Registered tracker for platform: {platform}")

    def get_tracker(self, platform: str) -> PlatformTracker:
        """Get tracker for a platform."""
        tracker = self._trackers.get(platform.lower())
        if not tracker:
            raise ValueError(f"No tracker registered for platform: {platform}")
        return tracker

    def get_supported_platforms(self) -> list[str]:
        """Get list of supported platforms."""
        return list(self._trackers.keys())

    def is_platform_supported(self, platform: str) -> bool:
        """Check if platform is supported."""
        return platform.lower() in self._trackers
