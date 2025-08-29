#!/usr/bin/env python3
"""
Example usage of json_storage module.
Demonstrates storing and retrieving JSON responses from external APIs/MCPs.
"""

from json_storage import save_json, load_json, query_recent, delete_json


def example_nansen_mcp_storage():
    """Example of storing Nansen MCP responses."""
    print("=== Nansen MCP Storage Example ===\n")
    
    # Simulate Nansen MCP response
    nansen_response = {
        "query": "ETH",
        "result_type": "token",
        "results": [
            {
                "name": "Ethereum",
                "symbol": "ETH",
                "price_usd": 4410.22,
                "volume_usd": "53.4B",
                "change_24h": -6.8
            }
        ]
    }
    
    # Store the response
    save_json("nansen_eth_query_20240826", "nansen", nansen_response)
    print("✅ Stored Nansen ETH query response")
    
    # Retrieve the response
    loaded_response = load_json("nansen_eth_query_20240826")
    print(f"✅ Retrieved response: {loaded_response['query']} -> {len(loaded_response['results'])} results")
    
    # Update with new data (upsert)
    updated_response = {
        "query": "ETH",
        "result_type": "token",
        "results": [
            {
                "name": "Ethereum",
                "symbol": "ETH",
                "price_usd": 4420.15,  # Updated price
                "volume_usd": "53.4B",
                "change_24h": -6.5
            }
        ],
        "updated_at": "2024-08-26T10:30:00Z"
    }
    
    save_json("nansen_eth_query_20240826", "nansen", updated_response)
    print("✅ Updated response with new price data")
    
    # Verify upsert worked
    final_response = load_json("nansen_eth_query_20240826")
    print(f"✅ Final price: ${final_response['results'][0]['price_usd']}")


def example_multiple_sources():
    """Example of storing data from multiple sources."""
    print("\n=== Multiple Sources Example ===\n")
    
    # Store CoinGecko data
    coingecko_data = {
        "bitcoin": {
            "usd": 109988,
            "usd_24h_vol": 59900000000,
            "usd_24h_change": -2.6
        }
    }
    save_json("coingecko_btc_20240826", "coingecko", coingecko_data)
    
    # Store Etherscan data
    etherscan_data = {
        "status": "1",
        "message": "OK",
        "result": {
            "blockNumber": "19500000",
            "timeStamp": "1735228800",
            "hash": "0x123...",
            "gasPrice": "20000000000"
        }
    }
    save_json("etherscan_tx_0x123", "etherscan", etherscan_data)
    
    # Query recent data by source
    recent_nansen = query_recent("nansen", limit=5)
    recent_coingecko = query_recent("coingecko", limit=5)
    recent_etherscan = query_recent("etherscan", limit=5)
    
    print(f"✅ Recent Nansen responses: {len(recent_nansen)}")
    print(f"✅ Recent CoinGecko responses: {len(recent_coingecko)}")
    print(f"✅ Recent Etherscan responses: {len(recent_etherscan)}")


def example_error_handling():
    """Example of error handling."""
    print("\n=== Error Handling Example ===\n")
    
    # Try to store non-JSON-serializable data
    try:
        non_serializable = {"func": lambda x: x}
        save_json("test", "test", non_serializable)
    except ValueError as e:
        print(f"✅ Caught expected error: {e}")
    
    # Try to load non-existent data
    missing_data = load_json("nonexistent_id")
    print(f"✅ Load non-existent: {missing_data}")
    
    # Try to delete non-existent data
    deleted = delete_json("nonexistent_id")
    print(f"✅ Delete non-existent: {deleted}")


if __name__ == "__main__":
    example_nansen_mcp_storage()
    example_multiple_sources()
    example_error_handling()
    
    print("\n=== Integration with Agent ===")
    print("To integrate with your agent, you can:")
    print("1. Store MCP responses before processing:")
    print("   save_json(tx_hash, 'nansen', mcp_response)")
    print("2. Cache API responses to avoid re-fetching:")
    print("   cached = load_json(request_id)")
    print("3. Query recent data for analysis:")
    print("   recent = query_recent('nansen', limit=10)")
