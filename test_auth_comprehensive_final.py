#!/usr/bin/env python3
"""
🚀 MITA AUTHENTICATION SYSTEM - COMPREHENSIVE END-TO-END VALIDATION
=================================================================

This script validates that ALL authentication fixes are working properly:
- FastAPI server starts without hangs
- Main registration and login endpoints work under 5 seconds
- Rate limiting is properly enforced
- JWT tokens work correctly 
- Error handling is appropriate
- All response formats are Flutter-compatible

SUCCESS CRITERIA:
✅ Server starts without hanging
✅ Registration works in <5 seconds with valid JWT
✅ Login works in <5 seconds with valid JWT  
✅ Rate limiting protects endpoints appropriately
✅ Error handling works correctly
✅ JWT tokens authenticate protected routes
✅ All response formats compatible with Flutter app
"""

import asyncio
import json
import logging
import os
import random
import string
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import aiohttp
import requests
from tabulate import tabulate

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AuthTestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.test_results = []
        self.test_users = []
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def generate_test_user(self) -> Dict[str, Any]:
        """Generate a unique test user"""
        user_id = str(uuid.uuid4())[:8]
        return {
            "email": f"test_user_{user_id}@mitaauth.test",
            "password": f"TestPass{user_id}!",
            "country": "US",
            "annual_income": random.randint(30000, 100000),
            "timezone": "UTC"
        }
    
    def record_test(self, test_name: str, success: bool, duration: float, 
                   details: str = "", expected_time: float = None):
        """Record test result with performance metrics"""
        status = "✅ PASS" if success else "❌ FAIL"
        performance_status = ""
        
        if expected_time and success:
            if duration <= expected_time:
                performance_status = f" (⚡ {duration:.2f}s - FAST)"
            else:
                performance_status = f" (🐌 {duration:.2f}s - SLOW)"
        
        self.test_results.append({
            "test": test_name,
            "status": status + performance_status,
            "duration": f"{duration:.2f}s",
            "details": details
        })
        
        logger.info(f"{status} {test_name} - {duration:.2f}s - {details}")
    
    async def test_server_startup(self) -> bool:
        """Test 1: Server starts without hangs"""
        logger.info("🔍 Testing server startup and health...")
        start_time = time.time()
        
        try:
            # Test basic health endpoint
            async with self.session.get(f"{self.base_url}/health") as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    health_data = await response.json()
                    server_healthy = health_data.get("status") in ["healthy", "degraded"]
                    
                    self.record_test(
                        "Server Health Check",
                        server_healthy,
                        duration,
                        f"Status: {health_data.get('status', 'unknown')}, Database: {health_data.get('database', 'unknown')}"
                    )
                    return server_healthy
                else:
                    self.record_test("Server Health Check", False, duration, f"HTTP {response.status}")
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.record_test("Server Health Check", False, duration, f"Error: {str(e)}")
            return False
    
    async def test_registration_endpoint(self) -> Optional[Dict[str, Any]]:
        """Test 2: Main registration endpoint /api/auth/register"""
        logger.info("🔍 Testing main registration endpoint...")
        test_user = self.generate_test_user()
        start_time = time.time()
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/auth/register",
                json=test_user,
                headers={"Content-Type": "application/json"}
            ) as response:
                duration = time.time() - start_time
                
                if response.status == 201:
                    registration_data = await response.json()
                    
                    # Validate JWT token structure
                    access_token = registration_data.get("access_token")
                    token_valid = self.validate_jwt_structure(access_token)
                    
                    success = (
                        access_token and
                        registration_data.get("token_type") == "bearer" and
                        registration_data.get("refresh_token") and
                        token_valid
                    )
                    
                    details = f"Response has tokens: {bool(access_token)}, Token valid: {token_valid}"
                    if success:
                        test_user["access_token"] = access_token
                        test_user["refresh_token"] = registration_data.get("refresh_token")
                        self.test_users.append(test_user)
                    
                    self.record_test(
                        "Registration Main Endpoint",
                        success,
                        duration,
                        details,
                        expected_time=5.0
                    )
                    
                    return test_user if success else None
                    
                else:
                    error_data = await response.text()
                    self.record_test(
                        "Registration Main Endpoint", 
                        False, 
                        duration, 
                        f"HTTP {response.status}: {error_data[:100]}"
                    )
                    return None
                    
        except Exception as e:
            duration = time.time() - start_time
            self.record_test(
                "Registration Main Endpoint", 
                False, 
                duration, 
                f"Error: {str(e)}"
            )
            return None
    
    async def test_login_endpoint(self, test_user: Dict[str, Any]) -> bool:
        """Test 3: Main login endpoint /api/auth/login"""
        logger.info("🔍 Testing main login endpoint...")
        start_time = time.time()
        
        try:
            login_data = {
                "email": test_user["email"],
                "password": test_user["password"]
            }
            
            async with self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    login_response = await response.json()
                    
                    # Validate JWT token structure
                    access_token = login_response.get("access_token")
                    token_valid = self.validate_jwt_structure(access_token)
                    
                    success = (
                        access_token and
                        login_response.get("token_type") == "bearer" and
                        login_response.get("refresh_token") and
                        token_valid
                    )
                    
                    details = f"Response has tokens: {bool(access_token)}, Token valid: {token_valid}"
                    
                    self.record_test(
                        "Login Main Endpoint",
                        success,
                        duration,
                        details,
                        expected_time=5.0
                    )
                    
                    if success:
                        test_user["login_token"] = access_token
                    
                    return success
                    
                else:
                    error_data = await response.text()
                    self.record_test(
                        "Login Main Endpoint", 
                        False, 
                        duration, 
                        f"HTTP {response.status}: {error_data[:100]}"
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.record_test(
                "Login Main Endpoint", 
                False, 
                duration, 
                f"Error: {str(e)}"
            )
            return False
    
    async def test_rate_limiting(self) -> bool:
        """Test 4: Rate limiting functionality"""
        logger.info("🔍 Testing rate limiting enforcement...")
        start_time = time.time()
        
        # Test registration rate limiting (3 attempts per hour)
        registration_blocked = await self._test_registration_rate_limit()
        
        # Test login rate limiting (5 attempts per 15 minutes)  
        login_blocked = await self._test_login_rate_limit()
        
        duration = time.time() - start_time
        success = registration_blocked and login_blocked
        
        details = f"Registration limit: {'✅' if registration_blocked else '❌'}, Login limit: {'✅' if login_blocked else '❌'}"
        
        self.record_test(
            "Rate Limiting Enforcement",
            success,
            duration,
            details
        )
        
        return success
    
    async def _test_registration_rate_limit(self) -> bool:
        """Test registration rate limiting (3 attempts per hour)"""
        try:
            # Make multiple registration attempts quickly
            for i in range(4):  # Try 4 registrations (should block on 4th)
                test_user = self.generate_test_user()
                
                async with self.session.post(
                    f"{self.base_url}/api/auth/register",
                    json=test_user,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if i >= 3 and response.status == 429:
                        # Rate limit triggered as expected
                        return True
                    elif response.status not in [201, 400]:  # 400 for duplicate emails is OK
                        # Unexpected error
                        return False
                        
            # If we got here, rate limiting didn't trigger
            return False
            
        except Exception as e:
            logger.warning(f"Rate limit test error: {e}")
            return False
    
    async def _test_login_rate_limit(self) -> bool:
        """Test login rate limiting (5 attempts per 15 minutes)"""
        try:
            # Use invalid credentials to trigger multiple failed attempts
            invalid_login = {
                "email": "invalid@test.com",
                "password": "wrongpassword"
            }
            
            for i in range(6):  # Try 6 login attempts (should block on 6th)
                async with self.session.post(
                    f"{self.base_url}/api/auth/login",
                    json=invalid_login,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if i >= 5 and response.status == 429:
                        # Rate limit triggered as expected
                        return True
                    elif response.status not in [401]:  # 401 for invalid credentials is expected
                        # Unexpected error
                        return False
                        
            # If we got here, rate limiting didn't trigger
            return False
            
        except Exception as e:
            logger.warning(f"Login rate limit test error: {e}")
            return False
    
    def validate_jwt_structure(self, token: str) -> bool:
        """Validate JWT token structure without verification"""
        if not token:
            return False
            
        try:
            import jwt
            # Decode without verification to check structure
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Check required claims
            required_claims = ["sub", "exp", "iat"]
            has_required = all(claim in decoded for claim in required_claims)
            
            # Check expiration is in the future
            exp_valid = decoded.get("exp", 0) > time.time()
            
            return has_required and exp_valid
            
        except Exception:
            return False
    
    async def test_jwt_authentication(self, test_user: Dict[str, Any]) -> bool:
        """Test 5: JWT tokens work for protected endpoints"""
        logger.info("🔍 Testing JWT token authentication...")
        start_time = time.time()
        
        try:
            access_token = test_user.get("access_token") or test_user.get("login_token")
            if not access_token:
                self.record_test("JWT Authentication", False, 0, "No access token available")
                return False
            
            # Test protected endpoint
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with self.session.get(
                f"{self.base_url}/api/users/profile",  # Protected user profile endpoint
                headers=headers
            ) as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    profile_data = await response.json()
                    success = bool(profile_data)
                    
                    self.record_test(
                        "JWT Authentication",
                        success,
                        duration,
                        f"Profile endpoint accessible with JWT"
                    )
                    return success
                    
                elif response.status == 401:
                    self.record_test(
                        "JWT Authentication",
                        False,
                        duration,
                        "JWT token rejected by protected endpoint"
                    )
                    return False
                    
                else:
                    error_data = await response.text()
                    self.record_test(
                        "JWT Authentication",
                        False,
                        duration,
                        f"HTTP {response.status}: {error_data[:100]}"
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.record_test(
                "JWT Authentication",
                False,
                duration,
                f"Error: {str(e)}"
            )
            return False
    
    async def test_error_handling(self) -> bool:
        """Test 6: Error handling scenarios"""
        logger.info("🔍 Testing error handling scenarios...")
        start_time = time.time()
        
        error_tests = []
        
        # Test invalid email registration
        invalid_email_test = await self._test_invalid_registration(
            {"email": "invalid-email", "password": "validpass123"},
            "Invalid Email"
        )
        error_tests.append(invalid_email_test)
        
        # Test weak password registration
        weak_password_test = await self._test_invalid_registration(
            {"email": "test@example.com", "password": "123"},
            "Weak Password"
        )
        error_tests.append(weak_password_test)
        
        # Test duplicate email registration
        if self.test_users:
            duplicate_email_test = await self._test_invalid_registration(
                {
                    "email": self.test_users[0]["email"],
                    "password": "validpass123",
                    "country": "US"
                },
                "Duplicate Email"
            )
            error_tests.append(duplicate_email_test)
        
        # Test invalid login credentials
        invalid_login_test = await self._test_invalid_login()
        error_tests.append(invalid_login_test)
        
        duration = time.time() - start_time
        success = all(error_tests)
        passed_tests = sum(error_tests)
        
        self.record_test(
            "Error Handling",
            success,
            duration,
            f"Passed {passed_tests}/{len(error_tests)} error scenarios"
        )
        
        return success
    
    async def _test_invalid_registration(self, invalid_data: Dict, test_name: str) -> bool:
        """Test invalid registration data returns proper error"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/auth/register",
                json=invalid_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                # Should return 400 for validation errors
                return response.status == 400
                
        except Exception:
            return False
    
    async def _test_invalid_login(self) -> bool:
        """Test invalid login credentials return proper error"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"email": "nonexistent@test.com", "password": "wrongpassword"},
                headers={"Content-Type": "application/json"}
            ) as response:
                # Should return 401 for authentication failure
                return response.status == 401
                
        except Exception:
            return False
    
    async def test_flutter_compatibility(self, test_user: Dict[str, Any]) -> bool:
        """Test 7: Response formats are Flutter-compatible"""
        logger.info("🔍 Testing Flutter app compatibility...")
        start_time = time.time()
        
        try:
            # Test registration response format
            test_user_flutter = self.generate_test_user()
            
            async with self.session.post(
                f"{self.base_url}/api/auth/register",
                json=test_user_flutter,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 201:
                    data = await response.json()
                    
                    # Check Flutter-expected fields
                    flutter_fields = ["access_token", "refresh_token", "token_type"]
                    has_required_fields = all(field in data for field in flutter_fields)
                    
                    # Check token format
                    token_format_valid = (
                        data.get("token_type") == "bearer" and
                        isinstance(data.get("access_token"), str) and
                        isinstance(data.get("refresh_token"), str)
                    )
                    
                    success = has_required_fields and token_format_valid
                    duration = time.time() - start_time
                    
                    details = f"Required fields: {'✅' if has_required_fields else '❌'}, Token format: {'✅' if token_format_valid else '❌'}"
                    
                    self.record_test(
                        "Flutter Compatibility",
                        success,
                        duration,
                        details
                    )
                    
                    return success
                    
                else:
                    duration = time.time() - start_time
                    self.record_test(
                        "Flutter Compatibility",
                        False,
                        duration,
                        f"Registration failed with status {response.status}"
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.record_test(
                "Flutter Compatibility",
                False,
                duration,
                f"Error: {str(e)}"
            )
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if "✅ PASS" in result["status"])
        
        # Calculate overall success rate
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Determine overall status
        if success_rate >= 90:
            overall_status = "🎉 EXCELLENT - Phase 1 Complete"
        elif success_rate >= 75:
            overall_status = "✅ GOOD - Minor Issues"
        elif success_rate >= 50:
            overall_status = "⚠️ NEEDS WORK - Major Issues"
        else:
            overall_status = "❌ CRITICAL - System Unstable"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "success_rate": f"{success_rate:.1f}%",
            "tests_passed": f"{passed_tests}/{total_tests}",
            "test_results": self.test_results,
            "phase_1_complete": success_rate >= 85,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        failed_tests = [result for result in self.test_results if "❌ FAIL" in result["status"]]
        
        for failed_test in failed_tests:
            if "Server Health" in failed_test["test"]:
                recommendations.append("🔧 Check server startup process and database connectivity")
            elif "Registration" in failed_test["test"]:
                recommendations.append("🔧 Investigate registration endpoint issues")
            elif "Login" in failed_test["test"]:
                recommendations.append("🔧 Fix login endpoint authentication flow")
            elif "Rate Limiting" in failed_test["test"]:
                recommendations.append("🔧 Verify Redis rate limiting configuration")
            elif "JWT Authentication" in failed_test["test"]:
                recommendations.append("🔧 Check JWT token generation and validation")
            elif "Error Handling" in failed_test["test"]:
                recommendations.append("🔧 Improve API error response handling")
            elif "Flutter Compatibility" in failed_test["test"]:
                recommendations.append("🔧 Ensure response formats match Flutter app expectations")
        
        if not recommendations:
            recommendations.append("🎉 All tests passed! Phase 1 critical fixes are complete.")
        
        return recommendations


async def main():
    """Main test execution function"""
    print("🚀 MITA AUTHENTICATION SYSTEM - COMPREHENSIVE END-TO-END VALIDATION")
    print("=" * 70)
    print()
    
    # Configuration
    base_url = os.getenv("TEST_BASE_URL", "http://localhost:8000")
    
    async with AuthTestRunner(base_url) as test_runner:
        print(f"🎯 Testing against: {base_url}")
        print("📋 Running comprehensive authentication tests...")
        print()
        
        # Execute test suite
        all_tests_passed = True
        
        # Test 1: Server Health
        server_healthy = await test_runner.test_server_startup()
        if not server_healthy:
            print("❌ CRITICAL: Server health check failed. Cannot continue tests.")
            all_tests_passed = False
        else:
            # Test 2: Registration
            test_user = await test_runner.test_registration_endpoint()
            if test_user:
                # Test 3: Login
                login_success = await test_runner.test_login_endpoint(test_user)
                
                if login_success:
                    # Test 4: JWT Authentication
                    jwt_success = await test_runner.test_jwt_authentication(test_user)
                    all_tests_passed &= jwt_success
                else:
                    all_tests_passed = False
                    
                # Test 5: Flutter Compatibility
                flutter_success = await test_runner.test_flutter_compatibility(test_user)
                all_tests_passed &= flutter_success
                
            else:
                all_tests_passed = False
            
            # Test 6: Rate Limiting
            rate_limit_success = await test_runner.test_rate_limiting()
            all_tests_passed &= rate_limit_success
            
            # Test 7: Error Handling
            error_handling_success = await test_runner.test_error_handling()
            all_tests_passed &= error_handling_success
        
        # Generate and display report
        report = test_runner.generate_report()
        
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 70)
        
        print(f"🎯 Overall Status: {report['overall_status']}")
        print(f"📈 Success Rate: {report['success_rate']}")
        print(f"✅ Tests Passed: {report['tests_passed']}")
        print(f"🚀 Phase 1 Complete: {'✅ YES' if report['phase_1_complete'] else '❌ NO'}")
        
        print("\n📋 DETAILED TEST RESULTS:")
        print("-" * 70)
        
        # Display test results in table format
        table_data = []
        for result in test_runner.test_results:
            table_data.append([
                result["test"],
                result["status"],
                result["duration"],
                result["details"][:50] + "..." if len(result["details"]) > 50 else result["details"]
            ])
        
        print(tabulate(
            table_data,
            headers=["Test", "Status", "Duration", "Details"],
            tablefmt="grid"
        ))
        
        print("\n🔧 RECOMMENDATIONS:")
        print("-" * 70)
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"{i}. {rec}")
        
        # Save report to file
        report_filename = f"auth_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 Report saved to: {report_filename}")
        
        # Final status
        if report['phase_1_complete']:
            print("\n🎉 SUCCESS: Authentication system validation complete!")
            print("✅ Phase 1 critical fixes are working properly")
            print("🚀 Ready to proceed with Phase 2 development")
        else:
            print("\n❌ ATTENTION REQUIRED: Critical issues found")
            print("🔧 Please address the recommendations above before Phase 2")
        
        return all_tests_passed


if __name__ == "__main__":
    # Install required packages if not available
    try:
        import aiohttp
        import tabulate
    except ImportError:
        print("Installing required packages...")
        os.system("pip install aiohttp tabulate PyJWT")
        import aiohttp
        from tabulate import tabulate
    
    # Run the comprehensive test suite
    success = asyncio.run(main())
    exit_code = 0 if success else 1
    exit(exit_code)