"""
Prometheus Metrics Configuration for MITA Finance API
Provides comprehensive monitoring metrics for production observability
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import psutil
import os

# ============================================================================
# HTTP Metrics
# ============================================================================

http_requests_total = Counter(
    'mita_http_requests_total',
    'Total HTTP requests by method, endpoint, and status code',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'mita_http_request_duration_seconds',
    'HTTP request latency in seconds by method and endpoint',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf'))
)

http_requests_in_progress = Gauge(
    'mita_http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method', 'endpoint']
)

# ============================================================================
# Business Metrics
# ============================================================================

budget_calculations_total = Counter(
    'mita_budget_calculations_total',
    'Total number of budget redistribution calculations performed'
)

budget_calculation_duration_seconds = Histogram(
    'mita_budget_calculation_duration_seconds',
    'Budget calculation processing time in seconds',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf'))
)

ocr_processing_total = Counter(
    'mita_ocr_processing_total',
    'Total number of OCR processing requests',
    ['status']  # success, failure
)

ocr_processing_duration_seconds = Histogram(
    'mita_ocr_processing_duration_seconds',
    'OCR processing time in seconds',
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, float('inf'))
)

transaction_amount_usd = Histogram(
    'mita_transaction_amount_usd',
    'Transaction amounts in USD',
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000, float('inf'))
)

active_users_gauge = Gauge(
    'mita_active_users',
    'Number of currently active users (authenticated in last 5 minutes)'
)

# ============================================================================
# Database Metrics
# ============================================================================

database_connections_active = Gauge(
    'mita_database_connections_active',
    'Number of active database connections'
)

database_connections_max = Gauge(
    'mita_database_connections_max',
    'Maximum number of database connections allowed'
)

database_query_duration_seconds = Histogram(
    'mita_database_query_duration_seconds',
    'Database query execution time',
    ['query_type', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf'))
)

database_errors_total = Counter(
    'mita_database_errors_total',
    'Total number of database errors',
    ['error_type']
)

# ============================================================================
# External Service Metrics
# ============================================================================

external_api_requests_total = Counter(
    'mita_external_api_requests_total',
    'Total requests to external APIs',
    ['service', 'status']  # service: openai, google_vision, etc.; status: success, failure
)

external_api_duration_seconds = Histogram(
    'mita_external_api_duration_seconds',
    'External API request duration',
    ['service'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float('inf'))
)

circuit_breaker_state = Gauge(
    'mita_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)

# ============================================================================
# System Metrics
# ============================================================================

system_cpu_usage_percent = Gauge(
    'mita_system_cpu_usage_percent',
    'System CPU usage percentage'
)

system_memory_usage_percent = Gauge(
    'mita_system_memory_usage_percent',
    'System memory usage percentage'
)

system_memory_available_bytes = Gauge(
    'mita_system_memory_available_bytes',
    'Available system memory in bytes'
)

# ============================================================================
# Application Info
# ============================================================================

app_info = Info(
    'mita_application',
    'MITA Finance application information'
)

# Set application info
app_info.info({
    'version': '1.0.0',
    'environment': os.getenv('ENVIRONMENT', 'unknown'),
    'service': 'mita-finance-api'
})

# ============================================================================
# Prometheus Middleware
# ============================================================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically collect HTTP metrics for all requests
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == '/metrics':
            return await call_next(request)

        # Normalize endpoint path (remove IDs for better grouping)
        endpoint = self._normalize_path(request.url.path)
        method = request.method

        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Start timer
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            return response
        except Exception as e:
            # Track errors
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by replacing UUIDs and IDs with placeholders
        Examples:
          /api/goals/123e4567-e89b-12d3-a456-426614174000 -> /api/goals/{id}
          /api/users/42 -> /api/users/{id}
        """
        import re

        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path, flags=re.IGNORECASE)

        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)

        return path

# ============================================================================
# System Metrics Collector
# ============================================================================

def update_system_metrics():
    """
    Update system resource metrics
    Should be called periodically (e.g., every 15 seconds)
    """
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        system_cpu_usage_percent.set(cpu_percent)

        # Memory usage
        memory = psutil.virtual_memory()
        system_memory_usage_percent.set(memory.percent)
        system_memory_available_bytes.set(memory.available)

    except Exception as e:
        # Silently fail - don't crash app if metrics collection fails
        pass

# ============================================================================
# Metrics Export
# ============================================================================

def get_metrics() -> bytes:
    """
    Generate Prometheus metrics in exposition format
    """
    # Update system metrics before export
    update_system_metrics()

    return generate_latest(REGISTRY)
