"""
Comprehensive Test Suite for JWT Security Enhancements

This test suite validates the production-ready JWT scopes and claims implementation
for the MITA financial application, including OAuth 2.0 style authorization,
security validation, and compliance with financial application standards.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from jose import jwt, JWTError

from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    verify_token,
    validate_token_security,
    get_user_scopes,
    validate_scope_access,
    has_any_scope,
    has_all_scopes,
    blacklist_token,
    TokenScope,
    UserRole,
    JWT_ISSUER,
    JWT_AUDIENCE
)
from app.middleware.jwt_scope_middleware import (
    require_scopes,
    require_profile_read,
    require_transactions_write,
    require_admin_system,
    SecurityAlertLevel
)
from app.services.token_security_monitoring import (
    TokenSecurityMonitor,
    get_security_monitor
)


class TestJWTClaimsAndSecurity:
    """Test JWT claims and security enhancements."""
    
    def test_token_creation_with_standard_claims(self):
        """Test that tokens contain all required standard JWT claims."""
        user_data = {
            "sub": "test-user-123",
            "is_premium": False,
            "country": "US"
        }
        
        token = create_access_token(user_data, user_role="basic_user")
        
        # Decode without verification to check claims structure
        from app.core.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        
        # Check standard claims (RFC 7519)
        assert "exp" in payload  # Expiration time
        assert "iat" in payload  # Issued at
        assert "nbf" in payload  # Not before
        assert "jti" in payload  # JWT ID
        assert "iss" in payload  # Issuer
        assert "aud" in payload  # Audience
        assert "sub" in payload  # Subject
        
        # Check custom claims
        assert "token_type" in payload
        assert "scope" in payload
        assert "user_id" in payload
        assert "token_version" in payload
        assert "security_level" in payload
        
        # Validate claim values
        assert payload["iss"] == JWT_ISSUER
        assert payload["aud"] == JWT_AUDIENCE
        assert payload["token_type"] == "access_token"
        assert payload["user_id"] == "test-user-123"
        assert payload["token_version"] == "2.0"
        assert payload["security_level"] == "high"
        
    def test_token_scopes_assignment(self):
        """Test OAuth 2.0 scope assignment based on user roles."""
        user_data = {"sub": "test-user-123"}
        
        # Test basic user scopes
        basic_token = create_access_token(user_data, user_role="basic_user")
        basic_payload = jwt.decode(basic_token, "test-secret", algorithms=["HS256"], options={"verify_signature": False})
        basic_scopes = basic_payload["scope"].split()
        
        assert TokenScope.READ_PROFILE.value in basic_scopes
        assert TokenScope.READ_TRANSACTIONS.value in basic_scopes
        assert TokenScope.ADMIN_SYSTEM.value not in basic_scopes
        
        # Test premium user scopes
        premium_token = create_access_token(user_data, user_role="premium_user")
        premium_payload = jwt.decode(premium_token, "test-secret", algorithms=["HS256"], options={"verify_signature": False})
        premium_scopes = premium_payload["scope"].split()
        
        assert TokenScope.PREMIUM_FEATURES.value in premium_scopes
        assert TokenScope.ADVANCED_ANALYTICS.value in premium_scopes
        assert TokenScope.DELETE_TRANSACTIONS.value in premium_scopes
        
        # Test admin scopes
        admin_token = create_access_token(user_data, user_role="admin")
        admin_payload = jwt.decode(admin_token, "test-secret", algorithms=["HS256"], options={"verify_signature": False})
        admin_scopes = admin_payload["scope"].split()
        
        assert TokenScope.ADMIN_SYSTEM.value in admin_scopes
        assert TokenScope.ADMIN_USERS.value in admin_scopes
        assert TokenScope.ADMIN_AUDIT.value in admin_scopes
        
    def test_token_issuer_audience_validation(self):
        """Test issuer and audience validation."""
        user_data = {"sub": "test-user-123"}
        token = create_access_token(user_data)
        
        # Valid verification should pass
        payload = verify_token(token, token_type="access_token")
        assert payload is not None
        assert payload["sub"] == "test-user-123"
        
        # Test with wrong issuer
        wrong_issuer_payload = {
            "sub": "test-user-123",
            "exp": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "nbf": int(datetime.utcnow().timestamp()),
            "jti": "test-jti",
            "iss": "wrong-issuer",
            "aud": JWT_AUDIENCE,
            "token_type": "access_token",
            "scope": "read:profile"
        }
        
        from app.core.config import settings
        wrong_issuer_token = jwt.encode(wrong_issuer_payload, settings.SECRET_KEY, algorithm="HS256")
        assert verify_token(wrong_issuer_token) is None
        
    def test_scope_validation_functions(self):
        """Test scope validation utility functions."""
        token_scopes = ["read:profile", "write:profile", "read:transactions"]
        
        # Test validate_scope_access
        assert validate_scope_access(token_scopes, "read:profile") is True
        assert validate_scope_access(token_scopes, "admin:system") is False
        
        # Test has_any_scope
        assert has_any_scope(token_scopes, ["read:profile", "admin:system"]) is True
        assert has_any_scope(token_scopes, ["admin:system", "admin:users"]) is False
        
        # Test has_all_scopes
        assert has_all_scopes(token_scopes, ["read:profile", "write:profile"]) is True
        assert has_all_scopes(token_scopes, ["read:profile", "admin:system"]) is False
        
    def test_token_type_validation(self):
        """Test token type validation."""
        user_data = {"sub": "test-user-123"}
        
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)
        
        # Access token should validate as access token
        access_payload = verify_token(access_token, token_type="access_token")
        assert access_payload is not None
        assert access_payload["token_type"] == "access_token"
        
        # Refresh token should validate as refresh token
        refresh_payload = verify_token(refresh_token, token_type="refresh_token")
        assert refresh_payload is not None
        assert refresh_payload["token_type"] == "refresh_token"
        
        # Cross-validation should fail
        assert verify_token(access_token, token_type="refresh_token") is None
        assert verify_token(refresh_token, token_type="access_token") is None
        
    def test_required_claims_validation(self):
        """Test validation of required JWT claims."""
        # Create token with missing claims
        incomplete_payload = {
            "sub": "test-user-123",
            "exp": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            # Missing iat, nbf, jti, iss, aud, token_type
        }
        
        from app.core.config import settings
        incomplete_token = jwt.encode(incomplete_payload, settings.SECRET_KEY, algorithm="HS256")
        
        # Should fail validation due to missing required claims
        assert verify_token(incomplete_token) is None
        
    def test_not_before_claim_validation(self):
        """Test not-before (nbf) claim validation."""
        future_time = datetime.utcnow() + timedelta(minutes=5)
        
        future_payload = {
            "sub": "test-user-123",
            "exp": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "nbf": int(future_time.timestamp()),  # Not valid yet
            "jti": "test-jti",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "token_type": "access_token",
            "scope": "read:profile"
        }
        
        from app.core.config import settings
        future_token = jwt.encode(future_payload, settings.SECRET_KEY, algorithm="HS256")
        
        # Should fail validation due to nbf claim
        assert verify_token(future_token) is None


class TestScopeBasedAuthorization:
    """Test scope-based authorization middleware."""
    
    def test_scope_requirement_creation(self):
        """Test creation of scope requirements."""
        from app.middleware.jwt_scope_middleware import ScopeRequirement
        
        # Test any_of requirement
        any_req = ScopeRequirement(any_of=["read:profile", "admin:system"])
        assert any_req.any_of == ["read:profile", "admin:system"]
        assert any_req.all_of == []
        
        # Test all_of requirement
        all_req = ScopeRequirement(all_of=["read:transactions", "write:transactions"])
        assert all_req.all_of == ["read:transactions", "write:transactions"]
        assert all_req.any_of == []
        
        # Test empty requirement should raise error
        with pytest.raises(ValueError):
            ScopeRequirement()
            
    def test_predefined_scope_requirements(self):
        """Test predefined scope requirement functions."""
        # These should not raise exceptions during import/creation
        profile_read = require_profile_read()
        transactions_write = require_transactions_write()
        admin_system = require_admin_system()
        
        assert profile_read is not None
        assert transactions_write is not None
        assert admin_system is not None
        
    @patch('app.middleware.jwt_scope_middleware.verify_token')
    def test_scope_middleware_authorization(self, mock_verify_token):
        """Test scope middleware authorization logic."""
        from app.middleware.jwt_scope_middleware import require_scopes
        from fastapi import HTTPException
        from unittest.mock import MagicMock
        
        # Mock successful token verification with scopes
        mock_verify_token.return_value = {
            "sub": "test-user-123",
            "scope": "read:profile write:profile read:transactions"
        }
        
        # Create scope requirement
        scope_dependency = require_scopes(any_of=["read:profile"])
        
        # Mock FastAPI dependencies
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        
        # Should succeed with valid scopes
        result = scope_dependency.dependency(mock_credentials, mock_request)
        assert result is not None
        assert result["sub"] == "test-user-123"
        
        # Test insufficient scopes
        mock_verify_token.return_value = {
            "sub": "test-user-123",
            "scope": "read:profile"  # Missing admin scope
        }
        
        admin_dependency = require_scopes(any_of=["admin:system"])
        
        with pytest.raises(HTTPException) as exc_info:
            admin_dependency.dependency(mock_credentials, mock_request)
        
        assert exc_info.value.status_code == 403
        assert "insufficient_scope" in str(exc_info.value.detail)


class TestTokenSecurityMonitoring:
    """Test token security monitoring features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = TokenSecurityMonitor()
        
    def test_security_monitor_initialization(self):
        """Test security monitor initialization."""
        monitor = TokenSecurityMonitor()
        assert monitor.metrics.total_tokens_issued == 0
        assert monitor.metrics.scope_violations == 0
        assert len(monitor.suspicious_ips) == 0
        
    def test_token_creation_logging(self):
        """Test token creation event logging."""
        monitor = TokenSecurityMonitor()
        
        monitor.log_token_creation(
            user_id="test-user-123",
            token_type="access_token",
            scopes=["read:profile", "write:profile"],
            ip_address="192.168.1.1"
        )
        
        assert monitor.metrics.total_tokens_issued == 1
        
    def test_scope_violation_detection(self):
        """Test scope violation detection and logging."""
        monitor = TokenSecurityMonitor()
        
        monitor.log_scope_violation(
            user_id="test-user-123",
            endpoint="/admin/users",
            required_scopes=["admin:users"],
            token_scopes=["read:profile", "write:profile"],
            ip_address="192.168.1.1"
        )
        
        assert monitor.metrics.scope_violations == 1
        
    def test_suspicious_activity_detection(self):
        """Test suspicious activity detection."""
        monitor = TokenSecurityMonitor()
        
        alert_level = monitor.detect_suspicious_activity(
            user_id="test-user-123",
            activity_type="admin_privilege_escalation_attempt",
            details={"attempted_scope": "admin:system"},
            ip_address="192.168.1.1"
        )
        
        assert alert_level == SecurityAlertLevel.CRITICAL
        assert monitor.metrics.suspicious_activities == 1
        
    def test_token_anomaly_detection(self):
        """Test token anomaly detection."""
        monitor = TokenSecurityMonitor()
        
        # Test with old token
        old_token_payload = {
            "sub": "test-user-123",
            "iat": int((datetime.utcnow() - timedelta(days=2)).timestamp()),  # 2 days old
            "scope": "read:profile write:profile",
            "country": "US"
        }
        
        request_context = {
            "country": "FR",  # Different country
            "user_agent": "Bot/1.0"  # Suspicious user agent
        }
        
        anomalies = monitor.check_token_anomalies(
            user_id="test-user-123",
            token_payload=old_token_payload,
            request_context=request_context
        )
        
        assert "token_age_unusual" in anomalies
        assert "geographic_anomaly" in anomalies
        assert "suspicious_user_agent" in anomalies
        
    def test_security_report_generation(self):
        """Test security report generation."""
        monitor = TokenSecurityMonitor()
        
        # Generate some activity
        monitor.log_token_creation("user1", "access_token", ["read:profile"])
        monitor.log_scope_violation("user2", "/admin", ["admin:system"], ["read:profile"])
        
        report = monitor.get_security_report()
        
        assert "metrics" in report
        assert "suspicious_ips" in report
        assert "report_generated" in report
        assert report["metrics"]["total_tokens_issued"] == 1
        assert report["metrics"]["scope_violations"] == 1


