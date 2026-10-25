# Auth UI — design inventory

The ChatGPT sign-in / sign-up / consent page (`/oauth/login`) and its error
pages. Code: `app/mcp/auth/pages.py` (markup, CSS, copy), served by the MCP
service; fonts and favicon in `app/mcp/auth/static/`. Designed mobile first:
ChatGPT opens it in its in-app browser. Current version: the premium
redesign (v4, below); v3 and v2 are kept below as history. The in-ChatGPT
calendar component has its own rules: docs/chatgpt-app/financial-calendar.md.

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
  `script-src`; `img-src 'self'` for the self-hosted photograph,
  `font-src 'self'` for the three self-hosted fonts).
* Fonts: WOFF2 subsets built by `scripts/mcp/build_auth_fonts.py` — Manrope
  and Sora variable (400–700) from the app's OFL files, Space Mono from
  google/fonts (SHA-256 pinned); 74 KB together, cached as immutable.
* Motion (v4): CSS only and decorative — the photo settles, the month tilts
  in, its dates appear, MITA's figures rise, one fictional expense flies into
  today; the end state is the still design. Under `prefers-reduced-motion`
  every animation and transition is off and the flying expense is hidden;
  nothing else starts invisible (tested).
* Copy states facts from `docs/chatgpt-app/data-inventory.md`; demo figures
  are fictional and labelled so. No "bank-grade", "encrypted", "free" or
  similar claims (tested).
* Mobile first: the base CSS is the phone layout; `min-width` queries only
  add (560 px: wider cards, the three limits side by side; 1040 px: the
  sign-in card as a right-hand column level with the logo). Order, from the
  top: headline, one line of value, the example, the sign-in card, limits,
  closed secondary details. Tested.
* Permissions: the five scope titles are always on screen; each one's
  explanation and the full "cannot move money" sentence are in a native
  `<details>` ("View permission details"), closed by default. Tested.
* The example's figures are what MITA's forecast engine returns for them
  (`test_the_example_is_what_the_forecast_engine_returns`), it is labelled
  "Fictional example", and its arithmetic is one tap away and tested.
* No calendar on this page: a day-by-day calendar needs per-day data and
  belongs in the signed-in product ("Spending calendar", below).
* No forecast status on the page — no "On track", "warning" or "danger"
  badge (owner decision 2026-10-23, tested). `get_budget_forecast` still
  returns `status` unchanged; its linear pace counts rent paid on the 1st as
  daily spending, so it can mislead until the forecast model is fixed in a
  dedicated task (below).
* Review screenshots, produced by `scripts/mcp/auth_ui_screenshots.py`:
  `docs/chatgpt-app/review/auth-ui-v3/` (current), `auth-ui-v2/` (mobile
  first, `1e24bf4`) and `auth-ui/` (first version, `ee388c0`).

## Premium redesign (v4, 2026-10-24)

The owner did not approve v3: technically sound, but visually generic, too
static, emotionally disconnected, and it did not show what MITA can do. Brief:
a distinctive, editorial, premium first screen; the headline kept; directly
under it, show how MITA turns expenses into a personal calendar; a real-looking
young family at home; a 2.5D calendar as the centerpiece with category budgets,
the daily amount, protected savings and upcoming commitments around it; depth,
light and polished motion — without hurting the figures' readability; every
OAuth disclosure and control kept; fictional data labelled.

**Composition.** A navy hero — full-bleed with rounded lower corners on phones,
a rounded navy panel beside the sign-in card from 1040 px:

1. Top bar: the logo in the guidelines' inverted variant (monochrome Mita
   yellow on navy, Logo Variants), "for ChatGPT", and on phones a yellow
   "Connect ↓" pill to the form (hidden on desktop, where the card is visible).
2. "Know what you can **safely spend** each day." (Sora; "safely spend" in Mita
   yellow; a no-break space keeps "each day." together).
3. "One conversation. Your whole month mapped out." and "Track spending, plan
   each day and protect your savings, right inside ChatGPT."
