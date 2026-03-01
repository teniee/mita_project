"""
Cache Management API Endpoints
Provides endpoints for cache monitoring, statistics, and management
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.caching import (
    get_cache_statistics,
    check_cache_health,
    cache_manager,
    warm_up_cache,
    invalidate_user_cache,
    invalidate_table_cache
)
from app.api.dependencies import get_current_user, require_admin_access
from app.db.models import User

router = APIRouter(prefix="/cache", tags=["cache_management"])


class CacheHealthResponse(BaseModel):
    """Response model for cache health check"""
    health_status: Dict[str, str]
    statistics: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime


class CacheStatisticsResponse(BaseModel):
    """Response model for cache statistics"""
    memory_cache: Dict[str, Any]
    redis_cache: Dict[str, Any]
    hit_ratios: Dict[str, float]
    hit_stats: Dict[str, int]
    timestamp: str


class CacheInvalidationRequest(BaseModel):
    """Request model for cache invalidation"""
    tags: Optional[List[str]] = Field(None, description="Tags to invalidate")
    user_id: Optional[str] = Field(None, description="User ID to invalidate")
    table_name: Optional[str] = Field(None, description="Table name to invalidate")
    keys: Optional[List[str]] = Field(None, description="Specific keys to invalidate")


@router.get("/health", response_model=CacheHealthResponse, summary="Cache System Health Check")
async def get_cache_health(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get comprehensive cache system health status
    
    Requires admin access. Returns:
    - Memory cache status and utilization
    - Redis cache connectivity and performance
    - Hit ratios and performance metrics
    - Optimization recommendations
    """
    try:
        health_data = await check_cache_health()
        
        return CacheHealthResponse(
            health_status=health_data['health_status'],
            statistics=health_data['statistics'],
            recommendations=health_data['recommendations'],
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking cache health: {str(e)}"
        )


@router.get("/statistics", response_model=CacheStatisticsResponse, summary="Cache Performance Statistics")
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get detailed cache performance statistics
    
    Requires admin access. Returns:
    - Memory cache utilization and performance
    - Redis cache metrics
    - Hit/miss ratios across cache tiers
    - Performance trends
    """
    try:
        stats = await get_cache_statistics()
        
        return CacheStatisticsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache statistics: {str(e)}"
        )


@router.get("/performance", summary="Cache Performance Metrics")
async def get_cache_performance_metrics(
    include_detailed: bool = Query(False, description="Include detailed performance metrics"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get cache performance metrics and analysis
    
    Requires admin access. Provides:
    - Cache hit/miss patterns
    - Performance bottlenecks
    - Memory utilization trends
    - Optimization opportunities
    """
    try:
        stats = await get_cache_statistics()
        hit_ratios = cache_manager.get_hit_ratio()
        
        performance_metrics = {
            "cache_efficiency": {
                "total_hit_ratio": hit_ratios['total'],
                "memory_hit_ratio": hit_ratios['memory'],
                "redis_hit_ratio": hit_ratios['redis'],
                "performance_grade": _calculate_performance_grade(hit_ratios['total'])
            },
            "utilization_metrics": {
                "memory_utilization": stats['memory_cache'].get('utilization', 0),
                "memory_entries": stats['memory_cache'].get('entries', 0),
                "redis_connected": stats['redis_cache'].get('connected', False)
            },
            "performance_indicators": {
                "cache_effectiveness": "high" if hit_ratios['total'] > 70 else "medium" if hit_ratios['total'] > 40 else "low",
                "memory_pressure": "high" if stats['memory_cache'].get('utilization', 0) > 80 else "normal",
                "redis_health": "healthy" if stats['redis_cache'].get('connected', False) else "degraded"
            }
        }
        
        if include_detailed:
            performance_metrics["detailed_stats"] = stats
            performance_metrics["optimization_suggestions"] = _generate_optimization_suggestions(stats, hit_ratios)
        
        return performance_metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache performance metrics: {str(e)}"
        )


@router.post("/warm-up", summary="Warm Up Cache")
async def warm_up_cache_endpoint(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Warm up cache with frequently accessed data
    
    Requires admin access. Pre-loads commonly used data into cache
    to improve initial response times after cache clears or application restarts.
    """
    try:
        await warm_up_cache()
        
        return {
            "status": "success",
            "message": "Cache warm-up completed successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error warming up cache: {str(e)}"
        )


@router.post("/invalidate", summary="Invalidate Cache Entries")
async def invalidate_cache(
    request: CacheInvalidationRequest,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Invalidate specific cache entries
    
    Requires admin access. Can invalidate cache by:
    - Tags (e.g., 'user', 'transaction')
    - User ID (all user-related cache)
    - Table name (all table-related cache)
    - Specific cache keys
    """
    try:
        invalidated_count = 0
        operations = []
        
        # Invalidate by tags
        if request.tags:
            await cache_manager.clear_by_tags(request.tags)
            operations.append(f"Cleared cache for tags: {', '.join(request.tags)}")
            invalidated_count += len(request.tags)
        
        # Invalidate by user ID
        if request.user_id:
            await invalidate_user_cache(request.user_id)
            operations.append(f"Cleared cache for user: {request.user_id}")
            invalidated_count += 1
        
        # Invalidate by table name
        if request.table_name:
            await invalidate_table_cache(request.table_name)
            operations.append(f"Cleared cache for table: {request.table_name}")
            invalidated_count += 1
        
        # Invalidate specific keys
        if request.keys:
            for key in request.keys:
                await cache_manager.delete(key)
            operations.append(f"Cleared specific keys: {', '.join(request.keys)}")
            invalidated_count += len(request.keys)
        
        if invalidated_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No invalidation criteria provided"
            )
        
        return {
            "status": "success",
            "operations_performed": operations,
            "estimated_entries_invalidated": invalidated_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error invalidating cache: {str(e)}"
        )


