#!/usr/bin/env python3
"""
Enhanced TensorFlixValidator v2 with Growth-Focused Scoring and Bot Detection
"""

import asyncio
import sys
import math
from pathlib import Path
from loguru import logger
from datetime import datetime, timedelta
import bittensor as bt
from motor.motor_asyncio import AsyncIOMotorClient
import re

# Add the src directory to Python path for bot detection
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the original validator
from tensorflix.validator import TensorFlixValidator

# Import bot detection integration
try:
    from validator_integration import ValidatorBotDetector, ValidatorConfig
    BOT_DETECTION_AVAILABLE = True
    logger.info("✅ Bot detection framework loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Bot detection framework not available: {e}")
    BOT_DETECTION_AVAILABLE = False

# Import the new growth scoring system
from new_growth_scoring import GrowthFocusedScoring


class EnhancedTensorFlixValidatorV2(TensorFlixValidator):
    """TensorFlixValidator with Growth-Focused Scoring and Bot Detection"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize bot detection if available
        if BOT_DETECTION_AVAILABLE:
            self.bot_config = ValidatorConfig(
                bot_threshold=0.6,  # More strict for growth scoring
                confidence_threshold=0.5,
                enable_bot_detection=True
            )
            self.bot_detector = ValidatorBotDetector(self.bot_config)
            self.bot_detection_enabled = True
            logger.info("✅ Bot detection integrated into validator")
        else:
            self.bot_detection_enabled = False
            logger.info("⚠️ Bot detection not available")
            
        # Initialize growth scorer
        self.growth_scorer = GrowthFocusedScoring()
        logger.info("✅ Growth-focused scoring system initialized")
        
        # Create follower history collection
        db = self._performances.database
        self._follower_history = db["follower_history"]
        asyncio.create_task(self._ensure_follower_indexes())
        
    async def _ensure_follower_indexes(self):
        """Ensure indexes for follower history collection"""
        await self._follower_history.create_index([("hotkey", 1), ("timestamp", -1)])
        await self._follower_history.create_index("timestamp")
        logger.info("✅ Follower history indexes created")
    
    async def _track_follower_count(self, hotkey: str, follower_count: int, bot_analysis: dict = None):
        """Track follower count history for growth calculations"""
        record = {
            "hotkey": hotkey,
            "timestamp": datetime.utcnow(),
            "follower_count": follower_count,
            "bot_analysis": bot_analysis or {}
        }
        
        await self._follower_history.insert_one(record)
        logger.debug(f"Tracked follower count for {hotkey[:8]}: {follower_count}")
    
    async def _get_follower_growth_data(self, hotkey: str, hours: int = 12):
        """Get historical follower data for growth calculation"""
        cutoff_date = datetime.utcnow() - timedelta(hours=hours)
        
        # Get oldest record within the time window
        historical = await self._follower_history.find_one(
            {
                "hotkey": hotkey,
                "timestamp": {"$gte": cutoff_date}
            },
            sort=[("timestamp", 1)]  # Oldest first
        )
        
        # Get most recent record
        current = await self._follower_history.find_one(
            {"hotkey": hotkey},
            sort=[("timestamp", -1)]  # Newest first
        )
        
        if not historical or not current:
            return None
            
        # Calculate hours elapsed
        time_diff = current["timestamp"] - historical["timestamp"]
        hours_elapsed = time_diff.total_seconds() / 3600
        
        if hours_elapsed < 12:  # Need at least 12 hours
            return None
            
        return {
            "current_followers": current["follower_count"],
            "previous_followers": historical["follower_count"],
            "hours_elapsed": hours_elapsed,
            "bot_analysis": current.get("bot_analysis", {})
        }
    
    async def _calculate_miner_growth_scores(self) -> dict[str, float]:
        """Calculate growth-focused scores for all miners"""
        growth_scores = {}
        
        # Get active miners (excluding validators)
        active_miners = []
        for uid, hotkey in enumerate(self.metagraph.hotkeys):
            is_active_miner = (
                self.metagraph.S[uid] > 0 and not self.metagraph.validator_permit[uid]
            )
            if is_active_miner:
                active_miners.append(hotkey)
        
        logger.info(f"Calculating growth scores for {len(active_miners)} active miners")
        
        for hotkey in active_miners:
            try:
                # Get latest performance metrics
                latest_perf = await self._get_latest_performance_metrics(hotkey)
                if not latest_perf:
                    growth_scores[hotkey] = 0.0
                    continue
                
                # Get follower growth data
                growth_data = await self._get_follower_growth_data(hotkey)
                if not growth_data:
                    logger.debug(f"No growth data for {hotkey[:8]} - insufficient history")
                    growth_scores[hotkey] = 0.0
                    continue
                
                # Get Instagram handle for bot analysis
                instagram_handle = await self._get_miner_instagram_handle(hotkey)
                
                # Perform bot analysis if available
                bot_probability = 0.0
                bot_confidence = 0.0
                
                if instagram_handle and self.bot_detection_enabled:
                    validation_result = await self.bot_detector.validate_miner_followers(
                        hotkey, instagram_handle
                    )
                    
                    if validation_result['analyzed']:
                        bot_probability = validation_result['bot_probability']
                        bot_confidence = validation_result['confidence']
                        
                        # Track current follower count with bot analysis
                        await self._track_follower_count(
                            hotkey, 
                            growth_data["current_followers"],
                            {
                                "bot_probability": bot_probability,
                                "confidence": bot_confidence,
                                "risk_level": validation_result.get('risk_level', 'UNKNOWN')
                            }
                        )
                
                # Calculate growth score
                score_result = await self.growth_scorer.calculate_miner_score(
                    hotkey=hotkey,
                    current_followers=growth_data["current_followers"],
                    previous_followers=growth_data["previous_followers"],
                    hours_elapsed=growth_data["hours_elapsed"],
                    likes=latest_perf.get("likes", 0),
                    comments=latest_perf.get("comments", 0),
                    bot_probability=bot_probability,
                    bot_confidence=bot_confidence
                )
                
                growth_scores[hotkey] = score_result['final_score']
                
                # Log detailed scoring
                if score_result['final_score'] > 0:
                    logger.info(f"📊 Growth score for {hotkey[:8]}: {score_result['final_score']:.2f}")
                    logger.info(f"   ├── Hourly growth: {score_result['hourly_growth_rate']:.3f}%")
                    logger.info(f"   ├── Bot penalty: {score_result['bot_penalty']:.2f}x")
                    logger.info(f"   └── Engagement: {score_result['engagement_multiplier']:.2f}x")
                
            except Exception as e:
                logger.error(f"Error calculating growth score for {hotkey[:8]}: {e}")
                growth_scores[hotkey] = 0.0
        
        return growth_scores
    
    async def _get_latest_performance_metrics(self, hotkey: str):
        """Get latest performance metrics for engagement calculation"""
        perf_docs = await self._performances.find({"hotkey": hotkey}).to_list(None)
        
        if not perf_docs:
            return None
            
        total_likes = 0
        total_comments = 0
        follower_count = 0
        
        for doc in perf_docs:
            if not doc.get('platform_metrics_by_interval'):
                continue
                
            # Get the most recent interval
            intervals = sorted(doc['platform_metrics_by_interval'].keys())
            if not intervals:
                continue
                
            latest_metric = doc['platform_metrics_by_interval'][intervals[-1]]
            
            # Only count Instagram content
            if 'instagram' in latest_metric.get('platform_name', '').lower():
                total_likes += latest_metric.get('like_count', 0)
                total_comments += latest_metric.get('comment_count', 0)
                
                if latest_metric.get('owner_follower_count', 0) > 0:
                    follower_count = latest_metric['owner_follower_count']
        
        # Also track current follower count if we found it
        if follower_count > 0:
            await self._track_follower_count(hotkey, follower_count)
        
        return {
            "likes": total_likes,
            "comments": total_comments,
            "follower_count": follower_count
        }
    
    async def _get_miner_instagram_handle(self, hotkey: str):
        """Extract Instagram handle from miner's performance data"""
        try:
            # Get miner's performance documents
            perf_docs = await self._performances.find({"hotkey": hotkey}).to_list(None)
            
            for doc in perf_docs:
                # Check if this is Instagram content
                platform_metrics = doc.get('platform_metrics_by_interval', {})
                
                for interval_key, metrics in platform_metrics.items():
                    platform_name = metrics.get('platform_name', '')
                    
                    if 'instagram' in platform_name.lower():
                        # Try to extract handle from URL or caption
                        content_url = metrics.get('url', '')
                        caption = metrics.get('caption', '')
                        
                        handle = self._extract_instagram_handle(content_url, caption)
                        if handle:
                            return handle
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Instagram handle for {hotkey}: {e}")
            return None
    
    def _extract_instagram_handle(self, content_url: str, caption: str = "") -> str:
        """Extract Instagram handle from content URL or caption"""
        
        # Extract from Instagram URL
        url_patterns = [
            r'instagram\.com/([^/]+)/',
            r'instagram\.com/p/[^/]+/.*@([^/\s]+)',
            r'instagram\.com/reel/[^/]+/.*@([^/\s]+)'
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, content_url)
            if match:
                return match.group(1)
        
        # Extract from caption mentions
        caption_patterns = [
            r'@([a-zA-Z0-9._]+)',
            r'Made with @([a-zA-Z0-9._]+)'
        ]
        
        for pattern in caption_patterns:
            match = re.search(pattern, caption)
            if match:
                handle = match.group(1)
                # Filter out bittensor mentions
                if 'infinitevibe' not in handle.lower() and 'bittensor' not in handle.lower():
                    return handle
        
        return None
    
    async def calculate_and_set_weights(self) -> None:
        """Calculate weights based on growth-focused scoring"""
        try:
            # Calculate growth scores instead of engagement rates
            growth_scores = await self._calculate_miner_growth_scores()
            
            if not growth_scores:
                logger.warning("No growth scores calculated - skipping weight update")
                return
            
            # Get top 5 miners by growth score
            sorted_miners = sorted(growth_scores.items(), key=lambda item: item[1], reverse=True)
            top_5_hotkeys = {hk for hk, _ in sorted_miners[:5] if _ > 0}  # Only include positive scores
            
            logger.info(f"🏆 Top 5 miners by growth score:")
            for i, (hk, score) in enumerate(sorted_miners[:5]):
                logger.info(f"   {i+1}. {hk[:8]}: {score:.2f}")
            
            # Build weights array
            uids, weights = [], []
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                uids.append(uid)
                if hotkey in top_5_hotkeys:
                    weights.append(growth_scores[hotkey])
                else:
                    weights.append(0.0)
            
            # Normalize weights
            import numpy as np
            weights_array = np.array(weights, dtype=np.float32)
            if np.sum(weights_array) > 0:
                weights_array /= np.sum(weights_array)
            
            uint_uids, uint_weights = bt.utils.weight_utils.convert_weights_and_uids_for_emit(
                uids=np.array(uids, dtype=np.int32),
                weights=weights_array,
            )
            
            if np.sum(uint_weights) == 0:
                logger.info("Empty weights array, setting equal weights for top 5")
                uint_weights = []
                uint_uids = []
                for hotkey in top_5_hotkeys:
                    uint_weights.append(65535)
                    uint_uids.append(self.metagraph.hotkeys.index(hotkey))
            
            # Set weights on subnet
            result = await self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.netuid,
                uids=uint_uids,
                weights=uint_weights,
                version_key=0,
            )
            
            logger.info(f"⚖️ Weights set result: {result}")
            
        except Exception as e:
            logger.error(f"Weight calculation failed: {str(e)}")


