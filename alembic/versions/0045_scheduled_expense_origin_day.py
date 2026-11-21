"""Scheduled expenses: where each one was made, and the day of the month asked for.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-17

PR #288 review findings P1 and P2 (docs/chatgpt-app/scheduled-obligations-safety.md).
Additive only: two columns and two CHECKs on ``scheduled_expenses``. No row is
removed and no amount, date or status is touched.

``origin`` — one of three values:

* ``app``: made in the mobile app. An instruction that the daily processor
  (``cron_task_scheduled_expenses``) records as an expense on its date.
* ``chatgpt``: an obligation saved in ChatGPT. It is paid only when the user
  links an expense to it (``obligation_payments``), and is never processed or
  pushed.
* ``unknown``: no source recorded. That covers every existing row not proven
  to be ChatGPT's, and any row a writer inserts without stating where it was
  made. It is never processed or pushed either.

The processor acts on ``app`` rows only. Only the app's own create route
writes ``app``; the processor's next occurrence of an ``app`` row keeps it.
So a bill saved in ChatGPT can never become an expense nobody recorded, and a
row of uncertain origin is treated the safe way: it is never turned into an
expense. Nothing runs the processor in production today, so for production
data the only observable change is none.

Backfill. A row becomes ``chatgpt`` only when MITA's own ChatGPT records name
it: the ids the ChatGPT app stored with its ``add_recurring_expense`` calls
(``mcp_idempotency_keys.resource_ids``), matched by id AND user. Every other
existing row becomes ``unknown``. No row becomes ``app``. Production has no
ChatGPT rows: no ChatGPT service has ever run against it, and the
idempotency table is created empty by 0038 in the same upgrade. Those
records are deleted after 30 days, and only when the same user writes again,
so an older ChatGPT row may stay ``unknown``. That is safe: it is never
processed, and its due dates follow the pre-0045 rule exactly.

``day_of_month`` — the day the user asked for (1–31) for a monthly payment.
It is kept apart from ``scheduled_date``, which is clamped to the month:
"the 31st" saved on 10 November is due 30 November, 31 December and 28
February (``monthly_obligations.due_dates_in_month``). It is NULL for every
existing row and for rows without one, which use the date's own day exactly
as before. An original day is never guessed for a record that did not keep
it.

Cost: both ``ADD COLUMN``s are metadata-only on PostgreSQL 11+ (a constant
default, a nullable column). Each CHECK scans the table once while it is
added, and the backfill updates only the matched rows. All of it runs under
the migration transaction's lock on ``scheduled_expenses``.

Downgrade drops both columns and both CHECKs. It loses which rows were made
in the app after this revision and every kept day: a re-upgrade marks such
rows ``unknown`` (never processed) and takes the day from the date again.
"""

import sqlalchemy as sa

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "scheduled_expenses",
        sa.Column("origin", sa.String(16), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "scheduled_expenses",
        sa.Column("day_of_month", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_scheduled_expenses_origin",
        "scheduled_expenses",
        "origin IN ('app', 'chatgpt', 'unknown')",
    )
    op.create_check_constraint(
        "ck_scheduled_expenses_day_of_month",
        "scheduled_expenses",
        "day_of_month IS NULL OR day_of_month BETWEEN 1 AND 31",
    )
    # Only rows the ChatGPT app's own records name, for the same user; a
    # record whose ids are not a JSON array is skipped, never an error that
    # would abort the deployment's boot migration.
    op.execute(
        """
        UPDATE scheduled_expenses AS se
        SET origin = 'chatgpt'
        FROM (
            SELECT k.user_id, ids.value AS expense_id
            FROM mcp_idempotency_keys AS k
            CROSS JOIN LATERAL jsonb_array_elements_text(
                CASE
                    WHEN jsonb_typeof(k.resource_ids) = 'array' THEN k.resource_ids
                    ELSE '[]'::jsonb
                END
            ) AS ids
            WHERE k.operation = 'add_recurring_expense'
        ) AS made_in_chatgpt
        WHERE se.id::text = made_in_chatgpt.expense_id
          AND se.user_id = made_in_chatgpt.user_id
        """
    )


def downgrade():
    op.drop_constraint(
        "ck_scheduled_expenses_day_of_month", "scheduled_expenses", type_="check"
    )
    op.drop_constraint(
        "ck_scheduled_expenses_origin", "scheduled_expenses", type_="check"
    )
    op.drop_column("scheduled_expenses", "day_of_month")
    op.drop_column("scheduled_expenses", "origin")
