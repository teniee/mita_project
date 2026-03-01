"""
Test Configuration for MITA Authentication Security Tests
=========================================================

Centralized test configuration, fixtures, and utilities for all 
authentication security tests. Provides consistent test environment
and shared utilities for comprehensive security testing.
"""

import os
import sys
import asyncio
import pytest
import redis
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, Optional

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Test configuration
REDIS_TEST_URL = "redis://localhost:6379/15"  # Use database 15 for tests
TEST_SECRET_KEY = "test_secret_key_for_mita_auth_testing_only"
TEST_DATABASE_URL = "sqlite:///test_mita_auth.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis_client():
    """
    Mock Redis client for testing rate limiting and blacklist functionality.
    Provides consistent Redis mock across all tests.
    """
    mock_client = Mock(spec=redis.Redis)
    
    # Mock basic Redis operations
    mock_client.ping.return_value = True
    mock_client.setex.return_value = True
    mock_client.exists.return_value = 0
    mock_client.get.return_value = None
    mock_client.delete.return_value = 1
    mock_client.expire.return_value = True
    
    # Mock pipeline operations
    mock_client.pipeline.return_value = mock_client
    mock_client.execute.return_value = [1, 300]  # Default rate limit response
    
    # Mock sorted set operations (for rate limiting)
    mock_client.zremrangebyscore.return_value = 0
    mock_client.zadd.return_value = 1
    mock_client.zcard.return_value = 1
    
    # Mock counter operations
    mock_client.incr.return_value = 1
    
    return mock_client


@pytest.fixture
def mock_database_session():
    """
    Mock async database session for testing authentication operations.
    Provides realistic database interaction simulation.
    """
    session = AsyncMock()
    
    # Mock database operations
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    
    # Mock query results
    mock_result = Mock()
    mock_result.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_result
    
    return session


@pytest.fixture
def test_user_data():
    """Standard test user data for consistent testing."""
    return {
        "sub": "test_user_123",
        "email": "test@example.com",
        "user_type": "basic_user",
        "country": "US",
        "annual_income": 50000,
        "timezone": "America/New_York"
    }


@pytest.fixture
def security_test_config():
    """Security test configuration with financial application settings."""
    return {
        "password_min_length": 8,
        "password_max_length": 128,
        "max_login_attempts": 5,
        "rate_limit_window": 900,  # 15 minutes
        "token_expiry_minutes": 60,
        "refresh_token_expiry_days": 7,
        "max_concurrent_sessions": 5,
        "suspicious_activity_threshold": 10
    }


@pytest.fixture
def test_tokens():
    """Generate test tokens for various scenarios."""
    from app.services.auth_jwt_service import create_access_token, create_refresh_token
    
    user_data = {"sub": "test_user_123", "email": "test@example.com"}
    
    return {
        "valid_access": create_access_token(user_data),
        "valid_refresh": create_refresh_token(user_data),
        "expired_access": "expired.access.token",  # Mock expired token
        "malformed": "not.a.valid.jwt",
        "empty": "",
        "none": None
    }


@pytest.fixture
def financial_test_scenarios():
    """Financial application specific test scenarios."""
    return {
        "high_value_user": {
            "annual_income": 500000,
            "user_type": "premium_user",
            "risk_level": "high"
        },
        "standard_user": {
            "annual_income": 75000,
            "user_type": "basic_user", 
            "risk_level": "medium"
        },
        "basic_user": {
            "annual_income": 25000,
            "user_type": "basic_user",
            "risk_level": "low"
        },
        "suspicious_patterns": {
            "multiple_failed_logins": 10,
            "rapid_requests": 50,
            "unusual_locations": ["CN", "RU", "NK"],
            "off_hours_access": True
        }
    }


