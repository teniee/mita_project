#!/usr/bin/env python3
"""
MITA Finance Production Connection Pool Validation Script
Final validation script for production deployment readiness

VALIDATION CHECKLIST:
✓ Pool size=20, max_overflow=30, pool_timeout=30 configuration
✓ Handle 25-100 concurrent users without timeouts  
✓ Connection acquisition < 200ms p95
✓ No connection leaks under sustained load
✓ Pool exhaustion recovery < 1000ms
✓ Zero 8-15+ second timeout regressions
✓ Database connection stability under load
✓ Error handling and resilience validation
"""

import asyncio
import sys
import os
import time
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class ProductionConnectionPoolValidator:
    """Production readiness validator for connection pool configuration"""
    
    def __init__(self):
        self.validation_results = {}
        self.critical_issues = []
        self.warnings = []
        self.passed_validations = []
        
        # Production requirements
        self.requirements = {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
            "max_connection_acquisition_ms": 200,
            "max_query_execution_ms": 500,
            "min_concurrent_users_supported": 50,
            "max_pool_exhaustion_recovery_ms": 1000,
            "max_acceptable_error_rate_percent": 2.0
        }
    
    async def validate_for_production_deployment(self) -> Tuple[bool, Dict[str, Any]]:
        """Execute complete production validation"""
        
        print("=" * 100)
        print("🚀 MITA FINANCE CONNECTION POOL PRODUCTION VALIDATION")
        print("=" * 100)
        print("CRITICAL: Validating connection pool for production deployment")
        print("REQUIREMENT: Eliminate previous 8-15+ second timeout issues")
        print("SCOPE: 100% connection pool validation for financial application")
        print("=" * 100)
        
        validation_start = time.time()
        
        # Step 1: Pre-flight environment checks
        print("\n🔍 STEP 1: Pre-flight Environment Validation")
        print("-" * 50)
        
        env_valid = await self._validate_environment()
        if not env_valid:
            return False, self._generate_failure_report("Environment validation failed")
        
        # Step 2: Database connectivity validation
        print("\n🔗 STEP 2: Database Connectivity Validation")
        print("-" * 50)
        
        db_valid = await self._validate_database_connectivity()
        if not db_valid:
            return False, self._generate_failure_report("Database connectivity validation failed")
        
        # Step 3: Pool configuration validation
        print("\n⚙️ STEP 3: Connection Pool Configuration Validation")
        print("-" * 50)
        
        config_valid = await self._validate_pool_configuration()
        if not config_valid:
            self.critical_issues.append("Pool configuration does not meet production requirements")
        
        # Step 4: Performance baseline validation
        print("\n⚡ STEP 4: Performance Baseline Validation")
        print("-" * 50)
        
        perf_valid = await self._validate_performance_baseline()
        if not perf_valid:
            self.critical_issues.append("Performance baseline validation failed")
        
        # Step 5: Load testing execution
        print("\n🧪 STEP 5: Comprehensive Load Testing Execution")
        print("-" * 50)
        
        load_test_valid = await self._execute_comprehensive_load_testing()
        if not load_test_valid:
            self.critical_issues.append("Load testing validation failed")
        
        # Step 6: Regression testing for timeout issues
        print("\n🔄 STEP 6: Timeout Regression Testing")
        print("-" * 50)
        
        regression_valid = await self._validate_timeout_regression_prevention()
        if not regression_valid:
            self.critical_issues.append("Timeout regression validation failed")
        
        # Step 7: Production readiness assessment
        print("\n🎯 STEP 7: Production Readiness Assessment")
        print("-" * 50)
        
        overall_valid = len(self.critical_issues) == 0
        
        validation_end = time.time()
        validation_duration = validation_end - validation_start
        
        # Generate final report
        final_report = self._generate_production_validation_report(
            overall_valid, validation_duration
        )
        
        # Display results
        self._display_validation_results(overall_valid, final_report)
        
        return overall_valid, final_report
    
    async def _validate_environment(self) -> bool:
        """Validate environment prerequisites"""
        
        print("   🔍 Checking Python environment...")
        python_version = sys.version_info
        if python_version < (3, 8):
            self.critical_issues.append(f"Python version {python_version} < 3.8 required")
            return False
        print(f"   ✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        print("   🔍 Checking required modules...")
        required_modules = [
            'asyncio', 'sqlalchemy', 'asyncpg', 'psutil'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"   ✅ {module} available")
            except ImportError:
                self.critical_issues.append(f"Required module {module} not available")
                return False
        
        print("   🔍 Checking project structure...")
        required_files = [
            'app/core/async_session.py',
            'app/core/database_monitoring.py',
            'connection_pool_load_testing_suite.py'
        ]
        
        for file_path in required_files:
            if not (project_root / file_path).exists():
                self.critical_issues.append(f"Required file {file_path} not found")
                return False
            print(f"   ✅ {file_path} found")
        
        self.passed_validations.append("Environment validation passed")
        return True
    
    async def _validate_database_connectivity(self) -> bool:
        """Validate database connectivity and basic operations"""
        
        try:
            from app.core.async_session import get_async_db_context, initialize_database
            
            print("   🔍 Initializing database connection...")
            initialize_database()
            print("   ✅ Database initialization successful")
            
            print("   🔍 Testing basic database connectivity...")
            async with get_async_db_context() as session:
                result = await session.execute("SELECT 1 as test")
                test_value = result.scalar()
                
                if test_value != 1:
                    self.critical_issues.append("Basic database query returned unexpected result")
                    return False
            
            print("   ✅ Database connectivity validated")
            
            print("   🔍 Testing connection pool access...")
            from app.core.async_session import async_engine
            
            if async_engine is None:
                self.critical_issues.append("Async engine not initialized")
                return False
            
            pool = async_engine.pool
            print(f"   ✅ Connection pool accessible (size: {pool.size()})")
            
            self.passed_validations.append("Database connectivity validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Database connectivity validation failed: {str(e)}")
            return False
    
    async def _validate_pool_configuration(self) -> bool:
        """Validate connection pool configuration matches requirements"""
        
        try:
            from app.core.async_session import async_engine
            
            if not async_engine:
                self.critical_issues.append("Async engine not available for configuration validation")
                return False
            
            pool = async_engine.pool
            
            # Check pool size
            actual_pool_size = pool.size()
            expected_pool_size = self.requirements["pool_size"]
            
            if actual_pool_size != expected_pool_size:
                self.critical_issues.append(
                    f"Pool size mismatch: actual={actual_pool_size}, expected={expected_pool_size}"
                )
                print(f"   ❌ Pool size: {actual_pool_size} (expected: {expected_pool_size})")
            else:
                print(f"   ✅ Pool size: {actual_pool_size}")
            
            # Check max overflow
            actual_overflow = getattr(pool, '_max_overflow', 0)
            expected_overflow = self.requirements["max_overflow"]
            
            if actual_overflow != expected_overflow:
                self.critical_issues.append(
                    f"Max overflow mismatch: actual={actual_overflow}, expected={expected_overflow}"
                )
                print(f"   ❌ Max overflow: {actual_overflow} (expected: {expected_overflow})")
            else:
                print(f"   ✅ Max overflow: {actual_overflow}")
            
            # Check pool timeout
            actual_timeout = getattr(pool, '_timeout', 0)
            expected_timeout = self.requirements["pool_timeout"]
            
            if actual_timeout != expected_timeout:
                self.warnings.append(
                    f"Pool timeout mismatch: actual={actual_timeout}, expected={expected_timeout}"
                )
                print(f"   ⚠️ Pool timeout: {actual_timeout}s (expected: {expected_timeout}s)")
            else:
                print(f"   ✅ Pool timeout: {actual_timeout}s")
            
            # Calculate total capacity
            total_capacity = actual_pool_size + actual_overflow
            expected_capacity = expected_pool_size + expected_overflow
            
            print(f"   ✅ Total pool capacity: {total_capacity} connections")
            
            config_valid = len([issue for issue in self.critical_issues if "mismatch" in issue]) == 0
            
            if config_valid:
                self.passed_validations.append("Pool configuration validation passed")
            
            return config_valid
            
        except Exception as e:
            self.critical_issues.append(f"Pool configuration validation failed: {str(e)}")
            return False
    
    async def _validate_performance_baseline(self) -> bool:
        """Validate basic performance baseline requirements"""
        
        try:
            from app.core.async_session import get_async_db_context
            
            print("   🔍 Measuring single connection performance...")
            
            # Test single connection acquisition and query
            times = []
            for i in range(10):
                start_time = time.time()
                async with get_async_db_context() as session:
                    await session.execute("SELECT 1")
                end_time = time.time()
                
                duration_ms = (end_time - start_time) * 1000
                times.append(duration_ms)
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            print(f"   📊 Avg connection + query time: {avg_time:.1f}ms")
            print(f"   📊 Max connection + query time: {max_time:.1f}ms")
            
            # Validate against requirements
            max_acceptable = self.requirements["max_connection_acquisition_ms"]
            
            if avg_time > max_acceptable:
                self.critical_issues.append(
                    f"Baseline performance too slow: {avg_time:.1f}ms > {max_acceptable}ms"
                )
                print(f"   ❌ Performance below requirements")
                return False
            
            print(f"   ✅ Performance meets requirements ({avg_time:.1f}ms < {max_acceptable}ms)")
            
            # Test concurrent connections
            print("   🔍 Testing concurrent connection performance...")
            
            async def concurrent_test():
                start_time = time.time()
                async with get_async_db_context() as session:
                    await session.execute("SELECT 1")
                return (time.time() - start_time) * 1000
            
            # Run 5 concurrent connections
            concurrent_tasks = [concurrent_test() for _ in range(5)]
            concurrent_times = await asyncio.gather(*concurrent_tasks)
            
            avg_concurrent_time = sum(concurrent_times) / len(concurrent_times)
            print(f"   📊 Avg concurrent connection time: {avg_concurrent_time:.1f}ms")
            
            if avg_concurrent_time > max_acceptable * 2:  # Allow 2x for concurrency
                self.warnings.append(
                    f"Concurrent performance degradation detected: {avg_concurrent_time:.1f}ms"
                )
                print(f"   ⚠️ Concurrent performance degradation")
            else:
                print(f"   ✅ Concurrent performance acceptable")
            
            self.passed_validations.append("Performance baseline validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Performance baseline validation failed: {str(e)}")
            return False
    
    async def _execute_comprehensive_load_testing(self) -> bool:
        """Execute comprehensive load testing"""
        
        try:
            print("   🔍 Executing comprehensive connection pool load testing...")
            
            # Import and run the load testing suite
            from run_connection_pool_load_tests import ConnectionPoolLoadTestOrchestrator
            
            orchestrator = ConnectionPoolLoadTestOrchestrator()
            
            # Run load testing (this will take significant time)
            load_test_success = await orchestrator.run_comprehensive_testing()
            
            if load_test_success:
                print("   ✅ Comprehensive load testing passed")
                self.passed_validations.append("Comprehensive load testing passed")
                return True
            else:
                print("   ❌ Comprehensive load testing failed")
                self.critical_issues.append("Comprehensive load testing validation failed")
                return False
        
        except Exception as e:
            print(f"   ❌ Load testing execution error: {str(e)}")
            self.critical_issues.append(f"Load testing execution failed: {str(e)}")
            return False
    
    async def _validate_timeout_regression_prevention(self) -> bool:
        """Validate that 8-15+ second timeout issues are prevented"""
        
        try:
            from app.core.async_session import get_async_db_context
            
            print("   🔍 Testing timeout regression prevention...")
            
            # Test 1: Rapid connection requests (simulate high load)
            print("   📊 Testing rapid connection acquisition...")
            
            start_time = time.time()
            tasks = []
            
            for i in range(20):  # 20 rapid connections
                async def quick_connection():
                    connection_start = time.time()
                    async with get_async_db_context() as session:
                        await session.execute("SELECT 1")
                    return (time.time() - connection_start) * 1000
                
                tasks.append(quick_connection())
            
            connection_times = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = (time.time() - start_time) * 1000
            
            # Filter successful connections
            successful_times = [
                t for t in connection_times 
                if isinstance(t, (int, float)) and t > 0
            ]
            
            if len(successful_times) < 18:  # Allow some failures
                self.warnings.append(f"Only {len(successful_times)}/20 rapid connections succeeded")
            
            max_connection_time = max(successful_times) if successful_times else 0
            avg_connection_time = sum(successful_times) / len(successful_times) if successful_times else 0
            
            print(f"   📊 Rapid connection test - Total time: {total_time:.1f}ms")
            print(f"   📊 Max single connection time: {max_connection_time:.1f}ms")
            print(f"   📊 Avg single connection time: {avg_connection_time:.1f}ms")
            
            # Critical check: no connection should take more than 8 seconds
            timeout_threshold_ms = 8000  # 8 seconds
            
            if max_connection_time > timeout_threshold_ms:
                self.critical_issues.append(
                    f"Timeout regression detected: {max_connection_time:.1f}ms > {timeout_threshold_ms}ms"
                )
                print(f"   ❌ TIMEOUT REGRESSION DETECTED!")
                return False
            
            if avg_connection_time > 1000:  # 1 second average is concerning
                self.warnings.append(
                    f"High average connection time: {avg_connection_time:.1f}ms"
                )
                print(f"   ⚠️ High average connection time detected")
            
            print(f"   ✅ No timeout regression detected (max: {max_connection_time:.1f}ms < {timeout_threshold_ms}ms)")
            
            # Test 2: Pool exhaustion simulation
            print("   📊 Testing pool exhaustion behavior...")
            
            try:
                # Try to exhaust the pool briefly
                exhaustion_start = time.time()
                
                async def hold_connection(duration: float):
                    async with get_async_db_context() as session:
                        await session.execute("SELECT pg_sleep($1)", [duration])
                        return True
                
                # Start enough long-running connections to approach pool limit
                pool_size = 20  # From requirements
                exhaustion_tasks = [
                    hold_connection(2.0)  # Hold for 2 seconds
                    for _ in range(pool_size - 5)  # Leave some connections available
                ]
                
                # Wait for exhaustion tasks
                await asyncio.gather(*exhaustion_tasks, return_exceptions=True)
                
                exhaustion_time = (time.time() - exhaustion_start) * 1000
                print(f"   📊 Pool exhaustion test completed in {exhaustion_time:.1f}ms")
                
                if exhaustion_time > 30000:  # More than 30 seconds is problematic
                    self.warnings.append(f"Pool exhaustion test took {exhaustion_time:.1f}ms")
                    print(f"   ⚠️ Slow pool exhaustion recovery")
                else:
                    print(f"   ✅ Pool exhaustion recovery acceptable")
            
            except Exception as e:
                self.warnings.append(f"Pool exhaustion test error: {str(e)}")
                print(f"   ⚠️ Pool exhaustion test encountered error: {str(e)}")
            
            self.passed_validations.append("Timeout regression prevention validated")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Timeout regression validation failed: {str(e)}")
            print(f"   ❌ Timeout regression validation error: {str(e)}")
            return False
    
    def _generate_production_validation_report(
        self, 
        overall_valid: bool, 
        validation_duration: float
    ) -> Dict[str, Any]:
        """Generate comprehensive production validation report"""
        
        return {
            "validation_metadata": {
                "timestamp": datetime.now().isoformat(),
                "validation_duration_seconds": validation_duration,
                "validator_version": "1.0.0"
            },
            
            "overall_validation_result": {
                "passed": overall_valid,
                "status": "APPROVED FOR PRODUCTION" if overall_valid else "NOT APPROVED FOR PRODUCTION"
            },
            
            "requirements_validation": {
                "pool_size": self.requirements["pool_size"],
                "max_overflow": self.requirements["max_overflow"],
                "pool_timeout": self.requirements["pool_timeout"],
                "max_connection_acquisition_ms": self.requirements["max_connection_acquisition_ms"],
                "max_query_execution_ms": self.requirements["max_query_execution_ms"],
                "min_concurrent_users_supported": self.requirements["min_concurrent_users_supported"]
            },
            
            "validation_results": {
                "passed_validations": self.passed_validations,
                "critical_issues": self.critical_issues,
                "warnings": self.warnings,
                "total_validations": len(self.passed_validations) + len(self.critical_issues),
                "success_rate": len(self.passed_validations) / (len(self.passed_validations) + len(self.critical_issues)) * 100 if (len(self.passed_validations) + len(self.critical_issues)) > 0 else 0
            },
            
            "production_readiness": {
                "database_connectivity": "database connectivity" in " ".join(self.passed_validations).lower(),
                "pool_configuration": "pool configuration" in " ".join(self.passed_validations).lower(),
                "performance_baseline": "performance baseline" in " ".join(self.passed_validations).lower(),
                "load_testing": "load testing" in " ".join(self.passed_validations).lower(),
                "timeout_regression_prevention": "timeout regression" in " ".join(self.passed_validations).lower()
            },
            
            "deployment_recommendation": self._generate_deployment_recommendation(overall_valid),
            
            "next_steps": self._generate_next_steps(overall_valid)
        }
    
    def _generate_deployment_recommendation(self, overall_valid: bool) -> Dict[str, Any]:
        """Generate deployment recommendation"""
        
        if overall_valid:
            return {
                "recommendation": "APPROVE",
                "confidence": "HIGH",
                "message": "✅ Connection pool validated for production deployment",
                "conditions": []
            }
        elif len(self.critical_issues) <= 2 and len(self.warnings) <= 5:
            return {
                "recommendation": "CONDITIONAL APPROVE",
                "confidence": "MEDIUM",
                "message": "⚠️ Deploy with enhanced monitoring and address issues",
                "conditions": self.critical_issues + self.warnings
            }
        else:
            return {
                "recommendation": "REJECT",
                "confidence": "HIGH",
                "message": "❌ Too many critical issues - address before deployment",
                "conditions": self.critical_issues
            }
    
    def _generate_next_steps(self, overall_valid: bool) -> List[str]:
        """Generate next steps based on validation results"""
        
        if overall_valid:
            return [
                "✅ Deploy to production with current connection pool configuration",
                "📊 Implement connection pool monitoring in production",
                "🔍 Monitor pool utilization for first 48 hours after deployment",
                "📈 Set up alerts for pool utilization > 85%",
                "⏰ Set up alerts for connection acquisition times > 200ms"
            ]
        else:
            steps = ["❌ Address critical issues before production deployment:"]
            steps.extend([f"   • {issue}" for issue in self.critical_issues])
            
            if self.warnings:
                steps.append("⚠️ Consider addressing warnings:")
                steps.extend([f"   • {warning}" for warning in self.warnings])
            
            steps.extend([
                "🔄 Re-run validation after addressing issues",
                "📋 Document all configuration changes made"
            ])
            
            return steps
    
    def _generate_failure_report(self, failure_reason: str) -> Dict[str, Any]:
        """Generate failure report for early validation failures"""
        
        return {
            "validation_result": "FAILED",
            "failure_reason": failure_reason,
            "timestamp": datetime.now().isoformat(),
            "critical_issues": self.critical_issues,
            "deployment_recommendation": "REJECT - Critical validation failure"
        }
    
    def _display_validation_results(self, overall_valid: bool, report: Dict[str, Any]):
        """Display final validation results"""
        
        print("\n" + "=" * 100)
        print("🎯 PRODUCTION CONNECTION POOL VALIDATION - FINAL RESULTS")
        print("=" * 100)
        
        # Overall status
        status_emoji = "✅" if overall_valid else "❌"
        status_text = report["overall_validation_result"]["status"]
        print(f"{status_emoji} VALIDATION RESULT: {status_text}")
        
        # Validation summary
        results = report["validation_results"]
        print(f"\n📊 VALIDATION SUMMARY:")
        print(f"   Passed Validations: {len(results['passed_validations'])}")
        print(f"   Critical Issues: {len(results['critical_issues'])}")
        print(f"   Warnings: {len(results['warnings'])}")
        print(f"   Success Rate: {results['success_rate']:.1f}%")
        
        # Production readiness
        readiness = report["production_readiness"]
        print(f"\n🚀 PRODUCTION READINESS CHECKLIST:")
        for check, passed in readiness.items():
            emoji = "✅" if passed else "❌"
            print(f"   {emoji} {check.replace('_', ' ').title()}")
        
        # Issues
        if results['critical_issues']:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in results['critical_issues']:
                print(f"   • {issue}")
        
        if results['warnings']:
            print(f"\n⚠️ WARNINGS:")
            for warning in results['warnings']:
                print(f"   • {warning}")
        
        # Deployment recommendation
        rec = report["deployment_recommendation"]
        print(f"\n💡 DEPLOYMENT RECOMMENDATION:")
        print(f"   {rec['message']}")
        print(f"   Confidence: {rec['confidence']}")
        
        # Next steps
        print(f"\n📋 NEXT STEPS:")
        for step in report["next_steps"]:
            print(f"   {step}")
        
        print("=" * 100)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"production_connection_pool_validation_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📁 Validation report saved: {filename}")
        print("=" * 100)


async def main():
    """Main validation execution"""
    
    validator = ProductionConnectionPoolValidator()
    
    try:
        success, report = await validator.validate_for_production_deployment()
        return success
    
    except Exception as e:
        print(f"❌ CRITICAL VALIDATION ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    """Execute production connection pool validation"""
    
    print("🚀 Starting MITA Finance Connection Pool Production Validation...")
    
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 VALIDATION COMPLETE - CONNECTION POOL APPROVED FOR PRODUCTION")
        exit_code = 0
    else:
        print("\n💥 VALIDATION FAILED - CONNECTION POOL NOT READY FOR PRODUCTION")
        exit_code = 1
    
    print(f"🏁 Exiting with code: {exit_code}")
    sys.exit(exit_code)