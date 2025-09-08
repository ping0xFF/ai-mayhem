"""
Worker node that executes the selected action via tool calls.
"""

import time
from datetime import datetime
from typing import Dict, Any

from json_storage import get_cursor, set_cursor
from data_model import save_raw_response, NormalizedEvent
from mock_tools import fetch_wallet_activity, fetch_lp_activity, web_metrics_lookup
from real_apis.provider_router import get_wallet_provider
from .rich_output import formatter


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
                hours_back=None
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
        formatter.log_node_progress(
            "Worker",
            f"Retrieved {len(events)} events",
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