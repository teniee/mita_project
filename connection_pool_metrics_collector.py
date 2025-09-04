#!/usr/bin/env python3
"""
MITA Finance Connection Pool Metrics Collector
Real-time connection pool monitoring and performance analysis

Provides detailed metrics collection for connection pool load testing
and production monitoring of database connection performance.
"""

import asyncio
import time
import json
import threading
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque, defaultdict
import statistics
import psutil

# Database imports
from sqlalchemy import event, text, func
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine

# MITA imports
from app.core.async_session import async_engine
from app.core.database_monitoring import DatabaseQueryMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolSnapshot:
    """Point-in-time snapshot of connection pool state"""
    timestamp: datetime
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    invalid: int
    total_capacity: int
    utilization_percent: float
    
    # Connection timing metrics
    avg_checkout_time_ms: float
    max_checkout_time_ms: float
    checkout_wait_count: int
    
    # Performance indicators
    connection_errors: int
    connection_timeouts: int
    pool_recreations: int
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ConnectionLifecycleEvent:
    """Individual connection lifecycle event"""
    event_type: str  # connect, checkout, checkin, close, error
    connection_id: str
    timestamp: datetime
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    connection_age_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class ConnectionPoolMetricsCollector:
    """Comprehensive connection pool metrics collection and analysis"""
    
    def __init__(self, max_snapshots: int = 1000, max_events: int = 5000):
        self.max_snapshots = max_snapshots
        self.max_events = max_events
        
        # Metrics storage
        self.pool_snapshots: deque = deque(maxlen=max_snapshots)
        self.lifecycle_events: deque = deque(maxlen=max_events)
        self.connection_timings: Dict[str, Dict] = {}
        
        # Statistics
        self.connection_stats = defaultdict(lambda: {
            'total_checkouts': 0,
            'total_checkout_time_ms': 0.0,
            'max_checkout_time_ms': 0.0,
            'min_checkout_time_ms': float('inf'),
            'errors': 0,
            'timeouts': 0
        })
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Monitoring state
        self.monitoring_active = False
        self.collection_interval = 1.0  # seconds
        self.alert_thresholds = {
            'utilization_warning': 80.0,
            'utilization_critical': 95.0,
            'checkout_time_warning': 100.0,  # ms
            'checkout_time_critical': 500.0,  # ms
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.10  # 10%
        }
        
        # Setup event listeners if engine is available
        if async_engine:
            self.setup_event_listeners()
    
    def setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for connection pool monitoring"""
        if not async_engine:
            logger.warning("No async_engine available for event listeners")
            return
        
        try:
            engine = async_engine.sync_engine
            pool = engine.pool
            
            # Connection lifecycle events
            @event.listens_for(pool, "connect")
            def on_connect(dbapi_connection, connection_record):
                connection_id = str(id(dbapi_connection))
                self._record_lifecycle_event("connect", connection_id)
                logger.debug(f"🔗 Connection established: {connection_id}")
            
            @event.listens_for(pool, "checkout")
            def on_checkout(dbapi_connection, connection_record, connection_proxy):
                connection_id = str(id(dbapi_connection))
                connection_record._checkout_start_time = time.time()
                self._record_lifecycle_event("checkout", connection_id)
                logger.debug(f"📤 Connection checked out: {connection_id}")
            
            @event.listens_for(pool, "checkin")
            def on_checkin(dbapi_connection, connection_record):
                connection_id = str(id(dbapi_connection))
                
                checkout_duration = None
                if hasattr(connection_record, '_checkout_start_time'):
                    checkout_duration = (time.time() - connection_record._checkout_start_time) * 1000
                    
                    # Update statistics
                    with self.lock:
                        stats = self.connection_stats[connection_id]
                        stats['total_checkouts'] += 1
                        stats['total_checkout_time_ms'] += checkout_duration
                        stats['max_checkout_time_ms'] = max(stats['max_checkout_time_ms'], checkout_duration)
                        stats['min_checkout_time_ms'] = min(stats['min_checkout_time_ms'], checkout_duration)
                
                self._record_lifecycle_event("checkin", connection_id, checkout_duration)
                logger.debug(f"📥 Connection checked in: {connection_id} (duration: {checkout_duration:.1f}ms)")
            
            @event.listens_for(pool, "close")
            def on_close(dbapi_connection, connection_record):
                connection_id = str(id(dbapi_connection))
                self._record_lifecycle_event("close", connection_id)
                logger.debug(f"❌ Connection closed: {connection_id}")
            
            # Error handling
            @event.listens_for(engine, "handle_error")
            def on_handle_error(exception_context):
                connection_id = str(id(exception_context.connection)) if exception_context.connection else "unknown"
                error_msg = str(exception_context.original_exception)
                
                self._record_lifecycle_event("error", connection_id, error_message=error_msg)
                
                with self.lock:
                    self.connection_stats[connection_id]['errors'] += 1
                
                logger.warning(f"💥 Connection error: {connection_id} - {error_msg}")
            
            logger.info("✅ Connection pool event listeners setup complete")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup event listeners: {e}")
    
    def _record_lifecycle_event(
        self, 
        event_type: str, 
        connection_id: str, 
        duration_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """Record a connection lifecycle event"""
        event = ConnectionLifecycleEvent(
            event_type=event_type,
            connection_id=connection_id,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            error_message=error_message
        )
        
        with self.lock:
            self.lifecycle_events.append(event)
    
    def capture_pool_snapshot(self) -> ConnectionPoolSnapshot:
        """Capture current pool state snapshot"""
        if not async_engine:
            raise RuntimeError("No async_engine available for pool monitoring")
        
        pool = async_engine.pool
        
        # Basic pool metrics
        pool_size = pool.size()
        checked_in = pool.checkedin()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
        invalid = pool.invalid()
        total_capacity = pool_size + getattr(pool, '_max_overflow', 0)
        
        utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0
        
        # Connection timing analysis
        with self.lock:
            checkout_times = []
            wait_count = 0
            error_count = 0
            timeout_count = 0
            
            for conn_id, stats in self.connection_stats.items():
                if stats['total_checkouts'] > 0:
                    avg_time = stats['total_checkout_time_ms'] / stats['total_checkouts']
                    checkout_times.append(avg_time)
                
                error_count += stats['errors']
                timeout_count += stats['timeouts']
            
            avg_checkout_time = statistics.mean(checkout_times) if checkout_times else 0.0
            max_checkout_time = max(checkout_times) if checkout_times else 0.0
        
        snapshot = ConnectionPoolSnapshot(
            timestamp=datetime.now(),
            pool_size=pool_size,
            checked_in=checked_in,
            checked_out=checked_out,
            overflow=overflow,
            invalid=invalid,
            total_capacity=total_capacity,
            utilization_percent=utilization,
            avg_checkout_time_ms=avg_checkout_time,
            max_checkout_time_ms=max_checkout_time,
            checkout_wait_count=wait_count,
            connection_errors=error_count,
            connection_timeouts=timeout_count,
            pool_recreations=0  # Would need additional tracking
        )
        
        with self.lock:
            self.pool_snapshots.append(snapshot)
        
        # Check for alerts
        self._check_alert_conditions(snapshot)
        
        return snapshot
    
    def _check_alert_conditions(self, snapshot: ConnectionPoolSnapshot):
        """Check for alert conditions and log warnings"""
        
        # Utilization alerts
        if snapshot.utilization_percent >= self.alert_thresholds['utilization_critical']:
            logger.critical(f"🚨 CRITICAL: Pool utilization at {snapshot.utilization_percent:.1f}% - Pool exhaustion imminent!")
        elif snapshot.utilization_percent >= self.alert_thresholds['utilization_warning']:
            logger.warning(f"⚠️ WARNING: High pool utilization: {snapshot.utilization_percent:.1f}%")
        
        # Checkout time alerts
        if snapshot.avg_checkout_time_ms >= self.alert_thresholds['checkout_time_critical']:
            logger.critical(f"🚨 CRITICAL: Very slow connection checkout: {snapshot.avg_checkout_time_ms:.1f}ms")
        elif snapshot.avg_checkout_time_ms >= self.alert_thresholds['checkout_time_warning']:
            logger.warning(f"⚠️ WARNING: Slow connection checkout: {snapshot.avg_checkout_time_ms:.1f}ms")
        
        # Error rate alerts
        total_operations = sum(stats['total_checkouts'] for stats in self.connection_stats.values())
        total_errors = sum(stats['errors'] for stats in self.connection_stats.values())
        
        if total_operations > 0:
            error_rate = total_errors / total_operations
            if error_rate >= self.alert_thresholds['error_rate_critical']:
                logger.critical(f"🚨 CRITICAL: High connection error rate: {error_rate*100:.1f}%")
            elif error_rate >= self.alert_thresholds['error_rate_warning']:
                logger.warning(f"⚠️ WARNING: Elevated connection error rate: {error_rate*100:.1f}%")
    
    async def start_continuous_monitoring(self, duration_seconds: Optional[int] = None):
        """Start continuous pool monitoring"""
        self.monitoring_active = True
        start_time = time.time()
        
        logger.info(f"📊 Starting continuous pool monitoring (interval: {self.collection_interval}s)")
        
        try:
            while self.monitoring_active:
                self.capture_pool_snapshot()
                
                # Check if duration limit reached
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    break
                
                await asyncio.sleep(self.collection_interval)
        
        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
        
        finally:
            self.monitoring_active = False
            logger.info("✅ Pool monitoring stopped")
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring_active = False
    
    def get_performance_summary(self, time_window_minutes: int = 10) -> Dict[str, Any]:
        """Get performance summary for specified time window"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        with self.lock:
            # Filter snapshots within time window
            recent_snapshots = [
                s for s in self.pool_snapshots 
                if s.timestamp >= cutoff_time
            ]
            
            # Filter events within time window
            recent_events = [
                e for e in self.lifecycle_events 
                if e.timestamp >= cutoff_time
            ]
        
        if not recent_snapshots:
            return {"error": "No data available for specified time window"}
        
        # Calculate metrics
        utilizations = [s.utilization_percent for s in recent_snapshots]
        checkout_times = [s.avg_checkout_time_ms for s in recent_snapshots if s.avg_checkout_time_ms > 0]
        
        # Event analysis
        event_counts = defaultdict(int)
        for event in recent_events:
            event_counts[event.event_type] += 1
        
        # Connection efficiency
        total_checkouts = event_counts.get('checkout', 0)
        total_checkins = event_counts.get('checkin', 0)
        connection_efficiency = (total_checkins / total_checkouts * 100) if total_checkouts > 0 else 0
        
        summary = {
            "time_window_minutes": time_window_minutes,
            "snapshots_analyzed": len(recent_snapshots),
            "events_analyzed": len(recent_events),
            
            "pool_utilization": {
                "current": recent_snapshots[-1].utilization_percent if recent_snapshots else 0,
                "average": statistics.mean(utilizations) if utilizations else 0,
                "peak": max(utilizations) if utilizations else 0,
                "minimum": min(utilizations) if utilizations else 0
            },
            
            "connection_performance": {
                "avg_checkout_time_ms": statistics.mean(checkout_times) if checkout_times else 0,
                "p95_checkout_time_ms": self._percentile(checkout_times, 95) if checkout_times else 0,
                "max_checkout_time_ms": max(checkout_times) if checkout_times else 0,
                "connection_efficiency_percent": connection_efficiency
            },
            
            "event_summary": dict(event_counts),
            
            "health_indicators": {
                "pool_healthy": all(u < 90 for u in utilizations[-10:]) if len(utilizations) >= 10 else True,
                "performance_healthy": all(t < 200 for t in checkout_times[-10:]) if len(checkout_times) >= 10 else True,
                "error_rate_acceptable": event_counts.get('error', 0) / max(len(recent_events), 1) < 0.05
            }
        }
        
        return summary
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile from data"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = int(k)
        c = int(k) + 1
        if f == c or f >= len(sorted_data) - 1:
            return sorted_data[f] if f < len(sorted_data) else sorted_data[-1]
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f) if c < len(sorted_data) else 0
        return d0 + d1
    
    def get_connection_lifecycle_analysis(self) -> Dict[str, Any]:
        """Analyze connection lifecycle patterns"""
        with self.lock:
            events_by_type = defaultdict(list)
            for event in self.lifecycle_events:
                events_by_type[event.event_type].append(event)
        
        analysis = {
            "total_events": len(self.lifecycle_events),
            "event_type_counts": {
                event_type: len(events) 
                for event_type, events in events_by_type.items()
            }
        }
        
        # Checkout duration analysis
        checkin_events = events_by_type.get('checkin', [])
        checkout_durations = [e.duration_ms for e in checkin_events if e.duration_ms is not None]
        
        if checkout_durations:
            analysis["checkout_duration_analysis"] = {
                "count": len(checkout_durations),
                "avg_ms": statistics.mean(checkout_durations),
                "median_ms": statistics.median(checkout_durations),
                "p95_ms": self._percentile(checkout_durations, 95),
                "max_ms": max(checkout_durations),
                "min_ms": min(checkout_durations)
            }
        
        # Error analysis
        error_events = events_by_type.get('error', [])
        if error_events:
            error_types = defaultdict(int)
            for error_event in error_events:
                if error_event.error_message:
                    # Categorize error types
                    error_msg = error_event.error_message.lower()
                    if 'timeout' in error_msg:
                        error_types['timeout'] += 1
                    elif 'connection' in error_msg:
                        error_types['connection_error'] += 1
                    elif 'pool' in error_msg:
                        error_types['pool_error'] += 1
                    else:
                        error_types['other'] += 1
            
            analysis["error_analysis"] = {
                "total_errors": len(error_events),
                "error_types": dict(error_types),
                "error_rate_percent": (len(error_events) / len(self.lifecycle_events) * 100) if self.lifecycle_events else 0
            }
        
        return analysis
    
    def export_metrics_data(self, filepath: str = None) -> str:
        """Export all collected metrics to JSON file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"connection_pool_metrics_{timestamp}.json"
        
        with self.lock:
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "collection_period": {
                    "start": self.pool_snapshots[0].timestamp.isoformat() if self.pool_snapshots else None,
                    "end": self.pool_snapshots[-1].timestamp.isoformat() if self.pool_snapshots else None,
                    "total_snapshots": len(self.pool_snapshots),
                    "total_events": len(self.lifecycle_events)
                },
                "pool_snapshots": [snapshot.to_dict() for snapshot in self.pool_snapshots],
                "lifecycle_events": [event.to_dict() for event in self.lifecycle_events],
                "connection_statistics": dict(self.connection_stats),
                "performance_summary": self.get_performance_summary(60),  # Last hour
                "lifecycle_analysis": self.get_connection_lifecycle_analysis()
            }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"📁 Metrics data exported to: {filepath}")
        return filepath
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        performance_summary = self.get_performance_summary(30)  # Last 30 minutes
        lifecycle_analysis = self.get_connection_lifecycle_analysis()
        
        with self.lock:
            latest_snapshot = self.pool_snapshots[-1] if self.pool_snapshots else None
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "monitoring_status": {
                "active": self.monitoring_active,
                "snapshots_collected": len(self.pool_snapshots),
                "events_recorded": len(self.lifecycle_events),
                "collection_interval_seconds": self.collection_interval
            },
            
            "current_pool_state": latest_snapshot.to_dict() if latest_snapshot else None,
            
            "performance_summary": performance_summary,
            
            "lifecycle_analysis": lifecycle_analysis,
            
            "alert_thresholds": self.alert_thresholds,
            
            "health_assessment": self._assess_overall_health(),
            
            "recommendations": self._generate_performance_recommendations()
        }
        
        return report
    
    def _assess_overall_health(self) -> Dict[str, Any]:
        """Assess overall connection pool health"""
        if not self.pool_snapshots:
            return {"status": "unknown", "reason": "No data available"}
        
        recent_snapshots = list(self.pool_snapshots)[-10:]  # Last 10 snapshots
        
        # Health checks
        checks = {
            "utilization_healthy": all(s.utilization_percent < 85 for s in recent_snapshots),
            "checkout_time_healthy": all(s.avg_checkout_time_ms < 150 for s in recent_snapshots),
            "error_rate_healthy": all(s.connection_errors == 0 for s in recent_snapshots[-5:]),  # Last 5 snapshots
            "pool_stable": len(set(s.pool_size for s in recent_snapshots)) == 1  # Pool size hasn't changed
        }
        
        health_score = sum(1 for check in checks.values() if check) / len(checks) * 100
        
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 50:
            status = "fair"
        else:
            status = "poor"
        
        return {
            "status": status,
            "health_score_percent": health_score,
            "health_checks": checks,
            "summary": f"Connection pool health is {status} ({health_score:.0f}% of checks passing)"
        }
    
    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance recommendations based on collected metrics"""
        recommendations = []
        
        if not self.pool_snapshots:
            return ["Insufficient data for recommendations - continue monitoring"]
        
        recent_snapshots = list(self.pool_snapshots)[-20:]  # Last 20 snapshots
        
        # Utilization analysis
        avg_utilization = statistics.mean(s.utilization_percent for s in recent_snapshots)
        peak_utilization = max(s.utilization_percent for s in recent_snapshots)
        
        if peak_utilization > 95:
            recommendations.append("Pool exhaustion detected - consider increasing pool_size or max_overflow")
        elif avg_utilization > 80:
            recommendations.append("High average utilization - monitor for capacity planning")
        elif avg_utilization < 20:
            recommendations.append("Low utilization - pool may be over-provisioned")
        
        # Performance analysis
        checkout_times = [s.avg_checkout_time_ms for s in recent_snapshots if s.avg_checkout_time_ms > 0]
        if checkout_times:
            avg_checkout = statistics.mean(checkout_times)
            if avg_checkout > 200:
                recommendations.append("Slow connection checkout times - investigate database connectivity")
            elif avg_checkout < 10:
                recommendations.append("Excellent connection performance - configuration is optimal")
        
        # Error analysis
        recent_errors = sum(s.connection_errors for s in recent_snapshots[-5:])
        if recent_errors > 0:
            recommendations.append(f"Connection errors detected ({recent_errors}) - investigate error patterns")
        
        # Stability analysis
        utilization_variance = statistics.variance([s.utilization_percent for s in recent_snapshots]) if len(recent_snapshots) > 1 else 0
        if utilization_variance > 500:  # High variance
            recommendations.append("High utilization variance - workload may be unpredictable")
        
        if not recommendations:
            recommendations.append("Connection pool performance is optimal - no issues detected")
        
        return recommendations


