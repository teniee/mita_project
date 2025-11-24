# MITA Platform - Architecture Diagrams & Visual Documentation

**Report Date:** 2025-11-16
**Version:** 1.0.0

---

## 1. SYSTEM OVERVIEW

### 1.1 High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                        MITA PLATFORM ECOSYSTEM                                 │
│                     (Money Intelligence Task Assistant)                        │
└────────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼────────┐            ┌───────▼────────┐           ┌───────▼────────┐
│   Mobile App   │            │  Backend API   │           │  Admin Portal  │
│   Flutter      │◄──────────►│   FastAPI      │◄─────────►│     Web        │
│   iOS/Android  │   HTTPS    │   Python 3.10  │   HTTPS   │    React       │
│                │            │                 │           │                │
└────────────────┘            └─────────────────┘           └────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼────────┐            ┌───────▼────────┐           ┌───────▼────────┐
│  PostgreSQL    │            │     Redis      │           │   Firebase     │
│    15+         │            │     7.0+       │           │   Admin SDK    │
│  Primary DB    │            │ Cache + Queue  │           │  Push + Auth   │
└────────────────┘            └────────────────┘           └────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼────────┐            ┌───────▼────────┐           ┌───────▼────────┐
│  Google Cloud  │            │     OpenAI     │           │     Sentry     │
│    Vision      │            │     GPT-4      │           │     Error      │
│   OCR + AI     │            │   Insights     │           │   Tracking     │
└────────────────┘            └────────────────┘           └────────────────┘
```

---

## 2. BACKEND ARCHITECTURE

### 2.1 FastAPI Application Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│                         (app/main.py)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
┌───▼───────┐     ┌────────▼─────────┐    ┌──────▼──────┐
│Middleware │     │   API Routers    │    │  Services   │
│  Stack    │────►│   (38 modules)   │───►│   Layer     │
└───────────┘     └──────────────────┘    └──────┬──────┘
    │                                             │
    │             ┌───────────────────────────────┘
    │             │
┌───▼─────────────▼─────────────────────┐
│         Core Infrastructure            │
│                                        │
│  - Security (JWT, Rate Limit, CORS)   │
│  - Error Handling (Standardized)      │
│  - Database (SQLAlchemy Async)        │
│  - Caching (Redis)                    │
│  - Monitoring (Sentry, Prometheus)    │
│  - Task Queue (RQ)                    │
└────────────────────────────────────────┘
```

### 2.2 Middleware Stack (Execution Order)

```
Request Flow →

1. ┌────────────────────────────────┐
   │ StandardizedErrorMiddleware    │ ← Catch all exceptions
   └───────────────┬────────────────┘
                   ▼
2. ┌────────────────────────────────┐
   │ ResponseValidationMiddleware   │ ← Validate response format
   └───────────────┬────────────────┘
                   ▼
3. ┌────────────────────────────────┐
   │ RequestContextMiddleware       │ ← Add trace_id, context
   └───────────────┬────────────────┘
                   ▼
4. ┌────────────────────────────────┐
   │ HTTPSRedirectMiddleware        │ ← Force HTTPS
   └───────────────┬────────────────┘
                   ▼
5. ┌────────────────────────────────┐
   │ CORSMiddleware                 │ ← Handle CORS
   └───────────────┬────────────────┘
                   ▼
6. ┌────────────────────────────────┐
   │ Performance Logging            │ ← Log slow requests
   └───────────────┬────────────────┘
                   ▼
7. ┌────────────────────────────────┐
   │ Optimized Audit Logging        │ ← Security audit trail
   └───────────────┬────────────────┘
                   ▼
8. ┌────────────────────────────────┐
   │ Security Headers               │ ← Add HSTS, CSP, etc.
   └───────────────┬────────────────┘
                   ▼
   ┌────────────────────────────────┐
   │        Route Handler           │
   └────────────────────────────────┘
```

### 2.3 API Router Hierarchy

