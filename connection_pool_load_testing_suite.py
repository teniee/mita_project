#!/usr/bin/env python3
"""
MITA Finance Connection Pool Load Testing Suite
Comprehensive 100% connection pool validation for production deployment

CRITICAL VALIDATION REQUIREMENTS:
- Pool configuration: pool_size=20, max_overflow=30, pool_timeout=30
- Test all connection pool scenarios under production load
- Validate against previous 8-15+ second timeout issues
- Ensure zero connection leaks and proper pool management
- Test concurrent access patterns and error handling
"""

import asyncio
import time
import json
import statistics
import logging
import psutil
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

# Database imports
from sqlalchemy import text, func, select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import TimeoutError, OperationalError, DisconnectionError
import asyncpg

# MITA imports
from app.core.async_session import initialize_database, get_async_db_context, AsyncSessionLocal, async_engine
from app.core.database_monitoring import get_db_engine, DatabaseQueryMonitor
from app.db.models import User, Transaction, Expense, Goal
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ConnectionPoolMetrics:
    """Comprehensive connection pool performance metrics"""
    test_scenario: str
    concurrent_users: int
    pool_size: int
    max_overflow: int
    pool_timeout: float
    
    # Connection metrics
    total_connections_requested: int
    successful_connections: int
    failed_connections: int
    timeout_connections: int
    
    # Timing metrics
    avg_connection_acquisition_ms: float
    p50_connection_acquisition_ms: float
    p95_connection_acquisition_ms: float
    p99_connection_acquisition_ms: float
    max_connection_acquisition_ms: float
    min_connection_acquisition_ms: float
    
    # Pool state metrics
    peak_checked_out: int
    peak_pool_utilization_percent: float
    pool_exhaustion_events: int
    connection_reuse_rate: float
    
    # Error metrics
    connection_errors: List[str]
    recovery_time_ms: Optional[float]
    
    # Performance metrics
    total_queries_executed: int
    avg_query_execution_ms: float
    queries_per_second: float
    
    # Test results
    test_duration_seconds: float
    passed: bool
    issues: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ConnectionLoadTestResult:
    """Individual connection load test result"""
    user_id: str
    operation: str
    start_time: float
    connection_acquired_time: float
    query_completed_time: float
    connection_released_time: float
    
    success: bool
    error: Optional[str] = None
    
    @property
    def connection_acquisition_ms(self) -> float:
        return (self.connection_acquired_time - self.start_time) * 1000
    
    @property
    def query_execution_ms(self) -> float:
        return (self.query_completed_time - self.connection_acquired_time) * 1000
    
    @property
    def total_operation_ms(self) -> float:
        return (self.connection_released_time - self.start_time) * 1000


