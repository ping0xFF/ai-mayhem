#!/usr/bin/env python3
"""
Test timestamp field consistency across mock provider and analyze node.
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


class TestTimestampFields(unittest.IsolatedAsyncioTestCase):
    """Test timestamp field consistency."""

    async def test_mock_events_processed_by_analyze(self):
        """Test that mock events are properly processed by analyze node."""
        
        # Get mock events from the mock provider
        mock_response = _fetch_wallet_activity_bitquery_mock(
            address="0x1234567890abcdef1234567890abcdef12345678",
            chain="base",
            since_ts=int((datetime.now() - timedelta(hours=12)).timestamp())
        )
        
        # Create state with mock events
        state = {
            "events": mock_response["events"],
            "goal": "test timestamp fields"
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
        
        # Verify the events we got from mock provider
        mock_events = mock_response["events"]
        self.assertGreater(len(mock_events), 0, "Mock provider should generate some events")
        
        # Check timestamp field in mock events
        first_event = mock_events[0]
        self.assertIn("timestamp", first_event, 
            "Mock events should use 'timestamp' field, not 'ts'")
        self.assertIsInstance(first_event["timestamp"], int,
            "Timestamp should be an integer (unix timestamp)")


if __name__ == '__main__':
    unittest.main()
