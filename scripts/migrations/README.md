# TASK-7/8/9 database migrations — preflight package (NOT on `main`)

These migrations (`0036`, `0037`, `0038`) live on the branch
`migrations/task-7-8-9-preflight` and are **deliberately kept off `main`**.
Railway auto-runs `alembic upgrade head` on every deploy
(`scripts/deployment/start.sh`), so merging these to `main` would apply them
to production **without a maintenance window**. They must be applied by the
owner, in a window, after running the preflight below. See
`docs/owner-actions.md §7`.

## What each migration does

| Rev | Task | Change | Production data impact |
|-----|------|--------|------------------------|
| `0036` | TASK-7 | FK + `ON DELETE CASCADE` on `user_id` for `moods`, `budget_advice`, `notification_logs`, `push_tokens`, `ignored_alerts` | **DELETES orphaned rows** (rows whose `user_id` has no live `users.id`) before adding each FK. |
| `0037` | TASK-8 | `users.monthly_income`, `users.savings_goal` and `expenses.amount` → `Numeric(12,2)` | **ROUNDS** any value with >2 decimal places to the cent (`expenses.amount` was `double precision`, the only real risk). No deletes. |
| `0038` | TASK-9 | partial `UNIQUE(platform, original_transaction_id) WHERE original_transaction_id IS NOT NULL` on `subscriptions` | **No row changes.** FAILS (raises, does not delete) if duplicate store-identity pairs already exist. |

## Critical behaviour verified on real PostgreSQL 15 (2026-07-11)

- **Empty-DB `alembic upgrade head` → `0038`, 34 tables.** ✅
- **`upgrade head` runs in ONE transaction (alembic default).** If `0038`
  aborts on a subscription duplicate, `0036` and `0037` **also roll back** —
  the DB stays at `0035`. So a production apply is **all-or-nothing**: with
  any subscription duplicate present, nothing is applied until it is
  reconciled. Confirmed: seeded a duplicate → `upgrade head` left head at
  `0035` with orphans/rounding untouched.
- **Orphan cleanup + FK CASCADE (TASK-7).** Seeded 1 orphan + 1 live row in
  `moods`/`push_tokens`; after upgrade only the live row remained, and
  deleting the live user cascaded its children to 0. ✅
- **Rounding (TASK-8).** Seeded `expenses.amount = 12.345`; after upgrade it
  was `12.35` in a `Numeric(12,2)` column. ✅
- **Idempotency guard (TASK-9).** With a duplicate present, `0038` raised
  the reconcile message and touched no subscription rows. After deleting one
  duplicate by id, `upgrade head` reached `0038` and created the unique
  index. ✅
- **Full downgrade `0038 → 0035`** drops the FKs, the unique index, and
  returns the columns to unbounded numeric / double precision. ✅ (Rounding
  and orphan deletion are NOT reversible — documented in each migration.)

## Owner runbook (maintenance window)

```bash
# 1. PREFLIGHT (read-only) — against production or a read replica.
psql "$DATABASE_URL" -f scripts/migrations/task_7_8_9_preflight.sql
#    - TASK-7 orphan counts  = rows 0036 will DELETE
#    - TASK-8 rounding counts = rows 0037 will ROUND
#    - TASK-9 duplicate list  = MUST be reconciled by hand first (0038 will
#      not delete subscription/money rows and will abort the whole chain)

# 2. Reconcile any TASK-9 duplicates by hand (keep the correct subscription).

# 3. Merge migrations/task-7-8-9-preflight into main during the window, or
#    apply directly:
DATABASE_URL=... alembic upgrade head        # 0035 -> 0038
#    Rollback if needed:
DATABASE_URL=... alembic downgrade 0035

# 4. Verify: alembic current == 0038; re-run scripts/remote_smoke_test.py.
```

The model classes (`app/db/models/{mood,budget_advice,notification_log,push_token,ignored_alert,user,expense}.py`)
were updated to match the post-migration schema (FK relationships +
`Numeric(12,2)`), so the ORM and DB agree once the window runs. Those model
edits are on this branch too — they must land **with** the migrations, not
before.
