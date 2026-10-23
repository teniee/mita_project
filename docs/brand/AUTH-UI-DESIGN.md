# Auth UI — design inventory

The ChatGPT sign-in / sign-up / consent page (`/oauth/login`) and its error
pages. Code: `app/mcp/auth/pages.py` (markup, CSS, copy), served by the MCP
service; fonts and favicon in `app/mcp/auth/static/`. Designed mobile first
(2026-10-23 refinement, below): ChatGPT opens it in its in-app browser.

## Sources

**Authoritative:** Figma *Mita-Finance-Brand-Guidelines*
(`512WdjnhPJXM8jeHKcg4g8`), page **Template** (`1:3`). Its frames keep the
template's names ("Branding Guidelines Template (FREE) by Sam Stoof - N");
the ones used:

| Frame | Node | Content |
|---|---|---|
| 30 | `2014:2` | Cover — lockup, "Mita Finance / Control Your money. Daily." |
| 4, 5, 6, 7 | `5:68`, `5:688`, `5:711`, `5:728` | Mission, vision, positioning; values & personality; audience; goal of the guidelines |
| 9 | `5:83` | Logomark |
| 10 | `5:545` | Logo variants (master logomark `2011:206`, wordmark `2011:212`) |
| 11, 12 | `5:567`, `5:630` | Logo do's / don'ts |
| 15, 16, 17 | `5:463`, `5:387`, `5:425` | Colors, gradients, color combinations |
| 19, 20, 22 | `5:211`, `5:370`, `5:192` | Manrope, Sora, text structure |
| 29, 24 | `6:911`, `5:228` | Pitch grid, imagery |
| — | local variables | collection "Variable collection" (6 colors) |

**Product language (secondary):** Figma `hGPeeY99LUn1Q2MSpmHBQu` (website
capture, frame `1:2`) and the Flutter theme (`mobile_app/lib/theme/`).

## Values defined in Figma

| What | Value | Where |
|---|---|---|
| Mita Blue — primary text, anchor | `#193C57` | variable *Mita Blue* |
| Mita yellow — highlights and key actions | `#FFD25F` | variable *Mita yellow*; Color Combinations text |
| Mita Red / Mita Green / Mita purple | `#F44336` / `#14B8A6` / `#6B73FF` | variables |
| Mita Back — page background | `#FFF9F0` | variable *Mita Back* |
| Light teal (pairs with Mita Green) | `#CCFBF1` | Color Combinations |
| Approved gradients | `#193C57`↔`#FFD25F`, `#F44336`↔`#14B8A6`, `#6B73FF`↔`#FFD25F` | Gradients |
| Approved pairings | yellow + blue, purple + red, green + light teal | Color Combinations |
| Primary font | **Manrope** — UI headlines, key figures, onboarding and core product flows; no light weights for financial data | Typography (Manrope) |
| Secondary font | **Sora** — marketing headlines, section dividers, feature highlights; not for dense data, long paragraphs or labels under 16 px | Typography (Sora) |
| Data font | **Space Mono** — "highlights financial data with precision" | Text Structure |
| Type scale | 1.25 ratio | Text Structure |
| Wordmark | "Mita", Manrope ExtraBold, letter-spacing −2 %, `#193C57` | Logo Variants, cover |
| Logomark | four modules: M red, I purple, T green, A yellow | Logomark |
| Logo rules | strong contrast; preserve proportions; approved palette; clear space; soft shadows only; never recreate — master files only | Logo Do's / Don'ts |
| Grid (decks) | 24 px margins, 24 px gutter | Pitch Grid |
| Voice | "Confident but not loud. Intelligent yet approachable. Structured, calm, and forward thinking … never with financial jargon or fear." | Values & Personality |

Not defined in Figma: buttons, inputs, cards, corner radii, shadow values,
status colors, a UI spacing scale, dark mode. The Colors frame also carries
template residue (RGB "255, 90, 95", HSL "43%, 69%, 100%" next to
`#FFD25F`); the hex values and the variables agree and are what is used.

## Derived for this page

Decisions, not brand facts. Contrast ratios are WCAG 2.x.

