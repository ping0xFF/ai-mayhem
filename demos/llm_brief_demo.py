#!/usr/bin/env python3
"""
Demo for LLM-backed briefs with different modes and token management.
"""

import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock
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

async def demo_deterministic_mode():
    """Demo deterministic brief mode."""
    print("\n📋 Deterministic Mode Demo")
    print("=" * 50)
    
    # Initialize data model
    data_model = ThreeLayerDataModel(Path("agent_state.db"))
    await data_model.initialize()
    
    # Create test events
    events = [MOCK_EVENT]
    for event in events:
        # First create the source in json_cache_scratch
        await data_model.save_raw_response(
            event.source_id,
            "test",
            {"test": "data"},
            {"test": "provenance"}
        )
        # Then create the normalized event
        await data_model.normalize_event(event)
    
    # Run brief node in deterministic mode
    with patch("nodes.config.BRIEF_MODE", "deterministic"):
        state = {
            "last24h_counts": {"lp_add": 5},
            "signals": MOCK_SIGNALS,
            "last_brief_at": 0,
            "source_ids": ["test_source"]
        }
        result = await brief_node(state)
        
        print("✅ Brief generated:")
        print(f"📝 Content: {result['brief_text']}")
        print(f"📋 Next Watchlist: {result['next_watchlist']}")
        print("🔍 LLM fields should be None:")
        briefs = await data_model.get_recent_briefs(1)
        print(f"   - summary_text_llm: {briefs[0].summary_text_llm}")
        print(f"   - llm_struct: {briefs[0].llm_struct}")
        print(f"   - llm_validation: {briefs[0].llm_validation}")
        print(f"   - llm_model: {briefs[0].llm_model}")
        print(f"   - llm_tokens: {briefs[0].llm_tokens}")

async def demo_llm_mode():
    """Demo LLM brief mode."""
    print("\n📋 LLM Mode Demo")
    print("=" * 50)
    
    # Initialize data model
    data_model = ThreeLayerDataModel(Path("agent_state.db"))
    await data_model.initialize()
    
    # Create test events
    events = [MOCK_EVENT]
    for event in events:
        # First create the source in json_cache_scratch
        await data_model.save_raw_response(
            event.source_id,
            "test",
            {"test": "data"},
            {"test": "provenance"}
        )
        # Then create the normalized event
        await data_model.normalize_event(event)
    
    # Run brief node in LLM mode
    with patch("nodes.config.BRIEF_MODE", "llm"), \
         patch("nodes.brief_llm.llm_call", AsyncMock(return_value=MOCK_LLM_RESPONSE)):
        state = {
            "last24h_counts": {"lp_add": 5},
            "signals": MOCK_SIGNALS,
            "last_brief_at": 0,
            "source_ids": ["test_source"]
        }
        result = await brief_node(state)
        
        print("✅ Brief generated:")
        print(f"📝 Content: {result['brief_text']}")
        print(f"📋 Next Watchlist: {result['next_watchlist']}")
        print("🔍 LLM fields should be populated:")
        briefs = await data_model.get_recent_briefs(1)
        print(f"   - summary_text_llm: {briefs[0].summary_text_llm}")
        print(f"   - llm_struct: {briefs[0].llm_struct}")
        print(f"   - llm_validation: {briefs[0].llm_validation}")
        print(f"   - llm_model: {briefs[0].llm_model}")
        print(f"   - llm_tokens: {briefs[0].llm_tokens}")

async def demo_both_mode():
    """Demo both (deterministic + LLM) brief mode."""
    print("\n📋 Both Mode Demo")
    print("=" * 50)
    
    # Initialize data model
    data_model = ThreeLayerDataModel(Path("agent_state.db"))
    await data_model.initialize()
    
    # Create test events
    events = [MOCK_EVENT]
    for event in events:
        # First create the source in json_cache_scratch
        await data_model.save_raw_response(
            event.source_id,
            "test",
            {"test": "data"},
            {"test": "provenance"}
        )
        # Then create the normalized event
        await data_model.normalize_event(event)
    
    # Run brief node in both mode
    with patch("nodes.config.BRIEF_MODE", "both"), \
         patch("nodes.brief_llm.llm_call", AsyncMock(return_value=MOCK_LLM_RESPONSE)):
        state = {
            "last24h_counts": {"lp_add": 5},
            "signals": MOCK_SIGNALS,
            "last_brief_at": 0,
            "source_ids": ["test_source"]
        }
        result = await brief_node(state)
        
        print("✅ Brief generated:")
        print(f"📝 Deterministic: {result['brief_text']}")
        print(f"📝 LLM: {result['llm_summary']}")
        print(f"📋 Next Watchlist: {result['next_watchlist']}")
        print("🔍 Both fields should be populated:")
        briefs = await data_model.get_recent_briefs(1)
        print(f"   - summary_text: {briefs[0].summary_text}")
        print(f"   - summary_text_llm: {briefs[0].summary_text_llm}")
        print(f"   - llm_struct: {briefs[0].llm_struct}")
        print(f"   - llm_validation: {briefs[0].llm_validation}")
        print(f"   - llm_model: {briefs[0].llm_model}")
        print(f"   - llm_tokens: {briefs[0].llm_tokens}")

async def demo_token_management():
    """Demo token management with different input policies."""
    print("\n📋 Token Management Demo")
    print("=" * 50)
    
    # Create large event set
    large_events = [MOCK_EVENT] * 1000  # Should exceed token cap
    
    # Test full input policy
    with patch("nodes.config.LLM_INPUT_POLICY", "full"):
        events, signals = reduce_events(large_events, MOCK_SIGNALS, LLM_TOKEN_CAP)
        print("✅ Full input policy:")
        print(f"   - Original events: {len(large_events)}")
        print(f"   - After reduction: {len(events)}")
        print(f"   - Reduction info: {signals.get('reduction_info', 'None')}")
    
    # Test budgeted input policy
    with patch("nodes.config.LLM_INPUT_POLICY", "budgeted"):
        events, signals = reduce_events(large_events, MOCK_SIGNALS, 1000)  # Small cap
        print("\n✅ Budgeted input policy:")
        print(f"   - Original events: {len(large_events)}")
        print(f"   - After reduction: {len(events)}")
        print(f"   - Reduction info: {signals.get('reduction_info', 'None')}")

async def main():
    """Run all demos."""
    print("🚀 LLM-Backed Briefs Demo")
    print("=" * 50)
    print(f"Current settings:")
    print(f"   - BRIEF_MODE: {BRIEF_MODE}")
    print(f"   - LLM_INPUT_POLICY: {LLM_INPUT_POLICY}")
    print(f"   - LLM_TOKEN_CAP: {LLM_TOKEN_CAP}")
    print(f"   - LLM_BRIEF_MODEL: {LLM_BRIEF_MODEL}")
    
    await demo_deterministic_mode()
    await demo_llm_mode()
    await demo_both_mode()
    await demo_token_management()

if __name__ == "__main__":
    asyncio.run(main())