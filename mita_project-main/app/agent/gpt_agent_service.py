"""GPTAgentService for analysing financial data using OpenAI."""

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai import OpenAIError


class GPTAgentService:
    """Use OpenAI to derive insights for analytics and notifications."""

    def __init__(self, api_key: str, model: str = "gpt-4o", system_prompt: str | None = None):
        """
        Initialize the GPT agent.

        :param api_key: Your OpenAI API key.
        :param model: The model to use, e.g., 'gpt-4o' or 'gpt-3.5-turbo'.
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt or (
            "You are a professional financial assistant. "
            "You help users manage their budgets and categorize expenses. "
            "Offer smart advice based on country and spending profile. "
            "Be concise, clear, and supportive."
        )

    def ask(self, user_messages: list[ChatCompletionMessageParam]) -> str:
        """Send prompts to OpenAI and return the generated advice."""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + user_messages

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )

            return response.choices[0].message.content.strip()

        except OpenAIError as e:
            print(f"OpenAI API error: {str(e)}")
            return "Sorry, I'm currently unavailable. Please try again later."
