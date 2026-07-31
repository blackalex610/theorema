import asyncio
import base64
import json
import re
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, Depends
from openai import OpenAI
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from app.config import settings
from app.auth.dependencies import require_image_scan
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mobile", tags=["Mobile Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
# Simplified: all uploads are treated as JPG since frontend converts everything


class MobileUploadResponse(BaseModel):
    file_name: str
    file_url: str
    content_type: str | None
    size_bytes: int
    uploaded_at: str


class UploadEvent(BaseModel):
    channel_id: str
    file_name: str
    file_url: str
    content_type: str | None
    size_bytes: int
    uploaded_at: str
    problem_number: int | None = None


class TaskGradeRequest(BaseModel):
    channel_id: str
    problem_number: int
    a: int
    b: int
    correct_xy: str
    student_answer: str
    photo_url: str | None = None


class TaskContext(BaseModel):
    channel_id: str
    problem_number: int
    a: int
    b: int
    correct_xy: str
    updated_at: str
    statement: str | None = None


class TaskGradeResponse(BaseModel):
    channel_id: str
    problem_number: int
    submitted_answer: str
    is_correct: bool
    score: int
    feedback: str
    graded_at: str
    file_url: str | None = None


class TaskPhotoGradeRequest(BaseModel):
    channel_id: str
    problem_number: int
    file_name: str


UPLOAD_HISTORY_LIMIT = 100
upload_history: dict[str, list[UploadEvent]] = defaultdict(list)
stream_subscribers: dict[str, set[asyncio.Queue[tuple[str, dict[str, Any]]]]] = defaultdict(set)
task_contexts: dict[str, dict[int, TaskContext]] = defaultdict(dict)

CHANNEL_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
SUPPORTED_PROBLEM_NUMBERS = {34, 35}


def _validate_channel_id(channel_id: str) -> str:
    normalized = (channel_id or "").strip()
    if not CHANNEL_ID_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Invalid channel_id")
    return normalized


def _validate_problem_number(problem_number: int) -> int:
    if problem_number not in SUPPORTED_PROBLEM_NUMBERS and not (1 <= problem_number <= 99):
        raise HTTPException(status_code=400, detail="Unsupported problem_number")
    return problem_number


def _broadcast_stream_event(channel_id: str, event_name: str, payload: dict[str, Any]):
    stale_subscribers: list[asyncio.Queue[tuple[str, dict[str, Any]]]] = []
    for queue in stream_subscribers[channel_id]:
        try:
            queue.put_nowait((event_name, payload))
        except asyncio.QueueFull:
            stale_subscribers.append(queue)

    for queue in stale_subscribers:
        stream_subscribers[channel_id].discard(queue)


def _record_upload_event(event: UploadEvent, channel_id: str):
    channel_history = upload_history[channel_id]
    channel_history.insert(0, event)
    del channel_history[UPLOAD_HISTORY_LIMIT:]
    _broadcast_stream_event(channel_id, "upload", event.model_dump())