| What | Value | Basis |
|---|---|---|
| Secondary text | `#4C6679` | Mita Blue 78 % over Mita Back; 5.8:1 on `#FFF9F0`, 6.0:1 on white |
| Hairlines | Mita Blue 14 % / 24 % | Figma's most used stroke is 1 px Mita Blue |
| Input border | `#7A8E9E` | Mita Blue 58 % on white; 3.4:1 (non-text contrast) |
| Focus ring | 3 px Mita purple, 2 px offset | 3.8:1 on white |
| Error | text `#BA1A1A` on `#FEECEB`, border Mita Red 40 % | Flutter `colorScheme.error`; Mita Red 10 % tint |
| Notice | Mita yellow 31 % | fill observed in Figma (`#FFD25F` @ 0.31) |
| Positive | Mita Green for icons and progress only (2.5:1 as text) | palette |
| Primary button | Mita Blue fill, Mita yellow text (8.0:1), pill, Manrope Bold 16, ≥ 52 px; hover `#2B5876` | yellow + blue pairing; website CTA text; Flutter `primaryLight` |
| Secondary button | transparent, Mita Blue text, 1 px Mita Blue 24 %, ≥ 44 px | — |
| Inputs | ≥ 48 px, radius 14, Manrope 500 16 px (no zoom on iOS) | Flutter inputs: radius 16, min 48 px |
| Cards | white, radius 24 (panels) / 16 (items), `0 16px 40px rgba(25,60,87,.10)` | "soft shadows only"; Flutter cards radius 16 |
| Headings | Sora 700 (hero; card and section titles 20–22 px) | Figma conflicts (Manrope page: "UI headlines"; Text Structure: "Sora defines headlines"); the Flutter theme uses Sora for headings |
| UI and body | Manrope 400–700 | Figma |
| Amounts, labels, step numbers, calendar | Space Mono 400/700 | Figma |
| Sizes | 16 body (13–15 in cards); hero clamps 28 → 54 | 1.25 scale |
| Spacing | multiples of 4/8; card padding 16 on phones, 24 from 560 px | 24 px grid |
| Pacing colors | days passed Mita Blue 7 %; today Mita Blue with a Mita yellow ring; days left light teal `#D5F2EF` with a Mita Green edge; the savings note Mita Blue text on light teal | green + light teal pairing; positive = Mita Green |
| Logo | full-color lockup: master vectors of `2011:206` + `2011:212` at the master offset (+92.39, +14.4); favicon = logomark | Logo Variants |
| Theme | light only (`color-scheme: light`) | the brand system is light; no dark spec |

## Conflicts noticed

* The mobile app ships an older hand-drawn "mita finance" logo on a yellow
  circle (`mobile_app/assets/logo/mitalogo.png`); Figma defines the geometric
  logomark + Manrope wordmark. This page follows Figma; the app is unchanged.
* `CLAUDE.md` (website section) gives the background as `#FFF8F0` and the
  logomark as four rounded squares; Figma says `#FFF9F0` and letter-shaped
  modules. The Flutter theme already uses `#FFF9F0`.
* Flutter status colors are Material (`#4CAF50`, `#FF9800`); Figma has none.
  This page uses brand colors only.
* Website CTAs use a navy→purple gradient, which is not an approved Figma
  gradient; this page uses solid Mita Blue.

## Page rules

* No JavaScript and nothing third-party (CSP `default-src 'none'`, no
  `script-src`; `font-src 'self'` for the three self-hosted fonts).
* Fonts: WOFF2 subsets built by `scripts/mcp/build_auth_fonts.py` — Manrope
  and Sora variable (400–700) from the app's OFL files, Space Mono from
  google/fonts (SHA-256 pinned); 74 KB together, cached as immutable.
* Motion: one entrance sequence of the demo on wide screens, CSS only, none
  under `prefers-reduced-motion`.
* Copy states facts from `docs/chatgpt-app/data-inventory.md`; demo figures
  are fictional and labelled so. No "bank-grade", "encrypted", "free" or
  similar claims (tested).
* Mobile first: the base CSS is the phone layout; `min-width` queries only
  add (560 px: wider cards, two-column lists; 1040 px: the sign-in card as a
  right-hand column level with the logo). Tested.
* Permissions: the five scope titles are always on screen; each one's
  explanation and the full "cannot move money" sentence are in a native
  `<details>` ("View permission details"), closed by default. Tested.
* The pacing example's figures are what MITA's forecast engine returns for
  them (`test_the_pacing_example_is_what_the_forecast_engine_returns`).
