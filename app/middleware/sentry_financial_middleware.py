"""
Financial-Specific Sentry Monitoring Middleware
Provides comprehensive monitoring for financial operations with compliance awareness
"""

import asyncio
import time
import logging
from typing import Any, Optional, Callable
from functools import wraps
from contextlib import asynccontextmanager

import sentry_sdk
from sentry_sdk import set_user, set_tag, set_context, add_breadcrumb
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.sentry_service import (
    sentry_service, FinancialErrorCategory, FinancialSeverity
)
from app.services.performance_monitor_enhanced import performance_monitor

logger = logging.getLogger(__name__)


class FinancialSentryMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds comprehensive financial monitoring to all requests
    """
    
    def __init__(
        self,
        app,
        enable_performance_monitoring: bool = True,
        enable_financial_context: bool = True,
        sensitive_endpoints: Optional[list] = None
    ):
        super().__init__(app)
        self.enable_performance_monitoring = enable_performance_monitoring
        self.enable_financial_context = enable_financial_context
        self.sensitive_endpoints = sensitive_endpoints or [
            '/api/auth/', '/api/transactions/', '/api/financial/',
            '/api/payments/', '/api/users/profile', '/api/budget/'
        ]
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive financial monitoring"""
        
        start_time = time.time()
        user_id = None
        transaction_id = None
        financial_operation = None
        
        # Extract user context from request
        try:
            user_id = await self._extract_user_id(request)
            transaction_id = self._extract_transaction_id(request)
            financial_operation = self._detect_financial_operation(request)
        except Exception as e:
            logger.debug(f"Failed to extract request context: {e}")
        
        # Set Sentry context for financial operations
        if self.enable_financial_context:
            self._set_financial_context(request, user_id, transaction_id, financial_operation)
        
        # Determine if this is a sensitive endpoint
        is_sensitive = any(endpoint in request.url.path for endpoint in self.sensitive_endpoints)
        
        response = None
        
        try:
            # Monitor performance if enabled
            if self.enable_performance_monitoring:
                async with performance_monitor.monitor_api_request(
                    request=request,
                    user_id=user_id,
                    additional_context={
                        'financial_operation': financial_operation,
                        'transaction_id': transaction_id,
                        'is_sensitive_endpoint': is_sensitive
                    }
                ):
                    response = await call_next(request)
            else:
                response = await call_next(request)
                
            # Add success breadcrumb for financial operations
            if financial_operation:
                add_breadcrumb(
                    message=f"Financial operation completed: {financial_operation}",
                    category="financial_success",
                    level="info",
                    data={
                        'operation': financial_operation,
                        'user_id': user_id,
                        'transaction_id': transaction_id,
                        'status_code': response.status_code,
                        'duration_ms': (time.time() - start_time) * 1000
                    }
                )
                
        except Exception as e:
            
            # Capture financial error with enhanced context
            if financial_operation:
                await sentry_service.capture_financial_error(
                    exception=e,
                    category=self._categorize_financial_error(request, financial_operation),
                    severity=self._determine_error_severity(request, e, is_sensitive),
                    user_id=user_id,
                    transaction_id=transaction_id,
                    request=request,
                    additional_context={
                        'financial_operation': financial_operation,
                        'is_sensitive_endpoint': is_sensitive,
                        'request_path': request.url.path,
                        'request_method': request.method,
                        'duration_ms': (time.time() - start_time) * 1000
                    }
                )
            
            raise
            
        finally:
            # Log financial operation metrics
            duration_ms = (time.time() - start_time) * 1000
            
            if financial_operation and duration_ms > 1000:  # Log slow financial operations
                logger.warning(
                    f"Slow financial operation: {financial_operation} "
                    f"took {duration_ms:.2f}ms for user {user_id}"
                )
        
        return response
    
    async def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        try:
            # Check if user is already in request state
            if hasattr(request.state, 'user') and request.state.user:
                return getattr(request.state.user, 'id', None)
            
            # Try to extract from JWT token
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                from app.services.auth_jwt_service import get_token_info
                token_info = get_token_info(auth_header.replace("Bearer ", ""))
                if token_info:
                    return token_info.get("user_id")
                    
        except Exception as e:
            logger.debug(f"Failed to extract user ID: {e}")
        
        return None
    
    def _extract_transaction_id(self, request: Request) -> Optional[str]:
        """Extract transaction ID from request"""
        try:
            # Check URL path for transaction ID
            if '/transactions/' in request.url.path:
                path_parts = request.url.path.split('/')
                if 'transactions' in path_parts:
                    idx = path_parts.index('transactions')
                    if idx + 1 < len(path_parts) and path_parts[idx + 1]:
                        return path_parts[idx + 1]
            
            # Check request body for transaction_id (for POST/PUT requests)
            # This would need to be implemented based on your request parsing logic
            
        except Exception as e:
            logger.debug(f"Failed to extract transaction ID: {e}")
        
        return None
    
    def _detect_financial_operation(self, request: Request) -> Optional[str]:
        """Detect the type of financial operation from request"""
        path = request.url.path.lower()
        method = request.method.upper()
        
        # Map endpoints to financial operations
        if '/auth/login' in path or '/auth/register' in path:
            return 'authentication'
        elif '/transactions' in path:
            if method in ['POST', 'PUT']:
                return 'transaction_processing'
            else:
                return 'transaction_retrieval'
        elif '/budget' in path:
            return 'budget_calculation'
        elif '/financial' in path:
            return 'financial_analysis'
        elif '/payments' in path:
            return 'payment_processing'
        elif '/users/profile' in path:
            return 'account_management'
        elif '/ocr' in path or '/receipt' in path:
            return 'receipt_processing'
        
        return None
    
    def _set_financial_context(
        self,
        request: Request,
        user_id: Optional[str],
        transaction_id: Optional[str],
        financial_operation: Optional[str]
    ):
        """Set comprehensive financial context in Sentry"""
        
        # Set user context
        if user_id:
            set_user({"id": user_id})
            set_tag("user_authenticated", True)
        else:
            set_tag("user_authenticated", False)
        
        # Set financial operation context
        if financial_operation:
            set_tag("financial_operation", financial_operation)
            set_context("financial", {
                "operation": financial_operation,
                "transaction_id": transaction_id,
                "user_id": user_id,
                "compliance_monitored": True,
                "pci_scope": self._is_pci_scope(request),
                "request_path": request.url.path,
                "request_method": request.method
            })
        
        # Set compliance context
        set_context("compliance", {
            "pci_dss_applicable": True,
            "data_classification": "confidential",
            "monitoring_required": True,
            "audit_trail": True
        })
        
        # Add breadcrumb for financial operation start
        add_breadcrumb(
            message=f"Starting financial operation: {financial_operation or 'unknown'}",
            category="financial_operation",
            level="info",
            data={
                "operation": financial_operation,
                "user_id": user_id,
                "transaction_id": transaction_id,
                "endpoint": request.url.path
            }
        )
    
    def _is_pci_scope(self, request: Request) -> bool:
        """Determine if request is in PCI DSS scope"""
        pci_endpoints = ['/api/payments/', '/api/cards/', '/api/billing/']
        return any(endpoint in request.url.path for endpoint in pci_endpoints)
    
    def _categorize_financial_error(
        self,
        request: Request,
        financial_operation: str
    ) -> FinancialErrorCategory:
        """Categorize error based on financial operation"""
        
        operation_mapping = {
            'authentication': FinancialErrorCategory.AUTHENTICATION,
            'transaction_processing': FinancialErrorCategory.TRANSACTION_PROCESSING,
            'payment_processing': FinancialErrorCategory.PAYMENT_PROCESSING,
            'budget_calculation': FinancialErrorCategory.BUDGET_CALCULATION,
            'financial_analysis': FinancialErrorCategory.FINANCIAL_ANALYSIS,
            'account_management': FinancialErrorCategory.ACCOUNT_MANAGEMENT,
        }
        
        return operation_mapping.get(
            financial_operation,
            FinancialErrorCategory.SYSTEM_ERROR
        )
    
    def _determine_error_severity(
        self,
        request: Request,
        error: Exception,
        is_sensitive: bool
    ) -> FinancialSeverity:
        """Determine error severity based on context"""
        
        error_str = str(error).lower()
        
        # Security-critical errors
        if any(keyword in error_str for keyword in ['unauthorized', 'forbidden', 'security']):
            return FinancialSeverity.SECURITY_CRITICAL
        
        # Financial operation critical errors
        if any(keyword in error_str for keyword in ['payment', 'transaction', 'balance']):
            return FinancialSeverity.CRITICAL
        
        # Sensitive endpoint errors
        if is_sensitive:
            return FinancialSeverity.HIGH
        
        # Database or system errors
        if any(keyword in error_str for keyword in ['database', 'connection', 'timeout']):
            return FinancialSeverity.HIGH
        
        return FinancialSeverity.MEDIUM


