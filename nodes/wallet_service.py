"""
Wallet Service Module - Handles wallet management operations.

This module provides clean, testable functions for wallet operations,
keeping the CLI and other components focused on their primary responsibilities.
"""

from typing import List, Optional
from .config import load_monitored_wallets, save_monitored_wallets, should_log_verbose


class WalletService:
    """Service class for wallet management operations."""

    @staticmethod
    def get_wallets() -> List[str]:
        """Get the list of monitored wallets."""
        return load_monitored_wallets()

    @staticmethod
    def add_wallet(wallet_address: str) -> bool:
        """Add a wallet to the monitored list.

        Args:
            wallet_address: The wallet address to add

        Returns:
            True if added successfully, False if already exists
        """
        wallets = load_monitored_wallets()

        # Validate wallet address format (basic Ethereum address check)
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            raise ValueError(f"Invalid Ethereum address format: {wallet_address}")

        if wallet_address in wallets:
            return False

        wallets.append(wallet_address)
        save_monitored_wallets(wallets)
        return True

    @staticmethod
    def remove_wallet(wallet_address: str) -> bool:
        """Remove a wallet from the monitored list.

        Args:
            wallet_address: The wallet address to remove

        Returns:
            True if removed successfully, False if not found
        """
        wallets = load_monitored_wallets()

        if wallet_address not in wallets:
            return False

        wallets.remove(wallet_address)
        save_monitored_wallets(wallets)
        return True

    @staticmethod
    def validate_wallet_address(address: str) -> bool:
        """Validate Ethereum wallet address format.

        Args:
            address: The address to validate

        Returns:
            True if valid format, False otherwise
        """
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        # Basic hex validation
        try:
            int(address, 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def get_wallet_count() -> int:
        """Get the number of monitored wallets."""
        return len(load_monitored_wallets())

    @staticmethod
    def clear_all_wallets() -> None:
        """Remove all monitored wallets."""
        save_monitored_wallets([])
