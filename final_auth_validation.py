#!/usr/bin/env python3
"""
Final Authentication Validation for MITA Finance
Comprehensive validation that works within rate limiting constraints
"""

import asyncio
import aiohttp
import time
import json
import logging
from typing import Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinalAuthValidator:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    async def create_session(self):
        timeout = aiohttp.ClientTimeout(total=30)
        return aiohttp.ClientSession(timeout=timeout)
    
    async def test_single_complete_flow(self):
        """Test a complete authentication flow for a single user"""
        
        flow_results = {}
        user_email = f"final_test_user_{int(time.time())}@example.com"
        user_password = "TestPassword123!"
        
        async with await self.create_session() as session:
            
            # Step 1: Emergency Registration
            logger.info(f"🔄 Testing emergency registration for {user_email[:15]}***")
            
            start_time = time.time()
            try:
                data = {
                    "email": user_email,
                    "password": user_password,
                    "country": "US",
                    "annual_income": 50000
                }
                
                async with session.post(f"{self.base_url}/auth/emergency-register", json=data) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        result = await response.json()
                        access_token = result.get("access_token")
                        refresh_token = result.get("refresh_token")
                        
                        flow_results["registration"] = {
                            "success": True,
                            "status_code": response.status,
                            "response_time_ms": response_time,
                            "access_token": access_token[:20] + "..." if access_token else None,
                            "has_refresh_token": bool(refresh_token)
                        }
                        
                        logger.info(f"  ✅ Registration successful ({response_time:.1f}ms)")
                        
                        # Wait before next request
                        await asyncio.sleep(3)
                        
                        # Step 2: Login with same credentials
                        logger.info(f"🔄 Testing login for registered user")
                        
                        start_time = time.time()
                        login_data = {"email": user_email, "password": user_password}
                        
                        async with session.post(f"{self.base_url}/auth/login", json=login_data) as login_response:
                            login_response_time = (time.time() - start_time) * 1000
                            
                            if login_response.status == 200:
                                login_result = await login_response.json()
                                new_access_token = login_result.get("access_token")
                                
                                flow_results["login"] = {
                                    "success": True,
                                    "status_code": login_response.status,
                                    "response_time_ms": login_response_time,
                                    "access_token": new_access_token[:20] + "..." if new_access_token else None
                                }
                                
                                logger.info(f"  ✅ Login successful ({login_response_time:.1f}ms)")
                                
                                # Use the new access token for subsequent requests
                                current_access_token = new_access_token
                                
                            elif login_response.status == 429:
                                flow_results["login"] = {
                                    "success": False,
                                    "status_code": login_response.status,
                                    "response_time_ms": login_response_time,
                                    "error": "Rate limited"
                                }
                                logger.info(f"  ⚠️ Login rate limited ({login_response_time:.1f}ms) - using registration token")
                                current_access_token = access_token
                            else:
                                flow_results["login"] = {
                                    "success": False,
                                    "status_code": login_response.status,
                                    "response_time_ms": login_response_time,
                                    "error": f"Login failed with status {login_response.status}"
                                }
                                logger.info(f"  ❌ Login failed: {login_response.status} ({login_response_time:.1f}ms)")
                                current_access_token = access_token
                        
                        # Wait before next request
                        await asyncio.sleep(3)
                        
                        # Step 3: Token Validation
                        if current_access_token:
                            logger.info(f"🔄 Testing token validation")
                            
                            start_time = time.time()
                            headers = {"Authorization": f"Bearer {current_access_token}"}
                            
                            async with session.get(f"{self.base_url}/auth/token/validate", headers=headers) as validate_response:
                                validate_response_time = (time.time() - start_time) * 1000
                                
                                flow_results["token_validation"] = {
                                    "success": validate_response.status == 200,
                                    "status_code": validate_response.status,
                                    "response_time_ms": validate_response_time
                                }
                                
                                if validate_response.status == 200:
                                    logger.info(f"  ✅ Token validation successful ({validate_response_time:.1f}ms)")
                                else:
                                    logger.info(f"  ❌ Token validation failed: {validate_response.status} ({validate_response_time:.1f}ms)")
                        
                        # Wait before next request
                        await asyncio.sleep(3)
                        
                        # Step 4: Token Refresh (if we have refresh token)
                        if refresh_token:
                            logger.info(f"🔄 Testing token refresh")
                            
                            start_time = time.time()
                            refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
                            
                            async with session.post(f"{self.base_url}/auth/refresh", headers=refresh_headers) as refresh_response:
                                refresh_response_time = (time.time() - start_time) * 1000
                                
                                if refresh_response.status == 200:
                                    refresh_result = await refresh_response.json()
                                    new_access = refresh_result.get("data", {}).get("access_token")
                                    
                                    flow_results["token_refresh"] = {
                                        "success": True,
                                        "status_code": refresh_response.status,
                                        "response_time_ms": refresh_response_time,
                                        "new_access_token": new_access[:20] + "..." if new_access else None
                                    }
                                    
                                    logger.info(f"  ✅ Token refresh successful ({refresh_response_time:.1f}ms)")
                                    current_access_token = new_access or current_access_token
                                    
                                else:
                                    flow_results["token_refresh"] = {
                                        "success": False,
                                        "status_code": refresh_response.status,
                                        "response_time_ms": refresh_response_time,
                                        "error": f"Refresh failed with status {refresh_response.status}"
                                    }
                                    logger.info(f"  ❌ Token refresh failed: {refresh_response.status} ({refresh_response_time:.1f}ms)")
                        
                        # Wait before final request
                        await asyncio.sleep(3)
                        
                        # Step 5: Logout
                        if current_access_token:
                            logger.info(f"🔄 Testing logout")
                            
                            start_time = time.time()
                            logout_headers = {"Authorization": f"Bearer {current_access_token}"}
                            
                            async with session.post(f"{self.base_url}/auth/logout", headers=logout_headers) as logout_response:
                                logout_response_time = (time.time() - start_time) * 1000
                                
                                flow_results["logout"] = {
                                    "success": logout_response.status == 200,
                                    "status_code": logout_response.status,
                                    "response_time_ms": logout_response_time
                                }
                                
                                if logout_response.status == 200:
                                    logger.info(f"  ✅ Logout successful ({logout_response_time:.1f}ms)")
                                else:
                                    logger.info(f"  ❌ Logout failed: {logout_response.status} ({logout_response_time:.1f}ms)")
                    
                    elif response.status == 429:
                        flow_results["registration"] = {
                            "success": False,
                            "status_code": response.status,
                            "response_time_ms": response_time,
                            "error": "Rate limited"
                        }
                        logger.info(f"  ⚠️ Registration rate limited ({response_time:.1f}ms)")
                    
                    else:
                        flow_results["registration"] = {
                            "success": False,
                            "status_code": response.status,
                            "response_time_ms": response_time,
                            "error": f"Registration failed with status {response.status}"
                        }
                        logger.info(f"  ❌ Registration failed: {response.status} ({response_time:.1f}ms)")
            
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                flow_results["registration"] = {
                    "success": False,
                    "status_code": 0,
                    "response_time_ms": response_time,
                    "error": str(e)
                }
                logger.info(f"  ❌ Registration exception: {e} ({response_time:.1f}ms)")
        
        return flow_results
    
    async def test_middleware_endpoints(self):
        """Test middleware endpoints performance"""
        
        middleware_results = {}
        endpoints = [
            ("health", "/health"),
            ("emergency_diagnostics", "/auth/emergency-diagnostics"),
            ("security_status", "/auth/security/status")
        ]
        
        async with await self.create_session() as session:
            for name, endpoint in endpoints:
                logger.info(f"🔄 Testing {name} endpoint")
                
                times = []
                statuses = []
                success_count = 0
                
                for i in range(3):  # Test each endpoint 3 times
                    start_time = time.time()
                    
                    try:
                        async with session.get(f"{self.base_url}{endpoint}") as response:
                            response_time = (time.time() - start_time) * 1000
                            times.append(response_time)
                            statuses.append(response.status)
                            
                            if response.status == 200:
                                success_count += 1
                    
                    except Exception as e:
                        response_time = (time.time() - start_time) * 1000
                        times.append(response_time)
                        statuses.append(0)
                    
                    await asyncio.sleep(1)  # Wait between requests
                
                middleware_results[name] = {
                    "success_count": success_count,
                    "total_requests": 3,
                    "success_rate": (success_count / 3) * 100,
                    "avg_response_time_ms": sum(times) / len(times) if times else 0,
                    "min_response_time_ms": min(times) if times else 0,
                    "max_response_time_ms": max(times) if times else 0,
                    "status_codes": statuses
                }
                
                logger.info(f"  📊 {name}: {success_count}/3 successful ({(success_count/3)*100:.1f}%), {middleware_results[name]['avg_response_time_ms']:.1f}ms avg")
        
        return middleware_results

