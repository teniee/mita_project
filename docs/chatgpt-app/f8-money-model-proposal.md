# F-8 — one money model for the plan, the ledger and the forecast (proposal, 2026-10-25)

Status: **awaiting the owner's approval. Nothing in this document is implemented.**
The tests that pin today's behaviour are in `tests_mcp/test_money_consistency.py`.

## 1. Root cause

F-8 is not an arithmetic error in either figure. The day-by-day plan and the
forecast follow two different money models:

* The **rebalancer** (`realtime_rebalancer.check_and_rebalance`, replayed by
  `expense_tracker.rebuild_month_plan` after every ledger change) judges each
  **(date, category)** on its own: spending above *that date's* row for *that
  name* is overspending. It covers it only from **later dates of other
  categories** (the same category is excluded as a donor, earlier dates are never
  considered) and credits the date that went over.
* The **forecast** (`budget_forecast_engine.compute_forecast`) works on **month
  totals**: `remaining = Σ plan − Σ spent`. Rebalancing moves money between
  rows but never changes the total, so the forecast ignores it.

Every time money is spent on a different date, or recorded under a different
name, than the layout expects, the rebalancer pulls later money into that date
while the original allocation stays where it was. The month total is
unchanged, so the forecast still counts that money as available, but the dates
ahead no longer hold it.

Measured on the review account, October 2026, as of 24 Oct (reproduced exactly;
`test_money_consistency.py::test_f8_review_month_as_today`):

| What MITA treated as overspending | Amount | Real? |
|---|---|---|
| Groceries over its **monthly** line (426.10 spent vs 249.60 planned) | 176.50 | yes |
| Shopping, a category with no plan line | 29.99 | yes |
| Bills paid on their due date, laid out elsewhere: kindergarten 180 on the 5th (layout: 8.19 a weekday), utilities 95 on the 18th (layout: the 5th) | 266.81 | no — timing |
| Expenses recorded under the API's names, planned under the planner's (F-2): dining, gas, entertainment, healthcare, public transport | 288.00 | no — naming |
| Groceries bought in a few large shops against an 11.35-a-weekday layout, with unspent grocery shares on other days | 186.75 | no — pacing |
| **Total** | **948.05** | 206.49 real |

The rebalancer moved €904.32 between categories to cover it. That took the plan
for 25–31 Oct from €299.95 to €12.16, while left to spend stayed €853.91 (€121.99 a
day). Side effects on lines:

* utilities planned 190.00 for one 95.00 bill (95 laid on the 5th, plus a 95 credit on the 18th);
* kindergarten planned 231.04 for one 180.00 bill;
* home internet (a saved €30 bill due 27 Oct) cut to 9.17, because unknown
  categories default to FLEXIBLE and are donors (only SACRED lines are protected).

## 2. Where the concepts diverge in the lifecycle

| Step | Code | Divergence |
|---|---|---|
| Income, commitments | `update_financial_profile`, `add_recurring_expense` → `scheduled_expenses` (due date known) | — |
| Draft and layout | `budget_draft.build_draft` → `allocations_from_profile` → `month_calendar` (`CATEGORY_BEHAVIOR`) | **Due dates are not used:** rent on the 1st, other "fixed" lines on the 5th, unknown obligations (childcare, subscriptions, insurance) spread over weekdays |
| Bill paid | `add_transaction(s)` → `rebuild_month_plan` | The payment date's row for that line is usually 0 → the whole bill counts as overspending |
| Everyday expense | same | Spending is accrued under the stored category; the plan line may have another name (F-2) → planned-0 row, the full amount is overspending |
| Rebalancing | `check_and_rebalance` | Day-level trigger; the same line's other dates are never used; non-SACRED commitments are donors |
| Remaining / daily | `compute_forecast` | Month totals; unpaid commitments count as spendable (known since 2026-10-23) |
| Calendar | `queries/calendar.py` | Shows both models, labelled (`planned_after_today` vs the average) |

## 3. Recommended behaviour — the smallest coherent correction

One rule: **a category's monthly plan is its envelope; the dates spread it out
for pacing.** Money moves between categories only when an envelope is used up.

