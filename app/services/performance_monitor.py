"""
Advanced Performance Monitoring System for MITA Backend
Provides real-time performance metrics, memory monitoring, 
and automatic optimization suggestions
"""

import time
import logging
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps
from collections import defaultdict, deque
import asyncio
import weakref
import gc

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance metric data point"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class EndpointMetrics:
    """Metrics for a specific API endpoint"""
    endpoint: str
    method: str
    total_requests: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    last_accessed: datetime = None
    
    @property
    def avg_time(self) -> float:
        return self.total_time / max(self.total_requests, 1)
    
    @property
    def error_rate(self) -> float:
        return (self.error_count / max(self.total_requests, 1)) * 100


class SystemResourceMonitor:
    """Monitor system resources (CPU, memory, disk)"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.metrics_history = deque(maxlen=100)  # Keep last 100 measurements
        self._monitoring = False
        self._monitor_thread = None
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("System resource monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("System resource monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                metrics = self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Check for alerts
                self._check_resource_alerts(metrics)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
            
            time.sleep(self.check_interval)
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """Collect current system metrics"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_used_gb': psutil.virtual_memory().used / (1024**3),
            'memory_available_gb': psutil.virtual_memory().available / (1024**3),
            'disk_percent': psutil.disk_usage('/').percent,
            'disk_free_gb': psutil.disk_usage('/').free / (1024**3),
            'load_avg_1min': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
            'active_connections': len(psutil.net_connections()),
            'process_count': len(psutil.pids()),
        }
    
    def _check_resource_alerts(self, metrics: Dict[str, float]):
        """Check for resource usage alerts"""
        alerts = []
        
        if metrics['cpu_percent'] > 80:
            alerts.append(f"High CPU usage: {metrics['cpu_percent']:.1f}%")
        
        if metrics['memory_percent'] > 85:
            alerts.append(f"High memory usage: {metrics['memory_percent']:.1f}%")
        
        if metrics['disk_percent'] > 90:
            alerts.append(f"High disk usage: {metrics['disk_percent']:.1f}%")
        
        if metrics['active_connections'] > 1000:
            alerts.append(f"High connection count: {metrics['active_connections']}")
        
        for alert in alerts:
            logger.warning(f"Resource Alert: {alert}")
    
    def get_current_metrics(self) -> Dict[str, float]:
        """Get current system metrics"""
        return self._collect_system_metrics()
    
    def get_metrics_history(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get metrics history for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            {**metrics, 'timestamp': datetime.now() - timedelta(seconds=i * self.check_interval)}
            for i, metrics in enumerate(reversed(self.metrics_history))
            if datetime.now() - timedelta(seconds=i * self.check_interval) >= cutoff_time
        ]


