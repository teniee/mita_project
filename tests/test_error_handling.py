"""
Comprehensive tests for error handling system
Tests all exception types, validation, and error responses
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import ValidationError

from app.core.error_handler import (
    MITAException, ValidationException, AuthenticationException,
    AuthorizationException, ResourceNotFoundException, BusinessLogicException,
    ExternalServiceException, DatabaseException, RateLimitException,
    ErrorHandler, InputValidator,
    validate_positive_number, validate_date_range, validate_user_access,
    sanitize_string_input, validate_amount, validate_category, validate_email
)


class TestMITAExceptions:
    """Test custom MITA exception classes"""
    
    def test_mita_exception_basic(self):
        """Test basic MITAException"""
        exc = MITAException("Test error", "TEST_CODE", 400, {"key": "value"})
        
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_CODE"
        assert exc.status_code == 400
        assert exc.details == {"key": "value"}

    def test_validation_exception(self):
        """Test ValidationException"""
        exc = ValidationException("Invalid field", "email", {"format": "invalid"})
        
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 400
        assert exc.details["field"] == "email"
        assert exc.details["format"] == "invalid"

    def test_authentication_exception(self):
        """Test AuthenticationException"""
        exc = AuthenticationException("Invalid token")
        
        assert exc.error_code == "AUTH_ERROR"
        assert exc.status_code == 401
        assert exc.message == "Invalid token"

    def test_authorization_exception(self):
        """Test AuthorizationException"""
        exc = AuthorizationException("Insufficient permissions")
        
        assert exc.error_code == "AUTHORIZATION_ERROR"
        assert exc.status_code == 403
        assert exc.message == "Insufficient permissions"

    def test_resource_not_found_exception(self):
        """Test ResourceNotFoundException"""
        exc = ResourceNotFoundException("User", "123")
        
        assert exc.error_code == "RESOURCE_NOT_FOUND"
        assert exc.status_code == 404
        assert "User not found: 123" in exc.message
        assert exc.details["resource"] == "User"
        assert exc.details["identifier"] == "123"

    def test_business_logic_exception(self):
        """Test BusinessLogicException"""
        exc = BusinessLogicException("Invalid operation", {"amount": 1000})
        
        assert exc.error_code == "BUSINESS_LOGIC_ERROR"
        assert exc.status_code == 422
        assert exc.details["amount"] == 1000

    def test_external_service_exception(self):
        """Test ExternalServiceException"""
        exc = ExternalServiceException("PayPal", "Connection timeout")
        
        assert exc.error_code == "EXTERNAL_SERVICE_ERROR"
        assert exc.status_code == 503
        assert "PayPal: Connection timeout" in exc.message
        assert exc.details["service"] == "PayPal"

    def test_database_exception(self):
        """Test DatabaseException"""
        exc = DatabaseException("Connection failed", {"host": "localhost"})
        
        assert exc.error_code == "DATABASE_ERROR"
        assert exc.status_code == 500
        assert exc.details["host"] == "localhost"

    def test_rate_limit_exception(self):
        """Test RateLimitException"""
        exc = RateLimitException("Too many requests")
        
        assert exc.error_code == "RATE_LIMIT_ERROR"
        assert exc.status_code == 429


class TestErrorHandler:
    """Test ErrorHandler class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_request = Mock(spec=Request)
        self.mock_request.method = "POST"
        self.mock_request.url = "http://test.com/api/test"
        self.mock_request.headers = {"Content-Type": "application/json"}
        self.mock_request.client.host = "127.0.0.1"

    @patch('app.core.error_handler.logger')
    @patch('app.core.error_handler.sentry_sdk')
    def test_log_error_client_error(self, mock_sentry, mock_logger):
        """Test logging client errors"""
        error = ValidationException("Invalid input", "email")
        
        error_id = ErrorHandler.log_error(error, self.mock_request, 123)
        
        assert error_id.startswith("error_")
        mock_logger.warning.assert_called_once()
        mock_sentry.capture_exception.assert_not_called()  # Client errors don't go to Sentry

    @patch('app.core.error_handler.logger')
    @patch('app.core.error_handler.sentry_sdk')
    def test_log_error_server_error(self, mock_sentry, mock_logger):
        """Test logging server errors"""
        error = DatabaseException("Connection failed")
        
        error_id = ErrorHandler.log_error(error, self.mock_request, 123)
        
        assert error_id.startswith("error_")
        mock_logger.error.assert_called_once()
        mock_sentry.capture_exception.assert_called_once_with(error)

    def test_create_error_response_mita_exception(self):
        """Test error response creation for MITA exceptions"""
        error = ValidationException("Invalid email", "email")
        
        response = ErrorHandler.create_error_response(error, self.mock_request, 123)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        content = response.body.decode('utf-8')
        assert '"success": false' in content
        assert '"code": "VALIDATION_ERROR"' in content
        assert '"message": "Invalid email"' in content

    def test_create_error_response_validation_error(self):
        """Test error response for Pydantic ValidationError"""
        # Mock ValidationError
        mock_error = Mock(spec=ValidationError)
        mock_error.errors.return_value = [
            {"loc": ("field1",), "msg": "Field required", "type": "value_error.missing"},
            {"loc": ("field2", "nested"), "msg": "Invalid value", "type": "value_error"}
        ]
        
        response = ErrorHandler.create_error_response(mock_error, self.mock_request)
        
        assert response.status_code == 422
        content = response.body.decode('utf-8')
        assert '"VALIDATION_ERROR"' in content
        assert '"field1"' in content
        assert '"field2.nested"' in content

    def test_create_error_response_sqlalchemy_error(self):
        """Test error response for SQLAlchemy errors"""
        # Test integrity error with duplicate key
        integrity_error = IntegrityError("statement", "params", "duplicate key value")
        
        response = ErrorHandler.create_error_response(integrity_error, self.mock_request)
        
        assert response.status_code == 500
        content = response.body.decode('utf-8')
        assert '"DATABASE_ERROR"' in content
        assert '"Resource already exists"' in content

    def test_create_error_response_generic_exception(self):
        """Test error response for generic exceptions"""
        error = Exception("Unexpected error")
        
        response = ErrorHandler.create_error_response(error, self.mock_request)
        
        assert response.status_code == 500
        content = response.body.decode('utf-8')
        assert '"INTERNAL_SERVER_ERROR"' in content
        assert '"An unexpected error occurred"' in content


