#!/usr/bin/env python3
"""
Test cursor persistence between runs to catch the wallet seeding issue.
"""

import unittest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock
import sys

sys.path.append(str(Path(__file__).parent.parent))

from nodes.planner import planner_node
from json_storage import get_cursor, set_cursor, init_db, DatabaseManager
from nodes.config import load_monitored_wallets


class TestCursorPersistence(unittest.IsolatedAsyncioTestCase):
    """Test that cursors persist between runs and wallet seeding doesn't repeat."""

    async def asyncSetUp(self):
        """Set up test database."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Patch the database path
        self.db_patcher = patch('json_storage.DB_PATH', Path(self.temp_db.name))
        self.db_patcher.start()
        
        # Initialize database
        await init_db()
        
        # Set up test wallets
        self.test_wallets = [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12"
        ]

    async def asyncTearDown(self):
        """Clean up test database."""
        self.db_patcher.stop()
        os.unlink(self.temp_db.name)

    @patch('nodes.planner.load_monitored_wallets')
    async def test_cursor_persistence_between_runs(self, mock_load_wallets):
        """Test that cursors persist between planner runs."""
        mock_load_wallets.return_value = self.test_wallets
        
        # First run - should seed wallets
        state1 = {
            "cursors": {},
            "spent_today": 0.0
        }
        
        result1 = await planner_node(state1)
        
        # Verify wallets were seeded
        cursors = result1.get("cursors", {})
        self.assertIn("wallet:0x1234567890abcdef1234567890abcdef12345678", cursors)
        self.assertIn("wallet:0xabcdef1234567890abcdef1234567890abcdef12", cursors)
        self.assertEqual(len([k for k in cursors.keys() if k.startswith("wallet:")]), 2)
        
        # Verify cursors were saved to database
        cursor1 = await get_cursor("wallet:0x1234567890abcdef1234567890abcdef12345678")
        cursor2 = await get_cursor("wallet:0xabcdef1234567890abcdef1234567890abcdef12")
        self.assertIsNotNone(cursor1)
        self.assertIsNotNone(cursor2)
        
        # Second run - should NOT seed wallets again
        state2 = {
            "cursors": {},  # Empty state again (simulating fresh run)
            "spent_today": 0.0
        }
        
        result2 = await planner_node(state2)
        
        # Verify wallets were NOT seeded again
        self.assertNotIn("Seeding 2 monitored wallets", str(result2))
        self.assertNotIn("Seeded cursor for", str(result2))
        
        # Verify cursors are still in the result (loaded from DB)
        self.assertIn("wallet:0x1234567890abcdef1234567890abcdef12345678", result2.get("cursors", {}))
        self.assertIn("wallet:0xabcdef1234567890abcdef1234567890abcdef12", result2.get("cursors", {}))

    @patch('nodes.planner.load_monitored_wallets')
    async def test_cursor_loading_from_database(self, mock_load_wallets):
        """Test that planner loads cursors from database when state is empty."""
        mock_load_wallets.return_value = self.test_wallets
        
        # Pre-populate database with cursors
        await set_cursor("wallet:0x1234567890abcdef1234567890abcdef12345678", 12345, "Test cursor")
        await set_cursor("wallet:0xabcdef1234567890abcdef1234567890abcdef12", 67890, "Test cursor")
        await set_cursor("lp", 11111, "Test LP cursor")
        
        # Run planner with empty state
        state = {
            "cursors": {},
            "spent_today": 0.0
        }
        
        result = await planner_node(state)
        
        # Verify cursors were loaded from database
        cursors = result.get("cursors", {})
        self.assertEqual(cursors.get("wallet:0x1234567890abcdef1234567890abcdef12345678"), 12345)
        self.assertEqual(cursors.get("wallet:0xabcdef1234567890abcdef1234567890abcdef12"), 67890)
        self.assertEqual(cursors.get("lp"), 11111)
        
        # Verify no seeding occurred
        self.assertNotIn("Seeding", str(result))

    @patch('nodes.planner.load_monitored_wallets')
    async def test_cursor_state_priority(self, mock_load_wallets):
        """Test that state cursors take priority over database cursors."""
        mock_load_wallets.return_value = self.test_wallets
        
        # Pre-populate database with cursors
        await set_cursor("wallet:0x1234567890abcdef1234567890abcdef12345678", 12345, "DB cursor")
        
        # Run planner with state that has different cursor value
        state = {
            "cursors": {
                "wallet:0x1234567890abcdef1234567890abcdef12345678": 99999
            },
            "spent_today": 0.0
        }
        
        result = await planner_node(state)
        
        # Verify state cursor takes priority
        cursors = result.get("cursors", {})
        self.assertEqual(cursors.get("wallet:0x1234567890abcdef1234567890abcdef12345678"), 99999)
        
        # Verify no seeding occurred
        self.assertNotIn("Seeding", str(result))


if __name__ == '__main__':
    unittest.main()
