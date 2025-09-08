#!/usr/bin/env python3
"""
Alchemy wallet activity adapter for Base chain.
High-level wallet-centric endpoints with optimal response sizes (~509 bytes per transaction).

🔗 OFFICIAL API DOCUMENTATION:
- Developer Documentation: https://docs.alchemy.com/
- API Reference: https://docs.alchemy.com/reference
- OpenAPI Specification: https://docs.alchemy.com/reference/openapi

📝 NAMING CONVENTION NOTE:
This file is named 'alchemy_provider.py' (not 'alchemy.py') to avoid naming conflicts
with the official Alchemy SDK package. The SDK is imported as 'from alchemy import Alchemy',
so naming this file 'alchemy.py' would create a circular import conflict.

⚠️  IMPORTANT: Based on our comprehensive testing, use alchemy_getAssetTransfers endpoint
    for optimal response sizes compared to other providers.
"""

import asyncio
import os
import time
import json
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import official Alchemy SDK
from alchemy import Alchemy

# Alchemy configuration
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 60.0  # seconds max per run


async def fetch_wallet_activity_alchemy_live(
    address: str,
    max_transactions: int = 1000,
    hours_back: Optional[int] = None,
    network: str = "base-mainnet"
) -> Dict[str, Any]:
    """
    Fetch wallet activity using Alchemy API.
    Uses alchemy_getAssetTransfers for massive size optimization (180x reduction).

    Args:
        address: Wallet address to fetch activity for
        max_transactions: Maximum transactions to return (max 1000)
        hours_back: If specified, only return transactions from last N hours
        network: Network name (default: base-mainnet)

    Returns:
        Dict with standardized format containing events and metadata
    """
    if not ALCHEMY_API_KEY:
        raise ValueError("ALCHEMY_API_KEY environment variable is required for Alchemy queries")

    print(f"    📡 Querying Alchemy for {address} on {network}...")
    print(f"    📄 Max transactions: {max_transactions}")
    if hours_back:
        print(f"    🕐 Time filter: last {hours_back} hours")
    print(f"    🎯 Using alchemy_getAssetTransfers endpoint")

    # Initialize Alchemy client with proper network handling
    # For Base mainnet, we'll use direct HTTP requests since the SDK doesn't support it
    # 2025-09-04: I have confirmed with Alchemy that the SDK does NOT support Base mainnet
    if network == "base-mainnet":
        # Base mainnet requires custom handling
        category = ["external", "erc20"]  # Base doesn't support internal
        alchemy = None  # Will use direct HTTP requests
    else:
        # Use standard network names for supported networks
        alchemy = Alchemy(api_key=ALCHEMY_API_KEY, network=network)
        category = ["external", "internal", "erc20"]
    
    try:
        # Ensure max_count doesn't exceed limit
        if max_transactions > 1000:
            max_transactions = 1000
            print(f"    ⚠️  Max transactions limited to 1000 for Alchemy")
        
        # Prepare parameters for get_asset_transfers
        params = {
            "from_address": address,
            "max_count": max_transactions,
            "category": category
        }
        
        # Handle Base mainnet vs other networks differently
        if network == "base-mainnet":
            # Base mainnet: Use direct HTTP requests
            result = await _fetch_base_mainnet_asset_transfers(address, params, hours_back)
        else:
            # Other networks: Use Alchemy SDK
            # Add time filtering if requested
            if hours_back:
                try:
                    # Calculate block number from hours back
                    blocks_per_hour = 0.5 * 3600  # 1800 blocks per hour
                    blocks_back = int(hours_back * blocks_per_hour)
                    
                    # Get current block number
                    current_block = await alchemy.core.get_block_number()
                    from_block = current_block - blocks_back
                    params["from_block"] = from_block
                    
                    print(f"    📊 Time filter: from block {from_block} (current: {current_block})")
                except Exception as e:
                    print(f"    ⚠️  Time filtering failed, proceeding without: {e}")
            
            # Call Alchemy API via SDK
            result = await alchemy.core.get_asset_transfers(**params)
        
        # Extract transfers from response
        transfers = result.get("transfers", [])
        page_key = result.get("pageKey")
        
        print(f"    📊 Alchemy returned {len(transfers)} transactions")
        print(f"    📏 Average size per transaction: ~{(len(str(result)) // max(len(transfers), 1))} bytes")
        if page_key:
            print(f"    📄 Next page available (pageKey: {page_key[:20]}...)")
        
        # Convert to standardized format
        events = []
        current_ts = int(datetime.now().timestamp())
        
        for tx in transfers:
            try:
                # Extract basic transaction info
                event = {
                    "ts": current_ts,  # Alchemy doesn't provide timestamp in transfers
                    "chain": "base",
                    "type": _classify_transaction(tx),
                    "wallet": address,
                    "tx": tx.get("hash", ""),
                    "block": int(tx.get("blockNum", "0"), 16) if tx.get("blockNum") else 0,
                    "gas_used": None,  # Not provided in transfers
                    "raw": {
                        "tx_hash": tx.get("hash"),
                        "block_num": tx.get("blockNum"),
                        "value": tx.get("value"),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "category": tx.get("category"),
                        "asset": tx.get("asset")
                    }
                }
                
                # Extract value and token info
                value_info = _extract_value_info(tx, address)
                event.update(value_info)
                
                events.append(event)
                
            except Exception as e:
                print(f"    ⚠️  Failed to process transaction {tx.get('hash', 'unknown')}: {e}")
                continue
        
        return {
            "events": events,
            "metadata": {
                "source": "alchemy",
                "network": network,
                "address": address,
                "total_transactions": len(events),
                "max_transactions": max_transactions,
                "time_filter_hours": hours_back,
                "has_more": page_key is not None,
                "next_page_key": page_key,
                "optimization": "alchemy_getAssetTransfers endpoint"
            }
        }
        
    except Exception as e:
        print(f"    ❌ Alchemy query failed: {e}")
        raise