class TestValidationFunctions:
    """Test validation utility functions"""
    
    def test_validate_positive_number_valid(self):
        """Test positive number validation with valid input"""
        result = validate_positive_number(10.5, "amount")
        assert result == 10.5

    def test_validate_positive_number_invalid(self):
        """Test positive number validation with invalid input"""
        with pytest.raises(ValidationException) as exc_info:
            validate_positive_number(-5, "amount")
        
        assert "amount must be positive" in str(exc_info.value)
        assert exc_info.value.details["field"] == "amount"

    def test_validate_date_range_valid(self):
        """Test date range validation with valid range"""
        from datetime import datetime, timedelta
        
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        
        # Should not raise exception
        validate_date_range(start, end)

    def test_validate_date_range_invalid_order(self):
        """Test date range validation with invalid order"""
        from datetime import datetime
        
        start = datetime(2025, 1, 31)
        end = datetime(2025, 1, 1)
        
        with pytest.raises(ValidationException) as exc_info:
            validate_date_range(start, end)
        
        assert "Start date must be before end date" in str(exc_info.value)

    def test_validate_date_range_too_long(self):
        """Test date range validation with range too long"""
        from datetime import datetime, timedelta
        
        start = datetime(2025, 1, 1)
        end = start + timedelta(days=400)  # More than 1 year
        
        with pytest.raises(ValidationException) as exc_info:
            validate_date_range(start, end)
        
        assert "Date range cannot exceed 1 year" in str(exc_info.value)

    def test_validate_user_access_valid(self):
        """Test user access validation with valid access"""
        # Should not raise exception
        validate_user_access(123, 123)

    def test_validate_user_access_invalid(self):
        """Test user access validation with invalid access"""
        with pytest.raises(AuthorizationException) as exc_info:
            validate_user_access(123, 456)
        
        assert "Access denied to resource" in str(exc_info.value)

    def test_sanitize_string_input_valid(self):
        """Test string sanitization with valid input"""
        result = sanitize_string_input("  Hello World  ", 20)
        assert result == "Hello World"

    def test_sanitize_string_input_too_long(self):
        """Test string sanitization with input too long"""
        long_string = "a" * 1001
        
        with pytest.raises(ValidationException) as exc_info:
            sanitize_string_input(long_string, 1000)
        
        assert "exceeds maximum length" in str(exc_info.value)

    def test_sanitize_string_input_dangerous_content(self):
        """Test string sanitization with dangerous content"""
        dangerous_input = "<script>alert('xss')</script>"
        
        with pytest.raises(ValidationException) as exc_info:
            sanitize_string_input(dangerous_input)
        
        assert "potentially dangerous content" in str(exc_info.value)

    def test_validate_amount_valid(self):
        """Test amount validation with valid amounts"""
        assert validate_amount(100.50) == 100.50
        assert validate_amount(0.01) == 0.01
        assert validate_amount(999999.99) == 999999.99

    def test_validate_amount_invalid_type(self):
        """Test amount validation with invalid type"""
        with pytest.raises(ValidationException) as exc_info:
            validate_amount("not a number")
        
        assert "Amount must be a number" in str(exc_info.value)

    def test_validate_amount_too_small(self):
        """Test amount validation with amount too small"""
        with pytest.raises(ValidationException) as exc_info:
            validate_amount(0.005)
        
        assert "Amount must be at least" in str(exc_info.value)

    def test_validate_amount_too_large(self):
        """Test amount validation with amount too large"""
        with pytest.raises(ValidationException) as exc_info:
            validate_amount(2000000)
        
        assert "Amount cannot exceed" in str(exc_info.value)

    def test_validate_amount_rounding(self):
        """Test amount validation rounds to 2 decimal places"""
        result = validate_amount(10.999)
        assert result == 11.0

    def test_validate_category_valid(self):
        """Test category validation with valid categories"""
        assert validate_category("Food") == "food"
        assert validate_category("TRANSPORTATION") == "transportation"
        assert validate_category("  entertainment  ") == "entertainment"

    def test_validate_category_invalid(self):
        """Test category validation with invalid category"""
        with pytest.raises(ValidationException) as exc_info:
            validate_category("invalid_category")
        
        assert "Invalid category" in str(exc_info.value)

    def test_validate_email_valid(self):
        """Test email validation with valid emails"""
        assert validate_email("test@example.com") == "test@example.com"
        assert validate_email("  User.Name+Tag@Domain.Co.UK  ") == "user.name+tag@domain.co.uk"

    def test_validate_email_invalid_format(self):
        """Test email validation with invalid format"""
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user@domain",
            "user..double.dot@domain.com"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationException) as exc_info:
                validate_email(email)
            assert "Invalid email format" in str(exc_info.value)

    def test_validate_email_too_long(self):
        """Test email validation with email too long"""
        long_email = "a" * 250 + "@domain.com"
        
        with pytest.raises(ValidationException) as exc_info:
            validate_email(long_email)
        
        assert "Email address too long" in str(exc_info.value)