@pytest.fixture
def security_attack_vectors():
    """Common security attack vectors for testing."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'/*",
            "'; INSERT INTO users VALUES ('hacker','hash'); --",
            "1' UNION SELECT password FROM users WHERE username='admin'--"
        ],
        "xss_payloads": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
            "';alert('xss');//"
        ],
        "weak_passwords": [
            "password",
            "123456",
            "qwerty",
            "admin",
            "letmein"
        ],
        "malformed_emails": [
            "not_an_email",
            "@example.com",
            "user@",
            "user..double@example.com",
            "user@example..com"
        ],
        "brute_force_patterns": [
            {"attempts": 100, "timeframe": 60},
            {"attempts": 50, "timeframe": 30},
            {"attempts": 20, "timeframe": 10}
        ]
    }


@pytest.fixture
def performance_benchmarks():
    """Performance benchmarks for financial application requirements."""
    return {
        "token_creation_max_time": 0.01,  # 10ms
        "token_validation_max_time": 0.01,  # 10ms
        "api_response_max_time": 0.2,      # 200ms p95
        "database_query_max_time": 0.05,   # 50ms p95
        "redis_operation_max_time": 0.005,  # 5ms
        "concurrent_operations": 100,
        "max_memory_growth_mb": 10
    }


class SecurityTestHelper:
    """
    Helper class for common security testing operations.
    Provides utilities for consistent security testing across test files.
    """
    
    @staticmethod
    def is_jwt_token(token: str) -> bool:
        """Check if string is a valid JWT token format."""
        if not token or not isinstance(token, str):
            return False
        
        parts = token.split('.')
        return len(parts) == 3
    
    @staticmethod
    def extract_token_payload(token: str) -> Optional[Dict[str, Any]]:
        """Extract payload from JWT token without verification (for testing)."""
        import base64
        import json
        
        try:
            if not SecurityTestHelper.is_jwt_token(token):
                return None
            
            # Get payload part
            payload_part = token.split('.')[1]
            
            # Add padding if needed
            while len(payload_part) % 4 != 0:
                payload_part += '='
            
            # Decode
            decoded = base64.urlsafe_b64decode(payload_part)
            return json.loads(decoded.decode())
        except Exception:
            return None
    
    @staticmethod
    def generate_realistic_email(prefix: str = "test") -> str:
        """Generate realistic test email address."""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    
    @staticmethod
    def create_mock_request(ip: str = "127.0.0.1", 
                          user_agent: str = "TestClient/1.0",
                          path: str = "/auth/login") -> Mock:
        """Create mock FastAPI request for testing."""
        from fastapi import Request
        
        request = Mock(spec=Request)
        request.client.host = ip
        request.headers = {'User-Agent': user_agent}
        request.url.path = path
        request.method = "POST"
        
        return request
    
    @staticmethod
    def assert_no_sensitive_data_in_response(response_text: str, 
                                           sensitive_data: list) -> None:
        """Assert that response doesn't contain sensitive information."""
        response_lower = response_text.lower()
        
        for sensitive_item in sensitive_data:
            if isinstance(sensitive_item, str):
                assert sensitive_item.lower() not in response_lower, \
                    f"Sensitive data leaked in response: {sensitive_item}"
    
    @staticmethod
    def assert_security_headers_present(headers: dict) -> None:
        """Assert that required security headers are present."""
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Referrer-Policy"
        ]
        
        for header in required_headers:
            assert header in headers, f"Missing security header: {header}"
    
    @staticmethod
    def measure_operation_time(operation_func, *args, **kwargs) -> tuple:
        """Measure operation execution time and return result and time."""
        import time
        
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        return result, execution_time


@pytest.fixture
def security_helper():
    """Provide SecurityTestHelper instance for tests."""
    return SecurityTestHelper


# Global test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "concurrent: mark test as a concurrency test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test data cleanup
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatically clean up test data after each test."""
    # Setup
    yield
    
    # Cleanup
    # Reset any global state, clean up test files, etc.
    from app.core.security import reset_security_instances
    reset_security_instances()


# Environment setup for CI/CD
def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    # Set test environment variables
    os.environ['TESTING'] = 'true'
    os.environ['SECRET_KEY'] = TEST_SECRET_KEY
    os.environ['DATABASE_URL'] = TEST_DATABASE_URL
    os.environ['REDIS_URL'] = REDIS_TEST_URL
    
    print("\n" + "="*60)
    print("MITA Authentication Security Test Suite")
    print("Financial Application Security Testing")
    print("="*60)