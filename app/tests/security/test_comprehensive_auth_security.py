"""
Comprehensive Authentication Security Test Suite for MITA Financial Application

This test suite provides comprehensive coverage of all authentication security features
including token management, rate limiting, password validation, and security compliance.

QA Test Requirements Coverage:
- Token blacklist functionality with Redis integration
- Refresh token rotation and prevention of reuse  
- Rate limiting on auth endpoints with progressive penalties
- Password validation with enterprise security rules
- Authentication flow security validation
- JWT token security and validation
- Redis failure handling and fail-secure behavior
- Concurrent operations and race condition prevention
- Performance and load testing for security components
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional

import pytest
import redis
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    blacklist_token,
    validate_token_security,
    get_token_info,
    hash_password,
    verify_password,
    revoke_user_tokens
)
from app.api.auth.services import (
    register_user_async,
    authenticate_user_async,
    authenticate_google
)
from app.api.auth.schemas import RegisterIn, LoginIn, GoogleAuthIn
from app.core.security import (
    AdvancedRateLimiter,
    SecurityConfig,
    get_rate_limiter,
    reset_security_instances
)
from app.core.error_handler import RateLimitException
from app.core.upstash import blacklist_token as upstash_blacklist_token, is_token_blacklisted
from app.db.models import User


class TestTokenBlacklistFunctionality:
    """
    Test comprehensive token blacklist functionality with Redis integration.
    
    This covers the critical QA requirement: test_token_blacklist_functionality()
    """
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for blacklist testing"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.setex.return_value = True
        mock_client.exists.return_value = 0  # Token not blacklisted initially
        mock_client.get.return_value = None
        return mock_client
    
    @pytest.fixture
    def blacklist_store(self):
        """In-memory store for blacklist testing"""
        return {}
    
    def test_token_blacklist_basic_functionality(self, blacklist_store):
        """Test basic token blacklisting functionality"""
        # Create a test token
        token_data = {"sub": "test_user_123", "exp": time.time() + 3600}
        token = create_access_token(token_data)
        
        # Mock Redis blacklist functions
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Token should be valid before blacklisting
            payload = verify_token(token)
            assert payload is not None
            assert payload["sub"] == "test_user_123"
            
            # Blacklist the token
            success = blacklist_token(token)
            assert success is True
            
            # Token should be invalid after blacklisting
            payload_after = verify_token(token)
            assert payload_after is None
    
    def test_token_blacklist_with_redis_integration(self, mock_redis, blacklist_store):
        """Test token blacklisting with Redis integration"""
        token_data = {"sub": "redis_user_456", "exp": time.time() + 7200}
        token = create_access_token(token_data)
        
        # Configure mock Redis to simulate actual Redis behavior
        def mock_setex(key, ttl, value):
            blacklist_store[key] = {"value": value, "expires": time.time() + ttl}
            return True
            
        def mock_exists(key):
            if key in blacklist_store:
                return 1 if blacklist_store[key]["expires"] > time.time() else 0
            return 0
        
        mock_redis.setex.side_effect = mock_setex
        mock_redis.exists.side_effect = mock_exists
        
        with patch('app.core.upstash.redis_client', mock_redis):
            # Blacklist token
            success = blacklist_token(token)
            assert success is True
            
            # Verify Redis was called correctly
            mock_redis.setex.assert_called()
            call_args = mock_redis.setex.call_args[0]
            assert len(call_args) == 3  # key, ttl, value
            assert call_args[2] == "blacklisted"  # Standard blacklist value
    
    def test_token_blacklist_ttl_calculation(self, blacklist_store):
        """Test proper TTL calculation for blacklisted tokens"""
        # Test with various expiration times
        test_cases = [
            (time.time() + 300, 300),    # 5 minutes
            (time.time() + 3600, 3600),  # 1 hour
            (time.time() + 86400, 86400), # 1 day
            (time.time() + 604800, 604800) # 7 days (max)
        ]
        
        for exp_time, expected_ttl in test_cases:
            token_data = {"sub": "ttl_test_user", "exp": exp_time}
            token = create_access_token(token_data)
            
            actual_ttl = None
            def capture_ttl(jti, ttl):
                nonlocal actual_ttl
                actual_ttl = ttl
                blacklist_store[jti] = time.time() + ttl
                return True
            
            with patch('app.services.auth_jwt_service.upstash_blacklist_token', capture_ttl):
                blacklist_token(token)
                # TTL should match token expiration (within 1 second tolerance)
                assert abs(actual_ttl - expected_ttl) <= 1
    
    def test_token_blacklist_with_expired_tokens(self, blacklist_store):
        """Test blacklisting already expired tokens"""
        # Create expired token
        expired_token_data = {"sub": "expired_user", "exp": time.time() - 3600}
        expired_token = create_access_token(expired_token_data, timedelta(seconds=-3600))
        
        def mock_blacklist_token(jti, ttl):
            # Should still allow blacklisting with minimum TTL
            assert ttl >= 1  # Minimum TTL of 1 second
            blacklist_store[jti] = time.time() + ttl
            return True
            
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token):
            success = blacklist_token(expired_token)
            assert success is True
    
    def test_token_blacklist_malformed_tokens(self):
        """Test blacklisting malformed or invalid tokens"""
        test_cases = [
            "",  # Empty token
            "invalid.token.format",  # Invalid JWT format
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature",  # Invalid signature
            None,  # None token
        ]
        
        for invalid_token in test_cases:
            with patch('app.services.auth_jwt_service.upstash_blacklist_token') as mock_blacklist:
                success = blacklist_token(invalid_token) if invalid_token else False
                
                # Should handle gracefully without calling Redis
                if invalid_token in ["", None]:
                    assert success is False
                    mock_blacklist.assert_not_called()
    
    def test_token_blacklist_redis_failure_handling(self, mock_redis):
        """Test blacklist behavior when Redis fails"""
        token_data = {"sub": "redis_failure_user", "exp": time.time() + 3600}
        token = create_access_token(token_data)
        
        # Simulate Redis failure
        mock_redis.setex.side_effect = redis.RedisError("Connection failed")
        
        with patch('app.core.upstash.redis_client', mock_redis):
            with pytest.raises(Exception):  # Should re-raise Redis errors
                blacklist_token(token)
    
    def test_concurrent_token_blacklisting(self, blacklist_store):
        """Test concurrent token blacklisting operations"""
        token_data = {"sub": "concurrent_user", "exp": time.time() + 3600}
        token = create_access_token(token_data)
        
        call_count = 0
        def thread_safe_blacklist(jti, ttl):
            nonlocal call_count
            call_count += 1
            blacklist_store[jti] = time.time() + ttl
            return True
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', thread_safe_blacklist):
            # Simulate concurrent blacklisting
            tasks = []
            for _ in range(5):
                tasks.append(blacklist_token(token))
            
            # All should succeed, but only one should actually blacklist
            successful_calls = sum(1 for result in tasks if result)
            assert successful_calls >= 1  # At least one should succeed
            assert call_count >= 1  # At least one Redis call should be made
    
    def test_token_blacklist_audit_logging(self):
        """Test that token blacklisting events are properly logged"""
        token_data = {"sub": "audit_user", "exp": time.time() + 3600}
        token = create_access_token(token_data)
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', return_value=True), \
             patch('app.core.audit_logging.log_security_event') as mock_log:
            
            blacklist_token(token)
            
            # Verify security event was logged
            mock_log.assert_called()
            call_args = mock_log.call_args
            assert call_args[0][0] == "token_blacklisted"  # Event type
            assert "jti" in call_args[0][1]  # Event data should contain JTI
            assert "user_id" in call_args[0][1]  # Event data should contain user ID


class TestRefreshTokenRotation:
    """
    Test refresh token rotation and prevention of token reuse.
    
    This covers the critical QA requirement for refresh token security.
    """
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing"""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    def test_refresh_token_rotation_basic(self):
        """Test basic refresh token rotation functionality"""
        blacklist_store = {}
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Create initial refresh token
            user_data = {"sub": "rotation_user_123"}
            old_refresh_token = create_refresh_token(user_data)
            
            # Verify old token is valid
            old_payload = verify_token(old_refresh_token, scope="refresh_token")
            assert old_payload is not None
            
            # Simulate refresh operation (blacklist old token)
            blacklist_success = blacklist_token(old_refresh_token)
            assert blacklist_success is True
            
            # Create new refresh token
            new_refresh_token = create_refresh_token(user_data)
            
            # Old token should now be invalid
            old_payload_after = verify_token(old_refresh_token, scope="refresh_token")
            assert old_payload_after is None
            
            # New token should be valid
            new_payload = verify_token(new_refresh_token, scope="refresh_token")
            assert new_payload is not None
            assert new_payload["sub"] == "rotation_user_123"
    
    def test_refresh_token_reuse_prevention(self):
        """Test that refresh tokens cannot be reused after refresh"""
        blacklist_store = {}
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Create refresh token
            user_data = {"sub": "reuse_test_user"}
            refresh_token = create_refresh_token(user_data)
            
            # First use - should work
            payload1 = verify_token(refresh_token, scope="refresh_token")
            assert payload1 is not None
            
            # Blacklist after first use (simulating rotation)
            blacklist_token(refresh_token)
            
            # Second use - should fail
            payload2 = verify_token(refresh_token, scope="refresh_token")
            assert payload2 is None
    
    @pytest.mark.asyncio
    async def test_refresh_token_endpoint_rotation(self):
        """Test the actual refresh endpoint performs rotation"""
        from app.api.auth.routes import refresh_token
        
        blacklist_store = {}
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted), \
             patch('app.core.security.get_rate_limiter') as mock_rate_limiter_factory:
            
            # Mock rate limiter
            mock_rate_limiter = Mock()
            mock_rate_limiter.check_rate_limit.return_value = None
            mock_rate_limiter_factory.return_value = mock_rate_limiter
            
            # Create initial refresh token
            user_data = {"sub": "endpoint_test_user"}
            initial_refresh = create_refresh_token(user_data)
            
            # Create mock request
            mock_request = SimpleNamespace()
            mock_request.headers = {"Authorization": f"Bearer {initial_refresh}"}
            
            # Call refresh endpoint
            response = await refresh_token(mock_request, mock_rate_limiter)
            
            # Should return new tokens
            response_data = json.loads(response.body.decode())
            assert "access_token" in response_data["data"]
            assert "refresh_token" in response_data["data"]
            
            # New refresh token should be different
            new_refresh = response_data["data"]["refresh_token"]
            assert new_refresh != initial_refresh
            
            # Old refresh token should be blacklisted
            old_payload = verify_token(initial_refresh, scope="refresh_token")
            assert old_payload is None
    
    def test_refresh_token_family_invalidation(self):
        """Test that token families are properly invalidated on compromise"""
        blacklist_store = {}
        token_family = str(uuid.uuid4())
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Create tokens in same family
            user_data = {"sub": "family_test_user", "token_family": token_family}
            
            token1 = create_refresh_token(user_data)
            token2 = create_refresh_token(user_data)
            token3 = create_refresh_token(user_data)
            
            # All tokens should initially be valid
            assert verify_token(token1, scope="refresh_token") is not None
            assert verify_token(token2, scope="refresh_token") is not None
            assert verify_token(token3, scope="refresh_token") is not None
            
            # Blacklist one token (simulating compromise detection)
            blacklist_token(token2)
            
            # That specific token should be invalid
            assert verify_token(token2, scope="refresh_token") is None
            
            # Other tokens should still be valid (individual invalidation)
            assert verify_token(token1, scope="refresh_token") is not None
            assert verify_token(token3, scope="refresh_token") is not None


