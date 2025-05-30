
from app.agent.gpt_agent_service import GPTAgentService

# Можно сделать через настройки или секреты
GPT = GPTAgentService(api_key="sk-REPLACE_ME", model="gpt-4o")

def explain_day_status(status: str, recommendations: list, user_id: str = None, date: str = None) -> str:
    if status == "green":
        return "Всё в порядке, день в пределах бюджета."
    
    prompt = "Ты финансовый помощник. Пользователь получил статус дня '{status}' на {date}.".format(
        status=status.upper(), date=date or "сегодня"
    )

    rec_text = "Вот рекомендации: " + "; ".join(recommendations) if recommendations else "Без конкретных рекомендаций."
    question = (
        f"{prompt} Объясни, что означает этот статус, и дай короткий совет. "
        f"{rec_text}"
    )

    return GPT.ask([{"role": "user", "content": question}])
