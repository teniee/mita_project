# R3 — the month's unpaid bills are not spendable

Status (2026-10-26): implemented in the shared forecast engine, used by
ChatGPT (`get_budget_forecast`, `get_calendar_month`, `show_financial_calendar`,
the sign-in page's example) and the mobile API (`GET /api/budget/forecast`).
Owner decision 2026-10-25 ("Bills come first", R3 approved); refined
2026-10-26 to the bills MITA can see paid — see "Which lines are bills".
Tests: `tests_mcp/test_bills_reserve.py` (the scenario matrix),
`tests_mcp/test_money_consistency.py` (every surface against each other),
`app/tests/test_budget_forecast_local_day.py` (the mobile routes).

## The rule

1. **A bill** is money MITA knows a payment will take this month and can see
   being paid:
   * the categories of the user's **saved regular payments** that count in
     the month (`monthly_obligations.due_in_month`: a repeating payment once
     it is running — its next date before the end of the following month; a
     one-time payment in its own month), and
   * the **essential lines the person stated** — rent, mortgage, utilities
     (`CATEGORY_PRIORITY` SACRED, not set aside) — with or without a saved
     payment behind them;
   * in both cases only a category an expense can be recorded under
     (`FinancialConstants.VALID_TRANSACTION_CATEGORIES`), because recording
     the payment is how MITA knows it is paid.
2. **What a bill needs** this month: its category's reviewed plan (the base
   plan, in-month rebalancing backed out — a rebalancing credit is not a
   second bill), or the saved payments due on it when they are more. Never
   both: a payment that is also in the plan is held once.
3. **Paid** is what is recorded under that category this month, in the
   user's timezone. `held = max(0, need − recorded)` per bill, summed as
   `commitments_reserved`. Matched by category, never by amount or by a
   specific transaction.
4. `left to spend = plan − spent − protected savings − commitments_reserved`;
   `safe daily = left to spend ÷ days after today` (Decimal, half-up; may be
   negative when the bills need more than the plan leaves).

`budget_forecast_engine.is_bill_line`, `is_recordable`,
`commitment_expectations` are the rule; every surface calls them.
`queries/plan.bill_line_keys` applies it to display lines: the calendar's
"Bills & commitments" group, and `get_budget_status.today`'s
`everyday_planned` / `everyday_spent` / `everyday_remaining` — today without
bill lines, so "Can I afford dinner out tonight?" on rent day does not count
the unpaid rent (`today.planned` still includes it, as the app's day figure
does; its description says so).

## Which lines are bills — the medical-insurance question

A reviewed plan can carry SACRED lines the person never stated. The engine
evidence:

| Question | What the repository shows |
|---|---|
| Where the "insurance medical" line comes from | `budget_logic.generate_budget_from_answers` adds it to **every** budget: 60 % of the income tier's healthcare weight, inside `discretionary_breakdown` (the other 40 % is "out of pocket medical"). The owner's real ChatGPT run (€2,500 income, rent stated, no insurance mentioned) got "insurance medical 105". |
| Whether a person can state it | No. Mobile onboarding stores stated bills under their own ids (`rent`, `utilities`, `internet`, `insurance`, `childcare`, `loan_payment`…); `category_mapper` (which would map `insurance` → `insurance medical`) is not used by any production code. ChatGPT's fixed lines are the saved payments' own categories. "School fees", "debt repayment" and "courses online" are written by no current flow at all. |
| Whether the person reviewed it as a bill | No. `preview_monthly_budget` lists it in `category_allocations` — "Flexible spending by category… from MITA's allocation rules" — not in `fixed_obligations` (the saved payments). |
| What SACRED means | "Never use as donor" (`category_priority`): the rebalancer never takes from the line. It is a redistribution order, not a statement that money is owed; it is unchanged. |
| Whether a payment can release it | No. No expense category is `insurance medical`; ChatGPT shows `healthcare` on "out of pocket medical" and `insurance` on its own line (`PRIMARY_PLAN_BUCKET`); the app accrues spending under the stored category (F-2). Held, the line would stay held after the person pays and records the bill — the payment counted twice — and held all month for people without such insurance. R1 (accrue to the paired line) was not adopted by the owner, so the release cannot be fixed without a model change. |
| Can it be removed | Not from ChatGPT (every preview recomputes it). |
| Earlier owner decision | 2026-10-25 approved R3 with the note that the default medical line counts; the approved mechanism is "planned − recorded, never reserved twice", which this line cannot satisfy. The refinement keeps the mechanism and the bills it can work for. |

