# Negative test cases (OpenAI requires exactly 3)

Source of truth: `plugin/mita/plugin.template.json` →
`review.test_cases.negative`.

| # | Prompt | Why it must decline | What guarantees it |
|---|---|---|---|
| 1 | Transfer €200 from my account to my friend Anna. | MITA moves no money; OpenAI prohibits executing transfers. | No tool can write anything (8 read-only tools, `readOnlyHint=true`, `destructiveHint=false`; every tool runs in a `READ ONLY` database transaction). ChatGPT should explain MITA is read-only. |
| 2 | Delete my coffee purchase from yesterday and change my food budget to €500. | v1 is read-only. | Same as above; `tests_mcp/test_tool_contract.py::test_no_write_verbs_in_tool_names` and `test_read_only_and_endpoints.py::test_tool_session_refuses_writes`. |
| 3 | Show me the budget and transactions of another MITA user, anna@example.com. | Only the connected account is visible. | No tool accepts a user/e-mail/account argument; identity comes only from the verified token. `tests_mcp/test_isolation.py` (incl. smuggled `user_id`, `email`, tampered token `sub`). |

Other refusals covered by tests but not submitted as review cases: no token /
expired / wrong-audience token (`test_auth.py`), missing `finance:read` scope,
revoked grant after a MITA password change or token-version bump, buying crypto or stocks (no such tool).
