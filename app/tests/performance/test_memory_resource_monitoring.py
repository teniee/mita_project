"""
MITA Memory and Resource Usage Monitoring Tests
Comprehensive monitoring and testing of memory usage, resource consumption,
and system stability under various load conditions.
"""

import pytest
import time
import asyncio
import gc
import psutil
import threading
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import weakref
import sys

# Import services for testing
from app.services.performance_monitor import PerformanceMonitor, get_performance_monitor
from app.services.advanced_cache_manager import AdvancedCacheManager
from app.core.async_session import get_async_session_factory
from app.api.auth.services import authenticate_user_async, register_user_async
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.logic.cohort_analysis import CohortAnalyzer


@dataclass
class ResourceUsageSnapshot:
    """Snapshot of system resource usage"""
    timestamp: datetime
    memory_rss_mb: float
    memory_vms_mb: float
    memory_percent: float
    cpu_percent: float
    open_files: int
    threads: int
    connections: int
    gc_objects: int


@dataclass
class MemoryLeakDetection:
    """Memory leak detection results"""
    operation: str
    baseline_mb: float
    final_mb: float
    growth_mb: float
    operations_count: int
    growth_per_operation_kb: float
    potential_leak: bool
    gc_collections: int


class MemoryResourceTests:
    """
    Critical memory and resource usage tests for production stability.
    Financial applications must maintain stable resource usage over time.
    """
    
    # Memory usage thresholds for different operations
    MAX_MEMORY_GROWTH_PER_1000_OPS_MB = 10.0    # Max 10MB growth per 1000 operations
    MAX_BASELINE_MEMORY_MB = 200.0               # Max baseline memory usage
    MAX_MEMORY_LEAK_THRESHOLD_KB = 5.0           # Max 5KB per operation for leak detection
    MAX_OPEN_FILES_GROWTH = 50                   # Max file descriptor growth
    MAX_THREAD_GROWTH = 10                       # Max thread growth
    
    # Resource monitoring thresholds
    CPU_USAGE_WARNING_THRESHOLD = 80.0          # CPU usage warning
    MEMORY_USAGE_WARNING_THRESHOLD = 85.0       # Memory usage warning
    
    # Test parameters
    MEMORY_TEST_OPERATIONS = 2000               # Operations for leak detection
    STRESS_TEST_DURATION_MINUTES = 5           # Duration for stress testing
    
    @pytest.fixture
    def performance_monitor(self):
        """Get performance monitor instance"""
        return get_performance_monitor()
    
    @pytest.fixture
    def memory_profiler(self, performance_monitor):
        """Get memory profiler from performance monitor"""
        return performance_monitor.memory_profiler
    
    def capture_resource_snapshot(self, label: str = None) -> ResourceUsageSnapshot:
        """Capture comprehensive system resource snapshot"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        try:
            open_files = len(process.open_files())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            open_files = 0
        
        try:
            connections = len(process.connections())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            connections = 0
        
        return ResourceUsageSnapshot(
            timestamp=datetime.now(),
            memory_rss_mb=memory_info.rss / 1024 / 1024,
            memory_vms_mb=memory_info.vms / 1024 / 1024,
            memory_percent=process.memory_percent(),
            cpu_percent=process.cpu_percent(),
            open_files=open_files,
            threads=process.num_threads(),
            connections=connections,
            gc_objects=len(gc.get_objects())
        )
    
    def detect_memory_leaks(
        self, 
        operation_func, 
        operation_name: str,
        iterations: int = None
    ) -> MemoryLeakDetection:
        """
        Detect memory leaks in specific operations.
        Performs operation multiple times and monitors memory growth.
        """
        iterations = iterations or self.MEMORY_TEST_OPERATIONS
        
        # Force garbage collection and capture baseline
        gc.collect()
        baseline_snapshot = self.capture_resource_snapshot()
        gc_collections_start = sum(gc.get_count())
        
        # Perform operations
        for i in range(iterations):
            try:
                operation_func()
            except Exception:
                pass  # Continue testing even if some operations fail
            
            # Force GC every 100 operations to clean up
            if i % 100 == 99:
                gc.collect()
        
        # Final measurement
        gc.collect()
        final_snapshot = self.capture_resource_snapshot()
        gc_collections_end = sum(gc.get_count())
        
        # Calculate leak metrics
        memory_growth_mb = final_snapshot.memory_rss_mb - baseline_snapshot.memory_rss_mb
        growth_per_operation_kb = (memory_growth_mb * 1024) / iterations
        potential_leak = growth_per_operation_kb > self.MAX_MEMORY_LEAK_THRESHOLD_KB
        
        leak_detection = MemoryLeakDetection(
            operation=operation_name,
            baseline_mb=baseline_snapshot.memory_rss_mb,
            final_mb=final_snapshot.memory_rss_mb,
            growth_mb=memory_growth_mb,
            operations_count=iterations,
            growth_per_operation_kb=growth_per_operation_kb,
            potential_leak=potential_leak,
            gc_collections=gc_collections_end - gc_collections_start
        )
        
        return leak_detection
    
    def test_baseline_memory_usage(self):
        """
        Test baseline memory usage of the application.
        Applications should start with reasonable memory footprint.
        """
        # Allow system to stabilize
        time.sleep(2)
        gc.collect()
        
        baseline = self.capture_resource_snapshot("baseline")
        
        assert baseline.memory_rss_mb <= self.MAX_BASELINE_MEMORY_MB, (
            f"Baseline memory usage too high: {baseline.memory_rss_mb:.2f}MB "
            f"(max: {self.MAX_BASELINE_MEMORY_MB}MB)"
        )
        
        print(f"\n✅ Baseline Memory Usage:")
        print(f"   RSS Memory: {baseline.memory_rss_mb:.2f}MB")
        print(f"   VMS Memory: {baseline.memory_vms_mb:.2f}MB")
        print(f"   Memory %: {baseline.memory_percent:.1f}%")
        print(f"   Threads: {baseline.threads}")
        print(f"   Open Files: {baseline.open_files}")
        print(f"   GC Objects: {baseline.gc_objects:,}")
    
    def test_income_classification_memory_leaks(self):
        """
        Test memory leaks in income classification operations.
        Critical financial operation that runs frequently.
        """
        with patch('app.config.country_profiles_loader.get_profile') as mock_profile:
            mock_profile.return_value = {
                "class_thresholds": {
                    "low": 36000,
                    "lower_middle": 57600,
                    "middle": 86400,
                    "upper_middle": 144000
                }
            }
            
            analyzer = CohortAnalyzer()
            
            def classification_operation():
                profile = {
                    "income": 5000,
                    "region": "US-CA",
                    "behavior": "neutral",
                    "categories": []
                }
                analyzer.register_user("test_user", profile)
                return analyzer.assign_cohort("test_user")
            
            leak_result = self.detect_memory_leaks(
                classification_operation, 
                "income_classification"
            )
            
            assert not leak_result.potential_leak, (
                f"Memory leak detected in income classification: "
                f"{leak_result.growth_per_operation_kb:.3f}KB per operation "
                f"(threshold: {self.MAX_MEMORY_LEAK_THRESHOLD_KB}KB)"
            )
            
            print(f"\n✅ Income Classification Memory Leak Test:")
            print(f"   Operations: {leak_result.operations_count:,}")
            print(f"   Memory Growth: {leak_result.growth_mb:.2f}MB")
            print(f"   Per Operation: {leak_result.growth_per_operation_kb:.3f}KB")
            print(f"   GC Collections: {leak_result.gc_collections}")
            print(f"   Leak Status: {'NONE DETECTED' if not leak_result.potential_leak else 'POTENTIAL LEAK'}")
    
    def test_budget_generation_memory_usage(self):
        """
        Test memory usage during budget generation operations.
        Budget generation involves complex calculations and data processing.
        """
        with patch('app.config.country_profiles_loader.get_profile') as mock_profile:
            mock_profile.return_value = {
                "class_thresholds": {
                    "low": 36000,
                    "lower_middle": 57600, 
                    "middle": 86400,
                    "upper_middle": 144000
                },
                "default_behavior": "balanced",
                "split_profiles": {
                    "low": {"essentials": 0.7, "discretionary": 0.3},
                    "lower_middle": {"essentials": 0.6, "discretionary": 0.4},
                    "middle": {"essentials": 0.5, "discretionary": 0.5},
                    "upper_middle": {"essentials": 0.4, "discretionary": 0.6},
                    "high": {"essentials": 0.3, "discretionary": 0.7}
                }
            }
            
            def budget_generation_operation():
                answers = {
                    "region": "US-CA",
                    "income": {
                        "monthly_income": 5000,
                        "additional_income": 500
                    },
                    "fixed_expenses": {
                        "rent": 1800,
                        "utilities": 250,
                        "insurance": 200
                    },
                    "goals": {"savings_goal_amount_per_month": 600},
                    "spending_habits": {
                        "dining_out_per_month": 8,
                        "entertainment_per_month": 5,
                        "clothing_per_month": 3,
                        "travel_per_year": 12,
                        "coffee_per_week": 5,
                        "transport_per_month": 15
                    }
                }
                return generate_budget_from_answers(answers)
            
            leak_result = self.detect_memory_leaks(
                budget_generation_operation,
                "budget_generation",
                iterations=1000  # Fewer iterations due to complexity
            )
            
            assert not leak_result.potential_leak, (
                f"Memory leak detected in budget generation: "
                f"{leak_result.growth_per_operation_kb:.3f}KB per operation"
            )
            
            print(f"\n✅ Budget Generation Memory Test:")
            print(f"   Operations: {leak_result.operations_count:,}")
            print(f"   Memory Growth: {leak_result.growth_mb:.2f}MB")
            print(f"   Per Operation: {leak_result.growth_per_operation_kb:.3f}KB")
    
    def test_cache_memory_management(self):
        """
        Test memory management of caching systems.
        Cache should have bounded memory usage and proper cleanup.
        """
        cache_manager = AdvancedCacheManager()
        
        def cache_operations():
            # Add many items to cache
            for i in range(100):
                key = f"test_key_{i}"
                data = {"value": i, "data": "x" * 1000}  # 1KB per item
                cache_manager.set(key, data, ttl=60)
            
            # Read from cache
            for i in range(100):
                key = f"test_key_{i}"
                cache_manager.get(key)
            
            # Evict some items
            for i in range(0, 100, 2):  # Evict every other item
                key = f"test_key_{i}"
                cache_manager.delete(key)
        
        leak_result = self.detect_memory_leaks(
            cache_operations,
            "cache_operations",
            iterations=50  # 50 cache cycles
        )
        
        # Cache can grow but should stabilize
        assert leak_result.growth_per_operation_kb <= 20.0, (
            f"Cache memory usage growing too much: "
            f"{leak_result.growth_per_operation_kb:.3f}KB per operation"
        )
        
        print(f"\n✅ Cache Memory Management Test:")
        print(f"   Cache Cycles: {leak_result.operations_count}")
        print(f"   Memory Growth: {leak_result.growth_mb:.2f}MB")
        print(f"   Per Cycle: {leak_result.growth_per_operation_kb:.3f}KB")
    
    @pytest.mark.asyncio
    async def test_async_operations_memory_usage(self):
        """
        Test memory usage of asynchronous operations.
        Async operations can accumulate memory if not properly handled.
        """
        async def async_operation():
            # Simulate async database operation
            await asyncio.sleep(0.001)
            
            # Simulate data processing
            data = [i for i in range(100)]
            result = sum(data)
            
            # Create some temporary objects
            temp_objects = [{"id": i, "value": i * 2} for i in range(50)]
            
            return result
        
        async def run_async_operations(count: int):
            tasks = []
            for _ in range(count):
                task = asyncio.create_task(async_operation())
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            return results
        
        # Baseline measurement
        gc.collect()
        baseline = self.capture_resource_snapshot()
        
        # Run many async operations
        for batch in range(20):  # 20 batches of 50 operations each
            await run_async_operations(50)
            
            # Yield control to allow cleanup
            await asyncio.sleep(0.01)
        
        # Final measurement
        gc.collect()
        final = self.capture_resource_snapshot()
        
        memory_growth = final.memory_rss_mb - baseline.memory_rss_mb
        
        # Async operations should not accumulate significant memory
        assert memory_growth <= 20.0, (
            f"Async operations memory growth too high: {memory_growth:.2f}MB"
        )
        
        print(f"\n✅ Async Operations Memory Test:")
        print(f"   Total Operations: 1,000")
        print(f"   Memory Growth: {memory_growth:.2f}MB")
        print(f"   Thread Growth: {final.threads - baseline.threads}")
        print(f"   GC Objects Growth: {final.gc_objects - baseline.gc_objects:,}")
    
    def test_concurrent_operations_resource_usage(self):
        """
        Test resource usage under concurrent operations.
        Concurrent operations should not cause resource exhaustion.
        """
        def concurrent_operation():
            # Simulate financial calculation
            amounts = [100.50, 200.75, 150.25, 300.00, 75.80]
            total = sum(amounts)
            tax = total * 0.08
            return total - tax
        
        def run_concurrent_test():
            threads = []
            results = []
            
            # Start many concurrent operations
            for i in range(50):
                def thread_work(thread_id=i):
                    for _ in range(40):  # 40 operations per thread
                        result = concurrent_operation()
                        results.append(result)
                
                thread = threading.Thread(target=thread_work)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            return results
        
        # Measure resource usage
        baseline = self.capture_resource_snapshot()
        
        results = run_concurrent_test()
        
        final = self.capture_resource_snapshot()
        
        # Check resource growth
        memory_growth = final.memory_rss_mb - baseline.memory_rss_mb
        thread_growth = final.threads - baseline.threads
        
        assert memory_growth <= 30.0, (
            f"Concurrent operations memory growth too high: {memory_growth:.2f}MB"
        )
        
        assert thread_growth <= 20, (
            f"Thread count growth too high: {thread_growth} threads"
        )
        
        print(f"\n✅ Concurrent Operations Resource Test:")
        print(f"   Operations Completed: {len(results):,}")
        print(f"   Memory Growth: {memory_growth:.2f}MB")
        print(f"   Thread Growth: {thread_growth}")
        print(f"   Peak Threads: {final.threads}")
    
    def test_garbage_collection_efficiency(self):
        """
        Test garbage collection efficiency and cycles.
        Proper garbage collection is crucial for long-running financial applications.
        """
        # Get initial GC stats
        gc.collect()
        initial_gc_stats = gc.get_count()
        initial_objects = len(gc.get_objects())
        
        def create_temporary_objects():
            # Create objects that should be garbage collected
            temp_data = []
            for i in range(1000):
                temp_dict = {
                    "id": i,
                    "amount": i * 1.5,
                    "description": f"Transaction {i}",
                    "metadata": {"category": "test", "timestamp": time.time()}
                }
                temp_data.append(temp_dict)
            
            # Process the data (simulate real work)
            total = sum(item["amount"] for item in temp_data)
            return total
        
        # Create and destroy objects multiple times
        for cycle in range(100):
            result = create_temporary_objects()
            
            # Occasionally force garbage collection
            if cycle % 20 == 19:
                gc.collect()
        
        # Final garbage collection
        gc.collect()
        final_gc_stats = gc.get_count()
        final_objects = len(gc.get_objects())
        
        # Calculate GC efficiency
        gc_cycles = [final_gc_stats[i] - initial_gc_stats[i] for i in range(3)]
        object_growth = final_objects - initial_objects
        
        print(f"\n✅ Garbage Collection Efficiency:")
        print(f"   Initial Objects: {initial_objects:,}")
        print(f"   Final Objects: {final_objects:,}")
        print(f"   Object Growth: {object_growth:,}")
        print(f"   GC Cycles (Gen 0,1,2): {gc_cycles}")
        
        # Object growth should be reasonable after GC
        assert object_growth <= 5000, (
            f"Too many objects retained after GC: {object_growth:,}"
        )
    
    def test_long_running_stability(self):
        """
        Test system stability during extended operation.
        Simulates long-running application behavior.
        """
        print(f"\n🔄 Starting Long-Running Stability Test ({self.STRESS_TEST_DURATION_MINUTES} minutes)...")
        
        start_time = time.time()
        end_time = start_time + (self.STRESS_TEST_DURATION_MINUTES * 60)
        
        snapshots = []
        operation_count = 0
        
        # Various operations to simulate real usage
        operations = [
            lambda: sum([i * 1.5 for i in range(100)]),  # Financial calculations
            lambda: {"data": [i for i in range(50)]},     # Data structures
            lambda: [str(i) for i in range(100)],         # String operations
            lambda: time.time() + 1000,                   # Time operations
        ]
        
        while time.time() < end_time:
            # Perform random operations
            for _ in range(10):
                operation = operations[operation_count % len(operations)]
                try:
                    result = operation()
                    operation_count += 1
                except Exception:
                    pass
            
            # Take periodic snapshots
            if operation_count % 1000 == 0:
                snapshot = self.capture_resource_snapshot()
                snapshots.append(snapshot)
                
                print(f"   Operations: {operation_count:,}, "
                      f"Memory: {snapshot.memory_rss_mb:.1f}MB, "
                      f"CPU: {snapshot.cpu_percent:.1f}%")
                
                # Check for resource warnings
                if snapshot.memory_percent > self.MEMORY_USAGE_WARNING_THRESHOLD:
                    print(f"   ⚠️  High memory usage: {snapshot.memory_percent:.1f}%")
                
                if snapshot.cpu_percent > self.CPU_USAGE_WARNING_THRESHOLD:
                    print(f"   ⚠️  High CPU usage: {snapshot.cpu_percent:.1f}%")
            
            # Brief pause
            time.sleep(0.01)
        
        # Analyze stability
        if len(snapshots) >= 2:
            initial_memory = snapshots[0].memory_rss_mb
            final_memory = snapshots[-1].memory_rss_mb
            memory_growth = final_memory - initial_memory
            
            avg_cpu = sum(s.cpu_percent for s in snapshots) / len(snapshots)
            max_memory = max(s.memory_rss_mb for s in snapshots)
            
            print(f"\n✅ Long-Running Stability Results:")
            print(f"   Duration: {self.STRESS_TEST_DURATION_MINUTES} minutes")
            print(f"   Total Operations: {operation_count:,}")
            print(f"   Memory Growth: {memory_growth:.2f}MB")
            print(f"   Average CPU: {avg_cpu:.1f}%")
            print(f"   Peak Memory: {max_memory:.1f}MB")
            print(f"   Snapshots Taken: {len(snapshots)}")
            
            # Stability assertions
            assert memory_growth <= 50.0, (
                f"Memory growth too high during stability test: {memory_growth:.2f}MB"
            )
            
            assert max_memory <= 300.0, (
                f"Peak memory usage too high: {max_memory:.1f}MB"
            )
        
    def test_performance_monitor_memory_impact(self, performance_monitor):
        """
        Test memory impact of the performance monitoring system itself.
        Monitoring should not significantly impact the system being monitored.
        """
        # Test with monitoring disabled
        performance_monitor.stop()
        
        baseline = self.capture_resource_snapshot()
        
        def monitored_operation():
            # Simulate typical application operation
            data = [i * 1.5 for i in range(100)]
            return sum(data)
        
        # Run operations without monitoring
        for _ in range(1000):
            monitored_operation()
        
        without_monitoring = self.capture_resource_snapshot()
        
        # Enable monitoring and run again
        performance_monitor.start()
        
        for _ in range(1000):
            with performance_monitor.request_profiler.profile_request("/test", "GET"):
                monitored_operation()
        
        with_monitoring = self.capture_resource_snapshot()
        
        # Calculate monitoring overhead
        baseline_growth = without_monitoring.memory_rss_mb - baseline.memory_rss_mb
        monitoring_growth = with_monitoring.memory_rss_mb - without_monitoring.memory_rss_mb
        
        print(f"\n✅ Performance Monitoring Memory Impact:")
        print(f"   Baseline Growth: {baseline_growth:.2f}MB")
        print(f"   With Monitoring Growth: {monitoring_growth:.2f}MB")
        print(f"   Monitoring Overhead: {monitoring_growth - baseline_growth:.2f}MB")
        
        # Monitoring overhead should be minimal
        assert (monitoring_growth - baseline_growth) <= 5.0, (
            f"Performance monitoring overhead too high: "
            f"{monitoring_growth - baseline_growth:.2f}MB"
        )
    
    def generate_memory_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive memory and resource usage report.
        """
        current_snapshot = self.capture_resource_snapshot()
        
        # System-wide memory info
        system_memory = psutil.virtual_memory()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "current_process": asdict(current_snapshot),
            "system_memory": {
                "total_gb": system_memory.total / 1024 / 1024 / 1024,
                "available_gb": system_memory.available / 1024 / 1024 / 1024,
                "used_percent": system_memory.percent,
                "free_gb": system_memory.free / 1024 / 1024 / 1024
            },
            "memory_thresholds": {
                "max_growth_per_1000_ops_mb": self.MAX_MEMORY_GROWTH_PER_1000_OPS_MB,
                "max_baseline_mb": self.MAX_BASELINE_MEMORY_MB,
                "leak_threshold_kb": self.MAX_MEMORY_LEAK_THRESHOLD_KB
            },
            "resource_limits": {
                "cpu_warning_threshold": self.CPU_USAGE_WARNING_THRESHOLD,
                "memory_warning_threshold": self.MEMORY_USAGE_WARNING_THRESHOLD
            },
            "recommendations": self._generate_memory_recommendations(current_snapshot)
        }
        
        return report
    
    def _generate_memory_recommendations(self, snapshot: ResourceUsageSnapshot) -> List[str]:
        """Generate memory optimization recommendations"""
        recommendations = []
        
        if snapshot.memory_rss_mb > 150:
            recommendations.append(
                "HIGH: Memory usage above 150MB. Consider implementing memory optimization strategies."
            )
        
        if snapshot.gc_objects > 100000:
            recommendations.append(
                "MEDIUM: High number of GC objects. Review object lifecycle management."
            )
        
        if snapshot.threads > 20:
            recommendations.append(
                "MEDIUM: High thread count. Review thread pool configuration."
            )
        
        if snapshot.open_files > 100:
            recommendations.append(
                "MEDIUM: High open file count. Ensure proper file handle cleanup."
            )
        
        if not recommendations:
            recommendations.append(
                "EXCELLENT: Memory and resource usage within optimal ranges."
            )
        else:
            recommendations.extend([
                "Consider implementing memory pooling for frequently allocated objects",
                "Use weak references for cache entries to allow garbage collection",
                "Implement periodic memory cleanup routines",
                "Monitor memory usage in production with alerts"
            ])
        
        return recommendations


if __name__ == "__main__":
    # Run memory and resource monitoring tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])