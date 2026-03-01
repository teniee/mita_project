"""
Enhanced Health Check API Routes with Comprehensive Middleware Monitoring
Provides advanced health monitoring to detect issues that could cause 8-15+ second timeouts
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.circuit_breaker import get_circuit_breaker_manager
from app.services.resilient_gpt_service import get_gpt_service
from app.services.resilient_google_auth_service import get_google_auth_service
from app.core.config import settings
from app.core.async_session import get_async_db
from app.core.middleware_health_monitor import middleware_health_monitor, HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/comprehensive", response_model=Dict[str, Any])
async def get_comprehensive_health(session: AsyncSession = Depends(get_async_db)):
    """
    Get comprehensive system health status including middleware validation
    This endpoint is designed to detect issues that could cause 8-15+ second timeouts
    """
    try:
        # Run comprehensive middleware health check
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        # Get circuit breaker health (existing functionality)
        try:
            circuit_breaker_manager = get_circuit_breaker_manager()
            circuit_breaker_health = circuit_breaker_manager.get_health_summary()
        except Exception as e:
            logger.warning(f"Circuit breaker health check failed: {str(e)}")
            circuit_breaker_health = {
                'overall_health': 'degraded',
                'error': str(e)
            }
        
        # Get individual service health (existing functionality)
        external_services_health = {}
        
        # Check GPT service health (if configured)
        try:
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                gpt_service = get_gpt_service(settings.OPENAI_API_KEY)
                external_services_health['gpt_service'] = await gpt_service.get_service_health()
            else:
                external_services_health['gpt_service'] = {
                    'status': 'not_configured',
                    'message': 'OpenAI API key not configured'
                }
        except Exception as e:
            logger.error(f"Error checking GPT service health: {str(e)}")
            external_services_health['gpt_service'] = {
                'status': 'error',
                'message': str(e)
            }
        
        # Check Google Auth service health
        try:
            google_auth_service = get_google_auth_service()
            external_services_health['google_auth_service'] = await google_auth_service.get_service_health()
        except Exception as e:
            logger.error(f"Error checking Google Auth service health: {str(e)}")
            external_services_health['google_auth_service'] = {
                'status': 'error',
                'message': str(e)
            }
        
        # Determine overall system health
        health_components = [
            middleware_report.overall_status.value,
            circuit_breaker_health['overall_health'],
            *[svc['status'] for svc in external_services_health.values()]
        ]
        
        if 'unhealthy' in health_components or 'error' in health_components:
            overall_status = 'unhealthy'
        elif 'critical' in health_components:
            overall_status = 'critical'
        elif 'degraded' in health_components or 'not_configured' in health_components:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'
        
        # Prepare middleware metrics for response
        middleware_metrics = {}
        for name, metric in middleware_report.metrics.items():
            middleware_metrics[name] = {
                'status': metric.status.value,
                'message': metric.message,
                'response_time_ms': metric.response_time_ms,
                'value': metric.value,
                'threshold_warning': metric.threshold_warning,
                'threshold_critical': metric.threshold_critical
            }
        
        response = {
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'middleware': {
                'overall_status': middleware_report.overall_status.value,
                'metrics': middleware_metrics,
                'performance_summary': middleware_report.performance_summary,
                'response_time_ms': middleware_report.response_time_ms
            },
            'circuit_breakers': circuit_breaker_health,
            'external_services': external_services_health,
            'alerts': middleware_report.alerts,
            'issues_detected': middleware_report.issues_detected,
            'recommendations': middleware_report.recommendations,
            'message': _get_comprehensive_health_message(overall_status, middleware_report)
        }
        
        # Return appropriate HTTP status based on health
        if overall_status == 'unhealthy':
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response
            )
        elif overall_status == 'critical':
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in comprehensive health check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'status': 'unhealthy',
                'message': 'Health check system failure',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/middleware", response_model=Dict[str, Any])
async def get_middleware_health(session: AsyncSession = Depends(get_async_db)):
    """Get detailed middleware health status"""
    try:
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        # Prepare detailed middleware metrics
        detailed_metrics = {}
        for name, metric in middleware_report.metrics.items():
            detailed_metrics[name] = {
                'status': metric.status.value,
                'message': metric.message,
                'value': metric.value,
                'response_time_ms': metric.response_time_ms,
                'threshold_warning': metric.threshold_warning,
                'threshold_critical': metric.threshold_critical,
                'timestamp': metric.timestamp.isoformat(),
                'details': metric.details
            }
        
        response = {
            'overall_status': middleware_report.overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': detailed_metrics,
            'performance_summary': middleware_report.performance_summary,
            'response_time_ms': middleware_report.response_time_ms,
            'alerts': middleware_report.alerts,
            'issues_detected': middleware_report.issues_detected,
            'recommendations': middleware_report.recommendations
        }
        
        # Return appropriate HTTP status
        if middleware_report.overall_status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in middleware health check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'Middleware health check failed',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/middleware/{component}", response_model=Dict[str, Any])
async def get_component_health(
    component: str, 
    session: AsyncSession = Depends(get_async_db)
):
    """Get health status of a specific middleware component"""
    try:
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        if component not in middleware_report.metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Middleware component '{component}' not found"
            )
        
        metric = middleware_report.metrics[component]
        
        response = {
            'component': component,
            'status': metric.status.value,
            'message': metric.message,
            'value': metric.value,
            'response_time_ms': metric.response_time_ms,
            'threshold_warning': metric.threshold_warning,
            'threshold_critical': metric.threshold_critical,
            'timestamp': metric.timestamp.isoformat(),
            'details': metric.details
        }
        
        # Return appropriate HTTP status
        if metric.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=response
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking component {component} health: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': f'Component {component} health check failed',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/performance", response_model=Dict[str, Any])
async def get_performance_health(session: AsyncSession = Depends(get_async_db)):
    """Get performance-focused health metrics to detect timeout risks"""
    try:
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        # Extract performance metrics
        performance_metrics = {}
        timeout_risks = []
        
        for name, metric in middleware_report.metrics.items():
            if metric.response_time_ms:
                performance_metrics[name] = {
                    'response_time_ms': metric.response_time_ms,
                    'status': metric.status.value,
                    'threshold_warning': metric.threshold_warning,
                    'threshold_critical': metric.threshold_critical
                }
                
                # Check for timeout risks
                if metric.response_time_ms > 5000:  # 5 seconds
                    timeout_risks.append(f"{name}: {metric.response_time_ms:.1f}ms (CRITICAL - timeout risk)")
                elif metric.response_time_ms > 2000:  # 2 seconds
                    timeout_risks.append(f"{name}: {metric.response_time_ms:.1f}ms (WARNING - approaching timeout)")
        
        # Calculate performance summary
        response_times = [m['response_time_ms'] for m in performance_metrics.values()]
        performance_summary = {
            'total_health_check_time_ms': middleware_report.response_time_ms,
            'component_response_times': performance_metrics,
            'average_response_time_ms': sum(response_times) / len(response_times) if response_times else 0,
            'max_response_time_ms': max(response_times) if response_times else 0,
            'min_response_time_ms': min(response_times) if response_times else 0,
            'components_over_2s': sum(1 for rt in response_times if rt > 2000),
            'components_over_5s': sum(1 for rt in response_times if rt > 5000),
            'timeout_risks': timeout_risks
        }
        
        # Determine performance status
        if performance_summary['components_over_5s'] > 0:
            performance_status = 'critical'
        elif performance_summary['components_over_2s'] > 0:
            performance_status = 'degraded'
        elif performance_summary['max_response_time_ms'] > 1000:
            performance_status = 'warning'
        else:
            performance_status = 'healthy'
        
        response = {
            'performance_status': performance_status,
            'timestamp': datetime.utcnow().isoformat(),
            'performance_summary': performance_summary,
            'alerts': [alert for alert in middleware_report.alerts if 'timeout' in alert.lower() or 'slow' in alert.lower()],
            'recommendations': [rec for rec in middleware_report.recommendations if 'performance' in rec.lower() or 'timeout' in rec.lower()],
            'message': _get_performance_message(performance_status, performance_summary)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error in performance health check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'Performance health check failed',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/history", response_model=Dict[str, Any])
async def get_health_history(
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = Query(None, ge=1, le=168)  # Max 7 days
):
    """Get health check history and trends"""
    try:
        # Get health history
        history = middleware_health_monitor.get_health_history(limit=limit)
        
        # Get trends if hours specified
        trends = None
        if hours:
            trends = middleware_health_monitor.get_health_trends(hours=hours)
        
        # Analyze recent health patterns
        recent_statuses = [report.overall_status.value for report in history[-10:]] if history else []
        recent_response_times = [report.response_time_ms for report in history[-10:]] if history else []
        
        analysis = {
            'total_checks': len(history),
            'recent_status_pattern': recent_statuses,
            'recent_avg_response_time_ms': sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0,
            'recent_max_response_time_ms': max(recent_response_times) if recent_response_times else 0,
            'health_stability': 'stable' if len(set(recent_statuses)) <= 1 else 'unstable',
            'performance_trend': 'improving' if recent_response_times and recent_response_times[0] > recent_response_times[-1] else 'degrading' if recent_response_times and recent_response_times[0] < recent_response_times[-1] else 'stable'
        }
        
        # Format history for response
        formatted_history = []
        for report in history:
            formatted_history.append({
                'timestamp': report.timestamp.isoformat(),
                'overall_status': report.overall_status.value,
                'response_time_ms': report.response_time_ms,
                'alerts_count': len(report.alerts),
                'issues_count': len(report.issues_detected),
                'healthy_components': report.performance_summary.get('healthy_components', 0),
                'total_components': report.performance_summary.get('components_checked', 0)
            })
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'history': formatted_history,
            'analysis': analysis,
            'trends': trends,
            'monitoring_duration': {
                'start_time': middleware_health_monitor.start_time.isoformat(),
                'duration_hours': (datetime.utcnow() - middleware_health_monitor.start_time).total_seconds() / 3600
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving health history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'Health history retrieval failed',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/alerts", response_model=Dict[str, Any])
async def get_current_alerts(session: AsyncSession = Depends(get_async_db)):
    """Get current health alerts and critical issues"""
    try:
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        # Categorize alerts by severity
        critical_alerts = []
        warning_alerts = []
        info_alerts = []
        
        for alert in middleware_report.alerts:
            if 'CRITICAL' in alert.upper():
                critical_alerts.append(alert)
            elif 'WARNING' in alert.upper():
                warning_alerts.append(alert)
            else:
                info_alerts.append(alert)
        
        # Get component-specific issues
        component_issues = {}
        for name, metric in middleware_report.metrics.items():
            if metric.status in [HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]:
                component_issues[name] = {
                    'status': metric.status.value,
                    'message': metric.message,
                    'response_time_ms': metric.response_time_ms
                }
        
        alert_summary = {
            'total_alerts': len(middleware_report.alerts),
            'critical_alerts': critical_alerts,
            'warning_alerts': warning_alerts,
            'info_alerts': info_alerts,
            'component_issues': component_issues,
            'issues_detected': middleware_report.issues_detected,
            'recommendations': middleware_report.recommendations,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Determine alert level
        if critical_alerts or component_issues:
            alert_level = 'critical'
        elif warning_alerts:
            alert_level = 'warning'
        elif info_alerts:
            alert_level = 'info'
        else:
            alert_level = 'none'
        
        return {
            'alert_level': alert_level,
            'alert_summary': alert_summary,
            'requires_immediate_attention': bool(critical_alerts or component_issues),
            'message': f"Alert level: {alert_level.upper()}. {len(middleware_report.alerts)} total alerts."
        }
        
    except Exception as e:
        logger.error(f"Error retrieving current alerts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'error': 'Alert retrieval failed',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        )


@router.get("/health/metrics", response_model=Dict[str, Any])
async def get_health_metrics(session: AsyncSession = Depends(get_async_db)):
    """Get health metrics in Prometheus format for monitoring integration"""
    try:
        middleware_report = await middleware_health_monitor.run_comprehensive_middleware_health_check(session)
        
        # Convert to Prometheus format
        metrics = []
        
        # Overall health (1 = healthy, 0.75 = degraded, 0.5 = critical, 0 = unhealthy)
        health_value = {
            "healthy": 1.0,
            "degraded": 0.75,
            "critical": 0.5,
            "unhealthy": 0.0
        }.get(middleware_report.overall_status.value, 0.0)
        
        metrics.append(f"mita_middleware_health_status {health_value}")
        
        # Component-specific metrics
        for name, metric in middleware_report.metrics.items():
            component_value = {
                "healthy": 1.0,
                "degraded": 0.75,
                "critical": 0.5,
                "unhealthy": 0.0
            }.get(metric.status.value, 0.0)
            
            metrics.append(f'mita_middleware_component_health{{component="{name}"}} {component_value}')
            
            # Response time metrics
            if metric.response_time_ms is not None:
                metrics.append(f'mita_middleware_component_response_time_ms{{component="{name}"}} {metric.response_time_ms}')
            
            # Value metrics (if available)
            if metric.value is not None:
                metrics.append(f'mita_middleware_component_value{{component="{name}"}} {metric.value}')
        
        # Performance summary metrics
        perf = middleware_report.performance_summary
        if 'healthy_components' in perf:
            metrics.append(f"mita_middleware_healthy_components {perf['healthy_components']}")
        if 'total_services' in perf:
            metrics.append(f"mita_middleware_total_components {perf['components_checked']}")
        
        # Alert metrics
        metrics.append(f"mita_middleware_alerts_count {len(middleware_report.alerts)}")
        metrics.append(f"mita_middleware_issues_count {len(middleware_report.issues_detected)}")
        
        # Overall response time
        metrics.append(f"mita_middleware_health_check_duration_ms {middleware_report.response_time_ms}")
        
        return {
            'metrics': "\n".join(metrics),
            'timestamp': datetime.utcnow().isoformat(),
            'format': 'prometheus',
            'total_metrics': len(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error generating health metrics: {str(e)}", exc_info=True)
        return {
            'metrics': "mita_middleware_health_status 0\nmita_middleware_metrics_error 1",
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'format': 'prometheus'
        }


def _get_comprehensive_health_message(overall_status: str, middleware_report) -> str:
    """Get comprehensive health message including middleware status"""
    base_messages = {
        'healthy': 'All systems operational',
        'degraded': 'Some services experiencing issues but system is functional',
        'critical': 'Critical issues detected, system functionality may be impacted',
        'unhealthy': 'System is unhealthy, multiple services are down'
    }
    
    base_message = base_messages.get(overall_status, 'Unknown health status')
    
    if middleware_report.alerts:
        return f"{base_message}. Middleware alerts: {len(middleware_report.alerts)} active."
    elif middleware_report.issues_detected:
        return f"{base_message}. {len(middleware_report.issues_detected)} middleware issues detected."
    else:
        return f"{base_message}. All middleware components healthy."


def _get_performance_message(performance_status: str, performance_summary: Dict[str, Any]) -> str:
    """Get performance-specific health message"""
    if performance_status == 'critical':
        return f"CRITICAL: {performance_summary['components_over_5s']} components exceed 5-second response time - timeout risk high"
    elif performance_status == 'degraded':
        return f"DEGRADED: {performance_summary['components_over_2s']} components exceed 2-second response time - monitor closely"
    elif performance_status == 'warning':
        return f"WARNING: Maximum component response time is {performance_summary['max_response_time_ms']:.1f}ms"
    else:
        return f"HEALTHY: All components responding within acceptable thresholds (max: {performance_summary['max_response_time_ms']:.1f}ms)"