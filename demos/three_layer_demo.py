#!/usr/bin/env python3
"""
Demo of the Three-Layer Data Model in action.
Shows the complete flow: mock wallet fetch → scratch JSON → normalized Event → brief → persisted with provenance.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from data_model import (
    save_raw_response, normalize_event, persist_brief, get_provenance_chain,
    NormalizedEvent, Artifact
)
from mock_tools import fetch_wallet_activity


async def demo_three_layer_flow():
    """Demonstrate the complete three-layer data flow."""
    print("🔍 Three-Layer Data Model Demo")
    print("=" * 50)
    print("Flow: Mock wallet fetch → Scratch JSON → Normalized Event → Brief → Persisted with provenance")
    print()
    
    # Step 1: Mock wallet fetch (simulating Worker)
    print("📥 Step 1: Mock wallet fetch (Worker)")
    wallet = "0x1234567890abcdef"
    since_ts = 1234567890
    
    # Fetch wallet activity (simulating API call)
    wallet_events = fetch_wallet_activity(wallet, since_ts)
    print(f"   Retrieved {len(wallet_events)} events for wallet {wallet}")
    
    # Step 2: Save raw response to Layer 1 (Scratch JSON Cache)
    print("\n💾 Step 2: Save raw response to Layer 1 (Scratch JSON Cache)")
    raw_id = f"wallet_activity_{wallet}_{since_ts}"
    raw_data = {
        "wallet": wallet,
        "since_ts": since_ts,
        "events": wallet_events,
        "timestamp": 1234567890
    }
    provenance = {
        "source": "mock_tools",
        "wallet": wallet,
        "since_ts": since_ts,
        "snapshot_time": 1234567890
    }
    
    response_id = await save_raw_response(raw_id, "wallet_activity", raw_data, provenance)
    print(f"   ✅ Saved raw response: {response_id}")
    print(f"   📊 Raw data size: {len(str(raw_data))} chars")
    
    # Step 3: Normalize events to Layer 2 (Normalized Events)
    print("\n🔄 Step 3: Normalize events to Layer 2 (Normalized Events)")
    normalized_events = []
    
    for i, event in enumerate(wallet_events):
        # Create normalized event
        normalized_event = NormalizedEvent(
            event_id=event.get("txHash", f"event_{i}"),
            wallet=wallet,
            event_type=event.get("kind", "unknown"),
            pool=event.get("pool"),
            value={
                "amounts": event.get("amounts", {}),
                "chain": event.get("chain", "base"),
                "provenance": event.get("provenance", {})
            },
            timestamp=event.get("timestamp", 1234567890),
            source_id=response_id,
            chain=event.get("chain", "base")
        )
        
        # Save to Layer 2
        event_id = await normalize_event(normalized_event)
        normalized_events.append(normalized_event)
        print(f"   ✅ Normalized event: {event_id} ({normalized_event.event_type})")
    
    print(f"   📊 Total normalized events: {len(normalized_events)}")
    
    # Step 4: Create brief artifact for Layer 3 (Artifacts/Briefs)
    print("\n📝 Step 4: Create brief artifact for Layer 3 (Artifacts/Briefs)")
    
    # Simulate signals computation (from Analyze node)
    signals = {
        "volume_signal": 0.8,
        "activity_signal": 0.6,
        "concentration_signal": 0.4,
        "total_events_24h": len(normalized_events)
    }
    
    # Generate brief text
    brief_text = f"24h activity: {len(normalized_events)} events across multiple pools. "
    brief_text += f"Signals: volume={signals['volume_signal']:.2f}, activity={signals['activity_signal']:.2f}. "
    
    # Generate next watchlist
    pools = list(set(e.pool for e in normalized_events if e.pool))
    next_watchlist = pools[:2] if pools else ["WETH/USDC"]
    brief_text += f"Next watchlist: {', '.join(next_watchlist)}."
    
    # Create artifact
    artifact = Artifact(
        artifact_id=f"brief_{1234567890}",
        timestamp=1234567890,
        summary_text=brief_text,
        signals=signals,
        next_watchlist=next_watchlist,
        source_ids=[response_id],
        event_count=len(normalized_events)
    )
    
    # Persist to Layer 3
    artifact_id = await persist_brief(artifact)
    print(f"   ✅ Persisted artifact: {artifact_id}")
    print(f"   📊 Brief text: {len(brief_text)} chars")
    print(f"   📋 Next watchlist: {', '.join(next_watchlist)}")
    
    # Step 5: Demonstrate provenance chain
    print("\n🔗 Step 5: Demonstrate provenance chain")
    chain = await get_provenance_chain(artifact_id)
    
    print(f"   📊 Provenance chain for {chain['artifact_id']}:")
    print(f"   - Raw responses: {len(chain['raw_responses'])}")
    print(f"   - Normalized events: {len(chain['events'])}")
    
    if chain['raw_responses']:
        raw_response = chain['raw_responses'][0]
        print(f"   - Raw response source: {raw_response.get('_provenance', {}).get('source', 'unknown')}")
        print(f"   - Raw response wallet: {raw_response.get('wallet', 'unknown')}")
    
    if chain['events']:
        event = chain['events'][0]
        print(f"   - Event type: {event.get('event_type', 'unknown')}")
        print(f"   - Event pool: {event.get('pool', 'unknown')}")
    
    print("\n" + "=" * 50)
    print("✅ Three-layer data model demo completed!")
    print("\n📋 Summary:")
    print("- Layer 1: Raw API responses stored with provenance")
    print("- Layer 2: Normalized events with structured schema")
    print("- Layer 3: Human-readable briefs with full provenance chain")
    print("- End-to-end traceability from brief back to raw data")


async def demo_retention_and_cleanup():
    """Demonstrate retention rules and cleanup."""
    print("\n🗑️ Retention and Cleanup Demo")
    print("=" * 30)
    
    from data_model import get_data_model
    
    model = await get_data_model()
    
    # Add some test data
    await model.save_raw_response("old_scratch", "test", {"old": "data"})
    await model.save_raw_response("new_scratch", "test", {"new": "data"})
    
    # Add events
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
    await model.normalize_event(old_event)
    
    # Add artifacts
    old_artifact = Artifact(
        artifact_id="old_brief",
        timestamp=1234567890,
        summary_text="Old brief",
        signals={"volume_signal": 0.8},
        next_watchlist=["WETH/USDC"],
        source_ids=["old_scratch"],
        event_count=1
    )
    await model.persist_brief(old_artifact)
    
    print("   📊 Retention rules:")
    print("   - Scratch JSON: 7 days (purgeable)")
    print("   - Normalized Events: 30 days (mid-term)")
    print("   - Artifacts/Briefs: 90 days (long-term)")
    
    # Note: Actual cleanup would depend on timestamps
    print("   ✅ Cleanup functions available for each layer")


async def main():
    """Main demo function."""
    await demo_three_layer_flow()
    await demo_retention_and_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
