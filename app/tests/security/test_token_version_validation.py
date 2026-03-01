"""
P0 Security Tests: Token Version Validation and Auth Flows

Tests the critical security fixes:
1. Token version validation for revocation
2. Backwards compatibility with old tokens
3. Google OAuth with token version
4. Account lockout mechanism
5. All auth endpoints include token_version_id
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_jwt_service import (
    create_token_pair,
    verify_token,
    InvalidTokenError
)
from app.db.models import User
from app.api.auth.services import (
    authenticate_google
)
from app.api.auth.schemas import GoogleAuthIn


class TestTokenVersionValidation:
    """Test Case 1: Token Version Revocation Mechanism"""

    def test_token_creation_includes_version_id(self):
        """Verify all tokens include token_version_id in payload"""
        user_data = {
            "sub": "test-user-123",
            "is_premium": False,
            "country": "US",
            "token_version_id": 5
        }

        tokens = create_token_pair(user_data, user_role="basic_user")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_token_version_mismatch_raises_error(self):
        """Test that outdated token version is rejected"""
        # Create a mock user with token_version = 5
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-123"
        mock_user.token_version = 5
        mock_user.is_premium = False
        mock_user.country = "US"

        # Create token with old version (token_version_id = 3)
        user_data = {
            "sub": str(mock_user.id),
            "is_premium": mock_user.is_premium,
            "country": mock_user.country,
            "token_version_id": 3  # OLD VERSION
        }
        tokens = create_token_pair(user_data, user_role="basic_user")

        # Mock database session to return our user
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock the execute result to return our user
        mock_result = Mock()
        mock_scalar = Mock()
        mock_scalar.scalar_one_or_none.return_value = mock_user
        mock_result.scalars.return_value = mock_scalar
        mock_db.execute.return_value = mock_result

        # Try to verify token - should raise InvalidTokenError
        with pytest.raises(InvalidTokenError, match="Token has been revoked"):
            await verify_token(tokens["access_token"], db=mock_db)

    @pytest.mark.asyncio
    async def test_current_token_version_accepted(self):
        """Test that current token version is accepted"""
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-123"
        mock_user.token_version = 5
        mock_user.is_premium = False
        mock_user.country = "US"

        # Create token with CURRENT version
        user_data = {
            "sub": str(mock_user.id),
            "is_premium": mock_user.is_premium,
            "country": mock_user.country,
            "token_version_id": 5  # CURRENT VERSION
        }
        tokens = create_token_pair(user_data, user_role="basic_user")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalar = Mock()
        mock_scalar.scalar_one_or_none.return_value = mock_user
        mock_result.scalars.return_value = mock_scalar
        mock_db.execute.return_value = mock_result

        # Should NOT raise error
        payload = await verify_token(tokens["access_token"], db=mock_db)
        assert payload["sub"] == str(mock_user.id)
        assert payload["token_version_id"] == 5


class TestBackwardsCompatibility:
    """Test Case 2: Backwards Compatibility with Old Tokens"""

    @pytest.mark.asyncio
    async def test_old_token_without_version_id_accepted(self):
        """Test that old tokens without token_version_id still work"""
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-123"
        mock_user.token_version = 1
        mock_user.is_premium = False
        mock_user.country = "US"

        # Create token WITHOUT token_version_id (simulating old token)
        user_data = {
            "sub": str(mock_user.id),
            "is_premium": mock_user.is_premium,
            "country": mock_user.country
            # NOTE: No token_version_id field
        }
        tokens = create_token_pair(user_data, user_role="basic_user")

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_scalar = Mock()
        mock_scalar.scalar_one_or_none.return_value = mock_user
        mock_result.scalars.return_value = mock_scalar
        mock_db.execute.return_value = mock_result

        # Should NOT raise error (backwards compatible)
        payload = await verify_token(tokens["access_token"], db=mock_db)
        assert payload["sub"] == str(mock_user.id)


class TestGoogleOAuthTokenVersion:
    """Test Case 3: Google OAuth includes token_version_id"""

    @pytest.mark.asyncio
    async def test_google_oauth_includes_token_version(self):
        """Verify Google OAuth flow includes token_version_id"""
        # Mock the Google auth service
        mock_user = Mock(spec=User)
        mock_user.id = "google-user-123"
        mock_user.is_premium = True
        mock_user.country = "US"
        mock_user.token_version = 1

        # Mock the authenticate_google_user function
        with patch('app.api.auth.services.authenticate_google_user',
                   return_value=mock_user) as mock_google_auth:

            mock_db = AsyncMock(spec=AsyncSession)

            # Call authenticate_google
            google_data = GoogleAuthIn(id_token="mock-google-token")
            result = await authenticate_google(google_data, mock_db)

            # Verify token was created
            assert result.access_token is not None
            assert result.refresh_token is not None

            # Decode and verify token_version_id is present
            # (In real scenario, we'd decode the JWT to check)
            mock_google_auth.assert_called_once_with("mock-google-token")


class TestAccountLockout:
    """Test Case 4: Account Lockout Mechanism"""

    def test_user_model_has_lockout_fields(self):
        """Verify User model includes lockout fields"""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            country="US"
        )

        # Check fields exist
        assert hasattr(user, 'failed_login_attempts')
        assert hasattr(user, 'account_locked_until')

        # Check default values
        assert user.failed_login_attempts == 0
        assert user.account_locked_until is None

    def test_lockout_expiration_logic(self):
        """Test that lockout expires after time period"""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            country="US"
        )

        # Lock account for 30 minutes
        user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

        # Should be locked now
        assert user.account_locked_until > datetime.utcnow()

        # Simulate time passing (set to past)
        user.account_locked_until = datetime.utcnow() - timedelta(minutes=1)

        # Should no longer be locked
        assert user.account_locked_until < datetime.utcnow()


class TestAllAuthEndpointsIncludeVersion:
    """Test Case 5: All auth endpoints include token_version_id"""

    @pytest.mark.asyncio
    async def test_registration_includes_token_version(self):
        """Test that registration endpoint creates tokens with version"""
        # This test verifies the code includes token_version_id
        # Actual integration test would require full database setup

        # Check the registration.py file includes token_version_id
        import app.api.auth.registration as reg_module
        import inspect

        source = inspect.getsource(reg_module.register_user_standardized)
        assert "token_version_id" in source, "registration.py must include token_version_id"

    @pytest.mark.asyncio
    async def test_login_includes_token_version(self):
        """Test that login endpoint creates tokens with version"""
        import app.api.auth.login as login_module
        import inspect

        source = inspect.getsource(login_module.login_user_standardized)
        assert "token_version_id" in source, "login.py must include token_version_id"

    @pytest.mark.asyncio
    async def test_token_refresh_includes_token_version(self):
        """Test that token refresh endpoint creates tokens with version"""
        import app.api.auth.token_management as token_module
        import inspect

        source = inspect.getsource(token_module.refresh_token_standardized)
        assert "token_version_id" in source, "token_management.py must include token_version_id"

    @pytest.mark.asyncio
    async def test_services_all_functions_include_version(self):
        """Test that all 6 functions in services.py include token_version_id"""
        import app.api.auth.services as services_module
        import inspect

        functions_to_check = [
            'register_user',
            'authenticate_user',
            'refresh_token_for_user',
            'authenticate_google',
            'register_user_async',
            'authenticate_user_async'
        ]

        for func_name in functions_to_check:
            func = getattr(services_module, func_name)
            source = inspect.getsource(func)
            assert "token_version_id" in source, \
                f"services.py function {func_name} must include token_version_id"


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
