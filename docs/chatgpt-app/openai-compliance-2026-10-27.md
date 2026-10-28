# OpenAI publication compliance — MITA in ChatGPT (2026-10-27)

Branch `feat/chatgpt-auth-ui` at `1ffa2b6` plus the uncommitted fixes listed
in "Changes in this pass". Supersedes `openai-requirements.md` (2026-10-02)
and the requirement notes in `production-readiness.md` /
`review/submission-checklist.md` where they differ.

**Method.** Every requirement below was re-read from OpenAI's current
documentation on 2026-10-27 (18:31 UTC, Markdown exports of each page), then
checked against the code, the plugin package, the live staging endpoint
(read-only HTTP) and Railway's service configuration (read-only). Old notes
were not treated as requirements.

**Verdict: not submittable yet.** Every requirement MITA can meet in code is
now met (six fixed in this pass). What is left is owner work — publisher
verification, domain, HTTPS website and legal pages, age decision, production
MCP service, review account, video — and the real-ChatGPT acceptance, which
needs the final code on staging first.

## Sources (official, fetched 2026-10-27)

| Id | Page |
|---|---|
| S1 | Upload and submit your plugin — https://developers.openai.com/plugins/deploy/submission |
| S2 | Remote MCP server review requirements — https://developers.openai.com/plugins/deploy/app-review |
| S3 | Plugin guidelines — https://developers.openai.com/plugins/plugin-guidelines |
| S4 | Plugin submission errors — https://developers.openai.com/plugins/deploy/submission-errors |
| S5 | Reference (`_meta`, annotations, UI resource fields) — https://developers.openai.com/plugins/reference |
| S6 | Add UI to your MCP server (CSP) — https://developers.openai.com/plugins/build/chatgpt-ui |
| S7 | Authentication — https://developers.openai.com/plugins/build/auth |
| S8 | Package your plugin (`mcp.json` auth) — https://developers.openai.com/plugins/build/plugins |
| S9 | Security & Privacy — https://developers.openai.com/plugins/guides/security-privacy |
| S10 | UI guidelines — https://developers.openai.com/plugins/concepts/ui-guidelines |
| S11 | Connect and test your plugin — https://developers.openai.com/plugins/deploy/connect-chatgpt |
| S12 | Build an MCP server — https://developers.openai.com/plugins/build/mcp-server |
| S13 | MCP Apps specification (2026-01-26), `ui.domain`, CSP — https://github.com/modelcontextprotocol/ext-apps |
| S14 | Agent Plugins schemas 1.0.0 — https://agent-plugins.org/schemas/1.0.0/plugin.schema.json, …/mcp.schema.json (identical to `plugin/schemas/`) |
| S15 | OpenAI Usage Policies — https://openai.com/policies/usage-policies/ — **owner-verified on the official page, 2026-10-28** (this environment gets HTTP 403 and does not bypass it; no third-party summary is used): update dated 2026-10-21, effective **2026-11-20**; until then the previous policy remains in effect |

`developers.openai.com/apps-sdk/*` now serves the same index as `/plugins/*`.

Status: **PASS** · **FIXED** (was NEEDS CHANGE, fixed in this pass) ·
**OWNER ACTION** · **NEEDS REAL CHATGPT TEST** · **NEEDS DEPLOY** · **N/A**.

## A. Publisher and account

| # | Requirement (source) | Meaning for MITA | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|---|
| A1 | Verified individual or business identity for the published name; enforced in review; the directory's developer name comes from it (S1, S2, S3, S4 `developer_name_defaulted`) | Publish as YAKOVLEV LTD (business verification) or as an individual | Unknown; nothing in the repo can show it | OWNER ACTION | platform.openai.com → Settings → Organization → General → Verification | P0 |
| A2 | Organization owner or `api.apps.write` ("Apps Management Write") to create and submit drafts (S1, S2) | The submitting user needs the role | — | OWNER ACTION | Grant the role if the submitter is not the org owner | P1 |
| A3 | "Projects with EU data residency cannot submit plugins with MCP servers" — use a global-residency project (S2) | YAKOVLEV LTD is in the EU: check the project's residency before uploading | Unknown | OWNER ACTION | Create/choose a project with global data residency | P0 |
| A4 | Policy attestations when submitting (S1, S4) | Done in the portal | — | OWNER ACTION | At submission | P1 |
| A5a | **In force until 2026-11-19:** the previous Usage Policies, which remain in effect until the update applies (S15, owner-verified) | MITA must not offer licensed advice or automate high-stakes financial actions under either version | No current tool, description, result note, skill, starter prompt, listing text, connect-page line or calendar label offers investment, credit, insurance, tax, legal or other licensed advice, and nothing automated decides or acts on credit, insurance or money (A5 below) | PASS | Re-check if MITA's scope changes | — |
| A5b | **From 2026-11-20** (update dated 2026-10-21, S15, owner-verified): no AI tools giving tailored advice that requires a professional licence without a licensed professional; no automation of high-stakes actions in sensitive areas — including financial activities, credit and insurance — without human review; stronger protections for children and teens; the changelog also covers model-training restrictions, national-security rules and approval for model-access intermediaries | The review will most likely run under this version | Same evidence as A5a; the training, national-security and intermediary rules do not concern MITA (it gives no model access and trains no model) | PASS | Re-check if MITA's scope changes; teen suitability is G8 | — |
| A6 | Coordinate press/announcements with press@openai.com (S2) | Before any launch announcement | — | OWNER ACTION | — | P2 |

