---
name: setup
description: Set up MITA and show what it can do. First check what MITA already knows (get_setup_status); ask only for missing income, currency, timezone, household size and savings target; save them; ask about regular payments such as rent and save them; then offer to preview and, after the user confirms, save a first monthly budget. Use when the user connects MITA, is new to MITA, or asks to set up or start their budget.
---

# MITA setup

MITA keeps the user's budget, expenses, recurring expenses and goals in their
MITA account, so they are available in every future conversation. Say this in
one or two sentences the first time, in the user's language. MITA does not
hold or move money and is not connected to any bank.

Explicit instructions from the user always take priority over this skill. If
the user only wants to record an expense or ask a question, do that and skip
setup — never block them on it.

## Steps

1. **Check first.** Call `get_setup_status`. Everything in `known` is already
   saved: never ask for it again. Only `missing_fields` may be asked.
2. **Ask once, briefly, only for what is missing** — in one message:
   - monthly net income (after tax);
   - currency (confirm the ISO code, e.g. EUR);
   - timezone (confirm the IANA name, e.g. Europe/Sofia);
   - how many people the budget covers;
   - how much they want to save each month (0 is a fine answer).
   Do not ask for an address, location, bank details, card numbers or
   passwords. Do not guess: if an answer is unclear, ask again.
3. **Save only what the user stated** with `update_financial_profile`.
4. **Fixed obligations — before any budget.** Ask once whether they have
   regular payments such as rent, utilities, loans or subscriptions (MITA
   suggests this as `ask_about_obligations`). For each one they name, get the
   amount, the category and when it is due (day of the month, weekday, or next
   date), then save it with `add_recurring_expense`, keeping their name for
   it. If they have none or prefer to skip, move on — do not show a detailed
   budget before asking.
5. **First budget.** Offer it; if they want it, call `preview_monthly_budget`
   and explain in plain words: fixed obligations, savings, the category
   amounts, unallocated money, the daily average and every warning. It is a
   preview — nothing is saved yet; without regular payments it is a default
   draft and says so. Save only after an explicit yes, with
   `save_monthly_budget` and the `draft_token`. If they want different
   figures, change income, savings or obligations with the tools and preview
   again; never adjust the numbers yourself.
6. **Finish with the cheat sheet** below, translated into the user's language.

## Rules

- Use MITA's figures exactly as returned, in the user's MITA currency.
- Call every category by its `category_label`, the same way each time.
- Keep the user's own words for names of goals, merchants and obligations.
- Offer only what MITA's tools can do. A savings goal cannot be changed after
  it is created (no monthly contribution, target date or added money from
  ChatGPT) — say so rather than offering it.
- MITA has only this user's own records; never suggest it can look up another
  person.
- When MITA has no data (empty lists, `insufficient_data`, no plan), say so;
  never estimate it.
- Do not repeat setup questions in later conversations once they are answered.

## Cheat sheet

RECORD SPENDING
- "I spent €42 at Lidl on groceries."
- "Today: €8 coffee, €55 fuel and €24 lunch."
- Attach a receipt photo: "Add these expenses to MITA."

BUILD A BUDGET
- "Build my budget for this month."
- "I earn €2,500 and want to save €400."

CHECK POSITION
- "How much can I safely spend today?"
- "Where am I overspending?"
- "How much have I spent on groceries?"

HISTORY
- "Compare this month with last month."
- "How have my grocery costs changed over six months?"

RECURRING
- "My rent is €700 every month on the first."

GOALS
- "I want to save €5,000 by June."

FIX A MISTAKE
- "That lunch was €12, not €21."
- "Delete the coffee I added twice."

FEEDBACK
- "I want to send feedback about MITA."
