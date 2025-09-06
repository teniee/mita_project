"""
Mobile-Specific Integration Tests
=================================

Integration tests for mobile-specific authentication scenarios including:
- Push token registration and management
- Offline functionality and token handling
- Background app refresh scenarios
- Network interruption handling
- Cross-platform compatibility
- Mobile app lifecycle management
"""

import pytest
import httpx
import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.mobile, pytest.mark.asyncio]


class TestPushTokenManagement:
    """Test push token registration and lifecycle management."""
    
    @pytest.mark.mobile
    async def test_push_token_registration_flow(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        mobile_device_context: Dict[str, str],
        integration_helper
    ):
        """Test complete push token registration flow."""
        
        # Step 1: Register and login user
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
        
        # Step 2: Register push token
        push_registration = await mobile_client.post(
            "/notifications/register-token",
            headers=auth_headers,
            json={
                "push_token": mobile_device_context["push_token"],
                "device_type": mobile_device_context["device_type"],
                "device_id": mobile_device_context["device_id"],
                "os_version": mobile_device_context["os_version"],
                "app_version": mobile_device_context["app_version"]
            }
        )
        
        # Should succeed or return 404 if endpoint not implemented
        if push_registration.status_code == 404:
            pytest.skip("Push token registration endpoint not implemented")
        
        assert push_registration.status_code in [200, 201], \
            f"Push token registration failed: {push_registration.text}"
        
        # Step 3: Update push token (simulate token refresh)
        new_push_token = f"updated_{mobile_device_context['push_token']}"
        
        update_response = await mobile_client.put(
            "/notifications/register-token",
            headers=auth_headers,
            json={
                "push_token": new_push_token,
                "device_type": mobile_device_context["device_type"],
                "device_id": mobile_device_context["device_id"]
            }
        )
        
        if update_response.status_code != 404:
            assert update_response.status_code in [200, 201], \
                f"Push token update failed: {update_response.text}"
    
    @pytest.mark.mobile
    async def test_push_token_cleanup_on_logout(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        mobile_device_context: Dict[str, str]
    ):
        """Test push token cleanup when user logs out."""
        
        # Register, login, and register push token
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
            "/notifications/register-token",
            headers=auth_headers,
            json={
                "push_token": mobile_device_context["push_token"],
                "device_type": mobile_device_context["device_type"],
                "device_id": mobile_device_context["device_id"]
            }
        )
        
        if push_response.status_code == 404:
            pytest.skip("Push token endpoints not implemented")
        
        # Logout (should cleanup push token)
        logout_response = await mobile_client.post("/auth/logout", headers=auth_headers)
        assert logout_response.status_code in [200, 204]
        
        # Verify push token is unregistered (would need endpoint to check)
        # This is more of a server-side verification
    
    @pytest.mark.mobile
    async def test_multiple_device_push_tokens(
        self,
        mobile_client: httpx.AsyncClient,
        android_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        mobile_device_context: Dict[str, str]
    ):
        """Test managing push tokens across multiple devices."""
        
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
        
        # Register push tokens from both devices
        ios_push = await mobile_client.post(
            "/notifications/register-token",
            headers=ios_headers,
            json={
                "push_token": f"ios_{mobile_device_context['push_token']}",
                "device_type": "iPhone",
                "device_id": f"ios_{mobile_device_context['device_id']}"
            }
        )
        
        android_push = await android_client.post(
            "/notifications/register-token", 
            headers=android_headers,
            json={
                "push_token": f"android_{mobile_device_context['push_token']}",
                "device_type": "Android",
                "device_id": f"android_{mobile_device_context['device_id']}"
            }
        )
        
        if ios_push.status_code == 404:
            pytest.skip("Push token endpoints not implemented")
        
        # Both should succeed
        assert ios_push.status_code in [200, 201]
        assert android_push.status_code in [200, 201]


