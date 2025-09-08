#!/usr/bin/env python3
"""
Three-Layer Data Model for Agent State

Layer 1: Scratch JSON Cache (raw API responses)
Layer 2: Normalized Events (curated schema for recurring entities)  
Layer 3: Artifacts/Briefs (human-readable summaries and signals)

Provides clear contracts for data flow and prevents state sprawl.
"""

import json
import sqlite3
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

# Use the same database as the agent
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agent_state.db"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_model.log'),  # Log to file
        logging.StreamHandler()  # Also log to console for critical messages
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class NormalizedEvent:
    """Normalized event schema for recurring entities."""
    event_id: str  # Deterministic: f"{txHash}:{logIndex}"
    wallet: Optional[str]  # Wallet address if applicable
    event_type: str  # "swap", "lp_add", "lp_remove", "metrics"
    pool: Optional[str]  # Pool identifier if applicable
    value: Dict[str, Any]  # Event-specific data
    timestamp: int  # Unix timestamp
    source_id: str  # Points back to scratch JSON row
    chain: str = "base"  # Default to base chain


@dataclass
class Artifact:
    """Human-readable summary artifact."""
    artifact_id: str  # Deterministic: f"brief_{timestamp}"
    timestamp: int  # Unix timestamp
    summary_text: str  # Human-readable summary
    signals: Dict[str, float]  # Computed signals
    next_watchlist: List[str]  # Suggested items to watch
    source_ids: List[str]  # Points back to scratch JSON rows
    event_count: int  # Number of events processed
    # LLM brief fields
    summary_text_llm: Optional[str] = None  # Free-form natural-language brief from LLM
    llm_struct: Optional[Dict[str, Any]] = None  # Machine-readable structured fields
    llm_validation: Optional[Dict[str, Any]] = None  # LLM's self-checks vs deterministic rollups
    llm_model: Optional[str] = None  # The gateway model alias actually used
    llm_tokens: Optional[int] = None  # Total tokens consumed for this brief


