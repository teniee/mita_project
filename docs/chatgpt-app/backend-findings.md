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
overspend.

Real ChatGPT (2026-10-18) showed the consequence as names: "Transport gas /
Fuel / Gas", "Insurance medical / Medical insurance". Reproduced locally
through the MCP tools with the owner's inputs: after €55 recorded as `gas`, budget status had
`transport gas` (112.50 planned, 0 spent) and `gas` (55 moved in by the
redistribution, 55 spent), and the forecast listed `gas` as at risk.

**MCP presentation since 2.1.0 (no data change):** every result carries
`category_label` (`app/mcp/categories.py`), and budget status / forecast show an
expense category on the line of the plan bucket it spends from, only for pairs
declared in `app/config/category_aliases.py` (`gas`→`transport gas`,
`dining`→`dining out`, `public_transport`→`transport public`,
`entertainment`→`entertainment events`, `healthcare`→`out of pocket medical`).
Figures stay sums of stored rows, so the redistribution's effect is still
visible (a note says when it moved money). **Still open, backend:** the ledger
does not accrue `gas` spending to `transport gas`, so the rebalancer covers it
from other categories and the app shows both rows; fixing that changes the
mobile app and the rebalancer and needs its own change and review.

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
branch and on `main`. Confirmed environmental: a full run on a clean `main`
worktree also ended with exit 139, and GitHub CI (Linux, Python 3.12) ran the
same suite green on 85cdc55.

## F-6 (security) API audit fallback logs contain bearer tokens

A redacted gitleaks scan of the local, git-ignored `logs/audit/audit_fallback_*.jsonl`
written by the API found 965 secret-shaped values: 49 complete JWTs and
fields named `token` (255) and `token_jti` (127). The API's audit fallback
therefore persists bearer tokens to disk (in production: the container's
filesystem). Not touched in this branch. The MCP service closes these file
handlers at startup (`configure_logging`) and its own logs are proven
token-free (`tests_mcp/test_oauth_adversarial.py::test_oauth_flow_logs_no_secrets`,
container log scan in `mcp-ci`). Recommend: stop logging token material in
`app/core/audit_logging.py` and delete existing fallback logs.

## F-7 (OAuth) A registered client keeps the scopes it registered with

The SDK's `/authorize` handler checks the requested scopes against the
client's registration (`OAuthClientInformationFull.validate_scope`: "Client
was not registered with scope …"). The v1 staging app was registered with the
two read scopes, so after v2 added `finance:write`, `feedback:write` and
`profile:write`, ChatGPT got `invalid_scope` until the owner recreated the app
(2026-10-18). Production starts at v2 (all five scopes at registration), so
this does not affect launch; it will affect every existing connection the next
time a scope is added. Options: treat the registered scope as advisory in
`MitaAuthorizationProvider.get_client` (requests are already limited to
`SUPPORTED_SCOPES` and shown on the consent page; DCR is open, so the
registered list adds no protection), or document "reconnect" in the release
notes of such a version. Not changed before the merge.

## F-8 (P1, money model) Paying a saved bill on its date drains the dates ahead

Found while building the financial calendar (2026-10-24), reproduced locally
through MITA's own tools (`scripts/mcp/calendar_widget_review.py`, account
deleted afterwards): income 3,200, savings target 400, regular payments rent
850 (1st), kindergarten 180 (5th), utilities 95 (18th), internet 30 (27th), the
reviewed October budget saved, a realistic month of expenses recorded.

* The layout puts bills where `CATEGORY_BEHAVIOR` says, not on their due date:
  utilities on the 5th; obligation categories it does not know (`childcare`,
  `subscriptions`, `insurance`…) spread over weekdays (kindergarten 8.18 a
  weekday).
* Recording the kindergarten fee (180) on the 5th, or utilities (95) on the
  18th, makes that date's line "overspent", and
  `realtime_rebalancer.rebalance_after_overspend` covers it by taking money
  from later dates (up to 50 % per line per pass). The bill's own allocation on
  the other dates is never released.
* Money left unspent on a past date stays on that date.

