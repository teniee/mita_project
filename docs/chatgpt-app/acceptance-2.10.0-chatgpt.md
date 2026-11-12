# Owner acceptance in real ChatGPT — MITA 2.10.0 on staging (phone first, ≈ 20 minutes)

What 2.10.0 changes is described in `flexible-envelopes-calendar.md`: a
budget is not a schedule — a flexible monthly budget is on no date of the
calendar. Tests and the local render checks (`review/calendar-v4/`) are not
ChatGPT. Nothing here counts as passed until it has run in real ChatGPT on a
phone. The Result column starts empty on purpose. The 2.9.0 script
(`acceptance-2.9.0-chatgpt.md`) still applies; this one adds only what
changed.

## Before you start

* `https://mita-mcp-staging-staging.up.railway.app/health` shows
  `"version":"2.10.0"` (`staging.md` → "MCP 2.10.0").
* In ChatGPT, open the plugin **MITA (staging)**, tap **Refresh** (the tool
  descriptions and the calendar component changed: the calendar is now
  `ui://mita/financial-calendar-v4.html`), then start a **new** conversation.
  A calendar card left open in an old conversation still shows the old
  drawing — judge only a calendar opened after the refresh.
* Part A is **your own staging account**, read-only: nothing in it changes
  and nothing has to be saved again — the correction is in what the calendar
  shows, not in your data. Parts B–C use a **new fictional account**
  (`cal210-<date>@example.test`).
* Phone first (note the ChatGPT app version), then the computer. Note the
  start time, so the logs can be matched.

## A — your own November (nothing is written)

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| A1 | "Show my financial calendar for November." Open it fullscreen. | **All categories**: dates so far show what you recorded; dates ahead show only what is scheduled — the car loan **270.00 on the 15th**, the laptop loan **70.00 on the 25th**, and a planned purchase only where you stated when you buy. There is **no "≈" figure** in any date. Dates with nothing scheduled are **empty**. | calendar | |
| A2 | Tap **Restaurants** (behind "More" on a phone). | **No 3.33 / 3.34 on any date.** A date shows an amount only where you really recorded a restaurant expense. The line above the grid reads "flexible budget · spent … of **100.00** this month · … left · about … a day as guidance · no purchase dates". Under the grid: "Restaurants is a flexible budget: a monthly limit with no purchase dates…". | filter | |
| A3 | Tap **Groceries**, then **Car maintenance**, then **Entertainment**. | No **10.67**, **6.67** or **3.33 / 3.34** on any date; each shows only its real expenses and its month: 320.00, 200.00, 100.00 with what is left. | one of them | |
| A4 | Tap **Coffee**. | If you told MITA you buy a coffee **every day**, 1.50 is on each date ahead, once — the same 1.50 "All categories" shows. If you never said when, the dates are empty and the line reads "flexible budget … 45.00 this month". Tell me which you see: it is the answer to "where does the 1.50 come from". | filter | |
| A5 | "Show all". Tap a date ahead with nothing scheduled. | "**Nothing scheduled** — No purchase or bill is planned for this date." Below it, "**Flexible budgets · this month**" lists each budget with what is left and "about … a day", and says it is guidance, not a daily limit. No "To spend on flexible budgets ≈ …". | detail | |
| A6 | Tap the **15th**. | The car loan, its state, and "Planned purchases + Bills due = Scheduled for the date" (270.00 plus any planned purchase). It is **not** marked paid unless you recorded its payment. | detail | |
| A7 | Tap a past date where you spent from a flexible budget. | The amount you spent, "· from its monthly budget" beside the line; no "… flexible budgets' daily share", no "… of the everyday plan left" counting shares. | detail | |
| A8 | Look at the summary. | Your monthly amounts, what you spent and what is left are as before. "Flexible budgets (monthly limits, no dates): … left · about … a day as guidance, not a daily limit". Left to spend, the average a day, Protected savings **500.00** and the held bills are **the same figures as before the release**. The tile now reads "Scheduled on the days left" and counts only planned purchases and bills. | summary | |
| A9 | **Save as PNG.** | In the image, dates ahead show only what is scheduled (270.00, 70.00, a stated purchase) — not a sum on every date. | image | |
| A10 | "How much is planned for 20 November?" | ChatGPT answers from what is scheduled: nothing (or your stated purchase). It does **not** say 3.33 for restaurants or about 25 a day is planned for that date. If it mentions the flexible budgets, it calls the daily figure guidance. | answer | |
| A11 | "What do I still have for restaurants this month?" | The month's 100.00, what you spent, what is left, and "about … a day" as guidance only. | answer | |
| A12 | "Is my 380 still unallocated, and did anything in my budget change?" | Your lines and amounts are unchanged; the money you left unallocated is still unallocated; savings 500.00. Nothing was saved by this session. | answer | |

## B — a new fictional account: a monthly budget, then a schedule

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| B1 | New account. "I earn 2,000 euros a month, I live alone in Bulgaria, I save 300." → "My budget lines: restaurants 100, groceries 320, coffee 45. That is what I spend on." → preview → "Save it." | The three lines are yours, exactly; each is a flexible budget ("monthly limit, no purchase dates"). ChatGPT does not say anything is planned on particular dates. | preview | |
| B2 | "Show my calendar." Filter Restaurants, Groceries, Coffee. | Every date is **empty** in all three (nothing recorded yet). All categories: empty dates. | calendar | |
| B3 | "I spent 40 at a restaurant today." → open the calendar again → Restaurants. | **40.00 on today only**; 60.00 left; "about … a day as guidance". No other date has a restaurant amount. Today is not marked over. | calendar | |
| B4 | "I buy a coffee every day, about 1.50." → preview → "Save it." → calendar → Coffee. | Coffee is now a planned purchase: **1.50 on every date**, once. All categories shows the same 1.50 — and still nothing for restaurants or groceries on dates without an expense. | calendar | |
| B5 | "I buy groceries every Wednesday." → preview → "Save it." → calendar → Groceries. | Groceries is on the **Wednesdays only**, the month's 320.00 split exactly over them; no 10.67 anywhere. | calendar | |

## C — bills are not paid by themselves

| # | Do | Pass when | Result |
|---|---|---|---|
| C1 | Same fictional account: "I pay a 270 car loan on the 15th of each month." → preview → "Save it." → calendar. | 270.00 on the 15th only, state "Scheduled" / "In N days". Held for bills 270.00. | |
| C2 | "I spent 60 on car parts" (do not say it paid the loan). | The loan is still unpaid, 270.00 still held; ChatGPT may ask whether it was the loan payment — say no. | |
| C3 | "I paid the car loan today, 270." | Only now the loan is **Paid**; the held amount falls by 270.00. | |

## After

Note the end time. The operator then checks the logs for that window: no
error-level line, no amount, e-mail or token in them. The fictional account
of parts B–C is deleted with `e2e_v2.cleanup` the next time database access
is authorised (it is listed in `staging.md` → "Left on staging").

If anything in part A differs — in particular an amount on a date that is
neither something you recorded, a bill, nor a purchase you scheduled — send a
screenshot and the date: that is exactly what this release is meant to end.
