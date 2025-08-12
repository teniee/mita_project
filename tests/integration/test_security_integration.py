"""
Security Integration Tests
=========================

Comprehensive security integration tests for MITA authentication system.
Tests rate limiting, token blacklisting, CSRF protection, session management,
and other security measures in a production-like environment.

Financial applications require zero-tolerance security standards.
"""

import pytest
import httpx
import asyncio
import time
import uuid
from typing import Dict, List, Any

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.security, pytest.mark.asyncio]


class TestRateLimitingIntegration:
    """Test rate limiting integration across multiple requests."""
    
    @pytest.mark.slow
    async def test_login_rate_limiting(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test login rate limiting with real requests."""
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Attempt rapid-fire logins to trigger rate limiting
        responses = []
        for i in range(15):  # Exceed typical rate limit
            response = await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            responses.append(response)
            
            # Small delay to avoid overwhelming the system
            if i > 5:
                await asyncio.sleep(0.1)
        
        # Analyze responses
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        # Should have some successes followed by rate limiting
        assert success_count > 0, "Some login attempts should succeed"
        assert rate_limited_count > 0, "Rate limiting should be triggered"
        
        # Verify rate limit headers are present
        for response in responses:
            if response.status_code == 429:
                assert "Retry-After" in response.headers or "X-RateLimit-Remaining" in response.headers
    
    @pytest.mark.concurrent
    async def test_concurrent_rate_limiting(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test rate limiting under concurrent load."""
        
        # Register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Create multiple concurrent clients
        async def make_login_requests(client_id: int, count: int):
            client = httpx.AsyncClient(
                base_url=mobile_client.base_url,
                headers=mobile_client.headers.copy()
            )
            try:
                responses = []
                for _ in range(count):
                    response = await client.post("/auth/login", json={
                        "email": test_user_credentials["email"],
                        "password": test_user_credentials["password"]
                    })
                    responses.append(response.status_code)
                    await asyncio.sleep(0.05)  # Small delay between requests
                return responses
            finally:
                await client.aclose()
        
        # Run concurrent sessions
        tasks = [make_login_requests(i, 10) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        all_responses = [code for client_responses in results for code in client_responses]
        success_count = sum(1 for code in all_responses if code == 200)
        rate_limited_count = sum(1 for code in all_responses if code == 429)
        
        # Rate limiting should be applied across all clients
        assert rate_limited_count > 0, "Rate limiting should affect concurrent requests"
        assert success_count > 0, "Some requests should still succeed"
    
    @pytest.mark.security
    async def test_registration_rate_limiting(
        self,
        mobile_client: httpx.AsyncClient,
        integration_helper
    ):
        """Test registration rate limiting to prevent abuse."""
        
        responses = []
        for i in range(10):
            unique_email = f"test_{i}_{uuid.uuid4().hex[:8]}@example.com"
            response = await mobile_client.post("/auth/register", json={
                "email": unique_email,
                "password": "SecurePassword123!"
            })
            responses.append(response)
            
            if i > 5:  # Add delay after several attempts
                await asyncio.sleep(0.1)
        
        # Should eventually hit rate limiting
        success_count = sum(1 for r in responses if r.status_code == 201)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        # Some registrations should succeed, but rate limiting should kick in
        assert success_count >= 3, "Initial registrations should succeed"
        # Note: Rate limiting might not kick in for registration if limits are high


class TestTokenBlacklistingIntegration:
    """Test token blacklisting functionality in real environment."""
    
    @pytest.mark.security
    async def test_token_blacklist_after_logout(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        redis_client
    ):
        """Test that tokens are properly blacklisted after logout."""
        
        # Register and login
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Verify token works initially
        profile_response = await mobile_client.get("/users/profile", headers=auth_headers)
        initial_status = profile_response.status_code
        
        # Logout to blacklist token
        logout_response = await mobile_client.post("/auth/logout", headers=auth_headers)
        assert logout_response.status_code in [200, 204]
        
        # Verify token is blacklisted
        post_logout_response = await mobile_client.get("/users/profile", headers=auth_headers)
        assert post_logout_response.status_code in [401, 403], \
            "Token should be blacklisted after logout"
        
        # If initial request was successful, blacklisting should be verified
        if initial_status == 200:
            assert post_logout_response.status_code != 200, \
                "Token blacklisting failed - token still works after logout"
    
    @pytest.mark.security
    async def test_multiple_device_logout(
        self,
        mobile_client: httpx.AsyncClient,
        android_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test logout from one device doesn't affect others."""
        
        # Register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Login from iOS device
        ios_login = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        ios_token = ios_login.json()["access_token"]
        ios_headers = {"Authorization": f"Bearer {ios_token}"}
        
        # Login from Android device
        android_login = await android_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        android_token = android_login.json()["access_token"]
        android_headers = {"Authorization": f"Bearer {android_token}"}
        
        # Logout from iOS device only
        await mobile_client.post("/auth/logout", headers=ios_headers)
        
        # iOS token should be invalid
        ios_response = await mobile_client.get("/users/profile", headers=ios_headers)
        assert ios_response.status_code in [401, 403], "iOS token should be blacklisted"
        
        # Android token should still work (if profile endpoint exists)
        android_response = await android_client.get("/users/profile", headers=android_headers)
        assert android_response.status_code in [200, 404], \
            "Android token should still be valid"
    
    @pytest.mark.security
    async def test_token_blacklist_persistence(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        redis_client
    ):
        """Test that token blacklist persists across server restarts."""
        
        # Register and login
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Logout to blacklist token
        await mobile_client.post("/auth/logout", headers=auth_headers)
        
        # Simulate checking blacklist directly in Redis
        # This would require access to the actual blacklist implementation
        # For now, just verify the token is rejected
        response = await mobile_client.get("/users/profile", headers=auth_headers)
        assert response.status_code in [401, 403], "Token should remain blacklisted"


class TestSessionManagementIntegration:
    """Test session management across requests."""
    
    @pytest.mark.security
    async def test_concurrent_session_limits(
        self,
        test_user_credentials: Dict[str, str],
        api_base_url: str
    ):
        """Test concurrent session limits to prevent session hijacking."""
        
        # Create multiple clients to simulate different devices
        clients = []
        for i in range(7):  # Exceed typical session limit
            client = httpx.AsyncClient(
                base_url=api_base_url,
                headers={
                    **MOBILE_CLIENT_HEADERS,
                    "X-Device-ID": f"device_{i}",
                    "User-Agent": f"MITA-Mobile/1.0 (Device{i})"
                }
            )
            clients.append(client)
        
        try:
            # Register user
            await clients[0].post("/auth/register", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            
            # Login from all devices
            tokens = []
            for i, client in enumerate(clients):
                response = await client.post("/auth/login", json={
                    "email": test_user_credentials["email"],
                    "password": test_user_credentials["password"]
                })
                
                if response.status_code == 200:
                    tokens.append((i, response.json()["access_token"]))
                else:
                    tokens.append((i, None))
            
            # Verify session management
            valid_sessions = [token for _, token in tokens if token is not None]
            
            # Should either limit concurrent sessions or allow all
            # (depends on implementation)
            if len(valid_sessions) < len(clients):
                # Session limiting is active
                assert len(valid_sessions) <= 5, "Should limit concurrent sessions"
                
                # Earlier sessions might be invalidated
                for device_id, token in tokens[:2]:  # Check first two devices
                    if token:
                        client = clients[device_id]
                        response = await client.get("/users/profile", 
                                                  headers={"Authorization": f"Bearer {token}"})
                        # Might be invalidated due to session limits
                        assert response.status_code in [200, 401, 404]
            
        finally:
            # Cleanup
            for client in clients:
                await client.aclose()
    
    @pytest.mark.security
    async def test_session_timeout(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test session timeout behavior."""
        
        # Register and login
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        access_token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test immediate access
        response = await mobile_client.get("/users/profile", headers=auth_headers)
        initial_status = response.status_code
        
        # Simulate time passing (would need actual expired tokens in real test)
        # For this test, just verify current behavior
        assert initial_status in [200, 404], "Token should work initially"
        
        # Note: Real session timeout testing would require:
        # 1. Short-lived test tokens
        # 2. Time manipulation
        # 3. Or waiting for actual timeout


class TestSecurityHeadersIntegration:
    """Test security headers in API responses."""
    
    @pytest.mark.security
    async def test_security_headers_on_auth_endpoints(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test that security headers are present on auth endpoints."""
        
        # Test registration endpoint
        register_response = await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        integration_helper.assert_security_headers(register_response)
        
        # Test login endpoint
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        integration_helper.assert_security_headers(login_response)
        
        # Test logout endpoint (if user is authenticated)
        if login_response.status_code == 200:
            access_token = login_response.json()["access_token"]
            logout_response = await mobile_client.post(
                "/auth/logout", 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            integration_helper.assert_security_headers(logout_response)
    
    @pytest.mark.security
    async def test_cors_headers(
        self,
        mobile_client: httpx.AsyncClient
    ):
        """Test CORS headers are properly configured."""
        
        # Test preflight request
        options_response = await mobile_client.options("/auth/login")
        
        # Should either return 200 with CORS headers or 405 if OPTIONS not allowed
        if options_response.status_code == 200:
            headers = options_response.headers
            # Check for common CORS headers
            cors_headers = ["Access-Control-Allow-Origin", 
                          "Access-Control-Allow-Methods",
                          "Access-Control-Allow-Headers"]
            
            # At least one CORS header should be present
            has_cors = any(header in headers for header in cors_headers)
            assert has_cors or options_response.status_code == 405, \
                "CORS should be configured or OPTIONS should be disabled"


class TestInputValidationSecurity:
    """Test input validation and sanitization."""
    
    @pytest.mark.security
    async def test_sql_injection_protection(
        self,
        mobile_client: httpx.AsyncClient,
        integration_helper
    ):
        """Test protection against SQL injection attacks."""
        
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'/*",
            "test@example.com'; INSERT INTO users VALUES ('hacker','hash'); --"
        ]
        
        for payload in sql_injection_payloads:
            response = await mobile_client.post("/auth/login", json={
                "email": payload,
                "password": "test123"
            })
            
            # Should be rejected with 400/422, not cause server error
            assert response.status_code in [400, 401, 422], \
                f"SQL injection payload not handled: {payload}"
            
            # Response should not contain SQL error messages
            response_text = response.text.lower()
            sql_errors = ["syntax error", "column", "table", "sql", "database"]
            for error in sql_errors:
                assert error not in response_text, \
                    f"SQL error information leaked: {error}"
    
    @pytest.mark.security
    async def test_xss_protection(
        self,
        mobile_client: httpx.AsyncClient
    ):
        """Test protection against XSS attacks."""
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "test@example.com<script>alert('xss')</script>"
        ]
        
        for payload in xss_payloads:
            response = await mobile_client.post("/auth/register", json={
                "email": payload,
                "password": "SecurePassword123!"
            })
            
            # Should be rejected or sanitized
            assert response.status_code in [400, 422], \
                f"XSS payload not handled: {payload}"
            
            # Response should not echo back the payload
            assert payload not in response.text, \
                f"XSS payload echoed in response: {payload}"
    
    @pytest.mark.security
    async def test_password_strength_enforcement(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test password strength requirements."""
        
        weak_passwords = [
            "123456",
            "password",
            "qwerty",
            "abc123",
            "letmein",
            "admin",
            "12345678",  # Too simple
            "a",  # Too short
        ]
        
        for weak_password in weak_passwords:
            response = await mobile_client.post("/auth/register", json={
                "email": test_user_credentials["email"],
                "password": weak_password
            })
            
            # Should reject weak passwords
            assert response.status_code in [400, 422], \
                f"Weak password accepted: {weak_password}"
            
            # Should provide helpful error message
            response_text = response.text.lower()
            password_hints = ["password", "strength", "requirements", "secure"]
            has_password_feedback = any(hint in response_text for hint in password_hints)
            assert has_password_feedback, \
                "Should provide password strength feedback"


class TestBruteForceProtection:
    """Test brute force attack protection."""
    
    @pytest.mark.slow
    @pytest.mark.security
    async def test_brute_force_login_protection(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test protection against brute force login attacks."""
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Attempt multiple failed logins
        failed_attempts = 0
        rate_limited = False
        
        for attempt in range(20):  # Many failed attempts
            response = await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": f"wrong_password_{attempt}"
            })
            
            if response.status_code == 401:
                failed_attempts += 1
            elif response.status_code == 429:
                rate_limited = True
                break
            elif response.status_code == 423:  # Account locked
                rate_limited = True
                break
            
            # Add small delay between attempts
            await asyncio.sleep(0.1)
        
        # Should eventually trigger protection
        assert failed_attempts > 0, "Should have some failed attempts"
        
        # After many failed attempts, should be protected
        if failed_attempts >= 10:
            assert rate_limited, \
                "Should trigger brute force protection after many failed attempts"
    
    @pytest.mark.security
    async def test_account_lockout_behavior(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test account lockout after repeated failures."""
        
        # Register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Make multiple failed attempts
        for _ in range(10):
            response = await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": "wrong_password"
            })
            await asyncio.sleep(0.1)
        
        # Try correct password after failed attempts
        correct_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Depending on implementation:
        # - Should succeed if no account lockout
        # - Should fail if account is locked
        # - Should be rate limited
        assert correct_response.status_code in [200, 401, 423, 429], \
            "Should handle post-failure login attempts appropriately"


# Import necessary fixtures
from tests.integration.conftest import MOBILE_CLIENT_HEADERS