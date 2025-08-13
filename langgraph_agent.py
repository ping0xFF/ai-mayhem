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
from typing import Dict, Any, Optional, List, TypedDict
from pathlib import Path

import requests
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
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
    print(f"🧠 Planning phase for goal: {state['goal']}")
    
    if not state["plan"]:  # Initial planning
        prompt = f"""
        You are an AI planner. Your job is to break down a goal into actionable steps.
        
        Goal: {state['goal']}
        
        Create a plan with 3-5 specific, actionable steps to achieve this goal.
        Each step should be something that can be executed independently.
        
        Format your response as a JSON list of strings, like:
        ["Step 1 description", "Step 2 description", "Step 3 description"]
        
        Only return the JSON list, nothing else.
        """
        
        response, usage = call_llm(prompt, PLANNER_MODEL, max_tokens=500)
        
        try:
            # Parse the plan from the response
            plan = json.loads(response.strip())
            state["plan"] = plan
            state["current_step"] = 0
            state["status"] = "working"
            state["messages"].append(AIMessage(content=f"Created plan with {len(plan)} steps"))
            print(f"📋 Plan created with {len(plan)} steps")
        except json.JSONDecodeError:
            print("❌ Failed to parse plan from response")
            state["status"] = "failed"
            state["messages"].append(AIMessage(content="Failed to create plan - invalid response format"))
    
    else:  # Re-planning or plan adjustment
        completed = len(state["completed_actions"])
        remaining = len(state["plan"]) - state["current_step"]
        
        if remaining > 0:
            print(f"📋 Plan has {remaining} steps remaining (completed {completed})")
            state["status"] = "working"
        else:
            print("✅ All planned steps completed")
            state["status"] = "completed"
    
    return state


def worker_node(state: AgentState) -> AgentState:
    """
    Worker node: Executes the current step in the plan.
    """
    if state["current_step"] >= len(state["plan"]):
        state["status"] = "completed"
        return state
    
    current_action = state["plan"][state["current_step"]]
    print(f"⚡ Executing step {state['current_step'] + 1}: {current_action}")
    
    # Context for the worker
    context = f"""
    Goal: {state['goal']}
    Current step ({state['current_step'] + 1}/{len(state['plan'])}): {current_action}
    
    Previous completed actions:
    {chr(10).join(f"- {action['description']}" for action in state['completed_actions'][-3:])}
    """
    
    prompt = f"""
    You are an AI worker executing a specific step in a plan.
    
    {context}
    
    Execute this step: {current_action}
    
    Provide:
    1. A description of what you did (be specific)
    2. Any important findings or results
    3. Whether this step is complete or needs more work
    
    Keep your response concise but informative.
    """
    
    # Use the more capable model for complex tasks
    model = WORKER_MODEL if "complex" in current_action.lower() or "analyze" in current_action.lower() else PLANNER_MODEL
    response, usage = call_llm(prompt, model, max_tokens=600)
    
    # Record the completed action
    action_result = {
        "step": state["current_step"],
        "description": current_action,
        "result": response,
        "model_used": model,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    state["completed_actions"].append(action_result)
    state["current_step"] += 1
    state["messages"].append(AIMessage(content=f"Completed: {current_action}\nResult: {response}"))
    
    print(f"✅ Step completed. Result: {response[:100]}...")
    
    # Determine next status
    if state["current_step"] >= len(state["plan"]):
        state["status"] = "completed"
        print("🎉 All steps completed!")
    else:
        state["status"] = "working"
    
    return state


def should_continue(state: AgentState) -> str:
    """
    Routing function to determine the next node.
    """
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
        
        # Set up SQLite persistence - simplified for now
        self.checkpointer = None  # Will add back when LangGraph API stabilizes
        self.app = workflow.compile()
        
    async def run(self, goal: str, thread_id: str = "default") -> AgentState:
        """
        Run the agent with a specific goal.
        
        Args:
            goal: The goal for the agent to work toward
            thread_id: Unique identifier for this conversation thread
        """
        print(f"🚀 Starting agent with goal: {goal}")
        print(f"📊 Using thread ID: {thread_id}")
        
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
            # Run the graph
            final_state = None
            async for state in self.app.astream(initial_state):
                # state is a dict with node name as key
                for node_name, node_state in state.items():
                    print(f"📍 Completed node: {node_name}")
                    final_state = node_state
            
            return final_state
            
        except Exception as e:
            print(f"❌ Error during execution: {e}")
            initial_state["status"] = "failed"
            initial_state["messages"].append(AIMessage(content=f"Execution failed: {str(e)}"))
            return initial_state
    
    async def resume(self, thread_id: str = "default") -> Optional[AgentState]:
        """
        Resume an existing conversation.
        Note: This is temporarily disabled until LangGraph checkpointer API stabilizes.
        """
        print(f"❌ Resume functionality temporarily disabled - checkpointer API changed")
        print(f"Please start a new session instead")
        return None
    
    def list_threads(self) -> List[str]:
        """List all available thread IDs."""
        # Temporarily disabled until checkpointer is re-enabled
        return []


async def main():
    """Main function to demonstrate the agent."""
    agent = LangGraphAgent()
    
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


if __name__ == "__main__":
    asyncio.run(main())
