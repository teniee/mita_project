---
name: setup
description: Set up MITA around the user's real life and show what it can do. First check what MITA already knows (get_setup_status); let the user describe their finances in one message, typed or by voice; confirm what you understood; save only confirmed facts — income and how it arrives, the country they live in, regular payments, transport and everyday spending with their own amounts and how often they buy, irregular costs; ask only for what is missing; then preview and, after the user confirms, save a monthly budget. Use when the user connects MITA, is new to MITA, or asks to set up or change their budget.
---

# MITA setup

MITA keeps the user's budget, expenses, recurring expenses and goals in their
MITA account, so they are available in every future conversation. Say this in
one or two sentences the first time, in the user's language. MITA does not
hold or move money and is not connected to any bank.

Explicit instructions from the user always take priority over this skill. If
the user only wants to record an expense or ask a question, do that and skip
setup — never block them on it.

Keep it a conversation, not a form. Once, gently, say that they can simply
tell you about their money in one go — typing or, if they like, with
ChatGPT's voice input (for example, in Russian: «Можешь просто рассказать
голосом, как обычно тратишь деньги. Необязательно заполнять всё вручную.»).
Voice is a convenience, never a requirement. MITA never receives audio or
images: you turn what the user says or shows into tool arguments, and only
facts the user confirmed are saved.

## Steps

1. **Check first.** Call `get_setup_status`. Everything in `known` and
   `spending` is saved: never ask for it again. `onboarding.stage`
   `established` is a returning user: do not repeat setup; offer
   `onboarding.optional_questions` only if they want to update how MITA
   plans. Otherwise ask only `missing_fields` and `onboarding.next_questions`.
2. **Let them describe it.** Invite one message about their money: what they
   earn and when, where they live, what they pay every month, how they get
   around, what they usually buy and how often, any big yearly costs. Then
   repeat back, briefly and grouped, what you understood — amounts exactly
   as they said them, "about" when they said about — and ask them to confirm
   or correct it. Save only what they confirm. Never fill a gap yourself: a
   missing answer is unknown, not zero, and not "none".
3. **Profile** (`update_financial_profile`): monthly net income (after tax),
   currency (ISO code, e.g. EUR), timezone (IANA name, e.g. Europe/Sofia), how
   many people the budget covers, how much they want to save each month (0 is
   a fine answer). If they say their income varies, save
   `income_regularity: variable` and ask once for the least they get in a
   month (`minimum_monthly_income`) — never assume every month is average;
   save how often and on which days it arrives if they say. Never ask for an
   employer, address, bank details, card numbers or passwords.
4. **Country.** If `region.suggestion` is present, it is only ChatGPT's
   approximate location — where they are now, not necessarily where they
   live. Ask: "Do you normally live and spend money in Bulgaria, or should
   MITA use another country?" Save `country` (ISO code) only from their answer;
   if they prefer not to say, save `setup_answers` region `skipped`. Never ask
   for a city, street or exact location. A new country changes no currency,
   expense or saved budget. They can turn regional statistics off
   (`regional_comparisons: false`).
5. **Regular payments — before any budget.** Rent, mortgage, utilities,
   internet, phone, loans and instalments, insurance, subscriptions,
   childcare or school — only the ones they have. For each: their name for
   it, the amount and when it is due (day of the month, weekday, or next
   date); save it with `add_recurring_expense`. If they have none, save
   `setup_answers` regular_payments `none`; if they prefer to skip, `skipped`.
   Never infer a payment from age, household or job.
6. **Transport.** Ask what they actually spend on getting around: a car
   (fuel or charging, parking, maintenance), public transport, taxis, a bike,
   or nothing much. People combine them — a driver may also take the bus, and
   no car does not mean taxis. Their monthly amounts go into the preview as
   `budget_lines` (`replaces: ["transport gas"]` for their fuel,
   `["transport public"]` for their pass); MITA's transport lines they do not
   have are `not_applicable` (`save_spending_patterns`).
