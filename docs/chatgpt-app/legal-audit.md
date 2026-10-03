# Privacy Policy / Terms audit for the ChatGPT app

This is an engineering comparison of the policy texts in the repository
(`PRIVACY_POLICY.md/.html`, `TERMS_OF_SERVICE.md/.html`) with what the code
does. It is **not legal advice**; every item marked *owner/legal* needs a
decision by the owner or counsel before submission. Nothing here was changed
in the published policies.

## Claims that the code does not support

| Claim (Privacy Policy) | What the code shows | Action |
|---|---|---|
| Bank connections "via Plaid or similar", "Plaid, Yodlee" (§1.1, §1.3, §9) | No Plaid/Yodlee dependency in `requirements.txt` or `mobile_app/pubspec.yaml`; no bank-sync code path | Remove or mark as future — *owner/legal* |
| "Google Analytics — usage analytics (anonymized)" (§3, §8) | No analytics SDK in `pubspec.yaml` | Remove or verify elsewhere — *owner* |
| "SOC 2 Type II certified hosting providers", "ISO 27001", "PCI DSS (when applicable)" (§4, appendix) | Vendor certifications are the vendors'; MITA itself holds none that the repo shows | Reword to vendor-level facts or remove — *owner/legal* |
| "Regular security audits and penetration testing" (§4) | No evidence in repo | Remove unless real — *owner* |
| "TLS 1.3 for all communications", "AES-256 at rest" (§4.1) | TLS depends on host config (and https://mitafinance.com currently fails TLS); at-rest encryption is Supabase's | Reword — *owner/legal* |
| "Peer data is aggregated and anonymized" | CLAUDE.md documents residual multi-account inference in cohort comparison | Reword — *owner/legal* |
| Retention: transactions "account lifetime + 7 years", backups purged in 90 days, deleted accounts purged in 30 days | `DELETE /api/auth/delete-account` exists; no retention/backup-purge job in the repo | Verify the actual process — *owner* |
| Contact addresses `privacy@`, `support@`, `dpo@mita.finance` | `mita.finance` is **not registered** (repository-audit §7) — these addresses cannot receive mail | Replace with working addresses on an owned domain — *owner* (blocker) |

Confirmed true in code: Google Cloud Vision is a dependency (OCR);
OpenAI is used by the API's AI features; Railway hosts the API; Supabase hosts
PostgreSQL; account deletion endpoint exists.

## Terms of Service

| Item | Issue | Action |
|---|---|---|
| §2.1 "You must be at least 18" | OpenAI: plugins must be suitable for users 13–17; "Age 18+ experiences require verification systems." MITA has no age verification. | Decide: allow 13+ (with any jurisdictional limits) or implement age verification — *owner/legal* (blocker) |
| Contact addresses on `mita.finance` | not deliverable | replace — *owner* |

## Additions needed for the ChatGPT data flow (draft text for counsel)

Proposed new Privacy Policy section — **draft, to be reviewed**:

> **Using MITA in ChatGPT.** If you connect MITA to ChatGPT, you sign in with
> your MITA e-mail and password on a MITA page and approve read-only access.
> When you ask ChatGPT about your finances, MITA sends ChatGPT only the data
> needed to answer that question: transaction dates, amounts, currencies,
> categories and merchant names; your budget plan and its totals; savings goal
> titles and amounts; scheduled and recurring expenses you entered; your
> display name, a masked e-mail address, currency and timezone. MITA never
> sends your password, full e-mail address, notes, receipt images or
> locations. The connection is read-only: ChatGPT cannot change your data,
> move money or make payments through MITA. Data you receive in ChatGPT is
> processed by OpenAI under OpenAI's terms and privacy policy. You can
> disconnect in ChatGPT at any time; changing your MITA password or signing
> out of all devices also ends the connection. MITA keeps a hashed record of
> the connection (no tokens in plain text) until it expires or is revoked, and
> deletes it with your account.

Also add OpenAI (ChatGPT) to the list of recipients **for users who connect
the ChatGPT app**, distinct from the API's existing OpenAI use for in-app AI
features (which sends data to the OpenAI API under MITA's account).

## Publishing requirements (OpenAI)

Website, support, privacy policy and terms URLs must be public **HTTPS** pages.
Today `https://mitafinance.com` fails the TLS handshake and every path returns
the same landing page (repository-audit §7). See OWNER_ACTIONS O-8.
