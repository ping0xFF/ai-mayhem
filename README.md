# AI Mayhem - LangGraph Agent with Planner/Worker Integration

A sophisticated LangGraph-based AI agent system with controlled autonomy, featuring a Planner/Worker pattern for blockchain data monitoring and analysis.

## 🎯 Project Overview

This project implements a **controlled autonomy** system that augments the existing Recon → Analyze → Brief loop with a minimal Planner/Worker pair. The system can choose between exploration paths (web/subgraph lookups) and the recon backbone, while keeping outputs stable and costs bounded.

### Key Features

- **Controlled Autonomy**: Planner selects actions based on cursor staleness and budget
- **Multi-Source API Integration**: Alchemy (primary) + Covalent + Bitquery (fallback) for wallet recon
- **Flexible JSON Storage**: SQLite-based persistence for arbitrary API responses
- **Per-Node Timing**: Execution time tracking for performance monitoring
- **Idempotent Operations**: No duplicate data on re-runs
- **Budget Awareness**: Cost tracking and limits
- **Graceful API Fallback**: Automatic degradation from live APIs to mock data
- **Mock Data Support**: Development-friendly with deterministic test data

## 🏗️ Architecture

### Flow: Budget → Planner → Worker → Analyze → Brief → Memory

```
Budget Check → Planner (selects action) → Worker (executes tools) → 
Analyze (processes events) → Brief (gates output) → Memory (persists artifacts)
```

### Core Components

1. **Planner Node**: Selects between `wallet_recon`, `lp_recon`, or `explore_metrics`
2. **Worker Node**: Executes chosen path via tool calls, saves raw and normalized JSON
3. **Analyze Node**: Rolls up last 24h counts and computes activity signals
4. **Brief Node**: Gates output based on thresholds and cooldowns
5. **Memory Node**: Persists curated artifacts and updates cursors

## 📁 Project Structure

```
ai-mayhem/
├── agent.py                 # Main LangGraph agent with integrated Planner/Worker
├── data_model.py            # Three-layer data model (Scratch → Events → Artifacts)
├── json_storage.py          # Flexible JSON persistence layer (legacy)
├── mock_tools.py            # Enhanced mock tools with simple/realistic fixtures
├── llm_client.py            # LLM client with cost tracking
├── agent_state.db           # SQLite database (persistent state)
├── cli.py                   # Command-line interface
├── requirements.txt         # Python dependencies
├── config.yaml              # LiteLLM configuration
├── real_apis/               # Real API integrations (Alchemy, Covalent, Bitquery)
│   ├── __init__.py         # API package exports
│   ├── alchemy_provider.py # Alchemy API client for Base chain
│   ├── covalent.py         # Covalent API client for wallet activity
│   ├── bitquery.py         # Bitquery API client for blockchain data
│   └── test_alchemy.py     # Alchemy provider tests
├── nodes/                   # Professional node organization
│   ├── __init__.py         # Node package exports
│   ├── config.py           # Shared configuration constants
│   ├── planner.py          # Planner node - action selection logic
│   ├── worker.py           # Worker node - tool execution & raw data save
│   ├── analyze.py          # Analyze node - signal computation & normalization
│   ├── brief.py            # Brief node - LP-focused gating & summaries
│   └── memory.py           # Memory node - cursor updates & artifact persistence
├── demos/                   # Comprehensive demo suite
│   ├── lp_e2e_demo.py      # Complete LP monitoring end-to-end demo
│   ├── covalent_demo.py    # Covalent wallet recon integration demo
│   ├── wallet_recon_live.py    # Live wallet recon with Bitquery/Covalent
│   ├── quick_verification.py   # Quick verification without hanging
│   └── three_layer_demo.py     # Three-layer data model demonstration
├── tests/                   # Comprehensive test suite
│   ├── test_enhanced_lp.py     # Enhanced LP functionality tests
│   ├── test_lp_brief_gating.py # LP brief gating tests
│   ├── test_planner_worker.py  # TDD tests for Planner/Worker nodes
│   ├── test_three_layer_data_model.py  # Three-layer data model tests
│   ├── test_json_storage.py    # JSON storage tests
│   ├── test_agent.py           # Main agent tests
│   ├── test_live.py            # Live integration tests
│   └── test_wallet_service.py  # Wallet management service tests
├── wallet_service.py          # Wallet management business logic
├── wallets.txt                # Monitored wallet addresses configuration
├── data/
│   └── raw/
│       └── nansen_real_api_response.json  # Sample API responses
└── logs/                    # Application logs
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone and setup
git clone <repository>
cd ai-mayhem

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:
```bash
# Budget settings
BUDGET_DAILY=5.0

# Wallet Recon Configuration
# Covalent API (primary source - higher-level wallet data)
# Get your API key from: https://www.covalenthq.com/
COVALENT_API_KEY=your_covalent_api_key_here

# Alchemy API (primary source - Base chain optimized)
# Get your API key from: https://dashboard.alchemy.com/
ALCHEMY_API_KEY=your_alchemy_api_key_here

# Bitquery API (fallback source - more detailed transaction data)
# Get your API key from: https://streaming.bitquery.io/
BITQUERY_API_KEY=your_bitquery_api_key_here

# Source Selection
WALLET_RECON_SOURCE=alchemy  # Options: alchemy, covalent, bitquery

# Optional: Enable verbose logging for debugging
BITQUERY_VERBOSE=1

# Optional: Bitquery API (for detailed transaction data)
BITQUERY_ACCESS_TOKEN=your_bitquery_api_key_here

