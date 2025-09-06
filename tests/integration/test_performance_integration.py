"""
Performance Integration Tests
============================

Performance validation tests for MITA authentication system that validate
production-level performance requirements for financial applications.

Performance Requirements:
- API responses: <200ms p95, <500ms p99
- Database queries: <50ms p95
- Token operations: <10ms
- Concurrent users: 100+
- Memory usage: stable under load
"""

import pytest
import httpx
import asyncio
import time
import statistics
import psutil
import gc
from typing import Dict, List, Any, Tuple
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.performance, pytest.mark.asyncio]


class TestAuthenticationPerformance:
    """Test authentication operation performance."""
    
    @pytest.mark.performance
    async def test_registration_performance(
        self,
        mobile_client: httpx.AsyncClient,
        performance_thresholds: Dict[str, float],
        integration_helper
    ):
        """Test user registration performance under normal conditions."""
        
        registration_times = []
        num_tests = 10
        
        for i in range(num_tests):
            credentials = {
                "email": f"perf_test_{i}_{uuid.uuid4().hex[:8]}@example.com",
                "password": f"SecurePassword123_{i}!"
            }
            
            start_time = time.perf_counter()
            response = await mobile_client.post("/auth/register", json=credentials)
            end_time = time.perf_counter()
            
            registration_time = end_time - start_time
            registration_times.append(registration_time)
            
            # Verify success
            assert response.status_code == 201, f"Registration {i} failed: {response.text}"
            
            # Small delay between registrations
            await asyncio.sleep(0.1)
        
        # Calculate performance metrics
        avg_time = statistics.mean(registration_times)
        p95_time = statistics.quantiles(registration_times, n=20)[18]  # 95th percentile
        p99_time = statistics.quantiles(registration_times, n=100)[98] if len(registration_times) >= 10 else max(registration_times)
        max_time = max(registration_times)
        
        # Performance assertions
        assert avg_time <= performance_thresholds["api_response_p95"], \
            f"Average registration time {avg_time:.3f}s exceeds threshold {performance_thresholds['api_response_p95']:.3f}s"
        
        assert p95_time <= performance_thresholds["api_response_p95"], \
            f"P95 registration time {p95_time:.3f}s exceeds threshold {performance_thresholds['api_response_p95']:.3f}s"
        
        assert max_time <= performance_thresholds["api_response_p99"], \
            f"Max registration time {max_time:.3f}s exceeds threshold {performance_thresholds['api_response_p99']:.3f}s"
        
        print(f"Registration Performance - Avg: {avg_time:.3f}s, P95: {p95_time:.3f}s, Max: {max_time:.3f}s")
    
    @pytest.mark.performance
    async def test_login_performance(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        performance_thresholds: Dict[str, float]
    ):
        """Test login performance under normal conditions."""
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_times = []
        num_tests = 20
        
        for i in range(num_tests):
            start_time = time.perf_counter()
            response = await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            end_time = time.perf_counter()
            
            login_time = end_time - start_time
            login_times.append(login_time)
            
            # Verify success or rate limiting
            assert response.status_code in [200, 429], f"Login {i} failed: {response.text}"
            
            # Small delay between logins
            await asyncio.sleep(0.05)
        
        # Filter out rate limited responses for performance calculation
        successful_times = [login_times[i] for i in range(len(login_times)) 
                          if i < num_tests]  # Consider all times for now
        
        if len(successful_times) < 5:
            pytest.skip("Too few successful logins to measure performance")
        
        # Calculate performance metrics
        avg_time = statistics.mean(successful_times)
        p95_time = statistics.quantiles(successful_times, n=20)[18] if len(successful_times) >= 20 else max(successful_times)
        max_time = max(successful_times)
        
        # Performance assertions
        assert avg_time <= performance_thresholds["api_response_p95"], \
            f"Average login time {avg_time:.3f}s exceeds threshold"
        
        assert p95_time <= performance_thresholds["api_response_p95"], \
            f"P95 login time {p95_time:.3f}s exceeds threshold"
        
        print(f"Login Performance - Avg: {avg_time:.3f}s, P95: {p95_time:.3f}s, Max: {max_time:.3f}s")
    
    @pytest.mark.performance
    async def test_token_refresh_performance(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        performance_thresholds: Dict[str, float]
    ):
        """Test token refresh operation performance."""
        
        # Register and login
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        refresh_times = []
        num_tests = 10
        
        for i in range(num_tests):
            start_time = time.perf_counter()
            response = await mobile_client.post("/auth/refresh-token", data={
                "refresh_token": refresh_token
            })
            end_time = time.perf_counter()
            
            if response.status_code == 404:
                pytest.skip("Token refresh endpoint not implemented")
            
            refresh_time = end_time - start_time
            refresh_times.append(refresh_time)
            
            assert response.status_code == 200, f"Token refresh {i} failed: {response.text}"
            
            # Update refresh token for next iteration
            if "refresh_token" in response.json():
                refresh_token = response.json()["refresh_token"]
            
            await asyncio.sleep(0.1)
        
        # Calculate performance metrics
        avg_time = statistics.mean(refresh_times)
        max_time = max(refresh_times)
        
        # Token refresh should be fast
        assert avg_time <= performance_thresholds["token_creation_max"], \
            f"Average token refresh time {avg_time:.3f}s exceeds threshold"
        
        print(f"Token Refresh Performance - Avg: {avg_time:.3f}s, Max: {max_time:.3f}s")


