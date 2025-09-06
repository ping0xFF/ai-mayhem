"""Rich-based output formatting for AI Mayhem."""

from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import textwrap
import json
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.logging import RichHandler
import logging
from .config import DEBUG

# Set up rich console with forced color
console = Console(force_terminal=True, color_system="truecolor")

# Configure logging with rich but suppress INFO
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and above
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            console=console,
            show_time=False,
            show_path=False,
            level=logging.WARNING
        )
    ]
)

# Suppress specific loggers
logging.getLogger('data_model').setLevel(logging.WARNING)
logging.getLogger('json_storage').setLevel(logging.WARNING)

def make_bar(value: float, width: int = 8) -> Text:
    """Create a visual bar with proper color based on value."""
    filled = int(value * width)
    bar = Text()
    
    if value < 0.4:
        color = "red"
        label = "Low"
    elif value < 0.7:
        color = "yellow"
        label = "Moderate"
    else:
        color = "green"
        label = "High"
        
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled))
    bar.append(f" {label:8}", style=color)
    
    return bar

def format_number(value: float) -> str:
    """Format number with appropriate precision."""
    if isinstance(value, (int, float)):
        if value >= 10:
            return f"{value:.1f}"
        return f"{value:.2f}"
    return str(value)

class RichOutputFormatter:
    """Rich-based output formatter for AI Mayhem."""
    
    def __init__(self):
        """Initialize the formatter."""
        self.execution_data = {
            'started_at': datetime.now(),
            'thread_id': None,
            'node_outputs': [],
            'provider': 'unknown',
            'action': None,
            'status': None,
            'duration': 0.0,
            'budget_used': 0.0,
            'events_24h': 0,
            'top_pools': [],
            'signals': {},
            'brief_text': None,
            'brief_skipped': False,
            'skip_reason': None,
            'notifications': []
        }
        
    def start_execution(self, thread_id: str):
        """Print execution header and store thread info."""
        self.execution_data['thread_id'] = thread_id
        
        header = Text()
        header.append("AI Mayhem Brief", style="bold blue")
        header.append(" " * (60 - len("AI Mayhem Brief")))
        header.append(self.execution_data['started_at'].strftime('%Y-%m-%d %H:%M:%S'), style="dim")
        console.print(header)
        console.print("─" * 80)
        console.print()
    
    def log_node_progress(self, node: str, message: str, duration: Optional[float] = None):
        """Log progress from a node in real-time."""
        duration_str = f" ({duration:.2f}s)" if duration is not None else ""
        
        text = Text()
        text.append(f"[{node:7}]", style="bold blue")
        text.append(" ")
        
        if any(x in message.lower() for x in ["completed", "ok", "success"]):
            text.append(f"{message}{duration_str}", style="green")
        else:
            text.append(message)
            if duration is not None:
                text.append(duration_str, style="dim")
        
        console.print(text)
    
    def update_execution_data(self, **kwargs):
        """Update execution data with new information."""
        self.execution_data.update(kwargs)
    
    def print_final_summary(self):
        """Print the final formatted summary."""
        console.print()
        console.print("[bold blue]EXECUTION[/bold blue]")
        console.print(f"Provider : {self.execution_data['provider']}")
        console.print(f"Action   : {self.execution_data['action']}")
        
        status_text = Text()
        status_text.append("Status   : ")
        if self.execution_data['status'] == 'completed':
            status_text.append("✓ Complete", style="green bold")
        else:
            status_text.append(self.execution_data['status'], style="yellow")
        console.print(status_text)
        
        console.print(f"Runtime  : {self.execution_data['duration']:.2f}s")
        console.print(f"Budget   : ${self.execution_data['budget_used']:.4f}", style="dim")
        console.print()

        # Activity Metrics
        console.print("[bold blue]ACTIVITY METRICS[/bold blue]")
        events = self.execution_data['events_24h']
        if isinstance(events, dict):
            events = events.get('total', 0)
        console.print(f"Events (24h)    : {events:<8} ", end="")
        console.print("Normal activity level", style="dim")

        signals = self.execution_data['signals']
        core_signals = {
            'Volume Signal': signals.get('volume_signal', 0.0),
            'Activity Signal': signals.get('activity_signal', 0.0),
        }

        for name, value in core_signals.items():
            console.print(f"{name:<15}: {format_number(value):<6} ", end="")
            console.print(make_bar(value))

        lp_signals = {
            'LP Net Delta': signals.get('net_liquidity_delta_24h', 0),
            'LP Churn Rate': signals.get('lp_churn_rate_24h', 0.0),
            'LP Activity': signals.get('pool_activity_score', 0.0)
        }

        for name, value in lp_signals.items():
            if name == 'LP Net Delta':
                console.print(f"{name:<15}: ", end="")
                if value > 0:
                    console.print(f"+{value}", style="green bold")
                else:
                    console.print(f"{value}", style="red")
            else:
                console.print(f"{name:<15}: {format_number(value):<6} ", end="")
                console.print(make_bar(value))
        console.print()

        # Pool Activity
        if self.execution_data['top_pools']:
            console.print("[bold blue]POOL ACTIVITY[/bold blue]")
            signals = self.execution_data['signals']
            raw_data = self.execution_data.get('raw_data', {})
            
            for pool in self.execution_data['top_pools']:
                console.print(f"[bold]{pool}[/bold]")
                
                # Get pool stats from raw data and signals
                pool_data = raw_data.get(pool, {})
                pool_signals = {k: v for k, v in signals.items() if k.startswith(pool)}
                
                # Extract event counts
                events = pool_data.get('events', [])
                adds = sum(1 for e in events if e.get('type') == 'add')
                removes = sum(1 for e in events if e.get('type') == 'remove')
                total = len(events)
                
                # Extract liquidity changes
                net_liq = pool_data.get('net_liquidity', 0)
                token = pool.split('/')[0]  # Use first token in pair
                
                # Get volume signal
                volume_signal = pool_signals.get(f'{pool}_volume', 0.0)
                volume_label = "High" if volume_signal > 0.7 else "Moderate" if volume_signal > 0.4 else "Low"
                volume_style = "green" if volume_signal > 0.7 else "yellow" if volume_signal > 0.4 else "red"
                
                # Display stats
                console.print(f"  Events        : {total} ({adds} add, {removes} remove)")
                if net_liq > 0:
                    console.print(f"  Net Liquidity : [green]+{net_liq} {token}[/green]")
                elif net_liq < 0:
                    console.print(f"  Net Liquidity : [red]{net_liq} {token}[/red]")
                else:
                    console.print(f"  Net Liquidity : 0 {token}")
                console.print(f"  Volume        : [{volume_style}]{volume_label}[/{volume_style}]")
                console.print()

        # Analysis
        if self.execution_data['brief_text']:
            console.print("[bold blue]ANALYSIS[/bold blue]")
            wrapped = textwrap.fill(
                self.execution_data['brief_text'],
                width=80,
                initial_indent='',
                subsequent_indent=''
            )
            console.print(wrapped)
            console.print()

        # System Status
        console.print("[bold blue]SYSTEM STATUS[/bold blue]")
        for notification in self.execution_data['notifications']:
            if "success" in notification.lower():
                console.print(notification, style="green")
            elif "error" in notification.lower() or "failed" in notification.lower():
                console.print(notification, style="red")
            elif "disabled" in notification.lower():
                console.print(notification, style="yellow")
            else:
                console.print(notification, style="dim")
                
        # LLM Interactions
        log_path = Path("logs") / f"llm-calls-{datetime.now().date().isoformat()}.jsonl"
        if log_path.exists():
            console.print("\n[bold blue]LLM INTERACTIONS[/bold blue]")
            with open(log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        # Skip if not from this run
                        if not entry['timestamp'].startswith(self.execution_data['started_at'].isoformat()[:19]):
                            continue
                            
                        console.print(f"[dim]Timestamp: {entry['timestamp']}[/dim]")
                        console.print(f"Model    : [yellow]{entry['model']}[/yellow]")
                        
                        # Print messages
                        console.print("Messages :")
                        for role, content in entry['messages']:
                            if role == "system":
                                console.print(f"  [blue]system[/blue]: {content}")
                            else:
                                console.print(f"  [green]human[/green] : {content}")
                        
                        # Print response
                        console.print("Response :")
                        console.print(f"  [cyan]{entry['response']}[/cyan]")
                        
                        # Print usage
                        usage = entry['usage']
                        console.print("Usage    :")
                        console.print(f"  Prompt tokens     : {usage.get('prompt_tokens', 0)}")
                        console.print(f"  Completion tokens : {usage.get('completion_tokens', 0)}")
                        console.print(f"  Total tokens      : {usage.get('total_tokens', 0)}")
                        console.print(f"  Estimated cost    : ${entry.get('estimated_cost', 0.0):.6f}")
                        console.print()
                    except (json.JSONDecodeError, KeyError):
                        continue
                        
        console.print("─" * 80)


# Global formatter instance
formatter = RichOutputFormatter()