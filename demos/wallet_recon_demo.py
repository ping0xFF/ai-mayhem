#!/usr/bin/env python3
"""
Wallet Recon Demo - Bitquery Adapter v1
Demonstrates the complete wallet activity fetching and processing flow.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import agent
sys.path.append(str(Path(__file__).parent.parent))

from agent import LangGraphAgent
from mock_tools import demo_wallet_recon_flow, fetch_wallet_activity_bitquery
from json_storage import set_cursor
from datetime import datetime
from nodes import planner_node, worker_node, analyze_node, brief_node


async def demo_wallet_recon():
    """Demonstrate wallet recon with Bitquery adapter."""
    print("🔍 Wallet Recon Demo - Bitquery Adapter v1")
    print("=" * 60)
    print("This demo shows:")
    print("• Fetching wallet activity via Bitquery adapter")
    print("• Persisting raw JSON to Layer 1")
    print("• Computing wallet-specific signals")
    print("• Generating brief with wallet recon note")
    print()

    # Test wallet addresses
    test_wallets = [
        "0x1234567890abcdef1234567890abcdef12345678",
        "0xabcdef1234567890abcdef1234567890abcdef12",
        "0xdeadbeef1234567890abcdef1234567890abcdef"
    ]

    # Choose a test wallet
    wallet = test_wallets[0]
    print(f"🎯 Target wallet: {wallet}")
    print()

    # Create agent instance
    agent = None
    try:
        agent = LangGraphAgent()

        # Set up initial state to force wallet recon
        initial_goal = f"Monitor wallet activity for {wallet}"

        print(f"📋 Goal: {initial_goal}")
        print(f"💰 Budget: $0.00/$5.00")
        print(f"📅 Current time: {datetime.now()}")
        print()

        # Set up cursors to force wallet recon
        current_ts = int(datetime.now().timestamp())
        print("🔧 Setting up demo cursors...")
        await set_cursor(f"wallet:{wallet}", 0, f"Demo: Force wallet cursor stale")
        await set_cursor("lp", current_ts, "Demo: Make LP cursor fresh")
        await set_cursor("explore_metrics", current_ts, "Demo: Make explore cursor fresh")
        print("   ✅ Cursors configured for wallet recon demo")
        print()

        # Run the agent with wallet recon
        print("🔄 Running agent with wallet recon...")
        print()

        result = await agent.run(initial_goal, thread_id="demo_wallet_recon")

        print("✅ Agent run completed!")
        print()

        # Show results
        print("📊 Results Summary:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Selected action: {result.get('selected_action', 'none')}")
        print(f"   Target wallet: {result.get('target_wallet', 'none')}")
        print(f"   Events retrieved: {len(result.get('events', []))}")
        if 'brief_text' in result and result.get('brief_text'):
            print(f"   Brief emitted: {len(result.get('brief_text', ''))} chars")
        if 'next_watchlist' in result:
            print(f"   Next watchlist: {result.get('next_watchlist', [])}")

        print()

        # Show wallet-specific signals
        signals = result.get('signals', {})
        wallet_signals = {k: v for k, v in signals.items() if k.startswith(('net_lp_usd', 'new_pools_touched'))}
        if wallet_signals:
            print("👛 Wallet Signals:")
            net_lp_usd = wallet_signals.get('net_lp_usd_24h', 0)
            new_pools = wallet_signals.get('new_pools_touched_24h', [])
            print(f"   Net LP USD (24h): ${net_lp_usd:.2f}")
            print(f"   New pools touched (24h): {len(new_pools)} pools")
            if new_pools:
                print(f"   Pool addresses: {', '.join(new_pools[:3])}")
                if len(new_pools) > 3:
                    print(f"   ... and {len(new_pools) - 3} more")
            print()

        # Show brief text
        if 'brief_text' in result and result.get('brief_text'):
            print("📝 Brief Text:")
            print(f"   {result.get('brief_text')}")
            print()

        print("🎉 Wallet recon demo completed successfully!")

    except Exception as e:
        print(f"❌ Error running wallet recon demo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up agent resources
        if agent:
            await agent.close()


async def demo_wallet_recon_flow_only():
    """Demo the complete wallet recon flow by calling nodes directly."""
    print("🔄 Wallet Recon Flow Demo (Direct Node Calls)")
    print("=" * 60)

    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    current_ts = int(datetime.now().timestamp())

    # Initial state with wallet cursor stale
    old_ts = current_ts - (3 * 3600)  # 3 hours ago (stale for wallet cursor)
    state = {
        "goal": f"Monitor wallet {wallet}",
        "status": "planning",
        "spent_today": 0.0,
        "cursors": {
            f"wallet:{wallet}": old_ts,  # Stale wallet cursor (3h ago, will trigger wallet_recon)
            "lp": current_ts,            # Fresh LP cursor
            "explore_metrics": current_ts,  # Fresh explore cursor
        },
        "selected_action": None,
        "target_wallet": None,
        "events": [],
        "raw_data": {},
        "last24h_counts": {},
        "top_pools": [],
        "signals": {},
        "brief_text": None,
        "next_watchlist": [],
        "last_brief_at": 0
    }

    print(f"🎯 Target wallet: {wallet}")
    print("📊 Initial cursors configured for wallet recon")
    print()

    try:
        # Step 1: Planner
        print("📋 Step 1: Planner selecting action...")
        state = await planner_node(state)
        print(f"   ✅ Selected action: {state.get('selected_action')}")
        print(f"   🎯 Target wallet: {state.get('target_wallet')}")
        print()

        # Step 2: Worker
        print("🔧 Step 2: Worker executing wallet_recon...")
        state = await worker_node(state)
        print(f"   ✅ Retrieved {len(state.get('events', []))} events")
        raw_data = state.get('raw_data', {})
        if raw_data:
            print(f"   📊 Provider: {raw_data.get('provider')}")
            print(f"   📦 Event count: {raw_data.get('event_count')}")
        print()

        # Step 3: Analyze
        print("📊 Step 3: Analyze computing signals...")
        state = await analyze_node(state)
        signals = state.get('signals', {})
        wallet_signals = {k: v for k, v in signals.items() if k.startswith(('net_lp_usd', 'new_pools_touched'))}
        if wallet_signals:
            net_lp_usd = wallet_signals.get('net_lp_usd_24h', 0)
            new_pools = wallet_signals.get('new_pools_touched_24h', [])
            print(f"   👛 Net LP USD (24h): ${net_lp_usd:.2f}")
            print(f"   🏊 New pools touched: {len(new_pools)} pools")
        print()

        # Step 4: Brief
        print("📝 Step 4: Brief generating summary...")
        state = await brief_node(state)
        brief_text = state.get('brief_text')
        if brief_text:
            print(f"   ✅ Brief emitted: {len(brief_text)} chars")
            print("   📋 Brief content:")
            print(f"      {brief_text}")
        else:
            print("   ⏰ Brief skipped (cooldown or low activity)")
        print()

        print("🎉 Wallet recon flow demo completed successfully!")

    except Exception as e:
        print(f"❌ Error in wallet recon flow: {e}")
        import traceback
        traceback.print_exc()


async def demo_bitquery_adapter_only():
    """Demo just the Bitquery adapter without full agent flow."""
    print("🔌 Bitquery Adapter Demo (Standalone)")
    print("=" * 50)

    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    response = demo_wallet_recon_flow(wallet)

    print()
    print("📋 Response Structure:")
    print(f"   Provider: {response.get('provider')}")
    print(f"   Next cursor: {response.get('next_cursor')}")
    print(f"   Events count: {len(response.get('events', []))}")
    print(f"   Metadata: {response.get('metadata', {})}")

    print()
    print("📊 Sample Event Structure:")
    if response.get('events'):
        event = response['events'][0]
        print(f"   ts: {event.get('ts')}")
        print(f"   chain: {event.get('chain')}")
        print(f"   type: {event.get('type')}")
        print(f"   wallet: {event.get('wallet')}")
        print(f"   pool: {event.get('pool')}")
        print(f"   usd: {event.get('usd')}")
        print(f"   tx: {event.get('tx')}")
        print(f"   raw keys: {list(event.get('raw', {}).keys())}")

    print("\n✅ Bitquery adapter demo completed!")


async def main():
    """Main demo function."""
    print("🎯 Wallet Recon Demo Suite")
    print("This demonstrates wallet activity monitoring with Bitquery adapter.")
    print()

    try:
        # Demo 1: Direct node flow (shows wallet recon working)
        await demo_wallet_recon_flow_only()

        print("\n" + "="*80 + "\n")

        # Demo 2: Full agent flow (may not trigger wallet recon due to cursor loading)
        await demo_wallet_recon()

        print("\n" + "="*80 + "\n")

        # Demo 3: Just the adapter
        await demo_bitquery_adapter_only()

        print("\n🎉 All wallet recon demos completed successfully!")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
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
        # Force cleanup of any remaining tasks
        import gc
        gc.collect()
        print("🧹 Cleanup completed")
