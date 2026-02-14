# MITA MVP Features Definition

## Overview

**MITA (Money Intelligence Task Assistant)** — AI-powered personal finance management app.
Platform: Mobile (iOS + Android via Flutter) + Backend API (FastAPI).

---

## Core MVP Features

### 1. Authentication & Onboarding
- Email/password registration and login (JWT tokens)
- Guided onboarding flow: income setup, expense categories, budget preferences, financial goals

### 2. Daily Category-Based Budgeting (Core Feature)
- Monthly income distributed across spending categories (food, transport, entertainment, etc.)
- Each category budget divided by days — user sees daily spending allowance
- **AI-powered redistribution**: if overspent in one category, remaining days' budgets auto-adjust
- Real-time budget status updates

### 3. Expense Tracking
- Manual expense entry (amount, category, description, date)
- **OCR receipt scanning** via camera — automatic amount and category recognition (Google Vision API)
- Transaction history with search and filters
- Bulk import/export support

### 4. Expense Calendar
- Monthly calendar view showing daily spend vs. budget
- Color-coded indicators (green = within budget, red = overspent)
- Day detail view with breakdown by category
- Historical comparison

### 5. Financial Goals
- Create savings goals (e.g., "iPhone in 3 months")
- Progress tracking with visual progress bar
- AI-powered recommendations for faster goal achievement
- Goal health scoring (0-100)

### 6. AI Assistant
- Chat-based financial assistant (GPT-4 integration)
- Personalized spending advice
- Weekly financial summaries and insights
- Spending pattern analysis
- Anomaly detection and alerts

### 7. Notifications
- Push notifications for budget limit warnings (Firebase Cloud Messaging)
- Daily expense logging reminders
- Goal milestone achievements
- Smart notification routing and preferences

### 8. Profile & Settings
- User profile management
- Currency and language settings
- Premium subscription tiers
- Data export (GDPR compliant)

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python / FastAPI |
| Database | PostgreSQL (Supabase) |
| Cache | Redis |
| Mobile | Flutter (Dart) — iOS + Android |
| AI | OpenAI GPT-4 API |
| OCR | Google Vision API |
| Push | Firebase Cloud Messaging |
| Hosting | Railway / Docker |
| CI/CD | GitHub Actions |
| Monitoring | Sentry + Prometheus + Grafana |

---

## Current Development Status

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | Ready | 120+ endpoints, 23 DB models, 100+ services |
| Mobile App | Ready | 47 screens, 80+ services, offline-first |
| AI Integration | Ready | GPT-4 insights, smart categorization |
| OCR Processing | Ready | Google Vision, 99.8% accuracy |
| DevOps | Ready | Docker, CI/CD, monitoring |
| QA Testing | Needs Work | ~35-40% coverage, needs 64h focused QA |

---

## What's Needed for Launch

1. **QA Testing & Bug Fixing** — comprehensive testing before release
2. **App Store / Google Play Publishing** — store listings, screenshots, review process
3. **Production Monitoring Setup** — alerting, incident runbooks
4. **AI Cost Optimization** — reduce per-user AI costs from $3-5 to <$2/month
5. **Beta Testing** — 100 users in 60 days for validation

---

## Business Model

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Basic budgeting, manual expense entry, 1 goal |
| Premium | $9.99/mo | AI insights, unlimited OCR, advanced analytics, unlimited goals |
| Enterprise | Custom | White-label, API access, SSO |

---

## Key Metrics (Target)

- 100+ beta users within 60 days
- 40%+ weekly retention rate
- NPS > 50
- $7K+ MRR within 12 months