@router.post("/clear", summary="Clear All Cache")
async def clear_all_cache(
    confirm: bool = Query(False, description="Confirmation required to clear all cache"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Clear all cache entries across all tiers
    
    Requires admin access and explicit confirmation.
    WARNING: This will clear all cached data and may impact performance
    until cache is rebuilt.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required. Set confirm=true to proceed with clearing all cache."
        )
    
    try:
        # Clear memory cache
        cache_manager.memory_cache.cache.clear()
        cache_manager.memory_cache.access_order.clear()
        
        # Clear Redis cache (if available)
        if cache_manager.redis_cache.redis_client:
            await cache_manager.redis_cache.redis_client.flushdb()
        
        # Reset hit statistics
        cache_manager.hit_stats = {
            'memory_hits': 0,
            'redis_hits': 0,
            'misses': 0
        }
        
        return {
            "status": "success",
            "message": "All cache entries cleared successfully",
            "warning": "Cache performance may be impacted until data is cached again",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {str(e)}"
        )


@router.get("/top-keys", summary="Get Most Accessed Cache Keys")
async def get_top_cache_keys(
    limit: int = Query(20, description="Number of top keys to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get most frequently accessed cache keys
    
    Requires admin access. Returns cache keys sorted by access frequency
    to help identify hot data and optimization opportunities.
    """
    try:
        # Get top keys from memory cache
        memory_entries = []
        for key, entry in cache_manager.memory_cache.cache.items():
            memory_entries.append({
                "key": key,
                "access_count": entry.access_count,
                "size_bytes": entry.size_bytes,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
                "tags": entry.tags
            })
        
        # Sort by access count
        memory_entries.sort(key=lambda x: x['access_count'], reverse=True)
        top_keys = memory_entries[:limit]
        
        return {
            "top_cache_keys": top_keys,
            "total_keys_analyzed": len(memory_entries),
            "analysis": {
                "most_accessed_key": top_keys[0]["key"] if top_keys else None,
                "highest_access_count": top_keys[0]["access_count"] if top_keys else 0,
                "total_size_top_keys": sum(entry["size_bytes"] for entry in top_keys),
                "avg_access_count": sum(entry["access_count"] for entry in top_keys) / len(top_keys) if top_keys else 0
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting top cache keys: {str(e)}"
        )


@router.get("/optimization-report", summary="Cache Optimization Report")
async def get_cache_optimization_report(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Generate comprehensive cache optimization report
    
    Requires admin access. Provides detailed analysis and recommendations
    for improving cache performance and efficiency.
    """
    try:
        stats = await get_cache_statistics()
        hit_ratios = cache_manager.get_hit_ratio()
        health_data = await check_cache_health()
        
        # Generate optimization report
        report = {
            "executive_summary": {
                "overall_health": health_data['health_status']['overall'],
                "total_hit_ratio": hit_ratios['total'],
                "performance_grade": _calculate_performance_grade(hit_ratios['total']),
                "primary_concerns": _identify_primary_concerns(stats, hit_ratios)
            },
            "performance_analysis": {
                "hit_ratio_breakdown": hit_ratios,
                "cache_utilization": {
                    "memory_utilization": stats['memory_cache'].get('utilization', 0),
                    "redis_connectivity": stats['redis_cache'].get('connected', False)
                },
                "efficiency_metrics": {
                    "cache_effectiveness": hit_ratios['total'],
                    "memory_efficiency": _calculate_memory_efficiency(stats),
                    "tier_distribution": _calculate_tier_distribution(cache_manager.hit_stats)
                }
            },
            "optimization_recommendations": {
                "immediate_actions": _get_immediate_optimization_actions(stats, hit_ratios),
                "configuration_tuning": _get_configuration_recommendations(stats),
                "architectural_improvements": _get_architectural_recommendations(stats, hit_ratios)
            },
            "capacity_planning": {
                "current_usage": _analyze_current_usage(stats),
                "growth_projections": _project_cache_growth(stats),
                "scaling_recommendations": _get_cache_scaling_recommendations(stats)
            },
            "generated_at": datetime.now().isoformat()
        }
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating cache optimization report: {str(e)}"
        )


def _calculate_performance_grade(hit_ratio: float) -> str:
    """Calculate performance grade based on hit ratio"""
    if hit_ratio >= 90:
        return "A+"
    elif hit_ratio >= 80:
        return "A"
    elif hit_ratio >= 70:
        return "B"
    elif hit_ratio >= 60:
        return "C"
    elif hit_ratio >= 50:
        return "D"
    else:
        return "F"


def _generate_optimization_suggestions(stats: Dict[str, Any], hit_ratios: Dict[str, float]) -> List[str]:
    """Generate cache optimization suggestions"""
    suggestions = []
    
    if hit_ratios['total'] < 50:
        suggestions.append("Consider increasing cache TTL for frequently accessed data")
        suggestions.append("Review caching strategy for key application paths")
    
    memory_util = stats['memory_cache'].get('utilization', 0)
    if memory_util > 80:
        suggestions.append("Increase memory cache size to reduce evictions")
    
    if not stats['redis_cache'].get('connected', False):
        suggestions.append("Fix Redis connectivity for distributed caching benefits")
    
    if hit_ratios['memory'] < 30:
        suggestions.append("Optimize memory cache configuration for better L1 performance")
    
    return suggestions


def _identify_primary_concerns(stats: Dict[str, Any], hit_ratios: Dict[str, float]) -> List[str]:
    """Identify primary cache performance concerns"""
    concerns = []
    
    if hit_ratios['total'] < 40:
        concerns.append("Low overall cache hit ratio")
    
    if stats['memory_cache'].get('utilization', 0) > 90:
        concerns.append("Memory cache near capacity")
    
    if not stats['redis_cache'].get('connected', False):
        concerns.append("Redis cache unavailable")
    
    return concerns


def _calculate_memory_efficiency(stats: Dict[str, Any]) -> float:
    """Calculate memory cache efficiency"""
    memory_stats = stats.get('memory_cache', {})
    utilization = memory_stats.get('utilization', 0)
    entries = memory_stats.get('entries', 0)
    
    if entries == 0:
        return 0.0
    
    # Efficiency based on utilization and entry distribution
    return min(100.0, (utilization * 0.7) + (min(entries / 1000, 1.0) * 30))


def _calculate_tier_distribution(hit_stats: Dict[str, int]) -> Dict[str, float]:
    """Calculate distribution of hits across cache tiers"""
    total = sum(hit_stats.values())
    if total == 0:
        return {"memory": 0.0, "redis": 0.0, "miss": 0.0}
    
    return {
        "memory": (hit_stats['memory_hits'] / total) * 100,
        "redis": (hit_stats['redis_hits'] / total) * 100,
        "miss": (hit_stats['misses'] / total) * 100
    }


def _get_immediate_optimization_actions(stats: Dict[str, Any], hit_ratios: Dict[str, float]) -> List[str]:
    """Get immediate optimization actions"""
    actions = []
    
    if hit_ratios['total'] < 30:
        actions.append("Review and optimize caching strategy for critical paths")
    
    if stats['memory_cache'].get('utilization', 0) > 90:
        actions.append("Increase memory cache size immediately")
    
    return actions


def _get_configuration_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Get cache configuration recommendations"""
    recommendations = []
    
    memory_util = stats['memory_cache'].get('utilization', 0)
    if memory_util > 80:
        recommendations.append("Increase memory cache max_size parameter")
    
    if not stats['redis_cache'].get('connected', False):
        recommendations.append("Configure Redis for distributed caching")
    
    return recommendations


def _get_architectural_recommendations(stats: Dict[str, Any], hit_ratios: Dict[str, float]) -> List[str]:
    """Get architectural improvement recommendations"""
    recommendations = []
    
    if hit_ratios['redis'] < 20 and stats['redis_cache'].get('connected', False):
        recommendations.append("Optimize Redis cache key patterns and TTL strategies")
    
    recommendations.append("Consider implementing cache warming strategies")
    recommendations.append("Implement cache-aside pattern for critical data")
    
    return recommendations


def _analyze_current_usage(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze current cache usage patterns"""
    return {
        "memory_entries": stats['memory_cache'].get('entries', 0),
        "memory_utilization": stats['memory_cache'].get('utilization', 0),
        "redis_connected": stats['redis_cache'].get('connected', False),
        "total_requests": sum(stats['hit_stats'].values())
    }


def _project_cache_growth(stats: Dict[str, Any]) -> Dict[str, str]:
    """Project cache growth patterns"""
    # This would analyze historical data in a real implementation
    return {
        "memory_usage_trend": "stable",
        "request_volume_trend": "increasing",
        "hit_ratio_trend": "stable"
    }


def _get_cache_scaling_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Get cache scaling recommendations"""
    recommendations = []
    
    memory_util = stats['memory_cache'].get('utilization', 0)
    if memory_util > 70:
        recommendations.append("Plan for memory cache capacity increase")
    
    if not stats['redis_cache'].get('connected', False):
        recommendations.append("Implement Redis clustering for scalability")
    
    return recommendations