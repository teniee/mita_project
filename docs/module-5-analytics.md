# МОДУЛЬ 5: Аналитика

## Описание

Модуль аналитики MITA предоставляет комплексное решение для отслеживания поведения пользователей, анализа использования функций и предиктивной аналитики финансовых данных.

## Архитектура

### Backend (FastAPI)

#### API Endpoints

**GET /analytics/monthly**
- Получение категорий расходов за текущий месяц
- Возвращает суммы по каждой категории

**GET /analytics/trend**
- Получение дневного тренда расходов за текущий месяц
- Возвращает массив с суммами по дням

**GET /analytics/behavioral-insights**
- Получение поведенческих инсайтов пользователя
- Анализ паттернов расходов, рисков и привычек

**GET /analytics/seasonal-patterns**
- Получение сезонных паттернов расходов
- Анализ трендов по месяцам и праздникам

**POST /analytics/feature-usage**
- Логирование использования функций приложения
- Параметры:
  - `feature`: название функции
  - `screen`: экран где произошло действие
  - `action`: тип действия
  - `metadata`: дополнительные данные
  - `session_id`: ID сессии
  - `platform`: платформа (iOS/Android)
  - `app_version`: версия приложения

**POST /analytics/feature-access-attempt**
- Логирование попыток доступа к премиум функциям
- Используется для анализа конверсии
- Параметры:
  - `feature`: название функции
  - `has_access`: есть ли доступ
  - `is_premium_feature`: премиум функция или нет
  - `screen`: экран
  - `metadata`: дополнительные данные

**POST /analytics/paywall-impression**
- Логирование показов paywall
- Анализ conversion funnel
- Параметры:
  - `screen`: экран где показан paywall
  - `feature`: функция которую пытались использовать
  - `context`: контекст показа
  - `metadata`: дополнительные данные

### Database Models

#### FeatureUsageLog
Логирование использования функций:
- `id` (UUID): уникальный идентификатор
- `user_id` (UUID): ID пользователя
- `feature` (String): название функции
- `screen` (String): экран приложения
- `action` (String): тип действия
- `extra_data` (JSON): дополнительные данные
- `session_id` (String): ID сессии
- `platform` (String): платформа (ios/android)
- `app_version` (String): версия приложения
- `timestamp` (DateTime): время события

#### FeatureAccessLog
Логирование попыток доступа к функциям:
- `id` (UUID): уникальный идентификатор
- `user_id` (UUID): ID пользователя
- `feature` (String): название функции
- `has_access` (Boolean): есть ли доступ
- `is_premium_feature` (Boolean): премиум функция
- `converted_to_premium` (Boolean): конвертировался в премиум
- `converted_at` (DateTime): время конверсии
- `screen` (String): экран
- `extra_data` (JSON): дополнительные данные
- `timestamp` (DateTime): время события

#### PaywallImpressionLog
Логирование показов paywall:
- `id` (UUID): уникальный идентификатор
- `user_id` (UUID): ID пользователя
- `screen` (String): экран
- `feature` (String): функция
- `resulted_in_purchase` (Boolean): привело к покупке
- `purchase_timestamp` (DateTime): время покупки
- `impression_context` (String): контекст показа
- `extra_data` (JSON): дополнительные данные
- `timestamp` (DateTime): время события

### Frontend (Flutter)

#### AnalyticsService

Центральный сервис для работы с аналитикой:

```dart
final analytics = AnalyticsService();

// Инициализация
await analytics.initialize();

// Логирование использования функции
await analytics.logFeatureUsage(
  feature: 'budget_creation',
  screen: 'BudgetScreen',
  action: 'create',
  metadata: {'budget_amount': 1000},
);

// Логирование попытки доступа к премиум функции
await analytics.logFeatureAccessAttempt(
  feature: 'advanced_analytics',
  hasAccess: false,
  isPremiumFeature: true,
  screen: 'AnalyticsScreen',
);

// Логирование показа paywall
await analytics.logPaywallImpression(
  screen: 'AnalyticsScreen',
  feature: 'advanced_analytics',
  context: 'feature_lock',
);

// Отслеживание просмотра экрана
await analytics.trackScreenView('BudgetScreen');

// Отслеживание нажатия кнопки
await analytics.trackButtonTap(
  buttonName: 'create_budget',
  screen: 'BudgetScreen',
);

// Получение сводки аналитики
final summary = await analytics.getAnalyticsSummary();
```

#### PredictiveAnalyticsService

Сервис для предиктивной аналитики:

