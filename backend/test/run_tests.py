#!/usr/bin/env python3
"""
Test runner script for Athletes Networking API

This script provides convenient commands to run different categories of tests.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run tests for Athletes Networking API")
    parser.add_argument(
        "category",
        choices=[
            "all", "services", "api", "unit", "integration", 
            "auth", "athletes", "scouts", "media", "opportunities",
            "admin", "coverage", "fast", "slow"
        ],
        help="Test category to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--no-cov",
        action="store_true",
        help="Run tests without coverage"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["pytest"]
    
    if args.verbose:
        cmd.append("-v")
    
    if args.parallel:
        cmd.extend(["-n", "auto"])
    
    if not args.no_cov:
        cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])
    
    # Add category-specific arguments
    if args.category == "all":
        cmd.append("test/")
    elif args.category == "services":
        cmd.append("test/services/")
    elif args.category == "api":
        cmd.append("test/api/")
    elif args.category == "unit":
        cmd.extend(["-m", "unit", "test/"])
    elif args.category == "integration":
        cmd.extend(["-m", "integration", "test/"])
    elif args.category == "auth":
        cmd.extend(["-m", "auth", "test/"])
    elif args.category == "athletes":
        cmd.extend(["-m", "athlete", "test/"])
    elif args.category == "scouts":
        cmd.extend(["-m", "scout", "test/"])
    elif args.category == "media":
        cmd.extend(["-m", "media", "test/"])
    elif args.category == "opportunities":
        cmd.extend(["-m", "opportunity", "test/"])
    elif args.category == "admin":
        cmd.extend(["-m", "admin", "test/"])
    elif args.category == "coverage":
        cmd.extend([
            "--cov=app",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "--cov-fail-under=80",
            "test/"
        ])
    elif args.category == "fast":
        cmd.extend(["-m", "not slow", "test/"])
    elif args.category == "slow":
        cmd.extend(["-m", "slow", "test/"])
    
    # Change to backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    
    # Run the tests
    return_code = run_command(cmd)
    
    if return_code == 0:
        print("\n✅ All tests passed!")
        if args.category == "coverage" or not args.no_cov:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(return_code)


if __name__ == "__main__":
    main() 