class TestTokenBlacklisting:
    """Test token blacklisting functionality."""
    
    @patch('app.services.auth_jwt_service.upstash_blacklist_token')
    @patch('app.services.auth_jwt_service.is_token_blacklisted')
    def test_token_blacklisting(self, mock_is_blacklisted, mock_blacklist):
        """Test token blacklisting functionality."""
        mock_blacklist.return_value = True
        mock_is_blacklisted.return_value = False
        
        user_data = {"sub": "test-user-123"}
        token = create_access_token(user_data)
        
        # Blacklist the token
        result = blacklist_token(token)
        assert result is True
        
        # Verify blacklist was called
        mock_blacklist.assert_called_once()
        
    @patch('app.services.auth_jwt_service.is_token_blacklisted')
    def test_blacklisted_token_verification(self, mock_is_blacklisted):
        """Test that blacklisted tokens fail verification."""
        mock_is_blacklisted.return_value = True
        
        user_data = {"sub": "test-user-123"}
        token = create_access_token(user_data)
        
        # Verification should fail for blacklisted token
        payload = verify_token(token)
        assert payload is None
        
    def test_token_security_validation(self):
        """Test comprehensive token security validation."""
        user_data = {"sub": "test-user-123"}
        token = create_access_token(user_data)
        
        validation = validate_token_security(token)
        
        assert validation["valid"] is True
        assert validation["jti_present"] is True
        assert validation["user_id_present"] is True
        assert validation["not_expired"] is True


