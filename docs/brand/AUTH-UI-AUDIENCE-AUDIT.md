# Connect page — audience and product audit (v5 brief, 2026-10-26)

Scope: the public OAuth connect / sign-in / sign-up page (`/oauth/login`,
`app/mcp/auth/pages.py`). Presentation only: the flow (`login.py`), scopes,
CSP, CSRF, rate limits, password and consent semantics are fixed and out of
scope. Sources read: `pages.py`, `demo.py`, `docs/brand/AUTH-UI-DESIGN.md`,
`docs/chatgpt-app/{HANDOFF,tool-catalog,financial-calendar}.md`,
`plugin/mita/plugin.template.json`, `tests_mcp/golden_prompts.json`, the
mobile app's theme and calendar/main screens, the brand guidelines in Figma
(`512WdjnhPJXM8jeHKcg4g8`: "Who we serve", mission/vision/positioning,
imagery) and the v4 screenshots (`docs/chatgpt-app/review/auth-ui-v4/`).

## 0. The product, traced (capability map)

Every row is a published MCP tool (`tool-catalog.md`); the wording in column 2
is a golden prompt or the page's tested example.

| User need | What they can say | MITA tool / feature | What they get |
|---|---|---|---|
| "I don't have a budget" | "Help me build my monthly budget." | `get_setup_status` → `update_financial_profile` → `preview_monthly_budget` → `save_monthly_budget` | a plan from stated income, savings target and saved bills, previewed first and saved only after they agree |
| "Rent and bills catch me out" | "My rent is €700 every month on the first." | `add_recurring_expense`, `get_recurring_expenses` | bills saved with their due dates; shown on the calendar |
| "I lose track of spending" | "I spent €36.80 on groceries today." / several at once / a receipt photo | `add_transaction`, `add_transactions` (ChatGPT reads the photo; MITA stores date, amount, category, merchant only) | the expense in their month, in seconds |
| "I typed it wrong" | "Oops, that lunch was €12, not €21." / "Delete the coffee I added twice." | `list_transactions` + `update_transaction` / `delete_transaction` | the record fixed in plain words |
| "What can I spend?" | "How much can I safely spend per day?" | `get_budget_forecast` (`safe_daily_limit`, savings kept out) | one amount per remaining day |
| "Can I afford it?" | "Can I afford dinner out tonight?" | `get_budget_status` (today's plan and what is left) | an answer from today's plan |
| "Show me my month" | "Show my financial calendar for this month." | `show_financial_calendar` (MCP Apps component), `get_calendar_month` | the month date by date in the chat: plan, spending, bills due, savings apart; save as PNG |
| "Where did it go?" | "Where did my money go in the last 30 days?" | `get_spending_breakdown` | spending by category |
| "Am I improving?" | "How has my spending changed over the last six months?" | `get_spending_history`, `get_financial_climate` | months compared; trends once three months are complete |
| "I want to save for something" | "Create an Emergency Fund goal for €3,000." | `create_savings_goal`, `get_goals` | a goal tracked next to the budget (a target date also sets money aside monthly) |
| "Don't make me repeat myself" | any of the above, in a new chat | the MITA account (OAuth) | the same records in every conversation |

Not in the product (never to be implied): bank connections, payments or
transfers, investing, shared household accounts / several members, custom
categories, editing a goal after creating it, a per-date forecast, anything
about other users.

## A. Audience segments

Brand guidelines ("Who we serve"): primary — young professionals and digital
natives aged 20–35 with stable income but inconsistent spending, who want
"structure, clarity, and daily financial control without complex
spreadsheets or traditional budgeting stress"; secondary — growth-oriented
people building savings goals and wanting proactive guidance. The v5 brief
widens this to: Gen Z and young millennials starting to manage money,
students, young couples, young families combining rent/bills/groceries/
savings, people on low or moderate incomes, people whose money feels
disorganised, people who refuse spreadsheets and jargon, and ChatGPT users who
do not yet see why connecting MITA helps.

What they share: they already talk to ChatGPT; money is a daily worry rather
than a hobby; they want an answer, not a dashboard.

## B. Jobs to be done

1. "Tell me what I can spend without blowing the month." (the core)
2. "Keep track for me — I'll just tell you what I spent."
3. "Don't let rent and bills surprise me."
4. "Help me save something, and keep it out of my spending."
5. "Show me where the money went, without spreadsheets."
6. "Remember all of it, so I don't start from zero in every chat."

## C. Emotional problems

Money avoidance and guilt (people stop looking because looking hurts); the
end-of-month squeeze; "everyone else seems to have it figured out"; low trust
in financial institutions; scarcity reduces bandwidth, so long explanations
lose people. Desired feelings (brief): clarity, control, relief, progress,
confidence — "my financial life feels manageable."

## D. Promises MITA can truthfully make

* Know what you can safely spend each day — MITA works it out from your plan
  and spending, with savings kept out (`get_budget_forecast`).
* Just tell ChatGPT what you spent; fix mistakes the same way.
* See your month date by date, in the chat, and save it as an image.
* Your budget, bills, goals and expenses stay in your MITA account, so every
  new chat starts from them.
* A budget built from what you tell it, saved only after you check it.
* Track a savings goal next to your budget.
* MITA cannot move money and does not connect to your bank; it does not store
  your ChatGPT conversations; usage statistics are optional.

## E. Weaknesses of the v4 page (ranked by user impact)

1. **"What can I ask?" is hidden.** The six prompts — the single best
   onboarding device on the page — sit in a closed `<details>` at the very
   bottom, below the form and a numbered feature list. Most people never open
   it. (Research: users can't use what they can't name; prompt starters exist
   to teach phrasing.)
2. **The page never says plainly what MITA *is* or what you do after
   connecting.** The hero promises a feeling ("safely spend each day") and a
   slogan ("One conversation. Your whole month mapped out."); the mechanism —
   connect, tell ChatGPT what you spend, ask about your month — has to be
   inferred.
3. **The hero shows lifestyle more than utility.** The family photograph takes
   the largest area; the product proof (the tilted month, tiny Space Mono
   digits at 8 px on a phone) is decorative at phone size; the floating
   cards carry the real message but read as a collage.
4. **Navy and yellow dominate; teal and purple are almost unused.** The full
   navy hero plus navy step numbers plus a navy primary button make the page
   feel heavy and bank-like; the brand's teal (savings, progress) and purple
   (planning, intelligence) carry no meaning.
5. **Trust is either legalistic or hidden.** Permission lists are in the
   form (required), but the human facts ("can't move money", "doesn't keep
   your conversations", "statistics optional") are split between a consent
   line and a closed "What MITA keeps" disclosure.
6. **"What MITA adds" is a generic numbered feature grid** (01/02/03), the
   pattern the v4 brief asked to remove; it repeats the hero.
7. **The photo speaks to one segment.** A family of three resonates with young
   families and couples, less with students and singles; as the dominant
   image it narrows the audience.
8. **Desktop leaves the story half-told.** The first viewport shows the hero
   and the form, but the prompts and the reasons to connect sit far below or
   are closed.

## F. Strengths worth keeping

* The headline "Know what you can safely spend each day." — concrete,
  benefit-first, tested wording ("each day", never "today").
* Figures computed by MITA's own code (`demo.py`), labelled fictional — a
  real trust asset.
* The month as a calendar with today ringed and a bill marked — the product's
  visual language (the in-ChatGPT calendar and the app's calendar).
* The sign-in card: clear tabs, labelled fields, all scopes on screen,
  forgery warning, "Then try: …" after connecting.
* No JavaScript, self-hosted assets, reduced motion, axe-clean.
* The family photograph: warm, human, real-life context — useful, in a
  supporting role.

## G. Information hierarchy problems

What/why/how are not in the first screen as plain sentences; the most
actionable content (prompts) is last and closed; trust facts are scattered;
"what MITA adds" repeats the hero instead of answering "why connect?".

## H. Visual hierarchy problems

Everything in the hero competes (photo, slab, four floating cards, caption,
check line, two buttons); the slab's digits are unreadable on phones; below
the hero the page turns into a plain form and a list — the brand disappears.

## I. Trust problems

No visible "MITA can't move money" outside the consent box; nothing says
what is stored vs not in plain view; the AI photo carries no context. (Gen Z
trust in financial institutions is low — EY: 42 % vs 59 % of millennials —
so plain limits matter more than badges.)

## J. Onboarding / discoverability problems

No "how it works" in three steps; no prompts in view; nothing tells people
they can type naturally, fix mistakes, or send a receipt photo.

## K. Proposed content hierarchy

1. **Hero** — what it is, why it matters, how it works (3 steps), proof (a
   question and MITA's answer), Connect.
2. **"Just ask ChatGPT"** — six prompt cards by intent (Plan, Track, Check,
   Save, Look back, See), each with what you get, then four more sentences.
3. **Sign in / create account** (phones: right after the prompts; desktop:
   the side column, beside the hero).
4. **"You stay in control"** — five plain facts and the full wording one tap
   away (phones: right after the form; desktop: under it).
5. **"Your whole month, at a glance"** — the calendar demo (photo + month +
   figures) as a product preview.
6. **"Why connect MITA?"** — without vs with MITA, three rows.
7. Final "Connect MITA" link; footer.

## L. Visual system

| Role | Colour | Use |
|---|---|---|
| Structure, text, product surfaces | Navy `#193C57` | headings, body, the answer card, the month panel, primary button |
| Action, attention | Yellow `#FFD25F` | Connect buttons, the headline marker, key figure, Check card |
| Savings, progress, "within plan" | Teal `#14B8A6` (ink `#0B6E64`, tint `#CCFBF1`) | savings kept, progress bars, Save card, trust ticks |
| Planning, intelligence, the assistant | Purple `#6B73FF` (ink `#454CC8`, tint `#EEF0FF`) | eyebrow, step numbers, Plan and Look back cards, bills marker |
| Warnings only | Red `#F44336` (text `#BA1A1A`) | the sign-in error's border and text only — no marketing use; the logo keeps its red quadrant |
| Warmth | Cream `#FFF9F0` | page background; white cards |

Contrast (WCAG): navy on cream 11.0, on yellow 8.0; `#4C6679` on cream 5.8;
purple ink `#454CC8` on white 6.7, on its tint 5.9; teal ink `#0B6E64` on
white 6.1, on light teal 5.4; on navy: cream 11.0, light teal `#5EEAD4` 7.8,
light purple `#A9AEFF` 5.6. Raw `#6B73FF` (3.8) and `#14B8A6` are used for
fills and large marks only.

Type: Sora 700 for the headline and section titles; Manrope for UI, body and
the prompts; Space Mono for figures, labels and step numbers (brand roles).
Cards: white, radius 20 (items) / 28 (panels), soft navy shadows; an intent
chip on each prompt card. Rhythm: 8-px grid; sections 44 px apart on phones,
56 px from 560 px, 64–72 px on desktop.

## M. Mobile-first behaviour

Base CSS is the phone. At 390 × 844 the first screen holds the topbar
(Connect pill), headline, one-sentence explanation, the three steps as a
numbered strip, the question-and-answer proof and the Connect button (at 320
and 360 px the button is just below the fold; the pill is always in view).
Prompt cards are one column (two from 560 px); the form follows the prompts;
the Connect pill jumps to it from anywhere above. On phones the month panel is
the photograph with the calendar laid flat over its lower edge (every amount
fits at 320 px); the tilted 3D layout starts at 560 px. No horizontal scroll
at 320 px.

## N. Motion

CSS only; off under `prefers-reduced-motion`; the still state is complete.
Hero: the question bubble rises, a typing indicator, then MITA's answer card
rises and its figures and savings bar settle — the workflow in two seconds.
Prompt cards and sections rise as they scroll in where the browser supports
scroll-driven animations (`animation-timeline: view()`, behind `@supports`);
elsewhere they are simply there. The month keeps its tilt-in and the one
fictional expense flying into today.

## O. Prompt / cheat-sheet strategy

Six intents in the order a new user meets them: **Plan** (build a budget),
**Track** (tell an expense; receipt photos too), **Check** (safe amount per
day), **Save** (a goal), **Look back** (where the money went), **See** (the
calendar, with a two-week preview — last, because it is the tallest card and
leads into the month section). Then "More to try": save a bill, fix an
expense, "Can I afford dinner out tonight?", six months of spending. Each
card: an intent chip, the exact sentence in quotes, and what you get in one
line. They are not buttons
(nothing to click — they work in ChatGPT after connecting) and say so: "Type
it the way you'd say it." Every sentence is executable today (golden prompts;
tested against published tools).

## P. Capabilities that must be visible

Safe amount per day; recording by message (and receipt photo); fixing a
record; the monthly budget preview; bills; the calendar (and PNG); savings
goals; spending breakdown/history; memory across chats; the limits.

## Q. Must not claim

Bank connection, payments/transfers, investing; "free", pricing, premium,
trials; testimonials, customers, "families trust"; encryption, "bank-grade",
"read-only"; on-track/danger statuses; a safe amount "today"; a budget for
each/every day; household profiles; editing goals; unpaid bills reserved in
the safe amount (not shipped); anything about ChatGPT's own memory features.

## Research notes (what helps, why)

Evidence is mostly industry studies and design case studies; treated as
direction, not proof.

* Outcomes over features: users connect with what changes for them, not a
  list of features (WageStream onboarding redesign —
  contra.com/p/kom6lr2Z-wage-stream-onboarding-redesign).
* Concrete sample utterances beat a blank box; 3–4 scannable task labels;
  never advertise what the assistant cannot do (aiuxplayground.com prompt
  starters / empty state; conversational-UI reference attributing the
  blank-box failure to NN/g).
* Show value and explain data use before asking for commitment; set
  expectations of the steps ahead (Bima, "How to design an effective
  onboarding process for fintech apps"; Mint onboarding review on
  reallygoodux.io; Albert's one-step-at-a-time onboarding on goodux.appcues.com).
* Scarcity and money anxiety reduce decision bandwidth; shame and avoidance
  are barriers; budgeting tools can heighten frustration if they only expose
  problems (ZHAW "Budget Compass", 2026; Filene pilot with 18–34-year-olds;
  St. Mary's University poster, 2026, preliminary; The Financial Brand on
  financial avoidance, citing Deloitte: about a third of Gen Z feel
  financially insecure, over half live paycheck to paycheck).
* Online budget planners help low-income households more
  (Review of Behavioral Finance, 2024 — ideas.repec.org/a/eme/rbfpps/rbf-04-2024-0106.html);
  71 % of lower-income US consumers worry about money (PYMNTS, 2025).
* Gen Z trust in financial institutions is low (EY, cited by
  contentworks.agency: 42 %); they expect speed and plain, transparent
  copy. Students want specific, actionable help and a human tone
  (Gold/Blackbullion poster).

Applied: lead with the outcome, show the mechanism in three steps, put the
exact sentences in view, keep every block short, never judge, state limits
plainly.

## Design spec (v5)

| # | Section | Purpose | Copy |
|---|---|---|---|
| 0 | Topbar | brand, a jump to the form | full-colour logo · "Connect ↓" (phones and tablets; the form is in view on desktop) |
| 1 | Hero | what / why / how in one screen | eyebrow "Your budget, inside ChatGPT"; H1 "Know what you can **safely spend** each day."; "MITA connects to ChatGPT and keeps your budget, bills, savings and expenses — so you can just ask."; steps "Connect MITA · Say what you spend · Ask about your month"; proof: "How much can I safely spend per day?" → MITA's answer card (amount a day, days left, savings kept, next bill, groceries bar) with "Fictional example, worked out by MITA. Connected, ChatGPT uses your own records."; one button "Connect MITA ↓" (phones and tablets) |
| 2 | Just ask ChatGPT | teach exact phrasing | "Just ask ChatGPT" · "No commands, no spreadsheets — type it the way you'd say it." · six cards · "More to try" (four sentences) · "These work in ChatGPT as soon as MITA is connected." |
| 3 | Sign in / create account | act | unchanged card (tabs, fields, all scopes, limits, statistics box, buttons, "Then try", forgery warning) |
| 4 | You stay in control | trust | can't move money or reach your bank · keeps money records, not your chats · receipt photos stay in ChatGPT · statistics only if you tick the box · disconnect any time · "What MITA keeps, and what it doesn't" (closed `<details>`, the full sentences) |
| 5 | Your whole month, at a glance | product preview | "Every day's plan and spending, bills on their dates and savings kept apart — right in the chat, and as an image you can save." · legend · the navy month panel (photo, month, safe amount; savings, groceries, bill and a flying expense from 560 px) · fictional caption |
| 6 | Why connect MITA? | the difference | rows "Your numbers", "The maths", "Your month" — without MITA vs with MITA |
| 7 | Close | one more way in | "Ready when you are." · "Connect MITA ↑" |

Desktop (≥ 1040 px): a main column (the hero, then the prompts in two columns)
beside a side column (the sign-in card, then "You stay in control"); below
both, the month panel beside its text, "why" as three columns, the close.
Tablet (560–1039): two-column prompts, single column otherwise.

## v5.1 refinement and v5.2 polish — the final page (owner reviews, 2026-10-26)

v5's direction is kept: the headline and its marker, the question → MITA's
answer proof with computed figures, the brand system, product left / form
right on desktop, the calendar preview, the trust facts, CSS-only motion. What
changed, and why:

* **Shorter path to the form.** The person already chose to connect; this is
  not cold-traffic marketing. Phones: hero → four everyday questions → sign-in
  card → "You stay in control" → the month → "More things you can ask" → the
  closing line. At 390 × 844 the form starts at 1,470 px (v5: 2,220) and the
  page is 3,982 px (v5: 4,893). The hero's three-step strip is gone: the
  lede, the proof and the four questions already say how it works.
* **Four primary questions, four different abilities:** Plan ("Help me build
  my monthly budget." — a draft from income, saved bills and the savings
  target, saved only after the person checks it), Track ("I spent €36.80 on
  groceries today."), See ("Show my financial calendar for this month.") and
  Decide ("Can I afford dinner out tonight?" — `get_budget_status`: what is
  left today and on each category's line). The safe amount per day is the
  hero's own question and appears nowhere else; every sentence on the page
  appears once (tested). Bills, Save, Fix, Look back and Trends are in "More
  things you can ask", one line each.
* **"Why connect MITA?" removed.** Its three-column without/with table
  repeated the hero and the questions. Its point survives as the page's last
  word, one line and no problem statement: "With MITA, ChatGPT answers from
  *your real month*." — nothing about ChatGPT's own memory (section Q).
* **Fewer boxes.** White rounded containers stay only where they stand for
  product UI: MITA's answer, the sign-in card, the calendar panel. Questions,
  trust facts and the extra sentences are rows on the page (icon tiles,
  hairline dividers); section labels only where they orient ("What can I
  ask?", "In the chat"). The trust facts lead with their key words in bold
  ("MITA can't move money", "Keeps money records,", "Receipt photos",
  "Disconnect") so they scan (v5.2: 15 px text, rows with dividers, even
  wrapping).
* **Lede:** "MITA remembers your budget, bills, savings and spending, so
  ChatGPT can answer with your real numbers." "Keeps your … savings" could
  read as MITA holding money; "remembers" says it holds what you tell it
  (there is no bank connection), and the second half says why it matters.
* **Less repetition:** the hero caption is one sentence; on phones the
  calendar panel drops the floating figure cards (the hero shows those
  figures); the legend fits one row.
* **Desktop:** main column = hero, the four questions (2 × 2), the extra
  sentences (two columns); side column = the card and the trust facts; then
  the month panel and the closing line full width. Rows are 40 px apart on
  desktop (the month text starts level with its panel), so the page is
  2,295 px at 1280 and 1440.

## Ideas that need JavaScript (proposed, not implemented)

* **Copy a prompt** with one tap (`navigator.clipboard`): needs `script-src`
  with a hashed or self-hosted script. Weakens the audit's "no script"
  control; would need a content-hashed file under `/oauth/assets/`, no
  inline handlers, and a review of clipboard access in ChatGPT's in-app
  browser. Deep links to `chatgpt.com/?q=…` are not an alternative: they
  would leave the OAuth flow before the connection exists.
* **Live password checklist** ticking each rule as the person types: script
  reading the password field in the page — acceptable only as self-hosted
  script, never sending anything.
* **Show/hide password** (deliberately absent since v1).
* **Counting-up figures and scroll reveals for older Safari** (IntersectionObserver):
  cosmetic; not worth a script on a credential page.
