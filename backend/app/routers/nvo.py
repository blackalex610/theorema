from fastapi import APIRouter, Depends, HTTPException
from typing import Callable, List, Union, cast
import asyncio
import json
import logging
import os
import re
from pathlib import Path
import random
import uuid
from pydantic import BaseModel
from openai import APIError, OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, SessionLocal
from app.services.playground_problems import select_playground_problems
from app.routers.mobile_uploads import _ai_grade
from app.services.progress_service import ProgressService
from app.services import nvo_exam_store
from app.services.nvo_content_retrieval import (
    build_slot_pool,
    select_diverse_pool_for_slot,
    slot_pool_to_catalog,
)
from app.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_admin,
    require_nvo_exam,
)
from app.models.user import User
from app.models.nvo_content import NvoGenerationRun

router = APIRouter(prefix="/nvo", tags=["nvo"])

logger = logging.getLogger(__name__)


class NVOQuestion(BaseModel):
    number: int
    question: str
    topic: str
    difficulty: str
    diagram: bool
    diagram_type: str | None = None
    diagram_config: dict | None = None
    open_parts: List[str] | None = None
    options: List[str] | None = None
    correct_answer: Union[str, List[str]] | None = None


class NVOExam(BaseModel):
    exam_id: str
    questions: List[NVOQuestion]


class NVOGenerationJobResponse(BaseModel):
    job_id: str


class NVOGenerationJobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    exam_id: str | None = None


class NVOOpenImageSubmission(BaseModel):
    problemId: int
    image: str


class NVOExamSubmitRequest(BaseModel):
    exam_id: str
    answers: dict[str, str | dict[str, str]]
    open_answer_images: list[NVOOpenImageSubmission]
    questions: list[NVOQuestion] | None = None


class NVOOpenGradeResult(BaseModel):
    problemId: int
    score: int
    max_score: int
    is_correct: bool
    extracted_answer: str
    feedback: str


class NVOExamSubmitResponse(BaseModel):
    exam_id: str
    open_results: list[NVOOpenGradeResult]
    total_open_score: int
    total_open_max_score: int


class NVOGenerationRequest(BaseModel):
    difficulty: str | None = None  # 'easy', 'standard', or 'hard'
    format: str | None = None  # 'full' (23 problems, 90min) or 'short' (16 problems, 30min)


def load_nvo_questions() -> dict:
    """Load NVO questions from JSON file"""
    try:
        json_path = os.path.join(os.path.dirname(__file__), "../../nvo_generated_exam.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        backend_dir = Path(json_path).resolve().parent
        transcript_files = sorted(backend_dir.glob("reference_nvo_full_exam_*.txt"))
        full_reference_exams: list[dict[str, str]] = list(data.get("full_reference_exams", []))
        for transcript_file in transcript_files:
            full_reference_exams.append(
                {
                    "source": transcript_file.stem,
                    "raw_text": transcript_file.read_text(encoding="utf-8").strip(),
                }
            )

        if full_reference_exams:
            data["full_reference_exams"] = full_reference_exams

        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="NVO exam questions not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid NVO questions format")


def load_nvo_catalog() -> dict:
    """Load the per-slot question catalog from nvo_question_catalog.json."""
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), "../../nvo_question_catalog.json")
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="NVO question catalog not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid NVO question catalog format")


def _load_catalog_or_db() -> tuple[dict, str]:
    """Return a catalog-shaped dict plus its source tag ('db' or 'file_catalog').

    DB retrieval is tried first only when the feature flag is on; any
    exception, or a corpus missing any of the 23 slots, falls back to the
    file catalog so generation never breaks because of this.
    """
    if settings.NVO_USE_DB_RETRIEVAL:
        db = SessionLocal()
        try:
            pool = build_slot_pool(db, list(range(1, 24)))
            if pool is not None:
                if settings.NVO_USE_EMBEDDING_RETRIEVAL:
                    pool = {
                        slot: select_diverse_pool_for_slot(db, candidates)
                        for slot, candidates in pool.items()
                    }
                return slot_pool_to_catalog(db, pool), "db"
        except Exception:
            logger.exception("NVO DB retrieval failed; falling back to file catalog")
        finally:
            db.close()
    return load_nvo_catalog(), "file_catalog"


