#!/usr/bin/env python3
"""
Comprehensive unit tests for WalletService module.

Tests all functions with proper input/output expectations,
covering both success and failure scenarios.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

# Add the parent directory to the path to import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from wallet_service import WalletService


class TestWalletService(unittest.IsolatedAsyncioTestCase):
    """Test suite for WalletService functionality."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
        self.temp_file.close()
        self.test_file = self.temp_file.name

        # Mock the config file path
        self.original_file = None

    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary file
        if os.path.exists(self.test_file):
            os.unlink(self.test_file)

        # Restore original file if it was patched
        if self.original_file and os.path.exists(self.original_file):
            os.unlink(self.original_file)

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_get_wallets_empty(self, mock_file):
        """Test getting wallets when none are configured."""
        # Create empty file
        with open(mock_file, 'w') as f:
            f.write("")

        result = WalletService.get_wallets()
        self.assertEqual(result, [])

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_get_wallets_from_file(self, mock_file):
        """Test getting wallets from configuration file."""
        # Create file with wallets
        with open(mock_file, 'w') as f:
            f.write("# Test wallets\n")
            f.write("0x1234567890123456789012345678901234567890\n")
            f.write("# Comment\n")
            f.write("0xabcdef1234567890abcdef1234567890abcdef12\n")

        result = WalletService.get_wallets()
        expected = [
            "0x1234567890123456789012345678901234567890",
            "0xabcdef1234567890abcdef1234567890abcdef12"
        ]
        self.assertEqual(result, expected)

    @patch('wallet_service.load_monitored_wallets')
    def test_get_wallets_from_env(self, mock_load):
        """Test getting wallets from environment variable (takes precedence)."""
        # Mock the load function to return env wallets
        mock_load.return_value = [
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222"
        ]

        result = WalletService.get_wallets()
        expected = [
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222"
        ]
        self.assertEqual(result, expected)
        mock_load.assert_called_once()

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_add_wallet_success(self, mock_file):
        """Test successfully adding a wallet."""
        # Start with empty file
        with open(mock_file, 'w') as f:
            f.write("")

        # Add a wallet
        result = WalletService.add_wallet("0x1234567890123456789012345678901234567890")
        self.assertTrue(result)

        # Verify it was added
        wallets = WalletService.get_wallets()
        self.assertEqual(len(wallets), 1)
        self.assertIn("0x1234567890123456789012345678901234567890", wallets)

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_add_wallet_duplicate(self, mock_file):
        """Test adding a wallet that already exists."""
        # Start with a wallet
        with open(mock_file, 'w') as f:
            f.write("0x1234567890123456789012345678901234567890\n")

        # Try to add the same wallet
        result = WalletService.add_wallet("0x1234567890123456789012345678901234567890")
        self.assertFalse(result)

        # Verify only one copy exists
        wallets = WalletService.get_wallets()
        self.assertEqual(len(wallets), 1)

    def test_add_wallet_invalid_format(self):
        """Test adding a wallet with invalid format."""
        with self.assertRaises(ValueError):
            WalletService.add_wallet("invalid_address")

    def test_add_wallet_wrong_length(self):
        """Test adding a wallet with wrong length."""
        with self.assertRaises(ValueError):
            WalletService.add_wallet("0x123")  # Too short

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_remove_wallet_success(self, mock_file):
        """Test successfully removing a wallet."""
        # Start with a wallet
        with open(mock_file, 'w') as f:
            f.write("0x1234567890123456789012345678901234567890\n")

        # Remove the wallet
        result = WalletService.remove_wallet("0x1234567890123456789012345678901234567890")
        self.assertTrue(result)

        # Verify it was removed
        wallets = WalletService.get_wallets()
        self.assertEqual(len(wallets), 0)

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_remove_wallet_not_found(self, mock_file):
        """Test removing a wallet that doesn't exist."""
        # Start with empty file
        with open(mock_file, 'w') as f:
            f.write("")

        # Try to remove non-existent wallet
        result = WalletService.remove_wallet("0x1234567890123456789012345678901234567890")
        self.assertFalse(result)

    def test_validate_wallet_address_valid(self):
        """Test validating a valid Ethereum address."""
        valid_addresses = [
            "0x1234567890123456789012345678901234567890",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x0000000000000000000000000000000000000000",
            "0xffffffffffffffffffffffffffffffffffffffff"
        ]

        for address in valid_addresses:
            with self.subTest(address=address):
                self.assertTrue(WalletService.validate_wallet_address(address))

    def test_validate_wallet_address_invalid(self):
        """Test validating invalid Ethereum addresses."""
        invalid_addresses = [
            "1234567890123456789012345678901234567890",  # Missing 0x
            "0x123456789012345678901234567890123456789",  # Too short
            "0x12345678901234567890123456789012345678901",  # Too long
            "0xgggggggggggggggggggggggggggggggggggggg",  # Invalid hex
            "",  # Empty
            "0x",  # Just prefix
            "not_an_address"  # Not hex
        ]

        for address in invalid_addresses:
            with self.subTest(address=address):
                self.assertFalse(WalletService.validate_wallet_address(address))

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_get_wallet_count(self, mock_file):
        """Test getting wallet count."""
        # Test empty
        with open(mock_file, 'w') as f:
            f.write("")
        self.assertEqual(WalletService.get_wallet_count(), 0)

        # Test with wallets
        with open(mock_file, 'w') as f:
            f.write("0x1234567890123456789012345678901234567890\n")
            f.write("0xabcdef1234567890abcdef1234567890abcdef12\n")
        self.assertEqual(WalletService.get_wallet_count(), 2)

    @patch('nodes.config.MONITORED_WALLETS_FILE', new_callable=lambda: tempfile.mktemp(suffix='.txt'))
    def test_clear_all_wallets(self, mock_file):
        """Test clearing all wallets."""
        # Start with wallets
        with open(mock_file, 'w') as f:
            f.write("0x1234567890123456789012345678901234567890\n")
            f.write("0xabcdef1234567890abcdef1234567890abcdef12\n")

        # Verify wallets exist
        self.assertEqual(WalletService.get_wallet_count(), 2)

        # Clear all wallets
        WalletService.clear_all_wallets()

        # Verify they're gone
        self.assertEqual(WalletService.get_wallet_count(), 0)


if __name__ == '__main__':
    unittest.main()