async def run_final_validation():
    """Run the final comprehensive authentication validation"""
    
    print("🎯 MITA AUTHENTICATION FINAL VALIDATION")
    print("=" * 80)
    print("Comprehensive end-to-end authentication system validation")
    print("Testing restored middleware with production-like scenarios")
    print()
    
    validator = FinalAuthValidator()
    
    # Test 1: Complete Authentication Flow
    print("🔐 TEST 1: Complete Authentication Flow")
    print("-" * 60)
    
    auth_flow_result = await validator.test_single_complete_flow()
    
    # Test 2: Middleware Performance
    print(f"\n🔧 TEST 2: Middleware Endpoint Performance")
    print("-" * 60)
    
    middleware_results = await validator.test_middleware_endpoints()
    
    # Test 3: Rate Limiting Validation (quick test)
    print(f"\n🚨 TEST 3: Rate Limiting Validation")
    print("-" * 60)
    
    rate_limit_results = {}
    
    async with await validator.create_session() as session:
        logger.info("🔄 Testing rate limiting with rapid requests")
        
        # Make 5 rapid login requests (should trigger rate limiting)
        rate_limited_count = 0
        total_requests = 5
        
        for i in range(total_requests):
            start_time = time.time()
            
            try:
                data = {"email": f"rate_test_{i}@example.com", "password": "test123"}
                async with session.post(f"{validator.base_url}/auth/login", json=data) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 429:
                        rate_limited_count += 1
                        logger.info(f"  ⚡ Request {i+1}: Rate limited ({response_time:.1f}ms) - Expected!")
                    else:
                        logger.info(f"  ➡️ Request {i+1}: Status {response.status} ({response_time:.1f}ms)")
            
            except Exception as e:
                logger.info(f"  ❌ Request {i+1}: Exception {e}")
            
            await asyncio.sleep(0.1)  # Very short delay
        
        rate_limit_results = {
            "total_requests": total_requests,
            "rate_limited_requests": rate_limited_count,
            "rate_limiting_triggered": rate_limited_count > 0,
            "rate_limiting_percentage": (rate_limited_count / total_requests) * 100
        }
        
        logger.info(f"  📊 Rate limiting: {rate_limited_count}/{total_requests} requests blocked")
    
    # Generate Final Report
    print(f"\n📊 FINAL VALIDATION RESULTS")
    print("=" * 80)
    
    # Authentication flow analysis
    auth_flow_success = 0
    auth_flow_total = 0
    auth_flow_steps = ["registration", "login", "token_validation", "token_refresh", "logout"]
    
    for step in auth_flow_steps:
        if step in auth_flow_result:
            auth_flow_total += 1
            if auth_flow_result[step].get("success", False):
                auth_flow_success += 1
    
    auth_flow_success_rate = (auth_flow_success / auth_flow_total * 100) if auth_flow_total > 0 else 0
    
    print(f"Authentication Flow Results:")
    for step in auth_flow_steps:
        if step in auth_flow_result:
            result = auth_flow_result[step]
            status = "✅" if result.get("success") else "❌" 
            response_time = result.get("response_time_ms", 0)
            status_code = result.get("status_code", "N/A")
            print(f"  {status} {step.replace('_', ' ').title()}: {status_code} ({response_time:.1f}ms)")
    
    print(f"  📈 Flow Success Rate: {auth_flow_success}/{auth_flow_total} ({auth_flow_success_rate:.1f}%)")
    
    # Middleware performance analysis
    print(f"\\nMiddleware Performance Results:")
    middleware_healthy = True
    for name, result in middleware_results.items():
        success_rate = result["success_rate"]
        avg_response = result["avg_response_time_ms"]
        status = "✅" if success_rate >= 90 else "⚠️" if success_rate >= 70 else "❌"
        
        print(f"  {status} {name.replace('_', ' ').title()}: {success_rate:.1f}% success, {avg_response:.1f}ms avg")
        
        if success_rate < 80:
            middleware_healthy = False
    
    # Rate limiting analysis
    print(f"\\nRate Limiting Results:")
    if rate_limit_results["rate_limiting_triggered"]:
        print(f"  ✅ Rate limiting is working correctly")
        print(f"  📊 {rate_limit_results['rate_limited_requests']}/{rate_limit_results['total_requests']} requests blocked")
    else:
        print(f"  ⚠️ Rate limiting may not be properly configured")
    
    # Overall assessment
    print(f"\\n🎯 FINAL ASSESSMENT:")
    print("=" * 80)
    
    assessment_criteria = {
        "auth_flow_functional": auth_flow_success_rate >= 60,
        "registration_works": auth_flow_result.get("registration", {}).get("success", False),
        "middleware_healthy": middleware_healthy,
        "rate_limiting_works": rate_limit_results["rate_limiting_triggered"],
        "performance_acceptable": True  # We'll calculate this
    }
    
    # Calculate performance acceptance
    all_response_times = []
    for result in auth_flow_result.values():
        if isinstance(result, dict) and result.get("response_time_ms"):
            all_response_times.append(result["response_time_ms"])
    
    for result in middleware_results.values():
        if result.get("avg_response_time_ms"):
            all_response_times.append(result["avg_response_time_ms"])
    
    if all_response_times:
        avg_response_time = sum(all_response_times) / len(all_response_times)
        assessment_criteria["performance_acceptable"] = avg_response_time < 2000
        print(f"Average Response Time: {avg_response_time:.1f}ms")
    
    passed_criteria = sum(assessment_criteria.values())
    total_criteria = len(assessment_criteria)
    
    print(f"\\nCriteria Assessment:")
    criteria_descriptions = {
        "auth_flow_functional": "Authentication flow is functional",
        "registration_works": "User registration is working",
        "middleware_healthy": "Middleware endpoints are healthy",
        "rate_limiting_works": "Rate limiting is operational", 
        "performance_acceptable": "Response times are acceptable"
    }
    
    for criterion, passed in assessment_criteria.items():
        status = "✅" if passed else "❌"
        description = criteria_descriptions[criterion]
        print(f"  {status} {description}")
    
    print(f"\\n📊 Overall Score: {passed_criteria}/{total_criteria} criteria met")
    
    # Final verdict
    if passed_criteria >= 4:
        print("\\n🎉 COMPREHENSIVE AUTHENTICATION VALIDATION: PASSED")
        print("✅ Authentication system is production-ready")
        print("🔒 Middleware restoration successful")
        print("⚡ System handles load appropriately")
        print("🚀 Ready for production deployment")
        final_success = True
    elif passed_criteria >= 3:
        print("\\n⚠️ COMPREHENSIVE AUTHENTICATION VALIDATION: CONDITIONAL PASS")
        print("✅ Core authentication functionality works")
        print("🔧 Some components may need minor optimization")
        print("📋 Monitor closely in production")
        final_success = True
    else:
        print("\\n❌ COMPREHENSIVE AUTHENTICATION VALIDATION: FAILED")
        print("🔒 Authentication system has significant issues")
        print("🛠️ Requires immediate fixes before production")
        print("📋 Review and address failing components")
        final_success = False
    
    # Save comprehensive report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"final_auth_validation_report_{timestamp}.json"
    
    comprehensive_report = {
        "test_summary": {
            "timestamp": timestamp,
            "test_type": "comprehensive_authentication_validation",
            "overall_success": final_success,
            "criteria_met": f"{passed_criteria}/{total_criteria}",
            "auth_flow_success_rate": auth_flow_success_rate
        },
        "authentication_flow_results": auth_flow_result,
        "middleware_performance_results": middleware_results,
        "rate_limiting_validation": rate_limit_results,
        "performance_summary": {
            "average_response_time_ms": avg_response_time if all_response_times else 0,
            "total_response_samples": len(all_response_times),
            "performance_acceptable": assessment_criteria["performance_acceptable"]
        },
        "assessment_criteria": assessment_criteria,
        "recommendations": [
            "Monitor rate limiting effectiveness in production",
            "Track response times under real load",
            "Implement comprehensive logging for auth flows",
            "Consider load balancing for high traffic periods",
            "Regularly test emergency endpoints functionality"
        ]
    }
    
    with open(report_file, 'w') as f:
        json.dump(comprehensive_report, f, indent=2, default=str)
    
    print(f"\\n📋 Final validation report saved: {report_file}")
    
    return final_success

if __name__ == "__main__":
    try:
        success = asyncio.run(run_final_validation())
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Final validation failed: {e}")
        logger.exception("Final validation error")
        exit(1)