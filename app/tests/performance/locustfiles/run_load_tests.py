#!/usr/bin/env python3
"""
MITA Load Testing Runner and Configuration
Automated load testing execution with different scenarios for production readiness validation.
"""

import os
import sys
import json
import subprocess
import argparse
import time
from typing import Dict, Any, List
from datetime import datetime


class MITALoadTestRunner:
    """
    Comprehensive load test runner for MITA financial application.
    Executes different load test scenarios and generates detailed reports.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.report_dir = "load_test_reports"
        
        # Create report directory
        os.makedirs(self.report_dir, exist_ok=True)
    
    def run_smoke_test(self) -> Dict[str, Any]:
        """
        Run smoke test with minimal load to validate basic functionality.
        """
        print("🔥 Running Smoke Test...")
        
        result = self._run_locust_test(
            test_name="smoke_test",
            users=5,
            spawn_rate=1,
            duration="2m",
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_baseline_performance_test(self) -> Dict[str, Any]:
        """
        Run baseline performance test to establish performance benchmarks.
        """
        print("📊 Running Baseline Performance Test...")
        
        result = self._run_locust_test(
            test_name="baseline_performance",
            users=50,
            spawn_rate=2,
            duration="10m",
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_load_test(self) -> Dict[str, Any]:
        """
        Run standard load test simulating expected production traffic.
        """
        print("⚡ Running Standard Load Test...")
        
        result = self._run_locust_test(
            test_name="standard_load",
            users=200,
            spawn_rate=5,
            duration="15m",
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_stress_test(self) -> Dict[str, Any]:
        """
        Run stress test to find system breaking points.
        """
        print("🔥 Running Stress Test...")
        
        result = self._run_locust_test(
            test_name="stress_test",
            users=500,
            spawn_rate=10,
            duration="20m",
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_spike_test(self) -> Dict[str, Any]:
        """
        Run spike test to validate system behavior under sudden load increases.
        """
        print("📈 Running Spike Test...")
        
        # Run with gradual increase then sudden spike
        result = self._run_locust_test(
            test_name="spike_test",
            users=1000,
            spawn_rate=25,  # Fast spawn rate for spike
            duration="10m",
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_endurance_test(self) -> Dict[str, Any]:
        """
        Run endurance test to validate system stability over extended periods.
        """
        print("⏱️ Running Endurance Test...")
        
        result = self._run_locust_test(
            test_name="endurance_test",
            users=100,
            spawn_rate=2,
            duration="60m",  # 1 hour endurance
            locustfile="mita_load_test.py"
        )
        
        return result
    
    def run_financial_operations_focus_test(self) -> Dict[str, Any]:
        """
        Run focused test on financial operations (income classification, budget generation).
        """
        print("💰 Running Financial Operations Focus Test...")
        
        result = self._run_locust_test(
            test_name="financial_focus",
            users=300,
            spawn_rate=10,
            duration="15m",
            locustfile="mita_load_test.py",
            additional_params=["--tags", "financial"]
        )
        
        return result
    
    def run_authentication_load_test(self) -> Dict[str, Any]:
        """
        Run focused test on authentication systems.
        """
        print("🔐 Running Authentication Load Test...")
        
        result = self._run_locust_test(
            test_name="auth_load",
            users=150,
            spawn_rate=5,
            duration="10m",
            locustfile="mita_load_test.py",
            additional_params=["--tags", "auth"]
        )
        
        return result
    
    def run_mobile_simulation_test(self) -> Dict[str, Any]:
        """
        Run test simulating mobile app usage patterns.
        """
        print("📱 Running Mobile Simulation Test...")
        
        result = self._run_locust_test(
            test_name="mobile_simulation",
            users=400,  # Many mobile users
            spawn_rate=8,
            duration="12m",
            locustfile="mita_load_test.py",
            user_class="MITAMobileUser"
        )
        
        return result
    
    def _run_locust_test(
        self,
        test_name: str,
        users: int,
        spawn_rate: int,
        duration: str,
        locustfile: str,
        user_class: str = None,
        additional_params: List[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a Locust load test with specified parameters.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"{test_name}_{timestamp}")
        
        # Build Locust command
        cmd = [
            "locust",
            "-f", locustfile,
            "--host", self.base_url,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", duration,
            "--headless",
            "--print-stats",
            "--html", f"{report_file}.html",
            "--csv", report_file,
            "--loglevel", "INFO"
        ]
        
        # Add user class if specified
        if user_class:
            cmd.extend(["--user-class", user_class])
        
        # Add additional parameters
        if additional_params:
            cmd.extend(additional_params)
        
        print(f"Executing: {' '.join(cmd)}")
        
        # Run the test
        start_time = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            end_time = time.time()
            
            test_result = {
                "test_name": test_name,
                "timestamp": timestamp,
                "duration_seconds": end_time - start_time,
                "users": users,
                "spawn_rate": spawn_rate,
                "planned_duration": duration,
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "report_files": {
                    "html": f"{report_file}.html",
                    "csv_stats": f"{report_file}_stats.csv",
                    "csv_failures": f"{report_file}_failures.csv"
                }
            }
            
            # Parse performance metrics from output
            test_result["metrics"] = self._parse_locust_output(result.stdout)
            
            self.test_results.append(test_result)
            
            if result.returncode == 0:
                print(f"✅ {test_name} completed successfully")
                self._print_test_summary(test_result)
            else:
                print(f"❌ {test_name} failed")
                print(f"Error: {result.stderr}")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_name} timed out after 1 hour")
            return {
                "test_name": test_name,
                "success": False,
                "error": "Test timed out"
            }
        except Exception as e:
            print(f"💥 {test_name} crashed: {e}")
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e)
            }
    
    def _parse_locust_output(self, output: str) -> Dict[str, Any]:
        """
        Parse key metrics from Locust output.
        """
        metrics = {
            "total_requests": 0,
            "total_failures": 0,
            "average_response_time": 0.0,
            "requests_per_second": 0.0,
            "failure_rate": 0.0
        }
        
        lines = output.split('\n')
        for line in lines:
            # Parse summary statistics
            if "requests" in line and "failures" in line:
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "requests":
                            metrics["total_requests"] = int(parts[i-1])
                        elif part == "failures":
                            metrics["total_failures"] = int(parts[i-1])
                        elif "req/s" in part:
                            metrics["requests_per_second"] = float(parts[i-1])
                except (ValueError, IndexError):
                    continue
            
            # Parse average response time
            if "Average response time" in line:
                try:
                    time_str = line.split(":")[-1].strip().replace("ms", "")
                    metrics["average_response_time"] = float(time_str)
                except ValueError:
                    continue
        
        # Calculate failure rate
        if metrics["total_requests"] > 0:
            metrics["failure_rate"] = (metrics["total_failures"] / metrics["total_requests"]) * 100
        
        return metrics
    
    def _print_test_summary(self, result: Dict[str, Any]):
        """
        Print a summary of test results.
        """
        metrics = result.get("metrics", {})
        print(f"\n📋 Test Summary for {result['test_name']}:")
        print(f"   Duration: {result.get('duration_seconds', 0):.1f} seconds")
        print(f"   Total Requests: {metrics.get('total_requests', 0):,}")
        print(f"   Total Failures: {metrics.get('total_failures', 0):,}")
        print(f"   Failure Rate: {metrics.get('failure_rate', 0):.2f}%")
        print(f"   Average Response Time: {metrics.get('average_response_time', 0):.1f}ms")
        print(f"   Requests/Second: {metrics.get('requests_per_second', 0):.1f}")
        
        # Performance assessment
        if metrics.get("average_response_time", 0) > 2000:
            print("   ⚠️  WARNING: High average response time")
        
        if metrics.get("failure_rate", 0) > 5:
            print("   ❌ CRITICAL: High failure rate")
        
        if metrics.get("failure_rate", 0) < 1 and metrics.get("average_response_time", 0) < 1000:
            print("   ✅ EXCELLENT: Performance within acceptable limits")
    
    def generate_comprehensive_report(self):
        """
        Generate comprehensive performance report from all test results.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"comprehensive_report_{timestamp}.json")
        
        comprehensive_report = {
            "report_timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total_tests_run": len(self.test_results),
            "successful_tests": len([r for r in self.test_results if r.get("success", False)]),
            "test_results": self.test_results,
            "performance_summary": self._generate_performance_summary(),
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        with open(report_file, 'w') as f:
            json.dump(comprehensive_report, f, indent=2)
        
        print(f"\n📊 Comprehensive Report Generated: {report_file}")
        self._print_comprehensive_summary(comprehensive_report)
        
        return comprehensive_report
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """
        Generate overall performance summary across all tests.
        """
        successful_tests = [r for r in self.test_results if r.get("success", False)]
        
        if not successful_tests:
            return {"error": "No successful tests to analyze"}
        
        # Aggregate metrics
        total_requests = sum(r["metrics"].get("total_requests", 0) for r in successful_tests)
        total_failures = sum(r["metrics"].get("total_failures", 0) for r in successful_tests)
        avg_response_times = [r["metrics"].get("average_response_time", 0) for r in successful_tests if r["metrics"].get("average_response_time", 0) > 0]
        
        return {
            "total_requests_across_all_tests": total_requests,
            "total_failures_across_all_tests": total_failures,
            "overall_failure_rate": (total_failures / max(total_requests, 1)) * 100,
            "average_response_time_across_tests": sum(avg_response_times) / max(len(avg_response_times), 1),
            "best_performing_test": min(successful_tests, key=lambda x: x["metrics"].get("average_response_time", float('inf')))["test_name"],
            "worst_performing_test": max(successful_tests, key=lambda x: x["metrics"].get("average_response_time", 0))["test_name"]
        }
    
    def _generate_recommendations(self) -> List[str]:
        """
        Generate performance optimization recommendations.
        """
        recommendations = []
        
        successful_tests = [r for r in self.test_results if r.get("success", False)]
        
        # Analyze results for recommendations
        high_response_time_tests = [
            r for r in successful_tests 
            if r["metrics"].get("average_response_time", 0) > 1000
        ]
        
        high_failure_rate_tests = [
            r for r in successful_tests
            if r["metrics"].get("failure_rate", 0) > 5
        ]
        
        if high_response_time_tests:
            recommendations.append(
                f"HIGH PRIORITY: Optimize response times for {len(high_response_time_tests)} test scenarios. "
                f"Average response times exceeded 1 second."
            )
        
        if high_failure_rate_tests:
            recommendations.append(
                f"CRITICAL: Investigate failure causes in {len(high_failure_rate_tests)} test scenarios. "
                f"Failure rates exceeded 5%."
            )
        
        # Check for specific performance issues
        auth_tests = [r for r in successful_tests if "auth" in r["test_name"].lower()]
        if auth_tests and any(r["metrics"].get("average_response_time", 0) > 500 for r in auth_tests):
            recommendations.append(
                "MEDIUM PRIORITY: Authentication response times are high. "
                "Consider optimizing password hashing, token generation, or database queries."
            )
        
        financial_tests = [r for r in successful_tests if "financial" in r["test_name"].lower()]
        if financial_tests and any(r["metrics"].get("average_response_time", 0) > 200 for r in financial_tests):
            recommendations.append(
                "HIGH PRIORITY: Financial operations (income classification, budget generation) "
                "are slower than target. This directly impacts user experience."
            )
        
        # General recommendations
        if not recommendations:
            recommendations.append(
                "EXCELLENT: All tests passed performance benchmarks. "
                "System is ready for production deployment."
            )
        else:
            recommendations.extend([
                "Consider implementing response caching for frequently accessed data",
                "Monitor database query performance and add indexes where needed",
                "Set up real-time performance monitoring in production",
                "Implement circuit breakers for external service dependencies",
                "Consider horizontal scaling if load increases significantly"
            ])
        
        return recommendations
    
    def _print_comprehensive_summary(self, report: Dict[str, Any]):
        """
        Print comprehensive test summary.
        """
        print("\n🎯 MITA Load Testing - Comprehensive Results")
        print("=" * 60)
        print(f"Tests Run: {report['total_tests_run']}")
        print(f"Successful: {report['successful_tests']}")
        print(f"Success Rate: {(report['successful_tests'] / max(report['total_tests_run'], 1)) * 100:.1f}%")
        
        summary = report['performance_summary']
        if 'error' not in summary:
            print("\n📊 Performance Summary:")
            print(f"   Total Requests: {summary['total_requests_across_all_tests']:,}")
            print(f"   Overall Failure Rate: {summary['overall_failure_rate']:.2f}%")
            print(f"   Average Response Time: {summary['average_response_time_across_tests']:.1f}ms")
            print(f"   Best Test: {summary['best_performing_test']}")
            print(f"   Worst Test: {summary['worst_performing_test']}")
        
        print("\n💡 Recommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")


def main():
    """
    Main function to run MITA load tests based on command line arguments.
    """
    parser = argparse.ArgumentParser(description="MITA Load Testing Suite")
    parser.add_argument("--host", default="http://localhost:8000", 
                       help="Base URL for the API server")
    parser.add_argument("--test", choices=[
        "smoke", "baseline", "load", "stress", "spike", "endurance",
        "financial", "auth", "mobile", "all"
    ], default="all", help="Test type to run")
    parser.add_argument("--skip-smoke", action="store_true",
                       help="Skip smoke test when running 'all'")
    
    args = parser.parse_args()
    
    runner = MITALoadTestRunner(base_url=args.host)
    
    print(f"🚀 Starting MITA Load Tests against {args.host}")
    print(f"Test Type: {args.test}")
    print("=" * 60)
    
    # Run tests based on selection
    if args.test == "smoke":
        runner.run_smoke_test()
    elif args.test == "baseline":
        runner.run_baseline_performance_test()
    elif args.test == "load":
        runner.run_load_test()
    elif args.test == "stress":
        runner.run_stress_test()
    elif args.test == "spike":
        runner.run_spike_test()
    elif args.test == "endurance":
        runner.run_endurance_test()
    elif args.test == "financial":
        runner.run_financial_operations_focus_test()
    elif args.test == "auth":
        runner.run_authentication_load_test()
    elif args.test == "mobile":
        runner.run_mobile_simulation_test()
    elif args.test == "all":
        # Run comprehensive test suite
        if not args.skip_smoke:
            smoke_result = runner.run_smoke_test()
            if not smoke_result.get("success", False):
                print("❌ Smoke test failed. Aborting remaining tests.")
                sys.exit(1)
        
        runner.run_baseline_performance_test()
        runner.run_load_test()
        runner.run_authentication_load_test()
        runner.run_financial_operations_focus_test()
        runner.run_mobile_simulation_test()
        runner.run_stress_test()
        # Skip spike and endurance in 'all' by default (too intensive)
        
    # Generate comprehensive report
    runner.generate_comprehensive_report()
    
    print("\n🏁 Load testing completed!")


if __name__ == "__main__":
    main()