Result on 24 October: MITA's plan for 25–31 October held **€12.16** (the base
layout held **€299.95**), while the forecast's safe daily amount was **€121.99
a day** (left to spend €853.91 over 7 days) — both are MITA figures, for the same
account and the same day. Line totals move too (utilities planned 190 = 95 + a
95 credit; childcare 231.04).

The calendar shows both figures, labelled (`planned_after_today`, the daily
average, a note when the gap is material) and does not hide either. Fixing it is
a model decision for the deferred forecast/plan task: lay bills out on their
due dates from the saved payments, release a bill's allocation when it is paid,
and decide what an underspent past date means (roll forward or stay).

**Root cause and proposal (2026-10-25; owner decided the same day: R3 —
unpaid bills held out of the safe daily amount — implemented; no change to the
rebalancer, "show exactly what the app implements"):**
`f8-money-model-proposal.md`. Of €948.05 MITA treated as overspending in that
month, €206.49 was real; the rest was timing (bills paid on their due dates),
naming (F-2) and pacing (a weekday-spread line spent in a few shops), because
the rebalancer works per date and category and never uses the same line's other
dates. Today's behaviour is pinned with hand-checkable figures in
`tests_mcp/test_money_consistency.py`.

## F-9 (P2, consistency) Two mobile figures disagreed with ChatGPT's — fixed 2026-10-26

Found while writing `tests_mcp/test_money_consistency.py` (2026-10-25); pinned
there, not changed.

* **The app's day budget counts today's savings slice.** `GET
  /api/budget/live_status` (the figure the app shows for today) sums every plan
  row of the user's local day, set-aside lines included (the Savings line,
  goal reservations). ChatGPT's `get_budget_status.today` and the safe daily
  amount leave them out since the owner's 2026-10-23 decision. With €10 of
  Savings planned today, ChatGPT says €10 of groceries, the app €20
  (`test_the_app_s_day_budget_still_counts_today_s_savings_slice`). Its
  `on_track` also compares spending with `monthly_income × day / 30`, not with
  the plan.
* **`GET /api/budget/forecast` reads the server's UTC date** for "today" and
  for the default month (`compute_forecast(today=None)`), so for a user in
  Sofia the days left differ by one from 21:00–22:00 UTC to midnight, and the
  first hours of a month are read as the previous one. The app does not call
  this endpoint today (it calls `live_status`, which already uses the local
  day); `/budget/spent`, `/remaining` and `/daily` default their month from UTC
  too when the app sends none.

Fix with F-8's implementation: one local-day helper for the budget routes, and
the set-aside rule in `live_status` (owner decision: the app's day figure
should leave savings out, as ChatGPT's does).

**Fixed 2026-10-26** (with R3, `docs/chatgpt-app/r3-bills-reserve.md`):
`/api/budget/forecast` takes "today" and the default month from the user's
calendar day (`local_day_of`) and holds the month's unpaid bills like
ChatGPT; `live_status.daily_budget` leaves money set aside out. Route tests:
`app/tests/test_budget_forecast_local_day.py`. Neither figure is on screen in
the app today (it reads `monthly_budget`, `monthly_spent` and
`transaction_count` from `live_status`, and never calls the forecast); the app
is not released. `/budget/spent`, `/remaining` and `/daily` still default
their month from UTC when the app sends none (the app sends one).

## F-10 (consistency) The app's "Total Budget" was income — fixed 2026-10-27

The app's "Live Budget Status" card (`daily_budget_screen.dart`,
`BudgetProvider.totalBudget`) shows `GET /api/budget/live_status`
`monthly_budget`, which is the user's **monthly income**, as "Total Budget",
and "remaining" as income minus spent. ChatGPT reports the month's **plan**
(`get_budget_status.total_planned`; income minus unallocated money) and plan
minus spent. For the owner's real account: app €2,500, ChatGPT €2,325.
`live_status.on_track` compares spending with `income × day / 30`, a
placeholder baseline. Not visible to anyone today (the app is unreleased).

