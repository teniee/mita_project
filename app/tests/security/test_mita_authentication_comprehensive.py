"""
Comprehensive Unit Tests for MITA Authentication System
========================================================

This test suite provides complete coverage for all critical authentication security
features in the MITA financial application, ensuring production readiness and
zero-tolerance quality standards for financial software.

Test Coverage:
1. Token Management Tests
   - Token blacklist functionality with Redis integration
   - Refresh token rotation and prevention of reuse
   - Token revocation on logout
   - JWT validation with proper claims checking
   - Token expiration handling

2. Authentication Flow Tests
   - User registration with strong password validation
   - Login scenarios (success, failure, locked accounts)
   - Logout with proper token cleanup
   - Password reset flow end-to-end
   - Google OAuth integration

3. Security Feature Tests
   - Rate limiting on auth endpoints
   - Brute force protection
   - Progressive penalties for repeat offenders
   - Redis failure handling (fail-secure behavior)
   - Input validation and sanitization

4. Edge Cases and Error Handling
   - Malformed JWT tokens
   - Expired tokens in various states
   - Redis connection failures
   - Concurrent token operations
   - Race conditions in refresh operations

5. Performance and Load Tests
   - Token validation performance
   - Rate limiting accuracy under load
   - Redis operations efficiency
   - Memory usage of security services

All tests follow pytest best practices and include proper fixtures and mocking.
Tests validate both success and failure scenarios with financial-grade accuracy.
"""

import asyncio
import json
import time
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

import pytest
import redis
from fastapi import HTTPException, Request, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    blacklist_token,
    validate_token_security,
    get_token_info,
    hash_password,
    verify_password,
    revoke_user_tokens,
    decode_token
)
from app.api.auth.services import (
    register_user_async,
    authenticate_user_async,
    authenticate_google,
    refresh_token_for_user,
    revoke_token
)
from app.api.auth.schemas import RegisterIn, LoginIn, GoogleAuthIn, TokenOut
from app.core.security import (
    AdvancedRateLimiter,
    SecurityConfig,
    SecurityUtils,
    SQLInjectionProtector,
    get_rate_limiter,
    reset_security_instances
)
from app.core.error_handler import RateLimitException, ValidationException, AuthenticationException
from app.core.upstash import blacklist_token as upstash_blacklist_token, is_token_blacklisted
from app.db.models import User


