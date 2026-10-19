# Handoff — MITA in ChatGPT (MCP), 2026-10-19

**Staging acceptance: CLOSED** (`staging-acceptance-v2.md` §11). The next
phase has not been started.

| Item | State |
|---|---|
| Staging code | `79efb1d612999339814b02b5220b7cde2a13921d`, MCP 2.1.0 |
| Staging deployment | `87d26668-4051-42c3-99b7-2036d0de42cf` (project `mita-mcp-staging`), `/health` ok, alembic 0039, role `mita_mcp`, 1 replica, database TCP proxy closed |
| Evidence | CI run `39155447750` green; public staging checks §9; real ChatGPT §8 and S-8 §11 |
| Branch | `feat/chatgpt-plugin`; commits after `79efb1d` are documentation only, so staging needs no redeploy |
| `main` | `27ed25d`, not merged |
| Production | untouched: API on `3aa52b7` at alembic 0036, no MCP service, no setting, variable or secret changed |

## PR #287 must not be merged yet

PR #287 (`feat/chatgpt-plugin` → `main`) is open, not a draft and mergeable,
and `main` has no branch protection. `mita-production` follows `main` with no
commit pin, path filter, CI gate or healthcheck, and its `start.sh` runs
`alembic upgrade head` on boot (aborting in production on failure). A merge
therefore deploys the API and applies 0037–0039 to the production database;
a failed boot leaves nothing serving, and a rollback cannot boot against the
migrated database. Merge only as `production-readiness.md` Step 7 — after
Step 1 (credential rotation) and with the healthcheck (O-11a) and pre-flight
(O-11b) done.

## Known limitations (not blockers)

* A repeated, deliberate receipt request is caught by ChatGPT's judgement;
  MITA's idempotency covers retried tool calls, not content duplicates.
* F-2: shown as one line in ChatGPT, but the ledger still books `gas` apart
  from the `transport gas` plan (backend debt).
* F-7: a future scope addition needs existing ChatGPT connections to
  re-register.
* The description on ChatGPT's own developer-mode app object is owner-managed.

## Next phase (not started)

MITA-branded login/sign-up/OAuth presentation and launch preparation, in a
fresh session. Owner steps: `OWNER_ACTIONS.md`; order: `production-readiness.md`.
