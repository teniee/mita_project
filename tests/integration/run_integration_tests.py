#!/usr/bin/env python3
"""
Integration Test Runner for MITA Authentication
===============================================

This script orchestrates the integration test suite for MITA authentication flows.
It handles test environment setup, execution, and cleanup for CI/CD pipelines.

Usage:
    python run_integration_tests.py [options]

Options:
    --fast          Run fast tests only (skip slow/performance tests)
    --security      Run security tests only
    --mobile        Run mobile-specific tests only
    --performance   Run performance tests only
    --parallel      Run tests in parallel
    --ci            Run in CI mode with appropriate timeouts and retries
    --local         Run against local development server
    --staging       Run against staging environment
    --production    Run against production (read-only tests only)
"""

import argparse
import asyncio
import os
import sys
import subprocess
import time
import signal
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import docker
import redis
import httpx
import pytest
import psutil


class IntegrationTestRunner:
    """Orchestrates integration test execution."""
    
    def __init__(self, args):
        self.args = args
        self.base_url = self._determine_base_url()
        self.redis_url = self._determine_redis_url()
        self.test_results = {}
        self.start_time = time.time()
        
    def _determine_base_url(self) -> str:
        """Determine API base URL based on environment."""
        if self.args.local:
            return "http://localhost:8000/api"
        elif self.args.staging:
            return os.getenv("STAGING_API_URL", "https://staging-api.mita.com/api")
        elif self.args.production:
            return os.getenv("PRODUCTION_API_URL", "https://mita-docker-ready-project-manus.onrender.com/api")
        else:
            # Default to environment variable or local
            return os.getenv("INTEGRATION_TEST_BASE_URL", "http://localhost:8000/api")
    
    def _determine_redis_url(self) -> str:
        """Determine Redis URL for testing."""
        if self.args.local:
            return "redis://localhost:6379/14"
        elif self.args.ci:
            return os.getenv("REDIS_TEST_URL", "redis://localhost:6379/14")
        else:
            return os.getenv("REDIS_URL", "redis://localhost:6379/14")
    
    async def check_dependencies(self) -> bool:
        """Check if required services are available."""
        print("🔍 Checking dependencies...")
        
        # Check API availability
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=10.0)
                if response.status_code not in [200, 404]:  # 404 is OK if health endpoint doesn't exist
                    print(f"❌ API not available at {self.base_url}")
                    return False
                print(f"✅ API available at {self.base_url}")
        except Exception as e:
            print(f"❌ API check failed: {e}")
            if not self.args.ci:  # In CI, continue anyway
                return False
        
        # Check Redis availability
        try:
            redis_client = redis.from_url(self.redis_url)
            redis_client.ping()
            print(f"✅ Redis available at {self.redis_url}")
        except Exception as e:
            print(f"⚠️  Redis check failed: {e}")
            # Redis might not be required for all tests
        
        return True
    
    def setup_test_environment(self):
        """Setup test environment variables."""
        print("🔧 Setting up test environment...")
        
        env_vars = {
            "INTEGRATION_TESTING": "true",
            "TESTING": "true",
            "INTEGRATION_TEST_BASE_URL": self.base_url,
            "REDIS_TEST_URL": self.redis_url,
            "PYTHONPATH": str(Path(__file__).parent.parent.parent),
        }
        
        # CI-specific settings
        if self.args.ci:
            env_vars.update({
                "CI": "true",
                "TEST_TIMEOUT": "300",  # 5 minutes per test in CI
                "PARALLEL_TESTS": "4" if self.args.parallel else "1",
            })
        
        # Production testing (read-only)
        if self.args.production:
            env_vars.update({
                "PRODUCTION_TESTING": "true",
                "READ_ONLY_TESTS": "true",
            })
        
        for key, value in env_vars.items():
            os.environ[key] = value
            print(f"  {key}={value}")
    
    def build_pytest_command(self) -> List[str]:
        """Build pytest command with appropriate options."""
        cmd = ["python", "-m", "pytest"]
        
        # Test selection
        if self.args.fast:
            cmd.extend(["-m", "not slow and not performance"])
        elif self.args.security:
            cmd.extend(["-m", "security"])
        elif self.args.mobile:
            cmd.extend(["-m", "mobile"])
        elif self.args.performance:
            cmd.extend(["-m", "performance"])
        else:
            # Run all tests except those marked as skip_ci in CI
            if self.args.ci:
                cmd.extend(["-m", "not skip_ci"])
        
        # Parallel execution
        if self.args.parallel and not self.args.performance:
            try:
                import pytest_xdist
                cmd.extend(["-n", "auto"])
            except ImportError:
                print("⚠️  pytest-xdist not available, running sequentially")
        
        # CI-specific options
        if self.args.ci:
            cmd.extend([
                "--maxfail=5",  # Stop after 5 failures
                "--tb=line",    # Shorter traceback in CI
                "--timeout=300", # 5 minute timeout per test
            ])
        
        # Verbosity
        if self.args.verbose:
            cmd.append("-vv")
        elif not self.args.ci:
            cmd.append("-v")
        
        # Test discovery path
        cmd.append("tests/integration")
        
        return cmd
    
    def create_reports_directory(self):
        """Create reports directory for test results."""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        return reports_dir
    
    async def run_tests(self) -> Dict[str, Any]:
        """Execute the integration tests."""
        print("🧪 Running integration tests...")
        
        reports_dir = self.create_reports_directory()
        cmd = self.build_pytest_command()
        
        print(f"Command: {' '.join(cmd)}")
        
        # Run tests
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent.parent.parent,
                capture_output=False,  # Let pytest handle output
                timeout=3600 if self.args.performance else 1800,  # 60/30 minutes
            )
            
            execution_time = time.time() - start_time
            
            # Parse results
            test_results = {
                "exit_code": result.returncode,
                "execution_time": execution_time,
                "success": result.returncode == 0,
                "timestamp": time.time(),
            }
            
            # Try to parse JUnit XML if available
            junit_file = reports_dir / "integration-test-results.xml"
            if junit_file.exists():
                test_results["junit_results"] = str(junit_file)
            
            return test_results
            
        except subprocess.TimeoutExpired:
            print("❌ Tests timed out!")
            return {
                "exit_code": -1,
                "execution_time": time.time() - start_time,
                "success": False,
                "error": "timeout",
                "timestamp": time.time(),
            }
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return {
                "exit_code": -1,
                "execution_time": time.time() - start_time,
                "success": False,
                "error": str(e),
                "timestamp": time.time(),
            }
    
    def generate_summary_report(self, results: Dict[str, Any]):
        """Generate summary report of test execution."""
        print("\n" + "="*70)
        print("🧪 MITA Authentication Integration Test Summary")
        print("="*70)
        
        print(f"Environment: {self.base_url}")
        print(f"Redis: {self.redis_url}")
        print(f"Execution Time: {results['execution_time']:.1f}s")
        print(f"Exit Code: {results['exit_code']}")
        print(f"Success: {'✅ PASSED' if results['success'] else '❌ FAILED'}")
        
        if "error" in results:
            print(f"Error: {results['error']}")
        
        # Test configuration info
        config_info = []
        if self.args.fast:
            config_info.append("fast")
        if self.args.security:
            config_info.append("security-only")
        if self.args.mobile:
            config_info.append("mobile-only")
        if self.args.performance:
            config_info.append("performance")
        if self.args.parallel:
            config_info.append("parallel")
        if self.args.ci:
            config_info.append("CI-mode")
        
        if config_info:
            print(f"Configuration: {', '.join(config_info)}")
        
        print("="*70)
        
        # Save results to JSON
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        results_file = reports_dir / "integration-test-summary.json"
        with open(results_file, 'w') as f:
            json.dump({
                "results": results,
                "configuration": {
                    "base_url": self.base_url,
                    "redis_url": self.redis_url,
                    "args": vars(self.args),
                },
                "environment": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "working_directory": str(Path.cwd()),
                }
            }, f, indent=2)
        
        print(f"📄 Detailed results saved to: {results_file}")
    
    async def run(self) -> int:
        """Run the complete integration test suite."""
        try:
            # Check dependencies
            if not await self.check_dependencies():
                if self.args.ci:
                    print("⚠️  Dependency check failed in CI, continuing anyway...")
                else:
                    print("❌ Dependency check failed. Use --ci to continue anyway.")
                    return 1
            
            # Setup environment
            self.setup_test_environment()
            
            # Run tests
            results = await self.run_tests()
            
            # Generate report
            self.generate_summary_report(results)
            
            return 0 if results["success"] else 1
            
        except KeyboardInterrupt:
            print("\n🛑 Tests interrupted by user")
            return 130
        except Exception as e:
            print(f"❌ Test runner failed: {e}")
            return 1


