# MITA 2.8 — personalized onboarding and regional context (Milestone 0, 2026-11-04)

Architecture assessment written before any 2.8 code. Branch
`feat/chatgpt-auth-ui` at `73b6921` (clean, = origin). Staging verified at
the same time: `/health` → `{"version":"2.7.0"}`; Railway deployment
`390805cb` SUCCESS, commit `2ab2e0f`. MCP suite on the head: 746 passed.

Rule that does not change: **ChatGPT interprets words; MITA stores only what
the user confirmed and computes every figure deterministically.** Nothing in
2.8 lets a statistic, a price or the model change a user's amount or a saved
plan.

## 1. What exists and is reused

| Need in the brief | Already in 2.7.0 | 2.8 change |
|---|---|---|
| Setup status, resume after reconnect | `get_setup_status` (`queries/setup.py`): profile fields, `missing_fields`, `suggested_next_step`, `spending` | add a derived `onboarding` object (stage, readiness, topics); no new read tool |
| Save stated facts | `update_financial_profile` → `users` + `mcp_user_profiles.*_confirmed_at` | new optional facts (country, income regularity, pay schedule, minimum income, regional switch, setup answers) on the same tool |
| Obligations (rent, loans, phone…) | `add_recurring_expense`, own `bill:` line, due dates (F-8), paid only by a linked expense | reuse unchanged; record "no regular payments" as an answer |
| Categories that apply / not | `spending_patterns` (0042): `planned`, `flexible`, `not_applicable`, source `user_confirmed` only | a `flexible`/`planned` pattern on a MITA line is the "user confirmed it applies" signal |
| User's own amounts | F-11 `my:` lines (`budget_lines`), never changed by MITA | reuse unchanged |
| Frequencies, dates | `spending_schedule` (stated days; "about weekly" → proposed dates, labelled) | reuse unchanged |
| Preview → confirm → save | `preview_monthly_budget` (read-only, signed digest) → `save_monthly_budget` | the draft also respects the onboarding answers; the digest already covers every allocation, so a changed answer invalidates a preview |
| Irregular expenses | one-time `scheduled_expenses` on their date; dated goals reserve money monthly | reuse; a monthly set-aside is only ever a goal the user creates |
| Voice | ChatGPT's own input; MITA receives structured arguments only | skill wording only |
| Region | `users.country` (ChatGPT sign-up stores `ZZ`), `users.region`; engine profiles `app/config/country_profiles/{US,US-*,GB,DEFAULT}.yaml` | confirmed country stored on `users.country`; the preview's region text made truthful |

Not reusable: the engine's region profiles are MITA's own unsourced weights
(no BG profile — Bulgaria falls back to DEFAULT, exactly like `ZZ`); income
tiers compare local-currency income with USD thresholds. They stay the
"generic MITA default" (priority 7) and are labelled so; 2.8 does not touch
them.

## 2. Gaps found (confirmed in code)

1. **Silence is treated as "yes".** Every preview includes all of MITA's
   default lines — `transport gas` (fuel) and `transport public` for
   everyone, `insurance medical` — unless the user explicitly marks them
   `not_applicable` (F-12). A user without a car gets a fuel line by
   assumption.
2. **"None" is not an answer.** A user with no regular payments stays on
   `ask_about_obligations` and every preview says "default draft … assumes
   there are none"; "the user skipped" and "never asked" look the same.
3. No income regularity, pay schedule or minimum income; variable income is
   planned as if every month matched.
4. No confirmed country (ChatGPT accounts are `ZZ`), no use of ChatGPT's
   coarse location hint, no regional statistics anywhere.
5. The preview says "MITA's allocation rules for region BG are used" for a
   region that has no rules of its own.
6. A preview line does not say whether the user confirmed the category or
   MITA merely suggested it.

## 3. Decisions, including where the brief is challenged

* **No city, address or coordinates as tool inputs.** OpenAI's current plugin
  guidelines (re-read 2026-11-04, `developers.openai.com/plugins/plugin-guidelines.md`):
  "Avoid requesting raw location fields (for example, city or coordinates) in
  your input schema. When location is needed, obtain it through the client's
  controlled side channel" and "If needed, rely on the coarse geographic
  location shared by the system. Do not request precise user location data".
  `tests_mcp/test_tool_contract.py` already rejects such field names. 2.8
  stores the **country** (ISO 3166-1 alpha-2) only. No official source in
  §6 measures prices by city, so a stored city would serve no figure today;
  city-level work belongs to Milestone 3, through the side channel.
