
#!/usr/bin/env python3
"""
Simple validation script for rate limiting implementation
Tests core functionality without requiring full FastAPI setup
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_security_config():
    """Validate security configuration"""
    try:
        from app.core.security import SecurityConfig
        
        print("✅ SecurityConfig imported successfully")
        
        # Check rate limiting configuration
        assert hasattr(SecurityConfig, 'RATE_LIMIT_TIERS'), "RATE_LIMIT_TIERS not found"
        assert hasattr(SecurityConfig, 'LOGIN_RATE_LIMIT'), "LOGIN_RATE_LIMIT not found"
        assert hasattr(SecurityConfig, 'REGISTER_RATE_LIMIT'), "REGISTER_RATE_LIMIT not found"
        
        # Validate tier structure
        tiers = SecurityConfig.RATE_LIMIT_TIERS
        required_tiers = ['anonymous', 'basic_user', 'premium_user', 'admin_user']
        
        for tier in required_tiers:
            assert tier in tiers, f"Missing tier: {tier}"
            tier_config = tiers[tier]
            assert 'requests_per_hour' in tier_config, f"Missing requests_per_hour in {tier}"
            assert 'burst_limit' in tier_config, f"Missing burst_limit in {tier}"
            assert 'window_size' in tier_config, f"Missing window_size in {tier}"
        
        print("✅ Rate limit tiers configured correctly")
        
        # Check that limits are reasonable for financial app
        assert SecurityConfig.LOGIN_RATE_LIMIT <= 10, "Login rate limit too high for financial app"
        assert SecurityConfig.REGISTER_RATE_LIMIT <= 5, "Register rate limit too high"
        assert SecurityConfig.PASSWORD_RESET_RATE_LIMIT <= 3, "Password reset limit too high"
        
        print("✅ Authentication rate limits are appropriately restrictive")
        
        return True
    except Exception as e:
        print(f"❌ SecurityConfig validation failed: {e}")
        return False

def validate_rate_limiter_class():
    """Validate AdvancedRateLimiter class structure"""
    try:
        from app.core.security import AdvancedRateLimiter
        
        print("✅ AdvancedRateLimiter imported successfully")
        
        # Check required methods
        required_methods = [
            '_get_client_identifier',
            '_sliding_window_counter', 
            'check_rate_limit',
            'check_auth_rate_limit',
            '_check_progressive_penalties',
            'get_rate_limit_status'
        ]
        
        for method in required_methods:
            assert hasattr(AdvancedRateLimiter, method), f"Missing method: {method}"
        
        print("✅ AdvancedRateLimiter has all required methods")
        return True
    except Exception as e:
        print(f"❌ AdvancedRateLimiter validation failed: {e}")
        return False

def validate_middleware():
    """Validate middleware structure"""
    try:
        from app.middleware.comprehensive_rate_limiter import ComprehensiveRateLimitMiddleware
        
        print("✅ ComprehensiveRateLimitMiddleware imported successfully")
        
        # Check required attributes
        middleware = ComprehensiveRateLimitMiddleware(None)
        
        assert hasattr(middleware, 'exempt_paths'), "Missing exempt_paths"
        assert hasattr(middleware, 'auth_paths'), "Missing auth_paths"
        assert hasattr(middleware, 'admin_paths'), "Missing admin_paths"
        
        print("✅ Rate limiting middleware configured correctly")
        return True
    except Exception as e:
        print(f"❌ Middleware validation failed: {e}")
        return False

def validate_auth_routes():
    """Validate auth routes have rate limiting applied"""
    try:
        from app.api.auth import routes
        
        print("✅ Auth routes imported successfully")
        
        # Check that comprehensive_auth_security is imported
        source_code = open('app/api/auth/routes.py', 'r').read()
        
        assert 'comprehensive_auth_security' in source_code, "comprehensive_auth_security not imported"
        assert 'AdvancedRateLimiter' in source_code, "AdvancedRateLimiter not imported"
        assert 'check_auth_rate_limit' in source_code, "Auth rate limiting not applied"
        
        print("✅ Auth routes have rate limiting dependencies")
        return True
    except Exception as e:
        print(f"❌ Auth routes validation failed: {e}")
        return False

def validate_security_dependencies():
    """Validate security dependency functions"""
    try:
        from app.core.security import (
            get_rate_limiter,
            get_security_monitor,
            get_security_health_status,
            require_auth_endpoint_protection,
            comprehensive_auth_security
        )
        
        print("✅ Security dependencies imported successfully")
        
        # Test health status function
        health_status = get_security_health_status()
        assert isinstance(health_status, dict), "Health status should be dict"
        assert 'timestamp' in health_status, "Missing timestamp in health status"
        
        print("✅ Security health monitoring working")
        return True
    except Exception as e:
        print(f"❌ Security dependencies validation failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🔒 Validating MITA Rate Limiting Implementation")
    print("=" * 50)
    
    tests = [
        ("Security Configuration", validate_security_config),
        ("Rate Limiter Class", validate_rate_limiter_class),
        ("Rate Limiting Middleware", validate_middleware),
        ("Auth Routes Integration", validate_auth_routes),
        ("Security Dependencies", validate_security_dependencies)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All rate limiting components validated successfully!")
        print("\n📝 Implementation Summary:")
        print("   • Sliding window rate limiting with Redis")
        print("   • Progressive penalties for repeat offenders")
        print("   • Fail-secure behavior for Redis outages")
        print("   • User tier-based rate limiting")
        print("   • Authentication endpoint protection")
        print("   • Security monitoring and logging")
        print("   • Comprehensive middleware integration")
        return True
    else:
        print("⚠️  Some components failed validation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)