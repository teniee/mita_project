# MITA in ChatGPT — data inventory

Everything the ChatGPT app stores or reads, why, and what happens on
deletion. Financial records and product analytics are separate purposes;
analytics is never a second copy of financial data. Retention periods that
need a legal decision are marked **[OWNER]**.

| Data | Where | Why MITA needs it | Source | Retention | Shown to the user | In analytics | Sensitivity | On account deletion |
|---|---|---|---|---|---|---|---|---|
| E-mail, password hash (bcrypt), name, token_version, lockout counters | `users` | sign-in, grant binding | user (sign-up / app) | life of the account | e-mail masked in `get_profile` | no | personal / credential | deleted |
| Country | `users.country` | the app's region rules | app; ChatGPT sign-up stores `ZZ` ("not stated") | life of the account | no | no | low | deleted |
| Monthly net income, currency, timezone, monthly savings target | `users` | budgeting | stated by the user | life of the account | yes (`get_setup_status`) | no | financial | deleted |
| Household size, which profile fields the user confirmed, usage-statistics choice | `mcp_user_profiles` | setup state; consent | stated by the user | life of the account | yes | no (the choice itself is not an event) | low | deleted (cascade) |
| Expenses: date, amount, currency, category, merchant | `transactions` | the ledger | user (app or ChatGPT; receipt photos are read by ChatGPT, never received by MITA) | until the user deletes them or the account (soft delete keeps the row, excluded everywhere) | yes | no | financial | per existing account-deletion behaviour |
| Budget plan per day and category | `daily_plan` | budgeting, redistribution | MITA engine from the reviewed draft | until replaced or account deletion | yes | no | financial | deleted (cascade) |
| Recurring obligations | `scheduled_expenses` | budgeting, upcoming payments | stated by the user | until cancelled or account deletion | yes | no | financial | deleted (cascade) |
| Savings goals: title, target, saved, date | `goals` | goals | stated by the user | until deleted or account deletion | yes | no | financial | deleted (cascade) |
| Idempotency records: digests of (operation, conversation, key) and of the request; ids of rows created | `mcp_idempotency_keys` | make retries safe | MITA | 30 days (purged per user on their next write) | no | no | low (no values) | deleted (cascade) |
| OAuth clients, codes, refresh tokens (SHA-256 digests only) | `mcp_oauth_*` | the ChatGPT connection | OAuth flow | codes 5 min; refresh 30 days without use; revoked on password change | no | no | credential (hashed) | deleted (cascade) |
| Feedback message, type, area, rating, triage status/theme/notes | `product_feedback` | improving MITA | the user, explicitly | **[OWNER]** (no purge today) | the user sees their own words only in ChatGPT | type, area, rating only | personal text | deleted (cascade) |
| Analytics identity link (user id → pseudonymous key) | `analytics_identities` | delete a user's analytics with them | MITA | until opt-out or account deletion | no | — | pseudonymous | deleted (cascade) |
| Usage events: tool, feature, intent, status, error class, latency, locale, conversation key, allow-listed properties | `analytics.events` | product decisions, reliability | MITA, only if consented (otherwise unlinked) | **[OWNER]** (no purge today) | no | — | pseudonymous usage | linked rows deleted (cascade); unlinked rows remain |
| Opaque references and draft tokens handed to ChatGPT | not stored | correct an expense; save a reviewed budget | MITA (AES-SIV / HMAC, user-bound) | refs stable; drafts 2 hours | in tool results | no | low | invalid without the account |
| Request logs: method, path, status, latency, request id, tool, outcome, hashed subject | stdout (Railway logs) | operations | MITA | Railway log retention **[OWNER]** | no | no | low | not linked by e-mail; subject hash only |

## Never stored

ChatGPT prompts, responses or transcripts; receipt images; raw ChatGPT
session or subject ids; precise location; bank or card data; passwords in
any log; amounts, merchants or titles in analytics or logs.

## What ChatGPT receives

Only tool results for the question asked: dates, amounts, currencies,
categories, merchants, plan figures, goal titles and amounts, scheduled
obligations, profile facts the user stated, display name and a masked e-mail.
Never notes, receipts, locations, full e-mail, internal ids (expenses are
addressed by opaque `ref`s), passwords or tokens.

## Account deletion

`DELETE /api/auth/delete-account` (app) deletes the `users` row; every table
above with a foreign key to `users` cascades, including the analytics
identity link and therefore every linked event, the feedback, the setup
state, idempotency records and OAuth grants. Unlinked analytics events
remain because they cannot be tied to anyone. Whether aggregate statistics
may be kept, and for how long linked events and feedback are retained while
the account exists, are legal decisions for the owner **[OWNER]** — no
retention rule is invented here.
