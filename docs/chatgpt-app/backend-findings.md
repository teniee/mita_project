# Pre-existing backend findings surfaced during the MCP work

Confirmed by running the real API locally on `feat/chatgpt-plugin` (API code
identical to `main` for these paths). Not fixed in this branch — the ChatGPT
work does not change the API's behavior — but each affects data the app and
ChatGPT show.

## F-1 (P1) A second active savings goal fails with HTTP 500 and is still saved

Repro: as a Premium user, `POST /api/goals/` twice with any target date in the
future. The second call returns 500:

```
UniqueViolationError: duplicate key value violates unique constraint
"uq_daily_plan_user_date_category"
  app/api/goals/routes.py:229 create_goal
  app/services/core/engine/goal_budget_sync.py:213 sync_goal_to_daily_plan
```

`sync_goal_to_daily_plan` writes one `goal_savings` row **per goal** per day,
while migration 0035's unique key is `(user_id, date, category)`. Observed
side effect: the goal row itself was committed (it appears in `GET /goals`)
although the client got a 500, and its daily reservations were not written.
Fix needs a design decision (one aggregated `goal_savings` row per day, or a
per-goal category), not a constraint drop.

## F-2 (P2) Plan categories and transaction categories use different names

Onboarding plans are stored under `CATEGORY_BEHAVIOR` names (`dining out`,
`transport public`, `transport gas`, `entertainment events`, `clothing`,
`insurance medical`…), while recorded transactions use
`VALID_TRANSACTION_CATEGORIES` (`dining`, `transportation`, `entertainment`,
`shopping`…). `category_mapper.CATEGORY_NAME_MAPPING` exists but no production
code path applies it to the ledger. Result, reproduced through
`GET /api/budget/spent`: a $72 dinner is "unplanned" `dining` spending while the
`dining out` allocation shows $0 spent. The rebalancer then treats it as
overspend. The MCP service reports exactly what is stored (it must not invent a
mapping), so ChatGPT will see the same split the app shows.

## F-3 (P2) Route-level issues in budget/AI endpoints

Listed in `data-trust-audit.md` → "Fix backlog": `/budget/forecast` uses UTC
and server date; `/budget/daily` reports `remaining 0.0` when nothing is spent;
`/budget/live_status` measures against income/30; `POST /ai/advice` includes
soft-deleted transactions; `/insights/` fabricates a fallback dated 2025-01-29;
`/insights/income_based_tips` defaults income to 3000.

## F-4 (security) API dependency advisories

`pip-audit` on 2026-10-02: `PyJWT 2.10.1` (multiple advisories incl. an
algorithm allow-list bypass), `cryptography 44.0.1`, `python-dotenv 1.0.1` in
`requirements.txt`. The MCP service pins fixed versions
(`requirements-mcp.txt`); the API should be upgraded with a full regression run.

## F-5 (test infra) Intermittent native crash in the local full suite

On macOS / Python 3.11.9, two full local runs of `app/tests` ended in
`Fatal Python error: Segmentation fault` inside sentry_sdk's SQL-tracing
thread, at different tests (`test_migration_0036_user_fks.py`,
`test_concurrent_auth_operations.py`); both files pass in isolation on the
branch and on `main`. Treated as environmental until CI (Linux, Python 3.12)
shows otherwise.
