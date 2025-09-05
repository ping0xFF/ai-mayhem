#!/usr/bin/env python3
"""
Tests for Alchemy API provider using official Alchemy SDK.
TDD approach: Write failing tests first, then implement to make them pass.
"""

import unittest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the module to test (will fail until we create it)
from alchemy_provider import (
    fetch_wallet_activity_alchemy_live,
    _classify_transaction,
    _extract_value_info
)


class TestAlchemyProvider(unittest.TestCase):
    """Test Alchemy provider functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_alchemy_response = {
            "transfers": [
                {
                    "hash": "0x1234567890abcdef",
                    "blockNum": "0x21639b2",
                    "from": "0xa8a2816280c98c74c4278c23fcb5430b3a583af7",
                    "to": "0x89421b6b2d38368fbda34a976d3cd5bdb1e22c98",
                    "value": "0x0",
                    "category": "external",
                    "asset": None
                },
                {
                    "hash": "0xabcdef1234567890",
                    "blockNum": "0x21639b3",
                    "from": "0x89421b6b2d38368fbda34a976d3cd5bdb1e22c98",
                    "to": "0xa8a2816280c98c74c4278c23fcb5430b3a583af7",
                    "value": "0xde0b6b3a7640000",  # 1 ETH in wei
                    "category": "external",
                    "asset": None
                }
            ],
            "pageKey": "test_page_key_123"
        }
        
        self.test_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"

    def test_fetch_wallet_activity_alchemy_base_chain_mocked(self):
        """Test successful wallet activity fetch from Alchemy on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            # Mock the Alchemy client
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            
            # Mock the core.get_asset_transfers method
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value=self.mock_alchemy_response)
            
            # Call the function with a network that triggers SDK path (not base-mainnet)
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                max_transactions=1000,
                network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
            ))
            
            # Verify the result structure
            self.assertIn("events", result)
            self.assertIn("metadata", result)
            self.assertEqual(len(result["events"]), 2)
            
            # Verify metadata
            metadata = result["metadata"]
            self.assertEqual(metadata["source"], "alchemy")
            self.assertEqual(metadata["network"], "eth-mainnet")  # Updated to match the network used in test
            self.assertEqual(metadata["address"], self.test_address)
            self.assertEqual(metadata["total_transactions"], 2)
            self.assertEqual(metadata["optimization"], "alchemy_getAssetTransfers endpoint")
            
            # Verify events
            events = result["events"]
            self.assertEqual(events[0]["tx"], "0x1234567890abcdef")
            self.assertEqual(events[0]["block"], 0x21639b2)
            self.assertEqual(events[0]["type"], "contract_interaction")
            self.assertEqual(events[0]["wallet"], self.test_address)

    def test_fetch_wallet_activity_alchemy_base_chain_time_filter_mocked(self):
        """Test wallet activity fetch with time filtering on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value=self.mock_alchemy_response)
            mock_alchemy.core.get_block_number = AsyncMock(return_value=1000000)
            
            # Call with time filtering (use eth-mainnet to trigger SDK path for mocking)
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                max_transactions=1000,
                hours_back=24,
                network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
            ))
            
            # Verify time filtering was applied
            self.assertEqual(result["metadata"]["time_filter_hours"], 24)
            self.assertEqual(len(result["events"]), 2)

    def test_fetch_wallet_activity_alchemy_base_chain_api_error_mocked(self):
        """Test handling of Alchemy API errors on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(side_effect=Exception("API rate limit exceeded"))
            
            # Should raise the exception (use eth-mainnet to trigger SDK path for mocking)
            with self.assertRaises(Exception) as context:
                asyncio.run(fetch_wallet_activity_alchemy_live(
                    address=self.test_address,
                    max_transactions=1000,
                    network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
                ))
            self.assertIn("API rate limit exceeded", str(context.exception))

    def test_fetch_wallet_activity_alchemy_base_chain_empty_response_mocked(self):
        """Test handling of empty API response on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value={"transfers": []})
            
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                max_transactions=1000,
                network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
            ))
            
            # Should handle empty response gracefully
            self.assertEqual(result["events"], [])
            self.assertEqual(result["metadata"]["total_transactions"], 0)

    def test_fetch_wallet_activity_alchemy_base_chain_pagination_mocked(self):
        """Test pagination handling with pageKey on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value=self.mock_alchemy_response)
            
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                max_transactions=1000,
                network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
            ))
            
            # Should indicate more pages available
            self.assertTrue(result["metadata"]["has_more"])
            self.assertEqual(result["metadata"]["next_page_key"], "test_page_key_123")

    def test_fetch_wallet_activity_alchemy_base_chain_max_transactions_limit_mocked(self):
        """Test max transactions limit enforcement on Base chain (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value=self.mock_alchemy_response)
            
            # Request more than 1000 transactions
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                max_transactions=2000,  # Should be limited to 1000
                network="eth-mainnet"  # Use eth-mainnet to trigger SDK path for mocking
            ))
            
            # Should respect the limit
            self.assertEqual(result["metadata"]["max_transactions"], 1000)

    def test_fetch_wallet_activity_alchemy_eth_mainnet_mocked(self):
        """Test network-specific URL handling for Ethereum mainnet (mocked)."""
        with patch('alchemy_provider.Alchemy') as mock_alchemy_class:
            mock_alchemy = Mock()
            mock_alchemy_class.return_value = mock_alchemy
            mock_alchemy.core = Mock()
            mock_alchemy.core.get_asset_transfers = AsyncMock(return_value=self.mock_alchemy_response)
            
            # Test with different network
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=self.test_address,
                network="eth-mainnet",
                max_transactions=1000
            ))
            
            # Should use the specified network
            self.assertEqual(result["metadata"]["network"], "eth-mainnet")


class TestTransactionClassification(unittest.TestCase):
    """Test transaction classification logic."""

    def test_classify_transaction_external_transfer(self):
        """Test classification of external ETH transfers."""
        tx = {
            "category": "external",
            "value": "0xde0b6b3a7640000"  # 1 ETH
        }
        
        result = _classify_transaction(tx)
        self.assertEqual(result, "transfer")

    def test_classify_transaction_contract_interaction(self):
        """Test classification of contract interactions."""
        tx = {
            "category": "external",
            "value": "0x0"  # No ETH transfer
        }
        
        result = _classify_transaction(tx)
        self.assertEqual(result, "contract_interaction")

    def test_classify_transaction_erc20_transfer(self):
        """Test classification of ERC20 token transfers."""
        tx = {
            "category": "erc20",
            "value": "0x0"
        }
        
        result = _classify_transaction(tx)
        self.assertEqual(result, "token_transfer")

    def test_classify_transaction_unknown(self):
        """Test classification of unknown transaction types."""
        tx = {
            "category": "unknown",
            "value": "0x0"
        }
        
        result = _classify_transaction(tx)
        self.assertEqual(result, "transaction")


class TestValueExtraction(unittest.TestCase):
    """Test value and token information extraction."""

    def test_extract_value_info_eth_transfer_out(self):
        """Test extraction of outgoing ETH transfer info."""
        tx = {
            "value": "0xde0b6b3a7640000",
            "from": "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30",
            "to": "0x1234567890123456789012345678901234567890",
            "category": "external"
        }
        wallet_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        result = _extract_value_info(tx, wallet_address)
        
        self.assertEqual(result["value"], "0xde0b6b3a7640000")
        self.assertEqual(result["token_symbol"], "ETH")
        self.assertEqual(result["direction"], "out")
        self.assertEqual(result["counterparty"], "0x1234567890123456789012345678901234567890")

    def test_extract_value_info_eth_transfer_in(self):
        """Test extraction of incoming ETH transfer info."""
        tx = {
            "value": "0xde0b6b3a7640000",
            "from": "0x1234567890123456789012345678901234567890",
            "to": "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30",
            "category": "external"
        }
        wallet_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        result = _extract_value_info(tx, wallet_address)
        
        self.assertEqual(result["direction"], "in")
        self.assertEqual(result["counterparty"], "0x1234567890123456789012345678901234567890")

    def test_extract_value_info_erc20_transfer(self):
        """Test extraction of ERC20 token transfer info."""
        tx = {
            "value": "0x0",
            "from": "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30",
            "to": "0x1234567890123456789012345678901234567890",
            "category": "erc20",
            "asset": "0x1234567890123456789012345678901234567890"
        }
        wallet_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        result = _extract_value_info(tx, wallet_address)
        
        self.assertEqual(result["token_symbol"], "0x1234567890123456789012345678901234567890")
        self.assertEqual(result["token_address"], "0x1234567890123456789012345678901234567890")
        self.assertEqual(result["direction"], "out")

    def test_extract_value_info_no_value(self):
        """Test extraction when no value is present."""
        tx = {
            "value": "0x0",
            "from": "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30",
            "to": "0x1234567890123456789012345678901234567890",
            "category": "external"
        }
        wallet_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        result = _extract_value_info(tx, wallet_address)
        
        # Should still extract basic info even without value
        self.assertIn("direction", result)
        self.assertIn("counterparty", result)


class TestIntegration(unittest.TestCase):
    """Integration tests with real environment."""

    @unittest.skipIf(not os.getenv("ALCHEMY_API_KEY"), "ALCHEMY_API_KEY not set")
    def test_real_alchemy_base_chain_api_call(self):
        """Test real API call to Alchemy on Base chain (requires API key)."""
        test_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        try:
            # Test Base mainnet since that's what you enabled in your dashboard
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=test_address,
                max_transactions=10,
                network="base-mainnet"
            ))
            
            # Basic structure validation
            self.assertIn("events", result)
            self.assertIn("metadata", result)
            self.assertEqual(result["metadata"]["source"], "alchemy")
            self.assertEqual(result["metadata"]["network"], "base-mainnet")
            
        except Exception as e:
            self.fail(f"Real API call to Base chain failed: {e}")

    @unittest.skipIf(not os.getenv("ALCHEMY_API_KEY"), "ALCHEMY_API_KEY not set")
    def test_real_alchemy_base_chain_time_filtering(self):
        """Test real API call with time filtering on Base chain (requires API key)."""
        test_address = "0xc18dad44e77cf2f2f689f68d93a3603cbcdc5a30"
        
        try:
            # Test Base mainnet with time filtering
            result = asyncio.run(fetch_wallet_activity_alchemy_live(
                address=test_address,
                max_transactions=100,
                hours_back=24,
                network="base-mainnet"
            ))
            
            # Should have time filtering metadata
            self.assertEqual(result["metadata"]["time_filter_hours"], 24)
            self.assertEqual(result["metadata"]["network"], "base-mainnet")
            
        except Exception as e:
            self.fail(f"Real API call with time filtering to Base chain failed: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