* **R1 — accrue spending to the plan line it belongs to.** `rebuild_month_plan`
  keys an expense by `categories.line_key` (the five declared pairs
  `dining→dining out`, `gas→transport gas`, `entertainment→entertainment events`,
  `healthcare→out of pocket medical`, `public_transport→transport public`, only
  when the month's plan has that line). This is the same mapping MITA's ChatGPT
  results already use for display. Stored transactions are unchanged. This
  closes F-2 in the ledger.
* **R2 — rebalance by envelope.** After spending on date D, compare the line's
  spending **from the 1st to D** with its plan **from the 1st to D**:
  1. within that → nothing moves (a bill paid late, a big shop after quiet days);
  2. above it → first move **the same line's later allocations** forward to D
     (a bill paid early, spending ahead of pace);
  3. only beyond the line's **whole month** → take the rest from other lines'
     later dates as today (discretionary first, at most 50 % per line). Never
     from set-aside lines or **commitment lines** (SACRED essentials plus the
     categories of the user's saved payments that count in the month — the
     calendar's existing definition).

  Same-line moves are pacing, not redistribution: they are not written to
  `redistribution_events` and not announced as "rebalanced".
* **R3 — mandatory payments come before discretionary money.**
  `compute_forecast` also returns `commitments_reserved` (per commitment line:
  planned − recorded, never below 0), and
  `safe_daily_limit = (remaining − savings_set_aside − commitments_reserved) / days_remaining`.
  This is the same treatment the savings fix of 2026-10-23 gave set-aside money.
  It is never matched to a specific bill by amount, only by the line.
* **R4 — lay saved bills on their due dates** in the reviewed budget
  (`build_draft`): each occurrence that counts in the month on its date (monthly
  on its day, the month's last day when shorter; weekly on its weekday; one-time
  on its date). Any rest of the line is laid out as today. Under R2 this changes
  where the money shows, not how much there is.
* **R5 — unspent money rolls forward within the month (rule D).** This is already
  what the forecast does. The calendar names it: "Planned for the dates ahead €X
  + carried forward from earlier days €Y = left to spend". The average stays an
  average, labelled; each date shows its own plan.

Simulated on the same base plan and ledger with the real rebalancer helpers
(the current rule reproduces €12.16 / €121.99 exactly):

| Figure (24 Oct) | Today | R1 + R2 | + R3 |
|---|---|---|---|
| Left to spend (after savings; with R3 also after unpaid commitments) | 853.91 | 853.91 | **689.51** |
| Commitments planned and not recorded | 289.61, counted as spendable (includes the double-held utilities and kindergarten money) | 164.40 (internet 30.00, medical insurance 134.40), counted as spendable | 164.40, reserved |
| Average a day, 7 days | 121.99 | 121.99 | **98.50** |
| Everyday plan on 25–31 Oct | 12.06 | **64.84** | 64.84 |
| Everyday money carried forward from earlier days | 552.24 (not shown as such) | 624.67 | 624.67 (shown, R5) |
| Utilities / kindergarten / internet lines | 190 / 231.04 / 9.17 | 95 / 180 / 30 | same |
| Moved between categories | 904.32 | 206.57 (groceries' and shopping's real overspending; 0.08 of it a knock-on of an earlier cut) | same |

The monthly arithmetic (plan, spent, left to spend) does not change. What changes
is that lines and dates keep their meaning: bills are held once, the internet bill
keeps its €30, and the dates ahead lose money only to real overspending.

## 4. Impact on stored and historical data

* **Reviewed budgets (base plans), transactions, goals: unchanged.**
  Adjustments are derived: `rebuild_month_plan` backs them out and replays from
  the base plan, so R1/R2 apply to a month the next time it is rebuilt.
* **Current month:** rebuilt on the next expense change. A one-off rebuild of
  every user's current month at deploy makes all views consistent at once
  (proposed: a guarded script per user under the ledger lock; staging first).
* **Past months: not rebuilt** (no silent rewrite). A past month is rebuilt
  only when the user edits an expense in it; its per-date plan then follows the
  current rule. The base plan and ledger are untouched. Alternative, if you
  prefer: freeze past months under the old rule (needs a rule version per month).
* **Next months:** R4 applies to budgets reviewed after the change. Rolled-over
  months (`ensure_month_plan`) keep today's layout; under R2 that is a
  presentation difference only.
* No migration and no schema change. R3 adds one field to the forecast output.

## 5. Impact on API and tool contracts (no field removed or renamed)

| Surface | R1 | R2 | R3 |
|---|---|---|---|
| `get_budget_status` | per-line spend is unchanged on MCP (it already pairs for display); planned per line changes (no double-held bills) | fewer "redistributed" notes | `today` unchanged |
| `get_budget_forecast` / mobile `/api/budget/forecast` | — | — | `safe_daily_limit` lower by unpaid commitments ÷ days left; adds `commitments_reserved` |
| `get_calendar_month`, `show_financial_calendar` | — | `planned_after_today` keeps real plan; line totals no longer inflated | `left_to_spend` excludes reserved commitments; "carried forward" shown (R5) |
| Mobile calendar / day details (`daily_plan` rows) | "dining" spending appears on the "dining out" row instead of a planned-0 row | redistribution banners only for real overspending; history shows fewer events | — |
| `redistribution_events` | — | fewer rows (same-line moves not logged) | — |

## 6. Tests that must pass before release

The scenarios in `test_money_consistency.py` (today's behaviour), switched to the
new expected figures for R1–R3, plus:

* the review month: the figures in the table above, exactly;
* a bill paid on its due date, early and late: no cross-category move, the line
  is held once, `commitments_reserved` falls to 0 once it is recorded;
* two bills in one category, paid together and apart;
* real overspending of an everyday line: covered from other everyday lines only,
  never from set-aside or commitment lines, with the 50 % cap;
* conservation: Σ rows = base plan total after every rebuild; the replay is
  deterministic and independent of recording order;
* parity: MCP status / forecast / calendar and the mobile forecast agree for the
  same rows (including Europe/Sofia near midnight);
* the mobile suites that pin the rebalancer (`app/tests/test_calendar_limits.py`,
  the redistribution history routes).

## 7. Decisions only you can make

1. **R2 envelope rule** (spending ahead of pace first uses that category's own
   later days; other categories pay only for real overspending), versus keeping
   today's "other categories pay first" at month-to-date level. **Recommended: R2.**
2. **R3**: unpaid commitments are excluded from the safe daily amount.
   **Recommended: yes.** Note that a default line the engine adds (medical
   insurance €134.40 here) counts as a commitment the user cannot remove from
   ChatGPT today.
3. **Past months**: rebuild on edit (recommended), or freeze.
4. **R1 in the mobile app**: "dining" expenses show on the "dining out" line.
   **Recommended: yes**; it is F-2's fix.

R4 and R5 follow from your principles A and D and need no separate decision
unless you disagree.
