#!/bin/bash

# Start background follower analyzer service
cd "$(dirname "$0")"
source .venv/bin/activate

# Export environment variables from .env file  
export $(cat .env | xargs)

# Add src directory to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "🤖 Starting Background Follower Analyzer..."
echo "   - Python path: $PYTHONPATH"
echo "   - Apify API Key: ${APIFY_API_KEY:0:15}..."
echo "   - MongoDB: $MONGODB_URI"
echo "   - Sample size: ${FOLLOWER_SAMPLE_SIZE:-50} followers"
echo "   - Analysis interval: ${ANALYSIS_INTERVAL_HOURS:-12} hours"

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the analyzer
python src/background_follower_analyzer.py