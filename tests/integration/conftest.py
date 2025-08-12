"""
Integration Test Configuration
==============================

Fixtures and utilities for MITA integration tests that simulate
real mobile client interactions with the API.
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional, AsyncGenerator
import uuid

import pytest
import httpx
import redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///test_integration.db"
TEST_REDIS_URL = "redis://localhost:6379/14"  # Use database 14 for integration tests

# Mobile client simulation configuration
MOBILE_CLIENT_HEADERS = {
    "User-Agent": "MITA-Mobile/1.0 (iOS 14.0; iPhone12,1)",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Client-Version": "1.0.0",
    "X-Platform": "iOS",
}

ANDROID_CLIENT_HEADERS = {
    "User-Agent": "MITA-Mobile/1.0 (Android 8.1; SM-G950F)",
    "Accept": "application/json", 
    "Content-Type": "application/json",
    "X-Client-Version": "1.0.0",
    "X-Platform": "Android",
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_database_url():
    """Provide test database URL."""
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
async def test_engine(test_database_url):
    """Create test database engine."""
    engine = create_async_engine(test_database_url, echo=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture(scope="session")
def redis_client():
    """Redis client for integration tests."""
    client = redis.from_url(TEST_REDIS_URL)
    
    # Test connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available for integration tests")
    
    yield client
    
    # Cleanup
    client.flushdb()
    client.close()


@pytest.fixture(scope="session")
async def api_base_url():
    """API base URL for integration tests."""
    # Check if we should test against local server or remote
    base_url = os.getenv("INTEGRATION_TEST_BASE_URL", "http://localhost:8000/api")
    return base_url


@pytest.fixture
async def http_client(api_base_url):
    """HTTP client for API integration tests."""
    async with httpx.AsyncClient(
        base_url=api_base_url,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def mobile_client(api_base_url):
    """Mobile client simulator with iOS headers."""
    async with httpx.AsyncClient(
        base_url=api_base_url,
        headers=MOBILE_CLIENT_HEADERS,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def android_client(api_base_url):
    """Android client simulator."""
    async with httpx.AsyncClient(
        base_url=api_base_url,
        headers=ANDROID_CLIENT_HEADERS,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
def test_user_credentials():
    """Generate unique test user credentials."""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "email": f"test_user_{unique_id}@example.com",
        "password": f"SecurePassword123_{unique_id}!",
        "weak_password": "weak123",
        "malformed_email": "not_an_email"
    }


@pytest.fixture
def financial_user_profiles():
    """Different financial user profiles for testing."""
    base_id = uuid.uuid4().hex[:8]
    
    return {
        "basic_user": {
            "email": f"basic_user_{base_id}@example.com",
            "password": "BasicPassword123!",
            "annual_income": 30000,
            "user_type": "basic",
            "risk_level": "low"
        },
        "premium_user": {
            "email": f"premium_user_{base_id}@example.com", 
            "password": "PremiumPassword456!",
            "annual_income": 150000,
            "user_type": "premium",
            "risk_level": "high"
        },
        "enterprise_user": {
            "email": f"enterprise_user_{base_id}@example.com",
            "password": "EnterprisePassword789!",
            "annual_income": 500000,
            "user_type": "enterprise",
            "risk_level": "very_high"
        }
    }


@pytest.fixture
def mobile_device_context():
    """Mobile device context for testing."""
    return {
        "device_id": str(uuid.uuid4()),
        "push_token": f"push_token_{uuid.uuid4().hex}",
        "device_type": "iPhone",
        "os_version": "14.0",
        "app_version": "1.0.0",
        "timezone": "America/New_York"
    }


@pytest.fixture
def network_conditions():
    """Different network conditions for testing."""
    return {
        "good": {"timeout": 1.0, "retries": 1},
        "poor": {"timeout": 5.0, "retries": 3},
        "offline": {"timeout": 0.1, "retries": 0}
    }


class IntegrationTestHelper:
    """Helper class for integration test utilities."""
    
    @staticmethod
    async def register_user(client: httpx.AsyncClient, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user and return response data."""
        response = await client.post("/auth/register", json={
            "email": credentials["email"],
            "password": credentials["password"]
        })
        return response
    
    @staticmethod
    async def login_user(client: httpx.AsyncClient, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Login user and return tokens."""
        response = await client.post("/auth/login", json={
            "email": credentials["email"],
            "password": credentials["password"]
        })
        return response
    
    @staticmethod
    async def create_authenticated_client(client: httpx.AsyncClient, 
                                        access_token: str) -> httpx.AsyncClient:
        """Create client with authentication headers."""
        client.headers.update({"Authorization": f"Bearer {access_token}"})
        return client
    
    @staticmethod
    def measure_response_time(response: httpx.Response) -> float:
        """Measure API response time from headers."""
        return response.elapsed.total_seconds()
    
    @staticmethod
    def validate_jwt_structure(token: str) -> bool:
        """Validate JWT token structure without verification."""
        if not token:
            return False
        parts = token.split('.')
        return len(parts) == 3
    
    @staticmethod
    def simulate_concurrent_requests(client, endpoint, data, count=10):
        """Simulate concurrent requests for load testing."""
        import asyncio
        
        async def make_request():
            return await client.post(endpoint, json=data)
        
        loop = asyncio.get_event_loop()
        tasks = [make_request() for _ in range(count)]
        return loop.run_until_complete(asyncio.gather(*tasks))
    
    @staticmethod
    def assert_security_headers(response: httpx.Response):
        """Assert required security headers are present."""
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy"
        ]
        
        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    @staticmethod
    def assert_no_sensitive_data_leaked(response_text: str, sensitive_data: list):
        """Assert response doesn't contain sensitive information."""
        response_lower = response_text.lower()
        for item in sensitive_data:
            assert item.lower() not in response_lower, f"Leaked sensitive data: {item}"
    
    @staticmethod
    def assert_financial_data_precision(value: float, expected: float, tolerance: float = 0.01):
        """Assert financial calculations are precise."""
        assert abs(value - expected) <= tolerance, \
            f"Financial precision error: {value} != {expected} (tolerance: {tolerance})"


@pytest.fixture
def integration_helper():
    """Provide IntegrationTestHelper instance."""
    return IntegrationTestHelper


@pytest.fixture
def performance_thresholds():
    """Performance thresholds for financial application."""
    return {
        "api_response_p95": 0.2,      # 200ms
        "api_response_p99": 0.5,      # 500ms
        "db_query_max": 0.05,         # 50ms
        "token_creation_max": 0.01,   # 10ms
        "concurrent_users": 100,
        "memory_usage_mb": 100
    }


@pytest.fixture(autouse=True)
async def cleanup_test_data(redis_client, db_session):
    """Clean up test data after each test."""
    yield
    
    # Clean up Redis
    try:
        redis_client.flushdb()
    except:
        pass
    
    # Clean up database would go here in a real scenario
    # For SQLite test DB, we could recreate it entirely


# Test environment setup
def pytest_sessionstart(session):
    """Initialize integration test environment."""
    os.environ['TESTING'] = 'true'
    os.environ['INTEGRATION_TESTING'] = 'true'
    os.environ['DATABASE_URL'] = TEST_DATABASE_URL
    os.environ['REDIS_URL'] = TEST_REDIS_URL
    
    print("\n" + "="*70)
    print("MITA Authentication Integration Test Suite")
    print("Mobile Client Simulation & API Testing")
    print("="*70)


# Custom markers for test organization
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: Integration test")
    config.addinivalue_line("markers", "mobile: Mobile client simulation test")
    config.addinivalue_line("markers", "security: Security focused test")
    config.addinivalue_line("markers", "performance: Performance test")
    config.addinivalue_line("markers", "concurrent: Concurrency test")
    config.addinivalue_line("markers", "financial: Financial accuracy test")
    config.addinivalue_line("markers", "slow: Slow running test")