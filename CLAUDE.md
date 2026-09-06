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

## Never invent the user's standing (cohort, challenges, leaderboard)

`ApiService` methods used to swallow their own exception and return hardcoded
sample data. Because the API layer never rethrew, the honest empty/error states
already written upstream were **unreachable dead code**:

- `getCohortInsights()` returned `cohort_size 1247`, `your_rank 312`,
  `percentile 75` plus four invented peer "insights". Shown on Insights
  (`CohortInsightsWidget`) and during onboarding
  (`OnboardingPeerComparisonScreen`) — a brand-new user was told they ranked
  312nd of 1247 people. The onboarding screen's own honest `catch` could never
  fire, because the call never threw.
- `getAvailableChallenges()` returned "Meal Prep Master" / "No-Spend Weekend" /
  "Subscription Audit", each with a fabricated `participants`, `success_rate`
  and a cash `reward_amount` — joinable offers backed by no real money.
- `getLeaderboard()` returned "BudgetNinja" and friends, ranking the user
  against people who do not exist.
- `CohortInsightsWidget._getDefaultCohortData()` was a *second* fabrication
  layer that would have re-introduced the invented cohort even after
  `ApiService` was made honest. Fixing only the API layer moves the lie
  downstream — both had to change together.

Rules:

- **An API failure is not data.** A failed call reports unavailability
  (`error` + `null` fields, or an empty list). It never returns a plausible
  sample. `getPeerComparison()` is the reference shape.
- **Fix the layer that swallows.** An honest empty state upstream is dead code
  if the service beneath it never fails. When adding an empty state, verify the
  path that reaches it can actually happen.
- **A null cohort renders the empty state.** `asInt(null) == 0` drives
  `CohortInsightsWidget`'s existing "nothing to rank against" card; an empty
  list drives `challenges_screen`'s "No challenges available right now" and the
  leaderboard's "No leaderboard standings yet."

Regression: `mobile_app/test/no_fabricated_personal_data_test.dart` fails if any
of the fabricated literals return.

## Never invent a verdict: peer comparisons and financial ratings

A second sweep found the same fabrication pattern in four more places. All of
them share one shape: **a failure path that returns a plausible answer instead
of admitting it has none**, which also makes the honest empty state upstream
unreachable.

### Peer comparisons (`social_comparison_service.dart`)

`generateSocialInsights()` fell back to `_generateFallbackPeerData()` — a
hardcoded table of per-income-tier peer averages (2200 / 3200 / 4800 / 7500 /
12000) and cohort sizes (1500 / 2200 / 3100 / 1800 / 800) — whenever the peer
API reported an error. `ApiService.getPeerComparison()` returns an honest
`{'error': ...}` envelope on *any* failure, so that fallback fired on every
failure, and `_generateComparisonText()` then told the user "You spend 12% more
than similar users" against a peer group that was a constant in the file.
`_extractPeerData()` also defaulted a missing peer savings rate to `0.15` and a
missing cohort to `1000` people, so even a *successful* response missing those
fields produced confident comparisons.

This was not confined to a peer widget. The text travels:

    EnhancedMasterBudgetEngine._generatePersonalizedInsights
      -> personalizedInsights
      -> EnhancedProductionBudgetEngine.intelligentInsights
      -> BudgetAdapterService.getEnhancedBudgetSuggestions() suggestions[].message
      -> BudgetProvider.budgetSuggestions
      -> daily_budget_screen "AI Budget Suggestions" card

Rules:

- **Guard once, share it.** `hasSufficientPeerData()` now lives in
  `utils/peer_data.dart` so services and widgets apply the same test;
  `peer_comparison_widgets.dart` re-exports it for existing imports.
- **No peers, no claim.** An insufficient cohort or a failed call returns an
  empty insight list. The two master-engine consumers are already guarded
  (`if (socialInsights.isNotEmpty)` and `socialInsights.take(1)`), so an empty
  list produces no text — that is what closes the chain above.
- **Never default a peer statistic.** A field the server did not send is
  absent, and the insight that needs it is skipped.

### Financial rating (`ai_personal_finance_profiler.py`)

