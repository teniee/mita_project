#!/usr/bin/env python3
"""
Rate Limiting Status Checker for MITA Finance API
Checks if rate limiting is properly configured and working
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional


class RateLimitStatusChecker:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    async def check_server_health(self) -> Dict[str, Any]:
        """Check if the server is running and healthy"""
        print("🏥 Checking server health...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print("   ✅ Server is healthy")
                        return {"status": "healthy", "data": data}
                    else:
                        print(f"   ⚠️  Server returned status {resp.status}")
                        return {"status": "unhealthy", "code": resp.status}
        except aiohttp.ClientError as e:
            print(f"   ❌ Connection error: {e}")
            return {"status": "connection_error", "error": str(e)}
        except asyncio.TimeoutError:
            print("   ❌ Server not responding (timeout)")
            return {"status": "timeout"}
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            return {"status": "error", "error": str(e)}
            
    async def check_redis_status(self) -> Dict[str, Any]:
        """Check Redis configuration and status"""
        print("\n🔍 Checking Redis configuration...")
        
        redis_status = {
            "env_vars": {},
            "configured": False,
            "connection_type": None
        }
        
        # Check environment variables
        env_vars = [
            "UPSTASH_REDIS_REST_URL",
            "UPSTASH_REDIS_REST_TOKEN", 
            "UPSTASH_REDIS_URL",
            "REDIS_URL"
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            redis_status["env_vars"][var] = bool(value)
            if value:
                print(f"   ✅ {var}: Configured")
            else:
                print(f"   ❌ {var}: Not set")
                
        # Determine connection type
        if redis_status["env_vars"]["UPSTASH_REDIS_REST_URL"] and redis_status["env_vars"]["UPSTASH_REDIS_REST_TOKEN"]:
            redis_status["connection_type"] = "upstash_rest"
            redis_status["configured"] = True
        elif redis_status["env_vars"]["UPSTASH_REDIS_URL"] or redis_status["env_vars"]["REDIS_URL"]:
            redis_status["connection_type"] = "redis_tcp"
            redis_status["configured"] = True
        else:
            redis_status["connection_type"] = "none"
            redis_status["configured"] = False
            
        if redis_status["configured"]:
            print(f"   ✅ Redis configured for: {redis_status['connection_type']}")
        else:
            print("   ⚠️  No Redis configuration found - will use in-memory fallback")
            
        return redis_status
        
    async def test_simple_rate_limiting(self) -> Dict[str, Any]:
        """Test basic rate limiting functionality"""
        print("\n⚡ Testing basic rate limiting...")
        
        test_results = {
            "endpoint_tested": "/api/auth/login",
            "requests_made": 0,
            "rate_limited": False,
            "rate_limit_at_request": None,
            "errors": []
        }
        
        login_data = {
            "email": "test_rate_limit@example.com",
            "password": "wrongpassword123"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                for i in range(10):  # Try 10 requests
                    try:
                        async with session.post(
                            f"{self.base_url}/api/auth/login",
                            json=login_data,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            test_results["requests_made"] = i + 1
                            
                            if resp.status == 429:
                                test_results["rate_limited"] = True
                                test_results["rate_limit_at_request"] = i + 1
                                print(f"   ✅ Rate limited at request {i + 1}")
                                
                                # Check for Retry-After header
                                retry_after = resp.headers.get('Retry-After')
                                if retry_after:
                                    print(f"   ✅ Retry-After header: {retry_after} seconds")
                                    test_results["retry_after"] = retry_after
                                    
                                break
                            elif resp.status in [400, 401]:
                                # Expected for invalid credentials
                                print(f"   → Request {i + 1}: Expected auth error ({resp.status})")
                            else:
                                print(f"   → Request {i + 1}: Unexpected status {resp.status}")
                                
                    except asyncio.TimeoutError:
                        test_results["errors"].append(f"Request {i + 1}: Timeout")
                        break
                    except Exception as e:
                        test_results["errors"].append(f"Request {i + 1}: {str(e)}")
                        break
                        
                    await asyncio.sleep(0.1)  # Small delay
                    
        except Exception as e:
            test_results["errors"].append(f"Test setup error: {str(e)}")
            
        if test_results["rate_limited"]:
            print("   ✅ Rate limiting is working!")
        else:
            print("   ❌ Rate limiting not triggered")
            
        return test_results
        
    async def check_auth_endpoints_rate_limits(self) -> Dict[str, Any]:
        """Check rate limiting configuration for auth endpoints"""
        print("\n🔐 Checking authentication endpoints rate limiting...")
        
        endpoints = {
            "login": "/api/auth/login",
            "register": "/api/auth/register", 
            "refresh": "/api/auth/refresh",
            "password_reset": "/api/auth/password-reset/request"
        }
        
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for name, endpoint in endpoints.items():
                print(f"   Testing {name} endpoint...")
                
                # Just test if endpoint exists and has rate limiting dependency
                try:
                    if name == "login":
                        data = {"email": "test@example.com", "password": "test"}
                    elif name == "register":
                        data = {"email": f"test_{datetime.now().timestamp()}@example.com", "password": "testpass123"}
                    elif name == "refresh":
                        data = {}
                    else:
                        data = {"email": "test@example.com"}
                        
                    async with session.post(
                        f"{self.base_url}{endpoint}",
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        # We expect either success, validation error, or rate limit
                        if resp.status in [200, 201, 400, 401, 422, 429]:
                            results[name] = {"status": "accessible", "code": resp.status}
                            print(f"     ✅ Endpoint accessible (status: {resp.status})")
                        else:
                            results[name] = {"status": "error", "code": resp.status}
                            print(f"     ❌ Unexpected status: {resp.status}")
                            
                except asyncio.TimeoutError:
                    results[name] = {"status": "timeout"}
                    print(f"     ❌ Timeout accessing endpoint")
                except Exception as e:
                    results[name] = {"status": "error", "error": str(e)}
                    print(f"     ❌ Error: {str(e)}")
                    
        return results
        
    async def generate_status_report(self) -> Dict[str, Any]:
        """Generate comprehensive status report"""
        print("\n" + "="*60)
        print("🔥 MITA Finance API - Rate Limiting Status Report")
        print("="*60)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "base_url": self.base_url,
            "checks": {}
        }
        
        # Check server health
        report["checks"]["server_health"] = await self.check_server_health()
        
        # Check Redis configuration
        report["checks"]["redis_status"] = await self.check_redis_status()
        
        # Test basic rate limiting
        report["checks"]["rate_limiting_test"] = await self.test_simple_rate_limiting()
        
        # Check auth endpoints
        report["checks"]["auth_endpoints"] = await self.check_auth_endpoints_rate_limits()
        
        # Generate overall assessment
        print("\n" + "="*60)
        print("📊 OVERALL ASSESSMENT")
        print("="*60)
        
        server_healthy = report["checks"]["server_health"]["status"] == "healthy"
        redis_configured = report["checks"]["redis_status"]["configured"]
        rate_limiting_works = report["checks"]["rate_limiting_test"]["rate_limited"]
        
        if server_healthy:
            print("✅ Server: Healthy")
        else:
            print("❌ Server: Not healthy")
            
        if redis_configured:
            redis_type = report["checks"]["redis_status"]["connection_type"]
            print(f"✅ Redis: Configured ({redis_type})")
        else:
            print("⚠️  Redis: Not configured (using in-memory fallback)")
            
        if rate_limiting_works:
            print("✅ Rate Limiting: Working")
        else:
            print("❌ Rate Limiting: Not working")
            
        # Overall status
        if server_healthy and rate_limiting_works:
            overall_status = "HEALTHY"
            print(f"\n🎉 Overall Status: {overall_status}")
            print("   Rate limiting is properly configured and working!")
        elif server_healthy:
            overall_status = "DEGRADED"
            print(f"\n⚠️  Overall Status: {overall_status}")
            print("   Server is running but rate limiting may not be working properly.")
        else:
            overall_status = "UNHEALTHY"
            print(f"\n❌ Overall Status: {overall_status}")
            print("   Server is not healthy.")
            
        report["overall_status"] = overall_status
        
        return report


async def main():
    """Main function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"
        
    checker = RateLimitStatusChecker(base_url)
    report = await checker.generate_status_report()
    
    # Save report
    report_file = "rate_limiting_status_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\n💾 Full report saved to: {report_file}")
    
    # Exit with appropriate code
    if report["overall_status"] == "HEALTHY":
        print("✅ Rate limiting status check PASSED!")
        sys.exit(0)
    elif report["overall_status"] == "DEGRADED":
        print("⚠️  Rate limiting status check shows DEGRADED performance!")
        sys.exit(1)
    else:
        print("❌ Rate limiting status check FAILED!")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())