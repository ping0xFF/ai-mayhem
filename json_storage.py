#!/usr/bin/env python3
"""
Flexible JSON persistence layer for exploratory agent work.
Stores arbitrary JSON responses from external APIs/MCPs without schema commitment.
Production-ready with proper namespacing, concurrency controls, and observability.
"""

import json
import sqlite3
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Use the same database as the agent
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agent_state.db"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize database with proper pragmas and tables."""
        conn = await self._get_connection()
        
        # Set production pragmas
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA cache_size=10000")
        await conn.execute("PRAGMA temp_store=MEMORY")
        
        # Create namespaced tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS json_cache_scratch (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create audit log table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS writes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                table_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                n_rows INTEGER NOT NULL,
                note TEXT
            )
        """)
        
        # Create cursors table for delta fetches
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cursors (
                name TEXT PRIMARY KEY,
                last_ts INTEGER NOT NULL,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create LLM usage tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                estimated_cost REAL NOT NULL,
                request_id TEXT
            )
        """)
        
        # Create indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_json_cache_source_ts ON json_cache_scratch(source, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_json_cache_created ON json_cache_scratch(created_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_writes_log_ts ON writes_log(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_ts ON llm_usage(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_model ON llm_usage(model)")
        
        await conn.commit()
        await conn.close()
        
        logger.info("Database initialized with production settings")
    
    async def _get_connection(self):
        """Get async database connection."""
        import aiosqlite
        return await aiosqlite.connect(self.db_path)
    
    async def upsert_json(self, id: str, source: str, payload: dict) -> None:
        """
        Save JSON data with upsert behavior.
        
        Args:
            id: Unique identifier
            source: Source of the data
            payload: Dictionary to store as JSON
        """
        # Validate JSON serializability
        try:
            json.dumps(payload)
        except (TypeError, ValueError) as e:
            raise ValueError(f"payload is not JSON-serializable: {e}")
        
        conn = await self._get_connection()
        
        try:
            await conn.execute("""
                INSERT OR REPLACE INTO json_cache_scratch (id, source, raw_json)
                VALUES (?, ?, ?)
            """, (id, source, json.dumps(payload)))
            
            # Log the operation
            await conn.execute("""
                INSERT INTO writes_log (table_name, operation, n_rows, note)
                VALUES (?, ?, ?, ?)
            """, ("json_cache_scratch", "upsert", 1, f"Upserted {id} from {source}"))
            
            await conn.commit()
            
        finally:
            await conn.close()
    
    async def load_json(self, id: str) -> Optional[dict]:
        """
        Load JSON data by ID.
        
        Args:
            id: Unique identifier
        
        Returns:
            Dictionary if found, None if not found
        """
        conn = await self._get_connection()
        
        try:
            async with conn.execute("SELECT raw_json FROM json_cache_scratch WHERE id = ?", (id,)) as cursor:
                row = await cursor.fetchone()
                
                if row is None:
                    return None
                
                return json.loads(row[0])
        except json.JSONDecodeError:
            logger.warning(f"Corrupted JSON data for id: {id}")
            return None
        finally:
            await conn.close()
    
    async def query_recent(self, source: str, limit: int = 10) -> List[dict]:
        """
        Query recent JSON data by source.
        
        Args:
            source: Source of the data
            limit: Maximum number of records to return
        
        Returns:
            List of dictionaries containing the stored JSON data
        """
        conn = await self._get_connection()
        
        try:
            results = []
            async with conn.execute("""
                SELECT raw_json FROM json_cache_scratch 
                WHERE source = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (source, limit)) as cursor:
                async for row in cursor:
                    try:
                        results.append(json.loads(row[0]))
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping corrupted JSON in query_recent for source: {source}")
                        continue
            
            return results
        finally:
            await conn.close()
    
    async def set_cursor(self, name: str, last_ts: int, notes: str = None) -> None:
        """Set cursor for delta fetches."""
        conn = await self._get_connection()
        
        try:
            await conn.execute("""
                INSERT OR REPLACE INTO cursors (name, last_ts, notes)
                VALUES (?, ?, ?)
            """, (name, last_ts, notes))
            
            await conn.commit()
        finally:
            await conn.close()
    
    async def get_cursor(self, name: str) -> Optional[int]:
        """Get cursor timestamp."""
        conn = await self._get_connection()
        
        try:
            async with conn.execute("SELECT last_ts FROM cursors WHERE name = ?", (name,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        finally:
            await conn.close()
    
    async def record_llm_usage(self, model: str, prompt_tokens: int, 
                              completion_tokens: int, estimated_cost: float, 
                              request_id: str = None) -> None:
        """Record LLM usage for budget tracking."""
        conn = await self._get_connection()
        
        try:
            await conn.execute("""
                INSERT INTO llm_usage (model, prompt_tokens, completion_tokens, estimated_cost, request_id)
                VALUES (?, ?, ?, ?, ?)
            """, (model, prompt_tokens, completion_tokens, estimated_cost, request_id))
            
            await conn.commit()
        finally:
            await conn.close()
    
    async def get_daily_usage(self, model: str = None) -> Dict[str, Any]:
        """Get 24h usage statistics."""
        conn = await self._get_connection()
        
        try:
            if model:
                async with conn.execute("""
                    SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(estimated_cost), COUNT(*)
                    FROM llm_usage 
                    WHERE model = ? AND timestamp >= datetime('now', '-1 day')
                """, (model,)) as cursor:
                    row = await cursor.fetchone()
            else:
                async with conn.execute("""
                    SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(estimated_cost), COUNT(*)
                    FROM llm_usage 
                    WHERE timestamp >= datetime('now', '-1 day')
                """) as cursor:
                    row = await cursor.fetchone()
            
            if row and row[0]:
                return {
                    'prompt_tokens': row[0],
                    'completion_tokens': row[1],
                    'estimated_cost': row[2],
                    'request_count': row[3]
                }
            return {'prompt_tokens': 0, 'completion_tokens': 0, 'estimated_cost': 0.0, 'request_count': 0}
        finally:
            await conn.close()
    
    async def health_check(self) -> bool:
        """Run database health check."""
        conn = await self._get_connection()
        
        try:
            # Check required tables exist
            tables = []
            async with conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('json_cache_scratch', 'cursors', 'llm_usage', 'writes_log')
            """) as cursor:
                async for row in cursor:
                    tables.append(row[0])
            
            if len(tables) < 4:
                logger.error(f"Missing required tables. Found: {tables}")
                return False
            
            # Run integrity check
            async with conn.execute("PRAGMA integrity_check") as cursor:
                result = await cursor.fetchone()
            
            if result[0] != "ok":
                logger.error(f"Database integrity check failed: {result[0]}")
                return False
            
            logger.info("Database health check passed")
            return True
            
        finally:
            await conn.close()
    
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old JSON cache data."""
        conn = await self._get_connection()
        
        try:
            result = await conn.execute("""
                DELETE FROM json_cache_scratch 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days))
            
            deleted_count = result.rowcount
            await conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old JSON cache records")
            return deleted_count
        finally:
            await conn.close()
    
    async def close(self):
        """Close database manager."""
        pass


