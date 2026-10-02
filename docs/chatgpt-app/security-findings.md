# Secrets and security findings (ChatGPT app audit)

Scope: current tree and full git history of `teniee/mita_project`
(1,371 commits, all refs) on 2026-10-02. Scanner: `gitleaks git --redact`
(174 raw findings), then manual triage. **No secret value is reproduced
here.** Fingerprints are the first 12 hex characters of SHA-256 of the
value, so the owner can match them against the current value without either
side disclosing it:

```bash
printf '%s' "$VALUE" | shasum -a 256 | cut -c1-12
```

The repository is **public** (`gh repo view` → `"visibility":"PUBLIC"`), so
anything in history must be treated as disclosed.

## Confirmed

| # | What | Where (first commit) | Fingerprint | Evidence it is still in use | Required action |
|---|---|---|---|---|---|
| S-1 | Supabase **secret key** (`sb_secret_…`) for project `atdcxppfflmiwjwjuqyl` | `.mcp.json` @ `f83ad16` (2025-12-16), still in `3f0bb68`; untracked in `95193a3` (DEF-003) | `825ad855969b` | The untracked local `.mcp.json` today holds a value with the **same fingerprint** → not rotated as of this audit | Rotate in Supabase (OWNER_ACTIONS O-1) |
| S-2 | Upstash Redis password (`integral-jaybird-23463.upstash.io`) | same file/commits | `9b824f818673` | Same fingerprint in the local `.mcp.json` today → not rotated | Rotate in Upstash; update every Railway variable that embeds it (O-2) |
| S-3 | OpenAI project key (`sk-proj…`, 164 chars) | `agent_finance_advisor.py` @ `2f2c1f11` (2025-06-11) | `86d0921d9661` | Not checked (validating it would mean using it) | Revoke in OpenAI dashboard if it still exists (O-3) |
| S-4 | `.env.production` committed with `JWT_SECRET` (`7d2122790a81`), `JWT_PREVIOUS_SECRET` (`4533279340f8`), `SECRET_KEY` (`9663211c9f9f`), `REDIS_PASSWORD` (`bca91625a628`), `REDIS_URL` (`cb2190673a19`), `DATABASE_URL` (`1b5a12cfe5c9`), `OPENAI_API_KEY` (`4c84d7d9e712`) | `0881bf7e` (2025-09-06), also `.env.production.test` | as listed | Not checked — comparing against production variables was blocked by this session's permission policy | Owner compares fingerprints; rotate any match (O-4). A matching `JWT_SECRET` means anyone can mint MITA access tokens for any user. |

Notes:

* `jwt` findings in `mobile_app/integration_test/inject_tokens_test.dart`,
  `mobile_app/test/**`, `tests/integration/test_auth_integration.py` are test
  fixtures; whether they were signed with a production secret depends on S-4.
* `gcp-api-key` findings are Firebase client keys in `firebase_options.dart`
  / `google-services.json`. They are public by design; they must be
  restricted by app/bundle id (`FIREBASE_API_KEY_RESTRICTIONS.md` already
  describes this; not verified in Google Cloud).
* History purge (BFG / `git filter-repo`) does not un-disclose a value in a
  public repo; rotation is the fix. Purging is optional hygiene.
* `.mcp.json.example` is a developer-tooling template (Flutter/Supabase/Redis
  MCP clients for the IDE). It is **not** the production ChatGPT MCP server
  and is unrelated to `app/mcp/`.

## Design-level findings relevant to the MCP service

* The MITA access token carries `write:transactions` / `write:budget` for
  every basic user. The MCP service never accepts a MITA token; its own
  tokens carry only `profile:read` / `finance:read`.
* `verify_token` fails **open** on Redis blacklist and DB token-version
  errors. The MCP verifier checks `users.token_version` on every tool call
  through the same read-only session and fails **closed**.

## What the MCP service adds to the secret inventory

| Variable | Purpose | Rotation impact |
|---|---|---|
| `MCP_OAUTH_PRIVATE_KEY` | RS256 signing key for MCP access tokens | Rotating invalidates outstanding access tokens (≤15 min); refresh tokens keep working |
| `MCP_OAUTH_PREVIOUS_PUBLIC_KEY` | optional, verify-only during rotation | |
| `MCP_LOGIN_CSRF_SECRET` | HMAC for the login form CSRF token | rotating invalidates open login pages only |
| `OPENAI_APPS_CHALLENGE_TOKEN` | domain verification token (not secret) | |

None of these are committed; `scripts/mcp/generate_keys.py` prints a key for
the owner to paste into Railway.
