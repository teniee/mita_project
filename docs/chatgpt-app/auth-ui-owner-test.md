# Owner test — the new MITA sign-in page in ChatGPT (≈ 5 minutes, staging)

> **Superseded on 2026-10-24** by `calendar-owner-test.md` (sign-in page v4
> and the financial calendar). Kept as the record of the v3 test.

Visual and UX check of the redesigned connection page, not another
acceptance suite. Staging only: `https://mita-mcp-staging-staging.up.railway.app/mcp`.
Use a fresh test address (for example `ui-1021@example.test`) — never a real
one — and any password that meets the four rules shown on the page.

| Step | Do | Look for |
|---|---|---|
| A | ChatGPT → Settings → Apps → **MITA (staging)** → disconnect, then **Connect**. The connection made before 2026-10-23 no longer works: staging's keys were rotated after Railway's security incident. | ChatGPT opens MITA's page. |
| B | Before typing anything, look for ~5 seconds — on the phone first (ChatGPT opens the page there), then on the computer. | "Know what you can safely spend each day." and "Just ask ChatGPT.", then one example marked "Fictional example": €66.70 a day, spent this month, protected savings, days left. The sign-in card starts on the same screen (on the computer: on the right). Can you tell what MITA does and why to connect it? Open "How is €66.70 worked out?" once. |
| C | Choose **Create account**. Type the e-mail and a password, and a *different* confirmation once. | The mismatch is explained and only "Confirm password" is marked. Then enter matching passwords. |
| D | Read the box **ChatGPT will be able to** before continuing, then open **View permission details**. | Five plain-language permissions and "MITA can't move money or access banks." on screen; the details open in place. Untick usage statistics if you prefer — both are fine. |
| E | Press **Create account and connect**. | You go straight back to ChatGPT, connected — there is deliberately no page in between. |
| F | In a new chat: "Help me build my monthly budget." | MITA starts the budget setup (asks about income or regular payments). |
| G (optional) | After saving a budget with a savings amount: "How much can I safely spend per day?" | A per-day figure that leaves your savings out (the forecast's `savings_set_aside`), not one that spends them. |

Optional: disconnect, connect again and use **Sign in** with the same account;
try a wrong password once (generic "Sign-in failed" message, both fields marked).

Send back: approve, or what to change (a screenshot helps). Reference
screenshots of every state are in `docs/chatgpt-app/review/auth-ui-v3/`
(the conversion redesign, on staging since 2026-10-23). They were taken
without a support link, as on staging (`MCP_SUPPORT_URL` is not set there),
so they show no "Need help? Contact MITA support" and no "Help" link on
error pages.
