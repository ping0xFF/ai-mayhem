"""
Shared configuration for all nodes.
"""

import os
from datetime import timedelta

# Budget configuration
BUDGET_DAILY = float(os.getenv("BUDGET_DAILY", "5.0"))

# Cursor staleness thresholds
CURSOR_STALE_WALLET = 2 * 3600      # 2 hours
CURSOR_STALE_LP = 6 * 3600          # 6 hours
CURSOR_STALE_EXPLORE = 24 * 3600    # 24 hours

# Brief gating configuration
BRIEF_COOLDOWN = 6 * 3600           # 6 hours
BRIEF_THRESHOLD_EVENTS = 5          # Minimum events
BRIEF_THRESHOLD_SIGNAL = 0.6        # Minimum signal strength

# Per-node timeout configuration
PLANNER_TIMEOUT = 10    # seconds
WORKER_TIMEOUT = 20     # seconds
ANALYZE_TIMEOUT = 15    # seconds
BRIEF_TIMEOUT = 10      # seconds
MEMORY_TIMEOUT = 10     # seconds