### A5. OpenAI Usage Policies — check for MITA's current scope (PASS)

Evidence: the owner read the official page on 2026-10-28 (S15). This
environment cannot fetch it (HTTP 403, not bypassed); no third-party summary
is used. Earlier drafts of this file quoted third-party summaries; they were
removed on 2026-10-28.

| Boundary (A5b; the same limits apply under A5a) | What MITA does — checked in the code and every text a user or ChatGPT sees on 2026-10-28 | Result |
|---|---|---|
| Tailored advice that requires a professional licence (investment, credit, insurance, tax, legal) without a licensed professional | Budgeting arithmetic from the user's own records: plan vs. spent, a month-end projection at the current pace, a safe daily amount, a goal's "plain arithmetic of the monthly amount needed" (`create_savings_goal`, which also states "MITA gives no advice"); `get_financial_climate` "states numbers, not judgments"; a budget preview is "MITA's deterministic allocation rules" applied to what the user stated, reviewed by the user before it is saved. Rent, mortgage, loans and insurance appear only as bills or budget lines the user records; "Investments", "Retirement" and "Debt payoff" only as names of the user's own budget lines or goals. No tool, description, result note, skill, starter prompt, listing line, connect-page line or calendar label recommends a financial product, investment, credit, insurance or tax position. The connect page's "Can I afford dinner out tonight?" is answered "against what's left in your plan" | PASS — no change needed |
| Automation of high-stakes actions in financial activities, credit or insurance without human review | MITA moves no money, pays nothing, trades nothing, holds no money, has no bank connection and decides nothing about credit, insurance or eligibility. Every write is a request the user makes in the conversation; destructive tools (`update_financial_profile`, `update_transaction`, `delete_transaction`, `save_monthly_budget`, `submit_feedback`, `set_usage_analytics`) make ChatGPT ask for approval; a budget is saved only from a preview the user reviewed. MITA's automatic redistribution moves planned amounts between the user's own budget lines after an expense the user recorded — bookkeeping inside the user's budget, shown and labelled, not an action on money or credit | PASS |
| Protections for children and teens | Budgeting content only; nothing targets minors. The age question (13–17 suitability vs. ToS 18+) stays G8 | see G8 |

Keep it this way: adding investment, credit, insurance, tax or legal
guidance, or any automated action on money, needs a new usage-policy check
first.

## B. Plugin package and listing