```
FastAPI App (/api)
│
├── /auth (Authentication - 9 sub-modules)
│   ├── /register
│   ├── /login
│   ├── /refresh
│   ├── /logout
│   ├── /forgot-password
│   ├── /reset-password
│   ├── /change-password
│   ├── /google
│   └── /security-status
│
├── /users (User Management)
│   ├── /profile
│   ├── /preferences
│   └── /settings
│
├── /transactions (Transaction CRUD)
│   ├── GET /
│   ├── POST /
│   ├── GET /{id}
│   ├── PUT /{id}
│   └── DELETE /{id}
│
├── /budget (Budget Management)
│   ├── /daily/{date}
│   ├── /redistribute
│   ├── /calendar/{month}
│   └── /forecast
│
├── /analytics (Analytics & Insights)
│   ├── /dashboard
│   ├── /trends
│   ├── /category-breakdown
│   └── /health-score
│
├── /ai (AI Insights)
│   ├── /insights
│   └── /analyze-spending
│
├── /ocr (Receipt Processing)
│   ├── /process
│   └── /jobs/{id}
│
├── /goals (Savings Goals)
│   ├── GET /
│   ├── POST /
│   └── POST /{id}/contribute
│
├── /challenge (Gamification)
│   ├── /available
│   ├── /{id}/join
│   └── /leaderboard
│
└── ... (29 more modules)
```

---

## 3. DATA LAYER ARCHITECTURE

### 3.1 Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Database Schema                             │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│    Users     │        │ Transactions │        │     Goals    │
├──────────────┤        ├──────────────┤        ├──────────────┤
│ id (PK)      │◄───────┤ user_id (FK) │        │ id (PK)      │
│ email        │        │ goal_id (FK) ├───────►│ user_id (FK) │
│ password_hash│        │ category     │        │ name         │
│ country      │        │ amount       │        │ target_amount│
│ is_premium   │        │ merchant     │        │ deadline     │
│ token_version│        │ receipt_url  │        └──────────────┘
└──────┬───────┘        │ spent_at     │
       │                └──────────────┘
       │                        │
       │                ┌───────▼──────┐        ┌──────────────┐
       │                │ Daily Plans  │        │  OCR Jobs    │
       │                ├──────────────┤        ├──────────────┤
       └───────────────►│ user_id (FK) │        │ id (PK)      │
                        │ date         │        │ user_id (FK) │
                        │ category     │        │ image_url    │
                        │ planned_amt  │        │ status       │
                        │ spent_amt    │        │ extracted_   │
                        │ status       │        │   data       │
                        └──────────────┘        └──────────────┘

┌──────────────┐        ┌──────────────┐
│  Challenges  │        │ Installments │
├──────────────┤        ├──────────────┤
│ id (PK)      │        │ id (PK)      │
│ name         │        │ user_id (FK) │
│ type         │        │ total_amount │
│ target_metric│        │ paid_amount  │
└──────────────┘        └──────────────┘
       │
       └───────┐
               ▼
┌──────────────────────┐
│ Challenge_           │
│ Participations       │
├──────────────────────┤
│ id (PK)              │
│ user_id (FK)         │
│ challenge_id (FK)    │
│ progress             │
│ status               │
└──────────────────────┘
```

### 3.2 Repository Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                           │
└─────────────────────────────────────────────────────────────┘

API Router
    │
    ▼
┌──────────────┐
│  Service     │ ← Business Logic
│   Layer      │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│         Repository Layer                 │
│                                          │
│  ┌────────────────────────────────┐     │
│  │   Base Repository              │     │
│  │   (CRUD operations)            │     │
│  └─────────────┬──────────────────┘     │
│                │                         │
│    ┌───────────┼───────────┐            │
│    │           │           │            │
│  ┌─▼───┐   ┌──▼───┐   ┌───▼──┐         │
│  │User │   │Trans │   │Goal  │         │
│  │Repo │   │Repo  │   │Repo  │         │
│  └──┬──┘   └───┬──┘   └───┬──┘         │
│     │          │          │             │
└─────┼──────────┼──────────┼─────────────┘
      │          │          │
      ▼          ▼          ▼
┌──────────────────────────────────┐
│      SQLAlchemy 2.0 (Async)      │
└──────────────┬───────────────────┘
               ▼
        ┌──────────────┐
        │ PostgreSQL   │
        │    15+       │
        └──────────────┘
```

