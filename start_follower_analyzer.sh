#!/bin/bash

# Start background follower analyzer service
cd "$(dirname "$0")"
source .venv/bin/activate

# Export environment variables
export $(cat .env | xargs)

# Add src directory to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Additional follower analyzer settings
export FOLLOWER_SAMPLE_SIZE="${FOLLOWER_SAMPLE_SIZE:-50}"
export ANALYSIS_INTERVAL_HOURS="${ANALYSIS_INTERVAL_HOURS:-6}"
export ANALYSIS_COOLDOWN_HOURS="${ANALYSIS_COOLDOWN_HOURS:-24}"

echo "🤖 Starting Background Follower Analyzer..."
echo "   - Apify API Key: ${APIFY_API_KEY:0:10}..."
echo "   - Sample size: $FOLLOWER_SAMPLE_SIZE followers"
echo "   - Analysis interval: $ANALYSIS_INTERVAL_HOURS hours"
echo "   - Cooldown period: $ANALYSIS_COOLDOWN_HOURS hours"
echo "   - MongoDB: $MONGODB_URI"

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the analyzer
python src/background_follower_analyzer.py