def financial_operation_monitor(
    operation_name: str,
    category: FinancialErrorCategory = FinancialErrorCategory.SYSTEM_ERROR,
    track_performance: bool = True,
    require_user: bool = False
):
    """
    Decorator for monitoring financial operations with comprehensive Sentry integration
    
    Usage:
        @financial_operation_monitor(
            operation_name="process_payment",
            category=FinancialErrorCategory.PAYMENT_PROCESSING,
            track_performance=True,
            require_user=True
        )
        async def process_payment(user_id: str, amount: float, currency: str):
            # Payment processing logic
            pass
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            user_id = kwargs.get('user_id') or (args[0] if args and isinstance(args[0], str) else None)
            
            # Validate user requirement
            if require_user and not user_id:
                error = ValueError("User ID required for this financial operation")
                await sentry_service.capture_financial_error(
                    exception=error,
                    category=FinancialErrorCategory.AUTHORIZATION,
                    severity=FinancialSeverity.HIGH,
                    additional_context={
                        'operation_name': operation_name,
                        'validation_failure': 'missing_user_id'
                    }
                )
                raise error
            
            # Set Sentry context
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("financial_operation", operation_name)
                scope.set_tag("operation_category", category.value)
                scope.set_tag("compliance_monitored", True)
                
                if user_id:
                    scope.set_user({"id": user_id})
                
                # Add operation start breadcrumb
                add_breadcrumb(
                    message=f"Starting {operation_name}",
                    category="financial_operation",
                    level="info",
                    data={
                        "operation": operation_name,
                        "category": category.value,
                        "user_id": user_id,
                        "function": func.__name__
                    }
                )
                
                try:
                    # Execute with performance monitoring if enabled
                    if track_performance:
                        async with performance_monitor.monitor_financial_operation(
                            operation_name=operation_name,
                            user_id=user_id or "anonymous",
                            additional_context={
                                'function_name': func.__name__,
                                'category': category.value,
                                'args_count': len(args),
                                'kwargs_keys': list(kwargs.keys())
                            }
                        ):
                            result = await func(*args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
                    
                    # Add success breadcrumb
                    duration_ms = (time.time() - start_time) * 1000
                    add_breadcrumb(
                        message=f"Completed {operation_name} successfully",
                        category="financial_success",
                        level="info",
                        data={
                            "operation": operation_name,
                            "user_id": user_id,
                            "duration_ms": duration_ms,
                            "function": func.__name__
                        }
                    )
                    
                    return result
                    
                except Exception as e:
                    # Capture financial error
                    duration_ms = (time.time() - start_time) * 1000
                    
                    await sentry_service.capture_financial_error(
                        exception=e,
                        category=category,
                        severity=FinancialSeverity.HIGH,
                        user_id=user_id,
                        additional_context={
                            'operation_name': operation_name,
                            'function_name': func.__name__,
                            'duration_ms': duration_ms,
                            'args_count': len(args),
                            'kwargs_keys': list(kwargs.keys()),
                            'compliance_impact': 'HIGH'
                        }
                    )
                    
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Synchronous version (if needed)
            start_time = time.time()
            user_id = kwargs.get('user_id') or (args[0] if args and isinstance(args[0], str) else None)
            
            if require_user and not user_id:
                raise ValueError("User ID required for this financial operation")
            
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("financial_operation", operation_name)
                scope.set_tag("operation_category", category.value)
                
                if user_id:
                    scope.set_user({"id": user_id})
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Log success
                    duration_ms = (time.time() - start_time) * 1000
                    logger.info(f"Financial operation {operation_name} completed in {duration_ms:.2f}ms")
                    
                    return result
                    
                except Exception as e:
                    # Capture error synchronously
                    sentry_sdk.capture_exception(e)
                    raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@asynccontextmanager
async def financial_transaction_context(
    user_id: str,
    operation: str,
    transaction_id: Optional[str] = None,
    amount: Optional[float] = None,
    currency: Optional[str] = None
):
    """
    Context manager for financial transactions with comprehensive monitoring
    
    Usage:
        async with financial_transaction_context(
            user_id="user123",
            operation="payment_processing",
            transaction_id="txn_456",
            amount=100.0,
            currency="USD"
        ) as ctx:
            # Financial transaction logic
            result = await process_payment()
            ctx.set_result(result)
    """
    
    start_time = time.time()
    
    # Start Sentry transaction
    transaction = sentry_sdk.start_transaction(
        op="financial.transaction",
        name=f"Financial Transaction: {operation}",
        sampled=True
    )
    
    transaction.set_tag("financial_operation", operation)
    transaction.set_tag("user_id", user_id)
    transaction.set_tag("compliance_monitored", True)
    
    if transaction_id:
        transaction.set_tag("transaction_id", transaction_id)
    if amount is not None:
        transaction.set_data("amount", amount)
    if currency:
        transaction.set_tag("currency", currency)
    
    # Set user context
    set_user({"id": user_id})
    
    # Context object to return
    class TransactionContext:
        def __init__(self):
            self.result = None
            self.metadata = {}
        
        def set_result(self, result):
            self.result = result
            transaction.set_data("result_type", type(result).__name__)
        
        def add_metadata(self, key: str, value: Any):
            self.metadata[key] = value
            transaction.set_data(key, value)
    
    context = TransactionContext()
    
    try:
        # Add start breadcrumb
        add_breadcrumb(
            message=f"Starting financial transaction: {operation}",
            category="financial_transaction",
            level="info",
            data={
                "operation": operation,
                "user_id": user_id,
                "transaction_id": transaction_id,
                "amount": amount,
                "currency": currency
            }
        )
        
        yield context
        
        # Add success breadcrumb
        duration_ms = (time.time() - start_time) * 1000
        add_breadcrumb(
            message=f"Financial transaction completed: {operation}",
            category="financial_success",
            level="info",
            data={
                "operation": operation,
                "user_id": user_id,
                "transaction_id": transaction_id,
                "duration_ms": duration_ms,
                "result_available": context.result is not None
            }
        )
        
        transaction.set_data("duration_ms", duration_ms)
        transaction.set_tag("success", True)
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Capture financial error
        await sentry_service.capture_financial_error(
            exception=e,
            category=FinancialErrorCategory.TRANSACTION_PROCESSING,
            severity=FinancialSeverity.CRITICAL,
            user_id=user_id,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            additional_context={
                'operation': operation,
                'duration_ms': duration_ms,
                'context_metadata': context.metadata
            }
        )
        
        transaction.set_tag("success", False)
        transaction.set_data("error_message", str(e))
        
        raise
        
    finally:
        transaction.finish()