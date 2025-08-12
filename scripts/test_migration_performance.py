#!/usr/bin/env python3
"""
Migration Performance Testing for MITA Financial Application

This script tests migration performance and validates rollback functionality:
- Measures migration execution time
- Tests with various data volumes
- Validates rollback performance
- Checks for lock contention
- Monitors resource utilization

Usage:
  python test_migration_performance.py --test-size=small
  python test_migration_performance.py --test-size=large --with-load
  python test_migration_performance.py --rollback-test
"""

import argparse
import datetime
import json
import logging
import os
import psutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Dict, List, Optional
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationPerformanceTester:
    """Test migration performance and rollback functionality"""
    
    def __init__(self):
        self.test_db_url = os.environ.get("TEST_DATABASE_URL")
        self.primary_db_url = os.environ.get("DATABASE_URL")
        
        if not self.test_db_url:
            raise RuntimeError("TEST_DATABASE_URL must be set for performance testing")
        
        self.performance_metrics = {}
        self.monitoring_active = False
    
    def create_test_data(self, size: str = "small") -> Dict[str, int]:
        """Create test data for migration performance testing"""
        logger.info(f"Creating {size} test dataset")
        
        data_sizes = {
            "small": {"users": 1000, "transactions": 10000, "goals": 2000},
            "medium": {"users": 10000, "transactions": 100000, "goals": 20000},
            "large": {"users": 50000, "transactions": 1000000, "goals": 100000}
        }
        
        counts = data_sizes.get(size, data_sizes["small"])
        
        conn = psycopg2.connect(self.test_db_url)
        try:
            with conn.cursor() as cur:
                # Clear existing test data
                cur.execute("TRUNCATE users, transactions, goals, push_tokens CASCADE")
                
                # Create users
                logger.info(f"Creating {counts['users']} users...")
                for i in range(counts['users']):
                    cur.execute("""
                        INSERT INTO users (id, email, password_hash, annual_income)
                        VALUES (gen_random_uuid(), %s, %s, %s)
                    """, (f"test{i}@example.com", "hashed_password", 50000 + (i * 10)))
                    
                    if (i + 1) % 1000 == 0:
                        conn.commit()
                        logger.info(f"Created {i + 1} users")
                
                # Get user IDs for foreign keys
                cur.execute("SELECT id FROM users LIMIT %s", (counts['users'],))
                user_ids = [row[0] for row in cur.fetchall()]
                
                # Create transactions
                logger.info(f"Creating {counts['transactions']} transactions...")
                import random
                
                for i in range(counts['transactions']):
                    user_id = random.choice(user_ids)
                    amount = round(random.uniform(1.0, 1000.0), 2)
                    
                    cur.execute("""
                        INSERT INTO transactions (id, user_id, category, amount, currency)
                        VALUES (gen_random_uuid(), %s, %s, %s, %s)
                    """, (user_id, "test_category", amount, "USD"))
                    
                    if (i + 1) % 5000 == 0:
                        conn.commit()
                        logger.info(f"Created {i + 1} transactions")
                
                # Create goals
                logger.info(f"Creating {counts['goals']} goals...")
                for i in range(counts['goals']):
                    user_id = random.choice(user_ids)
                    target = round(random.uniform(100.0, 50000.0), 2)
                    saved = round(target * random.uniform(0, 0.8), 2)
                    
                    cur.execute("""
                        INSERT INTO goals (id, user_id, title, target_amount, saved_amount)
                        VALUES (gen_random_uuid(), %s, %s, %s, %s)
                    """, (user_id, f"Test Goal {i}", target, saved))
                    
                    if (i + 1) % 1000 == 0:
                        conn.commit()
                        logger.info(f"Created {i + 1} goals")
                
                conn.commit()
                
        finally:
            conn.close()
        
        logger.info(f"Test data creation completed: {counts}")
        return counts
    
    def start_resource_monitoring(self):
        """Start monitoring system resources during migration"""
        self.monitoring_active = True
        self.resource_data = []
        
        def monitor_resources():
            while self.monitoring_active:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                
                timestamp = datetime.datetime.utcnow()
                
                self.resource_data.append({
                    "timestamp": timestamp.isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "disk_read_mb": disk_io.read_bytes / (1024**2) if disk_io else 0,
                    "disk_write_mb": disk_io.write_bytes / (1024**2) if disk_io else 0
                })
                
                time.sleep(5)  # Sample every 5 seconds
        
        self.monitoring_thread = threading.Thread(target=monitor_resources)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info("Resource monitoring started")
    
    def stop_resource_monitoring(self):
        """Stop resource monitoring and return data"""
        self.monitoring_active = False
        if hasattr(self, 'monitoring_thread'):
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Resource monitoring stopped")
        return getattr(self, 'resource_data', [])
    
    def measure_database_locks(self, duration: int = 30) -> List[Dict]:
        """Monitor database locks during migration"""
        lock_data = []
        start_time = time.time()
        
        conn = psycopg2.connect(self.test_db_url)
        try:
            while time.time() - start_time < duration:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            pid,
                            mode,
                            locktype,
                            relation::regclass as relation_name,
                            granted,
                            query_start,
                            state
                        FROM pg_locks l
                        LEFT JOIN pg_stat_activity a ON l.pid = a.pid
                        WHERE l.pid != pg_backend_pid()
                        ORDER BY query_start
                    """)
                    
                    locks = []
                    for row in cur.fetchall():
                        locks.append({
                            "pid": row[0],
                            "mode": row[1],
                            "locktype": row[2],
                            "relation": str(row[3]) if row[3] else None,
                            "granted": row[4],
                            "query_start": row[5].isoformat() if row[5] else None,
                            "state": row[6]
                        })
                    
                    lock_data.append({
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "locks": locks,
                        "total_locks": len(locks),
                        "blocked_locks": len([l for l in locks if not l["granted"]])
                    })
                
                time.sleep(2)
                
        finally:
            conn.close()
        
        return lock_data
    
    def test_migration_performance(self, target: str = "head") -> Dict[str, any]:
        """Test migration performance with monitoring"""
        logger.info(f"Starting migration performance test to {target}")
        
        # Get initial database state
        initial_stats = self._get_database_stats()
        
        # Start monitoring
        self.start_resource_monitoring()
        
        # Monitor locks in separate thread
        lock_monitoring_active = True
        lock_data = []
        
        def monitor_locks():
            nonlocal lock_data
            lock_data = self.measure_database_locks(180)  # Monitor for up to 3 minutes
        
        lock_thread = threading.Thread(target=monitor_locks)
        lock_thread.daemon = True
        lock_thread.start()
        
        # Execute migration with timing
        start_time = time.time()
        migration_start = datetime.datetime.utcnow()
        
        try:
            # Run alembic migration
            result = subprocess.run([
                "alembic", "upgrade", target, "--verbose"
            ], 
            capture_output=True, 
            text=True, 
            timeout=1800,  # 30 minute timeout
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=dict(os.environ, DATABASE_URL=self.test_db_url)
            )
            
            migration_duration = time.time() - start_time
            migration_success = result.returncode == 0
            
        except subprocess.TimeoutExpired:
            migration_duration = time.time() - start_time  
            migration_success = False
            result = type('obj', (object,), {
                'stdout': 'Migration timed out',
                'stderr': 'Migration exceeded 30 minute limit',
                'returncode': -1
            })
        
        # Stop monitoring
        resource_data = self.stop_resource_monitoring()
        lock_thread.join(timeout=5)
        
        # Get final database state
        final_stats = self._get_database_stats()
        
        # Analyze results
        performance_results = {
            "migration_target": target,
            "start_time": migration_start.isoformat(),
            "duration_seconds": migration_duration,
            "success": migration_success,
            "initial_stats": initial_stats,
            "final_stats": final_stats,
            "alembic_output": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            },
            "resource_usage": {
                "samples": len(resource_data),
                "max_cpu_percent": max((r["cpu_percent"] for r in resource_data), default=0),
                "max_memory_percent": max((r["memory_percent"] for r in resource_data), default=0),
                "avg_cpu_percent": sum(r["cpu_percent"] for r in resource_data) / max(len(resource_data), 1),
                "peak_memory_gb": max((r["memory_used_gb"] for r in resource_data), default=0)
            },
            "lock_analysis": {
                "samples": len(lock_data),
                "max_concurrent_locks": max((l["total_locks"] for l in lock_data), default=0),
                "max_blocked_locks": max((l["blocked_locks"] for l in lock_data), default=0),
                "lock_timeline": lock_data
            }
        }
        
        logger.info(f"Migration performance test completed:")
        logger.info(f"  Duration: {migration_duration:.2f} seconds")
        logger.info(f"  Success: {migration_success}")
        logger.info(f"  Max CPU: {performance_results['resource_usage']['max_cpu_percent']:.1f}%")
        logger.info(f"  Max Memory: {performance_results['resource_usage']['max_memory_percent']:.1f}%")
        
        return performance_results
    
    def test_rollback_performance(self, target: str) -> Dict[str, any]:
        """Test rollback performance"""
        logger.info(f"Starting rollback performance test to {target}")
        
        # Get current revision
        current_revision = self._get_current_revision()
        
        # Start monitoring
        self.start_resource_monitoring()
        
        # Execute rollback with timing
        start_time = time.time()
        rollback_start = datetime.datetime.utcnow()
        
        try:
            result = subprocess.run([
                "alembic", "downgrade", target, "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=dict(os.environ, DATABASE_URL=self.test_db_url)
            )
            
            rollback_duration = time.time() - start_time
            rollback_success = result.returncode == 0
            
        except subprocess.TimeoutExpired:
            rollback_duration = time.time() - start_time
            rollback_success = False
            result = type('obj', (object,), {
                'stdout': 'Rollback timed out',
                'stderr': 'Rollback exceeded 30 minute limit',  
                'returncode': -1
            })
        
        # Stop monitoring
        resource_data = self.stop_resource_monitoring()
        
        # Validate rollback result
        final_revision = self._get_current_revision()
        final_stats = self._get_database_stats()
        
        rollback_results = {
            "rollback_target": target,
            "start_revision": current_revision,
            "final_revision": final_revision,
            "start_time": rollback_start.isoformat(),
            "duration_seconds": rollback_duration,
            "success": rollback_success,
            "final_stats": final_stats,
            "alembic_output": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            },
            "resource_usage": {
                "max_cpu_percent": max((r["cpu_percent"] for r in resource_data), default=0),
                "max_memory_percent": max((r["memory_percent"] for r in resource_data), default=0),
                "avg_cpu_percent": sum(r["cpu_percent"] for r in resource_data) / max(len(resource_data), 1)
            }
        }
        
        logger.info(f"Rollback performance test completed:")
        logger.info(f"  Duration: {rollback_duration:.2f} seconds")
        logger.info(f"  Success: {rollback_success}")
        logger.info(f"  Revision: {current_revision} -> {final_revision}")
        
        return rollback_results
    
    def test_concurrent_load(self, duration: int = 60):
        """Simulate concurrent database load during migration"""
        logger.info(f"Starting concurrent load test for {duration} seconds")
        
        load_active = True
        operation_counts = {"reads": 0, "writes": 0, "errors": 0}
        
        def simulate_reads():
            conn = psycopg2.connect(self.test_db_url)
            try:
                while load_active:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("SELECT COUNT(*) FROM users")
                            cur.execute("SELECT SUM(amount) FROM transactions LIMIT 100")
                            cur.execute("SELECT * FROM goals ORDER BY created_at DESC LIMIT 10")
                        operation_counts["reads"] += 3
                        time.sleep(0.1)
                    except Exception:
                        operation_counts["errors"] += 1
                        time.sleep(0.5)
            finally:
                conn.close()
        
        def simulate_writes():
            conn = psycopg2.connect(self.test_db_url)
            try:
                while load_active:
                    try:
                        with conn.cursor() as cur:
                            # Simulate typical write operations
                            cur.execute("""
                                INSERT INTO push_tokens (id, user_id, token, platform)
                                SELECT gen_random_uuid(), u.id, 'test_token_' || random(), 'test'
                                FROM users u ORDER BY random() LIMIT 1
                            """)
                            conn.commit()
                        operation_counts["writes"] += 1
                        time.sleep(0.5)
                    except Exception:
                        operation_counts["errors"] += 1
                        conn.rollback()
                        time.sleep(1)
            finally:
                conn.close()
        
        # Start load threads
        read_threads = [threading.Thread(target=simulate_reads) for _ in range(3)]
        write_threads = [threading.Thread(target=simulate_writes) for _ in range(2)]
        
        for t in read_threads + write_threads:
            t.daemon = True
            t.start()
        
        time.sleep(duration)
        load_active = False
        
        # Wait for threads to complete
        for t in read_threads + write_threads:
            t.join(timeout=5)
        
        logger.info(f"Concurrent load test completed: {operation_counts}")
        return operation_counts
    
    def _get_database_stats(self) -> Dict[str, any]:
        """Get current database statistics"""
        conn = psycopg2.connect(self.test_db_url)
        stats = {}
        
        try:
            with conn.cursor() as cur:
                # Table counts
                tables = ["users", "transactions", "goals", "push_tokens", "subscriptions"]
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        stats[f"{table}_count"] = cur.fetchone()[0]
                    except psycopg2.Error:
                        stats[f"{table}_count"] = "error"
                
                # Database size
                cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                stats["database_size"] = cur.fetchone()[0]
                
                # Transaction totals
                try:
                    cur.execute("SELECT SUM(amount) FROM transactions")
                    result = cur.fetchone()[0]
                    stats["total_transaction_amount"] = float(result) if result else 0
                except (psycopg2.Error, TypeError):
                    stats["total_transaction_amount"] = "error"
                
                # Active connections
                cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'")
                stats["active_connections"] = cur.fetchone()[0]
                
        finally:
            conn.close()
        
        return stats
    
    def _get_current_revision(self) -> str:
        """Get current alembic revision"""
        try:
            result = subprocess.run([
                "alembic", "current"
            ],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=dict(os.environ, DATABASE_URL=self.test_db_url)
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                return "unknown"
                
        except Exception:
            return "error"
    
    def generate_performance_report(self, results: Dict[str, any], output_file: str):
        """Generate detailed performance report"""
        report = {
            "test_summary": {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "test_database": self.test_db_url.split('@')[1] if '@' in self.test_db_url else "masked",
                "total_tests": len([k for k in results.keys() if k.endswith("_results")])
            },
            "performance_results": results,
            "recommendations": self._generate_recommendations(results)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance report written to {output_file}")
    
    def _generate_recommendations(self, results: Dict[str, any]) -> List[str]:
        """Generate performance recommendations based on test results"""
        recommendations = []
        
        # Check migration duration
        if "migration_results" in results:
            duration = results["migration_results"].get("duration_seconds", 0)
            if duration > 300:  # 5 minutes
                recommendations.append(
                    f"Migration took {duration:.1f} seconds (>{5} minutes). "
                    "Consider batching large data updates or running during maintenance windows."
                )
            elif duration > 60:  # 1 minute
                recommendations.append(
                    f"Migration took {duration:.1f} seconds. Monitor for production impact."
                )
        
        # Check resource usage
        if "migration_results" in results:
            max_cpu = results["migration_results"]["resource_usage"].get("max_cpu_percent", 0)
            max_memory = results["migration_results"]["resource_usage"].get("max_memory_percent", 0)
            
            if max_cpu > 80:
                recommendations.append(
                    f"High CPU usage detected ({max_cpu:.1f}%). "
                    "Consider running migrations during low-traffic periods."
                )
            
            if max_memory > 80:
                recommendations.append(
                    f"High memory usage detected ({max_memory:.1f}%). "
                    "Monitor memory constraints on production servers."
                )
        
        # Check lock contention
        if "migration_results" in results:
            max_locks = results["migration_results"]["lock_analysis"].get("max_concurrent_locks", 0)
            max_blocked = results["migration_results"]["lock_analysis"].get("max_blocked_locks", 0)
            
            if max_blocked > 0:
                recommendations.append(
                    f"Lock contention detected ({max_blocked} blocked locks). "
                    "Review migration for long-running operations that could block user queries."
                )
        
        if not recommendations:
            recommendations.append("Migration performance appears to be within acceptable limits.")
        
        return recommendations


def main():
    parser = argparse.ArgumentParser(description="MITA Migration Performance Tester")
    parser.add_argument("--test-size", choices=["small", "medium", "large"], 
                       default="small", help="Test data size")
    parser.add_argument("--with-load", action="store_true", 
                       help="Run concurrent load during migration")
    parser.add_argument("--rollback-test", action="store_true", 
                       help="Test rollback performance")
    parser.add_argument("--target", default="head", 
                       help="Migration target")
    parser.add_argument("--rollback-target", default="0003_goals",
                       help="Rollback target")
    parser.add_argument("--output", default="migration_performance_report.json",
                       help="Output file for performance report")
    
    args = parser.parse_args()
    
    tester = MigrationPerformanceTester()
    results = {}
    
    try:
        # Create test data
        logger.info("Setting up test environment...")
        data_counts = tester.create_test_data(args.test_size)
        results["test_setup"] = {
            "data_size": args.test_size,
            "data_counts": data_counts
        }
        
        # Test migration performance
        if args.with_load:
            # Start concurrent load
            import threading
            load_thread = threading.Thread(
                target=lambda: tester.test_concurrent_load(300)  # 5 minutes
            )
            load_thread.daemon = True
            load_thread.start()
            
            time.sleep(5)  # Let load start
        
        migration_results = tester.test_migration_performance(args.target)
        results["migration_results"] = migration_results
        
        # Test rollback if requested
        if args.rollback_test:
            time.sleep(10)  # Brief pause between tests
            rollback_results = tester.test_rollback_performance(args.rollback_target)
            results["rollback_results"] = rollback_results
        
        # Generate report
        tester.generate_performance_report(results, args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("MIGRATION PERFORMANCE TEST SUMMARY")
        print("="*60)
        
        if "migration_results" in results:
            mr = results["migration_results"]
            print(f"Migration Duration: {mr['duration_seconds']:.2f} seconds")
            print(f"Migration Success: {mr['success']}")
            print(f"Peak CPU Usage: {mr['resource_usage']['max_cpu_percent']:.1f}%")
            print(f"Peak Memory Usage: {mr['resource_usage']['max_memory_percent']:.1f}%")
            print(f"Max Concurrent Locks: {mr['lock_analysis']['max_concurrent_locks']}")
            print(f"Max Blocked Locks: {mr['lock_analysis']['max_blocked_locks']}")
        
        if "rollback_results" in results:
            rr = results["rollback_results"]
            print(f"\nRollback Duration: {rr['duration_seconds']:.2f} seconds")
            print(f"Rollback Success: {rr['success']}")
        
        print(f"\nDetailed report: {args.output}")
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Performance test failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()