| # | Requirement (source) | Meaning for MITA | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|---|
| B1 | Agent Plugins ZIP: root `plugin.json` with `$schema`, `name` ≤ 64 `[a-z0-9-]`, semver `version`, `description` ≤ 1,024 (S1, S4, S14) | — | `mita-finance`, 2.3.0, 181 chars; schemas identical to upstream | PASS | — | — |
| B2 | ≥ 1 valid skill; `plugin:skill` ≤ 64; `onboardingSkill` points to an included skill (S1, S4) | — | `skills/setup/SKILL.md`, `mita-finance:setup` | PASS | — | — |
| B3 | No `apps` / `.app.json`, no lifecycle hooks (S1, S4, S8) | — | none; validator refuses them | PASS | — | — |
| B4 | One remote streamable-HTTP server in `mcp.json`; production HTTPS URL (S1, S4) | — | `plugin/mita/mcp.template.json`; URL filled at release | PASS | URL = production (D1) | — |
| B5 | Server auth declared in `mcp.json` → `extensions["com.openai"].auth`; "the portal reads advanced authentication settings from your package's `mcp.json`"; a protected server must not be `type: "none"` (S1, S8) | MITA = OAuth with DCR (no CIMD) | was absent | **FIXED** | `{"type":"oauth","client":{"mode":"dcr"}}`; validator checks it (the portable schema does not model the extension, so it is validated separately) | P1 |
| B6 | No credentials or reviewer instructions in the ZIP (`test_credentials`, `reviewer_instructions` rejected), no `clientSecret`, no non-empty server `headers` (S1) | — | none; validator now refuses each | PASS | — | — |
| B7 | Listing: display name ≤ 30, subtitle ≤ 30 (one line), long description ≤ 4,000, developer name ≤ 80, ≤ 20 one-line capabilities ≤ 120, ≤ 3 unique one-line starter prompts ≤ 128 without @mentions (S1, S4) | — | 12 / 26 / 1,541 chars; 10 capabilities (max 66); prompts 30–42 chars | PASS | — | — |
| B8 | Category from the dashboard list (S4 `plugin_category_unknown`) | "Finance" | placeholder filled at release; validator now checks the list | PASS | `CATEGORY=Finance` | — |
| B9 | Brand colours: light ≥ 2:1 vs white, dark ≥ 2:1 vs `#212121` (S1, S4) | — | `#193C57` 11.5:1; `#FFD25F` 11.2:1; validator checks | PASS | — | — |
| B10 | `logo` and `composerIcon` required; square ≥ 48 px; PNG/JPEG/WebP/SVG ≤ 5 MiB; SVG with a numeric square viewBox (S1, S4) | — | four 512×512 SVGs | PASS | Owner, optional: the icons are a hand-drawn approximation of the mark; the Figma master logomark (used on the sign-in page) would match the brand rules in `CLAUDE.md` | P2 |
| B11 | Names/descriptions "clear, accurate"; no unverifiable claims, comparisons, pricing or promotions (S3) | mitafinance.com says the MITA app is "Coming soon — join the list" | long description, setup skill and `add_transaction` promised records "in the MITA app" | **FIXED** | claim removed (tested; restore when the app is in the stores); no pricing words (tested) | P1 |
| B12 | Not a generic name; no "MCP"/"Plugin" suffix (S3) | — | "MITA Finance" | PASS | — | — |
| B13 | Website, support, privacy-policy and terms URLs: required for MCP review, HTTPS, ≤ 1,024, publicly accessible and "identify the same publisher as the submission" (S1, S4) | Four real pages naming the verified publisher | 2026-10-27: `https://mitafinance.com` fails TLS (`tlsv1 alert internal error`); `www` and `mcp.` have no DNS; over HTTP `/privacy`, `/terms`, `/support` all return the landing page (605,912 bytes) | OWNER ACTION | O-5, O-8a, O-8b, O-9 | P0 |
| B14 | Package version and release notes summarizing the version submitted (S1, S4) | First public release | plugin 2.1.0, notes listed internal 2.1.0/2.0.0 history without R3 | **FIXED** | 2.3.0; release notes rewritten (bills held out of the safe daily amount, the calendar, consented statistics) | P1 |
| B15 | Screenshots: optional; "no longer shown in the Directory"; if supplied, one PNG/JPEG per starter prompt, 706 px wide, 400–860 px tall, only with UI (S3, S4) | — | none supplied (recommended: none) | N/A | validator enforces the format if any are added | — |
| B16 | Country availability (`publication.countries`); submit only for countries where you intend public availability (S1, S2) | Owner/legal choice | omitted (no restriction) | OWNER ACTION | Decide before submitting | P1 |
| B17 | Translations of subtitle/description (S1) | Optional | none | N/A | — | — |

## C. Review materials

| # | Requirement (source) | Meaning for MITA | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|---|
| C1 | Exactly 5 positive and 3 negative test cases; positive: prompt, `tools_triggered`, `expected_behavior` (S1, S4) | — | 5 + 3 in `plugin.template.json`; validator | PASS | — | — |
| C2 | Negative cases state why the plugin must not act and "the expected refusal, clarification, or safe fallback" (S1); UI errors are a listed rejection reason (S2) | The only UI component must be exercised | no case used the calendar; negatives had no expected outcome | **FIXED** | case 3 = "Show my financial calendar for this month." (`show_financial_calendar`); all three negatives carry `expected_behavior` | P1 |
| C3 | Run every case with the test account before submitting; they must pass "on the supported ChatGPT and Codex surfaces" (S1, S2) | Production, web and phone; the directory is shared with Codex | never run in production (no production MCP) | NEEDS REAL CHATGPT TEST | After D1 + C5; check what Codex shows if MITA is listed there | P0 |
| C4 | Reviewer-accessible demo video "that shows the main use cases and tools across supported platforms" (S1, S4) | Web and phone; include the calendar | not recorded; script lacked the calendar and the phone | OWNER ACTION | Script updated (`review/demo-script.md`); record on production | P0 |
| C5 | Reviewer credentials: dedicated account with sample data, login URL and steps, works "without MFA approval, email or SMS codes, magic links, or private-network access"; keep it available; no sign-up required (S1, S2, S3) | MITA has no MFA; the account must exist in production | not created | OWNER ACTION | `review/review-account.md` (O-10) | P0 |
| C6 | Annotation justification per tool and hint: guidelines say "no longer required" (S3), the error list still has `justification_required` (S4) | Conflicting docs — be ready | prepared: `review/annotation-justifications.md` | PASS | Paste if the portal asks | — |

