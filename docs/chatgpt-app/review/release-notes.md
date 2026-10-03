# Release notes — MITA Finance plugin 1.0.0

(Also in `plugin.template.json` → `publication.release_notes`.)

**1.0.0 — first release**

* Eight read-only tools over the connected MITA account: `get_profile`,
  `get_financial_summary`, `list_transactions`, `get_spending_breakdown`,
  `get_budget_status`, `get_budget_forecast`, `get_recurring_expenses`,
  `get_goals`.
* Sign-in with MITA e-mail and password through OAuth 2.1 (authorization code
  + PKCE S256), scopes `profile:read` and `finance:read` only.
* No write, payment, transfer or trading capability; no commerce.
* Figures come from MITA's own ledger, budget plan and forecast engine in the
  user's timezone; missing data is reported as missing, never estimated.

Known limitations: accounts created with Google sign-in only cannot connect
yet (no MITA password); a month's budget appears after the MITA app has
generated it; transactions in a currency other than the account's are
summed at face value and flagged.
