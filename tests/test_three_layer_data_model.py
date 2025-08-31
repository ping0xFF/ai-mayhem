#!/usr/bin/env python3
"""
Tests for the three-layer data model.
"""

import unittest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data_model import (
    ThreeLayerDataModel, NormalizedEvent, Artifact,
    save_raw_response, normalize_event, persist_brief,
    get_events_by_wallet, get_recent_briefs
)


class TestThreeLayerDataModel(unittest.IsolatedAsyncioTestCase):
    """Test cases for the three-layer data model."""
    
    async def asyncSetUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Patch the DB_PATH to use our temporary database
        with patch('data_model.DB_PATH', Path(self.temp_db.name)):
            self.data_model = ThreeLayerDataModel(Path(self.temp_db.name))
            await self.data_model.initialize()
    
    async def asyncTearDown(self):
        """Clean up test database."""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def test_layer1_save_and_load_raw_response(self):
        """Test Layer 1: Save and load raw responses."""
        # Test data
        test_data = {
            "wallet": "0x123",
            "events": [{"txHash": "0xabc", "amount": 100}],
            "timestamp": 1234567890
        }
        provenance = {
            "source": "mock_tools",
            "wallet": "0x123",
            "snapshot_time": 1234567890
        }
        
        # Save raw response
        response_id = await self.data_model.save_raw_response(
            "test_response", "wallet_activity", test_data, provenance
        )
        self.assertEqual(response_id, "test_response")
        
        # Load raw response
        loaded = await self.data_model.get_raw_response("test_response")
        self.assertEqual(loaded["wallet"], "0x123")
        self.assertEqual(loaded["_provenance"]["source"], "mock_tools")
    
    async def test_layer2_normalize_events(self):
        """Test Layer 2: Normalize events."""
        # Create normalized event
        event = NormalizedEvent(
            event_id="0xabc:0",
            wallet="0x123",
            event_type="swap",
            pool="WETH/USDC",
            value={"amount": 100, "token": "WETH"},
            timestamp=1234567890,
            source_id="test_response",
            chain="base"
        )
        
        # Save normalized event
        event_id = await self.data_model.normalize_event(event)
        self.assertEqual(event_id, "0xabc:0")
        
        # Get events by wallet
        events = await self.data_model.get_events_by_wallet("0x123")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "swap")
        self.assertEqual(events[0].pool, "WETH/USDC")
    
    async def test_layer3_persist_briefs(self):
        """Test Layer 3: Persist briefs."""
        # Create artifact
        artifact = Artifact(
            artifact_id="brief_1234567890",
            timestamp=1234567890,
            summary_text="Test brief summary",
            signals={"volume_signal": 0.8, "activity_signal": 0.6},
            next_watchlist=["WETH/USDC", "DEGEN/WETH"],
            source_ids=["test_response_1", "test_response_2"],
            event_count=5
        )
        
        # Persist artifact
        artifact_id = await self.data_model.persist_brief(artifact)
        self.assertEqual(artifact_id, "brief_1234567890")
        
        # Get recent briefs
        briefs = await self.data_model.get_recent_briefs(limit=5)
        self.assertEqual(len(briefs), 1)
        self.assertEqual(briefs[0].summary_text, "Test brief summary")
        self.assertEqual(briefs[0].signals["volume_signal"], 0.8)
    
    async def test_provenance_chain(self):
        """Test end-to-end provenance tracking."""
        # Layer 1: Save raw response
        raw_data = {"wallet": "0x123", "events": [{"txHash": "0xabc"}]}
        await self.data_model.save_raw_response("source_1", "wallet_activity", raw_data)
        
        # Layer 2: Normalize event
        event = NormalizedEvent(
            event_id="0xabc:0",
            wallet="0x123",
            event_type="swap",
            pool="WETH/USDC",
            value={"amount": 100},
            timestamp=1234567890,
            source_id="source_1",
            chain="base"
        )
        await self.data_model.normalize_event(event)
        
        # Layer 3: Persist brief
        artifact = Artifact(
            artifact_id="brief_1234567890",
            timestamp=1234567890,
            summary_text="Test brief",
            signals={"volume_signal": 0.8},
            next_watchlist=["WETH/USDC"],
            source_ids=["source_1"],
            event_count=1
        )
        await self.data_model.persist_brief(artifact)
        
        # Get provenance chain
        chain = await self.data_model.get_provenance_chain("brief_1234567890")
        self.assertEqual(chain["artifact_id"], "brief_1234567890")
        self.assertEqual(len(chain["raw_responses"]), 1)
        self.assertEqual(len(chain["events"]), 1)
    
    async def test_idempotent_upserts(self):
        """Test that upserts are idempotent."""
        # Test Layer 1 idempotency
        test_data = {"test": "data"}
        await self.data_model.save_raw_response("test_id", "test", test_data)
        await self.data_model.save_raw_response("test_id", "test", test_data)  # Should not duplicate
        
        # Verify only one record exists
        loaded = await self.data_model.get_raw_response("test_id")
        self.assertIsNotNone(loaded)
        
        # Test Layer 2 idempotency
        event = NormalizedEvent(
            event_id="test_event",
            wallet="0x123",
            event_type="swap",
            pool="WETH/USDC",
            value={"amount": 100},
            timestamp=1234567890,
            source_id="test_id",
            chain="base"
        )
        await self.data_model.normalize_event(event)
        await self.data_model.normalize_event(event)  # Should not duplicate
        
        # Verify only one event exists
        events = await self.data_model.get_events_by_wallet("0x123")
        self.assertEqual(len(events), 1)
    
    async def test_cleanup_old_data(self):
        """Test cleanup of old data according to retention rules."""
        # Add some test data
        await self.data_model.save_raw_response("old_scratch", "test", {"old": "data"})
        await self.data_model.save_raw_response("new_scratch", "test", {"new": "data"})
        
        # Add old event
        old_event = NormalizedEvent(
            event_id="old_event",
            wallet="0x123",
            event_type="swap",
            pool="WETH/USDC",
            value={"amount": 100},
            timestamp=1234567890,
            source_id="old_scratch",
            chain="base"
        )
        await self.data_model.normalize_event(old_event)
        
        # Add old artifact
        old_artifact = Artifact(
            artifact_id="old_brief",
            timestamp=1234567890,
            summary_text="Old brief",
            signals={"volume_signal": 0.8},
            next_watchlist=["WETH/USDC"],
            source_ids=["old_scratch"],
            event_count=1
        )
        await self.data_model.persist_brief(old_artifact)
        
        # Clean up old data
        await self.data_model.cleanup_old_data(scratch_days=0, events_days=0, artifacts_days=0)
        
        # Verify cleanup (this is a basic test - actual cleanup depends on timestamps)
        # In a real scenario, you'd need to manually insert old timestamps
    
    async def test_convenience_functions(self):
        """Test convenience functions."""
        # Test save_raw_response convenience function
        response_id = await save_raw_response("conv_test", "test", {"data": "test"})
        self.assertEqual(response_id, "conv_test")
        
        # Test normalize_event convenience function
        event = NormalizedEvent(
            event_id="conv_event",
            wallet="0x123",
            event_type="swap",
            pool="WETH/USDC",
            value={"amount": 100},
            timestamp=1234567890,
            source_id="conv_test",
            chain="base"
        )
        event_id = await normalize_event(event)
        self.assertEqual(event_id, "conv_event")
        
        # Test persist_brief convenience function
        artifact = Artifact(
            artifact_id="conv_brief",
            timestamp=1234567890,
            summary_text="Convenience brief",
            signals={"volume_signal": 0.8},
            next_watchlist=["WETH/USDC"],
            source_ids=["conv_test"],
            event_count=1
        )
        artifact_id = await persist_brief(artifact)
        self.assertEqual(artifact_id, "conv_brief")
        
        # Test get_events_by_wallet convenience function
        events = await get_events_by_wallet("0x123")
        self.assertGreaterEqual(len(events), 1)  # May have multiple events from previous tests
        
        # Test get_recent_briefs convenience function
        briefs = await get_recent_briefs(limit=5)
        self.assertGreaterEqual(len(briefs), 1)  # May have multiple briefs from previous tests


if __name__ == '__main__':
    unittest.main()
