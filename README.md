# InfiniteVibe Validator with Growth-Focused Scoring

Enhanced TensorFlix validator for Bittensor subnet 89 with bot detection and growth-focused scoring.

## Key Features

- **Growth × Engagement Scoring**: Multiplicative formula prevents gaming
- **12-hour Growth Tracking**: Fast-response follower growth detection  
- **Bot Detection**: Advanced Instagram follower analysis
- **Minimum Thresholds**: 500+ followers, 12+ hours history required

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys in .env
APIFY_API_KEY=your_key
SIGHTENGINE_API_USER=your_user  
SIGHTENGINE_API_SECRET=your_secret

# Migrate follower history (first run)
python migrate_follower_history.py

# Start validator
./start_growth_validator.sh

# Monitor scores
python monitor_growth_scores.py
```

## Core Files

- `enhanced_validator_v2.py` - Main validator with growth scoring
- `new_growth_scoring.py` - Multiplicative scoring formula
- `src/validator_integration.py` - Bot detection integration
- `src/background_follower_analyzer.py` - Apify Instagram analysis

## Scoring Formula

```
final_score = authentic_growth_score × engagement_multiplier

Where:
- Growth score requires positive follower growth over 12+ hours
- Bot penalty applies up to 90% reduction for detected bots  
- Engagement multiplier ranges 0.5x to 2.0x based on likes/comments
- Zero growth = zero rewards (prevents bot engagement gaming)
```

## Requirements

- MongoDB running on localhost:27017
- Bittensor wallet configured
- Apify API access for Instagram data
- SightEngine API for content moderation