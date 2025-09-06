"""
Comprehensive Performance Monitoring Service with Sentry Integration
Monitors API performance, database queries, and financial operations
"""

import time
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum

import sentry_sdk
from sentry_sdk import start_transaction, start_span
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .sentry_service import sentry_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class PerformanceCategory(Enum):
    """Performance monitoring categories"""
    API_REQUEST = "api_request"
    DATABASE_QUERY = "database_query"
    EXTERNAL_API = "external_api"
    FINANCIAL_CALCULATION = "financial_calculation"
    AUTHENTICATION = "authentication"
    FILE_PROCESSING = "file_processing"
    CACHE_OPERATION = "cache_operation"
    BUSINESS_LOGIC = "business_logic"


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    operation_name: str
    category: PerformanceCategory
    duration_ms: float
    timestamp: datetime
    success: bool
    user_id: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['category'] = self.category.value
        return data


class PerformanceThresholds:
    """Performance threshold configurations for financial operations"""
    
    # API endpoint thresholds (milliseconds)
    API_THRESHOLDS = {
        'GET': 500,          # Read operations
        'POST': 1000,        # Create operations
        'PUT': 800,          # Update operations
        'DELETE': 600,       # Delete operations
        'PATCH': 700,        # Partial updates
    }
    
    # Specific endpoint thresholds
    ENDPOINT_THRESHOLDS = {
        '/api/auth/login': 1500,           # Authentication can be slower
        '/api/auth/register': 2000,        # Registration includes validation
        '/api/transactions': 800,          # Financial data should be fast
        '/api/financial/analysis': 3000,   # Complex analysis can take longer
        '/api/budget/calculate': 2000,     # Budget calculations
        '/api/users/profile': 400,         # Profile data should be instant
    }
    
    # Database operation thresholds
    DATABASE_THRESHOLDS = {
        'SELECT': 200,       # Read queries
        'INSERT': 300,       # Insert operations
        'UPDATE': 400,       # Update operations
        'DELETE': 250,       # Delete operations
    }
    
    # Financial operation thresholds
    FINANCIAL_THRESHOLDS = {
        'transaction_processing': 1000,
        'budget_calculation': 2000,
        'financial_analysis': 5000,
        'payment_processing': 1500,
        'account_balance': 300,
    }
    
    @classmethod
    def get_api_threshold(cls, method: str, endpoint: str) -> float:
        """Get threshold for API endpoint"""
        # Check specific endpoint first
        if endpoint in cls.ENDPOINT_THRESHOLDS:
            return cls.ENDPOINT_THRESHOLDS[endpoint]
        
        # Fall back to method-based threshold
        return cls.API_THRESHOLDS.get(method.upper(), 1000)
    
    @classmethod
    def get_database_threshold(cls, operation: str) -> float:
        """Get threshold for database operation"""
        return cls.DATABASE_THRESHOLDS.get(operation.upper(), 300)
    
    @classmethod
    def get_financial_threshold(cls, operation: str) -> float:
        """Get threshold for financial operation"""
        return cls.FINANCIAL_THRESHOLDS.get(operation, 2000)