## D. MCP server and tools

| # | Requirement (source) | Meaning for MITA | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|---|
| D1 | Production HTTPS MCP URL on a public domain; "You are not using a local or testing endpoint" (S1, S2, S4) | A production MCP service on production data; staging (test data, Railway hostname) cannot be submitted | production project has only `mita-production` + `mita-production-db` (Railway, read-only, 2026-10-27) | OWNER ACTION | O-6 / O-7 after the merge (Step 7) | P0 |
| D2 | The server origin (scheme, host, port) cannot change after publication — a new origin means a new plugin (S1, S2) | Choose the final hostname first, e.g. `mcp.mitafinance.com`; never `*.up.railway.app` | not chosen; `mita.finance` not registered (refused by the release build) | OWNER ACTION | O-5 | P0 |
| D3 | Domain verification: exact token as plain text at `https://<MCP host or eligible parent>/.well-known/openai-apps-challenge` (S1, S4) | — | endpoint returns the token as `text/plain`, `no-store`; 404 when unset (staging, 2026-10-27) | PASS (code) | Owner sets `OPENAI_APPS_CHALLENGE_TOKEN` on production | P0 |
| D4 | A successful, current tool scan of the production server (S4) | — | — | OWNER ACTION | After D1, in the portal | P0 |
| D5 | Tool names unique, plain verbs, no jargon (S3) | — | 24 tools; uniqueness tested | PASS | — | — |
| D6 | Descriptions match behaviour, state when to use, limits and side effects; never steer other plugins (S3) | — | every description states MITA cannot move money; write descriptions state their effect (tested) | PASS | — | — |
| D7 | `readOnlyHint`, `destructiveHint`, `openWorldHint` explicit booleans on every tool (S3, S4 `annotations_required`, S5) | — | `test_tool_contract.py` | PASS | — | — |
| D8 | Annotation accuracy: destructive for deletion, overwriting, revocation or "sending messages … you can't undo", "even … through indirect side effects"; "being able to undo an action does not, by itself, justify `destructiveHint` false" (S2, S3, S12) | `submit_feedback` sends the user's words to the MITA team | was `destructiveHint: false` | **FIXED** | now `true` (the host asks first). The other 23 stay as they were and are justified in `review/annotation-justifications.md` | P1 |
| D9 | Minimal, purpose-bound inputs; no conversation history, no precise location (S3) | — | regex test on every input schema; no identity arguments | PASS | — | — |
| D10 | Responses carry only what the request needs; no session/trace/request ids, timestamps, logs or secrets (S2, S3) | — | serializers whitelist fields; output scan tests | PASS | — | — |
| D11 | Each tool works independently; no generic executor (S3) | — | — | PASS | — | — |
| D12 | `outputSchema` for every tool that returns `structuredContent` (S5, S12) | — | tested on every tool | PASS | — | — |
| D13 | Safe to retry, or say when retries repeat effects (S3) | — | `idempotency_key` on create tools (race tested) | PASS | — | — |
| D14 | A tool marked `_meta["openai/profile"]: true` must return the standard profile (`id` plus optional `name`, `email`, `nickname`; `additionalProperties: false`) and publish that schema; "an invalid response can prevent account connection" (S7) | `get_profile` is MITA's profile tool | returned `currency`, `timezone`, `has_completed_onboarding` and `name: null` | **FIXED** | returns `{id, name (only when set), nickname}`; schema = OpenAI's; responses validated against OpenAI's schema in tests. Currency/timezone: `get_setup_status` and every money result | P0 |
| D15 | Server `instructions`: important details in the first 512 characters; reviewed with the tools (S2, S12) | — | present; the money-movement limit comes last (it is also in every tool description) | PASS | P2: move that sentence forward at the next instructions change | P2 |
| D16 | Auth failures: 401 + `WWW-Authenticate`; tool-level `_meta["mcp/www_authenticate"]` with `error` and `error_description` (S7) | — | `invalid_token` / `insufficient_scope` challenges (`runtime.py`) | PASS | — | — |
| D17 | After publication OpenAI scans daily: server code is live on deploy, new/changed tool metadata only after automated checks; "keep existing input schemas and each published UI resource URI working" (S1, S2) | Every production MCP deploy reaches users at once | — | OWNER ACTION (process) | Production MCP: pin commits or gate on CI; backward-compatible tool changes; bump the `ui://…-vN` URI only with the old one kept | P1 |

## E. Authentication

