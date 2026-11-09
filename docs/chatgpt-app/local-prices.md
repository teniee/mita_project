# Local prices — architecture, controls and what activation needs (2026-11-09)

Owner brief "complete regional budget intelligence", task 4. **No paid
provider is active.** Every lookup answers `no_verified_price`. Nothing below
is proof that a live lookup works: the tests use synthetic provider answers
to show what is rejected and what would be shown. The provider evaluation of
2.8 is in `personalization-2.8.md` §13. The current OpenAI facts below were
re-read from developers.openai.com on 2026-11-09.

## 1. What exists (implemented, not integrated)

`app/prices/` is a self-contained package. No MCP tool imports it, and it
imports no database, ledger or plan code (both are tested).

| Module | Role |
|---|---|
| `model.py` | `PriceQuery` (product, quantity, unit, the user's currency), `SearchArea`, `PriceCandidate` (untrusted), `VerifiedPrice`, `LookupResult` |
| `area.py` | the search area for one call (see §2) |
| `validation.py` | every check a candidate must pass (see §3) |
| `units.py` | g/kg/ml/cl/l/piece → kg, l or piece. MITA computes the unit price itself |
| `approval.py` | the owner's approval as configuration. Anything partial = no approval |
| `providers.py` | `DisabledProvider` (the only one buildable today) and `OpenAIWebSearchProvider` (request builder and parser, inert without approval) |
| `lookup.py` | approval → area → quota → provider → verification, failing closed at each step; `DenyAll` quota until a durable store exists |

## 2. Location

* **No new input.** No tool takes a city, address or coordinates (OpenAI
  plugin guidelines; `test_tool_contract` LOCATION_FIELD).
* **Temporary search area.** A city comes only from ChatGPT's approximate
  `_meta["openai/userLocation"]`, and only for that one lookup. It is
  labelled `chatgpt_current_location_approximate`, never stored and never
  logged.
* **Never assumed to be the residence.** The confirmed country is the
  residence for budgets. A hint in another country gives
  `country_is_residence: false`, and the answer must say "near where you are
  now".
* **Only a plain place name.** A city with digits, a street, a postcode, more
  than four words or instruction-like words is dropped, and the lookup falls
  back to the confirmed country. Latitude and longitude are never read.

## 3. Controls on every candidate (`validation.verify`)

In order; the first failure rejects the candidate.

1. **Product name.** Plain characters, at most 120, and nothing that reads
   like an instruction, a role or a link. It must contain every word (3+
   letters) of the product asked for.
2. **Price.** Positive, finite, at most 3 decimals, at most 100,000.
3. **Currency.** Exactly the user's currency; otherwise rejected, never
   converted.
4. **Quantity.** A known unit of the same kind as the one asked for. MITA
   computes the unit price.
5. **Merchant.** The same text rules as the product name.
6. **Source.** An https URL with no credentials or odd port, on an approved
   domain (subdomains allowed), **and cited by the search** (`url_citation`
   or `sources`). A URL the model made up is refused.
7. **Date.** Observed at most 31 days ago, never in the future.
8. **Labels.** Coverage is store, city or online_national. Price type is
   regular or promotion, and an ended promotion is refused. Delivery and
   deposit are stated apart and never folded into the price.

A result is data, never an instruction. It is never a transaction, a budget
line or a plan input. To use a price, the user sets their own amount
(`budget_lines`) and confirms a new preview, the same as with every other
suggestion.

## 4. Statistics and retail prices stay apart

`regional_observations` holds official statistics only. Retail prices, once
approved, go to a separate table proposed here and **not created**:
`retail_price_observations`, with the `VerifiedPrice` fields, the search area
(country, approximate city, its source), the provider, the request time and
`expires_at` = observed_on + the approved retention. It has no user column.
The quota store would be `price_search_usage (day, user_key, lookups,
estimated_cost)`, where user_key is an HMAC of the user id under its own
secret. Both need a migration, grants for `mita_mcp` and an update to the
data inventory and privacy policy.

## 5. The MCP capability, once approved

One read-only tool: `find_local_price(product, quantity?, unit?)`.

* **Annotations.** `readOnlyHint` true; `openWorldHint` **true**, because it
  reaches the web — a change OpenAI reviews.
* **Area.** From §2 only.
* **Output.** Verified prices, each with merchant, date, regular or promotion,
  extra costs and the cited link, which must be shown as a clickable link
  (OpenAI web search display rule). Or `no_verified_price` with its reason.
* **No hidden calls.** It is never called by the preview or any other tool.

ChatGPT can also search the web by itself. MCP cannot force or suppress
that, and MITA does not try. The skill already says such a result is not
MITA's and becomes an amount only when the user sets it.

## 6. Providers and costs (for the owner's approval)

| Option | What it is | Cost (as published) | Notes |
|---|---|---|---|
| **OpenAI Responses `web_search`** (recommended) | live web search with `user_location` `{type: "approximate", country, city, region, timezone}`, `filters.allowed_domains` (≤ 100, subdomains included), `include: ["web_search_call.action.sources"]`, `url_citation` annotations, `tool_choice: "required"` | **$10 / 1,000 calls + search content tokens at the model's rates** (for gpt-4o-mini and gpt-4.1-mini: a fixed 8,000 input tokens per call) | `store: false`; the Responses API keeps application state 30 days unless `store` is false; ZDR needs OpenAI's approval; whether structured outputs combine with `web_search` is **not stated**, so the parser takes one strict JSON object or nothing |
| Brave Search API | web search | $5 / 1,000 (Search) | result storage needs a storage-rights plan |
| Perplexity search | web search with user location | $2.50 / 1,000 | from the 2.8 evaluation; terms not re-read |
| Tavily | web search | $0.008 / credit | country boost only, no city |
| SerpApi | search-engine results | $25–$150+ / month | Legal Shield from $150 |
| Numbeo | crowd-sourced city costs | $260–$1,250 / month | no republication via APIs or public feeds |
| EU Weekly Oil Bulletin | official national fuel prices | free | XLSX download: a new dependency (owner decision) |
| Open Prices (Open Food Facts) | crowd-sourced shelf prices with proof photos | free (ODbL) | 284 BG prices on 2026-11-04; share-alike licence question |
| Eurostat household energy | official national €/kWh | free | **in use** since 2.8 |

**Cost of one lookup** with OpenAI: N search calls × $0.01, plus the search
content tokens × the model's input rate. A 1-search lookup on a mini model is
$0.01 + 8,000 × that model's input rate. A monthly cap C allows about C ÷
(cost per lookup) lookups. `InMemoryQuota` shows the arithmetic, and the
durable quota of §4 enforces it before any call.

## 7. What activation needs (owner)

1. **Approvals** — every item, as configuration
   (`MITA_PRICE_SEARCH_*`, `approval.py`):
   * the provider and model;
   * API access: the NAME of the key's environment variable, never the
     key;
   * a monthly spend cap;
   * a per-user daily quota;
   * the allowed domains (≤ 100);
   * how long a verified price is kept;
   * the privacy and data-handling text and its version.
2. **The two tables of §4**: migration, grants, data inventory, privacy
   policy update.
3. **A verification run** on staging with a capped key:
   * structured output with `web_search` — or a looser parser, reviewed
     again;
   * citations present;
   * `allowed_domains` effective;
   * the real cost per lookup measured.
4. **The tool of §5**, its golden prompts, and OpenAI's re-review
   (`openWorldHint`).

Until then MITA says it has no verified local price.
