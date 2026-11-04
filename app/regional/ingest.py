"""Ingest MITA's regional reference data (a batch job, never a tool call).

    DATABASE_URL=postgresql://<ingest role>@.../db \\
        python -m app.regional.ingest [--provider eurostat|worldbank|oecd|all]
        [--dry-run]

For each dataset of ``app/regional/catalog.py``: one run row; one request
per dataset (World Bank: per page), spaced and retried
(``app/regional/http.py``); every cell parsed into a checked
``Observation``; then an idempotent upsert keyed by provider, dataset, series
and period:

* new → inserted; same value and status → unchanged (``retrieved_at``
  refreshed: "last confirmed");
* changed → updated, flagged ``revised``; a level that moves by more than
  30 % (``price_level_index``, ``per_mille``, ``index``) is also flagged
  ``break_suspected`` — e.g. a series re-denominated into another currency
  (BGN → EUR divides by 1.95583: a 48.9 % move); price levels and spending
  shares move by a few per cent a year;
* a provider that fails leaves every stored row as it was: the run is
  ``failed`` with its error class, and readers keep the last good values
  (shown as stale once they age).

Logs carry provider, dataset and counts only — never a response body.
Refuses ``ENVIRONMENT=production``: ingestion is staging-only until the
owner approves it for production.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models.regional import RegionalIngestionRun, RegionalObservation
from app.regional import catalog
from app.regional.catalog import Dataset
from app.regional.http import ACCEPT_JSON, Fetcher, ProviderError
from app.regional.observations import Observation
from app.regional.providers import eurostat, oecd, worldbank

logger = logging.getLogger("app.regional")

LEVEL_KINDS = {"price_level_index", "per_mille", "index"}
BREAK_RATIO = Decimal("0.3")


@dataclass
class RunResult:
    provider: str
    dataset: str
    status: str
    requests: int = 0
    observations: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    error_class: Optional[str] = None


def since_period(spec: Dataset, today: date) -> str:
    """How far back to ask: about a year of a monthly series, a few years of
    an annual one (the latest household survey is older: from 2015)."""
    if spec.period_type == "month":
        index = today.year * 12 + today.month - 1 - 14
        return f"{index // 12:04d}-{index % 12 + 1:02d}"
    if spec.period_type == "half_year":
        return f"{today.year - 2}-S1"
    if spec.dataset == "hbs_str_t211":
        return "2015"
    return str(today.year - 4)


def fetch_observations(
    fetcher: Fetcher, spec: Dataset, today: date
) -> tuple[List[Observation], int]:
    """Every observation the provider has for ``spec`` (and the rejected
    cells), for MITA's countries."""
    if spec.provider == catalog.EUROSTAT:
        url = eurostat.request_url(
            spec, catalog.EUROSTAT_COUNTRIES, since_period(spec, today)
        )
        response = fetcher.get(spec.provider, url, headers={"Accept": ACCEPT_JSON})
        return eurostat.parse(spec, response.json(), url)
    if spec.provider == catalog.WORLD_BANK:
        found: List[Observation] = []
        rejected = 0
        page, total = 1, 1
        while page <= total:
            url = worldbank.request_url(spec, page)
            payload = fetcher.get(
                spec.provider, url, headers={"Accept": ACCEPT_JSON}
            ).json()
            rows, bad = worldbank.parse(spec, payload, url)
            found += rows
            rejected += bad
            total = min(worldbank.pages(payload), 20)
            page += 1
        return found, rejected
    if spec.provider == catalog.OECD:
        url = oecd.request_url(spec, sorted(catalog.OECD_AREAS))
        response = fetcher.get(spec.provider, url, headers={"Accept": oecd.ACCEPT})
        return oecd.parse(spec, response.text, url)
    raise ValueError(spec.provider)


def _relative_change(old: Decimal, new: Decimal) -> Decimal:
    if old == 0:
        return Decimal("1") if new != 0 else Decimal("0")
    return abs(new - old) / abs(old)


