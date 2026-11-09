# Owner acceptance in real ChatGPT — MITA 2.9.0 on staging (phone first, ≈ 20 minutes)

What 2.9.0 adds is described in `regional-recommendations.md`. Tests, the
local least-privilege server and the HTTPS smoke runs are not ChatGPT.
Nothing here counts as passed until it has run in real ChatGPT on a phone.
The Result column starts empty on purpose. The 2.8.0 script
(`acceptance-2.8.0-chatgpt.md`) still applies; this one adds only what
changed.

## Before you start

* `https://mita-mcp-staging-staging.up.railway.app/health` shows
  `"version":"2.9.0"` (`staging.md` → "MCP 2.9.0").
* In ChatGPT, open the plugin **MITA (staging)**, tap **Refresh**, then start
  a **new** conversation.
* Parts A–C use a **new fictional account** (`rg290-<date>@example.test`).
  Part D is your own staging account; nothing changes there unless you say
  "save".
* Use the phone first (note the ChatGPT app version), then the computer.
  Note the start time, so the logs can be matched.

## A — a national reference beside your own line

| # | Do | Pass when | 📸 | Result (phone / computer) |
|---|---|---|---|---|
| A1 | New account. Say by **voice**: "I live in Bulgaria, I earn 1,000 euros a month, I live alone." Confirm what ChatGPT repeats back. | It saves the income, the country and a household of 1 only after you confirm. It asks no city or address. | — | |
| A2 | "Build my budget for this month." | MITA's groceries line is about **€78**. ChatGPT says that households in Bulgaria spend about **€152 a month per adult** on food at home (Eurostat, 2020 survey, at 2025 prices). It calls this a national average, not your cost and not a shop price, and offers it as your amount. Nothing is saved. | preview | |
| A3 | "Why is MITA's groceries line lower?" | The answer says MITA's own lines are fixed shares of income that do not adjust for local prices. It does not invent a reason. | — | |
| A4 | "Set my groceries to 150." → preview → "Save it." | Groceries is **150.00** and marked as yours. The plan is saved only after your yes. | saved | |

## B — what MITA refuses to guess

| # | Do | Pass when | 📸 | Result |
|---|---|---|---|---|
| B1 | "How much do people here spend eating out?" | MITA has **no figure** for eating out, and ChatGPT says why: people who never eat out and people who do are mixed in one average. It does not estimate one. If ChatGPT searches the web itself, it says the result is not from MITA. | answer | |
| B2 | "What does a loaf of bread cost at the Lidl in Varna?" | MITA has **no verified local price**. Any web result is labelled as not MITA's and changes nothing. | answer | |
| B3 | "I drive, I spend 200 on fuel." → preview | **Fuel 200.00** stays exactly. Beside it, households that buy fuel spend about **€42 per adult** (a national figure). Nothing is replaced. | preview | |
| B4 | "Actually we are four people at home." → preview | Food at home is shown as a **range, €289–380** for the household, never 4 × €152. | preview | |

## C — other countries and currencies

| # | Do | Pass when | Result |
|---|---|---|---|
| C1 | "Turn off regional statistics." → preview | No reference is shown. **The plan is identical** to the one before. | |
| C2 | (a second fictional account) "I live in the US, I earn 3,000 dollars." → preview | No household-spending reference: MITA has none for the US. **No euro figure is converted.** | |

## D — your own staging account (read-only until you save)

| # | Do | Pass when | Result |
|---|---|---|---|
| D1 | "Preview my November budget" (do **not** save). | Your saved lines and amounts are unchanged. References, where there are any, appear only beside your own lines as suggestions. | |
| D2 | "Show my calendar for November." | The same November you saved, with every expense you recorded. | |

## After

Note the end time. The operator then checks the logs for that window: no
error line, no location, e-mail or amount. The operator also runs
`scripts/mcp/staging_account_fingerprint.py`: your account's digests must
match the ones recorded before the release unless you said "save".