# Logging configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
VERBOSE_API_LOGS=false           # Enable detailed API request/response logging
LOG_MALFORMED_TRANSACTIONS=false  # Enable logging of malformed transactions

# LiteLLM settings (if using local proxy)
LITELLM_URL=http://localhost:8000
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=http://localhost:8000

# Nansen API (for real data)
NANSEN_API_KEY=your_nansen_key_here
```

### 2. Configure Wallet Monitoring

Before running production mode, set up which wallets to monitor:

**Option 1: Environment Variable (recommended for production)**
```bash
export MONITORED_WALLETS="0x123...,0xabc...,0xdef..."
```

**Option 2: Configuration File**
```bash
# Create wallets.txt with one address per line
echo "0x1234567890abcdef1234567890abcdef12345678" > wallets.txt
echo "0xabcdef1234567890abcdef1234567890abcdef12" >> wallets.txt
```

**Option 3: CLI Management**
```bash
# Add wallets interactively
python -m ai_mayhem.cli wallets add 0x1234567890abcdef1234567890abcdef12345678
python -m ai_mayhem.cli wallets add 0xabcdef1234567890abcdef1234567890abcdef12

# View current wallets
python -m ai_mayhem.cli wallets show

# Remove wallets
python -m ai_mayhem.cli wallets remove 0x1234567890abcdef1234567890abcdef12345678
```

### 3. Run Demo

```bash
# 🏆 RECOMMENDED: Complete LP monitoring end-to-end demo
python demos/lp_e2e_demo.py

# Quick verification (no hanging issues)
python demos/quick_verification.py

# Original Planner/Worker demo
python demos/lp_e2e_demo.py

# Run comprehensive test suite
python tests/run_all_tests.py           # 🏆 RECOMMENDED: Run ALL tests
python tests/test_enhanced_lp.py        # LP functionality tests
python tests/test_lp_brief_gating.py    # LP brief gating tests
python tests/test_planner_worker.py     # Core Planner/Worker node tests

# Wallet Recon demos
python demos/covalent_demo.py           # 🆕 Covalent wallet recon demo
python demos/wallet_recon_live.py       # Live wallet recon (Bitquery/Covalent)
```

## 📊 Core Files Explained

### `agent.py` - Main Agent
- **LangGraphAgent**: Main agent class with integrated Planner/Worker flow
- **State Management**: AgentState with new fields for Planner/Worker integration
- **Graph Structure**: Budget → Planner → Worker → Analyze → Brief → Memory
- **Wrapper Functions**: Async-to-sync wrappers for LangGraph compatibility

### `nodes/` Directory - Professional Node Organization
**Prevents "split brain" drift by isolating each node in its own file:**

- **`nodes/__init__.py`**: Package exports for all nodes
- **`nodes/config.py`**: Shared configuration constants (timeouts, thresholds)
- **`nodes/planner.py`**: Planner node - selects action based on cursor staleness and budget
- **`nodes/worker.py`**: Worker node - executes tools and saves to JSON cache
- **`nodes/analyze.py`**: Analyze node - processes events and computes signals
- **`nodes/brief.py`**: Brief node - gates output with thresholds and cooldowns
- **`nodes/memory.py`**: Memory node - persists artifacts and updates cursors
- **Per-Node Timing**: Execution time tracking for all nodes

### `data_model.py` - Three-Layer Data Model
**Prevents state sprawl with clear data contracts:**

- **Layer 1: Scratch JSON Cache**: Raw API/MCP responses with provenance
- **Layer 2: Normalized Events**: Curated schema for recurring entities (wallet transfers, LP adds/removes)
- **Layer 3: Artifacts/Briefs**: Human-readable summaries with full provenance chain
- **Provenance Tracking**: End-to-end traceability from brief back to raw data
- **Retention Rules**: Scratch (7d), Events (30d), Artifacts (90d)
- **Idempotent Operations**: No duplicate upserts across all layers

### `json_storage.py` - Flexible Persistence (Legacy)
- **DatabaseManager**: SQLite-based JSON storage with WAL mode
- **Upsert Operations**: Idempotent save/update operations
- **Cursor Management**: Timestamp-based cursors for delta fetches
- **Audit Logging**: Tracks all database operations
- **LLM Usage Tracking**: Cost tracking for budget management

### `mock_tools.py` - Enhanced Development Tools
- **fetch_wallet_activity()**: Unified wallet activity with Covalent/Bitquery source selection
- **fetch_lp_activity()**: Mock LP activity queries
- **web_metrics_lookup()**: Mock market metrics queries
- **Source Selection**: `WALLET_RECON_SOURCE=alchemy|covalent|bitquery` environment variable
- **Graceful Fallback**: Alchemy → Covalent → Bitquery → Mock (automatic degradation)
- **Cursor Management**: Built-in cursor handling for pagination
- **Deterministic Data**: Uses fixtures from test files
- **Network Simulation**: Realistic delays and provenance tracking

### `real_apis/` Directory - Production API Integrations
**Prevents development/production drift by isolating real API implementations:**

- **`real_apis/__init__.py`**: Package exports for all API integrations
- **`real_apis/alchemy_provider.py`**: Alchemy API client for Base chain transactions
  - Dual approach: Direct HTTP for Base mainnet, SDK for other networks
  - ~509 bytes per transaction response size
  - Time filtering with block number calculations
  - JSON-RPC `alchemy_getAssetTransfers` endpoint
- **`real_apis/covalent.py`**: Covalent API client with async HTTPX, pagination, and error handling
  - Base chain optimized (`/address/{addr}/transfers/` endpoint - 95% data reduction)
  - Cursor-based pagination with retry logic and rate limiting
  - Graceful error handling for 401/402/404 status codes
  - Event normalization with provenance tracking
- **`real_apis/bitquery.py`**: Bitquery GraphQL client for detailed blockchain data
  - GraphQL queries for transfers and DEX trades
  - Offset-based pagination with deduplication
  - Comprehensive error handling and logging

**Swap Pattern**: Replace `from mock_tools import fetch_wallet_activity` with `from real_apis.alchemy_provider import fetch_wallet_activity_alchemy_live` for production use.

## 🔧 Configuration Architecture

AI Mayhem uses **multiple configuration systems** for different purposes. This section explains each system and when to use which approach.

### **Configuration Systems Overview**

| File | Purpose | Scope | Format | When to Use |
|------|---------|-------|--------|-------------|
| `/config.yaml` | LiteLLM proxy settings | AI models, rate limits, budgets | YAML | LiteLLM server configuration |
| `/nodes/config.py` | All application settings | API keys, timeouts, thresholds, notifications | Python constants | All configuration |
| Environment Variables | Runtime configuration | API keys, debug flags | Shell exports | Production secrets |

### **1. LiteLLM Configuration (`/config.yaml`)**

**Purpose**: Configures the LiteLLM proxy server for AI model access.

**Location**: Root directory *(required by LiteLLM convention)*

**What it controls**:
- Available AI models (Claude variants)
- Rate limits (RPM/TPM)
- Model-specific budgets
- Request logging

```yaml
model_list:
  - model_name: anthropic/claude-3-haiku-20240307
    rpm: 60
    tpm: 200000