class TestInputValidator:
    """Test InputValidator class"""
    
    def test_validate_expense_data_valid(self):
        """Test expense data validation with valid data"""
        data = {
            'amount': 50.25,
            'category': 'food',
            'description': 'Lunch at restaurant',
            'date': '2025-01-30T12:00:00Z'
        }
        
        result = InputValidator.validate_expense_data(data)
        
        assert result['amount'] == 50.25
        assert result['category'] == 'food'
        assert result['description'] == 'Lunch at restaurant'
        assert result['date'].year == 2025

    def test_validate_expense_data_missing_required(self):
        """Test expense data validation with missing required fields"""
        data = {'description': 'Missing amount and category'}
        
        with pytest.raises(ValidationException) as exc_info:
            InputValidator.validate_expense_data(data)
        
        assert "Amount is required" in str(exc_info.value)

    def test_validate_expense_data_invalid_date(self):
        """Test expense data validation with invalid date"""
        data = {
            'amount': 50.0,
            'category': 'food',
            'date': 'invalid-date-format'
        }
        
        with pytest.raises(ValidationException) as exc_info:
            InputValidator.validate_expense_data(data)
        
        assert "Invalid date format" in str(exc_info.value)

    def test_validate_budget_data_valid(self):
        """Test budget data validation with valid data"""
        data = {
            'monthly_income': 5000.0,
            'savings_target': 1000.0,
            'categories': {
                'food': 800.0,
                'transportation': 400.0,
                'entertainment': 200.0
            }
        }
        
        result = InputValidator.validate_budget_data(data)
        
        assert result['monthly_income'] == 5000.0
        assert result['savings_target'] == 1000.0
        assert result['categories']['food'] == 800.0
        assert result['categories']['transportation'] == 400.0

    def test_validate_budget_data_invalid_category(self):
        """Test budget data validation with invalid category"""
        data = {
            'categories': {
                'invalid_category': 100.0,
                'food': 200.0
            }
        }
        
        with pytest.raises(ValidationException) as exc_info:
            InputValidator.validate_budget_data(data)
        
        assert "Invalid category" in str(exc_info.value)

    def test_validate_user_data_valid(self):
        """Test user data validation with valid data"""
        data = {
            'email': 'test@example.com',
            'name': 'John Doe',
            'password': 'SecurePass123!'
        }
        
        result = InputValidator.validate_user_data(data)
        
        assert result['email'] == 'test@example.com'
        assert result['name'] == 'John Doe'
        assert result['password'] == 'SecurePass123!'

    def test_validate_user_data_weak_password(self):
        """Test user data validation with weak password"""
        data = {
            'email': 'test@example.com',
            'password': '123'  # Too short
        }
        
        with pytest.raises(ValidationException) as exc_info:
            InputValidator.validate_user_data(data)
        
        assert "Password must be at least 8 characters" in str(exc_info.value)

    def test_validate_user_data_password_too_long(self):
        """Test user data validation with password too long"""
        data = {
            'password': 'a' * 129  # Too long
        }
        
        with pytest.raises(ValidationException) as exc_info:
            InputValidator.validate_user_data(data)
        
        assert "Password too long" in str(exc_info.value)


