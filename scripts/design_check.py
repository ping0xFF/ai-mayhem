#!/usr/bin/env python3
"""
Design ⇄ Implementation Checkup Script
=====================================

Automated verification that README and intended architecture match actual code.
Checks for stale references, required DB tables, and provider selection.
"""

import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from real_apis.provider_router import get_wallet_provider
    PROVIDER_ROUTER_AVAILABLE = True
except ImportError:
    PROVIDER_ROUTER_AVAILABLE = False


class DesignChecker:
    """Comprehensive design ⇄ implementation checker."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        self.passed = []
        self.base_dir = Path(__file__).parent.parent
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with level."""
        if self.verbose or level in ["ERROR", "WARNING"]:
            prefix = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "SUCCESS": "✅"}
            print(f"{prefix.get(level, 'ℹ️')} {message}")
    
    def check_stale_references(self) -> bool:
        """Check for stale references to removed files/APIs."""
        self.log("Checking for stale references...")
        
        stale_patterns = [
            "planner_worker.py",  # Removed file
            "BITQUERY_LIVE",      # Deprecated env var
        ]
        
        found_stale = False
        
        for pattern in stale_patterns:
            try:
                result = subprocess.run(
                    ["grep", "-r", "-n", "--exclude-dir=.git", "--exclude-dir=__pycache__", "--exclude=*.pyc", pattern, str(self.base_dir)],
                    capture_output=True,
                    text=True,
                    cwd=self.base_dir
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    # Filter out false positives
                    filtered_lines = []
                    for line in lines:
                        if pattern == "planner_worker.py":
                            # Allow references in test files, README removal notes, and design check script
                            if ("test_planner_worker.py" in line or 
                                "removed" in line.lower() or 
                                "design_check.py" in line):
                                continue
                        elif pattern == "BITQUERY_LIVE":
                            # Allow references in comments about deprecation and design check script
                            if ("deprecated" in line.lower() or 
                                "old" in line.lower() or 
                                "design_check.py" in line):
                                continue
                        filtered_lines.append(line)
                    
                    if filtered_lines:
                        found_stale = True
                        self.errors.append(f"Stale reference to '{pattern}' found:")
                        for line in filtered_lines[:5]:  # Show first 5 matches
                            self.errors.append(f"  {line}")
                        if len(filtered_lines) > 5:
                            self.errors.append(f"  ... and {len(filtered_lines) - 5} more")
                
            except FileNotFoundError:
                self.warnings.append(f"grep command not found, skipping stale reference check for '{pattern}'")
        
        if not found_stale:
            self.passed.append("No stale references found")
            return True
        return False
    
    def check_database_tables(self) -> bool:
        """Check that required database tables exist."""
        self.log("Checking database tables...")
        
        db_path = self.base_dir / "agent_state.db"
        if not db_path.exists():
            self.warnings.append("Database file not found - may need to run agent first")
            return True
        
        required_tables = [
            "json_cache_scratch",
            "normalized_events", 
            "artifacts"
        ]
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = []
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
                else:
                    # Check if table has data
                    cursor.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cursor.fetchone()[0]
                    self.log(f"Table '{table}' exists with {count} rows")
            
            conn.close()
            
            if missing_tables:
                self.errors.append(f"Missing required database tables: {missing_tables}")
                return False
            else:
                self.passed.append("All required database tables exist")
                return True
                
        except Exception as e:
            self.errors.append(f"Database check failed: {e}")
            return False
    
    def check_provider_router(self) -> bool:
        """Check that provider router is working correctly."""
        self.log("Checking provider router...")
        
        if not PROVIDER_ROUTER_AVAILABLE:
            self.errors.append("Provider router not available (import failed)")
            return False
        
        try:
            router = get_wallet_provider()
            selected_provider = router.get_selected_provider()
            
            self.log(f"Selected provider: {selected_provider}")
            self.log(f"Available providers: {router.available_providers}")
            self.log(f"Fallback chain: {router.fallback_chain}")
            
            # Check that Alchemy is properly integrated
            if "alchemy" in router.available_providers:
                self.passed.append("Alchemy provider is available and integrated")
            else:
                self.warnings.append("Alchemy provider not available (check ALCHEMY_API_KEY)")
            
            # Check that fallback chain is reasonable
            if len(router.fallback_chain) >= 2:  # At least one real provider + mock
                self.passed.append("Fallback chain is properly configured")
            else:
                self.warnings.append("Fallback chain may be too short")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Provider router check failed: {e}")
            return False
    
    def check_environment_variables(self) -> bool:
        """Check environment variable consistency."""
        self.log("Checking environment variables...")
        
        # Check for deprecated variables
        deprecated_vars = ["BITQUERY_LIVE"]
        found_deprecated = []
        
        for var in deprecated_vars:
            if os.getenv(var):
                found_deprecated.append(var)
        
        if found_deprecated:
            self.warnings.append(f"Deprecated environment variables found: {found_deprecated}")
        
        # Check for required variables (if any are set)
        api_keys = {
            "ALCHEMY_API_KEY": "Alchemy",
            "COVALENT_API_KEY": "Covalent", 
            "BITQUERY_ACCESS_TOKEN": "Bitquery"
        }
        
        available_providers = []
        for var, provider in api_keys.items():
            if os.getenv(var):
                available_providers.append(provider)
        
        if available_providers:
            self.passed.append(f"API keys found for: {', '.join(available_providers)}")
        else:
            self.warnings.append("No API keys found - will use mock data")
        
        return True
    
    def check_file_structure(self) -> bool:
        """Check that required files exist."""
        self.log("Checking file structure...")
        
        required_files = [
            "real_apis/provider_router.py",
            "real_apis/alchemy_provider.py",
            "real_apis/covalent.py",
            "real_apis/bitquery.py",
            "nodes/worker.py",
            "nodes/planner.py",
            "nodes/analyze.py",
            "nodes/brief.py",
            "nodes/memory.py",
            ".env.example"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.base_dir / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.errors.append(f"Missing required files: {missing_files}")
            return False
        else:
            self.passed.append("All required files exist")
            return True
    
    def run_all_checks(self) -> bool:
        """Run all design checks and return overall status."""
        self.log("Starting design ⇄ implementation checkup...", "INFO")
        
        checks = [
            ("Stale References", self.check_stale_references),
            ("Database Tables", self.check_database_tables),
            ("Provider Router", self.check_provider_router),
            ("Environment Variables", self.check_environment_variables),
            ("File Structure", self.check_file_structure),
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            self.log(f"\n--- {check_name} ---")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.errors.append(f"{check_name} check failed with exception: {e}")
                all_passed = False
        
        # Print summary
        self.log(f"\n--- SUMMARY ---")
        self.log(f"✅ Passed: {len(self.passed)}")
        self.log(f"⚠️  Warnings: {len(self.warnings)}")
        self.log(f"❌ Errors: {len(self.errors)}")
        
        if self.passed:
            self.log("\nPassed checks:")
            for item in self.passed:
                self.log(f"  ✅ {item}")
        
        if self.warnings:
            self.log("\nWarnings:")
            for item in self.warnings:
                self.log(f"  ⚠️  {item}")
        
        if self.errors:
            self.log("\nErrors:")
            for item in self.errors:
                self.log(f"  ❌ {item}")
        
        return all_passed


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Design ⇄ Implementation Checkup")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", action="store_true", help="Quiet output")
    parser.add_argument("--exit-code", action="store_true", help="Exit with non-zero code on errors")
    
    args = parser.parse_args()
    
    checker = DesignChecker(verbose=args.verbose)
    success = checker.run_all_checks()
    
    if args.exit_code and not success:
        sys.exit(1)
    elif not success:
        print("\n⚠️  Some checks failed. Run with -v for details.")
        sys.exit(1)
    else:
        print("\n✅ All design checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
