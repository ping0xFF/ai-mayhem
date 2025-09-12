#!/usr/bin/env python3
"""
Test field name consistency across providers and analyze node.
"""

import unittest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.append(str(Path(__file__).parent.parent))

from mock_tools import _fetch_wallet_activity_bitquery_mock
from nodes.analyze import analyze_node
from real_apis.alchemy_provider import _classify_transaction as classify_alchemy
from real_apis.covalent import _classify_transaction as classify_covalent


class TestFieldConsistency(unittest.IsolatedAsyncioTestCase):
    """Test field name consistency across components."""

    async def test_schema_validation_system(self):
        """Test the new schema validation system works correctly."""
        from real_apis.provider_router import ProviderRouter

        router = ProviderRouter()

        # Test that schema validator is initialized
        self.assertIsNotNone(router.schema_validator)
        self.assertIsNotNone(router.schema_validator.field_mappings)

        # Test field mappings are comprehensive
        expected_fields = ['event_id', 'event_type', 'wallet', 'timestamp']
        for field in expected_fields:
            self.assertIn(field, router.schema_validator.field_mappings)

    async def test_provider_field_mapping_robustness(self):
        """Test that field mapping works across different provider formats."""
        from real_apis.provider_router import ProviderSchemaValidator

        validator = ProviderSchemaValidator({
            "event_id": ["tx", "txHash", "hash"],
            "event_type": ["type", "kind", "transaction_type"],
            "wallet": ["wallet", "address"],
            "timestamp": ["timestamp", "ts", "time"]
        })

        # Test Covalent-style event (uses 'type', 'tx')
        covalent_event = {
            "type": "transaction",
            "tx": "0x123...",
            "wallet": "0xabc...",
            "timestamp": 1234567890
        }

        standardized = validator.validate_and_standardize_event(covalent_event, "covalent")
        self.assertEqual(standardized["event_id"], "0x123...")
        self.assertEqual(standardized["event_type"], "transaction")

        # Test mock-style event (uses 'kind', 'txHash')
        mock_event = {
            "kind": "transfer",
            "txHash": "0x456...",
            "address": "0xdef...",
            "ts": 1234567891
        }

        standardized = validator.validate_and_standardize_event(mock_event, "mock")
        self.assertEqual(standardized["event_id"], "0x456...")
        self.assertEqual(standardized["event_type"], "transfer")
        self.assertEqual(standardized["timestamp"], 1234567891)

    async def test_timestamp_field_consistency(self):
        """Test that timestamp fields are consistent between providers and analyze."""
        
        # Get mock events from the mock provider
        mock_response = _fetch_wallet_activity_bitquery_mock(
            address="0x1234567890abcdef1234567890abcdef12345678",
            chain="base",
            since_ts=int((datetime.now() - timedelta(hours=12)).timestamp())
        )
        
        # Create state with mock events
        state = {
            "events": mock_response["events"],
            "goal": "test field consistency"
        }
        
        # Process events through analyze node
        result = await analyze_node(state)
        
        # Verify events were processed (not filtered out)
        self.assertIn("last24h_counts", result)
        counts = result["last24h_counts"]
        
        # We should have some events counted
        total_events = sum(counts.values())
        self.assertGreater(total_events, 0, 
            "No events were processed. Events may have been filtered out due to timestamp field mismatch.")
        
        # Check timestamp field in mock events
        first_event = mock_response["events"][0]
        self.assertIn("timestamp", first_event, 
            "Mock events should use 'timestamp' field, not 'ts'")
        self.assertIsInstance(first_event["timestamp"], int,
            "Timestamp should be an integer (unix timestamp)")

    async def test_event_type_field_consistency(self):
        """Test that event type fields are consistent between providers and analyze."""
        
        # Get mock events from the mock provider
        mock_response = _fetch_wallet_activity_bitquery_mock(
            address="0x1234567890abcdef1234567890abcdef12345678",
            chain="base",
            since_ts=int((datetime.now() - timedelta(hours=12)).timestamp())
        )
        
        # Create state with mock events
        state = {
            "events": mock_response["events"],
            "goal": "test field consistency"
        }
        
        # Process events through analyze node
        result = await analyze_node(state)
        
        # Verify events were processed and types were counted
        self.assertIn("last24h_counts", result)
        counts = result["last24h_counts"]
        
        # We should have some events counted by type
        total_events = sum(counts.values())
        self.assertGreater(total_events, 0, 
            "No events were processed. Events may have been filtered out due to type field mismatch.")
        
        # Check type field in mock events
        first_event = mock_response["events"][0]
        self.assertIn("type", first_event, 
            "Mock events should use 'type' field, not 'kind'")
        
        # Verify the type is one of our expected values
        expected_types = {"swap", "lp_add", "lp_remove", "transfer", "token_transfer", "contract_interaction"}
        self.assertIn(first_event["type"], expected_types,
            f"Event type '{first_event['type']}' not in expected types: {expected_types}")

    async def test_transaction_hash_field_consistency(self):
        """Test that transaction hash fields are consistent between providers and analyze."""
        
        # Get mock events from the mock provider
        mock_response = _fetch_wallet_activity_bitquery_mock(
            address="0x1234567890abcdef1234567890abcdef12345678",
            chain="base",
            since_ts=int((datetime.now() - timedelta(hours=12)).timestamp())
        )
        
        # Create state with mock events
        state = {
            "events": mock_response["events"],
            "goal": "test field consistency"
        }
        
        # Process events through analyze node
        result = await analyze_node(state)
        
        # Check transaction hash field in mock events
        first_event = mock_response["events"][0]
        self.assertIn("tx", first_event, 
            "Mock events should use 'tx' field for transaction hash")
        
        # Verify the hash format
        tx_hash = first_event["tx"]
        self.assertTrue(tx_hash.startswith("0x"), 
            "Transaction hash should start with '0x'")
        self.assertEqual(len(tx_hash), 66,  # 0x + 64 hex chars
            "Transaction hash should be 32 bytes (66 chars including '0x')")


if __name__ == '__main__':
    unittest.main()
