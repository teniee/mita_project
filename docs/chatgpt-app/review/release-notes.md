# Release notes — MITA Finance plugin

## Submitted text (`plugin.template.json` → `publication.release_notes`)

Plugin package **2.3.0**, the first public submission. OpenAI asks the notes
to summarize the package version being submitted, so the package carries only
this paragraph (2026-10-27); the history below is for the team.

> 2.3.0 — First public release of MITA Finance in ChatGPT. Sign in to your MITA account, or create one, on MITA's own page. Record expenses in plain language — one at a time, several at once, or from a receipt photo that ChatGPT reads (MITA never receives the image) — and correct or delete them. Save your income, currency, household size and savings target; preview a monthly budget built by MITA's rules and save it only after you review it. See where you stand, how the month ends at your current pace and what you can safely spend each day: money set aside for savings and goals, and the month's bills not yet recorded as paid, are held out of that amount. Open your month as an interactive calendar in the chat — each date's plan and spending, bills due and money set aside — and save it as an image. Save recurring expenses and savings goals, compare months, and send feedback to the MITA team. Usage statistics stay off unless you tick the box on the sign-in page. No payment, transfer, trading or bank connection.

## History (internal)

**2.3.0 — bills come first, the final connect page** (not yet deployed)

* The safe amount a day holds back the month's bills not yet recorded as paid
  (saved regular payments that fall in the month, stated rent, mortgage and
  utilities), as it already held back money set aside (R3,
  `docs/chatgpt-app/r3-bills-reserve.md`). The same rule applies in the MITA
  app's forecast.
* MITA's final connect page in ChatGPT (v5.2).
* `get_profile` returns OpenAI's standard profile (id, name, masked e-mail);
  sending feedback asks for the user's approval first.

**2.1.0 — your month on a calendar, in the chat**

* "Show my financial calendar for November": an interactive calendar of the
  user's own month opens in the conversation — each date's plan and recorded
  spending, days over the everyday plan, saved bills on their dates, money set
  aside for savings, and a summary with the safe amount a day.
* Pick a date to see its expenses and categories, filter by category, move
  between months, open it fullscreen, and save the month as an image.
* Read-only: the calendar changes nothing; every figure comes from MITA's
  records and calculations.
* MITA's sign-in page shows how the calendar works with a fictional example.
* The calendar is one of the three starter prompts ("Show my financial calendar
  for this month.").
* Usage statistics are off until you tick the box on the sign-in page.

**2.0.0 — free v1: MITA keeps your records across conversations**

* New users can create a MITA account on MITA's sign-in page while
  connecting; existing users sign in as before.
* Record expenses one at a time or several at once (also from a receipt
  photo that ChatGPT reads — MITA never receives the image), and correct or
  delete them.
* Save income, currency, timezone, household size and savings target; MITA
  asks only for what it does not know.
* Preview a monthly budget built by MITA's deterministic rules and save
  exactly the reviewed plan.
* Save recurring obligations and savings goals.
* Six months of spending history, trends and a factual overview.
* Send feedback to the MITA team; optional, consented usage statistics that
  the user can switch off (which deletes them).
* Still no payment, transfer, trading or bank capability; no commerce.

**1.0.0** — eight read-only tools over the connected MITA account.

Known limitations: accounts created with Google sign-in cannot connect yet
(no MITA password); push alerts are not sent for expenses recorded in
ChatGPT; a second dated savings goal cannot reserve daily amounts in the plan
(the goal is saved and the result says so); plan and expense categories use
different names (both shown as stored); amounts recorded in another currency
are summed at face value and flagged, never converted.