| # | Requirement (source) | Current state · evidence | Status | P |
|---|---|---|---|---|
| E1 | Protected-resource metadata + `401` with `resource_metadata` (S7) | staging, 2026-10-27: both PRM paths; `/mcp` → 401 with the challenge | PASS | — |
| E2 | AS metadata with exact `issuer`, endpoints and `code_challenge_methods_supported` incl. `S256` — otherwise "unsupported" (S7) | `["S256"]`, exact issuer | PASS | — |
| E3 | `token_endpoint_auth_methods_supported` published (S7) | `client_secret_basic`, `client_secret_post`, `none` | PASS | — |
| E4 | Client registration: CIMD preferred, DCR supported (S7, S9) | DCR | PASS (P2: CIMD) | P2 |
| E5 | `resource` echoed into the token audience; audience verified (S7) | RFC 8707 check at `/token`; `aud` required | PASS | — |
| E6 | Verify signature, issuer, expiry, audience, scopes on every call (S7) | RS256 + `kid`; grant bound to the password (`cfp`, `tv`) | PASS | — |
| E7 | Redirect URI: without RFC 9207 `iss`, ChatGPT uses `https://chatgpt.com/connector/oauth/{callback_id}` (S7) | both that form and the stable one allowed, exact matching | PASS | — |
| E8 | RFC 9207 issuer identification (optional; only advertise if `iss` is returned) | not advertised | N/A | — |
| E9 | Permissions explicit; users told every requested scope; least privilege (S3) | consent page lists all five scope titles (v5.2) | PASS | — |
| E10 | Keep registered OAuth clients valid while in use, or users get `invalid_client` (S7) | no client expiry; staging clean-up removes only token-less clients | PASS | — |
| E11 | Per-tool `securitySchemes` (S5, S7) | `_meta.securitySchemes` with the exact scope on every tool | PASS | — |
| E12 | No passwords, OTPs or keys collected through the plugin (S3 restricted data) | passwords only on MITA's own OAuth page; no tool takes one; the skill forbids asking | PASS | — |

## F. UI component (the financial calendar)

| # | Requirement (source) | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|
| F1 | MCP Apps resource, `text/html;profile=mcp-app`, `ui://` URI as the cache key (S5, S6, S13) | `ui://mita/financial-calendar-v1.html` | PASS | — | — |
| F2 | CSP that "allows the exact domains the component fetches from"; review compares the policy with behaviour (S2, S6) | `connectDomains: []`, `resourceDomains: []`, no `frameDomains`; the component loads nothing (source tests) | PASS | — | — |
| F3 | `_meta.ui.domain`: "Dedicated origin … required when submitting a plugin with UI; must be unique per plugin" (S5; S13: host-dependent, URL-derived for ChatGPT) | set from `MCP_WIDGET_DOMAIN`; now normalized to an origin, and **production refuses to start without it**; unset on staging (2026-10-27) | PASS (code) · OWNER ACTION (values) | staging: the staging origin (below); production: the final MCP origin | P0 |
| F4 | Embedded iframes need `frameDomains` and a justification (S3, S6) | none | N/A | — | — |
| F5 | Tools useful without UI; data and render tools separate (S6) | `get_calendar_month` / `show_financial_calendar`; render tool takes no figures | PASS | — | — |
| F6 | "Plugins must function reliably in ChatGPT on both desktop and mobile, including any UI components"; no UI errors (S2, S3) | only a local MCP Apps host (65/65, axe 0); staging still runs 2.2.0 | NEEDS REAL CHATGPT TEST | `calendar-owner-test.md` after the staging deploy | P0 |
| F7 | UI guidelines: ≤ 2 primary actions inline, system fonts, no logo in the response, WCAG AA (S10) | Open calendar + Save as PNG; system font stack; logomark only in the exported PNG; axe 0 violations | PASS | confirm in ChatGPT (F6) | — |
| F8 | Display modes declared before load (S5) | `inline`, `fullscreen` | PASS | — | — |

## G. Privacy, policy, commerce

