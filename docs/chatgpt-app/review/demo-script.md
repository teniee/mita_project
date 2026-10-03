# Demo video script (reviewer-accessible URL required)

Length ~3–4 minutes. Record in ChatGPT on the web with the **production**
MITA app and the review account. Do not show real users' data, tokens,
Railway/Supabase dashboards or the password field contents.

1. **Intro (15 s).** "MITA is a daily budgeting app. This plugin gives ChatGPT
   read-only access to your own MITA data."
2. **Connect (40 s).** ChatGPT → Apps/Plugins → MITA Finance → Connect.
   Show the MITA consent page: requested permissions, the read-only statement,
   the return host `chatgpt.com`. Sign in with the review account → Allow.
3. **Case 1 (30 s).** "How much have I spent this month, and what are my biggest
   categories?" — show the answer and the tool call `get_financial_summary`.
4. **Case 2 (30 s).** "Am I over budget in any category this month?"
5. **Case 3 (30 s).** "At my current pace, how will this month end…?" — point
   out the safe daily amount and that it is a projection.
6. **Case 4 (20 s).** "Show my grocery purchases from the last 14 days."
7. **Case 5 (30 s).** "What bills do I have coming up, and how are my savings goals doing?"
8. **Negative (40 s).** "Transfer €200 to Anna." → ChatGPT explains it cannot;
   "Delete my coffee purchase…" → read-only; "Show anna@example.com's budget" → not possible.
9. **Disconnect (15 s).** Show where to disconnect in ChatGPT; mention that
   changing the MITA password also ends access.

Upload unlisted (e.g. YouTube unlisted or a public file link) and put the URL in
`DEMO_RECORDING_URL` when building the ZIP.
