#!/usr/bin/env python3
"""
CLI interface for the LangGraph agent.
"""

import asyncio
import argparse
from agent import LangGraphAgent


async def main():
    parser = argparse.ArgumentParser(description="LangGraph AI Agent CLI")
    parser.add_argument("--goal", type=str, help="Goal for the agent to work toward")
    parser.add_argument("--thread", type=str, default="default", help="Thread ID for the session")
    parser.add_argument("--resume", action="store_true", help="Resume an existing thread")
    parser.add_argument("--list", action="store_true", help="List all available threads")
    
    args = parser.parse_args()
    
    agent = LangGraphAgent()
    
    if args.list:
        threads = agent.list_threads()
        print("Available threads:")
        for thread in threads:
            print(f"  - {thread}")
        return
    
    if args.resume:
        final_state = await agent.resume(args.thread)
        if final_state:
            print(f"Resumed thread '{args.thread}' - Final status: {final_state.status}")
        else:
            print(f"No thread found with ID: {args.thread}")
        return
    
    if not args.goal:
        print("Error: --goal is required when not resuming")
        parser.print_help()
        return
    
    final_state = await agent.run(args.goal, args.thread)
    print(f"Completed with status: {final_state.status}")


if __name__ == "__main__":
    asyncio.run(main())
