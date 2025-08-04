#!/usr/bin/env python3
"""
MITA Finance Production Backup Script
Automated backup with encryption, compression, and S3 storage
"""

import os
import sys
import gzip
import logging
import datetime
import subprocess
import boto3
from pathlib import Path
from typing import Optional
import psycopg2
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MitaProductionBackup:
    """Production backup manager for MITA Finance"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.backup_bucket = os.getenv('BACKUP_BUCKET', 'mita-production-backups')
        self.aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.encryption_key = os.getenv('BACKUP_ENCRYPTION_KEY')
        
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        
        # Initialize encryption
        if self.encryption_key:
            self.cipher = Fernet(self.encryption_key.encode())
        else:
            logger.warning("No encryption key provided, backups will not be encrypted")
            self.cipher = None
        
        # Backup directory
        self.backup_dir = Path('/tmp/backups')
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_database_backup(self) -> Optional[Path]:
        """Create compressed database backup"""
        try:
            timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"mita_db_backup_{timestamp}.sql"
            backup_path = self.backup_dir / backup_filename
            
            logger.info(f"Creating database backup: {backup_filename}")
            
            # Create pg_dump command
            cmd = [
                'pg_dump',
                self.database_url,
                '--no-password',
                '--verbose',
                '--clean',
                '--no-acl',
                '--no-owner',
                '-f', str(backup_path)
            ]
            
            # Execute backup
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode != 0:
                logger.error(f"Database backup failed: {result.stderr}")
                return None
            
            logger.info(f"Database backup created successfully: {backup_path}")
            return backup_path
            
        except subprocess.TimeoutExpired:
            logger.error("Database backup timed out after 1 hour")
            return None
        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            return None
    
    def compress_backup(self, backup_path: Path) -> Optional[Path]:
        """Compress backup file with gzip"""
        try:
            compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
            
            logger.info(f"Compressing backup: {compressed_path}")
            
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
            
            # Remove original file
            backup_path.unlink()
            
            # Get compression ratio
            original_size = backup_path.stat().st_size if backup_path.exists() else 0
            compressed_size = compressed_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            logger.info(f"Compression completed. Ratio: {ratio:.1f}%")
            return compressed_path
            
        except Exception as e:
            logger.error(f"Compression failed: {str(e)}")
            return None
    
    def encrypt_backup(self, backup_path: Path) -> Optional[Path]:
        """Encrypt backup file"""
        if not self.cipher:
            logger.info("Skipping encryption (no key provided)")
            return backup_path
        
        try:
            encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
            
            logger.info(f"Encrypting backup: {encrypted_path}")
            
            with open(backup_path, 'rb') as f_in:
                data = f_in.read()
                encrypted_data = self.cipher.encrypt(data)
                
                with open(encrypted_path, 'wb') as f_out:
                    f_out.write(encrypted_data)
            
            # Remove unencrypted file
            backup_path.unlink()
            
            logger.info("Encryption completed successfully")
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            return None
    
    def upload_to_s3(self, backup_path: Path) -> bool:
        """Upload backup to S3 with metadata"""
        try:
            timestamp = datetime.datetime.utcnow().strftime('%Y/%m/%d')
            s3_key = f"database_backups/{timestamp}/{backup_path.name}"
            
            logger.info(f"Uploading to S3: s3://{self.backup_bucket}/{s3_key}")
            
            # Calculate file size
            file_size = backup_path.stat().st_size
            
            # Upload with metadata
            extra_args = {
                'Metadata': {
                    'backup-type': 'database',
                    'environment': os.getenv('ENVIRONMENT', 'production'),
                    'created-at': datetime.datetime.utcnow().isoformat(),
                    'file-size': str(file_size),
                    'encrypted': str(bool(self.cipher))
                },
                'ServerSideEncryption': 'AES256',
                'StorageClass': 'STANDARD_IA'  # Infrequent Access for cost optimization
            }
            
            self.s3_client.upload_file(
                str(backup_path),
                self.backup_bucket,
                s3_key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"Upload completed successfully. Size: {file_size / 1024 / 1024:.1f} MB")
            return True
            
        except Exception as e:
            logger.error(f"S3 upload failed: {str(e)}")
            return False
    
    def cleanup_local_files(self, backup_path: Path):
        """Clean up local backup files"""
        try:
            if backup_path.exists():
                backup_path.unlink()
                logger.info("Local backup file cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
    
    def cleanup_old_backups(self, retention_days: int = 30):
        """Remove old backups from S3 based on retention policy"""
        try:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
            
            logger.info(f"Cleaning up backups older than {retention_days} days")
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.backup_bucket, Prefix='database_backups/')
            
            deleted_count = 0
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        self.s3_client.delete_object(
                            Bucket=self.backup_bucket,
                            Key=obj['Key']
                        )
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {obj['Key']}")
            
            logger.info(f"Cleanup completed. Deleted {deleted_count} old backups")
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")
    
    def verify_backup_integrity(self, backup_path: Path) -> bool:
        """Verify backup file integrity"""
        try:
            logger.info("Verifying backup integrity")
            
            # For encrypted files, try to decrypt a small portion
            if backup_path.suffix == '.enc' and self.cipher:
                with open(backup_path, 'rb') as f:
                    encrypted_data = f.read(1024)  # Read first 1KB
                    try:
                        self.cipher.decrypt(encrypted_data[:100])  # Try to decrypt small chunk
                        logger.info("Backup encryption integrity verified")
                        return True
                    except Exception:
                        logger.error("Backup encryption integrity check failed")
                        return False
            
            # For compressed files, verify gzip integrity
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f:
                    f.read(1024)  # Try to read first 1KB
                logger.info("Backup compression integrity verified")
                return True
            
            # For regular files, check if readable
            with open(backup_path, 'rb') as f:
                f.read(1024)
            
            logger.info("Backup integrity verified")
            return True
            
        except Exception as e:
            logger.error(f"Backup integrity verification failed: {str(e)}")
            return False
    
    def run_backup(self) -> bool:
        """Execute complete backup process"""
        logger.info("Starting MITA Finance production backup")
        
        try:
            # Create database backup
            backup_path = self.create_database_backup()
            if not backup_path:
                return False
            
            # Compress backup
            backup_path = self.compress_backup(backup_path)
            if not backup_path:
                return False
            
            # Encrypt backup
            backup_path = self.encrypt_backup(backup_path)
            if not backup_path:
                return False
            
            # Verify integrity
            if not self.verify_backup_integrity(backup_path):
                logger.error("Backup integrity verification failed")
                return False
            
            # Upload to S3
            if not self.upload_to_s3(backup_path):
                return False
            
            # Cleanup local files
            self.cleanup_local_files(backup_path)
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            logger.info("Backup process completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Backup process failed: {str(e)}")
            return False


def main():
    """Main backup execution"""
    try:
        backup_manager = MitaProductionBackup()
        success = backup_manager.run_backup()
        
        if success:
            logger.info("✅ Backup completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Backup failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()