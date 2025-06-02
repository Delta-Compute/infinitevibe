from argparse import ArgumentParser
from loguru import logger
import bittensor as bt


def get_args():
    parser = ArgumentParser()
    parser.add_argument("--commit-message", type=str, default="gh_username:gh_gist_id")
    parser.add_argument("--netuid", type=int, default=89)
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    return bt.Config(parser=parser)


def main():
    config = get_args()
    logger.info(f"Config: {config}")
    subtensor = bt.subtensor(config=config)
    wallet = bt.wallet(config=config)

    result = subtensor.commit(
        wallet=wallet,
        netuid=config.netuid,
        data=config.commit_message,
    )

    logger.info(f"Result: {result}")


if __name__ == "__main__":
    main()
