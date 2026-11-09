# Regional recommendations — rules (MCP 2.9.0)

Owner brief "Fix Backend CI and complete regional budget intelligence"
(2026-11-09), task 3. What 2.8.0 did and did not do is in
`regional-capability-audit.md`. This document covers what 2.9.0 adds, how,
and what it still cannot do.

**MITA does not produce locally accurate personal budgets.** 2.9.0 adds
national, low-confidence **references** beside budget lines: what households
in the user's country spend on average on a kind of spending. Each one is
built by a stated method from an absolute amount of money, never from an
index alone. They are suggestions with their evidence. They never change a
plan, a user's amount, a saved budget or the digest of a draft.

## 1. Evidence order (first wins)

For each line of `preview_monthly_budget`, `recommendation.basis` is the
first of these that gives the line an amount:

| # | Evidence | Where it comes from | `confirmed_by_user` |
|---|---|---|---|
| 1 | `obligation` | saved bills and loans (`fixed_obligations`): the user's contracts, planned as they are, never compared with statistics | — |
| 2 | `user_amount` | a line the user set (`set_by_you`, F-11) | true |
| 3 | `history` | the user's recorded average on the line over complete months (`recorded_average`) | false (a record, not a choice) |
| 4 | `planned_pattern` | a pattern the user stated × their usual amount (e.g. €50 × the month's Saturdays) | true |
| 5 | `verified_local_price` | **none exists**: MITA has no verified prices (`recommendations.verified_local_prices: "none"`, `local-prices.md`) | — |
| 6 | `regional_statistics` | the national reference below, when available | false |
| 7 | `mita_default` | MITA's own share of the income — not a local cost estimate | false |

The regional reference is shown on the line whatever wins, so ChatGPT can
put the user's own amount next to the national average. `differs_from_plan`
says whether the suggestion differs from the line's planned amount. Adopting
one is always explicit: the user's amount goes into `budget_lines`, a new
preview is shown, and the plan is saved only on the user's yes. No code path
writes a recommendation.

Lines MITA left out are never brought back by a reference: `not_applicable`
lines and, in a personalized plan, `not_included` lines carry none. A user
without a car has no fuel line, so no fuel reference appears on any line.

## 2. The reference (`app/regional/reference.py`, pure)

For category `c` in country `g`, survey year `Y` and latest price year `P`:

    yearly    = hbs_exp_t111  (mean consumption expenditure per adult
                               equivalent, year Y, in the user's currency)
    share     = hbs_str_t211  (per mille of it spent on c, year Y)
    factor    = prc_hicp_aind (annual average index of c, P ÷ Y)
    one adult = yearly × share / 1000 × factor ÷ 12
    fuel only:  ÷ (hbs_exp_t123b: % of households that bought fuel / 100)

* **Household.** One adult, or a household as a range on the survey's own
  modified OECD scale. The weights are 1 for the first adult, 0.5 for each
  other person aged 14+, 0.3 for each child under 14 (Eurostat, "Household
  budget survey – statistics on consumption expenditure", footnotes). MITA
  stores only a household size, not ages. So the low end counts the others
  as children and the high end as adults: 2 people = 1.3–1.5, 4 people =
  1.9–2.5, never ×n. Unknown size: one adult, and the summary says so.
* **Categories.** food at home `CP01` (line `groceries`), clothing `CP03`
  (`clothing`), home energy `CP045` (context only: energy is billed, so it is
  an obligation), fuel `CP0722` (`transport gas`, for households that buy it:
  50 % of Bulgarian households in 2020).
* **Lines with no reference, and why** (`regional_reason`):
  * dining out: `participation_varies` — no precondition separates those who
    never eat out from those who do;
  * public transport: `category_mismatch` — it sits inside "transport
    services" together with flights and taxis;
  * entertainment and hobbies: `category_mismatch` — recreation is broader;
  * medical: `personal_circumstances`;
  * anything unmapped: `no_statistic_for_line`.
* **Currency.** Only the user's currency, and only when it is the country's
  currency now. A euro budget uses Eurostat's euro figure for the euro area,
  including Croatia (2023) and Bulgaria (2026). A RON budget in Romania uses
  the lei figure. A euro budget in Romania, a leva budget in Bulgaria in
  2026, or a dollar budget anywhere → `currency_mismatch`. **Nothing is ever
  converted.**
* **Refused, never filled in** (`insufficient_data` + `reason`):
  * `no_country`, `turned_off`, `no_currency`;
  * `not_covered` — no licensed survey: the US, GB, JP and every
    non-Eurostat country;
  * `no_survey`, `survey_too_old` — a wave older than 8 years (Sweden and
    North Macedonia have 2015 only);
  * `share_missing` — Portugal and Romania publish no 2020 energy or fuel
    share;
  * `low_reliability` — the provider's flag on any input;
  * `price_index_missing`, `prices_too_old` — the 2025 index from mid-2027;
  * `prices_changed_too_much` — a factor outside 0.5–2.0, which breaks the
    same-quantities assumption: Turkey's food ×8.0, Estonia's energy ×2.33;
  * `buyers_missing`, `too_few_buyers` — fewer than 20 %.
* **Confidence** is always `low`. Provider flags pass through
  (`estimated`: France, Cyprus and Malta's "2020" was collected in 2015–17;
  `definition_differs`: candidate countries' indices).
* Whole currency units; the exact inputs are in `inputs` so the figure can be
  checked by hand.

Verified figures (real Eurostat data, recorded 2026-11-09): for **Bulgaria**
(EUR, one adult, a month at 2025 prices), groceries **152** (4,775 × 246‰ ×
1.554705 ÷ 12 = 152.19), clothing **13**, home energy **52**, fuel **42**
for households that buy it. For a household of 2, groceries are 198–228; for
4, 289–380. Germany: groceries 302, fuel 117. Romania (RON): groceries 817.
For comparison, MITA's own default groceries line for €1,000 in Bulgaria is
**78.00**.

## 3. Data (no migration)

Four Eurostat datasets join the existing `regional_observations` (0044
schema: the `ratio` unit kind and the currency column already exist).
`hbs_exp_t111` (EUR_AE, NAC_AE: the currency per cell comes from the unit
and the country's currency that year; an unknown country-year is rejected)
and `prc_hicp_aind` (`INX_A_AVG`, 2015 = 100, COICOP 1999; it ends with
2025) are new. `hbs_exp_t123b` (% of households with expenditure, fuel) is
new. `hbs_str_t211` gains `CP045` and `CP0722`. These rows are **inputs**:
`get_regional_context` never lists them as statistics
(`catalog.SHOWN_INDICATORS`). Eurostat only for EU, EFTA and candidate
countries (licence).

## 4. Contracts

* `preview_monthly_budget`: every line gets `recommendation`
  (`LineRecommendationOut`), and the result gets `recommendations`
  (`RecommendationSummaryOut`: precedence, country, currency, household,
  regional status, `verified_local_prices: "none"`, method, and the rule that
  nothing changes). Both are read after the draft (read-only transaction),
  so neither enters the digest. `save_monthly_budget` is unchanged. A new
  assumption, `INCOME_BANDS_NOTE`, appears unless the user is in the US with
  USD: MITA's income bands are fixed numbers, not purchasing-power aware
  (audit §8).
* `get_regional_context`: `spending_references` for topic
  `household_spending` (or no topic). The new categories `household_energy`
  and `fuel` can be used as filters.
* No new tool (26), no new input field, no location field.

## 5. Tests (fictional people, real recorded statistics)

`tests_mcp/test_regional_reference.py` (the engine, by hand),
`tests_mcp/test_regional_recommendations.py` (scenarios A–E through the
tools), `tests_mcp/test_local_prices.py` (scenario F and the price controls):

* **A** — €1,000 in Bulgaria → groceries 78.00 planned, 152.00 referenced,
  and the income-bands note. $1,000 / $1,080 in the US (€1,000 at a rate the
  test assumes; MITA uses none) → 90.00 / 97.20, `not_covered`, no euro
  anywhere.
* **B** — Varna and Sofia hints give byte-identical recommendations and
  references, and neither name appears in any result.
* **C** — no car → no fuel line and no fuel reference; public transport 26.00
  and a taxi line 30.00 are the user's own.
* **D** — Fuel €200 stays 200.00 with the 42.00 reference beside it. Turning
  statistics off gives the same amounts, total and unallocated money, and the
  saved plan equals the preview.
* **E** — a history of 300/310/320 gives a recommendation of 310.00 next to
  the 152.00 reference. The plan stays 117.00, and the user's own 250
  outranks both.
* **F** — no approval → `no_verified_price`. Injection text, a wrong
  currency, an uncited URL and a stale date are each rejected. The preview
  says MITA has no verified price.

## 6. Capability matrix after 2.9.0

| Capability | Status |
|---|---|
| National household-spending references (food, clothing, energy, fuel) in the user's currency, with a household range | IMPLEMENTED AND VERIFIED locally; **not on staging yet** — the release waits for the owner's authorisation of a temporary SSH key (`staging.md` → "MCP 2.9.0") |
| Evidence order per preview line, never applied | IMPLEMENTED AND VERIFIED locally |
| Honest statement that MITA's income bands are not purchasing-power aware | IMPLEMENTED AND VERIFIED locally |
| Currency- or PPP-aware income tiers / allocation shares | NOT IMPLEMENTED — an app-wide money-model decision for the owner |
| Household size in MITA's own allocation | NOT IMPLEMENTED (references only; the assumption says so) |
| City-level figures | NOT IMPLEMENTED (no city source; no city stored) |
| Eating out, public transport, recreation, health references | BLOCKED BY DATA (no defensible national figure; reasons above) |
| Verified local retail prices | BLOCKED BY APPROVAL — the architecture and controls are IMPLEMENTED BUT NOT INTEGRATED (`local-prices.md`) |
| US references (BLS Consumer Expenditure Survey) | BLOCKED BY DATA/APPROVAL: series meaning unverified without a free BLS API key (the owner registers) |
| OECD CPI | BLOCKED BY APPROVAL (licence) |
| Weekly refresh | BLOCKED BY APPROVAL (cron, ≈ $0.001 a month) |