def _ai_grade(
    statement: str,
    correct_xy: str,
    student_work: str,
    image_data_url: str | None = None,
    system_prompt_override: str | None = None,
) -> tuple[bool, str, str]:
    """Call OpenAI to grade the student's work.
    Returns (is_correct, extracted_answer, feedback_in_bulgarian).
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    system_prompt = system_prompt_override or (
        "Ти си учител по математика, който проверява ученическо решение. "
        "КРИТИЧНО ВАЖНО: Правилният отговор ти е даден в полето 'Правилен отговор'. "
        "НЕ решавай задачата сам. Приемай предоставения 'Правилен отговор' за абсолютна истина. "
        "Сравнявай ученическия отговор САМО с предоставения 'Правилен отговор'. "
        "Счита се за ВЕРЕН отговор ако математическата стойност съвпада, дори ако: "
        "- редът на корените е различен (напр. x1=3, x2=2 е РАВНОСИЛНО на x1=2, x2=3); "
        "- са използвани различни означения (x₁/x₂ vs x1/x2 vs корен 1/корен 2); "
        "- има малки разлики в форматирането. "
        "Провери дали ученикът е написал правилния отговор и обясни накратко (на български, 2-3 изречения). "
        "Ако е грешен — покажи правилния отговор от полето 'Правилен отговор'. "
        "Отговори САМО в следния JSON формат без markdown:"
        ' {"is_correct": true|false, "extracted_answer": "<написания от ученика краен отговор>", '
        '"feedback": "<обяснение на български>"}'
    )

    user_text = (
        f"Задача: {statement}\n"
        f"Правилен отговор: {correct_xy}\n"
        f"Ученическо решение/отговор: {student_work}"
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    if image_data_url:
        # Vision requests: content must be a list; response_format not supported with images
        user_content: Any = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
    else:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        import json as _json
        parsed = _json.loads(raw)
        is_correct = bool(parsed.get("is_correct", False))
        extracted = str(parsed.get("extracted_answer", student_work))
        feedback = str(parsed.get("feedback", "Няма обратна връзка."))
    except Exception:
        # Fallback: simple numeric check
        # fallback: just return the raw string as feedback
        is_correct = False
        extracted = student_work
        feedback = f"Грешка при обработка. Правилният отговор е {correct_xy}."
    return is_correct, extracted, feedback


def _build_task_grade(
    channel_id: str,
    problem_number: int,
    correct_xy: str,
    submitted_answer: str,
    statement: str | None = None,
) -> TaskGradeResponse:
    submitted_answer = submitted_answer.strip()
    if not submitted_answer:
        raise HTTPException(status_code=400, detail="student_answer is required")

    if statement and settings.OPENAI_API_KEY:
        is_correct, extracted, feedback = _ai_grade(
            statement=statement,
            correct_xy=correct_xy,
            student_work=submitted_answer,
        )
    else:
        is_correct = correct_xy.lower() in submitted_answer.lower()
        extracted = submitted_answer
        feedback = f"{'Верен отговор!' if is_correct else 'Грешен отговор.'} Правилният отговор е {correct_xy}."

    score = 100 if is_correct else 0
    return TaskGradeResponse(
        channel_id=channel_id,
        problem_number=problem_number,
        submitted_answer=extracted,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        graded_at=datetime.now(timezone.utc).isoformat(),
    )


def _grade_photo_with_ai(
    file_path: Path,
    correct_xy: str,
    statement: str | None = None,
) -> tuple[bool, str, str]:
    """Grade a photo submission using AI. Returns (is_correct, extracted_answer, feedback)."""
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found")

    image_bytes = file_path.read_bytes()
    mime = "image/jpeg"
    if file_path.suffix.lower() == ".png":
        mime = "image/png"
    elif file_path.suffix.lower() == ".webp":
        mime = "image/webp"
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    problem_text = statement if statement else f"Намери отговора. Очакван правилен отговор: {correct_xy}."

    photo_system_prompt = (
        "Ти си учител по математика, който проверява снимка на ученическо решение. "
        "КРИТИЧНО ВАЖНО: Правилният отговор ти е даден в полето 'Правилен отговор'. "
        "НЕ решавай задачата сам. НЕ проверявай дали даденият правилен отговор е математически верен. "
        "Приемай предоставения 'Правилен отговор' за абсолютна истина и сравнявай САМО с него. "
        "СТРОГИ ПРАВИЛА: "
        "1. Ако снимката е нечетлива, размазана, празна или не показва ясно написан математически отговор — "
        "ЗАДЪЛЖИТЕЛНО върни is_correct: false и обясни, че не можеш да прочетеш решението. "
        "2. САМО ако ясно виждаш написан отговор, провери дали съвпада с предоставения 'Правилен отговор'. "
        "3. Редът на корените не е важен (x1=3,x2=2 е същото като x1=2,x2=3). "
        "4. Ако ученикът е написал грешен отговор — покажи правилния отговор (от полето 'Правилен отговор'). "
        "Отговори САМО в следния JSON формат без markdown: "
        '{"is_correct": true|false, "extracted_answer": "<точно написаното от ученика или нечетливо>", "feedback": "<обяснение на български>"}'
    )

    return _ai_grade(
        statement=problem_text,
        correct_xy=correct_xy,
        student_work="(вижте снимката)",
        image_data_url=data_url,
        system_prompt_override=photo_system_prompt,
    )


@router.post("/uploads", response_model=MobileUploadResponse)
async def upload_mobile_photo(
    request: Request,
    channel_id: str = Form(...),
    file: UploadFile = File(...),
    problem_number: int | None = Form(None),
    _user=Depends(require_image_scan),
    db: Session = Depends(get_db),
):
    channel_id = _validate_channel_id(channel_id)

    # Ignore MIME type completely - just check file extension
    # Since frontend converts everything to JPG, we treat all as JPG
    original_filename = file.filename or "unknown"
    if not original_filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # All uploaded files are now JPG (converted by frontend)
    ext = ".jpg"
    print(f"Upload: original_filename={original_filename}, forced_ext={ext}, content_type={file.content_type}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    filename = f"{uuid4().hex}{ext}"
    target_path = UPLOAD_DIR / filename
    target_path.write_bytes(data)

    base_url = str(request.base_url).rstrip("/")
    file_url = f"{base_url}/media/{filename}"

    event = UploadEvent(
        channel_id=channel_id,
        file_name=filename,
        file_url=file_url,
        content_type="image/jpeg",  # Force content type to JPEG
        size_bytes=len(data),
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        problem_number=problem_number,
    )
    _record_upload_event(event, channel_id)

    return MobileUploadResponse(
        file_name=event.file_name,
        file_url=event.file_url,
        content_type=event.content_type,
        size_bytes=event.size_bytes,
        uploaded_at=event.uploaded_at,
    )
    _record_upload_event(event, channel_id)

    return MobileUploadResponse(
        file_name=event.file_name,
        file_url=event.file_url,
        content_type=event.content_type,
        size_bytes=event.size_bytes,
        uploaded_at=event.uploaded_at,
    )


@router.get("/uploads/latest", response_model=list[UploadEvent])
async def get_latest_uploads(
    channel_id: str = Query(...),
    limit: int = 20,
):
    channel_id = _validate_channel_id(channel_id)
    safe_limit = max(1, min(limit, 50))
    return upload_history[channel_id][:safe_limit]


@router.post("/tasks/context", response_model=TaskContext)
async def set_task_context(payload: TaskContext):
    channel_id = _validate_channel_id(payload.channel_id)
    problem_number = _validate_problem_number(payload.problem_number)
    context = TaskContext(
        channel_id=channel_id,
        problem_number=problem_number,
        a=payload.a,
        b=payload.b,
        correct_xy=payload.correct_xy,
        updated_at=datetime.now(timezone.utc).isoformat(),
        statement=payload.statement,
    )
    task_contexts[channel_id][problem_number] = context
    return context


@router.get("/tasks/contexts", response_model=list[TaskContext])
async def get_task_contexts(channel_id: str = Query(...)):
    channel_id = _validate_channel_id(channel_id)
    contexts = list(task_contexts.get(channel_id, {}).values())
    return sorted(contexts, key=lambda item: item.problem_number)


@router.post("/tasks/grade", response_model=TaskGradeResponse)
async def grade_task_submission(payload: TaskGradeRequest):
    channel_id = _validate_channel_id(payload.channel_id)
    problem_number = _validate_problem_number(payload.problem_number)
    context = task_contexts.get(channel_id, {}).get(problem_number)
    response = _build_task_grade(
        channel_id=channel_id,
        problem_number=problem_number,
        correct_xy=payload.correct_xy,
        submitted_answer=payload.student_answer,
        statement=context.statement if context else None,
    )
    _broadcast_stream_event(channel_id, "grade", response.model_dump())
    return response


@router.post("/tasks/grade-photo", response_model=TaskGradeResponse)
async def grade_task_from_photo(payload: TaskPhotoGradeRequest):
    channel_id = _validate_channel_id(payload.channel_id)
    problem_number = _validate_problem_number(payload.problem_number)
    context = task_contexts.get(channel_id, {}).get(problem_number)
    if not context:
        raise HTTPException(status_code=404, detail="Task context not found for this problem and channel")

    file_name = Path(payload.file_name).name
    file_path = UPLOAD_DIR / file_name
    is_correct, extracted_answer, feedback = _grade_photo_with_ai(file_path, context.correct_xy, context.statement)

    response = TaskGradeResponse(
        channel_id=channel_id,
        problem_number=problem_number,
        submitted_answer=extracted_answer,
        is_correct=is_correct,
        score=100 if is_correct else 0,
        feedback=feedback,
        graded_at=datetime.now(timezone.utc).isoformat(),
    )
    # Attach the file_name so the desktop can construct the media URL from the grade event.
    response.file_url = file_name
    _broadcast_stream_event(channel_id, "grade", response.model_dump())
    return response


class MathAnalysisRequest(BaseModel):
    image_data_url: str


class MathAnalysisResponse(BaseModel):
    extracted_text: str
    confidence: str


@router.post("/analyze-math", response_model=MathAnalysisResponse)
async def analyze_math_image(
    payload: MathAnalysisRequest,
    _user=Depends(require_image_scan),
):
    """Extract all mathematical content from an image using OpenAI vision."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    if not payload.image_data_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Invalid image data URL")

    system_prompt = (
        "Ти си специализирана система за разпознаване на математически текст от снимки на ученически работи. "
        "Твоята единствена задача е да ИЗВЛЕЧЕШ ТОЧНО всичко написано на снимката — "
        "всички числа, уравнения, изрази, дроби, корени, степени, геометрични означения, текст и работни стъпки. "
        "ПРАВИЛА: "
        "1. Пиши математическите изрази с LaTeX нотация — напр. \\frac{1}{2}, \\sqrt{x}, x^2, \\cdot. "
        "2. Запази реда на записите точно както са на страницата (отгоре надолу, ляво надясно). "
        "3. Ако има зачертани/поправени части — отбележи ги с ~~зачертано~~. "
        "4. Ако дадена част е нечетлива — напиши [нечетливо]. "
        "5. НЕ решавай, НЕ проверявай, НЕ коментирай — само извличай. "
        "6. Отговори в JSON формат: "
        '{\"extracted_text\": \"<пълно извлечено съдържание>\", \"confidence\": \"high|medium|low\"}'
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0)
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Извлечи всичко написано на тази снимка:"},
                    {"type": "image_url", "image_url": {"url": payload.image_data_url, "detail": "high"}},
                ],
            },
        ],
    )

    raw = (resp.choices[0].message.content or "").strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    try:
        parsed = json.loads(raw)
        extracted = str(parsed.get("extracted_text", raw))
        confidence = str(parsed.get("confidence", "medium"))
    except Exception:
        extracted = raw
        confidence = "low"

    return MathAnalysisResponse(extracted_text=extracted, confidence=confidence)


@router.delete("/channel/history")
async def clear_channel_history(channel_id: str = Query(...)):
    """Clear upload history and grade state for a channel (e.g. on page refresh)."""
    channel_id = _validate_channel_id(channel_id)
    upload_history.pop(channel_id, None)
    return {"cleared": True}


@router.get("/uploads/stream")
async def stream_upload_events(channel_id: str = Query(...)):
    channel_id = _validate_channel_id(channel_id)
    subscriber: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=10)
    stream_subscribers[channel_id].add(subscriber)

    async def event_generator():
        try:
            # Initial ping so clients know the connection is alive.
            yield ": connected\n\n"
            while True:
                try:
                    event_name, event_payload = await asyncio.wait_for(subscriber.get(), timeout=15.0)
                    payload = json.dumps(event_payload, ensure_ascii=True)
                    yield f"event: {event_name}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Send a keepalive comment so the connection is not silently dropped.
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            stream_subscribers[channel_id].discard(subscriber)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
