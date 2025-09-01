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
    
    # Separate general signals from LP-specific signals
    general_signals = {k: v for k, v in signals.items() if k in ['volume_signal', 'activity_signal', 'concentration_signal']}
    max_general_signal = max(general_signals.values()) if general_signals else 0.0
    
    # Check thresholds (including LP-specific thresholds)
    lp_activity_score = signals.get("pool_activity_score", 0.0)
    lp_threshold_met = lp_activity_score >= 0.6  # LP-specific threshold
    
    if total_events < BRIEF_THRESHOLD_EVENTS and max_general_signal < BRIEF_THRESHOLD_SIGNAL and not lp_threshold_met:
        execution_time = time.time() - start_time
        print(f"    📉 Low activity: {total_events} events, max general signal {max_general_signal:.2f}, LP score {lp_activity_score:.2f}")
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
    
    # Add LP-specific information if available
    lp_signals = {k: v for k, v in signals.items() if k.startswith(('net_liquidity', 'lp_churn', 'pool_activity'))}
    if lp_signals:
        brief_text += f"LP activity: net delta {lp_signals.get('net_liquidity_delta_24h', 0)}, "
        brief_text += f"churn rate {lp_signals.get('lp_churn_rate_24h', 0):.2f}, "
        brief_text += f"activity score {lp_signals.get('pool_activity_score', 0):.2f}. "

    # Add wallet-specific information if this was a wallet recon
    selected_action = state.get("selected_action")
    wallet_signals = {k: v for k, v in signals.items() if k.startswith(('net_lp_usd', 'new_pools_touched'))}
    if selected_action == "wallet_recon" and wallet_signals:
        brief_text += f"Wallet recon: net LP USD ${wallet_signals.get('net_lp_usd_24h', 0):.2f}, "
        new_pools = wallet_signals.get('new_pools_touched_24h', [])
        brief_text += f"new pools touched {len(new_pools)}. "
    
    if signals:
        brief_text += f"General signals: volume={signals.get('volume_signal', 0):.2f}, "
        brief_text += f"activity={signals.get('activity_signal', 0):.2f}. "
    
    # Generate next watchlist
    next_watchlist = []
    if top_pools:
        next_watchlist.extend(top_pools[:2])
    
    # Add LP-specific pools with high activity
    if lp_signals and lp_signals.get("pool_activity_score", 0) > 0.5:
        # Add pools with high LP activity to watchlist
        if top_pools:
            next_watchlist.extend([f"{pool} (LP)" for pool in top_pools[:2]])
    
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
