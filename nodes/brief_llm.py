"""
LLM integration for brief generation.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from data_model import NormalizedEvent
from llm_client import llm_call
from .config import LLM_BRIEF_MODEL

SYSTEM_PROMPT = """You are a crypto LP analyst. Produce a concise brief for a human trader. Respect schema. Validate your claims against provided rollups.

Your output must be valid JSON with the following schema:
{
  "summary_text": "Human-readable brief focusing on key insights and actionable signals",
  "struct": {
    "top_wallets": [{"address": "0x...", "score": 0.95, "reason": "..."}],
    "notable_events": [{"type": "lp_add", "pool": "...", "usd": 12345, "why": "..."}],
    "signals": {"churn": 0.42, "concentration": "high"},
    "risk_flags": ["price_divergence_possible"],
    "confidence": 0.77
  },
  "validation": {
    "consistency_ok": true,
    "discrepancies": []  # List of any mismatches vs deterministic rollups
  }
}

Guidelines:
1. Focus on actionable insights and patterns
2. Highlight largest moves and anomalies
3. Cross-validate against deterministic rollups
4. Assign confidence based on data quality
5. Keep summary under 200 words
"""

def format_events_for_llm(events: List[NormalizedEvent], rollups: Dict[str, Any]) -> str:
    """Format events and rollups for LLM consumption."""
    events_json = json.dumps([{
        "event_id": e.event_id,
        "wallet": e.wallet,
        "event_type": e.event_type,
        "pool": e.pool,
        "value": e.value,
        "timestamp": e.timestamp
    } for e in events], indent=2)
    
    rollups_json = json.dumps(rollups, indent=2)
    
    return f"""
Events ({len(events)} total):
{events_json}

Deterministic Rollups:
{rollups_json}

Analyze the above data and produce a brief following the schema.
Focus on:
1. Largest moves by USD value
2. Unusual patterns or anomalies
3. Wallet/pool concentration
4. Risk signals
5. Cross-validation with rollups
"""

async def generate_llm_brief(events: List[NormalizedEvent], rollups: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Generate LLM brief from events and rollups.
    
    Returns:
        Tuple[Dict[str, Any], Dict[str, Any]]: (brief_data, usage_data)
        - brief_data: The LLM's structured output
        - usage_data: Token usage statistics
    """
    prompt = format_events_for_llm(events, rollups)
    
    response = await llm_call(
        model=LLM_BRIEF_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        task_type="brief"  # Explicitly mark this as a brief generation task
    )
    
    try:
        brief_data = json.loads(response["text"])
        usage_data = response["usage"]
        model_used = response["model"]
        
        # Add model info to brief
        brief_data["model"] = model_used
        
        return brief_data, usage_data
    except json.JSONDecodeError:
        # If LLM output isn't valid JSON, return error brief
        error_brief = {
            "summary_text": "Error: LLM output was not valid JSON",
            "struct": {
                "top_wallets": [],
                "notable_events": [],
                "signals": {},
                "risk_flags": ["llm_output_invalid"],
                "confidence": 0.0
            },
            "validation": {
                "consistency_ok": False,
                "discrepancies": ["LLM output was not valid JSON"]
            },
            "model": LLM_BRIEF_MODEL
        }
        return error_brief, {"total_tokens": 0}