#!/usr/bin/env python3
"""
Tests for LLM-backed briefs.
"""

import unittest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from nodes.config import (
    BRIEF_MODE, LLM_INPUT_POLICY, LLM_TOKEN_CAP,
    LLM_BRIEF_MODEL
)
from nodes.brief import brief_node
from nodes.brief_utils import estimate_tokens, reduce_events
from data_model import (
    ThreeLayerDataModel, NormalizedEvent, Artifact,
    save_raw_response, normalize_event, persist_brief,
    get_events_by_wallet, get_recent_briefs
)

# Test fixtures
MOCK_EVENT = NormalizedEvent(
    event_id="tx123:0",
    wallet="0x123",
    event_type="lp_add",
    pool="pool123",
    value={"usd_value": 1000},
    timestamp=int(datetime.now().timestamp()),
    source_id="source123",
    chain="base"
)

MOCK_SIGNALS = {
    "volume_signal": 0.8,
    "activity_signal": 0.7,
    "pool_activity_score": 0.65,
    "net_liquidity_delta_24h": 5000,
    "lp_churn_rate_24h": 0.42
}

MOCK_LLM_RESPONSE = {
    "text": json.dumps({
        "summary_text": "Test LLM brief summary",
        "struct": {
            "top_wallets": [{"address": "0x123", "score": 0.95, "reason": "High activity"}],
            "notable_events": [{"type": "lp_add", "pool": "pool123", "usd": 1000, "why": "Large add"}],
            "signals": {"churn": 0.42, "concentration": "high"},
            "risk_flags": ["price_divergence_possible"],
            "confidence": 0.77
        },
        "validation": {
            "consistency_ok": True,
            "discrepancies": []
        }
    }),
    "usage": {"total_tokens": 500},
    "model": "haiku",
    "estimated_cost": 0.001
}

