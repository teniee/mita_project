# MITA Finance — Financial Invariants (Fable 5 must preserve)

> Auditor: Claude (Opus 4.8), 2026-07-09, base `d54667a`. Values marked **[repro]** were produced by running the actual module locally (`python3`, pydantic 2.9.2). Values marked **[src]** are derived from source. Values marked **[BLOCKED]** could not be exercised because DEF-001/002 500 the endpoint.
> Money convention in the app: **transactions are stored POSITIVE** (`amount >= 0.01`); `balance = income − Σ(positive spend)`. Any code assuming negative expenses is a bug (see V4).

---

## 1. Budget generation — `app/services/core/engine/budget_logic.py :: generate_budget_from_answers`

**INV-1 (income):** `total_income = monthly_income + additional_income`.
**INV-2 (fixed):** `fixed_expenses_total = Σ fixed_expenses.values()`.
**INV-3 (deficit guard):** if `fixed_total > income` → raises `ValueError("Fixed expenses exceed income")` → API **HTTP 400**.
**INV-4 (negative income):** negative income → `ValueError("Income cannot be negative")` (raised via `classify_income`) → HTTP 400.
**INV-5 (discretionary & savings clamp):**
```
discretionary = income − fixed_total − savings_goal
if discretionary < 0:
    savings_goal = max(0, savings_goal + discretionary)   # savings clamped DOWN
    discretionary = 0
```
**INV-6 (reconciliation, REQUIRED):** `total_income == fixed_expenses_total + savings_goal + discretionary_total` — must hold **to the cent** for any valid 2-dp inputs. **Currently violated for sub-cent inputs** (see V2).
**INV-7 (allocation):** category breakdown is tier-weighted; only **down-scaled** if `Σ base_allocations > discretionary` (`scale_factor = discretionary / total_allocated`); never up-scaled. Zero/negative allocations dropped.

