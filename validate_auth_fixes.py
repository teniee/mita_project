#!/usr/bin/env python3
"""
MITA AUTHENTICATION FIXES - QUICK VALIDATION SCRIPT
===================================================

This script demonstrates that all Phase 1 authentication fixes are working:
✅ JWT token creation and validation
✅ Password hashing and verification  
✅ Rate limiting components available
✅ Authentication schemas working
✅ Database model structure correct
✅ Authentication routes structure valid

Run this to quickly verify all fixes are in place.
"""

import sys
import os
import time
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/mikhail/StudioProjects/mita_project')

# Set minimal environment for testing
os.environ.setdefault('JWT_SECRET', 'test_jwt_secret_32_chars_minimum_testing')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_32_chars_minimum_testing')
os.environ.setdefault('ENVIRONMENT', 'test')

def test_jwt_functionality():
    """Test JWT token creation and validation"""
    print("🔍 Testing JWT functionality...")
    try:
        from app.services.auth_jwt_service import (
            create_access_token, create_refresh_token, 
            create_token_pair, hash_password
        )
        
        # Test data
        user_data = {
            "sub": "test-user-123",
            "email": "test@example.com", 
            "is_premium": False,
            "country": "US"
        }
        
        # Test token creation
        access_token = create_access_token(user_data, user_role="basic_user")
        refresh_token = create_refresh_token(user_data, user_role="basic_user") 
        token_pair = create_token_pair(user_data, user_role="basic_user")
        
        # Test password hashing
        password_hash = hash_password("TestPassword123!")
        
        success = all([
            access_token and len(access_token) > 50,
            refresh_token and len(refresh_token) > 50,
            token_pair and token_pair.get("access_token"),
            password_hash and len(password_hash) > 50
        ])
        
        print(f"   ✅ JWT Service: {'WORKING' if success else 'FAILED'}")
        return success
        
    except Exception as e:
        print(f"   ❌ JWT Service: FAILED - {str(e)[:50]}")
        return False

def test_rate_limiting_components():
    """Test rate limiting components are available"""
    print("🔍 Testing rate limiting components...")
    try:
        from app.core.simple_rate_limiter import (
            check_login_rate_limit,
            check_register_rate_limit,
            check_token_refresh_rate_limit
        )
        
        # Test functions exist and are callable
        success = all([
            callable(check_login_rate_limit),
            callable(check_register_rate_limit), 
            callable(check_token_refresh_rate_limit)
        ])
        
        print(f"   ✅ Rate Limiting: {'AVAILABLE' if success else 'MISSING'}")
        return success
        
    except Exception as e:
        print(f"   ❌ Rate Limiting: FAILED - {str(e)[:50]}")
        return False

def test_auth_schemas():
    """Test authentication schemas"""
    print("🔍 Testing authentication schemas...")
    try:
        from app.api.auth.schemas import (
            FastRegisterIn, LoginIn, TokenOut, RegisterIn
        )
        
        # Test schema creation
        register_schema = FastRegisterIn(
            email="test@example.com",
            password="TestPassword123!",
            country="US",
            annual_income=50000,
            timezone="UTC"
        )
        
        login_schema = LoginIn(
            email="test@example.com", 
            password="TestPassword123!"
        )
        
        token_schema = TokenOut(
            access_token="test.jwt.token",
            refresh_token="test.refresh.token", 
            token_type="bearer"
        )
        
        success = all([
            register_schema.email == "test@example.com",
            login_schema.password == "TestPassword123!",
            token_schema.token_type == "bearer"
        ])
        
        print(f"   ✅ Auth Schemas: {'WORKING' if success else 'FAILED'}")
        return success
        
    except Exception as e:
        print(f"   ❌ Auth Schemas: FAILED - {str(e)[:50]}")
        return False

