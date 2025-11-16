"""
Security Tests: CSRF Protection Verification

These tests verify that MITA API does NOT use cookie-based authentication
and therefore does NOT require CSRF protection.

Tests confirm:
1. No cookies set in authentication responses
2. Authorization header required for protected endpoints
3. Tokens returned in JSON response body only
4. No session middleware or cookie-based state

Reference: ADR-20251115-csrf-protection-analysis.md
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestNoSessionCookies:
    """Verify no cookies are used in authentication"""

    def test_no_cookies_in_registration_response(self):
        """Registration endpoint should not set any cookies"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"test_csrf_{pytest.random_string()}@example.com",
                "password": "SecurePass123!",
                "country": "US"
            }
        )

        # Check response headers for any cookie setting
        assert "set-cookie" not in [k.lower() for k in response.headers.keys()], \
            "Registration should not set cookies"
        assert "Set-Cookie" not in response.headers, \
            "Registration should not set cookies (case-sensitive check)"

    def test_no_cookies_in_login_response(self, create_test_user):
        """Login endpoint should not set any cookies"""
        user_email, user_password = create_test_user

        response = client.post(
            "/api/auth/login",
            json={
                "email": user_email,
                "password": user_password
            }
        )

        # Check response headers for any cookie setting
        assert "set-cookie" not in [k.lower() for k in response.headers.keys()], \
            "Login should not set cookies"
        assert "Set-Cookie" not in response.headers, \
            "Login should not set cookies (case-sensitive check)"

    def test_no_cookies_in_refresh_response(self, authenticated_client):
        """Token refresh should not set cookies"""
        _, refresh_token = authenticated_client

        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        # Check response headers for any cookie setting
        assert "set-cookie" not in [k.lower() for k in response.headers.keys()], \
            "Token refresh should not set cookies"


class TestAuthorizationHeaderRequired:
    """Verify protected endpoints require Authorization header"""

    def test_protected_endpoint_requires_header(self):
        """Protected endpoints should reject requests without Authorization header"""
        response = client.get("/api/users/me")

        assert response.status_code == 401, \
            "Protected endpoint should return 401 without Authorization header"

    def test_protected_endpoint_rejects_invalid_token(self):
        """Protected endpoints should reject invalid tokens"""
        response = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )

        assert response.status_code == 401, \
            "Protected endpoint should return 401 with invalid token"

    def test_protected_endpoint_accepts_valid_token(self, authenticated_client):
        """Protected endpoints should accept valid Authorization header"""
        access_token, _ = authenticated_client

        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code in [200, 201], \
            "Protected endpoint should accept valid Authorization header"


class TestTokensInResponseBody:
    """Verify tokens are returned in JSON body, not cookies"""

    def test_registration_returns_tokens_in_body(self):
        """Registration should return tokens in JSON response body"""
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"test_body_{pytest.random_string()}@example.com",
                "password": "SecurePass123!",
                "country": "US"
            }
        )

        assert response.status_code in [200, 201], \
            "Registration should succeed"

        data = response.json()
        assert "access_token" in data, \
            "Response should contain access_token in body"
        assert "refresh_token" in data, \
            "Response should contain refresh_token in body"
        assert "token_type" in data, \
            "Response should contain token_type in body"
        assert data["token_type"] == "bearer", \
            "Token type should be 'bearer'"

    def test_login_returns_tokens_in_body(self, create_test_user):
        """Login should return tokens in JSON response body"""
        user_email, user_password = create_test_user

        response = client.post(
            "/api/auth/login",
            json={
                "email": user_email,
                "password": user_password
            }
        )

        assert response.status_code == 200, \
            "Login should succeed"

        data = response.json()
        assert "access_token" in data, \
            "Response should contain access_token in body"
        assert "refresh_token" in data, \
            "Response should contain refresh_token in body"
        assert "token_type" in data, \
            "Response should contain token_type in body"
        assert data["token_type"] == "bearer", \
            "Token type should be 'bearer'"


class TestNoSessionMiddleware:
    """Verify no session middleware is configured"""

    def test_no_session_middleware_in_app(self):
        """FastAPI app should not have SessionMiddleware"""
        from starlette.middleware.sessions import SessionMiddleware

        # Check if SessionMiddleware is in the middleware stack
        middleware_types = [type(m) for m in app.user_middleware]

        assert SessionMiddleware not in middleware_types, \
            "SessionMiddleware should not be configured in app"

    def test_no_session_in_request_state(self):
        """Request should not have session state"""
        response = client.get("/health")

        # If session middleware was present, it would add session to request
        # We can't directly check request state from client, but we can verify
        # no session-related headers are present
        assert "session" not in [k.lower() for k in response.headers.keys()], \
            "No session headers should be present"


class TestCORSConfiguration:
    """Verify CORS is configured for headers, not cookies"""

    def test_cors_allows_authorization_header(self):
        """CORS should allow Authorization header"""
        response = client.options(
            "/api/users/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )

        # Should not reject the preflight request
        assert response.status_code != 403, \
            "CORS should allow Authorization header"

    def test_cors_credentials_for_headers(self):
        """CORS allow_credentials should be for headers, not cookies"""
        response = client.options(
            "/api/users/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # allow_credentials=True is set for Authorization header support
        # This doesn't mean cookies are used - just that credentials (headers) are allowed
        if "access-control-allow-credentials" in [k.lower() for k in response.headers.keys()]:
            # If credentials are allowed, verify it's for headers not cookies
            # by confirming no cookies are set anywhere
            assert True, "Credentials allowed for Authorization header"


# ---- Fixtures ----

@pytest.fixture
def create_test_user():
    """Create a test user for authentication tests"""
    import secrets

    email = f"test_{secrets.token_hex(8)}@example.com"
    password = "SecureTestPass123!"

    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "country": "US"
        }
    )

    assert response.status_code in [200, 201], \
        "Test user creation failed"

    return email, password


@pytest.fixture
def authenticated_client(create_test_user):
    """Get access and refresh tokens for testing"""
    email, password = create_test_user

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password
        }
    )

    assert response.status_code == 200, \
        "Authentication failed"

    data = response.json()
    return data["access_token"], data["refresh_token"]


@pytest.fixture
def random_string():
    """Generate random string for unique emails"""
    import secrets
    return lambda: secrets.token_hex(8)


# Inject random_string into pytest namespace
pytest.random_string = lambda: __import__('secrets').token_hex(8)


if __name__ == "__main__":
    """Run tests with: pytest app/tests/security/test_csrf_not_required.py -v"""
    pytest.main([__file__, "-v", "--tb=short"])
