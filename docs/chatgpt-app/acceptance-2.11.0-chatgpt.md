# Owner acceptance in real ChatGPT — MITA 2.11.0 on staging (phone first, ≈ 25 minutes)

What 2.11.0 changes is in `calendar-guidance-layer.md`: the calendar shows two
layers that are never merged — what you spent and what is scheduled (the
date's **amount**), and, apart from it on today and the days ahead, **what is
left per day on average** in your flexible budgets, marked **≈**. It is
called an average because it is one (what is left ÷ the days left): MITA has
no method yet that tailors a daily figure to your habits, income, country or
pay days (§2 and §8 of that document). A €1.50 coffee keeps its cents on a
phone. Tests and the local renders (`review/calendar-v5/`) are not ChatGPT:
nothing here counts as passed until it has run in real ChatGPT on a phone.
The Result column starts empty on purpose. The 2.10.0 script
(`acceptance-2.10.0-chatgpt.md`) still applies for what a date's amount is;
where it says "There is no ≈ figure in any date", read this script instead.

## Before you start

* `https://mita-mcp-staging-staging.up.railway.app/health` shows
  `"version":"2.11.0"` — deployed 2026-11-16 17:22 UTC (`65adcd9`, deployment
  `da577082`; `staging.md` → "MCP 2.11.0 — deployed").
* In ChatGPT, open the plugin **MITA (staging)**, tap **Refresh** (the tool
  descriptions and the component changed: the calendar is now
  `ui://mita/financial-calendar-v5.html`), then start a **new** conversation.
  A card left open in an old conversation still shows the old drawing — judge
  only a calendar opened after the refresh.
* Part A is **your own staging account**, read-only: nothing in it changes.
  Parts B–C use a **new fictional account** (`cal211-<date>@example.test`).
* Phone first (note the ChatGPT app version and the phone's width), then the
  computer. Note the start time, so the logs can be matched.
* To check any figure yourself: **a budget's average = what is left in it ÷
  the days left in the month, today included**; the "All categories" average
  = those added up, never more than the safe average a day.

## A — your own November (nothing is written)

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| A1 | "Show my financial calendar for November." Look at the card in the chat. | Amounts keep their cents: a coffee is **1.50**, never **2**; a whole amount may show without ".00" (40). From **today on**, each date has a small tinted pill **≈ N** under its amount (or alone on an empty date). The line under the grid says it is the average left per day, not a recommendation. | card | |
| A2 | Open it fullscreen. Stay on **All categories**. | Dates so far: what you recorded. Dates ahead: only what is scheduled — car loan **270.00 on the 15th**, laptop loan **70.00 on the 25th**, a purchase only where you stated when you buy. The **≈** pill is the **same figure on today and every date ahead**, equal to "≈ €… a day on average" in the summary. The caption ends "≈ marks the average left per day from today: an average of what is left, not a plan." Nowhere does the calendar say "guidance", "guide" or "recommended". | calendar | |
| A3 | Tap **Restaurants** (behind "More" on a phone). | **No 3.33 / 3.34** as an amount on any date; an amount only where you recorded a restaurant expense. The **≈** pill on today and ahead is Restaurants' **left ÷ days left, today included** (e.g. 50.00 left with 18 days → 2.78; a phone may show ≈3). The banner: "flexible budget · spent … of 100.00 this month · … left · ≈ €… a day on average · no purchase dates". | filter | |
| A4 | Tap **Groceries**, then **Car maintenance**, then **Entertainment**. | Same rule: amounts = what you recorded only; ≈ = that budget's left ÷ days left. **Car maintenance** shows no purchase and no date — only its month and its average. | one of them | |
| A5 | Tap **Coffee**. | If you told MITA you buy coffee **every day**: 1.50 on each date ahead and **no ≈ pill** (its money is on its dates). If you never said when: it is a flexible budget with its own ≈. Tell me which you see. | filter | |
| A6 | "Show all". Tap the **15th**. | "Bills due on this date": car loan 270.00, not marked paid unless you linked its payment. "Planned purchases + Bills due = Scheduled for the date". Then a separate box "**Average left per day**": ≈ €… "a day on average in your flexible budgets", how it is worked out, and "**It is an average of what is left, not a recommendation: not part of the €… scheduled for this date, and nothing is taken from your balance.**" No figure anywhere equals the bill plus the average. | detail | |
| A7 | Tap a date ahead with nothing scheduled. | "Nothing scheduled — No purchase or bill is planned for this date." Then the average box ("nothing is scheduled for it"), then "Flexible budgets · this month" with each budget's "≈ €… a day". | detail | |
| A8 | Tap the switch **Daily average** (above the grid) to **Off**. | Every ≈ pill disappears; every amount stays exactly as it was; the caption says "The daily average is hidden." Switch it **On** again. Close and reopen fullscreen: the switch keeps your choice (if ChatGPT keeps the card's state — tell me if it does not). | off / on | |
| A9 | In the summary tap **How is this worked out?** | Plan − Spent − Protected savings − Held for bills = Left to spend **÷ Days after today** = On average a day; then Flexible budgets left **÷ Days left, today included** = **Average left per day** ≈ €…, and "It is arithmetic, not a recommendation". The two "days" differ by one — today. | summary | |
| A10 | **Save as PNG**, then again with the switch off. | First image: each date from today has its amount and, apart, a "≈ …" pill, and a legend line "Average left per day: … not a plan or a recommendation". Second image: no ≈ anywhere, amounts unchanged. | both images | |
| A11 | Dark mode (phone settings), open the calendar again. | The ≈ pills, the switch and the amounts are all readable. | dark | |
| A12 | "How much can I spend on restaurants per day?" | ChatGPT: about €… a day **on average** (what is left ÷ days left) — not a recommendation, not a limit. It does not claim MITA tailored it to your income or country. | answer | |
| A13 | "Is that daily amount personalized for me?" | ChatGPT says it is an average of what you have left over the days left; it accounts for your bills and savings (the cap) but not your habits, income level, country or pay days. | answer | |
| A14 | "What is planned for 20 November?" | Only what is scheduled (nothing, or a stated purchase). If it mentions the average, it calls it an average, not a plan. | answer | |
| A15 | "Did anything in my budget change?" | Your lines and amounts, the 380 you left unallocated and savings 500.00 are unchanged. Nothing was saved by this session. | answer | |

## B — a new fictional account: averages from the first day

| # | Do | Pass when | Result |
|---|---|---|---|
| B1 | New account. "I earn 2,000 euros a month, I live alone in Bulgaria, I save 300." → "My budget lines: restaurants 100, groceries 320, coffee 45. That is what I spend on." → preview → "Save it." → "Show my calendar." | No amount on any date (nothing recorded or scheduled), and **every date from today has the same ≈ pill** = (100 + 320 + 45) ÷ days left, today included. | |
| B2 | "I spent 40 at a restaurant today." → calendar → **Restaurants**. | **40.00 on today only**; ≈ on today and ahead = 60.00 ÷ days left (today included). All categories: the ≈ went down accordingly. Today is not marked over. | |
| B3 | "I buy a coffee every day, about 1.50." → preview → "Save it." → calendar. | **1.50 on every date** (never "2"), the Coffee filter has **no ≈**, and the All-categories ≈ no longer counts coffee (restaurants + groceries ÷ days left). | |

## C — when the month has less than the budgets show

| # | Do | Pass when | Result |
|---|---|---|---|
| C1 | Same fictional account: "I spent 1,200 on a new phone" (no budget line for it). → calendar. | The budgets still show what they hold, but the All-categories ≈ drops to the **safe average a day** (or 0); the summary says "(the safe average)", and under the grid it says why ("after bills and savings the month as a whole has less left…"). | |
| C2 | Filter **Groceries**. | Its own ≈ (its left ÷ days left) and, in the banner, "all flexible budgets together ≈ €… a day (the safe average)". | |

## After

Note the end time. The operator then checks the logs for that window: no
error-level line, no amount, e-mail or token. The fictional account of parts
B–C is deleted with `e2e_v2.cleanup` the next time database access is
authorised (listed in `staging.md` → "Left on staging").

If anything differs — above all **an amount on a date that is neither
recorded, a bill nor a purchase you scheduled**, a **≈ figure added into a
date's amount or total**, a **daily figure called a recommendation or
guidance**, or a **small amount without its cents** — send a screenshot and
the date. And tell me whether you want a personalized daily method (§8 of
`calendar-guidance-layer.md`): that is a decision, not part of this release.
