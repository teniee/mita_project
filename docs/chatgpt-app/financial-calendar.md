# MITA's financial calendar in ChatGPT (MCP Apps) — v1, 2026-10-24

The user's month, date by date, rendered inside the ChatGPT conversation as an
interactive component: "Show my financial calendar for November." Built on the
open MCP Apps standard (`io.modelcontextprotocol/ui`), which ChatGPT implements
(developers.openai.com/plugins/build/chatgpt-ui, read 2026-10-24).

## What exists

| Piece | Where | What it is |
|---|---|---|
| Data tool `get_calendar_month` | `app/mcp/tools/calendar.py` | Read-only, `finance:read`. The month as data: summary, budget lines with their group, every date (plan, spend, state), saved bills by date. No template. Callable by the model and by the component. |
| Render tool `show_financial_calendar` | same | Read-only, `finance:read`. The only tool bound to the component (`_meta.ui.resourceUri`, alias `openai/outputTemplate`). Arguments choose the month, an optional date to open on and an optional category filter — never figures. Returns a short view for the model (`structuredContent`, text) and the month for the component (`_meta["mita/calendar"]`, never shown to the model). |
| Component | `app/mcp/ui/financial_calendar.html`, served by `app/mcp/ui/__init__.py` as `ui://mita/financial-calendar-v1.html` (`text/html;profile=mcp-app`) | One HTML document, vanilla JS, no build step, no dependency. |
| Query layer | `app/mcp/queries/calendar.py` | `calendar_month` (five indexed reads in the READ ONLY transaction) and the pure `build_calendar` (also used by the sign-in page's fictional example). |
| Day expenses | existing `list_transactions` | The component lists a selected date's expenses with it (merchant names stay out of the month payload). |
| Review harness | `scripts/mcp/calendar_widget_review.py` | A local MCP Apps host: real sign-up, real tools, the component in a sandboxed iframe under the spec's restrictive CSP. Not ChatGPT. |

The tool count is 24 (22 + 2); MCP 2.2.0.

### Why a render tool that recomputes

OpenAI's decoupled pattern has the render tool take "final data" from the
model. For money that would let a model-written argument change a figure on
screen. Here the render tool recomputes from the account (the same function as
the data tool, ≤ 20 ms) and takes only the month, a date and a category. The
model may still call `get_calendar_month` first to reason about the data —
both return the same summary (tested).

## What each figure means (owner decisions 2026-10-24)

Every figure is a sum of stored rows or what `get_budget_forecast` computes
from the same rows; the component formats, never computes.

**Budget lines** are `get_budget_status`'s lines (`categories.group_lines`;
"Fuel" = `gas` + `transport gas`). Each line is in exactly one group, so the
groups add up to the plan:

| Group | Lines |
|---|---|
| Protected savings (`set_aside`) | `SET_ASIDE_CATEGORIES`: savings, emergency savings, goal reservations, investments. Never spendable. |
| Bills & commitments (`commitment`) | essentials MITA never takes money from (`CATEGORY_PRIORITY` SACRED and not set aside: rent, mortgage, utilities, debt repayment, medical insurance, school fees, online courses) plus the categories of the user's saved regular payments that belong to the month (`counts_in_month`: the reviewed budget's own rule — a repeating payment once running, a one-time payment in its month). |
| Everyday (`everyday`) | every other line, including spending with no plan behind it. |