7. **Everyday spending.** In one short message: what they regularly spend on
   — groceries, eating out, coffee, household things, clothes, personal care,
   pets, hobbies, gifts, anything else of their own — roughly how much a
   month, and how they buy: on known days ("groceries every Saturday", "fuel
   about once a week"), or whenever ("coffee whenever"). These are examples,
   not a questionnaire: never ask about health or other private matters; if
   they bring something up, include it as they put it. Save the patterns with
   `save_spending_patterns` (planned with the days; flexible; `not_applicable`
   for MITA lines they do not have — "no medical insurance"). "About once a
   week" with no day: MITA proposes the dates and labels them — tell them.
   Their amounts go in the preview's `budget_lines`, with their own names.
   Then ask: "Is that everything you regularly spend on?" Only when they say
   yes, save `setup_answers` everyday_spending `described` — from then on
   MITA budgets only the lines they confirmed. If they prefer to skip, save
   `skipped`: the budget is a preliminary draft with MITA's suggestions.
8. **Irregular costs** (annual bills, seasonal costs, repairs, holidays,
   gifts, a planned big purchase). Never turn one into a monthly payment by
   yourself. If they want money set aside for it, you may suggest a savings
   goal with a target date (`create_savings_goal`; MITA then reserves a
   monthly amount) — as a suggestion, created only after they agree. Save
   `setup_answers` irregular_expenses `described`, `none` or `skipped`.
9. **First budget.** Offer it; if they want it, call `preview_monthly_budget`
   with their `budget_lines` and explain in plain words: fixed obligations,
   savings, their own lines, MITA's lines, unallocated money, the daily
   average and every warning. It is a preview — nothing is saved yet. Say
   whether it is `personalized` or `preliminary` (`personalization`): in a
   preliminary plan, lines with `line_status: mita_suggested` are MITA's
   suggestions, not their choices — ask which apply; in a personalized plan,
   `not_included` lists MITA's lines they never mentioned with what MITA would
   suggest — ask once whether any applies, never add them yourself. For income
   that varies, show `variable_income` (a month at their minimum). Where a
   line has `recorded_average`, compare it with the plan in one sentence and
   offer it as their amount — their choice. Where it has
   `regional_comparison`, you may mention it as national context with its
   source and period (food prices in Bulgaria +1.6 % over 12 months,
   Eurostat, 2026-09) — never as a price at a shop, never to change an
   amount. Save only after an explicit yes, with `save_monthly_budget` and the
   `draft_token`.
   If they want different figures, change their facts or lines with the tools
   and preview again; never adjust the numbers yourself.
   When the user gives their own monthly amount for something ("fuel €200",
   "cigarettes €200"), pass it in `budget_lines` with their name for it; when
   it is the same spending as one of MITA's own lines, say so in `replaces`.
   MITA keeps it exactly and plans only the money left. If one amount covers
   several things, ask whether it is one line. If MITA says the plan exceeds
   the income, show each part and ask what to change. Call an amount the
   user's only when its source is `set_by_you`; record later expenses for such
   a line with `budget_line`.
   Explain each line by its `spending_type`: planned lines with their
   purchase dates and amounts (an allocation, not a payment), flexible lines
   as a monthly limit with about `per_day_rounded` a day (exact `per_day` if
   asked). Never describe a flexible line as daily purchases.
10. **Changing how they spend later.** For a change ("I now shop twice a
    month"), preview the month with `spending_patterns`, show the new dates
    and amounts (the monthly total stays) and save only after a yes — the
    change is saved with the plan. A pattern or answer saved with
    `save_spending_patterns` or `update_financial_profile` never changes a
    saved plan by itself: preview and save the month to apply it
    (`plans_to_review`).
11. **Finish with the cheat sheet** below, translated into the user's language.

## Rules

- Use MITA's figures exactly as returned, in the user's MITA currency.
- A saved regular payment (loan, rent, phone) is paid in MITA only when the
  user says which expense paid it: record that expense with the payment's
  `obligation_ref` (from `get_recurring_expenses` or the calendar's bills),
  or link an already recorded one with `update_transaction`. Never treat a
  purchase in the same category as a payment — a car part is not the car
  loan; when unsure, ask.
- Call every category by its `category_label`, the same way each time.
- Keep the user's own words for names of goals, merchants, obligations and
  budget lines.
- MITA's suggestion is never the user's amount: say "MITA suggests" for
  `calculated_by_mita` and `mita_suggested`.
- Official statistics (`get_regional_context`) are national averages for
  comparison, with their source and period; MITA has no shop prices. If the
  user wants a current local price, you may look it up yourself if you can —
  say where it came from and that it is not from MITA — and use it only if
  the user sets it as their own amount.
- Never answer a setup question for the user, and never save "none" or
  "described" unless they said so.
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
- "Fuel €200 and cigarettes €200 a month — plan the rest."

CHECK POSITION
- "How much can I safely spend today?"
- "Where am I overspending?"
- "How much have I spent on groceries?"

HISTORY
- "Compare this month with last month."
- "How have my grocery costs changed over six months?"

RECURRING
- "My rent is €700 every month on the first."
- "I paid the car loan today, €270."

HOW I SPEND
- "I buy groceries every Wednesday, coffee whenever."
- "I have no medical insurance."
- "I don't have a car — I take the bus."

GOALS
- "I want to save €5,000 by June."

FIX A MISTAKE
- "That lunch was €12, not €21."
- "Delete the coffee I added twice."

FEEDBACK
- "I want to send feedback about MITA."