class TestHandleDatabaseErrorsDecorator:
    """Test handle_database_errors decorator"""
    
    def test_decorator_normal_function(self):
        """Test decorator with normal function execution"""
        from app.core.error_handler import handle_database_errors
        
        @handle_database_errors
        def normal_function():
            return "success"
        
        result = normal_function()
        assert result == "success"

    def test_decorator_integrity_error_duplicate(self):
        """Test decorator with integrity error (duplicate key)"""
        from app.core.error_handler import handle_database_errors
        
        @handle_database_errors
        def function_with_duplicate_error():
            raise IntegrityError("statement", "params", "duplicate key value violates unique constraint")
        
        with pytest.raises(BusinessLogicException) as exc_info:
            function_with_duplicate_error()
        
        assert "Resource already exists" in str(exc_info.value)

    def test_decorator_integrity_error_foreign_key(self):
        """Test decorator with integrity error (foreign key)"""
        from app.core.error_handler import handle_database_errors
        
        @handle_database_errors
        def function_with_fk_error():
            raise IntegrityError("statement", "params", "foreign key constraint fails")
        
        with pytest.raises(BusinessLogicException) as exc_info:
            function_with_fk_error()
        
        assert "Invalid reference to related resource" in str(exc_info.value)

    def test_decorator_generic_sqlalchemy_error(self):
        """Test decorator with generic SQLAlchemy error"""
        from app.core.error_handler import handle_database_errors
        
        @handle_database_errors
        def function_with_db_error():
            raise SQLAlchemyError("Database connection failed")
        
        with pytest.raises(DatabaseException) as exc_info:
            function_with_db_error()
        
        assert "Database operation failed" in str(exc_info.value)


@pytest.fixture
def mock_request():
    """Fixture for mock HTTP request"""
    request = Mock(spec=Request)
    request.method = "GET"
    request.url = "http://test.com/api/test"
    request.headers = {"Authorization": "Bearer token"}
    request.client.host = "192.168.1.1"
    return request


class TestExceptionHandlers:
    """Test FastAPI exception handlers"""
    
    def test_mita_exception_handler(self, mock_request):
        """Test MITA exception handler"""
        from app.core.error_handler import mita_exception_handler
        import asyncio
        
        exc = ValidationException("Test validation error", "field1")
        
        response = asyncio.run(mita_exception_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    def test_validation_exception_handler(self, mock_request):
        """Test validation exception handler"""
        from app.core.error_handler import validation_exception_handler
        import asyncio
        
        # Mock ValidationError
        mock_error = Mock(spec=ValidationError)
        mock_error.errors.return_value = [
            {"loc": ("field1",), "msg": "Required", "type": "missing"}
        ]
        
        response = asyncio.run(validation_exception_handler(mock_request, mock_error))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422

    def test_sqlalchemy_exception_handler(self, mock_request):
        """Test SQLAlchemy exception handler"""
        from app.core.error_handler import sqlalchemy_exception_handler
        import asyncio
        
        exc = SQLAlchemyError("Database error")
        
        response = asyncio.run(sqlalchemy_exception_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    def test_generic_exception_handler(self, mock_request):
        """Test generic exception handler"""
        from app.core.error_handler import generic_exception_handler
        import asyncio
        
        exc = Exception("Unexpected error")
        
        response = asyncio.run(generic_exception_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500