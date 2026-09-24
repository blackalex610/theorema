import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from app.config import settings
from app.services.openai_client import openai_client
from openai import APIError
from app.auth.dependencies import (
    get_current_user,
    increment_usage,
    require_admin,
    require_image_scan_capacity,
)
from app.services.media_tokens import build_media_url
from app.services.media_retention import purge_expired_uploads
from app.services.media_storage import (
    MediaStorageError,
    MediaStorageUnavailable,
    get_media_storage,
)
from app.services import channel_state_store
from app.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["Mobile Uploads"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
# Vercel rejects any request body over 4.5 MB before it reaches the app; the
# frontend downscales photos to well under that (utils/imageCapture.ts).

# Magic bytes -> (extension, MIME). Detected from content rather than trusted
# from the filename or Content-Type: iOS sends HEIC labelled as anything, and
# a stored file is later served back with the type chosen here.
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
)

UNSUPPORTED_IMAGE_MESSAGE = "Снимката трябва да е JPG, PNG или WEBP."
STORAGE_UNAVAILABLE_MESSAGE = "Качването на снимки временно не е налично."


def _detect_image_type(data: bytes) -> tuple[str, str] | None:
    for signature, ext, mime in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return ext, mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _charge_scan(user, db: Session) -> None:
    try:
        increment_usage(user, db, "image_scans")
    except HTTPException:
        # Another request spent the last credit between the capacity check
        # and now. The scan already happened; log it rather than fail it.
        logger.warning("image_scans credit already exhausted for user %s at charge time", user.id)


def _media_storage_or_503():
    try:
        return get_media_storage()
    except MediaStorageUnavailable:
        logger.error("Photo upload attempted with no usable media storage", exc_info=True)
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE_MESSAGE)


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

