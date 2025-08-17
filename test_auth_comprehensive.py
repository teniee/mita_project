#!/usr/bin/env python3
"""
MITA Authentication Comprehensive Test Suite
============================================

This test suite performs comprehensive authentication testing to identify
specific failure points in the login/registration flow.

As MITA's QA specialist, this test suite covers:
1. Network connectivity issues
2. Backend availability and performance  
3. API endpoint functionality
4. Database connectivity
5. Password hashing performance
6. Token generation
7. Mobile app API service configuration
8. Emergency registration endpoint testing
"""

import asyncio
import time
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

import aiohttp
import asyncpg
import requests
from urllib.parse import urlparse

# Test Configuration
BACKEND_URLS = [
    "http://localhost:8000",
    "https://mita-production.onrender.com",
    "http://127.0.0.1:8000"
]

TEST_USER_EMAIL = f"test_auth_{int(time.time())}@example.com"
TEST_USER_PASSWORD = "TestPassword123!"

class AuthTestResult:
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.success = False
        self.error_message = ""
        self.duration_ms = 0
        self.details = {}
        self.start_time = time.time()
    
    def complete(self, success: bool, error_message: str = "", details: Dict = None):
        self.success = success
        self.error_message = error_message
        self.duration_ms = (time.time() - self.start_time) * 1000
        self.details = details or {}
        return self

