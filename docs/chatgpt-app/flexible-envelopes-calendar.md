# A budget is not a schedule: flexible budgets in the calendar — 2026-11-11

Owner brief of 2026-11-11, after MITA MCP 2.9.0 on staging. Implemented on
`feat/chatgpt-auth-ui` as **MCP 2.10.0**, calendar component
`ui://mita/financial-calendar-v4.html`. No migration, no engine change, no
change to any stored row. This supersedes one sentence of
`behavioral-budget.md` §6 (the "≈" daily guide drawn on dates) and the
`planned_flexible` line of `financial-calendar.md`.

## 1. What the owner saw (2.9.0, November 2026)

| Flexible budget | A month | On every date ahead |
|---|---:|---:|
| Groceries | 320 | 10.67 (10.66 on the last ten dates) |
| Car maintenance | 200 | 6.67 / 6.66 |
| Entertainment | 100 | 3.33 / 3.34 |
| Restaurants | 100 | 3.33 / 3.34 |

Selecting Restaurants showed 3.33 on practically every future date. Nobody
scheduled a restaurant visit a day. And "All categories" showed 1.50 of
coffee on almost every future date, while the other categories showed
nothing there until they were selected.

Reproduced with a fictional account in the local harness on `af67d69`, in
the rendered component (`review/calendar-v4/README.md`):

```
All categories      13 Nov … 30 Nov: 1.50   (15th: 271.50, 25th: 71.50)
filter Restaurants  13 Nov … 30 Nov: 3.33
filter Groceries    13 Nov … 20 Nov: 10.67, 21 … 30 Nov: 10.66
filter Car maint.   13 Nov … 20 Nov: 6.67,  21 … 30 Nov: 6.66
filter Entertainment 13 Nov … 30 Nov: 3.33
```

## 2. Root cause (each step confirmed in the code of `af67d69`)

It is one chain, not a division error in one place: a storage convention
that is correct for the engine was handed, untyped, to the component.

| Step | Where | What happens |
|---|---|---|
| 1. The engine stores a monthly limit evenly | `spending_schedule.lay_out_line` (231): a line with no stated pattern is `flexible`, `dates = _month_days(year, month)` (248), `split_amount_exactly(total, len(dates))` (250) → `monthly_plan_service` (732) writes one `daily_plan` row per date, stamped `_mita_line_kind_v1 = flexible` (763) | 320.00 ÷ 30 = 20 × 10.67 + 10 × 10.66; 100.00 ÷ 30 = 20 × 3.33 + 10 × 3.34. Documented as a layout "only so that each date carries its share" — the ledger needs rows to move the line's own money to the dates it is spent on (`bill_timing.retime_bill_lines`) |
| 2. The calendar reads every row as a date's plan | `queries/plan.month_plan` (83) → `queries/calendar.build_calendar`: `per_day[day][line][0] += amount` for every row | no difference between a row that is a purchase and one that is a share |
| 3. It separates them only in the day totals | `CalendarDay.planned_flexible` (728) and `planned_scheduled = planned − planned_flexible` (158) | correct, and what "All categories" used — which is why that view showed only the coffee |
| 4. …but not line by line | `DayLine(line=key, planned=values[0], spent=values[1])` (735) → `serializers.calendar_widget_payload` (704): `day_lines[date] = [[line, money(line.planned), money(line.spent)], …]` | the component received `["my:Restaurants", "3.33", "0.00"]` for all 30 dates |
| 5. The filter drew it | `financial_calendar.html` `cellModel` (1012–1021): `planned = match ? match.planned : "0.00"`; the "≈" guide and the exclusion of flexible lines existed only on the unfiltered path (`!state.filter`, 1682) | **the reported defect**: 3.33 in every date ahead; a begun date judged over / within against 3.33 |
| 6. The image drew the sum | `drawExport` (2344): `cellAmount(day.planned)` | every date ahead in the PNG showed 25.50 — all envelopes' shares together |
| 7. The date's detail and the tiles used it too | "Everyday plan" in a bill date's split (1878) = `planned_everyday`; a begun date's "of X planned"; "Planned on the days left" (1530, 1553) = `summary.planned_after_today` = Σ `planned` of the dates ahead (`calendar.py` 349) | the shares counted as upcoming planned spending |
| 8. A date ahead was "planned" | `CalendarDay.status` (174): `"planned" if planned_everyday > 0` | every date of the month, because of the shares |

**Why "All categories" and a single category disagreed.** "All categories"
showed `planned_scheduled`; a filter showed the line's stored row. The 1.50
is not a share: it is a planned purchase. A line is `planned` only from a
pattern the user stated (`spending_patterns.source = user_confirmed`, or the
`spending_patterns` argument of the preview that is saved with the budget;
`lay_out_line` has no other source of dates) — here "every day", 45.00 ÷ 30.
With no stated pattern the same 45.00 is a flexible budget and is on no date
(tests E and F).

