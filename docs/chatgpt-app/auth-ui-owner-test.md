# Owner test — the new MITA sign-in page in ChatGPT (≈ 5 minutes, staging)

Visual and UX check of the redesigned connection page, not another
acceptance suite. Staging only: `https://mita-mcp-staging-staging.up.railway.app/mcp`.
Use a fresh test address (for example `ui-1021@example.test`) — never a real
one — and any password that meets the four rules shown on the page.

| Step | Do | Look for |
|---|---|---|
| A | ChatGPT → Settings → Apps → **MITA (staging)** → disconnect, then **Connect**. The connection made before 2026-10-23 no longer works: staging's keys were rotated after Railway's security incident. | ChatGPT opens MITA's page. |
| B | Before typing anything, look for ~10 seconds — on the phone first (ChatGPT opens the page there), then on the computer. | Phone: MITA logo, "Your finances, remembered in ChatGPT.", one short example ("€66.70 a day", marked Example), then the sign-in card. Computer: the same, with the card on the right. Further down: the daily-pacing calendar, with the calculation and "Your €400.00 of savings is never counted as money to spend." Does it read as MITA? |
| C | Choose **Create account**. Type the e-mail and a password, and a *different* confirmation once. | The mismatch is explained and only "Confirm password" is marked. Then enter matching passwords. |
| D | Read the box **ChatGPT will be able to** before continuing, then open **View permission details**. | Five plain-language permissions and "MITA can't move money or access banks." on screen; the details open in place. Untick usage statistics if you prefer — both are fine. |
| E | Press **Create account and connect**. | You go straight back to ChatGPT, connected — there is deliberately no page in between. |
| F | In a new chat: "Help me build my monthly budget." | MITA starts the budget setup (asks about income or regular payments). |
| G (optional) | After saving a budget with a savings amount: "How much can I safely spend per day?" | A per-day figure that leaves your savings out (the forecast's `savings_set_aside`), not one that spends them. |

Optional: disconnect, connect again and use **Sign in** with the same account;
try a wrong password once (generic "Sign-in failed" message, both fields marked).

Send back: approve, or what to change (a screenshot helps). Reference
screenshots of every state are in `docs/chatgpt-app/review/auth-ui-v2/`
(staging runs `1e24bf4` since 2026-10-23); they were taken with a support
link configured, so they show "Need help? Contact MITA support" (and "Help"
on error pages), which staging does not set (`MCP_SUPPORT_URL`).