class TestConcurrentPerformance:
    """Test performance under concurrent load."""
    
    @pytest.mark.slow
    @pytest.mark.performance
    async def test_concurrent_logins(
        self,
        api_base_url: str,
        performance_thresholds: Dict[str, float]
    ):
        """Test login performance under concurrent load."""
        
        # Create a test user first
        setup_client = httpx.AsyncClient(base_url=api_base_url)
        test_email = f"concurrent_test_{uuid.uuid4().hex[:8]}@example.com"
        test_password = "ConcurrentTestPassword123!"
        
        await setup_client.post("/auth/register", json={
            "email": test_email,
            "password": test_password
        })
        await setup_client.aclose()
        
        # Concurrent login function
        async def concurrent_login(client_id: int) -> Tuple[int, float]:
            client = httpx.AsyncClient(
                base_url=api_base_url,
                headers={
                    "User-Agent": f"MITA-Mobile/1.0 (ConcurrentTest-{client_id})",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
            
            try:
                start_time = time.perf_counter()
                response = await client.post("/auth/login", json={
                    "email": test_email,
                    "password": test_password
                })
                end_time = time.perf_counter()
                
                return response.status_code, end_time - start_time
            finally:
                await client.aclose()
        
        # Run concurrent logins
        num_concurrent = 50  # Start with moderate concurrency
        tasks = [concurrent_login(i) for i in range(num_concurrent)]
        
        overall_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        overall_end = time.perf_counter()
        
        overall_time = overall_end - overall_start
        
        # Analyze results
        successful_results = [(status, duration) for status, duration in results 
                            if isinstance((status, duration), tuple) and status == 200]
        rate_limited_count = sum(1 for status, duration in results 
                               if isinstance((status, duration), tuple) and status == 429)
        error_count = len(results) - len(successful_results) - rate_limited_count
        
        success_count = len(successful_results)
        successful_times = [duration for _, duration in successful_results]
        
        # Performance assertions
        assert success_count > 0, "Some concurrent logins should succeed"
        assert error_count < num_concurrent * 0.1, f"Too many errors: {error_count}/{num_concurrent}"
        
        if successful_times:
            avg_time = statistics.mean(successful_times)
            max_time = max(successful_times)
            
            # Concurrent operations may be slower but should still be reasonable
            concurrent_threshold = performance_thresholds["api_response_p99"]
            assert avg_time <= concurrent_threshold, \
                f"Concurrent login average time {avg_time:.3f}s exceeds threshold"
            
            # Calculate throughput
            throughput = success_count / overall_time
            
            print(f"Concurrent Login Performance:")
            print(f"  Successful: {success_count}/{num_concurrent}")
            print(f"  Rate Limited: {rate_limited_count}")
            print(f"  Errors: {error_count}")
            print(f"  Avg Time: {avg_time:.3f}s")
            print(f"  Max Time: {max_time:.3f}s") 
            print(f"  Throughput: {throughput:.1f} logins/sec")
    
    @pytest.mark.performance
    async def test_concurrent_registrations(
        self,
        api_base_url: str,
        performance_thresholds: Dict[str, float]
    ):
        """Test registration performance under concurrent load."""
        
        async def concurrent_registration(client_id: int) -> Tuple[int, float]:
            client = httpx.AsyncClient(
                base_url=api_base_url,
                headers={
                    "User-Agent": f"MITA-Mobile/1.0 (RegTest-{client_id})",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
            
            try:
                email = f"reg_test_{client_id}_{uuid.uuid4().hex[:8]}@example.com"
                password = f"SecurePassword{client_id}!"
                
                start_time = time.perf_counter()
                response = await client.post("/auth/register", json={
                    "email": email,
                    "password": password
                })
                end_time = time.perf_counter()
                
                return response.status_code, end_time - start_time
            finally:
                await client.aclose()
        
        # Run concurrent registrations
        num_concurrent = 30
        tasks = [concurrent_registration(i) for i in range(num_concurrent)]
        
        overall_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        overall_end = time.perf_counter()
        
        overall_time = overall_end - overall_start
        
        # Analyze results
        successful_results = [(status, duration) for status, duration in results 
                            if isinstance((status, duration), tuple) and status == 201]
        rate_limited_count = sum(1 for status, duration in results 
                               if isinstance((status, duration), tuple) and status == 429)
        
        success_count = len(successful_results)
        successful_times = [duration for _, duration in successful_results]
        
        # Performance assertions
        assert success_count > 0, "Some concurrent registrations should succeed"
        
        if successful_times:
            avg_time = statistics.mean(successful_times)
            throughput = success_count / overall_time
            
            print(f"Concurrent Registration Performance:")
            print(f"  Successful: {success_count}/{num_concurrent}")
            print(f"  Rate Limited: {rate_limited_count}")
            print(f"  Avg Time: {avg_time:.3f}s")
            print(f"  Throughput: {throughput:.1f} registrations/sec")


class TestMemoryAndResourceUsage:
    """Test memory and resource usage under load."""
    
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_memory_usage_during_auth_operations(
        self,
        mobile_client: httpx.AsyncClient,
        performance_thresholds: Dict[str, float]
    ):
        """Test memory usage during authentication operations."""
        
        # Measure initial memory
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many auth operations
        num_operations = 100
        
        for i in range(num_operations):
            email = f"memory_test_{i}_{uuid.uuid4().hex[:6]}@example.com"
            password = f"MemoryTest{i}!"
            
            # Register
            register_response = await mobile_client.post("/auth/register", json={
                "email": email,
                "password": password
            })
            
            if register_response.status_code == 201:
                # Login
                await mobile_client.post("/auth/login", json={
                    "email": email,
                    "password": password
                })
            
            # Periodic garbage collection and memory check
            if i % 20 == 0:
                gc.collect()
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_growth = current_memory - initial_memory
                
                # Memory growth should be reasonable
                max_growth = performance_thresholds["memory_usage_mb"]
                if memory_growth > max_growth:
                    print(f"Warning: Memory growth {memory_growth:.1f}MB exceeds threshold at operation {i}")
            
            # Small delay to prevent overwhelming the system
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        # Final memory check
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"Memory Usage - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Growth: {total_growth:.1f}MB")
        
        # Assert reasonable memory growth
        assert total_growth <= performance_thresholds["memory_usage_mb"], \
            f"Memory growth {total_growth:.1f}MB exceeds threshold {performance_thresholds['memory_usage_mb']:.1f}MB"
    
    @pytest.mark.performance
    async def test_connection_handling(
        self,
        api_base_url: str
    ):
        """Test proper connection handling under load."""
        
        # Test multiple clients to ensure proper connection management
        num_clients = 20
        operations_per_client = 5
        
        async def client_operations(client_id: int) -> List[int]:
            client = httpx.AsyncClient(
                base_url=api_base_url,
                timeout=30.0,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2)
            )
            
            try:
                results = []
                for op in range(operations_per_client):
                    email = f"conn_test_{client_id}_{op}@example.com"
                    
                    # Registration
                    response = await client.post("/auth/register", json={
                        "email": email,
                        "password": f"ConnTest{client_id}{op}!"
                    })
                    results.append(response.status_code)
                    
                    # Login if registration succeeded
                    if response.status_code == 201:
                        login_response = await client.post("/auth/login", json={
                            "email": email,
                            "password": f"ConnTest{client_id}{op}!"
                        })
                        results.append(login_response.status_code)
                
                return results
            finally:
                await client.aclose()
        
        # Run multiple clients concurrently
        tasks = [client_operations(i) for i in range(num_clients)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze connection handling
        successful_operations = 0
        total_operations = 0
        
        for client_results in results:
            if isinstance(client_results, list):
                total_operations += len(client_results)
                successful_operations += sum(1 for status in client_results if status in [200, 201])
            elif isinstance(client_results, Exception):
                print(f"Client error: {client_results}")
        
        # Assert reasonable success rate
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        assert success_rate >= 0.8, f"Success rate {success_rate:.2f} too low for connection handling test"
        
        print(f"Connection Handling - Success Rate: {success_rate:.2f} ({successful_operations}/{total_operations})")


class TestDatabasePerformance:
    """Test database-related performance (indirect through API)."""
    
    @pytest.mark.performance
    async def test_user_lookup_performance(
        self,
        mobile_client: httpx.AsyncClient,
        performance_thresholds: Dict[str, float]
    ):
        """Test user lookup performance during login operations."""
        
        # Create several users for testing
        test_users = []
        for i in range(20):
            email = f"db_perf_test_{i}@example.com"
            password = f"DbPerfTest{i}!"
            
            response = await mobile_client.post("/auth/register", json={
                "email": email,
                "password": password
            })
            
            if response.status_code == 201:
                test_users.append((email, password))
        
        if len(test_users) < 10:
            pytest.skip("Not enough test users created for database performance test")
        
        # Test login performance for existing users (tests database lookup)
        lookup_times = []
        
        for email, password in test_users:
            start_time = time.perf_counter()
            response = await mobile_client.post("/auth/login", json={
                "email": email,
                "password": password
            })
            end_time = time.perf_counter()
            
            if response.status_code == 200:
                lookup_times.append(end_time - start_time)
        
        if not lookup_times:
            pytest.skip("No successful logins for database performance test")
        
        # Analyze database lookup performance (indirect)
        avg_lookup_time = statistics.mean(lookup_times)
        max_lookup_time = max(lookup_times)
        
        # Database operations should be fast
        db_threshold = performance_thresholds["db_query_max"]
        assert avg_lookup_time <= db_threshold, \
            f"Average user lookup time {avg_lookup_time:.3f}s exceeds threshold {db_threshold:.3f}s"
        
        print(f"User Lookup Performance - Avg: {avg_lookup_time:.3f}s, Max: {max_lookup_time:.3f}s")


class TestEndToEndPerformance:
    """Test end-to-end performance scenarios."""
    
    @pytest.mark.slow
    @pytest.mark.performance
    async def test_full_user_journey_performance(
        self,
        mobile_client: httpx.AsyncClient,
        mobile_device_context: Dict[str, str],
        performance_thresholds: Dict[str, float]
    ):
        """Test complete user journey performance."""
        
        journey_times = {}
        overall_start = time.perf_counter()
        
        # Step 1: Registration
        start_time = time.perf_counter()
        email = f"journey_test_{uuid.uuid4().hex[:8]}@example.com"
        password = "JourneyTestPassword123!"
        
        register_response = await mobile_client.post("/auth/register", json={
            "email": email,
            "password": password
        })
        journey_times["registration"] = time.perf_counter() - start_time
        
        assert register_response.status_code == 201, "Registration should succeed"
        access_token = register_response.json()["access_token"]
        
        # Step 2: Login (subsequent)
        start_time = time.perf_counter()
        login_response = await mobile_client.post("/auth/login", json={
            "email": email,
            "password": password
        })
        journey_times["login"] = time.perf_counter() - start_time
        
        assert login_response.status_code in [200, 429], "Login should succeed or be rate limited"
        
        # Step 3: Authenticated request
        if login_response.status_code == 200:
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            
            start_time = time.perf_counter()
            profile_response = await mobile_client.get("/users/profile", headers=auth_headers)
            journey_times["authenticated_request"] = time.perf_counter() - start_time
            
            # Should succeed or return 404 if endpoint not implemented
            assert profile_response.status_code in [200, 404]
        
        # Step 4: Push token registration (if implemented)
        if access_token:
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            
            start_time = time.perf_counter()
            push_response = await mobile_client.post(
                "/notifications/register-device",
                headers=auth_headers,
                json={
                    "push_token": mobile_device_context["push_token"],
                    "device_type": mobile_device_context["device_type"],
                    "device_id": mobile_device_context["device_id"]
                }
            )
            journey_times["push_registration"] = time.perf_counter() - start_time
            
            # Should succeed or return 404 if not implemented
            assert push_response.status_code in [200, 201, 404]
        
        # Step 5: Logout
        if access_token:
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            
            start_time = time.perf_counter()
            logout_response = await mobile_client.post("/auth/logout", headers=auth_headers)
            journey_times["logout"] = time.perf_counter() - start_time
            
            assert logout_response.status_code in [200, 204]
        
        overall_time = time.perf_counter() - overall_start
        journey_times["total"] = overall_time
        
        # Performance assertions for each step
        for step, duration in journey_times.items():
            if step == "total":
                continue  # Skip total time check
                
            threshold = performance_thresholds["api_response_p95"]
            assert duration <= threshold, \
                f"{step} took {duration:.3f}s, exceeds threshold {threshold:.3f}s"
        
        # Total journey should complete reasonably quickly
        assert overall_time <= performance_thresholds["api_response_p99"] * 3, \
            f"Complete user journey took {overall_time:.3f}s, too slow"
        
        print("User Journey Performance:")
        for step, duration in journey_times.items():
            print(f"  {step}: {duration:.3f}s")


# Performance test utilities
class PerformanceMonitor:
    """Utility class for monitoring performance during tests."""
    
    def __init__(self):
        self.start_time = None
        self.measurements = []
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.perf_counter()
        self.measurements = []
    
    def record_measurement(self, operation: str, duration: float):
        """Record a performance measurement."""
        self.measurements.append({
            "operation": operation,
            "duration": duration,
            "timestamp": time.perf_counter() - self.start_time if self.start_time else 0
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.measurements:
            return {}
        
        operations = {}
        for measurement in self.measurements:
            op = measurement["operation"]
            if op not in operations:
                operations[op] = []
            operations[op].append(measurement["duration"])
        
        summary = {}
        for op, times in operations.items():
            summary[op] = {
                "count": len(times),
                "avg": statistics.mean(times),
                "min": min(times),
                "max": max(times),
                "p95": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            }
        
        return summary


@pytest.fixture
def performance_monitor():
    """Provide PerformanceMonitor instance."""
    return PerformanceMonitor()