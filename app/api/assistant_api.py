from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.gpt_agent_service import GPTAgentService
from app.core.config import settings
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/assistant", tags=["assistant"])

gpt_agent = GPTAgentService(
    api_key=settings.openai_api_key, model=settings.openai_model
)


class Message(BaseModel):
    role: str
    content: str


class ChatPayload(BaseModel):
    messages: List[Message]


@router.post("/message")
async def send_message(payload: ChatPayload):
    reply = gpt_agent.ask([m.model_dump() for m in payload.messages])
    return success_response({"reply": reply})
