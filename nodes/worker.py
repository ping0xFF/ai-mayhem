"""
Worker node that executes the selected action via tool calls.
"""

import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, Any

from json_storage import get_cursor, set_cursor
from data_model import save_raw_response, NormalizedEvent
from mock_tools import fetch_wallet_activity, fetch_lp_activity, web_metrics_lookup
from real_apis.provider_router import get_wallet_provider
from .rich_output import formatter


def calculate_hours_back_from_cursor(cursor_timestamp: int) -> int:
    """
    Calculate hours_back based on cursor staleness.
    
    Args:
        cursor_timestamp: Last update timestamp from cursor (0 if no cursor)
        
    Returns:
        int: Hours to look back (1-168 hours)
    """
    if cursor_timestamp == 0:
        # First time - get 48 hours of data
        return 48
    
    # Calculate hours since last update
    current_time = datetime.now().timestamp()
    hours_since_update = (current_time - cursor_timestamp) / 3600
    
    # Add 1 hour buffer to ensure we don't miss any data
    hours_back = hours_since_update + 1
    
    # Bound between 1 hour and 1 week (168 hours)
    return min(max(int(hours_back), 1), 168)


def analyze_events_detailed(events, selected_action, target_wallet=None):
    """
    Analyze events and return detailed breakdown for logging.
    
    Args:
        events: List of events to analyze
        selected_action: The action being performed (wallet_recon, lp_recon, etc.)
        target_wallet: The target wallet address (for wallet_recon)
    
    Returns:
        str: Detailed breakdown string for logging
    """
    if not events:
        return "No events retrieved"
    
    current_time = int(datetime.now().timestamp())
    
    # Event type breakdown
    event_types = Counter()
    wallet_counts = Counter()
    timestamps = []
    
    for event in events:
        # Event type (handle both 'type' and 'kind' fields)
        event_type = event.get("type", event.get("kind", "unknown"))
        event_types[event_type] += 1
        
        # Wallet breakdown (for wallet_recon) - collect all wallets, not just target
        if selected_action == "wallet_recon":
            wallet_addr = event.get("wallet", event.get("address", "unknown"))
            if wallet_addr and wallet_addr != "unknown":
                wallet_counts[wallet_addr] += 1
        
        # Timestamp analysis
        timestamp = event.get("timestamp", current_time)
        if isinstance(timestamp, (int, float)):
            timestamps.append(timestamp)
    
    # Build detailed breakdown
    breakdown_parts = []
    
    # Total count
    breakdown_parts.append(f"Total: {len(events)} events")
    
    # Event types (top 5)
    if event_types:
        type_summary = ", ".join([f"{t}: {c}" for t, c in event_types.most_common(5)])
        breakdown_parts.append(f"Types: {type_summary}")
    
    # Wallet breakdown (if applicable)
    if wallet_counts and selected_action == "wallet_recon":
        wallet_summary = ", ".join([f"{w[:8]}...: {c}" for w, c in wallet_counts.items()])
        breakdown_parts.append(f"Wallets: {wallet_summary}")
    
    # Age analysis with better granularity for recent events
    if timestamps:
        oldest = min(timestamps)
        newest = max(timestamps)
        avg_age_seconds = current_time - (sum(timestamps) / len(timestamps))
        oldest_age_seconds = current_time - oldest
        newest_age_seconds = current_time - newest
        
        # Use appropriate units based on age
        def format_age(seconds):
            if seconds < 60:  # Less than 1 minute
                return f"{seconds:.0f}s"
            elif seconds < 3600:  # Less than 1 hour
                return f"{seconds/60:.0f}m"
            elif seconds < 86400:  # Less than 1 day
                return f"{seconds/3600:.1f}h"
            else:  # Days or more
                return f"{seconds/86400:.1f}d"
        
        breakdown_parts.append(f"Age: {format_age(avg_age_seconds)} avg (oldest: {format_age(oldest_age_seconds)}, newest: {format_age(newest_age_seconds)})")
    
    return " | ".join(breakdown_parts)


