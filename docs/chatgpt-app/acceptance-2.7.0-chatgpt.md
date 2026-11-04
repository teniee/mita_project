# Owner acceptance in real ChatGPT — MITA 2.7.0 on staging (phone first, ≈ 45 minutes)

Everything verified for 2.7.0 so far ran in tests and in a **local MCP Apps
host** (`review/calendar-v3/`, labelled "not ChatGPT"). OpenAI requires
plugins to "function reliably in ChatGPT on both desktop and mobile,
including any UI components", so nothing here counts as passed until it has
been run in real ChatGPT. The Result column starts empty on purpose.

Product under test: the **ChatGPT MITA Finance MCP App** (interface: the
HTML/CSS/JS calendar component `ui://mita/financial-calendar-v3.html`;
backend: the Python MCP service, the shared budgeting engine and PostgreSQL).
The Flutter app is legacy and not part of this run.

## Before you start

* `https://mita-mcp-staging-staging.up.railway.app/health` says
  `"version":"2.7.0"` (until then staging runs 2.6.0 and steps B–E cannot
  pass; `staging.md` → "MCP 2.7.0 — release").
* Server: `https://mita-mcp-staging-staging.up.railway.app/mcp`. In ChatGPT:
  plugin **MITA (staging)** → **Refresh**, then start a **new** conversation
  (ChatGPT may keep the v2 calendar template for up to an hour).
* Part A–D use a **new fictional account** (`ab270-<date>@example.test`).
  Part E is your own staging account and changes nothing until you say
  "save".
* Phone first (ChatGPT app: note the app version and the phone), then the
  computer (chatgpt.com, any browser). Note the start time so the logs can be
  matched. Take the 📸 screenshots.

## A — the connection and the tool list

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| A1 | Refresh the plugin; open its tool list. | 25 tools, including `save_spending_patterns`, `get_calendar_month`, `show_financial_calendar`. | tool list | |
| A2 | Create the fictional account on MITA's page. | You land back in ChatGPT connected, no page in between; the usage box was unticked. | — | |

## B — bills are paid only by their own payment

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| B1 | "I earn €2,000 net a month and save €500. I pay a car loan of €270 on the 15th, a laptop loan of €70 on the 25th and my phone, €30, on the 10th." → "Build my budget for this month." | The preview lists the three payments as their own lines on their due dates, says nothing is saved; ChatGPT asks before saving. | preview | |
| B2 | Approve the save. "I bought a turbo pipe for the car, €60, today." | Recorded as ordinary car/transport spending. ChatGPT may ask whether it paid the car loan; answer **"No, it's a part, not the loan."** It is **not** linked. | answer | |
| B3 | "How much can I safely spend per day?" then "Show my financial calendar for this month." | **Held for bills still includes the whole €270 car loan** (€370 for all three until any is paid). The car-loan date shows it unpaid. | inline card | |
| B4 | "I paid the phone bill, €30, today — that was the phone payment." | ChatGPT links that expense to the phone payment (it says so). Held for bills falls by €30 only; the average a day does not jump. The phone date shows **recorded**. | calendar | |

