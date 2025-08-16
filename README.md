# AI Agent Scaffold

A professional LangGraph + LangChain agent scaffold with intelligent model routing and cost tracking.

## Architecture

This project uses **both** LangGraph and LangChain:
- **LangGraph**: Workflow orchestration (planner → worker → persistence)
- **LangChain**: LLM integration (replacing raw HTTP calls)

## File Structure

### Core Agent Files
- `agent.py` - Main LangGraph agent with planner/worker nodes
- `llm_client.py` - Professional LangChain LLM client with model routing
- `cli.py` - Command-line interface for the agent

### Configuration
- `config.yaml` - LiteLLM configuration
- `requirements.txt` - Python dependencies

### Testing
- `tests/` - Test suite
  - `test_agent.py` - Unit and integration tests (mocked)
  - `test_live.py` - Automated live testing with multiple goals
- `agent.py` - Interactive demo with single goal and detailed output

### Data
- `logs/` - LLM call logs and cost tracking
- `agent_state.db` - SQLite persistence for agent state

## Key Features

✅ **Professional LLM Integration**: LangChain's ChatOpenAI + LiteLLM  
✅ **Intelligent Model Routing**: Haiku for simple tasks, Sonnet for complex  
✅ **Cost Tracking**: Real-time cost estimation and reporting  
✅ **Persistence**: SQLite-based state management  
✅ **Extensible**: Easy to add new nodes and capabilities  

## Usage

```bash
# Interactive demo (single goal, detailed output)
python agent.py

# CLI interface
python cli.py

# Run unit tests (mocked)
python tests/test_agent.py

# Run live tests (multiple goals, automated)
python tests/test_live.py

# Test LLM client
python llm_client.py
```

## Model Routing Logic

The agent automatically selects models based on task complexity:
- **Haiku**: Planning, simple tasks (<180 chars, no technical keywords)
- **Sonnet**: Complex tasks, technical work, security analysis

## Cost Tracking

Real-time cost estimation:
- Haiku: $0.25/1M input, $1.25/1M output
- Sonnet: $3.00/1M input, $15.00/1M output
