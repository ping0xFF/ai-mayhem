#!/usr/bin/env python3
"""
Simple LangGraph scaffold for AI agents with persistent state.

Features:
- Planner step that figures out next action toward a goal
- Worker step that executes the action (can use different models)  
- SQLite persistence so it can resume where it left off
- Uses local LiteLLM endpoint for model swapping
- Easy to extend with more nodes
"""

import json
import os
import datetime
import asyncio
import sqlite3
import aiosqlite
from typing import Dict, Any, Optional, List, TypedDict
from pathlib import Path

import requests
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


# Configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:8000")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "anthropic/claude-3-haiku-20240307")
WORKER_MODEL = os.getenv("WORKER_MODEL", "anthropic/claude-3-5-sonnet-20240620")  # More capable for complex tasks

# Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agent_state.db"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class AgentState(TypedDict):
    """State that gets passed between nodes in the graph."""
    goal: str
    plan: List[str]
    current_step: int
    completed_actions: List[Dict[str, Any]]
    messages: List[BaseMessage]
    status: str  # planning, working, completed, failed


def call_llm(prompt: str, model: str = PLANNER_MODEL, max_tokens: int = 400) -> tuple[str, Dict[str, Any]]:
    """Call the LiteLLM endpoint."""
    response = requests.post(
        f"{LITELLM_URL}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    
    message = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    
    # Log the interaction
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "model": model,
        "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
        "response": message[:200] + "..." if len(message) > 200 else message,
        "usage": usage
    }
    
    log_path = LOGS_DIR / f"langgraph-{datetime.date.today().isoformat()}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return message, usage


def planner_node(state: AgentState) -> AgentState:
    """
    Planner node: Analyzes the goal and creates/updates the plan.
    """
    print(f"  Planning: {state['goal']}")
    
    # If we already have a plan and haven't completed it, continue working
    if state["plan"] and state["current_step"] < len(state["plan"]):
        print(f"    Plan has {len(state['plan']) - state['current_step']} steps remaining (completed {len(state['completed_actions'])})")
        return {**state, "status": "working"}
    
    # Create a new plan
    prompt = f"""
Create a step-by-step plan to accomplish this goal: {state['goal']}

Break it down into 3-5 specific, actionable steps. Return ONLY a JSON array of strings.

Example format: ["Step 1: Research X", "Step 2: Create Y", "Step 3: Test Z"]

Goal: {state['goal']}
"""
    
    # If there is no plan or we've completed the current plan, try to create a new one
    try:
        response, usage = call_llm(prompt, model=PLANNER_MODEL)
        plan = json.loads(response)
        
        if not isinstance(plan, list):
            raise ValueError("Plan must be a list")
            
        print(f"    Created plan with {len(plan)} steps")
        
        # Add AI message to conversation history documenting the created plan
        new_messages = state["messages"] + [
            AIMessage(content=f"Created plan: {json.dumps(plan, indent=2)}")
        ]
        
        # Return updated state with new plan, reset step counter, add messages, and set status to working
        return {
            **state,
            "plan": plan,
            "current_step": 0,
            "messages": new_messages,
            "status": "working"
        }
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"    Failed to parse plan from response")
        error_msg = f"Failed to create plan: {str(e)}"
        
        return {
            **state,
            "status": "failed",
            "messages": state["messages"] + [AIMessage(content=error_msg)]
        }


def worker_node(state: AgentState) -> AgentState:
    """
    Worker node: Executes the current step in the plan.
    """
    # Check if we've completed all steps
    if state["current_step"] >= len(state["plan"]):
        print(f"  All steps completed!")
        return {**state, "status": "completed"}
    
    # Get the current step
    current_step_description = state["plan"][state["current_step"]]
    step_number = state["current_step"] + 1
    
    print(f"  Executing step {step_number}: {current_step_description}")
    
    # Create prompt for the worker
    context = f"""
Goal: {state['goal']}
Current step ({step_number}/{len(state['plan'])}): {current_step_description}

Previous completed actions:
{json.dumps([action['description'] for action in state['completed_actions']], indent=2) if state['completed_actions'] else 'None'}

Execute this step and provide a detailed description of what you accomplished.
Be specific about what was done and any important findings or results.
"""
    
    try:
        # Use more capable model for execution
        response, usage = call_llm(context, model=WORKER_MODEL, max_tokens=600)
        
        # Record the completed action
        completed_action = {
            "step": state["current_step"],
            "description": current_step_description,
            "result": response,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "usage": usage
        }
        
        # Update state
        new_completed_actions = state["completed_actions"] + [completed_action]
        new_step = state["current_step"] + 1
        
        print(f"    Step completed. Result: {response[:50]}...")
        
        # Add the work message
        new_messages = state["messages"] + [
            AIMessage(content=f"Completed step {step_number}: {response}")
        ]
        
        # Determine next status
        if new_step >= len(state["plan"]):
            next_status = "completed"
        else:
            next_status = "working"
        
        return {
            **state,
            "current_step": new_step,
            "completed_actions": new_completed_actions,
            "messages": new_messages,
            "status": next_status
        }
        
    except Exception as e:
        error_msg = f"Failed to execute step {step_number}: {str(e)}"
        print(f"    Error: {error_msg}")
        
        return {
            **state,
            "status": "failed",
            "messages": state["messages"] + [AIMessage(content=error_msg)]
        }


def should_continue(state: AgentState) -> str:
    """Determine which node to go to next based on current status."""
    if state["status"] == "planning":
        return "plan"
    elif state["status"] == "working":
        return "work"
    else:  # completed or failed
        return END


