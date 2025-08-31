"""
Planner node that selects the next action based on cursor staleness and budget.
"""

import time
from datetime import datetime
from typing import Dict, Any

from .config import (
    BUDGET_DAILY, 
    CURSOR_STALE_WALLET, 
    CURSOR_STALE_LP, 
    CURSOR_STALE_EXPLORE
)


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