`generate_financial_rating()` returned `{"rating": "B", "risk": "moderate",
"summary": "User spending is generally steady..."}` when GPT was unavailable or
its answer did not parse. `save_ai_snapshot()` persists that straight into
`AIAnalysisSnapshot`, and the app renders it as an AI assessment of the user's
own finances. It now returns `None` for all three. The resilience requirement
is unchanged — it still must not raise, so the endpoint degrades rather than
500ing.

`main_screen._buildSnapshotPreview()` printed `Rating: B` for any snapshot
whose rating was null (`asString(..., fallback: 'B')`) — exactly what the
backend stored. It now requires a real rating and summary, matching
`insights_screen._buildAISnapshotCard()`, which already did.

### Weekly trend (`/ai/weekly-insights`)

The endpoint's `except` branch returned `"trend": "stable"` (plus two generic
recommendations) whenever `AIFinancialAnalyzer` threw. `insights_screen` read
it with `fallback: 'stable'` and drew `_buildTrendIndicator` — an arrow and a
"Stable" badge — so a failed analysis was presented as a finding about which
way the user's spending was moving. Both sides now use null, and the badge is
only drawn for a real trend.

This one also hid a broken test: `test_get_weekly_insights` patched
`app.services.ai_financial_analyzer.AIFinancialAnalyzer`, but
`app/api/ai/routes.py` binds that name at import, so the route kept using the
real analyzer, raised against the mock session, and fell into the degraded
branch. The test passed only because that branch hardcoded `"stable"`. Patch
where the name is looked up (`app.api.ai.routes.AIFinancialAnalyzer`).

### `budgetSuggestions` producer/consumer contract

`insights_screen` and `main_screen` read `confidence`, `intelligent_insights`
and `category_insights`. No producer emits any of them
(`BudgetAdapterService` emits `confidence_level`; `/budget/suggestions` emits
`suggestions` / `total_potential_savings` / `priority_areas`), so both blocks
were dead. **Do not "fix" this by mapping `confidence_level` onto
`confidence`** — the blocks derived a health score and letter grade from
budget-engine confidence (`(confidence * 100).round()`,
`_getGradeFromConfidence`). Engine confidence describes how sure the allocator
is about its own arithmetic, not the user's financial health. Both blocks were
deleted.

Item shape differs between producers too: the adapter emits `message`, the
backend emits `text`. `daily_budget_screen` read only `message` and fell back
to `suggestion.toString()`, rendering the raw Dart map into the card.

### A failed analysis is not a finding (AI + behaviour endpoints)

The same shape appeared across six endpoints. Each answered a caught exception
with a plausible payload:

| Endpoint | Invented |
|---|---|
| `/api/ai/financial-health-score` | `score 50`, `grade "C"`, every component `50` |
| `/api/ai/goal-analysis` | `on_track: True` |
| `/api/ai/spending-prediction` | `trend: "stable"` |
| `/api/ai/weekly-insights` | `trend: "stable"` |
| `/api/behavior/analysis` | `behavioral_score: 0.5` |
| `/api/behavior/patterns` | `dominant_pattern: "balanced"` |

`on_track: True` is the sharpest: a failed analysis telling the user their goal
is on track is a false reassurance about their own money. The health score is
the most reachable: `insights_screen` already renders "Add more transactions to
calculate your financial health score" when score/grade are null, and this
payload is precisely why that guard never fired.

Rules:

- **Degrade, don't invent.** These endpoints must keep answering 200 — a broken
  analyzer must not 500 the screen — but every *finding* field is null/empty
  and an `error` key says so. Zeroes that are genuinely zero
  (`confidence: 0.0`, `predicted_amount: 0.0`) stay.
- **Patch where the name is looked up.** `test_get_weekly_insights` and
  `test_get_financial_health_score` both patched
  `app.services.ai_financial_analyzer.AIFinancialAnalyzer` while
  `app/api/ai/routes.py` binds that name at import. The route kept the real
  analyzer, raised against the mock session, and fell into the degraded
  branch — so both tests were green without ever reaching the analyzer they
  claimed to exercise, asserting instead on the hardcoded `"stable"` and
  `50`/`"C"`. Patch `app.api.ai.routes.AIFinancialAnalyzer`.