4. The example (`aria-hidden` with a text summary for screen readers): the
   photograph; the month as a tilted white slab (CSS 3D: perspective, rotateX/Y,
   a sheen, a thickness edge) with each date's spending, today, the plan on the
   dates ahead (dashed) and the bill due; four floating cards with MITA's
   figures — Savings kept, Safe to spend (a day · days left), Groceries (of
   planned), Home internet (due). Labelled "Fictional example" on the slab and
   in the caption.
5. "ChatGPT answers with your own records and MITA's figures." and, on phones,
   "Connect MITA ↓" / "Create account" (anchors to the form; the tabs keep
   their links).

Then the sign-in card (unchanged flow and controls; its tab links now land on
`#auth`; "Then try" suggests the calendar after signing in and a budget for a
new account), then "What MITA adds to ChatGPT" (01 Your records in every chat,
02 Figures MITA works out, 03 Your month on a calendar) and two closed details
(What can I ask ChatGPT? — six prompts; What MITA keeps, and what it doesn't —
including the limits that v3 showed as a grid).

**Removed from v3:** the four-figure snapshot card and its arithmetic
disclosure (the figures live in the slab's cards now), the "Clear limits. Your
control." grid (its sentences are in the consent box and the details), the
dotted cream hero.

**The photograph.** AI-generated for MITA on 2026-10-24 with Figma AI
(`gpt-image-2.5-sunburst`, file `lhx381krLLUJBPDRCkVFXC`, owner decision): no
real person, so no model release; described as "Illustration: …" in its alt
text; never captioned as a user, customer or testimonial (tested). Served from
`/oauth/assets/` as WebP: `hero-family-640.webp` (26 KB) and
`hero-family-1100.webp` (52 KB), `srcset`/`sizes`, intrinsic size set.

**The example month** (`app/mcp/auth/demo.py`), fictional and computed by
MITA's own code: allocations of a reviewed budget (plan €2,340.00 with €400.00
savings and rent, utilities and internet as saved payments) laid out by
`monthly_plan_service.month_calendar`; expenses within each date's plan and in
categories whose plan line has the same name, so MITA's automatic rebalancing
would not touch the plan (F-2, F-8); figures from `build_calendar` and the
forecast engine: Monday 19 October, 12 days left, €62.10 a day, €400.00 kept,
groceries €189.85 of €420.00, Home internet €30.00 due 27 Oct (tested).

**Where the buttons end** (page px; "below" = scroll needed). v4 trades the
form's position on phones for the hero, and puts the way in on the first
screen instead: the "Connect ↓" pill in the top bar on every phone and tablet,
and "Connect MITA ↓" at the end of the hero.

| Viewport | Sign in | Create account | Card starts | "Connect MITA" (hero) |
|---|---|---|---|---|
| 390×844 | 1,613 (769 below) | 1,767 (923 below) | 948 | 908 (64 below) |
| 393×852 | 1,555 (703 below) | 1,767 (915 below) | 890 | 908 (56 below) |
| 430×932 | 1,565 (633 below) | 1,719 (787 below) | 900 | 860 — on screen |
| 768×1024 | 1,609 (585 below) | 1,743 (719 below) | 966 | 912 — on screen |
| 1280×800 | 688 — on screen | 843 (43 below) | 24 | — |
| 1440×900 | 688 — on screen | 843 — on screen | 24 | — |
| 1440×1000 | 688 — on screen | 843 — on screen | 24 | — |

Desktop is as in v3 (the card is the right-hand column).

### Visible claims and what supports them (v4)

