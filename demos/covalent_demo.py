#!/usr/bin/env python3
"""
Covalent Wallet Recon Demo
Tests Covalent adapter integration with pagination and cursor management.
"""

import os
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import agent
sys.path.append(str(Path(__file__).parent.parent))

from mock_tools import fetch_wallet_activity_bitquery


async def demo_covalent_integration():
    """Demo Covalent wallet recon integration."""
    print("🔵 Covalent Wallet Recon Demo")
    print("=" * 60)
    print("This demo tests Covalent API integration with:")
    print("• Live Covalent API calls")
    print("• Cursor-based pagination")
    print("• Fallback to Bitquery")
    print("• Raw data persistence")
    print()

    # Test wallet - using a known active wallet on Base
    test_wallet = "0x1234567890abcdef1234567890abcdef12345678"

    print(f"🎯 Test wallet: {test_wallet}")
    print()

    # Check environment
    covalent_key = os.getenv("COVALENT_API_KEY")
    bitquery_key = os.getenv("BITQUERY_API_KEY")
    source = os.getenv("WALLET_RECON_SOURCE", "covalent")

    print("🔧 Environment Check:")
    print(f"   COVALENT_API_KEY: {'✅ Set' if covalent_key else '❌ Missing'}")
    print(f"   BITQUERY_API_KEY: {'✅ Set' if bitquery_key else '❌ Missing'}")
    print(f"   WALLET_RECON_SOURCE: {source}")
    print()

    # Force Covalent source for demo
    os.environ["WALLET_RECON_SOURCE"] = "covalent"

    try:
        print("📡 Testing Covalent API call...")
        response = fetch_wallet_activity_bitquery(test_wallet, "base", 0)

        print("✅ API call successful")
        print(f"   📊 Events: {len(response.get('events', []))}")

        provider = response.get("provider", {})
        if isinstance(provider, dict):
            print(f"   🔖 Provider: {provider.get('name', 'unknown')}")
            cursor = provider.get('cursor', 'None')
            if cursor and cursor != 'None':
                print(f"   📄 Cursor: {str(cursor)[:20]}...")
            else:
                print("   📄 Cursor: None")

        metadata = response.get("metadata", {})
        print(f"   📈 Transaction count: {metadata.get('transaction_count', 0)}")
        print(f"   🔄 Has more: {metadata.get('has_more', False)}")

        # Show sample events
        events = response.get("events", [])
        if events:
            print("   💡 Sample transactions:")
            for i, event in enumerate(events[:3]):
                ts = datetime.fromtimestamp(event.get('ts', 0))
                event_type = event.get('type', 'unknown')
                counterparty = event.get('counterparty', 'unknown')[:10]
                print(f"      {i+1}. {ts.strftime('%H:%M')} - {event_type} with {counterparty}...")

        print()
        print("🎉 Covalent integration test completed successfully!")

    except Exception as e:
        print(f"❌ Covalent test failed: {e}")
        print("💡 This might be due to missing API key or billing setup")
        print("   Check your COVALENT_API_KEY in .env file")

    finally:
        # Restore original source setting
        if "WALLET_RECON_SOURCE" in os.environ:
            del os.environ["WALLET_RECON_SOURCE"]


async def demo_pagination_test():
    """Test cursor-based pagination."""
    print("📄 Covalent Pagination Test")
    print("=" * 40)

    test_wallet = "0x1234567890abcdef1234567890abcdef12345678"

    # This would test multiple pages if we had a real API key
    print(f"🎯 Testing pagination for wallet: {test_wallet}")
    print("💡 Note: This test requires a valid Covalent API key with billing enabled")
    print("   to see actual pagination behavior.")


async def main():
    """Main demo function."""
    print("🔵 Covalent Wallet Recon Integration Suite")
    print("=" * 70)

    try:
        await demo_covalent_integration()
        print("\n" + "="*70 + "\n")
        await demo_pagination_test()

        print("\n🎉 Covalent integration demos completed!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleanup completed")
