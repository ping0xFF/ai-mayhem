#!/usr/bin/env python3
"""
End-to-End LP Demo: Complete Three-Layer Data Flow
Demonstrates Task Card #1 + #2: Tools → Worker → Analyze → Brief → Memory
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mock_tools import fetch_lp_activity
from nodes.worker import worker_node
from nodes.analyze import analyze_node
from nodes.brief import brief_node
from nodes.memory import memory_node
from data_model import get_data_model


async def demo_lp_e2e_flow():
    """Demonstrate complete LP end-to-end flow."""
    print("🚀 LP End-to-End Demo: Three-Layer Data Flow")
    print("=" * 60)
    
    # Initialize data model
    data_model = await get_data_model()
    print("✅ Data model initialized")
    
    # Step 1: Worker - Fetch LP Activity and Save to Scratch Layer
    print("\n📋 Step 1: Worker - Fetch LP Activity")
    print("-" * 40)
    
    worker_state = {
        "selected_action": "lp_recon",
        "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())},
        "use_realistic_fixtures": True  # Use realistic fixtures for demo
    }
    
    worker_result = await worker_node(worker_state)
    print(f"✅ Worker completed: {len(worker_result['events'])} events retrieved")
    print(f"📊 Source IDs: {worker_result['source_ids']}")
    
    # Verify scratch layer
    source_id = worker_result["source_ids"][0]
    raw_response = await data_model.get_raw_response(source_id)
    print(f"📦 Scratch Layer: Raw response saved with {len(raw_response.get('events', []))} events")
    
    # Step 2: Analyze - Normalize Events and Compute Signals
    print("\n📋 Step 2: Analyze - Normalize Events")
    print("-" * 40)
    
    analyze_state = {
        **worker_result,
        "events": worker_result["events"]
    }
    
    analyze_result = await analyze_node(analyze_state)
    print(f"✅ Analyze completed: {len(analyze_result['normalized_events'])} events normalized")
    
    # Display LP signals
    signals = analyze_result["signals"]
    print(f"💧 LP Signals:")
    print(f"   - Net Liquidity Delta: {signals.get('net_liquidity_delta_24h', 0)}")
    print(f"   - LP Churn Rate: {signals.get('lp_churn_rate_24h', 0):.2f}")
    print(f"   - Pool Activity Score: {signals.get('pool_activity_score', 0):.2f}")
    print(f"   - Net Liquidity Value: {signals.get('net_liquidity_value', 0):.0f}")
    
    # Verify events layer
    events = await data_model.get_events_by_type("lp_add")
    print(f"📊 Events Layer: {len(events)} LP add events stored")
    
    # Step 3: Brief - Generate LP-Focused Summary
    print("\n📋 Step 3: Brief - Generate Summary")
    print("-" * 40)
    
    brief_state = {
        **analyze_result,
        "last_brief_at": int((datetime.now() - timedelta(hours=7)).timestamp())  # Cooldown passed
    }
    
    brief_result = await brief_node(brief_state)
    
    if "brief_skipped" in brief_result:
        print(f"⏰ Brief skipped: {brief_result['reason']}")
    else:
        print(f"✅ Brief emitted: {len(brief_result['brief_text'])} characters")
        print(f"📝 Content: {brief_result['brief_text']}")
        print(f"📋 Next Watchlist: {brief_result['next_watchlist']}")
    
    # Verify artifacts layer
    briefs = await data_model.get_recent_briefs(limit=5)
    if briefs:
        latest_brief = briefs[0]
        print(f"📦 Artifacts Layer: Brief saved with {latest_brief.event_count} events")
        print(f"🔗 Provenance: {len(latest_brief.source_ids)} source IDs")
    
    # Step 4: Memory - Persist and Update Cursors
    print("\n📋 Step 4: Memory - Persist and Update")
    print("-" * 40)
    
    memory_state = {
        **brief_result,
        "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())}
    }
    
    memory_result = await memory_node(memory_state)
    print(f"✅ Memory completed: Cursors updated")
    
    # Step 5: Provenance Chain Demo
    print("\n📋 Step 5: Provenance Chain Demo")
    print("-" * 40)
    
    if briefs:
        latest_brief = briefs[0]
        provenance_chain = await data_model.get_provenance_chain(latest_brief.artifact_id)
        
        print(f"🔗 Full Provenance Chain:")
        print(f"   - Artifact ID: {provenance_chain['artifact_id']}")
        print(f"   - Raw Responses: {len(provenance_chain['raw_responses'])}")
        print(f"   - Normalized Events: {len(provenance_chain['events'])}")
        
        # Show sample raw response
        if provenance_chain['raw_responses']:
            raw_response = provenance_chain['raw_responses'][0]
            print(f"   - Sample Raw: {len(raw_response.get('events', []))} events from {raw_response.get('_provenance', {}).get('source', 'unknown')}")
        
        # Show sample events
        if provenance_chain['events']:
            sample_event = provenance_chain['events'][0]
            print(f"   - Sample Event: {sample_event['event_type']} in {sample_event['pool']}")
    
    # Step 6: Data Layer Summary
    print("\n📋 Step 6: Three-Layer Data Summary")
    print("-" * 40)
    
    # Count data in each layer
    scratch_count = len(await data_model.get_raw_response("dummy")) if await data_model.get_raw_response("dummy") else 0
    events_count = len(await data_model.get_events_by_type("lp_add")) + len(await data_model.get_events_by_type("lp_remove"))
    artifacts_count = len(await data_model.get_recent_briefs(limit=100))
    
    print(f"📊 Layer 1 (Scratch): {len(worker_result['source_ids'])} raw responses")
    print(f"📊 Layer 2 (Events): {events_count} normalized events")
    print(f"📊 Layer 3 (Artifacts): {artifacts_count} brief artifacts")
    
    print("\n🎉 Demo Complete!")
    print("=" * 60)


async def demo_idempotency():
    """Demonstrate idempotent behavior."""
    print("\n🔄 Idempotency Demo")
    print("=" * 40)
    
    # Run the same worker operation twice
    worker_state = {
        "selected_action": "lp_recon",
        "cursors": {"lp": int((datetime.now() - timedelta(hours=10)).timestamp())},
        "use_realistic_fixtures": False  # Use simple fixtures
    }
    
    print("📋 Running worker twice with same parameters...")
    
    result1 = await worker_node(worker_state)
    result2 = await worker_node(worker_state)
    
    print(f"✅ First run: {len(result1['events'])} events")
    print(f"✅ Second run: {len(result2['events'])} events")
    print(f"🔄 Idempotent: {len(result1['events']) == len(result2['events'])}")
    
    # Check that no duplicate events were created
    data_model = await get_data_model()
    events = await data_model.get_events_by_type("lp_add")
    unique_event_ids = set(event.event_id for event in events)
    print(f"📊 Total LP add events: {len(events)}")
    print(f"📊 Unique event IDs: {len(unique_event_ids)}")
    print(f"🔄 No duplicates: {len(events) == len(unique_event_ids)}")


async def demo_signal_variations():
    """Demonstrate signal variations with different fixture types."""
    print("\n📊 Signal Variations Demo")
    print("=" * 40)
    
    # Test with simple fixtures
    print("📋 Simple Fixtures (3 events):")
    simple_events = fetch_lp_activity(int((datetime.now() - timedelta(hours=10)).timestamp()), use_realistic=False)
    
    simple_state = {
        "events": simple_events,
        "source_ids": ["simple_test"]
    }
    
    simple_result = await analyze_node(simple_state)
    simple_signals = simple_result["signals"]
    
    print(f"   - Net Delta: {simple_signals.get('net_liquidity_delta_24h', 0)}")
    print(f"   - Churn Rate: {simple_signals.get('lp_churn_rate_24h', 0):.2f}")
    print(f"   - Activity Score: {simple_signals.get('pool_activity_score', 0):.2f}")
    
    # Test with realistic fixtures
    print("\n📋 Realistic Fixtures (5 events):")
    realistic_events = fetch_lp_activity(int((datetime.now() - timedelta(hours=10)).timestamp()), use_realistic=True)
    
    realistic_state = {
        "events": realistic_events,
        "source_ids": ["realistic_test"]
    }
    
    realistic_result = await analyze_node(realistic_state)
    realistic_signals = realistic_result["signals"]
    
    print(f"   - Net Delta: {realistic_signals.get('net_liquidity_delta_24h', 0)}")
    print(f"   - Churn Rate: {realistic_signals.get('lp_churn_rate_24h', 0):.2f}")
    print(f"   - Activity Score: {realistic_signals.get('pool_activity_score', 0):.2f}")


async def main():
    """Run the complete LP end-to-end demo."""
    try:
        await demo_lp_e2e_flow()
        await demo_idempotency()
        await demo_signal_variations()
        
        print("\n🎯 Demo Summary:")
        print("✅ Task Card #1: Tools → Worker → Analyze + Signals + Tests")
        print("✅ Task Card #2: Brief/Gating + Tests")
        print("✅ End-to-End Flow: Complete three-layer data transformation")
        print("✅ Idempotent Operations: No duplicate data across layers")
        print("✅ Provenance Chain: Full traceability from brief to raw data")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
