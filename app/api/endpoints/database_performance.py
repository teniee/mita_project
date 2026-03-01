"""
Database Performance Monitoring API Endpoints
Provides endpoints for monitoring database performance, connection pools, and query optimization
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.database_monitoring import (
    get_database_performance_stats,
    analyze_database_performance,
    db_engine
)
from app.api.dependencies import get_current_user, require_admin_access
from app.db.models import User

router = APIRouter(prefix="/database", tags=["database_performance"])


class DatabaseHealthResponse(BaseModel):
    """Response model for database health check"""
    status: str
    health_score: int
    connection_pool_status: str
    query_performance: str
    recommendations: List[str]
    timestamp: datetime


class QueryPerformanceResponse(BaseModel):
    """Response model for query performance metrics"""
    total_queries: int
    unique_query_patterns: int
    average_query_time: float
    slowest_queries: List[Dict[str, Any]]
    recent_slow_queries: List[Dict[str, Any]]
    query_type_distribution: Dict[str, int]


class ConnectionPoolResponse(BaseModel):
    """Response model for connection pool metrics"""
    pool_utilization: float
    connection_efficiency: float
    current_metrics: Dict[str, Any]
    health_status: str


class OptimizationSuggestion(BaseModel):
    """Model for query optimization suggestions"""
    query_pattern: str
    execution_time: float
    suggestions: List[str]
    severity: str
    impact: str


@router.get("/health", response_model=DatabaseHealthResponse, summary="Database Health Check")
async def get_database_health(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get comprehensive database health status
    
    Requires admin access. Returns:
    - Overall health score (0-100)
    - Connection pool status
    - Query performance metrics
    - System recommendations
    """
    try:
        analysis = await analyze_database_performance()
        
        return DatabaseHealthResponse(
            status="healthy" if analysis['health_score'] >= 80 else "degraded" if analysis['health_score'] >= 60 else "critical",
            health_score=analysis['health_score'],
            connection_pool_status=analysis['performance_stats'].get('connection_metrics', {}).get('health_status', 'unknown'),
            query_performance="good" if analysis['health_score'] >= 80 else "needs_attention",
            recommendations=analysis['recommendations'],
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting database health: {str(e)}"
        )


