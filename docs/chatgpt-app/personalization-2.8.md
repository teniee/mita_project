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

## 10. Milestone 1 — implemented (MCP 2.8.0, migration 0043)

**Stage** (`get_setup_status.onboarding.stage`, derived on every call from
stored facts — nothing to keep in sync, survives reconnecting):

| Stage | When |
|---|---|
| `not_started` | nothing stated, nothing recorded |
| `in_progress` | something stated, income / currency / timezone incomplete |
| `basic_profile_completed` | profile complete, regular payments never asked |
| `spending_partially_known` | payments answered; some patterns or own lines, not "that is everything" |
| `ready_for_preliminary_budget` | payments answered, everyday spending unknown |
| `optional_questions_skipped` | the user skipped payments or everyday spending |
| `ready_for_personalized_budget` | payments saved or "none", and everyday spending `described` |
| `established` | any saved plan: a returning user — `next_questions` empty, open topics only in `optional_questions` |

Topic states: `answered` (facts saved), `none`, `described`,
`partially_known`, `skipped`, `unknown` (never asked — not "none"). A saved
payment outranks an earlier "none"; "none" over saved payments is refused.

**Line states in a preview**: `line_status` `user_confirmed` (the user's own
line, or a planned/flexible pattern on a MITA line) / `mita_suggested`;
`not_applicable_lines` as in 2.7.0; `not_included` (unknown: only after
`everyday_spending = described`, with `would_suggest` and
`not_included_money` — conserved: total = Σ to_other_lines + unallocated).
`personalization.level` is `personalized` only with payments
answered/none AND spending described. Without the answer the engine call is
the 2.7.0 one (same allocations and digest: `test_an_existing_user_is_not_sent_back_through_setup`).