| # | Requirement (source) | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|
| G1 | Published privacy policy with categories of personal data, purposes, recipients, **retention timelines** and user controls; followed at all times (S3) | none published; `legal/policy-redline.md` drafted; retention periods are **[OWNER]** cells in `data-inventory.md` | OWNER ACTION | O-9, O-17, O-8b | P0 |
| G2 | The policy discloses every user-related data type the tools return — a common rejection reason (S2) | returned: name, masked e-mail, expenses (date, amount, category, merchant), stated income, household size, savings target, regular payments, goals, plans; stored: feedback text, consented usage statistics | OWNER ACTION | include each in the policy | P0 |
| G3 | Terms of service URL (S1) | ToS not published | OWNER ACTION | after G8 | P0 |
| G4 | Customer support contact, kept accurate (S1, S3) | support page drafted (`legal/support-page.md`); no working address on an owned domain | OWNER ACTION | O-5, O-8b | P0 |
| G5 | Collect the minimum; no PCI, PHI, government ids or credentials (S3) | no such inputs; card/bank/address requests forbidden by the skill | PASS | — | — |
| G6 | Tracking or metadata collection only if "explicitly disclosed, narrowly scoped, subject to meaningful user control" (S3) | consented statistics: box unticked by default, `set_usage_analytics(false)` deletes linked events — PASS. Without consent MITA still writes tool-call counts linked to nobody | OWNER ACTION | disclose those counts, or turn them off (one line in `analytics.py`) | P1 |
| G7 | Publish retention; "Respect deletion requests" (S9) | account deletion exists only in the mobile app, which is not released: a ChatGPT-created account cannot delete itself | OWNER ACTION | policy + support page: deletion on request via support until the app ships | P0 |
| G8 | "Plugins must be suitable for general audiences, including users aged 13–17" and "may not explicitly target children under 13" (S3); the 2026-11-20 Usage Policies strengthen protections for children and teens (A5b) | ToS §2.1 = 18+; nothing enforces an age | OWNER ACTION | O-9c (legal) | P0 |
| G9 | Commerce: physical goods only; no digital subscriptions, upsell or checkout links (S3) | `commerce: false`; no Premium gate in ChatGPT; no pricing words (tested) | PASS | — | — |
| G10 | No "execution of money transfers, crypto transfers, or investment trades"; no lending/credit-repair schemes (S3) | no such tool; stated in every description; 3 negative cases | PASS | — | — |
| G11 | No ads; owned IP; no implied OpenAI endorsement; purpose beyond ChatGPT's built-ins; not a trial (S3) | persistent budget engine; AI hero image labelled illustration | PASS | — | — |
| G12 | Fair play and respect for user intent (S3) | metadata states facts only (tested) | PASS | — | — |

## H. Environments and security hygiene (not OpenAI review gates unless noted)

| # | Item | Current state · evidence | Status | Action | P |
|---|---|---|---|---|---|
| H1 | Staging carries the code that will be submitted | `mita-mcp-staging` pinned to `dbdc118` (MCP 2.2.0, v4 page, usage box pre-ticked) since 2026-10-24 | NEEDS DEPLOY | plan below | P0 |
| H2 | Submitting while staging is the only endpoint | not possible: D1–D4 and C5 need production | — | — | — |
| H3 | MCP image dependencies | `pip-audit` of `requirements-mcp.lock`: 0 known vulnerabilities (2026-10-27) | PASS | — | — |
| H4 | API image dependencies (`requirements.txt`, unchanged by this branch, already in production) | `pip-audit --no-deps` 2026-10-27: **130 advisories in 9 directly pinned packages** — aiohttp 3.12.14 (40), pillow 11.0.0 (51), pyjwt 2.10.1 (17), cryptography 44.0.1 (6), python-multipart 0.0.18 (6), starlette 0.47.2 (6), bleach 6.2.0 (2), python-dotenv 1.0.1 (1), requests 2.32.4 (1). The earlier "200" is not reproduced; the nine packages match | OWNER ACTION (eng) | separate upgrade PR with backend and mobile CI before the production merge; starlette ≥ 1.x needs a FastAPI upgrade | P1 |
| H5 | Production DB public TCP proxy `shinkansen.proxy.rlwy.net:12880` | still ACTIVE (2026-10-27) | OWNER ACTION | O-4b | P1 |
| H6 | Production API healthcheck before the merge (every merge migrates on boot) | none configured on `mita-production` | OWNER ACTION | O-11a | P0 (merge) |
| H7 | Credentials possibly exposed in Railway's 2026-10-21 incident | staging rotated 2026-10-23; production not | OWNER ACTION | before configuring the production MCP | P1 |

## Totals

