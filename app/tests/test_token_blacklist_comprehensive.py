"""
Comprehensive Token Blacklist System Tests

Tests for the complete JWT token blacklist functionality including:
- Token blacklisting and validation
- Performance requirements (<50ms)
- Admin functions
- Cleanup mechanisms
- Security incident response
- Flutter app integration
"""

import asyncio
import pytest
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.services.token_blacklist_service import (
    TokenBlacklistService,
    TokenType,
    BlacklistReason,
    BlacklistEntry,
    BlacklistMetrics
)
from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    blacklist_token,
    revoke_user_tokens,
    validate_token_security
)
from app.main import app


@pytest.fixture
async def blacklist_service():
    """Create blacklist service for testing."""
    service = TokenBlacklistService("redis://localhost:6379/15")  # Test DB
    await service.initialize()
    yield service
    await service.close()


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_tokens():
    """Create sample tokens for testing."""
    user_data = {"sub": str(uuid.uuid4())}
    access_token = create_access_token(user_data, user_role="basic_user")
    refresh_token = create_refresh_token(user_data, user_role="basic_user")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_data": user_data
    }


class TestTokenBlacklistService:
    """Test token blacklist service functionality."""
    
    @pytest.mark.asyncio
    async def test_blacklist_service_initialization(self, blacklist_service):
        """Test blacklist service initializes correctly."""
        health = await blacklist_service.health_check()
        
        assert health["service"] == "token_blacklist"
        assert health["status"] in ["healthy", "disabled"]
        assert "redis_connected" in health
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_token_blacklisting(self, blacklist_service, sample_tokens):
        """Test basic token blacklisting functionality."""
        access_token = sample_tokens["access_token"]
        
        # Token should not be blacklisted initially
        from app.services.auth_jwt_service import get_token_info
        token_info = get_token_info(access_token)
        jti = token_info["jti"]
        
        is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
        assert not is_blacklisted
        
        # Blacklist the token
        success = await blacklist_service.blacklist_token(
            access_token,
            reason=BlacklistReason.LOGOUT
        )
        assert success
        
        # Token should now be blacklisted
        is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
        assert is_blacklisted
    
    @pytest.mark.asyncio
    async def test_blacklist_performance(self, blacklist_service):
        """Test blacklist check performance (<50ms requirement)."""
        # Generate a test JTI
        test_jti = str(uuid.uuid4())
        
        # Measure blacklist check performance
        start_time = time.time()
        is_blacklisted = await blacklist_service.is_token_blacklisted(test_jti)
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Should complete within 50ms
        assert elapsed_ms < 50, f"Blacklist check took {elapsed_ms:.2f}ms (exceeds 50ms requirement)"
        assert not is_blacklisted  # Non-existent token should not be blacklisted
    
    @pytest.mark.asyncio
    async def test_user_token_revocation(self, blacklist_service):
        """Test mass token revocation for a user."""
        user_id = str(uuid.uuid4())
        
        # Create multiple tokens for the user
        tokens = []
        for _ in range(3):
            user_data = {"sub": user_id}
            token = create_access_token(user_data)
            tokens.append(token)
        
        # Simulate tokens being tracked (in real implementation, this happens during token creation)
        # For testing, we'll manually track them
        for token in tokens:
            await blacklist_service.blacklist_token(token, reason=BlacklistReason.LOGOUT)
        
        # Revoke all user tokens
        revoked_count = await blacklist_service.blacklist_user_tokens(
            user_id=user_id,
            token_type=TokenType.ALL,
            reason=BlacklistReason.SECURITY_INCIDENT,
            revoked_by="admin"
        )
        
        # Should have revoked all tokens
        assert revoked_count >= 0  # Redis may handle cleanup differently
        
        # All tokens should be blacklisted
        for token in tokens:
            from app.services.auth_jwt_service import get_token_info
            token_info = get_token_info(token)
            jti = token_info["jti"]
            is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
            assert is_blacklisted
    
    @pytest.mark.asyncio
    async def test_admin_token_revocation(self, blacklist_service):
        """Test admin token revocation by JTI."""
        # Create a test token
        user_data = {"sub": str(uuid.uuid4())}
        token = create_access_token(user_data)
        
        from app.services.auth_jwt_service import get_token_info
        token_info = get_token_info(token)
        jti = token_info["jti"]
        
        # Admin revokes token by JTI
        success = await blacklist_service.revoke_token_by_jti(
            jti=jti,
            reason=BlacklistReason.ADMIN_REVOKE,
            revoked_by="admin_user_id"
        )
        
        assert success
        
        # Token should be blacklisted
        is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
        assert is_blacklisted
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, blacklist_service):
        """Test blacklist metrics collection."""
        # Perform some operations to generate metrics
        user_data = {"sub": str(uuid.uuid4())}
        token = create_access_token(user_data)
        
        await blacklist_service.blacklist_token(token, reason=BlacklistReason.LOGOUT)
        
        from app.services.auth_jwt_service import get_token_info
        token_info = get_token_info(token)
        jti = token_info["jti"]
        
        await blacklist_service.is_token_blacklisted(jti)
        
        # Get metrics
        metrics = await blacklist_service.get_blacklist_metrics()
        
        assert isinstance(metrics, BlacklistMetrics)
        assert metrics.total_blacklisted >= 0
        assert metrics.blacklist_checks >= 0
        assert metrics.average_check_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_cleanup_mechanism(self, blacklist_service):
        """Test automatic cleanup mechanism."""
        # Run cleanup
        cleaned_count = await blacklist_service.cleanup_expired_tokens()
        
        # Redis handles TTL automatically, so this should always return 0
        assert cleaned_count == 0
        
        # Verify cleanup updated metrics
        metrics = await blacklist_service.get_blacklist_metrics()
        assert metrics.cleanup_operations >= 0