**Conclusion**: a SACRED line counts as a bill only when it is recordable
(rent, mortgage, utilities). The engine's medical-insurance allowance (and
school fees, debt repayment, online courses where old data has them) stays
protected from rebalancing and is everyday money, shown in the calendar's
everyday group. A person who pays health insurance saves it as a regular
payment (category `insurance` or `healthcare`): then it is a bill, held and
released like any other. Rent or utilities stated without a saved payment
are still bills.

## The fifteen questions

1. **What is a commitment?** A bill as defined above.
2. **Where does it come from?** Saved regular payments (`scheduled_expenses`,
   pending, not deleted) and the stated rent/mortgage/utilities lines of the
   reviewed plan.
3. **When is it unpaid?** While less than its need is recorded under its
   category in the month.
4. **When does it stop being reserved?** When the recorded amount reaches the
   need, or the month ends (an ended month has no days left; the figure is
   still reported, see 10).
5. **Reserved and spent at once?** Impossible: held is `need − recorded`, so
   every recorded euro leaves the reserve as it enters `total_spent`; left to
   spend does not change when a held bill is paid (tests 1–2).
6. **Savings?** `savings_set_aside` (savings, emergency savings, goal
   reservations, investments) — never a bill; subtracted once.
7. **Goals?** Their `goal_savings` rows are set aside, not bills.
8. **A bill already recorded?** Its recorded amount is subtracted from its
   need; a bill paid in full holds nothing; more than planned is spending.
9. **A bill later in the month?** Held from the first day of the month until
   recorded; its date does not matter inside the month (due today, tomorrow,
   or earlier and unrecorded: all held — MITA cannot know an unrecorded bill
   was paid).
10. **Past months?** Read as stored; nothing is rebuilt on view. Safe daily is
    0 (no days left); `commitments_reserved` still reports what was never
    recorded, and the calendar's "left when the month ended" excludes it.
11. **Editing an older month?** The existing path: a ledger write rebuilds that
    month's daily rows (`rebuild_month_plan`); the reviewed base plan never
    changes; the reserve is recomputed on the next read (owner decision
    2026-10-25, "rebuild only on edit").
12. **Bill differs from its plan?** Paid less: the rest of the line stays held
    (by category, not by amount). Paid more: nothing held, the extra is
    spending. Saved payment above the plan: the payment's amount is held.
13. **Mandatory line without a saved payment?** Rent/mortgage/utilities: held.
    Medical insurance and other unrecordable names: everyday money.
14. **Saved payment in a category the plan already has?** One need,
    `max(plan, payments due)` — never the sum. Two payments in one category
    add up as the payments due (22.00 for 12.00 + 10.00), still held once.
15. **Month boundary?** Every surface takes "today" and the default month from
    the user's timezone (ChatGPT's `UserContext`; the mobile forecast since
    F-9's fix). 22:30 UTC on 31 October in Sofia is 1 November: November's
    bills, 29 days after today.

## Money flow (traced)