def _record_generation_run(*, profile: dict, source: str, exam: "NVOExam", model: str | None) -> None:
    """Best-effort audit row. Never blocks or fails a generation on write error."""
    db = None
    try:
        db = SessionLocal()
        db.add(
            NvoGenerationRun(
                requested_profile_json=json.dumps(profile, ensure_ascii=False),
                source=source,
                model=model,
                status="completed",
                output_json=json.dumps({"exam_id": exam.exam_id}, ensure_ascii=False),
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to record NVO generation run (non-fatal)")
        if db is not None:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to roll back NVO generation run session (non-fatal)")
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Failed to close NVO generation run session (non-fatal)")


def _strip_json_fences(raw: str) -> str:
    """Strip ```json ... ``` markdown fences the model sometimes wraps JSON in.

    Without this, json.loads() raised on every fenced response, the caller
    swallowed the error and silently fell back to the catalog — i.e. AI
    generation never actually shipped a single AI-generated exam.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _inject_playground_problems(questions: list, format: str | None = None) -> list:
    """Replace the diagram slots with playground diagram questions.

    Full format (23 questions): Q10-Q15 (indices 9-14) and Q23 (index 22).
    Short format (16 questions): Q10-Q15 (indices 9-14) and the single open
    question at Q16 (index 15). Previously the short format skipped injection
    entirely, so a "16 question" short exam contained zero diagram questions.

    Real NVO structure (2024/2025 format, 23 questions):
      Q1-Q8   : arithmetic / algebra / probability  — no diagrams
      Q9      : arithmetic word problem or simple geometry — no diagram injected
      Q10-Q15 : geometry diagram MCQs (triangles, rhombus, parallelogram, 3D, etc.)
      Q16-Q18 : word problems — no diagrams
      Q19     : chart / data reading — no diagram injected (no SVG chart renderer yet)
      Q20     : geometry word problem — no diagram injected
      Q21-Q22 : open algebra / word problem — no diagrams
      Q23     : open geometry — diagram only if generator produces one (4/6 generators have no diagram)
    """
    pg = select_playground_problems()
    result = list(questions)
    # The open diagram question sits last in whichever format we generated.
    open_index = len(result) - 1 if format == "short" else 22
    for i, mcq_data in enumerate(pg["mcq"]):
        pos = 10 + i  # Q10 through Q15
        if pos - 1 >= open_index:
            break  # never overwrite the open question with an MCQ
        data = dict(mcq_data)
        data["number"] = pos
        result[pos - 1] = NVOQuestion(**data)
    q23_data = dict(pg["open_q23"])
    q23_data["number"] = open_index + 1
    # Respect the generator's own diagram flag — non-diagram generators set diagram=False
    result[open_index] = NVOQuestion(**q23_data)
    return result


def _normalize_math_delimiters(text: str) -> str:
    """
    Normalize math delimiters and fix common KaTeX noglyph issues.
    
    Fixes:
    - Remove unsupported \operatorname commands
    - Fix common problematic math operators
    - Remove Bulgarian text accidentally placed inside $...$
    - Ensure proper spacing in math expressions
    """
    import re
    
    result = text.strip()
    
    # Remove unsupported \operatorname (KaTeX doesn't support it by default)
    result = re.sub(r'\\operatorname\{([^}]+)\}', r'\\text{\1}', result)
    
    # Replace \tg with \tan (Bulgarian tangent notation -> standard)
    result = re.sub(r'\\tg(?![a-zA-Z])', r'\\tan', result)
    result = re.sub(r'\\ctg(?![a-zA-Z])', r'\\cot', result)
    result = re.sub(r'\\arctg(?![a-zA-Z])', r'\\arctan', result)
    result = re.sub(r'\\arcctg(?![a-zA-Z])', r'\\arccot', result)
    
    # Replace Bulgarian math notation with standard
    result = result.replace('×', '\\cdot ')
    result = result.replace('·', '\\cdot ')
    
    # Remove accidental Bulgarian text inside inline math
    # Pattern: $...Bulgarian text...$ -> extract just the math parts
    def clean_math_content(match):
        content = match.group(1)
        # If content has Cyrillic characters, it's likely text that shouldn't be in math mode
        if re.search(r'[а-яА-Я]', content):
            # Extract just the math expressions (numbers, operators, basic commands)
            math_parts = re.findall(r'[0-9\+\-\*/=^_{}\\\[\]()\s\.a-zA-Z]+', content)
            cleaned = ' '.join(p for p in math_parts if p.strip())
            if cleaned.strip():
                return f'${cleaned}$'
            return ''  # Remove empty math
        return match.group(0)
    
    result = re.sub(r'\$([^$]+)\$', clean_math_content, result)
    
    # Clean up double dollars and spacing
    result = re.sub(r'\$\$\s*\$\$', '', result)
    result = re.sub(r'\$\s*\$', '', result)
    
    return result


def _set_job_progress(job_id: str, *, status: str, progress: int, message: str, exam_id: str | None = None) -> None:
    job = NVOGenerationJobStatus(
        job_id=job_id,
        status=status,
        progress=progress,
        message=message,
        exam_id=exam_id,
    )
    nvo_exam_store.save_job(job_id, job.model_dump())


def _load_job(job_id: str) -> "NVOGenerationJobStatus | None":
    payload = nvo_exam_store.load_job(job_id)
    return NVOGenerationJobStatus(**payload) if payload else None


def _store_exam(exam: "NVOExam") -> None:
    nvo_exam_store.save_exam(exam.exam_id, exam.model_dump())


def _load_exam(exam_id: str) -> "NVOExam | None":
    payload = nvo_exam_store.load_exam(exam_id)
    return NVOExam(**payload) if payload else None


def _get_question_counts(format: str | None) -> tuple[int, int]:
    """
    Get question counts for each format.
    Returns (module1_count, module2_count)
    """
    if format == 'short':
        # Short NVO: 15 MCQ (Module 1) + 1 open (Module 2) = 16 total
        return (15, 1)
    else:
        # Full NVO: 20 MCQ (Module 1) + 3 open (Module 2) = 23 total
        return (20, 3)


def _fallback_generate_from_pool(
    format: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None
) -> NVOExam:
    """Fallback generator: picks one random variant per slot from the catalog.

    For each of the 23 question slots the catalog holds ~5 real official variants.
    This produces a different exam every run while maintaining the correct topic
    at every position.  Diagram slots (Q10-Q15, Q23) are overwritten by
    _inject_playground_problems immediately after.
    """
    if progress_callback:
        progress_callback(10, "Зареждане на каталог с НВО задачи")

    catalog, _source = _load_catalog_or_db()
    slots = catalog.get("slots", {})

    if len(slots) != 23:
        raise HTTPException(status_code=500, detail="NVO catalog must have exactly 23 slots")

    # Get question counts based on format
    module1_count, module2_count = _get_question_counts(format)
    total_questions = module1_count + module2_count
    
    normalized: list[NVOQuestion] = []
    if progress_callback:
        progress_callback(45, "Избор на случаен вариант за всяка задача")

    # Map slots: For short format, we need to pick representative slots
    # Full: 1-20 (MCQ), 21-23 (open) = 23 total
    # Short: 1-15 (MCQ from slots 1-20), 21 (open) = 16 total
    
    if format == 'short':
        # Short format: 15 MCQ from first 20 slots, 1 open from slot 21
        mcq_slots = random.sample(range(1, 21), module1_count)  # Pick 15 from 20
        mcq_slots.sort()
        open_slots = [21]  # Just Q21 for short format
        selected_slots = mcq_slots + open_slots
    else:
        # Full format: 20 MCQ (1-20), 3 open (21-23)
        selected_slots = list(range(1, total_questions + 1))

    for idx, slot_num in enumerate(selected_slots, start=1):
        slot = slots[str(slot_num)]
        variants = slot.get("variants", [])
        if not variants:
            raise HTTPException(status_code=500, detail=f"No variants in catalog slot {slot_num}")

        variant = random.choice(variants)
        is_open = slot_num >= 21

        options = variant.get("options")
        if isinstance(options, list) and options:
            shuffled = options[:]
            random.shuffle(shuffled)
        else:
            shuffled = None

        question = NVOQuestion(
            number=idx,  # Renumber sequentially
            question=_normalize_math_delimiters(str(variant.get("question", ""))),
            topic=slot.get("topic", "general"),
            difficulty=variant.get("difficulty", "medium"),
            diagram=False,  # playground injection overwrites diagram slots
            options=shuffled if not is_open else None,
            open_parts=variant.get("open_parts") if is_open else None,
            correct_answer=variant.get("correct_answer"),
        )
        normalized.append(question)

    if progress_callback:
        progress_callback(80, "Добавяне на диаграмни задачи")

    normalized = _inject_playground_problems(normalized, format)

    if progress_callback:
        progress_callback(95, "Локалният тест е готов")

    exam = NVOExam(exam_id=str(uuid.uuid4())[:8], questions=normalized)
    if settings.NVO_USE_DB_RETRIEVAL:
        _record_generation_run(profile={"format": format, "path": "fallback_pool"}, source=_source, exam=exam, model=None)
    return exam


def _get_difficulty_instructions(difficulty: str | None) -> str:
    """Return prompt modifications based on difficulty level."""
    if difficulty == 'easy':
        return """
DIFFICULTY: EASY
- Simplify all questions compared to standard NVO level
- Use shorter, clearer explanations and simpler numbers
- Focus on basic understanding and recognition
- Reduce multi-step problems to single-step where possible
- Avoid complex word problems; use straightforward contexts
"""
    elif difficulty == 'hard':
        return """
DIFFICULTY: HARD
- Increase complexity beyond standard NVO level
- Add deeper inference requirements and edge cases
- Combine multiple concepts in single problems
- Require stronger reasoning and multi-step solutions
- Include more challenging numbers and contexts
- Add problems that require creative application of concepts
"""
    else:
        # standard or None
        return """
DIFFICULTY: STANDARD
- Match the standard NVO difficulty level exactly
- Use balanced complexity appropriate for 7th grade
- Follow the difficulty distribution of official exams
"""


def _generate_via_openai(
    difficulty: str | None = None,
    format: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None
) -> NVOExam:
    """Generate a fresh NVO-style test from reference pool using a stronger model."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")

    if progress_callback:
        progress_callback(10, "Зареждане на референтен набор")

    catalog, _source = _load_catalog_or_db()
    slots = catalog.get("slots", {})

    # The prompt must describe the format actually being asked for. It used to
    # hard-code 23 questions even for format="short", so the model returned 23,
    # the 16-question check below rejected it, and short exams could never be
    # AI-generated at all — they always fell back to the catalog.
    mcq_count, open_count = _get_question_counts(format)
    total_count = mcq_count + open_count

    # Map output positions onto catalog slots: MCQ slots are 1-20, open are 21-23.
    source_slots = list(range(1, mcq_count + 1)) + list(range(21, 21 + open_count))

    # Build per-slot style hints: topic description + one random example variant per slot
    slot_hints: list[str] = []
    for position, slot_num in enumerate(source_slots, start=1):
        slot = slots[str(slot_num)]
        topic = slot.get("topic", "")
        notes = slot.get("notes", "")
        variants = slot.get("variants", [])
        example = random.choice(variants) if variants else {}
        example_q = example.get("question", "")[:200]
        slot_hints.append(
            f"Q{position} [{topic}]: {notes}\n"
            f"  Style example: {example_q}"
        )
    slot_guide = "\n".join(slot_hints)

    # Diagram slots are Q10-Q15 plus the final open question, whatever the length.
    diagram_slots = f"Q10-Q15 and Q{total_count}"

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=75.0)
    difficulty_instructions = _get_difficulty_instructions(difficulty)

    system_prompt = (
        "You are an expert Bulgarian 7th-grade NVO math exam generator. "
        "Generate high-quality, exam-grade questions in Bulgarian. "
        "Follow official NVO style and formatting strictly. "
        "Use ONLY standard LaTeX math commands that KaTeX supports."
    )
    user_prompt = f"""
Create ONE new NVO exam JSON. REWRITE each slot with a FRESH question — same topic, same style, different numbers/context.
Do NOT copy the example questions verbatim.

{difficulty_instructions}

Strict requirements:
1) Exactly {total_count} questions.
2) Q1-Q{mcq_count}: multiple choice, exactly 4 options each.
3) Q{mcq_count + 1}-Q{total_count}: open-ended, options = null, include open_parts list.
4) Bulgarian academic wording.
5) Math: use $...$ inline and $$...$$ block delimiters.
6) SET diagram=false FOR ALL QUESTIONS ({diagram_slots} diagrams are auto-injected).
7) Output ONLY a valid JSON object with key "questions".

CRITICAL MATH FORMATTING RULES to prevent rendering errors:
- NEVER use \\operatorname — instead write \\text{{name}} or just the word
- For trigonometry: use \\sin, \\cos, \\tan, \\cot (NOT \\tg, \\ctg, \\arctg)
- For inverse trig: use \\arcsin, \\arccos, \\arctan (NOT \\arctg, \\arcctg)
- Use standard symbols: \\cdot for multiplication, \\frac for fractions, \\sqrt for roots
- NEVER put Bulgarian text inside $...$ math delimiters — only numbers and math symbols
- Keep math expressions clean — avoid special Unicode characters in math mode

Per-slot topic guide and style examples:
{slot_guide}
""".strip()

    if progress_callback:
        progress_callback(25, "Генериране на нов НВО вариант чрез AI")

    response = client.chat.completions.create(
        model=settings.OPENAI_NVO_MODEL,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    if progress_callback:
        progress_callback(70, "Проверка и валидиране на генерирания тест")

    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(_strip_json_fences(raw))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI returned invalid JSON for NVO generation") from exc

    questions_data = data.get("questions", [])
    if len(questions_data) != total_count:
        raise HTTPException(status_code=502, detail=f"AI did not return exactly {total_count} questions")

    validated: list[NVOQuestion] = []
    for idx, q in enumerate(questions_data, start=1):
        item = dict(q)
        item["number"] = idx
        item["question"] = _normalize_math_delimiters(str(item.get("question", "")))
        item["diagram"] = False  # Only playground diagrams allowed
        validated.append(NVOQuestion(**item))

    if progress_callback:
        progress_callback(90, "Добавяне на диаграмни задачи")

    validated = _inject_playground_problems(validated, format)

    if progress_callback:
        progress_callback(98, "НВО тестът е готов")

    exam = NVOExam(exam_id=str(uuid.uuid4())[:8], questions=validated)
    if settings.NVO_USE_DB_RETRIEVAL:
        _record_generation_run(
            profile={"format": format, "difficulty": difficulty, "path": "openai"},
            source=_source,
            exam=exam,
            model=settings.OPENAI_NVO_MODEL,
        )
    return exam


def _run_generation_job(job_id: str, difficulty: str | None = None, format: str | None = None) -> None:
    def progress_callback(progress: int, message: str) -> None:
        _set_job_progress(job_id, status="running", progress=progress, message=message)

    try:
        _set_job_progress(job_id, status="running", progress=2, message="Създаване на заявка за нов тест")
        try:
            exam = _generate_via_openai(difficulty, format, progress_callback)
        except (ValueError, APIError, HTTPException):
            _set_job_progress(job_id, status="running", progress=35, message="AI не е наличен. Превключване към локален генератор")
            exam = _fallback_generate_from_pool(format, progress_callback)

        _store_exam(exam)
        _set_job_progress(job_id, status="completed", progress=100, message="Тестът е готов за стартиране", exam_id=exam.exam_id)
    except Exception as exc:
        _set_job_progress(job_id, status="failed", progress=100, message=f"Неуспешно генериране на НВО тест: {exc}")


@router.post("/generate")
async def generate_nvo_exam(
    request: NVOGenerationRequest | None = None,
    _user=Depends(require_nvo_exam),
) -> NVOExam:
    """Generate a fresh NVO exam each click. Uses OpenAI when available, fallback otherwise.

    Previously called the generators with no arguments, so the caller's
    difficulty and format were silently discarded and every exam came back as
    a standard-difficulty full exam.
    """
    difficulty = request.difficulty if request else None
    format = request.format if request else None
    try:
        exam = _generate_via_openai(difficulty, format)
    except (ValueError, APIError, HTTPException):
        exam = _fallback_generate_from_pool(format)
    # Store it so /nvo/submit can grade against the server's own copy of the
    # answers instead of trusting whatever the client posts back.
    _store_exam(exam)
    return exam


@router.post("/generate-job", response_model=NVOGenerationJobStatus)
async def create_nvo_generation_job(request: NVOGenerationRequest | None = None, _user=Depends(require_nvo_exam)) -> NVOGenerationJobStatus:
    job_id = str(uuid.uuid4())[:8]
    difficulty = request.difficulty if request else None
    format = request.format if request else None
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_generation_job, job_id, difficulty, format)
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="NVO generation job missing after run")
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.message)
    return job


