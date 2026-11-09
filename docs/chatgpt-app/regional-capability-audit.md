# Regional capability audit — what MITA's geography really does (2026-11-09)

Owner brief "Fix Backend CI and complete regional budget intelligence",
task 2. The audit covers MCP 2.8.0 as it runs on staging (`601a3d7`,
deployment `618cd6d9`). Every statement below was checked against the code,
against the data MITA holds and against the engine itself. The engine was run
on fictional incomes; no real account was read. "Staging data" means the
5,209 observations ingested on 2026-11-04. The local database `mita_lp_280`
holds the same rows, since the same job ran against the same sources, plus
the OECD rows that were excluded from staging.

**Bottom line.** Geography changes MITA's **calculated amounts** only for the
United States and, partly, for Great Britain. For every other country,
geography is **context beside the plan**: official statistics shown next to
lines, never used to calculate them. MITA does not produce locally accurate
personal budgets. Having inflation, price-level and household-spending
indices does not change that.

## 1. Which countries are covered

| Data on staging | Countries | Periods |
|---|---|---|
| World Bank inflation, all items (`FP.CPI.TOTL.ZG`) | 192 | 2011 – 2025 (yearly) |
| Eurostat HICP, 12-month rate (`prc_hicp_minr`, COICOP 2018) | 36 | 2025-09 – 2026-10 (monthly) |
| Eurostat price level indices (`prc_ppp_ind`) | 36 | 2022 – 2024 |
| Eurostat household budget survey shares (`hbs_str_t211`) | 32 | 2015 and 2020 |
| Eurostat household electricity price (`nrg_pc_204`) | 38 | 2024-S1 – 2026-S1 |
| Eurostat household gas price (`nrg_pc_202`) | 30 | 2024-S1 – 2026-S1 |
| OECD CPI | **0** (excluded: licence unverifiable) | — |

That is 193 countries in all: Eurostat covers only EU, EFTA and EU-candidate
countries (its reuse licence), and the World Bank covers everything else.
Examples: **Bulgaria** has all six datasets. **The United States, Great
Britain and Japan** have World Bank yearly inflation only (US 2024: 2.9 %;
GB, JP 2025).

## 2. Which indicators exist for a country

Read through `get_regional_context` (topics inflation, price_levels,
household_spending, prices). For an EU country: the monthly HICP rate overall
and for food, clothing, housing, transport, recreation and restaurants; price
levels against the EU average for six aggregates; household spending shares
for six COICOP divisions; the household electricity and gas price per kWh;
and World Bank yearly inflation. For any other country: World Bank yearly
inflation only.

## 3. Which values are amounts of money

Only the **household energy prices**: EUR per kWh, taxes included, for a
typical consumption band, and national averages. They are unit prices, not
amounts for a budget line, and they are requested in EUR only (any other
currency is rejected, never converted).

## 4. Which values are indices or percentages

Everything else:

* HICP and World Bank figures are percentage changes over 12 months or a
  calendar year.
* Price levels are an index (EU27_2020 = 100).
* Household budget survey figures are per-mille shares of spending.

None of these can be turned into an amount of money without an absolute
baseline. Before this work MITA had none and turned none of them into one:
no amount anywhere was derived from a statistic (`personalization-2.8.md`,
M4).

## 5. Does the country change a calculated amount?

**Only for US (and US-CA/FL/NY/TX) and GB.**
`budget_draft.build_draft` passes `users.region or users.country` to
`allocations_from_profile` → `generate_budget_from_answers`. That function
loads `app/config/country_profiles/<code>.yaml`, and only seven profiles
exist: DEFAULT, GB, US, US-CA, US-FL, US-NY, US-TX. Every other country (BG,
DE, RO, JP…) gets DEFAULT. Measured with the engine on 2026-11-09 (monthly
income, no bills, no savings):

| Region, income | Tier | Groceries | Dining out | Clothing | Transport public / gas |
|---|---|---|---|---|---|
| BG, 1,000 | lower_middle | 78.00 | 52.00 | 48.00 | 105.00 / 45.00 |
| DE, 1,000 | lower_middle | 78.00 | 52.00 | 48.00 | 105.00 / 45.00 |
| US, 1,000 | low | 90.00 | 60.00 | 18.00 | 105.00 / 45.00 |
| GB, 2,000 | lower_middle (GB weights) | 204.00 | 136.00 | 120.00 | 210.00 / 90.00 |
| JP, 300,000 | **high** | 14,400.00 | 9,600.00 | 9,000.00 | 21,000.00 / 9,000.00 |

Bulgaria and Germany get identical plans. The GB profile changes the weights
for the lower_middle tier only. `GB.yaml` also declares `currency: USD`;
nothing reads that field, but it is wrong.