* No forecast status on the page — no "On track", "warning" or "danger"
  badge (owner decision 2026-10-23, tested). `get_budget_forecast` still
  returns `status` unchanged; its linear pace counts rent paid on the 1st as
  daily spending, so it can mislead until the forecast model is fixed in a
  dedicated task (below).
* Review screenshots: `docs/chatgpt-app/review/auth-ui/` (first version, on
  staging since 2026-10-23) and `docs/chatgpt-app/review/auth-ui-v2/` (mobile
  first, local only, waiting for the owner), produced by
  `scripts/mcp/auth_ui_screenshots.py`.

## Mobile-first refinement (2026-10-23, local, not deployed)

The owner's review of the first version: it felt desktop-first, and the
daily-spending value of MITA was shown nowhere.

**What was wrong.** The phone got the desktop columns stacked: an eyebrow,
a four-line introduction, then a sign-in card whose consent box listed five
permissions with their full explanations; the example conversation came
only after the whole form. On a 390×844 phone the sign-in button sat 655 px
below the first screen and no product example was visible; at 1440×900 the
same consent box pushed the button 193 px below the fold.

**Order now (phone; wider screens keep it):** logo + "for ChatGPT" →
headline → one line of value → one compact example (the pacing answer with a
31-day strip) → sign-in card (tabs, fields, the five permission titles,
usage-statistics choice, button) → "What MITA does in ChatGPT" (record,
understand, pace with the month calendar, remember) → "Try asking" →
"How MITA works" (3 steps) → limits. From 1040 px the card becomes the
right-hand column, starting level with the logo.

Where the primary button ends (page px; "below" = scroll needed to see it).
"Staging" is `ee388c0`; "first refinement" the version reviewed earlier on
2026-10-23; "now" adds the phone trims of the second round (spacing, a
one-line card subtitle, a one-line "can't move money" line, a three-line
usage-statistics label — no content removed):

| Viewport | Sign in: staging | first refinement | now | Create account: staging | now |
|---|---|---|---|---|---|
| 390×844 | 1,499 (655 below) | 1,093 (249 below) | 983 (139 below) | 1,668 (824 below) | 1,137 (293 below) |
| 430×932 | 1,434 (502 below) | 1,061 (129 below) | 985 (53 below) | 1,603 (671 below) | 1,139 (207 below) |
| 768×1024 | 1,261 (237 below) | 1,079 (55 below) | 1,043 (19 below) | 1,433 (409 below) | 1,177 (153 below) |
| 1280×800 | 1,093 (293 below) | 730 — on screen | 686 — on screen | 1,242 (442 below) | 841 (41 below) |
| 1440×900 | 1,093 (193 below) | 730 — on screen | 686 — on screen | 1,242 (342 below) | 841 — on screen |
| 1440×1000 | 1,093 (93 below) | 730 — on screen | 686 — on screen | 1,242 (242 below) | 841 — on screen |

On phones the button cannot share the first screen with the headline and
example: the five permission titles and the usage-statistics choice must
come before it. At 390×844 the first screen now ends with all five titles,
the "can't move money" line and "View permission details"; the button is one
short scroll below.

## Daily spending — what MITA can truthfully show

Audited in the code (`app/mcp/tools/budget.py`, `app/mcp/queries/plan.py`,
`app/services/core/engine/budget_forecast_engine.py`,
`app/services/monthly_plan_service.py`, `goal_budget_sync.py`), the
exact-value tests and runs of the real tools for a reviewed plan with a
savings target.

How the plan holds money (`daily_plan`, one row per day and category):

* **Everyday spending lines** — the engine's categories (groceries, dining
  out, transport…), laid out on weekdays ("spread") or a few days
  ("clustered").
* **Fixed obligations** — the user's saved recurring expenses in the reviewed
  budget; rent, mortgage, school fees on the 1st, other "fixed" categories on
  the 5th; obligation categories the layout does not know (insurance,
  subscriptions…) spread over weekdays.
* **Savings** — the user's monthly savings target as the line
  `savings goal based`, spread over weekdays.
* **Goal reservations** — `goal_savings` rows (`goal_id` set) that
  `create_savings_goal` writes for each remaining day of the month.
