#!/usr/bin/env python3
"""
MITA Finance Database Migration Validation Script
=================================================
Comprehensive validation of database schema, migrations, and data integrity
for MITA Finance production system.

CRITICAL: This script validates:
1. Migration state consistency between Alembic and newer migration system
2. Database schema against model definitions
3. Data integrity across all financial tables
4. Connection pool performance
5. Backup system status
"""

import asyncio
import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import asyncpg
from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.exc import SQLAlchemyError

# Import MITA modules
from app.core.config import settings
from app.core.async_session import get_async_db_context, initialize_database, async_engine
from app.db.models import Base, User, Transaction, Expense, Goal, Subscription

class DatabaseValidationReport:
    """Comprehensive database validation report"""
    
    def __init__(self):
        self.timestamp = datetime.utcnow()
        self.validation_results = {
            "migration_state": {},
            "schema_validation": {},
            "data_integrity": {},
            "connection_pool": {},
            "performance": {},
            "backup_status": {},
            "critical_issues": [],
            "warnings": [],
            "recommendations": []
        }
        
    def add_critical_issue(self, issue: str):
        """Add a critical issue that requires immediate attention"""
        self.validation_results["critical_issues"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "issue": issue,
            "severity": "CRITICAL"
        })
        print(f"🚨 CRITICAL: {issue}")
        
    def add_warning(self, warning: str):
        """Add a warning that should be addressed"""
        self.validation_results["warnings"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "warning": warning,
            "severity": "WARNING"
        })
        print(f"⚠️ WARNING: {warning}")
        
    def add_recommendation(self, recommendation: str):
        """Add a recommendation for improvement"""
        self.validation_results["recommendations"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "recommendation": recommendation,
            "priority": "MEDIUM"
        })
        print(f"💡 RECOMMENDATION: {recommendation}")
        
    def save_report(self, filename: Optional[str] = None):
        """Save the validation report to a file"""
        if filename is None:
            timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"database_validation_report_{timestamp}.json"
            
        with open(filename, 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        print(f"📊 Report saved to: {filename}")
        return filename

class MITADatabaseValidator:
    """Main database validation class"""
    
    def __init__(self):
        self.report = DatabaseValidationReport()
        self.connection_pool = None
        
    async def validate_all(self) -> DatabaseValidationReport:
        """Run all validation checks"""
        print("🔍 Starting comprehensive database validation...")
        print(f"⏰ Timestamp: {self.report.timestamp}")
        print("=" * 80)
        
        try:
            await self._validate_migration_state()
            await self._validate_schema_consistency()
            await self._validate_connection_pool()
            await self._validate_data_integrity()
            await self._validate_performance()
            await self._validate_backup_system()
            
        except Exception as e:
            self.report.add_critical_issue(f"Validation failed with error: {str(e)}")
            
        print("=" * 80)
        print("🏁 Database validation completed")
        
        # Summary
        critical_count = len(self.report.validation_results["critical_issues"])
        warning_count = len(self.report.validation_results["warnings"])
        recommendation_count = len(self.report.validation_results["recommendations"])
        
        print(f"📊 Summary: {critical_count} critical issues, {warning_count} warnings, {recommendation_count} recommendations")
        
        if critical_count > 0:
            print("🚨 CRITICAL ISSUES DETECTED - IMMEDIATE ACTION REQUIRED")
        elif warning_count > 0:
            print("⚠️ Warnings detected - should be addressed")
        else:
            print("✅ No critical issues detected")
            
        return self.report
        
    async def _validate_migration_state(self):
        """Validate current migration state and consistency"""
        print("🔍 1. Validating Migration State...")
        
        try:
            # Check Alembic current head
            import subprocess
            result = subprocess.run(
                ["python3", "-m", "alembic", "current"], 
                capture_output=True, 
                text=True,
                cwd=project_root
            )
            
            alembic_current = result.stdout.strip() if result.returncode == 0 else "ERROR"
            
            # Check if there are newer migrations in migrations/versions/
            newer_migrations = []
            migrations_dir = os.path.join(project_root, "migrations", "versions")
            if os.path.exists(migrations_dir):
                migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and not f.startswith('__')]
                newer_migrations = sorted(migration_files)
            
            self.report.validation_results["migration_state"] = {
                "alembic_current": alembic_current,
                "newer_migrations_exist": len(newer_migrations) > 0,
                "newer_migrations": newer_migrations,
                "dual_migration_system": True  # Both alembic/ and migrations/ exist
            }
            
            # Critical issue: Dual migration systems
            if os.path.exists(os.path.join(project_root, "alembic")) and os.path.exists(migrations_dir):
                self.report.add_critical_issue("DUAL MIGRATION SYSTEMS DETECTED: Both alembic/ and migrations/ directories exist. This can cause schema conflicts.")
                
            # Check if current migration matches production
            if "ERROR" in alembic_current:
                self.report.add_critical_issue("Cannot determine current Alembic migration state")
            elif "0006_fix_financial_data_types" in alembic_current:
                print("✅ Alembic shows current migration: 0006_fix_financial_data_types")
                
                # But check if newer migrations exist
                if newer_migrations:
                    self.report.add_critical_issue(f"Newer migrations exist but may not be applied: {newer_migrations}")
                    
        except Exception as e:
            self.report.add_critical_issue(f"Migration state validation failed: {str(e)}")
            
    async def _validate_schema_consistency(self):
        """Validate database schema against model definitions"""
        print("🔍 2. Validating Schema Consistency...")
        
        try:
            # Initialize database connection
            initialize_database()
            
            async with get_async_db_context() as session:
                # Get actual database schema
                inspector = inspect(session.bind)
                actual_tables = inspector.get_table_names()
                
                # Get expected tables from models
                expected_tables = set()
                for table in Base.metadata.tables.values():
                    expected_tables.add(table.name)
                
                # Compare tables
                missing_tables = expected_tables - set(actual_tables)
                extra_tables = set(actual_tables) - expected_tables
                
                schema_issues = []
                
                if missing_tables:
                    for table in missing_tables:
                        issue = f"Missing table: {table}"
                        schema_issues.append(issue)
                        self.report.add_critical_issue(issue)
                        
                if extra_tables:
                    for table in extra_tables:
                        if not table.startswith('alembic_'):  # Ignore Alembic metadata tables
                            issue = f"Extra table not in models: {table}"
                            schema_issues.append(issue)
                            self.report.add_warning(issue)
                
                # Validate critical financial tables exist
                critical_tables = ['users', 'transactions', 'expenses', 'goals']
                for table in critical_tables:
                    if table not in actual_tables:
                        self.report.add_critical_issue(f"Critical financial table missing: {table}")
                    else:
                        print(f"✅ Critical table exists: {table}")
                        
                # Check for proper data types on financial columns
                await self._validate_financial_data_types(session, inspector)
                
                self.report.validation_results["schema_validation"] = {
                    "actual_tables": sorted(actual_tables),
                    "expected_tables": sorted(expected_tables),
                    "missing_tables": sorted(missing_tables),
                    "extra_tables": sorted(extra_tables),
                    "schema_issues": schema_issues
                }
                
        except Exception as e:
            self.report.add_critical_issue(f"Schema validation failed: {str(e)}")
            
    async def _validate_financial_data_types(self, session, inspector):
        """Validate financial data types for precision"""
        print("🔍 2.1. Validating Financial Data Types...")
        
        critical_columns = {
            'transactions': ['amount'],
            'expenses': ['amount'],
            'users': ['annual_income'],
            'goals': ['target_amount', 'saved_amount']
        }
        
        for table_name, columns in critical_columns.items():
            if table_name in inspector.get_table_names():
                table_columns = inspector.get_columns(table_name)
                
                for column_info in table_columns:
                    if column_info['name'] in columns:
                        column_type = str(column_info['type'])
                        
                        # Check if using proper Numeric type for financial data
                        if 'FLOAT' in column_type.upper():
                            self.report.add_critical_issue(
                                f"Table {table_name}.{column_info['name']} uses FLOAT instead of NUMERIC - this causes financial precision issues"
                            )
                        elif 'NUMERIC' in column_type.upper():
                            print(f"✅ {table_name}.{column_info['name']}: {column_type}")
                        else:
                            self.report.add_warning(
                                f"Table {table_name}.{column_info['name']} has unexpected type: {column_type}"
                            )
    
    async def _validate_connection_pool(self):
        """Validate asyncpg connection pool performance"""
        print("🔍 3. Validating Connection Pool Performance...")
        
        try:
            # Test direct asyncpg connection pool
            database_url = settings.DATABASE_URL
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
                
            # Parse URL for asyncpg
            import re
            match = re.match(r'postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', database_url)
            if not match:
                self.report.add_critical_issue("Cannot parse DATABASE_URL for connection testing")
                return
                
            user, password, host, port, database = match.groups()
            
            # Test connection pool with different sizes
            pool_sizes = [5, 10, 20]
            performance_results = {}
            
            for pool_size in pool_sizes:
                print(f"  Testing pool size: {pool_size}")
                
                start_time = time.time()
                try:
                    pool = await asyncpg.create_pool(
                        user=user,
                        password=password,
                        database=database,
                        host=host,
                        port=int(port),
                        min_size=pool_size,
                        max_size=pool_size * 2,
                        command_timeout=10
                    )
                    
                    # Test concurrent connections
                    async def test_query():
                        async with pool.acquire() as conn:
                            await conn.fetchval("SELECT 1")
                            
                    # Run 20 concurrent queries
                    tasks = [test_query() for _ in range(20)]
                    await asyncio.gather(*tasks)
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    performance_results[f"pool_size_{pool_size}"] = {
                        "duration_seconds": duration,
                        "queries_per_second": 20 / duration,
                        "status": "success"
                    }
                    
                    print(f"    ✅ Pool size {pool_size}: {duration:.2f}s, {20/duration:.1f} queries/sec")
                    
                    await pool.close()
                    
                except Exception as e:
                    performance_results[f"pool_size_{pool_size}"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    self.report.add_warning(f"Pool size {pool_size} test failed: {str(e)}")
            
            self.report.validation_results["connection_pool"] = {
                "performance_tests": performance_results,
                "current_pool_config": {
                    "pool_size": 20,
                    "max_overflow": 30,
                    "pool_timeout": 30
                }
            }
            
        except Exception as e:
            self.report.add_critical_issue(f"Connection pool validation failed: {str(e)}")
    
    async def _validate_data_integrity(self):
        """Validate data integrity across financial tables"""
        print("🔍 4. Validating Data Integrity...")
        
        try:
            initialize_database()
            
            async with get_async_db_context() as session:
                integrity_checks = {}
                
                # Check for orphaned records
                print("  4.1. Checking for orphaned records...")
                
                # Check transactions without users
                result = await session.execute(text("""
                    SELECT COUNT(*) 
                    FROM transactions t 
                    LEFT JOIN users u ON t.user_id = u.id 
                    WHERE u.id IS NULL
                """))
                orphaned_transactions = result.scalar()
                
                if orphaned_transactions > 0:
                    self.report.add_critical_issue(f"Found {orphaned_transactions} orphaned transactions without valid user_id")
                else:
                    print("    ✅ No orphaned transactions found")
                
                # Check expenses without users (if expenses table exists)
                try:
                    result = await session.execute(text("""
                        SELECT COUNT(*) 
                        FROM expenses e 
                        LEFT JOIN users u ON e.user_id = u.id 
                        WHERE u.id IS NULL
                    """))
                    orphaned_expenses = result.scalar()
                    
                    if orphaned_expenses > 0:
                        self.report.add_critical_issue(f"Found {orphaned_expenses} orphaned expenses without valid user_id")
                    else:
                        print("    ✅ No orphaned expenses found")
                        
                    integrity_checks["orphaned_expenses"] = orphaned_expenses
                except Exception as e:
                    print(f"    ⚠️ Could not check expenses table: {str(e)}")
                
                # Check for negative financial amounts
                print("  4.2. Checking for invalid financial amounts...")
                
                result = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE amount < 0"))
                negative_transactions = result.scalar()
                
                if negative_transactions > 0:
                    self.report.add_warning(f"Found {negative_transactions} transactions with negative amounts")
                    
                # Check for NULL amounts in financial tables
                result = await session.execute(text("SELECT COUNT(*) FROM transactions WHERE amount IS NULL"))
                null_amounts = result.scalar()
                
                if null_amounts > 0:
                    self.report.add_critical_issue(f"Found {null_amounts} transactions with NULL amounts")
                
                # Check user data consistency
                print("  4.3. Checking user data consistency...")
                
                result = await session.execute(text("SELECT COUNT(*) FROM users WHERE email IS NULL OR email = ''"))
                users_no_email = result.scalar()
                
                if users_no_email > 0:
                    self.report.add_critical_issue(f"Found {users_no_email} users without email addresses")
                
                # Check for duplicate emails
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM (
                        SELECT email, COUNT(*) as count 
                        FROM users 
                        GROUP BY email 
                        HAVING COUNT(*) > 1
                    ) duplicates
                """))
                duplicate_emails = result.scalar()
                
                if duplicate_emails > 0:
                    self.report.add_critical_issue(f"Found {duplicate_emails} duplicate email addresses")
                
                integrity_checks.update({
                    "orphaned_transactions": orphaned_transactions,
                    "negative_transactions": negative_transactions,
                    "null_amounts": null_amounts,
                    "users_no_email": users_no_email,
                    "duplicate_emails": duplicate_emails
                })
                
                self.report.validation_results["data_integrity"] = integrity_checks
                
        except Exception as e:
            self.report.add_critical_issue(f"Data integrity validation failed: {str(e)}")
    
    async def _validate_performance(self):
        """Validate database performance"""
        print("🔍 5. Validating Database Performance...")
        
        try:
            initialize_database()
            
            async with get_async_db_context() as session:
                performance_metrics = {}
                
                # Test query performance on critical tables
                critical_queries = {
                    "user_count": "SELECT COUNT(*) FROM users",
                    "transaction_count": "SELECT COUNT(*) FROM transactions",
                    "recent_transactions": "SELECT COUNT(*) FROM transactions WHERE spent_at >= NOW() - INTERVAL '30 days'",
                }
                
                for query_name, query in critical_queries.items():
                    start_time = time.time()
                    try:
                        result = await session.execute(text(query))
                        count = result.scalar()
                        end_time = time.time()
                        duration = end_time - start_time
                        
                        performance_metrics[query_name] = {
                            "duration_ms": duration * 1000,
                            "result_count": count,
                            "status": "success"
                        }
                        
                        print(f"    ✅ {query_name}: {duration*1000:.2f}ms, {count} records")
                        
                        # Warn on slow queries
                        if duration > 1.0:  # More than 1 second
                            self.report.add_warning(f"Slow query detected: {query_name} took {duration:.2f}s")
                        
                    except Exception as e:
                        performance_metrics[query_name] = {
                            "status": "error",
                            "error": str(e)
                        }
                        self.report.add_warning(f"Performance test failed for {query_name}: {str(e)}")
                
                self.report.validation_results["performance"] = performance_metrics
                
        except Exception as e:
            self.report.add_critical_issue(f"Performance validation failed: {str(e)}")
    
    async def _validate_backup_system(self):
        """Validate backup and recovery system"""
        print("🔍 6. Validating Backup System...")
        
        backup_status = {
            "backup_scripts_exist": False,
            "recent_backups": [],
            "backup_configuration": {}
        }
        
        # Check for backup scripts
        backup_script_paths = [
            "scripts/backup_database.py",
            "scripts/production_database_backup.py",
            "scripts/pg_backup.sh"
        ]
        
        existing_backup_scripts = []
        for script_path in backup_script_paths:
            full_path = os.path.join(project_root, script_path)
            if os.path.exists(full_path):
                existing_backup_scripts.append(script_path)
                print(f"    ✅ Backup script found: {script_path}")
        
        if existing_backup_scripts:
            backup_status["backup_scripts_exist"] = True
            backup_status["existing_scripts"] = existing_backup_scripts
        else:
            self.report.add_critical_issue("No backup scripts found in expected locations")
        
        # Check for backup directories
        backup_dirs = ["backups/", "backup/"]
        for backup_dir in backup_dirs:
            full_path = os.path.join(project_root, backup_dir)
            if os.path.exists(full_path):
                print(f"    ✅ Backup directory found: {backup_dir}")
                # Check for recent backup files
                backup_files = os.listdir(full_path)
                recent_backups = [f for f in backup_files if f.endswith(('.sql', '.dump', '.gz'))]
                backup_status["recent_backups"] = recent_backups[:5]  # Show last 5
                
        # Check for cron jobs or scheduled backups
        try:
            # Check for backup cron configuration
            cron_files = [
                "/etc/cron.d/mita-backup",
                "/var/spool/cron/crontabs/root",
                os.path.expanduser("~/crontab")
            ]
            
            for cron_file in cron_files:
                if os.path.exists(cron_file):
                    print(f"    ℹ️  Found cron file: {cron_file}")
                    # Note: We won't read the cron file for security reasons
                    
        except Exception as e:
            print(f"    ⚠️ Could not check cron configuration: {str(e)}")
        
        self.report.validation_results["backup_status"] = backup_status
        
        # Recommendations for backup system
        if not existing_backup_scripts:
            self.report.add_recommendation("Implement automated database backup system")
        
        self.report.add_recommendation("Regularly test backup restoration procedures")
        self.report.add_recommendation("Implement point-in-time recovery testing")

async def main():
    """Main validation function"""
    print("🚀 MITA Finance Database Migration Validation")
    print("=" * 80)
    
    # Check for DATABASE_URL in alembic.ini as fallback
    if not os.getenv("DATABASE_URL"):
        alembic_ini_path = os.path.join(project_root, "alembic.ini")
        if os.path.exists(alembic_ini_path):
            print("⚠️ DATABASE_URL not set in environment, checking alembic.ini...")
            with open(alembic_ini_path, 'r') as f:
                content = f.read()
                if "sqlalchemy.url" in content:
                    # Extract URL from alembic.ini
                    import re
                    match = re.search(r'sqlalchemy\.url = (.+)', content)
                    if match:
                        db_url = match.group(1).strip()
                        os.environ["DATABASE_URL"] = db_url
                        print(f"✅ Using DATABASE_URL from alembic.ini")
    
    try:
        validator = MITADatabaseValidator()
        report = await validator.validate_all()
        
        # Save report
        filename = report.save_report()
        
        print(f"\n📊 Full validation report saved to: {filename}")
        
        # Exit with appropriate code
        critical_issues = len(report.validation_results["critical_issues"])
        if critical_issues > 0:
            print(f"\n🚨 CRITICAL: {critical_issues} critical issues found - production deployment should be blocked!")
            sys.exit(1)
        else:
            print(f"\n✅ Validation completed successfully")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 Validation script failed: {str(e)}")
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main())