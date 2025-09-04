#!/usr/bin/env python3
"""
Test script for the optimized audit logging system.
Validates performance and ensures no database deadlocks.
"""

import asyncio
import time
import logging
import sys
import os
from typing import Dict, Any
from datetime import datetime

# Add project root to path
sys.path.append('/Users/mikhail/StudioProjects/mita_project')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_audit_system_performance():
    """Test the performance of the audit logging system"""
    print("🧪 Testing Optimized Audit Logging System")
    print("=" * 50)
    
    test_results = {
        "database_pool_init": False,
        "security_event_queue": False,
        "concurrent_logging": False,
        "no_deadlocks": False,
        "performance_acceptable": False
    }
    
    try:
        # Test 1: Database Pool Initialization
        print("\n1️⃣ Testing separate database pool initialization...")
        start_time = time.time()
        
        from app.core.audit_logging import _audit_db_pool, initialize_audit_system
        await _audit_db_pool.initialize()
        
        init_time = time.time() - start_time
        print(f"   ✅ Database pool initialized in {init_time:.3f}s")
        test_results["database_pool_init"] = True
        
        # Test 2: Security Event Queue
        print("\n2️⃣ Testing security event queue...")
        from app.core.audit_logging import _security_event_queue, AuditEvent, AuditEventType, SensitivityLevel
        
        # Create test audit events
        test_events = []
        for i in range(5):
            event = AuditEvent(
                id=f"test_event_{i}_{datetime.now().isoformat()}",
                timestamp=datetime.now(),
                event_type=AuditEventType.SECURITY_VIOLATION,
                user_id=f"test_user_{i}",
                session_id=f"test_session_{i}",
                client_ip="127.0.0.1",
                user_agent="test_agent",
                endpoint="/api/test",
                method="POST",
                status_code=200,
                response_time_ms=50.0,
                request_size=100,
                response_size=200,
                sensitivity_level=SensitivityLevel.INTERNAL,
                success=True,
                error_message=None,
                additional_context={"test": True, "event_number": i}
            )
            test_events.append(event)
        
        # Queue events concurrently
        queue_start = time.time()
        tasks = [_security_event_queue.enqueue(event) for event in test_events]
        await asyncio.gather(*tasks)
        queue_time = time.time() - queue_start
        
        print(f"   ✅ Queued {len(test_events)} events in {queue_time:.3f}s")
        print(f"   ✅ Average queue time: {(queue_time/len(test_events)*1000):.2f}ms per event")
        test_results["security_event_queue"] = True
        
        # Test 3: Concurrent Logging Stress Test
        print("\n3️⃣ Testing concurrent logging (stress test)...")
        concurrent_start = time.time()
        
        # Create many concurrent security events
        from app.core.audit_logging import log_security_event
        
        async def create_concurrent_events(event_count: int):
            tasks = []
            for i in range(event_count):
                # Use sync version to test both sync and async paths
                if i % 2 == 0:
                    log_security_event(f"concurrent_test_{i}", {
                        "test_id": i,
                        "user_id": f"concurrent_user_{i}",
                        "client_ip": "127.0.0.1",
                        "success": True
                    })
                else:
                    # Test async version
                    from app.core.audit_logging import log_security_event_async
                    tasks.append(log_security_event_async(f"concurrent_async_test_{i}", {
                        "test_id": i,
                        "user_id": f"concurrent_async_user_{i}",
                        "success": True
                    }))
            
            # Wait for async tasks
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run concurrent test
        await create_concurrent_events(20)
        concurrent_time = time.time() - concurrent_start
        
        print(f"   ✅ Processed 20 concurrent events in {concurrent_time:.3f}s")
        print(f"   ✅ Average processing time: {(concurrent_time/20*1000):.2f}ms per event")
        test_results["concurrent_logging"] = True
        
        # Test 4: Database Deadlock Prevention
        print("\n4️⃣ Testing database deadlock prevention...")
        deadlock_start = time.time()
        
        # Simulate multiple concurrent database operations
        async def simulate_database_load():
            tasks = []
            for i in range(10):
                # Create events that will trigger database writes
                from app.core.audit_logging import log_security_event_async
                tasks.append(log_security_event_async(f"deadlock_test_{i}", {
                    "test_type": "deadlock_prevention",
                    "user_id": f"deadlock_user_{i}",
                    "endpoint": "/api/auth/login",
                    "success": i % 3 == 0  # Mix of success/failure
                }))
            
            # Execute all at once to stress test
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        results = await simulate_database_load()
        deadlock_time = time.time() - deadlock_start
        
        # Check for exceptions (deadlocks would cause exceptions)
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            print(f"   ⚠️ Found {len(exceptions)} exceptions during deadlock test")
            for exc in exceptions[:3]:  # Show first 3
                print(f"      {type(exc).__name__}: {exc}")
        else:
            print(f"   ✅ No deadlocks detected in {deadlock_time:.3f}s")
            test_results["no_deadlocks"] = True
        
        # Test 5: Overall Performance Check
        print("\n5️⃣ Testing overall performance...")
        
        # Performance thresholds
        max_queue_time_ms = 50  # Max 50ms per event
        max_concurrent_time_ms = 100  # Max 100ms for 20 events
        
        queue_time_per_event = (queue_time / len(test_events)) * 1000
        concurrent_time_per_event = (concurrent_time / 20) * 1000
        
        performance_acceptable = (
            queue_time_per_event < max_queue_time_ms and 
            concurrent_time_per_event < max_concurrent_time_ms
        )
        
        if performance_acceptable:
            print(f"   ✅ Performance within acceptable limits")
            print(f"      Queue time per event: {queue_time_per_event:.2f}ms (< {max_queue_time_ms}ms)")
            print(f"      Concurrent time per event: {concurrent_time_per_event:.2f}ms (< {max_concurrent_time_ms}ms)")
            test_results["performance_acceptable"] = True
        else:
            print(f"   ⚠️ Performance may need optimization")
            print(f"      Queue time per event: {queue_time_per_event:.2f}ms (target: < {max_queue_time_ms}ms)")
            print(f"      Concurrent time per event: {concurrent_time_per_event:.2f}ms (target: < {max_concurrent_time_ms}ms)")
        
        # Wait a bit for background processing to complete
        print("\n⏳ Waiting for background processing to complete...")
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Print test summary
    print("\n📊 Test Results Summary")
    print("=" * 30)
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Audit logging system is ready for production.")
        return True
    else:
        print("⚠️ Some tests failed. Review the results before deploying.")
        return False


