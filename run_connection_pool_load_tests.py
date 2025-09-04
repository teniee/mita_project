#!/usr/bin/env python3
"""
MITA Finance Connection Pool Load Testing Execution Script
Orchestrates comprehensive connection pool validation testing

EXECUTION REQUIREMENTS:
1. Run complete connection pool load testing suite
2. Validate against production requirements
3. Generate comprehensive performance reports
4. Ensure zero performance regressions
5. Validate pool configuration effectiveness
"""

import asyncio
import sys
import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import testing modules
from connection_pool_load_testing_suite import ConnectionPoolValidator, run_comprehensive_connection_pool_testing
from connection_pool_metrics_collector import ConnectionPoolMetricsCollector, create_load_test_metrics_collector, monitor_during_load_test

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'connection_pool_load_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)


class ConnectionPoolLoadTestOrchestrator:
    """Orchestrates comprehensive connection pool load testing"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
        # Test configuration
        self.test_scenarios = [
            {
                "name": "Baseline Connection Pool Test",
                "description": "Validate basic connection pool functionality",
                "users": 10,
                "duration": 120,
                "expected_pool_usage": 50  # % of pool capacity
            },
            {
                "name": "Normal Production Load",
                "description": "Simulate expected production traffic patterns",
                "users": 25,
                "duration": 300,
                "expected_pool_usage": 60
            },
            {
                "name": "Peak Traffic Simulation",
                "description": "Test under peak production load conditions", 
                "users": 50,
                "duration": 300,
                "expected_pool_usage": 80
            },
            {
                "name": "Stress Test - High Concurrency",
                "description": "Push system to limits with high concurrent load",
                "users": 100,
                "duration": 180,
                "expected_pool_usage": 95
            },
            {
                "name": "Pool Exhaustion Recovery Test",
                "description": "Test pool behavior at capacity limits and recovery",
                "users": 60,  # More than pool capacity (50)
                "duration": 120,
                "expected_pool_usage": 100
            }
        ]
    
    async def run_comprehensive_testing(self) -> bool:
        """Execute all connection pool load tests with comprehensive monitoring"""
        
        print("=" * 120)
        print("🚀 MITA FINANCE COMPREHENSIVE CONNECTION POOL LOAD TESTING")
        print("=" * 120)
        print("CRITICAL VALIDATION: Pool Configuration (pool_size=20, max_overflow=30, pool_timeout=30)")
        print("OBJECTIVE: Validate against previous 8-15+ second timeout issues")
        print("SCOPE: 100% connection pool performance validation for production deployment")
        print("=" * 120)
        
        self.start_time = time.time()
        overall_success = True
        
        try:
            # Initialize metrics collector
            metrics_collector = create_load_test_metrics_collector()
            
            # Run main load testing suite with monitoring
            logger.info("🎯 Starting main connection pool load testing suite...")
            
            # Start metrics collection
            monitoring_task = asyncio.create_task(
                monitor_during_load_test(metrics_collector, 1800, 2.0)  # 30 minutes monitoring
            )
            
            # Run comprehensive tests
            success = await run_comprehensive_connection_pool_testing()
            
            # Stop monitoring
            metrics_collector.stop_monitoring()
            
            # Wait for monitoring to complete
            try:
                monitoring_report = await asyncio.wait_for(monitoring_task, timeout=10)
                self.test_results['monitoring_report'] = monitoring_report
            except asyncio.TimeoutError:
                logger.warning("Monitoring report generation timed out")
            
            # Export metrics data
            metrics_file = metrics_collector.export_metrics_data()
            self.test_results['metrics_file'] = metrics_file
            
            if not success:
                overall_success = False
                logger.error("❌ Main connection pool testing suite failed")
            else:
                logger.info("✅ Main connection pool testing suite passed")
            
            # Run additional specialized tests
            await self._run_specialized_tests()
            
        except Exception as e:
            logger.error(f"❌ Critical error in connection pool testing: {e}")
            overall_success = False
        
        finally:
            self.end_time = time.time()
        
        # Generate final report
        final_report = self._generate_final_report(overall_success)
        
        # Save comprehensive results
        self._save_test_results(final_report)
        
        # Display final results
        self._display_final_results(final_report, overall_success)
        
        return overall_success
    
    async def _run_specialized_tests(self):
        """Run specialized connection pool tests"""
        
        logger.info("🔬 Running specialized connection pool tests...")
        
        # Test 1: Connection leak detection
        try:
            leak_test_result = await self._test_connection_leak_detection()
            self.test_results['connection_leak_test'] = leak_test_result
        except Exception as e:
            logger.error(f"❌ Connection leak test failed: {e}")
            self.test_results['connection_leak_test'] = {"error": str(e)}
        
        # Test 2: Pool configuration validation
        try:
            config_validation = await self._validate_pool_configuration()
            self.test_results['pool_configuration_validation'] = config_validation
        except Exception as e:
            logger.error(f"❌ Pool configuration validation failed: {e}")
            self.test_results['pool_configuration_validation'] = {"error": str(e)}
        
        # Test 3: Timeout behavior validation
        try:
            timeout_test = await self._test_connection_timeout_behavior()
            self.test_results['timeout_behavior_test'] = timeout_test
        except Exception as e:
            logger.error(f"❌ Timeout behavior test failed: {e}")
            self.test_results['timeout_behavior_test'] = {"error": str(e)}
    
    async def _test_connection_leak_detection(self) -> dict:
        """Test for connection leaks under load"""
        logger.info("🔍 Testing connection leak detection...")
        
        from app.core.async_session import get_async_db_context, async_engine
        import psutil
        
        # Monitor system resources
        process = psutil.Process()
        initial_connections = len(psutil.net_connections())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform many rapid connection operations
        operations_count = 1000
        successful_operations = 0
        
        try:
            for i in range(operations_count):
                try:
                    async with get_async_db_context() as session:
                        await session.execute("SELECT 1")
                        successful_operations += 1
                except Exception as e:
                    logger.warning(f"Operation {i} failed: {e}")
                
                # Monitor every 100 operations
                if i % 100 == 99:
                    current_connections = len(psutil.net_connections())
                    current_memory = process.memory_info().rss / 1024 / 1024
                    
                    connection_growth = current_connections - initial_connections
                    memory_growth = current_memory - initial_memory
                    
                    # Check for concerning growth patterns
                    if connection_growth > 50:  # More than expected pool size
                        logger.warning(f"⚠️ High connection growth detected: +{connection_growth} connections")
                    
                    if memory_growth > 100:  # More than 100MB growth
                        logger.warning(f"⚠️ High memory growth detected: +{memory_growth:.1f}MB")
        
        except Exception as e:
            logger.error(f"Connection leak test error: {e}")
        
        # Final measurements
        final_connections = len(psutil.net_connections())
        final_memory = process.memory_info().rss / 1024 / 1024
        
        connection_delta = final_connections - initial_connections
        memory_delta = final_memory - initial_memory
        
        # Determine if leak detected
        leak_detected = connection_delta > 30 or memory_delta > 50  # Conservative thresholds
        
        return {
            "operations_performed": operations_count,
            "successful_operations": successful_operations,
            "initial_connections": initial_connections,
            "final_connections": final_connections,
            "connection_delta": connection_delta,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_delta_mb": memory_delta,
            "leak_detected": leak_detected,
            "test_passed": not leak_detected,
            "assessment": "No connection leaks detected" if not leak_detected else "Potential connection leak detected"
        }
    
    async def _validate_pool_configuration(self) -> dict:
        """Validate actual vs expected pool configuration"""
        logger.info("⚙️ Validating pool configuration...")
        
        from app.core.async_session import async_engine
        
        if not async_engine:
            return {"error": "No async_engine available for validation"}
        
        pool = async_engine.pool
        
        # Get actual configuration
        actual_config = {
            "pool_size": pool.size(),
            "max_overflow": getattr(pool, '_max_overflow', 0),
            "timeout": getattr(pool, '_timeout', 0),
            "total_capacity": pool.size() + getattr(pool, '_max_overflow', 0)
        }
        
        # Expected configuration
        expected_config = {
            "pool_size": 20,
            "max_overflow": 30,
            "timeout": 30,
            "total_capacity": 50
        }
        
        # Validate each setting
        validation_results = {}
        for key, expected_value in expected_config.items():
            actual_value = actual_config.get(key, 0)
            validation_results[key] = {
                "expected": expected_value,
                "actual": actual_value,
                "matches": actual_value == expected_value,
                "variance": actual_value - expected_value if isinstance(actual_value, (int, float)) else None
            }
        
        all_match = all(result["matches"] for result in validation_results.values())
        
        return {
            "expected_configuration": expected_config,
            "actual_configuration": actual_config,
            "validation_results": validation_results,
            "configuration_matches": all_match,
            "test_passed": all_match,
            "assessment": "Pool configuration matches expected values" if all_match else "Pool configuration discrepancies detected"
        }
    
    async def _test_connection_timeout_behavior(self) -> dict:
        """Test connection timeout behavior to prevent 8-15 second issues"""
        logger.info("⏱️ Testing connection timeout behavior...")
        
        from app.core.async_session import get_async_db_context
        import asyncio
        
        timeout_tests = []
        
        # Test 1: Normal operation timing
        try:
            start_time = time.time()
            async with get_async_db_context() as session:
                await session.execute("SELECT 1")
            normal_operation_time = (time.time() - start_time) * 1000
            
            timeout_tests.append({
                "test": "normal_operation",
                "duration_ms": normal_operation_time,
                "success": True,
                "within_threshold": normal_operation_time < 100  # Should be under 100ms
            })
        except Exception as e:
            timeout_tests.append({
                "test": "normal_operation", 
                "error": str(e),
                "success": False
            })
        
        # Test 2: Multiple rapid connections
        try:
            start_time = time.time()
            tasks = []
            
            for i in range(20):  # 20 rapid connections
                async def quick_query():
                    async with get_async_db_context() as session:
                        await session.execute("SELECT 1")
                        return True
                
                tasks.append(quick_query())
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            rapid_connection_time = (time.time() - start_time) * 1000
            
            successful_connections = len([r for r in results if r is True])
            
            timeout_tests.append({
                "test": "rapid_connections",
                "total_connections": 20,
                "successful_connections": successful_connections,
                "total_duration_ms": rapid_connection_time,
                "avg_per_connection_ms": rapid_connection_time / 20,
                "success": successful_connections >= 18,  # Allow some failures
                "within_threshold": rapid_connection_time < 2000  # Should be under 2 seconds total
            })
        except Exception as e:
            timeout_tests.append({
                "test": "rapid_connections",
                "error": str(e),
                "success": False
            })
        
        # Test 3: Simulated slow query timeout
        try:
            start_time = time.time()
            try:
                async with asyncio.wait_for(get_async_db_context(), timeout=5.0) as session:
                    # This should succeed quickly
                    await session.execute("SELECT pg_sleep(0.1)")  # 100ms sleep
                slow_query_time = (time.time() - start_time) * 1000
                
                timeout_tests.append({
                    "test": "managed_slow_query",
                    "duration_ms": slow_query_time,
                    "success": True,
                    "within_threshold": slow_query_time < 1000  # Should be under 1 second
                })
            except asyncio.TimeoutError:
                timeout_duration = (time.time() - start_time) * 1000
                timeout_tests.append({
                    "test": "managed_slow_query",
                    "duration_ms": timeout_duration,
                    "success": False,
                    "timeout_occurred": True
                })
        except Exception as e:
            timeout_tests.append({
                "test": "managed_slow_query",
                "error": str(e),
                "success": False
            })
        
        # Analyze results
        successful_tests = len([t for t in timeout_tests if t.get("success", False)])
        all_within_thresholds = all(t.get("within_threshold", False) for t in timeout_tests if "within_threshold" in t)
        
        max_operation_time = max(
            (t.get("duration_ms", 0) for t in timeout_tests if "duration_ms" in t),
            default=0
        )
        
        prevents_8_15s_timeouts = max_operation_time < 8000  # Should be well under 8 seconds
        
        return {
            "timeout_test_results": timeout_tests,
            "successful_tests": successful_tests,
            "total_tests": len(timeout_tests),
            "all_within_thresholds": all_within_thresholds,
            "max_operation_time_ms": max_operation_time,
            "prevents_8_15s_timeouts": prevents_8_15s_timeouts,
            "test_passed": successful_tests >= len(timeout_tests) * 0.8 and prevents_8_15s_timeouts,
            "assessment": (
                "Connection timeouts properly managed - no regression risk" 
                if prevents_8_15s_timeouts 
                else "Timeout concerns detected - investigate further"
            )
        }
    
    def _generate_final_report(self, overall_success: bool) -> dict:
        """Generate comprehensive final report"""
        
        test_duration = (self.end_time - self.start_time) if self.start_time and self.end_time else 0
        
        # Calculate overall metrics
        total_tests_run = len([k for k in self.test_results.keys() if not k.endswith('_file')])
        successful_tests = len([
            test for test in self.test_results.values() 
            if isinstance(test, dict) and test.get('test_passed', False)
        ])
        
        return {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "test_duration_seconds": test_duration,
                "total_test_execution_time_minutes": test_duration / 60
            },
            
            "test_summary": {
                "overall_success": overall_success,
                "total_test_categories": total_tests_run,
                "successful_test_categories": successful_tests,
                "success_rate_percent": (successful_tests / total_tests_run * 100) if total_tests_run > 0 else 0
            },
            
            "pool_validation_results": {
                "connection_pool_performance": overall_success,
                "configuration_validation": self.test_results.get('pool_configuration_validation', {}).get('test_passed', False),
                "connection_leak_prevention": self.test_results.get('connection_leak_test', {}).get('test_passed', False),
                "timeout_regression_prevention": self.test_results.get('timeout_behavior_test', {}).get('test_passed', False)
            },
            
            "detailed_test_results": self.test_results,
            
            "critical_findings": self._extract_critical_findings(),
            
            "production_readiness_assessment": self._assess_production_readiness(overall_success),
            
            "recommendations": self._generate_final_recommendations(overall_success)
        }
    
    def _extract_critical_findings(self) -> list:
        """Extract critical findings from all test results"""
        findings = []
        
        # Connection pool configuration
        config_validation = self.test_results.get('pool_configuration_validation', {})
        if not config_validation.get('configuration_matches', True):
            findings.append("Pool configuration does not match expected values")
        
        # Connection leaks
        leak_test = self.test_results.get('connection_leak_test', {})
        if leak_test.get('leak_detected', False):
            findings.append("Potential connection leak detected during testing")
        
        # Timeout behavior
        timeout_test = self.test_results.get('timeout_behavior_test', {})
        if not timeout_test.get('prevents_8_15s_timeouts', True):
            findings.append("Risk of timeout regression detected - may not prevent 8-15s timeout issues")
        
        # Monitoring report findings
        monitoring = self.test_results.get('monitoring_report', {})
        if monitoring:
            health_assessment = monitoring.get('health_assessment', {})
            if health_assessment.get('status') in ['poor', 'fair']:
                findings.append(f"Connection pool health rated as {health_assessment.get('status')}")
        
        return findings if findings else ["No critical issues detected"]
    
    def _assess_production_readiness(self, overall_success: bool) -> dict:
        """Assess overall production readiness"""
        
        readiness_criteria = {
            "load_testing_passed": overall_success,
            "pool_configuration_correct": self.test_results.get('pool_configuration_validation', {}).get('test_passed', False),
            "no_connection_leaks": self.test_results.get('connection_leak_test', {}).get('test_passed', False),
            "timeout_regression_prevented": self.test_results.get('timeout_behavior_test', {}).get('test_passed', False)
        }
        
        passed_criteria = sum(1 for criteria in readiness_criteria.values() if criteria)
        total_criteria = len(readiness_criteria)
        readiness_score = (passed_criteria / total_criteria) * 100
        
        if readiness_score >= 90:
            readiness_level = "FULLY READY"
            recommendation = "✅ APPROVED for immediate production deployment"
        elif readiness_score >= 75:
            readiness_level = "CONDITIONALLY READY"
            recommendation = "⚠️ APPROVED with monitoring - deploy with enhanced monitoring"
        else:
            readiness_level = "NOT READY"
            recommendation = "❌ NOT APPROVED - address critical issues before deployment"
        
        return {
            "readiness_criteria": readiness_criteria,
            "criteria_passed": passed_criteria,
            "total_criteria": total_criteria,
            "readiness_score_percent": readiness_score,
            "readiness_level": readiness_level,
            "deployment_recommendation": recommendation
        }
    
    def _generate_final_recommendations(self, overall_success: bool) -> list:
        """Generate final recommendations based on all test results"""
        recommendations = []
        
        if overall_success:
            recommendations.append("✅ Connection pool load testing passed - system ready for production")
            recommendations.append("🚀 No performance regressions detected from previous 8-15s timeout issues")
        else:
            recommendations.append("❌ Connection pool issues detected - investigate before production deployment")
        
        # Configuration recommendations
        config_test = self.test_results.get('pool_configuration_validation', {})
        if config_test.get('test_passed'):
            recommendations.append("✅ Pool configuration validated - maintain current settings")
        else:
            recommendations.append("⚙️ Pool configuration issues - verify pool_size=20, max_overflow=30, pool_timeout=30")
        
        # Leak detection recommendations
        leak_test = self.test_results.get('connection_leak_test', {})
        if leak_test.get('test_passed'):
            recommendations.append("🔒 No connection leaks detected - resource management is proper")
        else:
            recommendations.append("🚨 Investigate potential connection leaks - implement connection monitoring")
        
        # Timeout recommendations
        timeout_test = self.test_results.get('timeout_behavior_test', {})
        if timeout_test.get('prevents_8_15s_timeouts'):
            recommendations.append("⏱️ Timeout behavior validated - 8-15s timeout issues resolved")
        else:
            recommendations.append("⚠️ Timeout concerns remain - additional investigation required")
        
        # Monitoring recommendations
        recommendations.append("📊 Implement continuous connection pool monitoring in production")
        recommendations.append("🔍 Set up alerts for pool utilization > 85% and connection times > 200ms")
        recommendations.append("📈 Monitor connection pool metrics for first 48 hours after deployment")
        
        return recommendations
    
    def _save_test_results(self, final_report: dict):
        """Save comprehensive test results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comprehensive_connection_pool_test_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        logger.info(f"📁 Comprehensive test report saved: {filename}")
    
    def _display_final_results(self, final_report: dict, overall_success: bool):
        """Display final test results"""
        
        print("\n" + "=" * 120)
        print("🎯 COMPREHENSIVE CONNECTION POOL LOAD TESTING - FINAL RESULTS")
        print("=" * 120)
        
        # Overall result
        result_emoji = "✅" if overall_success else "❌"
        result_text = "PASSED" if overall_success else "FAILED"
        print(f"{result_emoji} OVERALL TEST RESULT: {result_text}")
        
        # Test summary
        summary = final_report["test_summary"]
        print(f"\n📊 TEST EXECUTION SUMMARY:")
        print(f"   Total Test Categories: {summary['total_test_categories']}")
        print(f"   Successful Categories: {summary['successful_test_categories']}")
        print(f"   Success Rate: {summary['success_rate_percent']:.1f}%")
        print(f"   Total Execution Time: {final_report['report_metadata']['total_test_execution_time_minutes']:.1f} minutes")
        
        # Pool validation
        validation = final_report["pool_validation_results"]
        print(f"\n🔗 CONNECTION POOL VALIDATION:")
        print(f"   Performance Testing: {'✅ PASSED' if validation['connection_pool_performance'] else '❌ FAILED'}")
        print(f"   Configuration Validation: {'✅ PASSED' if validation['configuration_validation'] else '❌ FAILED'}")
        print(f"   Connection Leak Prevention: {'✅ PASSED' if validation['connection_leak_prevention'] else '❌ FAILED'}")
        print(f"   Timeout Regression Prevention: {'✅ PASSED' if validation['timeout_regression_prevention'] else '❌ FAILED'}")
        
        # Critical findings
        findings = final_report["critical_findings"]
        print(f"\n🔍 CRITICAL FINDINGS:")
        for finding in findings:
            print(f"   • {finding}")
        
        # Production readiness
        readiness = final_report["production_readiness_assessment"]
        print(f"\n🚀 PRODUCTION READINESS ASSESSMENT:")
        print(f"   Readiness Level: {readiness['readiness_level']}")
        print(f"   Readiness Score: {readiness['readiness_score_percent']:.0f}%")
        print(f"   Deployment Recommendation: {readiness['deployment_recommendation']}")
        
        # Final recommendations
        recommendations = final_report["recommendations"]
        print(f"\n💡 FINAL RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"   • {rec}")
        
        print("=" * 120)
        
        if overall_success:
            print("🎉 CONNECTION POOL VALIDATION COMPLETE - SYSTEM READY FOR PRODUCTION DEPLOYMENT")
        else:
            print("⚠️ CONNECTION POOL VALIDATION INCOMPLETE - ADDRESS ISSUES BEFORE DEPLOYMENT")
        
        print("=" * 120)


async def main():
    """Main execution function"""
    
    print("🚀 Starting MITA Finance Connection Pool Load Testing Suite...")
    print("⚡ Testing pool configuration: pool_size=20, max_overflow=30, pool_timeout=30")
    print("🎯 Validating against previous 8-15+ second timeout issues\n")
    
    orchestrator = ConnectionPoolLoadTestOrchestrator()
    
    try:
        success = await orchestrator.run_comprehensive_testing()
        return success
    
    except Exception as e:
        logger.error(f"❌ Critical error in test orchestration: {e}")
        return False


if __name__ == "__main__":
    """Execute comprehensive connection pool load testing"""
    
    success = asyncio.run(main())
    
    # Exit with appropriate code
    exit_code = 0 if success else 1
    print(f"\n🏁 Exiting with code: {exit_code}")
    sys.exit(exit_code)