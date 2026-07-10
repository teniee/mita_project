"""Enforce INV-16: at most one daily_plan row per (user, day, category).

Duplicate rows came from two sources:
- onboarding re-submits / mobile retries: save_calendar_for_user appended a
  second full set of plan rows (no delete-first, no idempotency guard);
- rows written with a non-midnight time-of-day, which day-range queries then
  treated as the same day while equality lookups did not.

This migration:
1. normalizes daily_plan.date to midnight (day precision);
2. merges duplicates per (user_id, date, category): keeps the earliest row,
   SUMs spent_amount (the .first()-based accrual split spend across
   duplicates) and takes MAX of planned_amount / daily_budget (duplicates
   from re-onboarding carry identical planned values — summing would double
   the budget);
3. adds the composite unique constraint.

The merge logs how many rows were removed. Downgrade drops the constraint
only — merged duplicates are not resurrected.

Revision ID: 0035
Revises: 0034
"""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Normalize to day precision.
    conn.exec_driver_sql("UPDATE daily_plan SET date = date_trunc('day', date)")

    # 2. Merge duplicates into the keeper row (earliest created_at, then id).
    result = conn.exec_driver_sql(
        """
        WITH ranked AS (
            SELECT id, user_id, date, category,
                   row_number() OVER (
                       PARTITION BY user_id, date, category
                       ORDER BY created_at ASC NULLS LAST, id ASC
                   ) AS rn
            FROM daily_plan
            WHERE category IS NOT NULL
        ),
        agg AS (
            SELECT user_id, date, category,
                   SUM(COALESCE(spent_amount, 0)) AS spent_sum,
                   MAX(planned_amount) AS planned_max,
                   MAX(daily_budget) AS budget_max
            FROM daily_plan
            WHERE category IS NOT NULL
            GROUP BY user_id, date, category
            HAVING COUNT(*) > 1
        )
        UPDATE daily_plan dp
        SET spent_amount = agg.spent_sum,
            planned_amount = agg.planned_max,
            daily_budget = agg.budget_max
        FROM ranked, agg
        WHERE dp.id = ranked.id
          AND ranked.rn = 1
          AND ranked.user_id = agg.user_id
          AND ranked.date = agg.date
          AND ranked.category = agg.category
        """
    )

    deleted = conn.exec_driver_sql(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id, date, category
                       ORDER BY created_at ASC NULLS LAST, id ASC
                   ) AS rn
            FROM daily_plan
            WHERE category IS NOT NULL
        )
        DELETE FROM daily_plan
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )
    print(f"[0035] merged daily_plan duplicates: {deleted.rowcount} rows removed")

    # 3. Enforce going forward.
    op.create_unique_constraint(
        "uq_daily_plan_user_date_category",
        "daily_plan",
        ["user_id", "date", "category"],
    )


def downgrade():
    op.drop_constraint("uq_daily_plan_user_date_category", "daily_plan", type_="unique")
