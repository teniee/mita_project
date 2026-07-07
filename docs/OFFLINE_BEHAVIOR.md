# MITA Mobile — Offline Behavior: Honest Status & Implementation Estimate

> **Decision required from the product owner before closed beta:** ship online-first
> (current, verified behavior) or build true offline write-queueing first.
> **Do not** describe MITA as "offline-first" in store listings or beta notes until the
> write queue below exists.

## What actually works today (verified in code, session 4–5)

| Scenario | Behavior | Verdict |
|----------|----------|---------|
| Read calendar while offline | Served from the sqflite response cache (2h expiry) via `api_service.dart`; if cache is cold, the deterministic `CalendarFallbackService` renders a locally computed budget | ✅ works |
| Create a transaction while offline | POST fails → error is **rethrown and surfaced to the user** (both `ApiService.createTransaction` and `TransactionService`) | ✅ fails **visibly** |
| Silent data loss | None. Nothing pretends to succeed; nothing is dropped without the user seeing an error | ✅ none |
| Queue the failed write for later sync | **Not implemented.** `AdvancedOfflineService` contains a full offline machine (sqflite cache, `pending_sync` queue table with retry counts, connectivity-triggered `_processPendingSyncs`) — but **no production code path ever enqueues a write** | ❌ absent |
| Retry after reconnect | Nothing to retry — the queue is never populated | ❌ absent |

**Summary:** MITA is an *online-first app with cached reads*. That is a defensible closed-beta
posture (beta testers have connectivity, and failure is loud, not lossy), but it is not
offline-first.

## What building true offline writes requires

The scaffolding (`AdvancedOfflineService`) exists but is unwired and unproven under real
concurrency. The work, in dependency order:

| # | Work item | Scope | Estimate |
|---|-----------|-------|----------|
| 1 | **Server idempotency keys** — accept a client-generated `Idempotency-Key` (UUID) on `POST /api/transactions`, persist key→response for ≥24h (new table or Redis), return the stored response on replay. Backend + migration + tests. | backend | 2–3 days |
| 2 | **Persistent client write queue** — on network failure, enqueue `{idempotency_key, endpoint, payload, created_at, retry_count}` into the existing sqflite `pending_sync` table; wire `createTransaction` (both services) through it. Queue must survive app restart (sqflite already does). | mobile | 2–3 days |
| 3 | **Replay engine** — connectivity-triggered drain (`_processPendingSyncs` exists as a skeleton): FIFO per-endpoint, exponential backoff, retry cap, dead-letter state surfaced in UI. | mobile | 2 days |
| 4 | **Duplicate prevention** — the idempotency key is the mechanism (client generates it *once*, before first attempt, stores it with the queued write); UI must also disable double-submit while a write is queued. | both | folded into 1–3 |
| 5 | **Conflict handling** — policy decision + implementation: a queued transaction replayed hours later changes historical daily budgets → server must recompute redistribution on insert (it already recomputes on write), and the client must invalidate cached calendar after replay. Edge cases: month rollover, deleted category, changed budget. | both | 2–3 days |
| 6 | **Sync-state UX** — pending badge on unsynced transactions, "will sync when online" messaging, manual retry, failure surfacing. | mobile | 1–2 days |
| 7 | **Tests** — backend idempotency suite; mobile queue unit tests; E2E: create offline → restart app → reconnect → verify exactly-once server insert and calendar update. | both | 2–3 days |

**Total: roughly 2 weeks of focused work (11–16 engineer-days)**, spanning backend and mobile,
plus a product decision on conflict policy (#5) that cannot be made unilaterally.

## Recommendation

Ship closed beta **online-first** with the current loud-failure behavior, state it plainly in
beta notes ("MITA currently requires an internet connection to record spending"), and schedule
the write queue based on beta feedback. Rationale: failure today is visible and lossless; the
queue touches money-affecting redistribution logic and deserves unhurried design (especially
item 5), not a beta-gate rush.

**Awaiting owner confirmation.** No offline-write implementation will begin until the owner
decides it is required for closed beta.
