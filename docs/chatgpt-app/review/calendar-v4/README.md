# Calendar component v4 — local render checks (2026-11-12)

`ui://mita/financial-calendar-v4.html` (MCP 2.10.0,
`../../flexible-envelopes-calendar.md`). **Not ChatGPT.** The real component
in an iframe sandboxed with `allow-scripts` only under the MCP Apps
restrictive CSP (the host page of `scripts/mcp/calendar_widget_review.py`),
fed by the real tools in process on a local PostgreSQL transaction
(`tests_mcp/test_calendar_rendering.py`). The owner's run in real ChatGPT is
`../../acceptance-2.10.0-chatgpt.md`.

## The month (fictional)

The brief's November 2026, Europe/Sofia, EUR, seen on **12 November**:
income 1,985, savings 500; Car loan 270 (15th), Laptop loan 70 (25th); own
lines Groceries 320, Car maintenance 200, Entertainment 100, Restaurants 100
— no pattern stated, so flexible budgets — and Coffee 45 with the stated
pattern "every day, about 1.50" (30 planned purchases of 1.50); 380 left
unallocated. Recorded: coffee 1.50 on the 3rd and the 4th, 40.00 at a
restaurant on the 10th.

## Before — 2.9.0 (`af67d69`), the same month

| File | What it shows |
|---|---|
| `before-2.9.0-filter-restaurants.png` | Filter **Restaurants**: **3.33 on every date from the 13th to the 30th**, 0.00 today. Today's detail: "€0.00 of €22.23 planned — €1.50 for planned purchases · €20.73 flexible budgets' daily share", "€22.23 of the everyday plan left". Tile "Planned on the days left €798.80"; "The dates ahead hold €458.80 of everyday money" |
| `before-2.9.0-exported-month.png` | The image: every date ahead **25.50 / 25.48** (the 1.50 coffee plus all four budgets' shares: 10.67 + 6.67 + 3.33 + 3.33), 295.50 on the 15th, 95.48 on the 25th |

The cells the harness read on 2.9.0:

```
All categories       13…30 Nov: 1.50 (15th 271.50, 25th 71.50); begun dates 0.00 unless spent
filter Restaurants   13…30 Nov: 3.33; 12th 0.00; 10th 40.00
filter Groceries     13…20 Nov: 10.67; 21…30 Nov: 10.66; 1…12 Nov: 0.00
filter Car maint.    13…20 Nov: 6.67;  21…30 Nov: 6.66;  1…12 Nov: 0.00
filter Entertainment 13…30 Nov: 3.33;  1…12 Nov: 0.00
```

## After — 2.10.0, component v4

| File | What it shows |
|---|---|
| `desktop-filter-restaurants.png` | Filter **Restaurants**: **only 40.00 on the 10th**; every other date empty. Banner "flexible budget · spent €40.00 of €100.00 this month · €60.00 left · about €3 a day as guidance · no purchase dates"; under the grid "Restaurants is a flexible budget: a monthly limit with no purchase dates…". Today: "€0.00 of €1.50 planned", "Within what was planned and your monthly budgets". Tile "Scheduled on the days left €367.00 — planned purchases and bills, no flexible budget" (18 × 1.50 + 340) |
| `desktop-all-categories.png` | **All categories**: spent so far (1.50, 1.50, 40.00; 0 where a planned coffee was not recorded), ahead the stated coffee 1.50, 271.50 on the 15th, 71.50 on the 25th. No "≈". Hero: "Flexible budgets (monthly limits, no dates): €680.00 left · about €36 a day as guidance, not a daily limit" |
| `desktop-filter-coffee.png` | Filter **Coffee** (stated daily): 1.50 on every date ahead — the same events "All categories" shows |
| `desktop-date-spent.png` | The 10th: "€40.00 of €1.50 planned", Restaurants "from its monthly budget" €40.00, the expense itself; no "daily share", no "left for the date" |
| `desktop-empty-dates.png` | The same month with **no pattern stated at all** (seen on the 2nd): every date empty but the loans (270.00, 70.00); the 20th selected: "Nothing scheduled — No purchase or bill is planned for this date. Your flexible budgets are monthly limits: spend from them on any day." |
| `phone-390-inline-light.png` | 390 px inline card (WebKit): whole euros, 40 on the 10th, 2 / 272 / 72 ahead, no "≈" |
| `phone-390-filter-restaurants-light.png`, `…-dark.png` | 390 px fullscreen, Restaurants filter behind "More": only 40 on the 10th; nothing cut off or overflowing |
| `exported-month.png` | The image: ahead 1.50, 271.50, 71.50 — what is scheduled |

## Checks passed (`test_calendar_rendering.py`, 1 test, about 40 s)

* All categories and each of the seven filters read from the cells'
  exact amounts; **the filters' dates add up to "All categories"**.
* No cell, date label or date detail contains 3.33 / 3.34, 10.66 / 10.67 or
  6.66 / 6.67; no "≈" anywhere; no over / within verdict or meter on a
  flexible line's dates.
* A date ahead and its detail; the loan's date ("Planned purchases + Bills
  due = Scheduled for the date"); the date of the real expense with its
  merchant from `list_transactions`; the model context for the selection.
* Empty dates and "Nothing scheduled".
* Month navigation to December (no plan) and back: the same cells.
* Save as PNG through `ui/download-file`: 1080 px wide.
* 390 px phone, light and dark: inline and fullscreen, nothing cut off, no
  horizontal overflow; no console error; only `get_calendar_month` and
  `list_transactions` called by the component.
* **320 px** (a 360 dp Android's chat column), fullscreen: four kinds of date
  (spent, today, a loan's date, an empty date) × no filter, Restaurants,
  Coffee — nothing pushes the page sideways.
* With `MITA_AXE` (axe-core 4.10.2): no WCAG 2.2 AA violation in the
  Restaurants filter, a date ahead, the phone views (light and dark) and the
  empty month.

## The full review harness — 81/81 with axe

`scripts/mcp/calendar_widget_review.py --axe` against a local 2.10.0 server
(`python -m app.mcp`, the local test database at `0044`): a new fictional
account through the real sign-up page, its family month through MITA's
tools, the component in the sandboxed iframe. Passed: figures equal the
tools', inline and fullscreen at 320, 360, 390 and 430 px and desktop with
nothing cut off or overflowing, light and dark, bills and reminders, a
category filter, Save as PNG through `ui/download-file` and the in-card
fallback, no console error, read tools only, and **axe: no WCAG 2.2 AA
violation** in inline / fullscreen × light / dark. (81 rather than the 82 of
2.7.0: one check is conditional on the run date's data.)

Its first run on v4 failed at 320 px ("overflow 44"): the words "· from its
monthly budget" sat in the amount column of a date's lines, which never
wraps. They are now under the line's name. The stricter 320 px sweep added to
`test_calendar_rendering.py` then found the same fault in a string older
than this release — "nothing recorded · 1.50 planned" on a past date whose
planned purchase was not recorded (19 px) — and that status may now wrap.

Run it (dev-only dependencies, as for the harness):

```bash
python -m venv /tmp/pw && /tmp/pw/bin/pip install -r requirements-mcp-dev.txt \
    playwright==1.49.1 Pillow && /tmp/pw/bin/playwright install chromium webkit
MITA_CALENDAR_SHOTS=/tmp/calendar-v4 PYTHONPATH=. /tmp/pw/bin/pytest \
    -c tests_mcp/pytest.ini tests_mcp/test_calendar_rendering.py
```

The PNGs here are those screenshots at 1× and 128 colours (smaller files;
the red of "over" and the amber of reminders are flattened by it).
