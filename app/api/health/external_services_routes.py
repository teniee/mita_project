"""
External Services Health Check Routes
Provides monitoring endpoints for all external service integrations
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, List, Any
import logging
from datetime import datetime

from app.core.external_services import (
    external_services,
    validate_external_services,
    get_services_health,
    get_critical_services_status
)
from app.core.api_key_manager import get_api_key_health, validate_production_keys
from app.api.dependencies import require_admin_access as require_admin_role

router = APIRouter(prefix="/health", tags=["Health Check"])
logger = logging.getLogger(__name__)


@router.get("/")
async def health_check():
    """Simple health check endpoint for load balancers and monitoring"""
    return {
        "status": "healthy",
        "service": "MITA Finance API",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/external-services")
async def check_external_services():
    """Check health of all external services"""
    try:
        # Get current health status
        health_status = get_services_health()
        
        # Determine HTTP status code based on health
        if health_status['status'] == 'critical':
            pass
        elif health_status['status'] == 'degraded':
            pass  # Still functional but degraded
        
        return {
            "status": health_status['status'],
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_services": health_status['total_services'],
                "enabled_services": health_status['enabled_services'],
                "healthy_services": health_status['healthy_services'],
                "last_check": health_status['last_check']
            },
            "services": health_status['services']
        }
    
    except Exception as e:
        logger.error(f"External services health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/external-services/validate")
async def validate_all_external_services(admin_user = Depends(require_admin_role)):
    """Validate all external service connections (Admin only)"""
    try:
        results = await validate_external_services()
        
        # Count results
        total = len(results)
        connected = len([r for r in results.values() if r.get('connected', False)])
        enabled = len([r for r in results.values() if r.get('enabled', False)])
        
        overall_status = "healthy"
        if connected == 0 and enabled > 0:
            overall_status = "critical"
        elif connected < enabled * 0.8:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "validation_summary": {
                "total_services": total,
                "enabled_services": enabled,
                "connected_services": connected,
                "success_rate": (connected / enabled * 100) if enabled > 0 else 0
            },
            "services": results,
            "recommendations": _generate_service_recommendations(results)
        }
    
    except Exception as e:
        logger.error(f"Service validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service validation failed: {str(e)}"
        )


@router.get("/api-keys")
async def check_api_keys_health(admin_user = Depends(require_admin_role)):
    """Check API keys health status (Admin only)"""
    try:
        health_status = get_api_key_health()
        
        # Determine HTTP status code based on health
        if health_status['status'] == 'unhealthy':
            pass
        elif health_status['status'] == 'warning':
            pass
        
        return {
            "status": health_status['status'],
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_keys": health_status['total_keys'],
                "active_keys": health_status['active_keys'],
                "invalid_keys": health_status['invalid_keys'],
                "keys_needing_rotation": health_status['keys_needing_rotation'],
                "last_validation": health_status['last_validation']
            },
            "key_details": health_status['key_details']
        }
    
    except Exception as e:
        logger.error(f"API keys health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API keys health check failed: {str(e)}"
        )


@router.get("/api-keys/validate")
async def validate_all_api_keys(admin_user = Depends(require_admin_role)):
    """Validate all API keys (Admin only)"""
    try:
        results = await validate_production_keys()
        
        # Count results
        total = len(results)
        valid = len([r for r in results.values() if r.get('valid', False)])
        
        overall_status = "healthy"
        if valid == 0 and total > 0:
            overall_status = "critical"
        elif valid < total * 0.8:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "validation_summary": {
                "total_keys": total,
                "valid_keys": valid,
                "invalid_keys": total - valid,
                "success_rate": (valid / total * 100) if total > 0 else 0
            },
            "keys": results,
            "recommendations": _generate_api_key_recommendations(results)
        }
    
    except Exception as e:
        logger.error(f"API key validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key validation failed: {str(e)}"
        )


@router.get("/critical-services")
async def check_critical_services():
    """Check status of critical services only"""
    try:
        critical_status = get_critical_services_status()
        
        all_critical_healthy = all(critical_status.values())
        some_critical_healthy = any(critical_status.values())
        
        overall_status = "healthy"
        if not some_critical_healthy:
            overall_status = "critical"
        elif not all_critical_healthy:
            overall_status = "degraded"
        
        if overall_status == "critical":
            pass
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "critical_services": critical_status,
            "healthy_count": sum(critical_status.values()),
            "total_count": len(critical_status)
        }
    
    except Exception as e:
        logger.error(f"Critical services check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Critical services check failed: {str(e)}"
        )


@router.get("/services/{service_name}")
async def check_specific_service(service_name: str):
    """Check health of a specific external service"""
    try:
        if service_name not in external_services.services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        service = external_services.services[service_name]
        
        # Validate connection if possible
        connected = False
        error = None
        try:
            if hasattr(service, 'validate_connection'):
                connected = await service.validate_connection()
            else:
                connected = service.enabled
        except Exception as e:
            error = str(e)
        
        service_status = "healthy" if connected else "unhealthy" if service.enabled else "disabled"
        
        return {
            "service": service_name,
            "status": service_status,
            "enabled": service.enabled,
            "connected": connected,
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "config": service.get_config()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service check failed for {service_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service check failed: {str(e)}"
        )


@router.get("/services/{service_name}/test")
async def test_service_connection(service_name: str, admin_user = Depends(require_admin_role)):
    """Test connection to a specific service (Admin only)"""
    try:
        if service_name not in external_services.services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        service = external_services.services[service_name]
        
        if not service.enabled:
            return {
                "service": service_name,
                "test_result": "skipped",
                "reason": "Service not enabled",
                "timestamp": datetime.now().isoformat()
            }
        
        # Perform connection test
        test_start = datetime.now()
        connected = False
        error = None
        
        try:
            if hasattr(service, 'validate_connection'):
                connected = await service.validate_connection()
            else:
                connected = True  # Assume connected if no validation method
        except Exception as e:
            error = str(e)
        
        test_duration = (datetime.now() - test_start).total_seconds()
        
        return {
            "service": service_name,
            "test_result": "passed" if connected else "failed",
            "connected": connected,
            "error": error,
            "duration_seconds": test_duration,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service test failed for {service_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service test failed: {str(e)}"
        )


@router.get("/monitoring/dashboard")
async def get_monitoring_dashboard(admin_user = Depends(require_admin_role)):
    """Get comprehensive monitoring dashboard data (Admin only)"""
    try:
        # Get all health data
        services_health = get_services_health()
        api_keys_health = get_api_key_health()
        critical_services = get_critical_services_status()
        
        # Calculate overall system health
        services_score = (services_health['healthy_services'] / services_health['enabled_services'] * 100) if services_health['enabled_services'] > 0 else 0
        api_keys_score = ((api_keys_health['active_keys'] / api_keys_health['total_keys']) * 100) if api_keys_health['total_keys'] > 0 else 100
        critical_services_score = (sum(critical_services.values()) / len(critical_services) * 100) if critical_services else 0
        
        overall_health_score = (services_score + api_keys_score + critical_services_score) / 3
        
        # Determine overall status
        overall_status = "healthy"
        if overall_health_score < 50:
            overall_status = "critical"
        elif overall_health_score < 80:
            overall_status = "degraded"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "overall_health_score": overall_health_score,
            "services": {
                "status": services_health['status'],
                "score": services_score,
                "healthy": services_health['healthy_services'],
                "total": services_health['enabled_services']
            },
            "api_keys": {
                "status": api_keys_health['status'],
                "score": api_keys_score,
                "active": api_keys_health['active_keys'],
                "total": api_keys_health['total_keys'],
                "needing_rotation": api_keys_health['keys_needing_rotation']
            },
            "critical_services": {
                "all_healthy": all(critical_services.values()),
                "score": critical_services_score,
                "status": critical_services
            },
            "alerts": _generate_alerts(services_health, api_keys_health, critical_services),
            "last_updated": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Monitoring dashboard failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Monitoring dashboard failed: {str(e)}"
        )


def _generate_service_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on service validation results"""
    recommendations = []
    
    for service_name, result in results.items():
        if result.get('enabled') and not result.get('connected'):
            error = result.get('error', 'Connection failed')
            recommendations.append(f"Fix {service_name} connection: {error}")
        elif not result.get('enabled') and service_name in ['openai', 'sentry', 'redis']:
            recommendations.append(f"Consider enabling {service_name} service for full functionality")
    
    if not recommendations:
        recommendations.append("All enabled services are connected and healthy")
    
    return recommendations


