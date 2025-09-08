#!/usr/bin/env python3
"""
MITA Finance Authentication Debug Tool
Comprehensive testing and debugging of authentication endpoints
"""

import asyncio
import httpx
import time
import json
import logging
import os
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MITAAuthDebugger:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("API_BASE_URL", "https://mita-api.onrender.com")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = []
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def log_result(self, test_name: str, success: bool, details: Dict, duration_ms: float):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
            "details": details
        }
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name} ({duration_ms:.0f}ms)")
        
        if not success:
            logger.error(f"   Error: {details.get('error', 'Unknown error')}")
        elif 'response_time' in details:
            logger.info(f"   Response time: {details['response_time']:.0f}ms")

    async def test_server_health(self) -> bool:
        """Test if server is reachable"""
        start_time = time.time()
        success = False
        details = {}
        
        # Try multiple health endpoints
        health_endpoints = [
            "/api/health",
            "/health", 
            "/api/auth/emergency-diagnostics",
            "/"
        ]
        
        for endpoint in health_endpoints:
            try:
                response = await self.client.get(f"{self.base_url}{endpoint}")
                duration_ms = (time.time() - start_time) * 1000
                
                if response.status_code in [200, 404]:  # 404 is fine, means server is up
                    success = True
                    details = {
                        "status_code": response.status_code,
                        "response_time": duration_ms,
                        "endpoint": endpoint,
                        "response": response.text[:200]
                    }
                    break
                else:
                    details = {
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                        "endpoint": endpoint,
                        "response": response.text[:200]
                    }
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                details = {"error": str(e), "exception_type": type(e).__name__, "endpoint": endpoint}
                continue
        
        self.log_result("Server Health Check", success, details, duration_ms)
        return success

    async def test_auth_diagnostics(self) -> Dict:
        """Test emergency diagnostics endpoint"""
        start_time = time.time()
        success = False
        details = {}
        
        try:
            response = await self.client.get(f"{self.base_url}/api/auth/emergency-diagnostics")
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                success = True
                data = response.json()
                details = {
                    "status_code": response.status_code,
                    "response_time": duration_ms,
                    "diagnostics": data.get("diagnostics", {}),
                    "server_status": data.get("status", "unknown")
                }
            else:
                details = {
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:500]
                }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            details = {"error": str(e), "exception_type": type(e).__name__}
        
        self.log_result("Authentication Diagnostics", success, details, duration_ms)
        return details

    async def test_user_registration(self, test_user: Dict) -> Optional[Dict]:
        """Test user registration"""
        start_time = time.time()
        success = False
        details = {}
        tokens = None
        
        try:
            # Try emergency register first (fastest)
            response = await self.client.post(
                f"{self.base_url}/api/auth/emergency-register",
                json=test_user,
                headers={"Content-Type": "application/json"}
            )
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code in [200, 201]:
                success = True
                data = response.json()
                tokens = {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "token_type": data.get("token_type", "bearer")
                }
                details = {
                    "status_code": response.status_code,
                    "response_time": duration_ms,
                    "endpoint": "emergency-register",
                    "user_id": data.get("user_id"),
                    "has_tokens": bool(tokens["access_token"])
                }
            else:
                details = {
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:500],
                    "endpoint": "emergency-register"
                }
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            details = {"error": str(e), "exception_type": type(e).__name__}
        
        self.log_result("User Registration", success, details, duration_ms)
        return tokens

    async def test_user_login(self, email: str, password: str) -> Optional[Dict]:
        """Test user login"""
        start_time = time.time()
        success = False
        details = {}
        tokens = None
        
        try:
            login_data = {"email": email, "password": password}
            
            # Test main login endpoint
            response = await self.client.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                success = True
                data = response.json()
                tokens = {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "token_type": data.get("token_type", "bearer")
                }
                details = {
                    "status_code": response.status_code,
                    "response_time": duration_ms,
                    "has_tokens": bool(tokens["access_token"]),
                    "endpoint": "login"
                }
            else:
                details = {
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:500],
                    "endpoint": "login"
                }
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            details = {"error": str(e), "exception_type": type(e).__name__}
        
        self.log_result("User Login", success, details, duration_ms)
        return tokens

    async def test_token_validation(self, access_token: str) -> bool:
        """Test token validation with protected endpoint"""
        start_time = time.time()
        success = False
        details = {}
        
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Try to access a protected endpoint
            response = await self.client.get(
                f"{self.base_url}/api/users/me",
                headers=headers
            )
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                success = True
                data = response.json()
                details = {
                    "status_code": response.status_code,
                    "response_time": duration_ms,
                    "user_data": data.get("data", {}) if isinstance(data, dict) else {}
                }
            else:
                details = {
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:500]
                }
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            details = {"error": str(e), "exception_type": type(e).__name__}
        
        self.log_result("Token Validation", success, details, duration_ms)
        return success

    async def test_password_performance(self) -> Dict:
        """Test password hashing performance"""
        start_time = time.time()
        success = False
        details = {}
        
        try:
            response = await self.client.get(f"{self.base_url}/api/auth/security/password-config")
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                success = True
                data = response.json()
                details = {
                    "status_code": response.status_code,
                    "response_time": duration_ms,
                    "performance": data.get("data", {}).get("performance_test", {}),
                    "config": data.get("data", {}).get("configuration", {})
                }
            else:
                details = {
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:500]
                }
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            details = {"error": str(e), "exception_type": type(e).__name__}
        
        self.log_result("Password Performance Test", success, details, duration_ms)
        return details

    async def run_comprehensive_test(self):
        """Run all authentication tests"""
        logger.info("🚀 Starting MITA Authentication Debug Session")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info("=" * 60)
        
        # 1. Test server health
        if not await self.test_server_health():
            logger.error("❌ Server unreachable - aborting tests")
            return self.generate_report()
        
        # 2. Test authentication diagnostics
        diagnostics = await self.test_auth_diagnostics()
        
        # 3. Test password performance
        await self.test_password_performance()
        
        # 4. Test user registration
        test_user = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123!",
            "country": "US",
            "annual_income": 50000,
            "timezone": "America/New_York"
        }
        
        tokens = await self.test_user_registration(test_user)
        
        # 5. Test login with the created user
        if tokens:
            await self.test_user_login(test_user["email"], test_user["password"])
            await self.test_token_validation(tokens["access_token"])
        else:
            logger.warning("⚠️  Skipping login test - registration failed")
        
        # 6. Test login with potential existing users
        common_test_emails = [
            "test@example.com",
            "admin@example.com", 
            "user@example.com"
        ]
        
        for email in common_test_emails:
            logger.info(f"🔍 Testing common email: {email}")
            login_tokens = await self.test_user_login(email, "TestPassword123!")
            if login_tokens:
                await self.test_token_validation(login_tokens["access_token"])
                break
        
        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate comprehensive test report"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        
        # Analyze performance
        auth_tests = [r for r in self.results if "login" in r["test"].lower() or "register" in r["test"].lower()]
        avg_auth_time = sum(r["duration_ms"] for r in auth_tests) / len(auth_tests) if auth_tests else 0
        
        # Identify critical issues
        critical_issues = []
        for result in self.results:
            if not result["success"]:
                if "server health" in result["test"].lower():
                    critical_issues.append("Server unreachable")
                elif "login" in result["test"].lower():
                    critical_issues.append("Login endpoint failing")
                elif "register" in result["test"].lower():
                    critical_issues.append("Registration endpoint failing")
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "avg_auth_time_ms": avg_auth_time,
                "critical_issues": critical_issues
            },
            "detailed_results": self.results,
            "recommendations": self.get_recommendations(),
            "generated_at": time.time()
        }
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 AUTHENTICATION DEBUG REPORT")
        logger.info("=" * 60)
        logger.info(f"Tests: {passed_tests}/{total_tests} passed ({report['summary']['success_rate']:.1f}%)")
        logger.info(f"Average auth time: {avg_auth_time:.0f}ms")
        
        if critical_issues:
            logger.error("🚨 CRITICAL ISSUES:")
            for issue in critical_issues:
                logger.error(f"   • {issue}")
        
        recommendations = report["recommendations"]
        if recommendations:
            logger.info("💡 RECOMMENDATIONS:")
            for rec in recommendations:
                logger.info(f"   • {rec}")
        
        return report

    def get_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for slow authentication
        auth_tests = [r for r in self.results if "login" in r["test"].lower() or "register" in r["test"].lower()]
        if auth_tests:
            avg_time = sum(r["duration_ms"] for r in auth_tests) / len(auth_tests)
            if avg_time > 1000:
                recommendations.append(f"Authentication is slow ({avg_time:.0f}ms) - optimize bcrypt rounds or use async operations")
        
        # Check for failed endpoints
        failed_tests = [r for r in self.results if not r["success"]]
        if any("login" in r["test"].lower() for r in failed_tests):
            recommendations.append("Fix login endpoint - check password verification logic")
        
        if any("register" in r["test"].lower() for r in failed_tests):
            recommendations.append("Fix registration endpoint - check user creation logic")
        
        # Check performance stats
        perf_test = next((r for r in self.results if "password performance" in r["test"].lower()), None)
        if perf_test and perf_test["success"]:
            perf_data = perf_test["details"].get("performance", {})
            if perf_data.get("average_ms", 0) > 500:
                recommendations.append("Password hashing is slow - consider adjusting bcrypt rounds")
        
        return recommendations


async def main():
    """Main debug function"""
    base_url = os.getenv("MITA_API_URL", "https://mita-api.onrender.com")
    
    async with MITAAuthDebugger(base_url) as debugger:
        report = await debugger.run_comprehensive_test()
        
        # Save detailed report
        with open("auth_debug_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info("📄 Detailed report saved to: auth_debug_report.json")
        
        return report


if __name__ == "__main__":
    asyncio.run(main())