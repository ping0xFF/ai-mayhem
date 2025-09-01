#!/usr/bin/env python3
"""
Covalent wallet activity adapter for Base chain.
High-level wallet-centric endpoints with decent pagination support.
"""

import asyncio
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Covalent configuration
COVALENT_BASE_URL = "https://api.covalenthq.com/v1"
COVALENT_API_KEY = os.getenv("COVALENT_API_KEY")
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 60.0  # seconds max per run


class CovalentClient:
    """Covalent API client for wallet activity."""

    def __init__(self, api_key: str = None, timeout: int = REQUEST_TIMEOUT):
        self.api_key = api_key or COVALENT_API_KEY
        if not self.api_key:
            raise ValueError("COVALENT_API_KEY environment variable is required")

        self.base_url = COVALENT_BASE_URL
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()

    async def _execute_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Covalent API request with retry logic."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        last_error = None
        url = f"{self.base_url}{endpoint}"

        # Add API key to params
        params["key"] = self.api_key

        for attempt in range(MAX_RETRIES):
            try:
                # Add jittered delay for rate limiting
                if attempt > 0:
                    delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                    await asyncio.sleep(delay)

                print(f"    📡 Making Covalent request to {endpoint}...")
                response = await self.session.get(url, params=params)
                print(f"    📡 Response status: {response.status_code}")

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", str(BASE_DELAY * (2 ** attempt)))
                    try:
                        delay = min(float(retry_after), MAX_DELAY)
                    except ValueError:
                        delay = BASE_DELAY * (2 ** attempt)
                    print(f"    ⚠️  Rate limited, waiting {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue

                # Handle other errors
                if response.status_code == 401:
                    raise Exception("Invalid Covalent API key")
                elif response.status_code == 402:
                    raise Exception("Covalent billing/credits exhausted")
                elif response.status_code == 404:
                    raise Exception("Covalent endpoint or data not found")

                response.raise_for_status()
                result = response.json()

                # Check for Covalent-specific error responses
                if result.get("error_code"):
                    error_msg = result.get("error_message", "Unknown Covalent error")
                    raise Exception(f"Covalent API error: {error_msg}")

                return result

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    print(f"    ⚠️  Attempt {attempt + 1} failed: {e}")
                    continue
                else:
                    print(f"    ❌ All {MAX_RETRIES} attempts failed")
                    break

        raise last_error or Exception("Failed to execute request after all retries")


async def fetch_wallet_activity_covalent(
    address: str,
    chain_id: str = "8453",  # Base chain
    cursor: str = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch wallet activity using Covalent API.
    High-level wallet-centric endpoints with pagination support.

    Args:
        address: Wallet address to fetch activity for
        chain_id: Chain ID (default: 8453 for Base)
        cursor: Pagination cursor (None for first page)
        limit: Number of transactions per page (max 100)

    Returns:
        Dict with standardized format containing events and metadata
    """
    if not COVALENT_API_KEY:
        raise ValueError("COVALENT_API_KEY environment variable is required for Covalent queries")

    print(f"    📡 Querying Covalent for {address} on chain {chain_id}...")
    print(f"    🔍 Limit: {limit}, Cursor: {cursor or 'None'}")

    async with CovalentClient() as client:
        # Get transaction history for the wallet
        endpoint = f"/{chain_id}/address/{address}/transactions_v3/"
        params = {
            "limit": min(limit, 100),  # Covalent max is 100
        }

        if cursor:
            params["cursor"] = cursor

        try:
            result = await client._execute_request(endpoint, params)

            # Extract transactions
            data = result.get("data", {})
            transactions = data.get("items", [])
            next_cursor = data.get("pagination", {}).get("next_cursor")

            print(f"    📊 Covalent returned {len(transactions)} transactions")
            if next_cursor:
                print(f"    📄 Next cursor: {next_cursor[:20]}...")

            # Convert to standardized format
            events = []
            current_ts = int(datetime.now().timestamp())

            for tx in transactions:
                try:
                    # Extract basic transaction info
                    event = {
                        "ts": tx.get("block_signed_at_unix", 0),
                        "chain": "base",
                        "type": _classify_transaction(tx),
                        "wallet": address,
                        "tx": tx.get("tx_hash", ""),
                        "block": tx.get("block_height", 0),
                        "gas_used": tx.get("gas_spent", 0),
                        "raw": {
                            "covalent_tx": tx,
                            "block": {
                                "height": tx.get("block_height"),
                                "signed_at": tx.get("block_signed_at"),
                                "signed_at_unix": tx.get("block_signed_at_unix")
                            }
                        }
                    }

                    # Extract value and token info
                    value_info = _extract_value_info(tx, address)
                    event.update(value_info)

                    # Add provenance (matching other adapters)
                    event["provenance"] = {
                        "source": "covalent",
                        "snapshot": current_ts,
                        "wallet": address,
                        "chain": chain_id
                    }

                    events.append(event)

                except Exception as e:
                    print(f"    ⚠️  Skipping malformed transaction {tx.get('tx_hash', 'unknown')}: {e}")
                    continue

            return {
                "provider": {
                    "name": "covalent",
                    "chain": chain_id,
                    "endpoint": f"/{chain_id}/address/{address}/transactions_v3/",
                    "cursor": next_cursor
                },
                "events": events,
                "raw": result,
                "metadata": {
                    "address": address,
                    "chain_id": chain_id,
                    "fetched_at": current_ts,
                    "transaction_count": len(events),
                    "next_cursor": next_cursor,
                    "has_more": next_cursor is not None
                }
            }

        except Exception as e:
            print(f"    ❌ Covalent query failed: {e}")
            raise


def _classify_transaction(tx: Dict[str, Any]) -> str:
    """Classify transaction type based on Covalent data."""
    # Check for DEX-related logs
    log_events = tx.get("log_events", [])

    for log in log_events:
        # Look for common DEX patterns
        if "decoded" in log:
            decoded = log.get("decoded", {})
            if decoded.get("name") in ["Swap", "AddLiquidity", "RemoveLiquidity"]:
                return "swap"  # Broad category for DEX activity

    # Check transaction value
    if tx.get("value") and tx.get("value") != "0":
        return "transfer"

    # Default classification
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
        if tx.get("from_address", "").lower() == wallet_address.lower():
            info["direction"] = "out"
            info["counterparty"] = tx.get("to_address")
        else:
            info["direction"] = "in"
            info["counterparty"] = tx.get("from_address")

    # Check for token transfers in logs
    log_events = tx.get("log_events", [])
    for log in log_events:
        if log.get("decoded", {}).get("name") == "Transfer":
            decoded = log.get("decoded", {})
            params = decoded.get("params", [])

            # Find token transfer details
            for param in params:
                if param.get("name") == "value":
                    info["value"] = param.get("value")
                elif param.get("name") == "from" and param.get("value", "").lower() == wallet_address.lower():
                    info["direction"] = "out"
                elif param.get("name") == "to" and param.get("value", "").lower() == wallet_address.lower():
                    info["direction"] = "in"
                elif param.get("name") == "to" and info.get("direction") == "out":
                    info["counterparty"] = param.get("value")
                elif param.get("name") == "from" and info.get("direction") == "in":
                    info["counterparty"] = param.get("value")

            # Add token info
            if "value" in info:
                info["token_symbol"] = log.get("sender_name", "ERC20")
                info["token_address"] = log.get("sender_address")

    return info


# For backward compatibility
async def fetch_wallet_activity_covalent_live(
    address: str,
    chain_id: str = "8453",
    cursor: str = None,
    limit: int = 100
) -> Dict[str, Any]:
    """Alias for the main function."""
    return await fetch_wallet_activity_covalent(address, chain_id, cursor, limit)


# Import random for jitter
import random
