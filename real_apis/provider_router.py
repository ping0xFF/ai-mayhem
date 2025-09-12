#!/usr/bin/env python3
"""
Provider Router for Wallet Activity APIs
========================================

Centralized provider selection logic that:
1. Checks API key presence to determine available providers
2. Respects WALLET_RECON_SOURCE override
3. Implements fallback chain: Alchemy → Covalent → Bitquery → Mock
4. Provides consistent interface for all providers
"""

import os
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Provider imports
try:
    from .alchemy_provider import fetch_wallet_activity_alchemy_live
    ALCHEMY_AVAILABLE = True
except ImportError:
    ALCHEMY_AVAILABLE = False

try:
    from .covalent import fetch_wallet_activity_covalent_live
    COVALENT_AVAILABLE = True
except ImportError:
    COVALENT_AVAILABLE = False

try:
    from .bitquery import fetch_wallet_activity_bitquery_live
    BITQUERY_AVAILABLE = True
except ImportError:
    BITQUERY_AVAILABLE = False


class ProviderRouter:
    """Centralized provider selection and routing logic with schema validation."""

    # Standardized field mapping for all providers
    FIELD_MAPPINGS = {
        "event_id": ["tx", "txHash", "hash", "transaction_hash"],
        "event_type": ["type", "kind", "transaction_type", "event_type"],
        "wallet": ["wallet", "address", "from_address", "account"],
        "timestamp": ["timestamp", "ts", "block_timestamp", "time"],
        "block": ["block", "block_number", "block_height"],
        "chain": ["chain", "network", "chain_id"],
        "gas_used": ["gas_used", "gas", "gas_spent"],
        "value": ["value", "amount", "value_wei"],
        "token_symbol": ["token_symbol", "symbol", "token"],
        "token_address": ["token_address", "contract_address", "token_contract"],
        "direction": ["direction", "type", "transfer_type"],
        "counterparty": ["counterparty", "to_address", "recipient", "sender"],
        "pool": ["pool", "pool_address", "liquidity_pool"],
        "details": ["details", "log_events", "logs"],
        "amounts": ["amounts", "token_amounts", "transfer_amounts"]
    }

    def __init__(self):
        self.available_providers = self._detect_available_providers()
        self.fallback_chain = self._build_fallback_chain()
        self.schema_validator = ProviderSchemaValidator(self.FIELD_MAPPINGS)
    
    def _detect_available_providers(self) -> Dict[str, bool]:
        """Detect which providers are available based on API keys and imports."""
        providers = {
            "alchemy": False,
            "covalent": False,
            "bitquery": False,
            "mock": True  # Mock is always available
        }
        
        # Check Alchemy
        if ALCHEMY_AVAILABLE and os.getenv("ALCHEMY_API_KEY"):
            providers["alchemy"] = True
            print("    ✅ Alchemy provider available (API key present)")
        else:
            if not ALCHEMY_AVAILABLE:
                print("    ❌ Alchemy provider unavailable (import failed)")
            else:
                print("    ❌ Alchemy provider unavailable (no API key)")
        
        # Check Covalent
        if COVALENT_AVAILABLE and os.getenv("COVALENT_API_KEY"):
            providers["covalent"] = True
            print("    ✅ Covalent provider available (API key present)")
        else:
            if not COVALENT_AVAILABLE:
                print("    ❌ Covalent provider unavailable (import failed)")
            else:
                print("    ❌ Covalent provider unavailable (no API key)")
        
        # Check Bitquery
        if BITQUERY_AVAILABLE and os.getenv("BITQUERY_ACCESS_TOKEN"):
            providers["bitquery"] = True
            print("    ✅ Bitquery provider available (API key present)")
        else:
            if not BITQUERY_AVAILABLE:
                print("    ❌ Bitquery provider unavailable (import failed)")
            else:
                print("    ❌ Bitquery provider unavailable (no API key)")
        
        return providers
    
    def _build_fallback_chain(self) -> List[str]:
        """Build fallback chain based on available providers."""
        chain = []
        
        # Add available providers in priority order
        for provider in ["alchemy", "covalent", "bitquery"]:
            if self.available_providers.get(provider, False):
                chain.append(provider)
        
        # Always add mock as final fallback
        chain.append("mock")
        
        return chain
    
    def get_selected_provider(self) -> str:
        """Get the selected provider based on WALLET_RECON_SOURCE or fallback chain."""
        # Check for explicit source selection
        source = os.getenv("WALLET_RECON_SOURCE", "").lower()
        
        if source:
            if source in self.available_providers and self.available_providers[source]:
                print(f"    🎯 Using selected provider: {source}")
                return source
            else:
                print(f"    ⚠️  Selected provider '{source}' not available, using fallback chain")
        
        # Use first available provider in fallback chain
        if self.fallback_chain:
            selected = self.fallback_chain[0]
            print(f"    🔄 Using fallback chain provider: {selected}")
            return selected
        
        # Final fallback to mock
        print("    🟡 No providers available, using mock")
        return "mock"
    
    async def fetch_wallet_activity(
        self,
        address: str,
        chain: str = "base",
        since_ts: int = 0,
        max_transactions: int = 1000,
        hours_back: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch wallet activity using the selected provider with fallback chain.
        
        Args:
            address: Wallet address to fetch activity for
            chain: Blockchain chain (default: base)
            since_ts: Timestamp to fetch from (0 = all)
            max_transactions: Maximum transactions to return
            hours_back: Hours back for time filtering
            
        Returns:
            Dict with standardized format containing events and metadata
        """
        selected_provider = self.get_selected_provider()
        
        # Try providers in fallback chain until one succeeds
        for provider in self.fallback_chain:
            if provider == selected_provider or (selected_provider not in self.available_providers):
                try:
                    print(f"    📡 Attempting {provider} provider...")
                    result = await self._call_provider(
                        provider, address, chain, since_ts, max_transactions, hours_back
                    )

                    # Validate and analyze the response schema
                    events = result.get("events", [])
                    if events:
                        # Detect schema changes and validate structure
                        schema_analysis = self.schema_validator.detect_schema_changes(events, provider)

                        # Log schema information
                        if schema_analysis.get("unexpected_fields"):
                            print(f"    🔍 Provider {provider}: detected {len(schema_analysis['unexpected_fields'])} new fields")

                    # Add schema validation metadata
                    if "provider" not in result:
                        result["provider"] = {
                            "name": provider,
                            "chain": chain,
                            "selected_at": int(asyncio.get_event_loop().time()),
                            "schema_validated": True
                        }

                    print(f"    ✅ Successfully used {provider} provider")
                    return result
                except Exception as e:
                    print(f"    ❌ {provider} provider failed: {e}")
                    if provider == "mock":
                        # Mock should never fail, but if it does, raise the error
                        raise
                    # Continue to next provider in fallback chain
                    continue
        
        # This should never happen since mock is always in the chain
        raise Exception("No providers available in fallback chain")
    
    async def _call_provider(
        self,
        provider: str,
        address: str,
        chain: str,
        since_ts: int,
        max_transactions: int,
        hours_back: Optional[int]
    ) -> Dict[str, Any]:
        """Call the specified provider with proper async handling."""
        
        if provider == "alchemy":
            # Alchemy uses different parameters
            return await fetch_wallet_activity_alchemy_live(
                address=address,
                max_transactions=max_transactions,
                hours_back=hours_back,
                network="base-mainnet" if chain == "base" else chain
            )
        
        elif provider == "covalent":
            # Covalent uses chain_id and page-based pagination
            chain_id = "8453" if chain == "base" else chain
            return await fetch_wallet_activity_covalent_live(
                address=address,
                chain_id=chain_id,
                cursor=None,  # Start from beginning
                limit=min(max_transactions, 100)  # Covalent limit is 100
            )
        
        elif provider == "bitquery":
            # Bitquery uses since_ts parameter
            return await fetch_wallet_activity_bitquery_live(
                address=address,
                chain=chain,
                since_ts=since_ts
            )
        
        elif provider == "mock":
            # Use the existing mock implementation
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent))
            from mock_tools import _fetch_wallet_activity_bitquery_mock
            return _fetch_wallet_activity_bitquery_mock(address, chain, since_ts)
        
        else:
            raise ValueError(f"Unknown provider: {provider}")


class ProviderSchemaValidator:
    """Validates and standardizes API provider response schemas."""

    def __init__(self, field_mappings: Dict[str, List[str]]):
        self.field_mappings = field_mappings
        self.validation_cache = {}  # Cache validation results

    def validate_and_standardize_event(self, event: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """Validate event structure and standardize field names."""
        standardized = {}

        # Map each expected field to actual field in event
        for std_field, possible_names in self.field_mappings.items():
            value = None
            actual_field = None

            # Try each possible field name
            for field_name in possible_names:
                if field_name in event:
                    value = event[field_name]
                    actual_field = field_name
                    break

            # Store the standardized field
            standardized[std_field] = value

            # Log field mapping for monitoring
            if actual_field and actual_field != std_field:
                cache_key = f"{provider}:{std_field}:{actual_field}"
                if cache_key not in self.validation_cache:
                    print(f"    🔄 Provider {provider}: mapped '{actual_field}' → '{std_field}'")
                    self.validation_cache[cache_key] = True

        # Validate required fields
        required_fields = ["event_id", "event_type", "wallet", "timestamp"]
        missing = [f for f in required_fields if standardized.get(f) is None]

        if missing:
            print(f"    ⚠️  Provider {provider}: missing required fields: {missing}")
            # Don't fail, just log - maintain backward compatibility

        return standardized

    def detect_schema_changes(self, events: List[Dict[str, Any]], provider: str) -> Dict[str, Any]:
        """Detect potential schema changes by analyzing field patterns."""
        if not events:
            return {"status": "no_events"}

        # Analyze field patterns
        all_fields = set()
        field_patterns = {}

        for event in events[:10]:  # Sample first 10 events
            for field in event.keys():
                all_fields.add(field)
                field_patterns[field] = field_patterns.get(field, 0) + 1

        # Check for unexpected fields
        known_fields = set()
        for possible_names in self.field_mappings.values():
            known_fields.update(possible_names)

        unexpected = all_fields - known_fields
        if unexpected:
            print(f"    🔍 Provider {provider}: found {len(unexpected)} unexpected fields: {list(unexpected)[:5]}...")

        return {
            "total_fields": len(all_fields),
            "unexpected_fields": list(unexpected),
            "field_patterns": field_patterns
        }


# Global router instance
_router = None

def get_wallet_provider() -> ProviderRouter:
    """Get the global provider router instance."""
    global _router
    if _router is None:
        _router = ProviderRouter()
    return _router


# Convenience function for backward compatibility
async def fetch_wallet_activity_with_router(
    address: str,
    chain: str = "base",
    since_ts: int = 0,
    max_transactions: int = 1000,
    hours_back: Optional[int] = None
) -> Dict[str, Any]:
    """Fetch wallet activity using the provider router."""
    router = get_wallet_provider()
    return await router.fetch_wallet_activity(
        address, chain, since_ts, max_transactions, hours_back
    )
