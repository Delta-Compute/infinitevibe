"""
Instagram API integration for fetching follower data.
"""

import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import httpx

from analyzers.base import FollowerData


class InstagramAPIError(Exception):
    """Custom exception for Instagram API errors"""
    pass


class InstagramFollowerFetcher:
    """
    Fetcher for Instagram follower data.
    
    This is a placeholder implementation. In production, you would need:
    1. Instagram Basic Display API access (limited)
    2. Instagram Graph API access (business accounts only)
    3. Third-party service (RapidAPI, etc.)
    4. Web scraping (check ToS compliance)
    """
    
    def __init__(self, api_key: Optional[str] = None, rate_limit_delay: float = 1.0):
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.session = httpx.AsyncClient()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
    
    async def get_account_info(self, username: str) -> Dict[str, Any]:
        """
        Get basic account information.
        
        Args:
            username: Instagram username
            
        Returns:
            Dictionary with account info
        """
        # Placeholder implementation
        # In production, implement actual API calls
        
        await asyncio.sleep(self.rate_limit_delay)  # Rate limiting
        
        # Mock response
        return {
            'username': username,
            'follower_count': random.randint(100, 10000),
            'following_count': random.randint(50, 1000),
            'posts_count': random.randint(10, 500),
            'is_verified': random.choice([True, False]),
            'is_business': random.choice([True, False]),
            'is_private': random.choice([True, False]),
            'bio': self._generate_mock_bio(),
            'profile_picture_url': f"https://example.com/{username}_profile.jpg"
        }
    
    async def get_followers(self, username: str, limit: int = 1000) -> List[FollowerData]:
        """
        Fetch followers for an Instagram account.
        
        Args:
            username: Instagram username
            limit: Maximum number of followers to fetch
            
        Returns:
            List of FollowerData objects
        """
        # In production, implement actual Instagram API calls
        # Example with Instagram Graph API:
        # url = f"https://graph.instagram.com/{user_id}/followers"
        # params = {"access_token": self.api_key, "limit": limit}
        # response = await self.session.get(url, params=params)
        
        # For now, generate mock data
        followers = []
        num_followers = min(limit, random.randint(50, 500))
        
        for i in range(num_followers):
            await asyncio.sleep(self.rate_limit_delay / 10)  # Simulated API delay
            
            follower = await self._create_mock_follower(i)
            followers.append(follower)
            
        return followers
    
    async def _create_mock_follower(self, index: int) -> FollowerData:
        """Create mock follower data for testing"""
        
        # Generate different types of accounts
        account_type = random.choice(['human', 'suspicious', 'bot'])
        
        if account_type == 'human':
            return FollowerData(
                username=self._generate_human_username(),
                follower_count=random.randint(100, 5000),
                following_count=random.randint(50, 800),
                posts_count=random.randint(20, 200),
                bio=self._generate_mock_bio(),
                profile_picture_url=f"https://example.com/user_{index}.jpg",
                is_verified=random.choice([True, False]),
                is_business=random.choice([True, False]),
                is_private=random.choice([True, False]),
                account_creation_date=datetime.now() - timedelta(days=random.randint(30, 1800)),
                last_post_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                location=random.choice([None, "New York", "Los Angeles", "London", "Tokyo"]),
                external_url=random.choice([None, f"https://example{index}.com"])
            )
        elif account_type == 'suspicious':
            return FollowerData(
                username=self._generate_suspicious_username(),
                follower_count=random.randint(5, 100),
                following_count=random.randint(1000, 3000),
                posts_count=random.randint(0, 10),
                bio=random.choice(["", "Follow for follow", "DM for promo"]),
                profile_picture_url=random.choice([None, f"https://example.com/generic_{index}.jpg"]),
                is_verified=False,
                is_business=False,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=random.randint(1, 60)),
                last_post_date=random.choice([None, datetime.now() - timedelta(days=random.randint(100, 500))]),
                location=None,
                external_url=None
            )
        else:  # bot
            return FollowerData(
                username=self._generate_bot_username(),
                follower_count=random.randint(0, 50),
                following_count=random.randint(1500, 2000),
                posts_count=random.randint(0, 3),
                bio="",
                profile_picture_url=None,
                is_verified=False,
                is_business=False,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                last_post_date=None,
                location=None,
                external_url=None
            )
    
    def _generate_human_username(self) -> str:
        """Generate realistic human username"""
        first_names = ["john", "sarah", "mike", "emma", "david", "lisa", "alex", "maria"]
        last_names = ["smith", "jones", "brown", "wilson", "garcia", "martinez"]
        suffixes = ["", "_photo", "_travel", "_art", "123", "_official"]
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        suffix = random.choice(suffixes)
        
        return f"{first}_{last}{suffix}"
    
    def _generate_suspicious_username(self) -> str:
        """Generate suspicious username patterns"""
        patterns = [
            f"user_{random.randint(1000, 9999)}",
            f"follow_{random.randint(100, 999)}",
            f"insta_{random.randint(10, 999)}_gram",
            f"{"".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=8))}"
        ]
        return random.choice(patterns)
    
    def _generate_bot_username(self) -> str:
        """Generate obvious bot username patterns"""
        patterns = [
            f"user{random.randint(100000, 999999)}",
            f"{''.join(random.choices('0123456789', k=10))}",
            f"bot_{random.randint(1000, 9999)}_account",
            f"{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))}"
        ]
        return random.choice(patterns)
    
    def _generate_mock_bio(self) -> str:
        """Generate mock bio text"""
        bios = [
            "Love photography and travel 📸✈️",
            "Coffee enthusiast ☕ | Dog lover 🐕",
            "Entrepreneur | Motivational speaker 💪",
            "Artist 🎨 | Based in NYC",
            "Fitness trainer | Healthy lifestyle 💪",
            "Food blogger 🍕 | Recipe creator",
            "Tech enthusiast | Gadget reviewer",
            "Fashion designer ✨ | Style inspiration",
            "",  # Empty bio
            "Follow for follow",
            "DM for promo rates"
        ]
        return random.choice(bios)


