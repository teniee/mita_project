import logging

import openai

logger = logging.getLogger(__name__)


class GPTAgentService:
    """Service for analytics and notification generation via OpenAI."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """
        Initialize the GPT agent.

        :param api_key: Your OpenAI API key.
        :param model: The model to use, e.g., 'gpt-4o' or 'gpt-3.5-turbo'.
        """
        openai.api_key = api_key
        self.model = model
        self.system_prompt = (
            "You are a professional financial assistant. "
            "You help users manage their budgets, categorize their expenses, "
            "and offer smart advice based on their country and spending profile. "
            "Be concise, clear, and supportive."
        )

    def ask(self, user_messages: list) -> str:
        """Send prompts to OpenAI and return generated advice."""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + user_messages
            response = openai.ChatCompletion.create(
                model=self.model, messages=messages, temperature=0.3, max_tokens=600
            )
            return response["choices"][0]["message"]["content"].strip()

        except openai.error.RateLimitError:
            logger.warning("OpenAI rate limit hit.")
            return "Too many requests. Please slow down and try again."

        except openai.error.OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "Sorry, I'm currently unavailable. Please try again later."
