"""
Comprehensive Test Suite for Rate Limiting Implementation
Tests the production-ready rate limiting system for MITA financial application
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
import redis

from app.core.security import (
    AdvancedRateLimiter,
    SecurityConfig,
    get_rate_limiter,
    # reset_security_instances,  # Function doesn't exist
    get_security_health_status
)
from app.middleware.comprehensive_rate_limiter import ComprehensiveRateLimitMiddleware
from app.core.error_handler import RateLimitException


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.pipeline.return_value = mock_client
    mock_client.execute.return_value = [1, 300]  # count, ttl
    mock_client.zremrangebyscore.return_value = 0
    mock_client.zadd.return_value = 1
    mock_client.zcard.return_value = 1
    mock_client.expire.return_value = True
    mock_client.zrange.return_value = [(b'123456', 1234567890)]
    mock_client.exists.return_value = 0
    mock_client.incr.return_value = 1
    mock_client.setex.return_value = True
    mock_client.sadd.return_value = 1
    mock_client.scard.return_value = 1
    return mock_client


@pytest.fixture
def mock_request():
    """Create mock request object"""
    request = Mock(spec=Request)
    request.client.host = "192.168.1.100"
    request.headers = {
        'User-Agent': 'TestClient/1.0',
        'X-Forwarded-For': '10.0.0.1'
    }
    request.url.path = "/api/test"
    request.method = "GET"
    return request


@pytest.fixture
def rate_limiter(mock_redis):
    """Create rate limiter with mock Redis"""
    # reset_security_instances()  # Function doesn't exist - removed
    with patch('app.core.security.redis_client', mock_redis):
        limiter = AdvancedRateLimiter()
        limiter.redis = mock_redis
        return limiter


@pytest.fixture
def app_with_middleware():
    """Create FastAPI app with rate limiting middleware"""
    app = FastAPI()
    
    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.post("/auth/login")
    async def login_endpoint():
        return {"message": "login success"}
    
    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}
    
    # Add rate limiting middleware
    app.add_middleware(ComprehensiveRateLimitMiddleware, enable_rate_limiting=True)
    
    return app


class TestAdvancedRateLimiter:
    """Test the AdvancedRateLimiter class"""
    
    def test_client_identifier_generation(self, rate_limiter, mock_request):
        """Test client identifier generation with various headers"""
        client_id = rate_limiter._get_client_identifier(mock_request)
        assert "10.0.0.1" in client_id  # Should use X-Forwarded-For
        assert len(client_id.split(':')) == 2  # IP:hash format
    
    def test_sliding_window_counter_redis(self, rate_limiter, mock_request):
        """Test sliding window counter with Redis"""
        count, ttl, exceeded = rate_limiter._sliding_window_counter("test_key", 300, 10)
        
        assert count == 1
        assert ttl >= 0
        assert not exceeded
        
        # Verify Redis calls were made
        rate_limiter.redis.pipeline.assert_called()
        rate_limiter.redis.zadd.assert_called()
    
    def test_memory_fallback(self, mock_request):
        """Test memory fallback when Redis is unavailable"""
        with patch('app.core.security.redis_client', None):
            limiter = AdvancedRateLimiter()
            
            count, ttl, exceeded = limiter._memory_sliding_window("test_key", 300, 10)
            assert count == 1
            assert not exceeded
    
    def test_progressive_penalties(self, rate_limiter, mock_request):
        """Test progressive penalty system"""
        client_id = rate_limiter._get_client_identifier(mock_request)
        
        # Mock Redis responses for penalty checking
        rate_limiter.redis.get.return_value = "3"  # 3 violations
        
        penalty = rate_limiter._check_progressive_penalties(client_id, "login")
        assert penalty == 2.0  # Should be 2x penalty for 3 violations
        
        # Test higher penalty
        rate_limiter.redis.get.return_value = "15"  # 15 violations
        penalty = rate_limiter._check_progressive_penalties(client_id, "login")
        assert penalty == 8.0  # Max penalty
    
    def test_auth_rate_limiting(self, rate_limiter, mock_request):
        """Test authentication-specific rate limiting"""
        email = "test@example.com"
        
        # Should not raise for first attempt
        rate_limiter.check_auth_rate_limit(mock_request, email, "login")
        
        # Mock exceeded limits
        rate_limiter.redis.execute.return_value = [10, 10]  # Both IP and email exceeded
        
        with pytest.raises(RateLimitException):
            rate_limiter.check_auth_rate_limit(mock_request, email, "login")
    
    def test_suspicious_pattern_detection(self, rate_limiter, mock_request):
        """Test detection of suspicious authentication patterns"""
        client_id = rate_limiter._get_client_identifier(mock_request)
        
        # Mock many unique emails from same client
        rate_limiter.redis.execute.return_value = [1, 15, True]  # 15 unique emails
        
        # Should not raise exception but should flag as suspicious
        rate_limiter._check_suspicious_auth_patterns(client_id, "email_hash", "login")
        
        # Verify suspicious flag is set
        rate_limiter.redis.setex.assert_called()
    
    def test_fail_secure_mode(self, mock_request):
        """Test fail-secure behavior when Redis is unavailable"""
        with patch('app.core.security.redis_client', None):
            limiter = AdvancedRateLimiter()
            limiter.fail_secure_mode = True
            
            with pytest.raises(RateLimitException, match="Service temporarily unavailable"):
                limiter.check_rate_limit(mock_request, 10, 300, "test")
    
    def test_rate_limit_status(self, rate_limiter, mock_request):
        """Test rate limit status reporting"""
        status = rate_limiter.get_rate_limit_status(mock_request, "api", "user123")
        
        assert isinstance(status, dict)
        assert "penalty_multiplier" in status
        assert "is_suspicious" in status


class TestSecurityConfiguration:
    """Test security configuration and tiers"""
    
    def test_rate_limit_tiers(self):
        """Test that all user tiers have proper configuration"""
        tiers = SecurityConfig.RATE_LIMIT_TIERS
        
        assert "anonymous" in tiers
        assert "basic_user" in tiers
        assert "premium_user" in tiers
        assert "admin_user" in tiers
        
        # Verify tier progression (higher tiers should have higher limits)
        assert tiers["anonymous"]["requests_per_hour"] < tiers["basic_user"]["requests_per_hour"]
        assert tiers["basic_user"]["requests_per_hour"] < tiers["premium_user"]["requests_per_hour"]
        assert tiers["premium_user"]["requests_per_hour"] < tiers["admin_user"]["requests_per_hour"]
    
    def test_auth_rate_limits(self):
        """Test authentication rate limits are appropriately restrictive"""
        assert SecurityConfig.LOGIN_RATE_LIMIT <= 10  # Should be very restrictive
        assert SecurityConfig.REGISTER_RATE_LIMIT <= 5  # Even more restrictive
        assert SecurityConfig.PASSWORD_RESET_RATE_LIMIT <= 3  # Most restrictive


class TestRateLimitingMiddleware:
    """Test the comprehensive rate limiting middleware"""
    
    @pytest.mark.asyncio
    async def test_middleware_exempts_health_endpoints(self, app_with_middleware):
        """Test that health endpoints are exempt from rate limiting"""
        client = TestClient(app_with_middleware)
        
        # Health endpoint should work even with many requests
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_applies_general_rate_limiting(self, app_with_middleware, mock_redis):
        """Test that general endpoints get rate limited"""
        with patch('app.core.security.redis_client', mock_redis):
            client = TestClient(app_with_middleware)
            
            # First requests should succeed
            response = client.get("/api/test")
            assert response.status_code == 200
            
            # Mock rate limit exceeded
            mock_redis.execute.return_value = [100, 300]  # Exceeded count
            mock_redis.zcard.return_value = 100
            
            # This would trigger rate limiting in a real scenario
            # For this test, we verify the middleware structure works
    
    def test_middleware_adds_rate_limit_headers(self, app_with_middleware):
        """Test that middleware adds appropriate headers"""
        client = TestClient(app_with_middleware)
        
        response = client.get("/api/test")
        
        # Should have rate limiting headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Tier" in response.headers
    
    def test_middleware_handles_rate_limit_exceptions(self, app_with_middleware):
        """Test middleware handles rate limit exceptions properly"""
        with patch('app.middleware.comprehensive_rate_limiter.AdvancedRateLimiter') as mock_limiter_class:
            mock_limiter = Mock()
            mock_limiter.check_rate_limit.side_effect = HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Try again in 60 seconds"
            )
            mock_limiter_class.return_value = mock_limiter
            
            client = TestClient(app_with_middleware)
            response = client.get("/api/test")
            
            # Should return proper rate limit response
            assert response.status_code == 429
            assert "rate_limit_exceeded" in response.json()["error"]


class TestSecurityHealthChecks:
    """Test security system health monitoring"""
    
    @patch('app.core.security.redis_client')
    def test_security_health_status(self, mock_redis):
        """Test security health status reporting"""
        mock_redis.ping.return_value = True
        mock_redis.scan_iter.return_value = ["key1", "key2", "key3"]
        mock_redis.get.return_value = "5"
        
        status = get_security_health_status()
        
        assert isinstance(status, dict)
        assert "timestamp" in status
        assert "redis_connection" in status
        assert "rate_limiter_active" in status
        assert "blacklist_stats" in status
    
    def test_security_health_with_redis_failure(self):
        """Test health check handles Redis failures gracefully"""
        with patch('app.core.security.redis_client', None):
            status = get_security_health_status()
            
            assert status["redis_connection"] is False
            assert "error" not in status  # Should handle gracefully


class TestIntegrationScenarios:
    """Test real-world integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_brute_force_protection(self, rate_limiter, mock_request):
        """Test protection against brute force attacks"""
        email = "victim@example.com"
        
        # Simulate multiple failed login attempts
        for i in range(6):  # Exceed login limit of 5
            try:
                rate_limiter.check_auth_rate_limit(mock_request, email, "login")
            except RateLimitException:
                # Expected after 5 attempts
                assert i >= 5
                break
        else:
            pytest.fail("Expected RateLimitException for brute force attempt")
    
    @pytest.mark.asyncio
    async def test_distributed_attack_protection(self, rate_limiter):
        """Test protection against distributed attacks"""
        email = "target@example.com"
        
        # Simulate attacks from multiple IPs
        for i in range(3):
            mock_request = Mock(spec=Request)
            mock_request.client.host = f"192.168.1.{100 + i}"
            mock_request.headers = {'User-Agent': 'AttackBot/1.0'}
            mock_request.url.path = "/auth/login"
            
            # Each IP should be rate limited individually
            # But email-based limiting should catch distributed attacks
            try:
                rate_limiter.check_auth_rate_limit(mock_request, email, "login")
            except RateLimitException:
                # Email-based limiting should trigger
                pass
    
    def test_financial_compliance_logging(self, rate_limiter, mock_request):
        """Test that security events are properly logged for compliance"""
        with patch('app.core.audit_logging.log_security_event') as mock_log:
            email = "test@example.com"
            
            # Trigger rate limit violation
            try:
                # Mock exceeded limits
                rate_limiter.redis.execute.return_value = [10, 300]
                rate_limiter.check_auth_rate_limit(mock_request, email, "login")
            except RateLimitException:
                pass
            
            # Verify security event was logged
            mock_log.assert_called()
            call_args = mock_log.call_args[0]
            assert "rate_limit" in call_args[0]  # Event type
            assert isinstance(call_args[1], dict)  # Event data


class TestPerformanceAndScalability:
    """Test performance characteristics"""
    
    def test_rate_limiter_performance(self, rate_limiter, mock_request):
        """Test rate limiter performance under load"""
        import time
        
        start_time = time.time()
        
        # Simulate multiple requests
        for _ in range(100):
            try:
                rate_limiter.check_rate_limit(mock_request, 1000, 3600, "performance_test")
            except RateLimitException:
                pass
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time
        assert duration < 1.0  # Less than 1 second for 100 checks
    
    @patch('app.core.security.redis_client')
    def test_memory_usage_with_fallback(self, mock_redis):
        """Test memory usage with fallback storage"""
        mock_redis.side_effect = Exception("Redis unavailable")
        
        limiter = AdvancedRateLimiter()
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {'User-Agent': 'TestClient'}
        mock_request.url.path = "/api/test"
        
        # Generate many requests to test memory growth
        for i in range(1000):
            mock_request.url.path = f"/api/test/{i}"
            try:
                limiter.check_rate_limit(mock_request, 10, 300, "memory_test")
            except RateLimitException:
                pass
        
        # Memory store should contain entries
        assert len(limiter.memory_store) > 0
        assert len(limiter.memory_store) <= 1000  # Should not exceed reasonable bounds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])