| Visual claim | Backend / tool | Exact field / calculation | Safe to display? |
|---|---|---|---|
| "Know what you can safely spend each day." | `get_budget_forecast` | `safe_daily_limit`, one amount per remaining day | Yes ("each day", never "today") |
| "One conversation. Your whole month mapped out." | `show_financial_calendar` | the month, date by date | Yes |
| "Track spending, plan each day and protect your savings, right inside ChatGPT." | `add_transaction(s)`, `preview_monthly_budget`/`save_monthly_budget`, `savings_set_aside`, `show_financial_calendar` | — | Yes |
| The slab: spending per date, today, plan on the dates ahead, the bill due | `build_calendar` over the fictional month | `days[].spent`, `planned`, `day_kind`, `bills` | Yes — fictional, labelled, recomputed by a test |
| "Safe to spend €62.10 a day · 12 days left" | `get_budget_forecast` | `safe_daily_limit`, `days_remaining` | Yes — fictional, recomputed |
| "Savings kept €400.00" | `get_budget_forecast` | `savings_set_aside` | Yes — fictional, recomputed |
| "Groceries €189.85 of €420.00 planned" | `get_budget_status` / `get_calendar_month` | the line's `spent` / `planned` | Yes — fictional, recomputed |
| "Home internet €30.00 due 27 Oct" | `get_calendar_month` | `bills[]` from a saved monthly payment | Yes — fictional, recomputed |
| "Fictional example, worked out by MITA. Connected, ChatGPT shows your own month." | `show_financial_calendar` | the user's own month | Yes |
| "ChatGPT answers with your own records and MITA's figures." | every read tool | stored rows, MITA's computations | Yes |
| 01 "Your records in every chat" | stored rows read by every tool | transactions, `daily_plan`, goals | Yes |
| 02 "Figures MITA works out … with money for savings left out" | `get_budget_forecast` | `safe_daily_limit` excludes `savings_set_aside` | Yes |
| 03 "Your month on a calendar … and save it as an image" | `show_financial_calendar` + the component's Save as PNG | `financial-calendar.md` | Yes (the image is kept through the host download or shown to keep) |
| The photograph | — | AI-generated illustration | Yes — alt text says illustration; no customer claim |
| Consent: five scope titles, "MITA can't move money or access banks", details | `scopes.py` | `SCOPE_TITLES`, `SCOPE_DESCRIPTIONS` | Yes (tested) |
| "What can I ask ChatGPT?" (six prompts) | `show_financial_calendar`, `get_budget_forecast`, `add_transaction`, `preview_monthly_budget`, `create_savings_goal`, `get_spending_history` | — | Yes (tested map) |
| "What MITA keeps, and what it doesn't" | `data-inventory.md`, `product-analytics.md`, `fingerprint.py` | — | Yes |

Accessibility: axe-core WCAG 2.2 AA, 0 violations in 8 states (sign in,
create account, sign-up mismatch, sign-in failed × WebKit phone and Chromium
desktop); text on navy ≥ 8:1. Review screenshots:
`docs/chatgpt-app/review/auth-ui-v4/` (phone first, including two motion
frames). Not shown, as before: a forecast status, a "safe
to spend today" figure.

## Conversion redesign (v3, 2026-10-23)

The owner's review of v2 live from ChatGPT: polished, but overloaded with
explanations and examples — a new user could not tell within seconds what
MITA solves, why they need it next to ChatGPT, or what they get after
connecting. Brief: one benefit headline, one sentence of value, one compact
financial preview, the sign-in right after; trust in brief; everything
secondary progressive; no calendar on this page.

**Order now (phone; wider screens keep it):** logo + "for ChatGPT" → "Know
what you can safely spend each day." → "Just ask ChatGPT. MITA remembers your
expenses, budget and savings goals across chats." → the example (the
question, then safe to spend per day, spent this month, protected savings,
days left; the arithmetic in a closed "How is €66.70 worked out?") → the
sign-in card (unchanged flow: tabs, fields, five permission titles,
usage-statistics choice, button, forgery warning) → "Clear limits. Your
control." (three lines) → two closed details: "What can I ask ChatGPT?"
(five prompts) and "What MITA keeps, and what it doesn't".

**Removed:** the four-step conversation walkthrough (record / understand /
pace / remember), the month calendar and the 31-day strip, the seven prompt
cards, the three "How MITA works" step cards, the entrance animation. The
phone page is 1,876 px long instead of about 4,100.

**Headline wording.** The brief's promise reads "Know what you can safely
spend today". The page says "each day": `safe_daily_limit` is one amount for
every day left in the month (today counts as elapsed), not a figure for
today, and the owner's 2026-10-23 rule — tested — forbids "safe to spend
today". `get_budget_status.today` (today's spending plan minus today's
spending) exists, but it is a different number; using both on one page
would mislead.

