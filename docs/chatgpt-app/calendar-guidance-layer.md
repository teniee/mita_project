# The average left per day is a layer, not an event — calendar v5 (MCP 2.11.0)

Owner briefs of **2026-11-13** (the owner's acceptance of MCP 2.10.0 in the
real ChatGPT staging app failed on product grounds) and **2026-11-16** (an
equal division must not be presented as personalized advice). Implemented on
`feat/chatgpt-auth-ui` as **MCP 2.11.0**, calendar component
`ui://mita/financial-calendar-v5.html` (`13aa51f`; CI fixes `e48a24f`,
`65adcd9`); live on staging since 2026-11-16 17:22 UTC (deployment
`da577082`, `staging.md` → "MCP 2.11.0 — deployed"). No migration (alembic
stays `0044`), no engine change, no change to any stored row or approved
budget; month payload stays `version: 2`. Owner acceptance in real ChatGPT:
`acceptance-2.11.0-chatgpt.md` — not yet run.

This refines, and does not undo, `flexible-envelopes-calendar.md` (2.10.0): a
flexible budget is still on no date — no amount, no share, no purchase. 2.11.0
adds a second, labelled layer: **what is left per day, on average** — and says
plainly that it is an average. It supersedes the "whole euros in a phone's
grids" rule of `financial-calendar.md` (2.6.0) and the "≈ on dates with
nothing scheduled" of `behavioral-budget.md` §6 (2.7.0).

## 1. What failed, and why

| Seen | Cause |
|---|---|
| 2.10.0: with flexible budgets only, "All categories" showed the two loans and what was recorded; every flexible filter was an **empty grid**. The month's figures existed only as text. | 2.10.0 correctly removed the per-date share (3.33 on every date as a plan) and with it the only per-day figure on dates (2.7.0's "≈"). Nothing replaced it. |
| 2.10.0: on a phone a €1.50 coffee was drawn as **"2"**, inline and fullscreen. | A 2.6.0 rule for fit: whole euros in every phone grid (`fitAmount → wholeAmount` under 560 px). Nothing tested a small amount on a phone. |
| The first 2.11.0 draft called the restored figure a **"Daily guide"** and **"guidance"**. | The figure is what is left ÷ the days left — arithmetic. Naming it guidance presented an equal division as advice, which the 2026-11-16 brief rejects: "Adding ≈ … does not make it personalized financial guidance." |
| (found while testing) `ResizeObserver loop completed with undelivered notifications` as a page error (Chromium 1155). | v4 re-rendered inside its ResizeObserver callback; render is now deferred to the next frame. |

## 2. What MITA personalizes — verified in the code, 2026-11-16

| Question | Finding (file) |
|---|---|
| Income classes | `IncomeTier` (5 tiers) in `app/services/core/income_classification_service.py`, used by `generate_budget_from_answers` (`budget_logic.py`) to weight **MITA's own suggested monthly lines**. Profiles exist only for US, US-CA/FL/NY/TX and GB; every other country (Bulgaria included) gets `DEFAULT.yaml`: USD thresholds from a fallback stub, currency ignored, MIDDLE unreachable (`regional-capability-audit.md`). With the user's own lines (F-11) and "this is what I spend on" (2.8), MITA's lines are not in the plan at all. |
| Regional economics | 2.8/2.9: Eurostat/World Bank observations (`app/regional`, 7,047 on staging) give **references beside preview lines** (`regional_comparison`, `recommendation`), read **after** the draft's digest (`tools/budget.py`) — never an input, by the owner's 2.9 rule ("evidence order … never applied"). The calendar never reads them. |
| Spending history | `queries/history.py` → `recorded_average` and a warning **beside preview lines** (2.8 M4). Not in any allocation, forecast or calendar figure. |
| Spending patterns | Only what the user stated: a planned line's purchases on real dates (`spending_schedule.lay_out_line`, `purchase_dates`) — the one date-specific allocation, and it is Layer A. |
| Pay days | `pay_frequency` / `pay_days` are stored and reported (2.8, `tools/setup.py`) and **read by no calculation**. |
| Commitments and savings | Real and account-specific: unpaid bills (`commitments_reserved`) and savings not put aside are out of `safe_daily_limit` (R3). |
| Behaviour this month | The forecast engine's `pace_per_day` (spent ÷ days elapsed) against `planned_per_day`, `pace_status` (faster at ≥ 1.2×), `days_until_exhausted` — the user's own pace, arithmetic. |
| Legacy layout | `calendar_engine.distribute_budget_over_days`: weekday spreads and seeded-random weekend "clusters" — invented dates, retired for every month laid out since 2.7.0 ("never invent purchase dates"). |

