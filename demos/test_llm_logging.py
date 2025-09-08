#!/usr/bin/env python3
"""
Test LLM logging functionality.
"""

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from llm_client import llm_call, _log_interaction, HAIKU_MODEL

async def test_error_logging():
    """Test error logging with pretty printing."""
    print("🧪 Testing error logging...")
    
    try:
        # This will fail because we're passing invalid messages
        await llm_call([
            {
                "role": "invalid_role",  # This should cause an error
                "content": "Test message"
            }
        ], model=HAIKU_MODEL)
    except Exception as e:
        print(f"✅ Expected error caught: {e}")
    
    # Check the log file
    log_path = Path(__file__).parent.parent / "logs" / f"llm-errors-{datetime.date.today().isoformat()}.jsonl"
    if log_path.exists():
        with open(log_path) as f:
            content = f.read()
            print("\n📝 Error log content:")
            print(content)
            
            # Verify JSON formatting
            try:
                for line in content.strip().split("\n\n"):
                    if line.strip():
                        entry = json.loads(line)
                        assert isinstance(entry, dict)
                        assert "timestamp" in entry
                        assert "error" in entry
                        assert "model" in entry
                        assert "messages" in entry
                        assert isinstance(entry["messages"], list)
                        for msg in entry["messages"]:
                            assert "role" in msg
                            assert "content" in msg
                print("✅ Log entries are valid JSON with correct structure")
            except Exception as e:
                print(f"❌ Error validating log format: {e}")
    else:
        print("❌ No error log file found")

if __name__ == "__main__":
    import asyncio
    import datetime
    asyncio.run(test_error_logging())
