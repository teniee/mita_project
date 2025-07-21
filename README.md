
# 💸 MITA – Money Intelligence Task Assistant (Full Documentation)

MITA is an AI-powered personal finance backend platform designed to help users control their spending, plan budgets, and receive intelligent feedback using a daily calendar-based system. Built on **FastAPI**, this backend supports OCR receipt parsing, automatic budget redistribution, Firebase-based drift tracking, and more.

---

## 🔷 1. Overview

MITA distributes a user’s **monthly income** into **daily budgets per category** (e.g. food, rent, entertainment). As the user logs expenses, the system compares **planned vs spent**, detects overages, and **redistributes** funds automatically across categories.

---

## 🧱 2. System Architecture

```

\[ User App ] ─┬─> \[ Auth API         ]
├─> \[ Onboarding API   ]
├─> \[ Transactions API ]
├─> \[ Calendar API     ]──> DailyPlan
├─> \[ OCR Service      ]──> Receipt → Text → Expense
├─> \[ AI Analytics     ]
└─> \[ Drift Monitor    ]──> Firebase

\[ PostgreSQL ] <── \[ SQLAlchemy Models ]

````

| Layer      | Tech / Responsibility                              |
|------------|----------------------------------------------------|
| **Backend**| FastAPI, Pydantic, jwt-based auth                  |
| **DB**     | PostgreSQL (SQLAlchemy async engine)               |
| **OCR**    | Google Cloud Vision                                |
| **AI**     | GPT-based analytics, K-Means clustering            |
| **Tracking**| Firebase (optional drift metrics)                 |
| **Premium**| App- / Play-Store receipts, webhook handling       |
| **Deploy** | Docker, Alembic migrations, CI/CD pipeline         |

---

## ⚙️ 3. Core Business Logic (Use-Cases)

| Domain            | Key Flows                                                                                                      |
|-------------------|----------------------------------------------------------------------------------------------------------------|
| **Auth & Users**  | JWT login / refresh / logout, income + country stored, premium flag via subscription                           |
| **Expenses**      | Manual add or receipt photo → OCR → transaction                                                                |
| **Daily Budgeting**| Generate DailyPlan per day+category, update spent vs planned on each transaction                              |
| **Redistribution**| Scan month, detect overspend, pull from surplus days, write back new planned_amounts                           |
| **Mood / Habits** | `/mood` and `/habits` endpoints record qualitative factors for AI                                             |
| **AI Assistant**  | Periodic snapshot, GPT summaries, push tips, trend alerts                                                      |

---

## 🧬 4. Entities & Models

### User

```json
{
  "id": "UUID",
  "email": "user@example.com",
  "income": 60000,
  "country": "US",
  "class_segment": "mid",
  "config": { "income_check": true }
}
````

### Transaction

```json
{
  "amount": 1200,
  "category": "food",
  "date": "2025-05-10",
  "description": "groceries"
}
```

### DailyPlan

```json
{
  "date": "2025-05-10",
  "category": "food",
  "planned_amount": 300,
  "spent_amount": 220
}
```

---

## 📡 5. API Endpoints (selection)

| Method | Path                             | Description                   |
| ------ | -------------------------------- | ----------------------------- |
| POST   | `/api/auth/login`                | Login with email/password     |
| POST   | `/api/auth/register`             | Register new user             |
| GET    | `/user/profile`                  | Get user data                 |
| POST   | `/onboarding/answers`            | Submit onboarding answers     |
| POST   | `/transactions`                  | Add a new transaction         |
| GET    | `/transactions`                  | List transactions (paginated) |
| GET    | `/calendar/day/{date}`           | Get daily plan by category    |
| POST   | `/calendar/redistribute/{y}/{m}` | Redistribute month budget     |
| POST   | `/ocr/parse`                     | Parse receipt image           |
| GET    | `/ai/latest-snapshots`           | Latest AI analyses            |
| POST   | `/ai/snapshot`                   | Trigger new AI snapshot       |

*(see `docs/openapi.yaml` for full spec)*

---

## 🔄 6. Internal Logic Flow

### Expense Added

1. User submits amount / category.
2. Transaction saved → linked to `DailyPlan`.
3. `spent_amount` updated (or plan created).
4. UI reflects remaining budget.

### Redistribution

1. Iterate month’s `DailyPlan`.
2. Collect deficits (`spent > planned`).
3. Pull surplus from underspent days.
4. Write balanced `planned_amount` values.

---

## 🧰 7. Key Modules

| Path                                | Purpose                                 |
| ----------------------------------- | --------------------------------------- |
| `services/ocr_google.py`            | Google Vision integration               |
| `engine/budget_redistributor.py`    | Core redistribution algorithm           |
| `services/expense_tracker.py`       | Hooks to update DailyPlan on spend      |
| `orchestrator/receipt_orchestrator` | Receipt → OCR → Transaction pipeline    |
| `services/core/cohort/…`            | K-Means clustering, AI advice generator |
| `scripts/send_daily_ai_advice.py`   | Cron job: daily budget tips             |
| `scripts/refresh_premium_status.py` | Cron: deactivate expired subscriptions  |

---

## 🧪 8. Environment Variables

Copy `.env.example` to `.env` and adjust:

```bash
GOOGLE_CREDENTIALS_PATH=/path/to/ocr.json
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=change_me
SMTP_HOST=…
APPLE_SHARED_SECRET=…
GOOGLE_SERVICE_ACCOUNT=/path/to/google.json
ALLOWED_ORIGINS=https://app.mita.finance
SENTRY_DSN=
```

---

## 💻 9. Dev Setup

### Docker

```bash
docker-compose up --build
python scripts/run_migrations.py
```

### Manual venv

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/run_migrations.py
uvicorn app.main:app --reload
```

### Git Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🧠 10. Front-End Checklist

* Login / Register
* Onboarding wizard
* Daily dashboard & calendar
* Add transaction (manual / photo)
* Budget redistribution button
* History screen
* Assistant suggestions (premium)

---

## 🤖 11. Prompt for UI Team

> “Build a full budgeting analytics UI for:
> [https://github.com/teniee/mita\_docker\_ready\_project\_manus](https://github.com/teniee/mita_docker_ready_project_manus)
> Needs auth, onboarding, calendar, add TX, redistribute, history, AI tips, push/email reminders”

---

## 🛠 12. Roadmap

* [x] Assistant dialog
* [x] Spending goals
* [x] Email reminders

Future: budgeting rules engine, currency auto-detect, multi-wallet support.

---

## 📦 13. Automated Backups

```bash
python scripts/backup_database.py
```

Requires `S3_BUCKET`, AWS creds. Old backups (>7 days) auto-purged.

---

## 🔧 14. Running Tests

### Backend

```bash
pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing
```

### Mobile

```bash
flutter test --coverage
# coverage output → mobile_app/coverage/lcov.info
flutter test integration_test -d <deviceId>
```

> Integration tests aren’t run in CI (Chrome-only).

---

### CI Pipeline

* Install deps
* Lint (`black`, `isort`, `ruff`)
* Run tests + coverage ≥ 60 %
* Spin up Postgres → `alembic upgrade head`
* Build & push Docker on release tags

---

### Crash Reporting

* Firebase Crashlytics + optional Sentry (`SENTRY_DSN`)

---

### API Conventions

All FastAPI routes must return data via `success_response()` from
`app.utils.response_wrapper` for a consistent JSON envelope.

### Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for branching workflow, lint / coverage rules, and local testing instructions.

---

License: **Proprietary — All Rights Reserved**
© 2025 YAKOVLEV LTD (207808591)

