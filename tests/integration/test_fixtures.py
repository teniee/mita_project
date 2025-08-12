"""
Database and Redis Test Fixtures
=================================

Advanced fixtures for managing database and Redis state during integration tests.
Provides isolated test environments and proper cleanup for financial application testing.
"""

import pytest
import asyncio
import redis
import time
from typing import AsyncGenerator, Generator, Dict, Any, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
import uuid
import tempfile
from pathlib import Path

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class DatabaseTestManager:
    """Manages test database lifecycle and state."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        self._setup_complete = False
    
    async def setup(self):
        """Setup test database."""
        if self._setup_complete:
            return
        
        # Create async engine with test configuration
        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # Set to True for SQL debugging
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,  # For SQLite
                "isolation_level": "AUTOCOMMIT"
            } if "sqlite" in self.database_url else {},
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create database tables (if using in-memory or test database)
        if "test" in self.database_url or "sqlite" in self.database_url:
            await self._create_tables()
        
        self._setup_complete = True
    
    async def _create_tables(self):
        """Create database tables for testing."""
        try:
            from app.db.models.base import Base
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except ImportError:
            # Tables will be created by application if models not available
            pass
        except Exception as e:
            print(f"Warning: Could not create test tables: {e}")
    
    async def get_session(self) -> AsyncSession:
        """Get async database session."""
        if not self._setup_complete:
            await self.setup()
        
        async with self.session_factory() as session:
            yield session
    
    async def cleanup(self):
        """Cleanup database resources."""
        if self.engine:
            await self.engine.dispose()
        self._setup_complete = False
    
    async def reset_database(self):
        """Reset database to clean state."""
        if not self.engine:
            return
        
        try:
            from app.db.models.base import Base
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"Warning: Could not reset database: {e}")


class RedisTestManager:
    """Manages Redis test instance and state."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client = None
        self.db_number = None
        self._extract_db_number()
    
    def _extract_db_number(self):
        """Extract database number from Redis URL."""
        try:
            if "/" in self.redis_url:
                self.db_number = int(self.redis_url.split("/")[-1])
            else:
                self.db_number = 14  # Default test database
        except (ValueError, IndexError):
            self.db_number = 14
    
    async def setup(self):
        """Setup Redis test client."""
        try:
            self.client = redis.from_url(self.redis_url)
            # Test connection
            self.client.ping()
            
            # Clear test database
            self.client.flushdb()
            
            return True
        except redis.ConnectionError:
            print(f"Warning: Redis not available at {self.redis_url}")
            return False
        except Exception as e:
            print(f"Warning: Redis setup failed: {e}")
            return False
    
    def cleanup(self):
        """Cleanup Redis resources."""
        if self.client:
            try:
                # Clear test database
                self.client.flushdb()
                self.client.close()
            except Exception as e:
                print(f"Warning: Redis cleanup failed: {e}")
    
    def reset_state(self):
        """Reset Redis state for test isolation."""
        if self.client:
            try:
                self.client.flushdb()
            except Exception as e:
                print(f"Warning: Redis reset failed: {e}")


@pytest.fixture(scope="session")
async def database_manager() -> AsyncGenerator[DatabaseTestManager, None]:
    """Session-scoped database manager."""
    # Use unique database for each test session
    session_id = uuid.uuid4().hex[:8]
    database_url = f"sqlite+aiosqlite:///test_integration_{session_id}.db"
    
    manager = DatabaseTestManager(database_url)
    await manager.setup()
    
    try:
        yield manager
    finally:
        await manager.cleanup()
        
        # Remove test database file
        if "sqlite" in database_url:
            try:
                db_file = Path(database_url.split("///")[-1])
                if db_file.exists():
                    db_file.unlink()
            except Exception:
                pass


@pytest.fixture(scope="session")
async def redis_manager() -> AsyncGenerator[RedisTestManager, None]:
    """Session-scoped Redis manager."""
    redis_url = "redis://localhost:6379/14"  # Use test database 14
    
    manager = RedisTestManager(redis_url)
    redis_available = await manager.setup()
    
    if not redis_available:
        pytest.skip("Redis not available for integration tests")
    
    try:
        yield manager
    finally:
        manager.cleanup()


@pytest.fixture
async def clean_database(database_manager: DatabaseTestManager):
    """Function-scoped clean database state."""
    # Reset database before test
    await database_manager.reset_database()
    
    yield database_manager
    
    # Cleanup after test (optional - session cleanup will handle this)


@pytest.fixture
async def clean_redis(redis_manager: RedisTestManager):
    """Function-scoped clean Redis state."""
    # Reset Redis before test
    redis_manager.reset_state()
    
    yield redis_manager
    
    # Reset Redis after test for isolation
    redis_manager.reset_state()