**Region**: `users.country` + `mcp_user_profiles.country_confirmed_at` /
`country_source`; an app `users.region` of another country is cleared (the
engine would keep that country's rules). The hint is bound per call by the
runtime (`app/mcp/location_hint.py`), country only; never in analytics or
logs. `setup_answers region skipped` resets the country to `ZZ`. The region
text in a preview now says when MITA has no rules of its own for a country
(BG uses the DEFAULT profile, exactly like `ZZ` — no figure changes).

**Variable income**: `variable_income` in the preview — planned on the
stated income; `committed` (bills + savings + own lines), `plan_total`
against the stated minimum. MITA picks no other basis.

**Not done, deliberately**: city / admin region (OpenAI guidelines; no
city-level source), "people supported" (no figure uses it), irregular
expenses as monthly payments (only a dated goal the user agrees to). Bills
stay `monthly`/`weekly` (`add_recurring_expense` has no one-time or annual
recurrence; an annual bill becomes a goal only if the user wants money set
aside).

**Tests**: `tests_mcp/test_personalized_onboarding.py` (two people → two
budgets with hand-checked figures; no fuel without a car, no rent with a
mortgage; suggestions vs choices and the conservation of left-out money;
none/skipped/unknown; validation; income schedule; the location hint as a
question, travelling, moving, skipping; truthful region text; an existing
user unchanged and never re-asked, a stale draft refused; a new connection
and another account). Readiness and grants: `test_readiness.py`. HTTP smoke
for staging: `scripts/mcp/smoke_onboarding_280.py`.

**Staging procedure for 0043** (as for 0041/0042): pre-migration
`pg_dump -Fc` on the Postgres volume, restore test; `alembic upgrade 0043`
over the private SSH path; re-run `scripts/mcp/mcp_service_role.sql` (adds
`UPDATE (country, region) ON users` and `mcp_setup_answers`); verify the
grants; pin the 2.8 commit; `/health` 200 `"version":"2.8.0"` (503 until
`mcp_setup_answers` is visible to `mita_mcp`); `smoke_onboarding_280.py`,
`smoke_behavioral_270.py`, `e2e_v2.py`, `e2e_http.py`, failure modes;
`staging_account_fingerprint.py` before and after (the owner's November must
be identical). Rollback: re-pin `2ab2e0f` — 2.7.0 ignores the new columns
and table.

## 11. Milestone 2 — implemented (migration 0044, `get_regional_context`)

**Data layer** (`app/regional/`, a batch job — never inside a tool call):
`catalog.py` (every dataset, code, unit and licence verified live on
2026-11-04), one adapter per provider (`providers/`), `observations.py`
(normalization and checks), `http.py` (timeouts, up to 4 attempts with
exponential backoff and jitter on 413/429/5xx and network errors,
`Retry-After` honoured, one request at a time with a minimum interval per
provider — OECD 75 s, far under its 60 downloads an hour), `ingest.py`
(`python -m app.regional.ingest [--provider …] [--dry-run]`; refuses
`ENVIRONMENT=production`).

| Indicator | Provider · dataset | Countries | Unit · classification | Cadence · stale after |
|---|---|---|---|---|
| `consumer_price_inflation` | Eurostat `prc_hicp_minr` (RCH_A) | EU27, EFTA, candidates | % over 12 months · COICOP 2018 | monthly · 100 days |
| `consumer_price_inflation` | OECD `DF_PRICES_ALL` (CPI, GY) | OECD members + BG, HR, RO | % over 12 months · COICOP 1999 | monthly · 100 days |
| `price_level_index` | Eurostat `prc_ppp_ind` (PLI_EU27_2020) | EU27, EFTA, candidates | EU27_2020 = 100 · COICOP 1999 | yearly · 900 days |
| `household_spending_share` | Eurostat `hbs_str_t211` | EU27, EFTA, candidates | per mille · COICOP 1999 | survey (2020) · 7 years |
| `consumer_price_inflation_annual` | World Bank `FP.CPI.TOTL.ZG` | every country | annual % · all items | yearly · 900 days |

Categories: all items, food, clothing, housing, transport, recreation,
restaurants (provider codes kept; mapped to these keys for asking). The
read side prefers, per indicator and category, a fresh figure over a stale
one, then Eurostat over the OECD (the harmonised EU measure).

**Quality**: a missing cell is never stored (no zeros); impossible values
are rejected (a fall of more than 100 %, a share above 1000 ‰, a yearly
period in a monthly dataset); provider flags kept (`estimated`,
`provisional`, `break_in_series`); a changed value is `revised`; a level
(price level, share) that moves more than 30 % is `break_suspected` (BGN →
EUR re-denomination divides by 1.95583); |inflation| > 100 % is kept and
flagged `extreme_value`; `stale` is computed at read time from each
dataset's cadence, so an outage ages values instead of deleting them.
Upserts are idempotent (keyed by provider, dataset, series, period); a
failed provider leaves every stored value untouched.

**Not ingested, deliberately**: PPP conversion factors (their "local
currency unit" changes meaning when a country changes currency — the World
Bank's BG series is now in EUR); the World Bank ICP 2021 (reference year
2021, a multi-dimensional API) — evaluated, deferred; city-level prices (no
official source measures them).

**Verified locally on real data** (fresh database at 0044, roles from the
scripts): the job as `mita_regional_ingest` (`regional_ingest_role.sql`:
SELECT/INSERT/UPDATE on the two tables, the identity sequence; no user
table) — 5 requests, 5,673 observations inserted (HICP 3,276, PLI 648, HBS
372, World Bank 573, OECD 804), 0 rejected; the second run: all 5,673
unchanged. The MCP server as `mita_mcp` (SELECT only): `/health` 2.8.0
(`regional_observations` in `REQUIRED_TABLES`);
`smoke_onboarding_280.py --expect-statistics` 75/75 — Bulgaria from
Eurostat (HICP 6.0 % in 2026-10, flash `estimated`; food price level 88.8
vs 56.9 overall, 2024), the US from the OECD (CPI 3.7 %, 2026-09; its
category series end in 2024-12 and come back `stale`) and the World Bank,
never Eurostat; no country → nothing.

**Tests**: `tests_mcp/test_regional_data.py` (parsers on recorded real
responses, aggregates dropped, licence-restricted countries never queried,
values checked never invented, retries/backoff/no retry on 4xx, idempotent
upsert, revisions, re-denomination break, a failed provider keeps the last
values, no user column, amount-without-currency refused);
`tests_mcp/test_regional_context.py` (BG and US through the tool, filters,
no country / turned off / unavailable, statistics never change a preview).

**Staging procedure for 0044** (with 0043, one owner-authorised session):
backup → `alembic upgrade 0044` → `mcp_service_role.sql` (adds `SELECT ON
regional_observations`) → `regional_ingest_role.sql` (new role; password
generated into a 0600 file, never printed) → first ingestion run from the
operator machine over the same private path, as `mita_regional_ingest` →
pin the 2.8 commit → `smoke_onboarding_280.py --expect-statistics`.
**Schedule**: weekly is enough (Monday 06:00 UTC: HICP and OECD CPI are
monthly, the rest yearly; every run is idempotent and costs 5 requests).
On Railway that is a separate cron service in `mita-mcp-staging` from the
same image with start command `python -m app.regional.ingest`, cron
`0 6 * * 1`, restart policy never, no public domain and the ingest role's
`DATABASE_URL` — **a new service is an infrastructure change: owner
decision.** Until then the job runs from the operator machine.
