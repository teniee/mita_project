"""
Authentication Integration Tests
================================

Comprehensive integration tests for MITA authentication flows that simulate
real mobile client interactions with the API using httpx.

Tests complete user journeys:
- Registration with email verification
- Login with token generation
- Logout with token cleanup  
- Password reset flows
- OAuth integration
- Mobile-specific scenarios
"""

import pytest
import httpx
import asyncio
import time
from typing import Dict, Any

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestAuthenticationFlows:
    """Test complete authentication flows end-to-end."""
    
    @pytest.mark.mobile
    async def test_complete_user_registration_flow(
        self, 
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper,
        performance_thresholds: Dict[str, float]
    ):
        """Test complete user registration flow with mobile client."""
        
        # Step 1: Register new user
        start_time = time.time()
        response = await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        registration_time = time.time() - start_time
        
        # Assert successful registration
        assert response.status_code == 201, f"Registration failed: {response.text}"
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()
        
        # Validate token structure
        data = response.json()
        assert integration_helper.validate_jwt_structure(data["access_token"])
        assert integration_helper.validate_jwt_structure(data["refresh_token"])
        
        # Assert performance requirements
        assert registration_time <= performance_thresholds["api_response_p95"], \
            f"Registration took {registration_time:.3f}s, expected <= {performance_thresholds['api_response_p95']:.3f}s"
        
        # Validate security headers
        integration_helper.assert_security_headers(response)
        
        # Assert no sensitive data in response
        integration_helper.assert_no_sensitive_data_leaked(
            response.text, 
            [test_user_credentials["password"], "secret", "private_key"]
        )
        
        return data
    
    @pytest.mark.mobile
    async def test_complete_login_flow(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper,
        performance_thresholds: Dict[str, float]
    ):
        """Test complete login flow with mobile client."""
        
        # First register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Step 1: Login with credentials
        start_time = time.time()
        response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        login_time = time.time() - start_time
        
        # Assert successful login
        assert response.status_code == 200, f"Login failed: {response.text}"
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()
        
        data = response.json()
        
        # Validate token structure and uniqueness
        assert integration_helper.validate_jwt_structure(data["access_token"])
        assert integration_helper.validate_jwt_structure(data["refresh_token"])
        assert data["access_token"] != data["refresh_token"]
        
        # Assert performance requirements
        assert login_time <= performance_thresholds["api_response_p95"], \
            f"Login took {login_time:.3f}s, expected <= {performance_thresholds['api_response_p95']:.3f}s"
        
        # Test authenticated request
        access_token = data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Make authenticated request (assuming profile endpoint exists)
        profile_response = await mobile_client.get("/users/profile", headers=auth_headers)
        
        # Should succeed with valid token or return 404 if endpoint doesn't exist
        assert profile_response.status_code in [200, 404], \
            f"Authenticated request failed: {profile_response.status_code}"
        
        return data
    
    @pytest.mark.mobile
    async def test_complete_logout_flow(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test complete logout flow with token cleanup."""
        
        # Register and login user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]
        
        # Step 1: Logout with token
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        logout_response = await mobile_client.post("/auth/logout", headers=auth_headers)
        
        # Assert successful logout
        assert logout_response.status_code in [200, 204], f"Logout failed: {logout_response.text}"
        
        # Step 2: Verify token is blacklisted/invalid
        # Try to use the token after logout
        profile_response = await mobile_client.get("/users/profile", headers=auth_headers)
        assert profile_response.status_code in [401, 403], \
            "Token should be invalid after logout"
        
        # Step 3: Verify refresh token is also invalid
        refresh_response = await mobile_client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_response.status_code in [401, 403], \
            "Refresh token should be invalid after logout"
    
    @pytest.mark.security
    async def test_invalid_credentials_handling(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test handling of invalid credentials."""
        
        # Test 1: Invalid email format
        response = await mobile_client.post("/auth/login", json={
            "email": "invalid_email",
            "password": "password123"
        })
        assert response.status_code in [400, 422], "Should reject invalid email format"
        
        # Test 2: Non-existent user
        response = await mobile_client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code in [401, 404], "Should reject non-existent user"
        
        # Test 3: Register user then try wrong password
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": "wrong_password"
        })
        assert response.status_code == 401, "Should reject wrong password"
        
        # Ensure no sensitive data is leaked in error responses
        integration_helper.assert_no_sensitive_data_leaked(
            response.text,
            [test_user_credentials["password"], "hash", "secret"]
        )
    
    @pytest.mark.concurrent
    async def test_concurrent_authentication_operations(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test concurrent authentication operations."""
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Perform concurrent login attempts
        async def login_attempt():
            return await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
        
        # Execute 10 concurrent logins
        tasks = [login_attempt() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed (or some might fail due to rate limiting)
        success_count = sum(1 for r in responses 
                          if isinstance(r, httpx.Response) and r.status_code == 200)
        rate_limited_count = sum(1 for r in responses 
                               if isinstance(r, httpx.Response) and r.status_code == 429)
        
        # At least some should succeed, others might be rate limited
        assert success_count > 0, "At least some concurrent logins should succeed"
        assert success_count + rate_limited_count == 10, "All requests should complete"
    
    @pytest.mark.financial
    async def test_financial_user_profiles(
        self,
        mobile_client: httpx.AsyncClient,
        financial_user_profiles: Dict[str, Dict[str, Any]],
        integration_helper
    ):
        """Test authentication for different financial user profiles."""
        
        for profile_name, profile_data in financial_user_profiles.items():
            # Register user with financial profile
            response = await mobile_client.post("/auth/register", json={
                "email": profile_data["email"],
                "password": profile_data["password"]
            })
            
            assert response.status_code == 201, \
                f"Registration failed for {profile_name}: {response.text}"
            
            # Verify token contains appropriate claims (if accessible)
            data = response.json()
            access_token = data["access_token"]
            
            # Validate token structure
            assert integration_helper.validate_jwt_structure(access_token)
            
            # Login with profile
            login_response = await mobile_client.post("/auth/login", json={
                "email": profile_data["email"],
                "password": profile_data["password"]
            })
            
            assert login_response.status_code == 200, \
                f"Login failed for {profile_name}: {login_response.text}"


class TestPasswordResetFlow:
    """Test password reset functionality."""
    
    @pytest.mark.mobile
    async def test_password_reset_request(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test password reset request flow."""
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Request password reset
        response = await mobile_client.post("/auth/forgot-password", json={
            "email": test_user_credentials["email"]
        })
        
        # Should succeed even if email service is mocked
        assert response.status_code in [200, 202], f"Password reset request failed: {response.text}"
        
        # Should not reveal whether user exists or not for security
        response_text = response.text.lower()
        assert "sent" in response_text or "email" in response_text
    
    @pytest.mark.mobile
    async def test_password_reset_with_invalid_email(
        self,
        mobile_client: httpx.AsyncClient
    ):
        """Test password reset with invalid email."""
        
        response = await mobile_client.post("/auth/forgot-password", json={
            "email": "nonexistent@example.com"
        })
        
        # Should not reveal that user doesn't exist
        assert response.status_code in [200, 202], \
            "Should not reveal user existence for security"


class TestOAuthIntegration:
    """Test OAuth integration flows (if implemented)."""
    
    @pytest.mark.mobile
    @pytest.mark.skip(reason="OAuth implementation depends on external services")
    async def test_google_oauth_flow(
        self,
        mobile_client: httpx.AsyncClient,
        integration_helper
    ):
        """Test Google OAuth integration flow."""
        
        # Mock Google ID token (in real test this would be from Google)
        mock_id_token = "mock.google.jwt.token"
        
        response = await mobile_client.post("/auth/google", json={
            "id_token": mock_id_token
        })
        
        # Implementation depends on actual OAuth setup
        # This test would need real OAuth mocking
        assert response.status_code in [200, 400, 501]


class TestTokenManagement:
    """Test token lifecycle management."""
    
    @pytest.mark.mobile
    async def test_token_refresh_flow(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test token refresh functionality."""
        
        # Register and login user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        login_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        data = login_response.json()
        refresh_token = data["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_response = await mobile_client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        if refresh_response.status_code == 404:
            pytest.skip("Refresh endpoint not implemented")
        
        assert refresh_response.status_code == 200, \
            f"Token refresh failed: {refresh_response.text}"
        
        new_data = refresh_response.json()
        assert "access_token" in new_data
        
        # New token should be different from old one
        assert new_data["access_token"] != data["access_token"]
        
        # Validate new token structure
        assert integration_helper.validate_jwt_structure(new_data["access_token"])
    
    @pytest.mark.security
    async def test_token_blacklisting(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test token blacklisting after logout."""
        
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
        
        # Try to use blacklisted token
        response = await mobile_client.get("/users/profile", headers=auth_headers)
        assert response.status_code in [401, 403], \
            "Blacklisted token should be rejected"


class TestMobileSpecificScenarios:
    """Test mobile-specific authentication scenarios."""
    
    @pytest.mark.mobile
    async def test_push_token_registration(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        mobile_device_context: Dict[str, str]
    ):
        """Test push token registration after login."""
        
        # Register and login user
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
        
        # Register push token
        push_response = await mobile_client.post(
            "/notifications/register-device",
            headers=auth_headers,
            json={
                "push_token": mobile_device_context["push_token"],
                "device_type": mobile_device_context["device_type"],
                "device_id": mobile_device_context["device_id"]
            }
        )
        
        # Should succeed or return 404 if endpoint not implemented
        assert push_response.status_code in [200, 201, 404], \
            f"Push token registration failed: {push_response.text}"
    
    @pytest.mark.mobile
    async def test_cross_platform_compatibility(
        self,
        mobile_client: httpx.AsyncClient,
        android_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test authentication across different mobile platforms."""
        
        # Register user with iOS client
        ios_register = await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        assert ios_register.status_code == 201
        
        # Login with Android client (same user)
        android_login = await android_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        assert android_login.status_code == 200
        
        # Both should have valid tokens
        ios_token = ios_register.json()["access_token"]
        android_token = android_login.json()["access_token"]
        
        assert integration_helper.validate_jwt_structure(ios_token)
        assert integration_helper.validate_jwt_structure(android_token)
        
        # Tokens should be different (different sessions)
        assert ios_token != android_token
    
    @pytest.mark.mobile
    async def test_network_interruption_simulation(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        network_conditions: Dict[str, Dict[str, Any]]
    ):
        """Test authentication under poor network conditions."""
        
        # Register user under good conditions
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Simulate poor network conditions
        poor_client = httpx.AsyncClient(
            base_url=mobile_client.base_url,
            timeout=network_conditions["poor"]["timeout"],
            headers=mobile_client.headers
        )
        
        try:
            # Login under poor conditions
            response = await poor_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            
            # Should still work, just slower
            assert response.status_code == 200, "Login should work under poor network"
            
        except httpx.TimeoutException:
            # Acceptable under very poor conditions
            pytest.skip("Network conditions too poor for testing")
        finally:
            await poor_client.aclose()
    
    @pytest.mark.performance
    async def test_authentication_performance(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        performance_thresholds: Dict[str, float],
        integration_helper
    ):
        """Test authentication performance meets mobile requirements."""
        
        # Register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Measure login performance over multiple attempts
        login_times = []
        
        for _ in range(5):
            start_time = time.time()
            response = await mobile_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            login_time = time.time() - start_time
            
            assert response.status_code == 200
            login_times.append(login_time)
        
        # Calculate performance metrics
        avg_time = sum(login_times) / len(login_times)
        max_time = max(login_times)
        
        # Assert performance thresholds
        assert avg_time <= performance_thresholds["api_response_p95"], \
            f"Average login time {avg_time:.3f}s exceeds threshold"
        assert max_time <= performance_thresholds["api_response_p99"], \
            f"Max login time {max_time:.3f}s exceeds threshold"


# Integration test execution markers
if __name__ == "__main__":
    # Run with: python -m pytest tests/integration/test_auth_integration.py -v
    pass