---

## 4. AUTHENTICATION FLOW

### 4.1 User Registration Flow

```
Mobile App                Backend API              Database           External
    │                          │                       │                │
    │  1. POST /api/auth/      │                       │                │
    │     register             │                       │                │
    ├─────────────────────────►│                       │                │
    │  {email, password}       │                       │                │
    │                          │  2. Validate input    │                │
    │                          │     (Pydantic)        │                │
    │                          │                       │                │
    │                          │  3. Hash password     │                │
    │                          │     (bcrypt)          │                │
    │                          │                       │                │
    │                          │  4. Create user       │                │
    │                          ├──────────────────────►│                │
    │                          │                       │                │
    │                          │◄──────────────────────┤                │
    │                          │  5. User created      │                │
    │                          │                       │                │
    │                          │  6. Generate JWT      │                │
    │                          │     (access + refresh)│                │
    │                          │                       │                │
    │                          │  7. Store refresh     │                │
    │                          │     in Redis          │                │
    │                          ├──────────────────────────────────────►│
    │                          │                       │         Redis  │
    │  8. Return tokens        │◄──────────────────────────────────────┤
    │◄─────────────────────────┤                       │                │
    │  {access_token,          │                       │                │
    │   refresh_token}         │                       │                │
    │                          │                       │                │
    │  9. Store tokens         │                       │                │
    │     (secure storage)     │                       │                │
    │                          │                       │                │
```

### 4.2 JWT Token Structure

```
┌─────────────────────────────────────────────────────────┐
│                    JWT Access Token                      │
├─────────────────────────────────────────────────────────┤
│ Header:                                                  │
│   {                                                      │
│     "alg": "HS256",                                     │
│     "typ": "JWT"                                        │
│   }                                                      │
├─────────────────────────────────────────────────────────┤
│ Payload:                                                 │
│   {                                                      │
│     "user_id": "550e8400-e29b-41d4-a716-446655440000", │
│     "email": "user@example.com",                        │
│     "scopes": [                                         │
│       "read:transactions",                              │
│       "write:transactions",                             │
│       "read:budget",                                    │
│       "manage:budget"                                   │
│     ],                                                   │
│     "token_type": "access_token",                       │
│     "exp": 1700000000,  // 2 hours from issue          │
│     "iat": 1699993200,                                  │
│     "jti": "unique-token-id",                           │
│     "version": 1        // For revocation               │
│   }                                                      │
├─────────────────────────────────────────────────────────┤
│ Signature:                                               │
│   HMACSHA256(                                           │
│     base64UrlEncode(header) + "." +                    │
│     base64UrlEncode(payload),                          │
│     JWT_SECRET                                          │
│   )                                                      │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Authenticated Request Flow

```
Mobile App              Middleware                Route Handler        Database
    │                       │                           │                 │
    │  1. GET /api/        │                           │                 │
    │     transactions     │                           │                 │
    │  Authorization:      │                           │                 │
    │  Bearer <token>      │                           │                 │
    ├─────────────────────►│                           │                 │
    │                      │  2. Extract token         │                 │
    │                      │     from header           │                 │
    │                      │                           │                 │
    │                      │  3. Verify JWT            │                 │
    │                      │     signature             │                 │
    │                      │                           │                 │
    │                      │  4. Check expiration      │                 │
    │                      │                           │                 │
    │                      │  5. Validate version      │                 │
    │                      │     (check blacklist)     │                 │
    │                      │                           │                 │
    │                      │  6. Extract user_id       │                 │
    │                      ├──────────────────────────►│                 │
    │                      │  user context             │                 │
    │                      │                           │  7. Query DB    │
    │                      │                           ├────────────────►│
    │                      │                           │                 │
    │                      │                           │◄────────────────┤
    │                      │                           │  8. Results     │
    │◄────────────────────────────────────────────────┤                 │
    │  9. JSON response    │                           │                 │
    │                      │                           │                 │
