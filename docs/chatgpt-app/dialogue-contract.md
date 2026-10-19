# MITA in ChatGPT — dialogue contract

How a conversation with MITA should behave, and where each rule is enforced.
ChatGPT owns language, vision and the conversation; MITA owns the account, the
persisted records and every calculation. A rule that matters for money is not
left to the model: the right-hand column says what enforces it.

| # | Principle | In practice | Enforced by |
|---|---|---|---|
| A | **Don't interrogate.** Ask only what the task needs. | Recording "€40 on fuel" needs no setup. Setup asks only `missing_fields`, in one message. | Setup skill (`plugin/mita/skills/setup`), `get_setup_status.missing_fields` |
| B | **Use what MITA knows first.** | Call `get_setup_status` before setup questions; never ask for a value in `known`. | Tool descriptions; `get_setup_status.known` |
| C | **Clear writes.** A clear statement is recorded; an unclear one is asked about. | "Spent €40 on fuel" → `add_transaction`. "Add 30 for yesterday" → ask what it was. Category unclear → ask (`other` only when the user says so). The category is what was bought, not where: a receipt's lines can have different categories. | `CATEGORY_HELP`; category enum; `add_transactions` description; the host's confirmation for write tools |
| D | **Budget changes need a preview.** | "Make me a budget" → `preview_monthly_budget` (writes nothing). "Save it" → `save_monthly_budget(draft_token)`, which saves the reviewed plan byte for byte or refuses. Before a first budget, ask once about regular payments (rent, utilities, loans, subscriptions); a preview without them is labelled a default draft. | Signed draft + digest (`app/mcp/writes/budget.py`); `destructiveHint` on save; `suggested_next_step: ask_about_obligations`; preview warning |
| E | **Never invent financial data.** | No assumed income, rent, balances, regional costs or goals. Missing input → the tool refuses with what to ask. | Tools read only stored facts; `build_draft` refuses without income/currency |
| F | **Clear empty states.** | "No expenses are recorded this month." "No budget plan is saved for this month." History separates `before_tracking` (no data) from `recorded` with 0 transactions. | Notes in every read result; `plan_status`, month `status` |
| G | **Explain simply.** | Use MITA's figures as returned; mention assumptions and warnings from the preview; no internals unless asked. | Preview `assumptions`, `warnings`, `data_sources` |
| H | **Preserve the user's words.** | Merchant names, goal titles and obligation names are stored exactly (only surrounding spaces trimmed) and shown as stored. Categories are shown under their `category_label` (one name per category in every tool; "Fuel" for both `gas` and `transport gas`). | Write tools store the text verbatim; `app/mcp/categories.py`; schema descriptions; server instructions |
| I | **MITA is not a bank.** | MITA stores records, plans budgets and analyses history. It does not hold money, know verified balances, connect to banks, send payments, transfer or trade. | No such tool exists; `NO_MONEY_MOVEMENT` on every tool; consent page; listing |
| J | **Don't nag.** | Setup, the cheat sheet and feedback are offered when relevant, not in every reply. Feedback is sent only when the user explicitly asks. | Setup skill rules; `submit_feedback` description |
| K | **Offer only what a tool can do.** | A savings goal cannot be changed after it is created — no monthly contribution, target date, added money or deletion from ChatGPT. Say so instead of offering it. (Real ChatGPT offered "€400 a month toward your Emergency Fund".) | `GOAL_LIMITS` in both goal descriptions and in the no-date result note; server instructions; golden prompts en-27, ru-16, bg-16 |
| L | **Only this account.** | MITA cannot see anyone else's account. "Show Anna's transactions" is declined; a name can only match this user's own expenses (a merchant they typed), and must be worded that way. | No tool takes a user; `list_transactions` description and merchant-filter note; server instructions; golden prompts en-29, en-30, ru-17 |

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

Each line gets the category of what it is, not of the shop: one receipt may
produce lines in several categories (household goods are `shopping`, medicine
`healthcare`). MITA's taxonomy (the API's expense categories) has no alcohol or
tobacco category, and none is invented here: drinks bought in a shop count as
`groceries` unless the user picks another category. (Real ChatGPT stored a
12-line supermarket receipt with beer, gin and brandy as all groceries — which
is this rule — while the old hint "groceries for a supermarket" also pushed
non-food lines into groceries; the hint now says "by what was bought".)

## Languages

ChatGPT answers in the user's language; MITA stores canonical category codes
and the user's own text. The golden prompt set
(`tests_mcp/golden_prompts.json`) covers English, Russian and Bulgarian.

## Out of scope

No transfers, payments, trading, bank connections, credentials in chat,
precise location, server-side OCR or stored receipt images.