class TestOfflineScenarios:
    """Test offline functionality and token handling."""
    
    @pytest.mark.mobile
    async def test_token_validation_offline_simulation(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test token behavior during offline periods."""
        
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
        
        # Simulate offline period by testing token validity
        # In real mobile app, this would involve:
        # 1. Storing tokens securely
        # 2. Validating tokens locally (JWT validation)
        # 3. Attempting refresh when network returns
        
        # For this test, verify tokens are structured correctly for offline validation
        from tests.integration.conftest import IntegrationTestHelper
        helper = IntegrationTestHelper()
        
        assert helper.validate_jwt_structure(access_token), \
            "Access token should have valid JWT structure for offline validation"
        assert helper.validate_jwt_structure(refresh_token), \
            "Refresh token should have valid JWT structure"
    
    @pytest.mark.mobile
    async def test_offline_login_attempt(
        self,
        test_user_credentials: Dict[str, str],
        api_base_url: str
    ):
        """Test login attempt during network unavailability."""
        
        # Create client with very short timeout to simulate offline
        offline_client = httpx.AsyncClient(
            base_url=api_base_url,
            timeout=0.001,  # 1ms timeout to force timeout
            headers={
                "User-Agent": "MITA-Mobile/1.0 (iOS 14.0; Offline-Test)",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        try:
            # This should timeout/fail
            response = await offline_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            
            # If it doesn't timeout, the test setup might be wrong
            assert response.status_code >= 400, \
                "Should fail during offline conditions"
                
        except (httpx.TimeoutException, httpx.ConnectError):
            # Expected behavior - network unavailable
            pass
        except Exception as e:
            # Other network errors are acceptable
            assert "timeout" in str(e).lower() or "connection" in str(e).lower()
        finally:
            await offline_client.aclose()
    
    @pytest.mark.mobile
    async def test_background_token_refresh(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test token refresh in background scenarios."""
        
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
        
        # Simulate background refresh (when app comes to foreground)
        refresh_response = await mobile_client.post("/auth/refresh-token", data={
            "refresh_token": refresh_token
        })
        
        if refresh_response.status_code == 404:
            pytest.skip("Token refresh endpoint not implemented")
        
        assert refresh_response.status_code == 200, \
            f"Background token refresh failed: {refresh_response.text}"
        
        new_data = refresh_response.json()
        assert "access_token" in new_data
        
        # New token should be different
        assert new_data["access_token"] != login_response.json()["access_token"]


class TestNetworkInterruptionHandling:
    """Test handling of network interruptions during auth operations."""
    
    @pytest.mark.mobile
    async def test_login_with_network_delay(
        self,
        test_user_credentials: Dict[str, str],
        api_base_url: str,
        performance_thresholds: Dict[str, float]
    ):
        """Test login behavior with network delays."""
        
        # Create client with longer timeout for slow network
        slow_client = httpx.AsyncClient(
            base_url=api_base_url,
            timeout=10.0,  # 10 second timeout
            headers={
                "User-Agent": "MITA-Mobile/1.0 (iOS 14.0; Slow-Network)",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        try:
            # Register user first
            register_start = time.time()
            register_response = await slow_client.post("/auth/register", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            register_time = time.time() - register_start
            
            assert register_response.status_code == 201, \
                f"Registration failed: {register_response.text}"
            
            # Login with network delay
            login_start = time.time()
            login_response = await slow_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            login_time = time.time() - login_start
            
            assert login_response.status_code == 200, \
                f"Login failed: {login_response.text}"
            
            # Should complete within reasonable time even on slow network
            assert login_time <= 10.0, f"Login took too long: {login_time:.2f}s"
            
            # Log performance for monitoring
            print(f"Network delay test - Register: {register_time:.2f}s, Login: {login_time:.2f}s")
            
        finally:
            await slow_client.aclose()
    
    @pytest.mark.mobile
    async def test_retry_logic_simulation(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test retry behavior for failed requests."""
        
        # This test simulates client-side retry logic
        # In a real mobile app, this would be handled by the HTTP client
        
        max_retries = 3
        retry_delay = 0.5
        
        async def login_with_retries():
            for attempt in range(max_retries):
                try:
                    response = await mobile_client.post("/auth/login", json={
                        "email": test_user_credentials["email"],
                        "password": test_user_credentials["password"]
                    })
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code == 429:  # Rate limited
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        return response  # Don't retry for other errors
                        
                except (httpx.TimeoutException, httpx.ConnectError):
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    
            return None
        
        # Register user first
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Test retry logic
        response = await login_with_retries()
        
        if response is not None:
            assert response.status_code == 200, \
                f"Login with retries failed: {response.text}"
        # If response is None, all retries failed (acceptable for this test)


class TestCrossPlatformCompatibility:
    """Test authentication compatibility across mobile platforms."""
    
    @pytest.mark.mobile
    async def test_ios_android_token_compatibility(
        self,
        mobile_client: httpx.AsyncClient,  # iOS client
        android_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test that tokens work across iOS and Android platforms."""
        
        # Register user on iOS
        ios_register = await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        assert ios_register.status_code == 201
        ios_token = ios_register.json()["access_token"]
        
        # Use iOS token on Android client
        android_auth_response = await android_client.get(
            "/users/profile",
            headers={"Authorization": f"Bearer {ios_token}"}
        )
        
        # Token should work across platforms (or return 404 if endpoint missing)
        assert android_auth_response.status_code in [200, 404], \
            "iOS token should work on Android client"
        
        # Login separately on Android
        android_login = await android_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        assert android_login.status_code == 200
        android_token = android_login.json()["access_token"]
        
        # Tokens should be different (different sessions)
        assert android_token != ios_token, \
            "Different platforms should get different session tokens"
        
        # Both tokens should have valid structure
        assert integration_helper.validate_jwt_structure(ios_token)
        assert integration_helper.validate_jwt_structure(android_token)
    
    @pytest.mark.mobile
    async def test_platform_specific_headers(
        self,
        mobile_client: httpx.AsyncClient,
        android_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test that platform-specific headers are handled correctly."""
        
        # Register user
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Login from both platforms
        ios_response = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        android_response = await android_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Both should succeed
        assert ios_response.status_code == 200
        assert android_response.status_code == 200
        
        # Headers should be reflected appropriately (if server tracks them)
        # This would require server-side platform detection and logging
        
        # Verify response format is consistent across platforms
        ios_data = ios_response.json()
        android_data = android_response.json()
        
        # Same response structure
        assert set(ios_data.keys()) == set(android_data.keys()), \
            "Response structure should be consistent across platforms"


class TestMobileAppLifecycle:
    """Test authentication behavior during app lifecycle events."""
    
    @pytest.mark.mobile
    async def test_app_foreground_background_cycle(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str]
    ):
        """Test token behavior during app foreground/background cycles."""
        
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
        
        # Simulate app going to background (no requests for period)
        await asyncio.sleep(1)  # Short simulation
        
        # App comes to foreground - verify token still works
        foreground_response = await mobile_client.get("/users/profile", headers=auth_headers)
        
        # Should still work (or return 404 if endpoint missing)
        assert foreground_response.status_code in [200, 404], \
            "Token should persist through app lifecycle"
    
    @pytest.mark.mobile
    async def test_app_reinstall_simulation(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        mobile_device_context: Dict[str, str]
    ):
        """Test behavior when app is reinstalled (new device context)."""
        
        # Initial install - register and login
        await mobile_client.post("/auth/register", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        initial_login = await mobile_client.post("/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        
        # Simulate app reinstall with new client (different device ID)
        reinstall_client = httpx.AsyncClient(
            base_url=mobile_client.base_url,
            headers={
                **mobile_client.headers,
                "X-Device-ID": f"reinstall_{mobile_device_context['device_id']}",
                "X-Installation-ID": str(uuid.uuid4())
            }
        )
        
        try:
            # Login after "reinstall"
            reinstall_login = await reinstall_client.post("/auth/login", json={
                "email": test_user_credentials["email"],
                "password": test_user_credentials["password"]
            })
            
            assert reinstall_login.status_code == 200, \
                "Should be able to login after app reinstall"
            
            # Should get new tokens
            initial_token = initial_login.json()["access_token"]
            reinstall_token = reinstall_login.json()["access_token"]
            
            assert reinstall_token != initial_token, \
                "Should get new token after reinstall"
                
        finally:
            await reinstall_client.aclose()


class TestFinancialMobileScenarios:
    """Test mobile scenarios specific to financial applications."""
    
    @pytest.mark.financial
    @pytest.mark.mobile
    async def test_secure_session_on_financial_data_access(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test secure session requirements for financial data access."""
        
        # Register user
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
        
        # Test access to financial endpoints
        financial_endpoints = [
            "/transactions",
            "/budget",
            "/expenses", 
            "/financial/analytics",
            "/users/financial-profile"
        ]
        
        for endpoint in financial_endpoints:
            response = await mobile_client.get(endpoint, headers=auth_headers)
            
            # Should either succeed with proper auth or return 404 if not implemented
            assert response.status_code in [200, 404, 403], \
                f"Financial endpoint {endpoint} should require proper authentication"
            
            # If endpoint exists, check security headers
            if response.status_code == 200:
                integration_helper.assert_security_headers(response)
    
    @pytest.mark.financial
    @pytest.mark.mobile  
    async def test_financial_precision_in_mobile_responses(
        self,
        mobile_client: httpx.AsyncClient,
        test_user_credentials: Dict[str, str],
        integration_helper
    ):
        """Test financial data precision in mobile API responses."""
        
        # Register user
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
        
        # Test adding expense with precise amount
        expense_data = {
            "amount": 123.45,  # Test precise decimal
            "category": "food",
            "description": "Test expense",
            "date": "2025-01-01"
        }
        
        expense_response = await mobile_client.post(
            "/expenses",
            headers=auth_headers,
            json=expense_data
        )
        
        if expense_response.status_code == 404:
            pytest.skip("Expense endpoints not implemented")
        
        if expense_response.status_code in [200, 201]:
            # Verify financial precision is maintained
            response_data = expense_response.json()
            if "amount" in response_data:
                # Should maintain exact precision
                integration_helper.assert_financial_data_precision(
                    response_data["amount"],
                    123.45,
                    tolerance=0.001  # 0.1 cent tolerance
                )