**Fixed 2026-10-27 (label):** the Live Budget Status card now says "Monthly
income" and "… % of monthly income spent" (`daily_budget_screen.dart`;
`test/screens/daily_budget_screen_test.dart`). The figure is unchanged — it is
income, and the main screen's "Current Balance / Remaining" is deliberately
income − spent (its code comment says so). The month's plan is the calendar
screen's "Total Budget" (the sum of the saved days) and ChatGPT's
`total_planned`; nothing in the app now calls income a budget. Still open, not
displayed anywhere: the field is named `monthly_budget`, and `on_track` uses
income × day / 30.

## F-11 (product blocker) A user cannot set their own category amounts — found in real ChatGPT, 2026-10-28

**What happened (staging 2.3.0, owner's real-ChatGPT onboarding).** The owner
stated monthly amounts — fuel 200, cigarettes 200, coffee/walks/leisure 100,
housing 50 (a limit), groceries 50, plus two fixed loan payments — and asked
MITA to keep exactly them. Staging logs (tool names and outcomes only):
`update_financial_profile`, two `add_recurring_expense` (the loans), two
`preview_monthly_budget`; **no `save_monthly_budget`, no error, no backend
rejection**. The previews were MITA's generated draft. ChatGPT then said the
amounts "will be preserved", recalculated a budget itself in the
conversation (the tool description and the setup skill both say "never
recompute or edit the numbers yourself"), and finally — correctly — that this
budget could not be saved in MITA.

**Why: the product has no way to persist user-authored flexible category
amounts.** Traced on `feat/chatgpt-auth-ui` and `main`:

| Path | What it does |
|---|---|
| Mobile onboarding (`onboarding_expenses_screen.dart` → `POST /onboarding/submit`) | exact amounts only for **fixed** expenses (rent/mortgage, utilities, internet & phone, insurance, car payment, subscriptions, loan payments, childcare) plus spending frequencies; every flexible line is generated by `generate_budget_from_answers` from income-tier weights; `build_monthly_budget` then writes generated lines over a same-named user line. Once only (`has_onboarded`) |
| `OnboardingBudgetScreen` (per-category sliders) | **no route** in `main.dart` — unreachable; its values would have gone in as "fixed" expenses anyway |
| Mobile after onboarding (`budget_settings_screen.dart`) | budget mode and automation toggles only; no screen edits a category amount |
| `PATCH /calendar/day/{y}/{m}/{d}` | edits an in-memory copy and returns it — **nothing is saved**; the app does not call it |
| `POST /budget/monthly`, `/calendar/redistribute`, `/calendar/shell`, `/budget/behavioral_allocation` | compute and return; save nothing |
| `update_day_entry`, `UserDataService.save_user_calendar`, `budget_planner.generate_and_save_calendar`, `onboarding_engine_final` | write plan rows, but **nothing calls them** |
| ChatGPT `preview_monthly_budget` / `save_monthly_budget` | input is a month / the reviewed draft token only; the draft is `allocations_from_profile` (onboarding's engine) over stated income, savings target and saved regular payments |

What IS supported exactly: fixed obligations. In ChatGPT the two loans were
saved as regular payments and appear in the draft at their exact amounts
(`allocations_from_profile`'s `fixed`), and R3 holds them as bills until
recorded. Forcing a flexible amount in as "fixed" does not preserve it either:
the generator adds its own line of the same name (engine check, income 1,000:
user transport gas 200 → 245.00, groceries 50 → 128.00). MITA also has no
tobacco category (23 expense categories; none in the plan buckets).

Also found (pre-existing, not changed): the app's "auto redistribution"
switch sends `auto_redistribution`, the backend stores only
`redistribution_enabled`, and nothing in the rebalancer reads either.

**Status (2026-10-28): implemented for the ChatGPT plugin on
`feat/chatgpt-auth-ui`, uncommitted and undeployed, pending owner review.**
Owner decision: an amount the user sets overrides MITA's recommendation and
MITA allocates only the rest; plugin scope only (no mobile, no new taxonomy).
The user's lines are free-form (`"my:<label>"` plan lines; ChatGPT maps the
words, MITA does the money); one MCP table (`mcp_budget_lines`, migration
`0040`) remembers which of MITA's lines each one replaces. Design:
`user-budget-lines.md`. An earlier, wider implementation (mobile screen, REST
endpoints, a global Tobacco category, a `daily_plan` provenance column) was
withdrawn before commit.