async def worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker node that executes the selected action via tool calls.
    
    Saves raw responses to JSON cache and returns normalized events.
    """
    selected_action = state.get("selected_action")
    
    if not selected_action:
        return {**state, "events": [], "status": "completed"}
    
    start_time = time.time()
    formatter.log_node_progress("Worker", f"Executing {selected_action}...")
    
    events = []
    raw_data = {}
    source_ids = []
    
    try:
        if selected_action == "wallet_recon":
            wallet = state.get("target_wallet")
            if not wallet:
                raise ValueError("No target wallet specified")

            # Get cursor for this wallet
            cursor_key = f"wallet:{wallet}"
            since_ts = state.get("cursors", {}).get(cursor_key, 0)
            
            # Calculate dynamic hours_back based on cursor staleness
            hours_back = calculate_hours_back_from_cursor(since_ts)
            
            # Log the calculated hours_back
            if since_ts == 0:
                formatter.log_node_progress("Worker", f"First run for {wallet}, fetching 48 hours")
            else:
                hours_since_update = (datetime.now().timestamp() - since_ts) / 3600
                formatter.log_node_progress("Worker", f"Last update {hours_since_update:.1f}h ago, fetching {hours_back}h")

            # Get provider router and log selected provider
            router = get_wallet_provider()
            selected_provider = router.get_selected_provider()
            formatter.log_node_progress("Worker", f"Using provider: {selected_provider}")

            # Fetch wallet activity using provider router
            response = await router.fetch_wallet_activity(
                address=wallet,
                chain="base",
                since_ts=since_ts,
                max_transactions=1000,
                hours_back=hours_back  # Dynamic calculation
            )

            # Determine provider and create appropriate raw_id
            provider_info = response.get("provider", {})
            if isinstance(provider_info, dict):
                provider_name = provider_info.get("name", "unknown")
                chain = provider_info.get("chain", "base")
            else:
                provider_name = provider_info if provider_info else "unknown"  # Legacy format
                chain = "base"

            raw_id = f"{provider_name}_wallet_{wallet}_{int(datetime.now().timestamp())}"

            # Save raw data to Layer 1 (raw-first approach)
            await save_raw_response(raw_id, "wallet_activity", response, provenance={
                "source": provider_name,
                "address": wallet,
                "chain": chain,
                "since_ts": since_ts,
                "snapshot_time": int(datetime.now().timestamp()),
                "provider": provider_name
            })

            # Extract events from response (keep raw structure)
            events = response.get("events", [])
            raw_data = {
                "wallet": wallet,
                "provider": provider_name,
                "event_count": len(events),
                "next_cursor": response.get("metadata", {}).get("next_page_key") or response.get("next_cursor")
            }
            source_ids.append(raw_id)

            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor(cursor_key, new_cursor, f"Last wallet activity fetch for {wallet}")
            
        elif selected_action == "lp_recon":
            # Get LP cursor
            since_ts = state.get("cursors", {}).get("lp", 0)
            
            # Fetch LP activity (use realistic fixtures for demo, simple for tests)
            use_realistic = state.get("use_realistic_fixtures", False)
            lp_events = fetch_lp_activity(since_ts, use_realistic=use_realistic)
            
            # Save raw data to Layer 1
            raw_id = f"lp_activity_{since_ts}"
            await save_raw_response(raw_id, "lp_activity", {
                "since_ts": since_ts,
                "events": lp_events,
                "timestamp": int(datetime.now().timestamp())
            }, provenance={
                "source": "mock_tools",
                "since_ts": since_ts,
                "snapshot_time": int(datetime.now().timestamp())
            })
            
            events = lp_events
            raw_data = {"event_count": len(events)}
            source_ids.append(raw_id)
            
            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor("lp", new_cursor, "Last LP activity fetch")
            
        elif selected_action == "explore_metrics":
            # Fetch web metrics
            query = "base chain DEX metrics volume pools"
            metrics = web_metrics_lookup(query)
            
            # Save raw data to Layer 1
            raw_id = f"web_metrics_{int(datetime.now().timestamp())}"
            await save_raw_response(raw_id, "web_metrics", metrics, provenance={
                "source": "mock_tools",
                "query": query,
                "snapshot_time": metrics.get("snapshot_time", int(datetime.now().timestamp()))
            })
            
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
            source_ids.append(raw_id)
            
            # Update cursor
            new_cursor = int(datetime.now().timestamp())
            await set_cursor("explore_metrics", new_cursor, "Last metrics exploration")
        
        execution_time = time.time() - start_time
        
        # Detailed event analysis
        event_breakdown = analyze_events_detailed(events, selected_action, state.get("target_wallet"))
        formatter.log_node_progress(
            "Worker",
            f"Retrieved {len(events)} events ({event_breakdown})",
            execution_time
        )
        
        return {
            **state,
            "events": events,
            "raw_data": raw_data,
            "source_ids": source_ids,
            "execution_time": execution_time,
            "status": "analyzing"
        }
        
    except Exception as e:
        formatter.log_node_progress("Worker", f"Failed: {str(e)}")
        return {
            **state,
            "events": [],
            "error": str(e),
            "status": "failed"
        }