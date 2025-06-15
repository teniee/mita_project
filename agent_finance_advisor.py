
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Installment analysis tool
installment_tool = {
    "type": "function",
    "function": {
        "name": "can_user_afford_installment",
        "description": (
            "Analyzes whether the user can safely buy an item on installment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User identifier"
                },
                "price": {
                    "type": "number",
                    "description": "Item price"
                },
                "months": {
                    "type": "integer",
                    "description": "Duration in months"
                }
            },
            "required": ["user_id", "price", "months"]
        }
    }
}

# Risk analysis tool
risk_tool = {
    "type": "function",
    "function": {
        "name": "evaluate_user_risk",
        "description": "Evaluates the user's financial risk level.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                }
            },
            "required": ["user_id"]
        }
    }
}

# Create the assistant
assistant = client.beta.assistants.create(
    name="Finance Advisor Agent",
    instructions=(
        "You are a financial AI advisor. Analyze risks, behavior and stability. "
        "Recommend only reasonable financial actions and explain your reasoning."
    ),
    model="gpt-4o",
    tools=[installment_tool, risk_tool]
)

# Create thread and run
thread = client.beta.threads.create()
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="What is my financial risk?"
)

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
)

print("Assistant ID:", assistant.id)
print("Thread ID:", thread.id)
print("Run ID:", run.id)
