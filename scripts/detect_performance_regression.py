#!/usr/bin/env python3
"""
Performance Regression Detection for MITA
Compares current performance metrics against historical baselines to detect regressions.
"""

import json
import os
import argparse
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceRegressionDetector:
    """
    Detects performance regressions by comparing current metrics against baselines.
    Uses statistical analysis to determine significant performance changes.
    """
    
    def __init__(self, reports_dir: str, baseline_branch: str = "main", current_branch: str = "current"):
        self.reports_dir = Path(reports_dir)
        self.baseline_branch = baseline_branch
        self.current_branch = current_branch
        
        # Regression detection thresholds
        self.thresholds = {
            "critical_regression_percent": 50.0,    # 50% slower = critical
            "significant_regression_percent": 20.0, # 20% slower = significant  
            "minor_regression_percent": 10.0,       # 10% slower = minor
            "improvement_threshold_percent": 10.0,  # 10% faster = improvement
            "noise_threshold_percent": 5.0          # < 5% change = noise
        }
        
        # Key metrics to monitor for regressions
        self.key_metrics = [
            "income_classification_ms",
            "auth_login_ms", 
            "auth_token_validation_ms",
            "rate_limiter_overhead_ms",
            "average_response_time_ms",
            "requests_per_second",
            "memory_usage_mb"
        ]
        
        self.regression_report = {
            "analysis_timestamp": datetime.now().isoformat(),
            "baseline_branch": baseline_branch,
            "current_branch": current_branch,
            "regressions_detected": 0,
            "improvements_detected": 0,
            "critical_regressions": [],
            "significant_regressions": [],
            "minor_regressions": [],
            "improvements": [],
            "all_comparisons": [],
            "summary": {}
        }
    
    def load_baseline_metrics(self) -> Dict[str, Any]:
        """Load historical baseline performance metrics"""
        baseline_file = self.reports_dir / f"baseline_{self.baseline_branch}.json"
        
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load baseline metrics: {e}")
        
        # Try to construct baseline from available reports
        return self._construct_baseline_from_reports()
    
    def _construct_baseline_from_reports(self) -> Dict[str, Any]:
        """Construct baseline metrics from available performance reports"""
        logger.info("Constructing baseline from available performance reports...")
        
        # Look for performance summary files
        summary_files = list(self.reports_dir.glob("**/performance_summary.json"))
        
        if not summary_files:
            logger.warning("No baseline performance data found")
            return {}
        
        # Use the most recent performance summary as baseline
        # In production, you'd maintain historical data
        latest_summary = max(summary_files, key=lambda f: f.stat().st_mtime)
        
        try:
            with open(latest_summary, 'r') as f:
                baseline_data = json.load(f)
                logger.info(f"Using {latest_summary} as baseline")
                return baseline_data
        except Exception as e:
            logger.error(f"Could not load baseline from {latest_summary}: {e}")
            return {}
    
    def extract_current_metrics(self) -> Dict[str, Any]:
        """Extract current performance metrics from test reports"""
        current_metrics = {}
        
        # Look for current performance reports
        for report_dir in self.reports_dir.iterdir():
            if report_dir.is_dir():
                # Check for performance summary
                summary_file = report_dir / "performance_summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            data = json.load(f)
                            current_metrics.update(self._extract_metrics_from_summary(data))
                    except Exception as e:
                        logger.warning(f"Could not extract metrics from {summary_file}: {e}")
                
                # Check for load test results
                self._extract_load_test_metrics(report_dir, current_metrics)
                
                # Check for benchmark results
                self._extract_benchmark_metrics(report_dir, current_metrics)
        
        return current_metrics
    
    def _extract_metrics_from_summary(self, summary_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract key metrics from performance summary"""
        metrics = {}
        
        perf_metrics = summary_data.get("performance_metrics", {})
        
        # Income classification
        income = perf_metrics.get("income_classification", {})
        if income.get("actual_ms"):
            metrics["income_classification_ms"] = income["actual_ms"]
        
        # Authentication
        auth = perf_metrics.get("authentication", {})
        if auth.get("login_ms"):
            metrics["auth_login_ms"] = auth["login_ms"]
        if auth.get("token_validation_ms"):
            metrics["auth_token_validation_ms"] = auth["token_validation_ms"]
        
        # Security
        security = perf_metrics.get("security", {})
        if security.get("rate_limiter_overhead_ms"):
            metrics["rate_limiter_overhead_ms"] = security["rate_limiter_overhead_ms"]
        
        # Memory
        memory = perf_metrics.get("memory", {})
        if memory.get("peak_memory_mb"):
            metrics["memory_usage_mb"] = memory["peak_memory_mb"]
        
        return metrics
    
    def _extract_load_test_metrics(self, report_dir: Path, metrics: Dict[str, float]):
        """Extract metrics from load test results"""
        # Look for CSV files with load test results
        csv_files = list(report_dir.glob("**/*_stats.csv"))
        
        for csv_file in csv_files:
            try:
                import csv
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    total_requests = 0
                    total_time = 0.0
                    
                    for row in reader:
                        if row.get("Type") in ["GET", "POST"]:
                            requests = int(row.get("Request Count", 0))
                            avg_time = float(row.get("Average Response Time", 0))
                            
                            total_requests += requests
                            total_time += avg_time * requests
                    
                    if total_requests > 0:
                        avg_response_time = total_time / total_requests
                        metrics["average_response_time_ms"] = avg_response_time
                        
                        # Calculate rough RPS (this would be more accurate with duration)
                        metrics["requests_per_second"] = total_requests / 60  # Assume 1 minute test
            
            except Exception as e:
                logger.warning(f"Could not extract load test metrics from {csv_file}: {e}")
    
    def _extract_benchmark_metrics(self, report_dir: Path, metrics: Dict[str, float]):
        """Extract metrics from benchmark JSON files"""
        benchmark_files = list(report_dir.glob("**/*_benchmark.json"))
        
        for benchmark_file in benchmark_files:
            try:
                with open(benchmark_file, 'r') as f:
                    data = json.load(f)
                
                if "benchmarks" in data:
                    for benchmark in data["benchmarks"]:
                        name = benchmark.get("name", "").lower()
                        mean_ms = benchmark["stats"]["mean"] * 1000
                        
                        # Map benchmark names to metric keys
                        if "classification" in name and "income" in name:
                            metrics["income_classification_ms"] = mean_ms
                        elif "login" in name or "authenticate" in name:
                            metrics["auth_login_ms"] = mean_ms
                        elif "token" in name and "validat" in name:
                            metrics["auth_token_validation_ms"] = mean_ms
                        elif "rate" in name and "limit" in name:
                            metrics["rate_limiter_overhead_ms"] = mean_ms
            
            except Exception as e:
                logger.warning(f"Could not extract benchmark metrics from {benchmark_file}: {e}")
    
    def detect_regressions(self, baseline_metrics: Dict[str, Any], current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Detect performance regressions by comparing metrics"""
        
        # Extract baseline performance metrics
        baseline_perf = self._flatten_metrics(baseline_metrics)
        current_perf = current_metrics
        
        regressions = []
        improvements = []
        comparisons = []
        
        # Compare each key metric
        for metric_key in self.key_metrics:
            if metric_key in baseline_perf and metric_key in current_perf:
                comparison = self._compare_metric(
                    metric_key, 
                    baseline_perf[metric_key], 
                    current_perf[metric_key]
                )
                comparisons.append(comparison)
                
                if comparison["regression_level"] != "none":
                    regressions.append(comparison)
                elif comparison["change_percent"] < -self.thresholds["improvement_threshold_percent"]:
                    improvements.append(comparison)
        
        # Categorize regressions by severity
        critical_regressions = [r for r in regressions if r["regression_level"] == "critical"]
        significant_regressions = [r for r in regressions if r["regression_level"] == "significant"]
        minor_regressions = [r for r in regressions if r["regression_level"] == "minor"]
        
        # Update regression report
        self.regression_report.update({
            "regressions_detected": len(regressions),
            "improvements_detected": len(improvements),
            "critical_regressions": critical_regressions,
            "significant_regressions": significant_regressions,
            "minor_regressions": minor_regressions,
            "improvements": improvements,
            "all_comparisons": comparisons,
            "summary": {
                "total_metrics_compared": len(comparisons),
                "metrics_regressed": len(regressions),
                "metrics_improved": len(improvements),
                "metrics_stable": len(comparisons) - len(regressions) - len(improvements)
            }
        })
        
        return self.regression_report
    
    def _flatten_metrics(self, metrics_data: Dict[str, Any]) -> Dict[str, float]:
        """Flatten nested metrics structure to simple key-value pairs"""
        flattened = {}
        
        if "performance_metrics" in metrics_data:
            perf_metrics = metrics_data["performance_metrics"]
            
            # Income classification
            income = perf_metrics.get("income_classification", {})
            if income.get("actual_ms"):
                flattened["income_classification_ms"] = income["actual_ms"]
            
            # Authentication
            auth = perf_metrics.get("authentication", {})
            if auth.get("login_ms"):
                flattened["auth_login_ms"] = auth["login_ms"]
            if auth.get("token_validation_ms"):
                flattened["auth_token_validation_ms"] = auth["token_validation_ms"]
            
            # Security
            security = perf_metrics.get("security", {})
            if security.get("rate_limiter_overhead_ms"):
                flattened["rate_limiter_overhead_ms"] = security["rate_limiter_overhead_ms"]
            
            # Memory
            memory = perf_metrics.get("memory", {})
            if memory.get("peak_memory_mb"):
                flattened["memory_usage_mb"] = memory["peak_memory_mb"]
        
        # Also check for direct metrics
        for key in self.key_metrics:
            if key in metrics_data and isinstance(metrics_data[key], (int, float)):
                flattened[key] = metrics_data[key]
        
        return flattened
    
    def _compare_metric(self, metric_key: str, baseline_value: float, current_value: float) -> Dict[str, Any]:
        """Compare a single metric and determine regression level"""
        
        # Calculate change
        change_absolute = current_value - baseline_value
        change_percent = (change_absolute / baseline_value) * 100 if baseline_value != 0 else 0
        
        # Determine regression level
        regression_level = "none"
        if change_percent > self.thresholds["critical_regression_percent"]:
            regression_level = "critical"
        elif change_percent > self.thresholds["significant_regression_percent"]:
            regression_level = "significant"
        elif change_percent > self.thresholds["minor_regression_percent"]:
            regression_level = "minor"
        
        # Determine if this is noise
        is_noise = abs(change_percent) <= self.thresholds["noise_threshold_percent"]
        
        return {
            "metric": metric_key,
            "baseline_value": baseline_value,
            "current_value": current_value,
            "change_absolute": change_absolute,
            "change_percent": change_percent,
            "regression_level": regression_level,
            "is_noise": is_noise,
            "is_improvement": change_percent < -self.thresholds["improvement_threshold_percent"],
            "description": self._get_metric_description(metric_key)
        }
    
    def _get_metric_description(self, metric_key: str) -> str:
        """Get human-readable description for metric"""
        descriptions = {
            "income_classification_ms": "Income classification operation time",
            "auth_login_ms": "User authentication login time",
            "auth_token_validation_ms": "JWT token validation time", 
            "rate_limiter_overhead_ms": "Rate limiting overhead",
            "average_response_time_ms": "Average API response time",
            "requests_per_second": "Request throughput (higher is better)",
            "memory_usage_mb": "Memory usage"
        }
        return descriptions.get(metric_key, metric_key)
    
    def analyze_regression_impact(self) -> Dict[str, Any]:
        """Analyze the impact of detected regressions"""
        
        impact_analysis = {
            "overall_impact": "none",
            "production_readiness": True,
            "user_experience_impact": "minimal",
            "critical_issues": [],
            "action_required": []
        }
        
        critical_regressions = self.regression_report["critical_regressions"]
        significant_regressions = self.regression_report["significant_regressions"]
        
        # Analyze critical regressions
        if critical_regressions:
            impact_analysis["overall_impact"] = "critical"
            impact_analysis["production_readiness"] = False
            impact_analysis["user_experience_impact"] = "severe"
            
            for regression in critical_regressions:
                impact_analysis["critical_issues"].append(
                    f"{regression['description']}: {regression['change_percent']:.1f}% slower"
                )
                
                # Specific action recommendations
                if "income_classification" in regression["metric"]:
                    impact_analysis["action_required"].append(
                        "URGENT: Income classification performance critical for user experience"
                    )
                elif "auth_login" in regression["metric"]:
                    impact_analysis["action_required"].append(
                        "URGENT: Authentication performance affects user onboarding"
                    )
        
        # Analyze significant regressions
        elif significant_regressions:
            impact_analysis["overall_impact"] = "significant"
            impact_analysis["production_readiness"] = False  # Block deployment
            impact_analysis["user_experience_impact"] = "noticeable"
            
            for regression in significant_regressions:
                impact_analysis["action_required"].append(
                    f"Investigate {regression['description']} performance degradation"
                )
        
        # Minor regressions
        elif self.regression_report["minor_regressions"]:
            impact_analysis["overall_impact"] = "minor"
            impact_analysis["production_readiness"] = True  # Allow with monitoring
            impact_analysis["user_experience_impact"] = "minimal"
            impact_analysis["action_required"].append(
                "Monitor performance metrics after deployment"
            )
        
        # No regressions
        else:
            impact_analysis["action_required"].append(
                "No performance regressions detected - proceed with deployment"
            )
        
        return impact_analysis
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive regression detection report"""
        logger.info("Loading baseline performance metrics...")
        baseline_metrics = self.load_baseline_metrics()
        
        logger.info("Extracting current performance metrics...")
        current_metrics = self.extract_current_metrics()
        
        if not baseline_metrics:
            logger.warning("No baseline metrics available - cannot detect regressions")
            return {
                "error": "No baseline metrics available",
                "current_metrics": current_metrics
            }
        
        logger.info("Detecting performance regressions...")
        regression_analysis = self.detect_regressions(baseline_metrics, current_metrics)
        
        logger.info("Analyzing regression impact...")
        impact_analysis = self.analyze_regression_impact()
        
        # Combine all analysis
        comprehensive_report = {
            **regression_analysis,
            "impact_analysis": impact_analysis,
            "baseline_metrics_count": len(self._flatten_metrics(baseline_metrics)),
            "current_metrics_count": len(current_metrics)
        }
        
        return comprehensive_report
    
    def save_report(self, output_file: str) -> Dict[str, Any]:
        """Generate and save regression detection report"""
        report = self.generate_report()
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Regression analysis saved to {output_file}")
        
        # Print summary
        self._print_regression_summary(report)
        
        return report
    
    def _print_regression_summary(self, report: Dict[str, Any]):
        """Print regression analysis summary to console"""
        print(f"\n{'='*60}")
        print("MITA PERFORMANCE REGRESSION ANALYSIS")
        print(f"{'='*60}")
        
        if "error" in report:
            print(f"❌ {report['error']}")
            return
        
        summary = report.get("summary", {})
        impact = report.get("impact_analysis", {})
        
        print(f"Baseline Branch: {report['baseline_branch']}")
        print(f"Current Branch: {report['current_branch']}")
        print(f"Metrics Compared: {summary.get('total_metrics_compared', 0)}")
        
        print(f"\n📊 Regression Analysis:")
        print(f"   Critical Regressions: {len(report.get('critical_regressions', []))}")
        print(f"   Significant Regressions: {len(report.get('significant_regressions', []))}")
        print(f"   Minor Regressions: {len(report.get('minor_regressions', []))}")
        print(f"   Improvements: {len(report.get('improvements', []))}")
        
        print(f"\n🎯 Impact Assessment:")
        print(f"   Overall Impact: {impact.get('overall_impact', 'unknown').upper()}")
        print(f"   Production Ready: {'✅ YES' if impact.get('production_readiness', False) else '❌ NO'}")
        print(f"   User Experience: {impact.get('user_experience_impact', 'unknown').upper()}")
        
        # Show critical issues
        critical_issues = impact.get("critical_issues", [])
        if critical_issues:
            print(f"\n🚨 Critical Issues:")
            for issue in critical_issues:
                print(f"   - {issue}")
        
        # Show actions required
        actions = impact.get("action_required", [])
        if actions:
            print(f"\n💡 Actions Required:")
            for action in actions[:3]:  # Show top 3 actions
                print(f"   - {action}")


def main():
    parser = argparse.ArgumentParser(description="MITA Performance Regression Detection")
    parser.add_argument("--reports-dir", required=True,
                       help="Directory containing performance test reports")
    parser.add_argument("--baseline-branch", default="main",
                       help="Baseline branch for comparison")
    parser.add_argument("--current-branch", default="current",
                       help="Current branch being analyzed")
    parser.add_argument("--output", default="regression_report.json",
                       help="Output file for regression analysis")
    
    args = parser.parse_args()
    
    detector = PerformanceRegressionDetector(
        args.reports_dir, 
        args.baseline_branch, 
        args.current_branch
    )
    
    report = detector.save_report(args.output)
    
    # Exit with error code if critical regressions detected
    if report.get("impact_analysis", {}).get("overall_impact") == "critical":
        logger.error("Critical performance regressions detected!")
        exit(1)
    elif not report.get("impact_analysis", {}).get("production_readiness", True):
        logger.error("Performance regressions block production deployment!")
        exit(1)


if __name__ == "__main__":
    main()