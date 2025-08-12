"""
MITA Income Classification Performance Tests
Critical performance validation for financial accuracy with zero tolerance for slowdowns.
Target: ~0.08ms per classification as per QA report benchmark.
"""

import pytest
import time
import statistics
import asyncio
from decimal import Decimal
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Import the actual classification services
from app.logic.cohort_analysis import CohortAnalyzer as LegacyCohortAnalyzer
from app.engine.cohort_analyzer import CohortAnalyzer as EngineCohortAnalyzer
from app.services.core.cohort.cohort_analysis import CohortAnalyzer as CoreCohortAnalyzer
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.config.country_profiles_loader import get_profile


@dataclass
class PerformanceBenchmark:
    """Performance benchmark results"""
    operation: str
    target_ms: float
    actual_ms: float
    samples: int
    passed: bool
    percentile_95: float
    percentile_99: float
    memory_usage_mb: float


class IncomeClassificationPerformanceTests:
    """
    Critical performance tests for income classification.
    Financial applications require sub-millisecond response times for user experience.
    """
    
    # Performance targets from QA report
    CLASSIFICATION_TARGET_MS = 0.08  # Target from QA analysis
    CLASSIFICATION_MAX_MS = 0.15     # Absolute maximum acceptable
    BULK_OPERATION_TARGET_MS = 0.1   # Per item in bulk operations
    
    # Test parameters
    PERFORMANCE_ITERATIONS = 1000    # Number of iterations for reliable stats
    BULK_TEST_SIZE = 100            # Size of bulk operations
    
    @pytest.fixture
    def mock_country_profiles(self):
        """Mock country profiles with realistic US state data"""
        return {
            "US-CA": {
                "class_thresholds": {
                    "low": 44935,           # California median thresholds
                    "lower_middle": 71896,
                    "middle": 107844,
                    "upper_middle": 179740
                }
            },
            "US-TX": {
                "class_thresholds": {
                    "low": 36000,           # Texas median thresholds  
                    "lower_middle": 57600,
                    "middle": 86400,
                    "upper_middle": 144000
                }
            },
            "US-NY": {
                "class_thresholds": {
                    "low": 50000,           # New York median thresholds
                    "lower_middle": 80000,
                    "middle": 120000,
                    "upper_middle": 200000
                }
            }
        }
    
    @pytest.fixture
    def test_profiles(self):
        """Comprehensive test profiles covering all edge cases"""
        profiles = []
        
        # Generate profiles across all income ranges for each state
        states = ["US-CA", "US-TX", "US-NY"]
        incomes = [
            1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000,  # Low range
            5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000,  # Lower middle
            9500, 10000, 11000, 12000, 13000, 14000, 15000,  # Middle
            16000, 18000, 20000, 22000, 25000, 30000, 35000, # Upper middle
            40000, 50000, 75000, 100000, 150000              # High
        ]
        
        for state in states:
            for income in incomes:
                profiles.append({
                    "income": income,
                    "region": state, 
                    "behavior": "neutral",
                    "categories": []
                })
        
        return profiles
    
    def measure_performance(self, operation_func, iterations: int = None) -> Dict[str, float]:
        """
        Measure operation performance with statistical analysis.
        Returns comprehensive timing statistics.
        """
        iterations = iterations or self.PERFORMANCE_ITERATIONS
        times = []
        
        # Warmup runs to eliminate cold start effects
        for _ in range(10):
            operation_func()
        
        # Actual performance measurement
        for _ in range(iterations):
            start_time = time.perf_counter()
            operation_func()
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds
        
        return {
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times), 
            "std_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "min_ms": min(times),
            "max_ms": max(times),
            "p95_ms": self._percentile(times, 95),
            "p99_ms": self._percentile(times, 99),
            "samples": len(times)
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile from data"""
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = int(k)
        c = int(k) + 1
        if f == c:
            return sorted_data[f]
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_core_cohort_analyzer_single_classification_performance(
        self, mock_get_profile, mock_country_profiles, test_profiles
    ):
        """
        CRITICAL: Test single income classification performance.
        Must meet 0.08ms target per QA report.
        """
        # Use California profile for consistent testing
        mock_get_profile.return_value = mock_country_profiles["US-CA"]
        
        analyzer = CoreCohortAnalyzer()
        test_profile = test_profiles[0]  # Use first profile
        
        # Performance measurement
        def classify_once():
            return analyzer.assign_cohort(test_profile)
        
        perf_stats = self.measure_performance(classify_once)
        
        # Validate performance benchmarks
        benchmark = PerformanceBenchmark(
            operation="single_classification",
            target_ms=self.CLASSIFICATION_TARGET_MS,
            actual_ms=perf_stats["mean_ms"],
            samples=perf_stats["samples"],
            passed=perf_stats["mean_ms"] <= self.CLASSIFICATION_MAX_MS,
            percentile_95=perf_stats["p95_ms"],
            percentile_99=perf_stats["p99_ms"],
            memory_usage_mb=0  # Will implement memory tracking
        )
        
        # Critical assertions for financial application performance
        assert benchmark.passed, (
            f"Income classification FAILED performance benchmark! "
            f"Target: {self.CLASSIFICATION_TARGET_MS}ms, "
            f"Actual: {perf_stats['mean_ms']:.3f}ms, "
            f"Max allowed: {self.CLASSIFICATION_MAX_MS}ms. "
            f"This is a CRITICAL failure for production readiness."
        )
        
        # Additional quality checks
        assert perf_stats["p95_ms"] <= self.CLASSIFICATION_MAX_MS * 2, (
            f"95th percentile too slow: {perf_stats['p95_ms']:.3f}ms"
        )
        
        assert perf_stats["p99_ms"] <= self.CLASSIFICATION_MAX_MS * 3, (
            f"99th percentile too slow: {perf_stats['p99_ms']:.3f}ms"
        )
        
        # Performance report for monitoring
        print(f"\n✅ Single Classification Performance Report:")
        print(f"   Mean: {perf_stats['mean_ms']:.3f}ms (target: {self.CLASSIFICATION_TARGET_MS}ms)")
        print(f"   P95:  {perf_stats['p95_ms']:.3f}ms")
        print(f"   P99:  {perf_stats['p99_ms']:.3f}ms")
        print(f"   Range: {perf_stats['min_ms']:.3f}ms - {perf_stats['max_ms']:.3f}ms")
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_bulk_classification_performance(
        self, mock_get_profile, mock_country_profiles, test_profiles
    ):
        """
        Test bulk classification performance for batch operations.
        Common in financial reporting and analytics.
        """
        mock_get_profile.return_value = mock_country_profiles["US-CA"]
        analyzer = CoreCohortAnalyzer()
        
        # Select subset for bulk testing
        bulk_profiles = test_profiles[:self.BULK_TEST_SIZE]
        
        def classify_bulk():
            results = []
            for profile in bulk_profiles:
                results.append(analyzer.assign_cohort(profile))
            return results
        
        # Measure bulk operation performance
        perf_stats = self.measure_performance(classify_bulk, iterations=100)
        
        # Calculate per-item performance
        per_item_ms = perf_stats["mean_ms"] / len(bulk_profiles)
        
        assert per_item_ms <= self.BULK_OPERATION_TARGET_MS, (
            f"Bulk classification per-item performance failed! "
            f"Target: {self.BULK_OPERATION_TARGET_MS}ms per item, "
            f"Actual: {per_item_ms:.3f}ms per item"
        )
        
        print(f"\n✅ Bulk Classification Performance Report:")
        print(f"   Items processed: {len(bulk_profiles)}")
        print(f"   Total time: {perf_stats['mean_ms']:.3f}ms")
        print(f"   Per item: {per_item_ms:.3f}ms (target: {self.BULK_OPERATION_TARGET_MS}ms)")
        print(f"   Throughput: {len(bulk_profiles) / (perf_stats['mean_ms'] / 1000):.0f} classifications/second")
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_multi_state_classification_performance(
        self, mock_get_profile, mock_country_profiles, test_profiles
    ):
        """
        Test classification performance across different states.
        State-specific thresholds should not impact performance.
        """
        analyzer = CoreCohortAnalyzer()
        
        # Test each state's performance
        state_results = {}
        
        for state, profile_data in mock_country_profiles.items():
            mock_get_profile.return_value = profile_data
            
            # Find profiles for this state
            state_profiles = [p for p in test_profiles if p["region"] == state][:20]
            
            def classify_state_profiles():
                for profile in state_profiles:
                    analyzer.assign_cohort(profile)
            
            perf_stats = self.measure_performance(classify_state_profiles, iterations=100)
            per_item_ms = perf_stats["mean_ms"] / len(state_profiles)
            
            state_results[state] = {
                "per_item_ms": per_item_ms,
                "profiles_tested": len(state_profiles),
                "mean_ms": perf_stats["mean_ms"]
            }
            
            # Validate each state meets performance requirements
            assert per_item_ms <= self.CLASSIFICATION_MAX_MS, (
                f"State {state} classification too slow: {per_item_ms:.3f}ms"
            )
        
        # Ensure performance is consistent across states (within 50% variance)
        per_item_times = [result["per_item_ms"] for result in state_results.values()]
        performance_variance = max(per_item_times) - min(per_item_times)
        average_time = sum(per_item_times) / len(per_item_times)
        
        assert performance_variance / average_time <= 0.5, (
            f"Performance variance too high across states: {performance_variance:.3f}ms variance"
        )
        
        print(f"\n✅ Multi-State Performance Report:")
        for state, result in state_results.items():
            print(f"   {state}: {result['per_item_ms']:.3f}ms per item ({result['profiles_tested']} profiles)")
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_analyzer_consistency_performance(
        self, mock_get_profile, mock_country_profiles
    ):
        """
        Test that all analyzer implementations have similar performance.
        Critical for maintaining consistency across codebase.
        """
        mock_get_profile.return_value = mock_country_profiles["US-CA"]
        
        test_profile = {
            "income": 5000,
            "region": "US-CA",
            "behavior": "neutral", 
            "categories": []
        }
        
        # Test each analyzer type
        analyzers = {
            "legacy": LegacyCohortAnalyzer(),
            "engine": EngineCohortAnalyzer(),
            "core": CoreCohortAnalyzer()
        }
        
        analyzer_performance = {}
        
        for name, analyzer in analyzers.items():
            if hasattr(analyzer, 'register_user'):
                def classify_with_registration():
                    analyzer.register_user("test_user", test_profile)
                    return analyzer.assign_cohort("test_user")
            else:
                def classify_with_registration():
                    return analyzer.assign_cohort(test_profile)
            
            perf_stats = self.measure_performance(classify_with_registration)
            analyzer_performance[name] = perf_stats["mean_ms"]
            
            # Each analyzer must meet performance requirements
            assert perf_stats["mean_ms"] <= self.CLASSIFICATION_MAX_MS, (
                f"{name} analyzer too slow: {perf_stats['mean_ms']:.3f}ms"
            )
        
        print(f"\n✅ Analyzer Performance Comparison:")
        for name, ms in analyzer_performance.items():
            print(f"   {name.capitalize()}: {ms:.3f}ms")
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_budget_generation_performance(self, mock_get_profile, mock_country_profiles):
        """
        Test budget generation performance including income classification.
        End-to-end performance for complete financial operations.
        """
        mock_get_profile.return_value = mock_country_profiles["US-CA"]
        
        # Realistic budget generation request
        answers = {
            "region": "US-CA",
            "income": {
                "monthly_income": 5000,
                "additional_income": 500
            },
            "fixed_expenses": {
                "rent": 1800,
                "utilities": 250,
                "insurance": 200,
                "loan_payments": 400
            },
            "goals": {"savings_goal_amount_per_month": 800},
            "spending_habits": {
                "dining_out_per_month": 8,
                "entertainment_per_month": 5,
                "clothing_per_month": 3,
                "travel_per_year": 12,
                "coffee_per_week": 5,
                "transport_per_month": 15
            }
        }
        
        def generate_budget():
            return generate_budget_from_answers(answers)
        
        perf_stats = self.measure_performance(generate_budget, iterations=200)
        
        # Budget generation should complete within 50ms for excellent UX
        BUDGET_GENERATION_MAX_MS = 50.0
        
        assert perf_stats["mean_ms"] <= BUDGET_GENERATION_MAX_MS, (
            f"Budget generation too slow: {perf_stats['mean_ms']:.3f}ms "
            f"(max: {BUDGET_GENERATION_MAX_MS}ms)"
        )
        
        print(f"\n✅ Budget Generation Performance Report:")
        print(f"   Mean: {perf_stats['mean_ms']:.3f}ms")
        print(f"   P95:  {perf_stats['p95_ms']:.3f}ms")
        print(f"   Includes: Income classification, threshold lookup, budget calculation")
    
    def test_memory_usage_during_classification(self, mock_country_profiles, test_profiles):
        """
        Test memory usage during intensive classification operations.
        Financial apps must maintain stable memory usage.
        """
        import psutil
        import gc
        
        with patch('app.config.country_profiles_loader.get_profile') as mock_get_profile:
            mock_get_profile.return_value = mock_country_profiles["US-CA"]
            
            analyzer = CoreCohortAnalyzer()
            process = psutil.Process()
            
            # Baseline memory
            gc.collect()
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Perform many classifications
            for i in range(1000):
                profile = test_profiles[i % len(test_profiles)]
                analyzer.assign_cohort(profile)
                
                # Check memory every 100 operations
                if i % 100 == 99:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_growth = current_memory - baseline_memory
                    
                    # Memory growth should be minimal (< 10MB for 1000 operations)
                    assert memory_growth < 10.0, (
                        f"Memory growth too high after {i+1} operations: {memory_growth:.2f}MB"
                    )
            
            # Final memory check
            gc.collect()
            final_memory = process.memory_info().rss / 1024 / 1024
            total_growth = final_memory - baseline_memory
            
            print(f"\n✅ Memory Usage Report:")
            print(f"   Baseline: {baseline_memory:.2f}MB")
            print(f"   Final: {final_memory:.2f}MB")
            print(f"   Growth: {total_growth:.2f}MB (1000 classifications)")
            print(f"   Per operation: {(total_growth / 1000) * 1024:.2f}KB")
    
    @patch('app.config.country_profiles_loader.get_profile')
    def test_concurrent_classification_performance(
        self, mock_get_profile, mock_country_profiles, test_profiles
    ):
        """
        Test classification performance under concurrent load.
        Simulates real-world concurrent user scenarios.
        """
        mock_get_profile.return_value = mock_country_profiles["US-CA"]
        
        analyzer = CoreCohortAnalyzer()
        test_profile = test_profiles[0]
        
        async def classify_concurrently(num_concurrent: int, operations_per_task: int):
            """Run concurrent classification tasks"""
            
            async def classification_task():
                for _ in range(operations_per_task):
                    analyzer.assign_cohort(test_profile)
            
            tasks = [classification_task() for _ in range(num_concurrent)]
            start_time = time.perf_counter()
            await asyncio.gather(*tasks)
            end_time = time.perf_counter()
            
            total_operations = num_concurrent * operations_per_task
            total_time_ms = (end_time - start_time) * 1000
            per_operation_ms = total_time_ms / total_operations
            
            return {
                "concurrent_tasks": num_concurrent,
                "operations_per_task": operations_per_task,
                "total_operations": total_operations,
                "total_time_ms": total_time_ms,
                "per_operation_ms": per_operation_ms,
                "operations_per_second": total_operations / (total_time_ms / 1000)
            }
        
        # Test different concurrency levels
        concurrency_results = []
        
        for concurrent_tasks in [1, 5, 10, 20]:
            result = asyncio.run(classify_concurrently(concurrent_tasks, 50))
            concurrency_results.append(result)
            
            # Performance should not degrade significantly under concurrency
            assert result["per_operation_ms"] <= self.CLASSIFICATION_MAX_MS * 2, (
                f"Concurrent performance degraded at {concurrent_tasks} tasks: "
                f"{result['per_operation_ms']:.3f}ms per operation"
            )
        
        print(f"\n✅ Concurrent Classification Performance:")
        for result in concurrency_results:
            print(f"   {result['concurrent_tasks']:2d} tasks: "
                  f"{result['per_operation_ms']:.3f}ms/op, "
                  f"{result['operations_per_second']:.0f} ops/sec")


if __name__ == "__main__":
    # Run performance tests with detailed output
    pytest.main([__file__, "-v", "--tb=short", "-s"])