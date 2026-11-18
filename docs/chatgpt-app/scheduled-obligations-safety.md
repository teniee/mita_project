# Saved payments and the scheduled-expense processor (2.11.0, Gate 1)

This covers PR #288 review findings P1 and P2, review G0-01, and one gap found
while testing them (S1). The rules live in `CLAUDE.md` ("Saved payments are
never paid by a scheduler").

## What was wrong (each one reproduced by a test that fails without its fix)

**P1: a bill saved in ChatGPT could become an expense by itself.**
`scripts/rq_scheduler.py` runs
`cron_task_scheduled_expenses.run_scheduled_expenses_batch` daily at 06:00 UTC.
* **What it did:** turned every pending `scheduled_expenses` row due today
  into a `Transaction` and pushed a notification. It had no filter on where
  the row came from, and ChatGPT's `add_recurring_expense` writes into the
  same table. Since 2.7.0 a saved payment is paid only by an expense the user
  links to it (`obligation_payments`).
* **Consequence:** with the scheduler running, every bill saved in ChatGPT
  would have been recorded as spent on its due date. A payment the user had
  already recorded and linked would have been recorded twice.
* **Where it runs:** wired only in `docker-compose.yml`, the k8s manifests and
  `deploy_task_system.sh`. Railway runs nothing of it: production holds only
  `mita-production` and `mita-production-db` (read-only check, 2026-11-17).
  The fix does not rely on that.

**P2: "the 31st" became "the 30th" for good.**
* A monthly row kept only its clamped next date: "rent on the 31st" saved in
  November was stored as 30 November.
* Every reader took the day from that date, so the rent fell on the 30th of
  every month and December's 31st was lost.

**G0-01: the mobile forecast counted a bill paid in the app twice.**
* `GET /api/budget/forecast` holds unpaid bills out of the safe daily limit
  (R3). Since 2.7.0 a saved payment's line is released only by a linked
  payment, and the app cannot link.
* A rent of 800.00 paid in the app was therefore spent and still held:
  (1,100 − 800 − 800) / 29 = **−17.24** a day instead of **10.34**.

**S1: with the processor running, an app bill was held again after it was
recorded.**
* The processor records an app row and creates next month's row.
* Under the shared rule a monthly payment also counts in the month before its
  next date, so the new December row counted in November too, unpaid.
* ChatGPT's November held **574.99** instead of **505.00**.
* The calendar showed no such bill, because it never drew one before its
  row's date, so the month disagreed with itself.

## The fix

1. **Migration 0045 (additive).** It adds two columns to `scheduled_expenses`:
   * `origin` (`'app' | 'chatgpt' | 'unknown'`, NOT NULL, default
     **`'unknown'`**, CHECK);
   * `day_of_month` (SMALLINT NULL, CHECK 1–31).
2. **Only `app` rows are processed or pushed**, in both phases of the
   processor (recording, and the reminder three days ahead).
   * **`app` is written by exactly one place:** the app's own create route,
     `POST /api/scheduled-expenses`, which passes it explicitly. The next row
     the processor creates for an `app` row keeps it.
   * **ChatGPT writes `chatgpt`.**
   * **Anything else is `unknown`:** older rows not proven to be ChatGPT's,
     the staging seed script, any future writer that does not say. The
     database default and the service default are both `unknown`. So a row
     of uncertain origin is never turned into an expense: the safe way.
3. **An app row already paid by a linked expense is not recorded again.** The
   processor marks it processed with the user's own transaction and creates
   the next row (`summary["already_paid"]`).
4. **One due-date rule for every surface** (`monthly_obligations.due_dates_in_month`):
   * A monthly payment falls on `day_of_month` when kept, otherwise on its
     date's own day, as before, clamped to the month.
   * An **app** row is one occurrence and never counts before its own date.
   * A **ChatGPT** or **unknown** row keeps the rule from before 0045 exactly.
     It is the obligation itself: a bill saved after this month's date has
     passed is still this month's.
5. **The mobile forecast settles a bill the way it can** (G0-01): what linked
   expenses paid, or what is recorded on the bill's line, whichever is more
   (`obligation_lines.paid_without_linking`, R3's rule). ChatGPT's figures are
   unchanged.
6. **Readiness.** The MCP `/health` answers 503 until 0045's columns are
   visible (`__main__.REQUIRED_COLUMNS`).

## Migration 0045, line by line

| Step | What it does | Why it is safe |
|---|---|---|
| `ADD COLUMN origin VARCHAR(16) NOT NULL DEFAULT 'unknown'` | Every existing row starts `unknown`. | Metadata-only on PostgreSQL 11+. `unknown` is never processed. |
| `ADD COLUMN day_of_month SMALLINT NULL` | NULL everywhere. | NULL means "use the date's day", exactly the old behaviour. |
| `CHECK origin IN ('app','chatgpt','unknown')` | Rejects any other value. | Scans once. Tested: `'bank'` is refused. |
| `CHECK day_of_month IS NULL OR BETWEEN 1 AND 31` | Rejects 0 and 32. | Tested. |
| `UPDATE … SET origin = 'chatgpt'` from `mcp_idempotency_keys` | Matches only ids that ChatGPT's own `add_recurring_expense` records name, **for the same user**. | A record whose ids are not a JSON array is read as `[]`, so no error can abort the boot migration. **No row is ever set to `app`.** |
| downgrade | Drops both CHECKs and both columns. | Loses only the two new facts. A re-upgrade marks such rows `unknown`, which is never processed. |

**Classifications.** Tested on a disposable database on 2026-11-17, then
dropped:

| Existing row | Becomes |
|---|---|
| made in the app (no ChatGPT record) | `unknown` |
| saved in ChatGPT, its record kept | `chatgpt` |
| saved in ChatGPT, its record purged (older than 30 days, and its owner wrote again) | `unknown` (**ambiguous**: never processed; old due-date rule) |
| named only in another user's record | `unknown` |
| named only in an `add_transaction` record | `unknown` |
| a record holding `{"not": "an array"}` | skipped, no error |
| a new row from a writer that does not state an origin | `unknown` |

The tested cycle was upgrade → constraints → downgrade (6 rows, sum 1,356.00
unchanged) → re-upgrade (same classifications). **Production:** no ChatGPT
service has ever run there, and 0038 creates the idempotency table empty in
the same upgrade, so every production row becomes `unknown`. Production rows
are never processed, which is no change: nothing processes them today. They
also keep their due dates exactly. **Staging:** after 0045, run
`UPDATE scheduled_expenses SET origin = 'chatgpt'`. Every staging row was
written by the MCP service or its scripts.

## Every reader and writer of `scheduled_expenses`

| Writer | origin | day_of_month |
|---|---|---|
| App `POST /api/scheduled-expenses` → `create_scheduled_expense` | `app` (explicit, the only writer of it) | NULL |
| ChatGPT `add_recurring_expense` → `create_scheduled_expense` | `chatgpt` | the day the user gave (monthly) |
| Processor, next row (`_schedule_next_recurrence`) | the row's own | the row's own |
| Processor, recording (`_process_due_expenses`) | status `processed` + transaction id | — |
| App `DELETE /api/scheduled-expenses/{id}` | status `cancelled` | — |
| `scripts/mcp/seed_staging_db.py` | `unknown` (default) | NULL |

No API route updates a row's date, so `day_of_month` cannot drift from an
edited date.

| Reader | Rule |
|---|---|
| `monthly_obligations.dated_obligations` / `obligations_due` | pending, not deleted; `due_dates_in_month(…, day_of_month, origin)` |
| ↳ `obligation_lines.month_commitments`: mobile forecast, the ledger's bill lines (`expense_tracker.month_bill_lines`), MCP plan / forecast / status | same |
| ↳ month rollover (`monthly_plan_service`) | same |
| MCP `budget_draft` (preview) | its own query, the same function and arguments |
| MCP calendar (`saved_payments` → `occurrences_in_month`, `counts_in_month`) | the same function; the drawing never shows a date before the row's |
| MCP `get_recurring_expenses` | the same function |
| MCP payment links (`writes/obligation_payments`: due date validation, candidates) | the same function |
| Processor | pending, not deleted, due today / in 3 days, **origin `app`** |
| MCP obligations (names, lookup by id), setup counts, the transaction tool's link lookup, `similar_pending` | no due dates, origin-independent |
| App list / get / impact (`scheduled_expense_service`, `compute_scheduled_impact`) | the app's own date semantics, unchanged |

## `paid_without_linking()` audit (mobile forecast only)

The mobile forecast holds `need − max(linked, recorded on the line)` per bill
line (`_still_reserved`). In a month the app laid out (legacy, unkeyed), a
bill's line is its category, and `need` is that line's whole base: the bill
plus the category's other money. Figures are pinned in
`app/tests/test_paid_without_linking.py`.

| Case | Held | Verdict |
|---|---|---|
| Rent 800 paid in the app / not paid / 900 paid | 0 / 800 / 0 | correct |
| Rent 800, 400 paid | 400 | correct |
| Transportation 100 + car loan 270 (370); a 60 car part | 310: the whole loan and 40 unspent | unrelated spending never releases the bill |
| Same, 130 spent on transportation, none of it the loan | 240 | only spending beyond the category's own money reaches the bill |
| Two bills in one category (270 + 50) + 100; the loan paid | 150: the scooter and 100 unspent | correct, never below the unpaid bill |
| Month laid out in ChatGPT: 270 spent on the category line | 270 | category spending never settles a bill line |
| Same, linked 270 (or linked in October for November) | 0 | correct, the same figure as ChatGPT |
| Utilities line holding only the 45 bill; a 20 lamp | 25 | **known limit:** the app cannot tell, bounded by the unrelated amount; linking in ChatGPT is exact |

## Recurrence never brings a recorded app bill back

After the processor records an app row:

* **The processed row** is not pending, so no reader counts it.
* **The next row** is next month's. As an app row it never counts before its
  own date, so the month just recorded holds nothing for it.

The tests check every surface:

* **ChatGPT calendar:** bills and `commitments_reserved` 505.00.
* **`get_budget_forecast`:** 505.00.
* **`dated_obligations`** (the source of the mobile forecast, the ledger's
  bill lines and the rollover): the four ChatGPT bills only.
* **A weekly app row recorded on the 4th:** November holds the 11th, 18th and
  25th, never the 4th again.

## Tests

* **`tests_mcp/test_scheduled_obligations_safety.py`** (12 tests): the real
  processor, real tools and the real database, on the owner's reference
  profile: income 2,500; savings 500; bills 505; flexible budgets 1,115; 380
  unallocated.
  * ChatGPT bills are never recorded or pushed.
  * A linked payment is never recorded twice.
  * App rows are recorded once and roll forward to the requested day.
  * An unknown row is never processed and keeps its old dates.
  * A weekly app row does not come back to its recorded date.
  * A retried save writes one row.
  * The 31st falls on Nov 30, Dec 31, Jan 31 and Feb 28/29, and a 31
    December payment links to it.
  * The pure rule, every month length.
  * Readiness.
  * The source rules: `app` written only by the app route; defaults
    `unknown`.
* **`app/tests/test_budget_forecast_local_day.py::test_a_bill_paid_in_the_app_is_not_held_twice`**
  goes through the real mobile route and the real ledger rebuild. It fails on
  the old code (800.00 held).
* **`app/tests/test_paid_without_linking.py`** (7 tests): the audit above.
* **Mutation checks** (files restored byte for byte afterwards). Each of
  these fails its test:
  * removing the origin filter;
  * ignoring payment links;
  * ignoring the requested day;
  * putting back the linked-only rule on the mobile route.

## Limits (known, not closed)

* **Rows saved in ChatGPT whose idempotency record is gone** are `unknown`,
  not `chatgpt`. They are safe (never processed, old dates). Only the
  release's staging step marks them.
* **Months laid out in ChatGPT, viewed in the app.** A bill's own line holds
  only linked payments, so a payment entered in the app stays held there
  until it is linked in ChatGPT. That errs on the cautious side.
* **A category whose line is only the bill** takes any purchase in it as
  part payment in the app (the utilities case above).
* **Months the app laid out before 0045** keep their processing semantics,
  minus processing itself. A row the app created before 0045 is `unknown`,
  so an environment that runs the processor no longer records those old
  rows. New app rows are recorded as before.
* **After the processor records an app row,** the calendar shows the expense
  on its date, no longer the bill.