class MemoryProfiler:
    """Advanced memory profiling and leak detection"""
    
    def __init__(self):
        self.snapshots = []
        self.tracked_objects = weakref.WeakSet()
        self.allocation_tracker = defaultdict(int)
    
    def take_snapshot(self, label: str = None) -> Dict[str, Any]:
        """Take a memory snapshot"""
        gc.collect()  # Force garbage collection
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        snapshot = {
            'label': label or f"snapshot_{len(self.snapshots)}",
            'timestamp': datetime.now(),
            'rss_mb': memory_info.rss / (1024 * 1024),
            'vms_mb': memory_info.vms / (1024 * 1024),
            'percent': process.memory_percent(),
            'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0,
            'num_threads': process.num_threads(),
            'gc_stats': {
                'collected': gc.get_count(),
                'tracked_objects': len(self.tracked_objects),
            }
        }
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def compare_snapshots(self, snapshot1_idx: int = -2, snapshot2_idx: int = -1) -> Dict[str, Any]:
        """Compare two memory snapshots"""
        if len(self.snapshots) < 2:
            return {'error': 'Need at least 2 snapshots to compare'}
        
        snap1 = self.snapshots[snapshot1_idx]
        snap2 = self.snapshots[snapshot2_idx]
        
        return {
            'time_diff': (snap2['timestamp'] - snap1['timestamp']).total_seconds(),
            'rss_diff_mb': snap2['rss_mb'] - snap1['rss_mb'],
            'vms_diff_mb': snap2['vms_mb'] - snap1['vms_mb'],
            'percent_diff': snap2['percent'] - snap1['percent'],
            'fds_diff': snap2['num_fds'] - snap1['num_fds'],
            'threads_diff': snap2['num_threads'] - snap1['num_threads'],
            'potential_leak': snap2['rss_mb'] > snap1['rss_mb'] * 1.1,  # 10% increase
        }
    
    def track_object(self, obj: Any):
        """Track an object for memory leak detection"""
        self.tracked_objects.add(obj)
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Get comprehensive memory report"""
        current_snapshot = self.take_snapshot("report")
        
        report = {
            'current_memory': current_snapshot,
            'snapshots_count': len(self.snapshots),
            'tracked_objects': len(self.tracked_objects),
        }
        
        if len(self.snapshots) >= 2:
            report['recent_comparison'] = self.compare_snapshots()
        
        return report


class RequestProfiler:
    """Profile individual HTTP requests"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.endpoint_metrics: Dict[str, EndpointMetrics] = {}
        self.request_history = deque(maxlen=max_history)
        self.slow_requests = deque(maxlen=100)  # Keep track of slowest requests
        self.slow_threshold = 1.0  # seconds
    
    @contextmanager
    def profile_request(self, endpoint: str, method: str):
        """Context manager to profile a request"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        request_data = {
            'endpoint': endpoint,
            'method': method,
            'start_time': datetime.now(),
            'start_memory_mb': start_memory / (1024 * 1024),
        }
        
        try:
            yield request_data
            request_data['status'] = 'success'
        except Exception as e:
            request_data['status'] = 'error'
            request_data['error'] = str(e)
            raise
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            duration = end_time - start_time
            memory_diff = (end_memory - start_memory) / (1024 * 1024)
            
            request_data.update({
                'duration': duration,
                'end_time': datetime.now(),
                'memory_diff_mb': memory_diff,
            })
            
            self._record_request(request_data)
    
    def _record_request(self, request_data: Dict[str, Any]):
        """Record request metrics"""
        endpoint = request_data['endpoint']
        method = request_data['method']
        duration = request_data['duration']
        is_error = request_data['status'] == 'error'
        
        # Update endpoint metrics
        key = f"{method} {endpoint}"
        if key not in self.endpoint_metrics:
            self.endpoint_metrics[key] = EndpointMetrics(endpoint, method)
        
        metrics = self.endpoint_metrics[key]
        metrics.total_requests += 1
        metrics.total_time += duration
        metrics.min_time = min(metrics.min_time, duration)
        metrics.max_time = max(metrics.max_time, duration)
        metrics.last_accessed = request_data['start_time']
        
        if is_error:
            metrics.error_count += 1
        
        # Add to history
        self.request_history.append(request_data)
        
        # Track slow requests
        if duration > self.slow_threshold:
            self.slow_requests.append(request_data)
            logger.warning(f"Slow request detected: {method} {endpoint} took {duration:.3f}s")
    
    def get_endpoint_stats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get statistics for all endpoints"""
        stats = []
        for key, metrics in self.endpoint_metrics.items():
            stats.append({
                'endpoint': f"{metrics.method} {metrics.endpoint}",
                'total_requests': metrics.total_requests,
                'avg_time': metrics.avg_time,
                'min_time': metrics.min_time,
                'max_time': metrics.max_time,
                'error_rate': metrics.error_rate,
                'last_accessed': metrics.last_accessed.isoformat() if metrics.last_accessed else None,
            })
        
        # Sort by average response time (descending)
        stats.sort(key=lambda x: x['avg_time'], reverse=True)
        return stats[:limit]
    
    def get_slow_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest requests"""
        sorted_requests = sorted(
            self.slow_requests,
            key=lambda x: x['duration'],
            reverse=True
        )
        
        return [{
            'endpoint': f"{req['method']} {req['endpoint']}",
            'duration': req['duration'],
            'memory_diff_mb': req['memory_diff_mb'],
            'timestamp': req['start_time'].isoformat(),
            'status': req['status'],
        } for req in sorted_requests[:limit]]


class CachePerformanceMonitor:
    """Monitor cache performance and hit rates"""
    
    def __init__(self):
        self.cache_stats = defaultdict(lambda: {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'total_time_saved': 0.0,  # Time saved by cache hits
        })
    
    def record_cache_hit(self, cache_name: str, time_saved: float = 0.0):
        """Record a cache hit"""
        stats = self.cache_stats[cache_name]
        stats['hits'] += 1
        stats['total_time_saved'] += time_saved
    
    def record_cache_miss(self, cache_name: str):
        """Record a cache miss"""
        self.cache_stats[cache_name]['misses'] += 1
    
    def record_cache_set(self, cache_name: str):
        """Record a cache set operation"""
        self.cache_stats[cache_name]['sets'] += 1
    
    def record_cache_delete(self, cache_name: str):
        """Record a cache delete operation"""
        self.cache_stats[cache_name]['deletes'] += 1
    
    def get_cache_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get cache performance statistics"""
        stats = {}
        for cache_name, cache_data in self.cache_stats.items():
            total_requests = cache_data['hits'] + cache_data['misses']
            hit_rate = (cache_data['hits'] / max(total_requests, 1)) * 100
            
            stats[cache_name] = {
                'hits': cache_data['hits'],
                'misses': cache_data['misses'],
                'sets': cache_data['sets'],
                'deletes': cache_data['deletes'],
                'hit_rate_percent': hit_rate,
                'total_requests': total_requests,
                'time_saved_seconds': cache_data['total_time_saved'],
            }
        
        return stats


