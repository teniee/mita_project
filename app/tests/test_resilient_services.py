"""
Tests for resilient service implementations
Tests GPT service and Google Auth service with circuit breaker protection
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx
import openai
from fastapi import HTTPException

from app.services.resilient_gpt_service import ResilientGPTService, get_gpt_service
from app.services.resilient_google_auth_service import (
    ResilientGoogleAuthService,
    get_google_auth_service,
    authenticate_google_user
)
from app.core.circuit_breaker import CircuitBreakerState


def _make_mock_request():
    """Create a mock httpx.Request for OpenAI exception constructors"""
    return httpx.Request(method="POST", url="https://api.openai.com/v1/chat/completions")


def _make_mock_response(status_code=429):
    """Create a mock httpx.Response for OpenAI exception constructors"""
    request = _make_mock_request()
    return httpx.Response(status_code=status_code, request=request)


class TestResilientGPTService:
    """Test resilient GPT service functionality"""

    @pytest.fixture
    def gpt_service(self):
        """Create a GPT service with mocked OpenAI client"""
        with patch('app.services.resilient_gpt_service.AsyncOpenAI') as mock_openai:
            service = ResilientGPTService("test_api_key", "gpt-4")
            service.client = mock_openai.return_value
            return service

    @pytest.mark.asyncio
    async def test_successful_financial_advice(self, gpt_service):
        """Test successful financial advice generation"""
        # Mock successful OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Great financial advice here!"

        gpt_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "How can I save money?"}]
        result = await gpt_service.ask_financial_advice(messages)

        assert result == "Great financial advice here!"
        gpt_service.client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, gpt_service):
        """Test rate limit error handling"""
        mock_response = _make_mock_response(status_code=429)
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                "Rate limit exceeded",
                response=mock_response,
                body=None
            )
        )

        messages = [{"role": "user", "content": "Test message"}]
        result = await gpt_service.ask_financial_advice(messages)

        # Should return rate limit response
        assert "high demand" in result.lower() or "wait" in result.lower()

    @pytest.mark.asyncio
    async def test_connection_error_fallback(self, gpt_service):
        """Test connection error fallback"""
        mock_request = _make_mock_request()
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(
                message="Connection failed",
                request=mock_request
            )
        )

        messages = [{"role": "user", "content": "Test message"}]
        result = await gpt_service.ask_financial_advice(messages)

        # Should return fallback response
        assert "temporarily unavailable" in result.lower() or "try again" in result.lower()

    @pytest.mark.asyncio
    async def test_budget_analysis(self, gpt_service):
        """Test budget analysis functionality"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Your budget analysis shows..."

        gpt_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        spending_data = {
            "total_spent": 1500,
            "categories": {"food": 500, "transport": 300}
        }

        result = await gpt_service.analyze_budget(spending_data)

        assert "Your budget analysis shows..." in result

        # Verify correct system prompt was used
        call_args = gpt_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert any("budget analyst" in msg['content'].lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_expense_categorization(self, gpt_service):
        """Test expense categorization with confidence scoring"""
        # Test successful categorization
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Category: Food, Confidence: 90%"

        gpt_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await gpt_service.categorize_expense("McDonald's lunch", 12.50, "McDonald's")

        assert isinstance(result, dict)
        assert 'category' in result
        assert 'confidence' in result
        assert 'reasoning' in result

    @pytest.mark.asyncio
    async def test_expense_categorization_fallback(self, gpt_service):
        """Test expense categorization fallback on error"""
        mock_request = _make_mock_request()
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(
                message="Connection failed",
                request=mock_request
            )
        )

        result = await gpt_service.categorize_expense("Test expense", 10.0)

        assert result['category'] == 'Other'
        assert result['confidence'] == 50
        assert 'unavailable' in result['reasoning']

    @pytest.mark.asyncio
    async def test_authentication_error(self, gpt_service):
        """Test authentication error handling"""
        mock_response = _make_mock_response(status_code=401)
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                "Invalid API key",
                response=mock_response,
                body=None
            )
        )

        messages = [{"role": "user", "content": "Test"}]
        result = await gpt_service.ask_financial_advice(messages)

        assert "configuration" in result.lower() or "support" in result.lower()

    @pytest.mark.asyncio
    async def test_timeout_error(self, gpt_service):
        """Test timeout error handling"""
        mock_request = _make_mock_request()
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.APITimeoutError(request=mock_request)
        )

        messages = [{"role": "user", "content": "Test"}]
        result = await gpt_service.ask_financial_advice(messages)

        # The circuit breaker retries and may catch this as a connection-type error,
        # so the response may come from the timeout handler OR the connection fallback
        assert ("longer than usual" in result.lower() or
                "try again" in result.lower() or
                "temporarily unavailable" in result.lower())

    @pytest.mark.asyncio
    async def test_service_health_check(self, gpt_service):
        """Test service health status"""
        health = await gpt_service.get_service_health()

        assert 'service_name' in health
        assert 'status' in health
        assert 'circuit_breaker_state' in health
        assert 'available_features' in health

        assert health['service_name'] == 'resilient_gpt_service'
        assert len(health['available_features']) == 3

    @pytest.mark.asyncio
    async def test_connection_test(self, gpt_service):
        """Test connection testing"""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, I'm working fine!"

        gpt_service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await gpt_service.test_connection()
        assert result is True

        # Test failed connection
        mock_request = _make_mock_request()
        gpt_service.client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(
                message="Connection failed",
                request=mock_request
            )
        )

        result = await gpt_service.test_connection()
        assert result is False

    def test_singleton_pattern(self):
        """Test GPT service singleton pattern"""
        with patch('app.services.resilient_gpt_service.AsyncOpenAI'):
            # Reset global singleton before testing
            import app.services.resilient_gpt_service as gpt_module
            gpt_module._gpt_service = None

            service1 = get_gpt_service("test_key_1")
            service2 = get_gpt_service("test_key_2")  # Different key, but should return same instance

            assert service1 is service2

            # Clean up singleton to avoid polluting other tests
            gpt_module._gpt_service = None


