"""
Validator integration that reads bot detection results from background analyzer
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger


class ValidatorBotIntegration:
    """Integrates background bot detection results into validator scoring"""
    
    def __init__(self, mongodb_uri: str = None):
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.db_client = None
        self.db = None
        
        # Configuration
        self.bot_threshold = float(os.getenv('BOT_THRESHOLD', '0.7'))
        self.confidence_threshold = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))
        self.max_penalty = float(os.getenv('MAX_BOT_PENALTY', '0.8'))  # Max 80% reduction
        self.cache_hours = int(os.getenv('BOT_RESULT_CACHE_HOURS', '24'))
        
    async def initialize(self):
        """Initialize database connection"""
        if not self.db_client:
            self.db_client = AsyncIOMotorClient(self.mongodb_uri)
            self.db = self.db_client.infinitevibe
            logger.info("✅ Bot integration database connection initialized")
    
    async def get_bot_analysis(self, hotkey: str) -> Optional[Dict]:
        """Get the latest bot analysis for a miner"""
        await self.initialize()
        
        try:
            # Get analysis within cache period
            cache_cutoff = datetime.utcnow() - timedelta(hours=self.cache_hours)
            
            analysis = await self.db.follower_analysis.find_one(
                {
                    "hotkey": hotkey,
                    "analyzed_at": {"$gte": cache_cutoff}
                },
                sort=[("analyzed_at", -1)]  # Get most recent
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to get bot analysis for {hotkey}: {e}")
            return None
    
    def calculate_bot_penalty(self, bot_probability: float, confidence: float) -> float:
        """Calculate engagement rate penalty based on bot detection"""
        
        # Only apply penalty if confident enough
        if confidence < self.confidence_threshold:
            return 0.0
            
        # Only apply penalty if bot probability exceeds threshold
        if bot_probability < self.bot_threshold:
            return 0.0
            
        # Linear penalty scaling
        # At 70% bot probability = 0% penalty
        # At 100% bot probability = max_penalty (80%)
        penalty_range = 1.0 - self.bot_threshold
        penalty_scale = (bot_probability - self.bot_threshold) / penalty_range
        penalty = penalty_scale * self.max_penalty
        
        return min(penalty, self.max_penalty)
    
    async def apply_bot_penalties(self, engagement_rates: Dict[str, float]) -> Dict[str, float]:
        """Apply bot penalties to engagement rates"""
        await self.initialize()
        
        adjusted_rates = engagement_rates.copy()
        
        for hotkey, rate in engagement_rates.items():
            # Get bot analysis
            analysis = await self.get_bot_analysis(hotkey)
            
            if not analysis:
                continue
                
            bot_data = analysis.get('bot_detection', {})
            bot_probability = bot_data.get('bot_probability', 0)
            confidence = bot_data.get('confidence', 0)
            
            # Calculate penalty
            penalty = self.calculate_bot_penalty(bot_probability, confidence)
            
            if penalty > 0:
                # Apply penalty
                original_rate = rate
                adjusted_rate = rate * (1 - penalty)
                adjusted_rates[hotkey] = adjusted_rate
                
                logger.info(
                    f"🤖 Bot penalty applied to {hotkey[:8]}...: "
                    f"{penalty:.1%} reduction "
                    f"(bot_prob: {bot_probability:.2f}, conf: {confidence:.2f})"
                )
                logger.info(
                    f"   Engagement: {original_rate:.2f}% → {adjusted_rate:.2f}%"
                )
                
                # Store penalty record
                await self.db.bot_penalties.insert_one({
                    "hotkey": hotkey,
                    "timestamp": datetime.utcnow(),
                    "original_rate": original_rate,
                    "adjusted_rate": adjusted_rate,
                    "penalty": penalty,
                    "bot_probability": bot_probability,
                    "confidence": confidence
                })
        
        return adjusted_rates
    
    async def get_bot_stats(self) -> Dict:
        """Get summary statistics for bot detection"""
        await self.initialize()
        
        try:
            # Count recent analyses
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            
            stats = {
                "total_analyses": await self.db.follower_analysis.count_documents({}),
                "recent_analyses": await self.db.follower_analysis.count_documents({
                    "analyzed_at": {"$gte": recent_cutoff}
                }),
                "high_bot_accounts": await self.db.follower_analysis.count_documents({
                    "bot_detection.bot_probability": {"$gte": self.bot_threshold}
                }),
                "penalties_applied": await self.db.bot_penalties.count_documents({
                    "timestamp": {"$gte": recent_cutoff}
                })
            }
            
            # Get average bot probability
            pipeline = [
                {"$group": {
                    "_id": None,
                    "avg_bot_probability": {"$avg": "$bot_detection.bot_probability"},
                    "avg_confidence": {"$avg": "$bot_detection.confidence"}
                }}
            ]
            
            avg_result = await self.db.follower_analysis.aggregate(pipeline).to_list(1)
            if avg_result:
                stats.update(avg_result[0])
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get bot stats: {e}")
            return {}


# Patch function for existing validator
async def patch_validator_with_bot_detection(validator_instance):
    """Patch an existing validator instance with bot detection"""
    
    # Create bot integration
    bot_integration = ValidatorBotIntegration()
    await bot_integration.initialize()
    
    # Store original method
    original_calculate_rates = validator_instance._calculate_miner_engagement_rates
    
    # Create patched method
    async def patched_calculate_rates():
        # Get original rates
        engagement_rates = await original_calculate_rates()
        
        # Apply bot penalties
        adjusted_rates = await bot_integration.apply_bot_penalties(engagement_rates)
        
        # Log statistics
        stats = await bot_integration.get_bot_stats()
        logger.info(f"📊 Bot Detection Stats: {stats}")
        
        return adjusted_rates
    
    # Apply patch
    validator_instance._calculate_miner_engagement_rates = patched_calculate_rates
    
    logger.info("✅ Validator patched with bot detection integration")
    return validator_instance