class TestFinancialComplianceFeatures:
    """Test financial application compliance features."""
    
    def test_financial_scopes_coverage(self):
        """Test that all necessary financial scopes are defined."""
        required_financial_scopes = [
            "read:transactions", "write:transactions", "delete:transactions",
            "read:financial_data", "write:financial_data",
            "read:budget", "write:budget", "manage:budget",
            "process:receipts", "ocr:analysis"
        ]
        
        all_scopes = [scope.value for scope in TokenScope]
        
        for scope in required_financial_scopes:
            assert scope in all_scopes, f"Missing required financial scope: {scope}"
            
    def test_audit_trail_compliance(self):
        """Test that security events are properly logged for audit trails."""
        with patch('app.core.audit_logging.log_security_event') as mock_log:
            user_data = {"sub": "test-user-123"}
            create_access_token(user_data, user_role="basic_user")
            
            # Verify audit logging was called
            mock_log.assert_called()
            call_args = mock_log.call_args[0]
            assert call_args[0] == "access_token_created"
            assert "user_id" in call_args[1]
            assert "scopes" in call_args[1]
            
    def test_premium_feature_access_control(self):
        """Test premium feature access control."""
        basic_scopes = get_user_scopes("basic_user", is_premium=False)
        premium_scopes = get_user_scopes("premium_user", is_premium=True)
        
        # Basic users should not have premium scopes
        assert TokenScope.PREMIUM_FEATURES.value not in basic_scopes
        assert TokenScope.ADVANCED_ANALYTICS.value not in basic_scopes
        
        # Premium users should have premium scopes
        assert TokenScope.PREMIUM_FEATURES.value in premium_scopes
        assert TokenScope.ADVANCED_ANALYTICS.value in premium_scopes
        
    def test_admin_privilege_separation(self):
        """Test admin privilege separation."""
        basic_scopes = get_user_scopes("basic_user")
        admin_scopes = get_user_scopes("admin")
        
        admin_only_scopes = [
            TokenScope.ADMIN_SYSTEM.value,
            TokenScope.ADMIN_USERS.value,
            TokenScope.ADMIN_AUDIT.value
        ]
        
        # Basic users should not have admin scopes
        for scope in admin_only_scopes:
            assert scope not in basic_scopes
            
        # Admin users should have admin scopes
        for scope in admin_only_scopes:
            assert scope in admin_scopes