Where the primary button ends (page px; "below" = scroll needed to see it);
v2 is `1e24bf4`, v3 adds the four-figure example above the card:

| Viewport | Sign in: v2 | v3 | Create account: v2 | v3 | v3: card starts |
|---|---|---|---|---|---|
| 390×844 | 983 (139 below) | 1,095 (251 below) | 1,137 (293 below) | 1,249 (405 below) | 432 |
| 393×852 | — | 1,097 (245 below) | — | 1,251 (399 below) | 434 |
| 430×932 | 985 (53 below) | 1,099 (167 below) | 1,139 (207 below) | 1,253 (321 below) | 436 |
| 768×1024 | 1,043 (19 below) | 1,152 (128 below) | 1,177 (153 below) | 1,286 (262 below) | 509 |
| 1280×800 | 686 — on screen | 686 — on screen | 841 (41 below) | 841 (41 below) | 22 |
| 1440×900 | 686 — on screen | 686 — on screen | 841 — on screen | 841 — on screen | 22 |
| 1440×1000 | 686 — on screen | 686 — on screen | 841 — on screen | 841 — on screen | 22 |

The trade-off is deliberate: on phones the first screen now carries the
whole promise — headline, value, the complete example — plus the start of
the form (tabs, e-mail, password); the button follows the five permission
titles and the usage-statistics choice, which must come before it, one
short scroll down. Desktop is unchanged: the button is on the first screen.

## Mobile-first refinement (v2, 2026-10-23, `1e24bf4`)

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

**The calendar (v2 only, removed in v3).** It showed where the month stood —
days passed, today, the days left — with `safe_daily_limit` as one shade on
every remaining day. It never showed a budget per date or spending per day.
v3 replaces it with the four-figure example; the day-by-day calendar is
specified for the signed-in product ("Spending calendar", below).

**The example figures** (fictional; recomputed with `compute_forecast` by a
test): plan €2,325.00 with €400.00 Savings; Monday 19 October, spent
€1,124.60 → €1,200.40 left, €800.40 to spend, 12 days left, €66.70 a day
(the old formula: €100.03). v2 also showed Friday 23 October (€72.85 a day,
8 days left); v3 shows Monday only. The status the engine returns for them
is not shown.

## Visible claims and what supports them (v3)

| Visual claim | Backend / tool | Exact field / calculation | Safe to display? |
|---|---|---|---|
| "Know what you can safely spend each day." | `get_budget_forecast` | `safe_daily_limit` — one amount for each remaining day | Yes, as "each day"; not "today" (see "Headline wording") |
| "Just ask ChatGPT." | MITA's tools, called by ChatGPT | — | Yes |
| "MITA remembers your expenses, budget and savings goals across chats." | stored rows per account, read by every read tool | transactions, `daily_plan`, goals | Yes |
| "How much can I safely spend per day?" | `get_budget_forecast` | `safe_daily_limit` | Yes; golden prompt `bg-11` has the same meaning |
| "Safe to spend €66.70 a day" | `get_budget_forecast` | `safe_daily_limit` = (`remaining_budget` − `savings_set_aside`) ÷ `days_remaining` | Yes — fictional, labelled "Fictional example", recomputed by a test |
| "for the rest of October, with savings left out" | `get_budget_forecast` | `days_remaining`; `savings_set_aside` excluded | Yes |
| "Spent this month €1,124.60" | `get_budget_forecast` (also `get_budget_status`) | `total_spent` | Yes |
| "Protected savings €400.00" | `get_budget_forecast` | `savings_set_aside` | Yes |
| "Days left 12" | `get_budget_forecast` | `days_remaining` (the days after today) | Yes |
| "How is €66.70 worked out?": budget − spent = left; − protected savings = to spend; ÷ days left = a day | `get_budget_forecast` | `total_planned`, `total_spent`, `remaining_budget`, `savings_set_aside`, `days_remaining`, `safe_daily_limit` | Yes; the arithmetic is tested |
| "A bill in your plan counts as spent once you record it as an expense." | `get_budget_forecast` method text | an unrecorded bill stays in `remaining_budget` (D above) | Yes — states the limit |
| "ChatGPT writes the answer using MITA's figures." | no widget; the card is an illustration | — | Yes |
| (no status badge, no calendar) | `status`; per-day data | not displayed (B above; no per-day tool) | No — not on this page |
| The five permission titles, their details | `app/mcp/auth/scopes.py` | `SCOPE_TITLES`, `SCOPE_DESCRIPTIONS` | Yes (tested) |
| "MITA can't move money or access banks." / "Can't move money: no payments, transfers or trades, and no connection to your bank." | no payment, trading or bank capability | — | Yes |
| "Your records, not your chats: MITA stores the financial records its features need. It does not store your ChatGPT conversations." | `docs/chatgpt-app/data-inventory.md` | — | Yes |
| "You stay in control: Disconnect MITA in ChatGPT at any time; changing your MITA password also ends its access." | ChatGPT's app settings; grants are bound to the password (`fingerprint.py`) | — | Yes |
| "What can I ask ChatGPT?": the safe-per-day question, "I spent €36.80 on groceries today.", "Help me build my monthly budget.", "Create an Emergency Fund goal for €3,000.", "How has my spending changed over the last six months?" | `get_budget_forecast`, `add_transaction`, `preview_monthly_budget` → `save_monthly_budget`, `create_savings_goal`, `get_spending_history` | — | Yes (tested map) |
| "What MITA keeps, and what it doesn't": records stay in the account; receipt photos stay in ChatGPT; usage statistics optional, opting out deletes linked events | `data-inventory.md`, `product-analytics.md` | — | Yes |
| The usage-statistics box starts unticked; on Sign in, "Leaving it unticked keeps any choice I made before." (owner decision 2026-10-25) | `login._record_usage_choice`, `test_registration.py` | — | Yes |

