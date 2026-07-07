# MITA — Production Readiness (Live)

> **Owner:** production-readiness engineering · **Branch:** `claude/mita-closed-beta-readiness-95q19q`
> **Last updated:** 2026-07-07 (session 5 — deployability)
> **Latest code commit:** `7cc0e12` (jinja2 clean-env boot fix + deployment docs) on top of main `73c1817`
> **Verification environment:** Python 3.11 venv (prod requirements only) · PostgreSQL 16 (real, empty) · Redis 7 (real) · no Android SDK (dl.google.com blocked) · Railway host unreachable from sandbox (probe via GitHub runners)

This file is the single source of truth. Update **before** each change and **after** each verified fix.

---

## Where things stand (session 5)

Session-4 work **is merged**: PR #273 (squash `73c1817`) landed on main 2026-07-07 12:23 UTC and
**main CI is green** — Main CI/CD Pipeline run **#229** ✅ and Security Scanning run **#169** ✅ on
`73c1817`. (Run #227 was the same pipeline going green on the pre-merge branch.) The "PR the fixes
to main" item from session 4 is **done**.

This session moved from "locally verified" toward "deployable": booting the backend in
`ENVIRONMENT=production` from an **empty** database with **only documented env vars** exposed a
real deployment blocker — `jinja2` was missing from `requirements.txt` (only present transitively
via dev deps; a Railway/Docker image crashes at import, before binding the port). Fixed in
`7cc0e12`; the same clean-env boot then ran migrations 0001→0034 and passed the full **19/19**
smoke journey.

## Status dashboard

| Item | Status | Evidence / blocker |
|------|--------|--------------------|
| Branch | `claude/mita-closed-beta-readiness-95q19q` (from main `73c1817`) | — |
| Latest commit | `7cc0e12` + tracker update commit | this branch |
| PR status | Session-4 fixes: **merged** (PR #273). This session's jinja2 fix + docs: PR to main **open** (see PR list; do not merge without owner approval) | GitHub |
| Main CI | ✅ green — run #229 + Security #169 on `73c1817` | Actions |
| Railway deployment | ❌ **none exists** — old service returns Railway-edge 404. Complete recreation recipe ready: `docs/RAILWAY_DEPLOYMENT.md` | owner action |
| Staging URL | ❌ none — exact creation steps in `docs/RAILWAY_DEPLOYMENT.md` §4 | owner action |
| Remote E2E (deployed) | ❌ blocked on a URL. Locally: **19/19** vs clean-env production boot at this commit (register→login→onboarding→budget→transaction→calendar 31/31 days, today present, all limits > 0, spent 23.75 reflected, YYYY-MM-DD keys→day detail→refresh rotation→rotated token works→logout→404 stays 404→4xx never 500). One-click re-run vs any URL: Actions → "Deployed Backend Smoke Test" | this session |
| Clean-env production boot | ✅ **verified** with only `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET`, `SECRET_KEY`, `OPENAI_API_KEY`(placeholder), `REDIS_URL`, `PORT` — after `7cc0e12` | this session |
| Android release | ⚠️ debug APK only (CI artifact `mita-debug-apk`). Release hygiene source-verified ✅ (applicationId `mita.finance`, v1.0+1, dart-define API URL, no localhost, no bundled secrets, cleartext off, logging gated, Firebase degrades gracefully, pinning safely off). Release APK/AAB needs the owner's keystore — exact requirements in `docs/ANDROID_RELEASE.md` | owner keystore |
| Firebase | ❌ not connected (by design, fail-safe): app boots without it; push/Crashlytics off until `google-services.json` + FIREBASE_* dart-defines (mobile) and `GOOGLE_APPLICATION_CREDENTIALS` (backend) | owner credentials |
| IAP production | ❌ not configured; **fails closed** (safe). Not required for a free closed beta. Vars in `docs/RAILWAY_DEPLOYMENT.md` §2.8 | owner store setup |
| Offline reads | ✅ cached calendar reads (sqflite, 2h) + deterministic fallback | code-verified |
| Offline writes | ❌ **not queued** — offline transaction creation fails **visibly**, no silent loss. Estimate for true queue: 11–16 days. **Product decision pending** — see `docs/OFFLINE_BEHAVIOR.md` | owner decision |
| iOS build | ❌ needs macOS/Xcode runner | environment |

## Verified readiness

- **Code readiness: ~92%.** Everything session 4 verified still holds at merged main, plus:
  clean-environment production boot now actually works (it did **not** before `7cc0e12` — that
  crash would have been the first Railway deploy's failure mode). Test totals at this lineage:
  backend `tests/` 287 + `app/tests` 611+, Flutter 376 passed / 15 skipped, IAP suite 21, local
  E2E smoke 19/19 (re-run this session on prod-requirements-only venv).
- **Deployed readiness: 0%. There is still no deployment.** This remains the single gating
  item, and it is an owner action (Railway account). The recipe is now complete and verified
  as far as it can be without credentials: `docs/RAILWAY_DEPLOYMENT.md`.
- **The app is NOT ready for closed beta** until: backend deployed → deployed smoke 19/19 →
  release-signed Android build pointing at that backend (`--dart-define=API_BASE_URL=...`).
  No other critical/high blocker is known in the code itself.

## Remaining owner actions (nothing below can be done from the repo)

1. **Create the Railway service** (project + PostgreSQL + Redis + variables) —
   step-by-step: `docs/RAILWAY_DEPLOYMENT.md` §4. ~30 minutes.
2. Report the staging/production base URL → we run the **Deployed Backend Smoke Test**
   workflow against it (19 checks, one click).
3. Approve (or reject) the open PR with `7cc0e12` — **without the jinja2 pin, step 1 will
   crash-loop**, so merge this before deploying.
4. Generate the Android release keystore and provide it per `docs/ANDROID_RELEASE.md` (or
   accept debug-signed side-loading for the very first testers).
5. Decide the offline question: ship beta online-first (recommended) or fund the 11–16 day
   write-queue build first — `docs/OFFLINE_BEHAVIOR.md`.
6. When ready for push/IAP: Firebase + store credentials (`docs/RAILWAY_DEPLOYMENT.md` §2.4/§2.8).

## Exact next task

**Owner: execute `docs/RAILWAY_DEPLOYMENT.md` §4 (staging service) after merging the open PR.**
Everything code-side is done and verified; the next state change requires a Railway account.
Once a URL exists: run the deployed smoke workflow, then build the staging APK
(`docs/ANDROID_RELEASE.md`) and hand it to the first testers.

## Session history (compressed)

- **Session 3** (`claude/mita-finance-prod-ready-wqj2k9` → PR #272 `be220da`): calendar Decimal
  500 fix, migration 0034, Flutter 3.35.4 pin, hermetic mobile CI.
- **Session 4** (`claude/mita-closed-beta-readiness-4nn5q6` → PR #273 `73c1817`): Security
  Scanning workflow fix (upload-sarif v3 + permissions), `scripts/remote_smoke_test.py` +
  `deployed-smoke.yml`, Android CI build fixed (Kotlin-DSL java shadowing; conditional
  google-services plugin), Firebase-less startup crash fixed. CI green end-to-end at run #227
  (pre-merge) / #229 (main), debug APK artifact built.
- **Session 5** (this branch): confirmed merge + green main; **found & fixed jinja2 clean-env
  boot crash** (`7cc0e12`); verified empty-env production boot + 19/19 smoke on prod
  requirements only; wrote `docs/RAILWAY_DEPLOYMENT.md`, `docs/ANDROID_RELEASE.md`,
  `docs/OFFLINE_BEHAVIOR.md`; updated this tracker.
