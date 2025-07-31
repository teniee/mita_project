"""
Circuit Breaker Pattern Implementation for External APIs
Provides resilient error handling, retry logic, and fail-fast mechanisms
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional, Union
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 3          # Successes needed to close circuit
    timeout_duration: int = 60          # Seconds to wait before half-open
    max_retry_attempts: int = 3         # Max retries per request
    retry_backoff_factor: float = 2.0   # Exponential backoff multiplier
    timeout_seconds: float = 30.0       # Request timeout
    
    # Exception types that trigger circuit breaker
    trigger_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        OSError,
    )


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_at: datetime = field(default_factory=datetime.now)
    total_state_changes: int = 0


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._check_state()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if exc_type is None:
            await self._record_success()
        elif isinstance(exc_val, self.config.trigger_exceptions):
            await self._record_failure()
        return False  # Don't suppress exceptions
    
    async def _check_state(self):
        """Check current state and update if necessary"""
        async with self._lock:
            now = datetime.now()
            
            if self.state == CircuitBreakerState.OPEN:
                time_since_open = (now - self.stats.state_changed_at).total_seconds()
                if time_since_open >= self.config.timeout_duration:
                    self._change_state(CircuitBreakerState.HALF_OPEN)
                    logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Will retry in {self.config.timeout_duration - time_since_open:.1f} seconds"
                    )
    
    async def _record_success(self):
        """Record a successful request"""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = datetime.now()
            
            # Transition from HALF_OPEN to CLOSED after enough successes
            if (self.state == CircuitBreakerState.HALF_OPEN and 
                self.stats.consecutive_successes >= self.config.success_threshold):
                self._change_state(CircuitBreakerState.CLOSED)
                logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED")
    
    async def _record_failure(self):
        """Record a failed request"""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()
            
            # Transition to OPEN if failure threshold exceeded
            if (self.state in [CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN] and
                self.stats.consecutive_failures >= self.config.failure_threshold):
                self._change_state(CircuitBreakerState.OPEN)
                logger.warning(f"Circuit breaker '{self.name}' transitioned to OPEN after {self.stats.consecutive_failures} failures")
    
    def _change_state(self, new_state: CircuitBreakerState):
        """Change circuit breaker state"""
        old_state = self.state
        self.state = new_state
        self.stats.state_changed_at = datetime.now()
        self.stats.total_state_changes += 1
        
        logger.info(f"Circuit breaker '{self.name}' state changed: {old_state.value} → {new_state.value}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self:
            # Implement retry logic with exponential backoff
            last_exception = None
            
            for attempt in range(self.config.max_retry_attempts):
                try:
                    # Set timeout for the operation
                    if asyncio.iscoroutinefunction(func):
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=self.config.timeout_seconds
                        )
                    else:
                        result = func(*args, **kwargs)
                    
                    return result
                    
                except self.config.trigger_exceptions as e:
                    last_exception = e
                    if attempt < self.config.max_retry_attempts - 1:
                        delay = self.config.retry_backoff_factor ** attempt
                        logger.warning(
                            f"Circuit breaker '{self.name}' attempt {attempt + 1} failed: {str(e)}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Circuit breaker '{self.name}' all {self.config.max_retry_attempts} attempts failed")
                        raise
                except Exception as e:
                    # Non-triggering exceptions are re-raised immediately
                    logger.error(f"Circuit breaker '{self.name}' non-retriable error: {str(e)}")
                    raise
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            'name': self.name,
            'state': self.state.value,
            'total_requests': self.stats.total_requests,
            'successful_requests': self.stats.successful_requests,
            'failed_requests': self.stats.failed_requests,
            'success_rate': (
                self.stats.successful_requests / max(self.stats.total_requests, 1) * 100
            ),
            'consecutive_failures': self.stats.consecutive_failures,
            'consecutive_successes': self.stats.consecutive_successes,
            'last_failure_time': self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            'last_success_time': self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
            'state_changed_at': self.stats.state_changed_at.isoformat(),
            'total_state_changes': self.stats.total_state_changes,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'success_threshold': self.config.success_threshold,
                'timeout_duration': self.config.timeout_duration,
                'max_retry_attempts': self.config.max_retry_attempts,
                'timeout_seconds': self.config.timeout_seconds,
            }
        }


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different services"""
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._configs: Dict[str, CircuitBreakerConfig] = {}
    
    def register_service(self, name: str, config: CircuitBreakerConfig = None):
        """Register a service with circuit breaker protection"""
        if name not in self._circuit_breakers:
            config = config or CircuitBreakerConfig()
            self._circuit_breakers[name] = CircuitBreaker(name, config)
            self._configs[name] = config
            logger.info(f"Registered circuit breaker for service: {name}")
    
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get circuit breaker for a service"""
        if name not in self._circuit_breakers:
            self.register_service(name)
        return self._circuit_breakers[name]
    
    @asynccontextmanager
    async def protect(self, service_name: str):
        """Context manager for protected service calls"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        async with circuit_breaker:
            yield circuit_breaker
    
    async def call_service(self, service_name: str, func: Callable, *args, **kwargs) -> Any:
        """Call a service function with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        total_services = len(self._circuit_breakers)
        healthy_services = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.state == CircuitBreakerState.CLOSED
        )
        degraded_services = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.state == CircuitBreakerState.HALF_OPEN
        )
        failed_services = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.state == CircuitBreakerState.OPEN
        )
        
        return {
            'total_services': total_services,
            'healthy_services': healthy_services,
            'degraded_services': degraded_services,
            'failed_services': failed_services,
            'overall_health': 'healthy' if failed_services == 0 else ('degraded' if degraded_services > 0 else 'critical'),
            'health_percentage': (healthy_services / max(total_services, 1)) * 100
        }


# Global circuit breaker manager
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None

def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get singleton circuit breaker manager"""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
        
        # Pre-register common services with appropriate configurations
        _circuit_breaker_manager.register_service(
            'openai',
            CircuitBreakerConfig(
                failure_threshold=3,
                timeout_duration=120,  # OpenAI can be slow
                timeout_seconds=60.0,
                max_retry_attempts=2,
                trigger_exceptions=(
                    ConnectionError, TimeoutError, OSError,
                    Exception  # Catch OpenAI API errors too
                )
            )
        )
        
        _circuit_breaker_manager.register_service(
            'google_oauth',
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout_duration=60,
                timeout_seconds=10.0,
                max_retry_attempts=3
            )
        )
        
        _circuit_breaker_manager.register_service(
            'external_api',
            CircuitBreakerConfig(
                failure_threshold=4,
                timeout_duration=90,
                timeout_seconds=30.0,
                max_retry_attempts=2
            )
        )
        
    return _circuit_breaker_manager