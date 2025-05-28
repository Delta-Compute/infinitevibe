import asyncio
import os
from contextlib import asynccontextmanager
from typing import List, Optional, cast

from async_substrate_interface import AsyncSubstrateInterface
from fastapi import FastAPI, HTTPException
from loguru import logger
from scalecodec.utils.ss58 import ss58_encode

from tensorflix.services.chain_syncer.data_types import PeerMetadata


class ChainSyncer:
    """Handles blockchain data synchronization and peer metadata management."""

    def __init__(self):
        # Environment variables
        self.netuid = int(os.getenv("NETUID", 89))
        self.subtensor_network = os.getenv("SUBTENSOR_NETWORK", "mainnet")

        # Network configuration
        self.substrate_url = self._get_substrate_url()

        # Substrate interface
        self.substrate_interface: Optional[AsyncSubstrateInterface] = None

        # Data storage
        self.peers_metadata: List[PeerMetadata] = []

        # Background task
        self.background_task: Optional[asyncio.Task] = None

        logger.info(f"Using {self.subtensor_network} network")
        logger.info(f"Substrate URL: {self.substrate_url}")
        logger.info(f"Netuid: {self.netuid}")

    def _get_substrate_url(self) -> str:
        """Get the appropriate substrate URL based on network."""
        urls = {
            "testnet": "wss://test.finney.opentensor.ai:443",
            "mainnet": "wss://entrypoint-finney.opentensor.ai:443",
        }

        url = urls.get(self.subtensor_network)
        if not url:
            raise ValueError(f"Unknown network: {self.subtensor_network}")

        return url

    async def initialize(self):
        """Initialize the substrate interface."""
        if not self.substrate_interface:
            self.substrate_interface = AsyncSubstrateInterface(
                url=self.substrate_url,
                ss58_format=42,
            )
            logger.info("Substrate interface initialized")

    async def close(self):
        """Clean up resources."""
        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass

        if self.substrate_interface:
            await self.substrate_interface.close()
            logger.info("Substrate interface closed")

    @staticmethod
    def decode_metadata(metadata: dict) -> str:
        """Decode metadata from commitment data."""
        try:
            commitment = metadata["info"]["fields"][0][0]
            bytes_tuple = commitment[next(iter(commitment.keys()))][0]
            return bytes(bytes_tuple).decode()
        except (KeyError, IndexError, TypeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode metadata: {e}")
            return ""

    async def _update_peer_metadata_for_uid(
        self, uid: int, hotkey: bytes
    ) -> Optional[PeerMetadata]:
        """Update metadata for a single peer."""
        try:
            ss58_hotkey = ss58_encode(bytes(hotkey[0]).hex(), 42)
            logger.info(f"Updating metadata for UID {uid} - {ss58_hotkey}")

            commit_data = await self.substrate_interface.query(
                module="Commitments",
                storage_function="CommitmentOf",
                params=[self.netuid, ss58_hotkey],
                block_hash=None,
            )

            logger.info(f"Commit data: {commit_data}")

            if not commit_data:
                logger.warning(f"No commit data found for UID {uid}")
                return None

            commit_data = cast(dict, commit_data)
            decoded_commit = self.decode_metadata(commit_data)

            peer_metadata = PeerMetadata(
                uid=str(uid),
                hotkey=ss58_hotkey,
                commit=decoded_commit,
            )

            logger.info(
                f"Updating submissions for {peer_metadata.uid} - "
                f"{peer_metadata.hotkey} - {peer_metadata.commit}"
            )

            await peer_metadata.update_submissions()
            return peer_metadata

        except Exception as e:
            logger.error(f"Failed to update metadata for UID {uid}: {e}")
            return None

    async def update_peer_metadata(self):
        """Update metadata for all peers."""
        try:
            if not self.substrate_interface:
                raise RuntimeError("Substrate interface not initialized")

            logger.info("Starting peer metadata update")

            metagraph_data = await self.substrate_interface.runtime_call(
                api="SubnetInfoRuntimeApi",
                method="get_metagraph",
                params=[self.netuid],
                block_hash=None,
            )

            if not metagraph_data or not metagraph_data.value:
                logger.error("Failed to fetch metagraph data")
                return

            raw_metagraph = metagraph_data.value
            hotkeys = raw_metagraph.get("hotkeys", [])

            if not hotkeys:
                logger.warning("No hotkeys found in metagraph")
                return

            # Process all peers concurrently
            tasks = [
                self._update_peer_metadata_for_uid(uid, hotkey)
                for uid, hotkey in enumerate(hotkeys)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out None results and exceptions
            valid_metadata = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Exception in peer metadata update: {result}")
                elif result is not None:
                    valid_metadata.append(result)

            self.peers_metadata = valid_metadata
            logger.info(f"Updated metadata for {len(valid_metadata)} peers")

        except Exception as e:
            logger.error(f"Failed to update peer metadata: {e}")

    async def run_periodic_updates(self, interval_seconds: int = 600):
        """Run periodic metadata updates."""
        logger.info(f"Starting periodic updates every {interval_seconds} seconds")

        while True:
            try:
                await self.update_peer_metadata()
                logger.info("Periodic update completed successfully")
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")

            await asyncio.sleep(interval_seconds)

    def start_background_updates(self, interval_seconds: int = 600):
        """Start background task for periodic updates."""
        if self.background_task and not self.background_task.done():
            logger.warning("Background task already running")
            return

        self.background_task = asyncio.create_task(
            self.run_periodic_updates(interval_seconds)
        )
        logger.info("Background update task started")

    def get_peers_metadata(self) -> List[PeerMetadata]:
        """Get current peers metadata."""
        return self.peers_metadata.copy()


# Global chain syncer instance
chain_syncer = ChainSyncer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await chain_syncer.initialize()
    chain_syncer.start_background_updates()

    yield

    # Shutdown
    await chain_syncer.close()


# FastAPI app with lifespan management
app = FastAPI(lifespan=lifespan)


@app.get("/get_all_peers_metadata")
async def get_all_peers_metadata():
    """Get metadata for all peers."""
    try:
        metadata = chain_syncer.get_peers_metadata()
        return {"success": True, "count": len(metadata), "data": metadata}
    except Exception as e:
        logger.error(f"Error getting peers metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve peer metadata")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "network": chain_syncer.subtensor_network,
        "netuid": chain_syncer.netuid,
        "peers_count": len(chain_syncer.peers_metadata),
    }