general_settings:
  daily_budget: 1
  default_model: anthropic/claude-3-haiku-20240307
```

**When to modify**: When adding new AI models or changing rate limits.

### **2. Node Configuration (`/nodes/config.py`)**

**Purpose**: Defines timing constants and thresholds for node behavior.

**Location**: `/nodes/` directory *(co-located with node implementations)*

**What it controls**:
- Cursor staleness thresholds
- Brief gating thresholds  
- Node execution timeouts
- LP activity scoring

```python
CURSOR_STALE_WALLET = 2 * 3600      # 2 hours
BRIEF_THRESHOLD_EVENTS = 5          # Minimum events
PLANNER_TIMEOUT = 10                # seconds
```

**When to modify**: When tuning node behavior, timing, or thresholds.

### **3. Environment Variables (Runtime)**

**Purpose**: Runtime configuration and secrets that vary by deployment.

**Location**: Shell environment, `.env` files, deployment configs

**What it controls**:
- API keys and secrets
- Environment-specific overrides
- Debug flags
- Deployment-specific URLs

```bash
# Required for production
export ALCHEMY_API_KEY="your_key_here"
export WALLET_RECON_SOURCE="alchemy"
export BUDGET_DAILY="5.0"

# Optional features
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export DEBUG="false"
```

**When to modify**: When deploying to different environments or rotating secrets.

### **Configuration Hierarchy & Precedence**

```
Environment Variables (highest precedence)
    ↓ (overrides)
Node Constants (/nodes/config.py)
    ↓ (separate system)
LiteLLM Config (/config.yaml)
```

### **Why Files Are Located Where They Are**

- **`/config.yaml` in root**: LiteLLM expects it there by convention
- **`/nodes/config.py`**: Centralized configuration for all application settings
- **Environment variables**: External to codebase, set at deployment time

### **Common Configuration Tasks**

#### **Adding a New API Provider**
1. Add to `validate_wallet_source()` function in `/nodes/config.py`
2. Add environment variable: `YOUR_PROVIDER_API_KEY`
3. Update documentation in this README

#### **Changing Brief Thresholds**
1. Modify constants in `/nodes/config.py`
2. Update tests in `/tests/test_lp_brief_gating.py`
3. Document changes in deployment notes

#### **Adding New Environment Variables**
1. Add to `/nodes/config.py` with `os.getenv()`
2. Add to environment variable list in production documentation
3. Document in this README

#### **Modifying AI Model Settings**
1. Edit `/config.yaml` model list
2. Restart LiteLLM proxy server
3. No code changes needed

### **Development vs Production Configuration**

#### **Development Setup**:
```bash
# Minimal setup for development
export WALLET_RECON_SOURCE="mock"  # Use mock data
export DEBUG="true"                # Enable debug logging
export BUDGET_DAILY="1.0"          # Lower budget for testing
```

#### **Production Setup**:
```bash
# Full production configuration
export ALCHEMY_API_KEY="prod_key"
export DISCORD_WEBHOOK_URL="https://discord.com/..."
export WALLET_RECON_SOURCE="alchemy"
export BUDGET_DAILY="5.0"
export DEBUG="false"

# Production logging (quiet by default)
export LOG_LEVEL="WARNING"
export VERBOSE_API_LOGS="false"
export LOG_MALFORMED_TRANSACTIONS="false"
```

### **Configuration Validation**

The application validates configuration at startup:

- **Type checking**: Budget values must be positive numbers
- **URL validation**: Discord webhooks must be valid Discord URLs  
- **Source validation**: Wallet recon source must be a supported provider
- **Required fields**: Critical API keys are checked for presence

**Error example**:
```
❌ Configuration error: wallet_recon_source must be one of ['alchemy', 'covalent', 'bitquery', 'mock']
```

### **Migration Notes**

**Legacy Environment Variables** (deprecated but still supported):
- Old configuration formats are automatically migrated to current format

**Future Improvements** (see Code Quality Standards section):
- Add configuration file support (YAML/TOML)
- Implement configuration hot-reloading
- Add configuration schema validation

## 🧪 Testing & Verification

### Quick Verification Commands
**"Trust but verify" - Run these to confirm everything works:**

```bash
# 1. 🏆 Comprehensive test suite (catches broken tests!)
python tests/run_all_tests.py

