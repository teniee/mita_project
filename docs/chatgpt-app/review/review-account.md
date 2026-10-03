# OpenAI review account

OpenAI requires "a login and password for a fully featured demo account that
includes sample data", usable "without MFA approval, email or SMS codes, magic
links, or private-network access". Credentials go into the dashboard's
**Review details** form — **never into git, the plugin ZIP or this file.**

## Why the owner creates it by hand

Scripts that create data are blocked from production by
`scripts/_target_guard.py` with no override (production previously filled with
synthetic accounts). The review account is one deliberate production account,
created through the normal app UI so every figure is produced by MITA's own
code. `scripts/mcp/seed_review_account.py` creates the identical dataset on a
local or staging API for rehearsing the demo.

## Account

* E-mail: a dedicated mailbox the owner controls on an owned domain, e.g.
  `chatgpt-review@<owned domain>` (not `mita.finance`).
* Password: ≥16 random characters; no MFA (MITA has none).
* Do **not** sign in with Google for this account — the ChatGPT consent page
  accepts MITA e-mail/password only.
* Premium: required to create goals (`POST /api/goals/` returns 402 otherwise).
  See OWNER_ACTIONS O-10.

## Data to enter (in the app, within the current month)

Onboarding: monthly income **4,200**; rent **1,100**; utilities **150**;
dining out 6×/month; savings goal **300**/month.

Expenses (merchant as written):

| Category | Amount | Merchant | Mark recurring |
|---|---|---|---|
| groceries | 18.40 | Fresh Market | |
| dining | 6.20 | Corner Cafe | |
| groceries | 54.90 | Fresh Market | |
| subscriptions | 15.99 | StreamFlix | yes |
| transportation | 38.00 | City Transit | |
| dining | 72.35 | Bistro 21 | |
| groceries | 41.10 | Green Grocer | |
| shopping | 120.00 | Outdoor Store | |
| dining | 9.50 | Corner Cafe | |
| groceries | 63.25 | Fresh Market | |
| utilities | 45.00 | City Power | |
| entertainment | 25.00 | Cinema Plaza | |

Total **509.69**. Goal: "Emergency fund", target 3,000, saved 900, monthly
contribution 300, target date ~8 months ahead, priority high (one goal only —
see backend-findings F-1). Scheduled: rent 1,100 "Maple Apartments", first of
next month, monthly; insurance 240 "SafeCar Insurance", ~20 days ahead, once.

Expected (verified locally on 2026-10-02 against the real API + MCP service):
`get_financial_summary` → spent 509.69, 12 transactions, stated income 4200.00,
plan generated; `list_transactions` total 509.69; `get_recurring_expenses` →
rent monthly, insurance one-time, StreamFlix marked recurring; `get_goals` →
Emergency fund 900/3000 on track.

## Keep it current

The review may happen weeks after submission. In the week before submitting,
add a few expenses dated in the current month so "this month" is populated,
and confirm the five positive cases still produce sensible answers. If a new
month started and the app has not been opened, open it once so MITA
materializes the month's plan (the MCP service is read-only and never does).
