from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError
from pydantic import BaseModel, Field

from app.services.ai_theory_service import (
    generate_chat_reply,
    generate_diagram_json,
    AIQuotaExceededError,
    AIConfigurationError,
    AIServiceError,
)
from app.auth.dependencies import require_ai_chat, check_chat_cooldown, update_last_chat_at
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["AI Chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    lesson_title: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


class DiagramRequest(BaseModel):
    problem: str = Field(..., min_length=5, max_length=5000)


class DiagramResponse(BaseModel):
    diagram: dict[str, Any]


def _fallback_chat_reply(payload: ChatRequest) -> str:
    last_user_message = ""
    for message in reversed(payload.messages):
        if message.role == "user":
            last_user_message = message.content.strip()
            break

    lesson_hint = f"Урок: {payload.lesson_title}. " if payload.lesson_title else ""
    return (
        f"{lesson_hint}AI услугата е временно недостъпна, но можем да продължим. "
        "Изпрати ми задачата стъпка по стъпка (какво е дадено, какво се търси, какво си опитал) "
        "и ще ти дам структурирано решение. "
        f"Твоят последен въпрос беше: \"{last_user_message[:300]}\""
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    _user=Depends(require_ai_chat),
    db: Session = Depends(get_db),
):
    """Generate a chat response from OpenAI for the sidebar assistant."""
    if not payload.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    # 2-second cooldown only for authenticated users
    if _user is not None:
        check_chat_cooldown(_user, db)

    try:
        reply = generate_chat_reply(
            messages=[m.model_dump() for m in payload.messages],
            lesson_title=payload.lesson_title,
        )
    except (AIQuotaExceededError, AIConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if _user is not None:
        update_last_chat_at(_user, db)

    return ChatResponse(reply=reply)


@router.post("/diagram", response_model=DiagramResponse)
async def generate_diagram(
    payload: DiagramRequest,
    _user=Depends(require_ai_chat),
):
    """Generate structured diagram JSON for a Bulgarian math problem."""
    try:
        diagram = generate_diagram_json(problem_text=payload.problem)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=502, detail="OpenAI request failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to generate diagram JSON") from exc

    return DiagramResponse(diagram=diagram)
