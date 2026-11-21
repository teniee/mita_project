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

**G0-01: the mobile forecast counted a bill paid in the app twice.** Only
partly closed: everyday spending on a bill's line is no longer held twice. A
saved bill paid in the app without a link is still held, and that is the
open owner decision below.
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
5. **The mobile forecast cannot link, so only a link pays a saved bill — on
   every line** (G0-01; `obligation_lines.paid_without_linking`, mobile route
   only). What is recorded on a bill's line beyond its linked payments is
   ordinary spending. It uses only the line's own money that is not a bill
   due this month (`need − due`), so it is never held twice and can never
   release a bill. ChatGPT's figures do not change.

   Two earlier versions credited recorded spending to the bill. Both
   released unpaid bills (independent reviews, below). So a saved bill paid
   in the app without a link now stays held: the **open owner decision**
   below.
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

The forecast holds `need − paid` per bill line (`_still_reserved`), with
`paid = linked + min(recorded − linked, need − due)`. The figures are pinned
in `app/tests/test_paid_without_linking.py`, and the reviews' cases also run
through the real routes (`app/tests/test_budget_forecast_local_day.py`).

* **Nothing tells bill money from other money.** On a line the app laid out,
  `bills_on_due_dates` never places a bill beyond its category's allocation,
  and a bill scheduled after the month was laid out is not in it at all.
* **So recorded spending is never credited to a bill.** Every rule that did
  so released unpaid bills: 150 of fuel released a 270 car loan, 150 of
  electricity a 45 internet bill, and last month's late rent this month's.

| Case | Held | Verdict |
|---|---|---|
| Rent 800 not paid / linked / part-linked 400 | 800 / 0 / 400 | correct |
| Rent 800 paid in the app, **not linked** | 800 | **open owner decision** (G0-01): errs on holding |
| Utilities 150 of other money; internet 45 saved and unpaid; 150 of electricity paid (**review 2, N2**) | 45 | correct (was 0) |
| Last month's rent paid late this month, linked to last month (**review 2, N3**) | 800 | correct (was 0) |
| Transport 150; car loan 270 saved later; 150 of fuel (**review 1, P0**) | 270 | correct (was 120) |
| 'other' laptop loan 70 and a 70 lamp | 70 | correct (was 0) |
| Transport 370 = 100 + 270 loan; 60 / 130 spent | 310 / 270 | spending uses the line's own money only |
| Same, the loan linked; then 60 of fuel | 100 / 40 | the unspent money held, never twice |
| Two loans (270 + 50) + 100; 100 spent; then the 270 linked | 320 / 50 | each held until linked |
| Month laid out in ChatGPT: another month's linked payment on this month's line (**review 1, finding 2**) | 270 | correct |
| ChatGPT-linked payments recorded in another month | 0 | never more held than ChatGPT |

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

* **`tests_mcp/test_scheduled_obligations_safety.py`** (22 tests): the real
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
* **`app/tests/test_paid_without_linking.py`** (9 tests), plus route-level
  tests through the real mobile routes:
  * the fuel / car loan, lamp / laptop loan and electricity / internet
    cases;
  * the pinned owner decision (a saved rent paid in the app stays held);
  * the create route writing `app`.
* Since the second review, also: a first date contradicting the stated day
  is refused (N5), and a row deleted mid-run is skipped while the batch goes
  on (N7).
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
    * the digest ignoring the day;
    * and, since the second review, a contradicting first date accepted,
      and a deleted row not skipped.

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

## Second independent review (fix commit `e808df4`, 2026-11-18)

The same reviewer re-ran every reproduction and tried to break the new
design (disposable databases only).

* **Fixed:** all nine first-round findings, for the cases reported.
* **Partly closed:** two were still open on rent, mortgage and utilities
  lines.
* **New:** 3 P1 and 5 P2 findings.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| N1 | P1, errs on holding | A loan, subscription or insurance saved and paid in the app is held twice, permanently for a mobile-only user | **Open owner decision** (below). Since the uniform rule it also covers rent, mortgage and utilities. |
| N2 | P1, unsafe | Rent / mortgage / utilities: any spending in the category released a saved bill there (electricity released internet: 0.00 held, 30.00 a day instead of 25.50) | **Fixed**: one rule on every line |
| N3 | P1, unsafe | Same lines: a payment linked to last month released this month's bill | **Fixed** (same) |
| N4 | P2 | The processor records an app bill; the user then also records it in ChatGPT, which links it to the next due date: two records for one payment | **Limit**, processor only (below) |
| N5 | P2 | A stated day contradicting the first date ("the 1st", next due 15 Dec) was stored as the 1st | **Fixed**: refused, ChatGPT asks |
| N6 | P2 | A retry of a pre-deploy request with a clamped day is refused, not replayed (new digest) | **Limit**: staging only (production has no MCP records) |
| N7 | P2, existed before | A due row deleted mid-run aborted the whole batch | **Fixed**: ids taken while fresh, the row skipped |
| N8 | P2 | `MonthCommitments.due` defaulted to `{}` (all of `need` read as other money) | **Fixed**: required |
| — | P2, errs on holding | A loan paid early (last month) and linked: this month's other spending on its line is not credited | **Limit** (below) |

