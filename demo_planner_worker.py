#!/usr/bin/env python3
"""
Demo script for the integrated Planner/Worker flow using the main agent.
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from agent import LangGraphAgent


async def demo_complete_flow():
    """Demonstrate the complete Planner/Worker flow using the main agent."""
    print("🚀 Integrated Planner/Worker Demo")
    print("=" * 50)
    
    # Create agent instance
    agent = LangGraphAgent()
    
    # Set a goal that will trigger the Planner/Worker flow
    goal = "Monitor Base chain DEX activity and identify opportunities"
    
    print(f"📋 Goal: {goal}")
    print(f"💰 Budget: $0.00/$5.00")
    print(f"📅 Current time: {datetime.now()}")
    print()
    
    # Run the agent
    print("🔄 Running agent with integrated Planner/Worker flow...")
    print()
    
    try:
        result = await agent.run(goal, thread_id="demo_planner_worker")
        
        print("✅ Agent run completed!")
        print()
        
        # Show results
        print("📊 Results Summary:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Spent today: ${result.get('spent_today', 0.0):.4f}")
        print(f"   Messages: {len(result.get('messages', []))}")
        
        # Show Planner/Worker specific results
        if 'selected_action' in result:
            print(f"   Selected action: {result.get('selected_action')}")
        if 'target_wallet' in result:
            print(f"   Target wallet: {result.get('target_wallet')}")
        if 'events' in result:
            print(f"   Events retrieved: {len(result.get('events', []))}")
        if 'brief_text' in result and result.get('brief_text'):
            print(f"   Brief emitted: {len(result.get('brief_text', ''))} chars")
        if 'next_watchlist' in result:
            print(f"   Next watchlist: {result.get('next_watchlist')}")
        
        print()
        
        # Show recent messages
        print("💬 Recent Messages:")
        messages = result.get('messages', [])
        for msg in messages[-5:]:  # Last 5 messages
            print(f"   {msg}")
        
        print()
        print("🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running agent: {e}")
        import traceback
        traceback.print_exc()


async def demo_multiple_runs():
    """Demonstrate multiple runs to show idempotent behavior."""
    print("🔄 Multiple Runs Demo")
    print("=" * 50)
    
    agent = LangGraphAgent()
    goal = "Monitor Base chain DEX activity and identify opportunities"
    
    for run_num in range(1, 4):
        print(f"\n🏃 Run #{run_num}")
        print("-" * 30)
        
        try:
            result = await agent.run(goal, thread_id=f"demo_multi_run_{run_num}")
            
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"   Spent: ${result.get('spent_today', 0.0):.4f}")
            print(f"   Action: {result.get('selected_action', 'none')}")
            print(f"   Events: {len(result.get('events', []))}")
            print(f"   Brief: {'emitted' if result.get('brief_text') else 'skipped'}")
            
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n✅ Multiple runs completed!")


async def main():
    """Main demo function."""
    print("🎯 Planner/Worker Integration Demo")
    print("This demonstrates the Budget → Planner → Worker → Analyze → Brief → Memory flow")
    print("integrated into the main LangGraph agent.")
    print()
    
    # Run single flow demo
    await demo_complete_flow()
    
    print("\n" + "="*60 + "\n")
    
    # Run multiple runs demo
    await demo_multiple_runs()


if __name__ == "__main__":
    asyncio.run(main())
