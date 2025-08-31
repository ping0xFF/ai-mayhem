#!/usr/bin/env python3
"""
Mock tools for Planner/Worker implementation.
Provides deterministic mock data for testing and development.
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import mock fixtures from test file
from tests.test_planner_worker import MOCK_EVENTS, MOCK_WALLET_ACTIVITY, MOCK_LP_ACTIVITY, MOCK_WEB_METRICS


def fetch_wallet_activity(wallet: str, since_ts: int) -> List[Dict[str, Any]]:
    """
    Mock wallet activity fetch.
    
    Args:
        wallet: Wallet address to fetch activity for
        since_ts: Timestamp to fetch from
    
    Returns:
        List of normalized events for the wallet
    """
    # Simulate network delay
    time.sleep(0.1)
    
    # Filter events for the specific wallet and time range
    wallet_events = [
        event for event in MOCK_WALLET_ACTIVITY
        if event["timestamp"] >= since_ts
    ]
    
    # Add provenance
    for event in wallet_events:
        event["provenance"] = {
            "source": "mock",
            "snapshot": int(datetime.now().timestamp()),
            "wallet": wallet,
            "since_ts": since_ts
        }
    
    return wallet_events


def fetch_lp_activity(since_ts: int) -> List[Dict[str, Any]]:
    """
    Mock LP activity fetch.
    
    Args:
        since_ts: Timestamp to fetch from
    
    Returns:
        List of normalized LP events
    """
    # Simulate network delay
    time.sleep(0.2)
    
    # Filter events for the time range
    lp_events = [
        event for event in MOCK_LP_ACTIVITY
        if event["timestamp"] >= since_ts
    ]
    
    # Add provenance
    for event in lp_events:
        event["provenance"] = {
            "source": "mock",
            "snapshot": int(datetime.now().timestamp()),
            "since_ts": since_ts
        }
    
    return lp_events


def web_metrics_lookup(query: str) -> Dict[str, Any]:
    """
    Mock web metrics lookup.
    
    Args:
        query: Search query for metrics
    
    Returns:
        Dictionary with source, snapshot_time, key_values, raw_excerpt
    """
    # Simulate network delay
    time.sleep(0.15)
    
    # Return mock metrics with current timestamp
    metrics = MOCK_WEB_METRICS.copy()
    metrics["snapshot_time"] = int(datetime.now().timestamp())
    metrics["query"] = query
    
    return metrics


# Helper function to get deterministic event IDs
def get_event_id(event: Dict[str, Any]) -> str:
    """Generate deterministic ID for an event."""
    return f"{event['txHash']}:{event['logIndex']}"


# Helper function to filter events by time range
def filter_events_by_time(events: List[Dict[str, Any]], since_ts: int) -> List[Dict[str, Any]]:
    """Filter events by timestamp."""
    return [event for event in events if event["timestamp"] >= since_ts]
