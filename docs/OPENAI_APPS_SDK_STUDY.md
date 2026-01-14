# OpenAI Apps SDK - Полное руководство для создания MITA GPT App

## Оглавление
1. [Что такое OpenAI Apps SDK](#что-такое-openai-apps-sdk)
2. [Архитектура системы](#архитектура-системы)
3. [Model Context Protocol (MCP)](#model-context-protocol-mcp)
4. [Компоненты приложения](#компоненты-приложения)
5. [Создание MCP сервера](#создание-mcp-сервера)
6. [UI компоненты и виджеты](#ui-компоненты-и-виджеты)
7. [Аутентификация и OAuth](#аутентификация-и-oauth)
8. [Управление состоянием](#управление-состоянием)
9. [Deployment и хостинг](#deployment-и-хостинг)
10. [Требования к публикации](#требования-к-публикации)
11. [План создания MITA GPT App](#план-создания-mita-gpt-app)

---

## Что такое OpenAI Apps SDK

**OpenAI Apps SDK** - это open-source toolkit, который позволяет разработчикам создавать приложения, работающие нативно внутри ChatGPT.

### Ключевые особенности:
- Приложения интегрируются напрямую в интерфейс ChatGPT
- Построен на основе **MCP (Model Context Protocol)** - открытого стандарта
- Поддерживает любой frontend-фреймворк (React, Vue, Svelte и др.)
- Backend может быть на Python или Node.js/TypeScript
- Приложение состоит из **UI компонентов** (виджетов) и **MCP сервера**

### Доступность:
- **Ноябрь 2025**: Apps доступны в preview для ChatGPT Business, Enterprise и Edu
- Любой разработчик может создавать и тестировать приложения через Apps SDK preview
- Публикация в ChatGPT Apps Directory требует прохождения review

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                         ChatGPT                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐     ┌──────────────────────────────────┐  │
│  │   Conversation   │     │         Widget (iframe)          │  │
│  │                  │     │                                  │  │
│  │  User: "..."     │     │  ┌────────────────────────────┐  │  │
│  │  Assistant: "..."│     │  │    Your UI Component       │  │  │
│  │                  │     │  │    (React/Vue/HTML)        │  │  │
│  │  [Widget Here]   │◄────┼──│                            │  │  │
│  │                  │     │  │    window.openai API       │  │  │
│  └──────────────────┘     │  └────────────────────────────┘  │  │
│                           └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ MCP Protocol (HTTPS/SSE)
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Your MCP Server                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Tools (list_tools, call_tool)                              │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  Resources (widget HTML bundles)                            │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  Your Backend API (FastAPI, Express, etc.)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Database │ External APIs │ Business Logic                      │
└─────────────────────────────────────────────────────────────────┘
```

### Два обязательных компонента:

1. **Web Component (UI)** - HTML/JS/CSS бандл, рендерится в iframe внутри ChatGPT
2. **MCP Server** - определяет capabilities (tools) вашего приложения для ChatGPT

---

## Model Context Protocol (MCP)

MCP - это открытый протокол для подключения языковых моделей к внешним инструментам.

### Три основные capabilities:

#### 1. List Tools
Сервер объявляет список доступных инструментов с JSON Schema контрактами:

```python
@mcp.tool
def get_transactions(
    start_date: str,
    end_date: str,
    category: str | None = None
) -> list[dict]:
    """Получить транзакции пользователя за период."""
    # Ваша логика
    return transactions
```

#### 2. Call Tools
Когда модель выбирает tool, она отправляет `call_tool` запрос:

```json
{
  "method": "call_tool",
  "params": {
    "name": "get_transactions",
    "arguments": {
      "start_date": "2025-01-01",
      "end_date": "2025-01-31"
    }
  }
}
```

#### 3. Return Widgets
Ответ включает `_meta.openai/outputTemplate` для рендеринга UI:

```python
return {
    "content": structured_data,
    "_meta": {
        "openai/outputTemplate": "ui://widget/transactions.html"
    }
}
```

---

## Компоненты приложения

### Структура проекта:

```
mita-gpt-app/
├── src/                          # UI компоненты
│   ├── components/
│   │   ├── TransactionList.tsx
│   │   ├── BudgetChart.tsx
│   │   └── InsightsCard.tsx
│   ├── hooks/
│   │   └── useWidgetState.ts
│   └── main.tsx
├── assets/                       # Собранные бандлы
│   └── widget.html
├── mcp_server/                   # Python MCP сервер
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── transactions.py
│   │   ├── budgets.py
│   │   └── insights.py
│   └── auth.py
├── package.json
├── vite.config.ts
└── requirements.txt
```

---

## Создание MCP сервера

### Python с FastMCP (рекомендуется):

```python
# mcp_server/server.py
from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional
import httpx

mcp = FastMCP(
    name="MITA Finance",
    stateless_http=True  # Требуется для ChatGPT
)

# Pydantic модели для валидации
class TransactionFilter(BaseModel):
    start_date: str
    end_date: str
    category: Optional[str] = None
    limit: int = 50

# Tool с аннотациями
@mcp.tool(
    annotations={
        "readOnlyHint": True,      # Только чтение данных
        "openWorldHint": False     # Не взаимодействует с внешним миром
    }
)
async def get_transactions(
    filter: TransactionFilter,
    auth_token: str = None
) -> dict:
    """
    Получить список транзакций пользователя.

    Возвращает транзакции с категориями, суммами и датами.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.mita.app/v1/transactions",
            headers={"Authorization": f"Bearer {auth_token}"},
            params=filter.dict()
        )
        transactions = response.json()

    return {
        "transactions": transactions,
        "_meta": {
            "openai/outputTemplate": "ui://widget/transactions.html",
            "widgetSessionId": "transactions-view"
        }
    }

@mcp.tool(
    annotations={
        "readOnlyHint": False,     # Изменяет данные
        "destructiveHint": False,  # Не удаляет данные
        "openWorldHint": False
    }
)
async def add_transaction(
    amount: float,
    category: str,
    description: str,
    date: str,
    auth_token: str = None
) -> dict:
    """Добавить новую транзакцию."""
    # Логика добавления
    return {"status": "success", "transaction_id": "..."}

@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def get_budget_insights(
    month: str,
    auth_token: str = None
) -> dict:
    """
    Получить аналитику бюджета за месяц.

    Включает: расходы по категориям, сравнение с бюджетом,
    рекомендации по экономии.
    """
    # Логика аналитики
    return {
        "insights": {...},
        "_meta": {
            "openai/outputTemplate": "ui://widget/insights.html"
        }
    }

# Регистрация UI ресурсов
@mcp.resource("ui://widget/transactions.html")
def get_transactions_widget():
    with open("assets/transactions.html", "r") as f:
        return {
            "content": f.read(),
            "mimeType": "text/html+skybridge"  # Маркер виджета
        }

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
```

### Tool Annotations (критически важно для approval):

| Аннотация | Описание | Когда использовать |
|-----------|----------|-------------------|
| `readOnlyHint: true` | Tool только читает данные | GET запросы, просмотр |
| `readOnlyHint: false` | Tool изменяет данные | POST/PUT/DELETE |
| `destructiveHint: true` | Tool удаляет данные | Удаление транзакций |
| `openWorldHint: true` | Взаимодействует с внешними системами | Публикация, отправка |
| `openWorldHint: false` | Работает только с вашим backend | Внутренние операции |

---

## UI компоненты и виджеты

### window.openai API

Виджеты работают в iframe и общаются с ChatGPT через `window.openai`:

```typescript
// src/hooks/useOpenAI.ts
interface OpenAIGlobals {
  // Данные от tool
  toolInput: any;           // Входные параметры tool
  toolOutput: any;          // Результат tool
  toolResponseMetadata: any;

  // Состояние виджета
  widgetState: any;
  setWidgetState: (state: any) => void;

  // Методы
  callTool: (name: string, args: any) => Promise<any>;
  sendFollowUpMessage: (message: string) => void;
  requestDisplayMode: (mode: 'inline' | 'pip' | 'fullscreen') => void;

  // Файлы
  uploadFile: (file: File) => Promise<string>;
  getFileDownloadUrl: (fileId: string) => string;

  // Контекст
  locale: string;
  theme: 'light' | 'dark';
  displayMode: string;
}

declare global {
  interface Window {
    openai: OpenAIGlobals;
  }
}
```

### React виджет пример:

```tsx
// src/components/TransactionList.tsx
import { useEffect, useState } from 'react';

interface Transaction {
  id: string;
  amount: number;
  category: string;
  description: string;
  date: string;
}

export function TransactionList() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    // Получаем данные из tool output
    const data = window.openai.toolOutput;
    if (data?.transactions) {
      setTransactions(data.transactions);
    }

    // Восстанавливаем состояние виджета
    const savedState = window.openai.widgetState;
    if (savedState?.filter) {
      setFilter(savedState.filter);
    }
  }, []);

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter);
    // Сохраняем состояние для персистентности
    window.openai.setWidgetState({ filter: newFilter });
  };

  const handleRefresh = async () => {
    // Вызываем tool из виджета
    await window.openai.callTool('get_transactions', {
      start_date: '2025-01-01',
      end_date: '2025-01-31',
      category: filter || undefined
    });
  };

  const handleAskAI = () => {
    // Отправляем follow-up сообщение в чат
    window.openai.sendFollowUpMessage(
      `Проанализируй мои расходы за этот период и дай рекомендации`
    );
  };

  const totalAmount = transactions.reduce((sum, t) => sum + t.amount, 0);

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Транзакции</h2>
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => handleFilterChange(e.target.value)}
            className="px-3 py-1 border rounded"
          >
            <option value="">Все категории</option>
            <option value="food">Еда</option>
            <option value="transport">Транспорт</option>
            <option value="entertainment">Развлечения</option>
          </select>
          <button onClick={handleRefresh} className="px-3 py-1 bg-blue-500 text-white rounded">
            Обновить
          </button>
        </div>
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {transactions.map(tx => (
          <div key={tx.id} className="flex justify-between p-2 border-b">
            <div>
              <span className="font-medium">{tx.description}</span>
              <span className="text-sm text-gray-500 ml-2">{tx.category}</span>
            </div>
            <span className={tx.amount < 0 ? 'text-red-500' : 'text-green-500'}>
              {tx.amount.toFixed(2)} лв
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t flex justify-between items-center">
        <span className="font-semibold">
          Итого: {totalAmount.toFixed(2)} лв
        </span>
        <button
          onClick={handleAskAI}
          className="px-4 py-2 bg-green-500 text-white rounded"
        >
          Анализ от AI
        </button>
      </div>
    </div>
  );
}
```

### Display Modes:

```typescript
// Запросить полноэкранный режим для графиков
window.openai.requestDisplayMode('fullscreen');

// Picture-in-Picture для компактного виджета
window.openai.requestDisplayMode('pip');

// Вернуться к inline
window.openai.requestDisplayMode('inline');
```

---

## Аутентификация и OAuth

### OAuth 2.1 Flow с PKCE:

```
1. ChatGPT читает /.well-known/oauth-protected-resource
2. ChatGPT регистрируется через dynamic client registration
3. При первом вызове tool запускается OAuth flow
4. Пользователь авторизуется в вашем сервисе
5. ChatGPT получает access_token
6. Token передается в каждый MCP запрос: Authorization: Bearer <token>
```

### Реализация OAuth endpoint:

```python
# mcp_server/auth.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import jwt

app = FastAPI()

# OAuth Protected Resource Metadata
@app.get("/.well-known/oauth-protected-resource")
async def oauth_metadata():
    return {
        "resource": "https://api.mita.app",
        "authorization_servers": ["https://auth.mita.app"],
        "scopes_supported": [
            "transactions:read",
            "transactions:write",
            "budgets:read",
            "insights:read"
        ]
    }

# Authorization Server Metadata
@app.get("/.well-known/oauth-authorization-server")
async def auth_server_metadata():
    return {
        "issuer": "https://auth.mita.app",
        "authorization_endpoint": "https://auth.mita.app/authorize",
        "token_endpoint": "https://auth.mita.app/token",
        "registration_endpoint": "https://auth.mita.app/register",
        "code_challenge_methods_supported": ["S256"],  # PKCE обязательно!
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"]
    }

# Token validation middleware
async def validate_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header.split(" ")[1]

    try:
        # Валидация JWT
        payload = jwt.decode(
            token,
            key=PUBLIC_KEY,
            algorithms=["RS256"],
            audience="https://api.mita.app",
            issuer="https://auth.mita.app"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Интеграция с существующей MITA auth:

```python
# В MCP tool получаем токен из context
@mcp.tool
async def get_transactions(
    filter: TransactionFilter,
    context: dict = None  # MCP передает context с auth
) -> dict:
    # Извлекаем user_id из токена
    user_id = context.get("user_id")

    # Используем существующий MITA API
    transactions = await mita_api.get_user_transactions(
        user_id=user_id,
        start_date=filter.start_date,
        end_date=filter.end_date
    )

    return {"transactions": transactions}
```

---

## Управление состоянием

### Widget State (локальное состояние виджета):

```typescript
// Состояние сохраняется для конкретного message_id
window.openai.setWidgetState({
  selectedCategory: 'food',
  chartType: 'pie',
  dateRange: { start: '2025-01-01', end: '2025-01-31' }
});

// Восстанавливается при возврате к сообщению
const state = window.openai.widgetState;
```

### widgetSessionId (состояние между turns):

```python
# В MCP server
@mcp.tool
async def update_cart(item_id: str, quantity: int) -> dict:
    return {
        "cart": updated_cart,
        "_meta": {
            "openai/outputTemplate": "ui://widget/cart.html",
            "widgetSessionId": "shopping-cart"  # Связывает turns
        }
    }
```

### Серверное состояние (рекомендуется для production):

```python
# Сохраняем состояние в базе
@mcp.tool
async def save_preferences(preferences: dict, context: dict) -> dict:
    user_id = context.get("user_id")

    await db.user_preferences.upsert(
        user_id=user_id,
        preferences=preferences
    )

    return {"status": "saved"}
```

---

## Deployment и хостинг

### Локальная разработка с ngrok:

```bash
# 1. Запустить MCP сервер
python -m mcp_server.server  # Порт 8000

# 2. Запустить UI dev server
pnpm run dev  # Порт 5173

# 3. Создать туннель
ngrok http 8000

# 4. Настроить переменные для Python SDK
export MCP_ALLOWED_HOSTS="abc123.ngrok-free.app"
export MCP_ALLOWED_ORIGINS="https://abc123.ngrok-free.app"
```

### Production deployment:

```yaml
# docker-compose.yml
version: '3.8'
services:
  mcp-server:
    build: ./mcp_server
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - MITA_API_URL=https://api.mita.app
      - JWT_PUBLIC_KEY=...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  ui-server:
    build: ./ui
    ports:
      - "4444:80"
    volumes:
      - ./assets:/usr/share/nginx/html
```

### Рекомендуемые платформы:
- **Fly.io** - быстрый spin-up, автоматический TLS
- **Render** - простой deployment
- **Railway** - хороший для Python
- **Vercel** - для статических UI assets
- **Cloudflare Workers** - низкая latency

### Чеклист production:
- [ ] HTTPS обязательно
- [ ] Health checks настроены
- [ ] SSE/streaming не буферизируется proxy
- [ ] OAuth endpoints доступны
- [ ] CORS правильно настроен
- [ ] Rate limiting реализован

---

## Требования к публикации

### Технические требования:
1. **Стабильность** - приложение не должно падать или зависать
2. **Низкая latency** - быстрые ответы
3. **Полнота** - никаких demo/trial версий
4. **Корректные аннотации** - readOnlyHint, openWorldHint, destructiveHint

### Privacy требования:
1. **Privacy Policy** - опубликованная политика конфиденциальности
2. **Data minimization** - собирать только необходимые данные
3. **Explicit consent** - пользователь должен понимать что авторизует

### UX принципы:
1. **Focused experience** - узкая специализация
2. **Native feel** - соответствие стилю ChatGPT
3. **Clear value** - понятная польза для пользователя

### Процесс submission:
1. Создать verified OpenAI platform account
2. Тестировать в Developer Mode
3. Подготовить metadata (название, описание, скриншоты)
4. Указать MCP endpoint и auth details
5. Submit на review
6. Получить feedback и исправить если нужно

---

## План создания MITA GPT App

### Фаза 1: Проектирование

#### Tools для MITA:

| Tool | Описание | Annotations |
|------|----------|-------------|
| `get_transactions` | Получить транзакции | readOnly: true |
| `add_transaction` | Добавить транзакцию | readOnly: false |
| `get_budgets` | Получить бюджеты | readOnly: true |
| `update_budget` | Обновить бюджет | readOnly: false |
| `get_insights` | Финансовая аналитика | readOnly: true |
| `get_habits` | Получить привычки | readOnly: true |
| `log_habit` | Залогировать привычку | readOnly: false |
| `get_goals` | Получить цели | readOnly: true |
| `scan_receipt` | Сканировать чек | readOnly: false, openWorld: false |

#### Виджеты:

1. **TransactionList** - список транзакций с фильтрами
2. **BudgetOverview** - обзор бюджета с прогресс-барами
3. **InsightsChart** - графики расходов (pie, bar, line)
4. **HabitTracker** - трекер привычек
5. **GoalProgress** - прогресс по целям
6. **ReceiptScanner** - загрузка и OCR чеков

### Фаза 2: Реализация MCP Server

```python
# mita_gpt_app/server.py
from fastmcp import FastMCP
from mita_api import MitaAPIClient

mcp = FastMCP(name="MITA - Money Intelligence", stateless_http=True)
mita_client = MitaAPIClient()

@mcp.tool(annotations={"readOnlyHint": True})
async def get_financial_summary(month: str, context: dict) -> dict:
    """
    Получить финансовую сводку за месяц.

    Включает: доходы, расходы, баланс, топ категории.
    """
    user_id = context["user_id"]
    summary = await mita_client.get_monthly_summary(user_id, month)

    return {
        "summary": summary,
        "_meta": {
            "openai/outputTemplate": "ui://widget/summary.html",
            "openai/toolInvocation/invoking": "Анализирую ваши финансы..."
        }
    }

@mcp.tool(annotations={"readOnlyHint": True})
async def analyze_spending(
    category: str = None,
    period: str = "month",
    context: dict = None
) -> dict:
    """
    Глубокий анализ расходов с рекомендациями.

    Выявляет паттерны, аномалии и возможности экономии.
    """
    # AI-powered analysis
    analysis = await mita_client.analyze_spending(
        user_id=context["user_id"],
        category=category,
        period=period
    )

    return {
        "analysis": analysis,
        "recommendations": analysis.get("recommendations", []),
        "_meta": {
            "openai/outputTemplate": "ui://widget/analysis.html"
        }
    }
```

### Фаза 3: UI Implementation

```tsx
// Использовать apps-sdk-ui для consistent styling
import { Card, Button, ProgressBar } from '@openai/apps-sdk-ui';

export function BudgetOverview() {
  const budgets = window.openai.toolOutput?.budgets || [];

  return (
    <div className="space-y-4">
      {budgets.map(budget => (
        <Card key={budget.id}>
          <div className="flex justify-between mb-2">
            <span>{budget.category}</span>
            <span>{budget.spent} / {budget.limit} лв</span>
          </div>
          <ProgressBar
            value={budget.spent / budget.limit * 100}
            color={budget.spent > budget.limit ? 'red' : 'green'}
          />
        </Card>
      ))}
    </div>
  );
}
```

### Фаза 4: Auth Integration

Интегрировать с существующей MITA OAuth системой:
- Использовать те же endpoints
- Добавить scopes для ChatGPT
- Реализовать dynamic client registration

### Фаза 5: Testing & Deployment

1. Тестирование в ChatGPT Developer Mode
2. Deploy на production (Fly.io / Render)
3. Подготовка submission materials
4. Submit в ChatGPT Apps Directory

---

## Ресурсы

### Официальная документация:
- [Apps SDK Overview](https://developers.openai.com/apps-sdk/)
- [Quickstart Guide](https://developers.openai.com/apps-sdk/quickstart/)
- [Build MCP Server](https://developers.openai.com/apps-sdk/build/mcp-server/)
- [Build ChatGPT UI](https://developers.openai.com/apps-sdk/build/chatgpt-ui/)
- [Authentication](https://developers.openai.com/apps-sdk/build/auth/)
- [State Management](https://developers.openai.com/apps-sdk/build/state-management/)
- [App Submission Guidelines](https://developers.openai.com/apps-sdk/app-submission-guidelines/)

### GitHub репозитории:
- [openai/openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples) - официальные примеры
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) - Python MCP SDK

### Дополнительные материалы:
- [OpenAI Announcement](https://openai.com/index/introducing-apps-in-chatgpt/)
- [FastMCP Documentation](https://gofastmcp.com/integrations/openai)
- [Stytch Auth Guide](https://stytch.com/blog/guide-to-authentication-for-the-openai-apps-sdk/)

---

*Документ создан: 2026-01-14*
*Версия: 1.0*