class AuthTestSuite:
    def __init__(self):
        self.results: List[AuthTestResult] = []
        self.working_backend_url: Optional[str] = None
        
    def log_result(self, result: AuthTestResult):
        """Log test result with detailed output for QA analysis"""
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"\n{status} {result.test_name}")
        print(f"   Duration: {result.duration_ms:.1f}ms")
        
        if not result.success:
            print(f"   Error: {result.error_message}")
        
        if result.details:
            for key, value in result.details.items():
                print(f"   {key}: {value}")
        
        self.results.append(result)

    async def test_network_connectivity(self) -> None:
        """Test 1: Network connectivity to backend servers"""
        print("\n🔍 TEST 1: Network Connectivity")
        
        for url in BACKEND_URLS:
            result = AuthTestResult(f"Network connectivity to {url}")
            
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"{url}/health", ssl=False) as response:
                        if response.status == 200:
                            result.complete(True, details={
                                "status_code": response.status,
                                "response_headers": dict(response.headers)
                            })
                            if not self.working_backend_url:
                                self.working_backend_url = url
                        else:
                            result.complete(False, f"HTTP {response.status}")
            except Exception as e:
                result.complete(False, str(e))
            
            self.log_result(result)

    async def test_backend_availability(self) -> None:
        """Test 2: Backend API availability and basic endpoints"""
        print("\n🔍 TEST 2: Backend API Availability")
        
        if not self.working_backend_url:
            print("❌ Skipping - No working backend URL found")
            return
        
        endpoints_to_test = [
            "/health",
            "/api/auth/emergency-diagnostics",
            "/docs"
        ]
        
        for endpoint in endpoints_to_test:
            result = AuthTestResult(f"Backend endpoint {endpoint}")
            
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"{self.working_backend_url}{endpoint}", ssl=False) as response:
                        if response.status in [200, 307, 308]:  # Include redirects as success
                            text = await response.text()
                            result.complete(True, details={
                                "status_code": response.status,
                                "response_size": len(text),
                                "content_type": response.headers.get("content-type", "unknown")
                            })
                        else:
                            result.complete(False, f"HTTP {response.status}")
            except Exception as e:
                result.complete(False, str(e))
            
            self.log_result(result)

    async def test_emergency_diagnostics(self) -> None:
        """Test 3: Emergency diagnostics endpoint"""
        print("\n🔍 TEST 3: Emergency Diagnostics")
        
        if not self.working_backend_url:
            print("❌ Skipping - No working backend URL found")
            return
        
        result = AuthTestResult("Emergency diagnostics endpoint")
        
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.working_backend_url}/api/auth/emergency-diagnostics", ssl=False) as response:
                    if response.status == 200:
                        diagnostics = await response.json()
                        result.complete(True, details={
                            "server_status": diagnostics.get("diagnostics", {}).get("server_status", "unknown"),
                            "database_status": diagnostics.get("diagnostics", {}).get("database", {}).get("status", "unknown"),
                            "password_hashing_status": diagnostics.get("diagnostics", {}).get("registration_components", {}).get("password_hashing", {}).get("status", "unknown"),
                            "token_creation_status": diagnostics.get("diagnostics", {}).get("registration_components", {}).get("token_creation", {}).get("status", "unknown")
                        })
                    else:
                        result.complete(False, f"HTTP {response.status}")
        except Exception as e:
            result.complete(False, str(e))
        
        self.log_result(result)

    async def test_emergency_registration(self) -> None:
        """Test 4: Emergency registration endpoint"""
        print("\n🔍 TEST 4: Emergency Registration Endpoint")
        
        if not self.working_backend_url:
            print("❌ Skipping - No working backend URL found")
            return
        
        result = AuthTestResult("Emergency registration")
        
        try:
            # Test with unique email each time
            test_email = f"emergency_test_{int(time.time())}@example.com"
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try emergency registration endpoint directly (bypassing heavy middleware)
                async with session.post(
                    f"{self.working_backend_url}/api/auth/emergency-register",
                    json={
                        "email": test_email,
                        "password": TEST_USER_PASSWORD
                    },
                    ssl=False
                ) as response:
                    if response.status == 201:
                        token_data = await response.json()
                        result.complete(True, details={
                            "has_access_token": bool(token_data.get("access_token")),
                            "has_refresh_token": bool(token_data.get("refresh_token")),
                            "token_type": token_data.get("token_type", "unknown")
                        })
                    else:
                        response_text = await response.text()
                        result.complete(False, f"HTTP {response.status}: {response_text}")
        except Exception as e:
            result.complete(False, str(e))
        
        self.log_result(result)

    async def test_regular_registration(self) -> None:
        """Test 5: Regular registration endpoint"""
        print("\n🔍 TEST 5: Regular Registration Endpoint")
        
        if not self.working_backend_url:
            print("❌ Skipping - No working backend URL found")
            return
        
        result = AuthTestResult("Regular registration")
        
        try:
            # Test with unique email each time
            test_email = f"regular_test_{int(time.time())}@example.com"
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.working_backend_url}/api/auth/register",
                    json={
                        "email": test_email,
                        "password": TEST_USER_PASSWORD
                    },
                    ssl=False
                ) as response:
                    if response.status == 201:
                        token_data = await response.json()
                        result.complete(True, details={
                            "has_access_token": bool(token_data.get("access_token")),
                            "has_refresh_token": bool(token_data.get("refresh_token")),
                            "token_type": token_data.get("token_type", "unknown")
                        })
                    else:
                        response_text = await response.text()
                        result.complete(False, f"HTTP {response.status}: {response_text}")
        except Exception as e:
            result.complete(False, str(e))
        
        self.log_result(result)

    async def test_login_endpoint(self) -> None:
        """Test 6: Login endpoint with existing user"""
        print("\n🔍 TEST 6: Login Endpoint")
        
        if not self.working_backend_url:
            print("❌ Skipping - No working backend URL found")
            return
        
        # First create a user via emergency registration
        test_email = f"login_test_{int(time.time())}@example.com"
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Create user first
                async with session.post(
                    f"{self.working_backend_url}/api/auth/emergency-register",
                    json={
                        "email": test_email,
                        "password": TEST_USER_PASSWORD
                    },
                    ssl=False
                ) as response:
                    if response.status != 201:
                        self.log_result(
                            AuthTestResult("Login endpoint - user creation")
                            .complete(False, f"Failed to create test user: HTTP {response.status}")
                        )
                        return
                
                # Now test login
                result = AuthTestResult("Login endpoint")
                async with session.post(
                    f"{self.working_backend_url}/api/auth/login",
                    json={
                        "email": test_email,
                        "password": TEST_USER_PASSWORD
                    },
                    ssl=False
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        result.complete(True, details={
                            "has_access_token": bool(token_data.get("access_token")),
                            "has_refresh_token": bool(token_data.get("refresh_token")),
                            "token_type": token_data.get("token_type", "unknown")
                        })
                    else:
                        response_text = await response.text()
                        result.complete(False, f"HTTP {response.status}: {response_text}")
                
                self.log_result(result)
                
        except Exception as e:
            self.log_result(
                AuthTestResult("Login endpoint").complete(False, str(e))
            )

    async def test_mobile_api_configuration(self) -> None:
        """Test 7: Mobile app API service configuration"""
        print("\n🔍 TEST 7: Mobile App API Configuration")
        
        result = AuthTestResult("Mobile API configuration")
        
        try:
            # Check if mobile app config file exists and has correct base URL
            config_path = "/Users/mikhail/StudioProjects/mita_project/mobile_app/lib/config.dart"
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_content = f.read()
                    
                    # Look for API base URL configuration
                    if "localhost:8000" in config_content or "mita-production.onrender.com" in config_content:
                        result.complete(True, details={
                            "config_file_exists": True,
                            "has_api_url": True,
                            "config_preview": config_content[:200] + "..." if len(config_content) > 200 else config_content
                        })
                    else:
                        result.complete(False, "API URL not configured properly", {
                            "config_file_exists": True,
                            "config_preview": config_content[:200] + "..." if len(config_content) > 200 else config_content
                        })
            else:
                result.complete(False, "Mobile app config file not found")
                
        except Exception as e:
            result.complete(False, str(e))
        
        self.log_result(result)

    async def test_timeout_configurations(self) -> None:
        """Test 8: Timeout configurations in mobile and backend"""
        print("\n🔍 TEST 8: Timeout Configurations")
        
        result = AuthTestResult("Timeout configurations")
        
        try:
            details = {}
            
            # Check timeout manager service
            timeout_service_path = "/Users/mikhail/StudioProjects/mita_project/mobile_app/lib/services/timeout_manager_service.dart"
            if os.path.exists(timeout_service_path):
                with open(timeout_service_path, 'r') as f:
                    content = f.read()
                    if "Duration(seconds: 30)" in content and "authentication" in content:
                        details["mobile_auth_timeout"] = "30 seconds (configured)"
                    else:
                        details["mobile_auth_timeout"] = "Not properly configured"
            
            # Check API service timeout
            api_service_path = "/Users/mikhail/StudioProjects/mita_project/mobile_app/lib/services/api_service.dart"
            if os.path.exists(api_service_path):
                with open(api_service_path, 'r') as f:
                    content = f.read()
                    if "receiveTimeout: const Duration(seconds: 45)" in content:
                        details["mobile_receive_timeout"] = "45 seconds (configured)"
                    else:
                        details["mobile_receive_timeout"] = "Not properly configured"
            
            # Check if emergency registration is being used
            register_screen_path = "/Users/mikhail/StudioProjects/mita_project/mobile_app/lib/screens/register_screen.dart"
            if os.path.exists(register_screen_path):
                with open(register_screen_path, 'r') as f:
                    content = f.read()
                    if "emergencyRegister" in content:
                        details["uses_emergency_registration"] = "Yes (configured)"
                    else:
                        details["uses_emergency_registration"] = "No (potential issue)"
            
            result.complete(True, details=details)
                
        except Exception as e:
            result.complete(False, str(e))
        
        self.log_result(result)

    def generate_qa_report(self) -> Dict[str, Any]:
        """Generate comprehensive QA report"""
        passed_tests = sum(1 for r in self.results if r.success)
        total_tests = len(self.results)
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
                "timestamp": datetime.now().isoformat()
            },
            "working_backend_url": self.working_backend_url,
            "test_results": []
        }
        
        for result in self.results:
            report["test_results"].append({
                "test_name": result.test_name,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "error_message": result.error_message,
                "details": result.details
            })
        
        return report

    async def run_all_tests(self):
        """Execute all authentication tests"""
        print("🚀 MITA Authentication Comprehensive Test Suite")
        print("=" * 60)
        print(f"Starting comprehensive auth testing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Execute all tests in sequence
        await self.test_network_connectivity()
        await self.test_backend_availability()
        await self.test_emergency_diagnostics()
        await self.test_emergency_registration()
        await self.test_regular_registration()
        await self.test_login_endpoint()
        await self.test_mobile_api_configuration()
        await self.test_timeout_configurations()
        
        # Generate final report
        print("\n" + "=" * 60)
        print("🏆 FINAL TEST RESULTS")
        print("=" * 60)
        
        report = self.generate_qa_report()
        
        print(f"Total Tests: {report['test_summary']['total_tests']}")
        print(f"Passed: {report['test_summary']['passed']}")
        print(f"Failed: {report['test_summary']['failed']}")
        print(f"Success Rate: {report['test_summary']['success_rate']}")
        
        if self.working_backend_url:
            print(f"Working Backend: {self.working_backend_url}")
        else:
            print("❌ No working backend found")
        
        # Critical issues summary
        critical_failures = [r for r in self.results if not r.success and any(keyword in r.test_name.lower() for keyword in ["emergency", "registration", "login"])]
        
        if critical_failures:
            print("\n🚨 CRITICAL AUTHENTICATION ISSUES:")
            for failure in critical_failures:
                print(f"   ❌ {failure.test_name}: {failure.error_message}")
        
        # Save detailed report
        with open("auth_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: auth_test_report.json")
        
        return report

async def main():
    """Main test execution function"""
    suite = AuthTestSuite()
    try:
        await suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
    except Exception as e:
        print(f"\n\n💥 Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest suite interrupted")
        sys.exit(1)