class TestLLMBrief(unittest.IsolatedAsyncioTestCase):
    """Test LLM-backed brief functionality."""
    
    async def asyncSetUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Reset global data model instance
        import data_model
        data_model._data_model = None
        
        # Patch the DB_PATH to use our temporary database
        self.patcher = patch('data_model.DB_PATH', Path(self.temp_db.name))
        self.patcher.start()
        
        # Initialize data model
        self.data_model = await data_model.get_data_model()
        
        # Create test events
        self.events = [MOCK_EVENT]
        for event in self.events:
            # First create the source in json_cache_scratch
            await self.data_model.save_raw_response(
                event.source_id,
                "test",
                {"test": "data"},
                {"test": "provenance"}
            )
            # Then create the normalized event
            await self.data_model.normalize_event(event)
    
    async def asyncTearDown(self):
        """Clean up test database."""
        # Stop the patcher
        self.patcher.stop()
        
        # Reset global data model instance
        import data_model
        data_model._data_model = None
        
        # Clean up temp database
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def test_mode_switch(self):
        """Test that BRIEF_MODE controls which fields are persisted."""
        # Test deterministic mode
        with patch("nodes.config.BRIEF_MODE", "deterministic"), \
             patch("nodes.brief_llm.llm_call", side_effect=Exception("LLM call not expected in deterministic mode")):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0,
                "source_ids": ["test_source"]  # Add source_ids to state
            }
            result = await brief_node(state)
            self.assertNotIn("llm_summary", result)
            
            # Get latest brief
            briefs = await self.data_model.get_recent_briefs(1)
            self.assertIsNone(briefs[0].summary_text_llm)
            self.assertIsNone(briefs[0].llm_struct)
            self.assertIsNone(briefs[0].llm_validation)
            self.assertIsNone(briefs[0].llm_model)
            self.assertIsNone(briefs[0].llm_tokens)
        
        # Test LLM mode
        with patch("nodes.config.BRIEF_MODE", "llm"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0
            }
            result = await brief_node(state)
            self.assertIn("llm_summary", result)
            
            # Get latest brief
            briefs = await self.data_model.get_recent_briefs(1)
            self.assertIsNotNone(briefs[0].summary_text_llm)
            self.assertIsNotNone(briefs[0].llm_struct)
    
    async def test_full_vs_reduced_input(self):
        """Test event reduction based on token cap."""
        # Create large event set
        large_events = [MOCK_EVENT] * 1000  # Should exceed token cap
        
        # Test full input policy
        with patch("nodes.config.LLM_INPUT_POLICY", "full"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            events, signals = reduce_events(large_events, MOCK_SIGNALS, LLM_TOKEN_CAP)
            self.assertEqual(len(events), len(large_events))  # No reduction
            self.assertNotIn("reduction_info", signals)  # No reduction info
        
        # Test budgeted input policy with small token cap
        with patch("nodes.config.LLM_INPUT_POLICY", "budgeted"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            events, signals = reduce_events(large_events, MOCK_SIGNALS, 1000)  # Small cap
            self.assertLess(len(events), len(large_events))  # Should be reduced
            self.assertIn("reduction_info", signals)  # Should have reduction info
    
    async def test_persistence(self):
        """Test that all LLM fields are persisted correctly."""
        with patch("nodes.config.BRIEF_MODE", "both"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0,
                "source_ids": ["test_source"]  # Add source_ids to state
            }
            await brief_node(state)
            
            # Get latest brief
            briefs = await self.data_model.get_recent_briefs(1)
            brief = briefs[0]
            
            # Check all fields
            self.assertIsNotNone(brief.summary_text_llm)
            self.assertIsNotNone(brief.llm_struct)
            self.assertIsNotNone(brief.llm_validation)
            self.assertEqual(brief.llm_model, "haiku")
            self.assertEqual(brief.llm_tokens, 500)
    
    async def test_validation_wiring(self):
        """Test that validation discrepancies are captured."""
        # Mock LLM response with discrepancy
        mock_response = {
            **MOCK_LLM_RESPONSE,
            "text": json.dumps({
                "summary_text": "Test with discrepancy",
                "struct": json.loads(MOCK_LLM_RESPONSE["text"])["struct"],
                "validation": {
                    "consistency_ok": False,
                    "discrepancies": ["LP add count mismatch: LLM=6, rollup=5"]
                }
            })
        }
        
        with patch("nodes.config.BRIEF_MODE", "both"), \
             patch("nodes.brief_llm.llm_call", return_value=mock_response):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0,
                "source_ids": ["test_source"]  # Add source_ids to state
            }
            await brief_node(state)
            
            # Get latest brief
            briefs = await self.data_model.get_recent_briefs(1)
            self.assertEqual(len(briefs), 1, "No brief was persisted")
            brief = briefs[0]
            
            # Check validation
            self.assertIsNotNone(brief.llm_validation)  # Should have validation data
            validation = json.loads(brief.llm_validation)  # Parse JSON string
            self.assertFalse(validation["consistency_ok"])
            self.assertEqual(len(validation["discrepancies"]), 1)
    
    async def test_token_accounting(self):
        """Test that token usage is tracked correctly."""
        with patch("nodes.config.BRIEF_MODE", "both"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0,
                "source_ids": ["test_source"]  # Add source_ids to state
            }
            await brief_node(state)
            
            # Get latest brief
            briefs = await self.data_model.get_recent_briefs(1)
            brief = briefs[0]
            
            # Check token usage
            self.assertEqual(brief.llm_tokens, 500)
    
    async def test_idempotency(self):
        """Test that re-running with same window updates existing brief."""
        with patch("nodes.config.BRIEF_MODE", "both"), \
             patch("nodes.brief_llm.llm_call", return_value=MOCK_LLM_RESPONSE):
            state = {
                "last24h_counts": {"lp_add": 5},
                "signals": MOCK_SIGNALS,
                "last_brief_at": 0,
                "source_ids": ["test_source"]  # Add source_ids to state
            }
            
            # Run twice
            await brief_node(state)
            await brief_node(state)
            
            # Get all briefs
            briefs = await self.data_model.get_recent_briefs(10)
            
            # Should have only one brief
            self.assertEqual(len(briefs), 1)
    
if __name__ == '__main__':
    unittest.main()