## 6. Does the city change anything?

**No.** MITA never asks for, stores or receives a city as an input. The
OpenAI plugin guidelines rule out raw location fields, and ChatGPT's
`openai/userLocation` hint is reduced to its country and only suggested.
Every statistic is national (`geographic_scope: "country"`). Varna and Sofia
are indistinguishable to MITA, and nothing claims otherwise.

## 7. Does household size change anything?

**No.** `mcp_user_profiles.household_size` (1–20) is stored and shown in
setup, but no calculation reads it: neither the engine, nor the budget
draft, nor the regional queries. A household of four gets the same groceries
line as a single person on the same income.

## 8. Do income thresholds respect currency or purchasing power?

**No.** `income_classification_service.classify_income` compares `12 ×
monthly income` with fixed numbers, whatever the currency:

* The US profile sets 36,000 / 57,600 / 86,400 / 144,000, described as USD.
* DEFAULT has no thresholds at all, so the loader's stub applies (low 2,000,
  middle 5,000, high 10,000), mixed with the code defaults. The result for
  DEFAULT is "low" up to 166.67 a month, then lower_middle up to 4,800,
  upper_middle up to 12,000, and high above that. **MIDDLE can never be
  reached.**
* The currency is never consulted. ¥300,000 a month is read as the number
  300,000, as if it were $300,000, so it is classified **high** and groceries
  get 4.8 % of income. €1,000 in Bulgaria and €1,000
  in Germany are the same tier.

This is not a purchasing-power-aware model for any country outside the US,
and the preview must not imply one. Changing the tiers would change every
user's plan in ChatGPT and in the app. That is an app-wide money-model
decision for the owner (memory "ChatGPT mirrors the app"), so it is reported
here, not changed.

## 9. Does MITA have real local prices?

**No.** It has no shop, product, fare, fuel or service prices, at city or
national level. The only prices it holds are the national average household
electricity and gas prices per kWh. Paid web search, the EU Oil Bulletin
(XLSX) and Open Prices (ODbL, crowd-sourced) are owner decisions
(`personalization-2.8.md` §13–14).

## 10. Old or missing statistics

* **Old:** a figure older than its cadence allows is returned with
  `stale: true`. Staleness is computed at read time from `max_age_days`:
  100 days for monthly HICP, 900 for price levels and World Bank figures,
  7 years for the survey, 400 for energy. Fresh figures are preferred over
  stale ones.
* **Missing:** a missing cell is never stored. The 0044 schema refuses an
  amount without its currency, and a country with nothing is `unavailable`.
  The preview then shows no comparison.
* **Effect on the budget:** none. Statistics are read after the draft, so
  they cannot enter its digest. A provider outage cannot slow or fail a
  tool, because the tools read MITA's own copy.
* **No refresh yet:** values are refreshed by hand until a weekly job is
  approved (≈ $0.001 a month, `staging.md`).

## Capability matrix (2.8.0 on staging, before this work)

| Capability | Status |
|---|---|
| Confirmed country (stated, ChatGPT hint only as a question) | IMPLEMENTED AND VERIFIED (smoke 77/77 on staging; real-ChatGPT acceptance pending) |
| National inflation, price levels, spending shares, energy prices (`get_regional_context`) | IMPLEMENTED AND VERIFIED |
| Inflation beside preview lines (`regional_comparison`) and own history (`recorded_average`) | IMPLEMENTED AND VERIFIED (context only) |
| Stale / missing handling | IMPLEMENTED AND VERIFIED |
| Household spending shares as amounts | NOT IMPLEMENTED (shares only, no baseline) |
| Country-specific allocation rules | IMPLEMENTED for US (+4 states) and GB lower_middle only; every other country uses DEFAULT |
| Currency- or purchasing-power-aware income tiers | NOT IMPLEMENTED (USD numbers applied to any currency) |
| Household size in any calculation | NOT IMPLEMENTED (stored only) |
| City-level anything | NOT IMPLEMENTED (by design: no city is stored) |
| OECD CPI (non-Eurostat countries) | IMPLEMENTED BUT NOT INTEGRATED — BLOCKED BY APPROVAL (licence) |
| Verified local retail prices | BLOCKED BY APPROVAL (paid search) AND DATA (no free authorised source) |
| Fuel prices (EU Oil Bulletin) | BLOCKED BY APPROVAL (XLSX dependency) |
| US household-spending baseline (BLS CE) | BLOCKED BY DATA (series meaning unverified without a free BLS key, which the owner registers) |
| Weekly refresh of statistics | BLOCKED BY APPROVAL (cron service) |

What this release adds, and the matrix after it, are in
`regional-recommendations.md`.
