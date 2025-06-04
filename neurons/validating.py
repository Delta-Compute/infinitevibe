#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os

import bittensor as bt
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from tensorflix.config import CONFIG
from tensorflix.validator import TensorFlixValidator
from dotenv import load_dotenv

load_dotenv()


async def _bootstrap() -> None:
    parser = argparse.ArgumentParser(description="TensorFlix validator")
    parser.add_argument("--netuid", type=int, default=CONFIG.netuid)
    bt.wallet.add_args(parser)
    bt.async_subtensor.add_args(parser)
    cli_cfg = bt.config(parser=parser)

    wallet = bt.wallet(config=cli_cfg)
    subtensor = bt.async_subtensor(config=cli_cfg)
    metagraph = await subtensor.metagraph(netuid=cli_cfg.netuid)

    logger.success(
        "startup_complete",
        extra={
            "wallet": wallet.hotkey.ss58_address,
            "network": cli_cfg.subtensor.network,
            "netuid": cli_cfg.netuid,
            "neurons": metagraph.n.item(),
        },
    )

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        logger.critical("MONGO_URI_not_set")
        raise SystemExit(1)

    db_client = AsyncIOMotorClient(mongo_uri)
    validator = TensorFlixValidator(
        wallet, subtensor, metagraph, db_client, cli_cfg.netuid
    )
    await validator.run()


if __name__ == "__main__":
    asyncio.run(_bootstrap())