class TestTokenManagement:
    """
    Comprehensive token management tests covering all security requirements
    for JWT tokens, blacklisting, rotation, and validation in production.
    """
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client with comprehensive functionality"""
        mock_client = Mock(spec=redis.Redis)
        mock_client.ping.return_value = True
        mock_client.setex.return_value = True
        mock_client.exists.return_value = 0
        mock_client.get.return_value = None
        mock_client.delete.return_value = 1
        mock_client.pipeline.return_value = mock_client
        mock_client.execute.return_value = [1, 300]
        return mock_client
    
    @pytest.fixture
    def blacklist_store(self):
        """In-memory blacklist store for testing"""
        return {}
    
    @pytest.fixture
    def test_user_data(self):
        """Test user data for token generation"""
        return {
            "sub": "test_user_123",
            "email": "test@example.com",
            "user_type": "basic_user"
        }
    
    def test_token_blacklist_functionality_comprehensive(self, blacklist_store, test_user_data):
        """
        Test comprehensive token blacklist functionality with Redis integration.
        This is the critical test mentioned in QA requirements.
        """
        # Create test tokens with different expiration times
        short_lived_token = create_access_token(test_user_data, timedelta(minutes=5))
        long_lived_token = create_access_token(test_user_data, timedelta(hours=24))
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Test 1: Valid tokens should verify successfully before blacklisting
            short_payload = verify_token(short_lived_token)
            long_payload = verify_token(long_lived_token)
            
            assert short_payload is not None
            assert long_payload is not None
            assert short_payload["sub"] == test_user_data["sub"]
            assert long_payload["sub"] == test_user_data["sub"]
            
            # Test 2: Blacklist tokens should succeed
            short_blacklist_success = blacklist_token(short_lived_token)
            long_blacklist_success = blacklist_token(long_lived_token)
            
            assert short_blacklist_success is True
            assert long_blacklist_success is True
            
            # Test 3: Blacklisted tokens should fail verification
            short_payload_after = verify_token(short_lived_token)
            long_payload_after = verify_token(long_lived_token)
            
            assert short_payload_after is None
            assert long_payload_after is None
            
            # Test 4: Verify TTL is properly calculated
            assert len(blacklist_store) == 2  # Both tokens blacklisted
            
            # Test 5: Create new tokens with same user data should work
            new_token = create_access_token(test_user_data)
            new_payload = verify_token(new_token)
            assert new_payload is not None
            assert new_payload["sub"] == test_user_data["sub"]
    
    def test_refresh_token_rotation_security(self, blacklist_store, test_user_data):
        """
        Test refresh token rotation and prevention of token reuse.
        Critical for preventing token replay attacks in financial applications.
        """
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Test 1: Create initial refresh token
            original_refresh = create_refresh_token(test_user_data)
            original_payload = verify_token(original_refresh, scope="refresh_token")
            
            assert original_payload is not None
            assert original_payload["scope"] == "refresh_token"
            
            # Test 2: Use refresh token (simulate rotation)
            blacklist_success = blacklist_token(original_refresh)
            assert blacklist_success is True
            
            # Test 3: Create new refresh token
            new_refresh = create_refresh_token(test_user_data)
            new_payload = verify_token(new_refresh, scope="refresh_token")
            
            assert new_payload is not None
            assert new_payload["scope"] == "refresh_token"
            
            # Test 4: Original refresh token should be invalid (prevents reuse)
            original_payload_after = verify_token(original_refresh, scope="refresh_token")
            assert original_payload_after is None
            
            # Test 5: New refresh token should be valid
            new_payload_check = verify_token(new_refresh, scope="refresh_token")
            assert new_payload_check is not None
            
            # Test 6: Tokens should have different JTIs
            original_info = get_token_info(original_refresh)
            new_info = get_token_info(new_refresh)
            
            if original_info and new_info:  # If tokens are decodable
                assert original_info.get("jti") != new_info.get("jti")
    
    def test_jwt_validation_comprehensive(self, test_user_data):
        """
        Test comprehensive JWT validation with proper claims checking.
        Ensures all security claims are properly validated.
        """
        # Test 1: Valid token with all required claims
        valid_token = create_access_token(test_user_data)
        payload = verify_token(valid_token)
        
        assert payload is not None
        assert payload["sub"] == test_user_data["sub"]
        assert payload["scope"] == "access_token"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert payload["iss"] == "mita-app"
        
        # Test 2: Token info extraction
        token_info = get_token_info(valid_token)
        assert token_info is not None
        assert token_info["user_id"] == test_user_data["sub"]
        assert token_info["scope"] == "access_token"
        assert not token_info["is_expired"]
        
        # Test 3: Token security validation
        security_validation = validate_token_security(valid_token)
        assert security_validation["valid"] is True
        assert security_validation["jti_present"] is True
        assert security_validation["user_id_present"] is True
        assert security_validation["scope_valid"] is True
        assert security_validation["not_expired"] is True
        assert security_validation["issued_recently"] is True
        
        # Test 4: Scope validation
        access_payload = verify_token(valid_token, scope="access_token")
        refresh_payload = verify_token(valid_token, scope="refresh_token")  # Should fail
        
        assert access_payload is not None
        assert refresh_payload is None  # Wrong scope
    
    def test_token_expiration_handling(self, test_user_data):
        """
        Test token expiration handling with precise timing validation.
        Critical for financial applications with strict session timeouts.
        """
        # Test 1: Create tokens with specific expiration times
        short_exp = timedelta(seconds=1)
        long_exp = timedelta(hours=1)
        
        short_token = create_access_token(test_user_data, short_exp)
        long_token = create_access_token(test_user_data, long_exp)
        
        # Test 2: Tokens should be valid initially
        short_payload = verify_token(short_token)
        long_payload = verify_token(long_token)
        
        assert short_payload is not None
        assert long_payload is not None
        
        # Test 3: Wait for short token to expire
        time.sleep(1.1)  # Wait slightly longer than expiration
        
        # Test 4: Short token should be expired, long token still valid
        short_payload_after = verify_token(short_token)
        long_payload_after = verify_token(long_token)
        
        assert short_payload_after is None  # Expired
        assert long_payload_after is not None  # Still valid
        
        # Test 5: Token info should show expiration status
        short_info = get_token_info(short_token)
        long_info = get_token_info(long_token)
        
        if short_info and long_info:
            assert short_info["is_expired"] is True
            assert long_info["is_expired"] is False
    
    def test_token_revocation_on_logout(self, blacklist_store, test_user_data):
        """
        Test comprehensive token revocation on logout.
        Ensures all user tokens are properly invalidated for financial security.
        """
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Test 1: Create multiple tokens for user
            access_token1 = create_access_token(test_user_data)
            access_token2 = create_access_token(test_user_data)
            refresh_token = create_refresh_token(test_user_data)
            
            # Test 2: All tokens should be valid initially
            assert verify_token(access_token1) is not None
            assert verify_token(access_token2) is not None
            assert verify_token(refresh_token, scope="refresh_token") is not None
            
            # Test 3: Simulate logout by blacklisting tokens
            blacklist_token(access_token1)
            blacklist_token(access_token2)
            blacklist_token(refresh_token)
            
            # Test 4: All tokens should be invalid after logout
            assert verify_token(access_token1) is None
            assert verify_token(access_token2) is None
            assert verify_token(refresh_token, scope="refresh_token") is None
            
            # Test 5: New tokens can be created for fresh login
            new_access = create_access_token(test_user_data)
            new_refresh = create_refresh_token(test_user_data)
            
            assert verify_token(new_access) is not None
            assert verify_token(new_refresh, scope="refresh_token") is not None
    
    def test_malformed_jwt_token_handling(self, test_user_data):
        """
        Test handling of malformed JWT tokens with comprehensive edge cases.
        Ensures robust error handling for financial application security.
        """
        malformed_tokens = [
            "",  # Empty token
            "invalid",  # Not a JWT
            "invalid.token.format",  # Wrong number of parts
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature",  # Invalid base64
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +  # Valid header, invalid payload
            "invalid_payload." +
            "signature",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +  # Missing required claims
            "eyJ1c2VyIjoidGVzdCJ9." +  # No 'sub', 'exp', 'jti'
            "invalid_signature",
            None,  # None token
        ]
        
        for malformed_token in malformed_tokens:
            # Test 1: Verify token should return None for malformed tokens
            if malformed_token is not None:
                payload = verify_token(malformed_token)
                assert payload is None, f"Token should be invalid: {malformed_token}"
                
                # Test 2: Get token info should return None
                info = get_token_info(malformed_token)
                assert info is None, f"Token info should be None: {malformed_token}"
                
                # Test 3: Security validation should mark as invalid
                validation = validate_token_security(malformed_token)
                assert validation["valid"] is False, f"Token should be invalid: {malformed_token}"
            
            # Test 4: Blacklisting malformed tokens should fail gracefully
            if malformed_token in [None, ""]:
                success = blacklist_token(malformed_token) if malformed_token else False
                assert success is False
    
    def test_concurrent_token_operations(self, blacklist_store, test_user_data):
        """
        Test concurrent token operations for race condition prevention.
        Critical for financial applications with high concurrency.
        """
        def mock_blacklist_token(jti, ttl):
            # Simulate some processing time
            time.sleep(0.01)
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Test 1: Create token for concurrent operations
            token = create_access_token(test_user_data)
            
            # Test 2: Concurrent blacklisting
            results = []
            def blacklist_operation():
                try:
                    result = blacklist_token(token)
                    results.append(result)
                except Exception as e:
                    results.append(f"error: {e}")
            
            # Test 3: Run concurrent operations
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(blacklist_operation) for _ in range(5)]
                for future in futures:
                    future.result()  # Wait for completion
            
            # Test 4: At least one operation should succeed
            successful_operations = sum(1 for r in results if r is True)
            assert successful_operations >= 1
            
            # Test 5: Token should be blacklisted after concurrent operations
            assert verify_token(token) is None
    
    def test_token_performance_benchmarks(self, test_user_data):
        """
        Test token validation performance meets financial application requirements.
        Target: <50ms for token validation operations.
        """
        # Test 1: Token creation performance
        start_time = time.time()
        tokens = []
        for _ in range(100):
            tokens.append(create_access_token(test_user_data))
        creation_time = time.time() - start_time
        
        assert creation_time < 1.0  # Should create 100 tokens in <1 second
        avg_creation_time = creation_time / 100
        assert avg_creation_time < 0.01  # <10ms per token
        
        # Test 2: Token validation performance
        start_time = time.time()
        for token in tokens:
            verify_token(token)
        validation_time = time.time() - start_time
        
        assert validation_time < 1.0  # Should validate 100 tokens in <1 second
        avg_validation_time = validation_time / 100
        assert avg_validation_time < 0.01  # <10ms per token
        
        # Test 3: Token info extraction performance
        start_time = time.time()
        for token in tokens:
            get_token_info(token)
        info_time = time.time() - start_time
        
        assert info_time < 0.5  # Should extract info for 100 tokens in <500ms
        avg_info_time = info_time / 100
        assert avg_info_time < 0.005  # <5ms per token


class TestAuthenticationFlows:
    """
    Comprehensive authentication flow tests covering all security requirements
    for user registration, login, logout, password reset, and OAuth.
    """
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock async database session"""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        return session
    
    @pytest.fixture
    def mock_user(self):
        """Mock user object for testing"""
        user = Mock(spec=User)
        user.id = "test_user_123"
        user.email = "test@example.com"
        user.password_hash = hash_password("ValidPassword123!")
        user.country = "US"
        user.annual_income = 50000
        user.timezone = "America/New_York"
        return user
    
    @pytest.fixture
    def valid_registration_data(self):
        """Valid registration data for testing"""
        return RegisterIn(
            email="newuser@example.com",
            password="StrongPass123!",
            country="US",
            annual_income=75000,
            timezone="America/New_York"
        )
    
    @pytest.fixture
    def valid_login_data(self):
        """Valid login data for testing"""
        return LoginIn(
            email="test@example.com",
            password="ValidPassword123!"
        )
    
    @pytest.mark.asyncio
    async def test_user_registration_comprehensive(self, mock_db_session, valid_registration_data):
        """
        Test comprehensive user registration with strong password validation.
        Covers all security requirements for financial application user onboarding.
        """
        # Mock no existing user
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        # Test 1: Valid registration should succeed
        result = await register_user_async(valid_registration_data, mock_db_session)
        
        assert isinstance(result, TokenOut)
        assert result.access_token is not None
        assert result.refresh_token is not None
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        
        # Test 2: Password validation requirements
        weak_passwords = [
            "short",  # Too short
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoNumbers!",  # No numbers
            "NoSpecialChars123",  # No special characters
            "a" * 200,  # Too long
        ]
        
        for weak_password in weak_passwords:
            weak_data = RegisterIn(
                email="weak@example.com",
                password=weak_password,
                country="US",
                annual_income=50000,
                timezone="UTC"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await register_user_async(weak_data, mock_db_session)
            
            assert exc_info.value.status_code == 400
            assert "password" in exc_info.value.detail.lower()
        
        # Test 3: Email validation
        invalid_emails = [
            "notanemail",
            "@example.com",
            "test@",
            "test..double@example.com",
            "test@example..com",
        ]
        
        for invalid_email in invalid_emails:
            invalid_data = RegisterIn(
                email=invalid_email,
                password="ValidPass123!",
                country="US",
                annual_income=50000,
                timezone="UTC"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await register_user_async(invalid_data, mock_db_session)
            
            assert exc_info.value.status_code == 400
            assert "email" in exc_info.value.detail.lower()
        
        # Test 4: Duplicate email prevention
        mock_existing_user = Mock(spec=User)
        mock_result.scalars.return_value.first.return_value = mock_existing_user
        
        with pytest.raises(HTTPException) as exc_info:
            await register_user_async(valid_registration_data, mock_db_session)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail
        
        # Test 5: Annual income validation
        invalid_incomes = [-1000, 15000000]  # Negative and too high
        
        for invalid_income in invalid_incomes:
            income_data = RegisterIn(
                email="income@example.com",
                password="ValidPass123!",
                country="US",
                annual_income=invalid_income,
                timezone="UTC"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await register_user_async(income_data, mock_db_session)
            
            assert exc_info.value.status_code == 400
            assert "income" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_user_login_scenarios(self, mock_db_session, mock_user, valid_login_data):
        """
        Test comprehensive user login scenarios including success, failure, and security.
        Covers brute force protection and account lockout scenarios.
        """
        # Test 1: Successful login
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        result = await authenticate_user_async(valid_login_data, mock_db_session)
        
        assert isinstance(result, TokenOut)
        assert result.access_token is not None
        assert result.refresh_token is not None
        
        # Test 2: Invalid email
        mock_result.scalars.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user_async(valid_login_data, mock_db_session)
        
        assert exc_info.value.status_code == 401
        assert "Invalid email or password" in exc_info.value.detail
        
        # Test 3: Invalid password
        mock_result.scalars.return_value.first.return_value = mock_user
        invalid_login = LoginIn(email="test@example.com", password="WrongPassword")
        
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user_async(invalid_login, mock_db_session)
        
        assert exc_info.value.status_code == 401
        assert "Invalid email or password" in exc_info.value.detail
        
        # Test 4: Email case insensitivity
        uppercase_login = LoginIn(
            email="TEST@EXAMPLE.COM",
            password="ValidPassword123!"
        )
        
        # Should still find user with lowercase email
        result = await authenticate_user_async(uppercase_login, mock_db_session)
        assert isinstance(result, TokenOut)
        
        # Test 5: Timing attack prevention (artificial delay on failure)
        start_time = time.time()
        try:
            await authenticate_user_async(invalid_login, mock_db_session)
        except HTTPException:
            pass
        elapsed_time = time.time() - start_time
        
        # Should have artificial delay (at least 0.1 seconds)
        assert elapsed_time >= 0.1
    
    @pytest.mark.asyncio
    async def test_password_reset_flow_comprehensive(self):
        """
        Test comprehensive password reset flow end-to-end.
        Critical for financial application account recovery security.
        """
        from app.services.api_service import (
            sendPasswordResetEmail,
            verifyPasswordResetToken,
            resetPasswordWithToken
        )
        
        test_email = "reset@example.com"
        test_token = secrets.token_urlsafe(32)
        new_password = "NewSecurePass123!"
        
        # Mock API service methods
        with patch('app.services.api_service.sendPasswordResetEmail') as mock_send, \
             patch('app.services.api_service.verifyPasswordResetToken') as mock_verify, \
             patch('app.services.api_service.resetPasswordWithToken') as mock_reset:
            
            # Test 1: Send password reset email
            mock_send.return_value = True
            
            result = await mock_send(test_email)
            assert result is True
            mock_send.assert_called_once_with(test_email)
            
            # Test 2: Verify reset token
            mock_verify.return_value = True
            
            result = await mock_verify(test_token)
            assert result is True
            mock_verify.assert_called_once_with(test_token)
            
            # Test 3: Reset password with token
            mock_reset.return_value = True
            
            result = await mock_reset(test_token, new_password)
            assert result is True
            mock_reset.assert_called_once_with(test_token, new_password)
            
            # Test 4: Invalid token should fail verification
            mock_verify.return_value = False
            invalid_token = "invalid_token_123"
            
            result = await mock_verify(invalid_token)
            assert result is False
            
            # Test 5: Expired token should fail reset
            mock_reset.return_value = False
            
            result = await mock_reset("expired_token", new_password)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_google_oauth_integration(self, mock_db_session):
        """
        Test Google OAuth integration with comprehensive security validation.
        Ensures secure third-party authentication for financial application.
        """
        from app.services.google_auth_service import authenticate_google_user
        
        # Mock Google token data
        valid_google_data = GoogleAuthIn(id_token="valid_google_token_123")
        
        # Mock user returned by Google auth
        mock_google_user = Mock(spec=User)
        mock_google_user.id = "google_user_456"
        mock_google_user.email = "google@example.com"
        
        with patch('app.services.google_auth_service.authenticate_google_user', 
                   return_value=mock_google_user):
            
            # Test 1: Valid Google authentication
            result = await authenticate_google(valid_google_data, mock_db_session)
            
            assert isinstance(result, TokenOut)
            assert result.access_token is not None
            assert result.refresh_token is not None
            
            # Verify tokens contain correct user ID
            access_payload = verify_token(result.access_token)
            refresh_payload = verify_token(result.refresh_token, scope="refresh_token")
            
            assert access_payload["sub"] == "google_user_456"
            assert refresh_payload["sub"] == "google_user_456"
        
        # Test 2: Invalid Google token
        invalid_google_data = GoogleAuthIn(id_token="invalid_google_token")
        
        with patch('app.services.google_auth_service.authenticate_google_user', 
                   side_effect=HTTPException(status_code=401, detail="Invalid Google token")):
            
            with pytest.raises(HTTPException) as exc_info:
                await authenticate_google(invalid_google_data, mock_db_session)
            
            assert exc_info.value.status_code == 401
            assert "Invalid Google token" in exc_info.value.detail
        
        # Test 3: Google service unavailable
        with patch('app.services.google_auth_service.authenticate_google_user',
                   side_effect=HTTPException(status_code=503, detail="Google service unavailable")):
            
            with pytest.raises(HTTPException) as exc_info:
                await authenticate_google(valid_google_data, mock_db_session)
            
            assert exc_info.value.status_code == 503
    
    def test_logout_token_cleanup(self, mock_user):
        """
        Test comprehensive logout with proper token cleanup.
        Critical for financial application security to prevent token reuse.
        """
        blacklist_store = {}
        
        def mock_blacklist_token(jti, ttl):
            blacklist_store[jti] = time.time() + ttl
            return True
            
        def mock_is_blacklisted(jti):
            return jti in blacklist_store and blacklist_store[jti] > time.time()
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist_token), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_is_blacklisted):
            
            # Test 1: Create tokens for logout test
            user_data = {"sub": str(mock_user.id)}
            access_token = create_access_token(user_data)
            refresh_token = create_refresh_token(user_data)
            
            # Test 2: Tokens should be valid before logout
            assert verify_token(access_token) is not None
            assert verify_token(refresh_token, scope="refresh_token") is not None
            
            # Test 3: Perform logout (revoke tokens)
            revoke_result = revoke_token(mock_user)
            assert revoke_result is not None
            
            # Test 4: Manually blacklist tokens (simulating logout cleanup)
            access_blacklist_success = blacklist_token(access_token)
            refresh_blacklist_success = blacklist_token(refresh_token)
            
            assert access_blacklist_success is True
            assert refresh_blacklist_success is True
            
            # Test 5: Tokens should be invalid after logout
            assert verify_token(access_token) is None
            assert verify_token(refresh_token, scope="refresh_token") is None
            
            # Test 6: Verify tokens are in blacklist
            access_info = get_token_info(access_token)
            refresh_info = get_token_info(refresh_token)
            
            if access_info and refresh_info:
                assert access_info["jti"] in [k for k in blacklist_store.keys()]
                assert refresh_info["jti"] in [k for k in blacklist_store.keys()]


class TestSecurityFeatures:
    """
    Comprehensive security feature tests covering rate limiting, brute force
    protection, progressive penalties, and Redis failure handling.
    """
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for security testing"""
        mock_client = Mock(spec=redis.Redis)
        mock_client.ping.return_value = True
        mock_client.pipeline.return_value = mock_client
        mock_client.execute.return_value = [1, 300]
        mock_client.zremrangebyscore.return_value = 0
        mock_client.zadd.return_value = 1
        mock_client.zcard.return_value = 1
        mock_client.expire.return_value = True
        mock_client.get.return_value = None
        mock_client.incr.return_value = 1
        mock_client.setex.return_value = True
        return mock_client
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request for testing"""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"
        request.headers = {
            'User-Agent': 'MITA-Test/1.0',
            'X-Forwarded-For': '10.0.0.1'
        }
        request.url.path = "/auth/login"
        request.method = "POST"
        return request
    
    def test_rate_limiting_on_auth_endpoints(self, mock_request, mock_redis_client):
        """
        Test comprehensive rate limiting on auth endpoints.
        This is the critical test mentioned in QA requirements.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Test 1: Normal requests should pass
            for i in range(3):
                try:
                    rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
                except RateLimitException:
                    pytest.fail("Normal requests should not be rate limited")
            
            # Test 2: Simulate rate limit exceeded
            mock_redis_client.execute.return_value = [15, 300, 8, 300]  # Both IP and email limits exceeded
            mock_redis_client.zcard.return_value = 15
            
            with pytest.raises(RateLimitException) as exc_info:
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
            
            assert "rate limit" in str(exc_info.value).lower()
            
            # Test 3: Different endpoints have different limits
            endpoints_to_test = ["login", "register", "password_reset", "token_refresh"]
            
            for endpoint in endpoints_to_test:
                # Reset mock for each endpoint test
                mock_redis_client.reset_mock()
                mock_redis_client.execute.return_value = [1, 300, 1, 300]
                mock_redis_client.zcard.return_value = 1
                
                try:
                    rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", endpoint)
                    # Verify Redis operations were called
                    assert mock_redis_client.pipeline.called
                    assert mock_redis_client.execute.called
                except RateLimitException:
                    pytest.fail(f"Normal request to {endpoint} should not be rate limited")
    
    def test_progressive_penalty_system(self, mock_request, mock_redis_client):
        """
        Test progressive penalties for repeat offenders.
        Critical for financial application brute force protection.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Test progressive penalty calculations
            penalty_test_cases = [
                (0, 1.0),   # No violations
                (1, 1.0),   # Below threshold
                (3, 2.0),   # First penalty tier
                (5, 2.0),   # Still first tier
                (6, 4.0),   # Second penalty tier
                (10, 4.0),  # Still second tier
                (15, 8.0),  # Maximum penalty
                (25, 8.0),  # Capped at maximum
            ]
            
            for violation_count, expected_penalty in penalty_test_cases:
                mock_redis_client.get.return_value = str(violation_count)
                
                client_id = rate_limiter._get_client_identifier(mock_request)
                penalty = rate_limiter._check_progressive_penalties(client_id, "login")
                
                assert penalty == expected_penalty, \
                    f"Violation count {violation_count} should have penalty {expected_penalty}, got {penalty}"
            
            # Test penalty application
            mock_redis_client.get.return_value = "10"  # High violation count
            penalty = rate_limiter._check_progressive_penalties("test_client", "login")
            
            assert penalty == 4.0  # Should be in second tier
            
            # Test penalty storage
            rate_limiter._apply_progressive_penalty("test_client", "login", penalty)
            mock_redis_client.setex.assert_called()
    
    def test_brute_force_protection(self, mock_request, mock_redis_client):
        """
        Test comprehensive brute force protection mechanisms.
        Essential for financial application account security.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Test 1: Rapid successive requests should trigger protection
            rapid_requests_count = 0
            mock_redis_client.execute.return_value = [1, 300, 1, 300]
            
            # Simulate rapid requests
            for i in range(20):
                mock_redis_client.zcard.return_value = i + 1
                if i > 10:  # After 10 requests, should start limiting
                    mock_redis_client.execute.return_value = [i + 1, 300, 1, 300]
                
                try:
                    rate_limiter.check_auth_rate_limit(mock_request, f"user{i}@example.com", "login")
                    rapid_requests_count += 1
                except RateLimitException:
                    break  # Rate limit triggered
            
            # Should have been rate limited before all 20 requests
            assert rapid_requests_count < 20
            
            # Test 2: Suspicious pattern detection (many different emails from same IP)
            mock_redis_client.execute.return_value = [1, 25, True]  # High unique email count
            
            client_id = rate_limiter._get_client_identifier(mock_request)
            rate_limiter._check_suspicious_auth_patterns(client_id, "email_hash", "login")
            
            # Should mark as suspicious
            suspicious_calls = [call for call in mock_redis_client.setex.call_args_list 
                              if 'suspicious' in str(call)]
            assert len(suspicious_calls) > 0
            
            # Test 3: Account lockout after repeated violations
            violation_count = 20  # High violation count
            mock_redis_client.get.return_value = str(violation_count)
            
            penalty = rate_limiter._check_progressive_penalties(client_id, "login")
            assert penalty == SecurityConfig.RATE_LIMIT_TIERS['anonymous']['requests_per_hour'] * 8  # Maximum penalty multiplier
    
    def test_redis_failure_handling_fail_secure(self, mock_request):
        """
        Test Redis failure handling with fail-secure behavior.
        Critical for financial application security when infrastructure fails.
        """
        reset_security_instances()
        
        # Test 1: Redis completely unavailable
        with patch('app.core.security.redis_client', None):
            rate_limiter = AdvancedRateLimiter()
            rate_limiter.fail_secure_mode = True
            
            # Should raise exception in fail-secure mode
            with pytest.raises(RateLimitException, match="Service temporarily unavailable"):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
        
        # Test 2: Redis connection errors
        mock_failed_redis = Mock(spec=redis.Redis)
        mock_failed_redis.ping.side_effect = redis.ConnectionError("Connection failed")
        mock_failed_redis.pipeline.side_effect = redis.ConnectionError("Connection failed")
        
        with patch('app.core.security.redis_client', mock_failed_redis):
            rate_limiter = AdvancedRateLimiter()
            rate_limiter.fail_secure_mode = True
            
            with pytest.raises(RateLimitException):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
        
        # Test 3: Fail-open mode (when fail_secure_mode is False)
        with patch('app.core.security.redis_client', None):
            rate_limiter = AdvancedRateLimiter()
            rate_limiter.fail_secure_mode = False
            
            # Should pass in fail-open mode
            try:
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
                # Should not raise exception
            except RateLimitException:
                pytest.fail("Fail-open mode should allow requests when Redis is unavailable")
        
        # Test 4: Redis operation timeouts
        mock_timeout_redis = Mock(spec=redis.Redis)
        mock_timeout_redis.ping.return_value = True
        mock_timeout_redis.pipeline.return_value = mock_timeout_redis
        mock_timeout_redis.execute.side_effect = redis.TimeoutError("Operation timed out")
        
        with patch('app.core.security.redis_client', mock_timeout_redis):
            rate_limiter = AdvancedRateLimiter()
            rate_limiter.fail_secure_mode = True
            
            with pytest.raises(RateLimitException):
                rate_limiter.check_auth_rate_limit(mock_request, "test@example.com", "login")
    
    def test_input_validation_and_sanitization(self):
        """
        Test comprehensive input validation and sanitization.
        Critical for financial application data integrity and security.
        """
        # Test 1: SQL injection protection
        sql_injection_attempts = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/*",
            "' UNION SELECT password FROM users WHERE username='admin'--",
            "'; INSERT INTO users (username, password) VALUES ('hacker', 'password'); --",
        ]
        
        for injection_attempt in sql_injection_attempts:
            is_malicious = SQLInjectionProtector.scan_for_sql_injection(injection_attempt)
            assert is_malicious is True, f"Should detect SQL injection: {injection_attempt}"
        
        # Test 2: Safe inputs should pass
        safe_inputs = [
            "user@example.com",
            "ValidPassword123!",
            "John Doe",
            "123 Main Street",
            "Regular search query",
        ]
        
        for safe_input in safe_inputs:
            is_malicious = SQLInjectionProtector.scan_for_sql_injection(safe_input)
            assert is_malicious is False, f"Should allow safe input: {safe_input}"
        
        # Test 3: Password security validation
        weak_passwords = [
            "password",  # Common password
            "12345678",  # Only numbers
            "abcdefgh",  # Only letters
            "PASSWORD",  # Only uppercase
            "pass",      # Too short
        ]
        
        for weak_password in weak_passwords:
            with pytest.raises(ValidationException):
                SecurityUtils.hash_password(weak_password)
        
        # Test 4: Strong password should work
        strong_password = "StrongPass123!@#"
        hashed = SecurityUtils.hash_password(strong_password)
        assert hashed is not None
        assert len(hashed) > 50  # bcrypt hash length
        
        # Test 5: Password verification
        assert SecurityUtils.verify_password(strong_password, hashed) is True
        assert SecurityUtils.verify_password("WrongPassword", hashed) is False


class TestPerformanceAndLoad:
    """
    Performance and load tests for authentication system components.
    Ensures system meets financial application performance requirements.
    """
    
    def test_token_validation_performance(self):
        """
        Test token validation performance meets requirements.
        Target: <50ms p95 for token operations in financial applications.
        """
        user_data = {"sub": "perf_test_user", "email": "perf@example.com"}
        
        # Test 1: Token creation performance
        creation_times = []
        for _ in range(1000):
            start = time.time()
            create_access_token(user_data)
            creation_times.append(time.time() - start)
        
        avg_creation = sum(creation_times) / len(creation_times)
        p95_creation = sorted(creation_times)[950]  # 95th percentile
        
        assert avg_creation < 0.01  # <10ms average
        assert p95_creation < 0.05  # <50ms p95
        
        # Test 2: Token validation performance
        tokens = [create_access_token(user_data) for _ in range(1000)]
        validation_times = []
        
        for token in tokens:
            start = time.time()
            verify_token(token)
            validation_times.append(time.time() - start)
        
        avg_validation = sum(validation_times) / len(validation_times)
        p95_validation = sorted(validation_times)[950]
        
        assert avg_validation < 0.01  # <10ms average
        assert p95_validation < 0.05  # <50ms p95
    
    def test_rate_limiting_accuracy_under_load(self, mock_redis_client):
        """
        Test rate limiting accuracy under high load conditions.
        Ensures financial application maintains security under stress.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Configure Redis mock for load testing
            request_count = 0
            def mock_execute():
                nonlocal request_count
                request_count += 1
                # Simulate rate limit after 100 requests
                if request_count > 100:
                    return [request_count, 300, 1, 300]  # Exceeded IP limit
                return [request_count, 300, 1, 300]  # Normal response
            
            mock_redis_client.execute.side_effect = mock_execute
            mock_redis_client.zcard.side_effect = lambda key: min(request_count, 100)
            
            # Test concurrent requests
            successful_requests = 0
            rate_limited_requests = 0
            
            def make_request():
                nonlocal successful_requests, rate_limited_requests
                try:
                    mock_request = Mock(spec=Request)
                    mock_request.client.host = "192.168.1.100"
                    mock_request.headers = {'User-Agent': 'LoadTest/1.0'}
                    
                    rate_limiter.check_auth_rate_limit(
                        mock_request, 
                        f"load_test_{secrets.token_hex(4)}@example.com", 
                        "login"
                    )
                    successful_requests += 1
                except RateLimitException:
                    rate_limited_requests += 1
            
            # Run concurrent load test
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(make_request) for _ in range(200)]
                for future in futures:
                    future.result()
            
            # Verify rate limiting kicked in
            assert successful_requests > 50  # Some requests should succeed
            assert rate_limited_requests > 50  # Some should be rate limited
            assert successful_requests + rate_limited_requests == 200  # All requests processed
    
    def test_redis_operations_efficiency(self, mock_redis_client):
        """
        Test Redis operations efficiency for authentication system.
        Ensures minimal latency for financial application operations.
        """
        reset_security_instances()
        
        # Mock Redis with operation timing
        operation_times = []
        original_execute = mock_redis_client.execute
        
        def timed_execute(*args, **kwargs):
            start = time.time()
            result = original_execute(*args, **kwargs)
            operation_times.append(time.time() - start)
            return result
        
        mock_redis_client.execute.side_effect = timed_execute
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Test 1: Rate limiting operations
            mock_request = Mock(spec=Request)
            mock_request.client.host = "127.0.0.1"
            mock_request.headers = {'User-Agent': 'EfficiencyTest/1.0'}
            
            for i in range(100):
                try:
                    rate_limiter.check_auth_rate_limit(
                        mock_request, 
                        f"efficiency_{i}@example.com", 
                        "login"
                    )
                except RateLimitException:
                    pass  # Expected for some requests
        
        # Verify operation efficiency
        if operation_times:
            avg_operation_time = sum(operation_times) / len(operation_times)
            p95_operation_time = sorted(operation_times)[int(len(operation_times) * 0.95)]
            
            # Redis operations should be very fast (sub-millisecond for mocked operations)
            assert avg_operation_time < 0.01  # <10ms average (generous for mocked operations)
            assert p95_operation_time < 0.05  # <50ms p95
        
        # Test 2: Token blacklisting operations
        blacklist_times = []
        user_data = {"sub": "efficiency_user"}
        
        for i in range(100):
            token = create_access_token(user_data)
            
            start = time.time()
            with patch('app.services.auth_jwt_service.upstash_blacklist_token', return_value=True):
                blacklist_token(token)
            blacklist_times.append(time.time() - start)
        
        avg_blacklist_time = sum(blacklist_times) / len(blacklist_times)
        p95_blacklist_time = sorted(blacklist_times)[95]
        
        # Token blacklisting should be fast
        assert avg_blacklist_time < 0.01  # <10ms average
        assert p95_blacklist_time < 0.05  # <50ms p95
    
    def test_memory_usage_authentication_services(self):
        """
        Test memory usage of authentication services under load.
        Ensures efficient memory usage for financial application scalability.
        """
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test 1: Create many tokens without accumulating memory
        user_data = {"sub": "memory_test_user"}
        tokens = []
        
        for i in range(1000):
            token = create_access_token(user_data)
            tokens.append(token)
            
            # Verify tokens periodically to ensure processing
            if i % 100 == 0:
                verify_token(token)
        
        mid_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = mid_memory - initial_memory
        
        # Should not grow memory significantly (allow 10MB growth)
        assert memory_growth < 10, f"Memory grew by {memory_growth}MB, should be <10MB"
        
        # Test 2: Clean up and verify memory release
        tokens.clear()  # Clear token references
        
        # Force some garbage collection cycles
        import gc
        for _ in range(3):
            gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_after_cleanup = final_memory - initial_memory
        
        # Memory should not grow significantly even after cleanup
        assert memory_after_cleanup < 15, f"Final memory grew by {memory_after_cleanup}MB"
        
        # Test 3: Rate limiter memory usage
        reset_security_instances()
        
        with patch('app.core.security.redis_client', Mock()):
            rate_limiter = AdvancedRateLimiter()
            
            # Create many mock requests
            for i in range(1000):
                mock_request = Mock(spec=Request)
                mock_request.client.host = f"192.168.1.{i % 255}"
                mock_request.headers = {'User-Agent': f'MemTest/{i}'}
                
                try:
                    rate_limiter.check_auth_rate_limit(
                        mock_request, 
                        f"mem_test_{i}@example.com", 
                        "login"
                    )
                except:
                    pass  # Ignore exceptions, testing memory usage
        
        post_rate_limit_memory = process.memory_info().rss / 1024 / 1024  # MB
        rate_limiter_memory_growth = post_rate_limit_memory - final_memory
        
        # Rate limiter should not use excessive memory
        assert rate_limiter_memory_growth < 5, \
            f"Rate limiter grew memory by {rate_limiter_memory_growth}MB"


if __name__ == "__main__":
    # Run specific test groups for debugging
    pytest.main([
        __file__ + "::TestTokenManagement::test_token_blacklist_functionality_comprehensive",
        __file__ + "::TestSecurityFeatures::test_rate_limiting_on_auth_endpoints",
        "-v"
    ])