# Utility functions for integration with load testing
async def monitor_during_load_test(
    collector: ConnectionPoolMetricsCollector, 
    test_duration_seconds: int,
    snapshot_interval: float = 1.0
) -> Dict[str, Any]:
    """Monitor connection pool during load test execution"""
    
    logger.info(f"📊 Starting load test monitoring for {test_duration_seconds}s")
    
    # Set collection interval
    original_interval = collector.collection_interval
    collector.collection_interval = snapshot_interval
    
    try:
        # Start monitoring
        monitor_task = asyncio.create_task(
            collector.start_continuous_monitoring(test_duration_seconds)
        )
        
        # Wait for monitoring to complete
        await monitor_task
        
        # Generate report
        report = collector.generate_performance_report()
        
        logger.info("✅ Load test monitoring completed")
        return report
    
    finally:
        # Restore original interval
        collector.collection_interval = original_interval


def create_load_test_metrics_collector() -> ConnectionPoolMetricsCollector:
    """Create a metrics collector optimized for load testing"""
    collector = ConnectionPoolMetricsCollector(
        max_snapshots=2000,  # Higher capacity for load tests
        max_events=10000
    )
    
    # Adjust thresholds for load testing
    collector.alert_thresholds.update({
        'utilization_warning': 75.0,  # Lower threshold during testing
        'utilization_critical': 90.0,
        'checkout_time_warning': 50.0,  # Lower threshold for testing
        'checkout_time_critical': 200.0
    })
    
    return collector


if __name__ == "__main__":
    """Demonstration of connection pool metrics collection"""
    
    async def demo():
        collector = create_load_test_metrics_collector()
        
        print("🚀 Starting connection pool metrics demonstration...")
        
        # Monitor for 60 seconds
        await monitor_during_load_test(collector, 60, 2.0)
        
        # Export data
        filepath = collector.export_metrics_data()
        print(f"📁 Metrics exported to: {filepath}")
        
        # Generate report
        report = collector.generate_performance_report()
        print(f"📊 Health Status: {report['health_assessment']['status']}")
        print(f"📊 Health Score: {report['health_assessment']['health_score_percent']:.0f}%")
    
    asyncio.run(demo())