```

---

## 5. BUDGET MANAGEMENT ARCHITECTURE

### 5.1 Calendar-Based Budgeting System

```
┌─────────────────────────────────────────────────────────────────┐
│                  Calendar Budget Engine                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Step 1: Monthly Income Distribution                         │
└──────────────────────────────────────────────────────────────┘
Monthly Income: $3,000
      │
      ▼
┌────────────────────────────────────────────────────────────┐
│  Category Allocation (50/30/20 Rule)                       │
│                                                             │
│  Needs (50%):      $1,500                                  │
│  Wants (30%):      $900                                    │
│  Savings (20%):    $600                                    │
└────────────────────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────┐
│  Step 2: Daily Distribution                                │
│                                                             │
│  Days in Month: 30                                         │
│                                                             │
│  Daily Budget per Category:                                │
│    - Groceries:      $50/day                              │
│    - Transport:      $20/day                              │
│    - Entertainment:  $30/day                              │
│    - Restaurants:    $25/day                              │
│    - etc.                                                  │
└────────────────────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────┐
│  Step 3: Real-time Tracking                                │
│                                                             │
│  Nov 16, 2025:                                             │
│    Groceries:   Spent $45 / Budget $50  ✓ Green          │
│    Transport:   Spent $18 / Budget $20  ✓ Green          │
│    Dining:      Spent $35 / Budget $25  ⚠ Red            │
└────────────────────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────┐
│  Step 4: Auto-Redistribution                               │
│                                                             │
│  Trigger: Overspend detected in "Dining"                   │
│                                                             │
│  Algorithm:                                                 │
│  1. Calculate surplus in other categories                  │
│  2. Identify priority categories                           │
│  3. Reallocate funds from low-priority to overspent       │
│  4. Update daily plans for remaining days                  │
└────────────────────────────────────────────────────────────┘
```

### 5.2 Budget Redistribution Algorithm

```
Input: User ID, Overspent Category, Amount

Step 1: Calculate Current State
    ┌─────────────────────────────────────┐
    │  For each category:                 │
    │    - Total budgeted this month      │
    │    - Total spent so far             │
    │    - Remaining budget               │
    │    - Days left in month             │
    └─────────────────────────────────────┘
              │
              ▼
Step 2: Identify Surplus Categories
    ┌─────────────────────────────────────┐
    │  Categories with:                   │
    │    remaining_budget > 0             │
    │    AND low_priority                 │
    │    AND not essential                │
    └─────────────────────────────────────┘
              │
              ▼
Step 3: Calculate Redistribution
    ┌─────────────────────────────────────┐
    │  For each surplus category:         │
    │    available = min(                 │
    │      surplus * 0.5,  // Max 50%    │
    │      needed_amount                  │
    │    )                                │
    └─────────────────────────────────────┘
              │
              ▼
Step 4: Update Daily Plans
    ┌─────────────────────────────────────┐
    │  For remaining days:                │
    │    new_daily_budget =               │
    │      (remaining_budget -            │
    │       redistributed_amount) /       │
    │      days_left                      │
    └─────────────────────────────────────┘
              │
              ▼
Step 5: Notify User
    ┌─────────────────────────────────────┐
    │  "Budget adjusted:                  │
    │   Dining +$10                       │
    │   Entertainment -$10"               │
    └─────────────────────────────────────┘