OpenAI requirements (sections A–G, 79 rows, 4 not applicable): **75
applicable — 51 met** (6 of them fixed in this pass; the Usage Policies,
A5a/A5b, pass on the owner's verification of the official page), **2 met in
code but waiting for production values** (D3 the domain-verification token,
F3 the widget origin), **20 owner actions**, **2 need real ChatGPT** (C3,
F6).
Section H adds the staging deploy (H1) and four hygiene items for the owner
(H4–H7). No known code or configuration change is outstanding. By count that
is 68 % (51/75), but the open items include every P0 that blocks
submission, so the percentage is not a readiness measure.

## Earlier assumptions, checked against today's documents

| Earlier note | Today |
|---|---|
| Exactly 5 positive + 3 negative test cases | **Confirmed** (S1, S4) |
| Demo video required | **Confirmed**, and it must show the main use cases "across supported platforms" (S4) |
| Suitable for 13–17 | **Confirmed** (S3) |
| `_meta.ui.domain` required at submission, unique | **Confirmed** (S5) |
| All four listing URLs, HTTPS | **Confirmed**, plus "identify the same publisher" (S1) |
| Domain verification at `/.well-known/openai-apps-challenge` | **Confirmed**; MCP host or an eligible parent domain (S1) |
| "The MCP URL cannot be changed after publication" | **Refined**: the origin cannot change (new plugin needed); the path can, in a new version (S2) |
| Annotation justifications required | **Contradictory**: S3 "no longer required", S4 still lists `justification_required`; texts prepared |
| Screenshots | **Outdated**: optional, "no longer shown in the Directory"; strict format if supplied (S3, S4) |
| Profile tool = marker + stable id | **Stricter now**: the response must match OpenAI's profile schema exactly (S7) — fixed |
| Auth configured in the portal form | **Changed**: the portal reads auth from `mcp.json` (S1, S8) — fixed |
| Plugins are ChatGPT-only | **Changed**: one directory shared by ChatGPT and Codex; cases must pass on supported surfaces (S2) |
| Developer-mode path "Settings → Apps" | **Changed**: chatgpt.com/plugins → Add custom MCP server → Create as a plugin; Refresh (S11) |
| API dependency audit: 200 advisories | **Corrected**: 130 in the same 9 packages; not an OpenAI gate and not introduced by this branch |
| Usage policies | **New version** effective 2026-11-20 (S15, owner-verified); MITA's current scope passes both versions (A5) |
| EU data residency | **New**: EU-residency projects cannot submit MCP plugins (S2) |

## Changes in this pass (local, uncommitted)

| Change | Files | Tests |
|---|---|---|
| `get_profile` returns OpenAI's standard profile only; `name` omitted when unset; schema published exactly | `app/mcp/schemas.py`, `serializers.py`, `tools/profile.py` | `test_tool_contract.py` (schema + responses validated with OpenAI's schema), `test_finance_accuracy.py`, `test_empty_state.py`, `test_auth.py` |
| `submit_feedback` `destructiveHint` true | `app/mcp/tools/feedback.py`, `tools/common.py` | `test_tool_contract.EXPECTED` |
| `mcp.json` declares OAuth + DCR | `plugin/mita/mcp.template.json` | `test_plugin_package.py` |
| Validator: package description ≤ 1,024, category list, one-line fields, Unicode-normalized prompt uniqueness, brand contrast, release notes and demo URL required, credentials refused, screenshot format, `mcp.json` auth, logo + composer icon required, negative expected outcome | `scripts/mcp/build_plugin.py` | `test_plugin_package.py` (15 new rejection cases) |
| Listing 2.3.0: release notes, calendar review case, negative expected outcomes, no "MITA app" promise | `plugin/mita/plugin.template.json`, `skills/setup/SKILL.md`, `app/mcp/tools/transactions.py` | `test_plugin_package.py` |
| `MCP_WIDGET_DOMAIN` normalized to an origin; required in production | `app/mcp/config.py`, `deploy/mcp/.env.example` | `test_secret_separation.py` |
| Found while verifying (not an OpenAI rule): since the v5.2 page (`74ea5cf`) every start wrote one plain-text log line with the sign-in example's fictional amounts (the forecast engine's INFO line, emitted while the page's example is computed at import, before MCP logging took over). Logging is now taken over before the domain layer is imported | `app/mcp/__main__.py` | `test_startup_logging.py` (fails on the old order); `e2e_http.py` log check passes locally |

No financial behaviour changed: no engine, rebalancer, forecast, calendar
figure, sign-in page or migration was touched.

**Verification (local, 2026-10-27).** Full MCP suite 652 passed (627 before); `build_plugin.py --check` valid and a check ZIP built (7 files:
`plugin.json`, `mcp.json`, 4 icons, the skill); `scripts/mcp/e2e_http.py`
against a local server on a fresh database migrated to 0039 — OAuth with
PKCE, all 24 tools listed, every read tool with a read-only grant, a restart,
password-change revocation, and the log checks: all PASS; black, isort, ruff
(both CI toolchains) and Bandit clean. No backend or mobile file changed, so
those suites were not re-run locally; CI runs them on push.

## Staging deployment plan (MCP 2.3.0) — not executed

Pre-conditions: the owner approves the changes; they are committed on
`feat/chatgpt-auth-ui` and pushed; GitHub CI is green on that exact SHA
(Backend, Mobile, MCP incl. container end-to-end).