# Production implementation examples:

class InstagramGraphAPIFetcher(InstagramFollowerFetcher):
    """
    Production fetcher using Instagram Graph API.
    Requires business account and approved app.
    """
    
    def __init__(self, access_token: str, rate_limit_delay: float = 1.0):
        super().__init__(api_key=access_token, rate_limit_delay=rate_limit_delay)
        self.base_url = "https://graph.instagram.com"
    
    async def get_account_info(self, username: str) -> Dict[str, Any]:
        """Get account info via Graph API"""
        # Note: This requires user_id, not username
        # Implementation would need user_id lookup first
        url = f"{self.base_url}/{username}"
        params = {
            "fields": "account_type,media_count,followers_count,follows_count",
            "access_token": self.api_key
        }
        
        try:
            response = await self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise InstagramAPIError(f"Failed to fetch account info: {e}")


class ThirdPartyAPIFetcher(InstagramFollowerFetcher):
    """
    Fetcher using third-party Instagram API services.
    Example: RapidAPI Instagram services
    """
    
    def __init__(self, api_key: str, api_host: str, rate_limit_delay: float = 1.0):
        super().__init__(api_key=api_key, rate_limit_delay=rate_limit_delay)
        self.api_host = api_host
    
    async def get_followers(self, username: str, limit: int = 1000) -> List[FollowerData]:
        """Fetch followers via third-party API"""
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host
        }
        
        url = f"https://{self.api_host}/followers"
        params = {"username": username, "count": limit}
        
        try:
            await asyncio.sleep(self.rate_limit_delay)
            response = await self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            followers = []
            
            for follower_data in data.get('followers', []):
                follower = FollowerData(
                    username=follower_data.get('username', ''),
                    follower_count=follower_data.get('follower_count', 0),
                    following_count=follower_data.get('following_count', 0),
                    posts_count=follower_data.get('media_count', 0),
                    bio=follower_data.get('biography', ''),
                    profile_picture_url=follower_data.get('profile_pic_url'),
                    is_verified=follower_data.get('is_verified', False),
                    is_business=follower_data.get('is_business_account', False),
                    is_private=follower_data.get('is_private', False),
                    # Note: Third-party APIs may not provide creation dates
                    account_creation_date=None,
                    last_post_date=None,
                    location=None,
                    external_url=follower_data.get('external_url')
                )
                followers.append(follower)
            
            return followers
            
        except httpx.HTTPError as e:
            raise InstagramAPIError(f"Failed to fetch followers: {e}")


# Example usage:
async def example_usage():
    """Example of how to use the Instagram API fetcher"""
    
    # Using mock fetcher for development
    async with InstagramFollowerFetcher() as fetcher:
        account_info = await fetcher.get_account_info("example_user")
        print(f"Account: {account_info}")
        
        followers = await fetcher.get_followers("example_user", limit=100)
        print(f"Fetched {len(followers)} followers")
        
        # Show sample followers
        for i, follower in enumerate(followers[:5]):
            print(f"  {i+1}. {follower.username} ({follower.follower_count} followers)")


if __name__ == "__main__":
    asyncio.run(example_usage())