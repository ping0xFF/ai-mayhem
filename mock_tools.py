#!/usr/bin/env python3
"""
Enhanced Mock Tools for Three-Layer Data Model.
Provides both simple and realistic fixtures for testing.
"""

import time
import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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


# Bitquery Wallet Activity Adapter (v1) with Live Toggle
def fetch_wallet_activity_bitquery(address: str, chain: str = "base", since_ts: int = 0) -> Dict[str, Any]:
    """
    Fetch wallet activity using Bitquery adapter.
    Supports both mock (default) and live modes via BITQUERY_LIVE environment variable.

    Args:
        address: Wallet address to fetch activity for
        chain: Blockchain chain (default: base)
        since_ts: Timestamp to fetch from (0 = all)

    Returns:
        Dict with standardized format containing events and metadata
    """
    # Check if live mode is enabled
    use_live = os.getenv("BITQUERY_LIVE", "0").lower() in ("1", "true", "yes")

    # Debug logging
    verbose = os.getenv("BITQUERY_VERBOSE", "0").lower() in ("1", "true", "yes")
    if verbose:
        print(f"    🔍 Bitquery fetch: address={address[:10]}..., chain={chain}, use_live={use_live}")

    if use_live:
        # Use live Bitquery API
        try:
            from real_apis.bitquery import fetch_wallet_activity_bitquery_live
            print("    🔴 Using LIVE Bitquery API")
            # Create a new event loop in a separate thread to avoid nested event loop issues
            import concurrent.futures

            def run_in_thread():
                """Run the async function in a new event loop."""
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(fetch_wallet_activity_bitquery_live(address, chain, since_ts))
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                result = future.result(timeout=120)  # 2 minute timeout for the entire operation
                return result

        except concurrent.futures.TimeoutError:
            print("    ❌ Live Bitquery timed out after 2 minutes, falling back to mock")
        except Exception as e:
            print(f"    ❌ Live Bitquery failed: {e}, falling back to mock")
            # Fall through to mock implementation

    # Use mock implementation (default)
    print("    🟡 Using MOCK Bitquery API (default)")
    return _fetch_wallet_activity_bitquery_mock(address, chain, since_ts)


def _fetch_wallet_activity_bitquery_mock(address: str, chain: str = "base", since_ts: int = 0) -> Dict[str, Any]:
    """
    Mock implementation of Bitquery wallet activity fetch.
    Used when BITQUERY_LIVE is not set or live API fails.
    """
    # Simulate network delay and API call
    time.sleep(0.15)

    # Generate deterministic mock events based on wallet address
    wallet_hash = hashlib.md5(address.encode()).hexdigest()
    wallet_seed = int(wallet_hash[:8], 16) % 1000

    mock_events = []
    current_ts = int(datetime.now().timestamp())
    base_ts = max(since_ts, current_ts - 86400)  # Last 24h if no since_ts

    # Generate 1-3 events per wallet for demo purposes
    num_events = (wallet_seed % 3) + 1

    for i in range(num_events):
        event_ts = base_ts + (i * 3600) + (wallet_seed % 3600)  # Spread over time
        event_type = ["lp_add", "lp_remove", "swap", "transfer"][wallet_seed % 4]

        event = {
            "ts": event_ts,
            "chain": chain,
            "type": event_type,
            "wallet": address,
            "tx": f"0x{hashlib.md5(f'{address}_{i}'.encode()).hexdigest()[:64]}",
            "raw": {
                "transaction": {
                    "hash": f"0x{hashlib.md5(f'{address}_{i}'.encode()).hexdigest()[:64]}",
                    "block": {
                        "timestamp": {"unixtime": event_ts},
                        "number": 1234567 + i
                    }
                },
                "log": {
                    "index": i,
                    "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"],
                    "data": f"0x{hashlib.md5(f'{address}_{event_type}_{i}'.encode()).hexdigest()}"
                }
            }
        }

        # Add pool for LP events
        if event_type in ["lp_add", "lp_remove"]:
            pool_address = f"0x{hashlib.md5(f'pool_{wallet_seed}_{i}'.encode()).hexdigest()[:40]}"
            event["pool"] = pool_address
            event["raw"]["pool"] = pool_address
            # Add USD value for LP events (nullable)
            event["usd"] = (wallet_seed + i * 100) * 1.5 if wallet_seed % 2 == 0 else None
        elif event_type == "swap":
            event["pool"] = f"0x{hashlib.md5(f'pool_{wallet_seed}_{i}'.encode()).hexdigest()[:40]}"
            event["usd"] = (wallet_seed + i * 50) * 2.0

        mock_events.append(event)

    return {
        "provider": "bitquery",
        "next_cursor": None,  # Bitquery uses timestamps, not cursors
        "events": mock_events,
        "metadata": {
            "address": address,
            "chain": chain,
            "since_ts": since_ts,
            "fetched_at": current_ts,
            "event_count": len(mock_events)
        }
    }


# Demo helper for wallet recon
def demo_wallet_recon_flow(wallet_address: str = "0x1234567890abcdef1234567890abcdef12345678") -> Dict[str, Any]:
    """
    Demo function showing the complete wallet recon flow.
    Returns the response structure for testing.
    """
    print(f"🔍 Wallet Recon Demo for {wallet_address}")
    print("=" * 60)

    # Step 1: Fetch wallet activity
    print("📡 Step 1: Fetching wallet activity via Bitquery adapter...")
    response = fetch_wallet_activity_bitquery(wallet_address, "base", 0)

    print(f"   ✅ Fetched {response['metadata']['event_count']} events")
    print(f"   📊 Events: {len(response['events'])}")
    for i, event in enumerate(response['events'][:3]):  # Show first 3
        print(f"      {i+1}. {event['type']} at {event['ts']} (pool: {event.get('pool', 'N/A')})")
    if len(response['events']) > 3:
        print(f"      ... and {len(response['events']) - 3} more")

    return response