# `upload_history` and `task_contexts` used to be module-level dicts here. Both
# are read by a *different device's* request than the one that wrote them — the
# desktop registers a task context, the phone grades against it; the phone
# uploads a photo, the desktop polls for it — so on serverless they were read
# from an instance that had never seen the write, and both halves of the
# pairing flow silently failed. They now live in channel_state_store.
#
# `stream_subscribers` deliberately stays in memory: an asyncio.Queue cannot be
# serialised, and each SSE connection belongs to the single process holding it
# open. That means an event published on instance A still does not reach a
# subscriber on instance B — the SSE fanout needs a broker (Redis pub/sub, or
# the existing realtime server) to be correct across instances. Until then the
# clients poll /mobile/uploads/latest, which is now durable, and the stream is
# a same-instance fast path rather than the only delivery route.
stream_subscribers: dict[str, set[asyncio.Queue[tuple[str, dict[str, Any]]]]] = defaultdict(set)

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
    payload = event.model_dump()
    channel_state_store.record_upload(channel_id, payload, UPLOAD_HISTORY_LIMIT)
    _broadcast_stream_event(channel_id, "upload", payload)


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

    client = openai_client()

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
    image_bytes: bytes,
    correct_xy: str,
    statement: str | None = None,
) -> tuple[bool, str, str]:
    """Grade a photo submission using AI. Returns (is_correct, extracted_answer, feedback)."""
    detected = _detect_image_type(image_bytes)
    mime = detected[1] if detected else "image/jpeg"
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
    current_user=Depends(require_image_scan_capacity),
    db: Session = Depends(get_db),
):
    channel_id = _validate_channel_id(channel_id)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    detected = _detect_image_type(data)
    if detected is None:
        raise HTTPException(status_code=415, detail=UNSUPPORTED_IMAGE_MESSAGE)
    ext, content_type = detected

    storage = _media_storage_or_503()

    # Retention sweep runs here rather than on a schedule: there is no
    # scheduler in this deployment, and a photo of a child's handwriting
    # kept forever is the thing being prevented. Never raises.
    await run_in_threadpool(purge_expired_uploads, force=False)

    filename = f"{uuid4().hex}{ext}"
    try:
        await run_in_threadpool(storage.save, filename, data, content_type)
    except MediaStorageError:
        logger.exception("Storing an uploaded photo failed")
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE_MESSAGE)

    # Charged only now that the photo is stored.
    _charge_scan(current_user, db)

    base_url = str(request.base_url).rstrip("/")
    # Signed + expiring: /media refuses unsigned reads (see media_tokens.py).
    file_url = build_media_url(filename, base_url)

    event = UploadEvent(
        channel_id=channel_id,
        file_name=filename,
        file_url=file_url,
        content_type=content_type,
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


@router.get("/uploads/latest", response_model=list[UploadEvent])
async def get_latest_uploads(
    channel_id: str = Query(...),
    limit: int = 20,
    _user=Depends(get_current_user),
):
    """A channel's recent uploads — signed links to photos of a child's work.

    SECURITY: was anonymous, so the channel id alone exposed every photo on
    it. Both sides of the flow are signed in (the upload itself requires a
    session), so this now does too; the id remains a 128-bit secret on top.
    """
    channel_id = _validate_channel_id(channel_id)
    safe_limit = max(1, min(limit, 50))
    return [UploadEvent(**event) for event in channel_state_store.load_uploads(channel_id, safe_limit)]


@router.post("/tasks/context", response_model=TaskContext)
async def set_task_context(payload: TaskContext, _user=Depends(get_current_user)):
    """Store the problem statement/answer key a later grade call will use.

    SECURITY: unauthenticated writes here let anyone plant an arbitrary
    `statement` that /tasks/grade then interpolates straight into an OpenAI
    prompt — unauthenticated prompt injection against our key.
    """
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
    channel_state_store.save_task_context(channel_id, problem_number, context.model_dump())
    return context


@router.get("/tasks/contexts", response_model=list[TaskContext])
async def get_task_contexts(channel_id: str = Query(...), _user=Depends(get_current_user)):
    """The problems (answer key included) registered on a channel.

    SECURITY: was anonymous; see get_latest_uploads.
    """
    channel_id = _validate_channel_id(channel_id)
    # Already ordered by problem number in the store's query.
    return [TaskContext(**item) for item in channel_state_store.load_task_contexts(channel_id)]


@router.post("/tasks/grade", response_model=TaskGradeResponse)
async def grade_task_submission(payload: TaskGradeRequest, _user=Depends(get_current_user)):
    """Grade a typed answer (OpenAI when a statement is known).

    SECURITY: this reaches OpenAI with attacker-influenced text, so it must not
    be callable anonymously. No extra daily credit is charged — the photo/scan
    credit is already spent upstream at /mobile/uploads, and charging twice
    would make the free tier's 2 scans/day impossible to finish. Burst abuse is
    bounded by the per-IP limiter on /mobile/.
    """
    channel_id = _validate_channel_id(payload.channel_id)
    problem_number = _validate_problem_number(payload.problem_number)
    stored_context = channel_state_store.load_task_context(channel_id, problem_number)
    context = TaskContext(**stored_context) if stored_context else None
    response = await run_in_threadpool(
        _build_task_grade,
        channel_id=channel_id,
        problem_number=problem_number,
        correct_xy=payload.correct_xy,
        submitted_answer=payload.student_answer,
        statement=context.statement if context else None,
    )
    _broadcast_stream_event(channel_id, "grade", response.model_dump())
    return response


@router.post("/tasks/grade-photo", response_model=TaskGradeResponse)
async def grade_task_from_photo(payload: TaskPhotoGradeRequest, _user=Depends(get_current_user)):
    """Grade an already-uploaded photo with OpenAI vision.

    SECURITY: was unauthenticated, i.e. free gpt-4o vision inference for
    anyone. Auth is mandatory; the image_scans credit was charged when the
    photo was uploaded, so it is deliberately not charged again here.
    """
    channel_id = _validate_channel_id(payload.channel_id)
    problem_number = _validate_problem_number(payload.problem_number)
    stored_context = channel_state_store.load_task_context(channel_id, problem_number)
    context = TaskContext(**stored_context) if stored_context else None
    if not context:
        raise HTTPException(status_code=404, detail="Task context not found for this problem and channel")

    # Only a photo uploaded to this channel can be graded on it. Any
    # authenticated user used to be able to name any stored file and have it
    # sent to OpenAI (and get a fresh signed URL for it back).
    file_name = Path(payload.file_name).name
    channel_files = {
        event.get("file_name")
        for event in channel_state_store.load_uploads(channel_id, UPLOAD_HISTORY_LIMIT)
    }
    if file_name not in channel_files:
        raise HTTPException(status_code=404, detail="Photo file not found")

    storage = _media_storage_or_503()
    try:
        image_bytes = await run_in_threadpool(storage.read, file_name)
    except MediaStorageError:
        logger.exception("Reading an uploaded photo for grading failed")
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE_MESSAGE)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Photo file not found")

    is_correct, extracted_answer, feedback = await run_in_threadpool(
        _grade_photo_with_ai, image_bytes, context.correct_xy, context.statement
    )

    response = TaskGradeResponse(
        channel_id=channel_id,
        problem_number=problem_number,
        submitted_answer=extracted_answer,
        is_correct=is_correct,
        score=100 if is_correct else 0,
        feedback=feedback,
        graded_at=datetime.now(timezone.utc).isoformat(),
    )
    # Attach a signed, site-relative media URL the desktop can render directly.
    response.file_url = build_media_url(file_name)
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
    current_user=Depends(require_image_scan_capacity),
    db: Session = Depends(get_db),
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

    try:
        resp = await run_in_threadpool(
            openai_client().chat.completions.create,
            model=settings.OPENAI_VISION_MODEL,
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
    except APIError as exc:
        logger.warning("Math photo extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail="Разпознаването на снимката не успя. Опитай отново.") from exc

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

    _charge_scan(current_user, db)
    return MathAnalysisResponse(extracted_text=extracted, confidence=confidence)


@router.delete("/channel/history")
async def clear_channel_history(channel_id: str = Query(...), _user=Depends(get_current_user)):
    """Clear upload history and grade state for a channel (e.g. on page refresh).

    SECURITY: was anonymous — anyone holding a channel id could wipe it.
    """
    channel_id = _validate_channel_id(channel_id)
    channel_state_store.clear_uploads(channel_id)
    return {"cleared": True}


@router.get("/uploads/stream")
async def stream_upload_events(channel_id: str = Query(...)):
    # Deliberately no session check: EventSource cannot send an Authorization
    # header, and putting the 7-day JWT in the URL would write it into every
    # access log. The stream only mirrors what /uploads/latest returns, and
    # the channel id is a 128-bit CSPRNG value (frontend utils/channelId.ts).
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


@router.post("/admin/purge-expired-uploads")
async def purge_expired_uploads_endpoint(
    max_age_hours: int | None = None,
    _admin=Depends(require_admin),
):
    """Admin-only retention sweep over the uploads directory.

    The sweep also runs opportunistically on every upload, so this exists for
    a deliberate manual run (or an external cron) rather than being the only
    thing standing between the platform and photos of children's handwriting
    kept indefinitely.
    """
    removed = purge_expired_uploads(max_age_hours)
    return {"removed": removed}
