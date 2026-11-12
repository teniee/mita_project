"""Regional reference data (migration 0044) — shared, never per user.

Official statistics MITA ingests on a schedule (``app/regional``) and the MCP
service reads (``app/mcp/queries/regional.py``). No column refers to a user:
a user's confirmed country selects rows, nothing about the user is stored
here. See the migration for what every column means.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base

PROVIDERS = ("eurostat", "worldbank", "oecd")
UNIT_KINDS = (
    "percent_change",
    "index",
    "price_level_index",
    "per_mille",
    "currency_amount",
    "ratio",
)


class RegionalIngestionRun(Base):
    __tablename__ = "regional_ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('eurostat', 'worldbank', 'oecd')",
            name="ck_regional_ingestion_runs_provider",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')",
            name="ck_regional_ingestion_runs_status",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(16), nullable=False)
    dataset = Column(String(96), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False)
    requests = Column(Integer, nullable=False, default=0)
    observations = Column(Integer, nullable=False, default=0)
    inserted = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    unchanged = Column(Integer, nullable=False, default=0)
    rejected = Column(Integer, nullable=False, default=0)
    error_class = Column(String(64), nullable=True)


class RegionalObservation(Base):
    __tablename__ = "regional_observations"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "dataset",
            "series_key",
            "period",
            name="uq_regional_observations_series_period",
        ),
        CheckConstraint(
            "provider IN ('eurostat', 'worldbank', 'oecd')",
            name="ck_regional_observations_provider",
        ),
        CheckConstraint(
            "unit_kind IN ('percent_change', 'index', 'price_level_index', "
            "'per_mille', 'currency_amount', 'ratio')",
            name="ck_regional_observations_unit_kind",
        ),
        CheckConstraint(
            "geo_level IN ('country', 'region')", name="ck_regional_observations_geo"
        ),
        CheckConstraint(
            "period_type IN ('month', 'quarter', 'half_year', 'year')",
            name="ck_regional_observations_period_type",
        ),
        CheckConstraint(
            "(unit_kind = 'currency_amount') = (currency IS NOT NULL)",
            name="ck_regional_observations_currency",
        ),
        CheckConstraint(
            "classification IS NULL OR classification IN ('COICOP_2018', 'COICOP_1999')",
            name="ck_regional_observations_classification",
        ),
        Index(
            "ix_regional_observations_geo_indicator",
            "geo_code",
            "indicator",
            "period_start",
        ),
    )

    id = Column(BigInteger, Identity(), primary_key=True)
    provider = Column(String(16), nullable=False)
    dataset = Column(String(96), nullable=False)
    series_key = Column(String(160), nullable=False)
    indicator = Column(String(48), nullable=False)
    classification = Column(String(16), nullable=True)
    category = Column(String(16), nullable=True)
    category_label = Column(String(120), nullable=True)
    geo_level = Column(String(16), nullable=False)
    geo_code = Column(String(8), nullable=False)
    period = Column(String(10), nullable=False)
    period_type = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=False)
    value = Column(Numeric(20, 6), nullable=False)
    unit_kind = Column(String(24), nullable=False)
    unit = Column(String(120), nullable=False)
    currency = Column(String(3), nullable=True)
    base_period = Column(String(24), nullable=True)
    provider_status = Column(String(8), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    ingestion_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("regional_ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url = Column(Text, nullable=False)
    transformation = Column(String(200), nullable=False)
    license = Column(String(120), nullable=False)
    quality_flags = Column(JSONB, nullable=False, default=list)
