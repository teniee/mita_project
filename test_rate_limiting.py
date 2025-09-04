#!/usr/bin/env python3
"""
Rate Limiting Test Script for MITA Finance API
Tests the newly restored rate limiting functionality
"""

import asyncio
import aiohttp
import time
import json
import sys
from typing import Dict, Any


class RateLimitTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def test_endpoint(self, method: str, endpoint: str, data: Dict[str, Any] = None,
                          headers: Dict[str, str] = None, expected_limit: int = 5) -> Dict[str, Any]:
        """Test rate limiting on a specific endpoint"""
        print(f"\n🧪 Testing rate limiting on {method.upper()} {endpoint}")
        print(f"   Expected limit: {expected_limit} requests")
        
        results = {
            "endpoint": endpoint,
            "method": method,
            "expected_limit": expected_limit,
            "requests_made": 0,
            "rate_limited_at": None,
            "success": False,
            "errors": []
        }
        
        for i in range(expected_limit + 3):  # Test beyond the limit
            try:
                if method.upper() == "GET":
                    async with self.session.get(
                        f"{self.base_url}{endpoint}", 
                        headers=headers
                    ) as resp:
                        status = resp.status
                        response_data = await resp.text()
                else:
                    async with self.session.post(
                        f"{self.base_url}{endpoint}", 
                        json=data,
                        headers=headers
                    ) as resp:
                        status = resp.status
                        response_data = await resp.text()
                        
                results["requests_made"] = i + 1
                
                if status == 429:  # Rate limited
                    if results["rate_limited_at"] is None:
                        results["rate_limited_at"] = i + 1
                    print(f"   ✅ Request {i+1}: Rate limited (429)")
                    
                    # Check for Retry-After header
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        print(f"      Retry-After: {retry_after} seconds")
                    
                    results["success"] = True
                    break
                elif status < 400:
                    print(f"   ✅ Request {i+1}: Success ({status})")
                else:
                    print(f"   ⚠️  Request {i+1}: Error ({status}) - {response_data[:100]}")
                    results["errors"].append(f"Request {i+1}: {status} - {response_data[:100]}")
                    
            except Exception as e:
                print(f"   ❌ Request {i+1}: Exception - {str(e)}")
                results["errors"].append(f"Request {i+1}: Exception - {str(e)}")
                
            # Small delay between requests
            await asyncio.sleep(0.1)
            
        if results["rate_limited_at"] is None:
            print(f"   ❌ Rate limiting not triggered after {results['requests_made']} requests")
            results["success"] = False
        else:
            print(f"   ✅ Rate limiting triggered at request {results['rate_limited_at']}")
            
        return results
        
    async def test_authentication_endpoints(self) -> Dict[str, Any]:
        """Test rate limiting on authentication endpoints"""
        print("\n" + "="*60)
        print("🔐 TESTING AUTHENTICATION ENDPOINT RATE LIMITING")
        print("="*60)
        
        test_results = {}
        
        # Test registration rate limiting
        registration_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "testpassword123",
            "country": "US"
        }
        
        test_results["register"] = await self.test_endpoint(
            "POST", "/api/auth/register", 
            data=registration_data, 
            expected_limit=3
        )
        
        # Test login rate limiting (will fail due to invalid credentials, but that's okay)
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        test_results["login"] = await self.test_endpoint(
            "POST", "/api/auth/login",
            data=login_data,
            expected_limit=5
        )
        
        # Test password reset rate limiting
        test_results["password_reset"] = await self.test_endpoint(
            "POST", "/api/auth/password-reset/request",
            data={"email": "test@example.com"},
            expected_limit=3
        )
        
        return test_results
        
    async def test_api_endpoints(self) -> Dict[str, Any]:
        """Test rate limiting on API endpoints (requires authentication)"""
        print("\n" + "="*60)
        print("🔒 TESTING API ENDPOINT RATE LIMITING")
        print("="*60)
        print("Note: These tests require valid authentication tokens")
        
        test_results = {}
        
        # Create a test token (this would normally be from login)
        fake_token = "Bearer fake_token_for_testing"
        headers = {"Authorization": fake_token}
        
        # Test general API rate limiting
        test_results["api_general"] = await self.test_endpoint(
            "GET", "/api/users/me",  # This should be rate limited and return 401 due to invalid token
            headers=headers,
            expected_limit=1000  # High limit, won't be reached in test
        )
        
        return test_results
        
    async def test_health_and_public_endpoints(self) -> Dict[str, Any]:
        """Test that public endpoints work without rate limiting issues"""
        print("\n" + "="*60)
        print("🌐 TESTING PUBLIC ENDPOINTS")
        print("="*60)
        
        test_results = {}
        
        # Test health endpoint (should not be rate limited)
        print("\n🔍 Testing health endpoint...")
        try:
            async with self.session.get(f"{self.base_url}/health") as resp:
                if resp.status == 200:
                    print("   ✅ Health endpoint working")
                    test_results["health"] = {"status": "success", "code": resp.status}
                else:
                    print(f"   ❌ Health endpoint error: {resp.status}")
                    test_results["health"] = {"status": "error", "code": resp.status}
        except Exception as e:
            print(f"   ❌ Health endpoint exception: {e}")
            test_results["health"] = {"status": "exception", "error": str(e)}
            
        return test_results
        
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all rate limiting tests"""
        print("🚀 Starting comprehensive rate limiting tests...")
        print(f"   Base URL: {self.base_url}")
        
        all_results = {
            "timestamp": time.time(),
            "base_url": self.base_url,
            "tests": {}
        }
        
        # Test public endpoints first
        all_results["tests"]["public"] = await self.test_health_and_public_endpoints()
        
        # Test authentication rate limiting
        all_results["tests"]["auth"] = await self.test_authentication_endpoints()
        
        # Test API rate limiting
        all_results["tests"]["api"] = await self.test_api_endpoints()
        
        # Generate summary
        print("\n" + "="*60)
        print("📊 RATE LIMITING TEST SUMMARY")
        print("="*60)
        
        total_tests = 0
        successful_tests = 0
        
        for category, tests in all_results["tests"].items():
            if category == "public":
                continue  # Skip public endpoint counting
                
            for test_name, result in tests.items():
                total_tests += 1
                if result.get("success", False):
                    successful_tests += 1
                    print(f"✅ {category}.{test_name}: Rate limiting working")
                else:
                    print(f"❌ {category}.{test_name}: Rate limiting failed")
                    if result.get("errors"):
                        for error in result["errors"]:
                            print(f"   Error: {error}")
                            
        print(f"\n🎯 Overall: {successful_tests}/{total_tests} rate limiting tests passed")
        
        if successful_tests == total_tests:
            print("🎉 All rate limiting tests PASSED!")
        else:
            print("⚠️  Some rate limiting tests FAILED - review configuration")
            
        all_results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0
        }
        
        return all_results


async def main():
    """Main test function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"
        
    print("🔥 MITA Finance API - Rate Limiting Test Suite")
    print(f"Testing against: {base_url}")
    
    async with RateLimitTester(base_url) as tester:
        results = await tester.run_comprehensive_test()
        
        # Save results to file
        with open("rate_limiting_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
        print(f"\n💾 Results saved to: rate_limiting_test_results.json")
        
        # Exit with appropriate code
        success_rate = results["summary"]["success_rate"]
        if success_rate >= 0.8:  # 80% success rate required
            print("✅ Rate limiting tests completed successfully!")
            sys.exit(0)
        else:
            print("❌ Rate limiting tests failed!")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())