# Global database manager instance
_db_manager = None


async def init_db():
    """Initialize the database manager."""
    global _db_manager
    _db_manager = DatabaseManager(DB_PATH)
    await _db_manager.initialize()


async def save_json(id: str, source: str, json_blob: dict) -> None:
    """Save JSON data (async wrapper)."""
    if not _db_manager:
        await init_db()
    await _db_manager.upsert_json(id, source, json_blob)


async def load_json(id: str) -> Optional[dict]:
    """Load JSON data (async wrapper)."""
    if not _db_manager:
        await init_db()
    return await _db_manager.load_json(id)


async def query_recent(source: str, limit: int = 10) -> List[dict]:
    """Query recent JSON data (async wrapper)."""
    if not _db_manager:
        await init_db()
    return await _db_manager.query_recent(source, limit)


async def record_llm_usage(model: str, prompt_tokens: int, completion_tokens: int, 
                          estimated_cost: float, request_id: str = None) -> None:
    """Record LLM usage (async wrapper)."""
    if not _db_manager:
        await init_db()
    await _db_manager.record_llm_usage(model, prompt_tokens, completion_tokens, 
                                      estimated_cost, request_id)


async def get_daily_usage(model: str = None) -> Dict[str, Any]:
    """Get daily usage statistics (async wrapper)."""
    if not _db_manager:
        await init_db()
    return await _db_manager.get_daily_usage(model)


async def get_cursor(name: str) -> Optional[int]:
    """Get cursor timestamp (async wrapper)."""
    if not _db_manager:
        await init_db()
    return await _db_manager.get_cursor(name)


async def set_cursor(name: str, last_ts: int, notes: str = None) -> None:
    """Set cursor for delta fetches (async wrapper)."""
    if not _db_manager:
        await init_db()
    await _db_manager.set_cursor(name, last_ts, notes)


async def health_check() -> bool:
    """Run health check (async wrapper)."""
    if not _db_manager:
        await init_db()
    return await _db_manager.health_check()


async def close_db():
    """Close database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None


# Synchronous wrappers for backward compatibility
def save_json_sync(id: str, source: str, json_blob: dict) -> None:
    """Synchronous wrapper for save_json."""
    asyncio.run(save_json(id, source, json_blob))


def load_json_sync(id: str) -> Optional[dict]:
    """Synchronous wrapper for load_json."""
    return asyncio.run(load_json(id))


def query_recent_sync(source: str, limit: int = 10) -> List[dict]:
    """Synchronous wrapper for query_recent."""
    return asyncio.run(query_recent(source, limit))
