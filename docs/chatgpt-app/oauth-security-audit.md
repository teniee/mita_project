# OAuth 2.1 / MCP authorization — adversarial security audit

Scope: the built-in authorization server and resource server of the MITA MCP
service on `feat/chatgpt-plugin` — `app/mcp/auth/{provider,login,tokens,keys,
redirects,fingerprint,scopes}.py`, `app/mcp/{runtime,server,ratelimit,db,
config}.py`, `app/services/credential_verification.py`, `app/db/models/mcp_oauth.py`,
migration `0037`, and the MCP SDK 2.2.0 handlers they rely on
(`mcp/server/auth/handlers/{authorize,token,register,revoke,metadata}.py`,
`middleware/{bearer_auth,client_auth,auth_context}.py`).

Method: line-by-line review, then an attack suite
(`tests_mcp/test_oauth_adversarial.py`) written against the code as it was.
**30 of 88 attack cases succeeded** against commit `85cdc55` (one case was later moved to the API suite as `app/tests/test_mcp_token_boundary.py`, leaving 87); all six
resulting weaknesses were fixed in `e5d0228` with the failing tests as
regressions. "Blocked" below always cites a test; nothing is listed as safe
on reading alone.

## Confirmed vulnerabilities (fixed)

| ID | Sev | Threat | Behavior before | Reproduction | Fix (`e5d0228`) |
|---|---|---|---|---|---|
| V3 | **High** | Keep ChatGPT access after a password change | Grants bound only to `users.token_version`. `/reset-password` commits the new password, then bumps `token_version` inside a `try/except` that logs and continues (fail-open). Any path that changes the password without a successful bump left access + refresh tokens valid (refresh: 30 days). | `test_any_password_change_ends_chatgpt_access`: change `password_hash` only → tool call and refresh both succeeded | Every code, refresh token and access token carries `cfp` = HMAC-SHA256(key derived from `MCP_LOGIN_CSRF_SECRET`, `password_hash`). Token endpoint and every tool call compare with the current hash and fail closed. Mobile auth code untouched. |
| V1 | Med | Redirect to an attacker-chosen location | DCR allow-list used `str.startswith` on `https://chatgpt.com/connector/oauth/` and `…/connector_platform_oauth_redirect`: accepted extra segments, `%2e%2e%2f`, `?next=…`, `#…`, `…redirectX`, trailing `/`. Exploitation needs an open redirect on chatgpt.com, so impact is bounded, but the policy was not exact. | 9 cases of `test_registration_rejects_malicious_redirect` | `app/mcp/auth/redirects.py`: exact match, or one `[A-Za-z0-9_-]{1,128}` callback segment; no userinfo, port, query, fragment, `%`, `\`, dot or empty segments. Authorization requests are then matched exactly against the registered URI by the SDK. |
| V2 | Med | Abuse of open DCR | Unauthenticated `/register` accepted any extra grant type (`password`, `client_credentials`, `implicit`, device code), `response_types` with `token`, client `jwks`/`jwks_uri`, multi-KB metadata (SDK body limit 4 MiB), with no rate limit → unbounded rows in `mcp_oauth_clients`. Extra grants were inert at `/token`, but stored. | 9 cases of `test_registration_rejects_unneeded_or_dangerous_metadata`, `test_registration_is_rate_limited` | Only `authorization_code` + `refresh_token`, `response_types == ["code"]`, auth method `none`/`client_secret_post`/`client_secret_basic`, no jwks, ≤ 4 KiB serialized; per-IP limit (default 30/min) on `/register`, `/token`, `/authorize`, `/revoke` (`OAuthEndpointRateLimit`). |
| V4 | Med | Account enumeration on the consent page | Unknown e-mail returned without a bcrypt check (≈0.3 s faster); a locked account (only possible for real accounts) showed a distinct "temporarily locked" message. | `test_unknown_email_costs_a_password_check`, `test_lockout_does_not_reveal_that_an_account_exists` | Unknown and locked paths each spend one bcrypt verification against a random hash; one generic message for every failure. |
| V5 | Low | Weak PKCE challenge | Any string accepted as `code_challenge` (e.g. `"a"`). Not exploitable by itself (the verifier must still hash to it) but violates S256 form. | 5 cases of `test_malformed_code_challenge_is_refused` | Must be 43 base64url characters. |
| V6 | Low | Resource confusion at `/token` | A token request naming another `resource` was answered with a token for this resource (correctly bound, so no confusion, but RFC 8707 says refuse). Same on refresh. | `test_token_request_for_another_resource_is_refused`, `test_refreshed_access_token_keeps_resource_binding` | `/token` wrapper returns `invalid_target` for any other `resource`. |

Also corrected: documentation claimed MITA's "sign out of all devices" ends
ChatGPT access. **MITA has no user-facing logout-all endpoint**; `/logout`
blacklists only that mobile session's tokens and does not touch ChatGPT grants.
Claims removed from the plugin listing, ADR and legal draft.

## Security properties — evidence table

`Exploitable?` refers to the current code (`e5d0228` and later).

### Redirect URIs
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Unregistered / different-path / scheme / host / port / query / fragment redirect at `/authorize` | SDK `validate_redirect_uri` exact membership → 400, no redirect | `test_authorize_requires_the_exact_registered_redirect` (6) | No | — |
| Registering a malicious redirect (26 variants: scheme, host, look-alike host, port, userinfo, sub-domain, extra/encoded/dot path, case, query, fragment, localhost, `javascript:`, custom scheme) | refused 400 | `test_registration_rejects_malicious_redirect` (26) | No | V1 |
| Open-redirect chaining through MITA | the only redirects MITA issues go to the signed, allow-listed `redirect_uri` | `test_tampered_pending_request_is_refused`, `test_deny_returns_access_denied` | No | — |

### PKCE
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Authorization without PKCE | SDK requires `code_challenge`; no consent page reached | `test_pkce_is_mandatory` | No | — |
| `plain` method | SDK accepts only `S256` | `test_plain_pkce_method_is_refused` | No | — |
| Malformed challenge | refused | `test_malformed_code_challenge_is_refused` (5) | No | V5 |
| Missing / wrong / other-flow verifier | 400 `invalid_request` / `invalid_grant`; right verifier still works afterwards | `test_token_without_verifier_is_refused`, `test_wrong_pkce_verifier_is_refused`, `test_verifier_from_another_flow_is_refused` | No | — |

### Authorization codes
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Replay | atomic `DELETE … RETURNING`; second exchange `invalid_grant`; the delete commits even when the exchange is refused | `test_code_is_single_use`, e2e "code replay refused" | No | — |
| Expiry | 300 s TTL checked by SDK | `test_code_expires` | No | — |
| Other client | SDK compares `client_id` | `test_code_is_bound_to_its_client` | No | — |
| Other redirect URI | SDK compares | `test_code_is_bound_to_its_redirect_uri` | No | — |
| Other resource | code stores resource; `/token` refuses foreign `resource` | `test_token_request_for_another_resource_is_refused`, `test_foreign_resource_is_refused` | No | V6 |
| A's code → B's access | `sub` taken from the code row | `test_code_of_user_a_yields_only_user_a` | No | — |
| Raw code at rest / in logs | SHA-256 digest only; never logged | `test_secrets_are_stored_hashed`, `test_oauth_flow_logs_no_secrets`, e2e + container log scans | No | — |
| Code issued before revocation | exchange re-checks `token_version` and `cfp` | `test_code_issued_before_logout_all_cannot_be_exchanged` | No | V3 |

### State / CSRF / sessions
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Consent CSRF (cross-site POST) | `__Host-` cookie, `SameSite=Strict`, `HttpOnly`, `Secure`; form token = HMAC(cookie, pending request) | `test_post_without_csrf_cookie_is_refused`, `test_csrf_token_from_another_browser_is_refused` | No | — |
| Login CSRF (attacker credentials in victim browser) | needs the victim's own cookie + matching token → refused as above | same | No | — |
| GET completing consent | only POST issues codes | `test_get_cannot_complete_consent` | No | — |
| Session fixation / stale session | there is no server session: every consent requires the password; pending requests are signed and expire in 10 min | `test_expired_pending_request_is_refused` | No | — |
| State substitution | `state` is inside the HMAC-signed pending request | `test_state_cannot_be_substituted` | No | — |
| Authorization-request forgery (attacker sends victim the authorize link of the attacker's own ChatGPT connection) | MITA cannot tell who started the flow. Defense in MITA: consent page warning ("If someone sent you this link, press Cancel"). **Binding the callback `state` to the browser session that started it is ChatGPT's responsibility.** | `test_consent_page_is_hardened` (warning) | Depends on ChatGPT — see assumptions | — |

### Access tokens (resource server)
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Expired / wrong iss / wrong aud / foreign key / HS256 confusion / `alg:none` / no exp / no aud / unknown or missing kid / `typ` other than `at+jwt` / nbf or iat in future / garbage / empty | 401 + `WWW-Authenticate` | `test_auth.py` (16 total), `test_access_token_attacks_fail_closed` (11 attacks) | No | — |
| Modified claims (e.g. `sub` swapped) | signature fails → 401 | `test_forged_subject_without_signature_is_rejected` | No | — |
| Missing / non-UUID subject | 401 | `test_token_without_user_subject_is_401` | No | — |
| Unknown subject / deleted user | tool returns `auth` error, no data | `test_unknown_subject_is_auth_error`, `test_deleted_account_is_auth_error_not_empty_data` | No | — |
| Refresh token or code used as bearer | 401 | `test_refresh_token_and_code_are_not_access_tokens` | No | — |
| Mobile MITA JWT at MCP | 401 | `test_mita_mobile_app_token_is_401` | No | — |
| MCP token at the mobile API | `verify_token` returns None (RS256, MCP iss/aud), also when HS256-signed with the API secret | `app/tests/test_mcp_token_boundary.py` (2) | No | — |
| Token of another OAuth client | accepted: the resource server authorizes the **user** and **scopes**, not the client (all clients are ChatGPT connectors for the same user) | by design | Accepted | — |
| Locked account | lockout is anti-brute-force on sign-in, not a disable switch; existing grants continue. MITA has no disabled-account flag. | by design | Accepted | — |

### Scopes
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Register unsupported scope | 400 | `test_registration_rejects_unsupported_scopes` | No | — |
| Authorize unregistered scope | `invalid_scope` | `test_authorize_with_unregistered_scope_is_refused` | No | — |
| Widen on refresh / widen after narrowing | `invalid_scope` | `test_refresh_cannot_widen_scope`, `test_narrowed_refresh_stays_narrow` | No | — |
| Extra scope strings in a token | ignored (only `profile:read`, `finance:read` honored) | `test_unknown_scopes_in_token_are_ignored` | No | — |
| Profile-only token on finance tools | `forbidden` + `insufficient_scope` hint | `test_missing_scope_is_forbidden_with_reauth_hint` | No | — |

### Refresh tokens
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Storage | SHA-256 digest | `test_secrets_are_stored_hashed` | No | — |
| Rotation / reuse | rotated on use; presenting a rotated token revokes the family | `test_refresh_rotation_and_reuse_detection`, e2e after restart | No | — |
| Concurrent refresh | conditional `UPDATE … WHERE rotated_at IS NULL RETURNING`; at most one wins; the loser revokes the family (deliberate: a raced stolen token never survives; a client that double-submits must reconnect) | `test_concurrent_refresh_yields_at_most_one_grant` (real pooled connections) | No | — |
| Expired | `invalid_grant` | `test_expired_refresh_token_is_refused` | No | — |
| Other client | `invalid_grant`; rightful client unaffected | `test_refresh_token_of_another_client_is_refused` | No | — |
| Other user | `sub` comes from the stored row; no user parameter exists | `test_code_of_user_a_yields_only_user_a` | No | — |
| Change resource / widen scopes | refused | `test_refreshed_access_token_keeps_resource_binding`, scope tests | No | V6 |
| Survives service restart | yes (database) | e2e phase 2 (local process restart; CI container restart) | — | — |

### Revocation
| Trigger | Access token | Refresh token | Evidence |
|---|---|---|---|
| Password change (any path) | **refused on the next tool call** (`cfp` mismatch) | `invalid_grant`, family revoked | `test_any_password_change_ends_chatgpt_access` |
| `token_version` bump (`/change-password`, `/password-reset/confirm`, admin `revoke-user-tokens`) | refused on next call | `invalid_grant` | `test_token_version_bump_ends_access_and_refresh`, `test_logout_all_revokes_chatgpt_access` |
| Account deletion | refused on next call | rows cascade-deleted → `invalid_grant` | `test_account_deletion_ends_access_and_refresh`, `test_account_deletion_cascades_oauth_rows` |
| `/revoke` of a refresh token | **remains valid until expiry (≤ 15 min)** — it is a stateless JWT and only the triggers above are re-checked per call | renewal impossible | `test_revoking_refresh_token_does_not_kill_live_access_token` |
| Mobile `/logout` | unaffected (separate grant) | unaffected | by design |

"Refused on the next call" means the JWT is not invalidated in itself; every
tool call re-reads the user row and fails closed.

### Dynamic client registration
| Threat | Current behavior | Evidence | Exploitable? | Fix |
|---|---|---|---|---|
| Malicious redirect | refused | 26 + 3 cases | No | V1 |
| Unneeded grants / response types / jwks / auth methods | refused | 13 cases | No | V2 |
| Malformed JSON | 400 | `test_registration_rejects_malformed_json` (4) | No | — |
| Oversized metadata | ≤ 4 KiB | V2 cases | No | V2 |
| Mass / duplicate registration | allowed per RFC, limited per IP | `test_registration_is_rate_limited` | Bounded | V2 |
| Confidential-client secret at rest | stored in `client_info` JSON in plain text — the SDK compares the stored secret directly | code review | Only with DB read access, which already exposes all user data | Accepted; see assumptions |

### MCP tool isolation (transport + auth layer)
All eight tools are driven through the SDK client over the real ASGI app with
bearer auth. User B's markers never appear for A — including with smuggled
`user_id`/`userId`/`account_id`/`email`/`owner` arguments (40 cases) — and A
sees exactly A's own figures on every tool:
`test_a_never_sees_b` (8), `test_smuggled_identity_argument_gives_nothing` (40),
`test_a_sees_exactly_its_own_figures_on_every_tool`, `test_token_for_b_reads_b_only`.

### Consent / sign-in page
| Concern | Behavior | Evidence |
|---|---|---|
| XSS | all client-supplied text escaped; no scripts; CSP `default-src 'none'`, no `script-src` | `test_consent_page_is_hardened` (`<script>` client name) |
| Clickjacking | `frame-ancestors 'none'`, `X-Frame-Options: DENY` | same |
| Cookies | `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`, max-age = pending TTL (10 min), deleted after success | same |
| Caching / referrer | `Cache-Control: no-store`, `Referrer-Policy: no-referrer` | same |
| Enumeration | uniform message and timing | V4 tests |
| Brute force | per-IP 10/min (configurable) + shared account lockout (5 → 30 min) | `test_consent_page_rate_limit`, `test_wrong_password_and_shared_lockout` |
| Password / e-mail in logs | never logged; only a 12-hex subject hash | `test_oauth_flow_logs_no_secrets`, `test_logs_never_contain_tokens_amounts_or_pii` |

Residual: an attacker who knows a victim's e-mail can trigger the shared
30-minute lockout (true of the mobile login already); per-IP limits slow but
do not prevent this from distributed sources.

## Remaining assumptions (delegated)

1. **ChatGPT binds `state` to the initiating browser session** and validates it
   on the callback (defense against authorization-request forgery and code
   injection across ChatGPT users). PKCE prevents a stolen code from being
   redeemed by anyone without ChatGPT's verifier.
2. **ChatGPT keeps refresh tokens confidential** and does not submit the same
   refresh token concurrently (if it does, the connection must be re-authorized
   — fails safe).
3. **TLS** terminates at Railway for `MCP_PUBLIC_URL`; the service is reachable
   only through that proxy, and `MCP_TRUSTED_PROXY_HOPS=1` matches Railway's
   single `X-Forwarded-For` hop (otherwise per-IP limits could be spoofed).
4. **Secrets** (`MCP_OAUTH_PRIVATE_KEY`, `MCP_LOGIN_CSRF_SECRET`) stay only in
   Railway variables. Since the follow-up hardening, the fingerprint uses its own
   `MCP_GRANT_FINGERPRINT_SECRET`: rotating it revokes every ChatGPT grant
   (emergency kill switch); rotating `MCP_LOGIN_CSRF_SECRET` does not
   (`tests_mcp/test_secret_separation.py`).
5. **Database access = full compromise.** DCR client secrets are stored as
   issued (SDK constraint); codes and refresh tokens are hashed.
6. **Per-replica rate limits** (in memory). Use one replica, or move limits to
   Redis before scaling out.
7. **RFC 9207 `iss` in authorization responses is not sent.** ChatGPT then
   uses per-connection callback URLs, which already separate issuers.
8. **CIMD is not supported** (SDK); ChatGPT supports DCR.

## Recommendation on keeping the built-in authorization server

Bespoke code owned by MITA: storage, consent page, redirect policy, DCR
restrictions, fingerprint binding — 1,211 lines in `app/mcp/auth/` (including keys/token code). The
protocol-critical steps (request parsing, PKCE verification, code expiry,
redirect matching, client authentication, metadata) are the MCP SDK's. All
weaknesses found were in MITA's policy layer and are fixed and pinned by 127
OAuth tests (87 adversarial, 23 flow, 16 auth, 1 concurrency). Keeping it is defensible for a read-only v1.

If MITA prefers an established provider (Auth0/Stytch, both support MCP),
what stays unchanged: all tools, the query layer, `runtime.py`,
`JwtTokenVerifier` (`MCP_AUTH_MODE=external`, already tested with an external
JWKS), the protected-resource metadata, and every isolation/accuracy test.
What changes: `provider.py`, `login.py`, migration 0037's tables become
unused, and identity mapping moves to an IdP claim
(`MCP_EXTERNAL_USER_CLAIM`) — which requires the IdP to authenticate against
MITA's user store (Auth0 Custom Database = Professional plan) and gives up the
password-fingerprint revocation unless replicated there.
