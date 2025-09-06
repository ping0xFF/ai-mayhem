#!/usr/bin/env python3
"""
CLI interface for AI Mayhem with production wallet-brief mode.

Follows production code standards with proper error handling,
logging, type safety, and structured configuration.
"""

import sys
import asyncio
import argparse
from typing import NoReturn, Optional

from nodes.config import DEBUG, is_discord_enabled
from agent import LangGraphAgent


class CLIError(Exception):
    """CLI-specific errors."""
    pass


async def run_wallet_brief_mode() -> int:
    """
    Execute wallet brief mode: Budget → Planner → Worker → Analyze → Brief → Memory.
    
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    import time
    from datetime import datetime
    
    print("🚀 AI Mayhem - Wallet Brief Mode")
    print("=" * 50)
    
    start_time = time.time()
    
    try:
        # Create agent instance
        agent = LangGraphAgent()
        
        # Set up initial state for single execution
        thread_id = f"wallet_brief_{int(datetime.now().timestamp())}"
        goal = "Execute single wallet reconnaissance and brief generation"
        
        print(f"📅 Started at: {datetime.now().isoformat()}")
        print(f"🔗 Thread ID: {thread_id}")
        print()
        
        # Run the complete flow once
        print("🔄 Executing Budget → Planner → Worker → Analyze → Brief → Memory...")
        
        final_state = await agent.run(goal, thread_id)
        
        execution_time = time.time() - start_time
        
        # Extract state information
        status = final_state.get('status', 'unknown')
        spent_today = final_state.get('spent_today', 0.0)
        selected_action = final_state.get('selected_action', 'none')
        
        # Extract provider information
        provider = 'unknown'
        if 'raw_data' in final_state and final_state['raw_data']:
            for key, value in final_state['raw_data'].items():
                if isinstance(value, dict) and 'metadata' in value:
                    provider = value['metadata'].get('source', provider)
                    break
        if provider == 'unknown':
            provider = final_state.get('provider', 'unknown')
        
        # Log provider information as required
        print(f"🔍 provider={provider}")
        print(f"⚡ action={selected_action}")
        print(f"📊 status={status}")
        print(f"⏱️  execution_time={execution_time:.2f}s")
        print(f"💰 budget_used=${spent_today:.4f}")
        
        # Check if brief was emitted
        brief_text = final_state.get('brief_text')
        brief_skipped = final_state.get('brief_skipped', False)
        skip_reason = final_state.get('reason', 'unknown')
        
        if brief_text and not brief_skipped:
            print("\n📝 Brief Generated:")
            print("-" * 30)
            print(brief_text)
            print("-" * 30)
            
            # Send Discord notification if enabled
            if is_discord_enabled():
                print("\n📤 Sending Discord notification...")
                from discord_notifier import send_discord_notification
                
                try:
                    success = await send_discord_notification(
                        title="AI Mayhem Brief",
                        brief_text=brief_text,
                        metadata={
                            'provider': provider,
                            'action': selected_action,
                            'execution_time': f"{execution_time:.2f}s",
                            'budget_used': f"${spent_today:.4f}",
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                    
                    if success:
                        print("✅ Discord notification sent successfully")
                    else:
                        print("❌ Failed to send Discord notification")
                except Exception as e:
                    print(f"❌ Discord notification error: {e}")
            else:
                print("📵 Discord notifications disabled (no DISCORD_WEBHOOK_URL)")
        
        elif brief_skipped:
            print(f"\n⏭️  Brief skipped: {skip_reason}")
            print("   (Brief gating conditions not met)")
        else:
            print("\n📵 No brief generated")
        
        print(f"\n✅ Wallet brief mode completed in {execution_time:.2f}s")
        return 0
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"\n❌ Error in wallet brief mode: {str(e)}")
        print(f"⏱️  Failed after {execution_time:.2f}s")
        if DEBUG:
            import traceback
            traceback.print_exc()
        return 1


async def run_legacy_mode(args: argparse.Namespace) -> None:
    """Run legacy CLI commands."""
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
            status = final_state.get('status', 'unknown')
            print(f"Resumed thread '{args.thread}' - Final status: {status}")
        else:
            print(f"No thread found with ID: {args.thread}")
        return
    
    if not args.goal:
        raise CLIError("--goal is required when not resuming")
    
    final_state = await agent.run(args.goal, args.thread)
    status = final_state.get('status', 'unknown')
    print(f"Completed with status: {status}")


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="AI Mayhem - LangGraph AI Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the agent')
    run_parser.add_argument(
        "--mode", 
        type=str, 
        choices=["wallet-brief"], 
        help="Execution mode for production use"
    )
    run_parser.add_argument(
        "--goal", 
        type=str, 
        help="Goal for the agent to work toward"
    )
    run_parser.add_argument(
        "--thread", 
        type=str, 
        default="default", 
        help="Thread ID for the session"
    )
    run_parser.add_argument(
        "--resume", 
        action="store_true", 
        help="Resume an existing thread"
    )
    run_parser.add_argument(
        "--list", 
        action="store_true", 
        help="List all available threads"
    )
    
    # Legacy support for old CLI usage
    parser.add_argument("--goal", type=str, help="Goal for the agent to work toward")
    parser.add_argument("--thread", type=str, default="default", help="Thread ID for the session")
    parser.add_argument("--resume", action="store_true", help="Resume an existing thread")
    parser.add_argument("--list", action="store_true", help="List all available threads")
    
    return parser


async def main() -> NoReturn:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # Handle wallet-brief mode
        if args.command == "run" and hasattr(args, 'mode') and args.mode == "wallet-brief":
            exit_code = await run_wallet_brief_mode()
            sys.exit(exit_code)
        
        # Handle legacy commands
        await run_legacy_mode(args)
        
    except CLIError as e:
        print(f"❌ {e}")
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
