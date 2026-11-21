# Owner acceptance in real ChatGPT — MITA 2.8.0 on staging (phone first, ≈ 30 minutes)

Personalized onboarding (`personalization-2.8.md`). Tests, the local
least-privilege server and the HTTP smoke are not ChatGPT: nothing here
counts as passed until it ran in real ChatGPT on a phone. The Result column
starts empty on purpose.

## Before you start

* `https://mita-mcp-staging-staging.up.railway.app/health` says
  `"version":"2.8.0"` — deployed 2026-11-04 23:19 UTC (`601a3d7`,
  deployment `618cd6d9`; `staging.md` → "MCP 2.8.0 — deployed").
* Statistics on staging come from Eurostat and the World Bank; the OECD is
  excluded until its licence is confirmed, so a US account sees World Bank
  yearly inflation only. Electricity and gas prices exist for EU, EFTA and
  candidate countries.
* In ChatGPT: plugin **MITA (staging)** → **Refresh**, then a **new**
  conversation. Parts A–C use a **new fictional account**
  (`ob280-<date>@example.test`); part D is your own staging account and
  changes nothing until you say "save".
* Phone first (note the ChatGPT app version), then the computer. Note the
  start time so the logs can be matched. Take the 📸 screenshots.

## A — one message, by voice

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| A1 | Create the fictional account; say "Set up my monthly budget from scratch." | ChatGPT checks what MITA knows and invites you to tell it everything in one go, mentioning voice once. | — | |
| A2 | By **voice**: "I earn about 1,500 euros net a month, paid on the 25th. I rent a flat in Sofia for 600 on the 1st and pay 15 for my phone on the 20th. I don't have a car, I take the bus — the card is 26 a month. Groceries about 250, usually on Saturdays, and I eat out sometimes. I want to save 100." | ChatGPT repeats back what it understood, grouped, amounts as you said them, and asks you to confirm **before** saving anything. It does not ask your city, street or employer. | summary | |
| A3 | "Yes, that's right." | It saves; if ChatGPT shared your location it asks whether you **normally live** in Bulgaria (a question, not a statement). | — | |
| A4 | "Yes, Bulgaria." Then, when asked: "That's everything I regularly spend on." | No question is repeated; nothing about health, family or other private matters is asked. | — | |

## B — the budget fits the person

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| B1 | "Build my budget for this month." | It is called **personalized**; your lines Groceries 250 and Public transport 26 exactly; **no fuel line**; no rent other than your 600; rent and phone on their due dates; nothing saved yet. | preview | |
| B2 | Read what MITA left out. | ChatGPT says MITA did not budget lines you never mentioned (entertainment, clothing, fuel…), says what MITA would suggest, asks once whether any applies — and adds none by itself. The daily figure is the same money, not less. | — | |
| B3 | "Add clothing, about 40 a month." → preview again → "Save it." | Clothing 40 appears as **yours**; the plan is saved only after your yes. | saved | |

## C — answers, not assumptions

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| C1 | New conversation: "What do you know about my budget setup?" | Nothing is asked again; country Bulgaria, your income schedule and lines are known. | — | |
| C2 | "I'd rather not say where I live." | ChatGPT confirms MITA no longer keeps a country; your budget is unchanged. | — | |
| C3 | "My income varies, at least 1,200 a month." → "Show my budget preview." | The preview says MITA still plans on the 1,500 you stated and shows what a 1,200 month would mean; it does not lower anything by itself. | preview | |

## C2 — official statistics (after the first ingestion on staging)

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| R1 | (fictional account, country Bulgaria) "How fast are food prices rising here?" | A national figure with its source and period (Eurostat, a recent month), called a national average — not a shop price, not your cost. | answer | |
| R2 | "How much is electricity per kWh in Bulgaria?" | About 0.13 EUR per kWh (2026-S1), households, taxes included, with its band and source; not called your tariff. | answer | |
| R3 | "What does a loaf of bread cost at the Lidl in Varna?" | MITA says it has no shop prices; if ChatGPT searches the web, it says so and the figure is not MITA's. | answer | |
| R4 | "Build my budget for this month." | Lines like groceries show the national price change next to them as context; no amount moved because of it. | preview | |
| R5 | "Turn off regional statistics." → ask R1 again | No statistics; the budget is unchanged. | — | |

## D — your own staging account (read-only until you save)

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| D1 | In your account: "Check my MITA setup." | You are a returning user: no setup questions; at most an offer to update preferences. | — | |
| D2 | "Show my calendar for November." | Your saved November (bills, lines) with every expense you recorded — including the 6 recorded on 2026-11-05 at 08:11 UTC. | calendar | |
| D3 | "Preview my November budget" (do **not** save). | The same figures as your saved November, marked preliminary with MITA's suggestions labelled as suggestions. | preview | |

## After

Note the end time. The operator checks the logs for the window (no error
line, no location, e-mail or amount) and runs
`scripts/mcp/staging_account_fingerprint.py`: your account's digests must be
identical to the ones recorded before the release unless you said "save".
