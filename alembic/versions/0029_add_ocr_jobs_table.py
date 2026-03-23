"""add ocr_jobs table

Adds the ocr_jobs table required for tracking OCR receipt processing jobs.
Without this table the app crashes on the first POST to any OCR or
receipt-upload endpoint because OCRJob inserts fail with
"relation ocr_jobs does not exist".

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table('ocr_jobs'):
        return  # table already exists (e.g. created via create_all) — skip idempotently

    op.create_table(
        'ocr_jobs',
        # Primary key
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        # Unique business-level identifier: "ocr_<userid>_<timestamp>"
        sa.Column('job_id', sa.String(100), nullable=False),
        # Owner — hard FK so orphaned rows are impossible
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),

        # --- Status tracking ---
        # Allowed values: pending | processing | completed | failed
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        # 0.00–100.00
        sa.Column('progress', sa.Numeric(5, 2), nullable=False, server_default='0'),

        # --- File information ---
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),

        # --- OCR results ---
        sa.Column('store_name', sa.String(200), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('date', sa.String(50), nullable=True),
        sa.Column('category_hint', sa.String(50), nullable=True),
        # 0.00–100.00
        sa.Column('confidence', sa.Numeric(5, 2), nullable=False, server_default='0'),
        # Full OCR provider response stored as JSONB for efficient querying
        sa.Column('raw_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # --- Error handling ---
        sa.Column('error_message', sa.Text(), nullable=True),
        # Max 999 retries (Numeric(3,0))
        sa.Column('retry_count', sa.Numeric(3, 0), nullable=False, server_default='0'),

        # --- Timestamps ---
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint on job_id — enforced at DB level, not just app level
    op.create_unique_constraint('uq_ocr_jobs_job_id', 'ocr_jobs', ['job_id'])

    # Index: look up a job by its business ID (most common query pattern)
    op.create_index('ix_ocr_jobs_job_id', 'ocr_jobs', ['job_id'])

    # Index: all jobs for a user ordered by creation time (status polling, history)
    op.create_index(
        'ix_ocr_jobs_user_id_created_at',
        'ocr_jobs',
        ['user_id', 'created_at'],
    )

    # Index: queue worker queries — fetch pending/processing jobs by status
    op.create_index('ix_ocr_jobs_status', 'ocr_jobs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_ocr_jobs_status', table_name='ocr_jobs')
    op.drop_index('ix_ocr_jobs_user_id_created_at', table_name='ocr_jobs')
    op.drop_index('ix_ocr_jobs_job_id', table_name='ocr_jobs')
    op.drop_constraint('uq_ocr_jobs_job_id', 'ocr_jobs', type_='unique')
    op.drop_table('ocr_jobs')