```

---

## 6. OCR RECEIPT PROCESSING PIPELINE

### 6.1 Complete OCR Flow

```
Mobile App          Backend API         OCR Service        AI Service         Database
    │                    │                   │                  │                │
    │  1. Capture       │                   │                  │                │
    │     receipt       │                   │                  │                │
    │     photo         │                   │                  │                │
    │                   │                   │                  │                │
    │  2. Upload        │                   │                  │                │
    │     image         │                   │                  │                │
    ├──────────────────►│                   │                  │                │
    │  POST /ocr/       │  3. Create OCR    │                  │                │
    │  process          │     job           │                  │                │
    │                   ├──────────────────────────────────────────────────────►│
    │                   │                   │                  │    Store job   │
    │  4. Job ID        │                   │                  │                │
    │◄──────────────────┤                   │                  │                │
    │  {job_id: xxx}    │                   │                  │                │
    │                   │                   │                  │                │
    │                   │  5. Queue task    │                  │                │
    │                   ├──────────────────►│                  │                │
    │                   │    (async)        │                  │                │
    │                   │                   │  6. Extract text │                │
    │                   │                   │     (Google      │                │
    │                   │                   │      Vision)     │                │
    │                   │                   │                  │                │
    │                   │                   │  7. Parse data:  │                │
    │                   │                   │     - Merchant   │                │
    │                   │                   │     - Amount     │                │
    │                   │                   │     - Date       │                │
    │                   │                   │     - Items      │                │
    │                   │                   │                  │                │
    │                   │                   │  8. Categorize   │                │
    │                   │                   ├─────────────────►│                │
    │                   │                   │  Receipt data    │                │
    │                   │                   │                  │  9. AI          │
    │                   │                   │                  │     categorize  │
    │                   │                   │                  │     (keywords + │
    │                   │                   │                  │      ML)        │
    │                   │                   │◄─────────────────┤                │
    │                   │                   │  Category        │                │
    │                   │  10. Create       │                  │                │
    │                   │      transaction  │                  │                │
    │                   ├──────────────────────────────────────────────────────►│
    │                   │                   │                  │    Insert txn  │
    │                   │                   │                  │                │
    │                   │  11. Update       │                  │                │
    │                   │      budget       │                  │                │
    │                   ├──────────────────────────────────────────────────────►│
    │                   │                   │                  │  Update daily  │
    │                   │                   │                  │    plan        │
    │  12. Poll status  │                   │                  │                │
    ├──────────────────►│                   │                  │                │
    │  GET /ocr/jobs/   │                   │                  │                │
    │  {job_id}         │                   │                  │                │
    │                   │  13. Return       │                  │                │
    │                   │      results      │                  │                │
    │◄──────────────────┤                   │                  │                │
    │  {status: done,   │                   │                  │                │
    │   transaction_id} │                   │                  │                │
    │                   │                   │                  │                │
```

### 6.2 Receipt Data Structure

```
┌────────────────────────────────────────────────────────┐
│              Extracted Receipt Data                     │
├────────────────────────────────────────────────────────┤
│  {                                                      │
│    "ocr_raw_text": "KAUFLAND\n...",                   │
│    "merchant": "KAUFLAND",                            │
│    "merchant_normalized": "kaufland",                 │
│    "amount": 45.99,                                   │
│    "currency": "BGN",                                 │
│    "date": "2025-11-16",                             │
│    "time": "14:32",                                   │
│    "items": [                                         │
│      {                                                │
│        "name": "Milk",                               │
│        "quantity": 2,                                │
│        "unit_price": 3.50,                          │
│        "total": 7.00                                │
│      },                                              │
│      {                                                │
│        "name": "Bread",                              │
│        "quantity": 1,                                │
│        "unit_price": 2.30,                          │
│        "total": 2.30                                │
│      }                                               │
│    ],                                                 │
│    "category": "groceries",                          │
│    "category_confidence": 0.95,                      │
│    "location": "Sofia, Bulgaria",                    │
│    "receipt_url": "s3://receipts/xxx.jpg",          │
│    "processing_time_ms": 1234                        │
│  }                                                     │
└────────────────────────────────────────────────────────┘
```

---

## 7. AI/ML ARCHITECTURE

### 7.1 AI Services Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI/ML Services Layer                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  GPT-4 Agent     │      │ Categorization   │      │ Behavioral       │
│  Service         │      │ Engine           │      │ Analytics        │
├──────────────────┤      ├──────────────────┤      ├──────────────────┤
│ - Financial      │      │ - Keyword-based  │      │ - K-means        │
│   insights       │      │ - ML-enhanced    │      │   clustering     │
│ - Budget advice  │      │ - Multi-language │      │ - Pattern        │
│ - Spending       │      │ - Confidence     │      │   extraction     │
│   analysis       │      │   scoring        │      │ - Drift          │
│                  │      │                  │      │   detection      │
└──────────────────┘      └──────────────────┘      └──────────────────┘
        │                          │                         │
        └──────────────┬───────────┴────────────────────────┘
                       │
           ┌───────────▼──────────┐
           │   AI Orchestrator    │
           │   (Coordinates all)  │
           └──────────────────────┘
```

