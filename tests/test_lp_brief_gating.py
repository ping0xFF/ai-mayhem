#!/usr/bin/env python3
"""
Tests for LP Brief Gating functionality.
Tests Task Card #2: Brief/Gating + Tests
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


class TestLPBriefGating(unittest.IsolatedAsyncioTestCase):
    """Test cases for LP Brief Gating functionality."""
    
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
    
    async def test_brief_gate_emit_with_lp_activity(self):
        """Test brief emission when LP activity score is high."""
        from nodes.brief import brief_node
        from mock_tools import fetch_lp_activity
        
        # Get LP events with high activity
        since_ts = int((datetime.now() - timedelta(hours=10)).timestamp())
        lp_events = fetch_lp_activity(since_ts, use_realistic=True)  # 5 events = high activity
        
        # Test state with high LP activity
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),  # Cooldown passed
            "last24h_counts": {"lp_add": 3, "lp_remove": 2},
            "signals": {
                "volume_signal": 0.3,  # Low
                "activity_signal": 0.4,  # Low
                "pool_activity_score": 1.0,  # High - should trigger brief
                "net_liquidity_delta_24h": 1,
                "lp_churn_rate_24h": 1.0
            },
            "top_pools": ["WETH/USDC", "DEGEN/WETH"],
            "source_ids": ["test_lp_source_1"]
        }
        
        result = await brief_node(state)
        
        # Should emit brief due to high LP activity score
        self.assertNotIn("brief_skipped", result)
        self.assertIn("brief_text", result)
        self.assertIn("next_watchlist", result)
        self.assertEqual(result["status"], "memory")
        
        # Check brief content
        brief_text = result["brief_text"]
        self.assertIn("LP activity", brief_text)
        self.assertIn("net delta 1", brief_text)
        self.assertIn("activity score 1.00", brief_text)
        
        # Check next watchlist includes LP pools
        next_watchlist = result["next_watchlist"]
        self.assertGreater(len(next_watchlist), 0)
        lp_pools = [pool for pool in next_watchlist if "(LP)" in pool]
        self.assertGreater(len(lp_pools), 0)
    
    async def test_brief_gate_skip_with_low_lp_activity(self):
        """Test brief skip when LP activity score is low."""
        from nodes.brief import brief_node
        
        # Test state with low LP activity
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),  # Cooldown passed
            "last24h_counts": {"lp_add": 1, "lp_remove": 1},
            "signals": {
                "volume_signal": 0.2,  # Low
                "activity_signal": 0.3,  # Low
                "pool_activity_score": 0.2,  # Low - should skip brief
                "net_liquidity_delta_24h": 0,
                "lp_churn_rate_24h": 0.5
            },
            "top_pools": ["WETH/USDC"],
            "source_ids": ["test_lp_source_2"]
        }
        
        result = await brief_node(state)
        
        # Should skip brief due to low activity
        self.assertIn("brief_skipped", result)
        self.assertEqual(result["reason"], "low_activity")
        self.assertEqual(result["status"], "memory")
    
    async def test_brief_gate_cooldown(self):
        """Test brief cooldown logic."""
        from nodes.brief import brief_node
        
        # Test state with recent brief
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=1)).timestamp()),  # Recent brief
            "last24h_counts": {"lp_add": 5, "lp_remove": 2},
            "signals": {
                "volume_signal": 0.8,  # High
                "activity_signal": 0.7,  # High
                "pool_activity_score": 1.0,  # High
                "net_liquidity_delta_24h": 3,
                "lp_churn_rate_24h": 0.8
            },
            "top_pools": ["WETH/USDC", "DEGEN/WETH"],
            "source_ids": ["test_lp_source_3"]
        }
        
        result = await brief_node(state)
        
        # Should skip brief due to cooldown
        self.assertIn("brief_skipped", result)
        self.assertEqual(result["reason"], "cooldown")
        self.assertEqual(result["status"], "memory")
    
    async def test_brief_artifact_persistence(self):
        """Test that brief artifacts are persisted to Layer 3."""
        from nodes.brief import brief_node
        
        # Test state that should emit brief
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),
            "last24h_counts": {"lp_add": 3, "lp_remove": 1},
            "signals": {
                "volume_signal": 0.4,
                "activity_signal": 0.5,
                "pool_activity_score": 0.8,  # High enough to trigger
                "net_liquidity_delta_24h": 2,
                "lp_churn_rate_24h": 0.75
            },
            "top_pools": ["WETH/USDC", "DEGEN/WETH"],
            "source_ids": ["test_lp_source_4"]
        }
        
        result = await brief_node(state)
        
        # Should emit brief
        self.assertIn("brief_text", result)
        
        # Verify artifact was persisted to Layer 3
        data_model = await get_data_model()
        briefs = await data_model.get_recent_briefs(limit=10)
        self.assertGreater(len(briefs), 0)
        
        # Check latest brief
        latest_brief = briefs[0]
        self.assertIn("LP activity", latest_brief.summary_text)
        self.assertIn("net delta 2", latest_brief.summary_text)
        self.assertIn("activity score 0.80", latest_brief.summary_text)
        
        # Check signals in artifact
        self.assertIn("pool_activity_score", latest_brief.signals)
        self.assertEqual(latest_brief.signals["pool_activity_score"], 0.8)
        
        # Check source_ids for provenance
        self.assertIn("test_lp_source_4", latest_brief.source_ids)
    
    async def test_brief_lp_heatmap_generation(self):
        """Test LP heatmap generation in brief."""
        from nodes.brief import brief_node
        
        # Test state with multiple LP events
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),
            "last24h_counts": {"lp_add": 4, "lp_remove": 2},
            "signals": {
                "volume_signal": 0.6,
                "activity_signal": 0.5,
                "pool_activity_score": 1.0,  # High activity
                "net_liquidity_delta_24h": 2,
                "lp_churn_rate_24h": 0.8,
                "net_liquidity_value": 1500.0
            },
            "top_pools": ["WETH/USDC", "DEGEN/WETH", "USDC/DAI"],
            "source_ids": ["test_lp_source_5"]
        }
        
        result = await brief_node(state)
        
        # Should emit brief
        self.assertIn("brief_text", result)
        
        # Check LP heatmap content
        brief_text = result["brief_text"]
        self.assertIn("LP activity", brief_text)
        self.assertIn("net delta 2", brief_text)
        self.assertIn("churn rate 0.80", brief_text)
        self.assertIn("activity score 1.00", brief_text)
        
        # Check next watchlist includes LP pools
        next_watchlist = result["next_watchlist"]
        lp_pools = [pool for pool in next_watchlist if "(LP)" in pool]
        self.assertGreater(len(lp_pools), 0)
        
        # Should include top pools with LP designation
        self.assertIn("WETH/USDC (LP)", next_watchlist)
        self.assertIn("DEGEN/WETH (LP)", next_watchlist)
    
    async def test_brief_provenance_chain(self):
        """Test that brief maintains full provenance chain."""
        from nodes.brief import brief_node
        
        # Test state with multiple source IDs
        state = {
            "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),
            "last24h_counts": {"lp_add": 2, "lp_remove": 1},
            "signals": {
                "volume_signal": 0.3,
                "activity_signal": 0.4,
                "pool_activity_score": 0.6,  # Just enough to trigger
                "net_liquidity_delta_24h": 1,
                "lp_churn_rate_24h": 0.6
            },
            "top_pools": ["WETH/USDC"],
            "source_ids": ["lp_activity_123", "wallet_activity_456"]
        }
        
        result = await brief_node(state)
        
        # Should emit brief
        self.assertIn("brief_text", result)
        
        # Verify artifact was persisted with provenance
        data_model = await get_data_model()
        briefs = await data_model.get_recent_briefs(limit=5)
        self.assertGreater(len(briefs), 0)
        
        latest_brief = briefs[0]
        
        # Check source_ids for provenance chain
        self.assertIn("lp_activity_123", latest_brief.source_ids)
        self.assertIn("wallet_activity_456", latest_brief.source_ids)
        
        # Verify provenance chain can be traced
        provenance_chain = await data_model.get_provenance_chain(latest_brief.artifact_id)
        self.assertIsNotNone(provenance_chain)
        self.assertIn("artifact_id", provenance_chain)
        self.assertIn("raw_responses", provenance_chain)
        self.assertIn("events", provenance_chain)
    
    async def test_brief_threshold_variations(self):
        """Test brief thresholds with various LP activity levels."""
        from nodes.brief import brief_node
        
        test_cases = [
            {
                "name": "high_lp_activity",
                "lp_score": 1.0,
                "expected_emit": True,
                "description": "High LP activity should emit"
            },
            {
                "name": "medium_lp_activity",
                "lp_score": 0.6,
                "expected_emit": True,
                "description": "Medium LP activity should emit"
            },
            {
                "name": "low_lp_activity",
                "lp_score": 0.5,
                "expected_emit": False,
                "description": "Low LP activity should skip"
            },
            {
                "name": "very_low_lp_activity",
                "lp_score": 0.1,
                "expected_emit": False,
                "description": "Very low LP activity should skip"
            }
        ]
        
        for test_case in test_cases:
            with self.subTest(test_case["name"]):
                state = {
                    "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp()),
                    "last24h_counts": {"lp_add": 2, "lp_remove": 1},
                    "signals": {
                        "volume_signal": 0.2,  # Low
                        "activity_signal": 0.3,  # Low
                        "pool_activity_score": test_case["lp_score"],
                        "net_liquidity_delta_24h": 1,
                        "lp_churn_rate_24h": 0.5
                    },
                    "top_pools": ["WETH/USDC"],
                    "source_ids": [f"test_source_{test_case['name']}"]
                }
                
                result = await brief_node(state)
                
                if test_case["expected_emit"]:
                    self.assertNotIn("brief_skipped", result, 
                                   f"Should emit brief for {test_case['description']}")
                    self.assertIn("brief_text", result)
                else:
                    self.assertIn("brief_skipped", result,
                                 f"Should skip brief for {test_case['description']}")
                    self.assertEqual(result["reason"], "low_activity")


if __name__ == "__main__":
    unittest.main()