**Why the tests did not catch it.** They asserted the share as data
(`planned_scheduled == "0.00" and planned_flexible > 0`, "its flexible share
— never a fabricated purchase") and were right about the data. No test read
what the component is handed per line (`day_lines`), and the widget harness
never filtered to a flexible line or read a cell's amount under a filter, a
future cell of the image, or a date's state.

## 3. What the two fields are

| Field | What it is | A transaction? Persisted? |
|---|---|---|
| `days[].planned_flexible` | Σ over the flexible lines of the stored `daily_plan.planned_amount` on that date: the bookkeeping of where the engine keeps a monthly limit's money (evenly at first; after spending, where the line's own money moved). | No transaction is ever created for it (`transactions` is written only by the expense tools; test H counts the rows). The `daily_plan` rows are persisted — they are the plan's storage, and are not changed by this release. |
| `categories[].planned_per_day` | The forecast engine's `monthly_planned / days_in_month` for the line (`budget_forecast_engine` 340): the even pace `pace_per_day` is compared with. One figure per line, on no date. | Computed on read, never stored. |

Neither affects a balance: `left_to_spend`, `average_per_day`
(`safe_daily_limit`), the reserve for bills and every line's `remaining`
are month sums and were always right. What they did affect: the amounts drawn
on dates, a date's state, and `planned_after_today` shown as "Planned on the
days left".

## 4. The rule

A date holds only what belongs to it. Four different things, never merged:

| Kind | On a date | Source |
|---|---|---|
| Recorded spending | the date it was recorded | `transactions` (the ledger) |
| A saved bill (obligation) | its due date, in full; `paid` only from an expense the user linked | `scheduled_expenses`, `obligation_payments` |
| A planned purchase | the dates a pattern **the user stated** gives (or dates MITA proposed for a stated frequency, marked `proposed`) | `spending_patterns` → the plan's base rows |
| A flexible budget | **no date** | the line: `planned`, `spent`, `remaining`; guidance `left_per_day` |

Daily guidance (`left_per_day`, `summary.flexible_per_day`: what is left ÷
the days left, today included, never above the safe average) stays, with
the summary, each flexible line and the selected date's "Flexible budgets ·
this month" list — always worded as guidance ("about 3 a day as guidance,
not a daily limit"). It is never an amount in a date's cell.

## 5. What changed

**Query (`app/mcp/queries/calendar.py`).** `DayLine.scheduled`: what is
scheduled on the date for the line — its stored row, or 0 for a flexible
line. `CalendarDay.scheduled_everyday`. `CalendarDay.status`: a date ahead is
`planned` only when an everyday purchase is scheduled; a begun date with
nothing scheduled is `unplanned` (spent) or `quiet`, never `within` a plan it
did not have; `over` is unchanged. `everyday_left` only for `over` /
`within`. `CalendarMonth.scheduled_after_today`.

**Contract (`schemas.py`, `serializers.py`, `tools/calendar.py`).**

| Field | 2.9.0 | 2.10.0 |
|---|---|---|
| `days[].planned_scheduled` | planned purchases + bills | unchanged; described as the only amount to present as planned for a date |
| `days[].planned_scheduled_everyday` | — | **new**: its everyday part (planned purchases) |
| `days[].planned_flexible` | "the flexible budgets' daily share: guidance" | same value; described as bookkeeping, never a purchase, bill, limit or target for the date |
| `days[].planned`, `planned_everyday` | "the date's spending plan" | same values (the stored rows; `get_budget_status` and the mobile day budget still equal them); described as bookkeeping = scheduled + flexible share |
| `days[].state` | future `planned` whenever any row exists | `planned` only with a scheduled everyday purchase; begun dates as above |
| `days[].everyday_left` | for any begun date with rows | for `over` / `within` dates only |
| `summary.scheduled_after_today` | — | **new**: planned purchases and bills on the dates ahead |
| `summary.planned_after_today` | "the plan on the dates after today" | same value; described as bookkeeping (scheduled + shares) |
| `categories[].planned_per_day` | "recommended pace" | same value; "analysis only … not a daily limit" |
| `categories[].left_per_day`, `summary.flexible_per_day` | guidance | same values; "not a limit or a target for any date" |
| component payload `_meta["mita/calendar"]` | `version: 1`, `day_lines = [line, stored row, spent]` | **`version: 2`**, `day_lines = [line, scheduled, spent]`; a flexible line is listed on a date only when something was spent from it |
| `get_budget_status.today.planned` | — | same value; the description says it includes the flexible budgets' share kept on today (not a limit for today) |

Compatibility: every existing field keeps its name, type and value except
`state` / `everyday_left` on dates with nothing scheduled and `day_lines`
(component-only, versioned). A component written for payload version 1
refuses version 2 instead of drawing it with the old meaning, and v4 refuses
version 1.

