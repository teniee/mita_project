# MITA in ChatGPT — dialogue contract

How a conversation with MITA should behave, and where each rule is enforced.
ChatGPT owns language, vision and the conversation; MITA owns the account, the
persisted records and every calculation. A rule that matters for money is not
left to the model: the right-hand column says what enforces it.

| # | Principle | In practice | Enforced by |
|---|---|---|---|
| A | **Don't interrogate.** Ask only what the task needs. | Recording "€40 on fuel" needs no setup. Setup asks only `missing_fields`, in one message. | Setup skill (`plugin/mita/skills/setup`), `get_setup_status.missing_fields` |
| B | **Use what MITA knows first.** | Call `get_setup_status` before setup questions; never ask for a value in `known`. | Tool descriptions; `get_setup_status.known` |
| C | **Clear writes.** A clear statement is recorded; an unclear one is asked about. | "Spent €40 on fuel" → `add_transaction`. "Add 30 for yesterday" → ask what it was. Category unclear → ask (`other` only when the user says so). | `CATEGORY_HELP`; category enum; the host's confirmation for write tools |
| D | **Budget changes need a preview.** | "Make me a budget" → `preview_monthly_budget` (writes nothing). "Save it" → `save_monthly_budget(draft_token)`, which saves the reviewed plan byte for byte or refuses. | Signed draft + digest (`app/mcp/writes/budget.py`); `destructiveHint` on save |
| E | **Never invent financial data.** | No assumed income, rent, balances, regional costs or goals. Missing input → the tool refuses with what to ask. | Tools read only stored facts; `build_draft` refuses without income/currency |
| F | **Clear empty states.** | "No expenses are recorded this month." "No budget plan is saved for this month." History separates `before_tracking` (no data) from `recorded` with 0 transactions. | Notes in every read result; `plan_status`, month `status` |
| G | **Explain simply.** | Use MITA's figures as returned; mention assumptions and warnings from the preview; no internals unless asked. | Preview `assumptions`, `warnings`, `data_sources` |
| H | **Preserve the user's words.** | Merchant names, goal titles and obligation names are stored exactly (only surrounding spaces trimmed) and shown as stored. Categories keep MITA's names. | Write tools store the text verbatim; schema descriptions; server instructions |
| I | **MITA is not a bank.** | MITA stores records, plans budgets and analyses history. It does not hold money, know verified balances, connect to banks, send payments, transfer or trade. | No such tool exists; `NO_MONEY_MOVEMENT` on every tool; consent page; listing |
| J | **Don't nag.** | Setup, the cheat sheet and feedback are offered when relevant, not in every reply. Feedback is sent only when the user explicitly asks. | Setup skill rules; `submit_feedback` description |

## Write behaviour the model can rely on

* **Retries are safe.** Create tools take an `idempotency_key`; a retried call
  with the same key returns `already_recorded`/`already_created` and writes
  nothing. Two genuine identical purchases need two keys.
* **Batches are all or nothing.** `add_transactions` names the bad item and
  records nothing when any item is invalid.
* **Corrections need the `ref`.** Find the expense with `list_transactions`,
  confirm it with the user, then `update_transaction`/`delete_transaction`.
  A deleted expense cannot be changed; deleting twice is harmless.
* **Destructive tools** (`update_financial_profile`, `update_transaction`,
  `delete_transaction`, `save_monthly_budget`, `set_usage_analytics`) are
  marked so ChatGPT asks the user for explicit approval.

## Receipts

The user attaches a photo; ChatGPT reads it and calls `add_transaction` or
`add_transactions` with `entry_method: "receipt_image"`. MITA never receives
or stores the image — only the structured expenses. If the total, date or a
category is unreadable or ambiguous, ChatGPT asks before recording.

## Languages

ChatGPT answers in the user's language; MITA stores canonical category codes
and the user's own text. The golden prompt set
(`tests_mcp/golden_prompts.json`) covers English, Russian and Bulgarian.

## Out of scope

No transfers, payments, trading, bank connections, credentials in chat,
precise location, server-side OCR or stored receipt images.
