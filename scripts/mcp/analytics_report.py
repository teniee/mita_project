#!/usr/bin/env python3
"""Answer the core product questions from the analytics views — no dashboard needed.

    python scripts/mcp/analytics_report.py --database-url "$ANALYTICS_READER_URL"

Reads ONLY the ``analytics`` schema; run it with the ``mita_analytics_reader``
role (scripts/mcp/analytics_reader_role.sql). Prints counts, rates and
latencies — never a user key, e-mail, amount or feedback text (feedback is
summarised by type and area). Definitions: docs/chatgpt-app/product-analytics.md.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Dict, List, Optional

Fetch = Callable[[str], List[Dict]]

TODAY = "(now() AT TIME ZONE 'UTC')::date"


def _one(fetch: Fetch, sql: str) -> Dict:
    rows = fetch(sql)
    return rows[0] if rows else {}


def _ratio(part, whole) -> Optional[float]:
    return round(100.0 * float(part) / float(whole), 1) if whole else None


def build_report(fetch: Fetch) -> Dict:
    activity = _one(
        fetch, f"SELECT * FROM analytics.activity_daily WHERE day = {TODAY}"
    )
    week = _one(
        fetch,
        f"SELECT coalesce(sum(tool_calls), 0) AS calls, count(DISTINCT user_key) AS users "
        f"FROM analytics.user_daily WHERE day > {TODAY} - 7",
    )
    month = _one(
        fetch,
        f"SELECT coalesce(sum(tool_calls), 0) AS calls, count(DISTINCT user_key) AS users, "
        f"count(DISTINCT (user_key, day)) AS active_user_days "
        f"FROM analytics.user_daily WHERE day > {TODAY} - 30",
    )
    adoption = fetch(
        "SELECT feature, users_used, adoption_percent, calls, calls_per_user, "
        "repeat_percent, d30_repeat_percent FROM analytics.feature_adoption ORDER BY calls DESC, feature"
    )
    failing = fetch(
        f"SELECT tool_name, sum(failures) AS failures, sum(calls) AS calls "
        f"FROM analytics.reliability_daily WHERE day > {TODAY} - 30 AND tool_name IS NOT NULL "
        f"GROUP BY tool_name HAVING sum(failures) > 0 ORDER BY 2 DESC, 1 LIMIT 5"
    )
    latency = _one(
        fetch,
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95, "
        "count(*) AS calls, count(*) FILTER (WHERE status = 'ok') AS successes "
        "FROM analytics.tool_calls WHERE occurred_at >= now() - interval '30 days'",
    )
    funnel = _one(
        fetch,
        "SELECT count(*) AS users, count(oauth_connected) AS connected, "
        "count(setup_started) AS setup_started, count(profile_saved) AS profile_saved, "
        "count(budget_previewed) AS budget_previewed, count(budget_saved) AS budget_saved, "
        "count(first_transaction) AS first_transaction, count(setup_completed) AS setup_completed "
        "FROM analytics.user_firsts",
    )
    retention = _one(
        fetch,
        "SELECT count(*) FILTER (WHERE d1_eligible) AS d1_n, count(*) FILTER (WHERE d1_eligible AND d1) AS d1, "
        "count(*) FILTER (WHERE d7_eligible) AS d7_n, count(*) FILTER (WHERE d7_eligible AND d7) AS d7, "
        "count(*) FILTER (WHERE d30_eligible) AS d30_n, count(*) FILTER (WHERE d30_eligible AND d30) AS d30 "
        "FROM analytics.retention_days",
    )
    history_users = _one(
        fetch,
        "SELECT count(DISTINCT user_key) AS users FROM analytics.tool_calls "
        "WHERE tool_name IN ('get_spending_history', 'get_financial_climate') "
        "AND status = 'ok' AND occurred_at >= now() - interval '30 days'",
    )
    feedback = fetch(
        "SELECT feature_area, type, count(*) AS n, round(avg(rating), 2) AS avg_rating, "
        "count(*) FILTER (WHERE status = 'new') AS open "
        "FROM analytics.feedback GROUP BY feature_area, type ORDER BY n DESC, 1, 2"
    )
    registrations = _one(
        fetch,
        f"SELECT coalesce(sum(registrations), 0) AS total, "
        f"coalesce(sum(registrations) FILTER (WHERE day = {TODAY}), 0) AS today "
        f"FROM analytics.registrations_daily",
    )
    segments = fetch(
        "SELECT segment, count(*) AS users FROM analytics.user_segments GROUP BY 1 ORDER BY 2 DESC, 1"
    )
    dau = activity.get("dau") or 0
    used = [a for a in adoption if a["calls"]]
    return {
        "registered_users": registrations.get("total", 0),
        "new_users_today": registrations.get("today", 0),
        "dau": dau,
        "wau": activity.get("wau") or 0,
        "mau": activity.get("mau") or 0,
        "wfau": activity.get("wfau") or 0,
        "dau_mau_percent": _ratio(dau, activity.get("mau")),
        "calls_per_active_user_today": (
            round(float(activity.get("calls") or 0) / dau, 2) if dau else None
        ),
        "calls_per_user_week": (
            round(float(week["calls"]) / week["users"], 2)
            if week.get("users")
            else None
        ),
        "calls_per_user_month": (
            round(float(month["calls"]) / month["users"], 2)
            if month.get("users")
            else None
        ),
        "active_days_per_user_month": (
            round(float(month["active_user_days"]) / month["users"], 2)
            if month.get("users")
            else None
        ),
        "most_used_feature": used[0]["feature"] if used else None,
        "least_used_features": [a["feature"] for a in adoption if not a["calls"]]
        or ([used[-1]["feature"]] if used else []),
        "feature_adoption": adoption,
        "most_failing_tools": failing,
        "success_rate_percent": _ratio(
            latency.get("successes", 0), latency.get("calls")
        ),
        "p50_latency_ms": latency.get("p50"),
        "p95_latency_ms": latency.get("p95"),
        "funnel": funnel,
        "onboarding_completed_percent": _ratio(
            funnel.get("setup_completed", 0), funnel.get("users")
        ),
        "first_budget_saved_percent": _ratio(
            funnel.get("budget_saved", 0), funnel.get("users")
        ),
        "first_transaction_percent": _ratio(
            funnel.get("first_transaction", 0), funnel.get("users")
        ),
        "d1_retention_percent": _ratio(retention.get("d1", 0), retention.get("d1_n")),
        "d7_retention_percent": _ratio(retention.get("d7", 0), retention.get("d7_n")),
        "d30_retention_percent": _ratio(
            retention.get("d30", 0), retention.get("d30_n")
        ),
        "history_users_month": history_users.get("users", 0),
        "feedback": feedback,
        "segments": segments,
    }


def render(report: Dict) -> str:
    lines = []
    simple = [k for k, v in report.items() if not isinstance(v, (list, dict))]
    width = max(len(k) for k in simple)
    for key in simple:
        value = report[key]
        lines.append(f"{key.ljust(width)}  {'n/a' if value is None else value}")
    lines.append("")
    lines.append(
        "feature adoption (30 days): feature  users  adoption%  calls  calls/user  repeat%  d30-repeat%"
    )
    for row in report["feature_adoption"]:
        lines.append(
            "  {feature}  {users_used}  {adoption_percent}  {calls}  {calls_per_user}  "
            "{repeat_percent}  {d30_repeat_percent}".format(**row)
        )
    lines.append(
        "most failing tools (30 days): "
        + (
            ", ".join(
                f"{r['tool_name']} {r['failures']}/{r['calls']}"
                for r in report["most_failing_tools"]
            )
            or "none"
        )
    )
    lines.append(
        "funnel: " + ", ".join(f"{k} {v}" for k, v in report["funnel"].items())
    )
    lines.append(
        "segments: "
        + (
            ", ".join(f"{r['segment']} {r['users']}" for r in report["segments"])
            or "none"
        )
    )
    lines.append(
        "feedback (area/type n avg-rating open): "
        + (
            "; ".join(
                f"{r['feature_area']}/{r['type']} {r['n']} {r['avg_rating']} {r['open']}"
                for r in report["feedback"]
            )
            or "none"
        )
    )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args(argv)
    import psycopg2
    import psycopg2.extras

    with psycopg2.connect(
        args.database_url.replace("postgresql+asyncpg://", "postgresql://")
    ) as conn:
        conn.set_session(readonly=True)

        def fetch(sql: str) -> List[Dict]:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                return [dict(row) for row in cur.fetchall()]

        print(render(build_report(fetch)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