## C — planned purchases, approximate patterns and flexible budgets

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| C1 | "My budget lines: fuel €200, cigarettes €200, coffee and walks €100, groceries €200." → "I buy groceries every Wednesday." → "I refuel about once a week, around €50." → preview. | Groceries: one purchase each Wednesday, the €200 split exactly (4 × €50.00 in Nov 2026). Fuel: four dates **labelled proposed by MITA** (4/11/18/25), €200 exact. Cigarettes and coffee: **flexible** — no purchase dates, a daily guide instead. | preview | |
| C2 | "I don't have medical insurance." → preview again. | Medical insurance is left out; the preview says how much that **freed** and where it went (other lines by MITA's usual shares, or unallocated) — nothing is moved silently. "Put the freed money into groceries" → ChatGPT sets groceries to an exact amount and previews again. | freed money | |
| C3 | Save. Open the calendar (fullscreen) and tap a future date **with nothing scheduled**. | The date shows **≈ €X** muted (the flexible budgets' daily guide — "guidance, not a purchase"), never €0 and never an invented purchase. A Wednesday shows the groceries purchase; a fuel date shows the purchase with a **proposed** mark. | the date's detail | |
| C4 | "I spent €90 on cigarettes today." (early in the month) → "How am I doing?" / the calendar's breakdown. | Cigarettes: within its €200 but **faster than its pace** (spent per day vs the planned pace), the revised safe pace per day shown; no other line pays for it. Spending past €200 shows **over its limit**. | breakdown | |

## D — the calendar v3 on a phone and on a computer

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| D1 | Inline card on the phone (portrait). | Nothing cut off; whole euros in the grid, said under it; today highlighted; Open calendar and Save as PNG reachable. Check at the narrowest phone you have (320/360 px class) and a large one (390/430 px class). | inline ×2 | |
| D2 | Fullscreen: tap past, today, future dates; ‹ / › months. | Past/today: spent of planned; future: plan or the ≈ guide; bills by state (recorded / overdue / due today / upcoming / later), reminders 5 days ahead; next month without spending. | fullscreen | |
| D3 | Category filters: a planned line, a flexible line, Show all. | The grid redraws per line; a flexible line shows its daily guide, not dates. | filtered | |
| D4 | Dark mode (phone and computer). | Readable; nothing white-on-white; accents only. | dark | |
| D5 | Save as PNG (fullscreen, then inline). | A download/save **or** the image in the card with "Press and hold it (or right-click) to save"; the image is complete and has no merchant names. | image | |
| D6 | Computer (chatgpt.com): repeat D1–D5. | Same figures as on the phone. | desktop | |

## E — your own November (staging): read-only first, save only on your word

Deploying 2.7.0 changes none of your stored rows. Your saved November keeps
its 2.6.0 **layout** (which dates and lines hold the money: bills under
their categories, no planned/flexible kinds, per-date rebalancing) until you
save it again. The **payment rule** applies from the deploy on, to every
month: only an expense you link to a saved payment pays it, so in every
figure the €60 part and the €23.50 cosmetics stop counting as loan payments
(the reserve goes from 286.50 to 370.00 without anything being written).
The next expense you record re-derives November's in-month adjustments under
that rule: the €60 part becomes ordinary spending on 2 Nov, covered by the
legacy per-date rebalancing from later everyday dates, as any unplanned
purchase is; your base plan, your own lines and your expenses stay as they
are.

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| E1 | New conversation: "Show my November budget again — preview only, don't save." | A **preview** (not saved): each saved payment on its own line and due date; your own lines exact; lines without a stated pattern flexible. Expected from the reconstruction of your month used in development (fictional copy, not your rows): held for bills **€370.00** (the €60 turbo pipe and the €23.50 cosmetics do **not** pay the loans), left about €1,041, about €38.56 a day on 3 Nov — your real figures may differ by what you recorded since. | preview | |
| E2 | Compare with the calendar you have now (2.6.0 layout). | You understand every difference (the preview's notes say which lines moved and why). | — | |
| E3 | Only if you agree: "Save it." | ChatGPT asks for approval (save overwrites the month); after it, the calendar shows the 2.7.0 layout. If you do **not** agree, say so: nothing is changed. | approval | |
| E4 | Optional: tell ChatGPT which recorded expenses paid the phone and each loan. | Each link is your statement; ChatGPT never links the €60 part or the €23.50 cosmetics on its own. | — | |

## Negative checks (any account)

"Transfer €200 to Anna." · "Show me anna@example.com's budget." · "Mark my
car loan paid with the turbo pipe" (you can say it, but ChatGPT should
confirm the expense really paid the loan) — no transfer, no one else's data,
no invented payment.

## After the run

Tell the operator the time window; the logs are checked for e-mails, tokens,
amounts and line names (none expected) and the fictional account is deleted
with `e2e_v2.cleanup`.
