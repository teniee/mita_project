"""
Enhanced JWT Token Revocation System Tests

Comprehensive test suite for the production-ready token revocation system
for the MITA financial application.

Tests cover:
- Token blacklisting functionality
- Refresh token rotation
- Security monitoring and alerts
- Error handling and failover scenarios
- Performance under load
- Compliance and audit requirements
"""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import routes as auth_routes
from app.services import auth_jwt_service as jwt_service
from app.services.token_security_service import token_security_service
from app.core import upstash


class TestTokenBlacklisting:
    """Test token blacklisting functionality."""

    @pytest.fixture
    def mock_redis(self, monkeypatch):
        """Mock Redis operations for testing."""
        store = {}
        
        def mock_blacklist(jti, ttl):
            store[f"revoked:jwt:{jti}"] = {"value": "blacklisted", "ttl": ttl}
            
        def mock_check_blacklist(jti):
            return f"revoked:jwt:{jti}" in store
            
        monkeypatch.setattr(upstash, "blacklist_token", mock_blacklist)
        monkeypatch.setattr(upstash, "is_token_blacklisted", mock_check_blacklist)
        return store

    def test_token_blacklist_basic_functionality(self, mock_redis):
        """Test basic token blacklisting works correctly."""
        # Create a token
        token_data = {"sub": "user123", "scope": "access_token"}
        token = jwt_service.create_access_token(token_data)
        
        # Verify token is valid initially
        payload = jwt_service.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        
        # Blacklist the token
        success = jwt_service.blacklist_token(token)
        assert success is True
        
        # Verify token is now invalid
        payload = jwt_service.verify_token(token)
        assert payload is None

    def test_token_blacklist_with_ttl_validation(self, mock_redis):
        """Test TTL is correctly calculated for blacklisted tokens."""
        # Create token with specific expiry
        token_data = {"sub": "user123"}
        expires_in = 3600  # 1 hour
        token = jwt_service.create_access_token(token_data, 
                                               expires_delta=jwt_service.timedelta(seconds=expires_in))
        
        jwt_service.blacklist_token(token)
        
        # Check that TTL was set approximately correctly
        jti = jwt_service.get_token_info(token)["jti"]
        key = f"revoked:jwt:{jti}"
        assert key in mock_redis
        
        stored_ttl = mock_redis[key]["ttl"]
        assert abs(stored_ttl - expires_in) < 5  # Allow 5 second variance

    def test_blacklist_malformed_token(self, mock_redis):
        """Test blacklisting malformed tokens fails gracefully."""
        malformed_tokens = [
            "",
            "not.a.token",
            "header.payload",  # Missing signature
            "a" * 1000,  # Too long
            None
        ]
        
        for token in malformed_tokens:
            if token is None:
                with pytest.raises(TypeError):
                    jwt_service.blacklist_token(token)
            else:
                success = jwt_service.blacklist_token(token)
                assert success is False

    def test_blacklist_expired_token(self, mock_redis):
        """Test blacklisting expired tokens."""
        # Create an already expired token
        token_data = {"sub": "user123"}
        expired_token = jwt_service._create_token(
            token_data, 
            jwt_service.timedelta(seconds=-100),  # Expired 100 seconds ago
            "access_token"
        )
        
        # Should still be able to blacklist expired tokens
        success = jwt_service.blacklist_token(expired_token)
        assert success is True

    @pytest.mark.asyncio
    async def test_blacklist_performance_under_load(self, mock_redis):
        """Test blacklist performance with multiple concurrent operations."""
        tokens = []
        
        # Create multiple tokens
        for i in range(100):
            token = jwt_service.create_access_token({"sub": f"user{i}"})
            tokens.append(token)
        
        # Blacklist all tokens concurrently
        start_time = time.time()
        
        blacklist_results = await asyncio.gather(
            *[asyncio.create_task(asyncio.to_thread(jwt_service.blacklist_token, token)) 
              for token in tokens],
            return_exceptions=True
        )
        
        end_time = time.time()
        
        # Check all blacklisting succeeded
        assert all(result is True for result in blacklist_results)
        
        # Check performance (should complete in reasonable time)
        total_time = end_time - start_time
        assert total_time < 10  # Should complete within 10 seconds
        
        # Verify all tokens are blacklisted
        for token in tokens:
            assert jwt_service.verify_token(token) is None


