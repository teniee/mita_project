#!/usr/bin/env python3
"""
MITA Finance API - Production Deployment Monitor
Monitors production server deployment and tests authentication endpoints
"""

import asyncio
import json
import time
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production server configuration
PRODUCTION_BASE_URL = "https://mita-docker-ready-project-manus.onrender.com"

class DeploymentMonitor:
    """Monitor production deployment status and test endpoints"""
    
    def __init__(self, base_url: str = PRODUCTION_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_user_credentials = {
            "email": "test@mita.finance",
            "password": "TestPassword123!"
        }
        
    async def __aenter__(self):
        """Create aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    async def test_endpoint(self, path: str, method: str = "GET", 
                          data: Optional[Dict] = None, 
                          headers: Optional[Dict] = None,
                          expected_status: Optional[int] = None,
                          timeout: int = 30) -> Dict:
        """Test a specific endpoint and return results"""
        url = f"{self.base_url}{path}"
        
        try:
            start_time = time.time()
            
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers) as response:
                    response_time = (time.time() - start_time) * 1000
                    content = await response.text()
                    return {
                        "url": url,
                        "status": response.status,
                        "response_time_ms": round(response_time, 2),
                        "content": content[:500] if content else "",
                        "success": expected_status is None or response.status == expected_status,
                        "headers": dict(response.headers)
                    }
                    
            elif method.upper() == "POST":
                async with self.session.post(url, json=data, headers=headers) as response:
                    response_time = (time.time() - start_time) * 1000
                    content = await response.text()
                    return {
                        "url": url,
                        "status": response.status,
                        "response_time_ms": round(response_time, 2),
                        "content": content[:500] if content else "",
                        "success": expected_status is None or response.status == expected_status,
                        "headers": dict(response.headers)
                    }
                    
        except asyncio.TimeoutError:
            return {
                "url": url,
                "status": 0,
                "response_time_ms": timeout * 1000,
                "content": "Request timed out",
                "success": False,
                "error": "timeout"
            }
        except Exception as e:
            return {
                "url": url,
                "status": 0,
                "response_time_ms": 0,
                "content": str(e),
                "success": False,
                "error": str(e)
            }

    async def check_server_health(self) -> Dict:
        """Check basic server health"""
        logger.info("🔍 Checking server health...")
        
        # Test root endpoint
        root_result = await self.test_endpoint("/")
        
        # Test health endpoint
        health_result = await self.test_endpoint("/health")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "root_endpoint": root_result,
            "health_endpoint": health_result,
            "server_accessible": root_result["success"] and root_result["status"] == 200
        }

    async def test_api_endpoints(self) -> Dict:
        """Test various API endpoints to check availability"""
        logger.info("🔍 Testing API endpoints...")
        
        endpoints_to_test = [
            ("/api/auth/health", "GET", None, 404),  # May not exist
            ("/api/users/me", "GET", None, 401),     # Should require auth
            ("/api/health", "GET", None, None),      # General health
            ("/api/auth/register", "POST", {"email": "test@example.com"}, None),  # Should validate
        ]
        
        results = {}
        
        for path, method, data, expected_status in endpoints_to_test:
            logger.info(f"  Testing {method} {path}")
            result = await self.test_endpoint(path, method, data, expected_status=expected_status)
            results[f"{method} {path}"] = result
            
        return {
            "timestamp": datetime.now().isoformat(),
            "endpoint_tests": results,
            "api_accessible": any(r["success"] for r in results.values())
        }

    async def test_authentication_flow(self) -> Dict:
        """Test complete authentication flow"""
        logger.info("🔐 Testing authentication flow...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "registration": {},
            "login": {},
            "protected_endpoint": {},
            "token_refresh": {},
            "success": False
        }
        
        # Test registration
        registration_data = {
            "email": f"test_{int(time.time())}@mita.finance",
            "password": "TestPassword123!",
            "password_confirm": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User"
        }
        
        logger.info("  Testing user registration...")
        reg_result = await self.test_endpoint(
            "/api/auth/register", 
            "POST", 
            registration_data,
            expected_status=201
        )
        results["registration"] = reg_result
        
        # If registration successful, test login
        if reg_result.get("status") == 201:
            logger.info("  Testing user login...")
            login_data = {
                "email": registration_data["email"],
                "password": registration_data["password"]
            }
            
            login_result = await self.test_endpoint(
                "/api/auth/login",
                "POST",
                login_data,
                expected_status=200
            )
            results["login"] = login_result
            
            # If login successful, test protected endpoint
            if login_result.get("status") == 200:
                try:
                    login_response = json.loads(login_result["content"])
                    access_token = login_response.get("access_token")
                    
                    if access_token:
                        logger.info("  Testing protected endpoint...")
                        headers = {"Authorization": f"Bearer {access_token}"}
                        
                        protected_result = await self.test_endpoint(
                            "/api/users/me",
                            "GET",
                            headers=headers,
                            expected_status=200
                        )
                        results["protected_endpoint"] = protected_result
                        
                        # Test token refresh if available
                        refresh_token = login_response.get("refresh_token")
                        if refresh_token:
                            logger.info("  Testing token refresh...")
                            refresh_result = await self.test_endpoint(
                                "/api/auth/refresh",
                                "POST",
                                {"refresh_token": refresh_token},
                                expected_status=200
                            )
                            results["token_refresh"] = refresh_result
                            
                except json.JSONDecodeError:
                    logger.error("Failed to parse login response")
        
        # Determine overall success
        results["success"] = (
            results["registration"].get("success", False) and 
            results["login"].get("success", False)
        )
        
        return results

    async def monitor_deployment(self, interval: int = 30, max_attempts: int = 20) -> None:
        """Monitor deployment until server is fully operational"""
        logger.info(f"🚀 Starting deployment monitoring (checking every {interval}s, max {max_attempts} attempts)")
        
        attempts = 0
        
        while attempts < max_attempts:
            attempts += 1
            logger.info(f"\n--- Attempt {attempts}/{max_attempts} ---")
            
            # Check server health
            health_status = await self.check_server_health()
            
            if health_status["server_accessible"]:
                logger.info("✅ Server is accessible!")
                
                # Test API endpoints
                api_status = await self.test_api_endpoints()
                
                if any(r["status"] not in [500, 0] for r in api_status["endpoint_tests"].values()):
                    logger.info("✅ API endpoints are responding!")
                    
                    # Test authentication flow
                    auth_status = await self.test_authentication_flow()
                    
                    if auth_status["success"]:
                        logger.info("🎉 Authentication system is working!")
                        logger.info("🎯 Deployment monitoring complete - server is fully operational")
                        return
                    else:
                        logger.warning("⚠️ Authentication system not yet working")
                else:
                    logger.warning("⚠️ API endpoints returning errors")
            else:
                logger.warning("❌ Server not yet accessible")
            
            if attempts < max_attempts:
                logger.info(f"⏳ Waiting {interval} seconds before next check...")
                await asyncio.sleep(interval)
        
        logger.error("❌ Maximum attempts reached - server may still be deploying")

    async def generate_curl_commands(self) -> List[str]:
        """Generate curl commands for testing authentication endpoints"""
        base_url = self.base_url
        
        commands = [
            # Health checks
            f'# Health check commands',
            f'curl -X GET "{base_url}/" -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"',
            f'curl -X GET "{base_url}/health" -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"',
            '',
            
            # Registration
            f'# User registration',
            f'''curl -X POST "{base_url}/api/auth/register" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "email": "test@mita.finance",
    "password": "TestPassword123!",
    "password_confirm": "TestPassword123!",
    "first_name": "Test",
    "last_name": "User"
  }}' \\
  -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"''',
            '',
            
            # Login
            f'# User login',
            f'''curl -X POST "{base_url}/api/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "email": "test@mita.finance",
    "password": "TestPassword123!"
  }}' \\
  -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"''',
            '',
            
            # Protected endpoint test
            f'# Test protected endpoint (replace TOKEN with actual token)',
            f'''curl -X GET "{base_url}/api/users/me" \\
  -H "Authorization: Bearer TOKEN" \\
  -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"''',
            '',
            
            # Token refresh
            f'# Token refresh (replace REFRESH_TOKEN with actual refresh token)',
            f'''curl -X POST "{base_url}/api/auth/refresh" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "refresh_token": "REFRESH_TOKEN"
  }}' \\
  -w "\\nStatus: %{{http_code}}\\nTime: %{{time_total}}s\\n"''',
            '',
            
            # Performance test
            f'# Performance test with timing',
            f'''curl -X GET "{base_url}/" \\
  -w "DNS: %{{time_namelookup}}s\\nConnect: %{{time_connect}}s\\nSSL: %{{time_appconnect}}s\\nTransfer: %{{time_pretransfer}}s\\nTotal: %{{time_total}}s\\nSize: %{{size_download}} bytes\\n"''',
            '',
            
            # Load test example
            f'# Load test (run multiple concurrent requests)',
            f'for i in {{1..10}}; do curl -X GET "{base_url}/" & done; wait',
            ''
        ]
        
        return commands


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Monitor MITA Finance API deployment")
    parser.add_argument("--url", default=PRODUCTION_BASE_URL, help="Base URL to monitor")
    parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--max-attempts", type=int, default=20, help="Maximum number of attempts")
    parser.add_argument("--test-auth", action="store_true", help="Run authentication test immediately")
    parser.add_argument("--generate-curl", action="store_true", help="Generate curl commands")
    parser.add_argument("--quick-check", action="store_true", help="Run a quick health check only")
    
    args = parser.parse_args()
    
    async with DeploymentMonitor(args.url) as monitor:
        
        if args.generate_curl:
            logger.info("📋 Generating curl commands...")
            commands = await monitor.generate_curl_commands()
            
            print("\n" + "="*60)
            print("CURL COMMANDS FOR TESTING AUTHENTICATION")
            print("="*60)
            
            for command in commands:
                print(command)
            
            print("="*60)
            return
        
        if args.quick_check:
            logger.info("🔍 Running quick health check...")
            health_status = await monitor.check_server_health()
            
            if health_status["server_accessible"]:
                logger.info("✅ Server is accessible!")
                
                # Try a quick API test
                api_status = await monitor.test_api_endpoints()
                responding_endpoints = sum(
                    1 for r in api_status["endpoint_tests"].values() 
                    if r["status"] not in [0, 500]
                )
                
                logger.info(f"📊 {responding_endpoints} out of {len(api_status['endpoint_tests'])} API endpoints responding")
                
            else:
                logger.error("❌ Server is not accessible")
            return
        
        if args.test_auth:
            logger.info("🔐 Running authentication test...")
            auth_status = await monitor.test_authentication_flow()
            
            if auth_status["success"]:
                logger.info("🎉 Authentication system is working!")
            else:
                logger.error("❌ Authentication system has issues")
                
                # Print detailed results
                for step, result in auth_status.items():
                    if isinstance(result, dict) and "status" in result:
                        status_emoji = "✅" if result.get("success") else "❌"
                        logger.info(f"  {status_emoji} {step}: Status {result['status']}")
            return
        
        # Default: Monitor deployment
        await monitor.monitor_deployment(args.interval, args.max_attempts)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Monitoring failed: {e}")
        sys.exit(1)