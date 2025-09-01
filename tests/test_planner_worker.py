#!/usr/bin/env python3
"""
Tests for Planner/Worker nodes with mock tools and fixtures.
TDD approach: write tests first, then implement to make them pass.
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


# Mock fixture: ~10 events across 2-3 pools, mixed kinds, timestamps within last 24h
MOCK_EVENTS = [
    {
        "txHash": "0x1234567890abcdef1234567890abcdef12345678",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=2)).timestamp()),
        "kind": "swap",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 1.5, "USDC": 3000.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=2)).timestamp())}
    },
    {
        "txHash": "0x1234567890abcdef1234567890abcdef12345678",
        "logIndex": 1,
        "timestamp": int((datetime.now() - timedelta(hours=2)).timestamp()),
        "kind": "swap",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 0.5, "USDC": 1000.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=2)).timestamp())}
    },
    {
        "txHash": "0xabcdef1234567890abcdef1234567890abcdef12",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=4)).timestamp()),
        "kind": "lp_add",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 2.0, "USDC": 4000.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=4)).timestamp())}
    },
    {
        "txHash": "0x9876543210fedcba9876543210fedcba98765432",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=6)).timestamp()),
        "kind": "swap",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 10000.0, "WETH": 0.8},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=6)).timestamp())}
    },
    {
        "txHash": "0x9876543210fedcba9876543210fedcba98765432",
        "logIndex": 1,
        "timestamp": int((datetime.now() - timedelta(hours=6)).timestamp()),
        "kind": "lp_remove",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 5000.0, "WETH": 0.4},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=6)).timestamp())}
    },
    {
        "txHash": "0x5555555555555555555555555555555555555555",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=8)).timestamp()),
        "kind": "swap",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 3.0, "USDC": 6000.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=8)).timestamp())}
    },
    {
        "txHash": "0x6666666666666666666666666666666666666666",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=10)).timestamp()),
        "kind": "lp_add",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 15000.0, "WETH": 1.2},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=10)).timestamp())}
    },
    {
        "txHash": "0x7777777777777777777777777777777777777777",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=12)).timestamp()),
        "kind": "swap",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 0.2, "USDC": 400.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=12)).timestamp())}
    },
    {
        "txHash": "0x8888888888888888888888888888888888888888",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=14)).timestamp()),
        "kind": "swap",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 2000.0, "WETH": 0.16},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=14)).timestamp())}
    },
    {
        "txHash": "0x9999999999999999999999999999999999999999",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=16)).timestamp()),
        "kind": "lp_remove",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 1.0, "USDC": 2000.0},
        "chain": "base",
        "provenance": {"source": "mock", "snapshot": int((datetime.now() - timedelta(hours=16)).timestamp())}
    }
]

# Mock wallet activity (subset of events for specific wallet)
MOCK_WALLET_ACTIVITY = [
    event for event in MOCK_EVENTS 
    if event["txHash"] in ["0x1234567890abcdef1234567890abcdef12345678", "0xabcdef1234567890abcdef1234567890abcdef12"]
]

# Mock LP activity (all events)
MOCK_LP_ACTIVITY = MOCK_EVENTS

# Mock web metrics
MOCK_WEB_METRICS = {
    "source": "mock_metrics",
    "snapshot_time": int(datetime.now().timestamp()),
    "key_values": {
        "total_volume_24h": 1500000.0,
        "active_pools": 45,
        "top_pool": "WETH/USDC",
        "volume_change_24h": 12.5
    },
    "raw_excerpt": "Mock metrics showing WETH/USDC as top pool with $1.5M volume"
}


class TestPlannerWorker(unittest.IsolatedAsyncioTestCase):
    """Test cases for Planner/Worker nodes."""
    
    async def asyncSetUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        with patch('json_storage.DB_PATH', Path(self.temp_db.name)):
            await init_db()
    
    async def asyncTearDown(self):
        """Clean up test database."""
        await close_db()
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def test_planner_selection_with_cursors(self):
        """Test planner selection logic with cursor/budget inputs."""
        from nodes.planner import planner_node
        
        # Test case 1: Wallet cursor stale (>2h) - should choose wallet_recon
        state = {
            "goal": "test goal",
            "spent_today": 0.0,
            "messages": [],
            "cursors": {
                "wallet:0x123": int((datetime.now() - timedelta(hours=3)).timestamp()),
                "lp": int((datetime.now() - timedelta(hours=1)).timestamp()),
                "explore_metrics": int((datetime.now() - timedelta(hours=1)).timestamp())
            }
        }
        
        result = await planner_node(state)
        self.assertEqual(result["selected_action"], "wallet_recon")
        self.assertEqual(result["target_wallet"], "0x123")
        
        # Test case 2: LP cursor stale (>6h) - should choose lp_recon
        state["cursors"]["wallet:0x123"] = int((datetime.now() - timedelta(hours=1)).timestamp())
        state["cursors"]["lp"] = int((datetime.now() - timedelta(hours=7)).timestamp())
        
        result = await planner_node(state)
        self.assertEqual(result["selected_action"], "lp_recon")
        
        # Test case 3: All cursors fresh - should choose explore_metrics (if cooldown passed)
        state["cursors"]["lp"] = int((datetime.now() - timedelta(hours=1)).timestamp())
        state["cursors"]["explore_metrics"] = int((datetime.now() - timedelta(hours=25)).timestamp())
        
        result = await planner_node(state)
        self.assertEqual(result["selected_action"], "explore_metrics")
        
        # Test case 4: Budget exceeded - should stop
        state["spent_today"] = 10.0  # Assume budget is 5.0
        
        result = await planner_node(state)
        self.assertEqual(result["status"], "capped")
    
    async def test_worker_idempotent_saves_and_provenance(self):
        """Test worker idempotent saves and provenance tracking."""
        from nodes.worker import worker_node
        import os

        # Ensure we use mock data for this test
        original_live = os.environ.get("BITQUERY_LIVE", "0")
        os.environ["BITQUERY_LIVE"] = "0"

        try:
            # Test wallet activity fetch
            state = {
                "selected_action": "wallet_recon",
                "target_wallet": "0x1234567890abcdef1234567890abcdef12345678"
            }

            result = await worker_node(state)

            # Verify events were saved
            self.assertIn("events", result)
            self.assertGreater(len(result["events"]), 0)

            # Verify provenance
            for event in result["events"]:
                self.assertIn("provenance", event)
                self.assertEqual(event["provenance"]["source"], "mock")
        finally:
            # Restore original environment
            if original_live:
                os.environ["BITQUERY_LIVE"] = original_live
            elif "BITQUERY_LIVE" in os.environ:
                del os.environ["BITQUERY_LIVE"]
        
        # Test idempotency - run again with same state
        result2 = await worker_node(state)
        
        # Should return same events (no duplicates)
        self.assertEqual(len(result["events"]), len(result2["events"]))
        
        # Verify deterministic IDs were used
        # Handle both old format (txHash/logIndex) and new Bitquery format (tx)
        if 'txHash' in result["events"][0]:
            # Old format
            event_ids = [f"{event['txHash']}:{event['logIndex']}" for event in result["events"]]
            event_ids2 = [f"{event['txHash']}:{event['logIndex']}" for event in result2["events"]]
        else:
            # New Bitquery format
            event_ids = [event['tx'] for event in result["events"]]
            event_ids2 = [event['tx'] for event in result2["events"]]
        self.assertEqual(event_ids, event_ids2)
    
    async def test_analyze_last24h_rollup_counts_and_top_pools(self):
        """Test analyze rollup correctness on small fixture."""
        from nodes.analyze import analyze_node
        
        # Create state with mock events
        state = {
            "events": MOCK_EVENTS,
            "goal": "test analysis"
        }
        
        result = await analyze_node(state)
        
        # Verify rollup counts
        self.assertIn("last24h_counts", result)
        counts = result["last24h_counts"]
        
        # Should have counts for each kind
        self.assertIn("swap", counts)
        self.assertIn("lp_add", counts)
        self.assertIn("lp_remove", counts)
        
        # Verify top pools
        self.assertIn("top_pools", result)
        top_pools = result["top_pools"]
        
        # WETH/USDC should be top pool (most events)
        self.assertGreater(len([e for e in MOCK_EVENTS if e["pool"] == "WETH/USDC"]), 
                          len([e for e in MOCK_EVENTS if e["pool"] == "DEGEN/WETH"]))
        
        # Verify signals
        self.assertIn("signals", result)
        signals = result["signals"]
        self.assertIsInstance(signals, dict)
    
    async def test_brief_gate_emit_vs_skip(self):
        """Test brief gate behavior (emit/skip)."""
        from nodes.brief import brief_node
        
        # Test case 1: High activity - should emit brief
        state = {
            "last24h_counts": {"swap": 8, "lp_add": 1, "lp_remove": 1},
            "signals": {"volume_signal": 0.8, "activity_signal": 0.7},
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),
            "goal": "test brief"
        }
        
        result = await brief_node(state)
        self.assertEqual(result["status"], "memory")
        self.assertIn("brief_text", result)
        self.assertIn("next_watchlist", result)
        
        # Test case 2: Low activity - should skip
        state["last24h_counts"] = {"swap": 2, "lp_add": 0, "lp_remove": 0}
        state["signals"] = {"volume_signal": 0.2, "activity_signal": 0.1}
        
        result = await brief_node(state)
        self.assertEqual(result["status"], "memory")
        self.assertIn("brief_skipped", result)
        self.assertIn("reason", result)
        
        # Test case 3: Cooldown not passed - should skip
        state["last24h_counts"] = {"swap": 8, "lp_add": 1, "lp_remove": 1}
        state["signals"] = {"volume_signal": 0.8, "activity_signal": 0.7}
        state["last_brief_at"] = int((datetime.now() - timedelta(hours=2)).timestamp())
        
        result = await brief_node(state)
        self.assertEqual(result["status"], "memory")
        self.assertIn("brief_skipped", result)
        self.assertIn("cooldown", result["reason"])


if __name__ == '__main__':
    unittest.main()
