"""
API Endpoint Security Tests for MITA Authentication System
==========================================================

Comprehensive security tests for API endpoints, input validation,
output sanitization, and security headers in the MITA financial application.

This test suite ensures:
1. All auth endpoints are properly secured
2. Input validation prevents injection attacks
3. Output sanitization prevents data leaks
4. Security headers are correctly set
5. CORS policies are properly enforced
6. API versioning and deprecation security
7. Error handling doesn't leak sensitive information
8. Request/response logging is secure

Critical for financial application API security and compliance.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth.schemas import TokenOut
from app.services.auth_jwt_service import create_access_token


class TestAuthEndpointSecurity:
    """
    Test comprehensive security for authentication endpoints.
    Ensures all auth endpoints meet financial application security standards.
    """

    @pytest.fixture
    def test_app(self):
        """Use the real application: real prefixes, middleware, handlers"""
        from app.main import app as real_app

        return real_app

    @pytest.fixture
    def client(self, test_app):
        """Create test client for API testing"""
        with TestClient(test_app, raise_server_exceptions=False) as c:
            yield c

    @pytest.fixture
    def valid_token(self):
        """Create valid JWT token for testing"""
        user_data = {"sub": "test_user_123", "email": "test@example.com"}
        return create_access_token(user_data)

    def test_login_endpoint_security(self, client):
        """
        Test login endpoint comprehensive security measures.
        Critical for financial application authentication security.
        """
        # Test 1: Valid login request structure — real registration + login
        import secrets as _secrets

        email = f"api_sec_{_secrets.token_hex(6)}@example.com"
        valid_login_data = {"email": email, "password": "ValidPassword123!"}

        reg = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "ValidPassword123!",
                "country": "US",
                "annual_income": 50000,
                "timezone": "UTC",
            },
        )
        assert reg.status_code in [200, 201], f"registration failed: {reg.text}"

        response = client.post("/api/auth/login", json=valid_login_data)

        # Should succeed with proper structure
        assert response.status_code == 200
        response_data = response.json()
        assert "data" in response_data
        assert "access_token" in response_data["data"]
        assert "refresh_token" in response_data["data"]

        # Test 2: SQL injection attempts
        sql_injection_attempts = [
            {"email": "'; DROP TABLE users; --", "password": "password"},
            {"email": "admin'/*", "password": "password"},
            {"email": "' OR '1'='1", "password": "' OR '1'='1"},
            {
                "email": "admin'; INSERT INTO users VALUES ('hacker','hash'); --",
                "password": "pass",
            },
        ]

        for injection_data in sql_injection_attempts:
            response = client.post("/api/auth/login", json=injection_data)

            # Should reject malicious input
            assert response.status_code in [400, 401, 422]

            # Should not expose internal errors
            response_data = response.json()
            error_message = str(response_data).lower()

            # Check that database errors are not exposed
            dangerous_keywords = ["sql", "table", "database", "query", "syntax"]
            for keyword in dangerous_keywords:
                assert keyword not in error_message, f"Database error leaked: {keyword}"

        # Test 3: Input validation - malformed requests
        malformed_requests = [
            {},  # Empty request
            {"email": ""},  # Empty email
            {"password": ""},  # Empty password
            {"email": "not_an_email", "password": "pass"},  # Invalid email format
            {"email": "test@example.com"},  # Missing password
            {"password": "password123"},  # Missing email
            {
                "email": "test@example.com",
                "password": "x" * 1000,
            },  # Extremely long password
        ]

        for malformed_data in malformed_requests:
            response = client.post("/api/auth/login", json=malformed_data)
            assert response.status_code in [
                400,
                422,
            ], f"Should reject malformed data: {malformed_data}"

        # Test 4: Content-Type validation
        response = client.post(
            "/api/auth/login",
            data="email=test@example.com&password=pass",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Should require JSON content type for security
        assert response.status_code in [400, 415, 422]

        # Test 5: Request size limits
        oversized_data = {
            "email": "test@example.com",
            "password": "x" * 10000,  # Very large password
        }

        response = client.post("/api/auth/login", json=oversized_data)
        assert response.status_code in [
            400,
            413,
            422,
        ], "Should reject oversized requests"

    def test_register_endpoint_security(self, client):
        """
        Test registration endpoint security and validation.
        Ensures secure user onboarding for financial application.
        """
        # Test 1: Valid registration
        valid_registration = {
            "email": f"newuser_{__import__('secrets').token_hex(6)}@example.com",
            "password": "StrongPassword123!",
            "country": "US",
            "annual_income": 75000,
            "timezone": "America/New_York",
        }

        with patch("app.api.auth.services.register_user_async") as mock_register, patch(
            "app.core.security.get_rate_limiter"
        ) as mock_rate_limiter:

            mock_register.return_value = TokenOut(
                access_token="mock_access_token", refresh_token="mock_refresh_token"
            )

            mock_limiter = Mock()
            mock_limiter.check_auth_rate_limit = Mock()
            mock_rate_limiter.return_value = mock_limiter

            response = client.post("/api/auth/register", json=valid_registration)
            assert response.status_code in [200, 201]

        # Test 2: Password security requirements
        weak_passwords = [
            "password",  # Too weak
            "12345678",  # Only numbers
            "PASSWORD",  # Only uppercase
            "password123",  # Common pattern
            "abc",  # Too short
        ]

        for weak_password in weak_passwords:
            weak_reg_data = valid_registration.copy()
            weak_reg_data["password"] = weak_password

            response = client.post("/api/auth/register", json=weak_reg_data)
            assert response.status_code in [
                400,
                422,
            ], f"Should reject weak password: {weak_password}"

        # Test 3: Email validation
        invalid_emails = [
            "not_an_email",
            "@example.com",
            "user@",
            "user..double@example.com",
            "user@example..com",
            "",
        ]

        for invalid_email in invalid_emails:
            invalid_reg_data = valid_registration.copy()
            invalid_reg_data["email"] = invalid_email

            response = client.post("/api/auth/register", json=invalid_reg_data)
            assert response.status_code in [
                400,
                422,
            ], f"Should reject invalid email: {invalid_email}"

        # Test 4: Financial data validation
        invalid_incomes = [
            -1000,  # Negative income
            20000000,  # Unrealistic income
            "not_a_number",  # Invalid type
        ]

        for invalid_income in invalid_incomes:
            income_reg_data = valid_registration.copy()
            income_reg_data["annual_income"] = invalid_income

            response = client.post("/api/auth/register", json=income_reg_data)
            assert response.status_code in [
                400,
                422,
            ], f"Should reject invalid income: {invalid_income}"

        # Test 5: XSS prevention in input fields
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
        ]

        for xss_payload in xss_payloads:
            for field in ["email", "country", "timezone"]:
                if field == "email":
                    continue  # Email validation will catch this

                xss_reg_data = valid_registration.copy()
                xss_reg_data[field] = xss_payload

                response = client.post("/api/auth/register", json=xss_reg_data)
                # Should either reject or sanitize XSS attempts
                assert response.status_code in [200, 400, 422]

                if response.status_code == 200:
                    # If accepted, ensure XSS payload was sanitized
                    response_text = response.text.lower()
                    assert "<script>" not in response_text
                    assert "javascript:" not in response_text

    def test_token_refresh_endpoint_security(self, client, valid_token):
        """
        Test token refresh endpoint security and token rotation.
        Critical for maintaining session security in financial applications.
        """
        import secrets as _secrets

        email = f"refresh_sec_{_secrets.token_hex(6)}@example.com"
        reg = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "ValidPassword123!",
                "country": "US",
                "annual_income": 50000,
                "timezone": "UTC",
            },
        )
        assert reg.status_code in [200, 201]
        refresh_token = reg.json()["data"]["refresh_token"]

        # Test 1: Valid refresh request (token travels in the body)
        response = client.post(
            "/api/auth/refresh-token", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200, response.text
        response_data = response.json()
        assert "access_token" in response_data["data"]
        assert "refresh_token" in response_data["data"]

        # Test 2: Missing body
        response = client.post("/api/auth/refresh-token")
        assert response.status_code in [401, 403, 422]

        # Test 3: Invalid token values are rejected without a 5xx
        for bad_token in ["invalid_token", "", "Bearer xyz"]:
            response = client.post(
                "/api/auth/refresh-token", json={"refresh_token": bad_token}
            )
            assert response.status_code in [
                400,
                401,
                403,
                422,
            ], f"unexpected status for bad refresh token: {response.status_code}"

    def test_security_headers(self, client):
        """
        Test that proper security headers are set on auth endpoints.
        Essential for financial application security compliance.
        """
        endpoints_to_test = [
            (
                "/api/auth/login",
                "POST",
                {"email": "test@example.com", "password": "pass"},
            ),
            (
                "/api/auth/register",
                "POST",
                {
                    "email": "test@example.com",
                    "password": "Pass123!",
                    "country": "US",
                    "annual_income": 50000,
                    "timezone": "UTC",
                },
            ),
        ]

        with patch("app.api.auth.services.authenticate_user_async"), patch(
            "app.api.auth.services.register_user_async"
        ), patch("app.core.security.get_rate_limiter"):

            for endpoint, method, data in endpoints_to_test:
                if method == "POST":
                    response = client.post(endpoint, json=data)
                else:
                    response = client.get(endpoint)

                headers = response.headers

                # Test security headers that should be present
                security_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-XSS-Protection": "1; mode=block",
                    "Referrer-Policy": "same-origin",
                    "Content-Security-Policy": None,  # Should exist but value may vary
                }

                for header_name, expected_value in security_headers.items():
                    if expected_value is not None:
                        assert (
                            header_name in headers
                        ), f"Missing security header: {header_name}"
                        assert (
                            headers[header_name] == expected_value
                        ), f"Incorrect {header_name}: expected {expected_value}, got {headers[header_name]}"
                    else:
                        # Header should exist but we don't check exact value
                        assert (
                            header_name in headers
                        ), f"Missing security header: {header_name}"

                # Test that sensitive headers are not exposed
                sensitive_headers = [
                    "Server",  # Should not reveal server information
                    "X-Powered-By",  # Should not reveal technology stack
                ]

                for sensitive_header in sensitive_headers:
                    if sensitive_header in headers:
                        header_value = headers[sensitive_header].lower()
                        # Should not contain detailed version information
                        sensitive_keywords = [
                            "version",
                            "apache",
                            "nginx",
                            "fastapi",
                            "python",
                        ]
                        for keyword in sensitive_keywords:
                            assert (
                                keyword not in header_value
                            ), f"Sensitive info in {sensitive_header}: {header_value}"

    def test_error_handling_security(self, client):
        """
        Test that error handling doesn't leak sensitive information.
        Critical for preventing information disclosure in financial applications.
        """
        # Test 1: Database errors should not be exposed
        # (patch the credential check the login route actually awaits)
        with patch("app.api.auth.login.verify_password_async") as mock_verify:
            # Simulate database error
            mock_verify.side_effect = Exception(
                "Database connection failed on table 'users' at line 42"
            )

            import secrets as _secrets

            email = f"errsec_{_secrets.token_hex(6)}@example.com"
            client.post(
                "/api/auth/register",
                json={
                    "email": email,
                    "password": "ValidPassword123!",
                    "country": "US",
                    "annual_income": 50000,
                    "timezone": "UTC",
                },
            )

            response = client.post(
                "/api/auth/login",
                json={"email": email, "password": "ValidPassword123!"},
            )

            # Should return generic error, not database details
            assert response.status_code in [500, 503]
            error_text = response.text.lower()

            # Should not expose internal details
            internal_keywords = [
                "database",
                "table",
                "line",
                "connection",
                "sql",
                "exception",
            ]
            for keyword in internal_keywords:
                assert keyword not in error_text, f"Internal error leaked: {keyword}"

        # Test 2: Stack traces should not be exposed
        with patch("app.api.auth.services.register_user_async") as mock_register:
            # Simulate internal error with stack trace
            mock_register.side_effect = ValueError(
                "Invalid hash algorithm in crypto.py line 123"
            )

            response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "StrongPass123!",
                    "country": "US",
                    "annual_income": 50000,
                    "timezone": "UTC",
                },
            )

            # Should not expose stack trace information
            assert response.status_code in [400, 422, 500]
            error_text = response.text.lower()

            stack_trace_keywords = [
                ".py",
                "line",
                "traceback",
                "file",
                "crypto",
                "algorithm",
            ]
            for keyword in stack_trace_keywords:
                assert keyword not in error_text, f"Stack trace info leaked: {keyword}"

        # Test 3: Validation errors should be sanitized
        malicious_input = {
            "email": "<script>alert('xss')</script>@example.com",
            "password": "'; DROP TABLE users; --",
        }

        response = client.post("/api/auth/login", json=malicious_input)

        # Response should not echo back malicious input
        response_text = response.text
        assert "<script>" not in response_text
        assert "DROP TABLE" not in response_text
        assert "alert(" not in response_text

    def test_rate_limiting_integration(self, client):
        """
        Test rate limiting integration with auth endpoints.
        Ensures rate limiting is properly applied to prevent abuse.
        """
        # Mock rate limiter to trigger rate limiting
        # Restore production limits (the test env relaxes them) and hit the
        # real register limiter until it trips.
        import os as _os

        _os.environ["TESTING"] = "false"
        _prev_environment = _os.environ.get("ENVIRONMENT")
        _os.environ["ENVIRONMENT"] = "development"  # _testing_mode checks both
        try:
            import secrets as _secrets

            saw_429 = False
            for _ in range(7):  # production limit is 5/hour per IP
                response = client.post(
                    "/api/auth/register",
                    json={
                        "email": f"rl_{_secrets.token_hex(6)}@example.com",
                        "password": "StrongPass123!",
                        "country": "US",
                        "annual_income": 50000,
                        "timezone": "UTC",
                    },
                )
                if response.status_code == 429:
                    saw_429 = True
                    break

            assert saw_429, "register endpoint never rate-limited"
            body = response.json()
            detail = str(body).lower()
            assert "rate limit" in detail or "too many" in detail
        finally:
            _os.environ["TESTING"] = "true"
            if _prev_environment is not None:
                _os.environ["ENVIRONMENT"] = _prev_environment

    def test_cors_security(self, client):
        """
        Test CORS policy security for auth endpoints.
        Ensures proper cross-origin request handling.
        """
        # Test 1: Preflight request
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should handle preflight appropriately
        if response.status_code == 200:
            # If CORS is enabled, check that it's properly configured
            headers = response.headers

            # Should not allow all origins for financial app
            if "Access-Control-Allow-Origin" in headers:
                allowed_origin = headers["Access-Control-Allow-Origin"]
                assert (
                    allowed_origin != "*"
                ), "CORS should not allow all origins for financial app"

        # Test 2: Actual request with origin
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "pass"},
            headers={"Origin": "https://untrusted-site.com"},
        )

        # Should either reject or handle with proper CORS headers
        if response.status_code != 403:  # If not rejected outright
            headers = response.headers
            if "Access-Control-Allow-Origin" in headers:
                # Should not reflect arbitrary origins
                assert (
                    headers["Access-Control-Allow-Origin"]
                    != "https://untrusted-site.com"
                )

    def test_api_versioning_security(self, client):
        """
        Test API versioning security to prevent version-based attacks.
        Ensures deprecated endpoints are properly secured or disabled.
        """
        # Test 1: Current API version should work
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password"},
        )

        # Should respond (even if with error due to mocking)
        assert response.status_code in [200, 400, 401, 422, 429]

        # Test 2: Deprecated API versions should be handled securely
        deprecated_endpoints = [
            "/api/v1/auth/login",
            "/v1/auth/login",
            "/auth/v1/login",
        ]

        for deprecated_endpoint in deprecated_endpoints:
            response = client.post(
                deprecated_endpoint,
                json={"email": "test@example.com", "password": "password"},
            )

            # Should either be properly secured or return 404/410
            assert response.status_code in [
                404,
                410,
                501,
            ], f"Deprecated endpoint {deprecated_endpoint} should be disabled or secured"

    def test_request_logging_security(self, client, caplog):
        """
        Test that request logging doesn't expose sensitive information.
        Ensures audit trails don't contain passwords or tokens.
        """
        import logging as _logging

        sensitive_password = "SuperSecretPassword123!"
        with caplog.at_level(_logging.DEBUG):
            client.post(
                "/api/auth/login",
                json={"email": "user@example.com", "password": sensitive_password},
            )

        assert (
            sensitive_password not in caplog.text
        ), "Plaintext password appeared in application logs"


if __name__ == "__main__":
    # Run API endpoint security tests
    pytest.main([__file__, "-v"])
