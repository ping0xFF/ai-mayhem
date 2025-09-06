#!/usr/bin/env python3
"""
Unit tests for the provider router.
Tests provider selection, fallback chain, and API key detection.
"""

import unittest
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the module to test
from provider_router import ProviderRouter, get_wallet_provider


class TestProviderRouter(unittest.TestCase):
    """Test provider router functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing router instance
        import provider_router
        provider_router._router = None
        
        # Store original environment
        self.original_env = {}
        for key in ["ALCHEMY_API_KEY", "COVALENT_API_KEY", "BITQUERY_ACCESS_TOKEN", "WALLET_RECON_SOURCE"]:
            self.original_env[key] = os.getenv(key)

    def tearDown(self):
        """Restore original environment."""
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_detect_available_providers_no_keys(self):
        """Test provider detection with no API keys."""
        # Clear all API keys
        for key in ["ALCHEMY_API_KEY", "COVALENT_API_KEY", "BITQUERY_ACCESS_TOKEN"]:
            os.environ.pop(key, None)
        
        router = ProviderRouter()
        
        # Only mock should be available
        self.assertFalse(router.available_providers["alchemy"])
        self.assertFalse(router.available_providers["covalent"])
        self.assertFalse(router.available_providers["bitquery"])
        self.assertTrue(router.available_providers["mock"])

    def test_detect_available_providers_with_keys(self):
        """Test provider detection with API keys present."""
        # Set API keys
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ["BITQUERY_ACCESS_TOKEN"] = "test_bitquery_token"
        
        router = ProviderRouter()
        
        # All providers should be available
        self.assertTrue(router.available_providers["alchemy"])
        self.assertTrue(router.available_providers["covalent"])
        self.assertTrue(router.available_providers["bitquery"])
        self.assertTrue(router.available_providers["mock"])

    def test_build_fallback_chain_all_available(self):
        """Test fallback chain with all providers available."""
        # Set all API keys
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ["BITQUERY_ACCESS_TOKEN"] = "test_bitquery_token"
        
        router = ProviderRouter()
        
        # Should be in priority order: alchemy, covalent, bitquery, mock
        expected_chain = ["alchemy", "covalent", "bitquery", "mock"]
        self.assertEqual(router.fallback_chain, expected_chain)

    def test_build_fallback_chain_partial_available(self):
        """Test fallback chain with only some providers available."""
        # Set only Alchemy and Bitquery keys
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["BITQUERY_ACCESS_TOKEN"] = "test_bitquery_token"
        # Don't set COVALENT_API_KEY
        
        router = ProviderRouter()
        
        # Should include only available providers + mock
        expected_chain = ["alchemy", "bitquery", "mock"]
        self.assertEqual(router.fallback_chain, expected_chain)

    def test_get_selected_provider_explicit_source(self):
        """Test explicit provider selection via WALLET_RECON_SOURCE."""
        # Set API keys and explicit source
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ["WALLET_RECON_SOURCE"] = "covalent"
        
        router = ProviderRouter()
        selected = router.get_selected_provider()
        
        self.assertEqual(selected, "covalent")

    def test_get_selected_provider_invalid_source(self):
        """Test fallback when invalid source is selected."""
        # Set API keys and invalid source
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["WALLET_RECON_SOURCE"] = "invalid_provider"
        
        router = ProviderRouter()
        selected = router.get_selected_provider()
        
        # Should fall back to first available provider
        self.assertEqual(selected, "alchemy")

    def test_get_selected_provider_no_source(self):
        """Test provider selection without explicit source."""
        # Set API keys but no explicit source
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ.pop("WALLET_RECON_SOURCE", None)
        
        router = ProviderRouter()
        selected = router.get_selected_provider()
        
        # Should use first available provider in fallback chain
        self.assertEqual(selected, "alchemy")

    @patch('provider_router.fetch_wallet_activity_alchemy_live')
    async def test_fetch_wallet_activity_alchemy(self, mock_alchemy):
        """Test wallet activity fetch with Alchemy provider."""
        # Set up mock response
        mock_response = {
            "events": [{"tx": "0x123", "type": "transfer"}],
            "metadata": {"source": "alchemy", "network": "base-mainnet"}
        }
        mock_alchemy.return_value = mock_response
        
        # Set API keys
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["WALLET_RECON_SOURCE"] = "alchemy"
        
        router = ProviderRouter()
        result = await router.fetch_wallet_activity("0x123", "base", 0, 1000)
        
        # Verify Alchemy was called with correct parameters
        mock_alchemy.assert_called_once_with(
            address="0x123",
            max_transactions=1000,
            hours_back=None,
            network="base-mainnet"
        )
        
        self.assertEqual(result, mock_response)

    @patch('provider_router.fetch_wallet_activity_covalent_live')
    async def test_fetch_wallet_activity_covalent(self, mock_covalent):
        """Test wallet activity fetch with Covalent provider."""
        # Set up mock response
        mock_response = {
            "events": [{"tx": "0x456", "type": "transfer"}],
            "metadata": {"source": "covalent", "chain_id": "8453"}
        }
        mock_covalent.return_value = mock_response
        
        # Set API keys
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ["WALLET_RECON_SOURCE"] = "covalent"
        
        router = ProviderRouter()
        result = await router.fetch_wallet_activity("0x456", "base", 0, 1000)
        
        # Verify Covalent was called with correct parameters
        mock_covalent.assert_called_once_with(
            address="0x456",
            chain_id="8453",
            cursor=None,
            limit=100
        )
        
        self.assertEqual(result, mock_response)

    @patch('provider_router.fetch_wallet_activity_bitquery_live')
    async def test_fetch_wallet_activity_bitquery(self, mock_bitquery):
        """Test wallet activity fetch with Bitquery provider."""
        # Set up mock response
        mock_response = {
            "events": [{"tx": "0x789", "type": "transfer"}],
            "metadata": {"source": "bitquery", "chain": "base"}
        }
        mock_bitquery.return_value = mock_response
        
        # Set API keys
        os.environ["BITQUERY_ACCESS_TOKEN"] = "test_bitquery_token"
        os.environ["WALLET_RECON_SOURCE"] = "bitquery"
        
        router = ProviderRouter()
        result = await router.fetch_wallet_activity("0x789", "base", 12345, 1000)
        
        # Verify Bitquery was called with correct parameters
        mock_bitquery.assert_called_once_with(
            address="0x789",
            chain="base",
            since_ts=12345
        )
        
        self.assertEqual(result, mock_response)

    @patch('provider_router._fetch_wallet_activity_bitquery_mock')
    async def test_fetch_wallet_activity_mock(self, mock_mock):
        """Test wallet activity fetch with mock provider."""
        # Set up mock response
        mock_response = {
            "events": [{"tx": "0xabc", "type": "transfer"}],
            "metadata": {"source": "mock", "chain": "base"}
        }
        mock_mock.return_value = mock_response
        
        # No API keys set, should use mock
        router = ProviderRouter()
        result = await router.fetch_wallet_activity("0xabc", "base", 0, 1000)
        
        # Verify mock was called with correct parameters
        mock_mock.assert_called_once_with("0xabc", "base", 0)
        
        self.assertEqual(result, mock_response)

    @patch('provider_router.fetch_wallet_activity_alchemy_live')
    @patch('provider_router.fetch_wallet_activity_covalent_live')
    async def test_fallback_chain_execution(self, mock_covalent, mock_alchemy):
        """Test fallback chain when primary provider fails."""
        # Set up Alchemy to fail, Covalent to succeed
        mock_alchemy.side_effect = Exception("Alchemy API error")
        mock_covalent.return_value = {
            "events": [{"tx": "0xdef", "type": "transfer"}],
            "metadata": {"source": "covalent", "chain_id": "8453"}
        }
        
        # Set API keys for both providers
        os.environ["ALCHEMY_API_KEY"] = "test_alchemy_key"
        os.environ["COVALENT_API_KEY"] = "test_covalent_key"
        os.environ["WALLET_RECON_SOURCE"] = "alchemy"
        
        router = ProviderRouter()
        result = await router.fetch_wallet_activity("0xdef", "base", 0, 1000)
        
        # Verify Alchemy was tried first and failed
        mock_alchemy.assert_called_once()
        
        # Verify Covalent was called as fallback
        mock_covalent.assert_called_once()
        
        # Should return Covalent result
        self.assertEqual(result["metadata"]["source"], "covalent")

    def test_get_wallet_provider_singleton(self):
        """Test that get_wallet_provider returns singleton instance."""
        # Clear any existing instance
        import provider_router
        provider_router._router = None
        
        # Get two instances
        router1 = get_wallet_provider()
        router2 = get_wallet_provider()
        
        # Should be the same instance
        self.assertIs(router1, router2)

    def test_provider_router_imports(self):
        """Test that provider router can import all required modules."""
        # This test will fail if imports are broken
        from provider_router import ProviderRouter, get_wallet_provider, fetch_wallet_activity_with_router
        
        # Should be able to create router
        router = ProviderRouter()
        self.assertIsInstance(router, ProviderRouter)


class TestProviderRouterIntegration(unittest.TestCase):
    """Integration tests for provider router."""

    def setUp(self):
        """Set up test fixtures."""
        # Store original environment
        self.original_env = {}
        for key in ["ALCHEMY_API_KEY", "COVALENT_API_KEY", "BITQUERY_ACCESS_TOKEN", "WALLET_RECON_SOURCE"]:
            self.original_env[key] = os.getenv(key)

    def tearDown(self):
        """Restore original environment."""
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_environment_variable_handling(self):
        """Test that environment variables are properly handled."""
        # Test with no environment variables
        for key in ["ALCHEMY_API_KEY", "COVALENT_API_KEY", "BITQUERY_ACCESS_TOKEN"]:
            os.environ.pop(key, None)
        
        router = ProviderRouter()
        self.assertEqual(router.get_selected_provider(), "mock")
        
        # Test with Alchemy key only
        os.environ["ALCHEMY_API_KEY"] = "test_key"
        router = ProviderRouter()
        self.assertEqual(router.get_selected_provider(), "alchemy")
        
        # Test with explicit source override
        os.environ["WALLET_RECON_SOURCE"] = "mock"
        router = ProviderRouter()
        self.assertEqual(router.get_selected_provider(), "mock")

    def test_provider_availability_detection(self):
        """Test that provider availability is correctly detected."""
        # No keys
        for key in ["ALCHEMY_API_KEY", "COVALENT_API_KEY", "BITQUERY_ACCESS_TOKEN"]:
            os.environ.pop(key, None)
        
        router = ProviderRouter()
        self.assertFalse(router.available_providers["alchemy"])
        self.assertFalse(router.available_providers["covalent"])
        self.assertFalse(router.available_providers["bitquery"])
        self.assertTrue(router.available_providers["mock"])
        
        # Add Alchemy key
        os.environ["ALCHEMY_API_KEY"] = "test_key"
        router = ProviderRouter()
        self.assertTrue(router.available_providers["alchemy"])
        self.assertFalse(router.available_providers["covalent"])
        self.assertFalse(router.available_providers["bitquery"])
        self.assertTrue(router.available_providers["mock"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

