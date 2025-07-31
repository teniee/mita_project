"""
Health Check API Routes
Provides health monitoring for external services and circuit breakers
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
import logging

from app.core.circuit_breaker import get_circuit_breaker_manager
from app.services.resilient_gpt_service import get_gpt_service
from app.services.resilient_google_auth_service import get_google_auth_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health():
    """Get overall system health status"""
    try:
        circuit_breaker_manager = get_circuit_breaker_manager()
        health_summary = circuit_breaker_manager.get_health_summary()
        
        # Get individual service health
        services_health = {}
        
        # Check GPT service health (if configured)
        try:
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                gpt_service = get_gpt_service(settings.OPENAI_API_KEY)
                services_health['gpt_service'] = await gpt_service.get_service_health()
            else:
                services_health['gpt_service'] = {
                    'status': 'not_configured',
                    'message': 'OpenAI API key not configured'
                }
        except Exception as e:
            logger.error(f"Error checking GPT service health: {str(e)}")
            services_health['gpt_service'] = {
                'status': 'error',
                'message': str(e)
            }
        
        # Check Google Auth service health
        try:
            google_auth_service = get_google_auth_service()
            services_health['google_auth_service'] = await google_auth_service.get_service_health()
        except Exception as e:
            logger.error(f"Error checking Google Auth service health: {str(e)}")
            services_health['google_auth_service'] = {
                'status': 'error',
                'message': str(e)
            }
        
        return {
            'status': health_summary['overall_health'],
            'timestamp': '2024-01-01T00:00:00Z',  # Use actual timestamp in production
            'circuit_breakers': health_summary,
            'services': services_health,
            'message': _get_health_message(health_summary['overall_health'])
        }
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check service unavailable"
        )


@router.get("/health/detailed", response_model=Dict[str, Any])
async def get_detailed_health():
    """Get detailed health information including circuit breaker statistics"""
    try:
        circuit_breaker_manager = get_circuit_breaker_manager()
        
        return {
            'timestamp': '2024-01-01T00:00:00Z',  # Use actual timestamp in production
            'circuit_breakers': circuit_breaker_manager.get_all_stats(),
            'health_summary': circuit_breaker_manager.get_health_summary(),
        }
        
    except Exception as e:
        logger.error(f"Error in detailed health check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detailed health check service unavailable"
        )


@router.get("/health/circuit-breakers", response_model=Dict[str, Any])
async def get_circuit_breaker_status():
    """Get status of all circuit breakers"""
    try:
        circuit_breaker_manager = get_circuit_breaker_manager()
        all_stats = circuit_breaker_manager.get_all_stats()
        
        # Format for easy monitoring
        formatted_stats = {}
        for service_name, stats in all_stats.items():
            formatted_stats[service_name] = {
                'state': stats['state'],
                'health': 'healthy' if stats['state'] == 'closed' else 'degraded' if stats['state'] == 'half_open' else 'unhealthy',
                'success_rate': stats['success_rate'],
                'total_requests': stats['total_requests'],
                'consecutive_failures': stats['consecutive_failures'],
                'last_state_change': stats['state_changed_at']
            }
        
        return {
            'circuit_breakers': formatted_stats,
            'summary': circuit_breaker_manager.get_health_summary()
        }
        
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Circuit breaker status unavailable"
        )


@router.post("/health/circuit-breakers/{service_name}/reset")
async def reset_circuit_breaker(service_name: str):
    """Reset a specific circuit breaker (admin operation)"""
    try:
        circuit_breaker_manager = get_circuit_breaker_manager()
        circuit_breaker = circuit_breaker_manager.get_circuit_breaker(service_name)
        
        # Reset the circuit breaker state
        circuit_breaker.state = circuit_breaker.state.__class__.CLOSED
        circuit_breaker.stats.consecutive_failures = 0
        circuit_breaker.stats.consecutive_successes = 0
        
        logger.info(f"Circuit breaker '{service_name}' manually reset")
        
        return {
            'message': f"Circuit breaker '{service_name}' has been reset",
            'new_state': 'closed',
            'timestamp': '2024-01-01T00:00:00Z'  # Use actual timestamp in production
        }
        
    except Exception as e:
        logger.error(f"Error resetting circuit breaker {service_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset circuit breaker '{service_name}'"
        )


@router.get("/health/services/test-connections")
async def test_external_connections():
    """Test connections to external services"""
    results = {}
    
    # Test GPT service connection
    try:
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            gpt_service = get_gpt_service(settings.OPENAI_API_KEY)
            results['openai'] = {
                'connected': await gpt_service.test_connection(),
                'service': 'OpenAI GPT'
            }
        else:
            results['openai'] = {
                'connected': False,
                'service': 'OpenAI GPT',
                'message': 'API key not configured'
            }
    except Exception as e:
        results['openai'] = {
            'connected': False,
            'service': 'OpenAI GPT',
            'error': str(e)
        }
    
    # Test Google OAuth connection
    try:
        google_auth_service = get_google_auth_service()
        results['google_oauth'] = {
            'connected': await google_auth_service.test_connection(),
            'service': 'Google OAuth'
        }
    except Exception as e:
        results['google_oauth'] = {
            'connected': False,
            'service': 'Google OAuth',
            'error': str(e)
        }
    
    # Calculate overall connectivity
    connected_services = sum(1 for result in results.values() if result.get('connected', False))
    total_services = len(results)
    
    return {
        'services': results,
        'summary': {
            'connected_services': connected_services,
            'total_services': total_services,
            'connectivity_rate': (connected_services / total_services * 100) if total_services > 0 else 0,
            'overall_status': 'healthy' if connected_services == total_services else 'degraded' if connected_services > 0 else 'unhealthy'
        }
    }


def _get_health_message(health_status: str) -> str:
    """Get human-readable health message"""
    messages = {
        'healthy': 'All systems operational',
        'degraded': 'Some services experiencing issues but system is functional',
        'critical': 'Multiple services are down, system functionality may be impacted'
    }
    return messages.get(health_status, 'Unknown health status')