from app.agent.gpt_agent_service import GPTAgentService
from app.core.config import settings

# Можно сделать через настройки или секреты
GPT = GPTAgentService(
    api_key=settings.openai_api_key,
    model=settings.openai_model,
)


def explain_day_status(
    status: str, recommendations: list, user_id: str = None, date: str = None
) -> str:
    if status == "green":
        return "Всё в порядке, день в пределах бюджета."

    prompt = (
        "Ты финансовый помощник. Пользователь получил статус дня "
        "'{status}' на {date}.".format(
            status=status.upper(),
            date=date or "сегодня",
        )
    )

    rec_text = (
        "Вот рекомендации: " + "; ".join(recommendations)
        if recommendations
        else "Без конкретных рекомендаций."
    )
    question = (
        f"{prompt} Объясни, что означает этот статус, и дай короткий совет. "
        f"{rec_text}"
    )

    return GPT.ask([{"role": "user", "content": question}])
