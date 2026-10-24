# Owner test — the v4 sign-in page and the financial calendar in ChatGPT (≈ 15 minutes, staging)

Staging only: `https://mita-mcp-staging-staging.up.railway.app/mcp` (MCP 2.2.0).
Use a fresh test address (for example `cal-1024@example.test`) — never a real
one — and a password that meets the four rules shown on the page. Do it on the
phone first (ChatGPT's app), then on the computer.

| Step | Do | Look for |
|---|---|---|
| A | ChatGPT → Settings → Apps → **MITA (staging)**: refresh it (or disconnect and **Connect** again if ChatGPT offers no refresh). The new tools are `get_calendar_month` and `show_financial_calendar`; the permissions are unchanged. | The app lists the calendar tools. |
| B | While connecting, look at the sign-in page for ~5 seconds before touching anything. | Navy hero: the yellow MITA logo, "Know what you can **safely spend** each day.", the family photo with the tilted October calendar and four MITA figures (Savings kept, Safe to spend €62.10 a day, Groceries, Home internet due 27 Oct), "Fictional example". On a phone the yellow **Connect ↓** pill (top right) and **Connect MITA ↓** jump to the form. The motion plays once and settles; with iOS Reduce Motion on, the page is still. |
| C | **Create account** with the test address and connect. | Straight back to ChatGPT, connected (no page in between). |
| D | In a new chat, set up a month quickly: "I earn €3,200 net a month and want to save €400." → "My rent is €850 on the 1st and my internet is €30 on the 27th." → "Build my budget for this month." → confirm the preview → "I spent €38.40 at Lidl on groceries today and €12.50 on lunch." | MITA saves the profile, the two regular payments and the reviewed budget, then the two expenses. |
| E | **"Show my financial calendar for this month."** | An inline card: the month, the average a day ("a day on average · N days left"), Left to spend / Spent / Savings kept, a small calendar with an amount on each date, today in yellow, the internet bill noted, **Open calendar** and **Save as PNG**. ChatGPT adds only a short comment (the figures are on screen). |
| F | **Open calendar** (fullscreen). Tap today, a past date and a future date; tap **How is this worked out?**; tap a category (e.g. Groceries) and **Show all**; **More**; **›** (next month), **This month**. | Each date: what was spent against its everyday plan (or "plan" for a date ahead — never a forecast), its expenses with merchants, money set aside shown apart, bills due. The filter redraws every date for that category. Next month loads (planned, no spending). |
| G | **Save as PNG** (inline or fullscreen). | Tell us what ChatGPT did: a download prompt, a file that opens, or the image shown in the card with "Press and hold it (or right-click) to save". Any of the three is expected; the image shows the month, totals, categories and "Generated …", with no merchant names. |
| H | Ask a follow-up while a date is selected: "Why is that day over?" | ChatGPT knows which date and month you are looking at. |
| I | "How much can I safely spend per day?" | The same amount as the calendar's average a day. |
| J | Switch ChatGPT to dark appearance and open the calendar again. | Readable in dark mode; the primary button turns yellow. |

Optional: "Show my financial calendar for next month" before saving next
month's budget — the calendar says there is no saved plan and offers to ask
ChatGPT to plan it.

Send back: approve, or what to change — screenshots of the card, the
fullscreen calendar and the saved image help. Reference screens (local MCP
Apps host, not ChatGPT): `docs/chatgpt-app/review/calendar-v1/`; the sign-in
page: `docs/chatgpt-app/review/auth-ui-v4/`.

Known on staging, by design: labels are English; `MCP_WIDGET_DOMAIN` is not
set (ChatGPT's shared sandbox origin — a dedicated one is set at submission);
MITA's own figures can disagree in one known way — see "What the calendar
shows that MITA's model does not reconcile" in `financial-calendar.md`
(backend finding F-8). Delete the test account afterwards (ask Claude; it is
removed from the staging database).