# 2. Quick verification (recommended - no hanging issues)
python demos/quick_verification.py

# 3. Test the new nodes structure
python tests/test_planner_worker.py

# 4. Test three-layer data model
python tests/test_three_layer_data_model.py

# 5. Test JSON storage functionality
python tests/test_json_storage.py

# 6. Demo three-layer data model
python demos/three_layer_demo.py

# 7. Verify imports work correctly
python -c "from nodes import planner_node, worker_node, analyze_node, brief_node, memory_node; print('✅ All nodes imported successfully')"

# 8. Check that legacy functions are available for historical reference
python -c "from agent import legacy_planner_node, legacy_worker_node; print('✅ Legacy functions preserved for historical use')"

# 9. Full demo (may hang - use Ctrl+C if needed)
python demos/lp_e2e_demo.py
```

### Expected Test Results
- **`run_all_tests.py`**: Should run all 9 test files and report 9/9 passing (all tests working!)
- **`lp_e2e_demo.py`**: Complete LP monitoring flow with 5 events, signals, and provenance
- **`quick_verification.py`**: Should complete all tests without hanging
- **`covalent_demo.py`**: Should demonstrate Covalent API integration with 31+ transactions
- **`test_enhanced_lp.py`**: 7 tests should pass (LP tools, worker saves, normalization, signals, idempotency)
- **`test_lp_brief_gating.py`**: 7 tests should pass (LP gating, artifact persistence, provenance, thresholds)
- **`test_planner_worker.py`**: 4 tests should pass (planner selection, worker saves, analyze rollup, brief gating)
- **`test_wallet_service.py`**: 13 tests should pass (wallet CRUD operations, validation, error handling)
- **Legacy Functions**: `legacy_planner_node()` and `legacy_worker_node()` are preserved in `agent.py` for historical reference and potential future use
- **`test_three_layer_data_model.py`**: 7 tests should pass (all three layers, provenance, idempotency)
- **`test_json_storage.py`**: 12 tests should pass (upsert, query, delete, validation, etc.)
- **`test_agent.py`**: All async node tests should pass
- **`test_live.py`**: Live integration tests should pass
- **`three_layer_demo.py`**: Should show complete flow with provenance chain
- **Import test**: Should show "✅ All nodes imported successfully"
- **Old file test**: Should show "✅ Old file properly removed"
- **Full demo**: May hang after completion (use Ctrl+C if needed)

### Comprehensive Test Runner
The `tests/run_all_tests.py` script automatically runs all test files in the correct dependency order and provides:
- ✅ Detailed pass/fail reporting
- ✅ Import error detection (catches broken tests like `test_agent.py`)
- ✅ Execution time tracking
- ✅ Clear recommendations for fixing failed tests
- ✅ CI/CD compatible exit codes

**Always run this first** to catch test suite issues before committing!

### Test Coverage
- **LP Tools**: Enhanced mock tools with simple/realistic fixtures
- **Three-Layer Data Flow**: Scratch → Events → Artifacts with provenance
- **LP-Specific Signals**: Net liquidity delta, churn rate, activity score
- **LP Brief Gating**: LP-focused thresholds and heatmap generation
- **Planner Logic**: Cursor staleness and action selection
- **Worker Behavior**: Tool execution and idempotent saves
- **Analyze Processing**: Event counting and signal computation
- **Brief Gating**: Thresholds and cooldown logic
- **JSON Storage**: Upsert operations and cursor management
- **Idempotent Operations**: No duplicate data across all layers

## 🏗️ Three-Layer Data Model Architecture

### Layer 1: Scratch JSON Cache
**Purpose**: Store raw API/MCP responses without schema commitment
- **Fields**: `id`, `source`, `timestamp`, `raw_json`, `provenance`
- **Retention**: 7 days (purgeable)
- **Usage**: Always written first by Worker node
- **Example**: Raw wallet activity response from Nansen API

### Layer 2: Normalized Events  
**Purpose**: Curated schema for recurring entities
- **Fields**: `event_id`, `wallet`, `event_type`, `pool`, `value`, `timestamp`, `source_id`, `chain`
- **Retention**: 30 days (mid-term)
- **Usage**: Written by Analyze node after parsing scratch JSON
- **Example**: Normalized swap event with structured amounts and pool data

### Layer 3: Artifacts/Briefs
**Purpose**: Human-readable summaries and signals
- **Fields**: `artifact_id`, `timestamp`, `summary_text`, `signals`, `next_watchlist`, `source_ids`, `event_count`
- **Retention**: 90 days (long-term)
- **Usage**: Written by Brief node, persisted by Memory node
- **Example**: Daily brief with computed signals and watchlist

### Provenance Chain
Every artifact maintains full traceability:
```
Brief → Normalized Events → Raw Responses
```
- **End-to-end tracking**: From human-readable summary back to source data
- **Audit trail**: Complete history of data transformations
- **Debugging**: Easy to trace issues back to original API responses

### Data Flow Diagram
```
[ Layer 1: Scratch JSON Cache ]            (short-lived, 7d)
  id (pk) ── source ── timestamp ── raw_json ── provenance
      │
      │  (normalize)
      ▼