```dart
final predictive = PredictiveAnalyticsService();

// Инициализация
await predictive.initialize();

// Генерация предсказаний на 30 дней вперед
await predictive.generatePredictions(daysAhead: 30);

// Получение предсказаний по категории
final prediction = await predictive.predictCategorySpending(
  'groceries',
  daysAhead: 30,
);

// Анализ сезонных паттернов
await predictive.analyzeSeasonalPatterns();

// Получение прогноза расходов
final forecast = await predictive.getSpendingForecast(
  startDate: DateTime.now(),
  endDate: DateTime.now().add(Duration(days: 30)),
  categories: ['groceries', 'dining'],
);

// Анализ burn rate бюджета
final burnRate = await predictive.analyzeBudgetBurnRate(
  budget: {'groceries': 500, 'dining': 300},
  currentSpending: {'groceries': 300, 'dining': 150},
  remainingDays: 15,
);

// Получение ранних предупреждений
final alerts = predictive.getEarlyWarningAlerts();
```

#### ErrorAnalyticsService

Сервис для аналитики ошибок:

```dart
final errorAnalytics = ErrorAnalyticsService.instance;

// Инициализация
await errorAnalytics.initialize();

// Запись ошибки
errorAnalytics.recordError(
  error: exception,
  severity: ErrorSeverity.high,
  category: ErrorCategory.network,
  operationName: 'fetchTransactions',
  screenName: 'TransactionsScreen',
  stackTrace: stackTrace,
);

// Получение сводки ошибок за 7 дней
final summary = errorAnalytics.getAnalyticsSummary(
  period: Duration(days: 7),
);

// Получение трендов ошибок
final trends = errorAnalytics.getErrorTrends(
  period: Duration(days: 30),
  interval: Duration(days: 1),
);

// Оценка влияния ошибки
final impact = errorAnalytics.assessErrorImpact('network_timeout');
```

## Использование

### Интеграция в приложение

1. **Инициализация при старте приложения:**

```dart
class MyApp extends StatefulWidget {
  @override
  _MyAppState createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> with WidgetsBindingObserver {
  final _analytics = AnalyticsService();

  @override
  void initState() {
    super.initState();
    _initializeAnalytics();
    WidgetsBinding.instance.addObserver(this);
  }

  Future<void> _initializeAnalytics() async {
    await _analytics.initialize();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _analytics.endSession();
    } else if (state == AppLifecycleState.resumed) {
      _analytics.initialize();
    }
  }

  @override
  void dispose() {
    _analytics.dispose();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
```

2. **Отслеживание навигации:**

```dart
class MyNavigatorObserver extends NavigatorObserver {
  final _analytics = AnalyticsService();

  @override
  void didPush(Route route, Route? previousRoute) {
    super.didPush(route, previousRoute);
    if (route.settings.name != null) {
      _analytics.trackScreenView(route.settings.name!);
    }
  }
}
```

3. **Отслеживание действий пользователя:**

```dart
ElevatedButton(
  onPressed: () async {
    await AnalyticsService().trackButtonTap(
      buttonName: 'create_budget',
      screen: 'BudgetScreen',
      metadata: {'budget_type': 'monthly'},
    );

    // Ваш код
  },
  child: Text('Create Budget'),
)
```

## База данных

### Миграция

Миграция создается автоматически при запуске приложения. Файл миграции: `alembic/versions/0013_add_analytics_tables.py`

Для применения миграции вручную:

```bash
alembic upgrade head
```

## Тестирование

### Backend тесты

```bash
pytest app/tests/test_analytics_service.py -v
```

### Frontend тесты

```bash
cd mobile_app
flutter test test/services/analytics_service_test.dart
```

## Мониторинг

### Метрики для отслеживания:

1. **Feature Usage**:
   - Количество использований каждой функции
   - Топ используемых функций
   - Время использования функций

2. **Premium Conversion**:
   - Показы paywall
   - Conversion rate
   - Время до конверсии

3. **Behavioral Analytics**:
   - Паттерны расходов
   - Risk score
   - Сезонные тренды

4. **Error Analytics**:
   - Количество ошибок
   - Типы ошибок
   - Влияние ошибок на пользователей

## Безопасность

- Все данные аналитики связаны с пользователем через UUID
- Чувствительные данные не логируются
- Используется JWT авторизация для всех endpoints
- Данные хранятся с шифрованием в PostgreSQL

## Производительность

- Асинхронная обработка событий
- Батчинг запросов к API
- Кэширование предиктивных данных
- Периодическая очистка старых данных (30 дней)

## Roadmap

- [ ] Добавить A/B тестирование
- [ ] Расширить предиктивную аналитику ML моделями
- [ ] Добавить когортный анализ
- [ ] Интеграция с внешними аналитическими сервисами
- [ ] Dashboard для аналитики в админ панели