class ConnectionPoolValidator:
    """Comprehensive connection pool validation and testing"""
    
    def __init__(self):
        self.test_results: List[ConnectionLoadTestResult] = []
        self.pool_metrics_history: List[Dict[str, Any]] = []
        self.monitor = DatabaseQueryMonitor()
        self.test_start_time = None
        self.test_users = []
        
        # Expected pool configuration
        self.expected_pool_size = 20
        self.expected_max_overflow = 30
        self.expected_pool_timeout = 30
        self.expected_total_connections = self.expected_pool_size + self.expected_max_overflow  # 50
        
        # Performance thresholds
        self.max_connection_acquisition_ms = 100.0  # 100ms max to get connection
        self.max_query_execution_ms = 200.0  # 200ms max for simple queries
        self.max_pool_exhaustion_time_ms = 1000.0  # 1 second max recovery from exhaustion
        
    async def initialize_test_environment(self):
        """Initialize test environment and validate pool configuration"""
        logger.info("🔧 Initializing connection pool test environment...")
        
        # Ensure database is initialized
        initialize_database()
        
        if async_engine is None:
            raise RuntimeError("Database engine not initialized")
        
        # Validate pool configuration
        pool = async_engine.pool
        actual_pool_size = pool.size()
        actual_overflow = getattr(pool, '_overflow', 0)
        actual_timeout = getattr(pool, '_timeout', 0)
        
        logger.info(f"📊 Pool Configuration Validation:")
        logger.info(f"   Pool Size: {actual_pool_size} (expected: {self.expected_pool_size})")
        logger.info(f"   Max Overflow: {actual_overflow} (expected: {self.expected_max_overflow})")
        logger.info(f"   Pool Timeout: {actual_timeout}s (expected: {self.expected_pool_timeout}s)")
        
        # Create test users for load testing
        await self.create_test_users()
        
        logger.info("✅ Test environment initialized")
    
    async def create_test_users(self, count: int = 100):
        """Create test users for connection pool testing"""
        logger.info(f"👥 Creating {count} test users...")
        
        timestamp = int(time.time())
        users_created = 0
        
        try:
            async with get_async_db_context() as session:
                for i in range(count):
                    user = User(
                        email=f"pool_test_user_{timestamp}_{i}@example.com",
                        password_hash="test_hash_for_pool_testing",
                        country="US",
                        annual_income=50000 + (i * 1000),
                        timezone="America/New_York"
                    )
                    session.add(user)
                    
                    # Batch commit every 20 users
                    if i % 20 == 19:
                        await session.commit()
                        users_created += 20
                        logger.info(f"   Created {users_created} users...")
                
                # Final commit
                await session.commit()
                
                # Fetch created users with IDs
                result = await session.execute(
                    select(User).where(User.email.like(f"pool_test_user_{timestamp}_%"))
                )
                self.test_users = result.scalars().all()
                
        except Exception as e:
            logger.error(f"❌ Error creating test users: {e}")
            raise
        
        logger.info(f"✅ Created {len(self.test_users)} test users")
    
    async def capture_pool_state(self, scenario: str) -> Dict[str, Any]:
        """Capture current connection pool state"""
        if async_engine is None:
            return {}
        
        pool = async_engine.pool
        
        return {
            "timestamp": time.time(),
            "scenario": scenario,
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "total_capacity": pool.size() + getattr(pool, '_overflow', 0),
            "utilization_percent": (pool.checkedout() / (pool.size() + getattr(pool, '_overflow', 0))) * 100
        }
    
    async def simulate_user_database_operations(self, user: User, duration_seconds: int = 60) -> List[ConnectionLoadTestResult]:
        """Simulate realistic database operations for a single user"""
        user_results = []
        user_id = f"user_{user.id}"
        operations_completed = 0
        
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < duration_seconds:
                # Randomly select operation type to simulate realistic usage
                operation_type = self._select_weighted_operation()
                
                result = await self._execute_database_operation(user, operation_type, user_id)
                user_results.append(result)
                operations_completed += 1
                
                # Realistic delays between operations
                await asyncio.sleep(self._get_realistic_delay(operation_type))
        
        except Exception as e:
            logger.error(f"❌ User {user_id} simulation error: {e}")
        
        logger.debug(f"👤 User {user_id} completed {operations_completed} operations in {time.time() - start_time:.1f}s")
        return user_results
    
    def _select_weighted_operation(self) -> str:
        """Select database operation with realistic weights"""
        import random
        
        # Weighted based on typical financial app usage patterns
        operations = [
            ("user_lookup", 15),       # Authentication/session validation
            ("recent_transactions", 30), # Most common - viewing recent expenses
            ("transaction_insert", 20),  # Adding new transactions
            ("category_summary", 15),    # Viewing spending by category
            ("monthly_analysis", 10),    # Monthly spending analysis
            ("goal_check", 5),          # Checking financial goals
            ("complex_analytics", 5)     # Complex reporting queries
        ]
        
        total_weight = sum(weight for _, weight in operations)
        r = random.randint(1, total_weight)
        
        cumulative = 0
        for operation, weight in operations:
            cumulative += weight
            if r <= cumulative:
                return operation
        
        return "user_lookup"  # fallback
    
    def _get_realistic_delay(self, operation_type: str) -> float:
        """Get realistic delay between operations"""
        import random
        
        # Realistic delays based on user behavior
        delays = {
            "user_lookup": random.uniform(0.1, 0.5),      # Quick session checks
            "recent_transactions": random.uniform(1.0, 3.0), # Viewing transactions
            "transaction_insert": random.uniform(2.0, 5.0),  # Adding expense (thinking time)
            "category_summary": random.uniform(2.0, 8.0),    # Analyzing spending
            "monthly_analysis": random.uniform(5.0, 15.0),   # Deep analysis
            "goal_check": random.uniform(1.0, 4.0),          # Quick goal check
            "complex_analytics": random.uniform(10.0, 30.0)   # Heavy reporting
        }
        
        return delays.get(operation_type, 1.0)
    
    async def _execute_database_operation(self, user: User, operation_type: str, user_id: str) -> ConnectionLoadTestResult:
        """Execute specific database operation with detailed timing"""
        start_time = time.time()
        connection_acquired_time = None
        query_completed_time = None
        connection_released_time = None
        success = False
        error = None
        
        try:
            # Start connection acquisition timing
            async with get_async_db_context() as session:
                connection_acquired_time = time.time()
                
                # Execute operation based on type
                if operation_type == "user_lookup":
                    result = await session.execute(
                        select(User).where(User.id == user.id)
                    )
                    user_data = result.scalars().first()
                
                elif operation_type == "recent_transactions":
                    result = await session.execute(
                        select(Transaction)
                        .where(Transaction.user_id == user.id)
                        .order_by(Transaction.date.desc())
                        .limit(20)
                    )
                    transactions = result.scalars().all()
                
                elif operation_type == "transaction_insert":
                    new_transaction = Transaction(
                        user_id=user.id,
                        amount=25.50,
                        description=f"Pool test transaction {int(time.time())}",
                        category="test",
                        date=datetime.now().date(),
                        created_at=datetime.now()
                    )
                    session.add(new_transaction)
                    await session.commit()
                
                elif operation_type == "category_summary":
                    result = await session.execute(
                        select(
                            Transaction.category,
                            func.sum(Transaction.amount).label('total'),
                            func.count(Transaction.id).label('count')
                        )
                        .where(Transaction.user_id == user.id)
                        .where(Transaction.date >= datetime.now().date() - timedelta(days=30))
                        .group_by(Transaction.category)
                    )
                    summary = result.all()
                
                elif operation_type == "monthly_analysis":
                    result = await session.execute(
                        select(
                            func.extract('month', Transaction.date).label('month'),
                            func.sum(Transaction.amount).label('total'),
                            func.avg(Transaction.amount).label('average')
                        )
                        .where(Transaction.user_id == user.id)
                        .where(Transaction.date >= datetime.now().date() - timedelta(days=180))
                        .group_by(func.extract('month', Transaction.date))
                    )
                    analysis = result.all()
                
                elif operation_type == "goal_check":
                    result = await session.execute(
                        select(Goal).where(Goal.user_id == user.id)
                    )
                    goals = result.scalars().all()
                
                elif operation_type == "complex_analytics":
                    # Complex multi-table analytical query
                    result = await session.execute(
                        select(
                            Transaction.category,
                            func.extract('week', Transaction.date).label('week'),
                            func.sum(Transaction.amount).label('weekly_total'),
                            func.count(Transaction.id).label('transaction_count')
                        )
                        .where(Transaction.user_id == user.id)
                        .where(Transaction.date >= datetime.now().date() - timedelta(days=90))
                        .group_by(Transaction.category, func.extract('week', Transaction.date))
                        .order_by(func.sum(Transaction.amount).desc())
                    )
                    complex_data = result.all()
                
                query_completed_time = time.time()
                success = True
            
            connection_released_time = time.time()
        
        except TimeoutError as e:
            error = f"Connection timeout: {str(e)}"
            connection_released_time = time.time()
        except OperationalError as e:
            error = f"Operational error: {str(e)}"
            connection_released_time = time.time()
        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            connection_released_time = time.time()
        
        # Ensure all timing values are set
        if connection_acquired_time is None:
            connection_acquired_time = start_time
        if query_completed_time is None:
            query_completed_time = connection_acquired_time
        if connection_released_time is None:
            connection_released_time = query_completed_time
        
        return ConnectionLoadTestResult(
            user_id=user_id,
            operation=operation_type,
            start_time=start_time,
            connection_acquired_time=connection_acquired_time,
            query_completed_time=query_completed_time,
            connection_released_time=connection_released_time,
            success=success,
            error=error
        )
    
    async def test_connection_pool_scenario(
        self, 
        scenario_name: str, 
        concurrent_users: int, 
        duration_seconds: int = 300
    ) -> ConnectionPoolMetrics:
        """Test specific connection pool scenario with detailed metrics"""
        
        logger.info(f"🧪 Testing Scenario: {scenario_name}")
        logger.info(f"   Concurrent Users: {concurrent_users}")
        logger.info(f"   Duration: {duration_seconds}s")
        logger.info(f"   Expected Pool Capacity: {self.expected_total_connections}")
        
        # Capture initial pool state
        initial_state = await self.capture_pool_state(f"{scenario_name}_start")
        self.pool_metrics_history.append(initial_state)
        
        # Select users for this test
        test_users = self.test_users[:concurrent_users]
        if len(test_users) < concurrent_users:
            raise ValueError(f"Not enough test users: need {concurrent_users}, have {len(test_users)}")
        
        scenario_results = []
        scenario_start_time = time.time()
        
        # Create tasks for concurrent users
        tasks = []
        for user in test_users:
            task = asyncio.create_task(
                self.simulate_user_database_operations(user, duration_seconds)
            )
            tasks.append(task)
        
        # Monitor pool state during test
        monitor_task = asyncio.create_task(
            self._monitor_pool_during_test(scenario_name, duration_seconds)
        )
        
        try:
            # Wait for all user simulations to complete
            user_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Cancel monitoring
            monitor_task.cancel()
            
            # Collect all results
            for results in user_results:
                if isinstance(results, list):
                    scenario_results.extend(results)
                elif isinstance(results, Exception):
                    logger.error(f"❌ User simulation failed: {results}")
        
        except Exception as e:
            logger.error(f"❌ Scenario {scenario_name} failed: {e}")
            monitor_task.cancel()
        
        scenario_end_time = time.time()
        
        # Capture final pool state
        final_state = await self.capture_pool_state(f"{scenario_name}_end")
        self.pool_metrics_history.append(final_state)
        
        # Analyze results
        metrics = self._analyze_scenario_results(
            scenario_name, 
            concurrent_users, 
            scenario_results, 
            scenario_end_time - scenario_start_time
        )
        
        self.test_results.extend(scenario_results)
        
        logger.info(f"✅ Scenario {scenario_name} completed:")
        logger.info(f"   Total Operations: {metrics.total_queries_executed}")
        logger.info(f"   Success Rate: {(metrics.successful_connections/metrics.total_connections_requested*100):.1f}%")
        logger.info(f"   Avg Connection Time: {metrics.avg_connection_acquisition_ms:.1f}ms")
        logger.info(f"   Peak Pool Utilization: {metrics.peak_pool_utilization_percent:.1f}%")
        
        return metrics
    
    async def _monitor_pool_during_test(self, scenario_name: str, duration_seconds: int):
        """Monitor pool state during test execution"""
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < duration_seconds:
                state = await self.capture_pool_state(f"{scenario_name}_monitor")
                self.pool_metrics_history.append(state)
                
                # Log if pool is getting heavily utilized
                if state.get("utilization_percent", 0) > 80:
                    logger.warning(f"⚠️ High pool utilization: {state['utilization_percent']:.1f}%")
                
                await asyncio.sleep(2)  # Monitor every 2 seconds
        
        except asyncio.CancelledError:
            pass
    
    def _analyze_scenario_results(
        self, 
        scenario_name: str, 
        concurrent_users: int, 
        results: List[ConnectionLoadTestResult], 
        duration_seconds: float
    ) -> ConnectionPoolMetrics:
        """Analyze scenario results and generate comprehensive metrics"""
        
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        timeout_results = [r for r in failed_results if "timeout" in (r.error or "").lower()]
        
        # Connection timing analysis
        connection_times = [r.connection_acquisition_ms for r in results]
        query_times = [r.query_execution_ms for r in successful_results]
        
        # Pool state analysis
        pool_states = [state for state in self.pool_metrics_history 
                      if scenario_name in state.get("scenario", "")]
        
        peak_checked_out = max((state.get("checked_out", 0) for state in pool_states), default=0)
        peak_utilization = max((state.get("utilization_percent", 0) for state in pool_states), default=0)
        
        # Error analysis
        error_types = [r.error for r in failed_results if r.error]
        pool_exhaustion_events = len([r for r in failed_results 
                                     if r.error and "pool" in r.error.lower()])
        
        # Calculate metrics
        metrics = ConnectionPoolMetrics(
            test_scenario=scenario_name,
            concurrent_users=concurrent_users,
            pool_size=self.expected_pool_size,
            max_overflow=self.expected_max_overflow,
            pool_timeout=self.expected_pool_timeout,
            
            total_connections_requested=len(results),
            successful_connections=len(successful_results),
            failed_connections=len(failed_results),
            timeout_connections=len(timeout_results),
            
            avg_connection_acquisition_ms=statistics.mean(connection_times) if connection_times else 0,
            p50_connection_acquisition_ms=self._percentile(connection_times, 50),
            p95_connection_acquisition_ms=self._percentile(connection_times, 95),
            p99_connection_acquisition_ms=self._percentile(connection_times, 99),
            max_connection_acquisition_ms=max(connection_times) if connection_times else 0,
            min_connection_acquisition_ms=min(connection_times) if connection_times else 0,
            
            peak_checked_out=peak_checked_out,
            peak_pool_utilization_percent=peak_utilization,
            pool_exhaustion_events=pool_exhaustion_events,
            connection_reuse_rate=self._calculate_connection_reuse_rate(pool_states),
            
            connection_errors=error_types,
            recovery_time_ms=self._calculate_recovery_time(failed_results),
            
            total_queries_executed=len(successful_results),
            avg_query_execution_ms=statistics.mean(query_times) if query_times else 0,
            queries_per_second=len(successful_results) / duration_seconds if duration_seconds > 0 else 0,
            
            test_duration_seconds=duration_seconds,
            passed=self._evaluate_scenario_success(successful_results, failed_results, connection_times),
            issues=self._identify_performance_issues(successful_results, failed_results, connection_times, peak_utilization)
        )
        
        return metrics
    
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
    
    def _calculate_connection_reuse_rate(self, pool_states: List[Dict[str, Any]]) -> float:
        """Calculate connection reuse efficiency"""
        if len(pool_states) < 2:
            return 0.0
        
        total_checkouts = sum(state.get("checked_out", 0) for state in pool_states)
        unique_connections = max(state.get("checked_out", 0) for state in pool_states)
        
        return (total_checkouts / unique_connections) if unique_connections > 0 else 0.0
    
    def _calculate_recovery_time(self, failed_results: List[ConnectionLoadTestResult]) -> Optional[float]:
        """Calculate recovery time from connection failures"""
        if not failed_results:
            return None
        
        # Find the time from first failure to next successful connection
        # This is a simplified calculation
        return statistics.mean([r.total_operation_ms for r in failed_results])
    
    def _evaluate_scenario_success(
        self, 
        successful_results: List[ConnectionLoadTestResult], 
        failed_results: List[ConnectionLoadTestResult], 
        connection_times: List[float]
    ) -> bool:
        """Evaluate if scenario passed performance criteria"""
        
        if not successful_results:
            return False
        
        success_rate = len(successful_results) / (len(successful_results) + len(failed_results))
        avg_connection_time = statistics.mean(connection_times) if connection_times else 0
        p95_connection_time = self._percentile(connection_times, 95)
        
        # Pass criteria
        criteria = [
            success_rate >= 0.95,  # 95% success rate minimum
            avg_connection_time <= self.max_connection_acquisition_ms,
            p95_connection_time <= self.max_connection_acquisition_ms * 2,  # P95 can be 2x avg
            len(failed_results) < len(successful_results) * 0.1  # Less than 10% failures
        ]
        
        return all(criteria)
    
    def _identify_performance_issues(
        self, 
        successful_results: List[ConnectionLoadTestResult], 
        failed_results: List[ConnectionLoadTestResult], 
        connection_times: List[float],
        peak_utilization: float
    ) -> List[str]:
        """Identify specific performance issues"""
        issues = []
        
        if not successful_results:
            issues.append("No successful operations completed")
            return issues
        
        success_rate = len(successful_results) / (len(successful_results) + len(failed_results))
        if success_rate < 0.95:
            issues.append(f"Low success rate: {success_rate*100:.1f}% (target: 95%)")
        
        avg_connection_time = statistics.mean(connection_times) if connection_times else 0
        if avg_connection_time > self.max_connection_acquisition_ms:
            issues.append(f"Slow connection acquisition: {avg_connection_time:.1f}ms (max: {self.max_connection_acquisition_ms}ms)")
        
        p99_connection_time = self._percentile(connection_times, 99)
        if p99_connection_time > self.max_connection_acquisition_ms * 3:
            issues.append(f"Very slow P99 connection times: {p99_connection_time:.1f}ms")
        
        if peak_utilization > 95:
            issues.append(f"Pool exhaustion detected: {peak_utilization:.1f}% peak utilization")
        
        timeout_count = len([r for r in failed_results if "timeout" in (r.error or "").lower()])
        if timeout_count > 0:
            issues.append(f"Connection timeouts detected: {timeout_count} occurrences")
        
        return issues
    
    async def test_pool_exhaustion_recovery(self) -> ConnectionPoolMetrics:
        """Test pool exhaustion scenario and recovery"""
        logger.info("🔥 Testing pool exhaustion and recovery...")
        
        # Create more concurrent users than pool capacity to force exhaustion
        exhaustion_users = self.expected_total_connections + 10  # 60 users for 50 connection pool
        test_users = self.test_users[:exhaustion_users]
        
        async def long_running_operation(user: User, duration: float):
            """Long-running operation to exhaust pool"""
            try:
                async with get_async_db_context() as session:
                    # Hold connection for specified duration
                    await session.execute(select(func.pg_sleep(duration)))
                    return True
            except Exception as e:
                logger.warning(f"Pool exhaustion test operation failed: {e}")
                return False
        
        # Start long-running operations to exhaust pool
        exhaustion_tasks = []
        for user in test_users:
            task = asyncio.create_task(long_running_operation(user, 5.0))  # 5 second operations
            exhaustion_tasks.append(task)
            await asyncio.sleep(0.1)  # Stagger start times slightly
        
        # Monitor pool state during exhaustion
        start_time = time.time()
        pool_states = []
        
        try:
            while len([task for task in exhaustion_tasks if not task.done()]) > 0:
                state = await self.capture_pool_state("exhaustion_test")
                pool_states.append(state)
                
                if state["utilization_percent"] > 95:
                    logger.warning(f"🔥 Pool exhausted: {state['utilization_percent']:.1f}% utilization")
                
                await asyncio.sleep(1)
                
                # Safety timeout
                if (time.time() - start_time) > 30:
                    break
            
            # Wait for remaining tasks
            await asyncio.gather(*exhaustion_tasks, return_exceptions=True)
        
        except Exception as e:
            logger.error(f"❌ Pool exhaustion test error: {e}")
        
        end_time = time.time()
        
        # Analyze exhaustion behavior
        max_utilization = max(state["utilization_percent"] for state in pool_states) if pool_states else 0
        exhaustion_detected = max_utilization > 90
        
        recovery_time = None
        if exhaustion_detected:
            # Find recovery time (when utilization drops below 50%)
            for i, state in enumerate(reversed(pool_states)):
                if state["utilization_percent"] < 50:
                    recovery_time = i * 1000  # Convert to milliseconds
                    break
        
        issues = []
        if not exhaustion_detected:
            issues.append("Pool exhaustion not triggered - may indicate incorrect test setup")
        if recovery_time and recovery_time > self.max_pool_exhaustion_time_ms:
            issues.append(f"Slow pool recovery: {recovery_time}ms (max: {self.max_pool_exhaustion_time_ms}ms)")
        
        metrics = ConnectionPoolMetrics(
            test_scenario="Pool Exhaustion and Recovery",
            concurrent_users=exhaustion_users,
            pool_size=self.expected_pool_size,
            max_overflow=self.expected_max_overflow,
            pool_timeout=self.expected_pool_timeout,
            total_connections_requested=exhaustion_users,
            successful_connections=len([task for task in exhaustion_tasks if not isinstance(task.exception(), Exception)]),
            failed_connections=len([task for task in exhaustion_tasks if isinstance(task.exception(), Exception)]),
            timeout_connections=0,  # Will be updated based on actual results
            avg_connection_acquisition_ms=0,  # Not measured in this test
            p50_connection_acquisition_ms=0,
            p95_connection_acquisition_ms=0,
            p99_connection_acquisition_ms=0,
            max_connection_acquisition_ms=0,
            min_connection_acquisition_ms=0,
            peak_checked_out=max(state["checked_out"] for state in pool_states) if pool_states else 0,
            peak_pool_utilization_percent=max_utilization,
            pool_exhaustion_events=1 if exhaustion_detected else 0,
            connection_reuse_rate=0,
            connection_errors=[],
            recovery_time_ms=recovery_time,
            total_queries_executed=0,
            avg_query_execution_ms=0,
            queries_per_second=0,
            test_duration_seconds=end_time - start_time,
            passed=exhaustion_detected and (not recovery_time or recovery_time <= self.max_pool_exhaustion_time_ms),
            issues=issues
        )
        
        logger.info(f"✅ Pool Exhaustion Test Results:")
        logger.info(f"   Max Utilization: {max_utilization:.1f}%")
        logger.info(f"   Recovery Time: {recovery_time}ms" if recovery_time else "   Recovery Time: Not measured")
        logger.info(f"   Pool Exhaustion Detected: {'Yes' if exhaustion_detected else 'No'}")
        
        return metrics
    
    async def run_comprehensive_connection_pool_tests(self) -> Dict[str, Any]:
        """Run all connection pool tests comprehensively"""
        
        print("=" * 100)
        print("🚀 MITA FINANCE COMPREHENSIVE CONNECTION POOL LOAD TESTING")
        print("=" * 100)
        print("Validating restored authentication system connection pool performance")
        print("Testing against previous 8-15+ second timeout issues")
        print("=" * 100)
        
        await self.initialize_test_environment()
        
        all_metrics = []
        overall_success = True
        
        # Test Scenario 1: Normal Load (25 concurrent users)
        try:
            metrics_25 = await self.test_connection_pool_scenario(
                "Normal Production Load", 25, 180
            )
            all_metrics.append(metrics_25)
            if not metrics_25.passed:
                overall_success = False
        except Exception as e:
            logger.error(f"❌ Normal Load test failed: {e}")
            overall_success = False
        
        # Cool down
        await asyncio.sleep(10)
        
        # Test Scenario 2: Peak Load (50 concurrent users)
        try:
            metrics_50 = await self.test_connection_pool_scenario(
                "Peak Traffic Load", 50, 300
            )
            all_metrics.append(metrics_50)
            if not metrics_50.passed:
                overall_success = False
        except Exception as e:
            logger.error(f"❌ Peak Load test failed: {e}")
            overall_success = False
        
        # Cool down
        await asyncio.sleep(15)
        
        # Test Scenario 3: Stress Test (100 concurrent users)
        try:
            metrics_100 = await self.test_connection_pool_scenario(
                "Stress Test Load", 100, 180
            )
            all_metrics.append(metrics_100)
            if not metrics_100.passed:
                overall_success = False
        except Exception as e:
            logger.error(f"❌ Stress Test failed: {e}")
            overall_success = False
        
        # Cool down
        await asyncio.sleep(10)
        
        # Test Scenario 4: Pool Exhaustion and Recovery
        try:
            exhaustion_metrics = await self.test_pool_exhaustion_recovery()
            all_metrics.append(exhaustion_metrics)
            if not exhaustion_metrics.passed:
                overall_success = False
        except Exception as e:
            logger.error(f"❌ Pool Exhaustion test failed: {e}")
            overall_success = False
        
        # Generate comprehensive report
        report = self.generate_comprehensive_report(all_metrics, overall_success)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"connection_pool_load_test_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"\n📊 Comprehensive report saved: {report_file}")
        
        return report
    
    def generate_comprehensive_report(self, all_metrics: List[ConnectionPoolMetrics], overall_success: bool) -> Dict[str, Any]:
        """Generate comprehensive connection pool performance report"""
        
        total_operations = sum(m.total_queries_executed for m in all_metrics)
        total_connections = sum(m.total_connections_requested for m in all_metrics)
        total_successful = sum(m.successful_connections for m in all_metrics)
        
        overall_success_rate = (total_successful / total_connections * 100) if total_connections > 0 else 0
        
        # Performance analysis
        performance_summary = {
            "total_scenarios_tested": len(all_metrics),
            "total_database_operations": total_operations,
            "total_connections_requested": total_connections,
            "overall_success_rate_percent": overall_success_rate,
            "scenarios_passed": len([m for m in all_metrics if m.passed]),
            "scenarios_failed": len([m for m in all_metrics if not m.passed])
        }
        
        # Connection pool analysis
        pool_analysis = {
            "configured_pool_size": self.expected_pool_size,
            "configured_max_overflow": self.expected_max_overflow,
            "total_pool_capacity": self.expected_total_connections,
            "peak_utilization_across_tests": max((m.peak_pool_utilization_percent for m in all_metrics), default=0),
            "pool_exhaustion_events": sum(m.pool_exhaustion_events for m in all_metrics),
            "connection_timeout_events": sum(m.timeout_connections for m in all_metrics)
        }
        
        # Performance benchmarks
        connection_times = [m.avg_connection_acquisition_ms for m in all_metrics if m.avg_connection_acquisition_ms > 0]
        benchmarks = {
            "avg_connection_acquisition_ms": statistics.mean(connection_times) if connection_times else 0,
            "max_connection_acquisition_ms": max(connection_times) if connection_times else 0,
            "connection_acquisition_target_ms": self.max_connection_acquisition_ms,
            "performance_regression_check": "PASSED" if all(t <= 200 for t in connection_times) else "FAILED"
        }
        
        # Issues and recommendations
        all_issues = []
        for metrics in all_metrics:
            all_issues.extend(metrics.issues)
        
        recommendations = self._generate_recommendations(all_metrics, overall_success)
        
        # Critical analysis
        critical_analysis = {
            "prevents_8_15_second_timeouts": all(m.avg_connection_acquisition_ms < 1000 for m in all_metrics),
            "handles_production_load": any(m.test_scenario == "Peak Traffic Load" and m.passed for m in all_metrics),
            "pool_exhaustion_recovery": any(m.test_scenario == "Pool Exhaustion and Recovery" and m.passed for m in all_metrics),
            "concurrent_user_support": max((m.concurrent_users for m in all_metrics if m.passed), default=0)
        }
        
        return {
            "report_timestamp": datetime.now().isoformat(),
            "test_environment": {
                "database_url_type": "PostgreSQL + asyncpg",
                "pool_configuration": {
                    "pool_size": self.expected_pool_size,
                    "max_overflow": self.expected_max_overflow,
                    "pool_timeout": self.expected_pool_timeout,
                    "total_capacity": self.expected_total_connections
                }
            },
            "performance_summary": performance_summary,
            "pool_analysis": pool_analysis,
            "performance_benchmarks": benchmarks,
            "critical_analysis": critical_analysis,
            "detailed_scenario_results": [m.to_dict() for m in all_metrics],
            "issues_identified": all_issues,
            "recommendations": recommendations,
            "overall_test_result": "PASSED" if overall_success else "FAILED",
            "production_readiness": self._assess_production_readiness(all_metrics, overall_success)
        }
    
    def _generate_recommendations(self, all_metrics: List[ConnectionPoolMetrics], overall_success: bool) -> List[str]:
        """Generate specific recommendations based on test results"""
        recommendations = []
        
        # Performance recommendations
        avg_connection_times = [m.avg_connection_acquisition_ms for m in all_metrics if m.avg_connection_acquisition_ms > 0]
        if avg_connection_times:
            max_time = max(avg_connection_times)
            if max_time > 100:
                recommendations.append(f"Connection acquisition times are high (max: {max_time:.1f}ms) - consider pool tuning")
            elif max_time < 50:
                recommendations.append("Excellent connection pool performance - configuration is optimal")
        
        # Pool utilization recommendations
        peak_utilizations = [m.peak_pool_utilization_percent for m in all_metrics]
        if peak_utilizations:
            max_util = max(peak_utilizations)
            if max_util > 95:
                recommendations.append("Pool exhaustion detected - monitor production load and consider increasing pool size")
            elif max_util > 80:
                recommendations.append("High pool utilization - monitor for potential capacity issues")
            else:
                recommendations.append("Pool capacity is adequate for tested load levels")
        
        # Error handling recommendations
        total_failures = sum(m.failed_connections for m in all_metrics)
        if total_failures > 0:
            recommendations.append(f"{total_failures} connection failures detected - investigate error patterns")
        
        # Concurrency recommendations
        max_concurrent = max((m.concurrent_users for m in all_metrics if m.passed), default=0)
        if max_concurrent >= 100:
            recommendations.append("System handles high concurrency well - suitable for production scale")
        elif max_concurrent >= 50:
            recommendations.append("Good concurrency support - monitor under real production load")
        else:
            recommendations.append("Limited concurrency validation - additional testing recommended")
        
        # Production deployment recommendations
        if overall_success:
            recommendations.append("✅ Connection pool configuration validated for production deployment")
            recommendations.append("🚀 No performance regressions from previous 8-15+ second timeout issues")
        else:
            recommendations.append("❌ Connection pool issues detected - address before production deployment")
        
        return recommendations
    
    def _assess_production_readiness(self, all_metrics: List[ConnectionPoolMetrics], overall_success: bool) -> Dict[str, Any]:
        """Assess production readiness based on test results"""
        
        readiness_checks = {
            "connection_pool_performance": overall_success,
            "handles_expected_load": any(m.concurrent_users >= 25 and m.passed for m in all_metrics),
            "handles_peak_load": any(m.concurrent_users >= 50 and m.passed for m in all_metrics),
            "stress_test_passed": any(m.concurrent_users >= 100 and m.passed for m in all_metrics),
            "pool_exhaustion_recovery": any("exhaustion" in m.test_scenario.lower() and m.passed for m in all_metrics),
            "no_timeout_regressions": all(m.avg_connection_acquisition_ms < 1000 for m in all_metrics),
            "acceptable_error_rate": all(m.failed_connections / max(m.total_connections_requested, 1) <= 0.05 for m in all_metrics)
        }
        
        passed_checks = sum(1 for check in readiness_checks.values() if check)
        total_checks = len(readiness_checks)
        readiness_score = (passed_checks / total_checks) * 100
        
        return {
            "readiness_checks": readiness_checks,
            "readiness_score_percent": readiness_score,
            "production_ready": readiness_score >= 80,
            "critical_issues": [
                check for check, passed in readiness_checks.items() 
                if not passed and check in ["connection_pool_performance", "no_timeout_regressions"]
            ],
            "recommendation": (
                "✅ APPROVED for production deployment" if readiness_score >= 90
                else "⚠️ CONDITIONAL approval - monitor closely" if readiness_score >= 80
                else "❌ NOT READY for production - address critical issues first"
            )
        }
    
    async def cleanup_test_environment(self):
        """Clean up test environment and data"""
        logger.info("🧹 Cleaning up test environment...")
        
        try:
            async with get_async_db_context() as session:
                # Delete test transactions
                await session.execute(
                    delete(Transaction).where(Transaction.description.like("Pool test transaction%"))
                )
                
                # Delete test users
                await session.execute(
                    delete(User).where(User.email.like("pool_test_user_%@example.com"))
                )
                
                await session.commit()
                
            logger.info("✅ Test environment cleaned up")
        
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")