class TestResilientGoogleAuthService:
    """Test resilient Google authentication service"""

    @pytest.fixture
    def auth_service(self):
        """Create Google auth service"""
        return ResilientGoogleAuthService()

    @pytest.fixture
    def mock_user_repository(self, auth_service):
        """Mock user repository - patches both the module-level function and the service instance"""
        mock_repo = AsyncMock()
        # Patch the service instance's user_repository directly so _get_or_create_user uses it
        auth_service.user_repository = mock_repo
        return mock_repo

    @pytest.mark.asyncio
    async def test_successful_authentication(self, auth_service, mock_user_repository):
        """Test successful Google authentication"""
        # Mock successful Google token verification
        mock_payload = {
            "aud": "796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com",
            "email": "test@example.com",
            "name": "Test User",
            "locale": "en_US"
        }

        # Mock existing user
        mock_user = Mock()
        mock_user.id = "user_123"
        mock_user.email = "test@example.com"
        mock_user_repository.get_by_email.return_value = mock_user
        mock_user_repository.update_last_login.return_value = True

        with patch.object(auth_service, '_verify_google_token', return_value=mock_payload):
            result = await auth_service.authenticate_google_user("valid_token")

            assert result is mock_user
            mock_user_repository.get_by_email.assert_called_once_with("test@example.com")
            mock_user_repository.update_last_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_user_creation(self, auth_service, mock_user_repository):
        """Test creating new user from Google authentication"""
        mock_payload = {
            "aud": "796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com",
            "email": "newuser@example.com",
            "name": "New User",
            "locale": "en_GB"
        }

        # Mock no existing user, then new user creation
        mock_user_repository.get_by_email.return_value = None
        mock_new_user = Mock()
        mock_new_user.email = "newuser@example.com"
        mock_user_repository.create_user.return_value = mock_new_user

        with patch.object(auth_service, '_verify_google_token', return_value=mock_payload):
            result = await auth_service.authenticate_google_user("valid_token")

            assert result is mock_new_user
            mock_user_repository.create_user.assert_called_once()

            # Check user data passed to create_user
            call_args = mock_user_repository.create_user.call_args[0][0]
            assert call_args['email'] == 'newuser@example.com'
            assert call_args['country'] == 'GB'  # Extracted from locale

    @pytest.mark.asyncio
    async def test_invalid_client_id(self, auth_service):
        """Test invalid client ID rejection"""
        mock_payload = {
            "aud": "invalid_client_id",
            "email": "test@example.com"
        }

        with patch.object(auth_service, '_verify_google_token', return_value=mock_payload):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("invalid_token")

            assert exc_info.value.status_code == 401
            assert "Invalid Client ID" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_missing_email(self, auth_service):
        """Test missing email in token"""
        mock_payload = {
            "aud": "796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com",
            "name": "Test User"
            # Missing email
        }

        with patch.object(auth_service, '_verify_google_token', return_value=mock_payload):
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("token_without_email")

            assert exc_info.value.status_code == 400
            assert "Email not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_api_connection_error(self, auth_service):
        """Test Google API connection error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.RequestError("Connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("test_token")

            assert exc_info.value.status_code == 503
            assert "temporarily unavailable" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_api_timeout(self, auth_service):
        """Test Google API timeout"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("test_token")

            assert exc_info.value.status_code == 408
            assert "taking too long" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_api_rate_limit(self, auth_service):
        """Test Google API rate limiting"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = mock_response

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("test_token")

            assert exc_info.value.status_code == 429
            assert "Too many" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_token_response(self, auth_service):
        """Test invalid token response from Google"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = mock_response

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_google_user("invalid_token")

            assert exc_info.value.status_code == 401
            assert "Invalid ID token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_service_health_check(self, auth_service):
        """Test service health status"""
        health = await auth_service.get_service_health()

        assert 'service_name' in health
        assert 'status' in health
        assert 'circuit_breaker_state' in health
        assert 'allowed_client_ids' in health

        assert health['service_name'] == 'google_auth_service'
        assert health['allowed_client_ids'] == 3

    @pytest.mark.asyncio
    async def test_connection_test(self, auth_service):
        """Test connection testing"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = mock_response

            result = await auth_service.test_connection()
            assert result is True

            # Test failed connection
            mock_client_instance.get.side_effect = httpx.RequestError("Failed")
            result = await auth_service.test_connection()
            assert result is False

    def test_singleton_pattern(self):
        """Test Google auth service singleton pattern"""
        service1 = get_google_auth_service()
        service2 = get_google_auth_service()

        assert service1 is service2

    def test_country_extraction(self, auth_service):
        """Test country code extraction from locale"""
        # Test valid locale
        payload = {"locale": "en_GB"}
        country = auth_service._extract_country_from_payload(payload)
        assert country == "GB"

        # Test locale without country
        payload = {"locale": "en"}
        country = auth_service._extract_country_from_payload(payload)
        assert country == "US"  # Default

        # Test missing locale
        payload = {}
        country = auth_service._extract_country_from_payload(payload)
        assert country == "US"  # Default

    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test convenience authentication function"""
        mock_user = Mock()

        with patch('app.services.resilient_google_auth_service.get_google_auth_service') as mock_get_service:
            mock_auth_service = AsyncMock()
            mock_auth_service.authenticate_google_user.return_value = mock_user
            mock_get_service.return_value = mock_auth_service

            result = await authenticate_google_user("test_token")

            assert result is mock_user
            mock_auth_service.authenticate_google_user.assert_called_once_with("test_token")


