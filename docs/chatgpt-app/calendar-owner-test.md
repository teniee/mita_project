# Owner acceptance in real ChatGPT — MITA 2.3 on staging (≈ 20 minutes)

Everything Claude verified so far ran in a **local MCP Apps host** (a test page
that behaves like ChatGPT, labelled "not ChatGPT"). Only this test shows what
ChatGPT itself does. Until it passes, nobody may say the calendar works in
ChatGPT.

* Server: `https://mita-mcp-staging-staging.up.railway.app/mcp`. **Before you
  start**, staging must run the commit that holds R3 and the final connect
  page (MCP 2.3.0; `/health` says `"version":"2.3.0"`) with
  `MCP_WIDGET_DOMAIN` set to the staging origin, so the calendar is tested
  the way it will be submitted. On 2026-10-26 staging still ran `dbdc118`
  (2.2.0, the v4 page, the usage box pre-ticked): deploy first (owner).
* Use a **new fictional address** (for example `cal-1025@example.test`) and a
  password with upper and lower case, a digit and a symbol. Never a real address.
* Do it on the phone first (ChatGPT app), then repeat steps 4–12 on the computer.
* Take the screenshots marked 📸; they are the evidence. Note the time you
  started, so the server logs can be matched.

| # | Do | Pass when | Record |
|---|---|---|---|
| 1 | ChatGPT → Settings → Apps → **MITA (staging)** → refresh it (or disconnect and **Connect** again). Open the app's details. | The tool list includes `get_calendar_month` and `show_financial_calendar` (24 tools). | 📸 tool list |
| 2 | While connecting, look at the sign-in page, then switch to **Create account**. Leave the usage-statistics box as it is (unticked) and create the account. | Cream first screen: logo, "Know what you can safely spend each day.", the question "How much can I safely spend per day?" and MITA's answer (€59.60 a day · 12 days left, "Fictional example"), a yellow Connect button; below, four things to ask (Plan, Track, See, Decide), then the form. The usage box is **unticked**; on the Sign-in tab its text ends "Leaving it unticked keeps any choice I made before." You land back in ChatGPT, connected, with no page in between. | 📸 first screen, 📸 the form with the unticked box |
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
| 13 | Bills first: in fullscreen open **How is this worked out?** Then say "I paid my rent of €850 on the 1st." and show the calendar again. | Before: a "− Held for bills" row (rent €850 and internet €30 — saved payments and stated rent/utilities only; the plan's medical-insurance allowance is everyday money and is not held) and the callout "… is held for bills not recorded as paid yet". After recording rent: the held amount falls by €850 and Spent rises by €850, so Left to spend and the average a day **do not change** — the bill was already out of them. | 📸 before and after |

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
* `MCP_WIDGET_DOMAIN` must be set (see "Before you start"): OpenAI requires a
  dedicated, unique origin for an app with UI at submission, so the calendar
  is accepted only under one.
* The starter prompts are part of the plugin package, which a developer-mode
  connector does not use: step 4 types the prompt instead of tapping it.
* MITA's plan and its daily average can disagree when bills are paid on a
  date other than where the plan put them (F-8; your decision 2026-10-25:
  ChatGPT shows exactly what the app implements, no rebalancer change). The
  calendar shows both, labelled.
* Bills held out of the average (R3, `r3-bills-reserve.md`): saved regular
  payments and stated rent/mortgage/utilities until recorded; the plan's
  medical-insurance allowance is everyday money.

Reference screens from the local MCP Apps host (**not ChatGPT**):
`docs/chatgpt-app/review/calendar-v1/`; the sign-in page:
`docs/chatgpt-app/review/auth-ui-v5.2/`.