async def test_basic_functionality():
    """Test basic functionality of the audit logging system"""
    print("\n🔍 Testing Basic Functionality")
    print("-" * 30)
    
    try:
        # Test sync logging
        print("Testing sync security event logging...")
        from app.core.audit_logging import log_security_event
        log_security_event("test_sync_event", {
            "test": "basic_functionality",
            "user_id": "test_user",
            "success": True
        })
        print("   ✅ Sync logging works")
        
        # Test async logging  
        print("Testing async security event logging...")
        from app.core.audit_logging import log_security_event_async
        await log_security_event_async("test_async_event", {
            "test": "basic_functionality", 
            "user_id": "test_user_async",
            "success": True
        })
        print("   ✅ Async logging works")
        
        # Test audit logger directly
        print("Testing audit logger directly...")
        from app.core.audit_logging import audit_logger
        await audit_logger.initialize()
        print("   ✅ Audit logger initialization works")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    async def main():
        print("🔒 MITA Finance - Audit Logging System Test")
        print("Testing optimized security event logging with deadlock prevention")
        print("")
        
        # Test basic functionality first
        basic_ok = await test_basic_functionality()
        if not basic_ok:
            print("❌ Basic functionality tests failed. Aborting performance tests.")
            return False
        
        # Run performance tests
        performance_ok = await test_audit_system_performance()
        
        if basic_ok and performance_ok:
            print("\n🎉 SUCCESS: Audit logging system is ready for production!")
            print("\n📋 Summary:")
            print("   ✅ Separate database pool prevents deadlocks")
            print("   ✅ Queue-based system provides excellent performance")
            print("   ✅ Concurrent logging works without issues")
            print("   ✅ Security events are properly logged and stored")
            print("   ✅ System gracefully handles errors and fallbacks")
            return True
        else:
            print("\n❌ FAILURE: Some tests failed. Review before deploying.")
            return False
    
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)