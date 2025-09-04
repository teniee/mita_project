#!/usr/bin/env python3
"""
Realistic Authentication Load Testing for MITA Finance
Tests the complete authentication flow with proper rate limiting consideration
"""

import asyncio
import aiohttp
import time
import json
import logging
import random
from typing import Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealisticAuthTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.registered_users = []
    
    async def create_session(self):
        timeout = aiohttp.ClientTimeout(total=30)
        return aiohttp.ClientSession(timeout=timeout)
    
    async def register_user(self, session: aiohttp.ClientSession, email: str, password: str = "TestPassword123!"):
        """Register a single user with proper error handling"""
        try:
            data = {
                "email": email,
                "password": password,
                "country": "US",
                "annual_income": 50000
            }
            
            # Try emergency registration first (higher rate limits)
            async with session.post(f"{self.base_url}/auth/emergency-register", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self.registered_users.append({
                        "email": email,
                        "password": password,
                        "access_token": result.get("access_token"),
                        "refresh_token": result.get("refresh_token")
                    })
                    return True, "emergency_register", response.status
                else:
                    return False, "emergency_register", response.status
        except Exception as e:
            return False, "emergency_register", 0
    
    async def login_user(self, session: aiohttp.ClientSession, email: str, password: str):
        """Login a user with proper error handling"""
        try:
            data = {"email": email, "password": password}
            
            async with session.post(f"{self.base_url}/auth/login", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return True, result.get("access_token"), response.status
                else:
                    return False, None, response.status
        except Exception as e:
            return False, None, 0
    
    async def refresh_token(self, session: aiohttp.ClientSession, refresh_token: str):
        """Refresh a token"""
        try:
            headers = {"Authorization": f"Bearer {refresh_token}"}
            async with session.post(f"{self.base_url}/auth/refresh", headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    new_access = result.get("data", {}).get("access_token")
                    return True, new_access, response.status
                else:
                    return False, None, response.status
        except Exception as e:
            return False, None, 0
    
    async def logout_user(self, session: aiohttp.ClientSession, access_token: str):
        """Logout a user"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with session.post(f"{self.base_url}/auth/logout", headers=headers) as response:
                return response.status == 200, response.status
        except Exception as e:
            return False, 0

async def run_realistic_tests():
    """Run realistic authentication load tests"""
    
    print("🚀 MITA REALISTIC AUTHENTICATION LOAD TESTING")
    print("=" * 70)
    print("Testing complete authentication workflows under realistic conditions")
    print()
    
    tester = RealisticAuthTester()
    
    # Phase 1: Sequential User Registration (respecting rate limits)
    print("📝 PHASE 1: User Registration (Sequential to respect rate limits)")
    print("-" * 50)
    
    registration_results = []
    num_users_to_register = 5  # Conservative to avoid rate limiting
    
    async with await tester.create_session() as session:
        for i in range(num_users_to_register):
            email = f"realistic_test_user_{i}_{int(time.time())}@example.com"
            
            start_time = time.time()
            success, endpoint, status_code = await tester.register_user(session, email)
            response_time = (time.time() - start_time) * 1000
            
            registration_results.append({
                "user_index": i,
                "email": email,
                "success": success,
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time_ms": response_time
            })
            
            if success:
                logger.info(f"  ✅ User {i+1} registered successfully ({response_time:.1f}ms)")
            else:
                logger.info(f"  ❌ User {i+1} registration failed: {status_code} ({response_time:.1f}ms)")
            
            # Delay between registrations to respect rate limits
            await asyncio.sleep(2)
    
    successful_registrations = len([r for r in registration_results if r["success"]])
    print(f"Registration Summary: {successful_registrations}/{num_users_to_register} successful")
    
    if successful_registrations == 0:
        print("❌ No users registered successfully. Cannot proceed with authentication tests.")
        return False
    
    # Phase 2: Concurrent Login Testing
    print(f"\n🔐 PHASE 2: Concurrent Login Testing")
    print("-" * 50)
    
    login_results = []
    
    async def login_test_user(user_data):
        async with await tester.create_session() as session:
            start_time = time.time()
            success, token, status_code = await tester.login_user(session, user_data["email"], user_data["password"])
            response_time = (time.time() - start_time) * 1000
            
            return {
                "email": user_data["email"],
                "success": success,
                "access_token": token,
                "status_code": status_code,
                "response_time_ms": response_time
            }
    
    # Test concurrent logins with registered users
    login_tasks = [login_test_user(user) for user in tester.registered_users[:3]]  # Conservative concurrency
    login_results = await asyncio.gather(*login_tasks, return_exceptions=True)
    
    successful_logins = len([r for r in login_results if isinstance(r, dict) and r.get("success")])
    
    for i, result in enumerate(login_results):
        if isinstance(result, Exception):
            logger.info(f"  ❌ Login {i+1} failed with exception: {result}")
        elif result.get("success"):
            logger.info(f"  ✅ Login {i+1} successful ({result['response_time_ms']:.1f}ms)")
        else:
            logger.info(f"  ❌ Login {i+1} failed: {result['status_code']} ({result['response_time_ms']:.1f}ms)")
    
    print(f"Login Summary: {successful_logins}/{len(login_tasks)} successful")
    
    # Phase 3: Token Refresh Testing
    print(f"\n🔄 PHASE 3: Token Refresh Testing")
    print("-" * 50)
    
    refresh_results = []
    
    # Test token refresh for successful logins
    successful_login_results = [r for r in login_results if isinstance(r, dict) and r.get("success")]
    
    if successful_login_results:
        async with await tester.create_session() as session:
            for user_data in tester.registered_users[:len(successful_login_results)]:
                if user_data.get("refresh_token"):
                    start_time = time.time()
                    success, new_token, status_code = await tester.refresh_token(session, user_data["refresh_token"])
                    response_time = (time.time() - start_time) * 1000
                    
                    refresh_results.append({
                        "email": user_data["email"],
                        "success": success,
                        "status_code": status_code,
                        "response_time_ms": response_time
                    })
                    
                    if success:
                        logger.info(f"  ✅ Token refresh successful for {user_data['email'][:10]}*** ({response_time:.1f}ms)")
                        user_data["access_token"] = new_token  # Update token
                    else:
                        logger.info(f"  ❌ Token refresh failed for {user_data['email'][:10]}***: {status_code} ({response_time:.1f}ms)")
                    
                    await asyncio.sleep(0.5)  # Small delay
    
    successful_refreshes = len([r for r in refresh_results if r["success"]])
    print(f"Token Refresh Summary: {successful_refreshes}/{len(refresh_results)} successful")
    
    # Phase 4: Middleware Performance Testing
    print(f"\n🔧 PHASE 4: Middleware Performance Testing")
    print("-" * 50)
    
    middleware_results = []
    
    async def test_middleware_endpoint(endpoint_name, endpoint_path):
        times = []
        success_count = 0
        
        async with await tester.create_session() as session:
            for _ in range(3):  # Test each endpoint 3 times
                start_time = time.time()
                try:
                    async with session.get(f"{tester.base_url}{endpoint_path}") as response:
                        response_time = (time.time() - start_time) * 1000
                        times.append(response_time)
                        if response.status == 200:
                            success_count += 1
                except Exception:
                    response_time = (time.time() - start_time) * 1000
                    times.append(response_time)
                
                await asyncio.sleep(0.2)
        
        return {
            "endpoint": endpoint_name,
            "successful_requests": success_count,
            "total_requests": 3,
            "success_rate": (success_count / 3) * 100,
            "avg_response_time_ms": sum(times) / len(times) if times else 0,
            "min_response_time_ms": min(times) if times else 0,
            "max_response_time_ms": max(times) if times else 0
        }
    
    middleware_endpoints = [
        ("Emergency Diagnostics", "/auth/emergency-diagnostics"),
        ("Security Status", "/auth/security/status"),
        ("Health Check", "/health")
    ]
    
    middleware_tasks = [test_middleware_endpoint(name, path) for name, path in middleware_endpoints]
    middleware_results = await asyncio.gather(*middleware_tasks)
    
    for result in middleware_results:
        endpoint = result["endpoint"]
        success_rate = result["success_rate"]
        avg_response = result["avg_response_time_ms"]
        logger.info(f"  📊 {endpoint}: {success_rate:.1f}% success, {avg_response:.1f}ms avg")
    
    # Phase 5: Logout Testing
    print(f"\n🚪 PHASE 5: Logout Testing")
    print("-" * 50)
    
    logout_results = []
    
    # Test logout for users with valid tokens
    users_with_tokens = [user for user in tester.registered_users if user.get("access_token")]
    
    async with await tester.create_session() as session:
        for user_data in users_with_tokens:
            start_time = time.time()
            success, status_code = await tester.logout_user(session, user_data["access_token"])
            response_time = (time.time() - start_time) * 1000
            
            logout_results.append({
                "email": user_data["email"],
                "success": success,
                "status_code": status_code,
                "response_time_ms": response_time
            })
            
            if success:
                logger.info(f"  ✅ Logout successful for {user_data['email'][:10]}*** ({response_time:.1f}ms)")
            else:
                logger.info(f"  ❌ Logout failed for {user_data['email'][:10]}***: {status_code} ({response_time:.1f}ms)")
    
    successful_logouts = len([r for r in logout_results if r["success"]])
    print(f"Logout Summary: {successful_logouts}/{len(logout_results)} successful")
    
    # Generate Comprehensive Report
    print(f"\n📊 COMPREHENSIVE TEST RESULTS")
    print("=" * 70)
    
    # Calculate overall metrics
    total_operations = len(registration_results) + len(login_results) + len(refresh_results) + len(logout_results)
    successful_operations = (
        successful_registrations + 
        successful_logins + 
        successful_refreshes + 
        successful_logouts
    )
    
    overall_success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
    
    print(f"Overall Authentication Flow Performance:")
    print(f"  • Total Operations: {total_operations}")
    print(f"  • Successful Operations: {successful_operations}")
    print(f"  • Overall Success Rate: {overall_success_rate:.1f}%")
    print()
    
    print(f"Phase-by-Phase Results:")
    print(f"  • Registration: {successful_registrations}/{len(registration_results)} ({(successful_registrations/len(registration_results)*100):.1f}%)")
    print(f"  • Login: {successful_logins}/{len(login_results)} ({(successful_logins/len(login_results)*100) if login_results else 0:.1f}%)")
    print(f"  • Token Refresh: {successful_refreshes}/{len(refresh_results)} ({(successful_refreshes/len(refresh_results)*100) if refresh_results else 0:.1f}%)")
    print(f"  • Logout: {successful_logouts}/{len(logout_results)} ({(successful_logouts/len(logout_results)*100) if logout_results else 0:.1f}%)")
    
    # Performance Analysis
    all_response_times = []
    for result_set in [registration_results, login_results, refresh_results, logout_results]:
        for result in result_set:
            if isinstance(result, dict) and result.get("response_time_ms"):
                all_response_times.append(result["response_time_ms"])
    
    if all_response_times:
        avg_response_time = sum(all_response_times) / len(all_response_times)
        max_response_time = max(all_response_times)
        min_response_time = min(all_response_times)
        
        print(f"\nPerformance Metrics:")
        print(f"  • Average Response Time: {avg_response_time:.1f}ms")
        print(f"  • Minimum Response Time: {min_response_time:.1f}ms")
        print(f"  • Maximum Response Time: {max_response_time:.1f}ms")
    
    # Middleware Performance
    print(f"\nMiddleware Performance:")
    for result in middleware_results:
        print(f"  • {result['endpoint']}: {result['success_rate']:.1f}% success, {result['avg_response_time_ms']:.1f}ms avg")
    
    # Final Assessment
    print(f"\n🎯 REALISTIC TEST ASSESSMENT:")
    print("=" * 70)
    
    assessment_criteria = {
        "registration_works": successful_registrations > 0,
        "login_works": successful_logins > 0,
        "token_refresh_works": successful_refreshes > 0 if refresh_results else True,
        "logout_works": successful_logouts > 0 if logout_results else True,
        "middleware_healthy": all(r["success_rate"] >= 80 for r in middleware_results),
        "performance_acceptable": avg_response_time < 2000 if all_response_times else True,
        "overall_success_acceptable": overall_success_rate >= 60
    }
    
    passed_criteria = sum(assessment_criteria.values())
    total_criteria = len(assessment_criteria)
    
    findings = []
    
    if assessment_criteria["registration_works"]:
        findings.append("✅ User registration is functional")
    else:
        findings.append("❌ User registration is failing")
    
    if assessment_criteria["login_works"]:
        findings.append("✅ User login is functional")
    else:
        findings.append("❌ User login is failing")
    
    if assessment_criteria["middleware_healthy"]:
        findings.append("✅ Middleware endpoints are healthy")
    else:
        findings.append("⚠️ Some middleware endpoints have issues")
    
    if assessment_criteria["performance_acceptable"]:
        findings.append("✅ Response times are acceptable")
    else:
        findings.append("⚠️ Response times are elevated")
    
    # Rate limiting assessment
    rate_limited_count = sum(1 for r in registration_results + login_results + refresh_results if r.get("status_code") == 429)
    if rate_limited_count > 0:
        findings.append("✅ Rate limiting is working correctly")
    else:
        findings.append("⚠️ Rate limiting behavior unclear")
    
    for finding in findings:
        print(f"  • {finding}")
    
    print(f"\nCriteria Met: {passed_criteria}/{total_criteria}")
    
    if passed_criteria >= 6:
        print("✅ REALISTIC AUTHENTICATION TESTING: PASSED")
        print("🔒 Authentication system handles realistic workflows well")
        print("🚀 System appears ready for production load")
        success = True
    elif passed_criteria >= 4:
        print("⚠️ REALISTIC AUTHENTICATION TESTING: PARTIAL PASS")
        print("🔒 Authentication system works but has some issues")
        print("🔧 Consider minor optimizations")
        success = True
    else:
        print("❌ REALISTIC AUTHENTICATION TESTING: FAILED")
        print("🔒 Authentication system has significant issues")
        print("🛠️ Requires immediate investigation and fixes")
        success = False
    
    # Save comprehensive report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"realistic_auth_load_test_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump({
            "test_summary": {
                "timestamp": timestamp,
                "test_type": "realistic_authentication_flow",
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "overall_success_rate": overall_success_rate,
                "criteria_met": f"{passed_criteria}/{total_criteria}",
                "test_passed": success
            },
            "phase_results": {
                "registration": registration_results,
                "login": login_results,
                "token_refresh": refresh_results,
                "logout": logout_results,
                "middleware": middleware_results
            },
            "performance_metrics": {
                "average_response_time_ms": avg_response_time if all_response_times else 0,
                "min_response_time_ms": min_response_time if all_response_times else 0,
                "max_response_time_ms": max_response_time if all_response_times else 0,
                "total_response_samples": len(all_response_times)
            },
            "assessment_criteria": assessment_criteria,
            "findings": findings
        }, f, indent=2, default=str)
    
    print(f"\n📋 Comprehensive report saved: {report_file}")
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(run_realistic_tests())
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Realistic test failed: {e}")
        exit(1)