async def main():
    """Main validator startup with growth-focused scoring"""
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=89)
    parser.add_argument("--wallet.name", type=str, default="default")
    parser.add_argument("--wallet.hotkey", type=str, default="default")
    parser.add_argument("--wallet.path", type=str, default="~/.bittensor/wallets/")
    parser.add_argument("--subtensor.network", type=str, default="finney")
    parser.add_argument("--logging.debug", action="store_true")
    parser.add_argument("--mongodb_uri", type=str, default="mongodb://localhost:27017/")
    args = parser.parse_args()
    
    # Setup logging
    if getattr(args, 'logging.debug', False):
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    logger.info("🚀 Starting Enhanced TensorFlix Validator V2 with Growth-Focused Scoring")
    
    # Initialize Bittensor components
    wallet = bt.Wallet(name=getattr(args, 'wallet.name', 'default'), hotkey=getattr(args, 'wallet.hotkey', 'default'), path=getattr(args, 'wallet.path', '~/.bittensor/wallets/'))
    subtensor = bt.AsyncSubtensor(network=getattr(args, 'subtensor.network', 'finney'))
    metagraph = await subtensor.metagraph(netuid=args.netuid)
    
    logger.info(f"Wallet: {wallet}")
    logger.info(f"Subtensor: {subtensor}")
    logger.info(f"Metagraph: {metagraph}")
    
    # Initialize MongoDB
    db_client = AsyncIOMotorClient(args.mongodb_uri)
    
    # Create enhanced validator instance
    validator = EnhancedTensorFlixValidatorV2(
        wallet=wallet,
        subtensor=subtensor,
        metagraph=metagraph,
        db_client=db_client,
        netuid=args.netuid,
    )
    
    # Run the validator
    try:
        await validator.run()
    except KeyboardInterrupt:
        logger.info("👋 Validator shutdown requested")
    except Exception as e:
        logger.error(f"💥 Validator failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())