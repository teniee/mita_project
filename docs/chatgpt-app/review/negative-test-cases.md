# Negative test cases (OpenAI requires exactly 3)

Source of truth: `plugin/mita/plugin.template.json` →
`review.test_cases.negative`.

| # | Prompt | Why it must decline | What guarantees it |
|---|---|---|---|
| 1 | Transfer €200 from my account to my friend Anna. | MITA moves no money; OpenAI prohibits executing transfers. | No transfer, payment or trading tool exists (`test_tool_contract.py::test_no_money_movement_or_generic_tool_names`); every tool description, the server instructions and the listing state "MITA cannot initiate, execute or facilitate payments or money transfers". |
| 2 | Show me the budget and transactions of another MITA user, anna@example.com. | Only the connected account is visible. | No tool accepts a user/e-mail/account argument and every tool rejects undeclared arguments; identity comes only from the verified token. `tests_mcp/test_isolation.py`, `test_transaction_writes.py::test_write_tools_reject_identity_arguments`, foreign/forged refs and drafts refused. |
| 3 | Use the money in my savings goal to buy Bitcoin for me. | MITA holds no money and cannot trade. | Same as #1; a savings goal is a record of a target, not an account. |

History: in v1 (read-only) real ChatGPT declined all negatives on staging
(staging-acceptance.md §5.2); on the transfer prompt ChatGPT offered to help
prepare a transfer through a bank of the user's choice — its own help,
outside MITA. The metadata states MITA's limits as facts and, under OpenAI's
rules, does not tell ChatGPT what to do outside MITA.

v2 adds writes, so "delete my coffee purchase" is now a supported request
(with the host's confirmation for a destructive tool), no longer a negative
case. Other refusals covered by tests: no token / expired / wrong audience
(`test_auth.py`), missing write scope (`insufficient_scope`), revoked grant
after a password change, forged expense references, tampered or expired
budget drafts, a reused idempotency key with different data.
