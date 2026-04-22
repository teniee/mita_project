 ЧЕСТНЫЙ АУДИТ MITA — Апрель 2026

  Общая оценка: 6.5/10 — Работает в проде, но есть реальные проблемы

  ---
  1. КРИТИЧЕСКИЕ РАСХОЖДЕНИЯ — Что CLAUDE.md говорит vs Реальность

  ┌───────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
  │        Утверждение в CLAUDE.md        │                                       Реальность                                       │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "438 tests passing"                   │ 313 собирается, 305 проходит, 8 падают                                                 │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "87 test files"                       │ 88 в app/tests/ (не запускаются локально) + 15 в tests/ = 103                          │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "13 collection errors"                │ 7 ошибок коллекции + 8 failing tests                                                   │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "Google Cloud Vision API OCR (99.8%)" │ Tesseract (pytesseract). Google Vision SDK установлен, но не используется как основной │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "Python 3.9 compatibility fixed"      │ **main.py:84 имеет `str                                                                │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "app/api/v1/routes/"                  │ Реальная структура: app/api/*/routes.py (другой путь)                                  │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "app/models/"                         │ Реальный путь: app/db/models/                                                          │
  ├───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
  │ "592 Python files"                    │ 549 файлов                                                                             │
  └───────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  2. РЕАЛЬНЫЙ СТАТУС ТЕСТОВ

  tests/ directory:     313 собрано, 305 проходит, 8 ПАДАЮТ
  app/tests/ directory: 88 файлов — 7 НЕ ЗАПУСКАЮТСЯ вообще (Python 3.9 несовместимость)

  8 падающих тестов — ВСЕ в core-функциях:

  Календарь (4 падения) — test_category_mapping_fix.py
  AssertionError: assert 'rent' in {'bills', 'entertainment', 'food', 'housing', ...}
  Проблема: category mapping сломан — возвращает housing вместо rent. Система FIXED/SPREAD/CLUSTERED паттернов не применяется правильно.

  Budget + Location (2 падения) — test_income_location_budget_allocation.py
  assert <IncomeTier.LOWER_MIDDLE> == <IncomeTier.MIDDLE>  # tier classification wrong
  assert (Decimal('2150.00') / 3350) < 0.1  # off by 64%!
  Discretionary total выдаёт $5500 вместо $3350 — ошибка $2150 в основном алгоритме расчёта.

  E2E Core Journey (1 падение)
  assert abs(total_discretionary_check - budget_plan['discretionary_total']) < 10
  # diff = 300.0
  $300 расхождение в discretionary total.

  Scheduled Expenses Impact (1 падение)
  assert result.total_committed == Decimal("60.00")
  # Actual: Decimal('0.00')
  Scheduled expenses не учитываются в расчёте impact.

  ---
  3. PYTHON 3.9 / PRODUCTION НЕСОВМЕСТИМОСТЬ

  Проблема: Local development = Python 3.9.6, Production Railway = Python 3.12

  app/main.py:84:
  _firebase_init_error: str | None = None  # FAILS on Python 3.9

  Результат: from app.main import app падает локально. Все 88 тестов в app/tests/ не запускаются. В проде работает, потому что Railway использует Python 3.12.

  ---
  4. ЧТО РЕАЛЬНО РАБОТАЕТ

  ✅ Backend на Railway — работает, деплоится нормально
  ✅ Auth система — JWT, registration, login, token refresh — реальная реализация
  ✅ Calendar core — 305/313 тестов проходят, алгоритм работает частично
  ✅ Budget redistribution — core алгоритм (budget_redistributor.py) — чистый, реальный код
  ✅ Flutter app — 44 экрана, подключён к Railway, реальная реализация
  ✅ IAP — Apple + Google receipt validation — реальная реализация через httpx
  ✅ 30 Alembic migrations — БД схема последовательная
  ✅ Error handling + middleware — солидная реализация
  ✅ Security headers — HSTS, CSP, XSS protection настроены

  ---
  5. ЧТО РЕАЛЬНО НЕ РАБОТАЕТ / ПРОБЛЕМЫ

  🔴 Category mapping broken — housing не маппится в rent, SPREAD/CLUSTERED паттерны не применяются к категориям
  🔴 Discretionary calculation off by $2150 — бюджетный алгоритм с location weights считает неправильно
  🔴 Scheduled expenses impact = 0 — pending expenses не включаются в impact расчёт
  🔴 OCR — Tesseract, не Google Vision — "99.8% accuracy" это маркетинговая цифра для Tesseract — реальность намного хуже
  🔴 app/tests/ полностью сломаны локально — 7 test files не коллектятся
  🟡 Только 1 str | None в main.py — но это ломает весь dev workflow
  🟡 84 TODO — в основном мелкие, но 1 в production-пути (push notification в streak service)

  ---
  6. РЕАЛЬНЫЙ СЧЁТ ПО МОДУЛЯМ

  ┌───────────────────────┬────────────────────────┬────────────────────────────────────────────────────────────┐
  │        Модуль         │         Статус         │                           Детали                           │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Auth / JWT            │ ✅ Работает            │ Comprehensive implementation                               │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Calendar generation   │ ⚠️  Частично            │ Алгоритм работает, но category mapping сломан              │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Budget redistribution │ ⚠️  Частично            │ Core logic OK, но $300-2150 discrepancy в тестах           │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ OCR                   │ ⚠️  Работает слабо      │ Tesseract, не Google Vision. Нет production-grade accuracy │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ AI Insights           │ ⚠️  Зависит от ключа    │ OpenAI интеграция есть, но требует OPENAI_API_KEY          │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ IAP / Subscriptions   │ ✅ Работает            │ Real Apple/Google validation                               │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Push Notifications    │ ⚠️  Зависит от Firebase │ Настраивается через env vars, один TODO                    │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Flutter UI            │ ✅ Работает            │ 44 экрана, connected to Railway                            │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Database / Migrations │ ✅ Работает            │ 30 migrations, Supabase connected                          │
  ├───────────────────────┼────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Scheduled Expenses    │ 🔴 Сломано             │ Impact calculation returns 0                               │
  └───────────────────────┴────────────────────────┴────────────────────────────────────────────────────────────┘

  ---
  7. ЧТО НУЖНО ИСПРАВИТЬ СРОЧНО (в порядке приоритета)

  1. Category mapping — housing → rent, fix SPREAD/CLUSTERED pattern application (4 tests)
  2. Discretionary calculation with location — $2150 off (2 tests)
  3. Scheduled expense impact — pending не считаются (1 test)
  4. str | None → Optional[str] в main.py:84 — чтобы локальный dev работал
  5. Обновить CLAUDE.md — убрать неточности о тестах, OCR, структуре

  ---
  Итог

  Приложение работает в production и делает что обещает на базовом уровне. Но ключевая функция — daily category-based budgeting с auto-redistribution — имеет
  математические ошибки в core алгоритмах (что и показывают падающие тесты). OCR возможности значительно преувеличены. Для beta-запуска — нужно сначала исправить 8
   failing tests.

✻ Cooked for 4m 4s

⏺ Agent "Audit infrastructure, config and security" completed
                                                                                          
⏺ Agent "Audit tests and mobile app quality" completed
                                                                                                                                                                   
⏺ Agent "Audit backend app/ structure and quality" completed
                                                                                                                                                                   
⏺ Все три агента завершили. Вот финальный полный отчёт с их данными:                                                                                             

  ---                                                                                                                                                              
  ФИНАЛЬНЫЙ АУДИТ MITA — ПОЛНАЯ КАРТИНА
                                                                                                                                                                   
  Общая оценка: 5.5/10                                                                                                                                           
                                                                                                                                                                   
  Работает в production на базовом уровне. Но между документацией и реальностью — пропасть.                                                                        
   
  ---                                                                                                                                                              
  КРИТИЧЕСКИЕ БАГИ (Ломают функциональность)                                                                                                                     
                                                                                                                                                                   
  🔴 1. Missing import в goals/routes.py
                                                                                                                                                                   
  from app.services.notification_integration import get_notification_integration                                                                                 
  # Этот файл НЕ СУЩЕСТВУЕТ
  Goals module не импортируется. Если он вообще загружается — значит import не используется при старте, но это минное поле.                                        
                                                                                                                                                                   
  🔴 2. Dead assignment в financial/routes.py:87-93                                                                                                                
                                                                                                                                                                   
  monthly_payment = validated_price / payload.months                                                                                                             
  monthly_payment * payload.months  # ← ВЫЧИСЛЕНО НО НИГДЕ НЕ ИСПОЛЬЗУЕТСЯ
  Total installment cost не включается в response. Пользователь не видит итоговую стоимость рассрочки.                                                             
                                                                                                                                                                   
  🔴 3. Scheduled expenses impact = 0 (test failure)                                                                                                               
                                                                                                                                                                   
  assert result.total_committed == Decimal("60.00")                                                                                                                
  Actual: Decimal('0.00')                                                                                                                                          
  Pending расходы не учитываются в budget impact расчёте.                                                                                                          
                                                                                                                                                                   
  🔴 4. Category mapping сломан (4 test failures)                                                                                                                  
                                                                                                                                                                   
  AssertionError: assert 'rent' in {'housing', 'food', 'bills', ...}                                                                                             
  Система SPREAD/CLUSTERED паттернов не применяется к категориям корректно.                                                                                        
                                                                                                                                                                   
  🔴 5. Discretionary calculation off (2 test failures)                                                                                                            
                                                                                                                                                                   
  actual: Decimal('5500.00') vs expected: Decimal('3350.00')  # off by $2150                                                                                     
  Это в core алгоритме — основной фиче продукта.                                                                                                                   
                                                                                                                                                                   
  ---                                                                                                                                                              
  ТЕСТЫ — РЕАЛЬНОСТЬ                                                                                                                                               
                                                                                                                                                                 
  ┌───────────────────────┬──────────────────────┬────────────────────────────────────────┐
  │        Метрика        │ CLAUDE.md утверждает │               Реальность               │                                                                        
  ├───────────────────────┼──────────────────────┼────────────────────────────────────────┤
  │ Tests passing         │ "438"                │ 305 passing                            │                                                                        
  ├───────────────────────┼──────────────────────┼────────────────────────────────────────┤                                                                      
  │ Collection errors     │ "13"                 │ 7 errors                               │                                                                        
  ├───────────────────────┼──────────────────────┼────────────────────────────────────────┤                                                                        
  │ Test files            │ "87"                 │ 103 файла (88 + 15)                    │                                                                        
  ├───────────────────────┼──────────────────────┼────────────────────────────────────────┤                                                                        
  │ app/tests запускаются │ ✅                   │ ❌ 7 файлов не собираются (Python 3.9) │                                                                      
  ├───────────────────────┼──────────────────────┼────────────────────────────────────────┤                                                                        
  │ Failing tests         │ "0"                  │ 8 FAILING                              │                                                                      
  └───────────────────────┴──────────────────────┴────────────────────────────────────────┘                                                                        
                                                                                                                                                                 
  7 заблокированных тест-файлов (test_ai_api_integration.py, test_token_blacklist_comprehensive.py, test_ocr_integration.py, test_rate_limit.py и др.) — все падают
   из-за одной строки:                                                                                                                                           
  # app/main.py:84                                                                                                                                                 
  _firebase_init_error: str | None = None  # Python 3.10+ синтаксис, не работает на 3.9                                                                          
                                                                                                                                                                   
  ---                                                                                                                                                              
  BACKEND — ЧТО РЕАЛЬНО ЕСТЬ                                                                                                                                       
                                                                                                                                                                   
  Endpoints                                                                                                                                                      

  - Заявлено: 120+                                                                                                                                                 
  - Реально: 228 endpoints, но ~40% незавершены (stubs, pass, нет логики)
                                                                                                                                                                   
  Services с pass или заглушками (13+ файлов):                                                                                                                   
                                                                                                                                                                   
  - installments/services.py — core логика pass                                                                                                                    
  - financial/services.py — dead code
  - behavior_adapter.py — K-means clustering неполный (~50%)                                                                                                       
  - PredictionEngineService — не существует как единый сервис (<30%)                                                                                               
  - BankSyncService — файл не найден. 0% реализован                                                                                                                
  - WebhookDispatcherService — ~40%, нет retry logic                                                                                                               
  - Ещё 7 файлов с except Exception: pass (молча глотают ошибки)                                                                                                   
                                                                                                                                                                   
  Repository Pattern                                                                                                                                               
                                                                                                                                                                   
  Заявлен в архитектуре — реально не реализован. Везде прямые ORM запросы в routes.                                                                                
   
  ---                                                                                                                                                              
  МОБИЛЬНОЕ ПРИЛОЖЕНИЕ                                                                                                                                           

  Агент оценил как 75% shell, 25% functional.

  Конкретно:                                                                                                                                                       
  - ✅ UI архитектура хорошая (44 экрана)
  - ✅ API service готов (Dio, interceptors, certificate pinning)                                                                                                  
  - ✅ Offline SQLite, secure storage, Firebase                                                                                                                  
  - ❌ Calendar feature не интегрирован в mobile — основная фича продукта                                                                                          
  - ❌ OCR не вызывается из приложения                                                                                                                             
  - ❌ Budget provider использует mock data, не backend                                                                                                            
  - ❌ Income classification — только локальная логика, без backend sync                                                                                           
                                                                                                                                                                   
  ---                                                                                                                                                              
  БЕЗОПАСНОСТЬ                                                                                                                                                     
                                                                                                                                                                   
  Проблемы (из security агента):                                                                                                                                 
                                                                                                                                                                   
  Средние:
  - docker-compose.yml — хардкоженые postgres:postgres credentials                                                                                                 
  - /health endpoint (публичный) раскрывает список подключённых сервисов (OpenAI, Firebase, Redis, Sentry)                                                         
  - allow_methods=["*"], allow_headers=["*"] — слишком широко                                             
  - Rate limiting не масштабируется между workers (in-memory)                                                                                                      
  - Password hashing: 10 rounds (стандарт сегодня — 12-13)                                                                                                         
                                                                                                                                                                   
  Исправлено (хорошо):                                                                                                                                             
  - ✅ GET-based auth endpoints удалены                                                                                                                            
  - ✅ JWT с audience/issuer validation                                                                                                                            
  - ✅ Security headers (HSTS, CSP, X-Frame)                                                                                                                     
  - ✅ Sentry PII filtering                                                                                                                                        
  - ✅ SQLAlchemy ORM (нет SQL injection)                                                                                                                        
  - ✅ Multi-stage Dockerfile, non-root user                                                                                                                       
                                                                                                                                                                 
  ---                                                                                                                                                              
  OCR — МАРКЕТИНГ vs РЕАЛЬНОСТЬ                                                                                                                                  
                                                                                                                                                                   
  CLAUDE.md: "Google Cloud Vision API — OCR (99.8% accuracy)"                                                                                                    
  Реальность: Основная реализация — Tesseract (pytesseract). Google Vision SDK установлен но в файлах ocr_receipt_service.py и advanced_ocr_service.py используется
   Tesseract. Google Vision есть только в google_vision_ocr_service.py — отдельный файл, не основной путь.                                                         
                                                                                                                                                                   
  Tesseract на мобильных фото реальных чеков — точность 60-75%, не 99.8%.                                                                                          
                                                                                                                                                                 
  ---                                                                                                                                                              
  ИТОГОВЫЙ СЧЁТ ПО МОДУЛЯМ                                                                                                                                       
                          
  ┌───────────────────────┬───────────────────────────────────────────┐
  │        Модуль         │              Реальный статус              │                                                                                            
  ├───────────────────────┼───────────────────────────────────────────┤
  │ Auth / JWT            │ ✅ Работает                               │                                                                                            
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                          
  │ Calendar generation   │ ⚠️  Алгоритм ок, но mapping сломан         │
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Budget redistribution │ ⚠️  Core OK, но $2150 discrepancy в тестах │
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Scheduled expenses    │ 🔴 Impact = 0 (broken)                    │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ OCR                   │ ⚠️  Tesseract, не Google Vision            │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ AI/GPT insights       │ ⚠️  ~70% done, требует OPENAI_API_KEY      │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Installments          │ 🔴 Core logic = pass (stub)               │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Bank sync             │ 🔴 0% — файл не существует                │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Prediction engine     │ 🔴 <30%, разбросан по файлам              │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ IAP                   │ ✅ Работает                               │
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Mobile ↔ Backend      │ 🔴 Calendar/Budget не синхронизируются    │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Push notifications    │ ⚠️  Зависит от Firebase env                │                                                                                          
  ├───────────────────────┼───────────────────────────────────────────┤                                                                                            
  │ Repository pattern    │ 🔴 Заявлен, не реализован                 │
  └───────────────────────┴───────────────────────────────────────────┘                                                                                            
                                                                                                                                                                 
  ---                                                                                                                                                              
  ЧТО НУЖНО СДЕЛАТЬ ДО BETA (в порядке приоритета)                                                                                                               
                                                                                                                                                                   
  1. str | None → Optional[str] в main.py:84 — 1 минута, разблокирует 7 тест-файлов
  2. Починить 8 falling tests — calendar mapping, discretionary calculation, scheduled impact                                                                      
  3. goals/routes.py — починить или убрать несуществующий import                                                                                                   
  4. financial/routes.py — присвоить total_amount = monthly_payment * months                                                                                       
  5. Mobile ↔ Backend integration — Calendar и Budget должны реально синхронизироваться                                                                            
  6. Убрать except Exception: pass из 7+ файлов                                                                                                                    
  7. Обновить CLAUDE.md — там ошибочные данные о тестах, OCR, структуре              
