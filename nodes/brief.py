"""
Brief node with gating logic.
"""

import time
from datetime import datetime
from typing import Dict, Any

from .config import BRIEF_COOLDOWN, BRIEF_THRESHOLD_EVENTS, BRIEF_THRESHOLD_SIGNAL
from data_model import persist_brief, Artifact


async def brief_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced brief node with gating logic.
    
    Emits brief only if (new_events ≥ 5 OR max_signal ≥ 0.6) AND cooldown passed.
    Includes optional next_watchlist.
    """
    print("  📝 Brief: Checking if brief should be emitted...")
    start_time = time.time()
    
    # Get current time and last brief time
    current_time = int(datetime.now().timestamp())
    last_brief_at = state.get("last_brief_at", 0)
    
    # Check cooldown
    if current_time - last_brief_at < BRIEF_COOLDOWN:
        execution_time = time.time() - start_time
        print(f"    ⏰ Cooldown not passed ({BRIEF_COOLDOWN/3600:.1f}h remaining)")
        print(f"    ✅ Brief completed in {execution_time:.2f}s")
        return {
            **state,
            "brief_skipped": True,
            "reason": "cooldown",
            "status": "memory"
        }
    
    # Get event counts and signals
    event_counts = state.get("last24h_counts", {})
    signals = state.get("signals", {})
    
    total_events = sum(event_counts.values())
    max_signal = max(signals.values()) if signals else 0.0
    
    # Check thresholds
    if total_events < BRIEF_THRESHOLD_EVENTS and max_signal < BRIEF_THRESHOLD_SIGNAL:
        execution_time = time.time() - start_time
        print(f"    📉 Low activity: {total_events} events, max signal {max_signal:.2f}")
        print(f"    ✅ Brief completed in {execution_time:.2f}s")
        return {
            **state,
            "brief_skipped": True,
            "reason": "low_activity",
            "status": "memory"
        }
    
    # Generate brief
    top_pools = state.get("top_pools", [])
    brief_text = f"24h activity: {total_events} events across {len(event_counts)} types. "
    
    if top_pools:
        brief_text += f"Top pools: {', '.join(top_pools[:3])}. "
    
    if signals:
        brief_text += f"Signals: volume={signals.get('volume_signal', 0):.2f}, "
        brief_text += f"activity={signals.get('activity_signal', 0):.2f}. "
    
    # Generate next watchlist
    next_watchlist = []
    if top_pools:
        next_watchlist.extend(top_pools[:2])
    
    # Add any high-signal pools from raw data
    raw_data = state.get("raw_data", {})
    if "metrics" in raw_data:
        metrics = raw_data["metrics"]
        top_pool = metrics.get("key_values", {}).get("top_pool")
        if top_pool and top_pool not in next_watchlist:
            next_watchlist.append(top_pool)
    
    brief_text += f"Next watchlist: {', '.join(next_watchlist) if next_watchlist else 'none'}."
    
    # Create artifact for Layer 3
    current_time = int(datetime.now().timestamp())
    artifact_id = f"brief_{current_time}"
    source_ids = state.get("source_ids", [])
    
    artifact = Artifact(
        artifact_id=artifact_id,
        timestamp=current_time,
        summary_text=brief_text,
        signals=signals,
        next_watchlist=next_watchlist,
        source_ids=source_ids,
        event_count=total_events
    )
    
    # Persist to Layer 3
    await persist_brief(artifact)
    
    print(f"    ✅ Brief emitted: {len(brief_text)} chars")
    print(f"    📋 Next watchlist: {', '.join(next_watchlist) if next_watchlist else 'none'}")
    
    execution_time = time.time() - start_time
    print(f"    ✅ Brief completed in {execution_time:.2f}s")
    
    return {
        **state,
        "brief_text": brief_text,
        "next_watchlist": next_watchlist,
        "last_brief_at": current_time,
        "status": "memory"
    }
