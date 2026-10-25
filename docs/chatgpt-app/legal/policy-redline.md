# Privacy Policy and Terms — redline for publication (Step 4)

Engineering draft for counsel, **not legal advice**. It applies the
corrections already identified in `../legal-audit.md` to the repository texts
(`PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`), adds the ChatGPT section, and
gives both age-clause variants for Step 5. It is not a new audit: every
statement below is either evidenced in the code or production configuration
(cited), or marked **[CONFIRM]** for the owner. Nothing here has been
published or applied to the source files.

Placeholders: `{DOMAIN}` (Step 2, recommended `mitafinance.com`),
`{SUPPORT_EMAIL}`, `{PRIVACY_EMAIL}`, `{POSTAL_ADDRESS}`.

## A. Privacy Policy

| § | Current text (summary) | Replace with | Evidence |
|---|---|---|---|
| 1.1 Financial data | "Bank account connections (via secure third-party providers)" | delete the line | no bank or payment integration in `app/` or `mobile_app/pubspec.yaml` |
| 1.3 | "Bank Account Data … via Plaid or similar services" | delete the subsection | same |
| 1.3 Social authentication | "Apple/Google/Facebook" | "If you sign in with Google: your name and e-mail address from Google." **[CONFIRM]** Apple / Facebook sign-in | `GOOGLE_CLIENT_ID` is set on `mita-production`; Apple/Facebook not evidenced |
| 1.2 Device | "Unique device identifiers (IDFA/Advertising ID …)" | delete unless the app reads one **[CONFIRM]** | no advertising or analytics SDK in `pubspec.yaml` (legal-audit) |
| 3.1 Infrastructure | Railway; Supabase (database); Firebase; Cloudflare | "Railway (application hosting and PostgreSQL database, United States, us-east4); Upstash (Redis cache); Firebase / Google (push notifications, crash reports)." Remove Supabase and Cloudflare unless still used **[CONFIRM]** | `mita-production` and `mita-production-db` (Postgres 17) on Railway us-east4; `UPSTASH_*` variables; Firebase initialized (`/health`) |
| 3.1 Analytics | Sentry; Google Analytics | delete Google Analytics; keep Sentry only if enabled **[CONFIRM]** (the API reports Sentry unconfigured) | legal-audit; `/health` `sentry_configured: false` |
| 3.1 AI | "OpenAI (GPT-4) … Personal identifiers removed before processing" | "OpenAI (AI features inside the MITA app); Google Cloud Vision (reading receipt images you upload)." Keep "identifiers removed" only if true **[CONFIRM]** | `OPENAI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS` on `mita-production` |
| 3.1 Payments | Apple IAP; "Stripe (future)" | "Apple App Store and Google Play (Premium subscriptions; we never receive card numbers)." Delete future providers | `app/core/api_key_manager.py` only names Stripe; no Stripe code |
| 3.1 E-mail | SendGrid; "Postmark (future)" | name the provider behind `SMTP_HOST` **[CONFIRM]**; delete future providers | `SMTP_*` variables on `mita-production` |
| 3.1 closing | "All service providers sign DPAs … comply with GDPR and CCPA" | keep only what is signed **[CONFIRM]** | — |
| new 3.5 | — | **Using MITA in ChatGPT** (section C) | `app/mcp/` |
| 4.1 | "TLS 1.3 for all communications", "AES-256 at rest", "Certificate pinning" | "Connections to MITA's servers use HTTPS (TLS). Data at rest is stored with our hosting provider's encryption. Passwords are stored as bcrypt hashes." Keep certificate pinning only if the app does it **[CONFIRM]** | legal-audit; `app/core/password_security.py` |
| 4.2 | RBAC, MFA for admin accounts, access audits | keep only what exists **[CONFIRM]** | — |
| 4.3 | "SOC 2 Type II certified hosting providers", "DDoS protection via Cloudflare", "PgBouncer" | "Rate limiting on the API." Name vendor certifications only as the vendor's own **[CONFIRM]** | production DB is direct Railway Postgres, not PgBouncer |
| 4.4 | "24/7 security monitoring via Sentry", "Regular security audits and penetration testing" | delete unless real **[CONFIRM]** | legal-audit |
| 4.5 + Appendix | 30-day deletion, 90-day backup purge, 7-year transaction retention, 26-month analytics | state the real process: account deletion is available in the app (`DELETE /api/auth/delete-account`); give real backup and log periods **[CONFIRM]** — the repo has no scheduled purge or backup-rotation job | legal-audit |
| 6 Children | "not intended for users under 18" | per Step 5 (section D) | — |
| 8.1 | "Analytics Cookies: Google Analytics, Sentry" | delete Google Analytics | legal-audit |
| Peer comparison wording ("aggregated and anonymized") | — | "Peer comparisons show one figure: the median 30-day spending of your income tier, rounded to $100, and only when at least 10 other users in that tier have recorded spending. It is not linked to any person, but it is derived from real users' data." Do not call it anonymous **[CONFIRM wording with counsel]** | CLAUDE.md cohort contract: k = 10, `median_low` rounded to $100 (one member's bucket), residual multi-account inference |
| 12 Contact | `privacy@`, `support@`, `dpo@mita.finance` | `{PRIVACY_EMAIL}`, `{SUPPORT_EMAIL}`; "YAKOVLEV LTD (company no. 207808591), {POSTAL_ADDRESS}" | `mita.finance` is not registered: those addresses cannot receive mail |
| 17 | SOC 2 (Railway, Supabase), ISO 27001, PCI DSS, "GDPR/CCPA compliant" | delete the section, or list only vendor certifications with the vendor named **[CONFIRM]** | legal-audit |

## B. Terms of Service

| § | Current text | Replace with |
|---|---|---|
| header, 9, 13… (14 places) | `legal@` / `support@mita.finance` | `{SUPPORT_EMAIL}` (and a legal address on `{DOMAIN}`) |
| 2.1 | "at least 18 years of age" | per Step 5 (section D) |
| 8.1 Banking and Financial | "Plaid (bank account connections)", "Yodlee (transaction aggregation)", "Your financial institutions" | delete — MITA connects to no bank |
| 8.1 Infrastructure | "Railway, Supabase (hosting)", "Cloudflare (CDN and security)" | "Railway (hosting and database)"; Cloudflare only if used **[CONFIRM]** |
| 8.1 new item | — | "OpenAI ChatGPT — only if you connect the MITA app in ChatGPT (see 8.6)." |
| 8.3 Bank Account Connections | whole subsection | delete |
| new 8.6 | — | **ChatGPT app.** "If you connect MITA to ChatGPT, ChatGPT can read your MITA data and, when you ask, record and change it as described in the Privacy Policy (expenses, profile, budgets you reviewed, recurring expenses, goals, feedback). MITA cannot initiate, execute or facilitate payments, money transfers or trades. Answers in ChatGPT are generated by OpenAI and governed by OpenAI's terms; check figures in the MITA app before relying on them. You can disconnect in ChatGPT at any time; changing your MITA password also ends the connection." |

## C. New Privacy Policy section: Using MITA in ChatGPT

Updated 2026-10-12 for the read/write v2 app (`app/mcp/`,
`docs/chatgpt-app/data-inventory.md`):

> **Using MITA in ChatGPT.** You can connect MITA to ChatGPT by signing in
> to — or creating — your MITA account on a MITA page and approving access.
> When you ask, ChatGPT can then read your MITA data and, at your request,
> record and correct expenses, save your income, currency, household size
> and savings target, save a monthly budget you reviewed, add recurring
> expenses and savings goals, and send feedback to the MITA team. Everything
> saved stays in your MITA account and is available in later conversations
> and in the MITA app. If you attach a receipt photo, ChatGPT reads it and
> sends MITA only the expenses (date, amount, category, merchant); MITA never
> receives or stores the image. MITA sends ChatGPT only what your question
> needs and never your password, full e-mail address, notes or locations.
> MITA cannot initiate, execute or facilitate payments, money transfers or
> trades, and is not connected to your bank.
>
> **Usage statistics.** If you agree on the connection page, MITA records which
> MITA features you use, when, and whether they worked, under a pseudonymous
> key — never your conversations, amounts, merchants or other financial
> details. You can turn this off at any time in ChatGPT ("stop sharing my
> usage statistics"); that also deletes what was already linked to you.
>
> **Feedback** you choose to send is stored with your account and read by
> the MITA team. What ChatGPT receives is processed by OpenAI under OpenAI's
> terms and privacy policy. You can disconnect in ChatGPT at any time;
> changing your MITA password also ends the connection. MITA stores
> connection records with tokens only as one-way hashes; deleting your MITA
> account deletes your records, feedback, usage statistics and connection.

Evidence: tool outputs whitelist in `app/mcp/serializers.py`; write tools in
`app/mcp/tools/*`; analytics allow-list and consent in `app/mcp/analytics.py`;
cascades in migrations 0037–0039. **[CONFIRM with counsel]**: legal basis
for usage statistics (consent vs legitimate interest — the consent box starts
unticked since 2026-10-25, so ticking it is an affirmative act) and retention
periods for feedback and linked statistics.

Also list OpenAI as a recipient **for users who connect the ChatGPT app**,
separately from the in-app AI features.

## D. Age clause (Step 5 decides)

* **Variant (a), recommended for submission — 13+:**
  Terms 2.1: "You must be at least 13 years old to use MITA. If you are under
  the age at which you can consent to data processing in your country (14 in
  Bulgaria), a parent or guardian must agree to these Terms for you.
  Purchases are made through the App Store or Google Play and are subject to
  their family controls."
  Privacy 6: "MITA is not directed at children under 13 and we do not
  knowingly collect their data. If we learn that we have, we delete it.
  Users aged 13–17 may use MITA as described in the Terms."
* **Variant (b)/(c) — keep 18+:** unchanged text; record in OWNER_ACTIONS why
  the OpenAI 13–17 suitability requirement is still met (see
  production-readiness Step 5 for the risk).

## E. Facts only the owner can confirm before publication

Postal address · e-mail provider behind `SMTP_HOST`, and whether production
mail is delivered at all (`SMTP_PASSWORD` is not set on `mita-production`) ·
whether Sentry runs in
the mobile app · Apple/Facebook sign-in · Cloudflare use · signed DPAs ·
actual backup and log retention · whether personal identifiers are removed
before OpenAI calls · certificate pinning · admin MFA/RBAC · whether the
Supabase project `atdcxppfflmiwjwjuqyl` still holds personal data (if it
does, it is a processor and belongs in 3.1 until deleted).