class PerformanceMonitorService:
    """Comprehensive performance monitoring service"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.thresholds = PerformanceThresholds()
        self.max_metrics = 10000  # Keep last 10k metrics in memory
        self.alert_cooldown: Dict[str, datetime] = {}
        self.alert_cooldown_minutes = 15  # Don't spam alerts
    
    @asynccontextmanager
    async def monitor_api_request(
        self,
        request: Request,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Monitor API request performance"""
        operation_name = f"{request.method} {request.url.path}"
        start_time = time.time()
        
        # Start Sentry transaction
        transaction = sentry_sdk.start_transaction(
            op="http.server",
            name=operation_name,
            sampled=True
        )
        
        transaction.set_tag("method", request.method)
        transaction.set_tag("endpoint", request.url.path)
        transaction.set_tag("financial_api", True)
        
        if user_id:
            transaction.set_tag("user_id", user_id)
        
        success = True
        error: Optional[Exception] = None
        
        try:
            yield transaction
            
        except Exception as e:
            success = False
            error = e
            transaction.set_tag("error", True)
            transaction.set_data("error_message", str(e))
            raise
            
        finally:
            duration_ms = (time.time() - start_time) * 1000
            transaction.set_data("duration_ms", duration_ms)
            transaction.finish()
            
            # Record metric
            await self._record_metric(
                PerformanceMetric(
                    operation_name=operation_name,
                    category=PerformanceCategory.API_REQUEST,
                    duration_ms=duration_ms,
                    timestamp=datetime.now(),
                    success=success,
                    user_id=user_id,
                    additional_context=additional_context
                )
            )
            
            # Check threshold and alert if needed
            threshold = self.thresholds.get_api_threshold(
                request.method, 
                request.url.path
            )
            
            if duration_ms > threshold:
                await self._handle_performance_alert(
                    operation_name=operation_name,
                    duration_ms=duration_ms,
                    threshold=threshold,
                    category=PerformanceCategory.API_REQUEST,
                    user_id=user_id,
                    additional_context={
                        'method': request.method,
                        'endpoint': request.url.path,
                        'success': success,
                        'error': str(error) if error else None,
                        **(additional_context or {})
                    }
                )
    
    @asynccontextmanager
    async def monitor_database_operation(
        self,
        operation: str,
        table: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Monitor database operation performance"""
        operation_name = f"DB {operation}"
        if table:
            operation_name += f" {table}"
        
        start_time = time.time()
        
        # Start Sentry span
        with start_span(op="db.query", description=operation_name) as span:
            span.set_tag("db.operation", operation)
            if table:
                span.set_tag("db.table", table)
            span.set_tag("financial_db", True)
            
            if user_id:
                span.set_tag("user_id", user_id)
            
            success = True
            error: Optional[Exception] = None
            
            try:
                yield span
                
            except Exception as e:
                success = False
                error = e
                span.set_tag("error", True)
                span.set_data("error_message", str(e))
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_data("duration_ms", duration_ms)
                
                # Record metric
                await self._record_metric(
                    PerformanceMetric(
                        operation_name=operation_name,
                        category=PerformanceCategory.DATABASE_QUERY,
                        duration_ms=duration_ms,
                        timestamp=datetime.now(),
                        success=success,
                        user_id=user_id,
                        additional_context=additional_context
                    )
                )
                
                # Check threshold
                threshold = self.thresholds.get_database_threshold(operation)
                if duration_ms > threshold:
                    await self._handle_performance_alert(
                        operation_name=operation_name,
                        duration_ms=duration_ms,
                        threshold=threshold,
                        category=PerformanceCategory.DATABASE_QUERY,
                        user_id=user_id,
                        additional_context={
                            'operation': operation,
                            'table': table,
                            'success': success,
                            'error': str(error) if error else None,
                            **(additional_context or {})
                        }
                    )
    
    @asynccontextmanager
    async def monitor_financial_operation(
        self,
        operation_name: str,
        user_id: str,
        transaction_id: Optional[str] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Monitor financial operation performance"""
        start_time = time.time()
        
        # Start Sentry transaction for financial operations
        transaction = sentry_sdk.start_transaction(
            op="financial.operation",
            name=operation_name,
            sampled=True
        )
        
        transaction.set_tag("financial_operation", True)
        transaction.set_tag("user_id", user_id)
        transaction.set_tag("compliance_monitored", True)
        
        if transaction_id:
            transaction.set_tag("transaction_id", transaction_id)
        if amount is not None:
            transaction.set_data("amount", amount)
        if currency:
            transaction.set_tag("currency", currency)
        
        success = True
        error: Optional[Exception] = None
        
        try:
            yield transaction
            
        except Exception as e:
            success = False
            error = e
            transaction.set_tag("error", True)
            transaction.set_data("error_message", str(e))
            
            # Capture financial error
            await sentry_service.capture_financial_error(
                exception=e,
                category=sentry_service.FinancialErrorCategory.FINANCIAL_ANALYSIS,
                severity=sentry_service.FinancialSeverity.HIGH,
                user_id=user_id,
                transaction_id=transaction_id,
                amount=amount,
                currency=currency,
                additional_context={
                    'operation_name': operation_name,
                    'performance_monitoring': True,
                    **(additional_context or {})
                }
            )
            raise
            
        finally:
            duration_ms = (time.time() - start_time) * 1000
            transaction.set_data("duration_ms", duration_ms)
            transaction.finish()
            
            # Record metric
            await self._record_metric(
                PerformanceMetric(
                    operation_name=operation_name,
                    category=PerformanceCategory.FINANCIAL_CALCULATION,
                    duration_ms=duration_ms,
                    timestamp=datetime.now(),
                    success=success,
                    user_id=user_id,
                    additional_context={
                        'transaction_id': transaction_id,
                        'amount': amount,
                        'currency': currency,
                        **(additional_context or {})
                    }
                )
            )
            
            # Check financial operation threshold
            threshold = self.thresholds.get_financial_threshold(operation_name)
            if duration_ms > threshold:
                await self._handle_performance_alert(
                    operation_name=operation_name,
                    duration_ms=duration_ms,
                    threshold=threshold,
                    category=PerformanceCategory.FINANCIAL_CALCULATION,
                    user_id=user_id,
                    additional_context={
                        'transaction_id': transaction_id,
                        'amount': amount,
                        'currency': currency,
                        'financial_impact': 'HIGH',
                        'success': success,
                        'error': str(error) if error else None,
                        **(additional_context or {})
                    }
                )
    
    async def _record_metric(self, metric: PerformanceMetric):
        """Record performance metric"""
        self.metrics.append(metric)
        
        # Trim metrics list if too large
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics:]
        
        # Log slow operations
        if metric.category == PerformanceCategory.API_REQUEST and metric.duration_ms > 1000:
            logger.warning(
                f"Slow API request: {metric.operation_name} took {metric.duration_ms:.2f}ms"
            )
        elif metric.category == PerformanceCategory.DATABASE_QUERY and metric.duration_ms > 500:
            logger.warning(
                f"Slow database query: {metric.operation_name} took {metric.duration_ms:.2f}ms"
            )
        elif metric.category == PerformanceCategory.FINANCIAL_CALCULATION and metric.duration_ms > 2000:
            logger.warning(
                f"Slow financial operation: {metric.operation_name} took {metric.duration_ms:.2f}ms"
            )
    
    async def _handle_performance_alert(
        self,
        operation_name: str,
        duration_ms: float,
        threshold: float,
        category: PerformanceCategory,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Handle performance threshold breach"""
        
        # Check alert cooldown
        alert_key = f"{category.value}:{operation_name}"
        now = datetime.now()
        
        if alert_key in self.alert_cooldown:
            last_alert = self.alert_cooldown[alert_key]
            if now - last_alert < timedelta(minutes=self.alert_cooldown_minutes):
                return  # Still in cooldown
        
        self.alert_cooldown[alert_key] = now
        
        # Capture performance issue in Sentry
        event_id = await sentry_service.capture_performance_issue(
            operation_name=operation_name,
            duration_ms=duration_ms,
            threshold_ms=threshold,
            user_id=user_id,
            additional_context={
                'category': category.value,
                'performance_threshold_exceeded': True,
                'slowdown_factor': duration_ms / threshold,
                **(additional_context or {})
            }
        )
        
        logger.warning(
            f"Performance threshold exceeded [Sentry: {event_id}] - "
            f"{operation_name} took {duration_ms:.2f}ms (threshold: {threshold:.2f}ms)"
        )
    
    def get_performance_summary(
        self, 
        last_hours: int = 1,
        category: Optional[PerformanceCategory] = None
    ) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        
        cutoff_time = datetime.now() - timedelta(hours=last_hours)
        
        # Filter metrics
        filtered_metrics = [
            m for m in self.metrics 
            if m.timestamp > cutoff_time and
            (category is None or m.category == category)
        ]
        
        if not filtered_metrics:
            return {
                'total_operations': 0,
                'avg_duration_ms': 0,
                'max_duration_ms': 0,
                'min_duration_ms': 0,
                'success_rate': 100.0,
                'threshold_breaches': 0,
            }
        
        # Calculate statistics
        durations = [m.duration_ms for m in filtered_metrics]
        successful_ops = [m for m in filtered_metrics if m.success]
        
        # Count threshold breaches
        threshold_breaches = 0
        for metric in filtered_metrics:
            if metric.category == PerformanceCategory.API_REQUEST:
                # Need to extract method and endpoint from operation_name
                parts = metric.operation_name.split(' ', 1)
                if len(parts) == 2:
                    method, endpoint = parts
                    threshold = self.thresholds.get_api_threshold(method, endpoint)
                    if metric.duration_ms > threshold:
                        threshold_breaches += 1
        
        return {
            'total_operations': len(filtered_metrics),
            'avg_duration_ms': sum(durations) / len(durations),
            'max_duration_ms': max(durations),
            'min_duration_ms': min(durations),
            'success_rate': (len(successful_ops) / len(filtered_metrics)) * 100,
            'threshold_breaches': threshold_breaches,
            'operations_by_category': self._group_by_category(filtered_metrics),
            'slowest_operations': self._get_slowest_operations(filtered_metrics, limit=10)
        }
    
    def _group_by_category(self, metrics: List[PerformanceMetric]) -> Dict[str, int]:
        """Group metrics by category"""
        categories = {}
        for metric in metrics:
            category = metric.category.value
            categories[category] = categories.get(category, 0) + 1
        return categories
    
    def _get_slowest_operations(
        self, 
        metrics: List[PerformanceMetric], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get the slowest operations"""
        sorted_metrics = sorted(metrics, key=lambda m: m.duration_ms, reverse=True)
        return [
            {
                'operation_name': m.operation_name,
                'duration_ms': m.duration_ms,
                'category': m.category.value,
                'timestamp': m.timestamp.isoformat(),
                'success': m.success,
                'user_id': m.user_id
            }
            for m in sorted_metrics[:limit]
        ]


# Global performance monitor instance
performance_monitor = PerformanceMonitorService()


# Convenience functions
async def monitor_api_request(request: Request, user_id: Optional[str] = None, **kwargs):
    """Convenience function for API request monitoring"""
    return performance_monitor.monitor_api_request(request, user_id, **kwargs)


async def monitor_database_operation(operation: str, **kwargs):
    """Convenience function for database operation monitoring"""
    return performance_monitor.monitor_database_operation(operation, **kwargs)


async def monitor_financial_operation(operation_name: str, user_id: str, **kwargs):
    """Convenience function for financial operation monitoring"""
    return performance_monitor.monitor_financial_operation(operation_name, user_id, **kwargs)


def get_performance_summary(**kwargs) -> Dict[str, Any]:
    """Convenience function to get performance summary"""
    return performance_monitor.get_performance_summary(**kwargs)