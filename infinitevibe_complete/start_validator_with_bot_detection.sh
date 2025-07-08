#!/bin/bash

cd "$(dirname "$0")"
source .venv/bin/activate

# Set environment variables
set -a
source .env
set +a

# Add the follower analysis directory to Python path
export PYTHONPATH="$(pwd):$(pwd)/follower_analysis:${PYTHONPATH}"

echo "🤖 Starting validator with bot detection..."
echo "   - Bot detection enabled: $BOT_DETECTION_ENABLED"
echo "   - Bot threshold: $BOT_THRESHOLD"
echo "   - Confidence threshold: $CONFIDENCE_THRESHOLD"
echo "   - Python path: $PYTHONPATH"

# Start the modified validator with bot detection
python modified_validator.py \
  --netuid 89 \
  --wallet.hotkey default \
  --wallet.name subnet89_owner \
  --wallet.path ~/.bittensor/wallets/ \
  --subtensor.network finney \
  --logging.debug
