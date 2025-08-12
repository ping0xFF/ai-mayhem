# LangGraph AI Agent Scaffold

A simple but extensible LangGraph-based AI agent system with persistent state and local LLM integration.

## Features

- **Simple Graph Structure**: Planner → Worker nodes with conditional routing
- **Persistent State**: SQLite database for resuming sessions across restarts
- **Local LLM Integration**: Uses your existing LiteLLM proxy setup
- **Model Flexibility**: Different models for planning vs execution
- **Easy Extension**: Clean architecture for adding more nodes and capabilities

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure your LiteLLM proxy is running:
```bash
litellm --config config.yaml --port 8000
```

3. Set environment variables (optional):
```bash
export LITELLM_URL="http://localhost:8000"
export PLANNER_MODEL="anthropic/claude-3-haiku-20240307"
export WORKER_MODEL="anthropic/claude-3-5-sonnet-20240620"
```

## Usage

### Basic Usage

Run the main agent:
```bash
python langgraph_agent.py
```

### CLI Interface

Start a new goal:
```bash
python agent_cli.py --goal "Create a simple web scraper for news articles" --thread my-project
```

Resume an existing session:
```bash
python agent_cli.py --resume --thread my-project
```

List all threads:
```bash
python agent_cli.py --list
```

### Testing

Run the test script to see the agent in action:
```bash
python test_langgraph.py
```

## Architecture

### State Management
- **AgentState**: Contains goal, plan, current step, completed actions, and messages
- **SQLite Persistence**: Automatic state saving/loading using LangGraph's checkpointer
- **Thread-based Sessions**: Multiple concurrent conversations with unique IDs

### Graph Nodes
- **Planner Node**: Analyzes goals and creates actionable step-by-step plans
- **Worker Node**: Executes individual steps, with smart model selection
- **Conditional Routing**: Automatically determines next action based on current state

### Model Strategy
- **Planner Model**: Fast, efficient model (Haiku) for planning tasks
- **Worker Model**: More capable model (Sonnet) for complex execution tasks
- **Automatic Selection**: Uses appropriate model based on task complexity

## Files

- `langgraph_agent.py` - Main agent implementation
- `agent_cli.py` - Command-line interface
- `test_langgraph.py` - Test script with examples
- `agent_state.db` - SQLite database for persistent state
- `logs/langgraph-*.jsonl` - Daily log files with all LLM interactions

## Extension Points

The scaffold is designed to be easily extensible:

1. **Add New Nodes**: Create functions that take/return `AgentState`
2. **Cost Controls**: Add budget tracking in the state
3. **Multi-Agent**: Use different thread IDs for different agent types
4. **External Tools**: Add tool-calling capabilities to worker nodes
5. **Human-in-the-Loop**: Add approval nodes for high-risk actions

## Example Session

```python
agent = LangGraphAgent()

# Start new goal
state = await agent.run(
    goal="Research and implement a file monitoring system",
    thread_id="file-monitor-project"
)

# Later, resume the same session
state = await agent.resume(thread_id="file-monitor-project")
```

The agent will automatically:
1. Break down the goal into actionable steps
2. Execute each step using appropriate models
3. Save progress to SQLite
4. Resume from where it left off if restarted