class TestResilientServicesIntegration:
    """Integration tests for resilient services"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test that services properly integrate with circuit breaker"""
        with patch('app.services.resilient_gpt_service.AsyncOpenAI'):
            gpt_service = ResilientGPTService("test_key")

        # Get circuit breaker
        cb_manager = gpt_service.circuit_breaker_manager
        openai_cb = cb_manager.get_circuit_breaker('openai_chat')

        assert openai_cb.name == 'openai_chat'
        assert openai_cb.state == CircuitBreakerState.CLOSED

        # Verify configuration
        assert openai_cb.config.failure_threshold == 3
        assert openai_cb.config.timeout_duration == 300

    @pytest.mark.asyncio
    async def test_service_isolation(self):
        """Test that different services have isolated circuit breakers"""
        with patch('app.services.resilient_gpt_service.AsyncOpenAI'):
            gpt_service = ResilientGPTService("test_key")
        auth_service = ResilientGoogleAuthService()

        gpt_cb = gpt_service.circuit_breaker_manager.get_circuit_breaker('openai_chat')
        auth_cb = auth_service.circuit_breaker_manager.get_circuit_breaker('google_oauth_verify')

        assert gpt_cb is not auth_cb
        assert gpt_cb.name != auth_cb.name
        assert gpt_cb.config.timeout_duration != auth_cb.config.timeout_duration