def signal_handler(signum, frame):
    """Handle graceful shutdown on signals."""
    print(f"\n🛑 Received signal {signum}, shutting down...")
    sys.exit(130)


def main():
    """Main entry point."""
    # Setup signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="MITA Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Test selection options
    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--fast", action="store_true",
                          help="Run fast tests only (skip slow/performance tests)")
    test_group.add_argument("--security", action="store_true",
                          help="Run security tests only")
    test_group.add_argument("--mobile", action="store_true",
                          help="Run mobile-specific tests only")
    test_group.add_argument("--performance", action="store_true",
                          help="Run performance tests only")
    
    # Environment options
    env_group = parser.add_mutually_exclusive_group()
    env_group.add_argument("--local", action="store_true",
                         help="Run against local development server")
    env_group.add_argument("--staging", action="store_true",
                         help="Run against staging environment")
    env_group.add_argument("--production", action="store_true",
                         help="Run against production (read-only tests)")
    
    # Execution options
    parser.add_argument("--parallel", action="store_true",
                       help="Run tests in parallel")
    parser.add_argument("--ci", action="store_true",
                       help="Run in CI mode with appropriate settings")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Create and run test runner
    runner = IntegrationTestRunner(args)
    
    # Run async
    try:
        exit_code = asyncio.run(runner.run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()