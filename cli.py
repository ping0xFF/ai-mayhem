#!/usr/bin/env python3
"""
CLI interface for AI Mayhem with production wallet-brief mode.

Follows production code standards with proper error handling,
logging, type safety, and structured configuration.
"""

import sys
import asyncio
import argparse
import time
from typing import NoReturn, Optional
from datetime import datetime

from nodes.config import DEBUG, is_discord_enabled, load_monitored_wallets, save_monitored_wallets
from nodes.rich_output import formatter
from agent import LangGraphAgent


class CLIError(Exception):
    """CLI-specific errors."""
    pass


def show_monitored_wallets() -> None:
    """Show currently monitored wallet addresses."""
    wallets = load_monitored_wallets()
    if wallets:
        print("📋 Currently monitored wallets:")
        for i, wallet in enumerate(wallets, 1):
            print(f"  {i}. {wallet}")
        print(f"\nTotal: {len(wallets)} wallets")
    else:
        print("❌ No wallets are currently being monitored")
        print("   Use 'ai_mayhem wallets add <address>' to add wallets")
        print("   Or set MONITORED_WALLETS environment variable")
        print("   Or create wallets.txt file with one address per line")

def add_monitored_wallet(wallet_address: str) -> None:
    """Add a wallet to the monitored list."""
    wallets = load_monitored_wallets()
    if wallet_address in wallets:
        print(f"⚠️  Wallet {wallet_address} is already being monitored")
        return

    wallets.append(wallet_address)
    save_monitored_wallets(wallets)
    print(f"✅ Added wallet {wallet_address}")
    print(f"   Now monitoring {len(wallets)} wallets")

def remove_monitored_wallet(wallet_address: str) -> None:
    """Remove a wallet from the monitored list."""
    wallets = load_monitored_wallets()
    if wallet_address not in wallets:
        print(f"⚠️  Wallet {wallet_address} is not currently being monitored")
        return

    wallets.remove(wallet_address)
    save_monitored_wallets(wallets)
    print(f"✅ Removed wallet {wallet_address}")
    print(f"   Now monitoring {len(wallets)} wallets")


async def run_wallet_brief_mode() -> int:
    """
    Execute wallet brief mode: Budget → Planner → Worker → Analyze → Brief → Memory.
    
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    start_time = time.time()
    agent = None
    
    try:
        # Create agent instance
        agent = LangGraphAgent()
        
        # Set up initial state for single execution
        thread_id = f"wallet_brief_{int(datetime.now().timestamp())}"
        goal = "Execute single wallet reconnaissance and brief generation"
        
        # Initialize output
        formatter.start_execution(thread_id)
        
        # Run the complete flow once
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
        
        # Update execution data
        formatter.update_execution_data(
            provider=provider,
            action=selected_action,
            status=status,
            duration=execution_time,
            budget_used=spent_today,
            events_24h=final_state.get('last24h_counts', {}).get('total', 0),
            top_pools=final_state.get('top_pools', []),
            signals=final_state.get('signals', {}),
            brief_text=final_state.get('brief_text'),
            brief_skipped=final_state.get('brief_skipped', False),
            skip_reason=final_state.get('reason')
        )
        
        # Handle Discord notification if brief was generated
        if final_state.get('brief_text') and not final_state.get('brief_skipped', False):
            if is_discord_enabled():
                from discord_notifier import send_discord_notification
                
                try:
                    success = await send_discord_notification(
                        title="AI Mayhem Brief",
                        brief_text=final_state['brief_text'],
                        metadata={
                            'provider': provider,
                            'action': selected_action,
                            'execution_time': f"{execution_time:.2f}s",
                            'budget_used': f"${spent_today:.4f}",
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                    
                    formatter.update_execution_data(
                        notifications=[
                            "Discord: Notification sent successfully" if success else
                            "Discord: Failed to send notification"
                        ]
                    )
                except Exception as e:
                    formatter.update_execution_data(
                        notifications=[f"Discord: Error - {str(e)}"]
                    )
            else:
                formatter.update_execution_data(
                    notifications=["Discord: Notifications disabled (no webhook configured)"]
                )
        
        # Print final summary
        formatter.print_final_summary()
        return 0
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"\nError in wallet brief mode: {str(e)}")
        print(f"Failed after {execution_time:.2f}s")
        if DEBUG:
            import traceback
            traceback.print_exc()
        return 1
        
    finally:
        if agent:
            await agent.close()  # Close the database connection


async def run_legacy_mode(args: argparse.Namespace) -> None:
    """Run legacy CLI commands."""
    agent = LangGraphAgent()
    
    try:
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
        
    finally:
        await agent.close()  # Close the database connection


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
        "--wallets",
        type=str,
        help="Comma-separated list of wallet addresses to monitor (overrides config)"
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

    # Wallets management command
    wallets_parser = subparsers.add_parser('wallets', help='Manage monitored wallet addresses')
    wallets_subparsers = wallets_parser.add_subparsers(dest='wallets_command', help='Wallet operations')

    # wallets show
    wallets_subparsers.add_parser('show', help='Show currently monitored wallets')

    # wallets add
    add_parser = wallets_subparsers.add_parser('add', help='Add a wallet to monitor')
    add_parser.add_argument('address', help='Wallet address to add')

    # wallets remove
    remove_parser = wallets_subparsers.add_parser('remove', help='Remove a wallet from monitoring')
    remove_parser.add_argument('address', help='Wallet address to remove')
    
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
        # Handle wallet management commands
        if args.command == "wallets":
            if args.wallets_command == "show":
                show_monitored_wallets()
            elif args.wallets_command == "add":
                add_monitored_wallet(args.address)
            elif args.wallets_command == "remove":
                remove_monitored_wallet(args.address)
            else:
                wallets_parser.print_help()
            return

        # Handle wallet-brief mode
        if args.command == "run" and hasattr(args, 'mode') and args.mode == "wallet-brief":
            exit_code = await run_wallet_brief_mode()
            sys.exit(exit_code)

        # Handle legacy commands
        await run_legacy_mode(args)
        
    except CLIError as e:
        print(f"Error: {e}")
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())