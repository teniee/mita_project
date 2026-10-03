# Submission readiness (2026-10-03)

| Requirement | Status | Evidence | Remaining action |
|---|---|---|---|
| Public HTTPS MCP endpoint `/mcp` (streamable HTTP) | Code done; not deployed | `app/mcp/server.py`; container smoke in `mcp-ci` | O-6, O-7, O-11 |
| Tool hints explicit on every tool | Done | `tests_mcp/test_tool_contract.py` | — |
| Descriptions accurate, read-only stated | Done | same | — |
| No identity inputs; per-user isolation | Done | `tests_mcp/test_isolation.py` (48 cases) | — |
| Minimal outputs (no ids, notes, receipts, e-mails) | Done | `test_finance_accuracy.py::test_private_fields_never_returned` | — |
| OAuth 2.1: PRM, AS metadata, DCR, PKCE S256, resource-bound tokens | Done (DCR; CIMD not in SDK) | `tests_mcp/test_oauth_flow.py` (23) | — |
| `get_profile` with `openai/profile` | Done | `test_tool_contract.py` | — |
| Financial accuracy, soft deletes, empty state, timezone | Done | `test_finance_accuracy.py`, `test_empty_state.py`, `test_timezone.py`; REST parity check (local) | — |
| No digital-goods commerce / checkout | Done | `commerce: false`; no purchase text | — |
| 5 positive + 3 negative test cases | Done | `plugin.template.json`, validated by `build_plugin.py` | — |
| Plugin ZIP (Agent Plugins schema) | Done (template) | `build_plugin.py --check` in CI | O-15 (real values) |
| Icons | Brand-spec SVG placeholders | `plugin/mita/assets` | Replace with official artwork if desired |
| Domain verification endpoint | Done | `test_openai_domain_challenge_returns_only_the_token` | O-13 |
| Website / support / privacy / terms over HTTPS | **Blocked** | TLS fails; no real pages | O-8, O-9 |
| Working support contact | **Blocked** | `@mita.finance` undeliverable | O-8, O-9 |
| Age suitability (13–17) | **Blocked** | ToS §2.1 requires 18+ | O-9(c) |
| Review account with sample data, no MFA | Not created | dataset + local rehearsal script | O-10 |
| Demo video | Not recorded | `demo-script.md` | O-14 |
| Verified org / individual | Unknown | — | O-12 |
| Leaked credentials rotated | **Not done** | security-findings S-1..S-4 | O-1..O-4 |
