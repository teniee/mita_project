#!/usr/bin/env python3
"""
MITA Authentication Security Test Runner
========================================

Comprehensive test runner for MITA authentication security test suite.
Provides different test execution modes and detailed reporting for 
financial application security validation.

Usage:
    python run_auth_tests.py [options]

Options:
    --all                   Run all authentication security tests
    --token-tests           Run token management tests only
    --auth-flow-tests      Run authentication flow tests only
    --security-tests       Run security feature tests only
    --concurrent-tests     Run concurrent operation tests only
    --api-tests            Run API endpoint security tests only
    --password-tests       Run password security tests only
    --performance-tests    Run performance tests only
    --quick                Run quick test subset for CI
    --coverage             Run with coverage reporting
    --verbose              Verbose output
    --parallel             Run tests in parallel
    --report-html          Generate HTML test report
    --benchmark            Run performance benchmarks
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
TEST_DIR = Path(__file__).parent
REPORTS_DIR = TEST_DIR / "reports"
COVERAGE_DIR = TEST_DIR / "coverage"

# Test file mapping
TEST_FILES = {
    "comprehensive": "test_mita_authentication_comprehensive.py",
    "password": "test_password_security_validation.py", 
    "concurrent": "test_concurrent_auth_operations.py",
    "api": "test_api_endpoint_security.py",
}

# Test categories
TEST_CATEGORIES = {
    "token-tests": [
        "test_mita_authentication_comprehensive.py::TestTokenManagement",
    ],
    "auth-flow-tests": [
        "test_mita_authentication_comprehensive.py::TestAuthenticationFlows",
    ],
    "security-tests": [
        "test_mita_authentication_comprehensive.py::TestSecurityFeatures",
    ],
    "concurrent-tests": [
        "test_concurrent_auth_operations.py",
    ],
    "api-tests": [
        "test_api_endpoint_security.py",
    ],
    "password-tests": [
        "test_password_security_validation.py",
    ],
    "performance-tests": [
        "test_mita_authentication_comprehensive.py::TestPerformanceAndLoad",
        "test_concurrent_auth_operations.py::TestConcurrentTokenOperations",
    ],
}

# Quick test subset for CI/CD
QUICK_TESTS = [
    "test_mita_authentication_comprehensive.py::TestTokenManagement::test_token_blacklist_functionality_comprehensive",
    "test_mita_authentication_comprehensive.py::TestSecurityFeatures::test_rate_limiting_on_auth_endpoints",
    "test_password_security_validation.py::TestPasswordStrengthValidation::test_password_minimum_requirements",
    "test_api_endpoint_security.py::TestAuthEndpointSecurity::test_login_endpoint_security",
]


class AuthTestRunner:
    """Main test runner class for MITA authentication security tests."""
    
    def __init__(self):
        self.reports_dir = REPORTS_DIR
        self.coverage_dir = COVERAGE_DIR
        self.create_directories()
    
    def create_directories(self):
        """Create necessary directories for test reports."""
        self.reports_dir.mkdir(exist_ok=True)
        self.coverage_dir.mkdir(exist_ok=True)
    
    def run_pytest(self, 
                   test_paths: List[str], 
                   extra_args: List[str] = None,
                   capture_output: bool = False) -> subprocess.CompletedProcess:
        """
        Run pytest with specified paths and arguments.
        
        Args:
            test_paths: List of test files or paths to run
            extra_args: Additional pytest arguments
            capture_output: Whether to capture output
            
        Returns:
            CompletedProcess result
        """
        if extra_args is None:
            extra_args = []
        
        # Base pytest command
        cmd = [
            sys.executable, 
            "-m", "pytest"
        ] + test_paths + extra_args
        
        print(f"\nRunning command: {' '.join(cmd)}")
        
        # Run pytest
        return subprocess.run(
            cmd,
            cwd=TEST_DIR,
            capture_output=capture_output,
            text=True
        )
    
    def run_all_tests(self, verbose: bool = False, parallel: bool = False) -> bool:
        """
        Run all authentication security tests.
        
        Args:
            verbose: Enable verbose output
            parallel: Run tests in parallel
            
        Returns:
            True if all tests pass, False otherwise
        """
        print("\n" + "="*60)
        print("Running Complete MITA Authentication Security Test Suite")
        print("="*60)
        
        extra_args = []
        
        if verbose:
            extra_args.extend(["-v", "-s"])
        
        if parallel:
            extra_args.extend(["-n", "auto"])
        
        # Add comprehensive markers
        extra_args.extend([
            "-m", "not slow or security",
            "--tb=short",
            f"--html={self.reports_dir}/auth_security_report.html",
            f"--self-contained-html"
        ])
        
        test_files = list(TEST_FILES.values())
        result = self.run_pytest(test_files, extra_args)
        
        print(f"\nTest execution completed with return code: {result.returncode}")
        return result.returncode == 0
    
    def run_category_tests(self, 
                          category: str, 
                          verbose: bool = False,
                          parallel: bool = False) -> bool:
        """
        Run tests for specific category.
        
        Args:
            category: Test category to run
            verbose: Enable verbose output
            parallel: Run tests in parallel
            
        Returns:
            True if tests pass, False otherwise
        """
        if category not in TEST_CATEGORIES:
            print(f"Error: Unknown test category '{category}'")
            print(f"Available categories: {list(TEST_CATEGORIES.keys())}")
            return False
        
        print(f"\nRunning {category} authentication security tests...")
        
        extra_args = []
        
        if verbose:
            extra_args.extend(["-v", "-s"])
        
        if parallel:
            extra_args.extend(["-n", "auto"])
        
        extra_args.extend([
            "--tb=short",
            f"--html={self.reports_dir}/{category}_report.html",
            "--self-contained-html"
        ])
        
        test_paths = TEST_CATEGORIES[category]
        result = self.run_pytest(test_paths, extra_args)
        
        return result.returncode == 0
    
    def run_quick_tests(self, verbose: bool = False) -> bool:
        """
        Run quick test subset for CI/CD.
        
        Args:
            verbose: Enable verbose output
            
        Returns:
            True if tests pass, False otherwise
        """
        print("\n" + "="*50)
        print("Running Quick Authentication Security Tests")
        print("="*50)
        
        extra_args = [
            "--tb=short",
            "-x",  # Stop on first failure
        ]
        
        if verbose:
            extra_args.extend(["-v", "-s"])
        
        result = self.run_pytest(QUICK_TESTS, extra_args)
        return result.returncode == 0
    
    def run_with_coverage(self, 
                         test_paths: List[str] = None,
                         verbose: bool = False) -> bool:
        """
        Run tests with coverage reporting.
        
        Args:
            test_paths: Specific test paths to run
            verbose: Enable verbose output
            
        Returns:
            True if tests pass, False otherwise
        """
        print("\nRunning tests with coverage analysis...")
        
        if test_paths is None:
            test_paths = list(TEST_FILES.values())
        
        extra_args = [
            f"--cov=app.services.auth_jwt_service",
            f"--cov=app.api.auth.services", 
            f"--cov=app.core.security",
            f"--cov-report=html:{self.coverage_dir}/html",
            f"--cov-report=xml:{self.coverage_dir}/coverage.xml",
            f"--cov-report=term-missing",
            "--cov-fail-under=80",  # Require 80% coverage
        ]
        
        if verbose:
            extra_args.extend(["-v", "-s"])
        
        result = self.run_pytest(test_paths, extra_args)
        
        if result.returncode == 0:
            print(f"\nCoverage report generated:")
            print(f"  HTML: {self.coverage_dir}/html/index.html")
            print(f"  XML:  {self.coverage_dir}/coverage.xml")
        
        return result.returncode == 0
    
    def run_performance_benchmarks(self, verbose: bool = False) -> bool:
        """
        Run performance benchmarks for authentication system.
        
        Args:
            verbose: Enable verbose output
            
        Returns:
            True if benchmarks pass, False otherwise
        """
        print("\n" + "="*60)
        print("Running Authentication Performance Benchmarks")
        print("Financial Application Performance Requirements")
        print("="*60)
        
        extra_args = [
            "-m", "performance",
            "--benchmark-only",
            f"--benchmark-json={self.reports_dir}/benchmarks.json",
            f"--benchmark-html={self.reports_dir}/benchmarks.html",
            "--benchmark-sort=mean",
        ]
        
        if verbose:
            extra_args.extend(["-v", "-s"])
        
        # Run performance tests
        performance_tests = TEST_CATEGORIES["performance-tests"]
        result = self.run_pytest(performance_tests, extra_args)
        
        if result.returncode == 0:
            print(f"\nBenchmark report generated:")
            print(f"  JSON: {self.reports_dir}/benchmarks.json")
            print(f"  HTML: {self.reports_dir}/benchmarks.html")
        
        return result.returncode == 0
    
    def validate_test_environment(self) -> bool:
        """
        Validate test environment setup.
        
        Returns:
            True if environment is valid, False otherwise
        """
        print("Validating test environment...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            print("Error: Python 3.8 or higher is required")
            return False
        
        # Check required packages
        required_packages = [
            "pytest",
            "pytest-asyncio", 
            "pytest-cov",
            "pytest-html",
            "pytest-benchmark",
            "fastapi",
            "sqlalchemy",
            "redis",
            "jose",
            "passlib",
            "bcrypt",
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"Error: Missing required packages: {missing_packages}")
            print("Install with: pip install " + " ".join(missing_packages))
            return False
        
        # Check test files exist
        for test_file in TEST_FILES.values():
            test_path = TEST_DIR / test_file
            if not test_path.exists():
                print(f"Error: Test file not found: {test_file}")
                return False
        
        print("✓ Test environment validation passed")
        return True
    
    def generate_security_report(self) -> None:
        """Generate comprehensive security test report."""
        print("\nGenerating comprehensive security test report...")
        
        report_path = self.reports_dir / "security_summary.md"
        
        with open(report_path, 'w') as f:
            f.write("# MITA Authentication Security Test Report\n\n")
            f.write("## Test Suite Overview\n\n")
            f.write("This report summarizes the comprehensive security testing of the MITA authentication system.\n\n")
            
            f.write("## Test Categories\n\n")
            for category, tests in TEST_CATEGORIES.items():
                f.write(f"### {category.replace('-', ' ').title()}\n\n")
                for test in tests:
                    f.write(f"- {test}\n")
                f.write("\n")
            
            f.write("## Security Requirements Covered\n\n")
            security_requirements = [
                "Token blacklist functionality with Redis integration",
                "Refresh token rotation and prevention of reuse",
                "Rate limiting on auth endpoints with progressive penalties",
                "Password validation with enterprise security rules", 
                "JWT token security and validation",
                "Redis failure handling and fail-secure behavior",
                "Concurrent operations and race condition prevention",
                "Input validation and sanitization",
                "API endpoint security and error handling",
                "Performance benchmarks for financial applications",
            ]
            
            for req in security_requirements:
                f.write(f"- ✓ {req}\n")
            
            f.write(f"\n## Report Generated\n\n")
            f.write(f"- Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- Test Files: {len(TEST_FILES)} security test modules\n")
            f.write(f"- Total Test Categories: {len(TEST_CATEGORIES)}\n")
        
        print(f"Security report generated: {report_path}")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="MITA Authentication Security Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Test selection arguments
    parser.add_argument("--all", action="store_true", 
                       help="Run all authentication security tests")
    parser.add_argument("--token-tests", action="store_true",
                       help="Run token management tests only")
    parser.add_argument("--auth-flow-tests", action="store_true",
                       help="Run authentication flow tests only")
    parser.add_argument("--security-tests", action="store_true",
                       help="Run security feature tests only")
    parser.add_argument("--concurrent-tests", action="store_true",
                       help="Run concurrent operation tests only")
    parser.add_argument("--api-tests", action="store_true",
                       help="Run API endpoint security tests only")
    parser.add_argument("--password-tests", action="store_true", 
                       help="Run password security tests only")
    parser.add_argument("--performance-tests", action="store_true",
                       help="Run performance tests only")
    
    # Execution mode arguments
    parser.add_argument("--quick", action="store_true",
                       help="Run quick test subset for CI")
    parser.add_argument("--coverage", action="store_true",
                       help="Run with coverage reporting")
    parser.add_argument("--benchmark", action="store_true",
                       help="Run performance benchmarks")
    
    # Output arguments
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--parallel", action="store_true",
                       help="Run tests in parallel")
    parser.add_argument("--report-html", action="store_true",
                       help="Generate HTML test report")
    
    # Utility arguments
    parser.add_argument("--validate-env", action="store_true",
                       help="Validate test environment only")
    parser.add_argument("--generate-report", action="store_true",
                       help="Generate security test report")
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = AuthTestRunner()
    
    # Validate environment first
    if args.validate_env:
        success = runner.validate_test_environment()
        sys.exit(0 if success else 1)
    
    if not runner.validate_test_environment():
        sys.exit(1)
    
    # Generate report only
    if args.generate_report:
        runner.generate_security_report()
        sys.exit(0)
    
    success = True
    
    try:
        # Determine what tests to run
        if args.quick:
            success = runner.run_quick_tests(args.verbose)
        
        elif args.benchmark:
            success = runner.run_performance_benchmarks(args.verbose)
        
        elif args.coverage:
            success = runner.run_with_coverage(verbose=args.verbose)
        
        elif args.all or not any([
            args.token_tests, args.auth_flow_tests, args.security_tests,
            args.concurrent_tests, args.api_tests, args.password_tests,
            args.performance_tests
        ]):
            # Default: run all tests
            success = runner.run_all_tests(args.verbose, args.parallel)
        
        else:
            # Run specific test categories
            if args.token_tests:
                success &= runner.run_category_tests("token-tests", args.verbose, args.parallel)
            
            if args.auth_flow_tests:
                success &= runner.run_category_tests("auth-flow-tests", args.verbose, args.parallel)
            
            if args.security_tests:
                success &= runner.run_category_tests("security-tests", args.verbose, args.parallel)
            
            if args.concurrent_tests:
                success &= runner.run_category_tests("concurrent-tests", args.verbose, args.parallel)
            
            if args.api_tests:
                success &= runner.run_category_tests("api-tests", args.verbose, args.parallel)
            
            if args.password_tests:
                success &= runner.run_category_tests("password-tests", args.verbose, args.parallel)
            
            if args.performance_tests:
                success &= runner.run_category_tests("performance-tests", args.verbose, args.parallel)
        
        # Generate final report
        runner.generate_security_report()
        
        if success:
            print("\n" + "="*60)
            print("✓ All MITA Authentication Security Tests PASSED")
            print("Financial Application Security Validation Complete")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("✗ Some MITA Authentication Security Tests FAILED")
            print("Review test output and fix issues before production")
            print("="*60)
    
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        success = False
    
    except Exception as e:
        print(f"\nError during test execution: {e}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()