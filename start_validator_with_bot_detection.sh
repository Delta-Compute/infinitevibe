#!/bin/bash

# Start validator with bot detection enabled
cd "$(dirname "$0")"
source .venv/bin/activate

# Export environment variables
export $(cat .env | xargs)

# Add the src directory to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Enable bot detection logging
export BOT_DETECTION_ENABLED=true
export BOT_THRESHOLD=0.7
export CONFIDENCE_THRESHOLD=0.5

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
  --logging.debug \
  --mongodb_uri "${MONGODB_URI:-mongodb://localhost:27017/}"