**Equal division happens in six places**, none of them a personalized
recommendation: the stored bookkeeping (`lay_out_line`: a flexible line ÷ the
month's days), the preview's `per_day` (amount ÷ the month's days), the
forecast's `planned_per_day` (the same, the even pace), the calendar's
`left_per_day` (remaining ÷ days left, today included), `flexible_per_day`
(their sum, capped) and `safe_daily_limit` (left to spend ÷ the days after
today). The numbers were right; two descriptions were not: `planned_per_day`
was called "the recommended pace" and the calendar's figure "guidance". Both
now say what they are.

**The gap.** MITA has **no method that personalizes a daily figure** — none
weighs days by the user's history, income level, country or pay days. Adding
one is a new financial method and an owner decision (§8), not a calendar fix.

## 3. The rule: two layers, never merged

| Layer | What it is | MITA's fields | Drawn | Never |
|---|---|---|---|---|
| **Activity** | recorded spending (dates begun); planned purchases from a pattern the user stated, and saved bills on their due dates (dates ahead) | `days[].spent`, `planned_scheduled`, `planned_scheduled_everyday`, `day_lines = [line, scheduled, spent]`, `bills[]`, `purchases[]` | the date's **amount** (`data-amount`), the image's amount, the date's "Planned for this date" / "Everyday spending" / "Bills due" | — |
| **Average left per day** | what the money with no dates still holds, divided by the days left — an arithmetic average, said to be one | all categories: `summary.flexible_per_day`; filtered to a flexible budget: its `categories[].left_per_day` | on **today and every date ahead**: a pill marked **≈** (`data-guide`) under the amount; the date's spoken label; the date's "Average left per day" box; the image | in a date's amount, `planned_scheduled`, `scheduled_after_today`, `day_lines`, `data-amount`, a total or a balance; never a purchase, a bill, a plan, a limit **or a recommendation** |

A filter on a **planned** line (a stated daily coffee) or a **bill** has no
average: its money is on its dates already. A month with no flexible budget
has no second layer and no switch. Dates already past show history only.

## 4. Exactly which calculation it is

No new formula: both figures were published in 2.7.0 and are unchanged.

* **One flexible budget** — `CalendarLine.guidance()`
  (`app/mcp/queries/calendar.py`): `left_per_day = max(0, planned − spent) ÷
  days_left`, half-up to cents; `days_left` = today and every day after it
  in the month (a month ahead: all its days).
* **All categories** — `CalendarMonth.flexible_per_day`: `min(Σ left_per_day
  of the flexible budgets, max(0, safe_daily_limit))` for a month not ended.
  `safe_daily_limit` is the forecast engine's (`compute_forecast`, shared
  with `get_budget_forecast` and the mobile app): `(total_planned −
  total_spent − savings_set_aside − commitments_reserved) ÷ days_remaining`,
  `days_remaining` = the days **after** today. That `min` is the one place
  the figure depends on more than the envelopes: unpaid bills and savings
  keep it within what the month as a whole can afford.
* **Additive**: `summary.flexible_per_day_capped` — which branch of that
  `min` applied (true: the figure is the safe average; false: the
  envelopes' sum; null: no figure).

**Why `flexible_per_day` and not `average_per_day` for "All categories".**
`average_per_day` covers all everyday money, planned purchases included,
which are already on their dates (the 1.50 coffee would be counted twice),
and the filters' figures would not add up to it. `flexible_per_day` is
exactly the money that has no dates. `average_per_day` stays the hero figure
("Safe to spend, on average").

**The brief's month, by hand** (12 November, 30 days; 19 days left with
today, 18 after it): Groceries 320.00 ÷ 19 = 16.84, Car maintenance 200.00 ÷
19 = 10.53, Entertainment 100.00 ÷ 19 = 5.26, Restaurants 60.00 ÷ 19 = 3.16
(40.00 spent) — together **35.79** (680.00 left), under the safe average
722.00 ÷ 18 = 40.11. The 15th shows **271.50** (car loan 270.00 + the stated
coffee 1.50) as its amount and **≈ 35.79** apart; 307.29 appears nowhere.
**The reference profile** (income 2,500; savings 500; bills 505; flexible
1,115; 380 unallocated; 50.00 of groceries spent): planned 2,120.00, the 380
on no line, savings 500.00 protected, 505.00 held on the 5th, 15th, 20th and
25th, flexible 1,065.00 left → **56.05** a day, under the safe average 59.17.
An account on 1,985 with no country and one on 6,000 in Bulgaria, with the
same plan and spending, get the same figures to the cent — evidence that the
figure is arithmetic (`test_calendar_guidance_layer.py`).

**Two divisors, both named.** The safe average divides by the days after
today (the engine's, app-wide); the per-day average by the days left with
today. The summary says "18 days after today"; "How is this worked out?"
lists "÷ Days after today 18" and "÷ Days left, today included 19".

**A month ahead.** Nothing is spent and every day is left, so a budget's
average is its amount ÷ the month's days (Restaurants 100.00 ÷ 30 = 3.33) —
drawn only in the second layer, called an average, never a date's amount.

## 5. Component v5 — the smallest complete change

* **Cells** (fullscreen grid and the inline card): the amount as in 2.10.0;
  under it, on today and the dates ahead, the **≈** pill. Opaque colours so
  contrast holds on every cell, the yellow "today" included (light `#3D44B0`
  on `#EEF0FF` ≈ 7.0 : 1; dark `#C5C8FF` on `#2B2E55` ≈ 8.0 : 1). The date's
  label ends "average left per day for your flexible budgets about €35.79,
  what is left divided by the days left, not a plan or a recommendation".
* **Switch "Daily average"** above the grid (`role="switch"`, state in
  words), on by default, kept in ChatGPT's widget state. Off = activity
  alone (the 2.10.0 drawing) in the grid, the inline card, the date's detail
  and the image.
* **Every cent.** A phone drops ".00" and sets cents a little smaller; two
  smaller sizes come first; only then an amount of **100 or more** may lose
  its cents, said under the grid. An amount under 100 is never rounded. The
  ≈ pill on a phone shows whole units (it is "about"); exact figures are in
  the banner, the hero, the date's label and detail and "How is this worked
  out?".
* **Words**: hero "€680.00 left · ≈ €35.79 a day on average — an average, not
  a recommendation or a daily limit"; banner "≈ €3.16 a day on average"; the
  detail box "Average left per day … It is an average of what is left, not a
  recommendation: not part of the €271.50 scheduled for this date, and
  nothing is taken from your balance"; caption "≈ marks the average left per
  day from today: an average of what is left, not a plan"; "How is this
  worked out?" adds "It is arithmetic, not a recommendation: MITA does not
  weigh days by your habits, income or country". No visible text says
  "guidance" or "recommended" (tested).
* **For ChatGPT**: tool texts and schema descriptions call these figures
  averages — "not personalized recommendations (MITA's daily figures do not
  use the user's income level, country, past spending or pay days)";
  `planned_per_day` is "the even pace", no longer "the recommended pace".
* **Image**: each date from today has its amount and, apart, its pill; a note
  line gives the calculation, a legend line the meaning; the switch off
  draws none.

## 6. What did not change

Stored rows, approved budgets, the engine, layout, settlement within a line
(R2), rebalancing, the bills reserve (R3), bills on due dates (F-8), the
forecast, the mobile API, `day_lines` and the payload version, the 2.9
references (still beside preview lines, never applied) and every 2.10.0 rule
about what a date's amount is.

## 7. Acceptance criteria → tests

| Criterion | Where |
|---|---|
| Flexible envelopes never become scheduled purchases | `test_flexible_envelopes_calendar.py` A–D, K; `test_calendar_guidance_layer.py` (day_lines, planned_scheduled per date, the reference profile); rendered: filters' amounts = recorded only |
| An equal division is not presented as personalized advice | data: descriptions and the model's text say "average … not a recommendation"; the same figures for 1,985 / no country and 6,000 / Bulgaria; rendered: no visible "guidance", "daily guide" or "recommended"; the source rule |
| Income and region only where the engine supports them | data: income and country change no daily figure (the engine has no such method); the 2.9 references stay beside preview lines (`test_regional_recommendations.py`) |
| Differences between people are respected | data: 100.00 of groceries lowers that person's grocery average and aggregate, nobody else's |
| Expenses reduce balances; past expenses unchanged | data: 50.00 → 270.00 left; reading the month twice changes nothing |
| Irregular categories | Car maintenance: no purchase, no date, only its month and its average |
| Confirmed purchases, obligations on their dates | coffee 1.50 on each date; bills on the 5th/15th/20th/25th, held until linked |
| Protected savings, unallocated reserve | savings 500.00 out of every spendable figure; the 380 on no line |
| No double counting | `scheduled_after_today` = bills + purchases ahead only; rendered: 271.50 and ≈ 35.79 apart, never 307.29 |
| Filters consistent | rendered J: filters' amounts add up to All categories; flexible averages add up to the aggregate when not capped; capped wording |
| Default calendar not empty | rendered: the average on every date from today (35.79; 26.38 on the 2nd) |
| 1.50 never shown as 2; no overflow | rendered: 390 and 320 px, inline and fullscreen, every filter, average on and off |
| Image keeps the two apart | rendered: every `fillText` recorded — 19 pills in their colour, amounts in theirs, none merged; switch off draws no "≈" |
| Accessibility | axe-core 4.10.2, WCAG 2.2 AA, light and dark |

The rendered checks run in the **required MCP CI** job
(`requirements-mcp-render.txt`: playwright 1.50.0 — 1.49.1 pins
`greenlet==3.1.1`, which the lock's 3.5.3 rules out — Pillow, Chromium,
WebKit, axe-core; `MITA_RENDERING_REQUIRED=1`).

## 8. Open: a personalized daily figure (owner decision)

What the data already supports, if the owner wants daily figures that are
more than an average — each is a **new method** and needs a decision, a
documented formula and its own tests:

1. **History-shaped pacing** — the user's own complete months
   (`queries/history.py`, ≥ 3 months, local days) give how much of a
   category is usually spent by a given day of the month; "€X left, you
   usually spend about Y by this date" instead of an even split.
2. **Pay-day cash flow** — stated `pay_days` (2.8, unused) could pace
   spending between paydays instead of over the whole month.
3. **Irregular categories** — let the user say a budget is irregular (car
   maintenance, clothing) and show only its month, no per-day figure.
4. **Income bands and regional references** — fixing the DEFAULT bands, or
   applying a 2.9 reference to an amount, is app-wide and was explicitly not
   approved in 2.9.

## 9. Known limits

* Two divisors (§4): whether the safe average should count today is an
  app-wide owner decision.
* A date's `over` still pools the date's rows (2.10.0 §7, unchanged).
* The ≈ pill on a phone is whole units; a figure of 1,000 or more a day is
  untested at 320 px.
* Widget state depends on ChatGPT keeping it; the harness proves the
  component saves and restores it.
* PR #288 P1/P2 (the scheduler that would pay saved payments by itself; the
  29th–31st due day) are unrelated and still open.
