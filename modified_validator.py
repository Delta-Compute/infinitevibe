"""
Modified validator startup script with bot detection integration
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger
import bittensor as bt
from motor.motor_asyncio import AsyncIOMotorClient

# Add the src directory to Python path for bot detection
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the original validator
from tensorflix.validator import TensorFlixValidator

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
    
    # Parse command line arguments
    parser = bt.cli.__create_parser__()
    bt.cli.add_args(parser, command="validator")
    config = bt.config(parser)
    
    # Setup logging
    if config.logging.debug:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    logger.info("🚀 Starting TensorFlix Validator with Bot Detection")
    
    # Initialize Bittensor components
    wallet = bt.wallet(config=config)
    subtensor = bt.AsyncSubtensor(config=config)
    metagraph = bt.metagraph(netuid=config.netuid, network=config.subtensor.network)
    
    logger.info(f"Wallet: {wallet}")
    logger.info(f"Subtensor: {subtensor}")
    logger.info(f"Metagraph: {metagraph}")
    
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
                bot_threshold=0.7,  # 70% bot probability threshold
                confidence_threshold=0.5,  # 50% confidence required
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
    else:
        logger.warning("⚠️ Bot detection not available - running standard validator")
    
    # Run the validator
    try:
        await validator.run()
    except KeyboardInterrupt:
        logger.info("Validator stopped by user")
    except Exception as e:
        logger.error(f"Validator error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())