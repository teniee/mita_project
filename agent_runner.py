
import os
from openai import OpenAI
from dotenv import load_dotenv
from app.logic.installment_evaluator import can_user_afford_installment
from app.engine.risk_predictor import evaluate_user_risk

# Загрузка переменных среды
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY)

def run_agent_for_user_message(user_message: str):
    assistant = client.beta.assistants.create(
        name="Finance Advisor Agent",
        instructions="Ты — финансовый AI-советник. Анализируешь риски и рассрочку. Действуешь строго по фактам.",
        model=OPENAI_MODEL,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "can_user_afford_installment",
                    "description": "Проверяет, может ли пользователь позволить рассрочку",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "price": {"type": "number"},
                            "months": {"type": "integer"}
                        },
                        "required": ["user_id", "price", "months"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "evaluate_user_risk",
                    "description": "Оценивает финансовый риск пользователя",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"}
                        },
                        "required": ["user_id"]
                    }
                }
            }
        ]
    )

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    import time
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status == "requires_action":
            tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []

            for call in tool_calls:
                name = call.function.name
                args = eval(call.function.arguments)

                if name == "can_user_afford_installment":
                    result = can_user_afford_installment(**args)
                elif name == "evaluate_user_risk":
                    result = evaluate_user_risk(**args)
                else:
                    result = {"error": "unknown function"}

                tool_outputs.append({
                    "tool_call_id": call.id,
                    "output": result
                })

            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
        else:
            time.sleep(1)

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in reversed(messages.data):
        if msg.role == "assistant":
            return msg.content[0].text.value

    return "Агент не дал ответа."

if __name__ == "__main__":
    msg = "Оцени мой риск, если я user_001"
    print(run_agent_for_user_message(msg))