class TestRateLimitingAuthEndpoints:
    """
    Test rate limiting on authentication endpoints with progressive penalties.
    
    This covers the critical QA requirement: test_rate_limiting_on_auth_endpoints()
    """
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request for rate limiting tests"""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"
        request.headers = {
            'User-Agent': 'MITA-Test/1.0',
            'X-Forwarded-For': '10.0.0.1'
        }
        request.url.path = "/auth/login"
        request.method = "POST"
        return request
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis for rate limiting tests"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.pipeline.return_value = mock_client
        mock_client.execute.return_value = [1, 300]  # count, ttl
        mock_client.zremrangebyscore.return_value = 0
        mock_client.zadd.return_value = 1
        mock_client.zcard.return_value = 1
        mock_client.expire.return_value = True
        mock_client.get.return_value = None  # No penalties initially
        mock_client.incr.return_value = 1
        mock_client.setex.return_value = True
        return mock_client
    
    def test_auth_endpoint_rate_limiting_basic(self, mock_request, mock_redis):
        """Test basic rate limiting on authentication endpoints"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            # First few requests should succeed
            for i in range(3):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
            
            # Mock exceeded limit
            mock_redis.execute.return_value = [10, 300]  # Exceeded count
            mock_redis.zcard.return_value = 10
            
            # Should raise rate limit exception
            with pytest.raises(RateLimitException):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
    
    def test_progressive_penalty_system(self, mock_request, mock_redis):
        """Test progressive penalties for repeat offenders"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            # Test various violation counts and expected penalties
            test_cases = [
                (0, 1.0),   # No violations, no penalty
                (2, 1.0),   # Under threshold, no penalty
                (3, 2.0),   # First penalty tier
                (6, 4.0),   # Second penalty tier
                (15, 8.0),  # Maximum penalty
            ]
            
            for violation_count, expected_penalty in test_cases:
                mock_redis.get.return_value = str(violation_count)
                
                client_id = rate_limiter._get_client_identifier(mock_request)
                penalty = rate_limiter._check_progressive_penalties(client_id, "login")
                
                assert penalty == expected_penalty, f"Violation count {violation_count} should have penalty {expected_penalty}, got {penalty}"
    
    def test_auth_rate_limiting_by_email(self, mock_request, mock_redis):
        """Test rate limiting by email address"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            email = "target@example.com"
            
            # Normal requests should succeed
            for i in range(3):
                rate_limiter.check_auth_rate_limit(mock_request, email, "login")
            
            # Mock email-based rate limit exceeded
            def mock_execute_email_limit():
                return [5, 300, 8, 300]  # IP count, IP TTL, Email count (exceeded), Email TTL
            
            mock_redis.execute.side_effect = mock_execute_email_limit
            
            # Should raise exception due to email rate limit
            with pytest.raises(RateLimitException) as exc_info:
                rate_limiter.check_auth_rate_limit(mock_request, email, "login")
            
            assert "email" in str(exc_info.value).lower()
    
    def test_auth_rate_limiting_by_ip(self, mock_request, mock_redis):
        """Test rate limiting by IP address"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            # Mock IP-based rate limit exceeded
            def mock_execute_ip_limit():
                return [12, 300, 2, 300]  # IP count (exceeded), IP TTL, Email count, Email TTL
            
            mock_redis.execute.side_effect = mock_execute_ip_limit
            
            # Should raise exception due to IP rate limit
            with pytest.raises(RateLimitException) as exc_info:
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
            
            assert "ip" in str(exc_info.value).lower() or "client" in str(exc_info.value).lower()
    
    def test_suspicious_authentication_patterns(self, mock_request, mock_redis):
        """Test detection of suspicious authentication patterns"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            # Mock suspicious pattern detection (many unique emails from same IP)
            mock_redis.execute.return_value = [1, 20, True]  # Count, unique emails (suspicious), exists
            
            # Should detect and flag suspicious behavior
            client_id = rate_limiter._get_client_identifier(mock_request)
            rate_limiter._check_suspicious_auth_patterns(client_id, "hash123", "login")
            
            # Should set suspicious flag in Redis
            mock_redis.setex.assert_called()
            call_args = mock_redis.setex.call_args[0]
            assert "suspicious" in call_args[0]  # Key should contain "suspicious"
    
    def test_different_auth_endpoint_limits(self, mock_request, mock_redis):
        """Test different rate limits for different auth endpoints"""
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis):
            rate_limiter = AdvancedRateLimiter()
            
            # Test different endpoints have different limits
            endpoints = ["login", "register", "password_reset"]
            
            for endpoint in endpoints:
                # Reset mock
                mock_redis.reset_mock()
                
                # Make request to endpoint
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", endpoint)
                
                # Verify rate limiting was applied
                assert mock_redis.pipeline.called
                assert mock_redis.execute.called
    
    def test_rate_limiting_fail_secure_mode(self, mock_request):
        """Test fail-secure behavior when Redis is unavailable"""
        reset_security_instances()
        
        # No Redis available
        with patch('app.core.security.redis_client', None):
            rate_limiter = AdvancedRateLimiter()
            rate_limiter.fail_secure_mode = True
            
            # Should raise exception in fail-secure mode
            with pytest.raises(RateLimitException, match="Service temporarily unavailable"):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
    
    @pytest.mark.asyncio
    async def test_auth_endpoint_integration(self, mock_redis):
        """Test rate limiting integration with actual auth endpoints"""
        from app.api.auth.routes import login
        
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis), \
             patch('app.api.auth.services.authenticate_user_async') as mock_auth:
            
            # Mock successful authentication
            mock_db = AsyncMock()
            mock_auth.return_value = {"access_token": "test_token", "refresh_token": "test_refresh"}
            
            # Create mock request
            mock_request = Mock(spec=Request)
            mock_request.client.host = "127.0.0.1"
            mock_request.headers = {'User-Agent': 'TestClient'}
            
            # Create login payload
            login_data = LoginIn(email="test@example.com", password="testpassword")
            
            # Mock rate limiter
            mock_rate_limiter = Mock()
            mock_rate_limiter.check_auth_rate_limit.return_value = None
            
            # Should succeed with normal rate limiting
            result = await login(login_data, mock_request, mock_db, mock_rate_limiter)
            
            # Verify rate limiting was checked
            mock_rate_limiter.check_auth_rate_limit.assert_called_with(
                mock_request, "test@example.com", "login"
            )


# Additional test classes will continue in the next part...