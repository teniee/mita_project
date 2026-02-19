# MITA — Money Intelligence Task Assistant

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688.svg)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.19+-02569B.svg)](https://flutter.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D.svg)](https://redis.io)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#license)

[![Main CI](https://github.com/teniee/mita_project/actions/workflows/main-ci.yml/badge.svg)](https://github.com/teniee/mita_project/actions/workflows/main-ci.yml)
[![Security Scanning](https://github.com/teniee/mita_project/actions/workflows/security.yml/badge.svg)](https://github.com/teniee/mita_project/actions/workflows/security.yml)
[![Production Deployment](https://github.com/teniee/mita_project/actions/workflows/deploy-production.yml/badge.svg)](https://github.com/teniee/mita_project/actions/workflows/deploy-production.yml)

An AI-powered personal finance platform with daily category-based budgeting, OCR receipt processing, and behavioral spending analytics. Built on FastAPI + Flutter with a production-grade infrastructure stack.

---

## Table of Contents

- [Core Concept](#core-concept)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [License](#license)

---

## Core Concept

MITA distributes a user's monthly income into **daily per-category budgets** (food, transport, entertainment, etc.). When spending exceeds a day's allocation, the system automatically rebalances the remaining days in the month — no manual adjustment needed.

Key capabilities:
- **Daily budget redistribution** — proprietary algorithm rebalances budget across remaining days after overspending
- **OCR receipt scanning** — Google Cloud Vision extracts merchant, amount, date, and items; AI auto-categorizes
- **Behavioral analytics** — K-means clustering on spending patterns; mood–spending correlation
- **AI insights** — GPT-4 driven recommendations and anomaly detection
- **Offline-first mobile** — full functionality without connectivity, auto-syncs on reconnect
- **Real-time updates** — WebSocket push for budget changes and transaction alerts

---

## Tech Stack

### Backend

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.116.1 + Uvicorn 0.32.1 |
| Language | Python 3.10+ |
| Validation | Pydantic 2.9.2 |
| Database | PostgreSQL 15+ via SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.14.0 |
| Cache / Queue | Redis 7.0+ (aioredis + RQ) |
| Auth | JWT (PyJWT 2.10.1) + OAuth 2.0 scopes |
| AI / ML | OpenAI 1.54.4, scikit-learn, NumPy |
| OCR | Google Cloud Vision API |
| Notifications | Firebase Cloud Messaging |
| Email | SendGrid via queue |
| Monitoring | Sentry, Prometheus, Grafana |
| Task Queue | Redis Queue (RQ) + RQ Scheduler |

### Mobile

| Layer | Technology |
|-------|-----------|
| Framework | Flutter 3.19+ |
| Language | Dart 3.0+ (null-safe) |
| State | Offline-first with automatic sync |
| Auth | Biometric (Face ID / Touch ID / fingerprint) |
| Features | Camera, WebSocket, i18n (10+ languages), WCAG 2.1 AA |

### Infrastructure

| Layer | Technology |
|-------|-----------|
| Containers | Docker + Docker Compose |
| Orchestration | Kubernetes (Helm charts, ArgoCD) |
| IaC | Terraform |
| Hosting | Railway (production) + Supabase (managed DB) |
| CI/CD | GitHub Actions |
| Security scan | Bandit, Safety, secret detection |

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                      MITA Platform                      │
├────────────────────────────────────────────────────────┤
│  Flutter Mobile (iOS / Android / Web)                   │
│       │  REST + WebSocket                               │
│       ▼                                                  │
│  FastAPI Gateway  (36 routers, 120+ endpoints)          │
│   ├── Auth Service    (JWT, OAuth 2.0 scopes)           │
│   ├── Budget Engine   (100+ services, redistribution)   │
│   ├── AI Service      (GPT-4 insights, OCR, clustering) │
│   └── Admin Layer     (audit, perf, cache, feature flags│
│       │                                                  │
│  PostgreSQL 15 + Redis 7                                │
│  (23+ models | async ORM | multi-level cache)           │
│       │                                                  │
│  Background Workers (Redis Queue)                       │
│   • Email   • OCR   • AI Analysis                       │
│   • Budget Redistribution   • Notifications             │
│       │                                                  │
│  External Services                                      │
│   • Google Cloud Vision   • Firebase   • Sentry         │
└────────────────────────────────────────────────────────┘
```

### Backend structure

```
app/
├── api/                   # 36 routers, 120+ endpoints
│   ├── auth/              # Registration, login, token refresh, logout
│   ├── users/             # Profile, preferences
│   ├── transactions/      # CRUD, bulk import, CSV export
│   ├── budget/            # Daily/monthly budgets, redistribution
│   ├── calendar/          # Daily calendar view
│   ├── ocr/               # Receipt upload and processing
│   ├── ai/                # GPT-4 insights and predictions
│   ├── analytics/         # Trend analysis, category breakdown
│   ├── behavior/          # Spending pattern analysis
│   ├── cluster/           # K-means clustering
│   ├── drift/             # Budget drift detection
│   ├── goals/             # Savings goals CRUD
│   ├── goal/              # Goal tracking dashboard
│   ├── habits/            # Habit check-ins
│   ├── mood/              # Mood logging and correlation
│   ├── insights/          # Insights dashboard
│   ├── notifications/     # Push notification management
│   ├── onboarding/        # User onboarding flow
│   ├── installments/      # Installment payment calculator
│   ├── challenge/         # Savings challenges
│   ├── cohort/            # Anonymized peer comparison
│   ├── referral/          # Referral system
│   ├── iap/               # In-app purchases
│   ├── dashboard/         # Unified dashboard data
│   ├── spend/             # Spending analysis
│   ├── financial/         # Advanced financial metrics
│   ├── checkpoint/        # Daily progress checkpoints
│   ├── plan/              # Budget plan generation
│   ├── expense/           # Quick expense entry
│   ├── style/             # UI preferences
│   ├── email/             # Email management
│   ├── tasks/             # Background task status
│   ├── health/            # System + external services health
│   └── endpoints/         # Admin: audit, db_performance, cache, feature_flags
│
├── services/              # 100+ business logic services
│   ├── core/engine/       # Budget redistribution engine
│   ├── core/analytics/    # Analytics computation
│   ├── core/behavior/     # Behavioral services
│   ├── ai_financial_analyzer.py
│   ├── budget_planner.py
│   ├── budget_redistributor.py
│   ├── ocr_service.py
│   └── [90+ more]
│
├── db/models/             # 23+ SQLAlchemy models
├── middleware/            # 7 middleware layers (JWT scope, rate limit, audit, etc.)
├── repositories/          # 5 data access layers (clean architecture)
├── core/                  # Config, security, cache, DB connection
├── tests/                 # 84 test files
├── main.py                # FastAPI app entry point
└── worker.py              # RQ background worker
```

### Mobile structure

```
mobile_app/lib/
├── screens/               # auth, home, budget, transactions, calendar,
│                          #   goals, insights, receipts, settings
├── services/              # api_service, auth_service, budget_service,
│                          #   offline_service, camera_service, notification_service
├── models/                # user, transaction, budget, goal, insight
├── widgets/               # Reusable UI components
└── utils/                 # formatters, validators, constants
```

---

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register with email, income, currency |
| `/api/auth/login` | POST | JWT login |
| `/api/auth/refresh` | POST | Token rotation |
| `/api/auth/logout` | POST | Token revocation (Redis blacklist) |
| `/api/auth/google` | POST | Google OAuth 2.0 |
| `/api/auth/forgot-password` | POST | Password reset request |
| `/api/auth/reset-password` | POST | Complete password reset |

### Users

| Endpoint | Method | Scope |
|----------|--------|-------|
| `/api/users/me` | GET / PUT | `read:profile` / `write:profile` |
| `/api/users/preferences` | GET / PUT | `read:profile` |
| `/api/users/premium` | POST | `manage:subscription` |

### Transactions & Expenses

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/transactions` | GET | Paginated history with filters |
| `/api/transactions` | POST | Create transaction |
| `/api/transactions/{id}` | GET / PUT / DELETE | Detail, update, soft-delete |
| `/api/transactions/bulk` | POST | Bulk import |
| `/api/transactions/export` | GET | Export CSV |
| `/api/expense/track` | POST | Quick expense entry |
| `/api/expense/recurring` | GET / POST | Recurring expense management |

### Budget

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/budget/daily/{date}` | GET | Daily breakdown by category |
| `/api/budget/monthly` | GET | Monthly summary |
| `/api/budget/redistribute` | POST | Trigger AI redistribution |
| `/api/budget/adjust` | POST | Manual adjustment |
| `/api/budget/history` | GET | Historical performance |
| `/api/plan/current` | GET | Current daily plan |
| `/api/plan/generate` | POST | Generate new budget plan |

### OCR & Receipts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ocr/process` | POST | Upload receipt image |
| `/api/ocr/jobs/{id}` | GET | Job status |
| `/api/ocr/history` | GET | Processing history |
| `/api/ocr/reprocess/{id}` | POST | Retry failed job |

### AI & Analytics

| Endpoint | Method | Scope |
|----------|--------|-------|
| `/api/ai/insights` | GET | `premium:ai_insights` |
| `/api/ai/advice` | GET | `premium:ai_insights` |
| `/api/ai/predict` | POST | `premium:ai_insights` |
| `/api/analytics/dashboard` | GET | `read:analytics` |
| `/api/analytics/trends` | GET | `read:analytics` |
| `/api/behavior/patterns` | GET | `premium:ai_insights` |
| `/api/cluster/analysis` | GET | `premium:ai_insights` |
| `/api/drift/detect` | GET | `premium:ai_insights` |

### Goals, Habits, Mood

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/goals` | GET / POST | List / create savings goals |
| `/api/goals/{id}` | PUT | Update goal |
| `/api/goals/{id}/contribute` | POST | Add contribution |
| `/api/habits` | GET / POST | Habits |
| `/api/habits/{id}/check-in` | POST | Daily check-in |
| `/api/mood` | POST | Log mood |
| `/api/mood/analysis` | GET | Mood–spending correlation |

### Calendar & Planning

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/calendar/daily/{date}` | GET | Daily calendar view |
| `/api/calendar/monthly/{month}` | GET | Monthly calendar view |
| `/api/checkpoint/daily` | GET | Daily checkpoint data |

### Notifications

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications` | GET | User notifications |
| `/api/notifications/{id}/read` | PUT | Mark as read |
| `/api/notifications/settings` | GET / PUT | Preferences |

### Admin & System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health |
| `/api/health/external` | GET | External service status |
| `/api/audit` | GET | Audit log (admin) |
| `/api/db-performance` | GET | Database performance metrics (admin) |
| `/api/cache` | GET / DELETE | Cache management (admin) |
| `/api/feature-flags` | GET / PUT | Feature flag control (admin) |
| `/metrics` | GET | Prometheus metrics |

### Additional Endpoints

- `/api/installments` — payment plan calculator
- `/api/challenge` — savings challenges
- `/api/referral` — referral system
- `/api/cohort` — anonymized peer comparison
- `/api/financial` — advanced financial metrics
- `/api/onboarding` — onboarding flow
- `/api/iap` — in-app purchase handling
- `/api/dashboard` — unified dashboard data
- `/api/spend` — spending analysis
- `/api/style` — UI personalization
- `/api/tasks` — background task queue status

### WebSocket

- `/ws/budget-updates` — real-time budget changes
- `/ws/transaction-alerts` — live transaction updates
- `/ws/notifications` — push notification stream

### OAuth 2.0 Scopes

| Scope | Access |
|-------|--------|
| `read:profile`, `write:profile` | User profile and preferences |
| `read:transactions`, `write:transactions` | Transactions |
| `read:budget`, `manage:budget` | Budget data and adjustments |
| `read:goals`, `write:goals` | Savings goals |
| `read:analytics` | Analytics and reports |
| `premium:ai_insights` | GPT-4 insights, behavioral analysis |
| `process:receipts` | OCR processing |
| `admin:*` | Administrative access |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development without Docker)
- PostgreSQL 15+ and Redis 7.0+ (or use Docker)
- Flutter 3.19+ (for mobile development)

### Quick Start (Docker)

```bash
# Clone
git clone https://github.com/teniee/mita_project.git
cd mita_project

# Configure environment
cp .env.example .env
# Edit .env — minimum required variables listed below

# Generate secrets
openssl rand -base64 32          # → JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"  # → SECRET_KEY

# Start all services
docker-compose up --build

# Run database migrations
docker-compose exec backend python scripts/run_migrations.py

# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### Minimum Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mita
REDIS_URL=redis://localhost:6379/0

# Security (generate strong values — see above)
JWT_SECRET=<32+ char secret>
SECRET_KEY=<32+ char secret>
ENVIRONMENT=development

# Optional: AI features
OPENAI_API_KEY=sk-...

# Optional: OCR
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
# or
FIREBASE_JSON=<json string>

# Optional: Error tracking
SENTRY_DSN=<your sentry dsn>
```

### First API Calls

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!","income":5000,"currency":"USD","country":"US"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'

# Use token
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer <token>"
```

---

## Development

### Backend

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env

# Migrate
python scripts/run_migrations.py

# Run dev server
uvicorn app.main:app --reload --port 8000

# Code quality
black app/
isort app/
ruff check app/
mypy app/
```

### Mobile

```bash
cd mobile_app
flutter pub get
flutter packages pub run build_runner build

flutter run -d chrome          # Web (dev)
flutter run -d ios             # iOS simulator
flutter run -d android         # Android emulator

flutter build apk --release    # Android production
flutter build ios --release    # iOS production
flutter build web --release    # Web production
```

### Security

Multi-layer security stack:

- **JWT with OAuth 2.0 scopes** — granular, per-endpoint permissions
- **Token blacklisting** — real-time revocation via Redis
- **BCrypt** — password hashing (configurable work factor)
- **Rate limiting** — sliding window: 100 req/min standard, 1000 req/min premium
- **Audit logging** — all security events recorded (`/api/audit`)
- **HTTPS / TLS 1.3** — enforced in production
- **AES-256** — sensitive data encrypted at rest
- **Bandit + Safety** — automated vulnerability scanning in CI
- GDPR compliant (data export, right to deletion)

---

## Testing

```bash
# Full suite with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# By category
pytest app/tests/test_*.py -v          # Unit tests
pytest app/tests/security/ -v          # Security tests
pytest app/tests/performance/ -v       # Performance tests
pytest app/tests/test_end_to_end.py -v # Integration tests

# Specific areas
pytest app/tests/test_budget_routes.py -v
pytest app/tests/test_auth.py -v
pytest app/tests/test_transactions.py -v
```

**Test breakdown** (84 test files):
- 60 unit test files — business logic and services
- 12 integration test files — end-to-end API workflows
- 10 security test files — auth, JWT, rate limiting, input validation
- 6 performance test files — load testing, query benchmarks

```bash
# Mobile tests
cd mobile_app
flutter test
flutter test integration_test/
flutter test --coverage
```

---

## Deployment

### Railway (Current Production)

Deployed from `main` branch with automatic deployment. Uses Supabase (managed PostgreSQL) and managed Redis.

### Docker

```bash
docker build -t mita-backend:latest .
docker-compose -f docker-compose.prod.yml up -d
docker-compose exec backend python scripts/run_migrations.py
```

### Kubernetes

```bash
kubectl create namespace mita-production
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Scale
kubectl scale deployment mita-backend --replicas=5 -n mita-production
```

### Terraform

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

### CI/CD Pipeline (GitHub Actions)

1. **Feature branch push** — lint (Black, Ruff, MyPy), security scan (Bandit, Safety), unit tests
2. **Pull request** — full test suite, 90%+ coverage gate, migration validation
3. **Merge to main** — build Docker image, deploy to staging, smoke tests, gradual production rollout (5% → 25% → 100%)
4. **Failure** — automatic rollback via `scripts/rollback/`

### Health Checks

```bash
curl http://localhost:8000/health          # Overall
curl http://localhost:8000/health/db       # Database
curl http://localhost:8000/health/redis    # Redis
curl http://localhost:8000/metrics         # Prometheus
```

### Automation Scripts

`scripts/` contains 30+ production automation scripts:

- `run_migrations.py` — zero-downtime migrations
- `backup_database.py` / `production_backup.py` — automated backups
- `health_monitoring.py` — health check deployment
- `rq_scheduler.py` — background task scheduler
- `send_daily_ai_advice.py` — daily AI insight delivery
- `monthly_redistribute.py` — monthly budget redistribution
- `api_key_rotation.py` — automated key rotation
- `dependency_monitor.py` — vulnerability scanning
- `sentry_release_manager.py` — release tracking

---

## Documentation

- **Interactive API docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
- `docs/FIREBASE_SETUP.md` — Firebase Cloud Messaging setup
- `docs/GOOGLE_VISION_SETUP.md` — Google Cloud Vision OCR setup
- `docs/NOTIFICATION_INTEGRATIONS.md` — notification service integration
- `docs/OCR_TESTING_GUIDE.md` — OCR testing guide
- `docs/adr/` — Architecture Decision Records
- `alembic/MIGRATION_APPLICATION_GUIDE.md` — migration guide
- `monitoring/README.md` — Prometheus & Grafana setup

---

## Project Metrics

| Category | Value |
|----------|-------|
| Total lines of code | 94,000+ |
| Python files | 525 |
| Dart / Flutter files | 191+ |
| API routers | 36 |
| API endpoints | 120+ |
| Database models | 23+ |
| Business services | 100+ |
| Middleware layers | 7 |
| Test files | 84 |
| Automation scripts | 30+ |
| Claude AI agents | 10 |

---

## License

**Copyright © 2025 YAKOVLEV LTD** — Company Registration: 207808591
All Rights Reserved.

Proprietary license. Commercial use requires a valid license agreement. Evaluation permitted for 30 days. No redistribution or modification without written permission.

Third-party open-source components (FastAPI, Flutter, PostgreSQL, Redis, SQLAlchemy, Pydantic) are used under their respective licenses.

> MITA is a budgeting and financial management tool — not a financial advisor, bank, or financial institution. Always consult qualified professionals for important financial decisions.