- **No hardcoded timestamps.** `/api/ai/spending-patterns` reported
  `analysis_date: "2025-01-29T00:00:00Z"` — a fixed past date presented as when
  the analysis ran.

Regression: `app/tests/test_no_fabricated_verdicts.py`.

Regressions: `mobile_app/test/services/social_comparison_no_fabricated_peers_test.dart`,
`mobile_app/test/budget_suggestions_contract_test.dart`, and the updated
assertions in `app/tests/test_client_error_report_and_sync_session.py`.

## Making a producer honest can expose a dishonest consumer

Fixing `getCohortInsights()` to report `cohort_size: null` / `percentile: null`
instead of the invented 1247 / 75 did not finish the job — it moved the problem
downstream. `onboarding_peer_comparison_screen` read those with `?? 0`, so a
brand-new user was then told, mid-onboarding:

    Connect with 0 other Middle users
    You're in the 0th percentile of your peer group! This means you're
    already doing better than most users with similar income levels.

Two separate faults, one exposed and one pre-existing:

- `?? 0` printed the absence instead of suppressing the card. The peer-group
  card is now gated on `_cohortSize > 0`, the percentile line on a non-null
  percentile, and the Peer Insights / Recommendations cards on non-empty lists
  (a heading with no rows under it is not a card).
- The congratulation was **unconditional**: a user in the 10th percentile was
  told they were "already doing better than most users with similar income
  levels". It is now stated only when the percentile supports it.

`as List<String>?` on a JSON-decoded `List<dynamic>` returns null, so real peer
insights could silently vanish. The accessors read every element as a string.

In the service itself, two claims outran the data. The API sends a **mean, not
a distribution**, so nothing there can establish a ranking:
"You're ahead of most peers in your tier" became "well above the average for
your income tier", and "increase your savings rate by 2-3%" — a figure nothing
computed — now points at the average instead.
`SocialComparisonService._calculatePercentile()` is a ratio band, not a
distribution percentile; it exists only to pick a sentence.
`SocialComparisonInsight.percentile` is never rendered. **Keep it that way**
unless the API starts sending a real distribution.

Rule: after removing a fabricated value, grep for every consumer of that field.
A producer that starts telling the truth will surface every `?? 0`, `?? 50` and
`as List<String>?` that was relying on it to lie.

Regression: the `onboarding never states a cohort standing it does not have`
and `no peer claim outruns the data behind it` groups in
`mobile_app/test/no_fabricated_personal_data_test.dart`.

## The dashboard reports the persisted plan, including when it is zero

`GET /api/dashboard` had two surviving `monthly_income / 30` placeholders. The
rollover work removed the one that fired when a month had not been
materialized; these fired when a **day** had no allocation, which is a normal
state, not an error.

`distribute_budget_over_days()` gives `behavior == "spread"` categories to
`weekday_days` only, so a Saturday or Sunday legitimately carries no
`daily_plan` rows. On those days the dashboard answered:

- `daily_targets`: `monthly_income / 30` split across four hardcoded categories
  (Food & Dining 35 %, Transportation 25 %, Entertainment 20 %, Shopping 20 %)
  — the same invented breakdown deleted from the calendar day-details screen.
  For the test user that is a $173.33 daily budget nothing had planned, which
  the user could then overspend against.
- the week strip: `result.scalar() or (monthly_income / 30)`, where `or` also
  swallows a real `0.00`, so a day planned at zero was scored `good` / `warning`
  / `over` against a placeholder.

Rules:

- **No allocation is an answer.** An empty `today_plans` yields
  `daily_targets: []`; `main_screen._buildBudgetTargets()` already renders an
  empty state for it. `ensure_months_span_async()` runs first, so an empty day
  means the day is genuinely unallocated, not that the month is missing.
- **`or` is not a null check on money.** Use `is not None`; `0.00` is a real
  budget, and a day with none is `neutral` — it cannot be over or under.

This also explains a class of flaky test: three
`TestReadPathsMaterializeTheMonth` cases asserted that today carries a non-zero
budget, so they passed Monday–Friday and failed every Saturday and Sunday. They
now assert that each endpoint reports **this day's persisted allocation**,
whatever it is, and that an unallocated day reports no targets rather than the
placeholder. Do not restore a "today must have a budget" assertion — it encodes
the weekday shape of one seed plan, not an invariant.

