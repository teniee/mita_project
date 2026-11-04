# Calendar component v3 — local render check (2026-11-04)

`ui://mita/financial-calendar-v3.html` (MCP 2.7.0, `behavioral-budget.md`),
rendered with REAL tool results for a fictional account on the local test
database, viewed on 9 November: income 2,000, savings 500; Phone 30 (10th),
Car loan 270 (15th), Laptop loan 70 (25th); Groceries every Wednesday and
Fuel "about once a week, ~€50" (dates PROPOSED by MITA: 4, 11, 18, 25) as
planned purchases; Cigarettes and Coffee and walks as flexible budgets;
medical insurance and public transport marked not applicable; recorded: a €60
car part (not the car loan), €95 of cigarettes by 6 Nov (faster than its
pace), coffee, a €43 shop and €48 of fuel.

**Not ChatGPT and not the full review harness.** A minimal MCP Apps test host
(iframe sandboxed with `allow-scripts`, answering `ui/initialize`, one tool
result and the component's `tools/call`) in headless Chromium (Playwright
1.49.1): no console errors in any state. The full harness
(`scripts/mcp/calendar_widget_review.py`: axe, keyboard, PNG export through
the host) runs against the deployed staging service.

| File | What it shows |
|---|---|
| `w320-inline.png` | 320 px inline card: dates ahead show only planned purchases and bills in bold (10 Phone 30; 11/18 Groceries + proposed Fuel 100; 15 Car loan 270; 25 Groceries + Fuel + Laptop 170) and, where nothing is scheduled, the flexible budgets' daily guide "≈26" muted; the hero says "Flexible budgets: about €26 a day of €573.01 left" |
| `w360-full.png` | 360 px fullscreen, a Wednesday ahead: the planned shop and the proposed fuel date marked "proposed date" |
| `w390-full-dark.png` | 390 px, dark: a date with nothing scheduled leads with "≈€26.03 a day — guidance, not a purchase"; flexible budgets with what is left and "spending faster than its pace" |
| `w430-full.png` | 430 px, a past Wednesday: the planned €50 shop with €43 spent, the flexible share labelled as guidance |
| `desktop-full.png` | 1280 px: the car loan's due date (Everyday plan + Bills due = Plan for the date) |
