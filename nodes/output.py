"""Output formatting utilities for AI Mayhem."""

from typing import Dict, Any, Optional
from datetime import datetime
import textwrap


class OutputFormatter:
    """Handles consistent output formatting across nodes."""
    
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
        
        print("AI Mayhem - Wallet Brief Mode")
        print("=" * 80)
        print(f"Started  : {self.execution_data['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Thread   : {thread_id}")
        print("=" * 80)
        print("\nExecuting: Budget → Planner → Worker → Analyze → Brief → Memory")
        print("-" * 80)
    
    def log_node_progress(self, node: str, message: str, duration: Optional[float] = None):
        """Log progress from a node in real-time."""
        duration_str = f" ({duration:.2f}s)" if duration is not None else ""
        output = f"[{node:7}] {message}{duration_str}"
        print(output)
        
        self.execution_data['node_outputs'].append(output)
    
    def update_execution_data(self, **kwargs):
        """Update execution data with new information."""
        self.execution_data.update(kwargs)
    
    def _format_signal_name(self, name: str) -> str:
        """Format signal names for display."""
        name = name.replace('_', ' ').title()
        if name.endswith('24h'):
            name = name.replace('24h', '(24h)')
        return name
    
    def _format_signal_value(self, value: float) -> str:
        """Format signal values for display."""
        if isinstance(value, (int, float)):
            if value > 100:
                return f"{value:,.0f}"
            return f"{value:.2f}"
        return str(value)
    
    def print_final_summary(self):
        """Print the final formatted summary."""
        print("\nSummary Report")
        print("=" * 80)
        
        # Execution Summary
        print("\nExecution Summary")
        print("-" * 80)
        print(f"Provider      : {self.execution_data['provider']}")
        print(f"Action       : {self.execution_data['action']}")
        print(f"Status       : {self.execution_data['status']}")
        print(f"Duration     : {self.execution_data['duration']:.2f}s")
        print(f"Budget Used  : ${self.execution_data['budget_used']:.4f}")
        
        # Analysis Results (if available)
        if self.execution_data['events_24h'] or self.execution_data['signals']:
            print("\nAnalysis Results")
            print("-" * 80)
            
            # Events and Pools
            events = self.execution_data['events_24h']
            if isinstance(events, dict):
                events = events.get('total', 0)
            print(f"Events (24h)  : {events}")
            
            if self.execution_data['top_pools']:
                print(f"Top Pools     : {', '.join(self.execution_data['top_pools'])}")
            
            # Format signals nicely
            signals = self.execution_data['signals']
            core_signals = {
                'volume': signals.get('volume_signal', 0.0),
                'activity': signals.get('activity_signal', 0.0),
            }
            
            # Core signals with intensity labels
            for name, value in core_signals.items():
                intensity = "low" if value < 0.4 else "moderate" if value < 0.7 else "high"
                print(f"{name.title():12}: {value:.2f} ({intensity})")
            
            # LP-specific signals
            lp_signals = {
                'Net Delta': signals.get('net_liquidity_delta_24h', 0),
                'Churn Rate': signals.get('lp_churn_rate_24h', 0.0),
                'Activity': signals.get('pool_activity_score', 0.0)
            }
            print(f"LP Stats      : {', '.join(f'{k}={self._format_signal_value(v)}' for k, v in lp_signals.items())}")
        
        # Brief
        print("\nBrief")
        print("-" * 80)
        if self.execution_data['brief_text']:
            # Wrap text at 80 chars with proper indentation
            wrapped = textwrap.fill(
                self.execution_data['brief_text'],
                width=80,
                initial_indent='',
                subsequent_indent=''
            )
            print(wrapped)
        elif self.execution_data['brief_skipped']:
            print(f"Brief skipped: {self.execution_data['skip_reason']}")
            print("Note: Brief gating conditions not met")
        else:
            print("No brief generated")
        
        # Notifications
        if self.execution_data['notifications']:
            print("\nNotifications")
            print("-" * 80)
            for notification in self.execution_data['notifications']:
                print(notification)
        
        # Final Status
        print(f"\nStatus: {self.execution_data['status'].title()}")


# Global formatter instance
formatter = OutputFormatter()