
from app.agent.gpt_agent_service import GPTAgentService

# API key should be configured via settings or secrets
GPT = GPTAgentService(api_key="sk-REPLACE_ME", model="gpt-4o")

def explain_day_status(status: str, recommendations: list, user_id: str = None, date: str = None) -> str:
    if status == "green":
        return "Everything is on track for today."
    
    prompt = "You are a financial assistant. The user received a day status '{status}' on {date}.".format(
        status=status.upper(), date=date or "today"
    )

    rec_text = "Recommendations: " + "; ".join(recommendations) if recommendations else "No specific tips."
    question = (
        f"{prompt} Explain what this status means and give a short tip. "
        f"{rec_text}"
    )

    return GPT.ask([{"role": "user", "content": question}])
