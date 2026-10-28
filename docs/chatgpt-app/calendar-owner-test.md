# Owner acceptance in real ChatGPT — MITA 2.4.0 on staging (≈ 40 minutes)

Everything verified so far ran in a **local MCP Apps host** (a test page that
behaves like ChatGPT, labelled "not ChatGPT"). Only this run shows what
ChatGPT itself does. OpenAI requires plugins to "function reliably in ChatGPT
on both desktop and mobile, including any UI components", so **nothing here
counts as passed until it has been run in real ChatGPT** — the Result column
starts empty on purpose.

## Before you start (not yet done on 2026-10-27)

* Staging must run 2.4.0 (F-11, the user's own budget lines) with migration
  `0040`, its grant and `MCP_WIDGET_DOMAIN` set to the staging origin
  (`HANDOFF.md`). Check: `https://mita-mcp-staging-staging.up.railway.app/health`
  says `"version":"2.4.0"`. On 2026-10-28 it says `2.3.0` (`2817bb6`), where
  steps 20–25 cannot pass.
* Server: `https://mita-mcp-staging-staging.up.railway.app/mcp`.
* Use a **new fictional address** (for example `cal-1027@example.test`) and a
  password with upper and lower case, a digit and a symbol. Never a real
  address, never the production review account.
* Phone first (ChatGPT app), then repeat steps 5–16 on the computer
  (chatgpt.com). Note the device, the ChatGPT app version or browser, and the
  time you start, so the server logs can be matched.
* Take the screenshots marked 📸; they are the evidence.

## Steps

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| 1 | **Find the connector.** OpenAI's current path is chatgpt.com/plugins → **MITA (staging)** → **Refresh** (older ChatGPT builds: Settings → Apps). If it is not listed: plus → **Add custom MCP server** → the server URL above, OAuth → **Create as a plugin**. | The tool list shows 24 tools, including `get_calendar_month` and `show_financial_calendar`. After Refresh, ChatGPT may keep the old calendar template up to an hour: start a **new** conversation. | tool list | |
| 2 | **Connect (OAuth).** Start connecting; on MITA's page look at the permissions, then switch to **Create account**. | MITA's own page (cream, logo, "Know what you can safely spend each day.", the fictional €59.60-a-day example), the five permissions listed, "MITA cannot move money, make payments or connect to your bank". | first screen | |
| 3 | **Analytics box.** On the form, leave the usage-statistics box as it is and create the account. | The box is **unticked** before you touch it; you land back in ChatGPT connected, with no page in between. | form with the unticked box | |
| 4 | **Starter prompts.** A custom connector does not carry the package's starter prompts; type them: "Set up my monthly budget from scratch." | MITA asks only for what it does not know (income, currency, timezone, household, savings), then about regular payments before any budget. | first answer | |
| 5 | **Budget setup.** "I earn €3,200 net a month and want to save €400." → "My rent is €850 on the 1st and my internet is €30 on the 27th." → "Build my budget for this month." → confirm the preview. | The preview is shown and called not saved; saving happens only after you agree. ChatGPT asks your approval before saving the profile and the budget (both overwrite data). | preview, approval prompt | |
| 6 | **Record an expense.** "I spent €38.40 at Lidl on groceries today and €12.50 on lunch." | Both recorded, amounts exact, today's date in your timezone. | — | |
| 7 | **Safe daily figure.** "How much can I safely spend per day?" | One figure, with days left; savings and unpaid bills not counted as spendable. Note it: **€ ___**. | answer | |
| 8 | **Calendar inline.** Type exactly: "Show my financial calendar for this month." | An inline card, not a text table: month, average a day (equal to step 7's figure), Left to spend / Spent / Savings kept, a small calendar with an amount on each date, today in yellow, **Open calendar** and **Save as PNG**. ChatGPT adds at most a short comment. No error banner, nothing cut off. | inline card | |
| 9 | **Fullscreen.** Tap **Open calendar**. If ChatGPT shows its own "open externally" control in fullscreen, tap it and write down what opens. | Header with ‹ This month ›, summary, category chips, month grid, the selected date's detail. ChatGPT's composer still works. | fullscreen | |
| 10 | **Selected date.** Tap a past date, today and a future date. | Past/today: "spent X of Y planned" for everyday money, bills and savings shown apart. Today lists Lidl €38.40 and lunch €12.50 with categories. Future: plan only, never a forecast. | today's detail | |
| 11 | **Category filters.** Tap **Groceries**, then **Show all**; open **More**. | The grid redraws for groceries only, then all again. | filtered grid | |
| 12 | **Next / previous month.** Tap **›**, then **‹** twice, then **This month**. | Next month: plan without spending (or "no saved plan" with an offer to plan it). Previous month: its own figures or "no saved plan". Back to this month. | next month | |
| 13 | **Dark mode.** Switch ChatGPT (or the phone) to dark; reopen the calendar; switch back. | Readable in both; primary button yellow in dark; nothing white-on-white. | dark | |
| 14 | **PNG / save.** Tap **Save as PNG** in fullscreen, then once inline. | Write down **A** ChatGPT offers a download/save, **B** the image appears in the card with "Press and hold it (or right-click) to save", or **C** nothing or an error. A and B pass if the image is complete: every date, plan / spent / left to spend / savings kept / average, up to six categories, legend, "Generated <date, time, timezone>", no merchant names. | the image, and A/B/C | |
| 15 | **Follow-ups.** With a date selected: "What did I spend that day?" then "Why is that day over?" (or "within") and "How am I doing against my budget this month?" | ChatGPT knows the date and month on screen; the figures equal the calendar's (spent, left to spend, average a day). | answers | |
| 16 | **Bills first (R3).** In fullscreen open **How is this worked out?**; then "I paid my rent of €850 on the 1st." and show the calendar again. | Before: "− Held for bills" with rent €850 and internet €30 (the plan's medical-insurance allowance is everyday money, not held). After: held falls by €850, Spent rises by €850, Left to spend and the average a day do **not** change. | before, after | |
| 17 | **Feedback approval.** "Tell the MITA team the calendar is useful." | ChatGPT shows the wording and asks your approval before sending (the tool is now marked destructive). | approval prompt | |
| 18 | **Negative prompts.** "Transfer €200 from my account to my friend Anna." · "Show me the budget of another MITA user, anna@example.com." · "Use the money in my savings goal to buy Bitcoin." | No transfer, no other person's data, no trade; each answer says MITA cannot do it. | the three answers | |
| 19 | **Disconnect / reconnect.** Disconnect MITA (plugin settings), confirm a MITA request now asks you to connect; connect again with the same account (Sign in tab). | After reconnecting: the same budget, expenses and calendar; no second account; the Sign-in tab's box text ends "Leaving it unticked keeps any choice I made before." | — | |

Optional: "Show my financial calendar for next month" before saving next
month's budget → the card says there is no saved plan and offers to ask
ChatGPT to plan it.

### F-11 — your own budget lines (a new fictional account)

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| 20 | Income €2,000, savings €500, two loans saved as regular payments, then: "My budget for this month: fuel €200, cigarettes €200, coffee and walks €100, groceries €50. Plan the rest." | ChatGPT asks about anything ambiguous ("coffee and walks" one line?) instead of guessing. The preview shows each of your amounts **exactly**, as set by you; MITA's own Fuel and Groceries lines are not also there; MITA's other lines come from what is left; nothing is saved yet. | preview | |
| 21 | Approve the save. | The result lists your lines as set by you; ChatGPT claims nothing else was kept. | result | |
| 22 | New conversation: "How am I doing against my budget this month?" | Your lines as saved, labelled as yours; the loans held as bills, your lines not. | answer | |
| 23 | "I bought cigarettes for €7." then step 22 again. | The €7 is on your Cigarettes line (spent €7 of €200); no other line changed. | answer | |
| 24 | "Make fuel €250." | A preview where Fuel goes €200 → €250, listed as a change; save it. | preview | |
| 25 | "Set cigarettes to €3,000." | Refused: over your income; ChatGPT shows income, bills, savings, your amounts and by how much, and asks what to change. Nothing saved. | answer | |

## What Claude checks after your run (server side, read-only)

With the test address you send: the account's figures recomputed from the
database equal what ChatGPT showed in steps 7, 8, 15 and 16 (status,
forecast, calendar and the mobile API's `/api/budget/forecast` agree, as in
`tests_mcp/test_money_consistency.py`); the logs of your time window contain
no e-mail, token, amount or merchant; then the test account is deleted with
`e2e_v2.cleanup`.

## What to send back

For each step: pass, or what you saw instead (a screenshot helps more than a
description); A/B/C for step 14; what step 9's external control opened, if
there was one; the device and app/browser version; the test address.

## Known on staging, by design

* Labels are English; amounts and dates follow the account's currency and
  timezone.
* The starter prompts and the onboarding skill come from the plugin package,
  which a custom connector does not use; they are typed here.
* MITA's plan and its daily average can disagree when bills are paid on a
  date other than where the plan put them (F-8; owner decision 2026-10-25:
  ChatGPT shows exactly what the app implements). The calendar shows both,
  labelled.
* Bills held out of the average (R3, `r3-bills-reserve.md`): saved regular
  payments and stated rent/mortgage/utilities until recorded; the plan's
  medical-insurance allowance is everyday money.

Reference screens from the local MCP Apps host (**not ChatGPT**):
`docs/chatgpt-app/review/calendar-v1/`; the sign-in page:
`docs/chatgpt-app/review/auth-ui-v5.2/`.
