#!/usr/bin/env python3
"""
Test Bitquery provider initialization and token handling.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.append(str(Path(__file__).parent.parent))

from real_apis.bitquery import BitqueryClient


class TestBitqueryProvider(unittest.IsolatedAsyncioTestCase):
    """Test Bitquery provider initialization and configuration."""

    def setUp(self):
        """Save original environment."""
        self.original_token = os.environ.get("BITQUERY_ACCESS_TOKEN")
        self.original_api_key = os.environ.get("BITQUERY_API_KEY")

    def tearDown(self):
        """Restore original environment."""
        if self.original_token:
            os.environ["BITQUERY_ACCESS_TOKEN"] = self.original_token
        elif "BITQUERY_ACCESS_TOKEN" in os.environ:
            del os.environ["BITQUERY_ACCESS_TOKEN"]

        if self.original_api_key:
            os.environ["BITQUERY_API_KEY"] = self.original_api_key
        elif "BITQUERY_API_KEY" in os.environ:
            del os.environ["BITQUERY_API_KEY"]

    def test_token_check_not_printed_on_import(self):
        """Test that token status is not printed just by importing the module."""
        with patch('builtins.print') as mock_print:
            # Re-import the module
            import importlib
            import real_apis.bitquery
            importlib.reload(real_apis.bitquery)
            
            # Verify no token status was printed
            mock_print.assert_not_called()

    def test_token_check_on_client_init(self):
        """Test that token status is checked when client is initialized."""
        test_token = "test_token_123"
        os.environ["BITQUERY_ACCESS_TOKEN"] = test_token

        with patch('builtins.print') as mock_print:
            client = BitqueryClient()
            
            # Verify token status was printed
            mock_print.assert_called_with(
                f"    ✅ Using Bitquery access token: {test_token[:10]}... (length: {len(test_token)})"
            )

    def test_token_check_on_client_init_missing(self):
        """Test that missing token is reported when client is initialized."""
        if "BITQUERY_ACCESS_TOKEN" in os.environ:
            del os.environ["BITQUERY_ACCESS_TOKEN"]
        if "BITQUERY_API_KEY" in os.environ:
            del os.environ["BITQUERY_API_KEY"]

        with patch('builtins.print') as mock_print:
            with self.assertRaises(ValueError) as cm:
                client = BitqueryClient()
            
            # Verify error message
            self.assertEqual(
                str(cm.exception),
                "BITQUERY_ACCESS_TOKEN environment variable is required (or BITQUERY_API_KEY for backward compatibility)"
            )
            
            # Verify missing token was reported
            mock_print.assert_called_with(
                "    ❌ No Bitquery access token found. Set BITQUERY_ACCESS_TOKEN in .env"
            )

    def test_token_check_on_client_init_with_api_key(self):
        """Test that API key is accepted as fallback."""
        test_key = "test_api_key_123"
        os.environ["BITQUERY_API_KEY"] = test_key

        with patch('builtins.print') as mock_print:
            client = BitqueryClient()
            
            # Verify token status was printed
            mock_print.assert_called_with(
                f"    ✅ Using Bitquery API key: {test_key[:10]}... (length: {len(test_key)})"
            )


if __name__ == '__main__':
    unittest.main()
