# Release notes — MITA Finance plugin

(Also in `plugin.template.json` → `publication.release_notes`.)

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
