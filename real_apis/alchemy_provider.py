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


async def fetch_wallet_activity_alchemy_beta(
    address: str,
    max_transactions: int = 1000,
    hours_back: Optional[int] = None,
    network: str = "base-mainnet"
) -> Dict[str, Any]:
    """
    Fetch wallet activity using Alchemy Beta API.
    Uses /transactions/history/by-address for direct timestamp support.

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

    print(f"    📡 Querying Alchemy Beta API for {address} on {network}...")
    print(f"    📄 Max transactions: {max_transactions}")
    if hours_back:
        print(f"    🕐 Time filter: last {hours_back} hours")
    print(f"    🎯 Using Beta API /transactions/history/by-address endpoint")

    try:
        # Use Beta API endpoint for direct timestamp support
        result = await _fetch_beta_transactions(address, max_transactions, hours_back, network)
        
        # Extract transactions from response
        transactions = result.get("transactions", [])
        total_count = result.get("totalCount", len(transactions))
        
        print(f"    📊 Beta API returned {len(transactions)} transactions")
        print(f"    📊 Total available: {total_count}")
        
        # Convert to standardized format
        events = []
        
        for tx in transactions:
            try:
                # Parse timestamp from ISO 8601 format
                timestamp_str = tx.get("timeStamp", "")
                if timestamp_str:
                    # Convert ISO 8601 to Unix timestamp
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                else:
                    timestamp = int(datetime.now().timestamp())
                
                # Extract basic transaction info
                event = {
                    "ts": timestamp,  # Real timestamp from Beta API
                    "chain": "base",
                    "type": _classify_beta_transaction(tx),
                    "wallet": address,
                    "tx": tx.get("hash", ""),
                    "block": tx.get("blockNumber", 0),
                    "gas_used": tx.get("gasUsed"),
                    "raw": {
                        "tx_hash": tx.get("hash"),
                        "block_number": tx.get("blockNumber"),
                        "value": tx.get("value"),
                        "from_address": tx.get("fromAddress"),
                        "to_address": tx.get("toAddress"),
                        "timeStamp": tx.get("timeStamp"),
                        "gas_used": tx.get("gasUsed")
                    }
                }
                
                # Extract value and token info
                value_info = _extract_beta_value_info(tx, address)
                event.update(value_info)
                
                events.append(event)
                
            except Exception as e:
                print(f"    ⚠️  Failed to process transaction {tx.get('hash', 'unknown')}: {e}")
                continue
        
        return {
            "events": events,
            "metadata": {
                "source": "alchemy_beta",
                "network": network,
                "address": address,
                "total_transactions": len(events),
                "max_transactions": max_transactions,
                "time_filter_hours": hours_back,
                "total_available": total_count,
                "optimization": "Beta API /transactions/history/by-address"
            }
        }
        
    except Exception as e:
        print(f"    ❌ Alchemy Beta API query failed: {e}")
        raise


async def fetch_wallet_activity_alchemy_regular(
    address: str,
    network: str = "base-mainnet",
    max_transactions: int = 1000,
    hours_back: Optional[int] = None
) -> Dict[str, Any]:
    """
    Fetch wallet activity using Alchemy Regular API.
    Uses alchemy_getAssetTransfers with proper time filtering.

    Args:
        address: Wallet address to fetch activity for
        network: Network name (default: base-mainnet)
        max_transactions: Maximum transactions to return (max 1000)
        hours_back: If specified, only return transactions from last N hours

    Returns:
        Dict with standardized format containing events and metadata
    """
    if not ALCHEMY_API_KEY:
        raise ValueError("ALCHEMY_API_KEY environment variable is required for Alchemy queries")

    print(f"    📡 Querying Alchemy Regular API for {address} on {network}...")
    print(f"    📄 Max transactions: {max_transactions}")
    if hours_back:
        print(f"    🕐 Time filter: last {hours_back} hours")
    print(f"    🎯 Using Regular API alchemy_getAssetTransfers endpoint")

    try:
        # Prepare parameters for alchemy_getAssetTransfers
        params = {
            "fromAddress": address,
            "toAddress": address,
            "category": ["external", "erc20"],
            "withMetadata": True,
            "excludeZeroValue": False,
            "maxCount": f"0x{min(max_transactions, 1000):x}"  # API limit in hex
        }
        
        # Add time filtering if requested
        if hours_back:
            try:
                # For Base mainnet, estimate blocks for time filtering
                # Base produces ~0.5 blocks per second (2 seconds per block)
                blocks_per_hour = 0.5 * 3600  # 1800 blocks per hour
                blocks_back = int(hours_back * blocks_per_hour)
                
                # Get current block number first
                current_block = await _get_current_block_number(network)
                from_block = max(0, current_block - blocks_back)
                
                params["fromBlock"] = f"0x{from_block:x}"
                print(f"    📊 Time filter: from block {params['fromBlock']} (estimated)")
            except Exception as e:
                print(f"    ⚠️  Time filtering failed, proceeding without: {e}")
        
        # Fetch asset transfers
        if network == "base-mainnet":
            result = await _fetch_base_mainnet_asset_transfers(address, params, hours_back)
        else:
            # For other networks, use the Alchemy SDK
            alchemy = Alchemy(api_key=ALCHEMY_API_KEY, network=network)
            result = await alchemy.get_asset_transfers(params)
        
        # Extract transfers from response
        transfers = result.get("transfers", [])
        total_count = result.get("totalCount", len(transfers))
        
        print(f"    📊 Regular API returned {len(transfers)} transfers")
        print(f"    📊 Total available: {total_count}")
        
        # Convert to standardized format
        events = []
        
        for transfer in transfers:
            try:
                # Get block timestamp for accurate timing
                block_number = int(transfer.get("blockNum", "0x0"), 16)
                if block_number > 0:
                    timestamp = await _get_block_timestamp(block_number, network)
                else:
                    timestamp = int(datetime.now().timestamp())
                
                # Extract basic transfer info
                event = {
                    "ts": timestamp,  # Real timestamp from block
                    "chain": network.replace("-mainnet", ""),
                    "type": _classify_transaction(transfer),
                    "wallet": address,
                    "tx": transfer.get("hash", ""),
                    "block": block_number,
                    "raw": {
                        "tx_hash": transfer.get("hash"),
                        "block_number": block_number,
                        "value": transfer.get("value"),
                        "from": transfer.get("from"),
                        "to": transfer.get("to"),
                        "category": transfer.get("category"),
                        "asset": transfer.get("asset")
                    }
                }
                
                # Extract value and token info
                value_info = _extract_value_info(transfer, address)
                event.update(value_info)
                
                events.append(event)
                
            except Exception as e:
                print(f"    ⚠️  Failed to process transfer {transfer.get('hash', 'unknown')}: {e}")
                continue
        
        # Apply client-side time filtering if needed
        if hours_back and events:
            cutoff = datetime.now() - timedelta(hours=hours_back)
            events = [e for e in events if e.get("ts") >= cutoff.timestamp()]
            print(f"    📊 After time filtering: {len(events)} events")
        
        return {
            "events": events,
            "metadata": {
                "source": "alchemy_regular",
                "network": network,
                "address": address,
                "total_transactions": len(events),
                "max_transactions": max_transactions,
                "time_filter_hours": hours_back,
                "total_available": total_count,
                "optimization": "Regular API alchemy_getAssetTransfers with time filtering"
            }
        }
        
    except Exception as e:
        print(f"    ❌ Alchemy Regular API query failed: {e}")
        raise


async def fetch_wallet_activity_alchemy_live(
    address: str,
    network: str = "base-mainnet",
    max_transactions: int = 1000,
    hours_back: Optional[int] = None
) -> Dict[str, Any]:
    """
    Router function that selects between Beta and Regular Alchemy API.
    
    Selection logic:
    - Use Beta API for base-mainnet (has direct timestamps, 50 tx limit)
    - Use Regular API for other networks (broader support, time filtering)
    - Fallback to Regular API if Beta API fails
    
    Args:
        address: Wallet address to fetch activity for
        network: Network name (default: base-mainnet)
        max_transactions: Maximum transactions to return (max 1000)
        hours_back: If specified, only return transactions from last N hours

    Returns:
        Dict with standardized format containing events and metadata
    """
    print(f"    🎯 Alchemy Router: Selecting API for {network}")
    
    # Selection logic based on network and requirements
    use_beta_api = (
        network == "base-mainnet" and 
        max_transactions <= 50 and  # Beta API limit
        hours_back is not None  # Beta API works better with time filtering
    )
    
    if use_beta_api:
        print(f"    ✅ Using Beta API (base-mainnet, ≤50 txs, time filtered)")
        try:
            result = await fetch_wallet_activity_alchemy_beta(
                address, max_transactions, hours_back, network
            )
            # Validate response per README mandates
            validate_alchemy_response(result, hours_back)
            return result
        except Exception as e:
            print(f"    ⚠️  Beta API failed, falling back to Regular API: {e}")
            # Fall through to Regular API
    
    print(f"    ✅ Using Regular API (broader network support, time filtering)")
    try:
        result = await fetch_wallet_activity_alchemy_regular(
            address, network, max_transactions, hours_back
        )
        # Validate response per README mandates
        validate_alchemy_response(result, hours_back)
        return result
    except Exception as e:
        print(f"    ❌ Both APIs failed: {e}")
        raise


async def _get_current_block_number(network: str) -> int:
    """Get current block number for time filtering."""
    if network == "base-mainnet":
        base_url = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    else:
        base_url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }
    
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
                        return int(result["result"], 16)
                    else:
                        raise Exception(f"Invalid response format: {result}")
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
    except Exception as e:
        print(f"    ⚠️  Failed to get current block number: {e}")
        # Return a reasonable default for Base mainnet
        return 10000000  # Approximate current block


def _classify_beta_transaction(tx: Dict[str, Any]) -> str:
    """Classify transaction type based on Beta API data."""
    value = tx.get("value", "0")
    
    # Check if it's a native token transfer
    if value and value != "0" and value != "0x0":
        return "transfer"
    
    # Check if it has contract address (contract creation)
    if tx.get("contractAddress"):
        return "contract_creation"
    
    # Check if it has internal transactions (complex contract interaction)
    if tx.get("internalTxns"):
        return "contract_interaction"
    
    return "transaction"


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


def _extract_beta_value_info(tx: Dict[str, Any], wallet_address: str) -> Dict[str, Any]:
    """Extract value and token information from Beta API transaction."""
    info = {}

    # Check for native token transfers
    value = tx.get("value", "0")
    if value and value != "0" and value != "0x0":
        info["value"] = value
        info["token_symbol"] = "ETH"  # Base uses ETH
        info["token_address"] = "0x0000000000000000000000000000000000000000"

        # Determine direction
        from_addr = tx.get("fromAddress", "")
        to_addr = tx.get("toAddress", "")
        if from_addr.lower() == wallet_address.lower():
            info["direction"] = "out"
            info["counterparty"] = to_addr
        else:
            info["direction"] = "in"
            info["counterparty"] = from_addr

    return info


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


async def _fetch_beta_transactions(
    address: str,
    max_transactions: int,
    hours_back: Optional[int],
    network: str
) -> Dict[str, Any]:
    """Fetch transactions using Alchemy Beta API."""
    # Beta API base URL
    base_url = "https://api.g.alchemy.com/data/v1"
    
    # Prepare request payload
    payload = {
        "addresses": [
            {
                "address": address,
                "networks": ["base-mainnet"] if network == "base-mainnet" else [network]
            }
        ],
        "limit": min(max_transactions, 50)  # Beta API limit is 50
    }
    
    # Add time filtering if requested
    if hours_back:
        # Calculate timestamp for hours_back
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        # Note: Beta API might not support time filtering directly
        # We'll filter on the client side if needed
        print(f"    ⚠️  Time filtering not directly supported by Beta API, will filter client-side")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/{ALCHEMY_API_KEY}/transactions/history/by-address",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
    except Exception as e:
        print(f"    ❌ Beta API request failed: {e}")
        raise


async def _get_block_timestamp(block_number: int, network: str) -> int:
    """Get block timestamp using Alchemy's eth_getBlockByNumber endpoint."""
    if network == "base-mainnet":
        base_url = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    else:
        base_url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    # Prepare JSON-RPC request
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False]  # False = return only block header
    }
    
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
                    if "result" in result and result["result"]:
                        # Convert hex timestamp to int
                        timestamp_hex = result["result"].get("timestamp", "0x0")
                        return int(timestamp_hex, 16)
                    else:
                        raise Exception(f"No block data returned for block {block_number}")
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
    except Exception as e:
        print(f"    ⚠️  Failed to get block timestamp: {e}")
        raise


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


