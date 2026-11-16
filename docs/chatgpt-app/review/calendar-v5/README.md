# Calendar component v5 — local render checks (2026-11-16)

`ui://mita/financial-calendar-v5.html` (MCP 2.11.0,
`../../calendar-guidance-layer.md`). **Not ChatGPT.** The real component in
an iframe sandboxed with `allow-scripts` only under the MCP Apps restrictive
CSP (the host page of `scripts/mcp/calendar_widget_review.py`), fed by the
real tools in process on a local PostgreSQL transaction
(`tests_mcp/test_calendar_rendering.py`). The owner's run in real ChatGPT is
`../../acceptance-2.11.0-chatgpt.md`; 2.10.0's renders are in
`../calendar-v4/`.

## The month (fictional)

The brief's November 2026, Europe/Sofia, EUR, seen on **12 November**:
income 1,985, savings 500; Car loan 270 (15th), Laptop loan 70 (25th); own
lines Groceries 320, Car maintenance 200, Entertainment 100, Restaurants 100
— flexible budgets — and Coffee 45 with the stated pattern "every day, about
1.50"; 380 left unallocated. Recorded: coffee 1.50 on the 3rd and the 4th,
40.00 at a restaurant on the 10th. Average left per day, by hand (19 days
left with today): Groceries 16.84, Car maintenance 10.53, Entertainment 5.26,
Restaurants 3.16 — together **35.79** (680.00 left), under the safe average
40.11 (722.00 ÷ the 18 days after today). An average, and called one.

## The renders

| File | What it shows |
|---|---|
| `desktop-all-categories.png` | **All categories**: amounts as in 2.10.0 (1.50, 1.50, 40.00 so far; ahead 1.50, **271.50** on the 15th, 71.50 on the 25th) and, apart, a **≈35.79** pill on the 12th and every date after it. Caption "≈ marks the average left per day from today: an average of what is left, not a plan."; switch "Daily average On"; legend "Average left per day: not a plan or a recommendation". Tile "Scheduled on the days left €367.00" — no average in it |
| `desktop-filter-restaurants.png` | Filter **Restaurants**: the only amount is 40.00 on the 10th; **≈3.16** on the 12th and every date ahead; banner "… €60.00 left · ≈ €3.16 a day on average · no purchase dates"; the 15th selected: "Scheduled for the date €271.50", then "Average left per day ≈ €3.16 a day on average for Restaurants … All your flexible budgets together: ≈ €35.79 a day. It is an average of what is left, not a recommendation: not part of the €271.50 scheduled for this date" |
| `desktop-date-ahead.png` | The 20th: "Planned for this date €1.50 planned purchases and bills", then the "Average left per day" box, then each flexible budget with its exact figure |
| `desktop-average-off.png` | The switch **off**: no ≈ anywhere, every amount identical; "The daily average is hidden." |
| `desktop-empty-dates.png` | No pattern stated at all (seen on the 2nd): no amount but the loans — and **≈26.38** on every date from the 2nd |
| `desktop-average-capped.png` | After €300 of shopping in no budget: the budgets still hold 765.00, the month 465.00 after bills and savings → the figure is the safe average **≈16.61**, said under the grid and in the hero; Groceries' banner adds "all flexible budgets together ≈ €16.61 a day (the safe average)" |
| `phone-390-inline-light.png`, `…-dark.png` | 390 px inline card (WebKit): **1.50, never 2**; 40 (exact) on the 10th; 271.50, 71.50; a **≈36** pill on the 12th and after (whole units on a phone: it is "about") |
| `phone-320-inline.png` | The narrowest card: 1.50 / 271.50 / 71.50 still with their cents, the summary tiles stacked, nothing cut |
| `phone-390-filter-restaurants-light.png`, `…-dark.png` | 390 px fullscreen, Restaurants: 40 on the 10th, ≈3 from the 12th, the switch, the explanation under the grid |
| `exported-month.png` | The image: each date from the 12th has its amount and, below it, a separate "≈ 35.79" pill; a note line with the calculation, a legend line "Average left per day: … not a plan or a recommendation"; the tile "Days after today 18" |

## Checks passed (`test_calendar_rendering.py`, 1 test, about 60 s)

* Activity: every cell's exact amount, All categories and seven filters;
  the filters' amounts add up to All categories; no 3.33 / 10.67 / 6.67 share
  anywhere; no verdict or meter on a flexible line's dates.
* The average: on today and every date ahead = MITA's figure (35.79; each
  flexible filter its own `left_per_day`; Coffee and the loans none); past
  dates none; never inside an amount (`MERGED` = 0); the date's label, the
  caption, the legend, the note and the detail box call it an average;
  **no visible text says "guidance", "daily guide" or "recommended"**.
* "How is this worked out?": every row, both divisors (18 after today, 19
  with today) and "It is arithmetic, not a recommendation".
* The image: every `fillText` recorded — 19 pills in their colour, the
  scheduled amounts in theirs, the 15th's pill under its own 271.50, no
  merged figure (307.29…); with the switch off, no "≈" at all.
* The switch: off = identical amounts and no average (grid, detail, image,
  model context); kept in the widget state and restored on a new card.
* Phones (WebKit) at 390 px, light and dark, and 320 px: 1.50 everywhere it
  is due, never 2; nothing cut off or overflowing — every filter, average on
  and off, four dates' details; axe-core 4.10.2: no WCAG 2.2 AA violation in
  the filtered, empty-date and date-ahead views, light and dark.
* No console error in any view (v4's ResizeObserver page error is gone).

Run it (also part of MCP CI since 2.11.0):

```bash
python -m venv /tmp/pw && /tmp/pw/bin/pip install -r requirements-mcp-dev.txt \
    -r requirements-mcp-render.txt && /tmp/pw/bin/playwright install chromium webkit
caffeinate -dimsu env MITA_RENDERING_REQUIRED=1 MITA_CALENDAR_SHOTS=/tmp/calendar-v5 \
    PYTHONPATH=. /tmp/pw/bin/pytest -c tests_mcp/pytest.ini tests_mcp/test_calendar_rendering.py
```

The PNGs here are those screenshots at 1× and 128 colours.
