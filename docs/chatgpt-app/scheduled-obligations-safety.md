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
3. **An app row the user pays through links is theirs.** Once any expense
   is linked to any of its due dates, deleted or not, partial or not, the
   processor never records it, marks it processed, rolls it forward or
   reminds of it (`summary["paid_through_links"]`).
   * Every surface then shows its due dates paid or unpaid from the links,
     so a deleted or partial payment stays held and a payment linked ahead
     is never recorded again.
   * Each row is re-read under the user's ledger lock, so two runs never
     record it twice.
   * An app row's next row keeps its own date's day: 31 Jan → 28 Feb →
     31 Mar.
4. **One due-date rule for every surface** (`monthly_obligations.due_dates_in_month`):
   * A monthly payment falls on `day_of_month` when kept, otherwise on its
     date's own day, as before, clamped to the month.
   * An **app** row is one occurrence and never counts before its own date.
   * A **ChatGPT** or **unknown** row keeps the rule from before 0045 exactly.
     It is the obligation itself: a bill saved after this month's date has
     passed is still this month's.
5. **The mobile forecast cannot link, and ordinary spending never releases a
   saved bill** (G0-01; `obligation_lines.paid_without_linking`, mobile route
   only):
   * **rent, mortgage, utilities** (`is_bill_line`) in a month the app laid
     out: the category is the bill, and what is recorded on it pays it (R3).
     A rent paid in the app is counted once.
   * **any other saved payment** (a loan, a subscription, insurance): only a
     link pays it. Spending on its line uses only the line's everyday money
     (`need − due`), so it is never held twice either.
   * **a `bill:` line laid out in ChatGPT:** exactly ChatGPT's linked figure.

   ChatGPT's figures do not change. The first version credited all spending
   on the line, which let fuel release an unpaid car loan (independent
   review, below).
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

The forecast holds `need − paid` per bill line (`_still_reserved`). The
figures below are pinned in `app/tests/test_paid_without_linking.py`, and the
review's two cases also through the real routes
(`app/tests/test_budget_forecast_local_day.py`).

* **Bill money and everyday money look the same.** In a month the app laid
  out, a bill's line is its category, and nothing records which part of it
  is the bill. `bills_on_due_dates` never places a bill beyond its
  category's allocation, and a bill scheduled after the month was laid out
  is not in it at all.
* **So only the category tells.** Rent, mortgage and utilities are bills by
  nature. Any other category is ordinary money plus, perhaps, a bill.