class LangGraphAgent:
    """Main agent class that manages the LangGraph workflow."""
    
    def __init__(self):
        # Set up the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("plan", planner_node)
        workflow.add_node("work", worker_node)
        
        # Set entry point
        workflow.set_entry_point("plan")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "plan",
            should_continue,
            {
                "plan": "plan",
                "work": "work",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "work",
            should_continue,
            {
                "plan": "plan",
                "work": "work", 
                END: END
            }
        )
        
        # Set up SQLite persistence
        self.db_path = str(DB_PATH)
        self._checkpointer_cache = None
        self.app = workflow.compile()
        
    async def _get_checkpointer(self):
        """Get or create the async checkpointer."""
        if self._checkpointer_cache is None:
            conn = await aiosqlite.connect(self.db_path)
            self._checkpointer_cache = AsyncSqliteSaver(conn)
            # Recompile the app with checkpointer
            workflow = StateGraph(AgentState)
            workflow.add_node("plan", planner_node)
            workflow.add_node("work", worker_node)
            workflow.set_entry_point("plan")
            workflow.add_conditional_edges("plan", should_continue, {"plan": "plan", "work": "work", END: END})
            workflow.add_conditional_edges("work", should_continue, {"plan": "plan", "work": "work", END: END})
            self.app = workflow.compile(checkpointer=self._checkpointer_cache)
        return self._checkpointer_cache
        
    async def run(self, goal: str, thread_id: str = "default") -> AgentState:
        """
        Run the agent with a specific goal.
        
        Args:
            goal: The goal for the agent to work toward
            thread_id: Unique identifier for this conversation thread
        """
        print(f"Starting agent with goal: {goal}")
        print(f"Using thread ID: {thread_id}")
        
        # Set up checkpointer
        await self._get_checkpointer()
        
        # Initialize or load state
        initial_state: AgentState = {
            "goal": goal,
            "plan": [],
            "current_step": 0,
            "completed_actions": [],
            "messages": [HumanMessage(content=f"Goal: {goal}")],
            "status": "planning"
        }
        
        try:
            # Run the graph with persistence
            final_state = None
            config = {"configurable": {"thread_id": thread_id}}
            async for state in self.app.astream(initial_state, config=config):
                # state is a dict with node name as key
                for node_name, node_state in state.items():
                    print(f"  Completed node: {node_name}")
                    final_state = node_state
            
            return final_state
            
        except Exception as e:
            print(f"Error during execution: {e}")
            initial_state["status"] = "failed"
            initial_state["messages"].append(AIMessage(content=f"Execution failed: {str(e)}"))
            return initial_state
    
    async def resume(self, thread_id: str = "default") -> Optional[AgentState]:
        """Resume an existing conversation."""
        try:
            print(f"Resuming thread: {thread_id}")
            
            # Set up checkpointer
            await self._get_checkpointer()
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get the latest state
            state = await self.app.aget_state(config)
            if not state.values:
                print(f"No existing state found for thread: {thread_id}")
                return None
                
            print(f"Found existing state with status: {state.values['status']}")
            
            # Continue from where we left off
            final_state = None
            async for state in self.app.astream(None, config=config):
                for node_name, node_state in state.items():
                    print(f"  Completed node: {node_name}")
                    final_state = node_state
            
            return final_state
            
        except Exception as e:
            print(f"Error resuming thread {thread_id}: {e}")
            return None
    
    def list_threads(self) -> List[str]:
        """List all available thread IDs."""
        try:
            # Query the SQLite database directly
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints")
            threads = [row[0] for row in cursor.fetchall()]
            conn.close()
            return threads
        except Exception:
            return []  # Return empty if no database or error
    
    async def close(self):
        """Close the database connection."""
        if hasattr(self, '_checkpointer_cache') and self._checkpointer_cache:
            if hasattr(self._checkpointer_cache, 'conn'):
                await self._checkpointer_cache.conn.close()
            self._checkpointer_cache = None


async def main():
    """Main function to demonstrate the agent."""
    agent = LangGraphAgent()
    
    try:
        # Example usage
        goal = "Research and write a simple Python script that monitors a directory for new files"
        thread_id = "demo-session"
        
        print("=" * 60)
        print("🤖 LangGraph AI Agent Demo")
        print("=" * 60)
        
        # Check if we have an existing session
        existing_threads = agent.list_threads()
        if thread_id in existing_threads:
            print(f"📂 Found existing thread: {thread_id}")
            choice = input("Resume existing session? (y/n): ").lower()
            if choice == 'y':
                final_state = await agent.resume(thread_id)
                if final_state:
                    print(f"\n✅ Session resumed. Final status: {final_state['status']}")
                    return
        
        # Start new session
        final_state = await agent.run(goal, thread_id)
        
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS")
        print("=" * 60)
        print(f"Status: {final_state['status']}")
        print(f"Goal: {final_state['goal']}")
        print(f"Steps completed: {len(final_state['completed_actions'])}")
        
        if final_state["completed_actions"]:
            print("\nCompleted actions:")
            for i, action in enumerate(final_state["completed_actions"], 1):
                print(f"{i}. {action['description']}")
                print(f"   Result: {action['result'][:100]}...")
        
        print(f"\n💾 State saved to: {DB_PATH}")
        print(f"📝 Logs saved to: {LOGS_DIR}")
        
    finally:
        await agent.close()  # Close the database connection


if __name__ == "__main__":
    asyncio.run(main())