1. **Variables (staging only).** Add
   `MCP_WIDGET_DOMAIN=https://mita-mcp-staging-staging.up.railway.app` (the
   staging origin: the component is then served the way it will be in
   production). Keep the 18 existing variables unchanged. Do not set
   `OPENAI_APPS_CHALLENGE_TOKEN` (no submission from staging). Leave
   `MCP_SUPPORT_URL` unset until a real support page exists. Set with
   `--skip-deploys`.
2. **Source.** Connect `mita-mcp-staging` to `teniee/mita_project` @
   `feat/chatgpt-auth-ui` with `commitSha=<the CI-green SHA>` (a new build —
   not "Redeploy", which rebuilds `dbdc118`). Healthcheck `/health` (60 s)
   keeps `dbdc118` serving if the new build fails.
3. **Database.** No migration: head stays `0039`; no new grant for `mita_mcp`
   (no new table or column is written).
4. **Verify (Claude, public endpoints).** `/health` → `2.3.0`; protected-
   resource and AS metadata unchanged (five scopes, `S256`, `none`);
   unauthenticated `/mcp` → 401; `tools/list` = 24 tools; `get_profile`
   output schema = OpenAI's profile schema; `submit_feedback`
   `destructiveHint: true`; the calendar resource's `_meta.ui.domain` = the
   staging origin and its CSP empty; `scripts/mcp/e2e_http.py` (both phases,
   restart), `staging_failure_modes.py`, `e2e_v2.py`, `calendar_widget_review.py`
   against staging; a log scan (no e-mail, token, amount, merchant or secret).
   The clean-up of these runs needs a temporary database TCP proxy — owner
   approval, removed afterwards.
5. **Owner, in ChatGPT.** Refresh the staging connector (tool metadata
   changed) and run `calendar-owner-test.md` on the phone and the computer.
6. **Rollback.** Re-pin to `dbdc118` the same way; nothing in the database
   changes in either direction.

## Production, inspected read-only (nothing executed)

| Fact | Evidence (Railway, 2026-10-27) |
|---|---|
| Merging into `main` deploys `mita-production` automatically: source `teniee/mita_project` @ `main`, `checkSuites: false`, no commit pin | service config |
| `bash start.sh` runs `alembic upgrade head` on boot and exits in production if it fails; the merge applies 0037–0039 | `start.sh` lines 174–201 |
| No Railway healthcheck on `mita-production`: a failed boot leaves nothing serving | deploy config (no `healthcheckPath`) |
| Latest production deployment 2026-09-29 (`3aa52b7`); `main` = `27ed25d`, branch 48 commits ahead, 0 behind | Railway, git |
| The merge also changes the mobile API: forecast with bills held out (R3), local day (F-9), `live_status` without savings | `app/api/budget/routes.py`, forecast engine |
| No production MCP service; production DB `mita-production-db` (Postgres 17) with an ACTIVE public TCP proxy | Railway |
| Rollback after 0037: a pre-merge deployment cannot boot (`Can't locate revision '0037'`) — fix forward, or `alembic downgrade 0036` from merged code first | `production-readiness.md` Step 7 |
| Production MCP configuration (when created, O-6): OAuth issuer and resource derive from `MCP_PUBLIC_URL` (the final host; issuer compared exactly); redirect allow-list defaults to ChatGPT's two forms; fresh secrets from `generate_keys.py`, never staging's or the API's; `DATABASE_URL` as the least-privilege `mita_mcp` role (`scripts/mcp/mcp_service_role.sql`, owner-run after the migrations); `MCP_WIDGET_DOMAIN` and `OPENAI_APPS_CHALLENGE_TOKEN`; 1 replica (rate limits are per process); healthcheck `/health` (503 until 0037–0039 exist) | `staging.md` variable table, `OWNER_ACTIONS.md` O-6 |

## Sequence (adjusted)

The intended sequence holds. Insertions from today's documents:

1. **Now, in parallel (owner):** A1 verification and A3 global-residency
   project; D2 final MCP hostname; B13/G1–G4 domain, HTTPS website, privacy,
   terms and support pages; G8 age decision; G7 retention and deletion text;
   H7 production secret rotation.
2. Staging 2.3.0 (plan above) → real-ChatGPT acceptance → fix what it finds.
3. Before the merge: H4 dependency upgrade PR; H6 production healthcheck;
   O-11b pre-flight.
4. Merge → production API + migrations → D1 production MCP service with the
   final hostname, `MCP_WIDGET_DOMAIN`, `OPENAI_APPS_CHALLENGE_TOKEN`, source
   pinned or CI-gated (D17).
5. C5 review account in production (data entered through ChatGPT), C3 the
   5 + 3 cases on web and phone, C4 the video, release ZIP (`--release`),
   upload, resolve findings, domain verification, scan, submit.
