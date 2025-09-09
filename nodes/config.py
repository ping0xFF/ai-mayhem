"""
Shared configuration for all nodes and application settings.
"""

import os
from datetime import timedelta

# Budget configuration
BUDGET_DAILY = float(os.getenv("BUDGET_DAILY", "5.0"))

# API configuration
WALLET_RECON_SOURCE = os.getenv("WALLET_RECON_SOURCE", "alchemy")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VERBOSE_API_LOGS = os.getenv("VERBOSE_API_LOGS", "false").lower() == "true"
LOG_MALFORMED_TRANSACTIONS = os.getenv("LOG_MALFORMED_TRANSACTIONS", "false").lower() == "true"

# Cursor staleness thresholds
CURSOR_STALE_WALLET = 2 * 3600      # 2 hours
CURSOR_STALE_LP = 6 * 3600          # 6 hours
CURSOR_STALE_EXPLORE = 24 * 3600    # 24 hours

# Brief gating configuration
BRIEF_COOLDOWN = 6 * 3600           # 6 hours
BRIEF_THRESHOLD_EVENTS = 5          # Minimum events
BRIEF_THRESHOLD_SIGNAL = 0.6        # Minimum signal strength

# Brief modes
BRIEF_MODE = os.getenv("BRIEF_MODE", "both")   # deterministic | llm | both

# LLM input policy
LLM_INPUT_POLICY = os.getenv("LLM_INPUT_POLICY", "full")  # full | budgeted
LLM_TOKEN_CAP = int(os.getenv("LLM_TOKEN_CAP", "120000"))

# Model selection is controlled by the gateway; we pass a model alias:
LLM_BRIEF_MODEL = os.getenv("LLM_BRIEF_MODEL", "anthropic/claude-3-haiku-20240307")
# e.g. in prod: anthropic/claude-3-5-sonnet-20241022

# Per-node timeout configuration
PLANNER_TIMEOUT = 10    # seconds
WORKER_TIMEOUT = 20     # seconds
ANALYZE_TIMEOUT = 15    # seconds
BRIEF_TIMEOUT = 10      # seconds
MEMORY_TIMEOUT = 10     # seconds

# Wallet configuration
MONITORED_WALLETS_FILE = os.getenv("MONITORED_WALLETS_FILE", "wallets.txt")
MONITORED_WALLETS_ENV = os.getenv("MONITORED_WALLETS", "")

# Helper functions
def is_discord_enabled() -> bool:
    """Check if Discord notifications are enabled."""
    return DISCORD_WEBHOOK_URL is not None

def validate_wallet_source(source: str) -> bool:
    """Validate wallet reconnaissance source."""
    valid_sources = ['alchemy', 'covalent', 'bitquery', 'mock']
    return source in valid_sources

def validate_brief_mode(mode: str) -> bool:
    """Validate brief mode setting."""
    valid_modes = ['deterministic', 'llm', 'both']
    return mode in valid_modes

def load_monitored_wallets() -> list[str]:
    """Load monitored wallets from file or environment variable."""
    wallets = []

    # Try environment variable first
    if MONITORED_WALLETS_ENV:
        wallets.extend([w.strip() for w in MONITORED_WALLETS_ENV.split(',') if w.strip()])
        return wallets

    # Try file next
    try:
        with open(MONITORED_WALLETS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    wallets.append(line)
    except FileNotFoundError:
        pass  # File doesn't exist, use empty list

    return wallets

def save_monitored_wallets(wallets: list[str]) -> None:
    """Save monitored wallets to file."""
    with open(MONITORED_WALLETS_FILE, 'w') as f:
        f.write("# Monitored wallet addresses (one per line)\n")
        for wallet in wallets:
            f.write(f"{wallet}\n")

def validate_llm_input_policy(policy: str) -> bool:
    """Validate LLM input policy setting."""
    valid_policies = ['full', 'budgeted']
    return policy in valid_policies

# Logging helpers
def should_log_verbose() -> bool:
    """Check if verbose logging is enabled."""
    return VERBOSE_API_LOGS or DEBUG

def should_log_warnings() -> bool:
    """Check if warning-level messages should be logged."""
    return LOG_LEVEL in ['DEBUG', 'INFO', 'WARNING']

def should_log_malformed() -> bool:
    """Check if malformed transaction logging is enabled."""
    return LOG_MALFORMED_TRANSACTIONS
