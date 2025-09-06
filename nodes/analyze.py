"""
Analyze node that processes events and computes signals.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import Counter

from data_model import normalize_event, NormalizedEvent
from .output import formatter


async def analyze_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced analyze node that processes events and computes signals.
    
    Rolls up last 24h counts, identifies top pools, and computes activity signals.
    """
    start_time = time.time()
    formatter.log_node_progress("Analyze", "Processing events and computing signals...")
    
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

    # Wallet-specific signals (for wallet_recon actions)
    wallet_signals = {}
    selected_action = state.get("selected_action")

    if selected_action == "wallet_recon":
        # net_lp_usd_24h: Sum of LP adds minus LP removes in USD
        # Handle both legacy format (kind: lp_add/lp_remove) and new format (type: swap/transfer)
        net_lp_usd = 0.0
        for event in recent_events:
            usd_value = event.get("usd")
            if usd_value is not None:
                # Check legacy format first
                event_type = event.get("kind") or event.get("type")
                if event_type in ["lp_add", "swap"] and event.get("direction") != "out":
                    net_lp_usd += usd_value
                elif event_type in ["lp_remove"] and event.get("direction") == "out":
                    net_lp_usd -= usd_value
        wallet_signals["net_lp_usd_24h"] = net_lp_usd

        # new_pools_touched_24h: Distinct pool addresses from recent events
        # Handle both legacy pool field and new contract addresses
        all_pools = set()
        for event in recent_events:
            # Try multiple ways to find pool addresses
            pool = (event.get("pool") or
                   event.get("token_address") or
                   event.get("raw", {}).get("covalent_tx", {}).get("to_address"))

            if pool and pool != "unknown" and pool != "0x0000000000000000000000000000000000000000":
                all_pools.add(pool)
        wallet_signals["new_pools_touched_24h"] = list(all_pools)

    signals = {
        "volume_signal": volume_signal,
        "activity_signal": activity_signal,
        "concentration_signal": concentration_signal,
        "total_events_24h": total_events,
        **lp_signals,  # Include LP-specific signals
        **wallet_signals  # Include wallet-specific signals
    }
    
    # Log progress
    formatter.log_node_progress(
        "Analyze",
        f"Processed {total_events} events, computed {len(signals)} signals",
        time.time() - start_time
    )
    
    return {
        **state,
        "last24h_counts": dict(event_counts),
        "top_pools": top_pools,
        "signals": signals,
        "normalized_events": normalized_events,
        "source_ids": list(source_ids),
        "status": "briefing"
    }