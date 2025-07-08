#!/bin/bash

# Start validator with background bot detection integration
cd "$(dirname "$0")"
source .venv/bin/activate

# Export environment variables
export $(cat .env | xargs)

# Add src directory to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "🤖 Starting validator with background bot detection integration..."
echo "   - Bot detection enabled: $BOT_DETECTION_ENABLED"
echo "   - Bot threshold: $BOT_THRESHOLD"
echo "   - Max penalty: $MAX_BOT_PENALTY"
echo ""
echo "⚠️  Make sure the background follower analyzer is running!"
echo "   Run: pm2 start ./start_follower_analyzer.sh --name follower-analyzer"
echo ""

# Start the standard validator
# The bot integration will read results from MongoDB
python -m neurons.validating \
  --netuid 89 \
  --wallet.hotkey default \
  --wallet.name subnet89_owner \
  --wallet.path ~/.bittensor/wallets/ \
  --subtensor.network finney \
  --logging.debug \
  --mongodb_uri "${MONGODB_URI:-mongodb://localhost:27017/}"