| Step | Code | R3 |
|---|---|---|
| Stated facts | `update_financial_profile`, `add_recurring_expense` → `scheduled_expenses` | saved payments = bills |
| Reviewed budget | `budget_draft.build_draft` → `allocations_from_profile` (fixed = saved payments due, `obligations_for_month` = `due_in_month`) → `save_monthly_budget` → `replace_month_plan` | base plan per category |
| Mobile onboarding | `generate_budget_from_answers` → `build_calendar` → `save_calendar_for_user` (fixed lines under their stated ids) | rent/utilities lines = bills |
| Expense recorded | `add_transaction(s)` / `POST /transactions` → `rebuild_month_plan` → `check_and_rebalance` (unchanged) | recorded per category |
| Forecast | `compute_forecast(commitments=commitment_expectations(base, due))` | `commitments_reserved`, `safe_daily_limit` |
| ChatGPT | `queries/plan.month_commitments` (needs per stored category, keyed by display line) → `forecast_from_rows`; the calendar uses the same forecast and the same `is_bill_line` for its groups | identical figures |
| Mobile | `GET /api/budget/forecast`: `base_totals_by_category` + `obligations_due`, the user's local day | identical figures |

## Before and after, by hand

Fixture (`test_bills_reserve.py`), 19 October, 12 days after today; plan
1,610.00 = rent 800.00 + utilities 100.00 + Savings 300.00 + groceries 310.00
+ dining out 100.00; rent saved, due on the 25th.

| | plan | − spent | − savings | − held (rent) | = left | ÷ 12 |
|---|---|---|---|---|---|---|
| rent not recorded | 1,610.00 | 100.00 | 300.00 | 800.00 | 410.00 | **34.17** |
| rent recorded on the 1st | 1,610.00 | 900.00 | 300.00 | 0.00 | 410.00 | **34.17** |
| before R3, rent not recorded | 1,610.00 | 100.00 | 300.00 | — | 1,210.00 | 100.83 |

The rent leaves `commitments_reserved` at the moment 800.00 is recorded under
`rent`; left to spend does not move.

| Account | Before R3 | R3 as first built (every SACRED line) | R3 final |
|---|---|---|---|
| F-8 review account (24 Oct, 7 days) | 853.91 → 121.99 a day | held 164.40 (internet 30.00 + medical insurance 134.40) → 689.51, 98.50 | held 30.00 (internet) → 823.91, **117.70** |
| Owner's real run (Ana, 11 Oct, 20 days) | 56.70 | held 105.00 (medical insurance) → 51.45 | held 0.00 (rent recorded) → **56.70** |
| Sign-in page example (19 Oct, 12 days) | 62.10 | held 30.00 (internet) → 59.60 | held 30.00 → **59.60** |

## F-9 (the mobile figures)

* `GET /api/budget/forecast` took "today" and the default month from the
  server's UTC date; it now uses the user's calendar day (`local_day_of`), the
  same as ChatGPT. Not called by the app today; the app is unreleased.
* `GET /api/budget/live_status` summed today's set-aside slices into
  `daily_budget`; it now leaves them out, as `get_budget_status.today` does
  (owner decision 2026-10-23). The app reads only `monthly_budget`,
  `monthly_spent` and `transaction_count` from this route today.
* F-10 (fixed 2026-10-27): the app's Live Budget Status card showed the
  monthly income (`live_status.monthly_budget`) as "Total Budget"; it now says
  "Monthly income". The app's figures and ChatGPT's no longer share a name for
  different values: the month's plan is the calendar screen's "Total Budget"
  and `get_budget_status.total_planned`; income − spent is the app's
  "Remaining", by design. `live_status.on_track` (income × day / 30) is shown
  nowhere.

## Limits

* A bill is matched by category: everyday spending recorded under a bill's
  category (a 2.00 bus ticket under `public_transport` when the monthly pass
  is saved there) uses that bill's line.
* Fixed lines a mobile user stated under other ids (`insurance`,
  `childcare`, `internet`, `loan_payment`) are bills only when saved as
  regular payments. The mobile app is unreleased; in ChatGPT every stated bill
  is a saved payment.
* A saved payment in a category no expense can be recorded under (possible
  only through the mobile scheduled-expenses API, which accepts any text) is
  not held: it could never be released.