**Each date** (user's timezone):

| Field | Meaning |
|---|---|
| `planned` | the date's plan: every line except money set aside (as `get_budget_status.today`) |
| `planned_everyday` | its everyday part |
| `set_aside` | savings / goal slices planned that date — shown apart, never spendable |
| `spent`, `spent_everyday` | recorded (non-deleted) expenses; null for future dates |
| `state` | begun dates: **over** (everyday spending above that date's everyday plan), **within**, **unplanned** (spending on a date with no everyday plan — no verdict, the dashboard rule), **quiet**; future dates: **planned** / **free**. Never a forecast. |

Bills and commitments are kept out of the over/within verdict: rent planned on
the 1st and paid on the 3rd is a bill paid, not €850 of overspending on the 3rd.

**Summary**: plan, commitments, set aside, everyday (they add up to the plan);
spent (commitments + everyday); `total_remaining`; `savings_set_aside`;
`left_to_spend` = remaining − set aside; `average_per_day` =
`get_budget_forecast.safe_daily_limit` (an average for each remaining day — not
a budget for any date); `days_remaining`; `commitments_not_recorded` (planned on
commitment lines and not recorded yet — still inside left to spend);
`planned_after_today` (the plan on the dates ahead); `bills_due_after_today`.

**Saved bills** fall on dates by the rule the user stated: monthly on the
anchor's day (the month's last day when shorter), weekly on the weekday, one-time
on its date — never before the date it was first scheduled for. `in_plan` says
whether the month's plan holds money on that bill's line. Markers only: a bill's
amount is never added to any total (no double counting with the plan).

### What the calendar shows that MITA's model does not reconcile (reported, not fixed)

* **The dates ahead can hold far less than the daily average.** MITA's
  automatic rebalancing (`realtime_rebalancer.rebalance_after_overspend`) takes
  money from later dates to cover a date that went over; money left unspent on
  a past date stays there. The forecast's average counts both. Review account,
  24 Oct: base plan for 25–31 Oct €299.95, after the month as recorded €12.16,
  while the average was €121.99 a day. The calendar shows both, labelled; the
  component explains the gap when it is material (`planned_after_today`).
  Backend finding F-8.
* **A saved bill paid on its due date can count as overspending** where the
  layout put it elsewhere (rent/school fees on the 1st, other fixed categories
  on the 5th, obligation categories the layout does not know spread over
  weekdays) — that is what triggers the rebalancing above. F-8.
* **Unrecorded bills are spendable until recorded** (known since 2026-10-23):
  disclosed as `commitments_not_recorded`.
* **F-2**: an expense category named differently from its plan line (`gas` vs
  `transport gas`) is shown on one line here but is unplanned spending to the
  rebalancer.

None of these is changed here: the owner deferred the forecast/plan model to a
dedicated task. The calendar never adds a figure that would hide them.

## The component

* **Inline card** (ChatGPT's default): the month, the average a day, left to
  spend / spent / savings kept, a compact calendar with each date's amount and a
  bar against its everyday plan, the over days and the next bill; two actions
  (Open calendar → fullscreen; Save as PNG). No drill-in (OpenAI UI guidelines).
* **Fullscreen**: month navigation (`get_calendar_month` through the host),
  the summary and "How is this worked out?", category filters (top lines + More),
  the calendar grid (keyboard: arrows, Home/End), the selected date's detail
  (everyday plan vs spent, bills and commitments recorded, savings set aside,
  saved bills due, lines, the date's expenses), categories by group, the plan's
  composition and its caveats, the method. Phones: the calendar comes right
  after the summary; wide: summary, calendar and detail side by side.
* **States**: loading skeleton, no plan for the month (spending only; for the
  current or next month a button asks ChatGPT to plan it — `ui/message`), error,
  tool cancelled, a host that strips `_meta` (the component asks
  `get_calendar_month`).
* **Bridge**: `ui/initialize` (appCapabilities.availableDisplayModes
  inline+fullscreen, protocol 2026-01-26) → `ui/notifications/initialized`;
  tool input/result/cancelled; `host-context-changed` (theme, display mode);
  `tools/call` (read tools only: `get_calendar_month`, `list_transactions`);
  `ui/request-display-mode`; `ui/update-model-context` (the selected date and
  filter, so a follow-up question is grounded); `ui/message`;
  `ui/notifications/size-changed` (ResizeObserver); `ui/download-file`;
  `ui/resource-teardown`, `ping`. ChatGPT's `window.openai` is used only for
  what the standard lacks (widget state, file upload/download) and is
  feature-detected; its globals also hydrate the component if the bridge is
  missing.
* **Look**: the system font stack and the host's CSS variables (OpenAI: no
  custom fonts, no custom gradients, system colours for text; ChatGPT adds the
  logo and name). MITA colour only on accents: the primary button (navy/yellow,
  inverted in dark mode), the Today badge, savings (teal). Category colours by
  family in a fixed order (validated categorical palette, never by rank); red
  only for "over", always with an icon and words. Light and dark.
* **Accessibility**: axe-core WCAG 2.2 AA, 0 violations inline/fullscreen ×
  light/dark (harness); each date is a button with a full label; selection and
  filter changes announced; reduced motion honoured.

### Save as PNG

The month drawn on a canvas, 1080 px wide (height from content): plan, spent,
left to spend, protected savings, the average a day, days left; every date
(recorded vs dashed plan, over marks, bills due, today); up to six categories;
legend; "Generated <date, time, timezone>"; "From your MITA account". No
merchant, expense, bill name or e-mail. Delivery, by what the host supports:

1. `ui/download-file` (MCP Apps; the host asks the user) — tested in the harness.
2. ChatGPT's `window.openai.uploadFile` (to the user's own ChatGPT files) then
   `getFileDownloadUrl` opened with `ui/open-link` — not testable outside ChatGPT.
3. Otherwise the image is shown in the component to keep with a long press or
   right-click — tested.

No server-side PNG, no URL: the image never leaves the user's own session
except through the host's own download or file store.

## Security

* No tool takes a user id; identity from the token; `additionalProperties:
  false` (smuggled `user_id` refused — tested).
* The component loads nothing and connects nowhere: the resource declares
  empty `connectDomains`/`resourceDomains`, so the host's restrictive CSP
  applies; tested that the source has no remote URL, fetch/XHR/WebSocket,
  `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`, `eval` or
  `new Function`, and calls only the two read tools.
* Every value is set with `textContent`; host CSS variables are applied only
  when they look like variables (`--name`, no `<>{};`).
* `ui.domain` is set only when `MCP_WIDGET_DOMAIN` is configured (an https
  origin; required by OpenAI at submission, unset on staging — ChatGPT's shared
  sandbox origin).
* The `_meta` month payload goes to the component only; it contains no e-mail,
  no internal id; merchants appear only in `bills[].name` (the user's own saved
  payment names), which the image leaves out.

## Testing

* `tests_mcp/test_calendar.py` (32): exact figures for a hand-built month in
  Europe/Sofia (incl. a 22:30 UTC expense that is the next local day, a deleted
  expense, a cancelled payment), parity with `get_budget_status` and
  `get_budget_forecast`, no plan / past / future months, bill dates, groups,
  isolation, the render tool's split between model and component, the resource
  and its CSP, the component source rules, the master logomark in the image.
* `scripts/mcp/calendar_widget_review.py` (59 checks): sign-up through the real
  page, the month entered through MITA's tools, the component in a sandboxed
  iframe with the spec's restrictive CSP, phone (WebKit) and desktop
  (Chromium), light/dark, fullscreen, a date's label and expenses, model
  context, the filter, keyboard, next/previous month, the PNG through
  `ui/download-file` and without it, axe-core, read tools only, cleanup.
  Screenshots: `docs/chatgpt-app/review/calendar-v1/`.
* Real ChatGPT: owner-run (`calendar-owner-test.md`).

## Not supported (and not claimed)

* User-defined categories (MITA has none); household members or shared
  accounts (one account = one user); editing from the calendar (read-only by
  design); a forecast per date; localisation of the component's labels (English;
  amounts and dates in the user's currency and timezone); months beyond next
  year or before 2000 (`resolve_month`).
