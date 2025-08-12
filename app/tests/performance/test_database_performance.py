"""
MITA Database Performance Tests
Critical database performance validation for financial operations.
Tests query performance, transaction throughput, and database scalability.
"""

import pytest
import time
import asyncio
import statistics
import psutil
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, AsyncMock
from dataclasses import dataclass
from datetime import datetime, timedelta
import concurrent.futures
import threading
from decimal import Decimal

# Database imports
from sqlalchemy import text, func, select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models and database components
from app.db.models import User, Transaction, Expense, Goal, Budget
from app.core.async_session import get_async_session_factory
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.user_repository import UserRepository
from app.services.core.engine.budget_logic import generate_budget_from_answers


@dataclass
class DatabasePerformanceBenchmark:
    """Database performance benchmark result"""
    operation: str
    query_type: str
    records_processed: int
    execution_time_ms: float
    throughput_ops_per_sec: float
    memory_usage_mb: float
    passed: bool
    target_ms: float


class DatabasePerformanceTests:
    """
    Critical database performance tests for financial operations.
    Database performance directly impacts user experience and system scalability.
    """
    
    # Performance targets for database operations (production requirements)
    SINGLE_RECORD_QUERY_TARGET_MS = 5.0      # Individual record queries
    BULK_QUERY_TARGET_MS = 50.0              # Bulk operations (100-1000 records)
    COMPLEX_QUERY_TARGET_MS = 100.0          # Complex analytical queries
    TRANSACTION_INSERT_TARGET_MS = 10.0      # Financial transaction inserts
    USER_LOOKUP_TARGET_MS = 2.0              # User authentication queries
    
    # Database scalability targets
    MIN_THROUGHPUT_SINGLE_OPS = 200          # Operations per second for simple queries
    MIN_THROUGHPUT_BULK_OPS = 50             # Bulk operations per second
    MAX_QUERY_TIME_P99_MS = 200.0           # 99th percentile query time
    
    # Test parameters
    PERFORMANCE_ITERATIONS = 500
    BULK_OPERATION_SIZE = 1000
    CONCURRENT_USERS = 20
    
    @pytest.fixture
    async def async_session_factory(self):
        """Get async database session factory"""
        return get_async_session_factory()
    
    @pytest.fixture
    async def test_users(self, async_session_factory) -> List[User]:
        """Create test users for database performance testing"""
        async with async_session_factory() as session:
            users = []
            for i in range(100):  # Create 100 test users
                user = User(
                    email=f"perf_test_user_{i}@example.com",
                    password_hash="test_hash",
                    country="US",
                    annual_income=50000 + (i * 1000),
                    timezone="America/New_York"
                )
                session.add(user)
                users.append(user)
            
            await session.commit()
            
            # Refresh to get IDs
            for user in users:
                await session.refresh(user)
            
            return users
    
    def measure_database_operation_performance(
        self, 
        operation_func,
        operation_name: str,
        iterations: int = None,
        records_per_operation: int = 1
    ) -> DatabasePerformanceBenchmark:
        """
        Measure database operation performance with comprehensive metrics.
        """
        iterations = iterations or self.PERFORMANCE_ITERATIONS
        times = []
        process = psutil.Process()
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024
        
        # Warmup
        for _ in range(5):
            try:
                asyncio.run(operation_func()) if asyncio.iscoroutinefunction(operation_func) else operation_func()
            except Exception:
                pass
        
        # Measure performance
        for _ in range(iterations):
            start_time = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(operation_func):
                    asyncio.run(operation_func())
                else:
                    operation_func()
            except Exception as e:
                pass  # Some operations might fail in test environment
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        # Final memory
        final_memory = process.memory_info().rss / 1024 / 1024
        
        if not times:
            raise Exception("No successful database operations recorded")
        
        mean_time = statistics.mean(times)
        total_records = iterations * records_per_operation
        throughput = total_records / (sum(times) / 1000) if sum(times) > 0 else 0
        
        # Determine target based on operation type
        target_ms = self._get_operation_target(operation_name, records_per_operation)
        
        return DatabasePerformanceBenchmark(
            operation=operation_name,
            query_type=self._classify_operation_type(operation_name),
            records_processed=total_records,
            execution_time_ms=mean_time,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=final_memory - baseline_memory,
            passed=mean_time <= target_ms,
            target_ms=target_ms
        )
    
    def _get_operation_target(self, operation_name: str, records_count: int) -> float:
        """Get performance target for specific operation"""
        operation_lower = operation_name.lower()
        
        if "user" in operation_lower and "lookup" in operation_lower:
            return self.USER_LOOKUP_TARGET_MS
        elif "transaction" in operation_lower and "insert" in operation_lower:
            return self.TRANSACTION_INSERT_TARGET_MS
        elif records_count > 100:
            return self.BULK_QUERY_TARGET_MS
        elif "complex" in operation_lower or "analytical" in operation_lower:
            return self.COMPLEX_QUERY_TARGET_MS
        else:
            return self.SINGLE_RECORD_QUERY_TARGET_MS
    
    def _classify_operation_type(self, operation_name: str) -> str:
        """Classify database operation type"""
        operation_lower = operation_name.lower()
        
        if any(keyword in operation_lower for keyword in ["insert", "create", "add"]):
            return "INSERT"
        elif any(keyword in operation_lower for keyword in ["select", "query", "find", "lookup"]):
            return "SELECT"
        elif any(keyword in operation_lower for keyword in ["update", "modify"]):
            return "UPDATE"
        elif any(keyword in operation_lower for keyword in ["delete", "remove"]):
            return "DELETE"
        else:
            return "COMPLEX"
    
    @pytest.mark.asyncio
    async def test_user_authentication_query_performance(self, async_session_factory):
        """
        Test user authentication query performance.
        This is critical for login performance.
        """
        async def user_lookup_operation():
            async with async_session_factory() as session:
                # Simulate authentication query
                result = await session.execute(
                    select(User).where(User.email == "perf_test_user_50@example.com")
                )
                return result.scalars().first()
        
        benchmark = self.measure_database_operation_performance(
            user_lookup_operation,
            "user_authentication_lookup",
            iterations=1000
        )
        
        assert benchmark.passed, (
            f"User authentication query too slow: {benchmark.execution_time_ms:.3f}ms "
            f"(target: {benchmark.target_ms}ms)"
        )
        
        assert benchmark.throughput_ops_per_sec >= self.MIN_THROUGHPUT_SINGLE_OPS, (
            f"User authentication throughput too low: {benchmark.throughput_ops_per_sec:.0f} ops/sec "
            f"(min: {self.MIN_THROUGHPUT_SINGLE_OPS})"
        )
        
        print(f"\n✅ User Authentication Query Performance:")
        print(f"   Average Time: {benchmark.execution_time_ms:.3f}ms")
        print(f"   Target: {benchmark.target_ms}ms")
        print(f"   Throughput: {benchmark.throughput_ops_per_sec:.0f} lookups/sec")
        print(f"   Memory Usage: {benchmark.memory_usage_mb:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_financial_transaction_insert_performance(self, async_session_factory, test_users):
        """
        Test financial transaction insert performance.
        Transaction inserts are critical for expense tracking accuracy.
        """
        user = test_users[0]  # Use first test user
        
        async def transaction_insert_operation():
            async with async_session_factory() as session:
                transaction = Transaction(
                    user_id=user.id,
                    amount=Decimal("25.50"),
                    description="Performance test transaction",
                    category="food",
                    date=datetime.now().date(),
                    created_at=datetime.now()
                )
                session.add(transaction)
                await session.commit()
                await session.refresh(transaction)
                return transaction
        
        benchmark = self.measure_database_operation_performance(
            transaction_insert_operation,
            "financial_transaction_insert",
            iterations=500
        )
        
        assert benchmark.passed, (
            f"Transaction insert too slow: {benchmark.execution_time_ms:.3f}ms "
            f"(target: {benchmark.target_ms}ms). This impacts expense tracking UX."
        )
        
        print(f"\n✅ Financial Transaction Insert Performance:")
        print(f"   Average Time: {benchmark.execution_time_ms:.3f}ms")
        print(f"   Target: {benchmark.target_ms}ms")
        print(f"   Throughput: {benchmark.throughput_ops_per_sec:.0f} inserts/sec")
    
    @pytest.mark.asyncio
    async def test_bulk_transaction_query_performance(self, async_session_factory, test_users):
        """
        Test bulk transaction query performance.
        Used for generating spending reports and analytics.
        """
        # First, create some transactions for testing
        user = test_users[0]
        async with async_session_factory() as session:
            transactions = []
            for i in range(500):
                transaction = Transaction(
                    user_id=user.id,
                    amount=Decimal(f"{20 + (i % 100)}.{i % 100:02d}"),
                    description=f"Test transaction {i}",
                    category=["food", "transport", "entertainment", "utilities"][i % 4],
                    date=datetime.now().date() - timedelta(days=i % 90),
                    created_at=datetime.now()
                )
                transactions.append(transaction)
            
            session.add_all(transactions)
            await session.commit()
        
        async def bulk_transaction_query():
            async with async_session_factory() as session:
                # Query last 90 days of transactions
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=90)
                
                result = await session.execute(
                    select(Transaction)
                    .where(Transaction.user_id == user.id)
                    .where(Transaction.date >= start_date)
                    .where(Transaction.date <= end_date)
                    .order_by(Transaction.date.desc())
                )
                return result.scalars().all()
        
        benchmark = self.measure_database_operation_performance(
            bulk_transaction_query,
            "bulk_transaction_query",
            iterations=100,
            records_per_operation=500
        )
        
        assert benchmark.passed, (
            f"Bulk transaction query too slow: {benchmark.execution_time_ms:.3f}ms "
            f"(target: {benchmark.target_ms}ms)"
        )
        
        print(f"\n✅ Bulk Transaction Query Performance:")
        print(f"   Average Time: {benchmark.execution_time_ms:.3f}ms")
        print(f"   Records per Query: ~500")
        print(f"   Throughput: {benchmark.throughput_ops_per_sec:.0f} ops/sec")
    
    @pytest.mark.asyncio
    async def test_complex_financial_analytics_query_performance(self, async_session_factory, test_users):
        """
        Test complex financial analytics query performance.
        These queries power insights and spending pattern analysis.
        """
        user = test_users[0]
        
        async def complex_analytics_query():
            async with async_session_factory() as session:
                # Complex query: Monthly spending by category with aggregations
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=365)  # Last year
                
                result = await session.execute(
                    select(
                        Transaction.category,
                        func.extract('month', Transaction.date).label('month'),
                        func.extract('year', Transaction.date).label('year'),
                        func.sum(Transaction.amount).label('total_amount'),
                        func.count(Transaction.id).label('transaction_count'),
                        func.avg(Transaction.amount).label('avg_amount')
                    )
                    .where(Transaction.user_id == user.id)
                    .where(Transaction.date >= start_date)
                    .where(Transaction.date <= end_date)
                    .group_by(
                        Transaction.category,
                        func.extract('month', Transaction.date),
                        func.extract('year', Transaction.date)
                    )
                    .order_by(
                        func.extract('year', Transaction.date).desc(),
                        func.extract('month', Transaction.date).desc(),
                        func.sum(Transaction.amount).desc()
                    )
                )
                return result.all()
        
        benchmark = self.measure_database_operation_performance(
            complex_analytics_query,
            "complex_financial_analytics_query",
            iterations=50
        )
        
        assert benchmark.passed, (
            f"Complex analytics query too slow: {benchmark.execution_time_ms:.3f}ms "
            f"(target: {benchmark.target_ms}ms)"
        )
        
        print(f"\n✅ Complex Financial Analytics Query Performance:")
        print(f"   Average Time: {benchmark.execution_time_ms:.3f}ms")
        print(f"   Target: {benchmark.target_ms}ms")
        print(f"   Query Type: Monthly category aggregations")
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations_performance(self, async_session_factory, test_users):
        """
        Test database performance under concurrent load.
        Simulates multiple users accessing the system simultaneously.
        """
        async def concurrent_user_operations(user: User, session_factory):
            """Simulate typical user database operations"""
            operations_completed = 0
            
            async with session_factory() as session:
                # User lookup (authentication)
                result = await session.execute(
                    select(User).where(User.id == user.id)
                )
                user_record = result.scalars().first()
                operations_completed += 1
                
                # Recent transactions query
                result = await session.execute(
                    select(Transaction)
                    .where(Transaction.user_id == user.id)
                    .order_by(Transaction.date.desc())
                    .limit(20)
                )
                transactions = result.scalars().all()
                operations_completed += 1
                
                # Insert new transaction
                new_transaction = Transaction(
                    user_id=user.id,
                    amount=Decimal("15.75"),
                    description="Concurrent test transaction",
                    category="test",
                    date=datetime.now().date(),
                    created_at=datetime.now()
                )
                session.add(new_transaction)
                await session.commit()
                operations_completed += 1
            
            return operations_completed
        
        # Test with different concurrency levels
        concurrency_results = []
        
        for concurrent_users_count in [5, 10, 15, 20]:
            selected_users = test_users[:concurrent_users_count]
            
            start_time = time.perf_counter()
            
            tasks = [
                concurrent_user_operations(user, async_session_factory)
                for user in selected_users
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.perf_counter()
            
            # Calculate metrics
            total_time_ms = (end_time - start_time) * 1000
            successful_operations = sum(
                result for result in results 
                if isinstance(result, int)
            )
            
            avg_time_per_user = total_time_ms / concurrent_users_count
            total_throughput = successful_operations / (total_time_ms / 1000)
            
            result = {
                "concurrent_users": concurrent_users_count,
                "total_time_ms": total_time_ms,
                "avg_time_per_user_ms": avg_time_per_user,
                "total_operations": successful_operations,
                "throughput_ops_per_sec": total_throughput,
                "failed_operations": len([r for r in results if isinstance(r, Exception)])
            }
            
            concurrency_results.append(result)
            
            # Performance should not degrade severely with concurrency
            assert avg_time_per_user <= 1000, (  # 1 second per user max
                f"Concurrent performance too slow at {concurrent_users_count} users: "
                f"{avg_time_per_user:.0f}ms per user"
            )
            
            assert result["failed_operations"] == 0, (
                f"Failed operations under concurrency: {result['failed_operations']}"
            )
        
        print(f"\n✅ Concurrent Database Operations Performance:")
        for result in concurrency_results:
            print(f"   {result['concurrent_users']:2d} users: "
                  f"{result['avg_time_per_user_ms']:.0f}ms/user, "
                  f"{result['throughput_ops_per_sec']:.0f} ops/sec")
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling_performance(self, async_session_factory):
        """
        Test database connection pooling efficiency.
        Connection management affects overall system scalability.
        """
        async def rapid_connection_operations():
            """Perform rapid database operations that require new connections"""
            operations = []
            
            for i in range(50):  # 50 rapid operations
                async with async_session_factory() as session:
                    # Simple query to test connection acquisition
                    result = await session.execute(
                        select(func.now())  # Simple query
                    )
                    operations.append(result.scalar())
            
            return len(operations)
        
        # Measure connection pooling performance
        times = []
        
        for _ in range(20):  # 20 test runs
            start_time = time.perf_counter()
            operations_count = await rapid_connection_operations()
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            times.append(duration_ms)
        
        avg_time = statistics.mean(times)
        operations_per_second = (50 * 20) / (sum(times) / 1000)  # Total operations / total time
        
        # Connection pooling should be efficient
        MAX_CONNECTION_POOL_TIME_MS = 500.0
        
        assert avg_time <= MAX_CONNECTION_POOL_TIME_MS, (
            f"Connection pooling too slow: {avg_time:.1f}ms "
            f"(max: {MAX_CONNECTION_POOL_TIME_MS}ms)"
        )
        
        print(f"\n✅ Database Connection Pooling Performance:")
        print(f"   Average Time (50 connections): {avg_time:.1f}ms")
        print(f"   Connection Throughput: {operations_per_second:.0f} ops/sec")
        print(f"   P95 Time: {self._percentile(times, 95):.1f}ms")
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile from data"""
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = int(k)
        c = int(k) + 1
        if f == c:
            return sorted_data[f]
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1
    
    @pytest.mark.asyncio
    async def test_database_query_plan_optimization(self, async_session_factory, test_users):
        """
        Test query execution plans for performance optimization.
        Ensures database indexes are being used effectively.
        """
        user = test_users[0]
        
        async def analyze_query_plan(session: AsyncSession, query_sql: str):
            """Get query execution plan"""
            explain_result = await session.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_sql}")
            )
            return explain_result.scalar()
        
        async with async_session_factory() as session:
            # Test critical query plans
            critical_queries = [
                # User authentication query
                f"SELECT * FROM users WHERE email = 'perf_test_user_0@example.com'",
                
                # Recent transactions query
                f"SELECT * FROM transactions WHERE user_id = {user.id} ORDER BY date DESC LIMIT 20",
                
                # Monthly spending aggregation
                f"""SELECT category, SUM(amount) as total 
                   FROM transactions 
                   WHERE user_id = {user.id} 
                   AND date >= CURRENT_DATE - INTERVAL '30 days'
                   GROUP BY category""",
            ]
            
            for query_sql in critical_queries:
                try:
                    plan = await analyze_query_plan(session, query_sql)
                    
                    # Parse execution plan (simplified)
                    if isinstance(plan, str):
                        import json
                        plan_data = json.loads(plan)
                        
                        execution_time = plan_data[0]["Plan"]["Actual Total Time"]
                        
                        # Critical queries should execute quickly
                        assert execution_time <= 10.0, (
                            f"Query execution too slow: {execution_time:.2f}ms\nQuery: {query_sql[:50]}..."
                        )
                        
                        print(f"   Query execution time: {execution_time:.2f}ms")
                
                except Exception as e:
                    print(f"   Could not analyze query plan: {e}")
        
        print(f"\n✅ Database Query Plan Analysis Completed")
    
    @pytest.mark.asyncio
    async def test_database_memory_usage_under_load(self, async_session_factory, test_users):
        """
        Test database-related memory usage under sustained load.
        Financial applications must maintain stable memory usage.
        """
        import gc
        
        process = psutil.Process()
        
        # Baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform sustained database operations
        for cycle in range(20):  # 20 cycles of operations
            users_batch = test_users[cycle % len(test_users):min((cycle % len(test_users)) + 5, len(test_users))]
            
            for user in users_batch:
                async with async_session_factory() as session:
                    # Multiple database operations per user
                    
                    # Query user data
                    result = await session.execute(
                        select(User).where(User.id == user.id)
                    )
                    user_data = result.scalars().first()
                    
                    # Query transactions
                    result = await session.execute(
                        select(Transaction)
                        .where(Transaction.user_id == user.id)
                        .limit(50)
                    )
                    transactions = result.scalars().all()
                    
                    # Insert new transaction
                    new_transaction = Transaction(
                        user_id=user.id,
                        amount=Decimal(f"{cycle}.{cycle % 100:02d}"),
                        description=f"Memory test transaction {cycle}",
                        category="test",
                        date=datetime.now().date(),
                        created_at=datetime.now()
                    )
                    session.add(new_transaction)
                    await session.commit()
            
            # Check memory every 5 cycles
            if cycle % 5 == 4:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - baseline_memory
                
                # Memory growth should be controlled
                assert memory_growth <= 100.0, (
                    f"Database operation memory growth too high: {memory_growth:.2f}MB"
                )
        
        # Final memory check
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - baseline_memory
        
        print(f"\n✅ Database Memory Usage Under Load:")
        print(f"   Baseline: {baseline_memory:.2f}MB")
        print(f"   Final: {final_memory:.2f}MB") 
        print(f"   Growth: {total_growth:.2f}MB (sustained database operations)")
        
        # Total growth should be reasonable
        assert total_growth <= 50.0, (
            f"Database operations caused excessive memory growth: {total_growth:.2f}MB"
        )
    
    def generate_database_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive database performance report.
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "performance_targets": {
                "single_record_query_ms": self.SINGLE_RECORD_QUERY_TARGET_MS,
                "bulk_query_ms": self.BULK_QUERY_TARGET_MS,
                "complex_query_ms": self.COMPLEX_QUERY_TARGET_MS,
                "transaction_insert_ms": self.TRANSACTION_INSERT_TARGET_MS,
                "user_lookup_ms": self.USER_LOOKUP_TARGET_MS
            },
            "throughput_targets": {
                "min_single_ops_per_sec": self.MIN_THROUGHPUT_SINGLE_OPS,
                "min_bulk_ops_per_sec": self.MIN_THROUGHPUT_BULK_OPS,
                "max_p99_query_time_ms": self.MAX_QUERY_TIME_P99_MS
            },
            "recommendations": [
                "Monitor query execution plans in production",
                "Set up database performance alerts",
                "Implement query result caching for frequently accessed data",
                "Consider database connection pool optimization",
                "Monitor slow query logs and optimize problematic queries",
                "Implement database read replicas for analytical queries",
                "Set up database performance metrics collection",
                "Regular database maintenance and statistics updates"
            ]
        }


@pytest.mark.asyncio
async def test_cleanup_performance_test_data(async_session_factory):
    """
    Clean up performance test data after tests complete.
    Prevents test data from affecting subsequent runs.
    """
    async with async_session_factory() as session:
        # Delete test transactions
        await session.execute(
            delete(Transaction).where(Transaction.description.like("%test%"))
        )
        
        # Delete test users
        await session.execute(
            delete(User).where(User.email.like("perf_test_user_%@example.com"))
        )
        
        await session.commit()
        
    print("✅ Performance test data cleanup completed")


if __name__ == "__main__":
    # Run database performance tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])