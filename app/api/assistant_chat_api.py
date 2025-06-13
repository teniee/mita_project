import os

from fastapi import APIRouter, Depends
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from app.agent.gpt_agent_service import GPTAgentService
from app.api.dependencies import get_current_user
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/assistant", tags=["assistant"])

GPT = GPTAgentService(api_key=os.getenv("OPENAI_API_KEY", ""))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    user=Depends(get_current_user),  # noqa: B008
):
    msgs: list[ChatCompletionMessageParam] = [
        {"role": m.role, "content": m.content} for m in payload.messages
    ]
    reply = GPT.ask(msgs)
    return success_response({"reply": reply})
