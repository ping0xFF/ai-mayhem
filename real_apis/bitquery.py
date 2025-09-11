#!/usr/bin/env python3
"""
Live Bitquery GraphQL client for wallet activity fetching.
Raw-first approach with minimal processing and full provenance preservation.
"""

import asyncio
import os
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bitquery configuration
BITQUERY_ENDPOINT = "https://streaming.bitquery.io/graphql"
BITQUERY_ACCESS_TOKEN = os.getenv("BITQUERY_ACCESS_TOKEN") or os.getenv("BITQUERY_API_KEY")  # Support both naming conventions

# Token status will be checked in BitqueryClient.__init__
REQUEST_TIMEOUT = 60  # seconds - increased for GraphQL queries
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 60.0  # seconds max per run


class BitqueryClient:
    """Live Bitquery GraphQL client for wallet activity."""

    def __init__(self, access_token: str = None, timeout: int = REQUEST_TIMEOUT):
        """Initialize Bitquery client with access token and timeout."""
        # First try explicit access token
        if access_token:
            self.access_token = access_token
            print(f"    ✅ Using Bitquery access token: {access_token[:10]}... (length: {len(access_token)})")
        # Then try environment BITQUERY_ACCESS_TOKEN
        elif os.getenv("BITQUERY_ACCESS_TOKEN"):
            self.access_token = os.getenv("BITQUERY_ACCESS_TOKEN")
            print(f"    ✅ Using Bitquery access token: {self.access_token[:10]}... (length: {len(self.access_token)})")
        # Finally try environment BITQUERY_API_KEY
        elif os.getenv("BITQUERY_API_KEY"):
            self.access_token = os.getenv("BITQUERY_API_KEY")
            print(f"    ✅ Using Bitquery API key: {self.access_token[:10]}... (length: {len(self.access_token)})")
        # No token found
        else:
            self.access_token = None
            print("    ❌ No Bitquery access token found. Set BITQUERY_ACCESS_TOKEN in .env")
            raise ValueError("BITQUERY_ACCESS_TOKEN environment variable is required (or BITQUERY_API_KEY for backward compatibility)")


        self.endpoint = BITQUERY_ENDPOINT
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        # Try both authorization methods
        headers = {"Content-Type": "application/json"}

        # Check token format - if it looks like a UUID, try X-API-KEY header
        if len(self.access_token) == 36 and self.access_token.count('-') == 4:
            print("    🔑 Token looks like API key, trying X-API-KEY header")
            headers["X-API-KEY"] = self.access_token
        else:
            print("    🔑 Token looks like access token, trying Bearer header")
            headers["Authorization"] = f"Bearer {self.access_token}"

        self.session = httpx.AsyncClient(
            timeout=self.timeout,
            headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()

    async def _execute_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query with retry logic."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                # Add jittered delay for rate limiting
                if attempt > 0:
                    delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                    await asyncio.sleep(delay)

                print(f"    📡 Making GraphQL request to {self.endpoint}...")
                response = await self.session.post(
                    self.endpoint,
                    json={"query": query, "variables": variables}
                )
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

                # Handle billing issues
                if response.status_code == 402:
                    print("    💳 402 Payment Required - Please set up billing with Bitquery")
                    print("    🔗 Visit: https://streaming.bitquery.io/ to manage your billing")
                    raise Exception("Bitquery billing not set up. Please configure payment method.")

                # Handle other auth issues
                if response.status_code == 401:
                    print("    ❌ 401 Unauthorized - Invalid API key")
                    print("    💡 Check your BITQUERY_API_KEY in .env file")
                    raise Exception("Invalid API key. Please check your Bitquery credentials.")

                response.raise_for_status()
                result = response.json()

                # Check for GraphQL errors
                if "errors" in result:
                    error_msg = "; ".join([err.get("message", "Unknown error") for err in result["errors"]])
                    raise Exception(f"GraphQL errors: {error_msg}")

                return result

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    print(f"    ⚠️  Attempt {attempt + 1} failed: {e}")
                    continue
                else:
                    print(f"    ❌ All {MAX_RETRIES} attempts failed")
                    break

        raise last_error or Exception("Failed to execute query after all retries")


# GraphQL queries
WALLET_ACTIVITY_QUERY = """
query GetWalletActivity(
    $address: String!,
    $chain: String!,
    $since: DateTime,
    $limit: Int = 100,
    $offset: Int = 0
) {
    ethereum(network: $chain) {
        transfers(
            sender: {is: $address}
            receiver: {is: $address}
            date: {since: $since}
            options: {limit: $limit, offset: $offset}
        ) {
            block {
                timestamp {
                    time(format: "%Y-%m-%d %H:%M:%S")
                    unixtime
                }
                number
                hash
            }
            transaction {
                hash
                index
                gas_price
                gas_value
            }
            sender {
                address
                annotation
            }
            receiver {
                address
                annotation
            }
            amount
            currency {
                symbol
                address
                decimals
            }
            external
            log_index
            success
        }
        dexTrades(
            baseCurrency: {is: "0x0000000000000000000000000000000000000000"}
            quoteCurrency: {is: "0x0000000000000000000000000000000000000000"}
            options: {limit: $limit, offset: $offset}
            date: {since: $since}
            any: [
                {buyCurrency: {is: $address}},
                {sellCurrency: {is: $address}},
                {trader: {is: $address}}
            ]
        ) {
            block {
                timestamp {
                    time(format: "%Y-%m-%d %H:%M:%S")
                    unixtime
                }
                number
                hash
            }
            transaction {
                hash
                index
            }
            trader {
                address
            }
            exchange {
                fullName
            }
            smartContract {
                address
                contractType
                protocolType
            }
            baseCurrency {
                symbol
                address
                decimals
            }
            quoteCurrency {
                symbol
                address
                decimals
            }
            side
            tradeIndex
            buyAmount
            sellAmount
            price
            buyAmountInUsd: buyAmount(in: USD)
            sellAmountInUsd: sellAmount(in: USD)
            transaction {
                gasPrice
                gasValue
            }
            logIndex
        }
    }
}
"""


async def fetch_wallet_activity_bitquery_live(
    address: str,
    chain: str = "base",
    since_ts: int = None
) -> Dict[str, Any]:
    """
    Fetch wallet activity using live Bitquery GraphQL API.
    Raw-first approach: minimal processing, preserve original structure.

    Args:
        address: Wallet address to fetch activity for
        chain: Blockchain network (default: base)
        since_ts: Timestamp to fetch from (None = last 24h)

    Returns:
        Dict with standardized format containing events and metadata
    """
    if not BITQUERY_ACCESS_TOKEN:
        raise ValueError("BITQUERY_ACCESS_TOKEN environment variable is required for live queries (or BITQUERY_API_KEY for backward compatibility)")

    # Default to last 24 hours if no timestamp provided
    if since_ts is None:
        since_ts = int((datetime.now() - timedelta(hours=24)).timestamp())

    since_datetime = datetime.fromtimestamp(since_ts).isoformat()

    print(f"    📡 Querying Bitquery for {address} since {since_datetime}...")
    print(f"    🔍 Chain: {chain}, Limit per page: 100")

    all_transfers = []
    all_trades = []
    offset = 0
    limit = 100
    page_count = 0

    async with BitqueryClient() as client:
        while True:
            variables = {
                "address": address,
                "chain": chain,
                "since": since_datetime,
                "limit": limit,
                "offset": offset
            }

            try:
                page_count += 1
                print(f"    📄 Page {page_count}: offset={offset}, limit={limit}")

                result = await client._execute_query(WALLET_ACTIVITY_QUERY, variables)

                # Extract data
                transfers = result.get("data", {}).get("ethereum", {}).get("transfers", [])
                trades = result.get("data", {}).get("ethereum", {}).get("dexTrades", [])

                all_transfers.extend(transfers)
                all_trades.extend(trades)

                total_received = len(transfers) + len(trades)
                print(f"    📊 Page {page_count} results: {len(transfers)} transfers, {len(trades)} trades")

                # Check if we got less than limit (end of results)
                if total_received < limit:
                    print(f"    ✅ Pagination complete: {page_count} pages, {len(all_transfers)} transfers, {len(all_trades)} trades")
                    break

                offset += limit

                # Safety check to avoid infinite loops
                if offset > 10000:  # Reasonable limit
                    print(f"    ⚠️  Hit offset limit ({offset}), stopping pagination")
                    break

            except Exception as e:
                print(f"    ❌ Query failed at offset {offset}: {e}")
                break

    # Convert to standardized format
    events = []
    current_ts = int(datetime.now().timestamp())

    # Process transfers
    for transfer in all_transfers:
        try:
            event = {
                "ts": transfer["block"]["timestamp"]["unixtime"],
                "chain": chain,
                "type": "transfer",
                "wallet": address,
                "tx": transfer["transaction"]["hash"],
                "usd": None,  # Transfers don't have USD values in this query
                "raw": {
                    "transfer": transfer,
                    "block": transfer["block"],
                    "transaction": transfer["transaction"]
                }
            }

            # Add sender/receiver info
            if transfer["sender"]["address"].lower() == address.lower():
                event["direction"] = "out"
                event["counterparty"] = transfer["receiver"]["address"]
            else:
                event["direction"] = "in"
                event["counterparty"] = transfer["sender"]["address"]

            # Add provenance (matching mock format for test compatibility)
            event["provenance"] = {
                "source": "bitquery",
                "snapshot": current_ts,
                "wallet": address,
                "since_ts": since_ts
            }

            events.append(event)

        except KeyError as e:
            print(f"    ⚠️  Skipping malformed transfer: {e}")
            continue

    # Process DEX trades
    for trade in all_trades:
        try:
            # Determine if this wallet was involved
            trader_addr = trade["trader"]["address"]
            if trader_addr.lower() != address.lower():
                continue

            event = {
                "ts": trade["block"]["timestamp"]["unixtime"],
                "chain": chain,
                "type": "swap",
                "wallet": address,
                "tx": trade["transaction"]["hash"],
                "pool": trade["smartContract"]["address"],
                "usd": trade.get("buyAmountInUsd") or trade.get("sellAmountInUsd"),
                "raw": {
                    "trade": trade,
                    "block": trade["block"],
                    "transaction": trade["transaction"]
                }
            }

            # Add provenance (matching mock format for test compatibility)
            event["provenance"] = {
                "source": "bitquery",
                "snapshot": current_ts,
                "wallet": address,
                "since_ts": since_ts
            }

            events.append(event)

        except KeyError as e:
            print(f"    ⚠️  Skipping malformed trade: {e}")
            continue

    # Sort events by timestamp
    events.sort(key=lambda x: x["ts"])

    print(f"    📊 Processing complete: {len(events)} events from {len(all_transfers)} transfers and {len(all_trades)} trades")

    return {
        "provider": "bitquery",
        "next_cursor": None,  # Bitquery uses offset-based pagination
        "events": events,
        "metadata": {
            "address": address,
            "chain": chain,
            "since_ts": since_ts,
            "fetched_at": current_ts,
            "event_count": len(events),
            "transfers_count": len(all_transfers),
            "trades_count": len(all_trades),
            "pages_processed": page_count,
            "raw_response": {
                "transfers": all_transfers,
                "trades": all_trades
            }
        }
    }


# For backward compatibility and testing
import warnings

async def fetch_wallet_activity_bitquery(
    address: str,
    chain: str = "base",
    since_ts: int = None
) -> Dict[str, Any]:
    """Alias for the live function.
    
    Deprecated: Use fetch_wallet_activity_bitquery_live() instead.
    This function will be removed in a future version.
    """
    warnings.warn(
        "fetch_wallet_activity_bitquery() is deprecated. "
        "Use fetch_wallet_activity_bitquery_live() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return await fetch_wallet_activity_bitquery_live(address, chain, since_ts)