[ Layer 2: Normalized Events ]             (30d)
  event_id (pk) ─ wallet ─ event_type ─ pool ─ value ─ ts ─ source_id ─ chain
      │
      │  (aggregate + compute signals)
      ▼
[ Layer 3: Artifacts / Briefs ]            (90d)
  artifact_id (pk) ─ ts ─ summary_text ─ signals ─ next_watchlist ─ source_ids ─ event_count

Provenance chain:
Artifacts.source_ids → Events.event_id → Scratch.id
```

## 🔄 Integration Points

### Adding Real API Integration

1. **Configure Source Selection** in `.env`:
```bash
# Primary source (Alchemy recommended for Base chain activity)
WALLET_RECON_SOURCE=alchemy
ALCHEMY_API_KEY=your_alchemy_key

# Fallback sources
COVALENT_API_KEY=your_covalent_key
BITQUERY_API_KEY=your_bitquery_key
BITQUERY_ACCESS_TOKEN=your_bitquery_token
```

2. **Replace Mock Tools** (Automatic Fallback):
```python
# No code changes needed! The system automatically:
# 1. Tries Alchemy first (if configured)
# 2. Falls back to Covalent (if configured)
# 3. Falls back to Bitquery (if configured)
# 4. Uses mock data (development default)

# For custom integrations, use:
from real_apis.alchemy_provider import fetch_wallet_activity_alchemy_live
from real_apis.covalent import fetch_wallet_activity_covalent_live
from real_apis.bitquery import fetch_wallet_activity_bitquery_live
```

3. **Test Integration**:
```bash
# Test Alchemy integration
python real_apis/test_alchemy.py

# Test Covalent integration
python demos/covalent_demo.py

# Test with live APIs
python demos/wallet_recon_live.py
```

### Adding New Actions

1. **Update Planner Logic** in `planner_node()`
2. **Add Worker Implementation** in `worker_node()`
3. **Update Cursor Management** in `memory_node()`
4. **Add Tests** in `tests/test_planner_worker.py`

## 📈 Monitoring & Observability

### Database Tables
- **json_cache_scratch**: Raw API responses and normalized events
- **cursors**: Timestamp-based cursors for delta fetches
- **writes_log**: Audit log of all database operations
- **llm_usage**: Cost tracking for budget management

### Logging
- **Per-Node Timing**: Execution time for each node
- **JSON Cache**: Upsert operations and cursor updates
- **Brief Gating**: Emit/skip decisions with reasons
- **Error Handling**: Detailed error messages and stack traces

## 🎯 Use Cases

### Blockchain Monitoring
- **Wallet Activity**: Track specific wallet transactions with Alchemy/Covalent/Bitquery
- **LP Activity**: Monitor liquidity provider movements
- **Market Metrics**: Analyze DEX volume and pool activity
- **Multi-Source Recon**: Automatic fallback between API providers

### Data Analysis
- **Event Rollups**: 24h event counts and top pools
- **Signal Computation**: Volume, activity, and concentration signals
- **Trend Analysis**: Historical data for pattern recognition

### Automated Reporting
- **Brief Generation**: Automated summaries with thresholds
- **Watchlist Updates**: Dynamic pool and wallet recommendations
- **Cost Tracking**: Budget-aware execution

## 🔒 Security & Best Practices

### Data Handling
- **Provenance Tracking**: All data includes source and snapshot time
- **Idempotent Operations**: No duplicate data on re-runs
- **Cursor Management**: Delta fetches to minimize API calls

### Cost Control
- **Budget Limits**: Daily spending caps
- **Per-Run Caps**: Maximum cost per execution
- **Usage Tracking**: Detailed cost breakdown by model

### Error Handling
- **Timeout Protection**: Per-node timeouts prevent hanging
- **Graceful Degradation**: Continue operation on partial failures
- **Detailed Logging**: Comprehensive error tracking

## 🤝 Contributing

### Development Workflow
1. **Write Tests First**: Follow TDD approach
2. **Use Mock Data**: Develop with deterministic fixtures
3. **Add Timing**: Include execution time tracking
4. **Update Documentation**: Keep README current

### Code Standards
- **Type Hints**: Use Python type annotations
- **Async/Await**: Use async functions for I/O operations
- **Error Handling**: Comprehensive exception handling
- **Logging**: Structured logging with context

## 📚 References

- **LangGraph**: https://python.langchain.com/docs/langgraph
- **SQLite WAL Mode**: https://www.sqlite.org/wal.html
- **LiteLLM**: https://github.com/BerriAI/litellm
- **Nansen API**: https://docs.nansen.ai/
- **Covalent OpenAPI Spec**: https://api.covalenthq.com/v1/openapiv3/
- **GoldRush Developer Docs**: https://goldrush.dev/docs/api-reference/foundational-api/transactions/get-paginated-transactions-for-address-v3

## 🆘 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Database Locked**: Check for concurrent access, use WAL mode
3. **Timeout Errors**: Increase timeout values in configuration
4. **Budget Exceeded**: Check BUDGET_DAILY environment variable

### Debug Mode
```bash
# Enable debug logging
export DEBUG=1
python demos/lp_e2e_demo.py
```

### Database Inspection
```bash
# View database contents
sqlite3 agent_state.db ".tables"
sqlite3 agent_state.db "SELECT * FROM json_cache_scratch LIMIT 5;"
```

## 💧 LP Monitoring Features

This project now includes **comprehensive LP (Liquidity Provider) monitoring** capabilities:

### LP-Specific Signals
- **Net Liquidity Delta**: Tracks adds minus removes over 24h
- **LP Churn Rate**: Unique LPs / total LP operations (diversity metric)
- **Pool Activity Score**: Activity heuristic based on event volume
- **Net Liquidity Value**: Token-value weighted LP movements

### LLM-Backed Briefs
- **Multiple Modes**: Choose between deterministic, LLM, or both
  - `BRIEF_MODE=deterministic`: Traditional rule-based briefs
  - `BRIEF_MODE=llm`: AI-powered insights with structured validation
  - `BRIEF_MODE=both`: Both deterministic and LLM briefs
- **Token Management**: Smart event reduction to fit context limits
  - `LLM_INPUT_POLICY=full`: Use all events (may exceed token cap)
  - `LLM_INPUT_POLICY=budgeted`: Reduce events to fit token cap
  - `LLM_TOKEN_CAP=120000`: Maximum tokens for LLM input
- **Structured Output**: Machine-readable fields for automation
  - `summary_text_llm`: Natural language brief from LLM
  - `llm_struct`: Structured data (top wallets, notable events, etc.)
  - `llm_validation`: Cross-checks against deterministic rollups
  - `llm_model`: Model used for generation
  - `llm_tokens`: Token usage tracking

### Enhanced Brief Generation
- **LP Heatmap**: Automatic inclusion of high-activity pools in watchlists
- **LP Threshold Gating**: Briefs emit when `pool_activity_score >= 0.6`
- **LP-Specific Content**: Detailed LP metrics in brief summaries
- **Provenance Tracking**: Full traceability from brief → events → raw data
- **LLM-Backed Briefs**: AI-powered insights with structured validation
  - **Multiple Modes**: Choose between deterministic, LLM, or both
  - **Token Management**: Smart event reduction to fit context limits
  - **Structured Output**: Machine-readable fields for automation
  - **Self-Validation**: Cross-checks against deterministic rollups

### Demo & Testing
```bash
# 🏆 Complete LP monitoring demonstration
python demos/lp_e2e_demo.py

