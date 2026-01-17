# OpenAI Apps SDK - Полное руководство для создания MITA GPT App

## Оглавление
1. [Что такое OpenAI Apps SDK](#что-такое-openai-apps-sdk)
2. [Архитектура системы](#архитектура-системы)
3. [Планирование Use Case](#планирование-use-case)
4. [Model Context Protocol (MCP)](#model-context-protocol-mcp)
5. [Определение Tools](#определение-tools)
6. [Компоненты приложения](#компоненты-приложения)
7. [Создание MCP сервера](#создание-mcp-сервера)
8. [UI компоненты и виджеты](#ui-компоненты-и-виджеты)
9. [UX принципы](#ux-принципы)
10. [UI Guidelines](#ui-guidelines)
11. [Аутентификация и OAuth](#аутентификация-и-oauth)
12. [Управление состоянием](#управление-состоянием)
13. [Оптимизация Metadata](#оптимизация-metadata)
14. [Security & Privacy](#security--privacy)
15. [Deployment и хостинг](#deployment-и-хостинг)
16. [Тестирование](#тестирование)
17. [Troubleshooting](#troubleshooting)
18. [Требования к публикации](#требования-к-публикации)
19. [План создания MITA GPT App](#план-создания-mita-gpt-app)

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

## Планирование Use Case

> "Every successful Apps SDK app starts with a crisp understanding of what the user is trying to accomplish."

### Discovery механика

Discovery в ChatGPT **model-driven**: ассистент выбирает ваше приложение когда tool metadata, описания и история использования соответствуют промпту пользователя.

### Фаза исследования

Перед разработкой соберите:
- **User interviews** - jobs-to-be-done, терминология, источники данных
- **Prompt sampling** - прямые запросы ("покажи мой бюджет") и косвенные ("на что я трачу больше всего?")
- **System constraints** - compliance требования, offline данные, rate limits

### Критерии оценки (Checklist) ✅

Ответьте на эти вопросы перед разработкой:

| Критерий | Вопрос |
|----------|--------|
| **Conversational value** | Использует ли хотя бы одна capability сильные стороны ChatGPT (NLP, контекст, multi-turn)? |
| **Beyond base ChatGPT** | Предоставляет ли app новые знания, действия или презентацию недоступные без него? |
| **Atomic actions** | Tools неделимы, self-contained, с explicit inputs/outputs? |
| **End-to-end completion** | Можно ли завершить задачу не покидая ChatGPT? |
| **Performance** | Достаточно быстрые ответы для ритма чата? |
| **Discoverability** | Легко ли представить промпты где модель уверенно выберет этот app? |
| **Platform fit** | Использует ли app core behaviors платформы? |

### Хорошие примеры ✅

```
✓ Забронировать поездку
✓ Заказать еду
✓ Проверить доступность
✓ Отследить доставку
✓ Показать финансовую сводку
✓ Добавить транзакцию
```

**Характеристики:** conversational, time-bound, легко визуализировать, clear CTA.

### Плохие примеры ❌

```
✗ Дублирование контента с сайта
✗ Сложные multi-step workflows
✗ Реклама или upsells
✗ Показ sensitive данных в карточках
✗ Дублирование функций ChatGPT (например, recreating composer)
```

### Приоритизация

Ранжируйте use cases по **user impact** и **implementation effort**:
- **P0** - один high-confidence сценарий для первого релиза
- **P1** - расширение после подтверждения engagement

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

#### 3. Return Components
Ответ включает `_meta` для рендеринга UI:

```python
return {
    "content": structured_data,
    "_meta": {
        "openai/outputTemplate": "ui://widget/transactions.html",
        "openai/widgetAccessible": True,
        "openai/visibility": "public"
    }
}
```

### _meta поля

| Поле | Описание |
|------|----------|
| `openai/outputTemplate` | URI ресурса для рендеринга виджета |
| `openai/widgetAccessible` | Доступен ли виджет |
| `openai/visibility` | `"public"` или `"private"` (скрыт от модели) |
| `widgetSessionId` | ID для связи состояния между turns |
| `openai/toolInvocation/invoking` | Сообщение во время загрузки |

### Resources

UI бандлы экспортируются как MCP resources с `mimeType: "text/html+skybridge"`:

```python
@mcp.resource("ui://widget/transactions.html")
def get_widget():
    return {
        "content": html_content,
        "mimeType": "text/html+skybridge"  # Маркер для ChatGPT
    }
```

---

## Определение Tools

### Структура Tool Schema

```python
server.registerTool(
    "get_budget_summary",
    {
        "title": "Get Budget Summary",
        "description": "Use this when the user wants to see their budget overview for a specific month. Do not use for transaction history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month in YYYY-MM format"
                },
                "include_insights": {
                    "type": "boolean",
                    "default": True
                }
            },
            "required": ["month"],
            "additionalProperties": False
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "total_budget": {"type": "number"},
                "spent": {"type": "number"},
                "categories": {"type": "array"}
            }
        },
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": False
        }
    },
    handler_function
)
```

### Tool Annotations (КРИТИЧЕСКИ ВАЖНО!)

> ⚠️ **"Incorrect or missing action labels are a common cause of rejection."**

| Аннотация | Описание | Default | Когда использовать |
|-----------|----------|---------|-------------------|
| `readOnlyHint` | Tool не изменяет состояние | `false` | GET запросы, просмотр данных |
| `destructiveHint` | Tool может удалять данные | `false` | DELETE операции |
| `idempotentHint` | Повторные вызовы не имеют эффекта | `false` | Только когда readOnlyHint=false |
| `openWorldHint` | Взаимодействует с внешними API/web | `true` | Публикации, внешние сервисы |

### Примеры правильных аннотаций:

```python
# ✅ Только чтение
@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
async def get_transactions(...): ...

# ✅ Создание (не деструктивно)
@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False})
async def add_transaction(...): ...

# ✅ Удаление
@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False})
async def delete_transaction(...): ...

# ✅ Внешняя интеграция
@mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
async def share_to_social(...): ...
```

### Best Practices для Tools

1. **One job per tool** - каждый tool фокусируется на одном read или write действии
2. **Separate read/write** - разделяйте чтение и запись для confirmation flows
3. **"Use this when..."** - начинайте description с этой фразы
4. **Disallowed cases** - указывайте когда НЕ использовать tool
5. **Explicit schemas** - определяйте все параметры, типы, enums, defaults

---

## Компоненты приложения

### Структура проекта:

```
mita-gpt-app/
├── src/                          # UI компоненты
│   ├── components/
│   │   ├── TransactionList.tsx
│   │   ├── BudgetChart.tsx
│   │   ├── InsightsCard.tsx
│   │   └── Carousel.tsx
│   ├── hooks/
│   │   ├── useWidgetState.ts
│   │   └── useOpenAI.ts
│   └── main.tsx
├── assets/                       # Собранные бандлы
│   ├── widget.html
│   └── widget.js
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

### Типы компонентов:

| Компонент | Описание | Use Case |
|-----------|----------|----------|
| **Card** | Базовая карточка | Единичные данные |
| **List** | Ранжированный список | Транзакции, история |
| **Carousel** | Горизонтальный скроллер | Media-heavy layouts |
| **Map** | Geo данные с маркерами | Локации |
| **Chart** | Графики и диаграммы | Аналитика |
| **Form** | Ввод данных | Добавление транзакций |

---

## Создание MCP сервера

### Установка SDK:

```bash
# TypeScript / Node
npm install @modelcontextprotocol/sdk zod

# Python
pip install mcp
# или для FastMCP
pip install fastmcp
```

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
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def get_transactions(
    filter: TransactionFilter,
    auth_token: str = None
) -> dict:
    """
    Use this when the user wants to see their transaction history.

    Returns transactions with categories, amounts, and dates.
    Do not use for budget summaries or analytics.
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
        "readOnlyHint": False,
        "destructiveHint": False,
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
    """
    Use this when the user wants to add a new expense or income.

    Do not use for editing existing transactions.
    """
    # Логика добавления
    return {"status": "success", "transaction_id": "..."}

# Регистрация UI ресурсов
@mcp.resource("ui://widget/transactions.html")
def get_transactions_widget():
    with open("assets/transactions.html", "r") as f:
        return {
            "content": f.read(),
            "mimeType": "text/html+skybridge"
        }

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
```

### TypeScript пример:

```typescript
import { MCPServer } from "@modelcontextprotocol/sdk";
import { z } from "zod";

const server = new MCPServer({
  name: "MITA Finance",
  version: "1.0.0"
});

server.registerTool(
  "get_transactions",
  {
    title: "Get Transactions",
    description: "Use this when the user wants to see their transaction history.",
    inputSchema: {
      type: "object",
      properties: {
        startDate: { type: "string" },
        endDate: { type: "string" },
        category: { type: "string" }
      },
      required: ["startDate", "endDate"]
    },
    annotations: {
      readOnlyHint: true
    }
  },
  async (params) => {
    const transactions = await fetchTransactions(params);
    return {
      content: transactions,
      _meta: {
        "openai/outputTemplate": "ui://widget/transactions.html"
      }
    };
  }
);

server.start({ port: 8000 });
```

---

## UI компоненты и виджеты

### window.openai API

Виджеты работают в iframe и общаются с ChatGPT через `window.openai`:

```typescript
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
  openExternal: (url: string) => void;

  // Файлы
  uploadFile: (file: File) => Promise<string>;
  getFileDownloadUrl: (fileId: string) => string;

  // Контекст
  locale: string;
  theme: 'light' | 'dark';
  displayMode: string;
}
```

### React виджет пример:

```tsx
import { useEffect, useState } from 'react';
import { useWidgetState, useOpenAiGlobal } from './hooks';

export function TransactionList() {
  const [filter, setFilter] = useWidgetState('filter', '');
  const transactions = useOpenAiGlobal('toolOutput')?.transactions || [];
  const theme = useOpenAiGlobal('theme');

  const handleRefresh = async () => {
    await window.openai.callTool('get_transactions', {
      start_date: '2025-01-01',
      end_date: '2025-01-31',
      category: filter || undefined
    });
  };

  const handleAskAI = () => {
    window.openai.sendFollowUpMessage(
      `Проанализируй мои расходы за этот период`
    );
  };

  const handleExpand = () => {
    window.openai.requestDisplayMode('fullscreen');
  };

  return (
    <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}>
      {/* UI */}
    </div>
  );
}
```

### Display Modes:

| Mode | Описание | Use Case |
|------|----------|----------|
| `inline` | Внутри карточки в чате | Компактные данные |
| `pip` | Picture-in-Picture | Компактный виджет поверх |
| `fullscreen` | Полноэкранный | Графики, карты, формы |

```typescript
// Запросить режим
window.openai.requestDisplayMode('fullscreen');

// Проверить текущий
const mode = window.openai.displayMode;
```

---

## UX принципы

> "The goal is to design experiences that feel consistent and useful while extending what you can do in ChatGPT conversations."

### Ключевые принципы:

#### 1. Focus on Core Jobs
- Не копируйте весь сайт/app
- Выделите несколько atomic actions
- Минимум inputs/outputs для уверенного решения модели

#### 2. Support Multiple Entry Points
Пользователи приходят по-разному:
- **Open-ended**: "Помоги спланировать бюджет"
- **Direct commands**: "Покажи транзакции за январь"
- **First-run**: Нужен onboarding

#### 3. Composability
- Actions = маленькие reusable blocks
- Модель может комбинировать с другими apps
- Если не можете описать benefit работы в ChatGPT - iterate

#### 4. Native Feel
- UI не должен выглядеть как external iframe
- Respect layout, margins, color themes ChatGPT
- Цель: улучшить conversation, не прервать

### Что делать ✅

- Booking a ride
- Ordering food
- Checking availability
- Tracking delivery
- Показ финансовой сводки
- Quick data entry

### Чего избегать ❌

- Long-form static content
- Complex multi-step workflows
- Ads, upsells, irrelevant messaging
- Sensitive data в карточках
- Дублирование ChatGPT functions

---

## UI Guidelines

### Design System

Используйте **Apps SDK UI** для consistent styling:
- Design tokens (colors, typography, spacing)
- Tailwind 4 integration
- Accessible components на Radix primitives

```bash
npm install @openai/apps-sdk-ui
```

### Typography

- Используйте **system fonts** (SF Pro на iOS, Roboto на Android)
- Inherit system font stack
- **НЕ** используйте custom fonts даже в fullscreen

```css
font-family: system-ui, -apple-system, BlinkMacSystemFont,
             'Segoe UI', Roboto, sans-serif;
```

### Spacing & Layout

- Consistent margins, padding, alignment
- System grid spacing для cards, collections
- Respect system corner radius
- **NO nested scrolling** - cards должны auto-fit content

### Colors

- Используйте system colors для text, icons, dividers
- Brand accents (logos, icons) - OK
- **НЕ** override backgrounds или text colors
- **НЕ** custom gradients/patterns

### Cards

- **Max 2 actions** per card (1 primary CTA + 1 optional secondary)
- Не включайте tabs, drill-ins, deep navigation
- Split complex UI в separate cards/tool actions

### Carousel Guidelines

- **3-8 items** для scannability
- Title для каждого item
- Max 3 lines metadata
- Single optional CTA per card
- Consistent visual hierarchy

### Icons

- Monochromatic и outlined
- Fit ChatGPT's visual world
- **НЕ** включайте logo в response (ChatGPT добавит автоматически)

### Accessibility (ОБЯЗАТЕЛЬНО)

- Min contrast ratio (WCAG AA)
- Alt text для всех images
- Support text resizing без breaking layouts
- Keyboard navigation

---

## Аутентификация и OAuth

### OAuth 2.1 Flow с PKCE:

```
1. ChatGPT читает /.well-known/oauth-protected-resource
2. ChatGPT регистрируется через dynamic client registration
3. При первом вызове tool запускается OAuth flow
4. Пользователь авторизуется и дает consent
5. ChatGPT получает access_token
6. Token передается в каждый MCP запрос: Authorization: Bearer <token>
```

### Обязательные требования:

- **PKCE support** - `code_challenge_methods_supported: ["S256"]`
- Без этого ChatGPT откажется завершать flow

### OAuth Metadata endpoints:

```python
# /.well-known/oauth-protected-resource
{
    "resource": "https://api.mita.app",
    "authorization_servers": ["https://auth.mita.app"],
    "scopes_supported": [
        "transactions:read",
        "transactions:write",
        "budgets:read"
    ]
}

# /.well-known/oauth-authorization-server
{
    "issuer": "https://auth.mita.app",
    "authorization_endpoint": "https://auth.mita.app/authorize",
    "token_endpoint": "https://auth.mita.app/token",
    "registration_endpoint": "https://auth.mita.app/register",
    "code_challenge_methods_supported": ["S256"],
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code", "refresh_token"]
}
```

### Token Validation (ваша ответственность):

```python
async def validate_token(request: Request):
    token = extract_bearer_token(request)

    # 1. Signature validation (JWKS)
    # 2. Issuer matching (iss)
    # 3. Audience matching (aud)
    # 4. Expiry check (exp/nbf)
    # 5. Scope enforcement
    # 6. App-specific policy

    if invalid:
        raise HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
```

### Consent Screen

ChatGPT показывает built-in consent screen:
- Что app будет access
- Как данные shared
- Пользователь должен понять что авторизует

---

## Управление состоянием

### Три уровня состояния:

#### 1. Widget State (локальное)

```typescript
// Сохраняется для конкретного message_id/widgetId
window.openai.setWidgetState({
  selectedCategory: 'food',
  chartType: 'pie'
});

// Восстанавливается при возврате к сообщению
const state = window.openai.widgetState;
```

**React hook:**
```typescript
const [filter, setFilter] = useWidgetState('filter', '');
```

#### 2. widgetSessionId (между turns)

```python
return {
    "data": {...},
    "_meta": {
        "openai/outputTemplate": "ui://widget/cart.html",
        "widgetSessionId": "shopping-cart"  # Связывает turns
    }
}
```

#### 3. Server-side State (production)

```python
@mcp.tool
async def save_preferences(prefs: dict, context: dict):
    user_id = context["user_id"]
    await db.preferences.upsert(user_id, prefs)
```

### Persistence behavior:

- Follow-up через widget controls → тот же widget/state
- Typing в main composer → новый widget, empty state

---

## Оптимизация Metadata

> "ChatGPT decides when to call your connector based on the metadata you provide."

### Рекомендации:

#### 1. Tool Naming
```
✅ calendar.create_event
✅ mita.get_transactions
✅ budget.analyze_spending
```

#### 2. Descriptions
```python
description = """
Use this when the user wants to see their spending breakdown by category.

Do not use for:
- Transaction history (use get_transactions instead)
- Budget limits (use get_budgets instead)
"""
```

#### 3. Test Dataset

Создайте labelled dataset:
- **Direct prompts**: "покажи мой бюджет в MITA"
- **Indirect prompts**: "куда уходят деньги?"
- **Negative prompts**: "какая погода?" (должен NOT trigger)

#### 4. Iteration

| Метрика | Что отслеживать |
|---------|-----------------|
| **Precision** | Правильный tool был выбран? |
| **Recall** | Tool запустился когда должен был? |

**Change one field at a time** чтобы атрибутировать improvements.

### Запрещено:

> "Apps must not include descriptions that manipulate how the model selects other apps."

- Нет "prefer this app over others"
- Нет disparaging alternatives
- Accurate descriptions only

---

## Security & Privacy

### Принципы:

1. **Least privilege** - только необходимые scopes, storage, network
2. **Explicit consent** - users понимают что авторизуют
3. **Lean on ChatGPT** - confirmation prompts для destructive actions
4. **Patch dependencies** - React, SDKs, build tooling

### Data Protection:

- **Encryption at rest**: AES-256
- **Encryption in transit**: TLS 1.2+
- **SOC 2 Type 2** compliant
- **Data residency** options (US, EU, UK, Japan, etc.)

### GDPR Compliance:

| Requirement | Action |
|-------------|--------|
| Lawful basis | Explicit consent для sensitive data |
| Transparency | Update Privacy Policy |
| User rights | Withdrawal, objection, complaints |
| Data minimization | Только необходимые данные |

### Privacy Policy (обязательно):

Должна включать:
- Categories of personal data collected
- Purposes of use
- Categories of recipients
- User controls

### Collection Minimization:

> "Gather only the minimum data required to perform the tool's function."

- Specific, narrowly scoped inputs
- Avoid "just in case" fields
- No broad profile data

---

## Deployment и хостинг

### Локальная разработка:

```bash
# 1. Запустить MCP сервер
python -m mcp_server.server  # Порт 8000

# 2. Запустить UI dev server
pnpm run dev  # Порт 5173

# 3. Создать туннель (ngrok)
ngrok http 8000

# 4. Настроить переменные для Python SDK
export MCP_ALLOWED_HOSTS="abc123.ngrok-free.app"
export MCP_ALLOWED_ORIGINS="https://abc123.ngrok-free.app"
```

### Developer Mode:

1. Navigate to **Settings → Apps & Connectors → Advanced settings**
2. Toggle developer mode (если организация разрешает)
3. Click **Create** для добавления connector
4. Provide ngrok URL с `/mcp` path

### Production Deployment:

**Рекомендуемые платформы:**
- **Fly.io** - быстрый spin-up, auto TLS
- **Render** - простой deployment
- **Railway** - хороший для Python
- **Google Cloud Run** - scale-to-zero
- **Azure Container Apps** - enterprise

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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
```

### Production Checklist:

- [ ] HTTPS обязательно
- [ ] `/mcp` endpoint responsive
- [ ] Streaming responses supported
- [ ] SSE не буферизируется proxy
- [ ] Health checks настроены
- [ ] OAuth endpoints доступны
- [ ] Proper HTTP status codes

---

## Тестирование

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector@latest \
  --server-url http://localhost:8000/mcp \
  --transport http
```

- List Tools
- Call Tool
- Inspect raw requests/responses
- Renders components inline

### Testing in ChatGPT

1. Link app в **Settings → Connectors → Developer mode**
2. Toggle on в new conversation
3. Run golden prompt set:
   - Direct prompts
   - Indirect prompts
   - Negative prompts
4. Record: tool selection, arguments, confirmation prompts

### API Playground

1. Open API Playground
2. **Tools → Add → MCP Server**
3. Provide HTTPS endpoint
4. Test prompts, inspect JSON

### Checklist:

| Area | What to Test |
|------|--------------|
| **Tool correctness** | Right data returned |
| **Component UX** | Renders properly, state works |
| **Discovery precision** | Model selects right tool |
| **Auth flow** | OAuth completes |
| **Error handling** | Graceful failures |

---

## Troubleshooting

### Common Issues:

#### No tools listed
```
✓ Server is running
✓ Connecting to /mcp endpoint
✓ Correct port in connector URL
```

#### Structured content only, no component
```
✓ _meta["openai/outputTemplate"] set
✓ Resource registered with mimeType: "text/html+skybridge"
✓ No CSP errors
```

#### Schema mismatch errors
```
✓ Pydantic/TypeScript models match advertised schema
✓ Regenerate types after changes
```

#### Widget fails to load
```
✓ Check browser console for CSP violations
✓ HTML inlines compiled JS
✓ All dependencies bundled
```

#### Tool never triggers
```
✓ Rewrite descriptions with "Use this when..."
✓ Update starter prompts
✓ Test with golden prompt set
```

#### Wrong tool selected
```
✓ Add clarifying details to similar tools
✓ Specify disallowed scenarios
✓ Split large tools into smaller ones
```

### HTTP Errors:

| Code | Meaning | Fix |
|------|---------|-----|
| 403 | Access denied | Check auth, CORS |
| 424 | Unable to load tools | Server connectivity |
| 401 | Token invalid | Validate token, refresh |

### Transport:

- **Streamable HTTP** рекомендуется
- SSE также поддерживается
- Проверьте что proxy не буферизирует

---

## Требования к публикации

### Организационные требования:

- **Verified OpenAI platform account**
- **Owner role** в организации
- **Global data residency** (EU projects пока не поддерживаются)

### Технические требования:

1. **Стабильность** - no crashes, hangs, inconsistent behavior
2. **Низкая latency** - быстрые ответы
3. **Полнота** - никаких demo/trial версий
4. **Корректные аннотации** - readOnlyHint, openWorldHint, destructiveHint

### Privacy требования:

1. **Published Privacy Policy** с:
   - Categories of personal data
   - Purposes of use
   - Categories of recipients
   - User controls
2. **Data minimization**
3. **Explicit consent**

### Commerce ограничения:

> "Apps may conduct commerce only for physical goods."

**Запрещено:**
- Digital products
- Subscriptions
- Digital content
- Tokens/credits

### Submission Materials:

1. MCP connectivity details
2. Testing guidelines
3. Directory metadata (name, description, screenshots)
4. Country availability
5. **Demo account** (login/password с sample data)

### Common Rejection Reasons:

| Reason | How to Avoid |
|--------|--------------|
| Missing/incorrect annotations | Double-check all hints, provide justification |
| Demo account issues | No 2FA, no additional signup |
| Privacy policy issues | Complete, published policy |
| Age appropriateness | Suitable for 13+ |
| Manipulation | No "prefer this app" in descriptions |

### Review Timeline:

- **Variable** - может занять недели
- Email notification при approval/rejection
- Rationale предоставляется при rejection
- Можно appeal через email

---

## План создания MITA GPT App

### Фаза 1: Use Case Definition

#### Target Use Cases:

| Priority | Use Case | Tool |
|----------|----------|------|
| P0 | Просмотр транзакций | `get_transactions` |
| P0 | Добавление транзакции | `add_transaction` |
| P0 | Обзор бюджета | `get_budget_summary` |
| P1 | Финансовая аналитика | `analyze_spending` |
| P1 | Сканирование чеков | `scan_receipt` |
| P2 | Трекер привычек | `get_habits`, `log_habit` |

#### Golden Prompts:

**Direct:**
- "Покажи мои транзакции за январь в MITA"
- "Добавь расход 50 лв на еду"
- "Какой у меня бюджет на развлечения?"

**Indirect:**
- "На что я трачу больше всего?"
- "Сколько я потратил в этом месяце?"
- "Помоги спланировать бюджет"

**Negative:**
- "Какая погода?" (should NOT trigger)
- "Напиши код" (should NOT trigger)

### Фаза 2: Tools Definition

```python
# Tools с правильными аннотациями

@mcp.tool(annotations={
    "readOnlyHint": True,
    "openWorldHint": False
})
async def get_transactions(
    start_date: str,
    end_date: str,
    category: str = None,
    limit: int = 50
) -> dict:
    """
    Use this when the user wants to see their transaction history.

    Returns transactions with amounts, categories, descriptions, and dates.

    Do not use for:
    - Budget summaries (use get_budget_summary)
    - Spending analytics (use analyze_spending)
    """

@mcp.tool(annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "openWorldHint": False
})
async def add_transaction(
    amount: float,
    category: str,
    description: str,
    date: str = None  # defaults to today
) -> dict:
    """
    Use this when the user wants to add a new expense or income.

    Positive amount = income, negative = expense.

    Do not use for editing or deleting existing transactions.
    """

@mcp.tool(annotations={
    "readOnlyHint": True,
    "openWorldHint": False
})
async def get_budget_summary(
    month: str,
    include_insights: bool = True
) -> dict:
    """
    Use this when the user wants to see their budget overview.

    Returns budget limits, spent amounts, and remaining for each category.

    Do not use for transaction history.
    """

@mcp.tool(annotations={
    "readOnlyHint": True,
    "openWorldHint": False
})
async def analyze_spending(
    period: str = "month",
    category: str = None
) -> dict:
    """
    Use this when the user wants AI-powered spending analysis.

    Returns patterns, anomalies, and savings recommendations.
    """

@mcp.tool(annotations={
    "readOnlyHint": False,
    "destructiveHint": True,
    "openWorldHint": False
})
async def delete_transaction(transaction_id: str) -> dict:
    """
    Use this when the user explicitly asks to delete a transaction.

    Requires confirmation. Cannot be undone.
    """
```

### Фаза 3: Widgets Design

#### TransactionList Widget

```tsx
// Inline mode - компактный список
export function TransactionList() {
  const transactions = window.openai.toolOutput?.transactions || [];
  const [filter, setFilter] = useWidgetState('filter', '');

  return (
    <div className="space-y-2">
      <FilterBar value={filter} onChange={setFilter} />
      <TransactionCards items={transactions} />
      <SummaryFooter transactions={transactions} />
      <ActionButtons onAnalyze={handleAnalyze} onExpand={handleExpand} />
    </div>
  );
}
```

#### BudgetOverview Widget

```tsx
// С progress bars и insights
export function BudgetOverview() {
  const data = window.openai.toolOutput;

  return (
    <div className="space-y-4">
      <TotalBudgetCard total={data.total} spent={data.spent} />
      <CategoryBudgets categories={data.categories} />
      {data.insights && <InsightsCard insights={data.insights} />}
    </div>
  );
}
```

### Фаза 4: Auth Integration

1. Extend существующий MITA OAuth:
   - Add ChatGPT scopes
   - Implement dynamic client registration
   - Ensure PKCE support (S256)

2. OAuth metadata endpoints:
   - `/.well-known/oauth-protected-resource`
   - `/.well-known/oauth-authorization-server`

### Фаза 5: Testing

1. **Local testing** с MCP Inspector
2. **ChatGPT Developer Mode** testing
3. **Golden prompt validation**
4. **Auth flow testing**
5. **Error handling testing**

### Фаза 6: Deployment & Submission

1. Deploy на Fly.io или Render
2. Prepare demo account с sample data
3. Write comprehensive testing guidelines
4. Submit для review
5. Address feedback, iterate

---

## Ресурсы

### Официальная документация:
- [Apps SDK Overview](https://developers.openai.com/apps-sdk/)
- [Quickstart Guide](https://developers.openai.com/apps-sdk/quickstart/)
- [Research Use Cases](https://developers.openai.com/apps-sdk/plan/use-case/)
- [Define Tools](https://developers.openai.com/apps-sdk/plan/tools/)
- [Design Components](https://developers.openai.com/apps-sdk/plan/components/)
- [Build MCP Server](https://developers.openai.com/apps-sdk/build/mcp-server/)
- [Build ChatGPT UI](https://developers.openai.com/apps-sdk/build/chatgpt-ui/)
- [Authentication](https://developers.openai.com/apps-sdk/build/auth/)
- [State Management](https://developers.openai.com/apps-sdk/build/state-management/)
- [UX Principles](https://developers.openai.com/apps-sdk/concepts/ux-principles/)
- [UI Guidelines](https://developers.openai.com/apps-sdk/concepts/ui-guidelines/)
- [Optimize Metadata](https://developers.openai.com/apps-sdk/guides/optimize-metadata/)
- [Security & Privacy](https://developers.openai.com/apps-sdk/guides/security-privacy/)
- [Deploy](https://developers.openai.com/apps-sdk/deploy/)
- [Testing](https://developers.openai.com/apps-sdk/deploy/testing/)
- [Troubleshooting](https://developers.openai.com/apps-sdk/deploy/troubleshooting/)
- [App Submission Guidelines](https://developers.openai.com/apps-sdk/app-submission-guidelines/)
- [Reference](https://developers.openai.com/apps-sdk/reference/)

### GitHub репозитории:
- [openai/openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples) - официальные примеры
- [openai/apps-sdk-ui](https://github.com/openai/apps-sdk-ui) - UI components library
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) - Python MCP SDK
- [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) - TypeScript MCP SDK

### Дополнительные материалы:
- [OpenAI Announcement](https://openai.com/index/introducing-apps-in-chatgpt/)
- [Developers Can Now Submit Apps](https://openai.com/index/developers-can-now-submit-apps-to-chatgpt/)
- [Developer Mode Help](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [Apps SDK UI Storybook](https://openai.github.io/apps-sdk-ui/)
- [Stytch Auth Guide](https://stytch.com/blog/guide-to-authentication-for-the-openai-apps-sdk/)
- [Render Deployment Guide](https://render.com/blog/building-with-the-openai-apps-sdk-a-field-guide)

---

*Документ создан: 2026-01-17*
*Версия: 2.0 (расширенная)*