### Deterministic examples (exact) — **[repro]**
| Case | Inputs | total_income | fixed | savings | discretionary | Result |
|---|---|---|---|---|---|---|
| B1 normal | income 6000, fixed {rent1500,util200}, savings 400 | 6000 | 1700 | 400 | **3900** | ✅ |
| B8 income==fixed | income 2000, fixed {rent2000}, savings 400 | 2000 | 2000 | **0** (clamped) | **0** | ✅ |
| B9 fixed>income | income 2000, fixed {rent2500} | — | — | — | — | ✅ `ValueError`→400 |
| B10 neg-after-savings | income 3000, fixed 2800, savings 500 | 3000 | 2800 | **200** (clamped) | **0** | ✅ |
| Zero income | 0 / 0 / 0 | 0 | 0 | 0 | 0 | ✅ |
| Negative income | −1000 | — | — | — | — | ✅ `ValueError`→400 |
| 0.1 + 0.2 | mi 0.1, ai 0.2 | **0.3** (masked; internal `0.30000000000000004`) | 0 | 0 | 0.3 | ⚠️ V2 |
| 100.005 | mi 100.005 | **100.0** (banker's round + float repr; half-cent lost) | 0 | 0 | 100.0 | ⚠️ V2 |

---

## 2. Dashboard — `app/api/dashboard/routes.py`

**INV-8 (balance):** `current_balance = monthly_income − Σ(Transaction.amount WHERE user_id=U AND spent_at∈[month_start, now))`.
**INV-9 (today spent):** `today_spent = Σ(Transaction.amount WHERE user_id=U AND spent_at∈[today_start, now))`.
**INV-10 (soft-delete, REQUIRED):** all aggregations MUST exclude `deleted_at IS NOT NULL`. **Currently violated** (see V1).

### Deterministic examples — **[repro from prior audit, still valid]**
| Case | Expected |
|---|---|
| Post-onboarding, no spend (B1 inputs) | balance **6000**, today_spent **0** |
| +42.00 today | balance **5958**, today_spent **42**, calendar today.spent **42** |
| Edit 42→100 | balance **5900**, spent **100**, calendar **100** — **[BLOCKED by DEF-002/001]** |
| Delete the txn | balance **6000**, spent **0**, calendar **0** — **[BLOCKED by DEF-001]**; and even once unblocked, **wrong** until V1 is fixed |

---

## 3. Transaction lifecycle — `app/api/transactions/{services.py,schemas.py}`, `app/db/models/transaction.py`

**INV-11 (amount domain):** `0.01 ≤ amount ≤ 1_000_000`; stored `Numeric(12,2)` (Decimal). Values `≤ 0` rejected (`services.py:118-120`). `> 2dp` — verify quantization (matrix B18 unverified).
**INV-12 (create delta):** create adds `amount` to (day, category) planned/actual accrual.
**INV-13 (edit delta):** edit applies `(new − old)`; category change moves the delta between categories; date change across months moves it between months. **[BLOCKED — must be tested after DEF-001/002 fix]**.
**INV-14 (delete reversal):** delete soft-deletes (`deleted_at = now`) and reverses the accrual; the txn disappears from list AND from all balance/spend aggregations (requires V1 fix).
**INV-15 (temporal column):** the only temporal column is **`spent_at`** — there is **no `date` and no `timestamp` column** on `Transaction`. Code writing `Transaction(date=…)` (OCR path, `expense_tracker.py:24`) or querying `Transaction.timestamp` (analytics) is a **bug** (see V5).

---

## 4. Daily plan — `app/db/models/daily_plan.py`, `calendar_service_real.py`

**INV-16 (uniqueness, REQUIRED):** **at most one `daily_plan` row per (user_id, calendar-day, category).** Currently **not enforced** (no DB unique + append-only save + no onboarding idempotency guard) → duplicate rows; spend accrual via `.first()` updates only one → per-category `remaining` diverges (see V3).
**INV-17 (monthly = Σ daily):** monthly planned total = Σ(daily planned across the month); monthly actual = Σ(daily actual). Verify holds after any redistribution.
**INV-18 (category conservation under redistribution):** redistributing budget between days/categories MUST conserve the month's total planned amount (no money created/destroyed). **[not verified this pass — add a conservation property test]**.

---

## 5. Goals / savings — `app/services/goal_budget_integration.py`

**INV-19 (available for goals):** `available_for_goals = monthly_income − Σ(monthly expenses)`. Currently computed with `Σ(amount WHERE amount < 0)` = always 0 → `available = full income` (see V4). Also the whole `/goals/budget/*` surface 500s (async/sync).
**INV-20 (goal progress):** `progress_pct = min(saved/goal*100, 100)`, `remaining = max(goal − saved, 0)` (`app/api/goal/services.py:35`). Pure, correct; but `/goal/user-progress` reads a body-supplied `user_id` (authenticated IDOR, `adversarial-audit.md` N-P2-IDOR-1).

---

## Invariant VIOLATIONS found (ordered by impact)

| ID | Invariant | Violation | Severity | Fix |
|---|---|---|---|---|
| **V1** | INV-10 | Dashboard/quick-stats aggregations omit `deleted_at IS NULL` → balance/spend include soft-deleted txns; balance permanently wrong after a delete. | **P1** | Add `Transaction.deleted_at.is_(None)` to the 6 queries in `dashboard/routes.py`. Ship with DEF-001 delete fix. |
| **V2** | INV-6 | Budget math in binary float + banker's rounding; `income ≠ fixed+savings+discretionary` to the cent for sub-cent inputs; `.xx5` rounds half-to-even not half-up. | **P2** | Decimal + `quantize(Decimal('0.01'), ROUND_HALF_UP)` throughout `budget_logic.py`. |
| **V3** | INV-16 | No `UNIQUE(user_id, day, category)` on `daily_plan` + append-only save + no onboarding idempotency → duplicate plan rows; `.first()` accrual splits spend. | **P1** | Composite unique + delete-first/upsert + `has_onboarded` guard on `/onboarding/submit`. |
| **V4** | INV-19 | `_get_monthly_expenses` filters `amount < 0` while expenses are positive → `available_for_goals` = full income (over-allocation never detected). | **P2** | Use `amount > 0` (or the app's positive convention). |
| **V5** | INV-15 | `Transaction(date=…)` (OCR `record_expense`, `expense_tracker.py:24`, also duplicate at `core/engine/expense_tracker.py`) → `TypeError`; `Transaction.timestamp` (analytics) → column doesn't exist. Also `Decimal(amount)` on a `float` re-introduces binary error. | **P2** (deferred OCR/analytics paths) | Use `spent_at=<datetime>`; use `Decimal(str(amount))`. |
| **V6** | money type | `Expense.amount` is `Float` in the ORM though DB is `Numeric(12,2)`; `users.monthly_income`/`savings_goal` unbounded `Numeric`. | **P2** | Model = `Numeric(12,2)` everywhere; migration to bound the two user columns. |

## Global money rule for Fable
> **No binary `float` for money.** Use `Decimal` end-to-end; store `Numeric(12,2)`; quantize with `ROUND_HALF_UP`. Today `transactions.amount`, `daily_plan.*`, `goals.*`, `installments.*` are correct `Numeric`; the offenders are `budget_logic.py` (float), `Expense.amount` (Float), `users.monthly_income/savings_goal` (unbounded Numeric), and the several `float(...)` display coercions in `goal_budget_integration.py`, `savings_surplus_service.py`, `calendar_service_real.py`, `analytics_service.py` — the display coercions are lower risk but should read/round from Decimal.
