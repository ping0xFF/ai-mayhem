import unittest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from real_apis.alchemy_provider import (
    fetch_wallet_activity_alchemy_regular,
    fetch_wallet_activity_alchemy_beta,
    fetch_wallet_activity_alchemy_live,
    validate_alchemy_response
)


class TestAlchemyProvider(unittest.TestCase):
    """Test suite for Alchemy provider with TDD approach"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.sample_address = "0x1234567890123456789012345678901234567890"
        self.sample_chain = "base-mainnet"
        self.sample_hours_back = 48
        self.sample_max_transactions = 1000
        
        # Mock API responses
        self.mock_regular_api_response = {
            "transfers": [
                {
                    "hash": "0xabc123",
                    "blockNum": "0x12345",
                    "value": "1000000000000000000",
                    "from": "0x1234567890123456789012345678901234567890",
                    "to": "0x9876543210987654321098765432109876543210",
                    "category": "external",
                    "asset": None
                },
                {
                    "hash": "0xdef456",
                    "blockNum": "0x12346",
                    "value": "0",
                    "from": "0x9876543210987654321098765432109876543210",
                    "to": "0x1234567890123456789012345678901234567890",
                    "category": "erc20",
                    "asset": "0xTokenAddress"
                }
            ],
            "totalCount": 2
        }
        
        self.mock_beta_api_response = {
            "transactions": [
                {
                    "hash": "0xabc123",
                    "blockNumber": 74565,
                    "value": "1000000000000000000",
                    "fromAddress": "0x1234567890123456789012345678901234567890",
                    "toAddress": "0x9876543210987654321098765432109876543210",
                    "timeStamp": "2024-01-15T10:30:00Z"
                },
                {
                    "hash": "0xdef456",
                    "blockNumber": 74566,
                    "value": "0",
                    "fromAddress": "0x9876543210987654321098765432109876543210",
                    "toAddress": "0x1234567890123456789012345678901234567890",
                    "timeStamp": "2024-01-15T11:00:00Z"
                }
            ],
            "totalCount": 2
        }
        
        self.mock_block_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "timestamp": "0x65a5b8c0"  # Unix timestamp in hex
            }
        }

    @patch('real_apis.alchemy_provider._fetch_base_mainnet_asset_transfers')
    @patch('real_apis.alchemy_provider._get_block_timestamp')
    @patch('real_apis.alchemy_provider._get_current_block_number')
    def test_regular_api_time_filtering(self, mock_get_current_block, mock_get_block_timestamp, mock_fetch_transfers):
        """Test that regular API respects hours_back parameter"""
        # Setup mocks
        mock_get_current_block.return_value = 10000000
        mock_get_block_timestamp.return_value = int(datetime.now().timestamp())
        mock_fetch_transfers.return_value = self.mock_regular_api_response
        
        response = asyncio.run(fetch_wallet_activity_alchemy_regular(
            self.sample_address, self.sample_chain, self.sample_max_transactions, self.sample_hours_back
        ))
        
        # Should return transactions from mock data
        events = response.get("events", [])
        self.assertEqual(len(events), 2, f"Expected 2 events from mock data, got {len(events)}")
        
        # All events should have valid timestamps
        for event in events:
            self.assertIsNotNone(event.get("ts"), "Event missing timestamp")
            self.assertIsNotNone(event.get("tx"), "Event missing transaction hash")
            self.assertIsNotNone(event.get("chain"), "Event missing chain")
            self.assertIsNotNone(event.get("type"), "Event missing type")
            self.assertIsNotNone(event.get("wallet"), "Event missing wallet")
        
        # Verify mocks were called
        mock_fetch_transfers.assert_called_once()
        self.assertEqual(mock_get_block_timestamp.call_count, 2)  # Called for each transfer

    @patch('real_apis.alchemy_provider._fetch_beta_transactions')
    @patch('real_apis.alchemy_provider._fetch_base_mainnet_asset_transfers')
    @patch('real_apis.alchemy_provider._get_block_timestamp')
    @patch('real_apis.alchemy_provider._get_current_block_number')
    def test_beta_api_vs_regular_api(self, mock_get_current_block, mock_get_block_timestamp, mock_fetch_transfers, mock_fetch_beta):
        """Test that both APIs work and return similar data"""
        # Setup mocks
        mock_get_current_block.return_value = 10000000
        mock_get_block_timestamp.return_value = int(datetime.now().timestamp())
        mock_fetch_transfers.return_value = self.mock_regular_api_response
        mock_fetch_beta.return_value = self.mock_beta_api_response
        
        regular_response = asyncio.run(fetch_wallet_activity_alchemy_regular(
            self.sample_address, self.sample_chain, self.sample_max_transactions, self.sample_hours_back
        ))
        
        beta_response = asyncio.run(fetch_wallet_activity_alchemy_beta(
            self.sample_address, self.sample_max_transactions, self.sample_hours_back, self.sample_chain
        ))
        
        # Both should return valid responses
        self.assertIn("events", regular_response)
        self.assertIn("events", beta_response)
        
        # Both should have reasonable transaction counts
        self.assertEqual(len(regular_response["events"]), 2)
        self.assertEqual(len(beta_response["events"]), 2)
        
        # Both should have proper metadata
        self.assertEqual(regular_response["metadata"]["source"], "alchemy_regular")
        self.assertEqual(beta_response["metadata"]["source"], "alchemy_beta")

    @patch('real_apis.alchemy_provider._fetch_base_mainnet_asset_transfers')
    @patch('real_apis.alchemy_provider._get_block_timestamp')
    @patch('real_apis.alchemy_provider._get_current_block_number')
    def test_timestamp_accuracy(self, mock_get_current_block, mock_get_block_timestamp, mock_fetch_transfers):
        """Test that timestamps are reasonable (not all the same)"""
        # Setup mocks with different timestamps
        mock_get_current_block.return_value = 10000000
        mock_get_block_timestamp.side_effect = [
            int(datetime.now().timestamp()) - 3600,  # 1 hour ago
            int(datetime.now().timestamp()) - 7200   # 2 hours ago
        ]
        mock_fetch_transfers.return_value = self.mock_regular_api_response
        
        response = asyncio.run(fetch_wallet_activity_alchemy_regular(
            self.sample_address, self.sample_chain, self.sample_max_transactions, self.sample_hours_back
        ))
        
        events = response.get("events", [])
        self.assertEqual(len(events), 2, "Expected 2 events from mock data")
        
        timestamps = [e.get("ts") for e in events]
        # Should not have identical timestamps for all events
        self.assertGreater(len(set(timestamps)), 1, "All timestamps are identical")
        
        # Timestamps should be reasonable (not in the future, not too old)
        current_time = datetime.now().timestamp()
        for ts in timestamps:
            self.assertLessEqual(ts, current_time, "Timestamp in the future")
            self.assertGreaterEqual(ts, current_time - (self.sample_hours_back * 3600), "Timestamp too old")

    @patch('real_apis.alchemy_provider._fetch_base_mainnet_asset_transfers')
    @patch('real_apis.alchemy_provider._get_block_timestamp')
    @patch('real_apis.alchemy_provider._get_current_block_number')
    def test_transaction_limit(self, mock_get_current_block, mock_get_block_timestamp, mock_fetch_transfers):
        """Test that we don't return 1000+ transactions unnecessarily"""
        # Setup mocks
        mock_get_current_block.return_value = 10000000
        mock_get_block_timestamp.return_value = int(datetime.now().timestamp())
        mock_fetch_transfers.return_value = self.mock_regular_api_response
        
        response = asyncio.run(fetch_wallet_activity_alchemy_regular(
            self.sample_address, self.sample_chain, self.sample_max_transactions, self.sample_hours_back
        ))
        
        events = response.get("events", [])
        # Should respect max_transactions and time filtering
        self.assertLessEqual(len(events), self.sample_max_transactions, f"Too many transactions: {len(events)}")
        self.assertLessEqual(len(events), 100, f"Should not return 1000+ transactions: {len(events)}")
        self.assertEqual(len(events), 2, "Expected 2 events from mock data")

    @patch('real_apis.alchemy_provider._fetch_base_mainnet_asset_transfers')
    @patch('real_apis.alchemy_provider._get_block_timestamp')
    @patch('real_apis.alchemy_provider._get_current_block_number')
    def test_api_router_selection(self, mock_get_current_block, mock_get_block_timestamp, mock_fetch_transfers):
        """Test that the router correctly selects between Beta and Regular API"""
        # Setup mocks with different timestamps
        mock_get_current_block.return_value = 10000000
        mock_get_block_timestamp.side_effect = [
            int(datetime.now().timestamp()) - 3600,  # 1 hour ago
            int(datetime.now().timestamp()) - 7200   # 2 hours ago
        ]
        mock_fetch_transfers.return_value = self.mock_regular_api_response
        
        response = asyncio.run(fetch_wallet_activity_alchemy_live(
            self.sample_address, self.sample_chain, self.sample_max_transactions, self.sample_hours_back
        ))
        
        # Should return a valid response
        self.assertIn("events", response)
        self.assertLessEqual(len(response["events"]), 100)
        self.assertEqual(len(response["events"]), 2, "Expected 2 events from mock data")
        self.assertEqual(response["metadata"]["source"], "alchemy_regular")

    def test_validation_function(self):
        """Test the validation function per README mandates"""
        # Test valid response
        valid_response = {
            "events": [
                {"ts": datetime.now().timestamp() - 3600, "chain": "base-mainnet", "type": "transfer", "wallet": "0x123", "tx": "0xabc"},
                {"ts": datetime.now().timestamp() - 7200, "chain": "base-mainnet", "type": "transfer", "wallet": "0x123", "tx": "0xdef"}
            ]
        }
        
        # Should not raise any exceptions
        validate_alchemy_response(valid_response, hours_back=48)
        
        # Test invalid response - too many transactions
        invalid_response = {
            "events": [{"ts": datetime.now().timestamp(), "chain": "base-mainnet", "type": "transfer", "wallet": "0x123", "tx": f"0x{i:03x}"} for i in range(150)]
        }
        
        with self.assertRaises(ValueError) as context:
            validate_alchemy_response(invalid_response)
        self.assertIn("Too many transactions", str(context.exception))
        
        # Test invalid response - identical timestamps
        invalid_timestamps = {
            "events": [
                {"ts": 1234567890, "chain": "base-mainnet", "type": "transfer", "wallet": "0x123", "tx": "0xabc"},
                {"ts": 1234567890, "chain": "base-mainnet", "type": "transfer", "wallet": "0x123", "tx": "0xdef"}
            ]
        }
        
        with self.assertRaises(ValueError) as context:
            validate_alchemy_response(invalid_timestamps)
        self.assertIn("All timestamps are identical", str(context.exception))

    def test_required_fields_validation(self):
        """Test that all required fields are present in events"""
        # Test missing required field
        incomplete_response = {
            "events": [
                {"ts": datetime.now().timestamp(), "chain": "base-mainnet", "type": "transfer", "wallet": "0x123"}
                # Missing "tx" field
            ]
        }
        
        with self.assertRaises(ValueError) as context:
            validate_alchemy_response(incomplete_response)
        self.assertIn("missing required field: tx", str(context.exception))


if __name__ == '__main__':
    unittest.main()