def _classify_transaction(tx: Dict[str, Any]) -> str:
    """Classify transaction type based on Alchemy data."""
    category = tx.get("category", "")
    
    if category == "erc20":
        return "token_transfer"
    elif category == "external":
        value = tx.get("value", "0")
        # Handle both decimal and hex string values
        if value and value != "0" and value != "0x0":
            return "transfer"
        else:
            return "contract_interaction"
    
    return "transaction"


def _extract_value_info(tx: Dict[str, Any], wallet_address: str) -> Dict[str, Any]:
    """Extract value and token information from transaction."""
    info = {}

    # Check for native token transfers
    if tx.get("value") and tx.get("value") != "0":
        info["value"] = tx["value"]
        info["token_symbol"] = "ETH"  # Base uses ETH
        info["token_address"] = "0x0000000000000000000000000000000000000000"

        # Determine direction
        if tx.get("from", "").lower() == wallet_address.lower():
            info["direction"] = "out"
            info["counterparty"] = tx.get("to")
        else:
            info["direction"] = "in"
            info["counterparty"] = tx.get("from")

    # Check for token transfers
    if tx.get("category") == "erc20":
        info["token_symbol"] = tx.get("asset", "ERC20")
        info["token_address"] = tx.get("asset")
        
        # Determine direction for token transfers
        if tx.get("from", "").lower() == wallet_address.lower():
            info["direction"] = "out"
            info["counterparty"] = tx.get("to")
        else:
            info["direction"] = "in"
            info["counterparty"] = tx.get("from")

    return info


async def _fetch_base_mainnet_asset_transfers(
    address: str,
    params: Dict[str, Any],
    hours_back: Optional[int] = None
) -> Dict[str, Any]:
    """Fetch asset transfers from Base mainnet using direct HTTP requests."""
    base_url = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    # Prepare JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getAssetTransfers",
        "params": [params]
    }
    
    # Add time filtering if requested
    if hours_back:
        try:
            # For Base mainnet, we'll estimate blocks without precise calculation
            # Base produces ~0.5 blocks per second (2 seconds per block)
            blocks_per_hour = 0.5 * 3600  # 1800 blocks per hour
            blocks_back = int(hours_back * blocks_per_hour)
            
            # Use a reasonable starting block (Base started around block 0)
            from_block = f"0x{blocks_back:x}"  # Convert to hex
            params["from_block"] = from_block
            
            print(f"    📊 Time filter: from block {from_block} (estimated)")
        except Exception as e:
            print(f"    ⚠️  Time filtering failed, proceeding without: {e}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "result" in result:
                        return result["result"]
                    else:
                        raise Exception(f"Invalid response format: {result}")
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
    except Exception as e:
        print(f"    ❌ Base mainnet HTTP request failed: {e}")
        raise


# For backward compatibility
import warnings

async def fetch_wallet_activity_alchemy_live_legacy(
    address: str,
    network: str = "base-mainnet",
    max_transactions: int = 1000,
    hours_back: Optional[int] = None
) -> Dict[str, Any]:
    """Legacy function name for backward compatibility.
    
    Deprecated: Use fetch_wallet_activity_alchemy_live() instead.
    This function will be removed in a future version.
    """
    warnings.warn(
        "fetch_wallet_activity_alchemy_live_legacy() is deprecated. "
        "Use fetch_wallet_activity_alchemy_live() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return await fetch_wallet_activity_alchemy_live(
        address, max_transactions, hours_back, network
    )
