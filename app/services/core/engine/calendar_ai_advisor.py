from app.agent.gpt_agent_service import GPTAgentService
from app.services.template_service import AIAdviceTemplateService

# API key should be configured via settings or secrets


def explain_day_status(
    status: str, recommendations: list, db, user_id: str = None, date: str = None
) -> str:
    if status == "green":
        return "Everything is on track for today."

    tmpl_service = AIAdviceTemplateService(db)
    template = tmpl_service.get("day_status_prompt")
    system_prompt = tmpl_service.get("system_prompt")
    gpt = GPTAgentService(
        api_key="sk-REPLACE_ME", model="gpt-4o", system_prompt=system_prompt
    )
    if template:
        prompt = template.format(status=status.upper(), date=date or "today")
    else:
        prompt = "You are a financial assistant. The user received a day status '{status}' on {date}.".format(
            status=status.upper(),
            date=date or "today",
        )

    rec_text = (
        "Recommendations: " + "; ".join(recommendations)
        if recommendations
        else "No specific tips."
    )
    question = (
        f"{prompt} Explain what this status means and give a short tip. " f"{rec_text}"
    )

    return gpt.ask([{"role": "user", "content": question}])
