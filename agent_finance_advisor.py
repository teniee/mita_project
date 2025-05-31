
import os
from openai import OpenAI
from dotenv import load_dotenv

# Загрузка API-ключа
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Инструмент: Анализ рассрочки
installment_tool = {
    "type": "function",
    "function": {
        "name": "can_user_afford_installment",
        "description": "Анализирует, может ли пользователь безопасно взять товар в рассрочку.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Идентификатор пользователя"
                },
                "price": {
                    "type": "number",
                    "description": "Цена товара"
                },
                "months": {
                    "type": "integer",
                    "description": "Срок в месяцах"
                }
            },
            "required": ["user_id", "price", "months"]
        }
    }
}

# Инструмент: Анализ риска
risk_tool = {
    "type": "function",
    "function": {
        "name": "evaluate_user_risk",
        "description": "Оценивает уровень финансового риска пользователя.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "ID пользователя"
                }
            },
            "required": ["user_id"]
        }
    }
}

# Создание агента
assistant = client.beta.assistants.create(
    name="Finance Advisor Agent",
    instructions="""
Ты — финансовый AI-советник.
Анализируешь риски, поведение и стабильность.
Рекомендуешь только разумные финансовые действия, объясняешь свои выводы.
""",
    model="gpt-4o",
    tools=[installment_tool, risk_tool]
)

# Создание thread и запуск
thread = client.beta.threads.create()
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Какой у меня финансовый риск?"
)

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
)

print("Assistant ID:", assistant.id)
print("Thread ID:", thread.id)
print("Run ID:", run.id)
