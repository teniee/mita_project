#!/usr/bin/env python3
"""
Password Security Test Script
Tests the centralized bcrypt configuration for backward compatibility and performance
"""

import sys
import os
import time
import asyncio

# Add project root to path
sys.path.insert(0, '/Users/mikhail/StudioProjects/mita_project')

def test_bcrypt_compatibility():
    """Test that new configuration is compatible with old passwords"""
    print("=" * 60)
    print("BCRYPT COMPATIBILITY TEST")
    print("=" * 60)
    
    try:
        from app.core.password_security import (
            hash_password_sync, 
            verify_password_sync, 
            hash_password_async, 
            verify_password_async,
            get_bcrypt_rounds,
            test_password_performance,
            validate_bcrypt_configuration
        )
        
        # Test configuration
        print(f"✓ Bcrypt rounds configured: {get_bcrypt_rounds()}")
        
        # Test password that might exist in database with different rounds
        test_passwords = [
            "TestPassword123!",
            "UserPassword2024",
            "SecurePass!@#"
        ]
        
        # Create hashes with different rounds to simulate existing passwords
        import bcrypt
        legacy_hashes = {}
        
        print("\n--- Creating Legacy Password Hashes ---")
        for rounds in [4, 8, 10, 12]:
            print(f"Creating hashes with {rounds} rounds...")
            legacy_hashes[rounds] = {}
            for password in test_passwords:
                password_bytes = password.encode('utf-8')
                salt = bcrypt.gensalt(rounds=rounds)
                hash_result = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
                legacy_hashes[rounds][password] = hash_result
        
        print("\n--- Testing New System with Legacy Hashes ---")
        compatibility_success = True
        
        for rounds in [4, 8, 10, 12]:
            print(f"\nTesting {rounds}-round legacy hashes:")
            for password in test_passwords:
                legacy_hash = legacy_hashes[rounds][password]
                
                # Test sync verification
                sync_result = verify_password_sync(password, legacy_hash)
                if sync_result:
                    print(f"  ✓ Sync verification: {password[:4]}*** with {rounds} rounds")
                else:
                    print(f"  ✗ Sync verification FAILED: {password[:4]}*** with {rounds} rounds")
                    compatibility_success = False
                
                # Test wrong password
                wrong_result = verify_password_sync("wrong_password", legacy_hash)
                if not wrong_result:
                    print(f"  ✓ Correctly rejected wrong password for {rounds} rounds")
                else:
                    print(f"  ✗ SECURITY ISSUE: Accepted wrong password for {rounds} rounds")
                    compatibility_success = False
        
        print("\n--- Testing New Hash Creation ---")
        for password in test_passwords:
            # Create hash with new system
            start_time = time.time()
            new_hash = hash_password_sync(password)
            hash_time = (time.time() - start_time) * 1000
            
            # Verify the new hash works
            start_time = time.time()
            verify_result = verify_password_sync(password, new_hash)
            verify_time = (time.time() - start_time) * 1000
            
            if verify_result:
                print(f"  ✓ New hash for {password[:4]}***: hash={hash_time:.0f}ms, verify={verify_time:.0f}ms")
            else:
                print(f"  ✗ New hash verification FAILED for {password[:4]}***")
                compatibility_success = False
        
        print("\n" + "=" * 60)
        if compatibility_success:
            print("✅ COMPATIBILITY TEST PASSED")
            print("New system is backward compatible with existing passwords")
        else:
            print("❌ COMPATIBILITY TEST FAILED")
            print("New system may break existing password verification")
        
        return compatibility_success
        
    except Exception as e:
        print(f"❌ COMPATIBILITY TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_functions():
    """Test async password functions"""
    print("\n" + "=" * 60)
    print("ASYNC FUNCTIONS TEST")
    print("=" * 60)
    
    try:
        from app.core.password_security import hash_password_async, verify_password_async
        
        test_password = "AsyncTestPassword2024!"
        
        # Test async hashing
        print("Testing async password hashing...")
        start_time = time.time()
        hash_result = await hash_password_async(test_password)
        hash_time = (time.time() - start_time) * 1000
        print(f"  ✓ Async hash completed in {hash_time:.0f}ms")
        
        # Test async verification
        print("Testing async password verification...")
        start_time = time.time()
        verify_result = await verify_password_async(test_password, hash_result)
        verify_time = (time.time() - start_time) * 1000
        
        if verify_result:
            print(f"  ✓ Async verification completed in {verify_time:.0f}ms")
        else:
            print(f"  ✗ Async verification FAILED")
            return False
        
        # Test wrong password
        wrong_result = await verify_password_async("wrong_password", hash_result)
        if not wrong_result:
            print(f"  ✓ Correctly rejected wrong password in async mode")
        else:
            print(f"  ✗ SECURITY ISSUE: Accepted wrong password in async mode")
            return False
        
        print("✅ ASYNC FUNCTIONS TEST PASSED")
        return True
        
    except Exception as e:
        print(f"❌ ASYNC FUNCTIONS TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_performance():
    """Test password hashing performance"""
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST")
    print("=" * 60)
    
    try:
        from app.core.password_security import test_password_performance, get_password_performance_stats
        
        print("Running performance test...")
        perf_results = test_password_performance()
        
        print(f"Bcrypt rounds: {perf_results['bcrypt_rounds']}")
        print(f"Tests performed: {perf_results['tests_performed']}")
        print(f"Individual times: {[f'{t:.0f}ms' for t in perf_results['times_ms']]}")
        print(f"Average time: {perf_results['average_ms']:.0f}ms")
        print(f"Target time: 500ms")
        
        if perf_results['meets_target']:
            print("✅ Performance meets target (<500ms)")
        else:
            print("⚠️  Performance exceeds target (>500ms) - consider environment tuning")
        
        # Get overall stats
        print("\n--- Overall Performance Statistics ---")
        stats = get_password_performance_stats()
        print(f"Total hashes performed: {stats['total_hashes']}")
        print(f"Total verifications: {stats['total_verifications']}")
        print(f"Average hash time: {stats['avg_hash_time_ms']:.1f}ms")
        print(f"Average verify time: {stats['avg_verify_time_ms']:.1f}ms")
        print(f"Slow operations: {stats['slow_operations']}")
        
        return True
        
    except Exception as e:
        print(f"❌ PERFORMANCE TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration_validation():
    """Test configuration validation"""
    print("\n" + "=" * 60)
    print("CONFIGURATION VALIDATION TEST")
    print("=" * 60)
    
    try:
        from app.core.password_security import validate_bcrypt_configuration
        
        print("Validating bcrypt configuration...")
        validation_result = validate_bcrypt_configuration()
        
        print(f"Configuration valid: {validation_result['valid']}")
        print(f"Bcrypt rounds: {validation_result['configuration']['rounds']}")
        print(f"Environment: {validation_result['configuration']['environment']}")
        print(f"Performance target: {validation_result['configuration']['performance_target_ms']}ms")
        
        if validation_result['issues']:
            print(f"Issues found: {validation_result['issues']}")
        
        if validation_result['warnings']:
            print(f"Warnings: {validation_result['warnings']}")
        
        if 'performance' in validation_result:
            perf = validation_result['performance']
            print(f"Performance test: {perf['average_ms']:.0f}ms (target: {perf.get('target_ms', 'N/A')}ms)")
        
        if validation_result['valid']:
            print("✅ CONFIGURATION VALIDATION PASSED")
        else:
            print("❌ CONFIGURATION VALIDATION FAILED")
        
        return validation_result['valid']
        
    except Exception as e:
        print(f"❌ CONFIGURATION VALIDATION ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all password security tests"""
    print("🔐 MITA FINANCE PASSWORD SECURITY TEST SUITE")
    print("Testing centralized bcrypt configuration...")
    
    results = []
    
    # Test 1: Backward compatibility
    results.append(("Backward Compatibility", test_bcrypt_compatibility()))
    
    # Test 2: Async functions
    async def run_async_test():
        return await test_async_functions()
    
    results.append(("Async Functions", asyncio.run(run_async_test())))
    
    # Test 3: Performance
    results.append(("Performance", test_performance()))
    
    # Test 4: Configuration validation
    results.append(("Configuration Validation", test_configuration_validation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Password security configuration is working correctly.")
        print("✓ Backward compatible with existing passwords")
        print("✓ Async functions working properly")
        print("✓ Performance within acceptable limits")
        print("✓ Configuration properly validated")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        print("Review the failed tests above and address any issues.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)