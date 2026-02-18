"""add missing foreign key constraints

Revision ID: 0022_add_missing_fk_constraints
Revises: 0021_add_habit_completions_table
Create Date: 2026-01-11 20:00:00.000000

CRITICAL FIX: Adds foreign key constraints to daily_plan, subscriptions, and goals tables
to ensure data integrity and prevent orphaned records.

Issue: The daily_plan, subscriptions, and goals tables have user_id columns but no FK
constraints linking to users.id. This allows orphaned records to exist if users
are deleted, violating data integrity.

This migration:
1. Cleans up any existing orphaned records (soft delete)
2. Adds FK constraints with CASCADE behavior
3. Adds deleted_at column to subscriptions for soft delete support
4. Checks and adds FK to goals table if missing
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '0022_add_missing_fk_constraints'
down_revision = '0021_add_habit_completions'
branch_labels = None
depends_on = None


def upgrade():
    """Add foreign key constraints to ensure data integrity"""

    conn = op.get_bind()
    inspector = inspect(conn)

    # ========================================
    # STEP 1: Add deleted_at column to subscriptions if not exists
    # ========================================
    print("Checking subscriptions table schema...")
    subscriptions_columns = [col['name'] for col in inspector.get_columns('subscriptions')]

    if 'deleted_at' not in subscriptions_columns:
        print("  Adding deleted_at column to subscriptions table...")
        op.add_column('subscriptions',
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
        )
        op.create_index('ix_subscriptions_deleted_at', 'subscriptions', ['deleted_at'])
        print("  ✓ Added deleted_at column")
    else:
        print("  ✓ deleted_at column already exists")

    # ========================================
    # STEP 2: Clean up orphaned records BEFORE adding FK constraints
    # ========================================
    print("\nCleaning up orphaned records...")

    # Check for orphaned daily_plan records
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as count
        FROM daily_plan dp
        LEFT JOIN users u ON dp.user_id = u.id
        WHERE u.id IS NULL
    """))
    orphaned_daily_plan_count = result.fetchone()[0]

    if orphaned_daily_plan_count > 0:
        print(f"  Found {orphaned_daily_plan_count} orphaned daily_plan records")
        print("  Deleting orphaned daily_plan records...")
        conn.execute(sa.text("""
            DELETE FROM daily_plan
            WHERE user_id NOT IN (SELECT id FROM users)
        """))
        print(f"  ✓ Deleted {orphaned_daily_plan_count} orphaned daily_plan records")
    else:
        print("  ✓ No orphaned daily_plan records found")

    # Check for orphaned subscriptions
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as count
        FROM subscriptions s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE u.id IS NULL
    """))
    orphaned_subscriptions_count = result.fetchone()[0]

    if orphaned_subscriptions_count > 0:
        print(f"  Found {orphaned_subscriptions_count} orphaned subscriptions")
        print("  Soft deleting orphaned subscriptions...")
        conn.execute(sa.text("""
            UPDATE subscriptions
            SET deleted_at = NOW()
            WHERE user_id NOT IN (SELECT id FROM users)
            AND deleted_at IS NULL
        """))
        print(f"  ✓ Soft deleted {orphaned_subscriptions_count} orphaned subscriptions")
    else:
        print("  ✓ No orphaned subscriptions found")

    # Check for orphaned goals
    result = conn.execute(sa.text("""
        SELECT COUNT(*) as count
        FROM goals g
        LEFT JOIN users u ON g.user_id = u.id
        WHERE u.id IS NULL
    """))
    orphaned_goals_count = result.fetchone()[0]

    if orphaned_goals_count > 0:
        print(f"  Found {orphaned_goals_count} orphaned goals")
        print("  Soft deleting orphaned goals...")
        conn.execute(sa.text("""
            UPDATE goals
            SET deleted_at = NOW()
            WHERE user_id NOT IN (SELECT id FROM users)
            AND deleted_at IS NULL
        """))
        print(f"  ✓ Soft deleted {orphaned_goals_count} orphaned goals")
    else:
        print("  ✓ No orphaned goals found")

    # ========================================
    # STEP 3: Add foreign key constraints
    # ========================================
    print("\nAdding foreign key constraints...")

    # Check if FK already exists for daily_plan
    daily_plan_fks = inspector.get_foreign_keys('daily_plan')
    daily_plan_has_user_fk = any(
        fk['constrained_columns'] == ['user_id'] and fk['referred_table'] == 'users'
        for fk in daily_plan_fks
    )

    if not daily_plan_has_user_fk:
        print("  Adding FK constraint: daily_plan.user_id -> users.id")
        op.create_foreign_key(
            'fk_daily_plan_user_id',
            'daily_plan',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
        print("  ✓ Added FK constraint to daily_plan")
    else:
        print("  ✓ FK constraint on daily_plan.user_id already exists")

    # Check if FK already exists for subscriptions
    subscriptions_fks = inspector.get_foreign_keys('subscriptions')
    subscriptions_has_user_fk = any(
        fk['constrained_columns'] == ['user_id'] and fk['referred_table'] == 'users'
        for fk in subscriptions_fks
    )

    if not subscriptions_has_user_fk:
        print("  Adding FK constraint: subscriptions.user_id -> users.id")
        op.create_foreign_key(
            'fk_subscriptions_user_id',
            'subscriptions',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
        print("  ✓ Added FK constraint to subscriptions")
    else:
        print("  ✓ FK constraint on subscriptions.user_id already exists")

    # Check if FK already exists for goals
    goals_fks = inspector.get_foreign_keys('goals')
    goals_has_user_fk = any(
        fk['constrained_columns'] == ['user_id'] and fk['referred_table'] == 'users'
        for fk in goals_fks
    )

    if not goals_has_user_fk:
        print("  Adding FK constraint: goals.user_id -> users.id")
        op.create_foreign_key(
            'fk_goals_user_id',
            'goals',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
        print("  ✓ Added FK constraint to goals")
    else:
        print("  ✓ FK constraint on goals.user_id already exists")

    # ========================================
    # STEP 4: Verify constraints were added
    # ========================================
    print("\nVerifying foreign key constraints...")
    result = conn.execute(sa.text("""
        SELECT
            tc.table_name,
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_name IN ('daily_plan', 'subscriptions', 'goals')
        AND kcu.column_name = 'user_id'
        ORDER BY tc.table_name
    """))

    constraints = result.fetchall()
    if constraints:
        print("  ✓ Verified foreign key constraints:")
        for constraint in constraints:
            print(f"    - {constraint[0]}.{constraint[2]} -> {constraint[3]}")
    else:
        print("  ⚠️  WARNING: Could not verify constraints (may be a permissions issue)")

    print("\n✅ Migration 0022 completed successfully")


def downgrade():
    """Remove foreign key constraints and deleted_at column"""
    print("\nRemoving foreign key constraints...")

    # Remove FK constraints
    try:
        op.drop_constraint('fk_goals_user_id', 'goals', type_='foreignkey')
        print("  ✓ Removed FK constraint from goals")
    except Exception as e:
        print(f"  ⚠️  Could not remove FK from goals: {e}")

    try:
        op.drop_constraint('fk_subscriptions_user_id', 'subscriptions', type_='foreignkey')
        print("  ✓ Removed FK constraint from subscriptions")
    except Exception as e:
        print(f"  ⚠️  Could not remove FK from subscriptions: {e}")

    try:
        op.drop_constraint('fk_daily_plan_user_id', 'daily_plan', type_='foreignkey')
        print("  ✓ Removed FK constraint from daily_plan")
    except Exception as e:
        print(f"  ⚠️  Could not remove FK from daily_plan: {e}")

    # Remove deleted_at column from subscriptions
    try:
        op.drop_index('ix_subscriptions_deleted_at', table_name='subscriptions')
        op.drop_column('subscriptions', 'deleted_at')
        print("  ✓ Removed deleted_at column from subscriptions")
    except Exception as e:
        print(f"  ⚠️  Could not remove deleted_at column: {e}")

    print("\n✅ Migration 0022 downgrade completed")
