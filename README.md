# MITA — Money Intelligence Task Assistant

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688.svg)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.19+-02569B.svg)](https://flutter.dev)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://postgresql.org)
[![Main CI](https://github.com/teniee/mita_project/actions/workflows/main-ci.yml/badge.svg)](https://github.com/teniee/mita_project/actions/workflows/main-ci.yml)
[![Security Scanning](https://github.com/teniee/mita_project/actions/workflows/security.yml/badge.svg)](https://github.com/teniee/mita_project/actions/workflows/security.yml)

> **AI-powered daily budgeting for people who earn monthly but spend daily.**
> Full-stack product — FastAPI backend · Flutter mobile (iOS/Android) · production infrastructure.

---

## The Problem

Most people get paid monthly. Every budgeting app in the market thinks in months too.
But nobody buys groceries "monthly" — people spend money every single day, in dozens of small decisions.

The result: you check your balance on the 20th of the month, it's low, and you have no idea why.
Classic tools (Mint, YNAB, etc.) show you what happened. They don't prevent it.

---

## What MITA Does Differently

MITA converts your monthly income into **daily per-category budgets** — food, transport, entertainment, etc. — and keeps them alive throughout the month automatically.

**The core mechanic:**
1. User sets monthly income and spending preferences during onboarding
2. MITA generates a daily budget for each category
3. User logs spending (manual entry or receipt scan)
4. If a day is overspent in a category, the algorithm automatically redistributes the shortfall across remaining days
5. The user always sees a simple answer: *"Can I spend money today, and on what?"*

No manual rebalancing. No guilt-scrolling through charts. One clear daily signal.

---

## Product Status

This is a **working, production-grade codebase** — not a prototype.

| Area | Status |
|------|--------|
| Backend API | Production on Railway, 120+ endpoints |
| Mobile app | Flutter (iOS + Android), offline-first |
| AI features | GPT-4 insights, OCR receipt scanning |
| Infrastructure | K8s Helm charts, Terraform IaC, ArgoCD GitOps |
| CI/CD | GitHub Actions with security scanning |
| Tests | 84 test files (unit, integration, security, perf) |
| Database | PostgreSQL 15, 23 models, 20 migrations |

**What's not done yet:** user acquisition, App Store / Play Store launch, growth loops, monetization validation, and a co-founder.

---

## Business Model

**Freemium subscription:**

- **Free**: daily budget tracking, manual transactions, basic analytics
- **Premium (~$9.99/mo)**: GPT-4 spending insights, receipt OCR, behavioral pattern detection, budget drift alerts, savings challenges, peer cohort comparison

The AI features are genuinely differentiated — not a thin wrapper. The behavioral engine runs K-means clustering on spending patterns and correlates them with mood logs. The OCR pipeline uses Google Cloud Vision + category inference. These are real moats, not marketing copy.

**Adjacent revenue:** in-app purchases (IAP) scaffolding is already built. Referral system is live.

---

## Tech Stack — TL;DR for Engineers

```
Flutter mobile (iOS / Android / Web)
        │  REST + WebSocket
        ▼
FastAPI (Python 3.10) — 37 routers, 120+ endpoints
   ├── Auth:         JWT + OAuth 2.0 scopes, token blacklisting via Redis
   ├── Budget:       redistribution engine, daily planner, drift detection
   ├── AI/ML:        GPT-4 (OpenAI), scikit-learn K-means, spaCy, transformers
   ├── OCR:          Google Cloud Vision → categorization pipeline
   ├── Notifications: Firebase FCM + SendGrid via Redis Queue
   └── Admin:        feature flags, audit log, cache management, Prometheus metrics
        │
PostgreSQL 15 (async SQLAlchemy 2.0) + Redis 7
        │
Background workers (RQ) — email, OCR jobs, AI analysis, scheduled redistribution
        │
External: OpenAI · Google Cloud Vision · Firebase · Sentry · AWS S3
```

**Infrastructure:** Docker → Kubernetes (Helm, ArgoCD) → Terraform. Currently deployed on Railway + Supabase + Upstash.

---

## Repository Map

```
mita_project/
├── app/                    # Backend — FastAPI application
│   ├── api/                # 37 routers (auth, budget, transactions, OCR, AI, admin…)
│   ├── services/           # 100+ business logic services
│   ├── engine/             # 10 specialized engines (budget, analytics, behavior, OCR…)
│   ├── db/models/          # 23 SQLAlchemy models
│   ├── middleware/         # 7 layers: CORS, rate limiting, audit, JWT scope, perf logging
│   ├── repositories/       # Data access layer (clean architecture)
│   ├── core/               # Config, security, cache, DB connection pool
│   ├── tests/              # 84 test files
│   ├── main.py             # App entry point (1034 LOC)
│   └── worker.py           # RQ background worker
│
├── mobile_app/             # Flutter — iOS / Android / Web
│   └── lib/
│       ├── screens/        # auth, home, budget, transactions, calendar, goals, receipts…
│       ├── services/       # api, auth, budget, offline sync, camera, notifications
│       ├── models/         # user, transaction, budget, goal, insight
│       └── l10n/           # i18n — 10+ languages
│
├── infrastructure/         # Helm charts, ArgoCD, Lambda, Terraform
├── k8s/                    # 43 Kubernetes manifests + full monitoring stack
│   └── monitoring/         # Prometheus, Grafana dashboards, ELK, alert rules
├── scripts/                # 30+ automation scripts (migrations, backups, rollback, jobs)
├── alembic/                # 20 database migrations
├── docs/                   # Architecture diagrams, ADRs, setup guides
└── .github/workflows/      # CI (lint, test, security scan) + CD (deploy, rollback)
```

---

## Key Technical Decisions (and Why)

**FastAPI over Django/Flask** — async-first for concurrent WebSocket + background worker load. Auto-generated OpenAPI docs are a product feature for mobile dev speed.

**Flutter over React Native** — true cross-platform with a single Dart codebase. Offline-first SQLite sync was simpler to implement. Biometric auth and camera feel native.

**Redis Queue over Celery** — lower ops complexity for current scale. OCR and AI jobs are async, fire-and-forget. Scheduler handles daily redistribution cron.

**Supabase + Upstash on Railway** — zero-ops managed infra for current stage. Full K8s path is ready when needed (Helm charts exist and are tested).

**Proprietary redistribution algorithm** — the daily budget rebalance is the core IP. It accounts for category minimums, spending velocity, and remaining days. Not an off-the-shelf formula.

---

## Running It Locally

**Prerequisites:** Docker & Docker Compose

```bash
git clone https://github.com/teniee/mita_project.git
cd mita_project

cp .env.example .env
# Fill in: DATABASE_URL, REDIS_URL, JWT_SECRET, SECRET_KEY
# Optional for AI features: OPENAI_API_KEY, GOOGLE_APPLICATION_CREDENTIALS

docker-compose up --build
docker-compose exec backend python scripts/run_migrations.py

# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

Minimum env for local dev (no external APIs needed):
```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mita
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<run: openssl rand -base64 32>
SECRET_KEY=<run: openssl rand -base64 32>
ENVIRONMENT=development
```

---

## Test Suite

```bash
# Backend
pytest --cov=app --cov-report=term-missing     # Full suite with coverage
pytest app/tests/security/ -v                   # Security tests
pytest app/tests/performance/ -v                # Performance / benchmark tests

# Mobile
cd mobile_app && flutter test
```

84 test files: 60 unit · 12 integration · 10 security · 6 performance.
CI enforces 90%+ coverage gate on PRs.

---

## What a Co-Founder Would Step Into

The technical foundation is largely done. The hard work remaining is:

- **Distribution** — App Store / Play Store submission, growth loops, referral activation
- **Product** — User research, onboarding conversion, feature prioritization
- **AI product depth** — the ML pipeline is scaffolded; there's real room to build something novel on top of the behavioral data
- **Monetization** — premium conversion experiments, pricing, B2B angle (salary advance apps, neobanks licensing the engine)

The codebase is built to scale — K8s, HPA, connection pooling, circuit breakers are all in place. The current constraint is not engineering capacity, it's GTM.

---

## Security & Compliance

- JWT + OAuth 2.0 scopes (per-endpoint granular permissions)
- Token blacklisting via Redis (real-time revocation)
- Rate limiting: sliding window, 100 req/min free / 1000 req/min premium
- AES-256 encryption for sensitive fields at rest
- GDPR: data export, soft-delete, right to erasure
- Automated scanning: Bandit (SAST), Safety (deps), secret detection in CI
- Audit log on all security events (`/api/audit`)

---

## Project Metrics

| | |
|---|---|
| Lines of code | 94,000+ |
| Python files | 525 |
| Flutter/Dart files | 191+ |
| API endpoints | 120+ |
| Database models | 23 |
| Business services | 100+ |
| Automation scripts | 30+ |
| DB migrations | 20 |

---

## Links

- **API Docs (live):** http://localhost:8000/docs *(or production URL after deploy)*
- **Architecture diagrams:** `docs/ARCHITECTURE_DIAGRAMS.md`
- **Architecture decisions:** `docs/adr/`
- **Monitoring setup:** `monitoring/README.md`
- **Infrastructure:** `terraform/README.md`

---

## License

**Copyright © 2025 YAKOVLEV LTD** (Company Reg: 207808591) — All Rights Reserved.
Proprietary. Evaluation permitted for 30 days. No redistribution or modification without written permission.

> MITA is a budgeting tool, not a financial advisor or regulated financial institution.