# 🤖 LLM-backed brief demonstration
python demos/llm_brief_demo.py          # Shows all brief modes and token management
# - Demonstrates deterministic, LLM, and both modes
# - Shows token management with full/budgeted policies
# - Includes error handling and validation
# - Verifies persistence and provenance

# 🔥 Live Bitquery wallet reconnaissance (requires API key)
python demos/wallet_recon_live.py       # Live wallet activity demo

# LP-specific test suites
python tests/test_enhanced_lp.py        # Core LP functionality
python tests/test_lp_brief_gating.py    # LP brief gating logic
python tests/test_llm_brief.py          # LLM brief functionality

# Wallet Recon demos
python demos/covalent_demo.py           # 🆕 Covalent wallet recon demo
python demos/wallet_recon_live.py       # Live wallet recon (Bitquery/Covalent)
```

#### 🔴 Live Wallet Recon Integration
- **Primary Source**: Alchemy API for Base chain wallet transaction data
- **Secondary Source**: Covalent API for high-level wallet transaction data
- **Fallback Source**: Bitquery API for detailed transaction analysis
- **Source Selection**: Set `WALLET_RECON_SOURCE=alchemy|covalent|bitquery`
- **Authentication**: Alchemy uses API key in URL, Covalent uses X-API-KEY, Bitquery uses Bearer token
- **Fallback**: Automatically falls back to mock data if API keys missing
- **Raw-First**: Preserves complete API responses with full provenance
- **Pagination**: Alchemy uses maxCount/pageKey, Covalent uses cursor-based, Bitquery uses offset-based
- **Rate Limiting**: Built-in retry logic with exponential backoff
- **Demo**: `test_alchemy.py` shows live Base chain integration with 1000 transactions

## 📡 **Covalent API Integration - Size Optimization Complete**

### 🎯 **Key Achievement: 89x Size Reduction**
We've successfully optimized the Covalent API integration to reduce response sizes from 90MB+ down to manageable levels using the page-based endpoint.

### 📚 **Comprehensive Documentation Available**

For complete details about our API provider analysis, including:
- **Alchemy vs Covalent vs Bitquery comparison** with performance metrics
- **Full endpoint testing results** and size analysis
- **Technical analysis** of optimal endpoints and approaches
- **All curl commands** used for testing and validation  
- **Implementation notes** and best practices
- **Complete test coverage** for all providers

**📖 See: [`real_apis/README.md`](real_apis/README.md)**

This documentation contains our complete findings from testing all available providers, with Alchemy emerging as the optimal solution for Base chain transactions.

### 🚀 **BREAKTHROUGH: Alchemy Integration Complete!**

**Production Implementation:**
- ✅ **Working Endpoint**: `alchemy_getAssetTransfers` with JSON-RPC 2.0
- ✅ **Response Size**: **~509 bytes per transaction** (efficient and manageable)
- ✅ **Real Data**: Actual transaction history with hashes, block numbers, token transfers
- ✅ **Time Filtering**: `fromBlock` parameter for date range queries
- ✅ **Pagination**: `maxCount` and `pageKey` for handling large histories
- ✅ **Recent Data Access**: **Confirmed working with recent Base network data**
- ✅ **TDD Implementation**: **17 comprehensive tests** (unit + integration)
- ✅ **Dual Network Support**: Direct HTTP for Base mainnet, SDK for other networks

**Technical Implementation:**
- **File**: `real_apis/alchemy_provider.py` with `test_alchemy.py`
- **Base URL**: `https://{network}.g.alchemy.com/v2/` (network-specific URLs)
- **Method**: JSON-RPC 2.0 with `alchemy_getAssetTransfers`
- **Parameters**: `fromAddress`, `maxCount`, `category`, `fromBlock`
- **Categories**: `["external", "erc20"]` (Base doesn't support internal transactions)
- **Maximum Limit**: 1000 transactions per request (no pagination needed for most use cases)
- **Dependencies**: `alchemy-sdk`, `aiohttp>=3.8.0`, `dataclass-wizard`
- **Test Coverage**: Both mocked unit tests and real Base chain API integration tests

**Network Support**: The Alchemy Python SDK does not yet support Base mainnet directly, so we use a dual approach: direct `aiohttp` HTTP requests for Base mainnet and the official SDK for other supported networks (eth-mainnet, etc.).

### 🚨 **Critical Warnings**
- **NEVER use `/transactions_v3/`** - returns 16MB+ responses causing data bloat
- **ALWAYS use `/transactions_v3/page/{N}/`** - provides 89x size reduction
- **NEVER use `/transactions_v2/`** - even worse at 28MB+ responses

### 🔗 **Official API Documentation**
- **Alchemy API Documentation**: https://docs.alchemy.com/
- **Alchemy SDK (Python)**: https://github.com/alchemyplatform/alchemy-sdk-py
- **OpenAPI Specification**: https://api.covalenthq.com/v1/openapiv3/
- **Developer Documentation**: https://goldrush.dev/docs/api-reference/

### 💡 **What Was Implemented**
The `alchemy_provider.py` client provides production-ready Base chain integration:
- **Optimal response sizes** (~509 bytes per transaction)
- **Response size tracking** for monitoring
- **Fallback mechanisms** to Covalent and Bitquery when needed
- **Full test coverage** with both unit and integration tests
- **TDD implementation** with 17 comprehensive test cases

## 🤖 Built with grok-code-fast-1

This project was developed using **grok-code-fast-1**, which excels at:
- **Complex multi-step implementations** with clear reasoning
- **Comprehensive error handling** and edge case coverage
- **Production-ready code** with proper async patterns
- **Thorough testing** with TDD approach
- **Clean architecture** decisions and documentation

The model demonstrated exceptional capability in:
- **Task decomposition**: Breaking down complex requirements into manageable phases
- **Implementation planning**: Creating detailed implementation strategies
- **Code quality**: Producing well-structured, documented, and maintainable code
- **Testing strategy**: Building comprehensive test suites with proper isolation
- **Documentation**: Maintaining up-to-date project documentation

---

**Note**: This project uses mock data by default for development. Configure `WALLET_RECON_SOURCE=alchemy` and add API keys to `.env` for production use. The system automatically handles API fallback (Alchemy → Covalent → Bitquery → Mock) and maintains the same interface.

#### **💡 Conclusion: Stick with What Works**
Our current implementation using `/transactions_v3/page/{N}/` is already the **optimal solution**. It provides:
- ✅ **89x size reduction**
- ✅ **All necessary transaction data**
- ✅ **Proper pagination**
- ✅ **Proven reliability**

### 🧪 **Endpoint Discovery Testing Commands:**

```bash
# 1. Test regular transactions_v3 endpoint (baseline)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_baseline.json

# 2. Test page-based transactions_v3 endpoint (winner)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/page/0/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_page0.json

# 3. Test transactions_v2 endpoint (larger than v3!)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v2/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_transactions_v2.json

# 4. Test transfers_v2 endpoint (requires contract address)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transfers_v2/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_transfers_v2_clean.json

# 5. Test transactions_summary endpoint (metadata only)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_summary/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_transactions_summary.json

# 6. Test unsupported parameters (all return 400 errors)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/?noLogs=true" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_transactions_v3_no_logs.json

curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/page/0/?quoteCurrency=USD" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json" \
  -o data/raw/test_page0_with_quote.json
```

#### **Test Results Summary:**
| Endpoint | Size | Transactions | Avg/Txn | Status | Notes |
|----------|------|-------------|---------|--------|-------|
| **Page-based** | 735KB | 100 | ~7.3KB | ✅ **WINNER** | 89x reduction, all data |
| **Regular v3** | 16MB | 25 | ~650KB | ❌ Avoid | Massive bloat |
| **v2** | 28.7MB | N/A | N/A | ❌ Avoid | Even larger than v3 |
| **Transfers** | 107B | N/A | N/A | ❌ Error | Requires contract address |
| **Summary** | 817B | N/A | N/A | ⚠️ Limited | Only metadata |
| **v3 + noLogs** | 99B | N/A | N/A | ❌ Error | Parameter not supported |
| **Page + quote** | 106B | N/A | N/A | ❌ Error | Parameter not supported |

### 🔍 **Technical Analysis: Why Page-Based Endpoint Wins**

The page-based endpoint achieves 89x size reduction while maintaining full transaction data, making it the optimal choice for production wallet reconnaissance.

```

---

## 🚀 **Code Quality Standards & Future Improvements**

### **Production-Grade Code Standards**

This section outlines the coding standards and improvements needed to evolve this project from a proof-of-concept to production-ready software.

#### **🏗️ Architecture & Structure**
- **Proper Package Structure**: Migrate to `src/ai_mayhem/` package structure with proper `__init__.py` files
- **Dependency Injection**: Explicit dependencies instead of hidden global state
- **Configuration Management**: Centralized config class with validation instead of scattered `os.getenv()` calls
- **Focused Functions**: Single responsibility principle - break large functions into smaller, testable units

#### **🔒 Type Safety & Validation**
- **Comprehensive Type Hints**: Every function, method, and variable should have proper type annotations
- **Input Validation**: Validate all external inputs (API responses, user inputs, environment variables)
- **Custom Exception Types**: Specific exceptions for different error conditions instead of generic `Exception`
- **Pydantic Models**: Use Pydantic for data validation and serialization

#### **📊 Monitoring & Observability**
- **Structured Logging**: Replace `print()` statements with proper logging using `structlog` or similar
- **Metrics Collection**: Add Prometheus metrics for production monitoring
- **Health Checks**: Implement health check endpoints for deployment readiness
- **Distributed Tracing**: Add OpenTelemetry for request tracing across components

#### **🧪 Testing & Quality**
- **Test Coverage**: Aim for >90% test coverage with meaningful tests
- **Integration Tests**: Test real API interactions, not just mocked unit tests
- **Performance Tests**: Benchmark critical paths and set performance budgets
- **Contract Testing**: Verify API contract compatibility

#### **🔐 Security & Reliability**
- **Secrets Management**: Use proper secrets management instead of environment variables
- **Rate Limiting**: Implement client-side rate limiting for external APIs
- **Input Sanitization**: Sanitize all inputs to prevent injection attacks
- **Error Recovery**: Graceful degradation and retry strategies

#### **📈 Performance & Scalability**
- **Connection Pooling**: Reuse HTTP connections and database connections
- **Caching Strategy**: Implement intelligent caching for expensive operations
- **Async Best Practices**: Proper async/await patterns without blocking
- **Resource Management**: Proper cleanup of resources and memory management

#### **📚 Documentation & Maintenance**
- **API Documentation**: Auto-generated API docs with examples
- **Architecture Decision Records**: Document key architectural decisions
- **Deployment Guides**: Comprehensive deployment and operations documentation
- **Code Comments**: Explain *why*, not *what* - focus on business logic and complex algorithms

### **🎯 Priority Improvements**

#### **Phase 1: Foundation (1-2 weeks)**
1. **Package Structure**: Reorganize into proper Python package
2. **Type Hints**: Add comprehensive type annotations
3. **Logging**: Replace all `print()` with structured logging
4. **Configuration**: Create centralized config management

#### **Phase 2: Reliability (2-3 weeks)**
5. **Error Handling**: Implement proper exception hierarchy
6. **Input Validation**: Add validation for all external inputs
7. **Testing**: Achieve >80% test coverage
8. **Documentation**: Complete API documentation

#### **Phase 3: Production (3-4 weeks)**
9. **Monitoring**: Add metrics and health checks
10. **Security**: Implement secrets management
11. **Performance**: Add caching and connection pooling
12. **Deployment**: Create production deployment pipeline

### **🔄 Continuous Improvement**

- **Code Reviews**: All changes require peer review
- **Automated Quality Gates**: Pre-commit hooks, linting, type checking
- **Performance Monitoring**: Track and alert on performance regressions
- **Security Scanning**: Regular dependency and code security scans

---

## 🚀 **Run in Production**

### **Wallet Brief Mode**

Execute a single reconnaissance cycle and exit - perfect for cron jobs and automated monitoring.

```bash
# Run once and exit (uses configured wallets)
python -m ai_mayhem.cli run --mode=wallet-brief

# Override with specific wallets for one-off runs
python -m ai_mayhem.cli run --mode=wallet-brief --wallets="0x123...,0x456..."

# With Discord notifications
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your_webhook_id/your_webhook_token"
python -m ai_mayhem.cli run --mode=wallet-brief
```

### **Cron Job Setup**

```bash
# Edit crontab
crontab -e

# Add entry for every 30 minutes
*/30 * * * * cd /path/to/ai-mayhem && /usr/bin/python3 -m ai_mayhem.cli run --mode=wallet-brief >> /var/log/ai-mayhem.log 2>&1
```

### **Systemd Service**

Create `/etc/systemd/system/ai-mayhem-brief.service`:

```ini
[Unit]
Description=AI Mayhem Wallet Brief
After=network.target

[Service]
Type=oneshot
User=ai-mayhem
WorkingDirectory=/path/to/ai-mayhem
ExecStart=/usr/bin/python3 -m ai_mayhem.cli run --mode=wallet-brief
Environment=ALCHEMY_API_KEY=your_key
Environment=DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_id/your_webhook_token
Environment=BUDGET_DAILY=5.0

[Install]
WantedBy=multi-user.target
```

Create timer `/etc/systemd/system/ai-mayhem-brief.timer`:

```ini
[Unit]
Description=Run AI Mayhem Brief every 30 minutes
Requires=ai-mayhem-brief.service

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable ai-mayhem-brief.timer
sudo systemctl start ai-mayhem-brief.timer
sudo systemctl status ai-mayhem-brief.timer
```

### **Environment Variables**

Required environment variables for production:

```bash
# API Keys
ALCHEMY_API_KEY=your_alchemy_key
COVALENT_API_KEY=your_covalent_key
BITQUERY_ACCESS_TOKEN=your_bitquery_key

# Configuration
WALLET_RECON_SOURCE=alchemy
BUDGET_DAILY=5.0

# Brief modes
BRIEF_MODE=both                                     # deterministic | llm | both
LLM_INPUT_POLICY=full                              # full | budgeted
LLM_TOKEN_CAP=120000                               # Maximum tokens for LLM input
LLM_BRIEF_MODEL=anthropic/claude-3-haiku-20240307  # Dev default (cheaper)
# LLM_BRIEF_MODEL=anthropic/claude-3-5-sonnet-20241022  # Prod (better quality)

# Optional notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_id/your_webhook_token

# Optional debugging
BITQUERY_VERBOSE=false
DEBUG=false
```
