# MITA in ChatGPT — capacity plan (measured 2026-10-12, local)

Reproduce: `scripts/mcp/benchmark_capacity.py --generate` against a local
database named `*capacity*` (the script refuses anything else). Never load-test
staging or production.

## Dataset

Deterministic (hash-based) synthetic data, local PostgreSQL 15, laptop
(Apple silicon, shared with other work — absolute timings are conservative):

| Table | Rows | Table | Indexes |
|---|---|---|---|
| `transactions` (1,000 users × 600; 1% soft-deleted; May → 11 Oct) | 600,000 | 77.6 MB | 96.3 MB |
| `daily_plan` (1,000 users × 184 days × 8 categories) | 1,472,000 | 178.3 MB | 291.5 MB |
| `analytics.events` (1,000 users × 500; 600 linked) | 500,000 | 89.3 MB | 82.0 MB |
| `goals` (2/user), `scheduled_expenses` (3/user), `users` | 2,000 / 3,000 / 1,000 | < 1 MB each | |
| **Database** | | **827 MB** | |

Generation: transactions 16.6 s, plan 36.4 s, events 14.8 s.

## Tool query latency (query layer, READ ONLY transaction, 100 samples each)

Measured on the functions the tools call, for 50 users × 2 runs, user
context loaded separately (2 statements, not counted below).

| Operation (tool) | p50 ms | p95 ms | p99 ms | SQL statements |
|---|---|---|---|---|
| current-month summary (`get_financial_summary`) | 7.4 | 9.7 | 30.9 | 5 |
| list transactions, 30 days (`list_transactions`) | 2.3 | 3.1 | 3.7 | 3 |
| category breakdown, 30 days (`get_spending_breakdown`) | 0.8 | 1.3 | 1.4 | 1 |
| budget status (`get_budget_status`) | 7.8 | 8.8 | 26.7 | 4 |
| forecast (`get_budget_forecast`) | 7.5 | 8.3 | 32.5 | 3 |
| six-month history (`get_spending_history`) | 5.2 | 7.4 | 10.0 | 2 |
| category history, 6 months | 3.2 | 4.9 | 5.5 | 2 |
| financial climate (`get_financial_climate`) | 15.3 | 19.4 | 27.7 | 6 |
| recurring (`get_recurring_expenses`) | 1.0 | 1.3 | 2.1 | 2 |
| goals (`get_goals`) | 0.8 | 0.9 | 1.0 | 1 |
| setup status (`get_setup_status`) | 9.4 | 12.3 | 34.6 | 5 |
| budget preview (`preview_monthly_budget`) | 8.5 | 9.4 | 34.8 | 4 |

No N+1 pattern: every tool is 1–6 statements regardless of data size. The
p99 tail (25–35 ms) is cold cache on the first sample per user.

**Re-run 2026-10-18 (MCP 2.1.0, same dataset, `--runs 2`).** Budget status
gained one statement (5: the redistribution note reads `plan_json` on the
same `(user_id, date)` index; the summary skips it and stays at 5); the
forecast regroups lines in Python. p95: budget status 11.1 ms, forecast 10.0,
summary 11.7, climate 22.2, every other tool ≤ 14.2 ms — within run-to-run
noise of the table above on a shared laptop.

## EXPLAIN (ANALYZE, BUFFERS) — heaviest statement per operation

| Operation | Execution | Plan |
|---|---|---|
| summary / status / preview | 0.6–1.3 ms | Bitmap Index Scan `uq_daily_plan_user_date_category` |
| forecast | 1.2 ms | same |
| list / breakdown | 0.2–0.6 ms | Bitmap Index Scan `ix_transactions_user_id_spent_at` |
| six-month / category history | 1.7–1.8 ms | Bitmap Index Scan `ix_transactions_user_id` (the window covers most of a user's rows, so the planner prefers the single-column index) |
| climate | 4.2 ms | Bitmap Index Scan `ix_daily_plan_user_id` (plan totals per month) |
| setup status | 1.4 ms | Bitmap Index Scan `ix_transactions_user_id` |
| recurring / goals | < 0.1 ms | user_id indexes |

**Indexes: none added.** Every candidate from the plan already exists and is
used — `transactions (user_id, spent_at)`, `daily_plan (user_id, date,
category)` (unique), `goals (user_id)`, `scheduled_expenses (user_id)`, and
the three `analytics.events` indexes from 0039. `(user_id, category,
spent_at)` would save under 1 ms on category history; not worth the write
cost. No migration 0040.

## Analytics

| Query | Time on 500k events |
|---|---|
| full report (`analytics_report.py`, ~12 queries) | 3.5 s |
| `activity_daily` (90 days of DAU/WAU/MAU/WFAU) | 0.84 s |
| `feature_daily` / `reliability_daily` / `retention_weekly` | 0.17–0.27 s |
| `feature_adoption` | 0.12 s |
| `user_segments` / `retention_days` / `activation` | ~0.03 s |

Plain views are fine at this size and far beyond early-stage volume (500k
events ≈ 1,000 active users for ~5 months). Next steps when `analytics.events`
passes ~5M rows: (1) Metabase result caching (no code); (2) a materialized
`user_daily` refreshed by a scheduled job — MITA runs no scheduler today, so
that job must be added deliberately; (3) partition `analytics.events` by month.

## Writes

Write tools run the canonical ledger path (advisory lock + month rebuild):
`add_transaction` p50 was 30–45 ms in the test suite against a month with
~250 plan rows. Batches apply items sequentially under one lock, so a
25-item batch costs ~25 rebuilds of one month (≈ 0.5–1 s). Acceptable for
v1; if batches become common, rebuild once per affected month after all
inserts (a change to `expense_tracker`, not to MCP).

## Growth and sizing

Per active user (≈ 100 expenses/month, a daily plan of 8 categories, ~3 tool
calls/day): ≈ 0.29 MB transactions + 0.47 MB plan + 0.17 MB events per six
months, indexes included → **≈ 1.9 MB per user per year**, dominated by
`daily_plan` (6 indexes; index size exceeds table size). 10,000 active users
≈ 19 GB/year. Watch `analytics.storage`.

## Limits that matter before scale

* One MCP replica: rate limits are in-process (`app/mcp/ratelimit.py`).
* DB pool: 5 + 10 overflow per process; the analytics writer uses at most one.
* Statement timeouts: 5 s reads, 10 s writes.
