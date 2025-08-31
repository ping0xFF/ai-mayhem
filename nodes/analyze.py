"""
Analyze node that processes events and computes signals.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any
from collections import Counter


async def analyze_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced analyze node that processes events and computes signals.
    
    Rolls up last 24h counts, identifies top pools, and computes activity signals.
    """
    print("  📊 Analyze: Processing events and computing signals...")
    start_time = time.time()
    
    events = state.get("events", [])
    if not events:
        return {
            **state,
            "last24h_counts": {},
            "top_pools": [],
            "signals": {},
            "status": "completed"
        }
    
    # Filter events from last 24 hours
    cutoff_time = int((datetime.now() - timedelta(hours=24)).timestamp())
    recent_events = [e for e in events if e.get("timestamp", 0) >= cutoff_time]
    
    # Count events by kind
    event_counts = Counter(e.get("kind", "unknown") for e in recent_events)
    
    # Identify top pools by event count
    pool_counts = Counter(e.get("pool", "unknown") for e in recent_events)
    top_pools = [pool for pool, count in pool_counts.most_common(5)]
    
    # Compute signals
    total_events = len(recent_events)
    volume_signal = min(total_events / 10.0, 1.0)  # Normalize to 0-1
    
    # Activity signal based on variety of event types
    activity_signal = min(len(event_counts) / 3.0, 1.0)  # 3 types max
    
    # Pool concentration signal (lower is better for diversity)
    if top_pools:
        top_pool_events = pool_counts[top_pools[0]]
        concentration_signal = 1.0 - (top_pool_events / total_events if total_events > 0 else 0)
    else:
        concentration_signal = 0.0
    
    signals = {
        "volume_signal": volume_signal,
        "activity_signal": activity_signal,
        "concentration_signal": concentration_signal,
        "total_events_24h": total_events
    }
    
    print(f"    📈 24h events: {total_events}")
    print(f"    🏊 Top pools: {', '.join(top_pools[:3])}")
    print(f"    📊 Signals: volume={volume_signal:.2f}, activity={activity_signal:.2f}")
    
    execution_time = time.time() - start_time
    print(f"    ✅ Analyze completed in {execution_time:.2f}s")
    
    return {
        **state,
        "last24h_counts": dict(event_counts),
        "top_pools": top_pools,
        "signals": signals,
        "status": "briefing"
    }