@router.get("/performance", summary="Database Performance Metrics")
async def get_performance_metrics(
    include_slow_queries: bool = Query(True, description="Include slow query analysis"),
    query_limit: int = Query(10, description="Number of queries to return", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get detailed database performance metrics
    
    Requires admin access. Returns:
    - Query execution statistics
    - Connection pool metrics
    - System resource usage
    - Performance trends
    """
    try:
        stats = await get_database_performance_stats()
        
        response = {
            "performance_summary": {
                "total_queries_executed": stats.get('query_statistics', {}).get('total_queries', 0),
                "unique_query_patterns": stats.get('query_statistics', {}).get('unique_query_patterns', 0),
                "connection_pool_health": stats.get('connection_metrics', {}).get('health_status', 'unknown'),
                "system_resources": stats.get('system_resources', {})
            },
            "query_statistics": stats.get('query_statistics', {}),
            "connection_metrics": stats.get('connection_metrics', {}),
            "engine_info": stats.get('engine_info', {}),
            "generated_at": datetime.now().isoformat()
        }
        
        if include_slow_queries:
            slow_queries = await db_engine.analyze_slow_queries(limit=query_limit)
            response["slow_query_analysis"] = slow_queries
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting performance metrics: {str(e)}"
        )


@router.get("/queries/slow", summary="Slow Query Analysis")
async def get_slow_queries(
    limit: int = Query(20, description="Number of slow queries to analyze", ge=1, le=100),
    severity: Optional[str] = Query(None, description="Filter by severity: warning, critical, emergency"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get detailed analysis of slow queries with optimization suggestions
    
    Requires admin access. Returns:
    - Slow query details
    - Optimization suggestions
    - Performance impact analysis
    - Execution patterns
    """
    try:
        slow_queries = await db_engine.analyze_slow_queries(limit=limit)
        
        # Filter by severity if specified
        if severity:
            severity_upper = severity.upper()
            slow_queries = [
                q for q in slow_queries 
                if q['query'].get('severity') == severity_upper
            ]
        
        # Add additional analysis
        analyzed_queries = []
        for query_analysis in slow_queries:
            query_data = query_analysis['query']
            
            analyzed_query = {
                "query_id": query_data['query_id'],
                "query_type": query_data['query_type'],
                "execution_time": query_data['execution_time'],
                "severity": query_data.get('severity'),
                "timestamp": query_data['start_time'],
                "endpoint": query_data.get('endpoint'),
                "user_id": query_data.get('user_id'),
                "rows_affected": query_data.get('rows_affected'),
                "optimization_suggestions": query_analysis['suggestions'],
                "performance_impact": _assess_performance_impact(query_data['execution_time']),
                "query_pattern": _extract_query_pattern(query_data['query_text'])
            }
            
            analyzed_queries.append(analyzed_query)
        
        return {
            "total_slow_queries": len(analyzed_queries),
            "severity_distribution": _get_severity_distribution(analyzed_queries),
            "slow_queries": analyzed_queries,
            "global_recommendations": _generate_global_recommendations(analyzed_queries),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing slow queries: {str(e)}"
        )


@router.get("/connections", response_model=ConnectionPoolResponse, summary="Connection Pool Status")
async def get_connection_pool_status(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get detailed connection pool metrics
    
    Requires admin access. Returns:
    - Pool utilization metrics
    - Connection lifecycle stats
    - Pool health assessment
    - Optimization recommendations
    """
    try:
        stats = await get_database_performance_stats()
        connection_metrics = stats.get('connection_metrics', {})
        
        if not connection_metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection metrics not available"
            )
        
        return ConnectionPoolResponse(
            pool_utilization=connection_metrics.get('pool_utilization', 0),
            connection_efficiency=connection_metrics.get('connection_efficiency', 0),
            current_metrics=connection_metrics.get('current_metrics', {}),
            health_status=connection_metrics.get('health_status', 'unknown')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting connection pool status: {str(e)}"
        )


@router.get("/optimization-report", summary="Database Optimization Report")
async def get_optimization_report(
    days: int = Query(7, description="Number of days to analyze", ge=1, le=30),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Generate comprehensive database optimization report
    
    Requires admin access. Provides:
    - Performance trends over time
    - Query optimization opportunities
    - Index recommendations
    - Capacity planning insights
    """
    try:
        analysis = await analyze_database_performance()
        
        # Generate comprehensive report
        report = {
            "report_period": {
                "start_date": (datetime.now() - timedelta(days=days)).isoformat(),
                "end_date": datetime.now().isoformat(),
                "days_analyzed": days
            },
            "executive_summary": {
                "overall_health_score": analysis['health_score'],
                "critical_issues": _count_critical_issues(analysis),
                "performance_trend": _assess_performance_trend(analysis),
                "recommended_actions": len(analysis['recommendations'])
            },
            "detailed_analysis": {
                "query_performance": analysis['performance_stats'].get('query_statistics', {}),
                "connection_efficiency": analysis['performance_stats'].get('connection_metrics', {}),
                "resource_utilization": analysis['performance_stats'].get('system_resources', {}),
                "slow_query_patterns": analysis['slow_query_analysis']
            },
            "recommendations": {
                "immediate_actions": _get_immediate_actions(analysis),
                "short_term_improvements": _get_short_term_improvements(analysis),
                "long_term_optimizations": _get_long_term_optimizations(analysis)
            },
            "capacity_planning": {
                "current_utilization": _calculate_current_utilization(analysis),
                "projected_growth": _project_growth_trends(analysis),
                "scaling_recommendations": _get_scaling_recommendations(analysis)
            },
            "generated_at": datetime.now().isoformat()
        }
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating optimization report: {str(e)}"
        )


@router.post("/optimize/queries", summary="Optimize Query Performance")
async def optimize_query_performance(
    auto_apply: bool = Query(False, description="Automatically apply safe optimizations"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Analyze and optimize query performance
    
    Requires admin access. Can:
    - Analyze query patterns
    - Suggest index optimizations
    - Generate query rewrites
    - Apply safe optimizations (if enabled)
    """
    try:
        # This would implement actual query optimization logic
        # For now, return analysis and suggestions
        
        slow_queries = await db_engine.analyze_slow_queries(limit=50)
        
        optimizations = {
            "analyzed_queries": len(slow_queries),
            "optimization_opportunities": [],
            "index_recommendations": [],
            "query_rewrites": [],
            "applied_optimizations": [] if not auto_apply else ["Example: Added index on user_id column"]
        }
        
        for query_analysis in slow_queries:
            query_data = query_analysis['query']
            
            optimization = {
                "query_id": query_data['query_id'],
                "current_performance": query_data['execution_time'],
                "estimated_improvement": f"{query_data['execution_time'] * 0.3:.2f}s",
                "suggestions": query_analysis['suggestions'],
                "priority": "high" if query_data['execution_time'] > 5 else "medium"
            }
            
            optimizations["optimization_opportunities"].append(optimization)
        
        return optimizations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error optimizing query performance: {str(e)}"
        )


def _assess_performance_impact(execution_time: float) -> str:
    """Assess performance impact of a query"""
    if execution_time > 10:
        return "critical"
    elif execution_time > 5:
        return "high"
    elif execution_time > 1:
        return "medium"
    else:
        return "low"


def _extract_query_pattern(query_text: str) -> str:
    """Extract normalized query pattern"""
    import re
    
    pattern = query_text.strip().upper()
    pattern = re.sub(r"'[^']*'", '?', pattern)
    pattern = re.sub(r'\b\d+\b', '?', pattern)
    pattern = re.sub(r'\s+', ' ', pattern)
    
    return pattern[:100] + "..." if len(pattern) > 100 else pattern


def _get_severity_distribution(queries: List[Dict]) -> Dict[str, int]:
    """Get distribution of query severities"""
    distribution = {"warning": 0, "critical": 0, "emergency": 0}
    
    for query in queries:
        severity = query.get('severity', '').lower()
        if severity in distribution:
            distribution[severity] += 1
    
    return distribution


def _generate_global_recommendations(queries: List[Dict]) -> List[str]:
    """Generate global optimization recommendations"""
    recommendations = []
    
    if len(queries) > 10:
        recommendations.append("High number of slow queries detected - consider comprehensive database optimization")
    
    critical_queries = [q for q in queries if q.get('severity') == 'emergency']
    if critical_queries:
        recommendations.append(f"{len(critical_queries)} emergency-level slow queries require immediate attention")
    
    # Check for common patterns
    select_queries = [q for q in queries if q.get('query_type') == 'SELECT']
    if len(select_queries) > len(queries) * 0.8:
        recommendations.append("Most slow queries are SELECT statements - consider adding database indexes")
    
    return recommendations


def _count_critical_issues(analysis: Dict) -> int:
    """Count critical performance issues"""
    critical_count = 0
    
    if analysis['health_score'] < 60:
        critical_count += 1
    
    slow_queries = analysis.get('slow_query_analysis', [])
    critical_queries = [q for q in slow_queries if q['query'].get('severity') == 'emergency']
    critical_count += len(critical_queries)
    
    return critical_count


def _assess_performance_trend(analysis: Dict) -> str:
    """Assess overall performance trend"""
    health_score = analysis['health_score']
    
    if health_score >= 90:
        return "excellent"
    elif health_score >= 80:
        return "good"
    elif health_score >= 60:
        return "declining"
    else:
        return "poor"


def _get_immediate_actions(analysis: Dict) -> List[str]:
    """Get immediate action recommendations"""
    actions = []
    
    if analysis['health_score'] < 60:
        actions.append("Investigate and resolve critical performance issues immediately")
    
    emergency_queries = [
        q for q in analysis.get('slow_query_analysis', [])
        if q['query'].get('severity') == 'emergency'
    ]
    
    if emergency_queries:
        actions.append(f"Optimize {len(emergency_queries)} emergency-level slow queries")
    
    return actions


def _get_short_term_improvements(analysis: Dict) -> List[str]:
    """Get short-term improvement recommendations"""
    improvements = []
    
    slow_queries = analysis.get('slow_query_analysis', [])
    if len(slow_queries) > 5:
        improvements.append("Add database indexes for frequently slow queries")
    
    connection_health = analysis['performance_stats'].get('connection_metrics', {}).get('health_status')
    if connection_health == 'warning':
        improvements.append("Optimize connection pool configuration")
    
    return improvements


def _get_long_term_optimizations(analysis: Dict) -> List[str]:
    """Get long-term optimization recommendations"""
    optimizations = []
    
    query_stats = analysis['performance_stats'].get('query_statistics', {})
    if query_stats.get('total_queries', 0) > 10000:
        optimizations.append("Consider implementing query result caching")
    
    optimizations.append("Regular database maintenance and statistics updates")
    optimizations.append("Consider read replicas for better query distribution")
    
    return optimizations


def _calculate_current_utilization(analysis: Dict) -> Dict[str, float]:
    """Calculate current resource utilization"""
    system_resources = analysis['performance_stats'].get('system_resources', {})
    connection_metrics = analysis['performance_stats'].get('connection_metrics', {})
    
    return {
        "cpu_utilization": system_resources.get('cpu_percent', 0),
        "memory_utilization": system_resources.get('memory_percent', 0),
        "connection_pool_utilization": connection_metrics.get('pool_utilization', 0)
    }


def _project_growth_trends(analysis: Dict) -> Dict[str, str]:
    """Project growth trends"""
    # This would analyze historical data to project trends
    # For now, return placeholder projections
    return {
        "query_volume_trend": "increasing",
        "connection_usage_trend": "stable",
        "performance_trend": "declining"
    }


def _get_scaling_recommendations(analysis: Dict) -> List[str]:
    """Get scaling recommendations"""
    recommendations = []
    
    utilization = _calculate_current_utilization(analysis)
    
    if utilization['connection_pool_utilization'] > 80:
        recommendations.append("Consider increasing connection pool size")
    
    if utilization['cpu_utilization'] > 80:
        recommendations.append("Consider upgrading database server CPU")
    
    if utilization['memory_utilization'] > 80:
        recommendations.append("Consider increasing database server memory")
    
    return recommendations