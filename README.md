💸 MITA – Money Intelligence Task Assistant (Full Documentation)

MITA is an AI-powered personal finance backend platform designed to help users control their spending, plan budgets, and receive intelligent feedback using a daily calendar-based system. Built on **FastAPI**, this backend supports OCR receipt parsing, automatic budget redistribution, Firebase-based drift tracking, and more.

---

## 🔷 1. Overview

MITA distributes a user’s **monthly income** into **daily budgets per category** (e.g. food, rent, entertainment). As the user logs expenses, the system compares **planned vs spent**, detects overages, and **redistributes** funds automatically across categories.

---

## 🧱 2. System Architecture

```
[ User App ] ─┬─> [ Auth API        ]
              ├─> [ Onboarding API  ]
              ├─> [ Transactions API]
              ├─> [ Calendar API    ]──> DailyPlan
              ├─> [ OCR Service     ]──> Receipt → Text → Expense
              ├─> [ AI Analytics   ]
              └─> [ Drift Monitor   ]──> Firebase

[ PostgreSQL ] <── [ SQLAlchemy Models ]
```

* **Backend:** FastAPI
* **Database:** PostgreSQL (via SQLAlchemy)
* **OCR:** Google Cloud Vision
* **AI Analytics:** analyzes mood, habits and spending to push budgeting recommendations
* **Tracking:** Firebase Firestore (optional)
* **Premium:** advanced insights API requires an active subscription
* **Deployment:** Docker

---

## ⚙️ 3. Core Business Logic (Use Cases)

### 🔐 Auth & Users

* Register/login with JWT
* Store income, country, segment (low/mid/high), config flags

### 🧾 Expenses

* Add expense manually or via receipt (OCR)
* Store transaction (amount, date, category, description)

### 📅 Daily Budgeting

* Calculate budget per day/category
* Track spent vs planned per category
* Update `DailyPlan` after each transaction

### 🔁 Redistribution

* Redistribute remaining budget between categories
* Close gaps from overspending using surplus days
* Triggered manually or during planning phase

### 🙂 Mood Tracking

* Record user mood for each day via the `/mood` API
* Persist moods in the database for analytics
* Manage personal habits via the `/habits` API

### 🧠 Assistant

