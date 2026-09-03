# Mita Finance — Project Guide for Claude

## What is this project
Landing page + waitlist for **Mita Finance** — a daily budget redistribution app (iOS + Android, coming soon).
The site is a **single-file** `index.html` — no framework, no build step, pure HTML/CSS/JS.

## Live site
https://mitafinance.com

## Key file
`F:/adata/MITA FINANCE/index.html` — the only file you edit for the website.

## Backend API
`https://mita-production-production.up.railway.app`
- `POST /api/waitlist/join` — join waitlist, returns `{ effective_position, total_signups, referral_link, ref_code }`

## Brand guidelines
All brand files are in `F:/adata/MITA FINANCE/brand/` (26 PNG files).

### Brand colors (EXACT — do not deviate)
| Variable     | Hex       | Role                        |
|--------------|-----------|-----------------------------|
| `--navy`     | `#193C57` | Primary text & anchor color |
| `--yellow`   | `#FFD25F` | PRIMARY accent (CTA, energy)|
| `--teal`     | `#14B8A6` | Success, savings, positive  |
| `--purple`   | `#6B73FF` | Secondary accent            |
| `--red`      | `#F44336` | Alerts, logo quadrant       |
| `--teal-l`   | `#CCFBF1` | Light teal backgrounds      |
| `--bg`       | `#FFF8F0` | Page background (warm cream)|

### Approved gradients
- Navy → Yellow: `#193C57 → #FFD25F`
- Red → Teal: `#F44336 → #14B8A6`
- Purple → Yellow: `#6B73FF → #FFD25F`

### Typography
- `'Manrope'` — PRIMARY font (UI headlines, financial figures, dashboards)
- `'Sora'` — SECONDARY font (marketing body text, section content)
- `'Space Mono'` — financial data, numbers, position counters

### Logo mark
4-quadrant grid (2×2), each quadrant a solid rounded square:
- Top-left: Red `#F44336` (M)
- Top-right: Purple `#6B73FF` (I)
- Bottom-left: Teal `#14B8A6` (T)
- Bottom-right: Yellow `#FFD25F` (A)

### Background
The site is **LIGHT** — warm cream `#FFF8F0`. NOT dark. Glass cards use white `rgba(255,255,255,0.72)` with navy borders.

### Brand personality
Confident but not loud. Structured. Calm. Forward-thinking. Never financial jargon or fear language.

## Preserved JS IDs (never rename or remove)
These IDs are wired to the waitlist API and phone engine:
- Forms: `heroFormWrap`, `heroForm`, `heroBtn`, `heroSuccess`, `ctaFormWrap`, `ctaForm`, `ctaBtn`, `ctaSuccess`
- Success data: `hPos`, `hTotal`, `hLink`, `cPos`, `cTotal`, `cLink`
- Counters: `totalCount`
- Phone mockup: `phBc`, `phCal`, `phPanel`
- UI: `nav`, `confetti`, `cur`, `curRing`, `heroSocial`

## Preserved JS globals
- `window.mitaDay(d)` — show day detail in phone
- `window.mitaBack()` — return to calendar in phone

## Key features to never break
1. **Waitlist API** — hero form + CTA form both POST to the backend
2. **Referral system** — `?ref=CODE` URL param, referral link after signup
3. **Confetti** — triggers on successful signup (`boom()`)
4. **Interactive phone** — MITA Interactive Phone Engine IIFE at bottom of `<script>`; the calendar shows March 2026, days are clickable, shows budget redistribution detail
5. **Custom cursor** — `.cur` + `.cur-ring`
6. **Scroll reveal** — `.reveal` + IntersectionObserver

## Figma integration
- Figma capture script is already in the HTML: `<script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script>`
- To push to Figma: start `npx http-server . -p 8765 --cors -s`, then use `mcp__plugin_figma_figma__generate_figma_design`
- Latest Figma file: https://www.figma.com/design/hGPeeY99LUn1Q2MSpmHBQu

## Local dev server
```bash
cd "F:/adata/MITA FINANCE"
npx http-server . -p 8765 --cors -s
```
Then open http://localhost:8765

## Design decisions made
- Hero accent gradient: Red → Teal (brand-approved)
- CTA button: Navy background + Yellow text (Navy→Purple gradient)
- Step numbers use `Space Mono` font
- Stat numbers use `Space Mono` font
- Feature icon backgrounds: solid brand color tints (not gradients)
- Phone mockup exterior stays dark (phone frames are conventionally dark)
- Dot grid on body uses navy dots `rgba(25,60,87,0.06)` instead of white dots

## Backend deployment (Railway) — verified 2026-08-23

The FastAPI backend in `app/` deploys to Railway, project **Mita Finance**
(`d44d0580-3476-4e46-bc4c-b2d95dac64cd`), environment **production**
(`d4970d5d-3c58-4be7-b64e-5c05d359de3b`), service **mita-production**
(`b6cebfcc-201f-4e00-8b12-a8119cbef5a9`).

- Source: GitHub `teniee/mita_project`, branch `main`. Auto-deploy enabled,
  no watch patterns, no root directory, no check-suite gating.
