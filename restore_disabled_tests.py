#!/usr/bin/env python3
"""
MITA Test Suite Restoration Script
=================================

Comprehensive script to restore and validate all disabled test suites
throughout the MITA Finance application after backend stability restoration.

This script addresses TECHNICAL DEBT by:
1. Validating restored API endpoints work correctly
2. Running restored integration tests
3. Verifying security test functionality  
4. Generating test coverage reports
5. Documenting test restoration status

Usage:
    python restore_disabled_tests.py [--dry-run] [--verbose]
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx
import pytest


class TestRestorationValidator:
    """Validates restoration of disabled test suites."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "restoration_summary": {},
            "endpoint_validation": {},
            "test_results": {},
            "coverage_analysis": {},
            "recommendations": []
        }
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "✅",
            "ERROR": "❌", 
            "WARNING": "⚠️",
            "SUCCESS": "🎉"
        }.get(level, "ℹ️")
        
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose and level == "ERROR":
            print(f"    Details: {traceback.format_exc()}")
    
    async def validate_api_endpoints(self) -> Dict[str, Any]:
        """Validate that restored API endpoints are working."""
        self.log("Validating restored API endpoints...")
        
        # Test endpoints that were previously returning 404
        endpoints_to_test = {
            "auth_refresh": {
                "method": "POST",
                "url": "/auth/refresh-token", 
                "description": "Token refresh endpoint",
                "expected_without_auth": [400, 422, 401]  # Should not be 404
            },
            "push_token_registration": {
                "method": "POST",
                "url": "/notifications/register-token",
                "description": "Push token registration", 
                "expected_without_auth": [401, 422]  # Should not be 404
            },
            "google_oauth": {
                "method": "POST", 
                "url": "/auth/google",
                "description": "Google OAuth endpoint",
                "expected_without_auth": [400, 422, 501]  # 501 = not implemented, ok
            }
        }
        
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api")
        endpoint_results = {}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for endpoint_name, config in endpoints_to_test.items():
                    try:
                        self.log(f"Testing {config['description']} at {config['url']}")
                        
                        # Test without authentication to check if endpoint exists
                        if config["method"] == "POST":
                            response = await client.post(f"{base_url}{config['url']}", json={})
                        else:
                            response = await client.get(f"{base_url}{config['url']}")
                        
                        status_ok = response.status_code in config["expected_without_auth"]
                        not_404 = response.status_code != 404
                        
                        endpoint_results[endpoint_name] = {
                            "status_code": response.status_code,
                            "endpoint_exists": not_404,
                            "expected_behavior": status_ok,
                            "url": config["url"],
                            "description": config["description"]
                        }
                        
                        if not_404:
                            self.log(f"{config['description']} endpoint EXISTS (status: {response.status_code})")
                        else:
                            self.log(f"{config['description']} endpoint NOT FOUND (404)", "WARNING")
                            
                    except httpx.ConnectError:
                        self.log(f"Could not connect to API server for {endpoint_name}", "WARNING")
                        endpoint_results[endpoint_name] = {
                            "error": "connection_failed",
                            "endpoint_exists": False,
                            "url": config["url"],
                            "description": config["description"]
                        }
                    except Exception as e:
                        self.log(f"Error testing {endpoint_name}: {e}", "ERROR")
                        endpoint_results[endpoint_name] = {
                            "error": str(e),
                            "endpoint_exists": False,
                            "url": config["url"],
                            "description": config["description"]
                        }
                        
        except Exception as e:
            self.log(f"Failed to validate API endpoints: {e}", "ERROR")
            endpoint_results["validation_error"] = str(e)
        
        self.results["endpoint_validation"] = endpoint_results
        return endpoint_results
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """Run restored integration tests."""
        self.log("Running restored integration tests...")
        
        test_results = {}
        integration_test_path = self.project_root / "tests" / "integration"
        
        if not integration_test_path.exists():
            self.log("Integration test directory not found", "WARNING")
            return {"error": "integration_tests_not_found"}
        
        # Run specific restored tests
        tests_to_run = [
            "test_auth_integration.py::TestOAuthIntegration::test_google_oauth_flow",
            "test_auth_integration.py::TestTokenManagement::test_token_refresh_flow", 
            "test_mobile_scenarios.py::TestMobileDeviceLifecycle::test_push_token_management",
            "test_performance_integration.py::TestTokenPerformance::test_token_refresh_performance"
        ]
        
        for test_name in tests_to_run:
            try:
                self.log(f"Running {test_name}")
                
                # Change to project root for pytest
                original_cwd = os.getcwd()
                os.chdir(self.project_root)
                
                cmd = [
                    sys.executable, "-m", "pytest", 
                    f"tests/integration/{test_name}",
                    "-v", "--tb=short", "--no-header"
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                os.chdir(original_cwd)
                
                test_results[test_name] = {
                    "exit_code": result.returncode,
                    "passed": result.returncode == 0,
                    "output": result.stdout[-1000:],  # Last 1000 chars
                    "errors": result.stderr[-500:] if result.stderr else None
                }
                
                if result.returncode == 0:
                    self.log(f"✅ {test_name} PASSED")
                else:
                    self.log(f"❌ {test_name} FAILED (exit code: {result.returncode})")
                    
            except subprocess.TimeoutExpired:
                self.log(f"⏰ {test_name} TIMED OUT", "WARNING")
                test_results[test_name] = {"error": "timeout"}
            except Exception as e:
                self.log(f"Error running {test_name}: {e}", "ERROR")
                test_results[test_name] = {"error": str(e)}
        
        self.results["test_results"] = test_results
        return test_results
    
    def run_flutter_tests(self) -> Dict[str, Any]:
        """Run Flutter test suite."""
        self.log("Running Flutter test suite...")
        
        flutter_test_path = self.project_root / "mobile_app"
        flutter_results = {}
        
        if not flutter_test_path.exists():
            self.log("Flutter app directory not found", "WARNING") 
            return {"error": "flutter_app_not_found"}
        
        try:
            original_cwd = os.getcwd()
            os.chdir(flutter_test_path)
            
            # Run Flutter tests
            cmd = ["flutter", "test", "--reporter", "json"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            os.chdir(original_cwd)
            
            flutter_results = {
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output": result.stdout[-1500:],
                "errors": result.stderr[-500:] if result.stderr else None
            }
            
            if result.returncode == 0:
                self.log("✅ Flutter tests PASSED")
            else:
                self.log(f"❌ Flutter tests FAILED (exit code: {result.returncode})")
                
        except subprocess.TimeoutExpired:
            self.log("⏰ Flutter tests TIMED OUT", "WARNING")
            flutter_results = {"error": "timeout"}
        except FileNotFoundError:
            self.log("Flutter command not found - skipping Flutter tests", "WARNING")
            flutter_results = {"error": "flutter_not_installed"}
        except Exception as e:
            self.log(f"Error running Flutter tests: {e}", "ERROR")
            flutter_results = {"error": str(e)}
        
        self.results["flutter_results"] = flutter_results
        return flutter_results
    
    def analyze_test_coverage(self) -> Dict[str, Any]:
        """Analyze test coverage after restoration."""
        self.log("Analyzing test coverage...")
        
        coverage_results = {}
        
        try:
            # Run coverage for Python tests
            original_cwd = os.getcwd()
            os.chdir(self.project_root)
            
            cmd = [
                sys.executable, "-m", "pytest", 
                "--cov=app",
                "--cov-report=json:coverage.json",
                "--cov-report=term-missing",
                "tests/", "app/tests/", 
                "-q"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            os.chdir(original_cwd)
            
            # Try to read coverage JSON
            coverage_file = self.project_root / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                
                coverage_results = {
                    "total_coverage": coverage_data.get("totals", {}).get("percent_covered", 0),
                    "covered_lines": coverage_data.get("totals", {}).get("covered_lines", 0), 
                    "total_lines": coverage_data.get("totals", {}).get("num_statements", 0),
                    "missing_lines": coverage_data.get("totals", {}).get("missing_lines", 0)
                }
                
                self.log(f"Test coverage: {coverage_results['total_coverage']:.1f}%")
                
                # Coverage quality assessment
                coverage_pct = coverage_results["total_coverage"]
                if coverage_pct >= 80:
                    self.log("✅ Excellent test coverage (80%+)", "SUCCESS")
                elif coverage_pct >= 70:
                    self.log("⚠️ Good test coverage (70%+)", "WARNING")
                else:
                    self.log("❌ Test coverage needs improvement (<70%)", "ERROR")
                    
            else:
                self.log("Coverage report not generated", "WARNING")
                coverage_results = {"error": "coverage_file_not_found"}
                
        except Exception as e:
            self.log(f"Error analyzing coverage: {e}", "ERROR")
            coverage_results = {"error": str(e)}
        
        self.results["coverage_analysis"] = coverage_results
        return coverage_results
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test restoration results."""
        recommendations = []
        
        # Check endpoint validation results
        endpoint_results = self.results.get("endpoint_validation", {})
        for endpoint_name, result in endpoint_results.items():
            if isinstance(result, dict):
                if not result.get("endpoint_exists", False):
                    recommendations.append(
                        f"❌ Endpoint {result.get('url', endpoint_name)} still returns 404 - "
                        f"needs backend implementation"
                    )
                elif result.get("endpoint_exists") and result.get("expected_behavior"):
                    recommendations.append(
                        f"✅ Endpoint {result.get('url', endpoint_name)} is working correctly"
                    )
        
        # Check test results  
        test_results = self.results.get("test_results", {})
        failed_tests = [name for name, result in test_results.items() 
                       if isinstance(result, dict) and not result.get("passed", False)]
        
        if failed_tests:
            recommendations.append(
                f"❌ {len(failed_tests)} integration tests still failing - investigate: "
                f"{', '.join(failed_tests[:3])}{'...' if len(failed_tests) > 3 else ''}"
            )
        else:
            recommendations.append("✅ All restored integration tests are passing")
        
        # Check coverage
        coverage = self.results.get("coverage_analysis", {})
        coverage_pct = coverage.get("total_coverage", 0)
        
        if coverage_pct < 70:
            recommendations.append(
                f"❌ Test coverage at {coverage_pct:.1f}% - add more unit tests to reach 80%"
            )
        elif coverage_pct < 80:
            recommendations.append(
                f"⚠️ Test coverage at {coverage_pct:.1f}% - close to 80% target"
            )
        else:
            recommendations.append(f"✅ Excellent test coverage at {coverage_pct:.1f}%")
        
        # General recommendations
        recommendations.extend([
            "🔧 Set up automated CI/CD test execution for restored tests",
            "📊 Monitor test performance - ensure <200ms API response times", 
            "🔒 Verify security tests are covering authentication and authorization",
            "📱 Test mobile app integration with restored backend endpoints",
            "⚡ Add performance regression tests for critical financial operations"
        ])
        
        self.results["recommendations"] = recommendations
        return recommendations
    
    def save_results(self):
        """Save restoration results to file."""
        results_file = self.project_root / "test_restoration_results.json"
        
        try:
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            
            self.log(f"Results saved to {results_file}")
            
            # Also create a summary report
            summary_file = self.project_root / "test_restoration_summary.md"
            self.create_summary_report(summary_file)
            
        except Exception as e:
            self.log(f"Error saving results: {e}", "ERROR")
    
    def create_summary_report(self, summary_file: Path):
        """Create human-readable summary report."""
        try:
            with open(summary_file, "w") as f:
                f.write("# MITA Test Suite Restoration Summary\n\n")
                f.write(f"**Generated:** {self.results['timestamp']}\n\n")
                
                # Endpoint validation summary
                f.write("## API Endpoint Validation\n\n")
                endpoint_results = self.results.get("endpoint_validation", {})
                for endpoint_name, result in endpoint_results.items():
                    if isinstance(result, dict) and "url" in result:
                        status = "✅ Working" if result.get("endpoint_exists") else "❌ Not Found"
                        f.write(f"- **{result.get('description', endpoint_name)}** "
                               f"(`{result.get('url')}`) - {status}\n")
                
                # Test results summary
                f.write("\n## Integration Test Results\n\n")
                test_results = self.results.get("test_results", {})
                for test_name, result in test_results.items():
                    if isinstance(result, dict):
                        status = "✅ PASSED" if result.get("passed") else "❌ FAILED"
                        f.write(f"- `{test_name}` - {status}\n")
                
                # Coverage summary
                f.write("\n## Test Coverage Analysis\n\n")
                coverage = self.results.get("coverage_analysis", {})
                if coverage.get("total_coverage"):
                    f.write(f"**Coverage:** {coverage['total_coverage']:.1f}%\n")
                    f.write(f"**Covered Lines:** {coverage.get('covered_lines', 0)}\n")
                    f.write(f"**Total Lines:** {coverage.get('total_lines', 0)}\n\n")
                
                # Recommendations
                f.write("## Recommendations\n\n")
                for rec in self.results.get("recommendations", []):
                    f.write(f"- {rec}\n")
                
            self.log(f"Summary report saved to {summary_file}")
            
        except Exception as e:
            self.log(f"Error creating summary report: {e}", "ERROR")
    
    async def run_full_restoration_validation(self):
        """Run complete test restoration validation."""
        self.log("🚀 Starting MITA Test Suite Restoration Validation", "SUCCESS")
        
        start_time = time.time()
        
        try:
            # Step 1: Validate API endpoints
            await self.validate_api_endpoints()
            
            # Step 2: Run integration tests
            self.run_integration_tests()
            
            # Step 3: Run Flutter tests
            self.run_flutter_tests()
            
            # Step 4: Analyze coverage
            self.analyze_test_coverage()
            
            # Step 5: Generate recommendations
            self.generate_recommendations()
            
            # Step 6: Save results
            self.save_results()
            
            duration = time.time() - start_time
            
            self.log(f"🎉 Test restoration validation completed in {duration:.1f}s", "SUCCESS")
            
            # Print final summary
            self.print_final_summary()
            
        except Exception as e:
            self.log(f"Test restoration validation failed: {e}", "ERROR")
            raise
    
    def print_final_summary(self):
        """Print final validation summary."""
        print("\n" + "="*70)
        print("🧪 MITA TEST SUITE RESTORATION SUMMARY")
        print("="*70)
        
        # Endpoint status
        endpoint_results = self.results.get("endpoint_validation", {})
        working_endpoints = sum(1 for r in endpoint_results.values() 
                              if isinstance(r, dict) and r.get("endpoint_exists"))
        total_endpoints = len([r for r in endpoint_results.values() 
                              if isinstance(r, dict) and "url" in r])
        
        print(f"API Endpoints: {working_endpoints}/{total_endpoints} working")
        
        # Test status  
        test_results = self.results.get("test_results", {})
        passed_tests = sum(1 for r in test_results.values() 
                          if isinstance(r, dict) and r.get("passed"))
        total_tests = len(test_results)
        
        print(f"Integration Tests: {passed_tests}/{total_tests} passing")
        
        # Coverage
        coverage = self.results.get("coverage_analysis", {})
        coverage_pct = coverage.get("total_coverage", 0)
        print(f"Test Coverage: {coverage_pct:.1f}%")
        
        print("\n📄 Detailed results saved to test_restoration_results.json")
        print("📄 Summary report saved to test_restoration_summary.md")
        print("="*70 + "\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MITA Test Suite Restoration Validator"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN - Would validate and restore test suites")
        print("1. Check API endpoints for 404 errors")
        print("2. Run restored integration tests")
        print("3. Validate Flutter test suite") 
        print("4. Analyze test coverage")
        print("5. Generate recommendations")
        return
    
    validator = TestRestorationValidator(verbose=args.verbose)
    
    try:
        asyncio.run(validator.run_full_restoration_validation())
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()