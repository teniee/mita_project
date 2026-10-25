# Owner acceptance in real ChatGPT — MITA 2.2 on staging (≈ 20 minutes)

Everything Claude verified so far ran in a **local MCP Apps host** (a test page
that behaves like ChatGPT, labelled "not ChatGPT"). Only this test shows what
ChatGPT itself does. Until it passes, nobody may say the calendar works in
ChatGPT.

* Server: `https://mita-mcp-staging-staging.up.railway.app/mcp` (MCP 2.2.0).
  Check the commit in `staging.md` before you start.
* Use a **new fictional address** (for example `cal-1025@example.test`) and a
  password with upper and lower case, a digit and a symbol. Never a real address.
* Do it on the phone first (ChatGPT app), then repeat steps 4–12 on the computer.
* Take the screenshots marked 📸; they are the evidence. Note the time you
  started, so the server logs can be matched.

| # | Do | Pass when | Record |
|---|---|---|---|
| 1 | ChatGPT → Settings → Apps → **MITA (staging)** → refresh it (or disconnect and **Connect** again). Open the app's details. | The tool list includes `get_calendar_month` and `show_financial_calendar` (24 tools). | 📸 tool list |
| 2 | While connecting, look at the sign-in page, then switch to **Create account**. Leave the usage-statistics box as it is (unticked) and create the account. | Navy first screen (logo, headline, family photo, tilted October month with "Fictional example"). The usage box is **unticked**; on the Sign-in tab its text ends "Leaving it unticked keeps any choice I made before." You land back in ChatGPT, connected, with no page in between. | 📸 first screen, 📸 the form with the unticked box |
| 3 | In a new chat, set up a month: "I earn €3,200 net a month and want to save €400." → "My rent is €850 on the 1st and my internet is €30 on the 27th." → "Build my budget for this month." → confirm the preview → "I spent €38.40 at Lidl on groceries today and €12.50 on lunch." | Each is saved (ChatGPT says so; the preview shows the plan before you confirm). | — |
| 4 | Type exactly: **"Show my financial calendar for this month."** (the new starter prompt) | An **inline card**, not a text table: month, the average a day ("a day on average · N days left"), Left to spend / Spent / Savings kept, a small calendar with an amount on each date, today in yellow, Open calendar and Save as PNG. ChatGPT adds at most a short comment. | 📸 inline card |
| 5 | Tap **Open calendar**. | Fullscreen calendar: header with ‹ This month ›, the summary, category chips, the month grid, the selected date's detail. | 📸 fullscreen |
| 6 | Tap a **past date**, **today**, and a **future date**. | Past/today: "spent X of Y planned" for everyday money, bills recorded and savings shown apart. Future: "plan", never a forecast. | 📸 one past date |
| 7 | On today (or the date of your expenses), scroll the date's detail. | The **actual expenses** of that date are listed (Lidl €38.40, lunch €12.50) with their categories. | 📸 the expenses |
| 8 | Tap the **Groceries** chip, then **Show all**; open **More**. | The grid redraws for groceries only (each date's grocery plan and spending), then returns to all. | 📸 filtered grid |
| 9 | Tap **›** (next month), then **This month**. | Next month loads: planned, no spending (or "no saved plan" with an offer to plan it). Back to this month. | 📸 next month |
| 10 | Switch ChatGPT (or the phone) to **dark** appearance; open the calendar again. Switch back to light. | Readable in both; the primary button turns yellow in dark mode; nothing white-on-white. | 📸 dark |
| 11 | Tap **Save as PNG** (in fullscreen, then once in the inline card). | Write down **which one happened**: **A** ChatGPT offers a download/save of a file (host download), **B** the image appears inside the card with "Press and hold it (or right-click) to save" (preview fallback), **C** nothing or an error. A and B both pass if the image is complete. Open the image: every date of the month, plan/spent/left to spend/protected savings/average, up to six categories, the legend, "Generated <date, time, timezone>", no merchant names, readable on the phone. | 📸 the saved image itself (or the fallback card), and A / B / C |
| 12 | With a date selected in the calendar, ask: "Why is that day over?" (or "What did I spend that day?"). Then: "How much can I safely spend per day?" | ChatGPT knows which date and month you are looking at; the safe amount equals the calendar's average a day. | 📸 the answer |

Optional: "Show my financial calendar for next month" before saving next
month's budget → the card says there is no saved plan and offers to ask
ChatGPT to plan it.

## What to send back

For each step: **pass**, or what you saw instead (a screenshot helps more than
a description), plus A / B / C for step 11, the device (phone model, ChatGPT
app version, or browser), and the test address so Claude can delete the
account afterwards.

## Known on staging, by design

* Labels are English; amounts and dates follow the account's currency and
  timezone.
* `MCP_WIDGET_DOMAIN` is not set: ChatGPT uses its shared sandbox origin. A
  dedicated origin is set at submission.
* The starter prompts are part of the plugin package, which a developer-mode
  connector does not use: step 4 types the prompt instead of tapping it.
* MITA's plan and its daily average can disagree when bills are paid on a
  date other than where the plan put them (F-8; proposal awaiting your
  decision, `f8-money-model-proposal.md`). The calendar shows both, labelled.

Reference screens from the local MCP Apps host (**not ChatGPT**):
`docs/chatgpt-app/review/calendar-v1/`; the sign-in page:
`docs/chatgpt-app/review/auth-ui-v4/`.
