# Demo video script (reviewer-accessible URL required)

OpenAI (2026-10-27): the review needs "a demo-recording URL that shows the
main use cases and tools across supported platforms". Record against the
**production** MITA server with the review account (or a fresh demo account
created on camera), on the **web** and on a **phone** (ChatGPT app). About
6 minutes. Never show real users' data, tokens, Railway dashboards or a
password being typed in clear.

## Web (chatgpt.com) — about 4½ minutes

1. **Intro (15 s).** "MITA keeps your budget, expenses, recurring expenses and
   goals in your MITA account, so they are there in every conversation."
2. **Connect and sign in (45 s).** Open MITA Finance from ChatGPT's plugin
   directory → Connect. On MITA's page: the five permissions, "MITA cannot
   move money, make payments or connect to your bank", the usage-statistics
   box (unticked); sign in (or **Create account**); back in ChatGPT.
3. **Setup (40 s).** Tap the starter prompt "Set up my monthly budget from
   scratch." → MITA asks only for missing facts; "I earn €2,500 net, there
   are two of us, I want to save €400; my rent is €700 every month on the
   first."
4. **Budget (40 s).** "Build my budget for this month." → the preview (fixed
   obligations, savings, categories, warnings; *not saved*) → "Save it."
5. **Record (40 s).** "I spent €36.80 at Lidl on groceries today." Then
   "Also €8 coffee and €55 fuel." Attach a sample receipt photo: "Add these
   expenses to MITA."
6. **Correct (20 s).** "The coffee was €6, not €8."
7. **Calendar (60 s).** Starter prompt "Show my financial calendar for this
   month." → the inline card → **Open calendar** (fullscreen) → tap today
   (its expenses), a future date (plan only) → the Groceries chip → next
   month and back → **Save as PNG**.
8. **Safe daily amount (20 s).** "How much can I safely spend per day?" — the
   same figure as the calendar's average a day; savings and unpaid bills are
   held out.
9. **History and goal (30 s).** "How have my grocery costs changed over six
   months?" (months before the account show as no data); "I want to save
   €5,000 by June."
10. **Feedback (15 s).** "Tell the MITA team that categories are confusing."
    → ChatGPT asks approval before sending.
11. **Negatives (30 s).** "Transfer €200 to Anna." → not possible;
    "Show anna@example.com's budget" → not possible; "Use my savings goal to
    buy Bitcoin" → not possible.

## Phone (ChatGPT app) — about 1½ minutes

12. **Same account, new conversation (30 s).** "How much have I spent and
    what is my budget?" — the same figures, from MITA.
13. **Calendar on the phone (45 s).** "Show my financial calendar for this
    month." → inline card → fullscreen → a date → Save as PNG.
14. **Control (15 s).** Plugin settings → Disconnect; mention that changing
    the MITA password also ends access, and "stop sharing my usage
    statistics".

Upload unlisted (no sign-in needed to watch) and put the URL in
`DEMO_RECORDING_URL` when building the ZIP.
