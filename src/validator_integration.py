"""
Integration module for InfiniteVibe validator to detect bot followers.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from analyzers.base import FollowerData
from detector import ModularBotDetector, DetectionResult


@dataclass
class ValidatorConfig:
    """Configuration for validator bot detection"""
    bot_threshold: float = 0.7  # Bot probability threshold for flagging
    confidence_threshold: float = 0.5  # Minimum confidence to act on results
    min_followers_to_analyze: int = 50  # Minimum followers needed for analysis
    max_followers_to_analyze: int = 1000  # Maximum followers to analyze (API limits)
    analysis_interval_hours: int = 24  # How often to run analysis
    enable_bot_detection: bool = True  # Master switch for bot detection


class ValidatorBotDetector:
    """
    Bot detection integration for InfiniteVibe validator.
    
    This class integrates with the validator's workflow to:
    1. Fetch follower data from Instagram accounts
    2. Analyze followers for bot patterns
    3. Flag suspicious accounts
    4. Adjust engagement rate calculations
    """
    
    def __init__(self, config: ValidatorConfig = None):
        self.config = config or ValidatorConfig()
        self.detector = ModularBotDetector()
        self.analysis_cache: Dict[str, DetectionResult] = {}
        self.last_analysis: Dict[str, datetime] = {}
        
    async def should_analyze_account(self, instagram_handle: str) -> bool:
        """
        Check if account should be analyzed for bot followers.
        
        Args:
            instagram_handle: Instagram account handle
            
        Returns:
            True if analysis should be performed
        """
        if not self.config.enable_bot_detection:
            return False
            
        # Check if recently analyzed
        if instagram_handle in self.last_analysis:
            time_since_analysis = datetime.now() - self.last_analysis[instagram_handle]
            if time_since_analysis < timedelta(hours=self.config.analysis_interval_hours):
                return False
                
        return True
    
    async def fetch_instagram_followers(self, instagram_handle: str) -> List[FollowerData]:
        """
        Fetch follower data from Instagram account.
        
        Args:
            instagram_handle: Instagram account handle
            
        Returns:
            List of follower data
            
        Note: This is a placeholder implementation. In production, you would:
        1. Use Instagram's API (requires approval)
        2. Use a web scraping library (check ToS compliance)
        3. Use a third-party service
        """
        # Placeholder implementation
        # In production, integrate with Instagram API or scraping service
        
        # Mock data for demonstration
        followers = []
        
        # You would implement actual Instagram API calls here
        # Example using hypothetical Instagram API:
        # followers_response = await instagram_api.get_followers(instagram_handle)
        # for follower in followers_response['data']:
        #     followers.append(FollowerData(
        #         username=follower['username'],
        #         follower_count=follower['follower_count'],
        #         ...
        #     ))
        
        return followers
    
    async def analyze_account_followers(self, instagram_handle: str) -> Optional[DetectionResult]:
        """
        Analyze followers of an Instagram account for bot patterns.
        
        Args:
            instagram_handle: Instagram account handle
            
        Returns:
            DetectionResult or None if analysis couldn't be performed
        """
        if not await self.should_analyze_account(instagram_handle):
            # Return cached result if available
            return self.analysis_cache.get(instagram_handle)
            
        try:
            # Fetch follower data
            followers = await self.fetch_instagram_followers(instagram_handle)
            
            if len(followers) < self.config.min_followers_to_analyze:
                return None
                
            # Limit analysis to prevent API exhaustion
            if len(followers) > self.config.max_followers_to_analyze:
                # Analyze a random sample
                import random
                followers = random.sample(followers, self.config.max_followers_to_analyze)
            
            # Perform bot detection
            result = self.detector.analyze(followers)
            
            # Cache result
            self.analysis_cache[instagram_handle] = result
            self.last_analysis[instagram_handle] = datetime.now()
            
            return result
            
        except Exception as e:
            # Log error but don't crash validator
            print(f"Error analyzing {instagram_handle}: {e}")
            return None
    
    def is_account_suspicious(self, result: DetectionResult) -> bool:
        """
        Determine if account should be flagged as suspicious.
        
        Args:
            result: Detection result
            
        Returns:
            True if account appears to have bot followers
        """
        if result.overall_confidence < self.config.confidence_threshold:
            return False  # Not confident enough to flag
            
        return result.bot_probability >= self.config.bot_threshold
    
    def get_bot_penalty_factor(self, result: DetectionResult) -> float:
        """
        Calculate penalty factor for engagement rate based on bot detection.
        
        Args:
            result: Detection result
            
        Returns:
            Penalty factor (0.0 to 1.0) to multiply engagement rate
        """
        if result.overall_confidence < self.config.confidence_threshold:
            return 1.0  # No penalty if not confident
            
        # Linear penalty based on bot probability
        penalty = 1.0 - (result.bot_probability * 0.8)  # Max 80% penalty
        return max(0.2, penalty)  # Minimum 20% of original engagement
    
    async def validate_miner_followers(self, hotkey: str, instagram_handle: str) -> Dict[str, Any]:
        """
        Validate a miner's Instagram followers.
        
        Args:
            hotkey: Miner's hotkey
            instagram_handle: Instagram account handle
            
        Returns:
            Dictionary with validation results
        """
        result = await self.analyze_account_followers(instagram_handle)
        
        if result is None:
            return {
                'analyzed': False,
                'reason': 'insufficient_data_or_recent_analysis',
                'penalty_factor': 1.0,
                'suspicious': False
            }
        
        suspicious = self.is_account_suspicious(result)
        penalty_factor = self.get_bot_penalty_factor(result)
        
        return {
            'analyzed': True,
            'result': result,
            'suspicious': suspicious,
            'penalty_factor': penalty_factor,
            'bot_probability': result.bot_probability,
            'confidence': result.overall_confidence,
            'risk_level': result.risk_level,
            'flags': result.flags,
            'timestamp': result.timestamp
        }
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Get summary of all analyses performed.
        
        Returns:
            Summary statistics
        """
        if not self.analysis_cache:
            return {'total_analyses': 0}
            
        total_analyses = len(self.analysis_cache)
        suspicious_accounts = sum(
            1 for result in self.analysis_cache.values() 
            if self.is_account_suspicious(result)
        )
        
        avg_bot_probability = sum(
            result.bot_probability for result in self.analysis_cache.values()
        ) / total_analyses
        
        return {
            'total_analyses': total_analyses,
            'suspicious_accounts': suspicious_accounts,
            'suspicious_rate': suspicious_accounts / total_analyses,
            'avg_bot_probability': avg_bot_probability,
            'last_analysis_time': max(self.last_analysis.values()) if self.last_analysis else None
        }