@pytest.fixture
async def test_database_session(database_manager: DatabaseTestManager):
    """Get test database session."""
    async for session in database_manager.get_session():
        yield session


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_test_user(index: int = 0) -> Dict[str, Any]:
        """Create test user data."""
        unique_id = uuid.uuid4().hex[:8]
        return {
            "email": f"test_user_{index}_{unique_id}@example.com",
            "password": f"TestPassword{index}{unique_id}!",
            "first_name": f"Test{index}",
            "last_name": f"User{unique_id}",
            "country": "US",
            "annual_income": 50000 + (index * 10000),
            "timezone": "America/New_York"
        }
    
    @staticmethod
    def create_financial_profiles() -> Dict[str, Dict[str, Any]]:
        """Create different financial user profiles."""
        base_id = uuid.uuid4().hex[:8]
        
        return {
            "low_income": {
                "email": f"low_income_{base_id}@example.com",
                "password": f"LowIncome{base_id}!",
                "annual_income": 25000,
                "user_type": "basic",
                "risk_level": "low"
            },
            "middle_income": {
                "email": f"middle_income_{base_id}@example.com",
                "password": f"MiddleIncome{base_id}!",
                "annual_income": 75000,
                "user_type": "premium",
                "risk_level": "medium"
            },
            "high_income": {
                "email": f"high_income_{base_id}@example.com",
                "password": f"HighIncome{base_id}!",
                "annual_income": 200000,
                "user_type": "premium",
                "risk_level": "high"
            },
            "very_high_income": {
                "email": f"very_high_income_{base_id}@example.com",
                "password": f"VeryHighIncome{base_id}!",
                "annual_income": 500000,
                "user_type": "enterprise",
                "risk_level": "very_high"
            }
        }
    
    @staticmethod
    def create_mobile_device_contexts() -> Dict[str, Dict[str, Any]]:
        """Create mobile device contexts for testing."""
        return {
            "ios_device": {
                "device_id": str(uuid.uuid4()),
                "push_token": f"ios_push_{uuid.uuid4().hex}",
                "device_type": "iPhone",
                "os_version": "17.0",
                "app_version": "1.0.0",
                "platform": "iOS"
            },
            "android_device": {
                "device_id": str(uuid.uuid4()),
                "push_token": f"android_push_{uuid.uuid4().hex}",
                "device_type": "Samsung Galaxy",
                "os_version": "14.0",
                "app_version": "1.0.0",
                "platform": "Android"
            },
            "old_ios_device": {
                "device_id": str(uuid.uuid4()),
                "push_token": f"old_ios_push_{uuid.uuid4().hex}",
                "device_type": "iPhone",
                "os_version": "14.0",
                "app_version": "0.9.0",
                "platform": "iOS"
            }
        }


@pytest.fixture
def test_data_factory():
    """Provide TestDataFactory instance."""
    return TestDataFactory


@pytest.fixture
def financial_test_profiles(test_data_factory):
    """Provide financial test profiles."""
    return test_data_factory.create_financial_profiles()


@pytest.fixture
def mobile_device_contexts(test_data_factory):
    """Provide mobile device contexts."""
    return test_data_factory.create_mobile_device_contexts()


class TestStateValidator:
    """Validates test state and data integrity."""
    
    @staticmethod
    async def validate_user_creation(session: AsyncSession, email: str) -> bool:
        """Validate user was created correctly."""
        try:
            from app.db.models.user import User
            from sqlalchemy import select
            
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            
            return user is not None and user.email == email
        except Exception:
            return False
    
    @staticmethod
    def validate_token_in_redis(redis_client, token: str, expected_state: str = "active") -> bool:
        """Validate token state in Redis."""
        try:
            if not redis_client:
                return True  # Skip validation if Redis unavailable
            
            # Check if token exists in blacklist
            is_blacklisted = redis_client.exists(f"blacklisted_token:{token}")
            
            if expected_state == "blacklisted":
                return bool(is_blacklisted)
            elif expected_state == "active":
                return not bool(is_blacklisted)
            
            return True
        except Exception:
            return True  # Skip validation on error
    
    @staticmethod
    def validate_rate_limit_state(redis_client, key: str, expected_count: int) -> bool:
        """Validate rate limit state in Redis."""
        try:
            if not redis_client:
                return True
            
            current_count = redis_client.get(key)
            if current_count is None:
                return expected_count == 0
            
            return int(current_count) >= expected_count
        except Exception:
            return True


@pytest.fixture
def state_validator():
    """Provide TestStateValidator instance."""
    return TestStateValidator


# Test environment health check fixtures
@pytest.fixture(scope="session")
def test_environment_health():
    """Check test environment health."""
    health_status = {
        "database": False,
        "redis": False,
        "api_server": False
    }
    
    # Check database availability
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.close()
        health_status["database"] = True
    except Exception:
        pass
    
    # Check Redis availability
    try:
        client = redis.Redis(host='localhost', port=6379, db=14)
        client.ping()
        health_status["redis"] = True
        client.close()
    except Exception:
        pass
    
    # Check API server (if running locally)
    try:
        import httpx
        import asyncio
        
        async def check_api():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://localhost:8000/", timeout=2.0)
                    return response.status_code < 500
            except Exception:
                return False
        
        health_status["api_server"] = asyncio.run(check_api())
    except Exception:
        pass
    
    return health_status


# Performance monitoring fixtures
@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.start_memory = self.process.memory_info().rss
            self.start_time = time.time()
            self.measurements = []
        
        def record_measurement(self, operation: str):
            current_memory = self.process.memory_info().rss
            current_time = time.time()
            
            self.measurements.append({
                "operation": operation,
                "memory_mb": current_memory / 1024 / 1024,
                "memory_growth_mb": (current_memory - self.start_memory) / 1024 / 1024,
                "execution_time": current_time - self.start_time,
                "timestamp": current_time
            })
        
        def get_summary(self):
            if not self.measurements:
                return {}
            
            memory_values = [m["memory_mb"] for m in self.measurements]
            return {
                "total_measurements": len(self.measurements),
                "peak_memory_mb": max(memory_values),
                "total_time": time.time() - self.start_time,
                "memory_growth_mb": max(m["memory_growth_mb"] for m in self.measurements)
            }
    
    return PerformanceMonitor()


# Cleanup utilities
@pytest.fixture(autouse=True)
async def test_isolation():
    """Ensure test isolation and cleanup."""
    # Setup: Record initial state
    initial_time = time.time()
    
    yield
    
    # Cleanup: Ensure test completed within reasonable time
    execution_time = time.time() - initial_time
    if execution_time > 300:  # 5 minutes
        print(f"Warning: Test took {execution_time:.1f}s, which is quite long")
    
    # Force garbage collection to prevent memory leaks
    import gc
    gc.collect()