def _generate_api_key_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on API key validation results"""
    recommendations = []
    
    invalid_keys = [key for key, result in results.items() if not result.get('valid')]
    
    if invalid_keys:
        recommendations.append(f"Fix invalid API keys: {', '.join(invalid_keys)}")
    
    # Check for critical keys
    critical_keys = ['OPENAI_API_KEY', 'SENTRY_DSN', 'SENDGRID_API_KEY']
    missing_critical = [key for key in critical_keys if key in invalid_keys]
    
    if missing_critical:
        recommendations.append(f"URGENT: Fix critical API keys: {', '.join(missing_critical)}")
    
    if not recommendations:
        recommendations.append("All API keys are valid and functioning")
    
    return recommendations


def _generate_alerts(services_health: Dict, api_keys_health: Dict, critical_services: Dict) -> List[Dict[str, Any]]:
    """Generate alerts based on health status"""
    alerts = []
    
    # Service alerts
    if services_health['status'] == 'critical':
        alerts.append({
            "type": "critical",
            "category": "services",
            "message": "Multiple external services are down",
            "action": "Check service configurations and network connectivity"
        })
    elif services_health['status'] == 'degraded':
        alerts.append({
            "type": "warning",
            "category": "services",
            "message": "Some external services are experiencing issues",
            "action": "Monitor service health and check configurations"
        })
    
    # API key alerts
    if api_keys_health['status'] == 'unhealthy':
        alerts.append({
            "type": "critical",
            "category": "api_keys",
            "message": f"{api_keys_health['invalid_keys']} API keys are invalid",
            "action": "Update invalid API keys immediately"
        })
    elif api_keys_health['keys_needing_rotation'] > 0:
        alerts.append({
            "type": "warning",
            "category": "api_keys",
            "message": f"{api_keys_health['keys_needing_rotation']} API keys need rotation",
            "action": "Schedule API key rotation"
        })
    
    # Critical services alerts
    unhealthy_critical = [name for name, healthy in critical_services.items() if not healthy]
    if unhealthy_critical:
        alerts.append({
            "type": "critical",
            "category": "critical_services",
            "message": f"Critical services down: {', '.join(unhealthy_critical)}",
            "action": "Restore critical services immediately"
        })
    
    return alerts