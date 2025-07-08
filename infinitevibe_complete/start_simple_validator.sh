#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

# Set environment variables
set -a
source .env
set +a

echo "🚀 Starting simple validator with bot detection..."
python simple_validator_with_bot_detection.py
