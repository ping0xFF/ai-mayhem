#!/usr/bin/env python3
"""
Planner/Worker nodes for controlled autonomy.
Integrates with existing Budget → Recon → Analyze → Brief flow.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import Counter

from json_storage import save_json, get_cursor, set_cursor
from mock_tools import fetch_wallet_activity, fetch_lp_activity, web_metrics_lookup, get_event_id


# Configuration
BUDGET_DAILY = float(os.getenv("BUDGET_DAILY", "5.0"))
CURSOR_STALE_WALLET = 2 * 3600  # 2 hours
CURSOR_STALE_LP = 6 * 3600      # 6 hours
CURSOR_STALE_EXPLORE = 24 * 3600  # 24 hours
BRIEF_COOLDOWN = 6 * 3600       # 6 hours
BRIEF_THRESHOLD_EVENTS = 5
BRIEF_THRESHOLD_SIGNAL = 0.6

# Per-node timeout configuration
PLANNER_TIMEOUT = 10  # seconds
WORKER_TIMEOUT = 20   # seconds
ANALYZE_TIMEOUT = 15  # seconds
BRIEF_TIMEOUT = 10    # seconds
MEMORY_TIMEOUT = 10   # seconds


async def with_timeout(coro, timeout_seconds, node_name):
    """Execute a coroutine with timeout handling."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"    ⏰ {node_name} timed out after {timeout_seconds}s")
        return {
            "status": "failed",
            "error": f"{node_name} timed out after {timeout_seconds}s"
        }
    except Exception as e:
        print(f"    ❌ {node_name} failed: {e}")
        return {
            "status": "failed", 
            "error": str(e)
        }


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planner node that selects the next action based on cursor staleness and budget.
    
    Rules:
    - If wallet cursor stale (>2h): choose wallet_recon
    - Else if LP cursor stale (>6h): choose lp_recon  
    - Else: explore_metrics once per day (cooldown)
    - Hard stop if budget gate failed
    """
    print("  📋 Planner: Selecting next action...")
    start_time = time.time()
    
    # Check budget first
    spent = state.get("spent_today", 0.0)
    if spent >= BUDGET_DAILY:
        execution_time = time.time() - start_time
        print(f"    Budget exceeded: ${spent:.2f}/${BUDGET_DAILY:.2f}")
        print(f"    ✅ Planner completed in {execution_time:.2f}s")
        return {**state, "status": "capped"}
    
    # Get current cursors
    cursors = state.get("cursors", {})
    current_time = int(datetime.now().timestamp())
    
    # Check wallet cursors (stale if >2h)
    for cursor_key, cursor_ts in cursors.items():
        if cursor_key.startswith("wallet:") and cursor_ts:
            wallet = cursor_key.split(":", 1)[1]
            if current_time - cursor_ts > CURSOR_STALE_WALLET:
                execution_time = time.time() - start_time
                print(f"    Wallet cursor stale for {wallet} (>2h)")
                print(f"    ✅ Planner completed in {execution_time:.2f}s")
                return {
                    **state,
                    "selected_action": "wallet_recon",
                    "target_wallet": wallet,
                    "status": "working"
                }
    
    # Check LP cursor (stale if >6h)
    lp_cursor = cursors.get("lp", 0)
    if current_time - lp_cursor > CURSOR_STALE_LP:
        execution_time = time.time() - start_time
        print("    LP cursor stale (>6h)")
        print(f"    ✅ Planner completed in {execution_time:.2f}s")
        return {
            **state,
            "selected_action": "lp_recon",
            "status": "working"
        }
    
    # Check explore_metrics cursor (stale if >24h)
    explore_cursor = cursors.get("explore_metrics", 0)
    if current_time - explore_cursor > CURSOR_STALE_EXPLORE:
        execution_time = time.time() - start_time
        print("    Explore metrics cursor stale (>24h)")
        print(f"    ✅ Planner completed in {execution_time:.2f}s")
        return {
            **state,
            "selected_action": "explore_metrics",
            "status": "working"
        }
    
    # All cursors fresh - no action needed
    execution_time = time.time() - start_time
    print("    All cursors fresh - no action needed")
    print(f"    ✅ Planner completed in {execution_time:.2f}s")
    return {**state, "status": "completed"}


async def worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker node that executes the selected action via tool calls.
    
    Saves raw responses to JSON cache and returns normalized events.
    """
    selected_action = state.get("selected_action")
    
    if not selected_action:
        return {**state, "events": [], "status": "completed"}
    
    print(f"  🔧 Worker: Executing {selected_action}...")
    start_time = time.time()
    
    events = []
    raw_data = {}
    
    try:
        if selected_action == "wallet_recon":
            wallet = state.get("target_wallet")
            if not wallet:
                raise ValueError("No target wallet specified")
            
            # Get cursor for this wallet
            cursor_key = f"wallet:{wallet}"
            since_ts = state.get("cursors", {}).get(cursor_key, 0)
            
            # Fetch wallet activity
            wallet_events = fetch_wallet_activity(wallet, since_ts)
            
            # Save raw data
            raw_id = f"wallet_activity_{wallet}_{since_ts}"
            await save_json(raw_id, "wallet_activity", {
                "wallet": wallet,
                "since_ts": since_ts,
                "events": wallet_events,
                "timestamp": int(datetime.now().timestamp())
            })
            
            events = wallet_events
            raw_data = {"wallet": wallet, "event_count": len(events)}
            
            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor(cursor_key, new_cursor, f"Last wallet activity fetch for {wallet}")
            
        elif selected_action == "lp_recon":
            # Get LP cursor
            since_ts = state.get("cursors", {}).get("lp", 0)
            
            # Fetch LP activity
            lp_events = fetch_lp_activity(since_ts)
            
            # Save raw data
            raw_id = f"lp_activity_{since_ts}"
            await save_json(raw_id, "lp_activity", {
                "since_ts": since_ts,
                "events": lp_events,
                "timestamp": int(datetime.now().timestamp())
            })
            
            events = lp_events
            raw_data = {"event_count": len(events)}
            
            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor("lp", new_cursor, "Last LP activity fetch")
            
        elif selected_action == "explore_metrics":
            # Fetch web metrics
            query = "base chain DEX metrics volume pools"
            metrics = web_metrics_lookup(query)
            
            # Save raw data
            raw_id = f"web_metrics_{int(datetime.now().timestamp())}"
            await save_json(raw_id, "web_metrics", metrics)
            
            # Convert metrics to event-like format for consistency
            events = [{
                "txHash": f"metrics_{int(datetime.now().timestamp())}",
                "logIndex": 0,
                "timestamp": int(datetime.now().timestamp()),
                "kind": "metrics",
                "pool": metrics.get("key_values", {}).get("top_pool", "unknown"),
                "amounts": metrics.get("key_values", {}),
                "chain": "base",
                "provenance": {
                    "source": "mock",
                    "snapshot": metrics.get("snapshot_time", int(datetime.now().timestamp())),
                    "query": query
                }
            }]
            
            raw_data = {"metrics": metrics}
            
            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor("explore_metrics", new_cursor, "Last metrics exploration")
        
        execution_time = time.time() - start_time
        print(f"    ✅ {selected_action} completed in {execution_time:.2f}s")
        print(f"    📊 Retrieved {len(events)} events")
        
        return {
            **state,
            "events": events,
            "raw_data": raw_data,
            "execution_time": execution_time,
            "status": "analyzing"
        }
        
    except Exception as e:
        print(f"    ❌ {selected_action} failed: {e}")
        return {
            **state,
            "events": [],
            "error": str(e),
            "status": "failed"
        }


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


