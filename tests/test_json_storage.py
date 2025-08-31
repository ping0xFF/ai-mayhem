#!/usr/bin/env python3
"""
Tests for json_storage module (production-ready version).
"""

import json
import sqlite3
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

import sys
sys.path.append(str(Path(__file__).parent.parent))

from json_storage import (
    DatabaseManager, init_db, save_json, load_json, query_recent,
    record_llm_usage, get_daily_usage, health_check, close_db
)


class TestJsonStorageAsync(unittest.IsolatedAsyncioTestCase):
    """Test cases for async json_storage module."""
    
    async def asyncSetUp(self):
        """Set up test database."""
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Patch the DB_PATH to use our temporary database
        with patch('json_storage.DB_PATH', Path(self.temp_db.name)):
            self.db_manager = DatabaseManager(Path(self.temp_db.name))
            await self.db_manager.initialize()
    
    async def asyncTearDown(self):
        """Clean up test database."""
        if self.db_manager:
            await self.db_manager.close()
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def test_save_and_load_json(self):
        """Test basic save and load functionality."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        await self.db_manager.upsert_json("test_id", "test_source", test_data)
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        loaded_data = await self.db_manager.load_json("test_id")
        self.assertEqual(loaded_data, test_data)
    
    async def test_upsert_behavior(self):
        """Test that saving the same ID twice updates the record, doesn't duplicate."""
        original_data = {"original": "data"}
        updated_data = {"updated": "data"}
        
        # Save original data
        await self.db_manager.upsert_json("upsert_test", "test_source", original_data)
        
        # Save updated data with same ID
        await self.db_manager.upsert_json("upsert_test", "test_source", updated_data)
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Should have updated data, not original
        loaded_data = await self.db_manager.load_json("upsert_test")
        self.assertEqual(loaded_data, updated_data)
        self.assertNotEqual(loaded_data, original_data)
        
        # Verify only one row exists
        conn = await self.db_manager._get_connection()
        async with conn.execute("SELECT COUNT(*) FROM json_cache_scratch WHERE id = ?", ("upsert_test",)) as cursor:
            row = await cursor.fetchone()
            count = row[0]
        await conn.close()
        
        self.assertEqual(count, 1, "Should have exactly one row, not duplicated")
    
    async def test_query_recent(self):
        """Test querying recent entries by source."""
        # Save multiple entries
        await self.db_manager.upsert_json("id1", "nansen", {"data": "first"})
        await self.db_manager.upsert_json("id2", "nansen", {"data": "second"})
        await self.db_manager.upsert_json("id3", "coingecko", {"data": "other_source"})
        await self.db_manager.upsert_json("id4", "nansen", {"data": "third"})
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Query recent nansen entries
        recent_nansen = await self.db_manager.query_recent("nansen", limit=5)
        
        # Should return 3 entries (all nansen sources)
        self.assertEqual(len(recent_nansen), 3)
    
    async def test_query_recent_limit(self):
        """Test that query_recent respects the limit parameter."""
        # Save more entries than the limit
        for i in range(15):
            await self.db_manager.upsert_json(f"id{i}", "test_source", {"index": i})
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Query with limit
        recent = await self.db_manager.query_recent("test_source", limit=5)
        
        # Should return exactly 5 entries
        self.assertEqual(len(recent), 5)
    
    async def test_cursor_operations(self):
        """Test cursor operations for delta fetches."""
        # Set cursor
        await self.db_manager.set_cursor("nansen_wallet_0x123", 1234567890, "Last processed timestamp")
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Get cursor
        cursor_ts = await self.db_manager.get_cursor("nansen_wallet_0x123")
        self.assertEqual(cursor_ts, 1234567890)
        
        # Update cursor
        await self.db_manager.set_cursor("nansen_wallet_0x123", 1234567891, "Updated timestamp")
        await asyncio.sleep(0.3)
        
        updated_ts = await self.db_manager.get_cursor("nansen_wallet_0x123")
        self.assertEqual(updated_ts, 1234567891)
    
    async def test_llm_usage_tracking(self):
        """Test LLM usage tracking."""
        # Record usage
        await self.db_manager.record_llm_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            estimated_cost=0.003,
            request_id="req_123"
        )
        
        await self.db_manager.record_llm_usage(
            model="gpt-4",
            prompt_tokens=200,
            completion_tokens=100,
            estimated_cost=0.006,
            request_id="req_124"
        )
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Get daily usage
        usage = await self.db_manager.get_daily_usage("gpt-4")
        
        self.assertEqual(usage['prompt_tokens'], 300)
        self.assertEqual(usage['completion_tokens'], 150)
        self.assertAlmostEqual(usage['estimated_cost'], 0.009, places=6)
        self.assertEqual(usage['request_count'], 2)
    
    async def test_health_check(self):
        """Test database health check."""
        health = await self.db_manager.health_check()
        self.assertTrue(health)
    
    async def test_cleanup_old_data(self):
        """Test cleanup of old data."""
        # Manually insert old data
        conn = await self.db_manager._get_connection()
        await conn.execute("""
            INSERT INTO json_cache_scratch (id, source, raw_json, created_at)
            VALUES (?, ?, ?, datetime('now', '-1 day'))
        """, ("old_data", "test", json.dumps({"old": "data"})))
        await conn.commit()
        await conn.close()
        
        # Clean up data older than 12 hours (should clean the old data)
        deleted = await self.db_manager.cleanup_old_data(days=0.5)
        self.assertGreaterEqual(deleted, 1)
    
    async def test_json_validation(self):
        """Test that non-JSON-serializable data raises ValueError."""
        # Test with a function (not JSON-serializable)
        non_serializable = {"func": lambda x: x}
        
        with self.assertRaises(ValueError):
            await self.db_manager.upsert_json("test_id", "test_source", non_serializable)
    
    async def test_corrupted_json_handling(self):
        """Test handling of corrupted JSON data in database."""
        # Manually insert corrupted JSON
        conn = await self.db_manager._get_connection()
        await conn.execute("""
            INSERT INTO json_cache_scratch (id, source, raw_json)
            VALUES (?, ?, ?)
        """, ("corrupted", "test", "invalid json {"))
        await conn.commit()
        await conn.close()
        
        # Should handle corrupted JSON gracefully
        loaded = await self.db_manager.load_json("corrupted")
        self.assertIsNone(loaded)
    
    async def test_batch_writing(self):
        """Test that batch writing works correctly."""
        # Add multiple items quickly
        for i in range(5):
            await self.db_manager.upsert_json(f"batch_test_{i}", "test", {"batch": i})
        
        # Wait for batch to flush
        await asyncio.sleep(0.3)
        
        # Verify all items were written
        for i in range(5):
            data = await self.db_manager.load_json(f"batch_test_{i}")
            self.assertEqual(data, {"batch": i})


class TestJsonStorageSync(unittest.TestCase):
    """Test cases for synchronous wrappers."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Patch the DB_PATH to use our temporary database
        with patch('json_storage.DB_PATH', Path(self.temp_db.name)):
            from json_storage import save_json_sync, load_json_sync, query_recent_sync
            self.save_json = save_json_sync
            self.load_json = load_json_sync
            self.query_recent = query_recent_sync
    
    def tearDown(self):
        """Clean up test database."""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def test_sync_wrappers(self):
        """Test synchronous wrapper functions."""
        test_data = {"sync": "test"}
        
        # Test save and load
        self.save_json("sync_test", "test_source", test_data)
        loaded = self.load_json("sync_test")
        self.assertEqual(loaded, test_data)
        
        # Test query recent - use a unique source to avoid conflicts
        unique_source = f"test_source_{id(self)}"
        self.save_json("sync_test_unique", unique_source, test_data)
        recent = self.query_recent(unique_source, limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0], test_data)


if __name__ == '__main__':
    unittest.main()

