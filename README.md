# AI Mayhem - LangGraph Agent with Planner/Worker Integration

A sophisticated LangGraph-based AI agent system with controlled autonomy, featuring a Planner/Worker pattern for blockchain data monitoring and analysis.

## 🎯 Project Overview

This project implements a **controlled autonomy** system that augments the existing Recon → Analyze → Brief loop with a minimal Planner/Worker pair. The system can choose between exploration paths (web/subgraph lookups) and the recon backbone, while keeping outputs stable and costs bounded.

### Key Features

- **Controlled Autonomy**: Planner selects actions based on cursor staleness and budget
- **Flexible JSON Storage**: SQLite-based persistence for arbitrary API responses
- **Per-Node Timing**: Execution time tracking for performance monitoring
- **Idempotent Operations**: No duplicate data on re-runs
- **Budget Awareness**: Cost tracking and limits
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
├── planner_worker.py        # Planner/Worker nodes implementation
├── json_storage.py          # Flexible JSON persistence layer
├── mock_tools.py            # Mock implementations of blockchain tools
├── llm_client.py            # LLM client with cost tracking
├── agent_state.db           # SQLite database (persistent state)
├── requirements.txt         # Python dependencies
├── config.yaml              # LiteLLM configuration
├── demos/
│   └── planner_worker_demo.py  # Integration demo
├── tests/
│   ├── test_planner_worker.py  # TDD tests for Planner/Worker
│   ├── test_json_storage.py    # JSON storage tests
│   └── test_*.py               # Other test files
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

# LiteLLM settings (if using local proxy)
LITELLM_URL=http://localhost:8000
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=http://localhost:8000

# Nansen API (for real data)
NANSEN_API_KEY=your_nansen_key_here
```

### 3. Run Demo

```bash
# Run the integrated Planner/Worker demo
python demos/planner_worker_demo.py

# Run tests
python tests/test_planner_worker.py
```

## 📊 Core Files Explained

### `agent.py` - Main Agent
- **LangGraphAgent**: Main agent class with integrated Planner/Worker flow
- **State Management**: AgentState with new fields for Planner/Worker integration
- **Graph Structure**: Budget → Planner → Worker → Analyze → Brief → Memory
- **Wrapper Functions**: Async-to-sync wrappers for LangGraph compatibility

### `planner_worker.py` - Planner/Worker Nodes
- **planner_node()**: Selects action based on cursor staleness and budget
- **worker_node()**: Executes tools and saves to JSON cache
- **analyze_node()**: Processes events and computes signals
- **brief_node()**: Gates output with thresholds and cooldowns
- **memory_node()**: Persists artifacts and updates cursors
- **Per-Node Timing**: Execution time tracking for all nodes

### `json_storage.py` - Flexible Persistence
- **DatabaseManager**: SQLite-based JSON storage with WAL mode
- **Upsert Operations**: Idempotent save/update operations
- **Cursor Management**: Timestamp-based cursors for delta fetches
- **Audit Logging**: Tracks all database operations
- **LLM Usage Tracking**: Cost tracking for budget management

### `mock_tools.py` - Development Tools
- **fetch_wallet_activity()**: Mock wallet activity queries
- **fetch_lp_activity()**: Mock LP activity queries
- **web_metrics_lookup()**: Mock market metrics queries
- **Deterministic Data**: Uses fixtures from test files
- **Network Simulation**: Realistic delays and provenance tracking

## 🔧 Configuration

### Cursor Staleness Thresholds
```python
CURSOR_STALE_WALLET = 2 * 3600    # 2 hours
CURSOR_STALE_LP = 6 * 3600        # 6 hours  
CURSOR_STALE_EXPLORE = 24 * 3600  # 24 hours
```

### Brief Gating
```python
BRIEF_COOLDOWN = 6 * 3600         # 6 hours
BRIEF_THRESHOLD_EVENTS = 5        # Minimum events
BRIEF_THRESHOLD_SIGNAL = 0.6      # Minimum signal strength
```

### Per-Node Timeouts
```python
PLANNER_TIMEOUT = 10   # seconds
WORKER_TIMEOUT = 20    # seconds
ANALYZE_TIMEOUT = 15   # seconds
BRIEF_TIMEOUT = 10     # seconds
MEMORY_TIMEOUT = 10    # seconds
```

## 🧪 Testing

### Run All Tests
```bash
# Planner/Worker tests
python tests/test_planner_worker.py

# JSON storage tests
python tests/test_json_storage.py

# Other tests
python tests/test_*.py
```

### Test Coverage
- **Planner Logic**: Cursor staleness and action selection
- **Worker Behavior**: Tool execution and idempotent saves
- **Analyze Processing**: Event counting and signal computation
- **Brief Gating**: Thresholds and cooldown logic
- **JSON Storage**: Upsert operations and cursor management

## 🔄 Integration Points

### Adding Real API Integration

1. **Replace Mock Tools**:
```python
# In planner_worker.py, change:
from mock_tools import fetch_wallet_activity, fetch_lp_activity, web_metrics_lookup
# To:
from real_apis import fetch_wallet_activity, fetch_lp_activity, web_metrics_lookup
```

2. **Add API Keys** to `.env`:
```bash
NANSEN_API_KEY=your_key
ETHERSCAN_API_KEY=your_key
```

3. **Implement Real Tools** with same interface as mock tools

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
- **Wallet Activity**: Track specific wallet transactions
- **LP Activity**: Monitor liquidity provider movements
- **Market Metrics**: Analyze DEX volume and pool activity

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
python demos/planner_worker_demo.py
```

### Database Inspection
```bash
# View database contents
sqlite3 agent_state.db ".tables"
sqlite3 agent_state.db "SELECT * FROM json_cache_scratch LIMIT 5;"
```

---

**Note**: This project uses mock data by default for development. Replace `mock_tools.py` imports with real API implementations for production use.