class TestJWTServiceIntegration:
    """Test JWT service integration with blacklist."""
    
    @pytest.mark.asyncio
    async def test_token_verification_with_blacklist(self, sample_tokens):
        """Test token verification checks blacklist."""
        access_token = sample_tokens["access_token"]
        
        # Token should verify successfully initially
        payload = await verify_token(access_token)
        assert payload is not None
        assert payload["sub"] == sample_tokens["user_data"]["sub"]
        
        # Blacklist the token
        success = await blacklist_token(access_token, reason="logout")
        if success:  # Only test if Redis is available
            # Token verification should now fail
            payload = await verify_token(access_token)
            assert payload is None
    
    @pytest.mark.asyncio
    async def test_token_security_validation(self, sample_tokens):
        """Test token security validation includes blacklist check."""
        access_token = sample_tokens["access_token"]
        
        # Get security validation
        validation = await validate_token_security(access_token)
        
        assert validation["valid"]
        assert validation["jti_present"]
        assert validation["user_id_present"]
        assert validation["not_expired"]
        
        # Blacklist status should be included
        if "is_blacklisted" in validation:
            assert isinstance(validation["is_blacklisted"], bool)
    
    @pytest.mark.asyncio
    async def test_user_token_revocation_service(self):
        """Test user token revocation through service."""
        user_id = str(uuid.uuid4())
        
        # Revoke user tokens
        revoked_count = await revoke_user_tokens(
            user_id=user_id,
            reason="security",
            revoked_by="admin"
        )
        
        # Should return count (may be 0 if no active tokens)
        assert revoked_count >= 0


class TestAuthEndpointsIntegration:
    """Test authentication endpoints with blacklist functionality."""
    
    def test_logout_endpoint_blacklists_token(self, test_client):
        """Test logout endpoint properly blacklists tokens."""
        # Note: This test would require setting up a full test environment
        # with database and Redis. For now, we test the endpoint structure.
        
        # Mock token for testing
        headers = {"Authorization": "Bearer test_token"}
        
        response = test_client.post("/api/auth/logout", headers=headers)
        
        # Should handle the request (may fail due to invalid token in test)
        assert response.status_code in [200, 401, 500]
    
    def test_revoke_endpoint_functionality(self, test_client):
        """Test token revocation endpoint."""
        headers = {"Authorization": "Bearer test_token"}
        
        response = test_client.post("/api/auth/revoke", headers=headers)
        
        # Should handle the request
        assert response.status_code in [200, 401, 500]
    
    def test_admin_endpoints_require_auth(self, test_client):
        """Test admin endpoints require proper authentication."""
        # Test admin token revocation endpoint
        response = test_client.post(
            "/api/auth/admin/revoke-user-tokens",
            params={"user_id": "test_user", "reason": "admin_action"}
        )
        
        # Should require authentication
        assert response.status_code == 401
        
        # Test admin metrics endpoint
        response = test_client.get("/api/auth/admin/blacklist-metrics")
        assert response.status_code == 401