class ThreeLayerDataModel:
    """Manages the three-layer data model with proper provenance tracking."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize database with three-layer schema."""
        conn = await self._get_connection()
        
        # Set production pragmas
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA cache_size=10000")
        await conn.execute("PRAGMA temp_store=MEMORY")
        
        # Layer 1: Scratch JSON Cache (already exists, but add provenance field)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS json_cache_scratch (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add provenance column if it doesn't exist
        try:
            await conn.execute("ALTER TABLE json_cache_scratch ADD COLUMN provenance TEXT")
        except:
            # Column already exists, ignore
            pass
        
        # Layer 2: Normalized Events
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS normalized_events (
                event_id TEXT PRIMARY KEY,
                wallet TEXT,
                event_type TEXT NOT NULL,
                pool TEXT,
                value TEXT NOT NULL,  -- JSON string
                timestamp INTEGER NOT NULL,
                source_id TEXT NOT NULL,  -- Points to scratch JSON
                chain TEXT DEFAULT 'base',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES json_cache_scratch(id)
            )
        """)
        
        # Layer 3: Artifacts/Briefs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                signals TEXT NOT NULL,  -- JSON string
                next_watchlist TEXT NOT NULL,  -- JSON array string
                source_ids TEXT NOT NULL,  -- JSON array string
                event_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add LLM fields if they don't exist
        try:
            await conn.execute("ALTER TABLE artifacts ADD COLUMN summary_text_llm TEXT")  # LLM-generated brief
            await conn.execute("ALTER TABLE artifacts ADD COLUMN llm_struct TEXT")  # JSON string for structured fields
            await conn.execute("ALTER TABLE artifacts ADD COLUMN llm_validation TEXT")  # JSON string for validation results
            await conn.execute("ALTER TABLE artifacts ADD COLUMN llm_model TEXT")  # Model alias used
            await conn.execute("ALTER TABLE artifacts ADD COLUMN llm_tokens INTEGER")  # Token usage
        except:
            # Columns already exist, ignore
            pass
        
        # Create indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_wallet_ts ON normalized_events(wallet, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON normalized_events(event_type, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_pool_ts ON normalized_events(pool, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON normalized_events(source_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_ts ON artifacts(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_source ON artifacts(source_ids)")
        
        await conn.commit()
        await conn.close()
        
        logger.info("Three-layer data model initialized")
    
    async def _get_connection(self):
        """Get async SQLite connection."""
        import aiosqlite
        return await aiosqlite.connect(self.db_path)
    
    # Layer 1: Scratch JSON Cache (extended)
    async def save_raw_response(self, response_id: str, source: str, raw_data: Dict[str, Any], 
                               provenance: Optional[Dict[str, Any]] = None) -> str:
        """Save raw API/MCP response to scratch cache."""
        conn = await self._get_connection()
        
        try:
            # Validate JSON serialization
            raw_json = json.dumps(raw_data)
            provenance_json = json.dumps(provenance) if provenance else None
            
            await conn.execute("""
                INSERT OR REPLACE INTO json_cache_scratch (id, source, raw_json, provenance)
                VALUES (?, ?, ?, ?)
            """, (response_id, source, raw_json, provenance_json))
            
            await conn.commit()
            logger.debug(f"Saved raw response: {response_id} from {source}")
            return response_id
            
        finally:
            await conn.close()
    
    async def get_raw_response(self, response_id: str) -> Optional[Dict[str, Any]]:
        """Get raw response from scratch cache."""
        conn = await self._get_connection()
        
        try:
            async with conn.execute("""
                SELECT raw_json, provenance FROM json_cache_scratch WHERE id = ?
            """, (response_id,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    raw_json, provenance = row
                    try:
                        data = json.loads(raw_json)
                        if provenance:
                            data['_provenance'] = json.loads(provenance)
                        return data
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted JSON data for id: {response_id}")
                        return None
                return None
                
        finally:
            await conn.close()
    
    # Layer 2: Normalized Events
    async def normalize_event(self, event: NormalizedEvent) -> str:
        """Save normalized event with provenance tracking."""
        conn = await self._get_connection()
        
        try:
            value_json = json.dumps(event.value)
            
            await conn.execute("""
                INSERT OR REPLACE INTO normalized_events 
                (event_id, wallet, event_type, pool, value, timestamp, source_id, chain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.wallet, event.event_type, event.pool,
                value_json, event.timestamp, event.source_id, event.chain
            ))
            
            await conn.commit()
            logger.debug(f"Normalized event: {event.event_id} ({event.event_type})")
            return event.event_id
            
        finally:
            await conn.close()
    
    async def get_events_by_wallet(self, wallet: str, since_ts: int = 0) -> List[NormalizedEvent]:
        """Get normalized events for a wallet since timestamp."""
        conn = await self._get_connection()
        
        try:
            events = []
            async with conn.execute("""
                SELECT event_id, wallet, event_type, pool, value, timestamp, source_id, chain
                FROM normalized_events 
                WHERE wallet = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (wallet, since_ts)) as cursor:
                async for row in cursor:
                    event_id, wallet, event_type, pool, value_json, timestamp, source_id, chain = row
                    try:
                        value = json.loads(value_json)
                        events.append(NormalizedEvent(
                            event_id=event_id,
                            wallet=wallet,
                            event_type=event_type,
                            pool=pool,
                            value=value,
                            timestamp=timestamp,
                            source_id=source_id,
                            chain=chain
                        ))
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted event value for: {event_id}")
            
            return events
            
        finally:
            await conn.close()
    
    async def get_events_by_type(self, event_type: str, since_ts: int = 0) -> List[NormalizedEvent]:
        """Get normalized events by type since timestamp."""
        conn = await self._get_connection()
        
        try:
            events = []
            async with conn.execute("""
                SELECT event_id, wallet, event_type, pool, value, timestamp, source_id, chain
                FROM normalized_events 
                WHERE event_type = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (event_type, since_ts)) as cursor:
                async for row in cursor:
                    event_id, wallet, event_type, pool, value_json, timestamp, source_id, chain = row
                    try:
                        value = json.loads(value_json)
                        events.append(NormalizedEvent(
                            event_id=event_id,
                            wallet=wallet,
                            event_type=event_type,
                            pool=pool,
                            value=value,
                            timestamp=timestamp,
                            source_id=source_id,
                            chain=chain
                        ))
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted event value for: {event_id}")
            
            return events
            
        finally:
            await conn.close()
    
    async def get_all_events_since(self, since_ts: int = 0) -> List[NormalizedEvent]:
        """Get all normalized events since timestamp."""
        conn = await self._get_connection()
        
        try:
            events = []
            async with conn.execute("""
                SELECT event_id, wallet, event_type, pool, value, timestamp, source_id, chain
                FROM normalized_events 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (since_ts,)) as cursor:
                async for row in cursor:
                    event_id, wallet, event_type, pool, value_json, timestamp, source_id, chain = row
                    try:
                        value = json.loads(value_json)
                        events.append(NormalizedEvent(
                            event_id=event_id,
                            wallet=wallet,
                            event_type=event_type,
                            pool=pool,
                            value=value,
                            timestamp=timestamp,
                            source_id=source_id,
                            chain=chain
                        ))
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted event value for: {event_id}")
            
            return events
            
        finally:
            await conn.close()
    
    # Layer 3: Artifacts/Briefs
    async def persist_brief(self, artifact: Artifact) -> str:
        """Persist human-readable brief artifact."""
        conn = await self._get_connection()
        
        try:
            signals_json = json.dumps(artifact.signals)
            watchlist_json = json.dumps(artifact.next_watchlist)
            source_ids_json = json.dumps(artifact.source_ids)
            
            # Handle LLM fields
            llm_struct_json = json.dumps(artifact.llm_struct) if artifact.llm_struct else None
            llm_validation_json = json.dumps(artifact.llm_validation) if artifact.llm_validation else None
            
            await conn.execute("""
                INSERT OR REPLACE INTO artifacts 
                (artifact_id, timestamp, summary_text, signals, next_watchlist, source_ids, event_count,
                 summary_text_llm, llm_struct, llm_validation, llm_model, llm_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact.artifact_id, artifact.timestamp, artifact.summary_text,
                signals_json, watchlist_json, source_ids_json, artifact.event_count,
                artifact.summary_text_llm, llm_struct_json, llm_validation_json,
                artifact.llm_model, artifact.llm_tokens
            ))
            
            await conn.commit()
            logger.debug(f"Persisted artifact: {artifact.artifact_id}")
            return artifact.artifact_id
            
        finally:
            await conn.close()
    
    async def get_recent_briefs(self, limit: int = 10) -> List[Artifact]:
        """Get recent brief artifacts."""
        conn = await self._get_connection()
        
        try:
            artifacts = []
            async with conn.execute("""
                SELECT artifact_id, timestamp, summary_text, signals, next_watchlist, source_ids, event_count,
                       summary_text_llm, llm_struct, llm_validation, llm_model, llm_tokens
                FROM artifacts 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                async for row in cursor:
                    (artifact_id, timestamp, summary_text, signals_json, watchlist_json, source_ids_json, event_count,
                     summary_text_llm, llm_struct_json, llm_validation_json, llm_model, llm_tokens) = row
                    try:
                        signals = json.loads(signals_json)
                        next_watchlist = json.loads(watchlist_json)
                        source_ids = json.loads(source_ids_json)
                        llm_struct = json.loads(llm_struct_json) if llm_struct_json else None
                        llm_validation = json.loads(llm_validation_json) if llm_validation_json else None
                        
                        artifacts.append(Artifact(
                            artifact_id=artifact_id,
                            timestamp=timestamp,
                            summary_text=summary_text,
                            signals=signals,
                            next_watchlist=next_watchlist,
                            source_ids=source_ids,
                            event_count=event_count,
                            summary_text_llm=summary_text_llm,
                            llm_struct=llm_struct,
                            llm_validation=llm_validation,
                            llm_model=llm_model,
                            llm_tokens=llm_tokens
                        ))
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted artifact data for: {artifact_id}")
            
            return artifacts
            
        finally:
            await conn.close()
    
    # Cleanup and retention
    async def cleanup_old_data(self, scratch_days: int = 7, events_days: int = 30, artifacts_days: int = 90):
        """Clean up old data according to retention rules."""
        conn = await self._get_connection()
        
        try:
            # Clean old scratch data
            scratch_deleted = await conn.execute("""
                DELETE FROM json_cache_scratch 
                WHERE created_at < datetime('now', '-{} days')
            """.format(scratch_days))
            
            # Clean old events
            events_deleted = await conn.execute("""
                DELETE FROM normalized_events 
                WHERE created_at < datetime('now', '-{} days')
            """.format(events_days))
            
            # Clean old artifacts (keep longer)
            artifacts_deleted = await conn.execute("""
                DELETE FROM artifacts 
                WHERE created_at < datetime('now', '-{} days')
            """.format(artifacts_days))
            
            await conn.commit()
            
            logger.info(f"Cleanup: {scratch_deleted.rowcount} scratch, {events_deleted.rowcount} events, {artifacts_deleted.rowcount} artifacts")
            
        finally:
            await conn.close()
    
    # Provenance tracking
    async def get_provenance_chain(self, artifact_id: str) -> Dict[str, Any]:
        """Get full provenance chain from artifact back to raw responses."""
        conn = await self._get_connection()
        
        try:
            # Get artifact
            async with conn.execute("""
                SELECT source_ids FROM artifacts WHERE artifact_id = ?
            """, (artifact_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {}
                
                source_ids = json.loads(row[0])
            
            # Get source raw responses
            raw_responses = []
            for source_id in source_ids:
                response = await self.get_raw_response(source_id)
                if response:
                    raw_responses.append(response)
            
            # Get events from those sources
            events = []
            for source_id in source_ids:
                source_events = await self.get_events_by_source(source_id)
                events.extend(source_events)
            
            return {
                "artifact_id": artifact_id,
                "raw_responses": raw_responses,
                "events": [asdict(e) for e in events]
            }
            
        finally:
            await conn.close()
    
    async def get_events_by_source(self, source_id: str) -> List[NormalizedEvent]:
        """Get events that originated from a specific source."""
        conn = await self._get_connection()
        
        try:
            events = []
            async with conn.execute("""
                SELECT event_id, wallet, event_type, pool, value, timestamp, source_id, chain
                FROM normalized_events 
                WHERE source_id = ?
                ORDER BY timestamp DESC
            """, (source_id,)) as cursor:
                async for row in cursor:
                    event_id, wallet, event_type, pool, value_json, timestamp, source_id, chain = row
                    try:
                        value = json.loads(value_json)
                        events.append(NormalizedEvent(
                            event_id=event_id,
                            wallet=wallet,
                            event_type=event_type,
                            pool=pool,
                            value=value,
                            timestamp=timestamp,
                            source_id=source_id,
                            chain=chain
                        ))
                    except json.JSONDecodeError:
                        logger.warning(f"Corrupted event value for: {event_id}")
            
            return events
            
        finally:
            await conn.close()


# Global instance
_data_model = None

async def get_data_model() -> ThreeLayerDataModel:
    """Get or create global data model instance."""
    global _data_model
    if _data_model is None:
        _data_model = ThreeLayerDataModel(DB_PATH)
        await _data_model.initialize()
    return _data_model


# Convenience functions for the three layers
async def save_raw_response(response_id: str, source: str, raw_data: Dict[str, Any], 
                           provenance: Optional[Dict[str, Any]] = None) -> str:
    """Save raw API/MCP response to scratch cache."""
    model = await get_data_model()
    return await model.save_raw_response(response_id, source, raw_data, provenance)

async def normalize_event(event: NormalizedEvent) -> str:
    """Save normalized event with provenance tracking."""
    model = await get_data_model()
    return await model.normalize_event(event)

async def persist_brief(artifact: Artifact) -> str:
    """Persist human-readable brief artifact."""
    model = await get_data_model()
    return await model.persist_brief(artifact)

async def get_events_by_wallet(wallet: str, since_ts: int = 0) -> List[NormalizedEvent]:
    """Get normalized events for a wallet since timestamp."""
    model = await get_data_model()
    return await model.get_events_by_wallet(wallet, since_ts)

async def get_recent_briefs(limit: int = 10) -> List[Artifact]:
    """Get recent brief artifacts."""
    model = await get_data_model()
    return await model.get_recent_briefs(limit)

async def get_provenance_chain(artifact_id: str) -> Dict[str, Any]:
    """Get full provenance chain from artifact back to raw responses."""
    model = await get_data_model()
    return await model.get_provenance_chain(artifact_id)
