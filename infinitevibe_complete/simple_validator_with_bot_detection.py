#!/usr/bin/env python3

# Use the existing validator and patch it with bot detection
import sys
import os
from pathlib import Path

# Add bot detection to path
sys.path.insert(0, str(Path(__file__).parent / "follower_analysis"))

print("🤖 Starting validator with bot detection integration...")

# Import bot detection components first
try:
    from validator_patch import apply_bot_detection_patch, ValidatorConfig
    print("✅ Bot detection framework loaded")
    
    # Set bot detection environment variables for the subprocess
    os.environ['BOT_DETECTION_ENABLED'] = 'true'
    os.environ['BOT_THRESHOLD'] = '0.7'
    os.environ['CONFIDENCE_THRESHOLD'] = '0.5'
    
except ImportError as e:
    print(f"⚠️ Bot detection not available: {e}")

# Now run the original validator
import subprocess
import sys

cmd = [
    sys.executable, "-m", "neurons.validating",
    "--netuid", "89",
    "--wallet.hotkey", "default",
    "--wallet.name", "subnet89_owner",
    "--wallet.path", "~/.bittensor/wallets/",
    "--subtensor.network", "finney",
    "--logging.debug"
]

print(f"🚀 Executing validator: {' '.join(cmd)}")
result = subprocess.run(cmd, cwd=Path(__file__).parent)

if result.returncode != 0:
    print(f"❌ Validator exited with code {result.returncode}")
    sys.exit(result.returncode)
