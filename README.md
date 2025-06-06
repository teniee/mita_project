
# 💸 MITA – Money Intelligence Task Assistant (Full Documentation)

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
              ├─> [ AI Assistant    ]
              └─> [ Drift Monitor   ]──> Firebase

[ PostgreSQL ] <── [ SQLAlchemy Models ]
```

- **Backend:** FastAPI
- **Database:** PostgreSQL (via SQLAlchemy)
- **OCR:** Google Cloud Vision
 - **AI Assistant:** chat endpoint backed by OpenAI
- **Tracking:** Firebase Firestore (optional)
- **Deployment:** Docker

---

## ⚙️ 3. Core Business Logic (Use Cases)

### 🔐 Auth & Users
- Register/login with JWT
- Store income, country, segment (low/mid/high), config flags

### 🧾 Expenses
- Add expense manually or via receipt (OCR)
- Store transaction (amount, date, category, description)

### 📅 Daily Budgeting
- Calculate budget per day/category
- Track spent vs planned per category
- Update `DailyPlan` after each transaction
- Set monthly spending goals per category and track progress
- Send email reminders for important events

### 🔁 Redistribution
- Redistribute remaining budget between categories
- Close gaps from overspending using surplus days
- Triggered manually or during planning phase

### 🙂 Mood Tracking
- Record user mood for each day via the `/mood` API
- Persist moods in the database for analytics

### 🧠 Assistant
- Suggest budget changes
- Warn about overspending trends
- Predict category overshoot (planned)

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

| Method | Path                                 | Description                                 |
|--------|--------------------------------------|---------------------------------------------|
| POST   | `/auth/login`                        | Login with email/password                   |
| POST   | `/auth/register`                     | Register new user                           |
| GET    | `/user/profile`                      | Get user data                               |
| POST   | `/onboarding/answers`                | Submit onboarding answers                   |
| POST   | `/transactions`                      | Add a new transaction                       |
| GET    | `/transactions/history`              | Get transaction history                     |
| GET    | `/calendar/day/{date}`               | Get daily plan by category                  |
| POST   | `/calendar/redistribute/{y}/{m}`     | Redistribute budget for the month           |
| POST   | `/category-goal/set`                | Set monthly goal for a spending category    |
| POST   | `/category-goal/progress`           | Get progress toward a category goal         |
| POST   | `/ocr/parse`                         | (Optional) Parse text from receipt image    |
| GET    | `/assistant/recommendation`          | (Future) Get financial suggestions          |

---

## 🔄 6. Internal Logic Flow

### Expense Added:
- ⏎ User submits amount/category
- 🔁 Transaction saved → linked to day
- 🔍 System finds `DailyPlan`:
  - if exists → updates `spent_amount`
  - else → creates one
- 📊 UI shows remaining budget for that day

### Redistribution:
- 🧠 Scans all `DailyPlan` entries in month
- 🔴 Detects overspending (`spent > planned`)
- 🟢 Pulls from surplus days
- Updates planned values to balance categories
- ⏰ Monthly cron job runs automatic redistribution

---

## 🧰 7. Module Descriptions

- `services/ocr_google.py` — integrates Google Cloud Vision
- `services/budget_redistributor.py` — logic for balancing budget
- `services/expense_tracker.py` — updates DailyPlan after transaction
- `orchestrator/receipt_orchestrator.py` — parses receipt → transaction
 - `agent_runner.py` — demo for using the assistant API
- `financial/routes.py` — assistant and analytics routes
- `drift_service.py` — Firebase connection and drift tracking
- `mood_store.py` — persists user mood entries in the database
- `category_goal_service.py` — manage monthly spending goals per category
- `email_service.py` — send email reminders via SMTP

---

## 🧪 8. Environment Variables

```
GOOGLE_CREDENTIALS_PATH=/path/to/ocr.json
FIREBASE_CONFIGURED=true
SECRET_KEY=supersecret  # replace this in production
DATABASE_URL=postgresql://user:pass@localhost:5432/mita
SMTP_HOST=localhost
SMTP_PORT=25
FROM_EMAIL=no-reply@example.com
OPENAI_API_KEY=test_key
OPENAI_MODEL=gpt-4o-mini
```

---

## 💻 9. Dev Setup

### Docker
The provided Dockerfile now uses a multi-stage build to keep the final image
small. Build and start the stack with:
```bash
docker-compose up --build
```

### Local (manual)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Install git hooks with [pre-commit](https://pre-commit.com/) to ensure code style:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🧠 10. Frontend Expectations

A proper Flutter or React frontend should include:

- ✅ Login/register
- ✅ Onboarding: income, categories
- ✅ Dashboard: daily budget left
- ✅ Calendar: per-day category breakdown
- ✅ Add expense (manual or photo)
- ✅ Button: redistribute budget
- ✅ View history
- 🧠 Assistant suggestions (optional)

---

## 🤖 11. Lovable Prompt

> Build a full budgeting assistant UI for: https://github.com/teniee/mita_docker_ready_project_manus_

Include:
- Auth
- Onboarding (income, categories)
- Budget calendar
- Add transaction
- Redistribute button
- Expense history
- Assistant recommendations

---

## 🛠 12. Roadmap

 - [x] Assistant dialog with contextual replies
- [x] Spending goals per category
- [x] Email reminders
- [x] Scheduled redistribution (monthly cron task)
- [ ] i18n support

## 🔧 13. Running Tests

To run the backend unit tests locally, first install all Python dependencies:

```bash
pip install -r requirements.txt
```

Then execute:

```bash
pytest -q
```

If dependencies such as `SQLAlchemy` or `pydantic_settings` are missing,
`pytest` will fail with `ModuleNotFoundError`. Installing from
`requirements.txt` ensures all packages are available.