### 7.2 GPT-4 Insight Generation Flow

```
User Request                      Backend                       OpenAI API
    │                                │                               │
    │  1. GET /api/ai/insights      │                               │
    ├──────────────────────────────►│                               │
    │                                │  2. Gather user data:         │
    │                                │     - Transactions            │
    │                                │     - Budget status           │
    │                                │     - Goals                   │
    │                                │     - Spending patterns       │
    │                                │                               │
    │                                │  3. Build prompt:             │
    │                                │     "User in Bulgaria,        │
    │                                │      monthly income $3k,      │
    │                                │      overspent on dining      │
    │                                │      by 20%. Provide          │
    │                                │      actionable advice."      │
    │                                │                               │
    │                                │  4. Call GPT-4                │
    │                                ├──────────────────────────────►│
    │                                │                               │
    │                                │                               │  5. Generate
    │                                │                               │     response
    │                                │                               │     (AI magic)
    │                                │                               │
    │                                │  6. Response                  │
    │                                │◄──────────────────────────────┤
    │                                │  "Consider meal prepping      │
    │                                │   to reduce dining out..."    │
    │                                │                               │
    │                                │  7. Store insight             │
    │                                │     (cache for 24h)           │
    │                                │                               │
    │  8. Return insight             │                               │
    │◄───────────────────────────────┤                               │
    │  {advice: "...",               │                               │
    │   confidence: 0.92}            │                               │
    │                                │                               │
```

### 7.3 Behavioral Clustering (K-means)

```
┌─────────────────────────────────────────────────────────────┐
│                   Behavioral Clustering                      │
└─────────────────────────────────────────────────────────────┘

Step 1: Feature Extraction
    ┌──────────────────────────────────────┐
    │  For each user, extract features:    │
    │                                      │
    │  - Avg monthly spending              │
    │  - Category distribution %           │
    │  - Budget adherence score            │
    │  - Savings rate                      │
    │  - Transaction frequency             │
    │  - Impulse purchase rate             │
    └──────────────────────────────────────┘
              │
              ▼
Step 2: K-means Clustering (k=5)
    ┌──────────────────────────────────────┐
    │  Cluster Users into:                 │
    │                                      │
    │  Cluster 0: "Savers" (20%)          │
    │    - High savings rate               │
    │    - Low impulse purchases           │
    │                                      │
    │  Cluster 1: "Balanced" (35%)        │
    │    - Moderate spending               │
    │    - Good budget adherence           │
    │                                      │
    │  Cluster 2: "Spenders" (25%)        │
    │    - High dining/entertainment       │
    │    - Low savings                     │
    │                                      │
    │  Cluster 3: "Struggling" (15%)      │
    │    - Frequent overspending           │
    │    - Low income/high expenses        │
    │                                      │
    │  Cluster 4: "Premium Users" (5%)    │
    │    - High income                     │
    │    - Diverse spending                │
    └──────────────────────────────────────┘
              │
              ▼
Step 3: Personalized Insights
    ┌──────────────────────────────────────┐
    │  User in Cluster 2 ("Spenders"):    │
    │                                      │
    │  Recommendations:                    │
    │  - Set dining budget alerts          │
    │  - Join "No-Spend Weekend" challenge │
    │  - Compare to Cluster 1 (Balanced)  │
    └──────────────────────────────────────┘
```

---

