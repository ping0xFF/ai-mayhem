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
    CURSOR_STALE_EXPLORE,
    load_monitored_wallets
)
from json_storage import get_cursor, set_cursor
from .rich_output import formatter


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planner node that selects the next action based on cursor staleness and budget.
    
    Rules:
    - If wallet cursor stale (>2h): choose wallet_recon
    - Else if LP cursor stale (>6h): choose lp_recon  
    - Else: explore_metrics once per day (cooldown)
    - Hard stop if budget gate failed
    """
    start_time = time.time()
    
    # Check budget first
    spent = state.get("spent_today", 0.0)
    if spent >= BUDGET_DAILY:
        execution_time = time.time() - start_time
        formatter.log_node_progress(
            "Planner",
            f"Budget exceeded: ${spent:.2f}/${BUDGET_DAILY:.2f}",
            execution_time
        )
        return {**state, "status": "capped"}
    
    # Get current cursors and merge with database cursors
    cursors = state.get("cursors", {})
    current_time = int(datetime.now().timestamp())

    # Load existing cursors from database
    monitored_wallets = load_monitored_wallets()
    for wallet in monitored_wallets:
        cursor_key = f"wallet:{wallet}"
        if cursor_key not in cursors:
            db_cursor = await get_cursor(cursor_key)
            if db_cursor is not None:
                cursors[cursor_key] = db_cursor

    # Also load other cursors from database
    for cursor_name in ["lp", "explore_metrics"]:
        if cursor_name not in cursors:
            db_cursor = await get_cursor(cursor_name)
            if db_cursor is not None:
                cursors[cursor_name] = db_cursor

    # Seed wallet cursors if none exist (either in state or database)
    wallet_cursors = {k: v for k, v in cursors.items() if k.startswith("wallet:")}
    if not wallet_cursors and monitored_wallets:
        formatter.log_node_progress(
            "Planner",
            f"Seeding {len(monitored_wallets)} monitored wallets..."
        )
        for wallet in monitored_wallets:
            cursor_key = f"wallet:{wallet}"
            # Create cursor if it doesn't exist (set to 0 to force immediate update)
            if cursor_key not in cursors:
                await set_cursor(cursor_key, 0, f"Seeded cursor for monitored wallet {wallet}")
                cursors[cursor_key] = 0
                formatter.log_node_progress(
                    "Planner",
                    f"Seeded cursor for {wallet}"
                )
    elif not monitored_wallets:
        formatter.log_node_progress(
            "Planner",
            "No monitored wallets configured - skipping wallet recon"
        )

    # Check wallet cursors (stale if >2h)
    for cursor_key, cursor_ts in cursors.items():
        if cursor_key.startswith("wallet:") and cursor_ts is not None:
            wallet = cursor_key.split(":", 1)[1]
            if current_time - cursor_ts > CURSOR_STALE_WALLET:
                execution_time = time.time() - start_time
                formatter.log_node_progress(
                    "Planner",
                    f"Selected wallet_recon (cursor stale >2h for {wallet})",
                    execution_time
                )
                return {
                    **state,
                    "cursors": cursors,
                    "selected_action": "wallet_recon",
                    "target_wallet": wallet,
                    "status": "working"
                }
    
    # Check LP cursor (stale if >6h)
    lp_cursor = cursors.get("lp", 0)
    if current_time - lp_cursor > CURSOR_STALE_LP:
        execution_time = time.time() - start_time
        formatter.log_node_progress(
            "Planner",
            "Selected lp_recon (cursor stale >6h)",
            execution_time
        )
        return {
            **state,
            "cursors": cursors,
            "selected_action": "lp_recon",
            "status": "working"
        }
    
    # Check explore_metrics cursor (stale if >24h)
    explore_cursor = cursors.get("explore_metrics", 0)
    if current_time - explore_cursor > CURSOR_STALE_EXPLORE:
        execution_time = time.time() - start_time
        formatter.log_node_progress(
            "Planner",
            "Selected explore_metrics (cursor stale >24h)",
            execution_time
        )
        return {
            **state,
            "cursors": cursors,
            "selected_action": "explore_metrics",
            "status": "working"
        }
    
    # All cursors fresh - no action needed
    execution_time = time.time() - start_time
    formatter.log_node_progress(
        "Planner",
        "All cursors fresh - no action needed",
        execution_time
    )
    return {**state, "cursors": cursors, "status": "completed"}