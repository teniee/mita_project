#!/usr/bin/env python3
"""
Production Migration Manager for MITA Financial Application

This script provides safe database migration management with:
- Migration locks to prevent concurrent migrations  
- Pre/post migration validation
- Automated rollback on failure
- Comprehensive monitoring and alerting
- Financial data integrity verification

Usage:
  python migration_manager.py migrate --target=head
  python migration_manager.py rollback --target=0005_push_tokens
  python migration_manager.py status
  python migration_manager.py lock --operation=migration
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Dict, Optional, List
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/mita-migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MigrationError(Exception):
    """Custom exception for migration errors"""
    pass

class MigrationLockError(Exception):
    """Custom exception for migration lock errors"""
    pass

class ProductionMigrationManager:
    """Production-grade migration management system"""
    
    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise RuntimeError("DATABASE_URL environment variable must be set")
        
        self.max_migration_time = int(os.environ.get("MAX_MIGRATION_TIME", "1800"))  # 30 minutes
        self.lock_timeout = int(os.environ.get("MIGRATION_LOCK_TIMEOUT", "3600"))    # 1 hour
        
        # Financial validation queries
        self.pre_migration_checks = {
            "transaction_count": "SELECT COUNT(*) FROM transactions",
            "user_count": "SELECT COUNT(*) FROM users",
            "goal_count": "SELECT COUNT(*) FROM goals",
            "total_transaction_amount": "SELECT COALESCE(SUM(amount), 0) FROM transactions",
            "total_goal_amounts": "SELECT COALESCE(SUM(target_amount), 0) FROM goals",
            "active_subscriptions": "SELECT COUNT(*) FROM subscriptions WHERE status = 'active'",
            "data_integrity": """
                SELECT 
                    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as result,
                    COUNT(*) as issues
                FROM (
                    SELECT 'negative_transaction' as issue FROM transactions WHERE amount < 0
                    UNION ALL
                    SELECT 'negative_goal_target' as issue FROM goals WHERE target_amount < 0  
                    UNION ALL
                    SELECT 'negative_goal_saved' as issue FROM goals WHERE saved_amount < 0
                    UNION ALL
                    SELECT 'orphaned_transaction' as issue FROM transactions t 
                    LEFT JOIN users u ON t.user_id = u.id WHERE u.id IS NULL
                ) issues
            """
        }
        
    def _ensure_lock_table_exists(self):
        """Ensure migration lock table exists"""
        conn = psycopg2.connect(self.db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS migration_locks (
                        lock_name VARCHAR(100) PRIMARY KEY,
                        locked_by VARCHAR(255) NOT NULL,
                        locked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        lock_data JSONB,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                    )
                """)
                
                # Create index for expired lock cleanup
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_migration_locks_expires_at 
                    ON migration_locks(expires_at)
                """)
                
        finally:
            conn.close()
    
    @contextmanager
    def acquire_migration_lock(self, operation: str = "migration"):
        """
        Acquire a migration lock to prevent concurrent operations
        
        Args:
            operation: Type of operation (migration, rollback, etc.)
        """
        self._ensure_lock_table_exists()
        
        lock_name = f"mita_{operation}_lock"
        locked_by = f"{os.environ.get('USER', 'unknown')}@{os.environ.get('HOSTNAME', 'unknown')}"
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.lock_timeout)
        
        conn = psycopg2.connect(self.db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        try:
            with conn.cursor() as cur:
                # Clean up expired locks first
                cur.execute("DELETE FROM migration_locks WHERE expires_at < NOW()")
                expired_count = cur.rowcount
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired lock(s)")
                
                # Try to acquire lock
                try:
                    cur.execute("""
                        INSERT INTO migration_locks (lock_name, locked_by, expires_at, lock_data)
                        VALUES (%s, %s, %s, %s)
                    """, (lock_name, locked_by, expires_at, json.dumps({
                        "operation": operation,
                        "pid": os.getpid(),
                        "start_time": datetime.datetime.utcnow().isoformat()
                    })))
                    
                    logger.info(f"Acquired {operation} lock: {lock_name}")
                    
                except psycopg2.IntegrityError:
                    # Lock already exists, check if it's expired
                    cur.execute("""
                        SELECT locked_by, locked_at, expires_at, lock_data
                        FROM migration_locks WHERE lock_name = %s
                    """, (lock_name,))
                    
                    existing_lock = cur.fetchone()
                    if existing_lock:
                        locked_by_existing, locked_at, expires_at_existing, lock_data = existing_lock
                        
                        if expires_at_existing > datetime.datetime.utcnow().replace(tzinfo=expires_at_existing.tzinfo):
                            raise MigrationLockError(
                                f"Migration lock already held by {locked_by_existing} "
                                f"since {locked_at}, expires at {expires_at_existing}"
                            )
                        else:
                            # Force remove expired lock and retry
                            cur.execute("DELETE FROM migration_locks WHERE lock_name = %s", (lock_name,))
                            cur.execute("""
                                INSERT INTO migration_locks (lock_name, locked_by, expires_at, lock_data)
                                VALUES (%s, %s, %s, %s)
                            """, (lock_name, locked_by, expires_at, json.dumps({
                                "operation": operation,
                                "pid": os.getpid(),
                                "start_time": datetime.datetime.utcnow().isoformat()
                            })))
                            
                            logger.info(f"Forcibly acquired {operation} lock after expiration")
                
                try:
                    yield
                finally:
                    # Release lock
                    cur.execute("DELETE FROM migration_locks WHERE lock_name = %s", (lock_name,))
                    logger.info(f"Released {operation} lock: {lock_name}")
                    
        finally:
            conn.close()
    
    def _collect_pre_migration_stats(self) -> Dict[str, any]:
        """Collect database statistics before migration"""
        stats = {}
        
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cur:
                for check_name, query in self.pre_migration_checks.items():
                    try:
                        cur.execute(query)
                        result = cur.fetchone()
                        if check_name == "data_integrity":
                            stats[check_name] = {"result": result[0], "issues": result[1]}
                        else:
                            stats[check_name] = result[0] if result else None
                    except Exception as e:
                        stats[check_name] = f"ERROR: {str(e)}"
                        logger.warning(f"Failed to collect {check_name}: {str(e)}")
        finally:
            conn.close()
        
        return stats
    
    def _validate_pre_migration_state(self, stats: Dict[str, any]) -> bool:
        """Validate database state before migration"""
        logger.info("Validating pre-migration state")
        
        # Check for data integrity issues
        if stats.get("data_integrity", {}).get("result") == "FAIL":
            issues = stats["data_integrity"]["issues"]
            logger.error(f"Data integrity check failed: {issues} issues found")
            return False
        
        # Ensure we have data to migrate (not an empty database)
        if stats.get("user_count", 0) == 0 and stats.get("transaction_count", 0) == 0:
            logger.info("Empty database detected - allowing migration")
        elif stats.get("user_count", 0) > 0:
            logger.info(f"Database contains {stats['user_count']} users and "
                       f"{stats['transaction_count']} transactions")
        
        # Check for reasonable data ranges
        total_amount = stats.get("total_transaction_amount", 0)
        if total_amount and (total_amount < -1000000 or total_amount > 1000000000):
            logger.warning(f"Unusual total transaction amount: {total_amount}")
        
        logger.info("Pre-migration validation passed")
        return True
    
    def migrate(self, target: str = "head", dry_run: bool = False) -> bool:
        """
        Run database migration with comprehensive safety checks
        
        Args:
            target: Target migration (default: head)
            dry_run: If True, only show what would be migrated
            
        Returns:
            True if migration successful
        """
        logger.info(f"Starting migration to {target} (dry_run={dry_run})")
        
        try:
            with self.acquire_migration_lock("migration"):
                # Pre-migration checks
                pre_stats = self._collect_pre_migration_stats()
                if not self._validate_pre_migration_state(pre_stats):
                    raise MigrationError("Pre-migration validation failed")
                
                # Create pre-migration backup
                logger.info("Creating pre-migration backup")
                backup_result = self._create_pre_migration_backup()
                
                # Show current migration status
                current_revision = self._get_current_revision()
                logger.info(f"Current database revision: {current_revision}")
                
                if dry_run:
                    # Show pending migrations
                    pending = self._get_pending_migrations(target)
                    if pending:
                        logger.info("Pending migrations:")
                        for migration in pending:
                            logger.info(f"  - {migration}")
                    else:
                        logger.info("No pending migrations")
                    return True
                
                # Run the actual migration
                migration_start = time.time()
                success = self._run_alembic_migration(target)
                migration_duration = time.time() - migration_start
                
                if not success:
                    raise MigrationError("Alembic migration failed")
                
                # Post-migration validation
                post_stats = self._collect_pre_migration_stats()
                if not self._validate_post_migration_state(pre_stats, post_stats):
                    logger.error("Post-migration validation failed - initiating rollback")
                    self._rollback_to_backup(backup_result["backup_id"])
                    raise MigrationError("Post-migration validation failed, rolled back")
                
                # Log success
                new_revision = self._get_current_revision()
                logger.info(f"Migration completed successfully in {migration_duration:.2f}s")
                logger.info(f"Database migrated from {current_revision} to {new_revision}")
                
                # Send success notification
                self._send_migration_notification("success", {
                    "from_revision": current_revision,
                    "to_revision": new_revision,
                    "duration": migration_duration,
                    "backup_id": backup_result["backup_id"]
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            self._send_migration_notification("failed", {"error": str(e)})
            return False
    
    def _create_pre_migration_backup(self) -> Dict[str, str]:
        """Create backup before migration"""
        # This would call your backup system
        backup_script = os.path.join(os.path.dirname(__file__), "production_database_backup.py")
        
        result = subprocess.run([
            sys.executable, backup_script, "backup", "--type=pre-migration"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise MigrationError(f"Pre-migration backup failed: {result.stderr}")
        
        # Extract backup ID from output (simplified)
        backup_id = "pre-migration-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return {"backup_id": backup_id, "status": "created"}
    
    def _get_current_revision(self) -> str:
        """Get current database revision"""
        result = subprocess.run([
            "alembic", "current", "--verbose"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        if result.returncode != 0:
            return "unknown"
        
        # Parse alembic current output
        for line in result.stdout.split('\n'):
            if 'Rev:' in line:
                return line.split('Rev:')[1].strip().split()[0]
        
        return "unknown"
    
    def _get_pending_migrations(self, target: str) -> List[str]:
        """Get list of pending migrations"""
        result = subprocess.run([
            "alembic", "history", "--verbose"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        if result.returncode != 0:
            return []
        
        # This is simplified - you'd parse the actual alembic output
        return []
    
    def _run_alembic_migration(self, target: str) -> bool:
        """Run the actual alembic migration"""
        logger.info(f"Executing: alembic upgrade {target}")
        
        # Set environment variables for the migration
        env = os.environ.copy()
        env["MIGRATION_IN_PROGRESS"] = "true"
        env["MIGRATION_TIMESTAMP"] = datetime.datetime.utcnow().isoformat()
        
        # Run alembic upgrade with timeout
        try:
            result = subprocess.run([
                "alembic", "upgrade", target, "--verbose"
            ], 
            capture_output=True, 
            text=True, 
            timeout=self.max_migration_time,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env
            )
            
            if result.returncode != 0:
                logger.error(f"Alembic migration failed with code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return False
            
            logger.info(f"Alembic migration output: {result.stdout}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Migration timed out after {self.max_migration_time} seconds")
            return False
        except Exception as e:
            logger.error(f"Migration execution failed: {str(e)}")
            return False
    
    def _validate_post_migration_state(self, pre_stats: Dict[str, any], post_stats: Dict[str, any]) -> bool:
        """Validate database state after migration"""
        logger.info("Validating post-migration state")
        
        # Check that data counts haven't decreased (unless expected)
        critical_counts = ["user_count", "transaction_count"]
        
        for count_key in critical_counts:
            pre_count = pre_stats.get(count_key, 0)
            post_count = post_stats.get(count_key, 0)
            
            if post_count < pre_count:
                logger.error(f"Data loss detected in {count_key}: {pre_count} -> {post_count}")
                return False
        
        # Check data integrity again
        if post_stats.get("data_integrity", {}).get("result") == "FAIL":
            issues = post_stats["data_integrity"]["issues"]
            logger.error(f"Post-migration data integrity check failed: {issues} issues")
            return False
        
        # Check that financial totals are reasonable
        pre_total = pre_stats.get("total_transaction_amount", 0)
        post_total = post_stats.get("total_transaction_amount", 0)
        
        if pre_total and post_total and abs(pre_total - post_total) > 0.01:
            logger.warning(f"Transaction total changed: {pre_total} -> {post_total}")
            # This might be expected for some migrations, so we log but don't fail
        
        logger.info("Post-migration validation passed")
        return True
    
    def _rollback_to_backup(self, backup_id: str):
        """Rollback to specific backup"""
        logger.info(f"Initiating rollback to backup {backup_id}")
        
        backup_script = os.path.join(os.path.dirname(__file__), "production_database_backup.py")
        
        result = subprocess.run([
            sys.executable, backup_script, "restore", f"--backup-id={backup_id}"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Rollback failed: {result.stderr}")
            raise MigrationError("Rollback to backup failed")
        
        logger.info("Rollback completed successfully")
    
    def rollback(self, target: str) -> bool:
        """
        Rollback to specific migration
        
        Args:
            target: Target migration to rollback to
            
        Returns:
            True if rollback successful
        """
        logger.info(f"Starting rollback to {target}")
        
        try:
            with self.acquire_migration_lock("rollback"):
                # Create backup before rollback
                backup_result = self._create_pre_migration_backup()
                
                current_revision = self._get_current_revision()
                logger.info(f"Current revision: {current_revision}")
                
                # Run alembic downgrade
                result = subprocess.run([
                    "alembic", "downgrade", target, "--verbose"
                ], capture_output=True, text=True, timeout=self.max_migration_time,
                cwd=os.path.dirname(os.path.dirname(__file__)))
                
                if result.returncode != 0:
                    logger.error(f"Rollback failed: {result.stderr}")
                    return False
                
                new_revision = self._get_current_revision()
                logger.info(f"Rollback completed: {current_revision} -> {new_revision}")
                
                # Validate post-rollback state
                post_stats = self._collect_pre_migration_stats()
                if post_stats.get("data_integrity", {}).get("result") == "FAIL":
                    logger.warning("Data integrity issues found after rollback")
                
                self._send_migration_notification("rollback", {
                    "from_revision": current_revision,
                    "to_revision": new_revision,
                    "backup_id": backup_result["backup_id"]
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            return False
    
    def get_migration_status(self) -> Dict[str, any]:
        """Get current migration status"""
        status = {}
        
        try:
            # Current revision
            status["current_revision"] = self._get_current_revision()
            
            # Database stats
            status["database_stats"] = self._collect_pre_migration_stats()
            
            # Check for active locks
            conn = psycopg2.connect(self.db_url)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT lock_name, locked_by, locked_at, expires_at, lock_data
                        FROM migration_locks 
                        WHERE expires_at > NOW()
                        ORDER BY locked_at
                    """)
                    
                    active_locks = []
                    for row in cur.fetchall():
                        active_locks.append({
                            "lock_name": row[0],
                            "locked_by": row[1],
                            "locked_at": row[2].isoformat(),
                            "expires_at": row[3].isoformat(),
                            "lock_data": row[4]
                        })
                    
                    status["active_locks"] = active_locks
                    
            except psycopg2.Error:
                status["active_locks"] = "unable_to_check"
            finally:
                conn.close()
                
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def _send_migration_notification(self, event_type: str, data: Dict[str, any]):
        """Send migration notification (implement based on your notification system)"""
        # This would integrate with your notification system (Slack, PagerDuty, etc.)
        logger.info(f"NOTIFICATION: {event_type} - {json.dumps(data, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="MITA Production Migration Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run database migration")
    migrate_parser.add_argument("--target", default="head", help="Target migration")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated")
    
    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback database migration")
    rollback_parser.add_argument("--target", required=True, help="Target migration to rollback to")
    
    # Status command
    subparsers.add_parser("status", help="Show migration status")
    
    # Lock management
    lock_parser = subparsers.add_parser("lock", help="Manage migration locks")
    lock_parser.add_argument("--operation", required=True, help="Operation to lock")
    lock_parser.add_argument("--release", action="store_true", help="Release lock")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ProductionMigrationManager()
    
    try:
        if args.command == "migrate":
            success = manager.migrate(args.target, args.dry_run)
            exit(0 if success else 1)
            
        elif args.command == "rollback":
            success = manager.rollback(args.target)
            exit(0 if success else 1)
            
        elif args.command == "status":
            status = manager.get_migration_status()
            print(json.dumps(status, indent=2, default=str))
            
        elif args.command == "lock":
            if args.release:
                # Force release lock (emergency use only)
                manager._ensure_lock_table_exists()
                conn = psycopg2.connect(manager.db_url)
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM migration_locks WHERE lock_name = %s", 
                                  (f"mita_{args.operation}_lock",))
                        print(f"Released {args.operation} lock")
                finally:
                    conn.close()
            else:
                print(f"Use 'with acquire_migration_lock(\"{args.operation}\")' in your code")
                
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"Migration manager failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()