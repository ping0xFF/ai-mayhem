#!/usr/bin/env python3
"""
Test script for the LangGraph agent.
"""

import asyncio
from langgraph_agent import LangGraphAgent


async def test_agent():
    """Test the agent with a simple goal."""
    agent = LangGraphAgent()
    
    goals = [
        "Create a simple todo list application in Python",
        "Research the best practices for API design",
        "Write a script to backup important files"
    ]
    
    for i, goal in enumerate(goals):
        thread_id = f"test-{i+1}"
        print(f"\n{'='*60}")
        print(f"Testing goal {i+1}: {goal}")
        print(f"Thread ID: {thread_id}")
        print('='*60)
        
        try:
            final_state = await agent.run(goal, thread_id)
            print(f"\n✅ Goal completed with status: {final_state.status}")
            print(f"📊 Completed {len(final_state.completed_actions)} actions")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\nPress Enter to continue to next test...")
        input()


if __name__ == "__main__":
    asyncio.run(test_agent())
