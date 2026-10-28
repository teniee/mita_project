# OpenAI review account

OpenAI requires "a login and password for a fully featured demo account that
includes sample data", usable "without MFA approval, email or SMS codes, magic
links, or private-network access". Credentials go into the dashboard's
**Review details** form — **never into git, the plugin ZIP or this file.**

## Why the owner creates it by hand

Scripts that create data are blocked from production by
`scripts/_target_guard.py` with no override (production previously filled with
synthetic accounts). The review account is one deliberate production account
whose data is entered through MITA's own product — ChatGPT (v2 tools) or the
app — so every figure is produced by MITA's code.
`scripts/mcp/seed_review_account.py` (REST) and `scripts/mcp/e2e_v2.py` (the
ChatGPT tools) create equivalent data on local or staging for rehearsal.

## Account

* E-mail: a dedicated mailbox the owner controls on an owned domain, e.g.
  `chatgpt-review@<owned domain>` (not `mita.finance`).
* Password: ≥16 random characters; no MFA (MITA has none).
* Create it on MITA's sign-in page in ChatGPT (**Create an account**) or in
  the app with e-mail and password — never "Sign in with Google": the
  ChatGPT page accepts MITA e-mail/password only.
* Currency **EUR**: the five review prompts use €, and MITA records amounts
  in the account currency without converting.
* No Premium needed: goals are free in ChatGPT. (The app's own goal screen
  still requires Premium — create the goal in ChatGPT.)

## Data to enter (ChatGPT, custom connection to the production MCP, current month)

Enter it in one conversation, confirming each write when ChatGPT asks:

1. "My net income is €4,200 a month, my currency is euro, my timezone is
   Europe/Sofia, there are two of us and I want to save €300 a month."
2. "My rent is €1,100 to Maple Apartments every month on the 1st.
   StreamFlix is €15.99 every month on the <day>. Car insurance from
   SafeCar Insurance is €240 once, on <date about 20 days ahead>."
3. "Build my budget for this month." → review → "Save it."
4. "Record these expenses" with the dates (all within the current month):

| Category | Amount | Merchant |
|---|---|---|
| groceries | 18.40 | Fresh Market |
| dining | 6.20 | Corner Cafe |
| groceries | 54.90 | Fresh Market |
| subscriptions | 15.99 | StreamFlix |
| transportation | 38.00 | City Transit |
| dining | 72.35 | Bistro 21 |
| groceries | 41.10 | Green Grocer |
| shopping | 120.00 | Outdoor Store |
| dining | 9.50 | Corner Cafe |
| groceries | 63.25 | Fresh Market |
| utilities | 45.00 | City Power |
| entertainment | 25.00 | Cinema Plaza |

5. "I want to save €3,000 for an Emergency fund by <date about 8 months
   ahead>; I already have €900." (One dated goal only — backend-findings F-1.)

Expected: `get_financial_summary` → spent 509.69 EUR, 12 transactions, stated
income 4200.00, plan saved; `list_transactions` total 509.69;
`get_recurring_expenses` → rent and StreamFlix monthly, insurance one-time;
`get_goals` → Emergency fund 900/3000.

With this data the review's calendar case (positive case 3) shows a filled
month: rent and StreamFlix on their dates, the budget lines, the expenses on
their days, and the savings set aside.

## Keep it current

The review may happen weeks after submission. In the week before submitting,
add a few expenses dated in the current month so "this month" is populated,
and confirm the five positive cases still produce sensible answers. If a new
month has started, save that month's budget in ChatGPT ("Build my budget for
this month" → "Save it") or open the app once — MITA's read tools never
create a month's plan by themselves.
