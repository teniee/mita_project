# MITA in ChatGPT — data inventory

Everything the ChatGPT app stores or reads, why, and what happens on
deletion. Financial records and product analytics are separate purposes;
analytics is never a second copy of financial data. Retention periods that
need a legal decision are marked **[OWNER]**.

| Data | Where | Why MITA needs it | Source | Retention | Shown to the user | In analytics | Sensitivity | On account deletion |
|---|---|---|---|---|---|---|---|---|
| E-mail, password hash (bcrypt), name, token_version, lockout counters | `users` | sign-in, grant binding | user (sign-up / app) | life of the account | e-mail masked in `get_profile` | no | personal / credential | deleted |
| Country | `users.country` | the app's region rules; since 2.8 the country the user confirmed in ChatGPT (where they usually live and spend money) | app; ChatGPT sign-up stores `ZZ` ("not stated"); in ChatGPT only the user's answer — ChatGPT's approximate location is offered as a question, never stored | life of the account; "prefer not to say" resets it to `ZZ` | yes (`get_setup_status.region`) | no | low | deleted |
| Country confirmation and source (`stated` / `chatgpt_location_confirmed`), regional-statistics switch, income regularity, pay frequency and days, minimum monthly income (variable income) | `mcp_user_profiles` (0043) | personalized budgets: what applies to the user, a month at their minimum | stated by the user | life of the account | yes | field names only (`financial_profile_updated.fields`) | financial (income figures), else low | deleted (cascade) |
| Setup answers: "no regular payments", "that is what I spend on", "skip" per topic | `mcp_setup_answers` (0043) | never re-ask; budget only confirmed lines | stated by the user | life of the account | yes (`onboarding.topics`) | field name only | low | deleted (cascade) |
| Official statistics (inflation, price levels, household spending shares; since 2.9 household spending per adult equivalent, annual price indices and the share of households buying fuel — inputs of the spending references) per country, with provenance; ingestion run records | `regional_observations`, `regional_ingestion_runs` (0044) | regional context for budgets | Eurostat, World Bank, OECD (scheduled batch, never per user) | kept as reference data; a value is never deleted, only revised or marked stale | yes (`get_regional_context`, the user's confirmed country only) | no | none — no user column; nothing about a user is sent to a provider | unaffected (not personal data) |
| Monthly net income, currency, timezone, monthly savings target | `users` | budgeting | stated by the user | life of the account | yes (`get_setup_status`) | no | financial | deleted |
| Household size, which profile fields the user confirmed, usage-statistics choice | `mcp_user_profiles` | setup state; consent; since 2.9 the household range of a national spending reference (computed per call, never stored) | stated by the user | life of the account | yes | no (the choice itself is not an event) | low | deleted (cascade) |
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
any log; amounts, merchants or titles in analytics or logs. ChatGPT's
approximate location (`_meta["openai/userLocation"]`: city, region,
country, timezone, coordinates) is never stored or logged: only its country
code is read, for the current call, to suggest a question; a city, address or
coordinates are never asked for and never stored.

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