## Spending calendar — the signed-in product (design of 2026-10-23; built in ChatGPT on 2026-10-24 — docs/chatgpt-app/financial-calendar.md)

Not on the sign-in page: a calendar is only honest with per-day data, which
the page's fictional example does not have and ChatGPT's tools do not
return. Where it belongs: the MITA app's Calendar screen, which exists
(`mobile_app/lib/screens/calendar_screen.dart`,
`calendar_day_details_screen.dart`, data from `app/api/calendar/routes.py`);
an in-ChatGPT version would need a new read tool returning per-day figures
and a UI component (script, its own CSP, app review) — an owner decision.

**Month header** — the same four figures as the sign-in example, so the
product keeps the page's promise: safe to spend per day (`safe_daily_limit`),
spent this month, protected savings (`savings_set_aside`), days left.

**Each day cell** (user's time zone, money to the cent):

| Day | Shows | Data |
|---|---|---|
| Past | amount spent; "+€x" and an over icon when spending passed that day's spending plan | non-deleted expenses that day; the day's `daily_plan` rows **excluding** `SET_ASIDE_CATEGORIES` |
| Today | a navy ring with a yellow outline; spent so far and what is left of today's spending plan | `get_budget_status.today` semantics |
| Future | lighter, dashed outline, the planned spending for that date labelled "plan" — never "safe to spend"; no spending | the day's spending rows of `daily_plan` |

Past and future must differ in more than colour (solid vs dashed, amount vs
"plan" label); an overrun shows text and an icon, not only red. Each cell is
a button with a full label ("Tuesday 14 October: spent €42.10 of a €38.00
plan, €4.10 over"); at 390 px seven columns leave 51 px per cell, above the
44 px tap target.

**Selected day** — a bottom sheet on phones, a side panel on wide screens:
the date; spent vs that day's spending plan; what was set aside that day,
shown separately; the day's expenses (merchant, category, amount, time) with
edit; for a future date its planned categories and "No spending yet".

**Gaps found in the current app while specifying this (not fixed here):**
the saved-calendar endpoint's day `limit` sums every plan row, savings and
goal reservations included (`app/api/calendar/routes.py`), so the app shows
set-aside money as daily spending room — the calendar counterpart of the
safe-daily fix; and the screen reads `limit` / `spent` as integers
(`calendar_screen.dart`), where the design needs cents.
