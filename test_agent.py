#!/usr/bin/env python3
"""
Test suite for the LangGraph agent.
Covers core functionality without relying on actual LLM calls.
"""

import unittest
import asyncio
import json
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import the agent code
from langgraph_agent import (
    AgentState, 
    LangGraphAgent, 
    planner_node, 
    worker_node, 
    should_continue,
    call_llm
)
from langchain_core.messages import HumanMessage, AIMessage


class CleanTextTestResult(unittest.TextTestResult):
    """Simple formatter for clean test output."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.current_class = None
        self.verbosity = verbosity
        
    def startTest(self, test):
        super().startTest(test)
        class_name = test.__class__.__name__
        if class_name != self.current_class:
            self.stream.write(f"{class_name}\n")
            self.current_class = class_name
            
    def addSuccess(self, test):
        # Don't call super() to suppress default output
        if self.verbosity > 1:
            self.stream.write(f"  ✓ {test._testMethodName}\n")
            
    def addError(self, test, err):
        super().addError(test, err)  # Keep error tracking
        if self.verbosity > 1:
            self.stream.write(f"  ✗ {test._testMethodName}\n")
            
    def addFailure(self, test, err):
        super().addFailure(test, err)  # Keep failure tracking
        if self.verbosity > 1:
            self.stream.write(f"  ✗ {test._testMethodName}\n")


class TestAgentState(unittest.TestCase):
    """Test the AgentState TypedDict structure."""
    
    # Basic validation test to ensure AgentState TypedDict can be created with correct structure
    # Acts as a canary test to catch breaking changes to the core state dictionary structure
    def test_agent_state_creation(self):
        """Test creating a valid AgentState."""
        state: AgentState = {
            "goal": "Test goal",
            "plan": ["Step 1", "Step 2"],
            "current_step": 0,
            "completed_actions": [],
            "messages": [HumanMessage(content="test")],
            "status": "planning"
        }
        
        self.assertEqual(state["goal"], "Test goal")
        self.assertEqual(len(state["plan"]), 2)
        self.assertEqual(state["current_step"], 0)
        self.assertEqual(state["status"], "planning")


class TestNodeFunctions(unittest.TestCase):
    """Test individual node functions with mocked LLM calls."""
    
    def setUp(self):
        """Set up test state."""
        self.initial_state: AgentState = {
            "goal": "Create a simple test application",
            "plan": [],
            "current_step": 0,
            "completed_actions": [],
            "messages": [HumanMessage(content="Goal: Create a simple test application")],
            "status": "planning"
        }
    
    @patch('langgraph_agent.call_llm')
    def test_planner_node_success(self, mock_call_llm):
        """Test planner node creates a valid plan."""
        # Mock LLM response
        mock_plan = ["Step 1: Design", "Step 2: Implement", "Step 3: Test"]
        mock_call_llm.return_value = (json.dumps(mock_plan), {"tokens": 100})
        
        result = planner_node(self.initial_state)
        
        # Verify plan was created
        self.assertEqual(result["plan"], mock_plan)
        self.assertEqual(result["current_step"], 0)
        self.assertEqual(result["status"], "working")
        self.assertEqual(len(result["messages"]), 2)  # Original + new AI message
        
        # Verify LLM was called with correct parameters
        mock_call_llm.assert_called_once()
        args, kwargs = mock_call_llm.call_args
        self.assertIn("Create a simple test application", args[0])
    
    @patch('langgraph_agent.call_llm')
    def test_planner_node_json_error(self, mock_call_llm):
        """Test planner node handles invalid JSON response."""
        # Mock invalid JSON response
        mock_call_llm.return_value = ("Invalid JSON response", {"tokens": 50})
        
        result = planner_node(self.initial_state)
        
        # Verify error handling
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["plan"]), 0)
        
        # Check error message was added
        self.assertTrue(any("Failed to create plan" in msg.content for msg in result["messages"] if isinstance(msg, AIMessage)))
    
    def test_planner_node_existing_plan(self):
        """Test planner node with existing plan."""
        state_with_plan = self.initial_state.copy()
        state_with_plan["plan"] = ["Existing step"]
        state_with_plan["current_step"] = 0
        state_with_plan["completed_actions"] = []
        
        result = planner_node(state_with_plan)
        
        # Should set status to working since plan exists
        self.assertEqual(result["status"], "working")
        self.assertEqual(result["plan"], ["Existing step"])
    
    @patch('langgraph_agent.call_llm')
    def test_worker_node_execution(self, mock_call_llm):
        """Test worker node executes a step."""
        # Setup state with plan
        state_with_plan = self.initial_state.copy()
        state_with_plan["plan"] = ["Write unit tests", "Run tests"]
        state_with_plan["status"] = "working"
        
        # Mock worker response
        mock_call_llm.return_value = ("I created comprehensive unit tests for the application", {"tokens": 75})
        
        result = worker_node(state_with_plan)
        
        # Verify step execution
        self.assertEqual(result["current_step"], 1)
        self.assertEqual(len(result["completed_actions"]), 1)
        self.assertEqual(result["status"], "working")  # Still more steps
        
        # Check completed action details
        action = result["completed_actions"][0]
        self.assertEqual(action["step"], 0)
        self.assertEqual(action["description"], "Write unit tests")
        self.assertIn("unit tests", action["result"])
    
    def test_worker_node_completion(self):
        """Test worker node when all steps are completed."""
        # Setup state with completed plan
        state_completed = self.initial_state.copy()
        state_completed["plan"] = ["Step 1"]
        state_completed["current_step"] = 1  # Beyond plan length
        
        result = worker_node(state_completed)
        
        # Should mark as completed
        self.assertEqual(result["status"], "completed")
    
    def test_should_continue_routing(self):
        """Test the routing function."""
        # Test planning status
        planning_state = self.initial_state.copy()
        planning_state["status"] = "planning"
        self.assertEqual(should_continue(planning_state), "plan")
        
        # Test working status
        working_state = self.initial_state.copy()
        working_state["status"] = "working"
        self.assertEqual(should_continue(working_state), "work")
        
        # Test completed status
        completed_state = self.initial_state.copy()
        completed_state["status"] = "completed"
        self.assertEqual(should_continue(completed_state), "__end__")
        
        # Test failed status
        failed_state = self.initial_state.copy()
        failed_state["status"] = "failed"
        self.assertEqual(should_continue(failed_state), "__end__")


class TestLangGraphAgent(unittest.TestCase):
    """Test the main agent class."""
    
    def setUp(self):
        """Set up test environment."""
        self.agent = LangGraphAgent()
    
    def test_agent_initialization(self):
        """Test agent initializes properly."""
        self.assertIsNotNone(self.agent.app)
        self.assertIsNone(self.agent._checkpointer_cache)  # Lazy loaded
    
    @patch('langgraph_agent.call_llm')
    async def test_agent_run_success(self, mock_call_llm):
        """Test full agent run with mocked LLM."""
        # Mock responses for planner and worker
        mock_responses = [
            (json.dumps(["Design system", "Implement features"]), {"tokens": 100}),  # Planner
            ("Designed a comprehensive system architecture", {"tokens": 80}),        # Worker 1
            ("Implemented all core features successfully", {"tokens": 85})           # Worker 2
        ]
        mock_call_llm.side_effect = mock_responses
        
        result = await self.agent.run("Build a test system", "test-thread")
        
        # Verify successful completion
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["goal"], "Build a test system")
        self.assertEqual(len(result["completed_actions"]), 2)
        self.assertEqual(result["current_step"], 2)
        
        # Verify LLM was called appropriate number of times
        self.assertEqual(mock_call_llm.call_count, 3)  # 1 planner + 2 worker calls
    
    @patch('langgraph_agent.call_llm')
    async def test_agent_run_planning_failure(self, mock_call_llm):
        """Test agent handles planning failure."""
        # Mock invalid JSON from planner
        mock_call_llm.return_value = ("Not valid JSON", {"tokens": 50})
        
        result = await self.agent.run("Invalid goal", "test-thread")
        
        # Should fail gracefully
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["plan"]), 0)
    
    async def test_agent_resume_empty(self):
        """Test that resume works with nonexistent thread."""
        result = await self.agent.resume("nonexistent-thread")
        self.assertIsNone(result)  # Should return None for nonexistent thread
    
    def test_list_threads_enabled(self):
        """Test that thread listing works (returns empty list initially)."""
        threads = self.agent.list_threads()
        self.assertIsInstance(threads, list)  # Should return a list (empty initially)


class TestLLMIntegration(unittest.TestCase):
    """Test LLM integration (requires running LiteLLM server)."""
    
    def setUp(self):
        """Skip these tests if LiteLLM is not available."""
        self.skip_if_no_llm = False# Set to False to run live tests
    
    def test_call_llm_mock(self):
        """Test LLM call function with mocking."""
        with patch('requests.post') as mock_post:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}
            }
            mock_post.return_value = mock_response
            
            result, usage = call_llm("Test prompt")
            
            self.assertEqual(result, "Test response")
            self.assertEqual(usage["prompt_tokens"], 10)
            self.assertEqual(usage["completion_tokens"], 5)
            
            # Verify request was made correctly
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertIn("chat/completions", args[0])


def run_basic_tests():
    """Run basic tests that don't require external dependencies."""
    print("Running LangGraph Agent Tests...\n")
    
    # Create test suite with only basic tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAgentState))
    suite.addTests(loader.loadTestsFromTestCase(TestNodeFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestLangGraphAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMIntegration))
    
    # Run tests with clean formatter
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CleanTextTestResult)
    result = runner.run(suite)
    
    # Summary
    if result.wasSuccessful():
        print("\nAll tests passed!")
    else:
        print(f"\n{len(result.failures)} failures, {len(result.errors)} errors")
        
    return result.wasSuccessful()


async def run_integration_test():
    """Run a simple integration test with mocked LLM."""
    print("\nIntegration Test")
    
    with patch('langgraph_agent.call_llm') as mock_llm:
        # Mock successful planning and execution
        mock_llm.side_effect = [
            (json.dumps(["Test step 1", "Test step 2"]), {"tokens": 100}),
            ("Completed test step 1 successfully", {"tokens": 50}),
            ("Completed test step 2 successfully", {"tokens": 55})
        ]
        
        agent = LangGraphAgent()
        try:
            result = await agent.run("Test integration", "integration-test")
            
            if result['status'] == 'completed':
                print("  ✓ End-to-end workflow execution with persistence")
                return True
            else:
                print("  ✗ End-to-end workflow execution")
                return False
        finally:
            await agent.close()  # Close the database connection


if __name__ == "__main__":
    # Run basic unit tests
    success = run_basic_tests()
    
    # Run integration test
    integration_success = asyncio.run(run_integration_test())
    
    if success and integration_success:
        print("\nAll tests successful!")
        exit(0)
    else:
        print("\nSome tests failed!")
        exit(1)