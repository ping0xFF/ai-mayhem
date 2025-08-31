"""
Memory node that persists final artifacts and updates cursors.
"""

import time
from datetime import datetime
from typing import Dict, Any

from json_storage import save_json
from data_model import get_data_model


async def memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Memory node that persists final artifacts and updates cursors.
    
    Stores brief text, derived metrics, and updates cursors for next run.
    """
    print("  💾 Memory: Persisting final artifacts...")
    start_time = time.time()
    
    # Store brief if it was emitted (already done in brief node via Layer 3)
    if "brief_text" in state:
        print(f"    ✅ Brief already persisted to Layer 3")
    
    # Store derived metrics (legacy, for backward compatibility)
    if "signals" in state:
        metrics_id = f"metrics_{int(datetime.now().timestamp())}"
        await save_json(metrics_id, "derived_metrics", {
            "signals": state["signals"],
            "event_counts": state.get("last24h_counts", {}),
            "top_pools": state.get("top_pools", []),
            "timestamp": int(datetime.now().timestamp())
        })
        print(f"    ✅ Stored legacy metrics: {metrics_id}")
    
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