# Integration helper for existing validator code
async def integrate_bot_detection_with_validator(
    validator_instance, 
    hotkey: str, 
    instagram_handle: str,
    original_engagement_rate: float
) -> tuple[float, Dict[str, Any]]:
    """
    Helper function to integrate bot detection with existing validator.
    
    Args:
        validator_instance: Instance of TensorFlixValidator
        hotkey: Miner's hotkey
        instagram_handle: Instagram account handle
        original_engagement_rate: Original calculated engagement rate
        
    Returns:
        Tuple of (adjusted_engagement_rate, bot_detection_info)
    """
    # Initialize bot detector if not already done
    if not hasattr(validator_instance, '_bot_detector'):
        validator_instance._bot_detector = ValidatorBotDetector()
    
    # Analyze followers
    validation_result = await validator_instance._bot_detector.validate_miner_followers(
        hotkey, instagram_handle
    )
    
    if validation_result['analyzed']:
        # Apply penalty to engagement rate
        adjusted_rate = original_engagement_rate * validation_result['penalty_factor']
        
        # Log significant penalties
        if validation_result['penalty_factor'] < 0.8:
            print(f"Applied bot penalty to {hotkey}: {validation_result['penalty_factor']:.2f} "
                  f"(bot probability: {validation_result['bot_probability']:.3f})")
        
        return adjusted_rate, validation_result
    else:
        # No analysis performed, return original rate
        return original_engagement_rate, validation_result


# Example usage in validator.py:
"""
# In _calculate_miner_engagement_rates method, after calculating engagement rate:

if hasattr(latest_metric, 'instagram_handle'):
    adjusted_rate, bot_info = await integrate_bot_detection_with_validator(
        self, hotkey, latest_metric.instagram_handle, rate
    )
    
    # Log bot detection results
    if bot_info['analyzed'] and bot_info['suspicious']:
        logger.warning(f"Suspicious bot followers detected for {hotkey}: "
                      f"bot_probability={bot_info['bot_probability']:.3f}, "
                      f"flags={bot_info['flags']}")
    
    # Use adjusted rate instead of original
    engagement_rates[hotkey] = adjusted_rate
else:
    engagement_rates[hotkey] = rate
"""