Regression: `TestReadPathsMaterializeTheMonth` in
`app/tests/test_monthly_plan_rollover.py` (fails if either placeholder returns).

## Never measure against an invented budget, or invent account facts

`EnhancedMasterBudgetEngine.calculateEnhancedDailyBudget()` step 3 read
`userProfile['dailyBudget'] ?? 50.0` and `userProfile['monthlyBudget'] ?? 1500.0`.
`EnhancedProductionBudgetEngine._convertOnboardingToProfile()` emits
`monthlyIncome` / `incomeTier` / `goals` / `habits` and **no budget key at
all**, so on every live call the spending-velocity analysis ran against a
constant $50 day and $1500 month regardless of what the user earns or plans.

That is not cosmetic. The result feeds straight back into the user's own
number — `adjustedBudget = velocityAdjustment.adjustedDailyBudget` — and its
recommendations reach the Daily Budget screen via `_generateRecommendations`
-> `intelligentInsights` -> `BudgetAdapterService` `suggestions[].message`.

Nothing at that point can supply a real baseline: step 3 runs *before* the base
budget is calculated (step 2 passes `0.0, // Will be set after base
calculation`). The step is therefore skipped unless a real budget is known —
`velocityAdjustment` is nullable and every consumer already guards on null. A
wrong adjustment to someone's daily budget is worse than no adjustment.
**Restore this step by threading the real budget in, never by reinstating a
default.**

`user_profile_screen` stated three invented facts about the account: a
placeholder `user@mita.finance` shown as the user's own email, a
`profile_completion ?? 85`, and a join date of "30 days ago" fabricated
whenever `member_since` failed to parse. Each is now hidden when unknown.

Checked and left alone (unreachable — backlog, not blockers):
`ContextualNudgeService._personalizeMessage()` fills `{amount}`/`{days}`/
`{percentage}` with 50/5/75, which would render "75% of users in your income
tier save more than you this month" — but `suggestedNudge` is
`PersonalizedNudge? get suggestedNudge => null`, so `contextualNudge` is never
non-null and no nudge reaches the UI. `CalendarFallbackService` (194 lines
generating a month of fake `spent` amounts) has no production callers.
`ResilientGPTService.categorize_expense` returns `confidence: 50` on a 0–1 scale
the UI multiplies by 100, but has no production callers either.

Regression: the added groups in
`mobile_app/test/no_fabricated_personal_data_test.dart`.

## One bad row must not blank the whole list

`TransactionService.getTransactions()` mapped every row through
`TransactionModel.fromJson` inside a single `.map()`. `fromJson` hard-casts
`id` / `category` / `amount` and `DateTime.parse`s `spent_at` / `created_at`,
so one row missing any of them threw out of the map, the surrounding `catch`
rethrew, and the user lost **every** transaction rather than one. Rows are now
parsed individually; a row that fails is logged and skipped.

That payload is reachable, not hypothetical. In `alembic/0001_initial`:

    sa.Column("spent_at", sa.DateTime(), index=True)
    sa.Column("created_at", sa.DateTime())

Neither carries `nullable=False` nor a `server_default` (line 86 of the same
migration uses `server_default=sa.func.now()` for another table, so the pattern
was known). `Transaction.spent_at` / `.created_at` / `.currency` rely on
SQLAlchemy's **Python-side** `default=`, which only applies when the ORM builds
the object — any insert that bypasses it writes NULL. `TxnOut` then declares
`spent_at: datetime` and `created_at: datetime` as non-Optional, so a NULL row
fails Pydantic serialization and 500s the whole list endpoint.

**Open recommendation (not applied):** give those three columns `nullable=False`
plus a `server_default`, after backfilling any NULLs. That is a NOT NULL
migration on a populated production table — it needs a lock and a backfill, so
it is a deliberate release decision, not something to slip into a bug-fix
branch. No current code path writes NULL (no `bulk_insert_mappings`,
`bulk_save_objects` or raw INSERT on `transactions` exists), so this is latent
robustness, not an active defect.

Regression: `mobile_app/test/services/transaction_parse_isolation_test.dart`
drives the real Dio through a fake adapter and fails if a broken row again
takes the intact ones with it.