* Spending comes from the ledger. No expense category can be recorded
  against savings, goal reservations or investments
  (`VALID_TRANSACTION_CATEGORIES`), so those lines never receive spending.

| What | Tool → field | Calculation |
|---|---|---|
| Month's budget, spent, left | `get_budget_status` → `total_planned`, `total_spent`, `total_remaining` (also in the forecast as `remaining_budget`) | sums of every plan row and of the month's non-deleted expenses, in the user's time zone — the whole plan, savings included |
| Set aside | `get_budget_forecast` → `savings_set_aside` | over the set-aside lines (`category_priority.SET_ASIDE_CATEGORIES`: savings, emergency savings, goal reservations, investments), per line max(0, planned − deposited) |
| Safe amount per day | `get_budget_forecast` → `safe_daily_limit` | **(remaining_budget − savings_set_aside) ÷ days_remaining**, Decimal, ROUND_HALF_UP to the cent; negative once spending has used more than the plan leaves for spending; 0 when no days are left |
| Today's plan | `get_budget_status` → `today.planned / spent / remaining` | today's spending allocations (set-aside lines excluded) minus today's expenses — today only |
| Days left | `get_budget_forecast` → `days_remaining` | days in the month after today (today counts as elapsed) |
| Pace so far | `get_budget_forecast` → `current_daily_pace` | total spent ÷ days elapsed |
| On track / warning / danger | `get_budget_forecast` → `status` | projected month-end balance (spent + pace × days left vs the whole plan): ≥ 0 on track; < 10 % over warning; ≥ 10 % danger |
| Categories at risk | `get_budget_forecast` → `categories_at_risk` | category pace ≥ 1.2 × its planned daily rate |

Not supported, so not shown: a "safe to spend **today**" figure; a separate
amount for each future date (the stored plan has per-date rows, but no tool
returns them beyond today); a day-by-day spending history; any calendar or
card inside ChatGPT (MITA has no widget — ChatGPT writes the answer).

Corrected on 2026-10-23 (owner decision): savings and goal set-asides were
counted as spendable. Real tool run, reviewed plan 2,325.00 with 400.00
savings, 11 October, 20 days left: 76.70 a day before, **56.70** now
(`tests_mcp/test_spendable_forecast.py`).

What remains, classified (A — affects the safe daily limit; B — only the
projection / status; C — handled correctly; D — needs engine work). Deferred
by the owner to a dedicated forecast-engine task: the rent / fixed-bill pace
and the whole on track / warning / danger model (not fixed — the auth page
just stops showing the status), future fixed and recurring bills, and the
mobile scheduled-expenses figure:

| Issue | Class | State |
|---|---|---|
| Savings line, emergency savings, investments counted as spendable | A | fixed |
| Goal reservations counted as spendable | A | fixed; a line already filled by deposits holds nothing back |
| Today's plan included the day's savings and goal slices | today's figure | fixed |
| Rent (any bill) recorded when paid | C for the safe limit (it leaves `remaining_budget`); B for the status: the pace counts rent as daily spending, so early in the month the projection is too high and rent shows "at risk" | not changed → D |
| Savings in the status projection | B: the status compares with the whole plan, so savings still cushion it. Correcting it alone makes the status worse: a saver who records rent on the 1st and spends exactly to plan would read "danger" all month (pace includes the rent) | not changed → D, together with the rent pace |
| A bill in the plan not yet recorded (rent unpaid or never logged; utilities on the 5th) | A: counted as spendable until recorded — an unlogged 700.00 rent on the 11th adds 35.00 a day | D (reserve unpaid obligations by due date from the saved recurring expenses); the tool's method text says so |
| One-time bills later in the month | in the plan only if saved before the budget was reviewed; then as above; otherwise unknown to the forecast | D |
| Recurring expenses | C for totals (in the reviewed plan as fixed lines); obligation categories the layout does not know are spread over weekdays, so today's plan shows slices of them | D |
| A goal reservation on top of a savings target | both are set aside; whether a goal's contribution should come out of the savings target is a model question | D |
| Mobile app: `/api/scheduled-expenses` impact (`base_safe_daily_limit`, `adjusted_safe_daily_limit`) | A for the app only: still counts savings (not used by ChatGPT); `/api/budget/forecast` shares the corrected engine | deferred (technical debt) |