class TestRefreshTokenRotation:
    """Test refresh token rotation functionality."""

    @pytest.fixture
    def mock_redis(self, monkeypatch):
        """Mock Redis operations."""
        store = {}
        
        def mock_blacklist(jti, ttl):
            store[f"revoked:jwt:{jti}"] = {"value": "blacklisted", "ttl": ttl}
            
        def mock_check_blacklist(jti):
            return f"revoked:jwt:{jti}" in store
            
        monkeypatch.setattr(upstash, "blacklist_token", mock_blacklist)
        monkeypatch.setattr(upstash, "is_token_blacklisted", mock_check_blacklist)
        return store

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, mock_redis):
        """Test that refresh token rotation blacklists old tokens."""
        # Create initial refresh token
        refresh_token = jwt_service.create_refresh_token({"sub": "user123"})
        
        # Simulate refresh request
        request = SimpleNamespace(
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        
        # Call refresh endpoint
        response = await auth_routes.refresh_token(request)
        
        # Parse response
        data = json.loads(response.body.decode())["data"]
        new_access_token = data["access_token"]
        new_refresh_token = data["refresh_token"]
        
        # Verify new tokens are different
        assert new_refresh_token != refresh_token
        assert new_access_token != refresh_token
        
        # Verify old refresh token is blacklisted
        old_payload = jwt_service.verify_token(refresh_token, scope="refresh_token")
        assert old_payload is None
        
        # Verify new tokens are valid
        new_access_payload = jwt_service.verify_token(new_access_token)
        new_refresh_payload = jwt_service.verify_token(new_refresh_token, scope="refresh_token")
        
        assert new_access_payload is not None
        assert new_refresh_payload is not None
        assert new_access_payload["sub"] == "user123"
        assert new_refresh_payload["sub"] == "user123"

    @pytest.mark.asyncio
    async def test_refresh_token_replay_attack_prevention(self, mock_redis):
        """Test that refresh token rotation prevents replay attacks."""
        refresh_token = jwt_service.create_refresh_token({"sub": "user123"})
        
        request = SimpleNamespace(
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        
        # First refresh should succeed
        response1 = await auth_routes.refresh_token(request)
        assert response1.status_code == 200
        
        # Second refresh with same token should fail
        with pytest.raises(HTTPException) as exc_info:
            await auth_routes.refresh_token(request)
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired refresh token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_concurrent_refresh_requests(self, mock_redis):
        """Test handling of concurrent refresh requests with same token."""
        refresh_token = jwt_service.create_refresh_token({"sub": "user123"})
        
        # Create multiple concurrent requests with same token
        requests = [
            SimpleNamespace(headers={"Authorization": f"Bearer {refresh_token}"})
            for _ in range(5)
        ]
        
        # Execute concurrent refresh attempts
        results = await asyncio.gather(
            *[auth_routes.refresh_token(req) for req in requests],
            return_exceptions=True
        )
        
        # Only one should succeed, others should fail
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        assert len(successes) == 1
        assert len(failures) == 4
        
        # All failures should be authentication errors
        for failure in failures:
            assert isinstance(failure, HTTPException)
            assert failure.status_code == 401


class TestSecurityMonitoring:
    """Test security monitoring and alerting functionality."""

    def test_security_service_metrics_tracking(self):
        """Test that security metrics are properly tracked."""
        # Reset metrics
        token_security_service._metrics = token_security_service.__class__._metrics.__class__()
        
        # Record various activities
        token_security_service.record_token_issued("user123", "access_token", "192.168.1.1")
        token_security_service.record_token_verification("user123", True, "192.168.1.1", "jti123")
        token_security_service.record_token_verification("user456", False, "192.168.1.2", "jti456")
        token_security_service.record_token_blacklisted("user123", "jti123", "logout")
        token_security_service.record_blacklist_hit("user789", "jti789", "192.168.1.3")
        
        # Check metrics
        metrics = token_security_service.get_security_metrics()
        
        assert metrics["token_metrics"]["total_issued"] == 1
        assert metrics["token_metrics"]["total_verified"] == 2
        assert metrics["token_metrics"]["verification_failures"] == 1
        assert metrics["token_metrics"]["total_blacklisted"] == 1
        assert metrics["token_metrics"]["blacklist_hits"] == 1
        assert metrics["token_metrics"]["security_alerts"] >= 1  # From blacklist hit

    def test_suspicious_activity_detection(self):
        """Test detection of suspicious authentication patterns."""
        user_id = "test_user_suspicious"
        client_ip = "192.168.1.100"
        
        # Reset metrics
        token_security_service._metrics = token_security_service.__class__._metrics.__class__()
        token_security_service._alerts.clear()
        
        # Simulate excessive failed verification attempts
        for i in range(15):  # More than MAX_FAILED_ATTEMPTS (10)
            token_security_service.record_token_verification(
                user_id, False, client_ip, f"jti{i}"
            )
        
        # Check that alerts were generated
        alerts = token_security_service.get_recent_alerts()
        
        # Should have alerts for excessive failures and suspicious IP
        alert_types = [alert["type"] for alert in alerts]
        assert "excessive_verification_failures" in alert_types
        assert "suspicious_ip_activity" in alert_types
        
        # Check alert severities
        high_alerts = [a for a in alerts if a["severity"] == "HIGH"]
        critical_alerts = [a for a in alerts if a["severity"] == "CRITICAL"]
        
        assert len(high_alerts) >= 1
        assert len(critical_alerts) >= 1

    def test_user_activity_summary(self):
        """Test user activity tracking and summarization."""
        user_id = "activity_test_user"
        
        # Record various activities for user
        token_security_service.record_token_issued(user_id, "access_token", "192.168.1.1")
        token_security_service.record_token_issued(user_id, "refresh_token", "192.168.1.1")
        token_security_service.record_token_verification(user_id, True, "192.168.1.1", "jti1")
        token_security_service.record_token_verification(user_id, False, "192.168.1.2", "jti2")
        token_security_service.record_token_blacklisted(user_id, "jti1", "logout")
        
        # Get activity summary
        summary = token_security_service.get_user_activity_summary(user_id)
        
        assert summary["total_activities"] >= 5
        assert summary["tokens_issued"] == 2
        assert summary["successful_verifications"] == 1
        assert summary["failed_verifications"] == 1
        assert summary["tokens_blacklisted"] == 1
        assert summary["unique_ips"] == 2
        assert summary["last_activity"] is not None

    @pytest.mark.asyncio
    async def test_security_monitoring_cleanup(self):
        """Test that old monitoring data is cleaned up."""
        user_id = "cleanup_test_user"
        
        # Add some old activity (simulate old timestamp)
        old_activity = {
            "action": "token_issued",
            "timestamp": time.time() - 86400 * 2,  # 2 days ago
            "type": "access_token"
        }
        token_security_service._user_activity[user_id].append(old_activity)
        
        # Add recent activity
        token_security_service.record_token_issued(user_id, "access_token")
        
        # Run cleanup
        await token_security_service.cleanup_old_data()
        
        # Check that old activity was removed but recent activity remains
        activities = token_security_service._user_activity[user_id]
        assert len(activities) == 1
        assert activities[0]["action"] == "token_issued"
        assert activities[0]["timestamp"] > time.time() - 3600  # Recent


class TestTokenHealthChecks:
    """Test token health check and validation functionality."""

    @pytest.fixture
    def mock_redis(self, monkeypatch):
        """Mock Redis operations."""
        store = {}
        
        def mock_blacklist(jti, ttl):
            store[f"revoked:jwt:{jti}"] = {"value": "blacklisted", "ttl": ttl}
            
        def mock_check_blacklist(jti):
            return f"revoked:jwt:{jti}" in store
            
        monkeypatch.setattr(upstash, "blacklist_token", mock_blacklist)
        monkeypatch.setattr(upstash, "is_token_blacklisted", mock_check_blacklist)
        return store

    def test_token_health_check_valid_token(self, mock_redis):
        """Test health check for valid token."""
        token = jwt_service.create_access_token({"sub": "user123"})
        
        health = token_security_service.check_token_health(token)
        
        assert health["status"] == "healthy"
        assert health["token_info"]["user_id"] == "user123"
        assert health["token_info"]["scope"] == "access_token"
        assert health["token_info"]["expires_in"] > 0
        assert health["token_info"]["is_expired"] is False
        assert health["is_blacklisted"] is False

    def test_token_health_check_blacklisted_token(self, mock_redis):
        """Test health check for blacklisted token."""
        token = jwt_service.create_access_token({"sub": "user123"})
        
        # Blacklist the token
        jwt_service.blacklist_token(token)
        
        health = token_security_service.check_token_health(token)
        
        assert health["status"] == "blacklisted"
        assert health["reason"] == "Token is in blacklist"
        assert health["is_blacklisted"] is True

    def test_token_health_check_expired_token(self, mock_redis):
        """Test health check for expired token."""
        # Create expired token
        expired_token = jwt_service._create_token(
            {"sub": "user123"}, 
            jwt_service.timedelta(seconds=-100),
            "access_token"
        )
        
        health = token_security_service.check_token_health(expired_token)
        
        assert health["status"] == "expired"
        assert health["reason"] == "Token has expired"
        assert health["token_info"]["is_expired"] is True
        assert health["token_info"]["expires_in"] == 0

    def test_token_health_check_invalid_token(self, mock_redis):
        """Test health check for invalid token."""
        invalid_tokens = ["invalid", "not.a.token", ""]
        
        for invalid_token in invalid_tokens:
            health = token_security_service.check_token_health(invalid_token)
            
            assert health["status"] == "invalid"
            assert "could not be decoded" in health["reason"].lower()

    def test_token_security_validation(self):
        """Test comprehensive token security validation."""
        token = jwt_service.create_access_token({"sub": "user123"})
        
        validation = jwt_service.validate_token_security(token)
        
        assert validation["valid"] is True
        assert validation["jti_present"] is True
        assert validation["user_id_present"] is True
        assert validation["scope_valid"] is True
        assert validation["not_expired"] is True
        assert validation["issued_recently"] is True
        assert validation["time_to_expiry"] > 0


class TestErrorHandlingAndFailover:
    """Test error handling and failover scenarios."""

    def test_redis_connection_failure_blacklist(self, monkeypatch):
        """Test graceful handling of Redis connection failures during blacklisting."""
        def mock_failing_blacklist(jti, ttl):
            raise ConnectionError("Redis connection failed")
            
        monkeypatch.setattr(upstash, "blacklist_token", mock_failing_blacklist)
        
        token = jwt_service.create_access_token({"sub": "user123"})
        
        # Blacklisting should raise an exception (fail-secure)
        with pytest.raises(RuntimeError):
            jwt_service.blacklist_token(token)

    def test_redis_connection_failure_check(self, monkeypatch):
        """Test graceful handling of Redis connection failures during checks."""
        def mock_failing_check(jti):
            raise ConnectionError("Redis connection failed")
            
        monkeypatch.setattr(upstash, "is_token_blacklisted", mock_failing_check)
        
        token = jwt_service.create_access_token({"sub": "user123"})
        
        # Token verification should still work (fail-open for checks)
        payload = jwt_service.verify_token(token)
        assert payload is not None  # Should still verify despite Redis failure

    @pytest.mark.asyncio
    async def test_logout_with_redis_failure(self, monkeypatch):
        """Test logout behavior when Redis fails."""
        def mock_failing_blacklist(jti, ttl):
            raise ConnectionError("Redis connection failed")
            
        monkeypatch.setattr(upstash, "blacklist_token", mock_failing_blacklist)
        
        token = jwt_service.create_access_token({"sub": "user123"})
        request = SimpleNamespace(
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Logout should still complete gracefully but log the error
        response = await auth_routes.logout(request)
        
        # Should return success response
        data = json.loads(response.body.decode())
        assert "Logout processed" in data["data"]["message"]


class TestComplianceAndAudit:
    """Test compliance and audit trail functionality."""

    @patch('app.core.audit_logging.log_security_event')
    def test_security_event_logging(self, mock_log_event):
        """Test that security events are properly logged for audit."""
        user_id = "audit_test_user"
        
        # Perform various security-related operations
        token_security_service.record_token_issued(user_id, "access_token", "192.168.1.1")
        token_security_service.record_token_blacklisted(user_id, "jti123", "logout")
        token_security_service.record_blacklist_hit(user_id, "jti456", "192.168.1.2")
        
        # Verify security events were logged
        assert mock_log_event.call_count >= 3
        
        # Check specific event types
        call_args_list = [call[0] for call in mock_log_event.call_args_list]
        event_types = [args[0] for args in call_args_list]
        
        assert "token_issued" in event_types
        assert "token_blacklisted" in event_types
        assert "blacklisted_token_usage_attempt" in event_types

    def test_audit_trail_completeness(self):
        """Test that audit trail includes all required information."""
        # This would typically test integration with external audit systems
        # For now, we verify that our logging includes all necessary fields
        
        metrics = token_security_service.get_security_metrics()
        
        required_fields = [
            "token_metrics",
            "redis_metrics", 
            "alert_summary",
            "suspicious_activity"
        ]
        
        for field in required_fields:
            assert field in metrics
        
        # Verify token metrics include all necessary counters
        token_metrics = metrics["token_metrics"]
        required_counters = [
            "total_issued",
            "total_verified", 
            "total_blacklisted",
            "blacklist_hits",
            "verification_failures",
            "security_alerts"
        ]
        
        for counter in required_counters:
            assert counter in token_metrics
            assert isinstance(token_metrics[counter], int)

    def test_financial_compliance_requirements(self):
        """Test that implementation meets financial services compliance."""
        # Test that sensitive data is properly protected
        token = jwt_service.create_access_token({"sub": "user123"})
        token_info = jwt_service.get_token_info(token)
        
        # JTI should be present for revocation tracking
        assert token_info["jti"] is not None
        
        # Token should have proper expiration
        assert token_info["exp"] is not None
        assert token_info["exp"] > time.time()
        
        # Token should include issuer information
        payload = jwt_service.verify_token(token)
        assert payload.get("iss") == "mita-app"
        
        # Test that blacklist operations are atomic and reliable
        success = jwt_service.blacklist_token(token)
        assert success is True
        
        # Verify token is immediately invalid after blacklisting
        assert jwt_service.verify_token(token) is None


if __name__ == "__main__":
    # Run specific test categories
    pytest.main([
        __file__ + "::TestTokenBlacklisting",
        "-v"
    ])