#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path
from loguru import logger
import bittensor as bt
from motor.motor_asyncio import AsyncIOMotorClient

# Add the src directory to Python path for bot detection
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "follower_analysis"))

# Import bot detection integration
try:
    from validator_patch import apply_bot_detection_patch, ValidatorConfig
    BOT_DETECTION_AVAILABLE = True
    logger.info("✅ Bot detection framework loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Bot detection framework not available: {e}")
    BOT_DETECTION_AVAILABLE = False

async def main():
    """Main validator startup with bot detection"""

    logger.info("🚀 Starting TensorFlix Validator with Bot Detection")

    # Set up environment variables
    os.environ.setdefault('MONGODB_URI', 'mongodb://localhost:27017/')
    
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=89)
    parser.add_argument("--wallet.hotkey", dest="wallet_hotkey", default="default")
    parser.add_argument("--wallet.name", dest="wallet_name", default="subnet89_owner")
    parser.add_argument("--wallet.path", dest="wallet_path", default="~/.bittensor/wallets/")
    parser.add_argument("--subtensor.network", dest="subtensor_network", default="finney")
    parser.add_argument("--logging.debug", dest="logging_debug", action="store_true")
    parser.add_argument("--mongodb_uri", default="mongodb://localhost:27017/")

    args = parser.parse_args()

    # Setup logging
    if args.logging_debug:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")

    # Use the existing validator approach but with subprocess to avoid metagraph issues
    try:
        # Import and use the existing validator module approach
        from tensorflix.validator import TensorFlixValidator
        from tensorflix.config import CONFIG
        
        # Create config object the way the validator expects
        config = type('Config', (), {
            'netuid': args.netuid,
            'wallet': type('Wallet', (), {
                'name': args.wallet_name,
                'hotkey': args.wallet_hotkey,
                'path': args.wallet_path
            })(),
            'subtensor': type('Subtensor', (), {
                'network': args.subtensor_network
            })(),
            'mongodb_uri': args.mongodb_uri
        })()

        # Initialize components
        wallet = bt.wallet(
            name=config.wallet.name,
            hotkey=config.wallet.hotkey,
            path=config.wallet.path
        )
        
        subtensor = bt.AsyncSubtensor(network=config.subtensor.network)
        
        # Initialize metagraph properly
        metagraph = subtensor.metagraph(config.netuid)
        
        # Initialize MongoDB
        db_client = AsyncIOMotorClient(config.mongodb_uri)

        # Create validator instance
        validator = TensorFlixValidator(
            wallet=wallet,
            subtensor=subtensor,
            metagraph=metagraph,
            db_client=db_client,
            netuid=config.netuid,
        )

        # Apply bot detection patch if available
        if BOT_DETECTION_AVAILABLE:
            try:
                # Configure bot detection
                bot_config = ValidatorConfig(
                    bot_threshold=0.7,
                    confidence_threshold=0.5,
                    min_followers_to_analyze=50,
                    enable_bot_detection=True
                )

                # Apply the patch
                patch = apply_bot_detection_patch(validator, bot_config)

                logger.info("🤖 Bot detection successfully integrated!")
                logger.info(f"   - Bot threshold: {bot_config.bot_threshold}")
                logger.info(f"   - Confidence threshold: {bot_config.confidence_threshold}")
                logger.info(f"   - Enabled: {bot_config.enable_bot_detection}")

            except Exception as e:
                logger.error(f"❌ Failed to apply bot detection patch: {e}")
                logger.info("⚠️ Continuing without bot detection")

        # Run the validator
        await validator.run()

    except Exception as e:
        logger.error(f"Failed to start validator: {e}")
        # Fallback to subprocess approach
        logger.info("Falling back to subprocess approach...")
        
        import subprocess
        cmd = [
            sys.executable, "-m", "neurons.validating",
            "--netuid", str(args.netuid),
            "--wallet.hotkey", args.wallet_hotkey,
            "--wallet.name", args.wallet_name,
            "--wallet.path", args.wallet_path,
            "--subtensor.network", args.subtensor_network,
            "--logging.debug" if args.logging_debug else "",
        ]
        
        # Filter out empty args
        cmd = [arg for arg in cmd if arg]
        
        logger.info(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd)

if __name__ == "__main__":
    asyncio.run(main())
