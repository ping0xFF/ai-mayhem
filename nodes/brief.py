"""
Brief node with gating logic and LLM integration.
"""

import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .config import (
    BRIEF_COOLDOWN, BRIEF_THRESHOLD_EVENTS, BRIEF_THRESHOLD_SIGNAL,
    BRIEF_MODE, LLM_INPUT_POLICY, LLM_TOKEN_CAP, load_monitored_wallets
)
from data_model import (
    persist_brief, Artifact, get_data_model,
    NormalizedEvent
)
from .rich_output import formatter
from .brief_utils import estimate_tokens, reduce_events
from .brief_llm import generate_llm_brief

logger = logging.getLogger(__name__)


async def brief_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced brief node with gating logic and LLM integration.
    
    Emits brief only if (new_events ≥ 5 OR max_signal ≥ 0.6) AND cooldown passed.
    Includes optional discovered pools and LLM-generated insights.
    """
    start_time = time.time()
    formatter.log_node_progress("Brief", "Checking if brief should be emitted...")
    
    # Get current time and last brief time
    current_time = int(datetime.now().timestamp())
    last_brief_at = state.get("last_brief_at", 0)
    
    # Check cooldown
    if current_time - last_brief_at < BRIEF_COOLDOWN:
        execution_time = time.time() - start_time
        formatter.log_node_progress(
            "Brief",
            f"Cooldown not passed ({BRIEF_COOLDOWN/3600:.1f}h remaining)",
            execution_time
        )
        return {
            **state,
            "brief_skipped": True,
            "reason": "cooldown",
            "status": "memory"
        }
    
    # Get event counts and signals
    event_counts = state.get("last24h_counts", {})
    signals = state.get("signals", {})
    
    total_events = sum(event_counts.values())
    
    # Separate general signals from LP-specific signals
    general_signals = {k: v for k, v in signals.items() if k in ['volume_signal', 'activity_signal', 'concentration_signal']}
    max_general_signal = max(general_signals.values()) if general_signals else 0.0
    
    # Check thresholds (including LP-specific thresholds)
    lp_activity_score = signals.get("pool_activity_score", 0.0)
    lp_threshold_met = lp_activity_score >= 0.6  # LP-specific threshold
    
    if total_events < BRIEF_THRESHOLD_EVENTS and max_general_signal < BRIEF_THRESHOLD_SIGNAL and not lp_threshold_met:
        execution_time = time.time() - start_time
        formatter.log_node_progress(
            "Brief",
            f"Low activity: {total_events} events, max signal {max_general_signal:.2f}",
            execution_time
        )
        return {
            **state,
            "brief_skipped": True,
            "reason": "low_activity",
            "status": "memory"
        }
    
    # Generate deterministic brief
    top_pools = state.get("top_pools", [])

    # Load monitored wallets for context
    monitored_wallets = load_monitored_wallets()
    wallet_count = len(monitored_wallets)

    brief_text = f"24h activity: {total_events} events across {len(event_counts)} types"
    if wallet_count > 0:
        brief_text += f" (monitoring {wallet_count} wallets)"
    brief_text += ". "

    if top_pools:
        brief_text += f"Top pools: {', '.join(top_pools[:3])}. "
    
    # Add LP-specific information if available
    lp_signals = {k: v for k, v in signals.items() if k.startswith(('net_liquidity', 'lp_churn', 'pool_activity'))}
    if lp_signals:
        brief_text += f"LP activity: net delta {lp_signals.get('net_liquidity_delta_24h', 0)}, "
        brief_text += f"churn rate {lp_signals.get('lp_churn_rate_24h', 0):.2f}, "
        brief_text += f"activity score {lp_signals.get('pool_activity_score', 0):.2f}. "

    # Add wallet-specific information if this was a wallet recon
    selected_action = state.get("selected_action")
    wallet_signals = {k: v for k, v in signals.items() if k.startswith(('net_lp_usd', 'new_pools_touched'))}
    if selected_action == "wallet_recon" and wallet_signals:
        # Determine source from raw data
        raw_data = state.get("raw_data", {})
        provider_info = raw_data.get("provider", {})
        if isinstance(provider_info, dict):
            source_name = provider_info.get("name", "unknown")
        else:
            source_name = "bitquery"  # Legacy format

        brief_text += f"Wallet recon via {source_name}: net LP USD ${wallet_signals.get('net_lp_usd_24h', 0):.2f}, "
        new_pools = wallet_signals.get('new_pools_touched_24h', [])
        brief_text += f"new pools touched {len(new_pools)}. "
    
    if signals:
        brief_text += f"General signals: volume={signals.get('volume_signal', 0):.2f}, "
        brief_text += f"activity={signals.get('activity_signal', 0):.2f}. "
    
    # Generate pool suggestions from discovered activity
    discovered_pools = []
    if top_pools:
        discovered_pools.extend(top_pools[:2])
    
    # Add LP-specific pools with high activity
    if lp_signals and lp_signals.get("pool_activity_score", 0) > 0.5:
        # Add pools with high LP activity to suggestions
        if top_pools:
            discovered_pools.extend([f"{pool} (LP)" for pool in top_pools[:2]])
    
    # Add any high-signal pools from raw data
    raw_data = state.get("raw_data", {})
    if "metrics" in raw_data:
        metrics = raw_data["metrics"]
        top_pool = metrics.get("key_values", {}).get("top_pool")
        if top_pool and top_pool not in discovered_pools:
            discovered_pools.append(top_pool)
    
    brief_text += f"Discovered pools: {', '.join(discovered_pools) if discovered_pools else 'none'}."
    
    # Initialize LLM fields
    llm_summary = None
    llm_struct = None
    llm_validation = None
    llm_model = None
    llm_tokens = None
    
    # Generate LLM brief if enabled
    if BRIEF_MODE in ["llm", "both"]:
        try:
            # Get all events since last brief
            data_model = await get_data_model()
            events = await data_model.get_all_events_since(last_brief_at)
            
            # Check token budget
            estimated_tokens = estimate_tokens(events, signals)
            if LLM_INPUT_POLICY == "budgeted" and estimated_tokens > LLM_TOKEN_CAP:
                logger.info(f"Reducing events to fit token cap ({estimated_tokens} > {LLM_TOKEN_CAP})")
                events, signals = reduce_events(events, signals, LLM_TOKEN_CAP)
            
            # Generate LLM brief
            try:
                brief_data, usage_data = await generate_llm_brief(
                    events=events,
                    rollups=signals
                )
                
                # Extract fields
                llm_summary = brief_data["summary_text"]
                llm_struct = json.dumps(brief_data["struct"])  # Convert to JSON string
                llm_validation = json.dumps(brief_data["validation"])  # Convert to JSON string
                llm_model = brief_data["model"]
                llm_tokens = usage_data["total_tokens"]
                
                logger.info(f"Generated LLM brief using {llm_model} ({llm_tokens} tokens)")
            except Exception as e:
                logger.error(f"Failed to generate LLM brief: {e}")
                # Continue with deterministic brief only
                llm_summary = None
                llm_struct = None
                llm_validation = None
                llm_model = None
                llm_tokens = None
            
        except Exception as e:
            logger.error(f"Failed to generate LLM brief: {e}")
            # Continue with deterministic brief only
            llm_summary = None
            llm_struct = None
            llm_validation = None
            llm_model = None
            llm_tokens = None
    
    # Create artifact for Layer 3
    current_time = int(datetime.now().timestamp())
    artifact_id = f"brief_{current_time}"
    source_ids = state.get("source_ids", [])
    
    # Create base artifact
    artifact = Artifact(
        artifact_id=artifact_id,
        timestamp=current_time,
        summary_text=brief_text,
        signals=signals,
        discovered_pools=discovered_pools,
        source_ids=source_ids,
        event_count=total_events,
        summary_text_llm=llm_summary if BRIEF_MODE in ["llm", "both"] else None,
        llm_struct=llm_struct if BRIEF_MODE in ["llm", "both"] else None,
        llm_validation=llm_validation if BRIEF_MODE in ["llm", "both"] else None,
        llm_model=llm_model if BRIEF_MODE in ["llm", "both"] else None,
        llm_tokens=llm_tokens if BRIEF_MODE in ["llm", "both"] else None
    )
    
    # Persist to Layer 3
    await persist_brief(artifact)
    
    execution_time = time.time() - start_time
    formatter.log_node_progress(
        "Brief",
        f"Generated {len(brief_text)} char brief, {len(discovered_pools)} discovered pools",
        execution_time
    )
    
    result = {
        **state,
        "brief_text": brief_text,
        "discovered_pools": discovered_pools,
        "last_brief_at": current_time,
        "status": "memory"
    }
    
    # Add LLM fields to result if enabled and available
    if BRIEF_MODE in ["llm", "both"] and llm_summary is not None:
        result.update({
            "llm_summary": llm_summary,
            "llm_struct": llm_struct
        })
    
    return result