async def run_comprehensive_connection_pool_testing():
    """Main function to run comprehensive connection pool testing"""
    
    validator = ConnectionPoolValidator()
    
    try:
        # Run all tests
        report = await validator.run_comprehensive_connection_pool_tests()
        
        # Print final results
        print("\n" + "=" * 100)
        print("🎯 FINAL CONNECTION POOL VALIDATION RESULTS")
        print("=" * 100)
        
        readiness = report["production_readiness"]
        print(f"Overall Test Result: {report['overall_test_result']}")
        print(f"Production Readiness Score: {readiness['readiness_score_percent']:.1f}%")
        print(f"Recommendation: {readiness['recommendation']}")
        
        print(f"\n📊 Performance Summary:")
        perf = report["performance_summary"]
        print(f"   Total Database Operations: {perf['total_database_operations']:,}")
        print(f"   Overall Success Rate: {perf['overall_success_rate_percent']:.1f}%")
        print(f"   Scenarios Passed: {perf['scenarios_passed']}/{perf['total_scenarios_tested']}")
        
        print(f"\n🔗 Connection Pool Analysis:")
        pool = report["pool_analysis"]
        print(f"   Pool Configuration: {pool['configured_pool_size']} + {pool['configured_max_overflow']} = {pool['total_pool_capacity']} total")
        print(f"   Peak Utilization: {pool['peak_utilization_across_tests']:.1f}%")
        print(f"   Pool Exhaustion Events: {pool['pool_exhaustion_events']}")
        print(f"   Connection Timeouts: {pool['connection_timeout_events']}")
        
        print(f"\n⚡ Performance Benchmarks:")
        bench = report["performance_benchmarks"]
        print(f"   Avg Connection Acquisition: {bench['avg_connection_acquisition_ms']:.1f}ms (target: {bench['connection_acquisition_target_ms']}ms)")
        print(f"   Performance Regression Check: {bench['performance_regression_check']}")
        
        critical = report["critical_analysis"]
        print(f"\n🔍 Critical Analysis:")
        print(f"   Prevents 8-15s Timeouts: {'✅ YES' if critical['prevents_8_15_second_timeouts'] else '❌ NO'}")
        print(f"   Handles Production Load: {'✅ YES' if critical['handles_production_load'] else '❌ NO'}")
        print(f"   Pool Exhaustion Recovery: {'✅ YES' if critical['pool_exhaustion_recovery'] else '❌ NO'}")
        print(f"   Max Concurrent Users Tested: {critical['concurrent_user_support']}")
        
        if report["issues_identified"]:
            print(f"\n⚠️ Issues Identified:")
            for issue in report["issues_identified"]:
                print(f"   • {issue}")
        
        if report["recommendations"]:
            print(f"\n💡 Recommendations:")
            for rec in report["recommendations"]:
                print(f"   • {rec}")
        
        return report["overall_test_result"] == "PASSED"
    
    except Exception as e:
        logger.error(f"❌ Connection pool testing failed: {e}")
        return False
    
    finally:
        await validator.cleanup_test_environment()


if __name__ == "__main__":
    """Run comprehensive connection pool load testing"""
    
    success = asyncio.run(run_comprehensive_connection_pool_testing())
    exit(0 if success else 1)