| Case | Held | Verdict |
|---|---|---|
| Rent 800: paid in the app / not paid / 900 paid / 400 paid | 0 / 800 / 0 / 400 | correct |
| Rent saved after the month was laid out (no rent line), paid in the app | 0 | correct |
| Transport 150 (5 a day), car loan 270 scheduled in the app later, 150 of fuel (**the review's P0**) | 270 | the loan stays held; it was 120 in the first version |
| Same, and the loan also paid in the app (420 recorded) | 270 | **known limit**: link it in ChatGPT; it errs on holding |
| 'other' laptop loan 70 and a 70 lamp (no 'other' money, or 100 of it) | 70 | the loan stays held |
| Transport 370 = 100 everyday + 270 loan; 60 or 130 spent | 310 / 270 | spending uses the everyday money only, never the loan |
| Same, the loan linked (270 on the line); then 60 of fuel too | 100 / 40 | the unspent everyday money held, never twice |
| Two loans (270 + 50) + 100 everyday; 100 spent; then the 270 linked | 320 / 50 | each held until linked |
| Month laid out in ChatGPT: last month's loan paid late, linked to last month, lands on this month's line (**review finding 2**) | 270 | this month's loan stays held |
| Same line, this month's payment linked | 0 | the same figure as ChatGPT |
| Utilities line = the 45 bill; a 20 lamp recorded as utilities | 25 | **known limit** (R3): bounded by the amount |

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

* **`tests_mcp/test_scheduled_obligations_safety.py`** (20 tests): the real
  processor, real tools and the real database, on the owner's reference
  profile: income 2,500; savings 500; bills 505; flexible budgets 1,115; 380
  unallocated. Since the review it also covers:
  * payments linked ahead (monthly and weekly), never recorded again;
  * a deleted linked payment, before or after the run, leaving the bill
    held;
  * a partial payment keeping 450.00 held;
  * no reminder for a bill already paid;
  * a second run never recording a handled row;
  * an app row keeping 31 Jan → 28 Feb → 31 Mar;
  * a reused key asking for another day being refused.
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
* **`app/tests/test_paid_without_linking.py`** (8 tests), plus three
  route-level tests: the review's fuel / car loan and lamp / laptop loan
  cases, and the create route writing `app`.
* **Mutation checks** (files restored byte for byte afterwards). Each of
  these fails its test:
  * removing the origin filter;
  * ignoring payment links;
  * ignoring the requested day;
  * the linked-only rule on the mobile route;
  * and, since the review:
    * the processor ignoring links;
    * no re-read under the lock;
    * reminders ignoring links;
    * the successor forgetting the day;
    * crediting all spending to a loan;
    * keyed lines taking recorded spending;
    * the first date beating the stated day;
    * the digest ignoring the day.

## Independent review of the first Gate 1 commit (`ae18579`, 2026-11-18)

A fresh reviewer read the commit, verified every claim against the code and
reproduced each finding on disposable databases (never `test_mita`).

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | P0 | Mobile: unrelated spending in a bill's category released the unpaid bill: 150 of fuel left 120 of a 270 loan held, 18.00 a day instead of 3.00 | **Fixed**: ordinary spending never releases a non-rent/mortgage/utilities bill |
| 2 | P1 | Mobile, months laid out in ChatGPT: a payment linked to another month settled this month's bill line | **Fixed**: `bill:` lines take only this month's links |
| 3 | P1 | Processor: a link to a deleted expense counted as payment, so the bill was neither recorded nor held; a deletion after the run lost it | **Fixed**: rows paid through links are the user's; the links decide |
| 4 | P1 | Processor: a partial linked payment closed the whole occurrence | **Fixed** (same) |
| 5 | P1 | Processor: links to later occurrences were orphaned when the row rolled forward, so the payment was recorded twice | **Fixed** (same) |
| 6 | P2 | Two concurrent runs recorded twice (existed before) | **Fixed**: re-read under the ledger lock |
| 7 | P2 | App rows still drifted 31 Jan → 28 Feb → 28 Mar | **Fixed**: the next row keeps the day |
| 8 | P2 | "Due in 3 days" push for a bill already paid through a link | **Fixed** |
| 9a | P2 | The idempotency digest left out the requested day | **Fixed** (digest unchanged when the day equals the next date's) |
| 9b | P2 | "The 31st" with a first date of 30 Nov stored 30 | **Fixed**: the stated day wins |
| 9c | P2 | 0045's locks: `lock_timeout` was optional | **Fixed in the plan**: required (`production-readiness.md`, step 9) |
| 9d | P2 | Processor stamps `spent_at` = run time (06:00 UTC): for users west of UTC, the previous local day | **Limit**, existed before, processor only (below) |
| 9e | P2 | ChatGPT resolves a pending obligation before its ledger lock; a processor commit in that window gets a link to a processed row | **Limit**, processor only (below) |

What the review verified as correct:
* a ChatGPT row can never become processable or pushed (every writer
  enumerated);
* the backfill, including malformed JSON shapes, matched by id and user;
* 0036 → 0045 in one run on a production-shaped database (0.7 s, sums
  unchanged), with downgrade and re-upgrade;
* readiness, as owner and as a least-privilege role;
* the day arithmetic, and every database-backed caller passing the day;
* S1;
* ChatGPT's figures unchanged;
* Decimal throughout.

## Limits (known, not closed)

* **A loan, subscription or insurance paid in the app** (not linked) stays
  held on the app's forecast until it is linked in ChatGPT. This errs on
  holding: the app shows less to spend, never more. Rent, mortgage and
  utilities paid in the app are recognised.
* **The processor records at its run time** (06:00 UTC). For users west of
  UTC that is the previous local day, so a bill due on the 1st lands on the
  last day of the previous month. This existed before 0045 and matters only
  where the processor runs.
* **The ChatGPT linking race.** ChatGPT resolves the pending obligation
  before it takes the ledger lock. If the processor records that same row
  in between, the user's payment is linked to a processed row and both are
  kept. This needs the processor running and the same seconds.
* **An app row the user ever pays through a link** is no longer recorded
  automatically, by design: the links decide.
* **Rows saved in ChatGPT whose idempotency record is gone** are `unknown`,
  not `chatgpt`. They are safe (never processed, old dates). Only the
  release's staging step marks them.
* **Months laid out in ChatGPT, viewed in the app.** A bill's own line holds
  only linked payments, so a payment entered in the app stays held there
  until it is linked in ChatGPT. That errs on the cautious side.
* **Rent, mortgage and utilities** take any purchase recorded under them as
  part payment in the app (the utilities case above; R3's rule).
* **Months the app laid out before 0045** keep their processing semantics,
  minus processing itself. A row the app created before 0045 is `unknown`,
  so an environment that runs the processor no longer records those old
  rows. New app rows are recorded as before.
* **After the processor records an app row,** the calendar shows the expense
  on its date, no longer the bill.