class TestProductionReadinessFeatures:
    """Test production readiness features."""
    
    def test_token_rotation_capability(self):
        """Test token rotation functionality."""
        user_data = {"sub": "test-user-123"}
        
        # Create initial token pair
        initial_tokens = create_token_pair(user_data, user_role="basic_user")
        assert "access_token" in initial_tokens
        assert "refresh_token" in initial_tokens
        assert initial_tokens["token_type"] == "Bearer"
        
        # Verify tokens are different
        assert initial_tokens["access_token"] != initial_tokens["refresh_token"]
        
    def test_high_availability_features(self):
        """Test features that support high availability."""
        # Test graceful handling of blacklist failures
        with patch('app.services.auth_jwt_service.is_token_blacklisted', side_effect=Exception("Redis down")):
            user_data = {"sub": "test-user-123"}
            token = create_access_token(user_data)
            
            # Should still verify token (fail-open for availability)
            # but log the security concern
            payload = verify_token(token)
            assert payload is not None  # Fail-open behavior
            
    def test_performance_considerations(self):
        """Test performance-related features."""
        import time
        
        user_data = {"sub": "test-user-123"}
        
        # Measure token creation performance
        start_time = time.time()
        for _ in range(100):
            create_access_token(user_data)
        end_time = time.time()
        
        # Should create 100 tokens in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0
        
        # Measure token verification performance
        token = create_access_token(user_data)
        start_time = time.time()
        for _ in range(100):
            verify_token(token)
        end_time = time.time()
        
        # Should verify 100 tokens in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])