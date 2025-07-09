#!/bin/bash

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export BOT_DETECTION_ENABLED=true
export BOT_THRESHOLD=0.6
export CONFIDENCE_THRESHOLD=0.5

echo "🚀 Starting Enhanced TensorFlix Validator V2 with Growth-Focused Scoring..."
echo "   - Bot detection enabled: true"
echo "   - Bot threshold: 0.6 (stricter)"
echo "   - Confidence threshold: 0.5"
echo "   - Scoring: GROWTH × ENGAGEMENT"
echo "   - Python path: ${PYTHONPATH}"
echo "   - Python executable: $(which python)"
echo "   - Python version: $(python --version)"

# Run the enhanced validator v2
python enhanced_validator_v2.py \
  --netuid 89 \
  --wallet.name subnet89_owner \
  --wallet.hotkey default \
  --wallet.path ~/.bittensor/wallets/ \
  --subtensor.network finney \
  --mongodb_uri mongodb://localhost:27017/ \
  --logging.debug