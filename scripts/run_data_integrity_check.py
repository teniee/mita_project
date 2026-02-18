#!/usr/bin/env python3
"""
MITA Finance - Data Integrity Check Runner
Executes comprehensive data integrity checks and generates a report
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class DataIntegrityChecker:
    """Runs comprehensive data integrity checks"""

    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = None
        self.issues = []
        self.stats = {}

    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            print("✅ Connected to database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()
        except Exception as e:
            print(f"❌ Query error: {e}")
            return None

    def check_null_values(self):
        """Check for NULL values in critical fields"""
        print("\n🔍 Checking for NULL values in critical fields...")

        checks = [
            ("users", "email", "Email NULL in users"),
            ("users", "password_hash", "Password hash NULL in users"),
            ("transactions", "user_id", "User ID NULL in transactions"),
            ("transactions", "category", "Category NULL in transactions"),
            ("transactions", "amount", "Amount NULL in transactions"),
            ("goals", "user_id", "User ID NULL in goals"),
            ("goals", "title", "Title NULL in goals"),
            ("goals", "target_amount", "Target amount NULL in goals"),
        ]

        for table, column, description in checks:
            query = f"""
                SELECT COUNT(*) as count
                FROM {table}
                WHERE {column} IS NULL
            """
            result = self.execute_query(query)
            if result and result[0]['count'] > 0:
                issue = {
                    'category': 'NULL_VALUES',
                    'severity': 'HIGH',
                    'description': description,
                    'count': result[0]['count'],
                    'table': table,
                    'column': column
                }
                self.issues.append(issue)
                print(f"  ⚠️  {description}: {result[0]['count']} records")

        if not any(i['category'] == 'NULL_VALUES' for i in self.issues):
            print("  ✅ No NULL value issues found")

    def check_foreign_key_integrity(self):
        """Check for orphaned records"""
        print("\n🔍 Checking foreign key integrity...")

        # Orphaned transactions (no user)
        query = """
            SELECT COUNT(*) as count
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE u.id IS NULL
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'ORPHANED_RECORDS',
                'severity': 'CRITICAL',
                'description': 'Transactions with no user',
                'count': result[0]['count'],
                'table': 'transactions'
            })
            print(f"  ⚠️  Orphaned transactions: {result[0]['count']}")

        # Orphaned goals (no user)
        query = """
            SELECT COUNT(*) as count
            FROM goals g
            LEFT JOIN users u ON g.user_id = u.id
            WHERE u.id IS NULL
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'ORPHANED_RECORDS',
                'severity': 'CRITICAL',
                'description': 'Goals with no user',
                'count': result[0]['count'],
                'table': 'goals'
            })
            print(f"  ⚠️  Orphaned goals: {result[0]['count']}")

        # Transactions with invalid goal_id
        query = """
            SELECT COUNT(*) as count
            FROM transactions t
            WHERE t.goal_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM goals g WHERE g.id = t.goal_id
            )
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'ORPHANED_RECORDS',
                'severity': 'HIGH',
                'description': 'Transactions with invalid goal_id',
                'count': result[0]['count'],
                'table': 'transactions'
            })
            print(f"  ⚠️  Transactions with invalid goal_id: {result[0]['count']}")

        if not any(i['category'] == 'ORPHANED_RECORDS' for i in self.issues):
            print("  ✅ No orphaned records found")

    def check_duplicates(self):
        """Check for duplicate records"""
        print("\n🔍 Checking for duplicate records...")

        # Duplicate emails
        query = """
            SELECT email, COUNT(*) as count
            FROM users
            GROUP BY email
            HAVING COUNT(*) > 1
        """
        result = self.execute_query(query)
        if result and len(result) > 0:
            total_dupes = sum(r['count'] for r in result)
            self.issues.append({
                'category': 'DUPLICATES',
                'severity': 'CRITICAL',
                'description': 'Duplicate user emails',
                'count': total_dupes,
                'details': [dict(r) for r in result]
            })
            print(f"  ⚠️  Duplicate emails: {len(result)} unique emails with duplicates")

        # Duplicate daily plan entries
        query = """
            SELECT user_id, date, COUNT(*) as count
            FROM daily_plan
            GROUP BY user_id, date
            HAVING COUNT(*) > 1
        """
        result = self.execute_query(query)
        if result and len(result) > 0:
            self.issues.append({
                'category': 'DUPLICATES',
                'severity': 'HIGH',
                'description': 'Duplicate daily_plan entries',
                'count': len(result)
            })
            print(f"  ⚠️  Duplicate daily_plan entries: {len(result)}")

        if not any(i['category'] == 'DUPLICATES' for i in self.issues):
            print("  ✅ No duplicate records found")

    def check_timestamp_consistency(self):
        """Check for timestamp inconsistencies"""
        print("\n🔍 Checking timestamp consistency...")

        # Transactions with created_at > updated_at
        query = """
            SELECT COUNT(*) as count
            FROM transactions
            WHERE created_at > updated_at
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'TIMESTAMP_ISSUES',
                'severity': 'MEDIUM',
                'description': 'Transactions: created_at > updated_at',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Transactions with created > updated: {result[0]['count']}")

        # Future transactions
        query = """
            SELECT COUNT(*) as count
            FROM transactions
            WHERE spent_at > NOW() + INTERVAL '1 day'
            AND deleted_at IS NULL
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'TIMESTAMP_ISSUES',
                'severity': 'MEDIUM',
                'description': 'Transactions with future dates',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Transactions with future dates: {result[0]['count']}")

        # Goals completed before created
        query = """
            SELECT COUNT(*) as count
            FROM goals
            WHERE completed_at IS NOT NULL
            AND completed_at < created_at
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'TIMESTAMP_ISSUES',
                'severity': 'HIGH',
                'description': 'Goals: completed_at < created_at',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Goals completed before created: {result[0]['count']}")

        if not any(i['category'] == 'TIMESTAMP_ISSUES' for i in self.issues):
            print("  ✅ No timestamp issues found")

    def check_goal_progress(self):
        """Check goal progress calculation accuracy"""
        print("\n🔍 Checking goal progress calculations...")

        # Goals with incorrect progress calculation
        query = """
            SELECT COUNT(*) as count
            FROM goals
            WHERE target_amount > 0
            AND deleted_at IS NULL
            AND ABS(
                progress - (
                    CASE
                        WHEN saved_amount >= target_amount THEN 100
                        ELSE (saved_amount / target_amount * 100)
                    END
                )
            ) > 0.01
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'CALCULATION_ERROR',
                'severity': 'HIGH',
                'description': 'Goals with incorrect progress calculation',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Goals with wrong progress: {result[0]['count']}")

        # Goals with progress > 100 but not completed
        query = """
            SELECT COUNT(*) as count
            FROM goals
            WHERE progress > 100
            AND status != 'completed'
            AND deleted_at IS NULL
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'STATUS_MISMATCH',
                'severity': 'MEDIUM',
                'description': 'Goals: progress > 100 but not completed',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Goals should be completed: {result[0]['count']}")

        # Goals with negative amounts
        query = """
            SELECT COUNT(*) as count
            FROM goals
            WHERE saved_amount < 0
            AND deleted_at IS NULL
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'INVALID_DATA',
                'severity': 'HIGH',
                'description': 'Goals with negative saved_amount',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Goals with negative saved amount: {result[0]['count']}")

        if not any(i['category'] in ['CALCULATION_ERROR', 'STATUS_MISMATCH'] for i in self.issues):
            print("  ✅ Goal progress calculations are correct")

    def check_user_data_completeness(self):
        """Check for incomplete user onboarding data"""
        print("\n🔍 Checking user data completeness...")

        # Users marked onboarded but missing income
        query = """
            SELECT COUNT(*) as count
            FROM users
            WHERE (monthly_income IS NULL OR monthly_income = 0)
            AND has_onboarded = true
        """
        result = self.execute_query(query)
        if result and result[0]['count'] > 0:
            self.issues.append({
                'category': 'INCOMPLETE_DATA',
                'severity': 'MEDIUM',
                'description': 'Onboarded users without monthly_income',
                'count': result[0]['count']
            })
            print(f"  ⚠️  Onboarded users without income: {result[0]['count']}")

        # Users onboarded but no transactions
        query = """
            SELECT COUNT(*) as count
            FROM users u
            WHERE u.has_onboarded = true
            AND NOT EXISTS (
                SELECT 1 FROM transactions t
                WHERE t.user_id = u.id
                AND t.deleted_at IS NULL
            )
        """
        result = self.execute_query(query)
        if result:
            self.stats['users_no_transactions'] = result[0]['count']
            print(f"  ℹ️  Onboarded users with no transactions: {result[0]['count']} (not necessarily an issue)")

        if not any(i['category'] == 'INCOMPLETE_DATA' for i in self.issues):
            print("  ✅ User data is complete")

    def get_database_stats(self):
        """Get overall database statistics"""
        print("\n📊 Gathering database statistics...")

        tables = ['users', 'transactions', 'goals', 'daily_plan', 'habits']

        for table in tables:
            query = f"SELECT COUNT(*) as count FROM {table}"
            try:
                result = self.execute_query(query)
                if result:
                    self.stats[f'{table}_count'] = result[0]['count']
                    print(f"  {table}: {result[0]['count']} records")
            except:
                # Table might not exist
                pass

    def generate_report(self):
        """Generate a comprehensive report"""
        print("\n" + "="*60)
        print("DATA INTEGRITY CHECK REPORT")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Total Issues Found: {len(self.issues)}")
        print()

        # Group by severity
        critical = [i for i in self.issues if i['severity'] == 'CRITICAL']
        high = [i for i in self.issues if i['severity'] == 'HIGH']
        medium = [i for i in self.issues if i['severity'] == 'MEDIUM']

        if critical:
            print(f"🔴 CRITICAL: {len(critical)} issues")
            for issue in critical:
                print(f"   - {issue['description']}: {issue.get('count', 'N/A')} records")

        if high:
            print(f"🟠 HIGH: {len(high)} issues")
            for issue in high:
                print(f"   - {issue['description']}: {issue.get('count', 'N/A')} records")

        if medium:
            print(f"🟡 MEDIUM: {len(medium)} issues")
            for issue in medium:
                print(f"   - {issue['description']}: {issue.get('count', 'N/A')} records")

        if not self.issues:
            print("✅ No data integrity issues found!")

        print("\n" + "="*60)

        # Save detailed report
        report_file = f"data_integrity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'stats': self.stats,
                'issues': self.issues
            }, f, indent=2)

        print(f"📄 Detailed report saved to: {report_file}")

        return len(critical), len(high), len(medium)

    def run_all_checks(self):
        """Run all integrity checks"""
        if not self.connect():
            return False

        try:
            self.get_database_stats()
            self.check_null_values()
            self.check_foreign_key_integrity()
            self.check_duplicates()
            self.check_timestamp_consistency()
            self.check_goal_progress()
            self.check_user_data_completeness()

            critical, high, medium = self.generate_report()

            # Return exit code based on severity
            if critical > 0:
                return 2  # Critical issues
            elif high > 0:
                return 1  # High priority issues
            else:
                return 0  # Success

        except Exception as e:
            print(f"\n❌ Error during checks: {e}")
            import traceback
            traceback.print_exc()
            return 3
        finally:
            if self.conn:
                self.conn.close()


def main():
    """Main entry point"""
    print("MITA Finance - Data Integrity Checker")
    print("=" * 60)

    # Get DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        print("❌ DATABASE_URL environment variable is not set")
        print("\nPlease set your DATABASE_URL:")
        print("export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'")
        return 1

    # Run checks
    checker = DataIntegrityChecker(db_url)
    return checker.run_all_checks()


if __name__ == "__main__":
    sys.exit(main())