def upsert(
    session: Session,
    observations: Sequence[Observation],
    run_id: uuid.UUID,
    now: datetime,
) -> Dict[str, int]:
    """Insert, update or confirm each observation; counts by outcome."""
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    if not observations:
        return counts
    unique: Dict[tuple, Observation] = {}
    for obs in observations:
        unique[obs.key] = obs  # a repeated cell counts once (last wins)
    providers = {o.provider for o in unique.values()}
    datasets = {o.dataset for o in unique.values()}
    existing = {
        (r.provider, r.dataset, r.series_key, r.period): r
        for r in session.scalars(
            select(RegionalObservation).where(
                RegionalObservation.provider.in_(providers),
                RegionalObservation.dataset.in_(datasets),
                RegionalObservation.period.in_({o.period for o in unique.values()}),
            )
        )
    }
    for key, obs in unique.items():
        row = existing.get(key)
        if row is None:
            session.add(
                RegionalObservation(
                    provider=obs.provider,
                    dataset=obs.dataset,
                    series_key=obs.series_key,
                    indicator=obs.indicator,
                    classification=obs.classification,
                    category=obs.category,
                    category_label=obs.category_label,
                    geo_level=obs.geo_level,
                    geo_code=obs.geo_code,
                    period=obs.period,
                    period_type=obs.period_type,
                    period_start=obs.period_start,
                    value=obs.value,
                    unit_kind=obs.unit_kind,
                    unit=obs.unit,
                    currency=obs.currency,
                    base_period=obs.base_period,
                    provider_status=obs.provider_status,
                    published_at=obs.published_at,
                    retrieved_at=now,
                    ingestion_run_id=run_id,
                    source_url=obs.source_url,
                    transformation=obs.transformation,
                    license=obs.license,
                    quality_flags=list(obs.quality_flags),
                )
            )
            counts["inserted"] += 1
            continue
        old_value = Decimal(str(row.value))
        if old_value == obs.value and row.provider_status == obs.provider_status:
            row.retrieved_at = now
            row.ingestion_run_id = run_id
            if obs.published_at is not None:
                row.published_at = obs.published_at
            counts["unchanged"] += 1
            continue
        flags = [f for f in obs.quality_flags]
        if old_value != obs.value:
            flags.append("revised")
            if (
                obs.unit_kind in LEVEL_KINDS
                and _relative_change(old_value, obs.value) > BREAK_RATIO
            ):
                flags.append("break_suspected")
        row.value = obs.value
        row.provider_status = obs.provider_status
        row.published_at = obs.published_at
        row.retrieved_at = now
        row.ingestion_run_id = run_id
        row.source_url = obs.source_url
        row.quality_flags = sorted(set(flags))
        counts["updated"] += 1
    return counts


def run_dataset(
    session_factory: Callable[[], Session],
    fetcher: Fetcher,
    spec: Dataset,
    *,
    now: datetime,
    dry_run: bool = False,
) -> RunResult:
    result = RunResult(provider=spec.provider, dataset=spec.dataset, status="running")
    run_id = uuid.uuid4()
    started = time.monotonic()
    before = fetcher.requests
    if not dry_run:
        with session_factory() as session:
            session.add(
                RegionalIngestionRun(
                    id=run_id,
                    provider=spec.provider,
                    dataset=spec.dataset,
                    started_at=now,
                    status="running",
                )
            )
            session.commit()
    try:
        observations, rejected = fetch_observations(fetcher, spec, now.date())
        result.observations = len(observations)
        result.rejected = rejected
        if not dry_run:
            with session_factory() as session:
                counts = upsert(session, observations, run_id, now)
                session.commit()
            result.inserted = counts["inserted"]
            result.updated = counts["updated"]
            result.unchanged = counts["unchanged"]
        result.status = "partial" if rejected else "succeeded"
    except (ProviderError, ValueError, KeyError, TypeError) as exc:
        result.status = "failed"
        result.error_class = type(exc).__name__
    result.requests = fetcher.requests - before
    if not dry_run:
        with session_factory() as session:
            run = session.get(RegionalIngestionRun, run_id)
            run.finished_at = datetime.now(timezone.utc)
            for name in (
                "status",
                "requests",
                "observations",
                "inserted",
                "updated",
                "unchanged",
                "rejected",
                "error_class",
            ):
                setattr(run, name, getattr(result, name))
            session.commit()
    (logger.warning if result.status == "failed" else logger.info)(
        "regional ingestion",
        extra={
            "event": "regional_ingestion",
            "provider": spec.provider,
            "dataset": spec.dataset,
            "status": result.status,
            "requests": result.requests,
            "observations": result.observations,
            "inserted": result.inserted,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "rejected": result.rejected,
            "error_class": result.error_class,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result


def selected(provider: str) -> Iterable[Dataset]:
    return [d for d in catalog.DATASETS if provider in ("all", d.provider)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--provider",
        choices=["all", catalog.EUROSTAT, catalog.WORLD_BANK, catalog.OECD],
        default="all",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="fetch and check, write nothing"
    )
    args = parser.parse_args(argv)
    if os.environ.get("ENVIRONMENT", "").lower() in {"production", "prod"}:
        print("refused: regional ingestion is staging-only for now", file=sys.stderr)
        return 2
    url = os.environ.get("DATABASE_URL", "")
    if not url and not args.dry_run:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    session_factory = None
    if not args.dry_run:
        engine = create_engine(
            url.replace("postgresql+asyncpg://", "postgresql://", 1),
            pool_pre_ping=True,
        )
        session_factory = lambda: Session(engine, expire_on_commit=False)  # noqa: E731
    fetcher = Fetcher()
    now = datetime.now(timezone.utc)
    results = [
        run_dataset(session_factory, fetcher, spec, now=now, dry_run=args.dry_run)
        for spec in selected(args.provider)
    ]
    for r in results:
        print(
            f"{r.provider:9s} {r.dataset:44s} {r.status:9s} req={r.requests} "
            f"obs={r.observations} new={r.inserted} upd={r.updated} "
            f"same={r.unchanged} rejected={r.rejected}"
            + (f" error={r.error_class}" if r.error_class else "")
        )
    return 0 if all(r.status != "failed" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
