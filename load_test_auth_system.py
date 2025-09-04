#!/usr/bin/env python3
"""
MITA Finance Authentication Load Testing Suite
Comprehensive load testing to validate restored authentication system performance
"""

import asyncio
import aiohttp
import time
import json
import random
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Individual test result data"""
    endpoint: str
    status_code: int
    response_time_ms: float
    success: bool
    error: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    base_url: str = "http://localhost:8000"
    concurrent_users: int = 50
    test_duration_seconds: int = 300  # 5 minutes
    ramp_up_seconds: int = 30
    test_data_file: str = "load_test_data.json"
    
    # Authentication endpoints to test - ALL CRITICAL ENDPOINTS
    endpoints = {
        "register": "/auth/register",
        "register_fast": "/auth/register-fast",
        "emergency_register": "/auth/emergency-register",
        "register_full": "/auth/register-full",
        "login": "/auth/login", 
        "refresh": "/auth/refresh",
        "logout": "/auth/logout",
        "revoke": "/auth/revoke",
        "validate": "/auth/token/validate",
        "password_reset_request": "/auth/password-reset/request",
        "google_auth": "/auth/google",
        "security_status": "/auth/security/status",
        "emergency_diagnostics": "/auth/emergency-diagnostics"
    }
    
    # Rate limiting expectations (requests per time window)
    rate_limits = {
        "auth_login": {"limit": 5, "window": 900},  # 5 per 15 minutes
        "auth_register": {"limit": 3, "window": 3600},  # 3 per hour
        "auth_password_reset": {"limit": 3, "window": 1800},  # 3 per 30 minutes
        "auth_token_refresh": {"limit": 20, "window": 300},  # 20 per 5 minutes
        "api_general": {"limit": 1000, "window": 3600},  # 1000 per hour
        "emergency_endpoints": {"limit": 100, "window": 3600}  # Emergency endpoints should have higher limits
    }

class AuthLoadTester:
    """Comprehensive authentication load testing"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.active_sessions = {}
        self.test_users = []
        self.start_time = None
        self.end_time = None
        
    def generate_test_data(self) -> Dict[str, Any]:
        """Generate realistic test data for load testing"""
        
        timestamp = int(time.time())
        test_users = []
        
        # Generate users for different scenarios
        for i in range(self.config.concurrent_users * 2):  # Extra users for variety
            user = {
                "email": f"loadtest_user_{timestamp}_{i}@example.com",
                "password": f"LoadTest123_{i}",
                "first_name": f"Load{i}",
                "last_name": f"Test{i}",
                "phone_number": f"+1555010{i:04d}"
            }
            test_users.append(user)
        
        test_data = {
            "users": test_users,
            "test_timestamp": timestamp,
            "config": asdict(self.config)
        }
        
        # Save test data for reproducibility
        with open(self.config.test_data_file, 'w') as f:
            json.dump(test_data, f, indent=2)
            
        self.test_users = test_users
        logger.info(f"Generated {len(test_users)} test users")
        return test_data
    
    async def create_session(self) -> aiohttp.ClientSession:
        """Create HTTP session with appropriate settings"""
        
        timeout = aiohttp.ClientTimeout(
            total=30,  # Total timeout
            connect=10,  # Connection timeout
            sock_read=20  # Socket read timeout
        )
        
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection limit
            limit_per_host=50,  # Per-host connection limit
            keepalive_timeout=30
        )
        
        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "MITA-LoadTester/1.0"}
        )
    
    async def test_user_registration(self, session: aiohttp.ClientSession, user_data: Dict) -> TestResult:
        """Test user registration endpoint"""
        
        start_time = time.time()
        
        try:
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['register']}",
                json=user_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                response_data = await response.json()
                
                success = response.status in [200, 201]
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                return TestResult(
                    endpoint="register",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_data["email"]
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="register",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_data["email"]
            )
    
    async def test_user_login(self, session: aiohttp.ClientSession, user_data: Dict) -> TestResult:
        """Test user login endpoint"""
        
        start_time = time.time()
        
        try:
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['login']}",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                response_data = await response.json()
                
                success = response.status == 200
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                # Store session for subsequent tests
                if success and "access_token" in response_data:
                    self.active_sessions[user_data["email"]] = {
                        "access_token": response_data["access_token"],
                        "refresh_token": response_data.get("refresh_token"),
                        "login_time": time.time()
                    }
                
                return TestResult(
                    endpoint="login",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_data["email"]
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="login",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_data["email"]
            )
    
    async def test_token_refresh(self, session: aiohttp.ClientSession, user_email: str) -> TestResult:
        """Test token refresh endpoint"""
        
        start_time = time.time()
        
        try:
            if user_email not in self.active_sessions:
                return TestResult(
                    endpoint="refresh",
                    status_code=0,
                    response_time_ms=0,
                    success=False,
                    error="No active session",
                    user_id=user_email
                )
            
            session_data = self.active_sessions[user_email]
            refresh_data = {"refresh_token": session_data["refresh_token"]}
            
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['refresh']}",
                json=refresh_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                response_data = await response.json()
                
                success = response.status == 200
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                # Update session with new tokens
                if success and "access_token" in response_data:
                    self.active_sessions[user_email].update({
                        "access_token": response_data["access_token"],
                        "refresh_token": response_data.get("refresh_token", session_data["refresh_token"])
                    })
                
                return TestResult(
                    endpoint="refresh",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_email
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="refresh",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_email
            )
    
    async def test_logout(self, session: aiohttp.ClientSession, user_email: str) -> TestResult:
        """Test user logout endpoint"""
        
        start_time = time.time()
        
        try:
            if user_email not in self.active_sessions:
                return TestResult(
                    endpoint="logout",
                    status_code=0,
                    response_time_ms=0,
                    success=False,
                    error="No active session",
                    user_id=user_email
                )
            
            session_data = self.active_sessions[user_email]
            headers = {
                "Authorization": f"Bearer {session_data['access_token']}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['logout']}",
                headers=headers
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                
                try:
                    response_data = await response.json()
                except:
                    response_data = {"message": "No JSON response"}
                
                success = response.status in [200, 202]
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                # Clear session after logout
                if success and user_email in self.active_sessions:
                    del self.active_sessions[user_email]
                
                return TestResult(
                    endpoint="logout",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_email
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="logout",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_email
            )
    
    async def test_emergency_register(self, session: aiohttp.ClientSession, user_data: Dict) -> TestResult:
        """Test emergency registration endpoint specifically"""
        
        start_time = time.time()
        
        try:
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['emergency_register']}",
                json=user_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                
                try:
                    response_data = await response.json()
                except:
                    response_data = {"detail": "No JSON response"}
                
                success = response.status in [200, 201]
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                # Store session for subsequent tests
                if success and "access_token" in response_data:
                    self.active_sessions[user_data["email"]] = {
                        "access_token": response_data["access_token"],
                        "refresh_token": response_data.get("refresh_token"),
                        "login_time": time.time()
                    }
                
                return TestResult(
                    endpoint="emergency_register",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_data["email"]
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="emergency_register",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_data["email"]
            )
    
    async def test_token_validate(self, session: aiohttp.ClientSession, user_email: str) -> TestResult:
        """Test token validation endpoint"""
        
        start_time = time.time()
        
        try:
            if user_email not in self.active_sessions:
                return TestResult(
                    endpoint="validate",
                    status_code=0,
                    response_time_ms=0,
                    success=False,
                    error="No active session",
                    user_id=user_email
                )
            
            session_data = self.active_sessions[user_email]
            headers = {
                "Authorization": f"Bearer {session_data['access_token']}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{self.config.base_url}{self.config.endpoints['validate']}",
                headers=headers
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                
                try:
                    response_data = await response.json()
                except:
                    response_data = {"detail": "No JSON response"}
                
                success = response.status == 200
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                return TestResult(
                    endpoint="validate",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_email
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="validate",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_email
            )
    
    async def test_rate_limiting_specifically(self, session: aiohttp.ClientSession, endpoint: str) -> List[TestResult]:
        """Test rate limiting for specific endpoint by making rapid requests"""
        
        results = []
        test_user = self.test_users[0]  # Use first test user
        
        # Make requests rapidly to trigger rate limiting
        rate_limit_info = self.config.rate_limits.get(endpoint.split('_')[1], {"limit": 10, "window": 60})
        requests_to_make = rate_limit_info["limit"] + 5  # Exceed the limit
        
        for i in range(requests_to_make):
            start_time = time.time()
            
            try:
                if endpoint == "auth_login":
                    login_data = {
                        "email": test_user["email"],
                        "password": test_user["password"]
                    }
                    
                    async with session.post(
                        f"{self.config.base_url}/auth/login",
                        json=login_data,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        response_time = (time.time() - start_time) * 1000
                        
                        success = response.status not in [429]  # 429 is expected after rate limit
                        error = f"Rate limit test {i+1}" if response.status == 429 else None
                        
                        results.append(TestResult(
                            endpoint=f"rate_limit_test_{endpoint}",
                            status_code=response.status,
                            response_time_ms=response_time,
                            success=success,
                            error=error,
                            user_id=test_user["email"]
                        ))
                        
                        # If we get rate limited, that's actually good - the system is working
                        if response.status == 429:
                            logger.info(f"Rate limiting triggered correctly after {i+1} requests")
                            break
                
                # Small delay between requests
                await asyncio.sleep(0.1)
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                results.append(TestResult(
                    endpoint=f"rate_limit_test_{endpoint}",
                    status_code=0,
                    response_time_ms=response_time,
                    success=False,
                    error=str(e),
                    user_id=test_user["email"]
                ))
        
        return results
    
    async def test_password_reset_request(self, session: aiohttp.ClientSession, user_data: Dict) -> TestResult:
        """Test password reset request endpoint"""
        
        start_time = time.time()
        
        try:
            reset_data = {"email": user_data["email"]}
            
            async with session.post(
                f"{self.config.base_url}{self.config.endpoints['password_reset_request']}",
                json=reset_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                response_time = (time.time() - start_time) * 1000
                response_data = await response.json()
                
                success = response.status in [200, 202]  # Accept both success and accepted
                error = None if success else response_data.get("detail", f"HTTP {response.status}")
                
                return TestResult(
                    endpoint="password_reset_request",
                    status_code=response.status,
                    response_time_ms=response_time,
                    success=success,
                    error=error,
                    user_id=user_data["email"]
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                endpoint="password_reset_request",
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e),
                user_id=user_data["email"]
            )
    
    async def simulate_user_workflow(self, user_index: int) -> List[TestResult]:
        """Simulate realistic user authentication workflow"""
        
        workflow_results = []
        user_data = self.test_users[user_index % len(self.test_users)]
        
        async with await self.create_session() as session:
            
            # Step 1: Register user (if not testing existing users)
            if random.random() < 0.7:  # 70% of users register
                result = await self.test_user_registration(session, user_data)
                workflow_results.append(result)
                
                # Small delay between registration and login
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Step 2: Login user
            result = await self.test_user_login(session, user_data)
            workflow_results.append(result)
            
            if result.success:
                # Step 3: Random actions during session
                for _ in range(random.randint(2, 8)):  # 2-8 actions per user
                    action = random.choice(["refresh", "password_reset", "validate", "logout", "idle"])
                    
                    if action == "refresh" and random.random() < 0.3:  # 30% chance to refresh
                        result = await self.test_token_refresh(session, user_data["email"])
                        workflow_results.append(result)
                    
                    elif action == "password_reset" and random.random() < 0.1:  # 10% chance
                        result = await self.test_password_reset_request(session, user_data)
                        workflow_results.append(result)
                    
                    elif action == "validate" and random.random() < 0.2:  # 20% chance to validate token
                        result = await self.test_token_validate(session, user_data["email"])
                        workflow_results.append(result)
                    
                    elif action == "logout" and random.random() < 0.15:  # 15% chance to logout
                        result = await self.test_logout(session, user_data["email"])
                        workflow_results.append(result)
                        # If we logged out, break the workflow
                        if result.success:
                            break
                    
                    # Random delay between actions
                    await asyncio.sleep(random.uniform(1.0, 5.0))
                    
            # Step 4: Test emergency endpoint occasionally
            if random.random() < 0.1:  # 10% chance to test emergency endpoint
                emergency_user = {
                    "email": f"emergency_{user_data['email']}",
                    "password": user_data["password"],
                    "country": user_data.get("country", "US"),
                    "annual_income": user_data.get("annual_income", 0),
                    "timezone": user_data.get("timezone", "UTC")
                }
                result = await self.test_emergency_register(session, emergency_user)
                workflow_results.append(result)
        
        return workflow_results
    
    async def run_rate_limiting_test(self) -> Dict[str, Any]:
        """Run specific rate limiting validation tests"""
        
        logger.info("Starting dedicated rate limiting tests...")
        rate_limit_results = []
        
        async with await self.create_session() as session:
            # Test login rate limiting
            logger.info("Testing login rate limiting...")
            login_results = await self.test_rate_limiting_specifically(session, "auth_login")
            rate_limit_results.extend(login_results)
            
            # Wait between tests to avoid interference
            await asyncio.sleep(5)
            
        return {
            "rate_limit_tests": len(rate_limit_results),
            "rate_limit_429_responses": len([r for r in rate_limit_results if r.status_code == 429]),
            "rate_limiting_working": any(r.status_code == 429 for r in rate_limit_results),
            "results": [{
                "endpoint": r.endpoint,
                "status_code": r.status_code,
                "response_time_ms": r.response_time_ms,
                "success": r.success,
                "error": r.error
            } for r in rate_limit_results]
        }
    
    async def run_middleware_stress_test(self) -> Dict[str, Any]:
        """Test middleware components under concurrent load"""
        
        logger.info("Starting middleware stress test...")
        
        async def stress_endpoint(endpoint_name: str, num_requests: int = 20):
            results = []
            async with await self.create_session() as session:
                tasks = []
                
                for i in range(num_requests):
                    if endpoint_name == "emergency_diagnostics":
                        task = session.get(f"{self.config.base_url}/auth/emergency-diagnostics")
                    elif endpoint_name == "security_status":
                        task = session.get(f"{self.config.base_url}/auth/security/status")
                    else:
                        continue
                    
                    tasks.append(task)
                
                # Execute all requests concurrently
                start_time = time.time()
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                total_time = time.time() - start_time
                
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        results.append({
                            "request_id": i,
                            "status_code": 0,
                            "success": False,
                            "error": str(response),
                            "response_time_ms": total_time * 1000 / num_requests
                        })
                    else:
                        results.append({
                            "request_id": i,
                            "status_code": response.status,
                            "success": response.status == 200,
                            "error": None,
                            "response_time_ms": total_time * 1000 / num_requests
                        })
                        response.close()
            
            return results
        
        # Test multiple endpoints concurrently
        diagnostics_results = await stress_endpoint("emergency_diagnostics", 10)
        status_results = await stress_endpoint("security_status", 10)
        
        return {
            "middleware_stress_test": {
                "diagnostics_endpoint": {
                    "total_requests": len(diagnostics_results),
                    "successful_requests": len([r for r in diagnostics_results if r["success"]]),
                    "average_response_time_ms": sum(r["response_time_ms"] for r in diagnostics_results) / len(diagnostics_results) if diagnostics_results else 0,
                    "error_rate_percent": (len([r for r in diagnostics_results if not r["success"]]) / len(diagnostics_results) * 100) if diagnostics_results else 0
                },
                "security_status_endpoint": {
                    "total_requests": len(status_results),
                    "successful_requests": len([r for r in status_results if r["success"]]),
                    "average_response_time_ms": sum(r["response_time_ms"] for r in status_results) / len(status_results) if status_results else 0,
                    "error_rate_percent": (len([r for r in status_results if not r["success"]]) / len(status_results) * 100) if status_results else 0
                }
            }
        }
    
    async def run_load_test(self) -> Dict[str, Any]:
        """Execute comprehensive load test"""
        
        logger.info(f"Starting load test with {self.config.concurrent_users} concurrent users")
        logger.info(f"Test duration: {self.config.test_duration_seconds}s")
        logger.info(f"Target endpoints: {list(self.config.endpoints.keys())}")
        
        # Generate test data
        self.generate_test_data()
        
        self.start_time = time.time()
        
        # Create tasks for concurrent users
        tasks = []
        
        # Stagger user start times (ramp-up)
        for user_index in range(self.config.concurrent_users):
            delay = (user_index / self.config.concurrent_users) * self.config.ramp_up_seconds
            task = asyncio.create_task(self._run_user_workflow(user_index, delay))
            tasks.append(task)
        
        logger.info(f"Created {len(tasks)} user workflow tasks")
        
        # Wait for all users to complete or timeout
        try:
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Flatten results and handle exceptions
            for user_results in all_results:
                if isinstance(user_results, Exception):
                    logger.error(f"User workflow exception: {user_results}")
                elif isinstance(user_results, list):
                    self.results.extend(user_results)
        
        except Exception as e:
            logger.error(f"Load test execution error: {e}")
        
        self.end_time = time.time()
        
        # Analyze results
        return self.analyze_results()
    
    async def _run_user_workflow(self, user_index: int, start_delay: float) -> List[TestResult]:
        """Run individual user workflow with delay and duration control"""
        
        # Wait for ramp-up delay
        await asyncio.sleep(start_delay)
        
        workflow_results = []
        user_start_time = time.time()
        
        try:
            # Run user workflow until test duration expires
            while (time.time() - self.start_time) < self.config.test_duration_seconds:
                batch_results = await self.simulate_user_workflow(user_index)
                workflow_results.extend(batch_results)
                
                # Break if we've hit any major errors
                if len([r for r in batch_results if not r.success]) > 3:
                    logger.warning(f"User {user_index} stopping due to repeated failures")
                    break
                
                # Random delay between workflow cycles
                await asyncio.sleep(random.uniform(10, 30))
        
        except Exception as e:
            logger.error(f"User {user_index} workflow error: {e}")
        
        user_duration = time.time() - user_start_time
        logger.info(f"User {user_index} completed: {len(workflow_results)} requests in {user_duration:.1f}s")
        
        return workflow_results
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze load test results and generate comprehensive report"""
        
        if not self.results:
            return {"error": "No results to analyze"}
        
        total_duration = self.end_time - self.start_time
        
        # Basic statistics
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if r.success])
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Performance metrics
        response_times = [r.response_time_ms for r in self.results if r.success]
        
        performance_metrics = {}
        if response_times:
            performance_metrics = {
                "avg_response_time_ms": statistics.mean(response_times),
                "median_response_time_ms": statistics.median(response_times),
                "p95_response_time_ms": self._percentile(response_times, 95),
                "p99_response_time_ms": self._percentile(response_times, 99),
                "min_response_time_ms": min(response_times),
                "max_response_time_ms": max(response_times)
            }
        
        # Endpoint-specific analysis
        endpoint_stats = {}
        all_endpoints = set(r.endpoint for r in self.results)
        
        for endpoint in all_endpoints:
            endpoint_results = [r for r in self.results if r.endpoint == endpoint]
            if endpoint_results:
                endpoint_success = len([r for r in endpoint_results if r.success])
                successful_times = [r.response_time_ms for r in endpoint_results if r.success]
                endpoint_stats[endpoint] = {
                    "total_requests": len(endpoint_results),
                    "successful_requests": endpoint_success,
                    "success_rate": (endpoint_success / len(endpoint_results) * 100),
                    "avg_response_time_ms": statistics.mean(successful_times) if successful_times else 0,
                    "p95_response_time_ms": self._percentile(successful_times, 95) if successful_times else 0,
                    "errors": [r.error for r in endpoint_results if not r.success and r.error]
                }
        
        # Rate limiting analysis
        rate_limit_violations = len([r for r in self.results if r.status_code == 429])
        
        # Error analysis
        error_types = {}
        for result in self.results:
            if not result.success and result.error:
                error_types[result.error] = error_types.get(result.error, 0) + 1
        
        # Throughput calculation
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        
        analysis = {
            "test_summary": {
                "concurrent_users": self.config.concurrent_users,
                "test_duration_seconds": total_duration,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate_percent": success_rate,
                "requests_per_second": requests_per_second,
                "rate_limit_violations": rate_limit_violations
            },
            "performance_metrics": performance_metrics,
            "endpoint_statistics": endpoint_stats,
            "error_analysis": error_types,
            "rate_limiting_analysis": {
                "violations_count": rate_limit_violations,
                "violations_percentage": (rate_limit_violations / total_requests * 100) if total_requests > 0 else 0
            },
            "recommendations": self._generate_recommendations(success_rate, performance_metrics, rate_limit_violations, total_requests)
        }
        
        return analysis
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile / 100
        f = int(k)
        c = k - f
        if f == len(sorted_values) - 1:
            return sorted_values[f]
        return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c
    
    def _generate_recommendations(self, success_rate: float, performance_metrics: Dict, rate_violations: int, total_requests: int) -> List[str]:
        """Generate recommendations based on test results"""
        
        recommendations = []
        
        # Success rate recommendations
        if success_rate < 95:
            recommendations.append(f"Success rate is {success_rate:.1f}% - investigate failed requests")
        elif success_rate >= 99:
            recommendations.append("Excellent success rate - authentication system is stable")
        
        # Performance recommendations  
        if performance_metrics:
            avg_response = performance_metrics.get("avg_response_time_ms", 0)
            p99_response = performance_metrics.get("p99_response_time_ms", 0)
            
            if avg_response > 2000:  # 2 second average
                recommendations.append(f"High average response time ({avg_response:.1f}ms) - optimize authentication flow")
            elif avg_response < 500:
                recommendations.append("Excellent response times - authentication performance is optimal")
                
            if p99_response > 5000:  # 5 second P99
                recommendations.append(f"High P99 response time ({p99_response:.1f}ms) - investigate timeout issues")
        
        # Rate limiting recommendations
        rate_violation_percent = (rate_violations / total_requests * 100) if total_requests > 0 else 0
        if rate_violation_percent > 10:
            recommendations.append(f"High rate limiting violations ({rate_violation_percent:.1f}%) - consider adjusting limits")
        elif rate_violation_percent > 0 and rate_violation_percent <= 5:
            recommendations.append("Rate limiting is working as expected - low violation rate")
        
        # Middleware-specific recommendations
        emergency_results = [r for r in self.results if "emergency" in r.endpoint]
        if emergency_results:
            emergency_success_rate = len([r for r in emergency_results if r.success]) / len(emergency_results) * 100
            if emergency_success_rate >= 95:
                recommendations.append("✅ Emergency endpoints working correctly - fallback system operational")
            else:
                recommendations.append("❌ Emergency endpoints failing - critical fallback issue")
        
        # Rate limiting recommendations
        rate_limit_results = [r for r in self.results if r.status_code == 429]
        if rate_limit_results:
            recommendations.append(f"✅ Rate limiting active - {len(rate_limit_results)} requests properly blocked")
        else:
            recommendations.append("⚠️ No rate limiting detected - may indicate configuration issues")
        
        # Overall system recommendations
        if success_rate >= 99 and performance_metrics.get("avg_response_time_ms", 0) < 1000:
            recommendations.append("🟢 Authentication system is production-ready for current load levels")
        elif success_rate >= 95:
            recommendations.append("🟡 Authentication system is functional but may need optimization")
        else:
            recommendations.append("🔴 Authentication system needs immediate attention before production")
        
        # Performance regression check
        slow_endpoints = [ep for ep, stats in endpoint_stats.items() 
                         if stats.get("avg_response_time_ms", 0) > 2000]
        if slow_endpoints:
            recommendations.append(f"⚠️ Slow endpoints detected: {', '.join(slow_endpoints)} - investigate timeouts")
        
        # Success rate analysis per endpoint
        failing_endpoints = [ep for ep, stats in endpoint_stats.items() 
                           if stats.get("success_rate", 0) < 90]
        if failing_endpoints:
            recommendations.append(f"❌ Failing endpoints: {', '.join(failing_endpoints)} - need immediate attention")
        
        return recommendations

async def run_comprehensive_auth_testing():
    """Run all authentication load tests comprehensively"""
    
    print("=" * 80)
    print("🚀 MITA FINANCE COMPREHENSIVE AUTHENTICATION LOAD TESTING")
    print("=" * 80)
    print("Testing restored middleware components and authentication system")
    print("=" * 80)
    
    all_results = {}
    overall_success = True
    
    # Test configurations for different load levels
    test_configurations = [
        {
            "name": "Baseline Load Test",
            "concurrent_users": 10,
            "test_duration_seconds": 120,
            "ramp_up_seconds": 10,
            "description": "Light load to establish performance baseline"
        },
        {
            "name": "Normal Production Load",
            "concurrent_users": 25,
            "test_duration_seconds": 180,
            "ramp_up_seconds": 20,
            "description": "Expected production traffic simulation"
        },
        {
            "name": "Peak Traffic Load",
            "concurrent_users": 50,
            "test_duration_seconds": 300,
            "ramp_up_seconds": 30,
            "description": "High traffic simulation for peak periods"
        },
        {
            "name": "Stress Test",
            "concurrent_users": 100,
            "test_duration_seconds": 180,
            "ramp_up_seconds": 15,
            "description": "System limits and failure point identification"
        }
    ]
    
    for i, test_config in enumerate(test_configurations):
        print(f"\n🔬 TEST {i+1}/4: {test_config['name']}")
        print(f"   {test_config['description']}")
        print(f"   Users: {test_config['concurrent_users']}, Duration: {test_config['test_duration_seconds']}s")
        print("-" * 60)
        
        # Create configuration
        config = LoadTestConfig(
            concurrent_users=test_config['concurrent_users'],
            test_duration_seconds=test_config['test_duration_seconds'],
            ramp_up_seconds=test_config['ramp_up_seconds']
        )
        
        # Create and run load tester
        tester = AuthLoadTester(config)
        
        try:
            # Run the load test
            start_time = time.time()
            results = await tester.run_load_test()
            test_duration = time.time() - start_time
            
            # Store results
            all_results[test_config['name']] = results
            all_results[test_config['name']]['actual_test_duration'] = test_duration
            
            # Quick analysis
            summary = results["test_summary"]
            success_rate = summary['success_rate_percent']
            avg_response = results["performance_metrics"].get("avg_response_time_ms", 0) if results["performance_metrics"] else 0
            
            print(f"   ✓ Completed in {test_duration:.1f}s")
            print(f"   ✓ Success Rate: {success_rate:.1f}%")
            print(f"   ✓ Avg Response: {avg_response:.1f}ms")
            print(f"   ✓ Total Requests: {summary['total_requests']}")
            print(f"   ✓ Rate Limits: {summary['rate_limit_violations']}")
            
            # Check if this test passed
            test_passed = success_rate >= 90 and avg_response < 3000  # More lenient for stress tests
            if not test_passed:
                overall_success = False
                print(f"   ⚠️  Test performance below threshold")
            
            # Cool down between tests
            if i < len(test_configurations) - 1:
                print(f"   😴 Cooling down for 10 seconds...")
                await asyncio.sleep(10)
                
        except Exception as e:
            print(f"   ❌ Test failed: {str(e)}")
            all_results[test_config['name']] = {"error": str(e)}
            overall_success = False
    
    # Run dedicated rate limiting tests
    print(f"\n🔒 DEDICATED RATE LIMITING VALIDATION")
    print("-" * 60)
    
    try:
        rate_limit_config = LoadTestConfig(concurrent_users=5, test_duration_seconds=30, ramp_up_seconds=0)
        rate_tester = AuthLoadTester(rate_limit_config)
        await rate_tester.generate_test_data()
        
        rate_limit_results = await rate_tester.run_rate_limiting_test()
        all_results["Rate Limiting Tests"] = rate_limit_results
        
        if rate_limit_results.get("rate_limiting_working"):
            print("   ✓ Rate limiting is working correctly")
        else:
            print("   ⚠️  Rate limiting may not be configured properly")
            
    except Exception as e:
        print(f"   ❌ Rate limiting test failed: {str(e)}")
        all_results["Rate Limiting Tests"] = {"error": str(e)}
    
    # Run middleware stress tests
    print(f"\n🔧 MIDDLEWARE STRESS TESTING")
    print("-" * 60)
    
    try:
        middleware_config = LoadTestConfig(concurrent_users=10, test_duration_seconds=60, ramp_up_seconds=0)
        middleware_tester = AuthLoadTester(middleware_config)
        
        middleware_results = await middleware_tester.run_middleware_stress_test()
        all_results["Middleware Stress Tests"] = middleware_results
        
        middleware_stats = middleware_results["middleware_stress_test"]
        print("   ✓ Emergency diagnostics endpoint tested")
        print("   ✓ Security status endpoint tested")
        
        for endpoint_name, stats in middleware_stats.items():
            success_rate = (stats["successful_requests"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0
            print(f"   ✓ {endpoint_name}: {success_rate:.1f}% success, {stats['average_response_time_ms']:.1f}ms avg")
            
    except Exception as e:
        print(f"   ❌ Middleware stress test failed: {str(e)}")
        all_results["Middleware Stress Tests"] = {"error": str(e)}
    
    # Generate comprehensive report
    print(f"\n📊 COMPREHENSIVE TEST SUMMARY")
    print("=" * 80)
    
    # Calculate overall statistics
    total_requests = sum(
        result.get("test_summary", {}).get("total_requests", 0) 
        for result in all_results.values() 
        if isinstance(result, dict) and "test_summary" in result
    )
    
    total_successful = sum(
        result.get("test_summary", {}).get("successful_requests", 0)
        for result in all_results.values() 
        if isinstance(result, dict) and "test_summary" in result
    )
    
    overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
    
    print(f"Total Requests Across All Tests: {total_requests}")
    print(f"Total Successful Requests: {total_successful}")
    print(f"Overall Success Rate: {overall_success_rate:.1f}%")
    
    # Performance analysis
    print(f"\n⚡ PERFORMANCE ANALYSIS:")
    for test_name, result in all_results.items():
        if isinstance(result, dict) and "test_summary" in result:
            perf = result.get("performance_metrics", {})
            if perf:
                print(f"  {test_name}:")
                print(f"    ├─ Avg Response: {perf.get('avg_response_time_ms', 0):.1f}ms")
                print(f"    ├─ P95 Response: {perf.get('p95_response_time_ms', 0):.1f}ms")
                print(f"    └─ Success Rate: {result['test_summary']['success_rate_percent']:.1f}%")
    
    # Critical issues detection
    print(f"\n🚨 CRITICAL ISSUES ANALYSIS:")
    
    issues_found = []
    
    # Check for authentication failures
    for test_name, result in all_results.items():
        if isinstance(result, dict) and "test_summary" in result:
            success_rate = result["test_summary"]["success_rate_percent"]
            if success_rate < 90:
                issues_found.append(f"Low success rate in {test_name}: {success_rate:.1f}%")
    
    # Check for performance regressions
    for test_name, result in all_results.items():
        if isinstance(result, dict) and "performance_metrics" in result:
            avg_response = result["performance_metrics"].get("avg_response_time_ms", 0)
            if avg_response > 5000:  # 5 second threshold
                issues_found.append(f"High response time in {test_name}: {avg_response:.1f}ms")
    
    if issues_found:
        print("   Issues detected:")
        for issue in issues_found:
            print(f"   ❌ {issue}")
        overall_success = False
    else:
        print("   ✅ No critical issues detected")
    
    # Save comprehensive report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"comprehensive_auth_load_test_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n📋 Comprehensive report saved: {report_file}")
    
    # Final verdict
    print(f"\n🎯 FINAL VERDICT:")
    print("=" * 80)
    
    if overall_success and overall_success_rate >= 95:
        print("✅ COMPREHENSIVE AUTHENTICATION TESTING: PASSED")
        print("🔒 Authentication system is production-ready")
        print("🚀 Middleware restoration successful - no performance regressions detected")
        print("⚡ System can handle expected production load")
        return True
    else:
        print("❌ COMPREHENSIVE AUTHENTICATION TESTING: FAILED")
        print("🔒 Authentication system needs optimization before production")
        print("⚠️  Issues detected that require immediate attention")
        return False


def main():
    """Run comprehensive authentication load testing"""
    
    try:
        success = asyncio.run(run_comprehensive_auth_testing())
        return success
    except Exception as e:
        print(f"\n❌ COMPREHENSIVE TESTING ERROR: {e}")
        logger.error(f"Comprehensive testing failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)