#!/usr/bin/env python3
"""
Professional LLM client using LangChain + LiteLLM integration.

Features:
- Uses LangChain's ChatOpenAI client pointing to LiteLLM
- Model routing (Haiku for simple tasks, Sonnet for complex)
- Cost tracking and estimation
- Proper error handling and logging
"""

import os
import json
import datetime
from typing import Dict, Any, List, Tuple
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


# Configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:8000")
OPENAI_BASE_URL = f"{LITELLM_URL}/v1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "dummy")  # LiteLLM ignores this

# Model names (actual models available in LiteLLM)
HAIKU_MODEL = "anthropic/claude-3-haiku-20240307"
SONNET_MODEL = "anthropic/claude-3-5-sonnet-20240620"

# Cost tracking (per 1M tokens)
PRICING = {
    "haiku":  {"in": 0.25/1e6, "out": 1.25/1e6},
    "sonnet": {"in": 3.00/1e6, "out": 15.0/1e6},
}

# Logging setup
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# Initialize LangChain clients (OpenAI-style, but routed to LiteLLM)
HAIKU_CLIENT = ChatOpenAI(
    model=HAIKU_MODEL,
    temperature=0.2,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)

SONNET_CLIENT = ChatOpenAI(
    model=SONNET_MODEL,
    temperature=0.1,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


def _needs_sonnet(text: str) -> bool:
    """
    Determine if a task needs the more capable Sonnet model.
    
    Criteria:
    - Long/complex prompts (>180 chars)
    - Technical keywords indicating complex reasoning
    """
    complexity_keywords = [
        "exploit", "reverse", "optimize", "trade", "analyze", "debug",
        "security", "vulnerability", "penetration", "crack", "hack",
        "algorithm", "architecture", "design", "strategy", "planning"
    ]
    
    return (
        len(text) > 180 or 
        any(keyword in text.lower() for keyword in complexity_keywords)
    )


def _convert_messages(messages: List[Tuple[str, str]]) -> List[SystemMessage | HumanMessage]:
    """Convert tuple format to LangChain message objects."""
    lc_messages = []
    for role, content in messages:
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages


def _log_interaction(model: str, messages: List[Tuple[str, str]], response: str, usage: Dict[str, Any]):
    """Log the LLM interaction for debugging and cost tracking."""
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "model": model,
        "messages": messages,
        "response": response[:200] + "..." if len(response) > 200 else response,
        "usage": usage,
        "estimated_cost": estimate_cost(model, usage)
    }
    
    log_path = LOGS_DIR / f"llm-calls-{datetime.date.today().isoformat()}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def estimate_cost(model: str, usage: Dict[str, Any]) -> float:
    """Estimate the cost of an LLM call."""
    if model not in PRICING:
        return 0.0
    
    pricing = PRICING[model]
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    cost = (
        pricing["in"] * prompt_tokens + 
        pricing["out"] * completion_tokens
    )
    
    return cost


def llm_call(
    messages: List[Tuple[str, str]], 
    model: str = None,
    max_tokens: int = 400,
    **kwargs
) -> Dict[str, Any]:
    """
    Unified LLM call through LangChain + LiteLLM.
    
    Args:
        messages: List of (role, content) tuples, e.g. [("system", "..."), ("human", "...")]
        model: HAIKU_MODEL, SONNET_MODEL, or None for auto-selection
        max_tokens: Maximum tokens for response
        **kwargs: Additional parameters for the LLM call
    
    Returns:
        Dict with "text", "usage", and "model_used" keys
    """
    # Auto-select model if not specified
    if model is None:
        # Use the first human message to determine complexity
        human_content = next((content for role, content in messages if role == "human"), "")
        model = SONNET_MODEL if _needs_sonnet(human_content) else HAIKU_MODEL
    
    # Select appropriate client based on model name
    if model == SONNET_MODEL:
        client = SONNET_CLIENT
        model_short = "sonnet"
    else:
        client = HAIKU_CLIENT
        model_short = "haiku"
    
    # Convert messages to LangChain format
    lc_messages = _convert_messages(messages)
    
    try:
        # Make the call
        response = client.invoke(
            lc_messages,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # Extract response and usage
        text = response.content
        usage = response.response_metadata.get("token_usage", {}) or {}
        
        # Log the interaction
        _log_interaction(model, messages, text, usage)
        
        return {
            "text": text,
            "usage": usage,
            "model_used": model_short,
            "estimated_cost": estimate_cost(model_short, usage)
        }
        
    except Exception as e:
        # Log error and re-raise
        error_log = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "error": str(e),
            "model": model,
            "messages": messages
        }
        
        log_path = LOGS_DIR / f"llm-errors-{datetime.date.today().isoformat()}.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(error_log) + "\n")
        
        raise


def get_model_stats() -> Dict[str, Any]:
    """Get statistics about model usage and costs."""
    try:
        # Read today's log file
        log_path = LOGS_DIR / f"llm-calls-{datetime.date.today().isoformat()}.jsonl"
        if not log_path.exists():
            return {"total_calls": 0, "total_cost": 0.0, "model_breakdown": {}}
        
        stats = {
            "total_calls": 0,
            "total_cost": 0.0,
            "model_breakdown": {"haiku": 0, "sonnet": 0}
        }
        
        with open(log_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    stats["total_calls"] += 1
                    stats["total_cost"] += entry.get("estimated_cost", 0.0)
                    model = entry.get("model", "unknown")
                    if model in stats["model_breakdown"]:
                        stats["model_breakdown"][model] += 1
                except json.JSONDecodeError:
                    continue
        
        return stats
        
    except Exception:
        return {"total_calls": 0, "total_cost": 0.0, "model_breakdown": {}}


# Sanity test
if __name__ == "__main__":
    print("Testing LLM client...")
    
    # Test simple call (should use Haiku)
    result = llm_call([
        ("human", "Say hello in one short sentence.")
    ], model=HAIKU_MODEL, max_tokens=50)
    
    print(f"Response: {result['text']}")
    print(f"Model used: {result['model_used']}")
    print(f"Cost: ${result['estimated_cost']:.6f}")
    
    # Test complex call (should use Sonnet)
    result2 = llm_call([
        ("system", "You are a security expert."),
        ("human", "Analyze the security implications of this WiFi penetration testing approach and provide detailed recommendations for improving the security posture.")
    ], model=SONNET_MODEL, max_tokens=200)
    
    print(f"\nComplex response: {result2['text'][:100]}...")
    print(f"Model used: {result2['model_used']}")
    print(f"Cost: ${result2['estimated_cost']:.6f}")
    
    # Show stats
    stats = get_model_stats()
    print(f"\nToday's stats: {stats}")