**Component v4 (`app/mcp/ui/financial_calendar.html`).** One rule for
"All categories" and every filter (`cellModel`): a begun date shows what was
spent, a date ahead what is scheduled; so the filters' dates add up to the
unfiltered calendar (test J, and drawn in `test_calendar_rendering.py`).
The "≈" daily guide is no longer drawn on dates; dates with nothing scheduled
are empty, and a line under the grid says why. A flexible filter's banner
gives the month: "flexible budget · spent 40.00 of 100.00 this month · 60.00
left · about 3 a day as guidance · no purchase dates". The date's detail
shows "Nothing scheduled" or the scheduled amount, "Planned purchases + Bills
due = Scheduled for the date", and the flexible budgets as the month's. The
tile reads "Scheduled on the days left". The exported image draws
`planned_scheduled`. The model context no longer carries a per-date share.

## 6. What did not change

* No stored row: `daily_plan`, `transactions`, `scheduled_expenses`,
  `spending_patterns`, `mcp_budget_lines`, `obligation_payments` and the
  profile are read exactly as before; the calendar tools are read-only by
  construction (`SET TRANSACTION READ ONLY`), and test N compares the account
  before and after every way the calendar is opened.
* No amount: the user's lines, the savings target, the unallocated remainder
  (the 380.00 of the brief's month is `income − total_planned`, on no line),
  `left_to_spend`, `average_per_day`, `commitments_reserved`.
* No engine rule: layout, settlement within the line (R2), rebalancing, the
  forecast, the mobile API. Months saved before 2.7.0 (no line kinds) read
  exactly as before (`test_a_month_saved_before_line_kinds_reads_exactly_as_before`).
* No migration, no grant, no environment variable.

## 7. Known limits (reported, not changed here)

* **A date's `over` still pools the date's rows.** `over` compares the
  date's everyday spending with everything the plan rows hold on it, the
  other flexible budgets' shares included (the 2026-10-24 rule, unchanged).
  So one line going over its month can be absorbed on the date by other
  lines' shares: Restaurants 101.00 against 100.00 is `over_limit` with
  `remaining −1.00` on the line (always exact), while the 10th is not `over`.
  The component therefore states an over date in an envelope month without a
  pooled amount. A line-exact date verdict is a money-model decision (it
  would also change legacy months' wording), not made here.
* **`get_budget_status.today.planned`** still sums today's rows, shares
  included (it equals the mobile day budget). The description now says so;
  the safe daily figure was never affected.
* **Savings** are still laid out as dated slices ("set aside 23.81 on this
  date — not for spending"), shown apart and never in a date's amount.
* **A planned line after an early or larger purchase**: the date's cell
  shows what the line still holds on it (76.60 after an 85.00 shop used 3.40
  of the next one), while `purchases[].planned` keeps the reviewed 80.00.
* **Open review findings on PR #288, both still true at this commit and not
  part of this change** (each needs an owner decision):
  P1 — `cron_task_scheduled_expenses._process_due_expenses` would turn every
  pending saved payment into a transaction on its date and mark it
  processed. Nothing runs it on Railway (`start.sh` and the MCP image start
  no scheduler; the compose / k8s scheduler manifests are not deployed), so
  no obligation is paid by itself today — but starting that scheduler would
  break "an obligation is not automatically a completed payment".
  P2 — a monthly payment saved for the 29th–31st in a shorter month stores
  the clamped date, and `monthly_obligations.due_dates_in_month` then derives
  later months from `scheduled_date.day` (saved as the 31st on 10 Nov → 30 Nov,
  then 30 Dec instead of 31 Dec). Fixing it needs the requested day stored
  (a column). The brief's loans (15th, 25th) are not affected.

## 8. Tests

* `tests_mcp/test_flexible_envelopes_calendar.py` (18): the brief's November
  through the real tools on PostgreSQL — A–D no flexible budget on any date
  (**fails on `af67d69`** with `'my:Groceries' … ('10.67', '0.00')` in the
  component's date lines), E stated daily coffee once per date, F coffee
  without a pattern, G weekly groceries on the four Wednesdays, H a real
  40.00 expense, the whole budget on one day, I the loans on their due dates
  and never paid by themselves, J all categories = the sum of the filters, K
  the contract and the published descriptions, M months of 28 / 29 / 30 / 31
  days to the cent, N nothing of the user's changed, the state rule and the
  legacy layout without a database, the component's source rules.
* `tests_mcp/test_calendar_rendering.py` (L; dev-only dependencies, skipped
  in MCP CI): the real component in a sandboxed iframe fed by the real
  tools — desktop and 390 px phone, light and dark, every filter, the
  selected date, empty dates, month navigation, the PNG.
* Updated deliberately: `test_calendar.py` (`scheduled_after_today`),
  `test_behavioral_budget.py` and `test_bill_due_dates.py` (a date with
  nothing scheduled is `unplanned` / `quiet`, not `within`).
