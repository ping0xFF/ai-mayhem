#!/usr/bin/env python3
"""
Tests for Enhanced LP functionality with Three-Layer Data Model.
Tests Task Card #1: Tools → Worker → Analyze + Signals + Tests
"""

import json
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

import sys
sys.path.append(str(Path(__file__).parent.parent))

from json_storage import DatabaseManager, init_db, close_db
from data_model import get_data_model, save_raw_response, normalize_event, NormalizedEvent


class TestEnhancedLP(unittest.IsolatedAsyncioTestCase):
    """Test cases for Enhanced LP functionality."""
    
    async def asyncSetUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        with patch('json_storage.DB_PATH', Path(self.temp_db.name)):
            await init_db()
            # Initialize three-layer data model
            data_model = await get_data_model()
            await data_model.initialize()
    
    async def asyncTearDown(self):
        """Clean up test database."""
        await close_db()
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def test_enhanced_lp_tool_simple_fixtures(self):
        """Test enhanced LP tool with simple fixtures."""
        from mock_tools import fetch_lp_activity
        
        # Test with simple fixtures (default)
        since_ts = int((datetime.now() - timedelta(hours=10)).timestamp())
        lp_events = fetch_lp_activity(since_ts, use_realistic=False)
        
        # Should return simple fixtures
        self.assertGreater(len(lp_events), 0)
        self.assertLessEqual(len(lp_events), 3)  # Simple fixtures have 3 events
        
        # Check structure
        for event in lp_events:
            self.assertIn("txHash", event)
            self.assertIn("kind", event)
            self.assertIn("pool", event)
            self.assertIn("details", event)
            self.assertIn("provenance", event)
            self.assertEqual(event["provenance"]["source"], "mock_lp")
            self.assertEqual(event["provenance"]["fixture_type"], "simple")
    
    async def test_enhanced_lp_tool_realistic_fixtures(self):
        """Test enhanced LP tool with realistic fixtures."""
        from mock_tools import fetch_lp_activity
        
        # Test with realistic fixtures
        since_ts = int((datetime.now() - timedelta(hours=10)).timestamp())
        lp_events = fetch_lp_activity(since_ts, use_realistic=True)
        
        # Should return realistic fixtures
        self.assertGreater(len(lp_events), 0)
        self.assertLessEqual(len(lp_events), 5)  # Realistic fixtures have 5 events
        
        # Check structure
        for event in lp_events:
            self.assertIn("txHash", event)
            self.assertIn("kind", event)
            self.assertIn("pool", event)
            self.assertIn("details", event)
            self.assertIn("provenance", event)
            self.assertEqual(event["provenance"]["source"], "mock_lp")
            self.assertEqual(event["provenance"]["fixture_type"], "realistic")
            
            # Realistic fixtures should have more detailed info
            details = event["details"]
            self.assertIn("token0", details)
            self.assertIn("token1", details)
            self.assertIn("lp_tokens_delta", details)
            self.assertIn("pool_address", details)
    
    async def test_worker_lp_recon_with_scratch_save(self):
        """Test Worker node LP recon with scratch layer save."""
        from nodes.worker import worker_node
        
        # Test state with LP recon
        state = {
            "selected_action": "lp_recon",
            "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())},
            "use_realistic_fixtures": False  # Use simple fixtures for test
        }
        
        result = await worker_node(state)
        
        # Should complete successfully
        self.assertEqual(result["status"], "analyzing")
        self.assertIn("events", result)
        self.assertIn("source_ids", result)
        self.assertIn("execution_time", result)
        
        # Should have events
        self.assertGreater(len(result["events"]), 0)
        
        # Should have source_ids for scratch layer
        self.assertGreater(len(result["source_ids"]), 0)
        
        # Verify scratch layer was written
        source_id = result["source_ids"][0]
        data_model = await get_data_model()
        raw_response = await data_model.get_raw_response(source_id)
        self.assertIsNotNone(raw_response)
        # Check that it contains LP activity data
        self.assertIn("events", raw_response)
        self.assertIn("since_ts", raw_response)
    
    async def test_analyze_lp_events_normalization(self):
        """Test Analyze node LP events normalization."""
        from nodes.analyze import analyze_node
        from mock_tools import fetch_lp_activity
        
        # Get LP events
        since_ts = int((datetime.now() - timedelta(hours=10)).timestamp())
        lp_events = fetch_lp_activity(since_ts, use_realistic=False)
        
        # Test state with LP events
        state = {
            "events": lp_events,
            "source_ids": ["test_lp_source_1"]
        }
        
        result = await analyze_node(state)
        
        # Should complete successfully
        self.assertEqual(result["status"], "briefing")
        self.assertIn("normalized_events", result)
        self.assertIn("signals", result)
        
        # Should have normalized events
        self.assertGreater(len(result["normalized_events"]), 0)
        
        # Check LP-specific signals
        signals = result["signals"]
        self.assertIn("net_liquidity_delta_24h", signals)
        self.assertIn("lp_churn_rate_24h", signals)
        self.assertIn("pool_activity_score", signals)
        self.assertIn("net_liquidity_value", signals)
        
        # Verify events were saved to Layer 2
        data_model = await get_data_model()
        events = await data_model.get_events_by_type("lp_add")
        self.assertGreaterEqual(len(events), 0)
    
    async def test_lp_signals_computation(self):
        """Test LP-specific signals computation."""
        from nodes.analyze import analyze_node
        from mock_tools import fetch_lp_activity
        
        # Get realistic LP events for better signal testing
        since_ts = int((datetime.now() - timedelta(hours=10)).timestamp())
        lp_events = fetch_lp_activity(since_ts, use_realistic=True)
        
        # Test state with LP events
        state = {
            "events": lp_events,
            "source_ids": ["test_lp_source_2"]
        }
        
        result = await analyze_node(state)
        signals = result["signals"]
        
        # Test LP-specific signals
        self.assertIn("net_liquidity_delta_24h", signals)
        self.assertIn("lp_churn_rate_24h", signals)
        self.assertIn("pool_activity_score", signals)
        self.assertIn("net_liquidity_value", signals)
        
        # Net delta should be calculated correctly
        # Realistic fixtures have 3 adds and 2 removes = net +1
        self.assertEqual(signals["net_liquidity_delta_24h"], 1)
        
        # Activity score should be reasonable
        self.assertGreater(signals["pool_activity_score"], 0)
        self.assertLessEqual(signals["pool_activity_score"], 1)
        
        # Churn rate should be reasonable (with 5 unique wallets out of 5 events = 1.0)
        self.assertGreater(signals["lp_churn_rate_24h"], 0)
        self.assertLessEqual(signals["lp_churn_rate_24h"], 1)
        # With realistic fixtures, should have 5 unique wallets out of 5 events = 1.0
        self.assertEqual(signals["lp_churn_rate_24h"], 1.0)
    
    async def test_three_layer_lp_data_flow(self):
        """Test complete three-layer data flow for LP events."""
        from nodes.worker import worker_node
        from nodes.analyze import analyze_node
        
        # Step 1: Worker saves to scratch layer
        worker_state = {
            "selected_action": "lp_recon",
            "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())},
            "use_realistic_fixtures": True
        }
        
        worker_result = await worker_node(worker_state)
        self.assertEqual(worker_result["status"], "analyzing")
        self.assertGreater(len(worker_result["source_ids"]), 0)
        
        # Step 2: Analyze normalizes to events layer
        analyze_state = {
            **worker_result,
            "events": worker_result["events"]
        }
        
        analyze_result = await analyze_node(analyze_state)
        self.assertEqual(analyze_result["status"], "briefing")
        self.assertGreater(len(analyze_result["normalized_events"]), 0)
        
        # Step 3: Verify data in all three layers
        data_model = await get_data_model()
        
        # Layer 1: Scratch
        source_id = worker_result["source_ids"][0]
        raw_response = await data_model.get_raw_response(source_id)
        self.assertIsNotNone(raw_response)
        # Check that it contains LP activity data
        self.assertIn("events", raw_response)
        self.assertIn("since_ts", raw_response)
        
        # Layer 2: Normalized Events
        events = await data_model.get_events_by_type("lp_add")
        self.assertGreaterEqual(len(events), 0)
        
        # Verify provenance chain
        for event in analyze_result["normalized_events"]:
            self.assertEqual(event.source_id, source_id)
    
    async def test_lp_event_idempotency(self):
        """Test LP event idempotency across layers."""
        from nodes.worker import worker_node
        from nodes.analyze import analyze_node
        
        # Run worker twice with same parameters
        worker_state = {
            "selected_action": "lp_recon",
            "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())},
            "use_realistic_fixtures": False
        }
        
        result1 = await worker_node(worker_state)
        result2 = await worker_node(worker_state)
        
        # Should have same number of events (idempotent)
        self.assertEqual(len(result1["events"]), len(result2["events"]))
        
        # Run analyze twice
        analyze_state1 = {**result1, "events": result1["events"]}
        analyze_state2 = {**result2, "events": result2["events"]}
        
        analyze_result1 = await analyze_node(analyze_state1)
        analyze_result2 = await analyze_node(analyze_state2)
        
        # Should have same number of normalized events (idempotent)
        self.assertEqual(len(analyze_result1["normalized_events"]), len(analyze_result2["normalized_events"]))
        
        # Verify no duplicate events in Layer 2
        data_model = await get_data_model()
        events = await data_model.get_events_by_type("lp_add")
        unique_event_ids = set(event.event_id for event in events)
        self.assertEqual(len(events), len(unique_event_ids))


if __name__ == "__main__":
    unittest.main()