* **`_meta["openai/userLocation"]` is a suggestion, never a fact.** The
  reference lists `city, region, country, timezone, longitude, latitude` and
  says servers "must tolerate their absence". MITA reads only `country`,
  checks it against ISO 3166-1, offers it as a question ("Do you normally
  live and spend money in Bulgaria…?") and stores the user's answer. The
  hint is never stored, logged, sent to analytics or echoed beyond the
  country code; coordinates are dropped on arrival.
* **No "people financially supported" field.** It would change no figure
  (household size does not change MITA's rules either) and OpenAI asks for
  no "just in case" fields. Money sent to others is a regular payment and is
  budgeted as one.
* **Unknown ≠ zero, unknown ≠ yes.** Four line states, as the brief asks:
  `user_confirmed` (the user's own line, or a stated pattern on a MITA
  line), `mita_suggested` (MITA's default, included, unconfirmed),
  `unknown` (not mentioned — not budgeted in a personalized plan, listed
  with the amount MITA would suggest), `not_applicable` (excluded; never
  returns by itself). Money not earmarked stays unallocated, i.e. still
  spendable and inside the daily figure.
* **Personalized only on the user's word.** A plan is labelled
  `personalized` only after the user answered the regular-payments question
  (saved or "none") and described their everyday spending; otherwise
  `preliminary`, with its unknowns listed. **Without new answers a preview
  is computed exactly as in 2.7.0** (same allocations, same digest): no
  existing account changes until its owner answers and saves.
* **Variable income** is planned on the stated monthly figure (what the user
  said), and the preview states, by exact arithmetic, what a month at the
  stated minimum would leave. MITA does not pick a lower basis by itself.
* **Eurostat only for EU, EFTA and candidate countries.** Eurostat's
  copyright notice forbids commercial reuse of its data for other countries
  ("USA, Japan, China"); the US gets OECD and World Bank data.
* **ChatGPT's own web search cannot be called by an MCP tool** (no such
  mechanism in the plugin reference); it stays opportunistic. A server-side
  price provider is evaluated in Milestone 3 and stays off without approval.

## 4. Data flow

```
user (typed or ChatGPT voice) ──▶ ChatGPT: understands, asks, confirms
        │                                   │ tool arguments only
        │            _meta openai/userLocation (country used as a hint)
        ▼                                   ▼
  MITA MCP tools ── validate ──▶ PostgreSQL (confirmed facts only)
        │   users (income, currency, tz, country)   mcp_user_profiles (+2.8 facts)
        │   mcp_setup_answers (2.8)  scheduled_expenses  spending_patterns  mcp_budget_lines
        │
        ├─▶ preview_monthly_budget: deterministic engine (unchanged) with
        │   exclusions = not_applicable ∪ (personalized ? unknown : ∅)
        │   → signed digest → save_monthly_budget only after "yes"
        │
        └─▶ (M2) regional_observations ◀── scheduled ingestion (shared, per
            country, not per user) ◀── Eurostat · World Bank · OECD
```

## 5. Database changes (additive, migration-controlled)

**0043 (Milestone 1)**
* `mcp_user_profiles` + `country_confirmed_at`, `country_source`
  (`stated` | `chatgpt_location_confirmed`), `regional_context_enabled`
  (default true), `income_regularity` (`regular` | `variable`),
  `pay_frequency`, `pay_days` (JSONB days of month), `minimum_monthly_income`
  — all nullable/defaulted, CHECK-constrained.
* new `mcp_setup_answers` (user, topic, answer, answered_at; cascades):
  topics `regular_payments`, `everyday_spending`, `irregular_expenses`,
  `income_schedule`, `region`; answers `none` | `described` | `skipped`.
* grants: `UPDATE (country, region) ON users`; full DML on
  `mcp_setup_answers`; added to `REQUIRED_TABLES`.

**0044 (Milestone 2)** — shared reference data, no user column:
`regional_ingestion_runs` and `regional_observations` (provider, dataset,
series key, indicator, COICOP code, geography, period, value with an explicit
`unit_kind` — index / percent / ratio / currency amount / PPP —, unit,
currency, base period, provider status flag, publication and retrieval
times, source URL, transformation, licence, quality flags; unique per
provider series and period, upserted idempotently). Local prices (M3) get
their own table when a provider is approved — never mixed with statistics.
The MCP role gets `SELECT` only; ingestion runs with its own role.

## 6. Official providers (verified live 2026-11-04)

| Provider | Endpoint | Verified series | Licence / limits |
|---|---|---|---|
| Eurostat | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}` (JSON-stat 2.0) | `prc_hicp_minr` — HICP, **ECOICOP ver.2** (`coicop18`), units `I25`, `RCH_A`, `RCH_M`; BG to 2026-10 (flash values flagged `e`). The old `prc_hicp_manr`/`prc_hicp_aind` stop at 2025 — not used. `prc_ppp_ind` — PLI (`PLI_EU27_2020`) by category (`A0101` food…), BG 2024 (`p`). `hbs_str_t211` — household budget structure, per mille, latest wave 2020. `prc_hpi_q` — house prices, BG 2026-Q2 | reuse authorised with source acknowledged; **not for commercial reuse for non-EU/EFTA/candidate countries**; no numeric rate limit, one extraction at a time, large queries answer 413 `ASYNCHRONOUS_RESPONSE` |
| World Bank | `https://api.worldbank.org/v2/country/{iso}/indicator/{id}?format=json` | `FP.CPI.TOTL.ZG` (inflation, annual %; BG 2025, US 2024), `PA.NUS.PRVT.PP` (PPP, household consumption, LCU per international $). **BG's LCU is now EUR** (0.41 for 2025; BGN-era values were ~0.8): the stored row must carry its currency, never an implicit "LCU". `NE.CON.PRVT.PC.KD` BG jumps 7,073 → 11,851 in one year — the kind of break plausibility checks must flag; not used | CC BY 4.0 (attribution, state changes); no stated rate limit; caching advised |
| OECD | SDMX `https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{key}` (CSV) | CPI annual growth `USA.M.N.CPI.PA._T.N.GY` 2026-09 (3.74); `CP01` food 2026-08 (flag `E`); US `CP04`/`CP07` last 2024-12 (stale); `BGR` all-items last 2025-12 | the brief's 60 downloads/hour; oecd.org returns 403 to automated reads, so **the licence text could not be read: owner to confirm** before production use |

Cadence: HICP monthly (Eurostat flash around month end, full ~mid-month),
OECD CPI monthly, PLI and World Bank annual. Ingestion runs per provider on
its own schedule, batched (one Eurostat request per dataset and country
set; OECD well under its hourly limit) — never per user or per tool call.

## 7. Tool contracts

* `get_setup_status` (read): + `onboarding` {stage, budget_readiness,
  topics[], next_questions[]}, + `region` {country, source, regional
  context on/off, suggestion from ChatGPT's approximate location}.
* `update_financial_profile` (write; already destructive/idempotent): +
  `country`, `income_regularity`, `pay_frequency`, `pay_days`,
  `minimum_monthly_income`, `regional_comparisons`, `setup_answers`.
* `preview_monthly_budget` (read): + `personalization`
  (`preliminary`/`personalized`, unknowns, skipped), `line_status` per
  line, `not_included` (unknown lines with what MITA would suggest),
  `variable_income` check, truthful region text.
* `save_spending_patterns`: description states that `flexible`/`planned`
  confirms the user has that spending.
* M2: one read tool for the user's country's statistics from MITA's own
  table (no live provider call, no location input).

No tool takes a user id, a city, an address or coordinates.

## 8. Privacy impact

New personal data: the confirmed country and its source, income regularity,
pay frequency and days, a minimum monthly income, setup answers. All are
stated by the user, low sensitivity except the income figures (financial,
like the existing income), cascade with the account, shown back in
`get_setup_status`, never in analytics (only field names), never in logs.
Not collected: city, address, coordinates, employer, bank details, health
details, dependants outside the household. Official statistics are shared
reference data: no user data leaves MITA to fetch them. The privacy policy
draft (`legal/policy-redline.md` §C) says MITA never sends "locations"; it
needs one sentence on the stored country and the use of ChatGPT's
approximate location as a suggestion — **owner/counsel**.

## 9. Plan and gates

| Milestone | What | Gate |
|---|---|---|
| M1 | 0043, onboarding state, country confirmation, setup answers, personalized vs preliminary preview, variable income check, skill, golden prompts, tests | — |
| M2 | 0044, Eurostat/World Bank/OECD adapters with real responses recorded as fixtures, idempotent ingestion with retries, backoff, rate limits, plausibility and staleness flags, one read tool | OECD licence (owner) |
| M3 | local price provider comparison; a proof of concept only with a free, licensed source behind a flag (off) | any paid provider (owner) |
| M4 | statistics and verified prices as labelled suggestions in previews (never amounts by themselves) | — |
| M5 | staging: backup, 0043/0044, grants, pin, checks | **database access**: the established path needs a temporary SSH key on the owner's Railway account (owner decision, as on 2026-11-04); no TCP proxy |