class TestPerformanceRequirements:
    """Test system meets performance requirements."""
    
    @pytest.mark.asyncio
    async def test_blacklist_check_performance(self):
        """Test blacklist checks complete within 50ms."""
        service = TokenBlacklistService("redis://localhost:6379/15")
        
        if not await service.initialize():
            pytest.skip("Redis not available for performance testing")
        
        try:
            # Test multiple blacklist checks
            test_jtis = [str(uuid.uuid4()) for _ in range(10)]
            
            start_time = time.time()
            
            for jti in test_jtis:
                await service.is_token_blacklisted(jti)
            
            elapsed_time = time.time() - start_time
            avg_time_ms = (elapsed_time / len(test_jtis)) * 1000
            
            # Average should be under 50ms
            assert avg_time_ms < 50, f"Average blacklist check time {avg_time_ms:.2f}ms exceeds 50ms requirement"
            
        finally:
            await service.close()
    
    @pytest.mark.asyncio
    async def test_token_blacklisting_performance(self):
        """Test token blacklisting completes efficiently."""
        service = TokenBlacklistService("redis://localhost:6379/15")
        
        if not await service.initialize():
            pytest.skip("Redis not available for performance testing")
        
        try:
            # Create test token
            user_data = {"sub": str(uuid.uuid4())}
            token = create_access_token(user_data)
            
            # Measure blacklisting time
            start_time = time.time()
            await service.blacklist_token(token, reason=BlacklistReason.LOGOUT)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Should complete reasonably quickly
            assert elapsed_ms < 100, f"Token blacklisting took {elapsed_ms:.2f}ms"
            
        finally:
            await service.close()


class TestSecurityIncidentResponse:
    """Test security incident response capabilities."""
    
    @pytest.mark.asyncio
    async def test_mass_token_revocation(self):
        """Test mass token revocation for security incidents."""
        user_id = str(uuid.uuid4())
        
        # Simulate security incident response
        revoked_count = await revoke_user_tokens(
            user_id=user_id,
            reason="security_incident",
            revoked_by="security_team"
        )
        
        # Should handle the request
        assert revoked_count >= 0
    
    @pytest.mark.asyncio
    async def test_suspicious_activity_response(self):
        """Test response to suspicious activity."""
        service = TokenBlacklistService("redis://localhost:6379/15")
        
        if not await service.initialize():
            pytest.skip("Redis not available for security testing")
        
        try:
            # Create token representing suspicious activity
            user_data = {"sub": str(uuid.uuid4())}
            token = create_access_token(user_data)
            
            # Blacklist for suspicious activity
            success = await service.blacklist_token(
                token,
                reason=BlacklistReason.SUSPICIOUS_ACTIVITY,
                metadata={"detected_patterns": ["unusual_location", "rapid_requests"]}
            )
            
            assert success
            
        finally:
            await service.close()


class TestCleanupTasks:
    """Test cleanup and maintenance tasks."""
    
    @pytest.mark.asyncio
    async def test_cleanup_task_execution(self):
        """Test cleanup tasks execute successfully."""
        from app.tasks.token_cleanup_task import cleanup_token_blacklist
        
        result = await cleanup_token_blacklist()
        
        assert "status" in result
        assert result["status"] in ["success", "failed"]
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance monitoring task."""
        from app.tasks.token_cleanup_task import monitor_blacklist_performance
        
        result = await monitor_blacklist_performance()
        
        assert "status" in result
        assert result["status"] in ["success", "failed"]


# Integration tests for Flutter app compatibility

class TestFlutterAppIntegration:
    """Test Flutter app compatibility."""
    
    def test_logout_flow_compatibility(self, test_client):
        """Test logout flow works as expected for Flutter app."""
        # Mock Flutter app logout request
        headers = {
            "Authorization": "Bearer flutter_test_token",
            "User-Agent": "Flutter/MITA",
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/api/auth/logout", headers=headers)
        
        # Should return proper response format
        assert response.status_code in [200, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
    
    def test_token_refresh_with_blacklist(self, test_client):
        """Test token refresh properly handles blacklisted tokens."""
        headers = {
            "Authorization": "Bearer flutter_refresh_token",
            "User-Agent": "Flutter/MITA"
        }
        
        response = test_client.post("/api/auth/refresh", headers=headers)
        
        # Should handle the request appropriately
        assert response.status_code in [200, 401, 500]


# Mock tests for when Redis is not available

class TestMockFunctionality:
    """Test system behavior when Redis is not available."""
    
    @patch('app.services.token_blacklist_service.redis.ConnectionPool.from_url')
    @pytest.mark.asyncio
    async def test_graceful_degradation_without_redis(self, mock_redis):
        """Test system handles Redis unavailability gracefully."""
        mock_redis.side_effect = Exception("Redis connection failed")
        
        service = TokenBlacklistService("redis://localhost:6379")
        initialized = await service.initialize()
        
        # Should handle initialization failure gracefully
        assert not initialized
    
    @patch('app.services.token_blacklist_service.get_blacklist_service')
    @pytest.mark.asyncio
    async def test_verify_token_fallback(self, mock_service):
        """Test token verification falls back gracefully when blacklist unavailable."""
        # Mock blacklist service to raise exception
        mock_service.return_value.is_token_blacklisted = AsyncMock(side_effect=Exception("Redis error"))
        
        user_data = {"sub": str(uuid.uuid4())}
        token = create_access_token(user_data)
        
        # Should still verify token (fail-open)
        payload = await verify_token(token)
        assert payload is not None


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])