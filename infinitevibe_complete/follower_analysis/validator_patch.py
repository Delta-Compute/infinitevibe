"""
Patch for integrating bot detection into existing TensorFlixValidator.

This module provides the necessary modifications to integrate the follower analysis
framework into the existing InfiniteVibe validator without breaking existing functionality.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import re

# Import the integration module
from validator_integration import ValidatorBotDetector, ValidatorConfig


class ValidatorBotDetectionPatch:
    """
    Patch class to add bot detection to existing TensorFlixValidator.
    
    Usage:
    1. Add this patch to your validator
    2. Call the patched methods instead of original ones
    3. Bot detection will be applied automatically
    """
    
    def __init__(self, config: ValidatorConfig = None):
        self.config = config or ValidatorConfig()
        self.bot_detector = ValidatorBotDetector(self.config)
        
    def extract_instagram_handle(self, content_url: str, caption: str = "") -> Optional[str]:
        """
        Extract Instagram handle from content URL or caption.
        
        Args:
            content_url: URL of the Instagram post/reel
            caption: Post caption text
            
        Returns:
            Instagram handle if found, None otherwise
        """
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
    
    async def patched_calculate_miner_engagement_rates(self, validator_instance) -> dict[str, float]:
        """
        Patched version of _calculate_miner_engagement_rates with bot detection.
        
        This method wraps the original engagement rate calculation and applies
        bot detection penalties where appropriate.
        """
        # Get original engagement rates
        original_rates = await self._call_original_method(validator_instance, '_calculate_miner_engagement_rates')
        
        # Apply bot detection adjustments
        adjusted_rates = {}
        
        for hotkey, original_rate in original_rates.items():
            # Get Instagram handle for this miner
            instagram_handle = await self._get_miner_instagram_handle(validator_instance, hotkey)
            
            if instagram_handle and self.config.enable_bot_detection:
                # Analyze bot followers
                validation_result = await self.bot_detector.validate_miner_followers(
                    hotkey, instagram_handle
                )
                
                if validation_result['analyzed']:
                    # Apply penalty
                    adjusted_rate = original_rate * validation_result['penalty_factor']
                    
                    # Log significant adjustments
                    if validation_result['penalty_factor'] < 0.9:
                        print(f"🤖 Bot penalty applied to {hotkey[:8]}: "
                              f"{validation_result['penalty_factor']:.2f}x "
                              f"(bot probability: {validation_result['bot_probability']:.3f})")
                    
                    adjusted_rates[hotkey] = adjusted_rate
                else:
                    adjusted_rates[hotkey] = original_rate
            else:
                # No Instagram handle found or bot detection disabled
                adjusted_rates[hotkey] = original_rate
        
        return adjusted_rates
    
    async def _call_original_method(self, validator_instance, method_name: str) -> Any:
        """Call the original validator method"""
        original_method = getattr(validator_instance, method_name)
        return await original_method()
    
    async def _get_miner_instagram_handle(self, validator_instance, hotkey: str) -> Optional[str]:
        """
        Extract Instagram handle from miner's performance data.
        
        Args:
            validator_instance: TensorFlixValidator instance
            hotkey: Miner's hotkey
            
        Returns:
            Instagram handle if found
        """
        try:
            # Get miner's performance documents
            perf_docs = await validator_instance._performances.find({"hotkey": hotkey}).to_list(None)
            
            for doc in perf_docs:
                # Check if this is Instagram content
                platform_metrics = doc.get('platform_metrics_by_interval', {})
                
                for interval_key, metrics in platform_metrics.items():
                    platform_name = metrics.get('platform_name', '')
                    
                    if 'instagram' in platform_name.lower():
                        # Try to extract handle from URL or caption
                        content_url = metrics.get('url', '')
                        caption = metrics.get('caption', '')
                        
                        handle = self.extract_instagram_handle(content_url, caption)
                        if handle:
                            return handle
            
            return None
            
        except Exception as e:
            print(f"Error extracting Instagram handle for {hotkey}: {e}")
            return None
    
    def get_bot_detection_stats(self) -> Dict[str, Any]:
        """Get bot detection statistics"""
        return self.bot_detector.get_analysis_summary()


# Integration helper function
def apply_bot_detection_patch(validator_instance, config: ValidatorConfig = None) -> ValidatorBotDetectionPatch:
    """
    Apply bot detection patch to an existing validator instance.
    
    Args:
        validator_instance: TensorFlixValidator instance
        config: Bot detection configuration
        
    Returns:
        Patch instance for manual control if needed
    """
    patch = ValidatorBotDetectionPatch(config)
    
    # Store original method
    validator_instance._original_calculate_miner_engagement_rates = validator_instance._calculate_miner_engagement_rates
    
    # Replace with patched version
    async def patched_method():
        return await patch.patched_calculate_miner_engagement_rates(validator_instance)
    
    validator_instance._calculate_miner_engagement_rates = patched_method
    validator_instance._bot_detection_patch = patch
    
    print("🤖 Bot detection patch applied to validator")
    return patch


# Example usage in validator startup:
"""
# In your validator initialization code:

from follower_analysis.src.validator_patch import apply_bot_detection_patch, ValidatorConfig

# Configure bot detection
bot_config = ValidatorConfig(
    bot_threshold=0.7,  # Flag accounts with >70% bot probability
    confidence_threshold=0.5,  # Require 50% confidence to act
    enable_bot_detection=True
)

# Apply patch to validator
validator = TensorFlixValidator(...)
bot_patch = apply_bot_detection_patch(validator, bot_config)

# Bot detection is now automatically applied during engagement rate calculation

# Optionally, get bot detection statistics
stats = bot_patch.get_bot_detection_stats()
print(f"Bot detection stats: {stats}")
"""


# Stand-alone integration for testing
async def test_integration():
    """Test the bot detection integration"""
    
    print("🧪 Testing Bot Detection Integration")
    print("=" * 50)
    
    # Create patch instance
    config = ValidatorConfig(
        bot_threshold=0.6,
        confidence_threshold=0.4,
        enable_bot_detection=True
    )
    
    patch = ValidatorBotDetectionPatch(config)
    
    # Test Instagram handle extraction
    test_urls = [
        "https://instagram.com/example_user/p/ABC123/",
        "https://instagram.com/test_account/reel/XYZ789/",
        "Made with @infinitevibe.ai on #bittensor --- @test_creator"
    ]
    
    for url in test_urls:
        handle = patch.extract_instagram_handle(url, url)
        print(f"URL: {url}")
        print(f"Extracted handle: {handle}")
        print()
    
    # Test bot detection on mock data
    test_handle = "test_creator"
    result = await patch.bot_detector.validate_miner_followers("test_hotkey", test_handle)
    
    print(f"Bot detection result for {test_handle}:")
    print(f"  Analyzed: {result['analyzed']}")
    if result['analyzed']:
        print(f"  Suspicious: {result['suspicious']}")
        print(f"  Penalty factor: {result['penalty_factor']:.3f}")
        print(f"  Bot probability: {result['bot_probability']:.3f}")
        print(f"  Risk level: {result['risk_level']}")
    
    print("\n✅ Integration test complete")


if __name__ == "__main__":
    asyncio.run(test_integration())