What the review verified:
* no spending pattern releases an unpaid saved payment;
* the app never holds more than ChatGPT;
* on ChatGPT, no sequence of link, unlink, delete, partial, early or late
  payments loses a bill, with or without the processor;
* `db.refresh` and the rollback inside the loop are safe;
* the reminder phase survives a failed row;
* `lock_timeout` works through `env.py` (0044 → 0045 aborted after 2 s and
  left 0044 intact).

## Third independent review (final commit `d4f0b7c`, 2026-11-21)

* **Fixed:** N2, N3, N5, N7 and N8. The first-round fixes (fuel, lamp,
  findings 3–8) hold on the final commit.
* **No release, no over-hold.** No case made the mobile forecast release
  an unpaid saved bill or hold more than ChatGPT. That includes a randomised
  check of 52,747 saved-bill lines across 20,000 random months (legacy and
  keyed; partial, oversized and wrong-date links; any spending): none held
  less than its links leave unpaid, and none more than ChatGPT. The bound is
  `held ≥ due − linked` and `held ≤ need − linked` per line.
* **The N5 refusal never blocks a consistent input.** Tested: the 31st with
  30 Nov, 28 Feb or 29 Feb in a leap year; a first date with no stated day;
  weekly rows.

| Finding | Disposition |
|---|---|
| The owner decision below, now covering rent too | **Open owner decision** (unchanged) |
| The document suggested cancelling the scheduled expense as a workaround: that ends the whole series | **Fixed**: removed, with a warning (option 1 below) |
| A row whose re-read fails for another reason (e.g. a dropped connection) was skipped silently | **Fixed**: logged and counted as an error. It stays pending, and held. |
| A `failed` row (an error on its due date) is pending nowhere: neither recorded nor held, and no next row is created (existed before) | **Limit**, processor only (below) |
| A stated weekday contradicting a weekly first date is accepted silently (existed before) | **Limit** (below) |
| N5's message could name the clamped date | Not changed (wording) |

## Open owner decision: how may the app recognise a saved bill paid in it?

The mobile app cannot link an expense to a saved payment. So a bill
scheduled in the app and paid in the app stays held on the app's forecast: a
rent of 800 shows −17.24 a day instead of 10.34. That errs on showing less to
spend, never more, and it repeats every month for a mobile-only user.
ChatGPT is exact. Options:

1. **Accept it for this release:** the app holds the paid bill until the
   month ends. Do **not** tell users to cancel the scheduled expense after
   paying. Cancelling ends the whole series, so every later month's bill
   would stop being held, which is the unsafe direction (third review).
2. **Recognise a payment by amount:** one expense of exactly the amount still
   due, in the bill's category, within a few days of its due date. This is a
   new inference rule and needs your approval. A same-amount purchase in
   that window would be taken as the payment.
3. **Run the processor in production** (a worker for `rq_scheduler`). It
   records app bills on their dates, so users do not pay them by hand.
4. **A "paid" action in the app** that creates the link. That needs app work
   and is later.

`app/tests/test_budget_forecast_local_day.py::test_a_saved_bill_paid_in_the_app_stays_held_pending_the_owner_decision`
pins option 1 until you decide.

## Limits (known, not closed)

* **A saved bill paid in the app without a link** stays held on the app's
  forecast: the open owner decision above. This errs on holding.
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
* **A loan paid early and linked** (recorded last month): this month's other
  spending on its line is not credited, so up to that line's own money stays
  held. This errs on holding.
* **The processor records an app bill, then the user also records it in
  ChatGPT:** two records for one payment (N4). Processor only; ChatGPT may
  ask.
* **A retry across the 0045 deploy** of a request with a clamped day is
  refused instead of replayed (N6). Staging only.
* **A row the processor marks `failed`** (an error on its due date) is pending
  nowhere: it is neither recorded nor held, and no next row is created. This
  existed before, and matters only where the processor runs. Errors are
  counted and logged.
* **A weekly payment's stated weekday that contradicts its first date** is
  accepted, and the first date's weekday is used. This existed before.
* **Months the app laid out before 0045** keep their processing semantics,
  minus processing itself. A row the app created before 0045 is `unknown`,
  so an environment that runs the processor no longer records those old
  rows. New app rows are recorded as before.
* **After the processor records an app row,** the calendar shows the expense
  on its date, no longer the bill.