- Start command: `bash start.sh`, which runs `alembic upgrade head` before
  launching uvicorn and **aborts startup in production if the migration
  fails** — every deploy is also a migration.
- Public URL: `https://mita-production-production.up.railway.app`
  (`GET /health` is the liveness endpoint).

Release invariant: push to `main` -> Railway builds exactly that commit ->
deployment becomes active. Verify the deployed SHA against GitHub `main`
after every release.

## Monthly plan rollover — invariant (added 2026-09-03)

`daily_plan` rows are materialized **lazily, on read**, by
`app/services/monthly_plan_service.py::ensure_month_plan(db, user_id, year, month)`.

Onboarding only ever wrote its own month. Nothing created the next one, so on
the 1st of every month an account went blank at once: `/calendar/saved` returned
an empty list, the dashboard fell through to its `monthly_income / 30`
placeholder ("$0 of $0"), and affordability answered "no budget set".

**Correctness must not depend on a scheduler.** Nothing periodic runs in
production — `start.sh` launches uvicorn only, and `scripts/rq_scheduler.py` has
no worker starting it. A cron job may be added later to warm months ahead of the
first read, but only as an optimization: `ensure_month_plan` is idempotent, so
running it never, twice, or concurrently with a user request gives the same
result.

Rules for anyone touching this:

- **One boundary.** Read paths call `ensure_month_plan_safe` /
  `ensure_month_plan_async` / `ensure_months_span_async`. Never re-implement
  "if the month is missing, generate it" in a router.
- **Not a second budget algorithm.** Totals come from the user's own last
  persisted month, or from `generate_budget_from_answers`; layout comes from
  `distribute_budget_over_days`; rows are written by `save_calendar_for_user`;
  spend is accrued by `rebuild_month_plan`. All pre-existing, all canonical.
- **Never guard on "does the month have rows".** `rebuild_month_plan` creates
  `planned_amount = 0` rows tagged `_mita_transaction_generated_v1` for spend
  with no plan behind it, and the rebalancer can credit one to a non-zero
  amount. `GoalBudgetSyncService` writes `goal_savings` rows too. Guard on a
  real allocation — that is what `month_has_plan` does.
- **Roll forward the BASE plan.** `_mita_realtime_adjustment_v1` records an
  in-month rebalance and is backed out before a month is carried forward;
  otherwise a one-off overspend would permanently reshape every later month.
- **Serialize with `lock_user_ledger`.** The same per-user
  `pg_advisory_xact_lock` every ledger mutation takes — a second lock would
  deadlock. The mobile app fires several budget reads in one `Future.wait` on
  cold start, so the race is the normal case.
- **Write midnight UTC, never a NULL category.** `uq_daily_plan_user_date_category`
  is on the raw timestamptz and PostgreSQL treats NULLs as distinct, so either
  mistake silently creates a duplicate parallel month.
- **Money conserves to the cent.** `split_amount_exactly` in
  `app/services/core/engine/calendar_engine.py` replaced per-day `round(x/n, 2)`,
  which drifted by up to ±0.10 per category. `_materialize_month` refuses to
  commit a month whose daily rows do not re-sum to their allocation.

Regressions: `app/tests/test_monthly_plan_rollover.py`.

## Calendar day budget — invariant (added 2026-09-03)

For a selected date D, the day-details summary card and its Category Breakdown
must both derive from the SAME persisted plan:

    day_budget    == SUM(daily_plan.planned_amount for D)
    day_remaining == day_budget - day_spent

The screen showed `Budget $79.00` with `$0 / $0` categories on 2026-08-04,
2026-08-05 and 2026-08-18 — three days whose real plans sum to $49.11, $409.11
and $49.11. The $79 came from `POST /calendar/shell`: a monthly total divided
by a hardcoded 30 days, so every day of the month carried the same figure.

Rules:

- **The card sums the categories.** `_headerLimit` in
  `calendar_day_details_screen.dart` is the sum of `_dayCategories`; it must
  never read an independent `limit` field.
- **Never invent categories.** `_generateDefaultCategoryBreakdown()` (four
  hardcoded names at 40/25/20/15 % of the day limit) was deleted. No
  allocation → `_buildNoPlanState`, not a fabricated split.
- **A preview is not a budget.** `/calendar/shell` days are tagged
  `is_preview: true` (`ApiService._transformCalendarData`); the saved calendar
  tags `is_preview: false` (`mergeSavedCalendarDay`). A preview day yields no
  day budget and is labelled as an estimate.
- **Render cents.** `toStringAsFixed(0)` displayed a real $0.30 allocation as
  "$0", which is what made a planned day look unplanned. Use `formatMoney`.
- **Shell weights are fractions.** `_as_fraction()` in
  `app/api/calendar/routes.py` accepts both 0.15 and 15; `num_days` is the real
  month length, never a hardcoded 30.

Regressions: `mobile_app/test/screens/calendar_day_details_consistency_test.dart`
and `TestDayBudgetEqualsCategorySum` in `app/tests/test_monthly_plan_rollover.py`.
