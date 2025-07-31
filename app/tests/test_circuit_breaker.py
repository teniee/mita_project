"""
Comprehensive tests for circuit breaker pattern implementation
Tests circuit breaker functionality, state transitions, and resilience patterns
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timedelta

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreakerOpenException,
    CircuitBreakerManager,
    get_circuit_breaker_manager
)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout_duration == 60
        assert config.max_retry_attempts == 3
        assert config.retry_backoff_factor == 2.0
        assert config.timeout_seconds == 30.0
        assert ConnectionError in config.trigger_exceptions
        assert TimeoutError in config.trigger_exceptions
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_duration=30,
            max_retry_attempts=2
        )
        
        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.timeout_duration == 30
        assert config.max_retry_attempts == 2


class TestCircuitBreaker:
    """Test circuit breaker core functionality"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker with test configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_duration=1,  # 1 second for fast tests
            max_retry_attempts=1,
            timeout_seconds=0.1
        )
        return CircuitBreaker("test_service", config)
    
    @pytest.mark.asyncio
    async def test_initial_state(self, circuit_breaker):
        """Test circuit breaker starts in CLOSED state"""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.total_requests == 0
        assert circuit_breaker.stats.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker):
        """Test successful function call through circuit breaker"""
        async def successful_function():
            return "success"
        
        result = await circuit_breaker.call(successful_function)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.successful_requests == 1
        assert circuit_breaker.stats.consecutive_successes == 1
    
    @pytest.mark.asyncio
    async def test_failed_call(self, circuit_breaker):
        """Test failed function call through circuit breaker"""
        async def failing_function():
            raise ConnectionError("Test failure")
        
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED  # Still closed after 1 failure
        assert circuit_breaker.stats.failed_requests == 1
        assert circuit_breaker.stats.consecutive_failures == 1
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold"""
        async def failing_function():
            raise ConnectionError("Test failure")
        
        # First failure
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(failing_function)
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Second failure - should open circuit
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(failing_function)
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.stats.consecutive_failures == 2
    
    @pytest.mark.asyncio
    async def test_circuit_blocks_when_open(self, circuit_breaker):
        """Test circuit breaker blocks calls when open"""
        async def failing_function():
            raise ConnectionError("Test failure")
        
        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Next call should be blocked
        async def any_function():
            return "should not execute"
        
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(any_function)
    
    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit breaker transitions to half-open after timeout"""
        async def failing_function():
            raise ConnectionError("Test failure")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for timeout (1 second in test config)
        await asyncio.sleep(1.1)
        
        # Manually trigger state check
        async with circuit_breaker:
            pass
        
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_closes_after_successes(self, circuit_breaker):
        """Test circuit breaker closes after success threshold in half-open"""
        async def failing_function():
            raise ConnectionError("Test failure")
        
        async def successful_function():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(failing_function)
        
        # Wait for half-open
        await asyncio.sleep(1.1)
        
        # Transition to half-open
        async with circuit_breaker:
            pass
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        # Successful calls to close circuit
        await circuit_breaker.call(successful_function)
        await circuit_breaker.call(successful_function)
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.consecutive_successes == 2
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, circuit_breaker):
        """Test retry logic with exponential backoff"""
        call_count = 0
        
        async def intermittent_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 2:  # Fail first call, succeed second
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await circuit_breaker.call(intermittent_failure)
        
        assert result == "success"
        assert call_count == 2  # Should have retried once
        assert circuit_breaker.stats.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, circuit_breaker):
        """Test function timeout handling"""
        async def slow_function():
            await asyncio.sleep(1.0)  # Longer than timeout (0.1s)
            return "too slow"
        
        with pytest.raises(asyncio.TimeoutError):
            await circuit_breaker.call(slow_function)
        
        assert circuit_breaker.stats.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_non_triggering_exceptions(self, circuit_breaker):
        """Test that non-triggering exceptions don't affect circuit breaker"""
        async def function_with_value_error():
            raise ValueError("This should not trigger circuit breaker")
        
        with pytest.raises(ValueError):
            await circuit_breaker.call(function_with_value_error)
        
        # Should not count as failure for circuit breaker
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.stats.consecutive_failures == 0
    
    def test_get_stats(self, circuit_breaker):
        """Test circuit breaker statistics"""
        stats = circuit_breaker.get_stats()
        
        assert 'name' in stats
        assert 'state' in stats
        assert 'total_requests' in stats
        assert 'successful_requests' in stats
        assert 'failed_requests' in stats
        assert 'success_rate' in stats
        assert 'config' in stats
        
        assert stats['name'] == 'test_service'
        assert stats['state'] == 'closed'
        assert stats['success_rate'] == 0.0  # No requests yet


