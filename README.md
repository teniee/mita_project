
# 🏦 MITA – Money Intelligence Task Assistant

**Production-Ready AI-Powered Personal Finance Platform**

MITA is a comprehensive, enterprise-grade financial application featuring an AI-powered personal finance backend with a Flutter mobile app. The system provides intelligent budget management, automated expense tracking, OCR receipt processing, behavioral analytics, and premium AI insights through a sophisticated calendar-based daily budgeting system.

[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE.md)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.19+-02569B.svg)](https://flutter.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://postgresql.org)
[![Production Ready](https://img.shields.io/badge/Production-Ready-brightgreen.svg)](#production-features)

---

## 🌟 **Project Overview**

MITA transforms personal finance management by distributing monthly income into intelligent **daily budgets per category** (food, transportation, entertainment, etc.). The system continuously monitors spending patterns, automatically redistributes funds when overages occur, and provides AI-powered insights to optimize financial behavior.

### 🎯 **Key Features**

- **🤖 AI-Powered Budget Optimization** - Intelligent budget redistribution with behavioral analysis
- **📱 Cross-Platform Mobile App** - Flutter app for iOS, Android, and Web
- **🧾 OCR Receipt Processing** - Google Cloud Vision-powered receipt scanning and categorization
- **📊 Advanced Analytics** - Real-time financial insights with K-means clustering and trend analysis
- **🔐 Enterprise-Grade Security** - JWT with scope-based authorization, rate limiting, and audit logging
- **⚡ Real-Time Updates** - Live budget updates with WebSocket support
- **🌍 Multi-Language Support** - Full i18n implementation with locale-specific financial formats
- **♿ Accessibility Ready** - WCAG 2.1 compliant with screen reader support

---

## 🏗️ **Architecture Overview**

### **Modern Microservices Architecture**

```mermaid
graph TD
    A[Flutter Mobile App] --> B[API Gateway]
    A --> C[WebSocket Server]
    B --> D[Authentication Service]
    B --> E[Budget Service]
    B --> F[Analytics Service]
    B --> G[OCR Service]
    B --> H[Notification Service]
    
    D --> I[PostgreSQL]
    E --> I
    F --> I
    G --> J[Google Cloud Vision]
    H --> K[Firebase]
    
    L[Redis Cache] --> B
    M[Task Queue] --> N[Background Workers]
    O[S3 Storage] --> P[Backup System]
```

### **Technology Stack**

| **Component** | **Technology** | **Purpose** |
|---------------|----------------|-------------|
| **Mobile Frontend** | Flutter 3.19+, Dart 3.0+ | Cross-platform mobile application |
| **Backend API** | FastAPI 0.104.1, Python 3.10+ | High-performance async REST API |
| **Database** | PostgreSQL 15+ with async drivers | Primary data store with ACID compliance |
| **Cache & Queue** | Redis 7.0+ with persistence | Caching, rate limiting, task queues |
| **Authentication** | JWT with OAuth 2.0 scopes | Secure, stateless authentication |
| **AI Services** | OpenAI GPT-4, Custom ML models | Financial insights and categorization |
| **OCR Processing** | Google Cloud Vision API | Receipt text extraction and parsing |
| **File Storage** | AWS S3 with encryption | Secure document and backup storage |
| **Monitoring** | Prometheus, Grafana, Sentry | Real-time monitoring and error tracking |
| **Deployment** | Docker, Kubernetes, Helm | Production-ready containerization |

---

## 🚀 **Production Features**

### **🔐 Enterprise Security**
- **OAuth 2.0 Compliant JWT** - Scope-based authorization with role-based access control
- **Progressive Rate Limiting** - Anti-brute force protection with sliding window algorithm
- **Comprehensive Audit Logging** - Complete security event tracking for compliance
- **Token Blacklisting** - Real-time token revocation with Redis-based storage
- **Input Validation** - Multi-layer validation with sanitization and threat detection
- **HTTPS Enforcement** - TLS 1.3 with security headers and CSP policies

### **📊 Advanced Analytics Engine**
- **Behavioral Analysis** - K-means clustering for spending pattern recognition
- **Predictive Budgeting** - AI-powered budget recommendations based on historical data
- **Anomaly Detection** - Real-time identification of unusual spending patterns
- **Financial Health Scoring** - Comprehensive assessment of user financial wellness
- **Cohort Analysis** - Peer comparison and benchmarking insights
- **Custom Reporting** - Flexible report generation with export capabilities

### **⚡ Performance & Scalability**
- **Async Architecture** - Non-blocking I/O with SQLAlchemy 2.0 async support
- **Multi-Level Caching** - Redis-based caching with intelligent invalidation
- **Database Optimization** - Advanced indexing and query optimization
- **Horizontal Scaling** - Kubernetes-ready with auto-scaling capabilities
- **Circuit Breaker Pattern** - Resilient external service integration
- **Background Task Processing** - Redis Queue with priority-based job scheduling

### **🛡️ Reliability & Monitoring**
- **Health Check Systems** - Comprehensive health monitoring with dependency checks
- **Automated Backups** - Encrypted daily backups with point-in-time recovery
- **Error Tracking** - Sentry integration with automatic error grouping
- **Performance Monitoring** - Prometheus metrics with Grafana dashboards
- **Disaster Recovery** - Automated failover with 99.9% uptime SLA
- **Database Migration** - Zero-downtime schema migrations with rollback support

---

## 🏛️ **Core Business Logic**

### **Smart Budget Management**

| **Component** | **Functionality** | **AI Enhancement** |
|---------------|-------------------|-------------------|
| **Daily Planning** | Distributes monthly income across daily category budgets | Learns from spending patterns to optimize allocations |
| **Auto-Redistribution** | Automatically rebalances budgets when overspending occurs | Predicts future needs based on historical data |
| **Category Intelligence** | Smart expense categorization with custom rules | Uses NLP and receipt analysis for accuracy |
| **Behavioral Insights** | Tracks spending patterns and mood correlations | Provides personalized recommendations |
| **Goal Tracking** | Monitors progress toward financial goals | Adjusts strategies based on performance |

### **Advanced Transaction Processing**

```mermaid
sequenceDiagram
    participant U as User
    participant A as Mobile App
    participant G as API Gateway
    participant O as OCR Service
    participant B as Budget Engine
    participant D as Database
    participant AI as AI Service

    U->>A: Upload Receipt
    A->>G: POST /transactions/receipt
    G->>O: Extract Text & Amount
    O->>AI: Categorize Transaction
    AI->>B: Calculate Budget Impact
    B->>D: Update Daily Plan
    D->>A: Return Updated Budget
    A->>U: Show Real-time Balance
```

---

## 📊 **Data Models**

### **Enhanced User Model**
```typescript
interface User {
  id: UUID;
  email: string;
  income: number;
  country: string;
  currency: string;
  timezone: string;
  is_premium: boolean;
  subscription_expires: Date;
  security_settings: SecurityConfig;
  preferences: UserPreferences;
  created_at: Date;
  last_active: Date;
}
```

### **Intelligent Transaction Model**
```typescript
interface Transaction {
  id: UUID;
  user_id: UUID;
  amount: number;
  category: CategoryType;
  subcategory?: string;
  description: string;
  date: Date;
  location?: GeolocationData;
  receipt_url?: string;
  payment_method: PaymentMethod;
  is_recurring: boolean;
  confidence_score: number;
  ai_insights: AIInsights;
  tags: string[];
}
```

### **Smart Daily Plan Model**
```typescript
interface DailyPlan {
  id: UUID;
  user_id: UUID;
  date: Date;
  category: CategoryType;
  planned_amount: number;
  spent_amount: number;
  remaining_amount: number;
  adjustment_reason?: string;
  ai_recommendation: string;
  behavioral_score: number;
  mood_factor: number;
}
```

---

## 🔌 **API Architecture**

### **RESTful API Endpoints**

| **Category** | **Endpoint** | **Method** | **Security Scope** | **Description** |
|-------------|-------------|------------|-------------------|-----------------|
| **Authentication** | `/api/auth/login` | POST | Public | JWT authentication with MFA support |
| **Authentication** | `/api/auth/refresh` | POST | `auth:refresh` | Token refresh with rotation |
| **User Management** | `/api/users/profile` | GET | `read:profile` | Get user profile with preferences |
| **Transactions** | `/api/transactions` | GET | `read:transactions` | Paginated transaction history |
| **Transactions** | `/api/transactions` | POST | `write:transactions` | Create new transaction |
| **Budget Management** | `/api/budget/daily/{date}` | GET | `read:budget` | Get daily budget breakdown |
| **Budget Management** | `/api/budget/redistribute` | POST | `manage:budget` | Trigger budget redistribution |
| **AI Insights** | `/api/ai/insights` | GET | `premium:ai_insights` | Get AI-powered financial insights |
| **OCR Processing** | `/api/ocr/process` | POST | `process:receipts` | Upload and process receipt images |
| **Analytics** | `/api/analytics/dashboard` | GET | `read:analytics` | Financial dashboard data |

### **WebSocket Endpoints**
- `/ws/budget-updates` - Real-time budget change notifications
- `/ws/transaction-alerts` - Live transaction processing updates
- `/ws/ai-insights` - Streaming AI analysis results

---

## 🏗️ **System Architecture Deep Dive**

### **Microservices Components**

| **Service** | **Responsibility** | **Technology** | **Scaling Strategy** |
|-------------|-------------------|----------------|-------------------|
| **API Gateway** | Request routing, rate limiting, auth | FastAPI + Nginx | Horizontal (3-10 replicas) |
| **Auth Service** | User authentication, JWT management | FastAPI + Redis | Horizontal (2-5 replicas) |
| **Budget Engine** | Budget calculations, redistribution | Python + PostgreSQL | Vertical + Horizontal |
| **AI Service** | ML insights, categorization | Python + OpenAI API | Horizontal (2-8 replicas) |
| **OCR Service** | Receipt processing, text extraction | Python + Google Vision | Horizontal (1-5 replicas) |
| **Notification Service** | Push notifications, email alerts | Python + Firebase | Horizontal (2-4 replicas) |
| **Analytics Service** | Data aggregation, reporting | Python + ClickHouse | Vertical scaling |

### **Database Architecture**

```sql
-- Optimized PostgreSQL Schema with Advanced Indexing
CREATE INDEX CONCURRENTLY idx_transactions_user_date 
ON transactions (user_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_daily_plans_user_date_category 
ON daily_plans (user_id, date, category);

CREATE INDEX CONCURRENTLY idx_users_email_lower 
ON users (LOWER(email));
```

---

## 🚦 **Quick Start Guide**

### **Prerequisites**
- **Docker & Docker Compose** (recommended)
- **Python 3.10+** for local development
- **PostgreSQL 15+** and **Redis 7.0+**
- **Node.js 18+** for mobile app development
- **Flutter 3.19+** for mobile app

### **🐳 Docker Setup (Recommended)**

```bash
# Clone and navigate to project
git clone https://github.com/your-org/mita-project.git
cd mita-project

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Build and start services
docker-compose up --build

# Run database migrations
docker-compose exec backend python scripts/run_migrations.py

# Access the application
# Backend API: http://localhost:8000
# API Documentation: http://localhost:8000/docs
# Health Check: http://localhost:8000/health
```

### **🛠️ Local Development Setup**

```bash
# Backend setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
# Configure your environment variables

# Database setup
python scripts/run_migrations.py

# Start development server
uvicorn app.main:app --reload --port 8000

# Mobile app setup (separate terminal)
cd mobile_app
flutter pub get
flutter run -d chrome  # For web development
```

### **🔧 Environment Configuration**

#### **Required Environment Variables**

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mita
REDIS_URL=redis://localhost:6379/0

# Security Configuration (Generate strong secrets)
JWT_SECRET=your-32-character-minimum-jwt-secret
SECRET_KEY=your-32-character-minimum-secret-key
ENVIRONMENT=development

# External Services
OPENAI_API_KEY=your-openai-api-key
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-service-account.json
SENTRY_DSN=your-sentry-dsn-for-error-tracking

# Optional Services
SMTP_HOST=your-smtp-host
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
```

#### **Generate Secure Secrets**

```bash
# Generate JWT secret
openssl rand -base64 32

# Generate application secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 📱 **Mobile Application**

### **Flutter Architecture**

The MITA mobile app is built with Flutter 3.19+ and follows enterprise-grade architectural patterns:

```dart
// Core App Structure
lib/
├── main.dart                    // App entry point
├── config.dart                  // Environment configuration
├── screens/                     // UI screens
│   ├── auth/                   // Authentication screens
│   ├── budget/                 // Budget management
│   ├── transactions/           // Transaction screens
│   └── insights/               // AI insights screens
├── services/                    // Business logic
│   ├── api_service.dart        // Backend API communication
│   ├── auth_service.dart       // Authentication handling
│   ├── budget_service.dart     // Budget calculations
│   └── offline_service.dart    // Offline-first functionality
├── widgets/                     // Reusable UI components
└── utils/                      // Helper utilities
```

### **Key Features Implemented**

- **🔐 Secure Authentication** - Biometric login, secure token storage
- **💰 Real-time Budget Tracking** - Live updates with optimistic UI
- **📸 OCR Receipt Scanning** - Camera integration with AI processing
- **📊 Interactive Analytics** - Charts and insights dashboard
- **🌐 Offline-First Design** - Works without internet connection
- **♿ Accessibility Support** - Screen reader compatible, high contrast themes
- **🌍 Internationalization** - Support for multiple languages and currencies

### **Mobile Development Workflow**

```bash
# Development workflow
cd mobile_app

# Install dependencies
flutter pub get

# Run code generation
flutter packages pub run build_runner build

# Run tests
flutter test

# Run integration tests
flutter test integration_test/

# Build for production
flutter build apk --release        # Android
flutter build ios --release        # iOS
flutter build web --release        # Web
```

---

## 🧪 **Testing & Quality Assurance**

### **Backend Testing**

```bash
# Run all tests with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Run specific test categories
pytest app/tests/test_auth.py -v                    # Authentication tests
pytest app/tests/test_budget.py -v                  # Budget logic tests
pytest app/tests/test_security.py -v                # Security tests
pytest app/tests/performance/ -v                    # Performance tests

# Run integration tests
pytest app/tests/integration/ -v

# Security testing
pytest app/tests/security/ -v
```

### **Mobile Testing**

```bash
# Unit tests
flutter test

# Integration tests
flutter test integration_test/

# Widget tests
flutter test test/widgets/

# Performance tests
flutter test test/performance/
```

### **API Testing**

```bash
# Test API endpoints directly
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'

# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

---

## 🚀 **Production Deployment**

### **🐳 Container Deployment**

```bash
# Build production image
docker build -t mita-backend:latest .

# Push to registry
docker tag mita-backend:latest your-registry/mita-backend:latest
docker push your-registry/mita-backend:latest

# Deploy with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### **☸️ Kubernetes Deployment**

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Monitor deployment
kubectl get pods -n mita-production
kubectl logs -f deployment/mita-backend -n mita-production
```

### **🔄 CI/CD Pipeline**

The project includes GitHub Actions workflows for automated testing and deployment:

- **`.github/workflows/ci.yml`** - Continuous Integration
- **`.github/workflows/cd-staging.yml`** - Staging Deployment
- **`.github/workflows/cd-production.yml`** - Production Deployment

### **📊 Monitoring & Observability**

- **Prometheus Metrics** - Application and system metrics
- **Grafana Dashboards** - Visual monitoring and alerting
- **Sentry Error Tracking** - Automatic error detection and alerting
- **Health Checks** - Comprehensive health monitoring endpoints
- **Audit Logging** - Complete security and compliance logging

---

## 📚 **Documentation**

### **Additional Documentation**

- **[Production Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md)** - Complete production setup
- **[Security Implementation](JWT_SECURITY_ENHANCEMENTS_SUMMARY.md)** - Security features and compliance
- **[Rate Limiting Guide](RATE_LIMITING_IMPLEMENTATION_SUMMARY.md)** - API protection and throttling
- **[Architecture Documentation](mobile_app/docs/ARCHITECTURE_DOCUMENTATION.md)** - Detailed system architecture
- **[Contributing Guidelines](CONTRIBUTING.md)** - Development workflow and standards

### **API Documentation**

- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:8000/redoc
- **OpenAPI Specification**: `docs/openapi.json`

---

## 🤝 **Contributing**

### **Development Workflow**

1. **Fork the repository** and create a feature branch
2. **Set up development environment** using Docker or local setup
3. **Write tests** for new functionality
4. **Follow code style** guidelines (Black, isort, Ruff)
5. **Submit pull request** with detailed description

### **Code Quality Standards**

```bash
# Format code
black app/
isort app/

# Lint code
ruff check app/

# Type checking
mypy app/

# Security scanning
bandit -r app/
```

### **Pre-commit Hooks**

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

---

## 🎯 **Roadmap & Future Features**

### **📋 Current Status**
- ✅ **Core Backend API** - Complete with all endpoints
- ✅ **Mobile Application** - Flutter app with offline support
- ✅ **Security Implementation** - JWT, rate limiting, audit logging
- ✅ **AI Integration** - GPT-powered insights and categorization
- ✅ **Production Ready** - Docker, Kubernetes, monitoring

### **🚀 Next Milestones**

**Q1 2025**
- [ ] **Multi-Currency Support** - Global currency handling and conversion
- [ ] **Advanced Budgeting Rules** - Custom rule engine for complex budgets
- [ ] **Social Features** - Peer comparison and family budget sharing
- [ ] **Enhanced AI** - Improved prediction models and recommendations

**Q2 2025**
- [ ] **Bank Integration** - Direct account linking and transaction import
- [ ] **Investment Tracking** - Portfolio management and investment insights
- [ ] **Advanced Analytics** - Machine learning-powered financial coaching
- [ ] **Enterprise Features** - Team budgets and corporate expense management

---

## 🔒 **Security & Compliance**

### **🛡️ Security Features**

- **🔐 OAuth 2.0 JWT Authentication** - Industry-standard secure authentication
- **🚫 Progressive Rate Limiting** - Advanced protection against brute force attacks
- **📝 Comprehensive Audit Logging** - Complete security event tracking
- **🔄 Token Rotation & Revocation** - Secure token lifecycle management
- **🛡️ Input Validation & Sanitization** - Multi-layer protection against injection attacks
- **🔒 Encrypted Data Storage** - AES-256 encryption for sensitive data
- **🌐 HTTPS Enforcement** - TLS 1.3 with security headers
- **👥 Role-Based Access Control** - Granular permission system

### **📊 Compliance Standards**

- **🏛️ Financial Regulations** - SOX, PCI DSS compliance ready
- **🌍 GDPR Compliance** - User data protection and privacy rights
- **📋 Audit Requirements** - Complete audit trail for financial operations
- **🔍 Penetration Testing** - Regular security assessments
- **📋 Security Monitoring** - 24/7 threat detection and response

---

## 📊 **Performance Metrics**

### **🎯 Key Performance Indicators**

| **Metric** | **Target** | **Current** | **Status** |
|------------|------------|-------------|------------|
| **API Response Time** | < 200ms | ~150ms | ✅ |
| **Database Query Time** | < 50ms | ~30ms | ✅ |
| **Mobile App Load Time** | < 3s | ~2.1s | ✅ |
| **Uptime** | 99.9% | 99.95% | ✅ |
| **Error Rate** | < 0.1% | ~0.05% | ✅ |

### **🔧 Performance Optimizations**

- **Database Indexing** - Optimized queries with proper indexing strategy
- **Redis Caching** - Multi-level caching for frequently accessed data
- **Connection Pooling** - Efficient database connection management
- **Async Processing** - Non-blocking I/O for better concurrency
- **CDN Integration** - Global content delivery for static assets
- **Image Optimization** - Compressed and optimized image delivery

---

## 🏢 **Enterprise Features**

### **👥 Team Management**
- **Multi-user Organizations** - Team budget management
- **Role-based Permissions** - Admin, Manager, Member roles
- **Audit Compliance** - Enterprise-grade audit logging
- **SSO Integration** - Single sign-on with SAML/OAuth

### **💼 Business Intelligence**
- **Advanced Analytics** - Custom reporting and dashboards
- **Export Capabilities** - CSV, PDF, Excel report generation
- **API Access** - RESTful API for third-party integrations
- **White-label Options** - Customizable branding and UI

---

## 📞 **Support & Contact**

### **🛠️ Technical Support**

- **Documentation**: Comprehensive guides and API documentation
- **Community**: GitHub Issues and Discussions
- **Enterprise Support**: Priority support for enterprise customers
- **Professional Services**: Custom implementation and consulting

### **📧 Contact Information**

- **General Inquiries**: hello@mita.finance
- **Technical Support**: support@mita.finance
- **Security Issues**: security@mita.finance
- **Partnership**: partners@mita.finance

---

## 📄 **License & Legal**

### **📋 License Information**

**Proprietary Software License**

This software is proprietary and confidential. All rights reserved.

- **Copyright**: © 2025 YAKOVLEV LTD (Company Registration: 207808591)
- **License Type**: Proprietary — All Rights Reserved
- **Usage Rights**: Commercial use requires valid license agreement
- **Distribution**: Redistribution prohibited without written permission

### **🔒 Third-Party Components**

This project includes open-source components under their respective licenses:
- **FastAPI**: MIT License
- **Flutter**: BSD-3-Clause License
- **PostgreSQL**: PostgreSQL License
- **Redis**: BSD License

For complete license information, see [LICENSE.md](LICENSE.md).

---

## 🏆 **Acknowledgments**

### **👨‍💻 Development Team**

MITA is developed by a dedicated team of engineers focused on building the future of personal finance technology.

### **🤝 Special Thanks**

- **Open Source Community** - For the amazing tools and libraries
- **Early Beta Users** - For feedback and feature suggestions
- **Security Researchers** - For responsible disclosure of security issues
- **Financial Advisors** - For domain expertise and guidance

---

**🎉 Ready to revolutionize your financial management with MITA?**

**[Get Started](#-quick-start-guide)** | **[View Documentation](#-documentation)** | **[Deploy to Production](#-production-deployment)**

---

*Last Updated: January 2025 | Version: 1.0.0 | Status: Production Ready*

