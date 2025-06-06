MITA distributes a user’s **monthly income** into **daily budgets per category**.

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

...

| GET    | `/transactions/history`              | Get transaction history                     |
| GET    | `/calendar/day/{date}`               | Get daily plan by category                  |
| POST   | `/calendar/redistribute/{y}/{m}`     | Redistribute budget for the month           |
| POST   | `/category-goal/set`                 | Set monthly goal for a spending category    |
| POST   | `/category-goal/progress`            | Get progress toward a category goal         |
| POST   | `/ocr/parse`                         | (Optional) Parse text from receipt image    |
| GET    | `/assistant/recommendation`          | (Future) Get financial suggestions          |

...

- 🔴 Detects overspending (`spent > planned`)
- 🟢 Pulls from surplus days
- Updates planned values to balance categories
- ⏰ Monthly cron job runs automatic redistribution

---

- `agent_runner.py` — placeholder for AI logic
- `financial/routes.py` — assistant and analytics routes
- `drift_service.py` — Firebase connection and drift tracking
- `mood_store.py` — persists user mood entries in the database
- `category_goal_service.py` — manage monthly spending goals per category
- `email_service.py` — send email reminders via SMTP

...