## 8. DEPLOYMENT ARCHITECTURE

### 8.1 Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                            │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Ingress (NGINX)                                             │
│  - TLS termination                                           │
│  - Load balancing                                            │
│  - Rate limiting                                             │
└──────────────────┬───────────────────────────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼────┐   ┌────▼────┐   ┌───▼─────┐
│ API Pod │   │ API Pod │   │ API Pod │  (3-10 replicas)
│  #1     │   │  #2     │   │  #3     │
└────┬────┘   └────┬────┘   └───┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼──────┐ ┌───▼──────┐ ┌────▼──────┐
│ Worker    │ │ Worker   │ │ Scheduler │
│ Pod #1    │ │ Pod #2   │ │ Pod       │
└────┬──────┘ └───┬──────┘ └────┬──────┘
     │            │              │
     └────────────┼──────────────┘
                  │
     ┌────────────┼────────────┐
     │            │            │
┌────▼────┐  ┌───▼────┐  ┌────▼─────┐
│Postgres │  │ Redis  │  │ External │
│ Primary │  │ Cache  │  │ Services │
└─────────┘  └────────┘  └──────────┘
```

### 8.2 CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                            │
└─────────────────────────────────────────────────────────────────┘

Developer Push
      │
      ▼
┌──────────────────────┐
│  GitHub Actions      │
│  Trigger             │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Stage 1: Lint       │
│  - ruff              │
│  - black             │
│  - isort             │
│  - mypy              │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Stage 2: Test       │
│  - pytest            │
│  - coverage (>90%)   │
│  - security tests    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Stage 3: Build      │
│  - Docker image      │
│  - Tag: latest, sha  │
│  - Push to registry  │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Stage 4: Deploy     │
│  - Deploy to staging │
│  - Run smoke tests   │
└──────┬───────────────┘
       │
       ├───► ❌ Fail → Rollback
       │
       ▼ ✓ Pass
┌──────────────────────┐
│  Stage 5: Production │
│  - Blue-Green deploy │
│  - Gradual rollout   │
│  - Health monitoring │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Stage 6: Verify     │
│  - Post-deploy tests │
│  - Sentry release    │
│  - Notify team       │
└──────────────────────┘
```

---

## 9. MONITORING & OBSERVABILITY

### 9.1 Observability Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    Observability Architecture                    │
└─────────────────────────────────────────────────────────────────┘

                    ┌───────────────┐
                    │  Application  │
                    │   (FastAPI)   │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐      ┌────▼─────┐
   │  Logs    │      │   Metrics   │      │  Traces  │
   │ (JSON)   │      │ (Prometheus)│      │ (Sentry) │
   └────┬─────┘      └──────┬──────┘      └────┬─────┘
        │                   │                   │
        │                   │                   │
   ┌────▼─────────┐    ┌───▼──────────┐   ┌───▼──────┐
   │ CloudWatch   │    │  Prometheus  │   │  Sentry  │
   │ Logs         │    │  Server      │   │  Backend │
   └──────────────┘    └───┬──────────┘   └──────────┘
                           │
                      ┌────▼─────┐
                      │ Grafana  │
                      │Dashboard │
                      └──────────┘
                           │
                      ┌────▼─────┐
                      │  Alerts  │
                      │  (Slack) │
                      └──────────┘
