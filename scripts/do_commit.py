#!/usr/bin/env python3
"""
Bittensor Commitment Management Script

This script allows users to set commitments on the Bittensor network
for specified subnets using wallet credentials.
"""

import sys
from argparse import ArgumentParser
from typing import Optional, Tuple
from dataclasses import dataclass

from async_substrate_interface import SubstrateInterface
from bittensor_wallet import Wallet
from scalecodec.types import GenericCall
from loguru import logger


@dataclass
class NetworkConfig:
    """Configuration for different Bittensor networks."""

    testnet: str = "wss://test.finney.opentensor.ai:443"
    mainnet: str = "wss://entrypoint-finney.opentensor.ai:443"


@dataclass
class CommitmentArgs:
    """Arguments for commitment operations."""

    netuid: int
    wallet_hotkey: str
    wallet_name: str
    commit: str
    network: str


class BittensorCommitmentManager:
    """Manages Bittensor commitment operations."""

    def __init__(self, args: CommitmentArgs):
        self.args = args
        self.network_config = NetworkConfig()
        self.substrate_interface = self._initialize_substrate_interface()
        self.wallet = self._initialize_wallet()

    def _initialize_substrate_interface(self) -> SubstrateInterface:
        """Initialize and return SubstrateInterface with appropriate URL."""
        substrate_url = self._get_substrate_url()
        return SubstrateInterface(url=substrate_url, ss58_format=42)

    def _get_substrate_url(self) -> str:
        """Get the appropriate substrate URL based on network."""
        network_urls = {
            "testnet": self.network_config.testnet,
            "mainnet": self.network_config.mainnet,
        }

        if self.args.network not in network_urls:
            raise ValueError(
                f"Unsupported network: {self.args.network}. "
                f"Supported networks: {list(network_urls.keys())}"
            )

        return network_urls[self.args.network]

    def _initialize_wallet(self) -> Wallet:
        """Initialize and return wallet with provided credentials."""
        return Wallet(name=self.args.wallet_name, hotkey=self.args.wallet_hotkey)

    def get_uid(self) -> Optional[int]:
        """Query and return the UID for the wallet's hotkey."""
        try:
            result = self.substrate_interface.query(
                module="SubtensorModule",
                storage_function="Uids",
                params=[self.args.netuid, self.wallet.hotkey.ss58_address],
                block_hash=None,
            )
            return getattr(result, "value", result)
        except Exception as e:
            logger.error(f"Failed to get UID: {e}")
            return None

    def create_commitment_call(self) -> GenericCall:
        """Create and return a commitment call."""
        data_type = f"Raw{len(self.args.commit)}"

        return self.substrate_interface.compose_call(
            call_module="Commitments",
            call_function="set_commitment",
            call_params={
                "netuid": self.args.netuid,
                "info": {"fields": [[{f"{data_type}": self.args.commit.encode()}]]},
            },
        )

    def sign_and_send_extrinsic(
        self,
        call: GenericCall,
        wait_for_inclusion: bool = True,
        wait_for_finalization: bool = False,
        sign_with: str = "coldkey",
        use_nonce: bool = False,
        period: Optional[int] = None,
        nonce_key: str = "hotkey",
        raise_error: bool = False,
    ) -> Tuple[bool, str]:
        """
        Sign and submit an extrinsic call to the chain.

        Args:
            call: A prepared Call object
            wait_for_inclusion: Whether to wait until the extrinsic is included on chain
            wait_for_finalization: Whether to wait until the extrinsic is finalized
            sign_with: The wallet's keypair to use for signing ('coldkey', 'hotkey', 'coldkeypub')
            use_nonce: Whether to use a unique identifier for the transaction
            period: Number of blocks during which the transaction remains valid
            nonce_key: The type of nonce to use ('hotkey' or 'coldkey')
            raise_error: Whether to raise exceptions instead of returning False

        Returns:
            Tuple of (success: bool, error_message: str)

        Raises:
            AttributeError: If invalid sign_with or nonce_key provided
            Exception: If raise_error is True and operation fails
        """
        self._validate_keypair_options(sign_with, nonce_key)

        signing_keypair = getattr(self.wallet, sign_with)
        extrinsic_data = {"call": call, "keypair": signing_keypair}

        if use_nonce:
            next_nonce = self.substrate_interface.get_account_next_index(
                getattr(self.wallet, nonce_key).ss58_address
            )
            extrinsic_data["nonce"] = next_nonce

        if period is not None:
            extrinsic_data["era"] = {"period": period}

        extrinsic = self.substrate_interface.create_signed_extrinsic(**extrinsic_data)

        try:
            response = self.substrate_interface.submit_extrinsic(
                extrinsic,
                wait_for_inclusion=wait_for_inclusion,
                wait_for_finalization=wait_for_finalization,
            )

            if not wait_for_finalization and not wait_for_inclusion:
                message = "Not waiting for finalization or inclusion."
                logger.debug(f"{message}. Extrinsic: {extrinsic}")
                return True, message

            if response.is_success:
                return True, ""

            if raise_error:
                raise Exception(response.error_message)

            return False, response.error_message

        except Exception as e:
            if raise_error:
                raise
            return False, str(e)

    @staticmethod
    def _validate_keypair_options(sign_with: str, nonce_key: str) -> None:
        """Validate keypair options."""
        possible_keys = ("coldkey", "hotkey", "coldkeypub")

        if sign_with not in possible_keys:
            raise AttributeError(
                f"'sign_with' must be one of {possible_keys}, not '{sign_with}'"
            )

        if nonce_key not in possible_keys:
            raise AttributeError(
                f"'nonce_key' must be one of {possible_keys}, not '{nonce_key}'"
            )

    def execute_commitment(self) -> bool:
        """Execute the commitment operation."""
        logger.info(f"Starting commitment process for netUID {self.args.netuid}")

        # Get UID for validation
        uid = self.get_uid()
        if uid is None:
            logger.error("Failed to retrieve UID. Cannot proceed with commitment.")
            return False

        logger.info(f"Found UID: {uid}")

        # Create and execute commitment
        call = self.create_commitment_call()
        success, error = self.sign_and_send_extrinsic(call, sign_with="hotkey")

        if success:
            logger.info("Commitment successful")
            return True
        else:
            logger.error(f"Commitment failed: {error}")
            return False


def parse_arguments() -> CommitmentArgs:
    """Parse and return command line arguments."""
    parser = ArgumentParser(
        description="Set commitment on Bittensor network",
        formatter_class=ArgumentParser.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--netuid", type=int, required=True, help="Network UID for the subnet"
    )
    parser.add_argument(
        "--wallet-hotkey", type=str, required=True, help="Wallet hotkey name"
    )
    parser.add_argument("--wallet-name", type=str, required=True, help="Wallet name")
    parser.add_argument(
        "--commit", type=str, required=True, help="Commitment data to set"
    )
    parser.add_argument(
        "--network",
        type=str,
        required=True,
        choices=["testnet", "mainnet"],
        help="Network to connect to",
    )

    args = parser.parse_args()

    return CommitmentArgs(
        netuid=args.netuid,
        wallet_hotkey=args.wallet_hotkey,
        wallet_name=args.wallet_name,
        commit=args.commit,
        network=args.network,
    )


def main() -> None:
    """Main entry point."""
    try:
        args = parse_arguments()
        logger.info(f"Parsed arguments: {args}")

        commitment_manager = BittensorCommitmentManager(args)
        success = commitment_manager.execute_commitment()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