async def memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Memory node that persists final artifacts and updates cursors.
    
    Stores brief text, derived metrics, and updates cursors for next run.
    """
    print("  💾 Memory: Persisting final artifacts...")
    start_time = time.time()
    
    # Store brief if it was emitted
    if "brief_text" in state:
        brief_id = f"brief_{int(datetime.now().timestamp())}"
        await save_json(brief_id, "briefs", {
            "text": state["brief_text"],
            "next_watchlist": state.get("next_watchlist", []),
            "timestamp": int(datetime.now().timestamp()),
            "signals": state.get("signals", {}),
            "event_counts": state.get("last24h_counts", {})
        })
        print(f"    ✅ Stored brief: {brief_id}")
    
    # Store derived metrics
    if "signals" in state:
        metrics_id = f"metrics_{int(datetime.now().timestamp())}"
        await save_json(metrics_id, "derived_metrics", {
            "signals": state["signals"],
            "event_counts": state.get("last24h_counts", {}),
            "top_pools": state.get("top_pools", []),
            "timestamp": int(datetime.now().timestamp())
        })
        print(f"    ✅ Stored metrics: {metrics_id}")
    
    # Update cursors in state for next run
    current_time = int(datetime.now().timestamp())
    cursors = state.get("cursors", {})
    
    # Update relevant cursors based on what was executed
    selected_action = state.get("selected_action")
    if selected_action == "wallet_recon":
        wallet = state.get("target_wallet")
        if wallet:
            cursors[f"wallet:{wallet}"] = current_time
    elif selected_action == "lp_recon":
        cursors["lp"] = current_time
    elif selected_action == "explore_metrics":
        cursors["explore_metrics"] = current_time
    
    print(f"    ✅ Updated cursors for next run")
    
    execution_time = time.time() - start_time
    print(f"    ✅ Memory completed in {execution_time:.2f}s")
    
    return {
        **state,
        "cursors": cursors,
        "status": "completed"
    }