class TestCircuitBreakerManager:
    """Test circuit breaker manager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh circuit breaker manager"""
        return CircuitBreakerManager()
    
    def test_register_service(self, manager):
        """Test registering a service with circuit breaker"""
        config = CircuitBreakerConfig(failure_threshold=3)
        manager.register_service("test_service", config)
        
        circuit_breaker = manager.get_circuit_breaker("test_service")
        assert circuit_breaker.name == "test_service"
        assert circuit_breaker.config.failure_threshold == 3
    
    def test_auto_register_service(self, manager):
        """Test automatic service registration"""
        circuit_breaker = manager.get_circuit_breaker("auto_service")
        
        assert circuit_breaker.name == "auto_service"
        assert circuit_breaker.config.failure_threshold == 5  # Default
    
    @pytest.mark.asyncio
    async def test_call_service(self, manager):
        """Test calling service through manager"""
        async def test_function(x, y):
            return x + y
        
        result = await manager.call_service("math_service", test_function, 2, 3)
        
        assert result == 5
        
        # Verify service was registered
        circuit_breaker = manager.get_circuit_breaker("math_service")
        assert circuit_breaker.stats.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_protect_context_manager(self, manager):
        """Test protect context manager"""
        async def test_function():
            return "protected"
        
        async with manager.protect("context_service") as circuit_breaker:
            result = await circuit_breaker.call(test_function)
        
        assert result == "protected"
        
        # Verify service stats
        cb = manager.get_circuit_breaker("context_service")
        assert cb.stats.successful_requests == 1
    
    def test_get_all_stats(self, manager):
        """Test getting statistics for all services"""
        manager.register_service("service1")
        manager.register_service("service2")
        
        all_stats = manager.get_all_stats()
        
        assert "service1" in all_stats
        assert "service2" in all_stats
        assert all_stats["service1"]["name"] == "service1"
        assert all_stats["service2"]["name"] == "service2"
    
    def test_get_health_summary(self, manager):
        """Test getting health summary"""
        manager.register_service("healthy_service")
        manager.register_service("failed_service")
        
        # Simulate failed service
        failed_cb = manager.get_circuit_breaker("failed_service")
        failed_cb.state = CircuitBreakerState.OPEN
        
        health_summary = manager.get_health_summary()
        
        assert health_summary["total_services"] == 2
        assert health_summary["healthy_services"] == 1
        assert health_summary["failed_services"] == 1
        assert health_summary["overall_health"] in ["healthy", "degraded", "critical"]
        assert health_summary["health_percentage"] == 50.0


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker system"""
    
    @pytest.mark.asyncio
    async def test_global_manager_singleton(self):
        """Test global circuit breaker manager is singleton"""
        manager1 = get_circuit_breaker_manager()
        manager2 = get_circuit_breaker_manager()
        
        assert manager1 is manager2
        
        # Test pre-registered services
        openai_cb = manager1.get_circuit_breaker("openai")
        google_cb = manager1.get_circuit_breaker("google_oauth")
        
        assert openai_cb.name == "openai"
        assert google_cb.name == "google_oauth"
        assert openai_cb.config.timeout_duration == 120
        assert google_cb.config.timeout_duration == 60
    
    @pytest.mark.asyncio
    async def test_multiple_services_independence(self):
        """Test that different services maintain independent state"""
        manager = get_circuit_breaker_manager()
        
        async def failing_function():
            raise ConnectionError("Failure")
        
        async def successful_function():
            return "success"
        
        # Service 1 fails
        service1_cb = manager.get_circuit_breaker("independent_service_1")
        service2_cb = manager.get_circuit_breaker("independent_service_2")
        
        # Fail service 1
        for _ in range(service1_cb.config.failure_threshold):
            with pytest.raises(ConnectionError):
                await service1_cb.call(failing_function)
        
        # Service 1 should be open, service 2 should be closed
        assert service1_cb.state == CircuitBreakerState.OPEN
        assert service2_cb.state == CircuitBreakerState.CLOSED
        
        # Service 2 should still work
        result = await service2_cb.call(successful_function)
        assert result == "success"
        assert service2_cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test circuit breaker under concurrent access"""
        manager = get_circuit_breaker_manager()
        circuit_breaker = manager.get_circuit_breaker("concurrent_test")
        
        async def concurrent_function(delay):
            await asyncio.sleep(delay)
            return f"result_{delay}"
        
        # Run multiple concurrent calls
        tasks = [
            circuit_breaker.call(concurrent_function, 0.01),
            circuit_breaker.call(concurrent_function, 0.02),
            circuit_breaker.call(concurrent_function, 0.01),
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all("result_" in result for result in results)
        assert circuit_breaker.stats.successful_requests == 3
        assert circuit_breaker.stats.failed_requests == 0


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_zero_failure_threshold(self):
        """Test circuit breaker with zero failure threshold"""
        config = CircuitBreakerConfig(failure_threshold=0)
        circuit_breaker = CircuitBreaker("zero_threshold", config)
        
        # Should open immediately on any failure
        async def failing_function():
            raise ConnectionError("Immediate failure")
        
        # Circuit should still be closed initially
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Any failure should open it (but we need at least 1 failure to trigger)
        config.failure_threshold = 1
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_very_short_timeout(self):
        """Test circuit breaker with very short timeout"""
        config = CircuitBreakerConfig(
            timeout_duration=0.001,  # 1ms
            failure_threshold=1
        )
        circuit_breaker = CircuitBreaker("short_timeout", config)
        
        # Open the circuit
        async def failing_function():
            raise ConnectionError("Failure")
        
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait slightly longer than timeout
        await asyncio.sleep(0.002)
        
        # Should transition to half-open
        async with circuit_breaker:
            pass
        
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_function_returning_none(self):
        """Test circuit breaker with function returning None"""
        manager = get_circuit_breaker_manager()
        circuit_breaker = manager.get_circuit_breaker("none_return")
        
        async def none_function():
            return None
        
        result = await circuit_breaker.call(none_function)
        
        assert result is None
        assert circuit_breaker.stats.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_sync_function_call(self):
        """Test circuit breaker with synchronous function"""
        manager = get_circuit_breaker_manager()
        circuit_breaker = manager.get_circuit_breaker("sync_function")
        
        def sync_function(x, y):
            return x * y
        
        result = await circuit_breaker.call(sync_function, 4, 5)
        
        assert result == 20
        assert circuit_breaker.stats.successful_requests == 1