```

### 9.2 Key Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│                    Grafana Dashboard Layout                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  API Performance                                       │    │
│  │  - Request Rate: 1,234 req/min                        │    │
│  │  - Response Time p50: 45ms                            │    │
│  │  - Response Time p95: 150ms                           │    │
│  │  - Response Time p99: 320ms                           │    │
│  │  - Error Rate: 0.05%                                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Database Performance                                  │    │
│  │  - Connection Pool: 45/100                            │    │
│  │  - Query Time p95: 30ms                               │    │
│  │  - Slow Queries: 3/hour                               │    │
│  │  - Deadlocks: 0                                       │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Redis Cache                                           │    │
│  │  - Hit Rate: 87%                                      │    │
│  │  - Memory Usage: 234MB / 512MB                        │    │
│  │  - Evictions: 12/hour                                 │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Background Tasks                                      │    │
│  │  - Queue Depth: 15 tasks                              │    │
│  │  - Processing Rate: 45 tasks/min                      │    │
│  │  - Failed Tasks: 2 (retry pending)                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. SECURITY ARCHITECTURE

### 10.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     Security Defense-in-Depth                    │
└─────────────────────────────────────────────────────────────────┘

Layer 1: Network Security
    ┌──────────────────────────────────┐
    │  - TLS 1.3 encryption            │
    │  - WAF (Web Application Firewall)│
    │  - DDoS protection               │
    │  - IP allowlisting (admin)       │
    └──────────────┬───────────────────┘
                   │
Layer 2: Application Security
    ┌──────────────▼───────────────────┐
    │  - CORS protection               │
    │  - Security headers (HSTS, CSP)  │
    │  - Rate limiting                 │
    │  - Input validation              │
    └──────────────┬───────────────────┘
                   │
Layer 3: Authentication & Authorization
    ┌──────────────▼───────────────────┐
    │  - JWT OAuth 2.0                 │
    │  - Scope-based permissions       │
    │  - Token blacklisting            │
    │  - Password hashing (bcrypt)     │
    └──────────────┬───────────────────┘
                   │
Layer 4: Data Security
    ┌──────────────▼───────────────────┐
    │  - Encryption at rest (AES-256)  │
    │  - Encrypted backups             │
    │  - PII filtering (Sentry)        │
    │  - Secure file storage (S3)      │
    └──────────────┬───────────────────┘
                   │
Layer 5: Audit & Monitoring
    ┌──────────────▼───────────────────┐
    │  - Audit logging (all actions)   │
    │  - Security event monitoring     │
    │  - Anomaly detection             │
    │  - Incident response             │
    └──────────────────────────────────┘
```

---

## 11. SCALABILITY & PERFORMANCE

### 11.1 Horizontal Scaling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                      Load Scaling                                │
└─────────────────────────────────────────────────────────────────┘

Low Load (< 100 req/min)
    ┌──────────────────┐
    │  Load Balancer   │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │   API Pod #1     │
    │   API Pod #2     │
    │   API Pod #3     │  (Minimum: 3 replicas)
    └──────────────────┘

High Load (> 1000 req/min)
    ┌──────────────────┐
    │  Load Balancer   │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │   API Pod #1     │
    │   API Pod #2     │
    │   API Pod #3     │
    │   API Pod #4     │
    │   API Pod #5     │
    │   API Pod #6     │
    │   API Pod #7     │
    │   API Pod #8     │
    │   API Pod #9     │
    │   API Pod #10    │  (Maximum: 10 replicas)
    └──────────────────┘

Auto-scaling Triggers:
  - CPU > 70%
  - Memory > 80%
  - Request queue > 100
  - Response time p95 > 500ms
```

### 11.2 Caching Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                      Multi-Level Caching                         │
└─────────────────────────────────────────────────────────────────┘

Request
    │
    ▼
┌────────────────────┐
│ L1: In-Memory      │  ← LRU cache (app instance)
│ Cache (Python)     │    TTL: 5 minutes
│ Hit Rate: 40%      │
└─────────┬──────────┘
          │ Miss
          ▼
┌────────────────────┐
│ L2: Redis Cache    │  ← Distributed cache
│ (Shared)           │    TTL: 1 hour
│ Hit Rate: 50%      │
└─────────┬──────────┘
          │ Miss
          ▼
┌────────────────────┐
│ L3: Database       │  ← PostgreSQL with indexes
│ Query              │    Optimized queries
└────────────────────┘

Cached Data:
  - User profiles (1 hour)
  - Transaction lists (5 min)
  - AI insights (24 hours)
  - Budget calculations (15 min)
  - Analytics (1 hour)
```

---

**Document End**

For the complete technical analysis, see: `COMPREHENSIVE_PLATFORM_ANALYSIS.md`
