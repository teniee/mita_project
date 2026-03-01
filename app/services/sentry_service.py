"""
Comprehensive Sentry Integration Service for MITA Finance
Provides advanced error monitoring, performance tracking, and financial-specific logging
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from contextlib import contextmanager

import sentry_sdk
from sentry_sdk import (
    set_user, set_tag, add_breadcrumb,
    capture_exception, capture_message, push_scope,
    start_transaction, start_span
)
from fastapi import Request

logger = logging.getLogger(__name__)


class FinancialErrorCategory(Enum):
    """Financial application specific error categories"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    TRANSACTION_PROCESSING = "transaction_processing"
    PAYMENT_PROCESSING = "payment_processing"
    ACCOUNT_MANAGEMENT = "account_management"
    BUDGET_CALCULATION = "budget_calculation"
    FINANCIAL_ANALYSIS = "financial_analysis"
    DATA_VALIDATION = "data_validation"
    EXTERNAL_INTEGRATION = "external_integration"
    SECURITY_VIOLATION = "security_violation"
    COMPLIANCE_ISSUE = "compliance_issue"
    SYSTEM_ERROR = "system_error"


class FinancialSeverity(Enum):
    """Financial application specific severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    SECURITY_CRITICAL = "security_critical"


class SentryFinancialService:
    """Enhanced Sentry service for financial applications"""
    
    def __init__(self):
        self.initialized = bool(sentry_sdk.Hub.current.client)
        if not self.initialized:
            logger.warning("Sentry not initialized - error monitoring will be limited")
    
    def capture_financial_error(
        self,
        exception: Exception,
        category: FinancialErrorCategory,
        severity: FinancialSeverity = FinancialSeverity.MEDIUM,
        user_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Capture financial-specific errors with enhanced context
        
        Returns:
            str: Event ID from Sentry
        """
        if not self.initialized:
            logger.error(f"Financial error (not sent to Sentry): {exception}")
            return ""
        
        with push_scope() as scope:
            # Set financial error context
            scope.set_tag("error_category", category.value)
            scope.set_tag("severity", severity.value)
            scope.set_tag("financial_error", True)
            
            # Set user context
            if user_id:
                scope.set_user({"id": user_id})
            
            # Set financial context
            financial_context = {
                "category": category.value,
                "severity": severity.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if transaction_id:
                financial_context["transaction_id"] = transaction_id
            if amount is not None:
                financial_context["amount"] = amount
            if currency:
                financial_context["currency"] = currency
            
            scope.set_context("financial_operation", financial_context)
            
            # Set request context
            if request:
                self._set_request_context(scope, request)
            
            # Set additional context
            if additional_context:
                for key, value in additional_context.items():
                    scope.set_extra(key, value)
            
            # Add breadcrumb for financial operation
            add_breadcrumb(
                message=f"Financial error: {category.value}",
                category="financial",
                level="error",
                data={
                    "category": category.value,
                    "severity": severity.value,
                    "user_id": user_id,
                    "transaction_id": transaction_id
                }
            )
            
            # Capture the exception
            event_id = capture_exception(exception)
            
            # Log to application logger as well
            logger.error(
                f"Financial error captured [Sentry: {event_id}] - "
                f"Category: {category.value}, Severity: {severity.value}, "
                f"User: {user_id}, Transaction: {transaction_id}, Error: {str(exception)}"
            )
            
            return event_id or ""
    
    def capture_transaction_error(
        self,
        exception: Exception,
        user_id: str,
        transaction_id: str,
        amount: float,
        currency: str,
        transaction_type: str,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        request: Optional[Request] = None
    ) -> str:
        """Capture transaction-specific errors"""
        
        additional_context = {
            "transaction_type": transaction_type,
            "merchant": merchant,
            "transaction_category": category,
            "compliance_level": "PCI_DSS"
        }
        
        return self.capture_financial_error(
            exception=exception,
            category=FinancialErrorCategory.TRANSACTION_PROCESSING,
            severity=FinancialSeverity.HIGH,
            user_id=user_id,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            request=request,
            additional_context=additional_context
        )
    
    def capture_authentication_error(
        self,
        exception: Exception,
        user_id: Optional[str] = None,
        auth_method: Optional[str] = None,
        ip_address: Optional[str] = None,
        request: Optional[Request] = None
    ) -> str:
        """Capture authentication-specific errors"""
        
        additional_context = {
            "auth_method": auth_method,
            "ip_address": ip_address,
            "security_event": True,
            "compliance_impact": "HIGH"
        }
        
        return self.capture_financial_error(
            exception=exception,
            category=FinancialErrorCategory.AUTHENTICATION,
            severity=FinancialSeverity.SECURITY_CRITICAL,
            user_id=user_id,
            request=request,
            additional_context=additional_context
        )
    
    def capture_payment_error(
        self,
        exception: Exception,
        user_id: str,
        payment_method: str,
        amount: float,
        currency: str,
        payment_provider: str,
        request: Optional[Request] = None
    ) -> str:
        """Capture payment processing errors"""
        
        additional_context = {
            "payment_method": payment_method,
            "payment_provider": payment_provider,
            "pci_compliance_required": True,
            "financial_impact": "DIRECT"
        }
        
        return self.capture_financial_error(
            exception=exception,
            category=FinancialErrorCategory.PAYMENT_PROCESSING,
            severity=FinancialSeverity.CRITICAL,
            user_id=user_id,
            amount=amount,
            currency=currency,
            request=request,
            additional_context=additional_context
        )
    
    def capture_budget_error(
        self,
        exception: Exception,
        user_id: str,
        budget_category: str,
        calculation_type: str,
        request: Optional[Request] = None
    ) -> str:
        """Capture budget calculation errors"""
        
        additional_context = {
            "budget_category": budget_category,
            "calculation_type": calculation_type,
            "financial_accuracy_impact": True
        }
        
        return self.capture_financial_error(
            exception=exception,
            category=FinancialErrorCategory.BUDGET_CALCULATION,
            severity=FinancialSeverity.HIGH,
            user_id=user_id,
            request=request,
            additional_context=additional_context
        )
    
    @contextmanager
    def performance_monitoring(
        self,
        operation_name: str,
        operation_type: str = "financial_operation",
        user_id: Optional[str] = None,
        transaction_data: Optional[Dict[str, Any]] = None
    ):
        """Context manager for performance monitoring of financial operations"""
        
        if not self.initialized:
            # Provide a no-op context manager if Sentry is not initialized
            class NoOpContext:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def set_tag(self, key, value):
                    pass
                def set_data(self, key, value):
                    pass
            
            yield NoOpContext()
            return
        
        with start_transaction(
            op=operation_type,
            name=operation_name,
            sampled=True
        ) as transaction:
            
            # Set transaction context
            transaction.set_tag("operation_type", operation_type)
            transaction.set_tag("financial_operation", True)
            
            if user_id:
                transaction.set_tag("user_id", user_id)
            
            if transaction_data:
                for key, value in transaction_data.items():
                    transaction.set_data(key, value)
            
            # Add breadcrumb
            add_breadcrumb(
                message=f"Starting {operation_name}",
                category="performance",
                level="info",
                data={"operation": operation_name, "type": operation_type}
            )
            
            yield transaction
    
    @contextmanager
    def span_monitoring(
        self,
        span_name: str,
        description: Optional[str] = None,
        operation: str = "financial_span"
    ):
        """Context manager for span monitoring within transactions"""
        
        if not self.initialized:
            class NoOpSpan:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def set_tag(self, key, value):
                    pass
                def set_data(self, key, value):
                    pass
            
            yield NoOpSpan()
            return
        
        with start_span(
            op=operation,
            description=description or span_name
        ) as span:
            span.set_tag("span_name", span_name)
            yield span
    
    def add_financial_breadcrumb(
        self,
        message: str,
        category: str = "financial",
        level: str = "info",
        data: Optional[Dict[str, Any]] = None
    ):
        """Add financial-specific breadcrumb"""
        
        if not self.initialized:
            return
        
        breadcrumb_data = data or {}
        breadcrumb_data.update({
            "timestamp": datetime.utcnow().isoformat(),
            "financial_context": True
        })
        
        add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=breadcrumb_data
        )
    
    def set_financial_user_context(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        subscription_tier: Optional[str] = None,
        account_type: Optional[str] = None,
        risk_level: Optional[str] = None
    ):
        """Set comprehensive user context for financial applications"""
        
        if not self.initialized:
            return
        
        user_context = {"id": user_id}
        
        if user_email:
            user_context["email"] = user_email
        if subscription_tier:
            user_context["subscription_tier"] = subscription_tier
        if account_type:
            user_context["account_type"] = account_type
        if risk_level:
            user_context["risk_level"] = risk_level
        
        set_user(user_context)
        
        # Set additional financial tags
        set_tag("has_user_context", True)
        if subscription_tier:
            set_tag("subscription_tier", subscription_tier)
        if account_type:
            set_tag("account_type", account_type)
        if risk_level:
            set_tag("risk_level", risk_level)
    
    def _set_request_context(self, scope, request: Request):
        """Set comprehensive request context"""
        
        # Basic request info (filtered for security)
        request_context = {
            "url": str(request.url.replace(query=None)),  # Remove query params
            "method": request.method,
            "endpoint": request.url.path,
            "user_agent": request.headers.get("user-agent", "")[:100],  # Truncate
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", "0")
        }
        
        # Add client IP (if available)
        if "x-forwarded-for" in request.headers:
            request_context["client_ip"] = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            request_context["client_ip"] = request.headers["x-real-ip"]
        
        scope.set_context("request", request_context)
        
        # Set request tags
        scope.set_tag("endpoint", request.url.path)
        scope.set_tag("method", request.method)
        scope.set_tag("has_request_context", True)
    
    def capture_performance_issue(
        self,
        operation_name: str,
        duration_ms: float,
        threshold_ms: float,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Capture performance issues that exceed thresholds"""
        
        if not self.initialized:
            return ""
        
        with push_scope() as scope:
            scope.set_tag("performance_issue", True)
            scope.set_tag("operation", operation_name)
            scope.set_tag("exceeded_threshold", True)
            
            if user_id:
                scope.set_user({"id": user_id})
            
            # Performance context
            perf_context = {
                "operation": operation_name,
                "duration_ms": duration_ms,
                "threshold_ms": threshold_ms,
                "slowdown_factor": duration_ms / threshold_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            scope.set_context("performance", perf_context)
            
            if additional_context:
                for key, value in additional_context.items():
                    scope.set_extra(key, value)
            
            # Create a message for the performance issue
            message = (
                f"Performance threshold exceeded: {operation_name} "
                f"took {duration_ms:.2f}ms (threshold: {threshold_ms:.2f}ms)"
            )
            
            event_id = capture_message(message, level="warning")
            
            logger.warning(
                f"Performance issue captured [Sentry: {event_id}] - "
                f"{message}, User: {user_id}"
            )
            
            return event_id or ""


# Global instance
sentry_service = SentryFinancialService()


# Convenience functions for common use cases
def capture_financial_error(exception: Exception, **kwargs) -> str:
    """Convenience function to capture financial errors"""
    return sentry_service.capture_financial_error(exception, **kwargs)


def capture_transaction_error(exception: Exception, **kwargs) -> str:
    """Convenience function to capture transaction errors"""
    return sentry_service.capture_transaction_error(exception, **kwargs)


def capture_authentication_error(exception: Exception, **kwargs) -> str:
    """Convenience function to capture authentication errors"""
    return sentry_service.capture_authentication_error(exception, **kwargs)


def capture_payment_error(exception: Exception, **kwargs) -> str:
    """Convenience function to capture payment errors"""
    return sentry_service.capture_payment_error(exception, **kwargs)


def monitor_financial_performance(operation_name: str, **kwargs):
    """Convenience function for performance monitoring"""
    return sentry_service.performance_monitoring(operation_name, **kwargs)


def add_financial_breadcrumb(message: str, **kwargs):
    """Convenience function to add financial breadcrumbs"""
    return sentry_service.add_financial_breadcrumb(message, **kwargs)


def set_financial_user(user_id: str, **kwargs):
    """Convenience function to set financial user context"""
    return sentry_service.set_financial_user_context(user_id, **kwargs)