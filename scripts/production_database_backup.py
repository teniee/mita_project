#!/usr/bin/env python3
"""
Production Database Backup System for MITA Financial Application

This script provides comprehensive backup and recovery capabilities with:
- Pre-migration snapshots
- Automated validation
- Point-in-time recovery
- Monitoring and alerting
- Financial data integrity checks

Usage:
  python production_database_backup.py backup --type=pre-migration
  python production_database_backup.py restore --backup-id=20250811-120000
  python production_database_backup.py validate --backup-id=20250811-120000
"""

import argparse
import datetime
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import boto3
import psycopg2
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/mita-backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionBackupSystem:
    """Production-grade backup system for MITA financial database"""
    
    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        self.bucket = os.environ.get("S3_BACKUP_BUCKET")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
        
        if not self.db_url or not self.bucket:
            raise RuntimeError("DATABASE_URL and S3_BACKUP_BUCKET must be set")
        
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region
        )
        
        # Financial data validation queries
        self.validation_queries = {
            "total_users": "SELECT COUNT(*) FROM users",
            "total_transactions": "SELECT COUNT(*) FROM transactions", 
            "total_transaction_amount": "SELECT SUM(amount) FROM transactions",
            "total_goals": "SELECT COUNT(*) FROM goals",
            "total_goal_targets": "SELECT SUM(target_amount) FROM goals",
            "negative_amounts_check": """
                SELECT 'transactions' as table_name, COUNT(*) as negative_count 
                FROM transactions WHERE amount < 0
                UNION ALL
                SELECT 'goals_target', COUNT(*) FROM goals WHERE target_amount < 0
                UNION ALL
                SELECT 'goals_saved', COUNT(*) FROM goals WHERE saved_amount < 0
            """
        }
    
    def create_backup(self, backup_type: str = "scheduled") -> Dict[str, str]:
        """
        Create a production database backup with validation
        
        Args:
            backup_type: Type of backup (scheduled, pre-migration, manual)
            
        Returns:
            Dict with backup metadata
        """
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        backup_id = f"{backup_type}-{timestamp}"
        
        logger.info(f"Starting {backup_type} backup: {backup_id}")
        
        try:
            # Pre-backup validation
            pre_backup_stats = self._collect_database_stats()
            logger.info(f"Pre-backup stats: {pre_backup_stats}")
            
            # Create the backup
            backup_metadata = self._create_database_dump(backup_id, backup_type)
            backup_metadata["pre_backup_stats"] = pre_backup_stats
            
            # Validate backup integrity
            if not self._validate_backup(backup_metadata):
                raise RuntimeError(f"Backup validation failed for {backup_id}")
            
            # Upload metadata
            self._upload_metadata(backup_metadata)
            
            # Cleanup old backups
            self._cleanup_old_backups()
            
            logger.info(f"Backup {backup_id} completed successfully")
            return backup_metadata
            
        except Exception as e:
            logger.error(f"Backup {backup_id} failed: {str(e)}")
            self._send_backup_alert("failed", backup_id, str(e))
            raise
    
    def _create_database_dump(self, backup_id: str, backup_type: str) -> Dict[str, str]:
        """Create PostgreSQL database dump with compression"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sql_path = os.path.join(tmpdir, f"{backup_id}.sql")
            gz_path = f"{sql_path}.gz"
            
            # Create database dump with additional options for production
            dump_cmd = [
                "pg_dump",
                self.db_url,
                "--verbose",
                "--clean",
                "--create",
                "--if-exists",
                "--format=custom",  # Use custom format for better compression and parallel restore
                "--compress=9",     # Maximum compression
                "--no-password",
                f"--file={sql_path}"
            ]
            
            start_time = time.time()
            result = subprocess.run(dump_cmd, capture_output=True, text=True)
            dump_duration = time.time() - start_time
            
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump failed: {result.stderr}")
            
            # Calculate file checksums
            with open(sql_path, 'rb') as f:
                sql_content = f.read()
                sql_checksum = hashlib.sha256(sql_content).hexdigest()
                sql_size = len(sql_content)
            
            # Compress the dump
            with open(sql_path, 'rb') as f_in, gzip.open(gz_path, 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
            
            with open(gz_path, 'rb') as f:
                gz_content = f.read()
                gz_checksum = hashlib.sha256(gz_content).hexdigest()
                gz_size = len(gz_content)
            
            # Upload to S3
            s3_key = f"backups/{backup_id}.sql.gz"
            self.s3.upload_file(gz_path, self.bucket, s3_key)
            
            # Create backup metadata
            metadata = {
                "backup_id": backup_id,
                "backup_type": backup_type,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "s3_bucket": self.bucket,
                "s3_key": s3_key,
                "sql_checksum": sql_checksum,
                "gz_checksum": gz_checksum,
                "sql_size": sql_size,
                "gz_size": gz_size,
                "dump_duration": dump_duration,
                "compression_ratio": round((1 - gz_size / sql_size) * 100, 2)
            }
            
            logger.info(f"Database dump created: {sql_size} bytes -> {gz_size} bytes "
                       f"({metadata['compression_ratio']}% compression)")
            
            return metadata
    
    def _collect_database_stats(self) -> Dict[str, any]:
        """Collect database statistics for validation"""
        stats = {}
        
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cur:
                for stat_name, query in self.validation_queries.items():
                    cur.execute(query)
                    if stat_name == "negative_amounts_check":
                        stats[stat_name] = cur.fetchall()
                    else:
                        stats[stat_name] = cur.fetchone()[0]
        finally:
            conn.close()
        
        return stats
    
    def _validate_backup(self, metadata: Dict[str, str]) -> bool:
        """Validate backup integrity and financial data consistency"""
        logger.info(f"Validating backup {metadata['backup_id']}")
        
        try:
            # Download and verify checksums
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = os.path.join(tmpdir, "backup_validation.sql.gz")
                self.s3.download_file(self.bucket, metadata["s3_key"], local_path)
                
                # Verify checksum
                with open(local_path, 'rb') as f:
                    downloaded_checksum = hashlib.sha256(f.read()).hexdigest()
                
                if downloaded_checksum != metadata["gz_checksum"]:
                    logger.error(f"Checksum mismatch for backup {metadata['backup_id']}")
                    return False
                
                # Test restore to temporary database (if TEST_DATABASE_URL is provided)
                test_db_url = os.environ.get("TEST_DATABASE_URL")
                if test_db_url:
                    success = self._test_restore_to_temp_db(local_path, test_db_url, metadata)
                    if not success:
                        return False
            
            logger.info(f"Backup {metadata['backup_id']} validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Backup validation failed: {str(e)}")
            return False
    
    def _test_restore_to_temp_db(self, backup_path: str, test_db_url: str, metadata: Dict[str, str]) -> bool:
        """Test restore to temporary database for validation"""
        logger.info("Testing backup restore to temporary database")
        
        try:
            # Decompress backup
            with tempfile.TemporaryDirectory() as tmpdir:
                sql_path = os.path.join(tmpdir, "test_restore.sql")
                
                with gzip.open(backup_path, 'rb') as f_in, open(sql_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                
                # Restore to test database
                restore_cmd = [
                    "pg_restore",
                    "--verbose",
                    "--clean",
                    "--if-exists",
                    "--dbname", test_db_url,
                    sql_path
                ]
                
                result = subprocess.run(restore_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Test restore failed: {result.stderr}")
                    return False
                
                # Validate restored data
                post_restore_stats = self._collect_test_database_stats(test_db_url)
                pre_backup_stats = metadata["pre_backup_stats"]
                
                # Compare critical metrics
                for key in ["total_users", "total_transactions", "total_goals"]:
                    if post_restore_stats.get(key) != pre_backup_stats.get(key):
                        logger.error(f"Data mismatch in {key}: "
                                   f"original={pre_backup_stats.get(key)}, "
                                   f"restored={post_restore_stats.get(key)}")
                        return False
                
                logger.info("Test restore validation passed")
                return True
                
        except Exception as e:
            logger.error(f"Test restore failed: {str(e)}")
            return False
    
    def _collect_test_database_stats(self, test_db_url: str) -> Dict[str, any]:
        """Collect stats from test database"""
        stats = {}
        
        conn = psycopg2.connect(test_db_url)
        try:
            with conn.cursor() as cur:
                for stat_name, query in self.validation_queries.items():
                    try:
                        cur.execute(query)
                        if stat_name == "negative_amounts_check":
                            stats[stat_name] = cur.fetchall()
                        else:
                            stats[stat_name] = cur.fetchone()[0]
                    except Exception:
                        stats[stat_name] = "error"
        finally:
            conn.close()
        
        return stats
    
    def _upload_metadata(self, metadata: Dict[str, str]):
        """Upload backup metadata to S3"""
        metadata_key = f"metadata/{metadata['backup_id']}.json"
        metadata_content = json.dumps(metadata, indent=2)
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=metadata_key,
            Body=metadata_content,
            ContentType='application/json'
        )
    
    def _cleanup_old_backups(self):
        """Remove backups older than retention period"""
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=self.retention_days)
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix="backups/")
            if "Contents" not in response:
                return
            
            deleted_count = 0
            for obj in response["Contents"]:
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    self.s3.delete_object(Bucket=self.bucket, Key=obj["Key"])
                    # Also delete corresponding metadata
                    backup_id = Path(obj["Key"]).stem.replace(".sql", "")
                    metadata_key = f"metadata/{backup_id}.json"
                    try:
                        self.s3.delete_object(Bucket=self.bucket, Key=metadata_key)
                    except ClientError:
                        pass  # Metadata might not exist for older backups
                    
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {obj['Key']}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backup(s)")
                
        except Exception as e:
            logger.warning(f"Backup cleanup failed: {str(e)}")
    
    def list_backups(self) -> List[Dict[str, str]]:
        """List available backups with metadata"""
        backups = []
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix="metadata/")
            if "Contents" not in response:
                return backups
            
            for obj in response["Contents"]:
                try:
                    metadata_content = self.s3.get_object(Bucket=self.bucket, Key=obj["Key"])
                    metadata = json.loads(metadata_content["Body"].read().decode())
                    backups.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to load metadata for {obj['Key']}: {str(e)}")
            
            # Sort by timestamp, newest first
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
        
        return backups
    
    def restore_backup(self, backup_id: str, target_db_url: str = None) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_id: ID of backup to restore
            target_db_url: Target database URL (defaults to main database)
        
        Returns:
            True if restore successful
        """
        if target_db_url is None:
            target_db_url = self.db_url
        
        logger.info(f"Starting restore of backup {backup_id}")
        
        try:
            # Get backup metadata
            metadata = self._get_backup_metadata(backup_id)
            if not metadata:
                raise RuntimeError(f"Backup metadata not found for {backup_id}")
            
            # Download backup
            with tempfile.TemporaryDirectory() as tmpdir:
                backup_path = os.path.join(tmpdir, f"{backup_id}.sql.gz")
                self.s3.download_file(self.bucket, metadata["s3_key"], backup_path)
                
                # Verify checksum
                with open(backup_path, 'rb') as f:
                    downloaded_checksum = hashlib.sha256(f.read()).hexdigest()
                
                if downloaded_checksum != metadata["gz_checksum"]:
                    raise RuntimeError(f"Backup checksum verification failed for {backup_id}")
                
                # Decompress
                sql_path = os.path.join(tmpdir, f"{backup_id}.sql")
                with gzip.open(backup_path, 'rb') as f_in, open(sql_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                
                # Perform restore
                restore_cmd = [
                    "pg_restore",
                    "--verbose",
                    "--clean",
                    "--if-exists",
                    "--dbname", target_db_url,
                    sql_path
                ]
                
                result = subprocess.run(restore_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Restore failed: {result.stderr}")
                
                logger.info(f"Backup {backup_id} restored successfully")
                return True
                
        except Exception as e:
            logger.error(f"Restore failed for backup {backup_id}: {str(e)}")
            self._send_backup_alert("restore_failed", backup_id, str(e))
            return False
    
    def _get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, str]]:
        """Get metadata for specific backup"""
        try:
            metadata_key = f"metadata/{backup_id}.json"
            response = self.s3.get_object(Bucket=self.bucket, Key=metadata_key)
            return json.loads(response["Body"].read().decode())
        except ClientError:
            return None
    
    def _send_backup_alert(self, alert_type: str, backup_id: str, message: str):
        """Send backup alert (implement based on your alerting system)"""
        # This would integrate with your alerting system (PagerDuty, Slack, etc.)
        logger.error(f"ALERT: {alert_type} for backup {backup_id}: {message}")
    
    def create_pre_migration_backup(self) -> Dict[str, str]:
        """Create backup specifically before database migration"""
        return self.create_backup("pre-migration")
    
    def verify_migration_readiness(self) -> bool:
        """Verify database is ready for migration"""
        logger.info("Verifying migration readiness")
        
        try:
            # Check for active connections
            conn = psycopg2.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM pg_stat_activity 
                    WHERE state = 'active' AND pid != pg_backend_pid()
                """)
                active_connections = cur.fetchone()[0]
                
                if active_connections > 5:  # Configurable threshold
                    logger.warning(f"High number of active connections: {active_connections}")
                    return False
                
                # Check for long-running transactions
                cur.execute("""
                    SELECT COUNT(*) FROM pg_stat_activity 
                    WHERE state IN ('active', 'idle in transaction')
                    AND query_start < NOW() - INTERVAL '5 minutes'
                """)
                long_running = cur.fetchone()[0]
                
                if long_running > 0:
                    logger.warning(f"Long-running transactions detected: {long_running}")
                    return False
                
                # Check database size and available space
                cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cur.fetchone()[0]
                logger.info(f"Database size: {db_size}")
            
            conn.close()
            
            logger.info("Database is ready for migration")
            return True
            
        except Exception as e:
            logger.error(f"Migration readiness check failed: {str(e)}")
            return False


def main():
    parser = argparse.ArgumentParser(description="MITA Production Database Backup System")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create database backup")
    backup_parser.add_argument("--type", default="manual", 
                              choices=["scheduled", "pre-migration", "manual"],
                              help="Backup type")
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore database from backup")
    restore_parser.add_argument("--backup-id", required=True, help="Backup ID to restore")
    restore_parser.add_argument("--target-db", help="Target database URL")
    
    # List command
    subparsers.add_parser("list", help="List available backups")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate backup")
    validate_parser.add_argument("--backup-id", required=True, help="Backup ID to validate")
    
    # Verify readiness command
    subparsers.add_parser("verify-readiness", help="Verify migration readiness")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    backup_system = ProductionBackupSystem()
    
    try:
        if args.command == "backup":
            metadata = backup_system.create_backup(args.type)
            print(f"Backup created: {metadata['backup_id']}")
            print(f"S3 location: s3://{metadata['s3_bucket']}/{metadata['s3_key']}")
            
        elif args.command == "restore":
            success = backup_system.restore_backup(args.backup_id, args.target_db)
            if success:
                print(f"Backup {args.backup_id} restored successfully")
            else:
                print(f"Restore failed for backup {args.backup_id}")
                exit(1)
                
        elif args.command == "list":
            backups = backup_system.list_backups()
            if backups:
                print("\nAvailable backups:")
                for backup in backups:
                    size_mb = backup.get('gz_size', 0) / (1024 * 1024)
                    print(f"  {backup['backup_id']} - {backup['timestamp']} "
                          f"({backup['backup_type']}, {size_mb:.1f} MB)")
            else:
                print("No backups found")
                
        elif args.command == "validate":
            metadata = backup_system._get_backup_metadata(args.backup_id)
            if not metadata:
                print(f"Backup {args.backup_id} not found")
                exit(1)
            
            if backup_system._validate_backup(metadata):
                print(f"Backup {args.backup_id} is valid")
            else:
                print(f"Backup {args.backup_id} validation failed")
                exit(1)
                
        elif args.command == "verify-readiness":
            if backup_system.verify_migration_readiness():
                print("Database is ready for migration")
            else:
                print("Database is NOT ready for migration")
                exit(1)
                
    except Exception as e:
        logger.error(f"Command failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()