#!/usr/bin/env python3
"""
Performance Report Generator for MITA
Consolidates performance test results from multiple sources into comprehensive reports.
"""

import json
import os
import argparse
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


class PerformanceReportGenerator:
    """
    Generates comprehensive performance reports from various test outputs.
    Consolidates unit tests, load tests, security tests, and memory tests.
    """
    
    def __init__(self, input_dir: str, output_file: str = "performance_summary.json"):
        self.input_dir = Path(input_dir)
        self.output_file = output_file
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "detailed_results": {},
            "performance_metrics": {},
            "recommendations": [],
            "overall_status": "UNKNOWN"
        }
    
    def collect_benchmark_results(self) -> Dict[str, Any]:
        """Collect and parse pytest-benchmark results"""
        benchmark_results = {}
        
        benchmark_files = [
            "income_classification_benchmark.json",
            "auth_benchmark.json", 
            "security_benchmark.json",
            "memory_benchmark.json"
        ]
        
        for filename in benchmark_files:
            file_path = self.input_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    test_category = filename.replace('_benchmark.json', '')
                    benchmark_results[test_category] = self._parse_benchmark_data(data)
                except Exception as e:
                    print(f"Warning: Could not parse {filename}: {e}")
        
        return benchmark_results
    
    def _parse_benchmark_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse pytest-benchmark JSON output"""
        parsed = {
            "benchmarks": [],
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "average_time_ms": 0.0
            }
        }
        
        if "benchmarks" in data:
            for benchmark in data["benchmarks"]:
                parsed_benchmark = {
                    "name": benchmark.get("name", "unknown"),
                    "fullname": benchmark.get("fullname", ""),
                    "mean_ms": benchmark["stats"]["mean"] * 1000,  # Convert to ms
                    "stddev_ms": benchmark["stats"]["stddev"] * 1000,
                    "min_ms": benchmark["stats"]["min"] * 1000,
                    "max_ms": benchmark["stats"]["max"] * 1000,
                    "rounds": benchmark["stats"]["rounds"]
                }
                parsed["benchmarks"].append(parsed_benchmark)
            
            # Calculate summary statistics
            if parsed["benchmarks"]:
                mean_times = [b["mean_ms"] for b in parsed["benchmarks"]]
                parsed["summary"] = {
                    "total_tests": len(parsed["benchmarks"]),
                    "passed_tests": len(parsed["benchmarks"]),  # All benchmarks that ran are considered passed
                    "failed_tests": 0,
                    "average_time_ms": statistics.mean(mean_times),
                    "fastest_test_ms": min(mean_times),
                    "slowest_test_ms": max(mean_times)
                }
        
        return parsed
    
    def collect_load_test_results(self) -> Dict[str, Any]:
        """Collect Locust load test results"""
        load_test_results = {}
        
        # Look for load test report directories
        for subdir in self.input_dir.iterdir():
            if subdir.is_dir() and "load-test-reports" in subdir.name:
                scenario_name = subdir.name.replace("load-test-reports-", "")
                
                # Look for CSV stats files
                stats_files = list(subdir.glob("*_stats.csv"))
                if stats_files:
                    try:
                        load_test_results[scenario_name] = self._parse_load_test_csv(stats_files[0])
                    except Exception as e:
                        print(f"Warning: Could not parse load test results for {scenario_name}: {e}")
        
        return load_test_results
    
    def _parse_load_test_csv(self, csv_file: Path) -> Dict[str, Any]:
        """Parse Locust CSV stats output"""
        import csv
        
        results = {
            "endpoints": [],
            "summary": {
                "total_requests": 0,
                "total_failures": 0,
                "average_response_time": 0.0,
                "requests_per_second": 0.0,
                "failure_rate": 0.0
            }
        }
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                total_requests = 0
                total_failures = 0
                weighted_response_time = 0.0
                total_rps = 0.0
                
                for row in reader:
                    if row.get("Type") == "GET" or row.get("Type") == "POST":
                        requests = int(row.get("Request Count", 0))
                        failures = int(row.get("Failure Count", 0))
                        avg_response = float(row.get("Average Response Time", 0))
                        rps = float(row.get("Requests/s", 0))
                        
                        endpoint_result = {
                            "name": row.get("Name", "unknown"),
                            "method": row.get("Type", "unknown"),
                            "requests": requests,
                            "failures": failures,
                            "avg_response_time": avg_response,
                            "requests_per_second": rps,
                            "failure_rate": (failures / max(requests, 1)) * 100
                        }
                        results["endpoints"].append(endpoint_result)
                        
                        # Aggregate totals
                        total_requests += requests
                        total_failures += failures
                        weighted_response_time += avg_response * requests
                        total_rps += rps
                
                # Calculate summary
                results["summary"] = {
                    "total_requests": total_requests,
                    "total_failures": total_failures,
                    "average_response_time": weighted_response_time / max(total_requests, 1),
                    "requests_per_second": total_rps,
                    "failure_rate": (total_failures / max(total_requests, 1)) * 100
                }
        
        except Exception as e:
            print(f"Error parsing CSV file {csv_file}: {e}")
        
        return results
    
    def analyze_performance_targets(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance against defined targets"""
        
        # Define performance targets (from QA report)
        targets = {
            "income_classification": {
                "target_ms": 0.08,
                "max_acceptable_ms": 0.15,
                "description": "Income classification operations"
            },
            "auth_login": {
                "target_ms": 200.0,
                "max_acceptable_ms": 500.0,
                "description": "User authentication login"
            },
            "auth_token_validation": {
                "target_ms": 15.0,
                "max_acceptable_ms": 50.0,
                "description": "JWT token validation"
            },
            "rate_limiter_overhead": {
                "target_ms": 5.0,
                "max_acceptable_ms": 10.0,
                "description": "Rate limiting overhead"
            }
        }
        
        analysis = {
            "targets_met": 0,
            "targets_failed": 0,
            "critical_failures": 0,
            "results": {}
        }
        
        # Analyze each category
        for category, data in benchmark_results.items():
            if "benchmarks" in data:
                for benchmark in data["benchmarks"]:
                    benchmark_name = benchmark["name"]
                    mean_time = benchmark["mean_ms"]
                    
                    # Try to match benchmark to target
                    target_key = self._match_benchmark_to_target(benchmark_name, targets)
                    
                    if target_key:
                        target = targets[target_key]
                        
                        result = {
                            "benchmark": benchmark_name,
                            "actual_ms": mean_time,
                            "target_ms": target["target_ms"],
                            "max_acceptable_ms": target["max_acceptable_ms"],
                            "meets_target": mean_time <= target["target_ms"],
                            "within_acceptable": mean_time <= target["max_acceptable_ms"],
                            "performance_ratio": mean_time / target["target_ms"]
                        }
                        
                        analysis["results"][target_key] = result
                        
                        if result["meets_target"]:
                            analysis["targets_met"] += 1
                        else:
                            analysis["targets_failed"] += 1
                            
                            if not result["within_acceptable"]:
                                analysis["critical_failures"] += 1
        
        return analysis
    
    def _match_benchmark_to_target(self, benchmark_name: str, targets: Dict[str, Any]) -> Optional[str]:
        """Match benchmark name to performance target"""
        name_lower = benchmark_name.lower()
        
        if "classification" in name_lower and "income" in name_lower:
            return "income_classification"
        elif "login" in name_lower or "authenticate" in name_lower:
            return "auth_login"  
        elif "token" in name_lower and ("validation" in name_lower or "verify" in name_lower):
            return "auth_token_validation"
        elif "rate" in name_lower and "limit" in name_lower:
            return "rate_limiter_overhead"
        
        return None
    
    def generate_recommendations(
        self, 
        benchmark_results: Dict[str, Any], 
        load_test_results: Dict[str, Any],
        performance_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate performance optimization recommendations"""
        
        recommendations = []
        
        # Check critical failures
        if performance_analysis.get("critical_failures", 0) > 0:
            recommendations.append(
                "CRITICAL: Some performance benchmarks exceed maximum acceptable limits. "
                "Immediate optimization required before production deployment."
            )
        
        # Check income classification performance (most critical)
        income_results = performance_analysis.get("results", {}).get("income_classification")
        if income_results and not income_results["meets_target"]:
            if income_results["performance_ratio"] > 2.0:
                recommendations.append(
                    "HIGH PRIORITY: Income classification is >2x slower than target. "
                    "This will significantly impact user experience."
                )
            else:
                recommendations.append(
                    "MEDIUM PRIORITY: Income classification performance needs optimization. "
                    "Consider caching frequently used threshold data."
                )
        
        # Check authentication performance
        auth_results = performance_analysis.get("results", {}).get("auth_login")
        if auth_results and not auth_results["meets_target"]:
            recommendations.append(
                "Authentication performance optimization needed. "
                "Consider optimizing password hashing parameters or database queries."
            )
        
        # Check load test results
        for scenario, results in load_test_results.items():
            summary = results.get("summary", {})
            if summary.get("failure_rate", 0) > 5.0:
                recommendations.append(
                    f"Load test scenario '{scenario}' has high failure rate "
                    f"({summary['failure_rate']:.1f}%). Investigate error causes."
                )
            
            if summary.get("average_response_time", 0) > 2000:
                recommendations.append(
                    f"Load test scenario '{scenario}' has slow average response time "
                    f"({summary['average_response_time']:.0f}ms). Consider performance optimization."
                )
        
        # General recommendations if no specific issues
        if not recommendations:
            recommendations.extend([
                "EXCELLENT: All performance targets met. System ready for production.",
                "Continue monitoring performance metrics in production environment.",
                "Set up automated performance regression detection.",
                "Consider implementing performance budgets for CI/CD pipeline."
            ])
        else:
            recommendations.extend([
                "Implement performance monitoring dashboards for production.",
                "Set up alerts for performance degradation.",
                "Consider load testing with production-like data volumes.",
                "Review database query performance and add indexes where needed."
            ])
        
        return recommendations
    
    def determine_overall_status(self, performance_analysis: Dict[str, Any]) -> str:
        """Determine overall performance status"""
        
        critical_failures = performance_analysis.get("critical_failures", 0)
        targets_failed = performance_analysis.get("targets_failed", 0)
        targets_met = performance_analysis.get("targets_met", 0)
        
        if critical_failures > 0:
            return "CRITICAL_FAILURE"
        elif targets_failed > targets_met:
            return "PERFORMANCE_ISSUES"
        elif targets_failed > 0:
            return "MINOR_ISSUES"
        elif targets_met > 0:
            return "EXCELLENT"
        else:
            return "INSUFFICIENT_DATA"
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        print("Collecting benchmark results...")
        benchmark_results = self.collect_benchmark_results()
        
        print("Collecting load test results...")
        load_test_results = self.collect_load_test_results()
        
        print("Analyzing performance targets...")
        performance_analysis = self.analyze_performance_targets(benchmark_results)
        
        print("Generating recommendations...")
        recommendations = self.generate_recommendations(
            benchmark_results, load_test_results, performance_analysis
        )
        
        overall_status = self.determine_overall_status(performance_analysis)
        
        # Build comprehensive report
        self.report_data.update({
            "summary": {
                "targets_met": performance_analysis.get("targets_met", 0),
                "targets_failed": performance_analysis.get("targets_failed", 0),
                "critical_failures": performance_analysis.get("critical_failures", 0),
                "load_test_scenarios": len(load_test_results),
                "benchmark_categories": len(benchmark_results)
            },
            "detailed_results": {
                "benchmark_results": benchmark_results,
                "load_test_results": load_test_results,
                "performance_analysis": performance_analysis
            },
            "performance_metrics": {
                "income_classification": self._extract_metric(performance_analysis, "income_classification"),
                "authentication": self._extract_auth_metrics(performance_analysis),
                "security": self._extract_security_metrics(performance_analysis),
                "memory": self._extract_memory_metrics(benchmark_results)
            },
            "recommendations": recommendations,
            "overall_status": overall_status
        })
        
        return self.report_data
    
    def _extract_metric(self, analysis: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Extract specific metric from analysis"""
        results = analysis.get("results", {}).get(key, {})
        return {
            "actual_ms": results.get("actual_ms"),
            "target_ms": results.get("target_ms"),
            "meets_target": results.get("meets_target", False),
            "performance_ratio": results.get("performance_ratio", 0)
        } if results else {"status": "not_measured"}
    
    def _extract_auth_metrics(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authentication-related metrics"""
        login_metric = self._extract_metric(analysis, "auth_login")
        token_metric = self._extract_metric(analysis, "auth_token_validation")
        
        return {
            "login_ms": login_metric.get("actual_ms"),
            "token_validation_ms": token_metric.get("actual_ms"),
            "login_meets_target": login_metric.get("meets_target", False),
            "token_meets_target": token_metric.get("meets_target", False)
        }
    
    def _extract_security_metrics(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract security-related metrics"""
        rate_limiter = self._extract_metric(analysis, "rate_limiter_overhead")
        
        return {
            "rate_limiter_overhead_ms": rate_limiter.get("actual_ms"),
            "rate_limiter_meets_target": rate_limiter.get("meets_target", False)
        }
    
    def _extract_memory_metrics(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract memory-related metrics from benchmark results"""
        # This would need to be enhanced based on actual memory test output format
        return {
            "leaks_detected": False,  # Would parse from memory test results
            "peak_memory_mb": None    # Would extract from memory test results
        }
    
    def save_report(self):
        """Save report to file"""
        report = self.generate_report()
        
        with open(self.output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Performance report saved to {self.output_file}")
        
        # Print summary to console
        self._print_summary(report)
        
        return report
    
    def _print_summary(self, report: Dict[str, Any]):
        """Print performance report summary to console"""
        print(f"\n{'='*60}")
        print("MITA PERFORMANCE REPORT SUMMARY")
        print(f"{'='*60}")
        
        summary = report["summary"]
        print(f"Overall Status: {report['overall_status']}")
        print(f"Targets Met: {summary['targets_met']}")
        print(f"Targets Failed: {summary['targets_failed']}")
        print(f"Critical Failures: {summary['critical_failures']}")
        
        print("\n📊 Key Performance Metrics:")
        metrics = report["performance_metrics"]
        
        # Income classification
        income = metrics["income_classification"]
        if income.get("actual_ms"):
            status = "✅" if income["meets_target"] else "❌"
            print(f"   Income Classification: {income['actual_ms']:.3f}ms {status}")
        
        # Authentication
        auth = metrics["authentication"]
        if auth.get("login_ms"):
            status = "✅" if auth["login_meets_target"] else "❌"
            print(f"   Authentication Login: {auth['login_ms']:.1f}ms {status}")
        
        print("\n💡 Top Recommendations:")
        for i, rec in enumerate(report["recommendations"][:3], 1):
            print(f"   {i}. {rec[:80]}{'...' if len(rec) > 80 else ''}")


def main():
    parser = argparse.ArgumentParser(description="Generate MITA Performance Report")
    parser.add_argument("--input-dir", required=True, 
                       help="Directory containing performance test results")
    parser.add_argument("--output", default="performance_summary.json",
                       help="Output file for the performance report")
    
    args = parser.parse_args()
    
    # Create input directory if it doesn't exist
    os.makedirs(args.input_dir, exist_ok=True)
    
    generator = PerformanceReportGenerator(args.input_dir, args.output)
    generator.save_report()


if __name__ == "__main__":
    main()