* Suggest budget changes
* Warn about overspending trends
* Predict category overshoot (planned)

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
```

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

## 📡 5. API Endpoints

| Method | Path                                                             | Description                              |
| ------ | ---------------------------------------------------------------- | ---------------------------------------- |
| POST   | `/auth/login`                                                    | Login with email/password                |
| POST   | `/auth/register`                                                 | Register new user                        |
| GET    | `/user/profile`                                                  | Get user data                            |
| POST   | `/onboarding/answers`                                            | Submit onboarding answers                |
| POST   | `/transactions`                                                  | Add a new transaction                    |
| GET    | `/transactions`                                                  | List transactions (paginated)            |
|        | *Supports `skip`, `limit`, `start_date`, `end_date`, `category`* |                                          |
| GET    | `/calendar/day/{date}`                                           | Get daily plan by category               |
| POST   | `/calendar/redistribute/{y}/{m}`                                 | Redistribute budget for the month        |
| POST   | `/ocr/parse`                                                     | (Optional) Parse text from receipt image |
| GET    | `/ai/latest-snapshots`                                           | Get latest AI budget analyses            |
| POST   | `/ai/snapshot`                                                   | Generate AI analysis snapshot            |

---

## 🔄 6. Internal Logic Flow

### Expense Added:

* ⏎ User submits amount/category
* 🔁 Transaction saved → linked to day
* 🔍 System finds `DailyPlan`:

  * if exists → updates `spent_amount`
  * else → creates one
* 📊 UI shows remaining budget for that day

### Redistribution:

* 🧠 Scans all `DailyPlan` entries in month
* 🔴 Detects overspending (`spent > planned`)
* 🟢 Pulls from surplus days
* Updates planned values to balance categories

---

## 🧰 7. Module Descriptions

* `services/ocr_google.py` — integrates Google Cloud Vision
* `services/budget_redistributor.py` — logic for balancing budget
* `services/expense_tracker.py` — updates DailyPlan after transaction
* `orchestrator/receipt_orchestrator.py` — parses receipt → transaction
* `financial/routes.py` — AI analytics routes
* `drift_service.py` — Firebase connection and drift tracking
* `mood_store.py` — persists user mood entries in the database
* `scripts/send_daily_ai_advice.py` — cron entry for daily push tips
* `scripts/refresh_premium_status.py` — cron entry to disable expired subscriptions

---

## 🧪 8. Environment Variables

Copy `.env.example` to `.env` and adjust the values:

```bash
cp .env.example .env
```

Example:

```bash
GOOGLE_CREDENTIALS_PATH=/path/to/ocr.json
FIREBASE_CONFIGURED=true
SECRET_KEY=change_me
DATABASE_URL=postgresql://user:pass@localhost:5432/mita
SMTP_HOST=mail.example.com
SMTP_PORT=587
SMTP_USERNAME=mailer
SMTP_PASSWORD=secret
SMTP_FROM=notify@example.com
APPLE_SHARED_SECRET=changeme
GOOGLE_SERVICE_ACCOUNT=/path/to/google.json
ALLOWED_ORIGINS=https://app.mita.finance
JWT_PREVIOUS_SECRET=
SENTRY_DSN=
```

### Security Headers

Strict headers and HTTPS redirects are enabled by default. Use `ALLOWED_ORIGINS` to configure CORS.

---

## 💻 9. Dev Setup

### Docker

```bash
docker-compose up --build
```

### Manual (Local)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Git Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🧠 10. Frontend Expectations

* ✅ Login/register
* ✅ Onboarding: income, categories
* ✅ Dashboard: daily budget left
* ✅ Calendar: per-day category breakdown
* ✅ Add expense (manual or photo)
* ✅ Button: redistribute budget
* ✅ View history
* ✅ Responsive layout (tablet/desktop) via `LayoutBuilder`
* 🧠 Optional: assistant suggestions

---

## 🤖 11. Lovable Prompt

> Build a full budgeting analytics UI for: [https://github.com/teniee/mita\_docker\_ready\_project\_manus](https://github.com/teniee/mita_docker_ready_project_manus)\_

Include:

* Auth
* Onboarding
* Budget calendar
* Add transaction
* Redistribute button
* Expense history
* AI-driven budget tips
* Push notifications (FCM, APNs)
* Email reminders

---

## 🛠 12. Roadmap

* [x] Assistant dialog with contextual replies
* [x] Spending goals per category
* [x] Email reminders

---

## 📦 13. Automated Backups

Use:

```bash
python scripts/backup_database.py
```

Requires `S3_BUCKET` and AWS credentials. Automatically deletes backups older than 7 days.

---

## 🔧 14. Running Tests

### Backend

```bash
pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing
```

If you see `ModuleNotFoundError`, ensure all required packages are installed.

### Mobile App

```bash
flutter test --coverage
```
Coverage results will be written to `mobile_app/coverage/lcov.info`.

Integration tests live in `mobile_app/integration_test/` and require a connected Android or iOS device or emulator. Run them locally:

```bash
flutter test integration_test -d <deviceId>
```

> ⚠️ Integration tests are **not** run in CI (Chrome-only support).

### CI


The CI workflow installs dependencies and runs tests with coverage for both the
backend and Flutter app. Docker images are built and pushed on tagged releases
via the `Deploy Docker` workflow.


### Crash Reporting

* Firebase Crashlytics is integrated
* Errors from `runApp` and `PlatformDispatcher` are sent to Crashlytics and Sentry
* Set `SENTRY_DSN` to enable Sentry tracking


