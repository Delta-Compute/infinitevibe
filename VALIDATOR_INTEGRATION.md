# Validator Integration Guide

This document explains how to integrate the follower analysis framework with the InfiniteVibe validator.

## 🚀 Quick Integration

### Step 1: Copy Files to Validator Directory

```bash
# Copy the follower analysis module to your validator environment
cp -r follower-analysis/src/* /path/to/infinitevibe/follower_analysis/
```

### Step 2: Install Dependencies

```bash
# Add to your requirements.txt or install directly
pip install dataclasses typing-extensions
```

### Step 3: Apply the Patch

In your validator startup code (e.g., `neurons/validating.py`):

```python
import sys
sys.path.append('/path/to/follower_analysis')

from validator_patch import apply_bot_detection_patch, ValidatorConfig

# Configure bot detection
bot_config = ValidatorConfig(
    bot_threshold=0.7,          # Flag accounts with >70% bot probability
    confidence_threshold=0.5,   # Require 50% confidence to act
    min_followers_to_analyze=50, # Need at least 50 followers for analysis
    enable_bot_detection=True   # Master switch
)

# Apply patch to validator
validator = TensorFlixValidator(...)
bot_patch = apply_bot_detection_patch(validator, bot_config)
```

### Step 4: Monitor Results

```python
# Get bot detection statistics
stats = bot_patch.get_bot_detection_stats()
logger.info(f"Bot detection stats: {stats}")
```

## 🔧 Manual Integration

If you prefer manual integration, modify your `_calculate_miner_engagement_rates` method:

```python
async def _calculate_miner_engagement_rates(self) -> dict[str, float]:
    """Calculate engagement rate for all active miners with bot detection"""
    
    # Initialize bot detector if not already done
    if not hasattr(self, '_bot_detector'):
        from follower_analysis.validator_integration import ValidatorBotDetector, ValidatorConfig
        config = ValidatorConfig(bot_threshold=0.7, enable_bot_detection=True)
        self._bot_detector = ValidatorBotDetector(config)
    
    engagement_rates = {}
    # ... existing code to get active_hotkeys ...
    
    for hotkey in active_hotkeys:
        # ... existing code to calculate base engagement rate ...
        
        # Apply bot detection if Instagram content found
        instagram_handle = await self._extract_instagram_handle(hotkey)
        
        if instagram_handle:
            validation_result = await self._bot_detector.validate_miner_followers(
                hotkey, instagram_handle
            )
            
            if validation_result['analyzed']:
                # Apply penalty to engagement rate
                adjusted_rate = rate * validation_result['penalty_factor']
                
                if validation_result['suspicious']:
                    logger.warning(f"Suspicious bot followers detected for {hotkey}: "
                                 f"bot_probability={validation_result['bot_probability']:.3f}")
                
                engagement_rates[hotkey] = adjusted_rate
            else:
                engagement_rates[hotkey] = rate
        else:
            engagement_rates[hotkey] = rate
    
    return engagement_rates
```

## 📊 Configuration Options

### ValidatorConfig Parameters

```python
@dataclass
class ValidatorConfig:
    bot_threshold: float = 0.7          # Bot probability threshold for flagging
    confidence_threshold: float = 0.5   # Minimum confidence to act on results
    min_followers_to_analyze: int = 50  # Minimum followers needed for analysis
    max_followers_to_analyze: int = 1000 # Maximum followers to analyze (API limits)
    analysis_interval_hours: int = 24   # How often to run analysis
    enable_bot_detection: bool = True   # Master switch for bot detection
```

### Recommended Settings

**Conservative (Low False Positives):**
```python
ValidatorConfig(
    bot_threshold=0.8,
    confidence_threshold=0.7,
    min_followers_to_analyze=100
)
```

**Aggressive (High Detection):**
```python
ValidatorConfig(
    bot_threshold=0.6,
    confidence_threshold=0.4,
    min_followers_to_analyze=30
)
```

**Balanced (Recommended):**
```python
ValidatorConfig(
    bot_threshold=0.7,
    confidence_threshold=0.5,
    min_followers_to_analyze=50
)
```

## 🔍 Instagram Handle Extraction

The system automatically extracts Instagram handles from:

1. **Instagram URLs**: `instagram.com/username/p/ABC123/`
2. **Post Captions**: `Made with @infinitevibe.ai --- @username`
3. **Bio Links**: Links in miner submissions

### Custom Handle Extraction

If you need custom logic:

```python
async def _extract_instagram_handle(self, hotkey: str) -> Optional[str]:
    """Extract Instagram handle from miner's performance data"""
    perf_docs = await self._performances.find({"hotkey": hotkey}).to_list(None)
    
    for doc in perf_docs:
        platform_metrics = doc.get('platform_metrics_by_interval', {})
        for metrics in platform_metrics.values():
            if 'instagram' in metrics.get('platform_name', '').lower():
                # Your custom extraction logic here
                handle = extract_handle_from_url(metrics.get('url', ''))
                if handle:
                    return handle
    return None
```

## 🚨 Error Handling

The integration is designed to fail gracefully:

- **API Errors**: Returns original engagement rate if bot detection fails
- **Rate Limits**: Caches results to avoid repeated API calls
- **Invalid Data**: Skips analysis if insufficient follower data
- **Configuration Errors**: Logs warnings but continues validation

```python
# Example error handling
try:
    result = await bot_detector.validate_miner_followers(hotkey, handle)
    if result['analyzed']:
        adjusted_rate = original_rate * result['penalty_factor']
    else:
        adjusted_rate = original_rate  # Fallback to original
except Exception as e:
    logger.error(f"Bot detection failed for {hotkey}: {e}")
    adjusted_rate = original_rate  # Always fallback
```

## 📈 Monitoring and Logging

### Bot Detection Logs

The system automatically logs:
- Bot detection penalties applied
- Suspicious accounts flagged
- Analysis statistics

### Custom Monitoring

```python
# In your validator loop
if hasattr(validator, '_bot_detection_patch'):
    stats = validator._bot_detection_patch.get_bot_detection_stats()
    
    if stats['total_analyses'] > 0:
        logger.info(f"Bot Detection Summary:")
        logger.info(f"  Total analyses: {stats['total_analyses']}")
        logger.info(f"  Suspicious accounts: {stats['suspicious_accounts']}")
        logger.info(f"  Suspicious rate: {stats['suspicious_rate']:.2%}")
        logger.info(f"  Avg bot probability: {stats['avg_bot_probability']:.3f}")
```

### Integration with Wandb/Logging

```python
# Log to Wandb
wandb.log({
    "bot_detection/total_analyses": stats['total_analyses'],
    "bot_detection/suspicious_rate": stats['suspicious_rate'],
    "bot_detection/avg_bot_probability": stats['avg_bot_probability']
})
```

## 🔄 Testing Integration

### Test the Patch

```bash
cd follower-analysis/src
python validator_patch.py
```

### Validate Instagram Handle Extraction

```python
from validator_patch import ValidatorBotDetectionPatch

patch = ValidatorBotDetectionPatch()

# Test URL extraction
test_urls = [
    "https://instagram.com/your_test_account/p/ABC123/",
    "Made with @infinitevibe.ai on #bittensor --- @test_creator"
]

for url in test_urls:
    handle = patch.extract_instagram_handle(url, url)
    print(f"Extracted: {handle}")
```

## 🚫 Disabling Bot Detection

To disable bot detection temporarily:

```python
# Method 1: Configuration
config = ValidatorConfig(enable_bot_detection=False)

# Method 2: Runtime disable
validator._bot_detection_patch.config.enable_bot_detection = False

# Method 3: Remove patch entirely
if hasattr(validator, '_original_calculate_miner_engagement_rates'):
    validator._calculate_miner_engagement_rates = validator._original_calculate_miner_engagement_rates
```

## 🔧 Performance Considerations

### API Rate Limits
- Instagram API: ~200 calls/hour
- Analysis cached for 24 hours by default
- Batch followers to stay within limits

### Memory Usage
- Cache cleared after 1000 analyses
- Follower data not stored permanently
- Analysis results stored temporarily

### Processing Time
- Typical analysis: 5-30 seconds per account
- Runs asynchronously during weight calculation
- Doesn't block main validator loop

## 🐛 Troubleshooting

### Common Issues

**1. Import Errors**
```python
# Ensure correct path
sys.path.append('/correct/path/to/follower_analysis')
```

**2. Instagram API Errors**
```python
# Check API configuration
config = ValidatorConfig(enable_bot_detection=False)  # Disable temporarily
```

**3. Handle Extraction Failures**
```python
# Add debug logging
handle = patch.extract_instagram_handle(url, caption)
logger.debug(f"Extracted handle '{handle}' from URL: {url}")
```

**4. Performance Issues**
```python
# Reduce analysis frequency
config = ValidatorConfig(analysis_interval_hours=48)  # Analyze every 2 days
```

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('follower_analysis').setLevel(logging.DEBUG)
```

---

**✅ Integration Complete**

The follower analysis framework is now integrated with your validator and will automatically detect and penalize accounts with suspicious bot followers.

Monitor the logs for bot detection results and adjust configuration as needed.