# Calendar component v3 — local render checks (2026-11-04)

`ui://mita/financial-calendar-v3.html` (MCP 2.7.0, `behavioral-budget.md`).
**Not ChatGPT.** Both checks below run the real component and real tool
results from a local 2.7.0 server; the owner's run in real ChatGPT is
`../../acceptance-2.7.0-chatgpt.md`.

## 1. The full review harness — 82/82

`scripts/mcp/calendar_widget_review.py --axe` (axe-core 4.10.2) against a
local server on a fresh database at `0042`: a new fictional account through
the real sign-up page, its family month through MITA's tools (the rent,
kindergarten and utilities payments linked to their saved payments, as
ChatGPT does after asking), the component in an iframe sandboxed with
`allow-scripts` only and the spec's CSP, every `tools/call` forwarded with the
account's token. Passed: figures equal the tools', inline and fullscreen at
**320, 360, 390 and 430 px** and desktop with nothing cut off or overflowing,
light and dark, bill states and reminders, a category filter (behind
"More (N)" on a phone since every saved payment is a line of its own), Save
as PNG through `ui/download-file` (1080 px wide) and the in-card fallback,
no console error, read tools only, **axe: no WCAG 2.2 AA violation** in
inline/fullscreen × light/dark.

The first 2.7.0 run failed axe: the "≈" guide on dates without a purchase
was a pale colour with opacity (contrast below 4.5:1). It is now
`--color-text-secondary` at a lighter weight, told apart by "≈". The run
also showed the guide above the safe average when an envelope still held
money that was no longer safe; the guide is now never above
`average_per_day` (`test_the_daily_guide_never_exceeds_the_safe_average`).

## 2. The owner's month, fictional copy — these PNGs

A fictional copy of the owner's November from the current code, viewed on
4 November: income 2,000, savings 500; Phone 30 (10th), Car loan 270 (15th),
Laptop loan 70 (25th); own lines Fuel 200 ("about once a week, ~€50": dates
PROPOSED by MITA, 4/11/18/25), Groceries 50 (every Wednesday), Cigarettes
200, Coffee and walks 100, Housing 50; medical insurance and public
transport not applicable; recorded: a €60 car part and €23.50 of personal
care (neither pays a loan), cigarettes 3.50 + 45.00 (faster than its pace),
coffee 2.00, groceries 12.40. Held for bills **€370.00**, €34.37 a day,
flexible budgets €656.00 left in their lines, ≈€24 a day as guidance.
Rendered by a minimal MCP Apps host (sandboxed iframe, `ui/initialize`, one
tool result, the component's `tools/call`) in headless Chromium; no console
error in any state.

| File | What it shows |
|---|---|
| `w320-inline.png` | 320 px inline card: planned purchases and bills in bold on their dates, "≈24" on dates with nothing scheduled; the hero's safe average and the flexible budgets' line |
| `w360-full.png` | 360 px fullscreen, Wednesday 18 Nov: Fuel on a "proposed date" and the groceries shop as planned purchases, the flexible budgets each with its daily guide, Cigarettes "spending faster than its pace"; bills by due date |
| `w390-full-dark.png` | 390 px, dark, Friday 20 Nov: nothing scheduled — the date leads with the flexible guide, "guidance, not a purchase" |
| `w430-full.png` | 430 px, Wednesday 11 Nov: the groceries shop and the proposed fuel date |
| `desktop-full.png` | 1280 px, Sunday 15 Nov: the car loan's due date (everyday plan + bill due = plan for the date), still unpaid |
