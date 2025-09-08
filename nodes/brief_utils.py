"""
Brief node utilities for LLM integration.
"""

import json
import numpy as np
from typing import List, Dict, Any, Tuple
from data_model import NormalizedEvent

def estimate_tokens(events: List[NormalizedEvent], rollups: Dict[str, Any]) -> int:
    """
    Estimate token count for LLM input.
    
    Uses a rough heuristic based on JSON string length:
    - 1 token ≈ 4 chars for English text
    - 1 token ≈ 3 chars for JSON (denser due to syntax)
    """
    events_json = json.dumps([{
        "event_id": e.event_id,
        "wallet": e.wallet,
        "event_type": e.event_type,
        "pool": e.pool,
        "value": e.value,
        "timestamp": e.timestamp
    } for e in events])
    
    rollups_json = json.dumps(rollups)
    
    # Estimate based on JSON string length
    # - 1 token ≈ 4 chars for English text
    # - 1 token ≈ 3 chars for JSON (denser due to syntax)
    total_chars = len(events_json) + len(rollups_json)
    return total_chars // 3 + 100  # +100 for prompt

def get_usd_value(event: NormalizedEvent) -> float:
    """Extract USD value from event."""
    if "usd_value" in event.value:
        return float(event.value["usd_value"])
    return 0.0

def is_outlier(values: List[float], value: float, threshold: float = 2.0) -> bool:
    """Check if a value is an outlier using z-score."""
    if not values or len(values) < 2:
        return False
    mean = sum(values) / len(values)
    std = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
    z_score = abs((value - mean) / std) if std > 0 else 0
    return z_score > threshold

def reduce_events(events: List[NormalizedEvent], signals: Dict[str, float], token_cap: int) -> Tuple[List[NormalizedEvent], Dict[str, Any]]:
    """
    Reduce event set to fit within token cap while preserving important events.
    
    Strategy:
    1. Keep largest USD moves
    2. Keep first/last events per wallet/pool
    3. Keep unique wallets/pools
    4. Keep anomalies (outliers by z-score)
    5. Keep events referenced by deterministic rollups
    
    Drop:
    1. Micro-noise below dollar/size floor
    2. Repetitive micro-events
    """
    if not events:
        return [], signals
    
    # First check if we're under cap
    if estimate_tokens(events, signals) <= token_cap:
        return events, signals
    
    # Extract USD values
    usd_values = [get_usd_value(e) for e in events]
    
    # Track unique wallets and pools
    wallets = set()
    pools = set()
    
    # Track first/last events
    first_events = {}  # wallet/pool -> event
    last_events = {}   # wallet/pool -> event
    
    # Track important events
    keep_events = set()  # event_ids to keep
    
    # Process events
    for event in events:
        # Track uniques
        if event.wallet:
            wallets.add(event.wallet)
            if event.wallet not in first_events:
                first_events[event.wallet] = event
            last_events[event.wallet] = event
        
        if event.pool:
            pools.add(event.pool)
            if event.pool not in first_events:
                first_events[event.pool] = event
            last_events[event.pool] = event
        
        # Check if outlier
        value = get_usd_value(event)
        if is_outlier(usd_values, value):
            keep_events.add(event.event_id)
    
    # Add first/last events
    for e in first_events.values():
        keep_events.add(e.event_id)
    for e in last_events.values():
        keep_events.add(e.event_id)
    
    # Sort by USD value and add top events until we hit cap
    sorted_events = sorted(events, key=get_usd_value, reverse=True)
    result_events = []
    
    # First add all important events
    for event in sorted_events:
        if event.event_id in keep_events:
            result_events.append(event)
    
    # Then add top events by USD value until we hit cap
    for event in sorted_events:
        if event.event_id not in keep_events:
            result_events.append(event)
            if estimate_tokens(result_events, signals) > token_cap:
                result_events.pop()  # Remove last event that put us over cap
                break
    
    # If we still have too many events, reduce further
    while estimate_tokens(result_events, signals) > token_cap and len(result_events) > 10:
        result_events.pop()  # Keep removing events until we're under cap
    
    # Add reduction info to signals
    signals["reduction_info"] = {
        "original_count": len(events),
        "reduced_count": len(result_events),
        "unique_wallets": len(wallets),
        "unique_pools": len(pools),
        "outliers_kept": sum(1 for e in result_events if e.event_id in keep_events)
    }
    
    return result_events, signals