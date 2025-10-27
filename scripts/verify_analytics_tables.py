#!/usr/bin/env python3
"""
Verify Analytics Tables Script
This script checks if analytics tables exist and are properly configured
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")

def check_database_connection(db_url):
    """Check if we can connect to the database"""
    print_header("Checking Database Connection")

    try:
        conn = psycopg2.connect(db_url)
        print_success("Successfully connected to database")

        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print_info(f"PostgreSQL version: {version.split(',')[0]}")

        conn.close()
        return True
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return False

def check_table_exists(conn, table_name):
    """Check if a table exists"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            );
        """, (table_name,))
        return cur.fetchone()['exists']

def get_table_info(conn, table_name):
    """Get detailed information about a table"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get column information
        cur.execute("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        columns = cur.fetchall()

        # Get index information
        cur.execute("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = %s;
        """, (table_name,))
        indexes = cur.fetchall()

        # Get row count
        cur.execute(f"SELECT COUNT(*) as count FROM {table_name};")
        row_count = cur.fetchone()['count']

        return {
            'columns': columns,
            'indexes': indexes,
            'row_count': row_count
        }

def verify_analytics_tables(db_url):
    """Main verification function"""
    print_header(f"Analytics Tables Verification - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tables = [
        'feature_usage_logs',
        'feature_access_logs',
        'paywall_impression_logs'
    ]

    try:
        conn = psycopg2.connect(db_url)

        all_tables_exist = True

        for table_name in tables:
            print(f"\n{'─'*60}")
            print(f"Checking table: {table_name}")
            print(f"{'─'*60}")

            if check_table_exists(conn, table_name):
                print_success(f"Table '{table_name}' exists")

                # Get detailed info
                info = get_table_info(conn, table_name)

                # Show column count
                print_info(f"Columns: {len(info['columns'])}")

                # Show some key columns
                key_columns = ['id', 'user_id', 'timestamp']
                found_columns = [col['column_name'] for col in info['columns'] if col['column_name'] in key_columns]
                if found_columns:
                    print_info(f"Key columns found: {', '.join(found_columns)}")

                # Show indexes
                print_info(f"Indexes: {len(info['indexes'])}")
                for idx in info['indexes']:
                    print(f"    - {idx['indexname']}")

                # Show row count
                print_info(f"Current rows: {info['row_count']}")

            else:
                print_error(f"Table '{table_name}' does NOT exist")
                all_tables_exist = False

        conn.close()

        # Summary
        print_header("Verification Summary")

        if all_tables_exist:
            print_success("All analytics tables are properly configured!")
            print_info("You can now use the analytics module")
            return 0
        else:
            print_error("Some analytics tables are missing")
            print_info("Run the migration script to create them:")
            print_info("  ./scripts/apply_analytics_migration.sh")
            return 1

    except Exception as e:
        print_error(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main entry point"""
    # Check for DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        print_error("DATABASE_URL environment variable is not set")
        print_info("\nPlease set your Supabase DATABASE_URL:")
        print_info("export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'")
        print_info("\nExample:")
        print_info("export DATABASE_URL='postgresql://postgres:mypassword@db.xxxxx.supabase.co:5432/postgres'")
        return 1

    # Check connection first
    if not check_database_connection(db_url):
        return 1

    # Verify tables
    return verify_analytics_tables(db_url)

if __name__ == "__main__":
    sys.exit(main())