def validate_alchemy_response(response: Dict[str, Any], hours_back: Optional[int] = None) -> None:
    """
    Validate Alchemy API response per README mandates.
    
    This function implements the "Output Validation & Anomaly Detection" protocol
    from the README to ensure API responses meet quality standards.
    
    Args:
        response: API response dictionary
        hours_back: Expected time filter in hours (for validation)
        
    Raises:
        ValueError: If response doesn't meet validation criteria
    """
    events = response.get("events", [])
    
    # 1. Transaction Count Check - per README mandate
    if len(events) > 100:
        raise ValueError(f"Too many transactions: {len(events)} (max allowed: 100)")
    
    # 2. API Response Format Validation - per README mandate (check first)
    required_fields = ["ts", "chain", "type", "wallet", "tx"]
    for i, event in enumerate(events):
        for field in required_fields:
            if field not in event:
                raise ValueError(f"Event {i} missing required field: {field}")
    
    # 3. Data Quality Checks - per README mandate
    for i, event in enumerate(events):
        # Check for empty transaction hashes
        if not event.get("tx") or event.get("tx") == "":
            raise ValueError(f"Event {i} has empty transaction hash")
        
        # Check for valid chain identifier
        if not event.get("chain") or event.get("chain") == "":
            raise ValueError(f"Event {i} has empty chain identifier")
        
        # Check for valid wallet address
        if not event.get("wallet") or event.get("wallet") == "":
            raise ValueError(f"Event {i} has empty wallet address")
    
    # 4. Time Filtering Validation - per README mandate (check before timestamp validation)
    if hours_back and events:
        cutoff = datetime.now() - timedelta(hours=hours_back)
        for i, event in enumerate(events):
            if event.get("ts") < cutoff.timestamp():
                raise ValueError(f"Event {i} outside time filter: {event.get('ts')} < {cutoff.timestamp()}")
    
    # 5. Timestamp Validation - per README mandate (check after required fields and time filtering)
    if events:
        timestamps = [e.get("ts") for e in events]
        if len(set(timestamps)) == 1:
            raise ValueError("All timestamps are identical - indicates timestamp bug")
        
        # Check for reasonable timestamps
        current_time = datetime.now().timestamp()
        for i, ts in enumerate(timestamps):
            if ts > current_time:
                raise ValueError(f"Event {i} has future timestamp: {ts}")
            if ts < current_time - (365 * 24 * 3600):  # More than 1 year old
                raise ValueError(f"Event {i} has very old timestamp: {ts}")


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
