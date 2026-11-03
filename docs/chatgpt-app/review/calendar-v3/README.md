# Calendar component v3 — local render check (2026-11-04)

`ui://mita/financial-calendar-v3.html` (MCP 2.7.0, `behavioral-budget.md`),
rendered with REAL tool results: a fictional account on the local test
database (income 2,000, savings 500; Phone 30 on the 10th, Car loan 270 on the
15th, Laptop loan 70 on the 25th; Fuel every Friday and Groceries every
Wednesday as planned purchases, Cigarettes and Coffee and walks as flexible
budgets, medical insurance and public transport marked not applicable; a €60
car part, cigarettes, coffee and a €43 shop recorded), the month dumped from
`show_financial_calendar` and `list_transactions` on 12 November.

**Not ChatGPT and not the full review harness.** A minimal MCP Apps test host
(iframe sandboxed with `allow-scripts`, answering `ui/initialize`, one tool
result and the component's `tools/call`) in headless Chromium (Playwright
1.49.1); no console errors in any state. `scripts/mcp/calendar_widget_review.py`
(axe, keyboard, PNG export, 320/360 px) was NOT run: it needs the MCP service
running over HTTPS (locally or on staging), which this change did not deploy.
Run it before the owner's real-ChatGPT check.

| File | What it shows |
|---|---|
| `phone-inline-12nov.png` | 390 px inline card: dates ahead show only planned purchases and bills (13 Fuel 50, 15 Car loan 270, 18/27 Groceries 50, 25 Groceries 50 + Laptop loan 70); no fabricated amounts; the car loan not paid by the car part |
| `phone-fullscreen-11nov.png` | a past Wednesday: €50 planned shop "nothing recorded", the flexible share labelled as guidance; bills paid / overdue / in 3 days |
| `phone-fullscreen-dark-18nov.png` | dark mode, a date ahead: the planned purchase, flexible budgets as "about €X a day" with what is left, no flexible "purchases" |
| `desktop-fullscreen-15nov.png` | 1280 px: the car loan's due date (Everyday plan €22.20 + Bills due €270.00 = €292.20) |
