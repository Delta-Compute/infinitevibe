#!/usr/bin/env python3
"""
Background follower analyzer that runs independently from the validator.
Analyzes top 5 miners' Instagram followers using Apify API.
"""

import asyncio
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
import random

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from detector import ModularBotDetector, FollowerData


class ApifyInstagramFetcher:
    """Fetches Instagram data using Apify actors"""
    
    def __init__(self):
        self.api_key = os.getenv('APIFY_API_KEY')
        self.actor_id = os.getenv('APIFY_ACTOR_ID', 'shu8hvrXbJbY3Eb9W')  # instagram-scraper
        self.base_url = 'https://api.apify.com/v2'
        
        if not self.api_key:
            raise ValueError("APIFY_API_KEY environment variable not set")
    
    async def get_profile_and_followers(self, username: str, sample_size: int = 50) -> Dict:
        """
        Fetch profile data and random sample of followers
        """
        logger.info(f"🔍 Fetching profile and followers for @{username}")
        
        # Step 1: Get profile basic info
        profile_run_input = {
            "usernames": [username],
            "resultsType": "details",
            "resultsLimit": 1
        }
        
        try:
            profile_data = await self._run_actor(profile_run_input)
            
            if not profile_data or not profile_data[0].get('followersCount'):
                logger.warning(f"No profile data found for @{username}")
                return {"profile": None, "followers": []}
                
            profile = profile_data[0]
            follower_count = profile.get('followersCount', 0)
            
            # Step 2: Get random followers sample
            followers_data = []
            if follower_count > 10:  # Only analyze if they have enough followers
                followers_run_input = {
                    "usernames": [username],
                    "resultsType": "followers", 
                    "resultsLimit": min(sample_size * 2, 200)  # Get extra to randomize
                }
                
                raw_followers = await self._run_actor(followers_run_input)
                
                # Random sample from the results
                if raw_followers:
                    followers_data = random.sample(
                        raw_followers, 
                        min(sample_size, len(raw_followers))
                    )
                    logger.info(f"✅ Sampled {len(followers_data)} followers from @{username}")
            
            return {
                "profile": profile,
                "followers": followers_data
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch data for @{username}: {e}")
            return {"profile": None, "followers": []}
    
    async def _run_actor(self, run_input: Dict) -> List[Dict]:
        """Execute Apify actor and wait for results"""
        async with httpx.AsyncClient() as client:
            # Start actor run
            logger.debug(f"Starting Apify actor with input: {run_input}")
            
            run_response = await client.post(
                f"{self.base_url}/acts/{self.actor_id}/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=run_input,
                timeout=180.0
            )
            
            if run_response.status_code not in [200, 201]:
                raise Exception(f"Failed to run Apify actor: {run_response.text}")
                
            return run_response.json()


class BackgroundFollowerAnalyzer:
    """Background service that analyzes top miners' followers"""
    
    def __init__(self, mongodb_uri: str = None):
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.db_client = None
        self.db = None
        self.fetcher = ApifyInstagramFetcher()
        self.detector = ModularBotDetector()
        
        # Configuration
        self.sample_size = int(os.getenv('FOLLOWER_SAMPLE_SIZE', '50'))
        self.analysis_interval = int(os.getenv('ANALYSIS_INTERVAL_HOURS', '6')) * 3600
        self.cooldown_hours = int(os.getenv('ANALYSIS_COOLDOWN_HOURS', '24'))
        
    async def initialize(self):
        """Initialize database connection"""
        self.db_client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.db_client.tensorflix
        logger.info("✅ Database connection initialized")
        
    async def get_top_miners(self, limit: int = 5) -> List[Dict]:
        """Get top 5 miners by engagement rate from MongoDB"""
        try:
            # Get miners with submissions (they have Instagram content)
            miners = await self.db['submissions-0.0.2'].find(
                {},
                {"hotkey": 1, "submissions": 1}
            ).limit(limit).to_list(length=limit)
            
            # Extract miners with Instagram content
            instagram_miners = []
            for miner in miners:
                for submission in miner.get('submissions', []):
                    if 'instagram' in submission.get('platform', '').lower():
                        instagram_miners.append({
                            'hotkey': miner['hotkey'],
                            'instagram_handle': self._extract_instagram_handle_from_submission(submission)
                        })
                        break
            
            logger.info(f"📊 Found {len(instagram_miners)} miners with Instagram content to analyze")
            return instagram_miners
            
        except Exception as e:
            logger.error(f"Failed to get top miners: {e}")
            return []
    
    def _extract_instagram_handle_from_submission(self, submission: Dict) -> str:
        """Extract Instagram handle from submission data"""
        import re
        
        # Try to get handle from content_id or url
        content_id = submission.get('content_id', '')
        
        # Extract from Instagram URL patterns
        url_patterns = [
            r'instagram\.com/([^/]+)/',
            r'instagram\.com/p/[^/]+/.*@([^/\s]+)',
            r'instagram\.com/reel/[^/]+/.*@([^/\s]+)'
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, content_id)
            if match:
                return match.group(1)
        
        # If no handle found, use the content_id as is (might be just the handle)
        if content_id and not content_id.startswith('http'):
            return content_id.replace('@', '')
        
        return None
    
    async def is_analysis_recent(self, instagram_handle: str) -> bool:
        """Check if we've analyzed this account recently"""
        cooldown_time = datetime.utcnow() - timedelta(hours=self.cooldown_hours)
        
        recent_analysis = await self.db.follower_analysis.find_one({
            "instagram_handle": instagram_handle,
            "analyzed_at": {"$gte": cooldown_time}
        })
        
        return recent_analysis is not None
    
    async def analyze_miner_followers(self, miner: Dict) -> Optional[Dict]:
        """Analyze a single miner's followers"""
        instagram_handle = miner.get('instagram_handle')
        if not instagram_handle:
            logger.warning(f"No Instagram handle for miner {miner.get('hotkey')}")
            return None
            
        # Check cooldown
        if await self.is_analysis_recent(instagram_handle):
            logger.info(f"⏳ Skipping @{instagram_handle} - analyzed recently")
            return None
            
        logger.info(f"🔍 Analyzing followers for @{instagram_handle} (hotkey: {miner.get('hotkey')[:8]}...)")
        
        try:
            # Fetch data from Apify
            data = await self.fetcher.get_profile_and_followers(
                instagram_handle, 
                sample_size=self.sample_size
            )
            
            if not data['followers']:
                logger.warning(f"No followers data for @{instagram_handle}")
                return None
            
            # Convert to FollowerData format
            follower_objects = []
            for follower in data['followers']:
                follower_obj = FollowerData(
                    username=follower.get('username', ''),
                    follower_count=follower.get('followersCount', 0),
                    following_count=follower.get('followsCount', 0),
                    post_count=follower.get('postsCount', 0),
                    bio=follower.get('biography', ''),
                    has_profile_pic=bool(follower.get('profilePicUrl')),
                    is_verified=follower.get('verified', False),
                    is_private=follower.get('private', False),
                    account_creation_date=None  # Not available from this scraper
                )
                follower_objects.append(follower_obj)
            
            # Run bot detection
            result = self.detector.analyze(follower_objects)
            
            # Prepare analysis record
            analysis_record = {
                "hotkey": miner.get('hotkey'),
                "instagram_handle": instagram_handle,
                "analyzed_at": datetime.utcnow(),
                "profile_data": {
                    "follower_count": data['profile'].get('followersCount', 0),
                    "following_count": data['profile'].get('followsCount', 0),
                    "posts_count": data['profile'].get('postsCount', 0),
                    "engagement_rate": miner.get('engagement_rate', 0)
                },
                "bot_detection": {
                    "bot_probability": result.bot_probability,
                    "authenticity_score": result.overall_authenticity_score,
                    "confidence": result.overall_confidence,
                    "risk_level": result.risk_level,
                    "suspicious_followers": result.suspicious_followers,
                    "flags": result.flags
                },
                "sample_size": len(follower_objects),
                "analyzer_scores": result.analyzer_scores
            }
            
            # Store in database
            await self.db.follower_analysis.update_one(
                {"hotkey": miner.get('hotkey')},
                {"$set": analysis_record},
                upsert=True
            )
            
            # Log results
            if result.bot_probability > 0.7:
                logger.warning(f"🚨 High bot probability ({result.bot_probability:.2f}) for @{instagram_handle}")
            else:
                logger.info(f"✅ Low bot probability ({result.bot_probability:.2f}) for @{instagram_handle}")
                
            return analysis_record
            
        except Exception as e:
            logger.error(f"Failed to analyze @{instagram_handle}: {e}")
            # Store error record
            await self.db.follower_analysis_errors.insert_one({
                "hotkey": miner.get('hotkey'),
                "instagram_handle": instagram_handle,
                "error": str(e),
                "timestamp": datetime.utcnow()
            })
            return None
    
    async def run_analysis_cycle(self):
        """Run one complete analysis cycle for top 5 miners"""
        logger.info("🚀 Starting follower analysis cycle")
        start_time = time.time()
        
        # Get top 5 miners
        top_miners = await self.get_top_miners(5)
        
        if not top_miners:
            logger.warning("No miners found to analyze")
            return
        
        # Analyze each miner
        results = []
        for miner in top_miners:
            result = await self.analyze_miner_followers(miner)
            if result:
                results.append(result)
                
            # Small delay between analyses to avoid rate limits
            await asyncio.sleep(5)
        
        # Summary
        elapsed = time.time() - start_time
        logger.info(f"✅ Analysis cycle complete. Analyzed {len(results)} miners in {elapsed:.1f}s")
        
        if results:
            avg_bot_prob = sum(r['bot_detection']['bot_probability'] for r in results) / len(results)
            logger.info(f"📊 Average bot probability: {avg_bot_prob:.2%}")
    
    async def run_forever(self):
        """Run the analyzer continuously"""
        await self.initialize()
        
        logger.info(f"🤖 Background Follower Analyzer started")
        logger.info(f"   - Sample size: {self.sample_size} followers")
        logger.info(f"   - Analysis interval: {self.analysis_interval/3600} hours")
        logger.info(f"   - Cooldown period: {self.cooldown_hours} hours")
        
        while True:
            try:
                await self.run_analysis_cycle()
                
                # Wait for next cycle
                logger.info(f"💤 Sleeping for {self.analysis_interval/3600} hours until next cycle")
                await asyncio.sleep(self.analysis_interval)
                
            except Exception as e:
                logger.error(f"Analysis cycle error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry


async def main():
    """Main entry point"""
    analyzer = BackgroundFollowerAnalyzer()
    await analyzer.run_forever()


if __name__ == "__main__":
    # Configure logging
    logger.add(
        "logs/follower_analyzer_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # Run the analyzer
    asyncio.run(main())