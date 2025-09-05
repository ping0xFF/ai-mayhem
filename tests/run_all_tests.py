#!/usr/bin/env python3
"""
Comprehensive Test Runner for AI Mayhem
========================================

Runs all tests in the tests directory and provides a detailed report.
This ensures we don't accidentally skip broken tests.

Usage:
    python tests/run_all_tests.py        # Run all tests
    python tests/run_all_tests.py -v     # Verbose output
    python tests/run_all_tests.py -q     # Quiet mode (just summary)
"""

import sys
import os
import glob
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test files to run (in dependency order)
TEST_FILES = [
    "test_json_storage.py",          # Foundation - no dependencies
    "test_three_layer_data_model.py", # Depends on json_storage
    "test_enhanced_lp.py",           # LP functionality
    "test_lp_brief_gating.py",       # LP brief logic
    "test_planner_worker.py",        # Core planner/worker (rule-based)
    "test_agent.py",                 # Main agent (may be broken)
    "test_live.py",                  # Live integration (may require setup)
]

# Design check script
DESIGN_CHECK_SCRIPT = "scripts/design_check.py"

class TestRunner:
    """Comprehensive test runner with detailed reporting."""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.verbose = verbose
        self.quiet = quiet
        self.results = {}
        self.start_time = None

    def log(self, message: str, force: bool = False):
        """Log message based on verbosity settings."""
        if force or (self.verbose and not self.quiet):
            print(message)

    def run_single_test(self, test_file: str) -> Tuple[bool, str]:
        """Run a single test file and return (success, output)."""
        test_path = Path(__file__).parent / test_file

        if not test_path.exists():
            return False, f"Test file not found: {test_file}"

        self.log(f"🧪 Running {test_file}...")

        try:
            # Run with python -m unittest for better isolation
            cmd = [sys.executable, "-m", "unittest", str(test_path), "-v" if self.verbose else "--quiet"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per test
                cwd=Path(__file__).parent.parent
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            if success:
                self.log(f"✅ {test_file} PASSED", force=True)
                if self.verbose:
                    self.log(output)
            else:
                self.log(f"❌ {test_file} FAILED", force=True)
                if not self.quiet:
                    self.log("Output:", force=True)
                    self.log(output, force=True)

            return success, output

        except subprocess.TimeoutExpired:
            error_msg = f"Test {test_file} timed out after 5 minutes"
            self.log(f"⏰ {error_msg}", force=True)
            return False, error_msg

        except Exception as e:
            error_msg = f"Error running {test_file}: {str(e)}"
            self.log(f"💥 {error_msg}", force=True)
            return False, error_msg

    def run_design_check(self) -> Tuple[bool, str]:
        """Run the design check script."""
        design_check_path = Path(__file__).parent.parent / DESIGN_CHECK_SCRIPT
        
        if not design_check_path.exists():
            return False, f"Design check script not found: {DESIGN_CHECK_SCRIPT}"

        self.log("🔍 Running design ⇄ implementation checkup...")

        try:
            cmd = [sys.executable, str(design_check_path), "--exit-code"]
            if not self.verbose:
                cmd.append("--quiet")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout
                cwd=Path(__file__).parent.parent
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            if success:
                self.log("✅ Design check PASSED", force=True)
            else:
                self.log("❌ Design check FAILED", force=True)
                if not self.quiet:
                    self.log("Output:", force=True)
                    self.log(output, force=True)

            return success, output

        except subprocess.TimeoutExpired:
            error_msg = "Design check timed out after 1 minute"
            self.log(f"⏰ {error_msg}", force=True)
            return False, error_msg

        except Exception as e:
            error_msg = f"Error running design check: {str(e)}"
            self.log(f"💥 {error_msg}", force=True)
            return False, error_msg

    def run_all_tests(self) -> Dict[str, Tuple[bool, str]]:
        """Run all test files and collect results."""
        self.start_time = time.time()
        self.log("🚀 Starting comprehensive test suite...", force=True)
        self.log(f"📁 Test directory: {Path(__file__).parent}", force=True)
        self.log(f"📋 Will run {len(TEST_FILES)} test files + design check", force=True)
        self.log("=" * 60, force=True)

        results = {}

        # Run design check first
        success, output = self.run_design_check()
        results["design_check"] = (success, output)
        self.log("")  # Add spacing

        # Run all test files
        for test_file in TEST_FILES:
            success, output = self.run_single_test(test_file)
            results[test_file] = (success, output)
            self.log("")  # Add spacing between tests

        return results

    def print_summary(self, results: Dict[str, Tuple[bool, str]]):
        """Print comprehensive test summary."""
        total_time = time.time() - self.start_time

        passed = sum(1 for success, _ in results.values() if success)
        failed = len(results) - passed

        self.log("=" * 60, force=True)
        self.log("📊 TEST SUMMARY", force=True)
        self.log("=" * 60, force=True)
        self.log(f"⏱️  Total time: {total_time:.2f}s", force=True)
        self.log(f"✅ Passed: {passed}/{len(results)}", force=True)
        self.log(f"❌ Failed: {failed}/{len(results)}", force=True)
        self.log("", force=True)

        if failed > 0:
            self.log("❌ FAILED TESTS:", force=True)
            for test_file, (success, output) in results.items():
                if not success:
                    self.log(f"   • {test_file}", force=True)
            self.log("", force=True)

        self.log("📋 DETAILED RESULTS:", force=True)
        for test_file, (success, output) in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            self.log(f"   {status} {test_file}", force=True)

        self.log("", force=True)
        self.log("🎯 RECOMMENDATIONS:", force=True)
        if failed == 0:
            self.log("   🎉 All tests passing! Great job!", force=True)
        else:
            self.log("   🔧 Fix failed tests before committing", force=True)
            self.log("   📝 Update this script if you add new test files", force=True)
            self.log("   🐛 Check import errors - tests may be outdated", force=True)

        return failed == 0

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run all AI Mayhem tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (summary only)")
    parser.add_argument("--list", action="store_true", help="Just list test files, don't run")

    args = parser.parse_args()

    if args.list:
        print("📋 Test files that will be run:")
        for i, test_file in enumerate(TEST_FILES, 1):
            print(f"   {i}. {test_file}")
        return

    runner = TestRunner(verbose=args.verbose, quiet=args.quiet)
    results = runner.run_all_tests()
    success = runner.print_summary(results)

    # Exit with appropriate code for CI/CD
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