@router.get("/generate-job/{job_id}", response_model=NVOGenerationJobStatus)
async def get_nvo_generation_job(job_id: str) -> NVOGenerationJobStatus:
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="NVO generation job not found")
    return job


@router.get("/generated/{exam_id}", response_model=NVOExam)
async def get_generated_nvo_exam(exam_id: str) -> NVOExam:
    exam = _load_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Generated NVO exam not found")
    return exam


@router.get("/questions")
async def get_nvo_questions() -> dict:
    """Get all available NVO questions (for admin/preview purposes)"""
    return load_nvo_questions()


@router.post("/submit", response_model=NVOExamSubmitResponse)
async def submit_nvo_exam(
    payload: NVOExamSubmitRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NVOExamSubmitResponse:
    """Grade a finished NVO exam (open-ended answers go through AI vision).

    SECURITY: previously unauthenticated, which let anyone burn our OpenAI key
    with attacker-supplied prompts. Auth is now mandatory. The daily nvo_exams
    credit is charged at generation time, so submitting the exam you already
    paid for must NOT charge a second credit (that would make the free tier's
    1 exam/day impossible to ever finish).
    """
    exam = _load_exam(payload.exam_id)
    if not exam:
        if payload.questions:
            exam = NVOExam(exam_id=payload.exam_id, questions=payload.questions)
        else:
            raise HTTPException(status_code=404, detail="Generated NVO exam not found")

    image_by_problem = {item.problemId: item.image for item in payload.open_answer_images}
    open_results: list[NVOOpenGradeResult] = []
    total_open_score = 0
    total_open_max_score = 0

    for question in exam.questions:
        if question.options is not None:
            continue

        raw_answer = payload.answers.get(str(question.number), "")
        if isinstance(raw_answer, dict):
            student_work = " ".join(f"{k}: {v}" for k, v in raw_answer.items()).strip()
        else:
            student_work = str(raw_answer or "").strip()

        image_data_url = image_by_problem.get(question.number, "")
        if image_data_url and not image_data_url.startswith("data:image/"):
            raise HTTPException(status_code=400, detail=f"Invalid image format for problem {question.number}")

        correct_answer = question.correct_answer
        if isinstance(correct_answer, list):
            correct_xy = " | ".join(str(item) for item in correct_answer)
        else:
            correct_xy = str(correct_answer or "")

        if not student_work and not image_data_url:
            total_open_max_score += 1
            open_results.append(
                NVOOpenGradeResult(
                    problemId=question.number,
                    score=0,
                    max_score=1,
                    is_correct=False,
                    extracted_answer="",
                    feedback="Липсва подаден отговор за тази задача.",
                )
            )
            continue

        try:
            is_correct, extracted, feedback = _ai_grade(
                statement=question.question,
                correct_xy=correct_xy,
                student_work=student_work or "(вижте снимката)",
                image_data_url=image_data_url or None,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Failed to grade open-ended response") from exc

        total_open_max_score += 1
        score = 1 if is_correct else 0
        total_open_score += score
        open_results.append(
            NVOOpenGradeResult(
                problemId=question.number,
                score=score,
                max_score=1,
                is_correct=is_correct,
                extracted_answer=extracted,
                feedback=feedback,
            )
        )

    return NVOExamSubmitResponse(
        exam_id=payload.exam_id,
        open_results=open_results,
        total_open_score=total_open_score,
        total_open_max_score=total_open_max_score,
    )


class NVOAwardXpRequest(BaseModel):
    percentage_correct: int  # 0-100
    difficulty: str = "standard"  # easy, standard, hard
    minutes_taken: int  # completion time in minutes
    exam_id: str | None = None


@router.post("/award-xp")
async def award_nvo_exam_xp(
    request: NVOAwardXpRequest,
    user_id: int | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Award XP for NVO exam completion with performance-based calculation.
    
    Pipeline:
    1. Base XP from percentage correct (10-300 XP based on performance tiers)
    2. Difficulty multiplier (Easy: 0.5x, Standard: 1.0x, Hard: 2.0x)
    3. Time bonus/penalty (0-60min: +40%, 61-75min: +20%, 76-90min: 0%, 91+min: -10%)
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    resolved_user_id = int(cast(int, current_user.id))

    service = ProgressService(db)
    
    # Validate inputs
    percentage = max(0, min(100, request.percentage_correct))
    difficulty = request.difficulty.lower() if request.difficulty in ["easy", "standard", "hard"] else "standard"
    minutes = max(0, request.minutes_taken)
    
    # Award XP with full calculation pipeline
    result = service.award_nvo_exam_xp_detailed(
        user_id=resolved_user_id,
        percentage_correct=percentage,
        difficulty=difficulty,
        minutes_taken=minutes,
        exam_id=request.exam_id,
    )
    
    service.evaluate_and_grant_badges(resolved_user_id)
    
    return {
        **result,
        "leveled_up": result["level_info"]["level"] > result.get("level_before", 1),
    }


@router.post("/admin/reset-all-xp")
async def reset_all_xp(
    confirm: bool = False,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: Reset ALL user XP to 0 globally.
    Requires confirmation flag to prevent accidental resets.
    Preserves user accounts and non-XP progress.

    SECURITY: previously guarded only by "is logged in", so any student could
    wipe every user's XP. Now requires the admin role.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Must set confirm=true to perform global XP reset"
        )
    
    service = ProgressService(db)
    affected_count = service.reset_all_users_xp()
    
    return {
        "success": True,
        "message": f"Global XP reset completed. {affected_count} user profiles reset to 0 XP.",
        "affected_users": affected_count,
    }


@router.get("/generation-runs/{run_id}")
async def get_nvo_generation_run(
    run_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    run = db.query(NvoGenerationRun).filter_by(id=run_id).one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return {
        "id": run.id,
        "requested_profile": json.loads(run.requested_profile_json),
        "source": run.source,
        "model": run.model,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/retrieval/preview")
async def preview_nvo_retrieval(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Admin-only: report whether the DB corpus is generation-ready right now."""
    pool = build_slot_pool(db, list(range(1, 24)))
    return {
        "use_db_retrieval_flag": settings.NVO_USE_DB_RETRIEVAL,
        "db_corpus_ready": pool is not None,
        "slots_with_candidates": sorted(pool.keys()) if pool else [],
    }