class PerformanceDecorator:
    """Decorator for automatic performance monitoring"""
    
    def __init__(self, performance_monitor: 'PerformanceMonitor'):
        self.monitor = performance_monitor
    
    def profile(self, category: str = "general", track_memory: bool = False):
        """Decorator to profile function execution"""
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss if track_memory else 0
                
                try:
                    result = await func(*args, **kwargs)
                    status = 'success'
                    return result
                except Exception:
                    status = 'error'
                    raise
                finally:
                    duration = time.time() - start_time
                    end_memory = psutil.Process().memory_info().rss if track_memory else 0
                    memory_diff = (end_memory - start_memory) / (1024 * 1024) if track_memory else 0
                    
                    self.monitor.record_function_call(
                        func.__name__,
                        category,
                        duration,
                        status,
                        memory_diff
                    )
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss if track_memory else 0
                
                try:
                    result = func(*args, **kwargs)
                    status = 'success'
                    return result
                except Exception:
                    status = 'error'
                    raise
                finally:
                    duration = time.time() - start_time
                    end_memory = psutil.Process().memory_info().rss if track_memory else 0
                    memory_diff = (end_memory - start_memory) / (1024 * 1024) if track_memory else 0
                    
                    self.monitor.record_function_call(
                        func.__name__,
                        category,
                        duration,
                        status,
                        memory_diff
                    )
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator


