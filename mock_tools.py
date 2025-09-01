#!/usr/bin/env python3
"""
Enhanced Mock Tools for Three-Layer Data Model.
Provides both simple and realistic fixtures for testing.
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import existing mock fixtures
from tests.test_planner_worker import MOCK_EVENTS, MOCK_WALLET_ACTIVITY, MOCK_LP_ACTIVITY, MOCK_WEB_METRICS

# Simple LP fixtures (for testing)
SIMPLE_LP_FIXTURES = [
    {
        "txHash": "0xsimple_lp_1",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=2)).timestamp()),
        "kind": "lp_add",
        "wallet": "0xwallet_1",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 1.0, "USDC": 2000.0},
        "chain": "base",
        "details": {
            "token0": "WETH",
            "token1": "USDC", 
            "amount0": 1.0,
            "amount1": 2000.0,
            "lp_tokens_delta": 100.0,
            "pool_address": "0xsimple_pool_1"
        }
    },
    {
        "txHash": "0xsimple_lp_2", 
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=4)).timestamp()),
        "kind": "lp_remove",
        "wallet": "0xwallet_2",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 0.5, "USDC": 1000.0},
        "chain": "base",
        "details": {
            "token0": "WETH",
            "token1": "USDC",
            "amount0": 0.5,
            "amount1": 1000.0,
            "lp_tokens_delta": -50.0,
            "pool_address": "0xsimple_pool_1"
        }
    },
    {
        "txHash": "0xsimple_lp_3",
        "logIndex": 0, 
        "timestamp": int((datetime.now() - timedelta(hours=6)).timestamp()),
        "kind": "lp_add",
        "wallet": "0xwallet_3",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 5000.0, "WETH": 0.4},
        "chain": "base",
        "details": {
            "token0": "DEGEN",
            "token1": "WETH",
            "amount0": 5000.0,
            "amount1": 0.4,
            "lp_tokens_delta": 200.0,
            "pool_address": "0xsimple_pool_2"
        }
    }
]

# Realistic LP fixtures (for demo)
REALISTIC_LP_FIXTURES = [
    {
        "txHash": "0xrealistic_lp_1",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=1)).timestamp()),
        "kind": "lp_add",
        "wallet": "0xrealistic_wallet_1",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 5.0, "USDC": 10000.0},
        "chain": "base",
        "details": {
            "token0": "WETH",
            "token1": "USDC",
            "amount0": 5.0,
            "amount1": 10000.0,
            "lp_tokens_delta": 500.0,
            "pool_address": "0x420DD381b31aEf6683db6B902084cB0FFECe40Da",
            "price_reference": {"WETH": 2000.0, "USDC": 1.0},
            "tvl_at_block": 5000000.0
        }
    },
    {
        "txHash": "0xrealistic_lp_2",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=2)).timestamp()),
        "kind": "lp_remove", 
        "wallet": "0xrealistic_wallet_2",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 2.0, "USDC": 4000.0},
        "chain": "base",
        "details": {
            "token0": "WETH",
            "token1": "USDC",
            "amount0": 2.0,
            "amount1": 4000.0,
            "lp_tokens_delta": -200.0,
            "pool_address": "0x420DD381b31aEf6683db6B902084cB0FFECe40Da",
            "price_reference": {"WETH": 2000.0, "USDC": 1.0},
            "tvl_at_block": 4800000.0
        }
    },
    {
        "txHash": "0xrealistic_lp_3",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=3)).timestamp()),
        "kind": "lp_add",
        "wallet": "0xrealistic_wallet_3",
        "pool": "DEGEN/WETH", 
        "amounts": {"DEGEN": 25000.0, "WETH": 2.0},
        "chain": "base",
        "details": {
            "token0": "DEGEN",
            "token1": "WETH",
            "amount0": 25000.0,
            "amount1": 2.0,
            "lp_tokens_delta": 1000.0,
            "pool_address": "0x1234567890abcdef1234567890abcdef12345678",
            "price_reference": {"DEGEN": 0.00008, "WETH": 2000.0},
            "tvl_at_block": 1000000.0
        }
    },
    {
        "txHash": "0xrealistic_lp_4",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=4)).timestamp()),
        "kind": "lp_add",
        "wallet": "0xrealistic_wallet_4",
        "pool": "WETH/USDC",
        "amounts": {"WETH": 10.0, "USDC": 20000.0},
        "chain": "base",
        "details": {
            "token0": "WETH",
            "token1": "USDC",
            "amount0": 10.0,
            "amount1": 20000.0,
            "lp_tokens_delta": 1000.0,
            "pool_address": "0x420DD381b31aEf6683db6B902084cB0FFECe40Da",
            "price_reference": {"WETH": 2000.0, "USDC": 1.0},
            "tvl_at_block": 5200000.0
        }
    },
    {
        "txHash": "0xrealistic_lp_5",
        "logIndex": 0,
        "timestamp": int((datetime.now() - timedelta(hours=5)).timestamp()),
        "kind": "lp_remove",
        "wallet": "0xrealistic_wallet_5",
        "pool": "DEGEN/WETH",
        "amounts": {"DEGEN": 10000.0, "WETH": 0.8},
        "chain": "base",
        "details": {
            "token0": "DEGEN",
            "token1": "WETH", 
            "amount0": 10000.0,
            "amount1": 0.8,
            "lp_tokens_delta": -400.0,
            "pool_address": "0x1234567890abcdef1234567890abcdef12345678",
            "price_reference": {"DEGEN": 0.00008, "WETH": 2000.0},
            "tvl_at_block": 800000.0
        }
    }
]


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


def fetch_lp_activity(since_ts: int, use_realistic: bool = False) -> List[Dict[str, Any]]:
    """
    Mock LP activity fetch with enhanced fixtures.
    
    Args:
        since_ts: Timestamp to fetch from
        use_realistic: Use realistic fixtures instead of simple ones
    
    Returns:
        List of normalized LP events
    """
    # Simulate network delay
    time.sleep(0.2)
    
    # Choose fixture set
    fixtures = REALISTIC_LP_FIXTURES if use_realistic else SIMPLE_LP_FIXTURES
    
    # Filter events for the time range
    lp_events = [
        event for event in fixtures
        if event["timestamp"] >= since_ts
    ]
    
    # Add provenance
    for event in lp_events:
        event["provenance"] = {
            "source": "mock_lp",
            "snapshot": int(datetime.now().timestamp()),
            "since_ts": since_ts,
            "fixture_type": "realistic" if use_realistic else "simple"
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