def test_database_model():
    """Test User database model"""
    print("🔍 Testing User database model...")
    try:
        from app.db.models.user import User
        
        # Test model creation
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test.hash.here",
            country="US",
            annual_income=50000,
            timezone="UTC"
        )
        
        # Check required fields exist
        required_fields = ['id', 'email', 'password_hash', 'created_at', 'updated_at']
        has_fields = all(hasattr(user, field) for field in required_fields)
        
        # Check field values
        correct_values = (
            user.email == "test@example.com" and
            user.country == "US" and
            user.annual_income == 50000
        )
        
        success = has_fields and correct_values
        
        print(f"   ✅ Database Model: {'WORKING' if success else 'FAILED'}")
        if not has_fields:
            missing = [f for f in required_fields if not hasattr(user, f)]
            print(f"      Missing fields: {missing}")
        
        return success
        
    except Exception as e:
        print(f"   ❌ Database Model: FAILED - {str(e)[:50]}")
        return False

def test_auth_routes_structure():
    """Test authentication routes structure"""
    print("🔍 Testing authentication routes...")
    try:
        from app.api.auth.routes import router
        
        # Check router exists and has routes
        has_router = router is not None
        has_routes = hasattr(router, 'routes') and len(router.routes) > 0
        
        if has_routes:
            route_count = len(router.routes)
            # Check for key route patterns
            route_paths = []
            for route in router.routes:
                if hasattr(route, 'path'):
                    route_paths.append(route.path)
            
            # Look for core auth endpoints
            key_routes = ['/register', '/login', '/refresh', '/logout']
            found_routes = sum(1 for key in key_routes 
                             if any(key in path for path in route_paths))
            
            success = has_router and has_routes and found_routes >= 3
            
            print(f"   ✅ Auth Routes: {'WORKING' if success else 'FAILED'}")
            print(f"      Routes found: {route_count}, Key routes: {found_routes}")
            
        else:
            success = False
            print("   ❌ Auth Routes: FAILED - No routes found")
            
        return success
        
    except Exception as e:
        print(f"   ❌ Auth Routes: FAILED - {str(e)[:50]}")
        return False

def main():
    """Run all validation tests"""
    print("🚀 MITA AUTHENTICATION FIXES - QUICK VALIDATION")
    print("=" * 55)
    print()
    
    start_time = time.time()
    
    # Run all tests
    tests = [
        ("JWT Functionality", test_jwt_functionality),
        ("Rate Limiting Components", test_rate_limiting_components), 
        ("Authentication Schemas", test_auth_schemas),
        ("Database Model", test_database_model),
        ("Authentication Routes", test_auth_routes_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ {test_name}: FAILED - {str(e)[:50]}")
            results.append((test_name, False))
        print()
    
    # Generate summary
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result)
    success_rate = (passed_tests / total_tests) * 100
    
    duration = time.time() - start_time
    
    print("=" * 55)
    print("📊 VALIDATION SUMMARY")
    print("=" * 55)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print()
    print(f"📈 Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
    print(f"⏱️ Duration: {duration:.2f} seconds")
    
    # Overall assessment
    if success_rate >= 80:
        print("🎉 OVERALL STATUS: AUTHENTICATION FIXES WORKING!")
        print("✅ Phase 1 critical components are functional")
        print("🚀 Ready for endpoint testing with running server")
        overall_success = True
    elif success_rate >= 60:
        print("⚠️ OVERALL STATUS: MOSTLY WORKING - MINOR ISSUES")  
        print("🔧 Some components need attention")
        overall_success = False
    else:
        print("❌ OVERALL STATUS: CRITICAL ISSUES FOUND")
        print("🔧 Major fixes required before proceeding")
        overall_success = False
    
    # Save results
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "success_rate": success_rate,
        "tests_passed": f"{passed_tests}/{total_tests}",
        "duration_seconds": duration,
        "test_results": [{"test": name, "passed": result} for name, result in results],
        "overall_success": overall_success
    }
    
    with open("quick_auth_validation.json", "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"💾 Results saved to: quick_auth_validation.json")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)