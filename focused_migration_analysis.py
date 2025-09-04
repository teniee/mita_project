#!/usr/bin/env python3
"""
MITA Finance Database Migration Analysis
=====================================
Focused analysis of migration state and critical database issues
using direct database connection from alembic.ini
"""

import os
import sys
import json
import subprocess
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any
import re

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor

class MigrationAnalyzer:
    def __init__(self):
        self.report = {
            "timestamp": datetime.utcnow().isoformat(),
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "migration_analysis": {},
            "schema_analysis": {},
            "data_integrity": {},
            "connection_analysis": {}
        }
        self.db_url = None
        
    def extract_db_url_from_alembic(self):
        """Extract database URL from alembic.ini"""
        alembic_ini = os.path.join(project_root, "alembic.ini")
        if not os.path.exists(alembic_ini):
            raise Exception("alembic.ini not found")
            
        with open(alembic_ini, 'r') as f:
            content = f.read()
            
        match = re.search(r'sqlalchemy\.url = (.+)', content)
        if not match:
            raise Exception("Could not find sqlalchemy.url in alembic.ini")
            
        self.db_url = match.group(1).strip()
        print(f"✅ Database URL extracted from alembic.ini")
        return self.db_url
    
    def add_critical_issue(self, issue: str):
        self.report["critical_issues"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "issue": issue
        })
        print(f"🚨 CRITICAL: {issue}")
    
    def add_warning(self, warning: str):
        self.report["warnings"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "warning": warning
        })
        print(f"⚠️ WARNING: {warning}")
    
    def add_recommendation(self, rec: str):
        self.report["recommendations"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "recommendation": rec
        })
        print(f"💡 RECOMMENDATION: {rec}")
    
    def analyze_migration_state(self):
        """Analyze current migration state"""
        print("🔍 1. Analyzing Migration State...")
        
        # Check Alembic current state
        try:
            result = subprocess.run(
                ["python3", "-m", "alembic", "current"], 
                capture_output=True, text=True, cwd=project_root
            )
            alembic_current = result.stdout.strip()
            print(f"  Alembic current: {alembic_current}")
        except Exception as e:
            alembic_current = f"ERROR: {str(e)}"
            self.add_critical_issue(f"Cannot determine Alembic state: {str(e)}")
        
        # Check for dual migration systems
        alembic_dir = os.path.join(project_root, "alembic")
        migrations_dir = os.path.join(project_root, "migrations")
        
        dual_systems = os.path.exists(alembic_dir) and os.path.exists(migrations_dir)
        if dual_systems:
            self.add_critical_issue("DUAL MIGRATION SYSTEMS: Both alembic/ and migrations/ exist")
        
        # List migrations in both systems
        alembic_migrations = []
        if os.path.exists(os.path.join(alembic_dir, "versions")):
            alembic_migrations = [f for f in os.listdir(os.path.join(alembic_dir, "versions")) 
                                if f.endswith('.py') and not f.startswith('__')]
        
        newer_migrations = []
        if os.path.exists(os.path.join(migrations_dir, "versions")):
            newer_migrations = [f for f in os.listdir(os.path.join(migrations_dir, "versions")) 
                              if f.endswith('.py') and not f.startswith('__')]
        
        self.report["migration_analysis"] = {
            "alembic_current": alembic_current,
            "dual_systems": dual_systems,
            "alembic_migrations": sorted(alembic_migrations),
            "newer_migrations": sorted(newer_migrations)
        }
        
        if newer_migrations and dual_systems:
            self.add_critical_issue(f"Newer migrations exist that may not be applied: {newer_migrations}")
    
    def analyze_database_schema(self):
        """Analyze database schema directly"""
        print("🔍 2. Analyzing Database Schema...")
        
        try:
            # Parse the psycopg2 connection string
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get all tables
            cursor.execute("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            table_names = [t['table_name'] for t in tables]
            print(f"  Found {len(table_names)} tables: {', '.join(table_names[:10])}...")
            
            # Check critical financial tables
            critical_tables = ['users', 'transactions', 'expenses', 'goals']
            missing_critical = [t for t in critical_tables if t not in table_names]
            
            if missing_critical:
                self.add_critical_issue(f"Missing critical tables: {missing_critical}")
            else:
                print("  ✅ All critical financial tables exist")
            
            # Check financial data types
            self.check_financial_data_types(cursor)
            
            # Check for foreign key constraints
            self.check_foreign_keys(cursor)
            
            # Check indexes
            self.check_indexes(cursor)
            
            self.report["schema_analysis"] = {
                "total_tables": len(table_names),
                "table_names": table_names,
                "missing_critical_tables": missing_critical
            }
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.add_critical_issue(f"Database schema analysis failed: {str(e)}")
    
    def check_financial_data_types(self, cursor):
        """Check financial columns use proper data types"""
        print("  🔍 Checking financial data types...")
        
        # Check critical financial columns
        financial_checks = [
            ("transactions", "amount"),
            ("expenses", "amount"),
            ("users", "annual_income"),
            ("goals", "target_amount"),
            ("goals", "saved_amount")
        ]
        
        for table, column in financial_checks:
            try:
                cursor.execute("""
                    SELECT data_type, numeric_precision, numeric_scale
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (table, column))
                
                result = cursor.fetchone()
                if result:
                    data_type = result['data_type']
                    precision = result['numeric_precision']
                    scale = result['numeric_scale']
                    
                    if data_type == 'double precision':  # PostgreSQL FLOAT
                        self.add_critical_issue(
                            f"Table {table}.{column} uses FLOAT (double precision) - should use NUMERIC for financial precision"
                        )
                    elif data_type == 'numeric' and precision and scale:
                        print(f"    ✅ {table}.{column}: NUMERIC({precision},{scale})")
                    else:
                        self.add_warning(f"Table {table}.{column} has unexpected type: {data_type}")
                        
            except Exception as e:
                self.add_warning(f"Could not check {table}.{column}: {str(e)}")
    
    def check_foreign_keys(self, cursor):
        """Check foreign key constraints"""
        print("  🔍 Checking foreign key constraints...")
        
        cursor.execute("""
            SELECT 
                tc.table_name, 
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """)
        
        foreign_keys = cursor.fetchall()
        fk_count = len(foreign_keys)
        print(f"    Found {fk_count} foreign key constraints")
        
        # Check for expected foreign keys
        expected_fks = [
            ("transactions", "user_id", "users"),
            ("expenses", "user_id", "users"),
            ("goals", "user_id", "users"),
        ]
        
        existing_fks = [(fk['table_name'], fk['column_name'], fk['foreign_table_name']) for fk in foreign_keys]
        
        missing_fks = []
        for table, column, ref_table in expected_fks:
            if (table, column, ref_table) not in existing_fks:
                missing_fks.append(f"{table}.{column} -> {ref_table}")
        
        if missing_fks:
            self.add_critical_issue(f"Missing foreign key constraints: {missing_fks}")
        else:
            print("    ✅ Critical foreign key constraints exist")
    
    def check_indexes(self, cursor):
        """Check database indexes"""
        print("  🔍 Checking database indexes...")
        
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        indexes = cursor.fetchall()
        print(f"    Found {len(indexes)} indexes")
        
        # Check for critical performance indexes
        critical_indexes = [
            "transactions_user_id",
            "transactions_spent_at",
            "expenses_user_id"
        ]
        
        index_names = [idx['indexname'] for idx in indexes]
        missing_indexes = []
        
        for critical_idx in critical_indexes:
            if not any(critical_idx in idx_name for idx_name in index_names):
                missing_indexes.append(critical_idx)
        
        if missing_indexes:
            self.add_warning(f"Missing performance indexes: {missing_indexes}")
    
    def check_data_integrity(self):
        """Check data integrity"""
        print("🔍 3. Checking Data Integrity...")
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            integrity_issues = []
            
            # Check for orphaned records
            queries = [
                ("orphaned_transactions", "SELECT COUNT(*) FROM transactions t LEFT JOIN users u ON t.user_id = u.id WHERE u.id IS NULL"),
                ("null_transaction_amounts", "SELECT COUNT(*) FROM transactions WHERE amount IS NULL"),
                ("negative_transactions", "SELECT COUNT(*) FROM transactions WHERE amount < 0"),
                ("users_no_email", "SELECT COUNT(*) FROM users WHERE email IS NULL OR email = ''"),
                ("duplicate_emails", "SELECT COUNT(*) FROM (SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1) AS dups")
            ]
            
            for check_name, query in queries:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    
                    if count > 0:
                        if check_name in ['orphaned_transactions', 'null_transaction_amounts', 'users_no_email', 'duplicate_emails']:
                            self.add_critical_issue(f"Data integrity issue - {check_name}: {count} records")
                        else:
                            self.add_warning(f"Data issue - {check_name}: {count} records")
                    else:
                        print(f"    ✅ {check_name}: OK")
                        
                    integrity_issues.append({check_name: count})
                    
                except Exception as e:
                    print(f"    ⚠️ Could not check {check_name}: {str(e)}")
            
            self.report["data_integrity"] = integrity_issues
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.add_critical_issue(f"Data integrity check failed: {str(e)}")
    
    async def test_connection_performance(self):
        """Test connection pool performance"""
        print("🔍 4. Testing Connection Performance...")
        
        try:
            # Convert psycopg2 URL to asyncpg format
            db_url = self.db_url.replace("postgresql://", "").replace("postgres://", "")
            
            # Parse connection details
            match = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
            if not match:
                self.add_critical_issue("Cannot parse database URL for performance testing")
                return
            
            user, password, host, port, database = match.groups()
            
            # Test different pool sizes
            performance_results = {}
            
            for pool_size in [5, 10, 20]:
                print(f"  Testing pool size: {pool_size}")
                
                start_time = time.time()
                try:
                    pool = await asyncpg.create_pool(
                        user=user,
                        password=password,
                        database=database,
                        host=host,
                        port=int(port),
                        min_size=pool_size//2,
                        max_size=pool_size
                    )
                    
                    # Run concurrent queries
                    async def test_query():
                        async with pool.acquire() as conn:
                            return await conn.fetchval("SELECT COUNT(*) FROM users")
                    
                    # Test 10 concurrent connections
                    tasks = [test_query() for _ in range(10)]
                    results = await asyncio.gather(*tasks)
                    
                    duration = time.time() - start_time
                    qps = 10 / duration
                    
                    performance_results[f"pool_{pool_size}"] = {
                        "duration_seconds": duration,
                        "queries_per_second": qps,
                        "user_count": results[0] if results else 0
                    }
                    
                    print(f"    ✅ Pool {pool_size}: {duration:.2f}s, {qps:.1f} QPS")
                    
                    await pool.close()
                    
                except Exception as e:
                    performance_results[f"pool_{pool_size}"] = {"error": str(e)}
                    self.add_warning(f"Pool size {pool_size} test failed: {str(e)}")
            
            self.report["connection_analysis"] = performance_results
            
        except Exception as e:
            self.add_critical_issue(f"Connection performance test failed: {str(e)}")
    
    def save_report(self):
        """Save analysis report"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"migration_analysis_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        print(f"📊 Analysis report saved to: {filename}")
        return filename

async def main():
    print("🚀 MITA Finance Migration Analysis")
    print("=" * 60)
    
    analyzer = MigrationAnalyzer()
    
    try:
        # Extract database URL
        analyzer.extract_db_url_from_alembic()
        
        # Run analysis
        analyzer.analyze_migration_state()
        analyzer.analyze_database_schema()
        analyzer.check_data_integrity()
        await analyzer.test_connection_performance()
        
        # Save report
        filename = analyzer.save_report()
        
        print("=" * 60)
        print(f"📊 Analysis completed - Report: {filename}")
        
        # Summary
        critical_count = len(analyzer.report["critical_issues"])
        warning_count = len(analyzer.report["warnings"])
        
        print(f"🔍 Found {critical_count} critical issues, {warning_count} warnings")
        
        if critical_count > 0:
            print("🚨 CRITICAL ISSUES REQUIRE IMMEDIATE ATTENTION")
            for issue in analyzer.report["critical_issues"]:
                print(f"  • {issue['issue']}")
            return 1
        else:
            print("✅ No critical issues found")
            return 0
            
    except Exception as e:
        print(f"💥 Analysis failed: {str(e)}")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)