**The calendar.** It shows where the month stands — days passed, today, the
days left — and `safe_daily_limit` as one shade on every remaining day,
because the forecast gives one amount for each of them. It does not show or
imply a budget per date, spending per day, or a calendar in ChatGPT; the
grid is decorative (`aria-hidden`) and the key beside it states the figures,
including the arithmetic: "€1,200.40 left − €400.00 savings = €800.40 ÷ 12
days = €66.70".

**The example figures** (fictional; recomputed with `compute_forecast` by a
test): plan €2,325.00 with €400.00 Savings; Monday 19 October, spent
€1,124.60 → €1,200.40 left, €800.40 to spend, 12 days left, €66.70 a day
(the old formula: €100.03); Friday 23 October, spent €1,342.20 → €982.80
left, €582.80 to spend, 8 days left, €72.85 a day. 1 October falls on a
Thursday, as in 2026. The status the engine returns for them is not shown.

## Visible claims and what supports them

| Visual claim | Backend / tool | Exact field / calculation | Safe to display? |
|---|---|---|---|
| "Your finances, remembered in ChatGPT." | MITA account data, read by every read tool | stored rows per account; any conversation with MITA connected can read them | Yes |
| "Log expenses by chatting" · "I spent €36.80 at Lidl." → Expense recorded, Groceries · Lidl · €36.80 | `add_transaction` | one transaction: amount, category, merchant, date | Yes |
| "How am I doing this month?" → Budget €2,325.00 · Spent €1,124.60 · Left €1,200.40 | `get_budget_status` | `total_planned`, `total_spent`, `total_remaining` | Yes |
| "48% of October's budget used" | from `get_budget_status` | `total_spent ÷ total_planned` (page arithmetic) | Yes |
| "Safe to spend per day €66.70" | `get_budget_forecast` | `safe_daily_limit` = (`remaining_budget` − `savings_set_aside`) ÷ `days_remaining` | Yes, per remaining day — not "today"; bills must be recorded (D above) |
| "for the 12 days left in October" | `get_budget_forecast` | `days_remaining` | Yes |
| "€1,200.40 left − €400.00 savings = €800.40 ÷ 12 days = €66.70" | `get_budget_forecast` | `remaining_budget`, `savings_set_aside`, `days_remaining`, `safe_daily_limit` | Yes |
| "Your €400.00 of savings is never counted as money to spend." | `get_budget_forecast` | `savings_set_aside` excluded from `safe_daily_limit` | Yes |
| (no status badge) | `get_budget_forecast` → `status` | not displayed: the linear pace can mislead (B above) | No — removed from the page until the forecast model is fixed |
| Calendar and strip: days passed, today, days left | `get_budget_forecast` | `days_elapsed`, `days_remaining`, `days_in_month` | Yes — one shade for all days left |
| "Spent so far €1,124.60" | `get_budget_forecast` | `total_spent` | Yes |
| New conversation: Per day €72.85 · Days left 8 · Savings kept €400.00 | `get_budget_forecast` | `safe_daily_limit`, `days_remaining`, `savings_set_aside` four days later | Yes |
| "Saved in your MITA account" | storage | — | Yes |
| "How much can I safely spend per day?" | `get_budget_forecast` | `safe_daily_limit` | Yes; golden prompt `bg-11` has the same meaning; routing of this English wording in real ChatGPT not yet observed |
| "Help me build my monthly budget." | `preview_monthly_budget` → `save_monthly_budget` | deterministic draft, saved only after the user confirms | Yes |
| "I spent €36.80 on groceries today." / "Add the expenses from this receipt to MITA." | `add_transaction` / `add_transactions` | ChatGPT reads the photo; MITA keeps date, amount, category, merchant | Yes |
| "How am I doing against my budget?" | `get_budget_status` | per-category planned, spent, remaining, state | Yes |
| "Create an Emergency Fund goal for €3,000." | `create_savings_goal` | — | Yes |
| "How has my spending changed over the last six months?" | `get_spending_history` | — | Yes |
| "MITA can't move money or access banks." | no payment or bank capability (`scopes.py`) | — | Yes |
| "It does not store your ChatGPT conversations" | `docs/chatgpt-app/data-inventory.md` | — | Yes |
| "ChatGPT answers in its own words, using the figures MITA returns." | no widget; the cards are illustrations | — | Yes |
