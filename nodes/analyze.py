"""
Analyze node that processes events and computes signals.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import Counter

from data_model import normalize_event, NormalizedEvent


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
    
    # Normalize events into Layer 2
    normalized_events = []
    source_ids = set()
    
    # Get source_ids from worker
    worker_source_ids = state.get("source_ids", [])
    source_ids.update(worker_source_ids)
    
    for event in recent_events:
        # Use source_id from worker or generate one
        source_id = event.get("provenance", {}).get("source_id", worker_source_ids[0] if worker_source_ids else f"event_{int(time.time())}")
        source_ids.add(source_id)
        
        # Enhanced value dict with LP-specific details
        value_dict = {
            "amounts": event.get("amounts", {}),
            "chain": event.get("chain", "base"),
            "provenance": event.get("provenance", {})
        }
        
        # Add LP-specific details if available
        if event.get("details"):
            value_dict["details"] = event["details"]
        
        # Create normalized event
        normalized_event = NormalizedEvent(
            event_id=event.get("txHash", f"event_{int(time.time())}"),
            wallet=event.get("wallet"),
            event_type=event.get("kind", "unknown"),
            pool=event.get("pool"),
            value=value_dict,
            timestamp=event.get("timestamp", int(time.time())),
            source_id=source_id,
            chain=event.get("chain", "base")
        )
        
        # Save to Layer 2
        await normalize_event(normalized_event)
        normalized_events.append(normalized_event)
    
    # Count events by kind
    event_counts = Counter(e.get("kind", "unknown") for e in recent_events)
    
    # Identify top pools by event count
    pool_counts = Counter(e.get("pool", "unknown") for e in recent_events)
    top_pools = [pool for pool, count in pool_counts.most_common(5)]
    
    # Compute base signals
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
    
    # LP-specific signals
    lp_signals = {}
    lp_events = [e for e in recent_events if e.get("kind") in ["lp_add", "lp_remove"]]
    
    if lp_events:
        # Net liquidity delta (adds - removes)
        adds = sum(1 for e in lp_events if e.get("kind") == "lp_add")
        removes = sum(1 for e in lp_events if e.get("kind") == "lp_remove")
        net_delta = adds - removes
        lp_signals["net_liquidity_delta_24h"] = net_delta
        
        # LP churn rate (unique LPs / total LP ops)
        unique_lps = len(set(e.get("wallet", "unknown") for e in lp_events if e.get("wallet")))
        lp_signals["lp_churn_rate_24h"] = unique_lps / len(lp_events) if lp_events else 0
        
        # Pool activity score (simple heuristic 0-1)
        pool_activity_score = min(len(lp_events) / 5.0, 1.0)  # 5+ events = max score
        lp_signals["pool_activity_score"] = pool_activity_score
        
        # Net liquidity value (if details available)
        total_add_value = 0
        total_remove_value = 0
        for event in lp_events:
            details = event.get("details", {})
            if details.get("lp_tokens_delta"):
                if event.get("kind") == "lp_add":
                    total_add_value += abs(details["lp_tokens_delta"])
                else:
                    total_remove_value += abs(details["lp_tokens_delta"])
        
        lp_signals["net_liquidity_value"] = total_add_value - total_remove_value
    
    signals = {
        "volume_signal": volume_signal,
        "activity_signal": activity_signal,
        "concentration_signal": concentration_signal,
        "total_events_24h": total_events,
        **lp_signals  # Include LP-specific signals
    }
    
    print(f"    📈 24h events: {total_events}")
    print(f"    🏊 Top pools: {', '.join(top_pools[:3])}")
    print(f"    📊 Signals: volume={volume_signal:.2f}, activity={activity_signal:.2f}")
    
    # Print LP-specific signals if available
    if lp_signals:
        print(f"    💧 LP Signals: net_delta={lp_signals.get('net_liquidity_delta_24h', 0)}, "
              f"churn_rate={lp_signals.get('lp_churn_rate_24h', 0):.2f}, "
              f"activity_score={lp_signals.get('pool_activity_score', 0):.2f}")
    
    execution_time = time.time() - start_time
    print(f"    ✅ Analyze completed in {execution_time:.2f}s")
    
    return {
        **state,
        "last24h_counts": dict(event_counts),
        "top_pools": top_pools,
        "signals": signals,
        "normalized_events": normalized_events,
        "source_ids": list(source_ids),
        "status": "briefing"
    }
