"""Regional reference data: official statistics, normalized, with provenance.

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-04

Additive only: two new tables, no user column, no change to any existing row
(docs/chatgpt-app/personalization-2.8.md, Milestone 2).

``regional_observations`` holds official statistics MITA ingested on a
schedule — shared reference data, never per user, never fetched during a
tool call. One row per provider series and period; every value says what it
is:

* ``unit_kind`` — ``percent_change`` (an inflation rate), ``index`` (a price
  index with its ``base_period``), ``price_level_index`` (a PPP-based price
  level against ``base_period``, e.g. EU27_2020 = 100), ``per_mille`` (a
  share of household spending), ``currency_amount`` (an average price paid,
  e.g. EUR per kWh of household electricity); never mixed in one column
  without it;
* ``unit`` — the provider's own wording with what it covers; ``currency``
  exactly when the value is an amount of money (checked);
* ``classification`` — ``COICOP_2018`` (Eurostat HICP ver.2, OECD) or
  ``COICOP_1999`` (Eurostat PPP and HBS): "CP12" means different things in
  them;
* provenance — provider, dataset, series key, the exact request URL, the
  provider's update time, MITA's retrieval time, the ingestion run, the
  transformation applied ("none" for every first dataset), the licence, the
  provider's status flag and MITA's quality flags (``provisional``,
  ``estimated``, ``break_suspected``, ``revised``).

``regional_ingestion_runs`` records each ingestion (counts and an error class
only — never a response body). A value never becomes zero for being
missing: a missing cell is not stored.

The MCP role reads observations only (``GRANT SELECT``); ingestion runs with
its own role (scripts/mcp/regional_ingest_role.sql).

Downgrade drops both tables: MITA then shows no regional statistics.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "regional_ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("dataset", sa.String(length=96), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "provider IN ('eurostat', 'worldbank', 'oecd')",
            name="ck_regional_ingestion_runs_provider",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')",
            name="ck_regional_ingestion_runs_status",
        ),
    )
    op.create_table(
        "regional_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("dataset", sa.String(length=96), nullable=False),
        sa.Column("series_key", sa.String(length=160), nullable=False),
        sa.Column("indicator", sa.String(length=48), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=True),
        sa.Column("category_label", sa.String(length=120), nullable=True),
        sa.Column("geo_level", sa.String(length=16), nullable=False),
        sa.Column("geo_code", sa.String(length=8), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit_kind", sa.String(length=24), nullable=False),
        sa.Column("unit", sa.String(length=120), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("base_period", sa.String(length=24), nullable=True),
        sa.Column("provider_status", sa.String(length=8), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingestion_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regional_ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("transformation", sa.String(length=200), nullable=False),
        sa.Column("license", sa.String(length=120), nullable=False),
        sa.Column(
            "quality_flags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.UniqueConstraint(
            "provider",
            "dataset",
            "series_key",
            "period",
            name="uq_regional_observations_series_period",
        ),
        sa.CheckConstraint(
            "provider IN ('eurostat', 'worldbank', 'oecd')",
            name="ck_regional_observations_provider",
        ),
        sa.CheckConstraint(
            "unit_kind IN ('percent_change', 'index', 'price_level_index', "
            "'per_mille', 'currency_amount', 'ratio')",
            name="ck_regional_observations_unit_kind",
        ),
        sa.CheckConstraint(
            "geo_level IN ('country', 'region')", name="ck_regional_observations_geo"
        ),
        sa.CheckConstraint(
            "period_type IN ('month', 'quarter', 'half_year', 'year')",
            name="ck_regional_observations_period_type",
        ),
        sa.CheckConstraint(
            "(unit_kind = 'currency_amount') = (currency IS NOT NULL)",
            name="ck_regional_observations_currency",
        ),
        sa.CheckConstraint(
            "classification IS NULL OR classification IN ('COICOP_2018', 'COICOP_1999')",
            name="ck_regional_observations_classification",
        ),
    )
    op.create_index(
        "ix_regional_observations_geo_indicator",
        "regional_observations",
        ["geo_code", "indicator", "period_start"],
    )


def downgrade():
    op.drop_index(
        "ix_regional_observations_geo_indicator", table_name="regional_observations"
    )
    op.drop_table("regional_observations")
    op.drop_table("regional_ingestion_runs")
