#!/usr/bin/env python3
"""
Safely clear all data from the AI Mayhem database while preserving schema.

This script removes all records from all tables but keeps the table structures
intact so the system can run fresh.
"""

import sqlite3
import os
from pathlib import Path

def clear_database():
    """Clear all data from the database while preserving schema."""

    db_path = Path(__file__).parent / "agent_state.db"

    if not db_path.exists():
        print("❌ Database file not found!")
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get all table names (excluding system tables)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()

        print("🗑️  Clearing database data...")
        print(f"📊 Found {len(tables)} tables to clear")

        # Clear each table
        cleared_count = 0
        for (table_name,) in tables:
            # Get count before clearing
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]

            # Clear the table
            cursor.execute(f"DELETE FROM {table_name}")
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")  # Reset autoincrement

            print(f"   ✅ Cleared {count} records from {table_name}")
            cleared_count += count

        # Reset all sequences and vacuum to reclaim space
        conn.commit()
        cursor.execute("VACUUM")

        conn.close()

        print(f"\n🎉 Successfully cleared {cleared_count} total records!")
        print("📋 Database is now fresh and ready for new runs.")
        print("💡 Run 'python cli.py run --mode=wallet-brief' to generate fresh data.")

        return True

    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

def show_database_stats():
    """Show current database statistics."""
    db_path = Path(__file__).parent / "agent_state.db"

    if not db_path.exists():
        print("❌ Database file not found!")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        print("📊 Current Database Statistics:")
        print("=" * 50)

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()

        total_records = 0
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print("25")
            total_records += count

        print("=" * 50)
        print(f"📈 Total Records: {total_records}")

        conn.close()

    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        show_database_stats()
    else:
        print("🗑️  AI Mayhem Database Cleaner")
        print("This will clear ALL data from the database while preserving the schema.")
        print()

        # Show current stats first
        show_database_stats()
        print()

        # Confirm before clearing
        response = input("⚠️  Are you sure you want to clear all data? (type 'yes' to confirm): ")
        if response.lower() == 'yes':
            print()
            if clear_database():
                print("\n✅ Database cleared successfully!")
                print("💡 You can now run fresh monitoring sessions.")
            else:
                print("\n❌ Failed to clear database.")
                sys.exit(1)
        else:
            print("❌ Operation cancelled.")