class PerformanceMonitor:
    """Central performance monitoring system"""
    
    def __init__(self):
        self.system_monitor = SystemResourceMonitor()
        self.memory_profiler = MemoryProfiler()
        self.request_profiler = RequestProfiler()
        self.cache_monitor = CachePerformanceMonitor()
        self.decorator = PerformanceDecorator(self)
        
        # Function call statistics
        self.function_stats = defaultdict(lambda: {
            'calls': 0,
            'total_time': 0.0,
            'errors': 0,
            'total_memory_diff': 0.0,
        })
        
        # Performance alerts
        self.alert_thresholds = {
            'slow_request_threshold': 2.0,  # seconds
            'high_memory_threshold': 85,    # percent
            'low_cache_hit_rate': 60,       # percent
        }
    
    def start(self):
        """Start all monitoring systems"""
        self.system_monitor.start_monitoring()
        self.memory_profiler.take_snapshot("initial")
        logger.info("Performance monitoring started")
    
    def stop(self):
        """Stop all monitoring systems"""
        self.system_monitor.stop_monitoring()
        logger.info("Performance monitoring stopped")
    
    def record_function_call(self, func_name: str, category: str, 
                           duration: float, status: str, memory_diff: float = 0.0):
        """Record function call statistics"""
        stats = self.function_stats[f"{category}.{func_name}"]
        stats['calls'] += 1
        stats['total_time'] += duration
        stats['total_memory_diff'] += memory_diff
        
        if status == 'error':
            stats['errors'] += 1
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            'timestamp': datetime.now().isoformat(),
            'system_resources': self.system_monitor.get_current_metrics(),
            'memory_profile': self.memory_profiler.get_memory_report(),
            'endpoint_performance': self.request_profiler.get_endpoint_stats(),
            'slow_requests': self.request_profiler.get_slow_requests(),
            'cache_performance': self.cache_monitor.get_cache_stats(),
            'function_statistics': self._get_function_stats(),
            'recommendations': self._generate_recommendations(),
        }
    
    def _get_function_stats(self) -> List[Dict[str, Any]]:
        """Get function call statistics"""
        stats = []
        for func_name, data in self.function_stats.items():
            avg_time = data['total_time'] / max(data['calls'], 1)
            error_rate = (data['errors'] / max(data['calls'], 1)) * 100
            avg_memory = data['total_memory_diff'] / max(data['calls'], 1)
            
            stats.append({
                'function': func_name,
                'calls': data['calls'],
                'avg_time': avg_time,
                'total_time': data['total_time'],
                'error_rate': error_rate,
                'avg_memory_diff_mb': avg_memory,
            })
        
        return sorted(stats, key=lambda x: x['avg_time'], reverse=True)
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Check system resources
        current_metrics = self.system_monitor.get_current_metrics()
        if current_metrics['memory_percent'] > 80:
            recommendations.append("High memory usage detected - consider implementing memory optimization")
        
        if current_metrics['cpu_percent'] > 70:
            recommendations.append("High CPU usage - consider optimizing compute-intensive operations")
        
        # Check cache performance
        cache_stats = self.cache_monitor.get_cache_stats()
        for cache_name, stats in cache_stats.items():
            if stats['hit_rate_percent'] < 60:
                recommendations.append(f"Low cache hit rate for {cache_name} ({stats['hit_rate_percent']:.1f}%) - review cache strategy")
        
        # Check endpoint performance
        slow_endpoints = [ep for ep in self.request_profiler.get_endpoint_stats(5) if ep['avg_time'] > 1.0]
        if slow_endpoints:
            recommendations.append(f"Slow endpoints detected - optimize: {', '.join([ep['endpoint'] for ep in slow_endpoints[:3]])}")
        
        # Check memory leaks
        memory_report = self.memory_profiler.get_memory_report()
        if 'recent_comparison' in memory_report and memory_report['recent_comparison'].get('potential_leak'):
            recommendations.append("Potential memory leak detected - investigate object retention")
        
        return recommendations or ["Performance is optimal"]


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
        _performance_monitor.start()
    return _performance_monitor

# Convenience decorators
def profile_performance(category: str = "general", track_memory: bool = False):
    """Decorator for performance profiling"""
    monitor = get_performance_monitor()
    return monitor.decorator.profile(category, track_memory)

# FastAPI middleware integration
async def performance_monitoring_middleware(request, call_next):
    """FastAPI middleware for request performance monitoring"""
    monitor = get_performance_monitor()
    endpoint = request.url.path
    method = request.method
    
    with monitor.request_profiler.profile_request(endpoint, method) as request_data:
        response = await call_next(request)
        request_data['response_status'] = response.status_code
        return response