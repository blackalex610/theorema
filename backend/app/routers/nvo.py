from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import Callable, List, Union, cast
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
    increment_usage,
    require_admin,
    require_nvo_exam,
    require_nvo_exam_capacity,
)
from app.models.user import User
from app.models.nvo_content import NvoGenerationRun
from app.models.nvo_exam import NvoAttempt

# Exam duration by format, in whole minutes. Mirrors
# frontend/src/utils/nvoFormat.ts (SHORT/FULL_EXAM_DURATION_SECONDS) — used
# server-side only to clamp a client-reported completion time (see
# award_nvo_exam_xp), never to enforce the timer itself.
_EXAM_DURATION_MINUTES = {"short": 30, "full": 90}

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
    # Per-sub-part marks, straight off the official keys ("2 т., при един верен
    # отговор"). Carried from generation so the marking screen can award
    # partial credit instead of treating every item as all-or-nothing.
    points: List[int] | None = None
    # "mc" | "short" | "open". The 2026 format reinstated a short-answer block
    # between the multiple choice and the extended items; before that Part 1
    # was multiple choice throughout.
    kind: str | None = None


class NVOExam(BaseModel):
    exam_id: str
    questions: List[NVOQuestion]
    # Threaded through from generation so /nvo/submit and /nvo/award-xp can
    # look these up from the server's own stored copy of the exam instead of
    # trusting a client-supplied value for either.
    #
    # One of 'easy' | 'medium' | 'actual' | 'extra_hard' on anything the
    # blueprint path produced. Older stored exams still carry the previous
    # names ('standard', 'hard'), so every reader goes through
    # ``nvo_gen.difficulty.normalize`` rather than comparing strings.
    difficulty: str = "actual"
    difficulty_label: str | None = None
    format: str = "full"
    # Which exam shape this paper was built to. Absent on papers produced by
    # the legacy catalog path, which is why every field below has a default.
    blueprint: str | None = None
    blueprint_label: str | None = None
    # Where Part 1 ends. The client used to infer this from `number <= 20`,
    # which is right for a 2024/2025 paper and wrong for a 2026 one.
    part1_count: int | None = None
    part1_minutes: int | None = None
    part2_minutes: int | None = None
    total_points: int | None = None
    # Position of the first geometry item, where the official papers print
    # „Чертежите са само за илюстрация…”.
    scale_notice_before: int | None = None
    scale_notice: str | None = None


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
    # Added so the score shown to the student — and the percentage handed to
    # /nvo/award-xp — comes from the server's own grading of every question,
    # MCQ included, instead of a client-side computation the client posted
    # back as a bare, unverifiable number.
    mcq_score: int
    mcq_max_score: int
    total_score: int
    total_max_score: int
    percentage_correct: int


class NVOGenerationRequest(BaseModel):
    # 'easy' | 'medium' | 'actual' | 'extra_hard'. 'actual' is the real exam;
    # the others are the same format with easier or harder items. The legacy
    # 'standard' and 'hard' still resolve (to 'actual' and 'extra_hard'), so an
    # un-reloaded client keeps working.
    difficulty: str | None = None
    format: str | None = None  # 'full' (complete sitting) or 'short' (practice run)
    # Which exam shape to build: 'nvo2026' (14 MC + 7 short + 3 open) or
    # 'classic' (20 MC + 3 open, as in 2024 and 2025). Unknown values fall back
    # to the current official format rather than erroring, so an old client
    # keeps working.
    blueprint: str | None = None


def _normalize_difficulty(difficulty: str | None) -> str:
    """Resolve any difficulty spelling to one of the four current codes.

    The catalog and OpenAI paths record whatever they were handed on the
    attempt, and that value later drives the XP multiplier. Normalising here
    means a legacy 'standard' is stored as 'actual' rather than as a fifth,
    undocumented level.
    """
    from app.nvo_gen.difficulty import normalize

    return normalize(difficulty)


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


def _strip_answer_key(exam: "NVOExam") -> "NVOExam":
    """Return a copy of `exam` with every question's correct_answer cleared.

    SECURITY: the exam a client fetches before submitting must never carry
    the answer key. MCQ grading now happens entirely in /nvo/submit against
    the server's own stored copy (returned by _load_exam, untouched by this
    function) — there is nothing left for a client to gain by holding
    correct_answer, so it is not sent at all.
    """
    return exam.model_copy(update={
        "questions": [q.model_copy(update={"correct_answer": None}) for q in exam.questions]
    })


def _normalize_option_key(value: str | None) -> str:
    """Mirror the frontend's normalizeOptionKey (NVOPracticeExamPage.tsx) so
    a Latin 'A' and its Cyrillic look-alike 'А' compare equal, and stray case
    or whitespace from the client never causes a false miss against the
    catalog's Cyrillic-only correct_answer values.
    """
    if not value:
        return ""
    key = value.strip()[:1].upper()
    if key in ("A", "А"):  # Latin A (U+0041) vs Cyrillic А (U+0410)
        return "А"
    return key


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
    progress_callback: Callable[[int, str], None] | None = None,
    difficulty: str | None = None,
) -> NVOExam:
    """Fallback generator: picks one random variant per slot from the catalog.

    For each of the 23 question slots the catalog holds ~5 real official variants.
    This produces a different exam every run while maintaining the correct topic
    at every position.  Diagram slots (Q10-Q15, Q23) are overwritten by
    _inject_playground_problems immediately after.

    `difficulty` does not change which variants are picked here (the catalog
    has no difficulty-aware selection) — it is only recorded on the returned
    exam so the XP multiplier the student chose still applies even when
    generation had to fall back to the pool.
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

    exam = NVOExam(
        exam_id=str(uuid.uuid4())[:8],
        questions=normalized,
        difficulty=_normalize_difficulty(difficulty),
        format=format or "full",
    )
    if settings.NVO_USE_DB_RETRIEVAL:
        _record_generation_run(profile={"format": format, "path": "fallback_pool"}, source=_source, exam=exam, model=None)
    return exam


def _generate_via_blueprint(
    blueprint: str | None,
    difficulty: str | None,
    format: str | None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> NVOExam:
    """Build a paper from item templates against a blueprint.

    This is the primary generation path. Unlike the catalog fallback below it
    does not draw from a fixed pool of transcribed variants — it samples a
    parameter space per slot, so two papers are different rather than
    re-shuffled, and every item is verified before it is returned.

    It is also offline and deterministic, which matters on serverless: no
    OpenAI call, no 75-second timeout to lose a student's daily credit to.

    `difficulty` is real here, unlike on the catalog path below: it re-weights
    which template fills each position and is handed to the templates so they
    can size their own numbers. The blueprint — positions, topics, points — is
    identical at every level, which is the point: "actual" is the real exam and
    the rest are versions of it.
    """
    from app.nvo_gen.api import exam_payload
    from app.nvo_gen.assemble import generate_paper

    if progress_callback:
        progress_callback(15, "Избор на формат на изпита")

    paper = generate_paper(blueprint, short=(format == "short"), difficulty=difficulty)

    if progress_callback:
        progress_callback(70, "Съставяне на задачите и чертежите")

    if not paper.report.ok:
        # The verifier refused the assembled paper. Falling through to the
        # catalog path is better than serving a paper we know is wrong.
        raise ValueError(f"generated paper failed verification: {paper.report.errors}")

    payload = exam_payload(paper, format_=format or "full")
    exam = NVOExam(**payload)

    if progress_callback:
        progress_callback(95, "Тестът е готов")
    if settings.NVO_USE_DB_RETRIEVAL:
        _record_generation_run(
            profile={"format": format, "blueprint": paper.blueprint.code, "path": "blueprint"},
            source="blueprint", exam=exam, model=None,
        )
    return exam


def _get_difficulty_instructions(difficulty: str | None) -> str:
    """Return prompt modifications based on difficulty level.

    Four levels, matching the blueprint path. The structure of the paper is
    never negotiable at any of them — only how hard the items are — so every
    branch says so explicitly; left to itself the model shortens the easy paper
    and pads the hard one, which is exactly what must not happen.
    """
    from app.nvo_gen.difficulty import normalize

    common = (
        "\n- Keep the exam STRUCTURE identical to the official format at every "
        "difficulty: same number of questions, same topic per position, same "
        "points per question, same four Cyrillic options А/Б/В/Г.\n"
        "- Difficulty changes only how hard each item is, never the shape of "
        "the paper.\n"
    )

    level = normalize(difficulty)
    if level == 'easy':
        return """
DIFFICULTY: EASY
- Simplify every question relative to the real NVO level
- Use small whole numbers; avoid fractions, negatives and unit conversions
- Reduce multi-step problems to one or two steps
- Use straightforward, concrete word-problem contexts
""" + common
    if level == 'medium':
        return """
DIFFICULTY: MEDIUM
- Slightly below the real NVO level
- Use clean numbers, but keep two-step reasoning where the topic calls for it
- Avoid the hardest angle chases and the multi-concept combinations
- Keep contexts familiar
""" + common
    if level == 'extra_hard':
        return """
DIFFICULTY: EXTRA HARD
- Above the real NVO level
- Add deeper inference requirements and edge cases
- Combine multiple concepts in a single problem
- Use larger and less friendly numbers, and more steps per item
- Prefer the harder variant of each topic wherever one exists
""" + common
    return """
DIFFICULTY: ACTUAL (the real NVO exam)
- Match the official NVO difficulty exactly — no simplification, no escalation
- Use balanced complexity appropriate for 7th grade
- Follow the difficulty distribution of the official papers
""" + common


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

    exam = NVOExam(
        exam_id=str(uuid.uuid4())[:8],
        questions=validated,
        difficulty=_normalize_difficulty(difficulty),
        format=format or "full",
    )
    if settings.NVO_USE_DB_RETRIEVAL:
        _record_generation_run(
            profile={"format": format, "difficulty": difficulty, "path": "openai"},
            source=_source,
            exam=exam,
            model=settings.OPENAI_NVO_MODEL,
        )
    return exam


def _run_generation_job(job_id: str, difficulty: str | None = None, format: str | None = None,
                        blueprint: str | None = None) -> None:
    def progress_callback(progress: int, message: str) -> None:
        _set_job_progress(job_id, status="running", progress=progress, message=message)

    try:
        _set_job_progress(job_id, status="running", progress=2, message="Създаване на заявка за нов тест")
        try:
            exam = _generate_via_blueprint(blueprint, difficulty, format, progress_callback)
        except Exception:
            logger.exception("blueprint generation failed in job %s; falling back", job_id)
            _set_job_progress(job_id, status="running", progress=25,
                              message="Превключване към резервен генератор")
            try:
                exam = _generate_via_openai(difficulty, format, progress_callback)
            except (ValueError, APIError, HTTPException):
                _set_job_progress(job_id, status="running", progress=35, message="AI не е наличен. Превключване към локален генератор")
                exam = _fallback_generate_from_pool(format, progress_callback, difficulty)

        _store_exam(exam)
        _set_job_progress(job_id, status="completed", progress=100, message="Тестът е готов за стартиране", exam_id=exam.exam_id)
    except Exception as exc:
        _set_job_progress(job_id, status="failed", progress=100, message=f"Неуспешно генериране на НВО тест: {exc}")


def _run_generation_job_and_charge(job_id: str, difficulty: str | None, format: str | None,
                                   user_id: int, blueprint: str | None = None) -> None:
    """Generate the exam, then charge the daily nvo_exams credit only if it
    actually succeeded.

    Runs as a background task (see create_nvo_generation_job) with no
    request-scoped DB session of its own, so it opens a fresh one just for
    the charge — the same pattern nvo_exam_store already uses for background
    persistence.
    """
    _run_generation_job(job_id, difficulty, format, blueprint)

    job = _load_job(job_id)
    if not job or job.status != "completed":
        return  # nothing to charge; the job's own status/message explains why

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one_or_none()
        if user is not None:
            increment_usage(user, db, "nvo_exams")
    except HTTPException:
        # Capacity was spent elsewhere between the pre-flight check and here
        # (e.g. two tabs racing the last credit of the day). The exam still
        # exists and is gradeable; just log rather than fail a job that
        # already reports "completed" to the poller.
        logger.warning("nvo_exams credit already exhausted for user %s at charge time", user_id)
    finally:
        db.close()


@router.post("/generate")
async def generate_nvo_exam(
    request: NVOGenerationRequest | None = None,
    current_user: User = Depends(require_nvo_exam_capacity),
    db: Session = Depends(get_db),
) -> NVOExam:
    """Generate a fresh NVO exam each click. Uses OpenAI when available, fallback otherwise.

    Previously called the generators with no arguments, so the caller's
    difficulty and format were silently discarded and every exam came back as
    a standard-difficulty full exam. Separately, the daily credit used to be
    charged before generation ran at all (require_nvo_exam); it is now
    charged only once an exam has actually been produced and stored.
    """
    difficulty = request.difficulty if request else None
    format = request.format if request else None
    blueprint = request.blueprint if request else None
    try:
        exam = _generate_via_blueprint(blueprint, difficulty, format)
    except Exception:
        logger.exception("blueprint generation failed; falling back")
        try:
            exam = _generate_via_openai(difficulty, format)
        except (ValueError, APIError, HTTPException):
            exam = _fallback_generate_from_pool(format, difficulty=difficulty)
    # Store it so /nvo/submit can grade against the server's own copy of the
    # answers instead of trusting whatever the client posts back.
    _store_exam(exam)
    increment_usage(current_user, db, "nvo_exams")
    return _strip_answer_key(exam)


@router.post("/generate-job", response_model=NVOGenerationJobStatus)
async def create_nvo_generation_job(
    background_tasks: BackgroundTasks,
    request: NVOGenerationRequest | None = None,
    current_user: User = Depends(require_nvo_exam_capacity),
) -> NVOGenerationJobStatus:
    """Queue a generation job and return immediately; the caller polls
    GET /nvo/generate-job/{job_id} for progress.

    Previously this awaited the entire generation inline
    (`await loop.run_in_executor(...)`), so the request blocked for as long
    as generation took — up to the 75s OpenAI timeout — despite the
    "job"/polling shape existing on both sides already. On a platform with a
    much shorter default function timeout that is a guaranteed gateway
    timeout, not just a slow response.

    The daily nvo_exams credit is charged only once the background job
    actually produces an exam (_run_generation_job_and_charge), not here —
    charging on request-in used to cost a student their one-exam-per-day
    credit for a generation that then failed.
    """
    job_id = str(uuid.uuid4())[:8]
    difficulty = request.difficulty if request else None
    format = request.format if request else None
    blueprint = request.blueprint if request else None

    _set_job_progress(job_id, status="queued", progress=0, message="Заявката е приета")
    background_tasks.add_task(
        _run_generation_job_and_charge, job_id, difficulty, format,
        int(current_user.id), blueprint,
    )

    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="NVO generation job missing after queuing")
    return job


@router.get("/blueprints")
async def list_nvo_blueprints() -> dict:
    """The exam shapes a student can choose between.

    Public and unauthenticated on purpose — it is static metadata about the
    format of a state exam, and the picker renders before a student commits a
    daily credit to generating anything.
    """
    from app.nvo_gen.api import blueprint_catalogue

    return {"blueprints": blueprint_catalogue()}


@router.get("/difficulties")
async def list_nvo_difficulties() -> dict:
    """The four levels a student can sit the same paper at.

    Public and unauthenticated for the same reason as /nvo/blueprints: the
    picker renders before a daily credit is spent. `isActual` marks the one
    level that reproduces the real exam — the client highlights it as the
    default rather than hard-coding a string.
    """
    from app.nvo_gen.api import difficulty_catalogue

    return {"difficulties": difficulty_catalogue()}


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
    return _strip_answer_key(exam)


@router.get("/questions")
async def get_nvo_questions(_admin: User = Depends(require_admin)) -> dict:
    """Get all available NVO questions, answer key included — admin only.

    SECURITY: this returns the entire catalog (all 23 slots, every variant,
    every correct_answer) and had no auth at all until now. Anyone who found
    the route could read the full NVO answer key with a single GET.
    """
    return load_nvo_questions()


@router.post("/submit", response_model=NVOExamSubmitResponse)
async def submit_nvo_exam(
    payload: NVOExamSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NVOExamSubmitResponse:
    """Grade a finished NVO exam — every question, MCQ included — server-side.

    SECURITY: previously unauthenticated (fixed) and, separately, only the
    open-ended questions were graded here at all: MCQ correctness and the
    final percentage were computed in the browser and posted to
    /nvo/award-xp as a bare number with nothing to check it against. This now
    grades MCQs against the server's own stored exam too and writes the
    result to an NvoAttempt row, which /nvo/award-xp reads back instead of
    trusting the request.

    Also removed: falling back to `NVOExam(exam_id=..., questions=payload.questions)`
    when the server had no record of the exam. That trusted the client's own
    `questions` — including correct_answer — whenever the id was unknown, so
    an attacker could submit a fabricated exam_id with a self-chosen answer
    key and have it graded as real. Exams persist for 24h (nvo_exam_store),
    long enough for the longest sitting, so an unknown id is just that.

    The daily nvo_exams credit is charged at generation time, so submitting
    the exam you already paid for must NOT charge a second credit (that would
    make the free tier's 1 exam/day impossible to ever finish).
    """
    exam = _load_exam(payload.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Generated NVO exam not found")

    image_by_problem = {item.problemId: item.image for item in payload.open_answer_images}
    open_results: list[NVOOpenGradeResult] = []
    total_open_score = 0
    total_open_max_score = 0
    mcq_score = 0
    mcq_max_score = 0

    for question in exam.questions:
        if question.options is not None:
            # MCQ — graded here against the server's own stored correct_answer.
            # The client never received that value in the first place (see
            # _strip_answer_key), so it can only report which option it
            # picked; it has nothing left to forge.
            mcq_max_score += 1
            submitted = payload.answers.get(str(question.number), "")
            selected = submitted if isinstance(submitted, str) else ""
            correct = question.correct_answer if isinstance(question.correct_answer, str) else ""
            if selected and _normalize_option_key(selected) == _normalize_option_key(correct):
                mcq_score += 1
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

    total_score = mcq_score + total_open_score
    total_max_score = mcq_max_score + total_open_max_score
    percentage_correct = round(total_score / total_max_score * 100) if total_max_score else 0

    attempt = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == current_user.id, NvoAttempt.exam_id == payload.exam_id)
        .one_or_none()
    )
    if attempt is None:
        attempt = NvoAttempt(user_id=current_user.id, exam_id=payload.exam_id)
        db.add(attempt)
    # xp_awarded / xp_result_json are deliberately left untouched: a resubmit
    # re-grades (network retry, or the exam legitimately re-scored), but must
    # not reopen an XP award that already happened for this attempt.
    attempt.difficulty = exam.difficulty
    attempt.format = exam.format
    attempt.mcq_score = mcq_score
    attempt.mcq_max_score = mcq_max_score
    attempt.open_score = total_open_score
    attempt.open_max_score = total_open_max_score
    attempt.percentage_correct = percentage_correct
    db.commit()

    return NVOExamSubmitResponse(
        exam_id=payload.exam_id,
        open_results=open_results,
        total_open_score=total_open_score,
        total_open_max_score=total_open_max_score,
        mcq_score=mcq_score,
        mcq_max_score=mcq_max_score,
        total_score=total_score,
        total_max_score=total_max_score,
        percentage_correct=percentage_correct,
    )


class NVOAttemptSummary(BaseModel):
    """One graded sitting, as the history list needs it.

    Deliberately not the questions or the submitted answers: generated exams
    live in nvo_exam_store behind a 24h TTL, so anything referencing them
    would go stale while the attempt row does not. Review stays a local-device
    feature; this is the part that has to survive a new device.
    """

    exam_id: str
    difficulty: str
    format: str
    mcq_score: int
    mcq_max_score: int
    open_score: int
    open_max_score: int
    # Summed server-side so every client shows the same headline number.
    score: int
    max_score: int
    percentage_correct: int
    xp_awarded: bool
    created_at: str
    graded_at: str


# A student sees a short recent list, not an archive. The hard ceiling exists
# so a crafted `limit` cannot turn this into an unbounded table scan.
ATTEMPT_HISTORY_DEFAULT_LIMIT = 20
ATTEMPT_HISTORY_MAX_LIMIT = 100


@router.get("/attempts", response_model=List[NVOAttemptSummary])
async def list_nvo_attempts(
    limit: int = ATTEMPT_HISTORY_DEFAULT_LIMIT,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[NVOAttemptSummary]:
    """The signed-in student's own graded NVO attempts, newest first.

    /nvo/submit has written an NvoAttempt row per sitting for a while, but
    nothing read them back: the exam page built its history purely from
    localStorage, so switching devices or clearing browser data wiped every
    past score. The rows were already there — this makes them readable.

    SECURITY: filtered on current_user.id, never a caller-supplied user id.
    An attempt is the student's own exam record and nobody else's.
    """
    safe_limit = max(1, min(int(limit), ATTEMPT_HISTORY_MAX_LIMIT))

    rows = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == current_user.id)
        .order_by(NvoAttempt.graded_at.desc(), NvoAttempt.id.desc())
        .limit(safe_limit)
        .all()
    )

    return [
        NVOAttemptSummary(
            exam_id=row.exam_id,
            difficulty=row.difficulty,
            format=row.format,
            mcq_score=row.mcq_score,
            mcq_max_score=row.mcq_max_score,
            open_score=row.open_score,
            open_max_score=row.open_max_score,
            score=row.mcq_score + row.open_score,
            max_score=row.mcq_max_score + row.open_max_score,
            percentage_correct=row.percentage_correct,
            xp_awarded=bool(row.xp_awarded),
            created_at=row.created_at.isoformat(),
            graded_at=row.graded_at.isoformat(),
        )
        for row in rows
    ]


class NVOAwardXpRequest(BaseModel):
    exam_id: str
    minutes_taken: int  # completion time in minutes; clamped server-side to the exam's own duration


@router.post("/award-xp")
async def award_nvo_exam_xp(
    request: NVOAwardXpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Award XP for NVO exam completion with performance-based calculation.

    Pipeline:
    1. Base XP from percentage correct (10-300 XP based on performance tiers)
    2. Difficulty multiplier (Easy: 0.5x, Standard: 1.0x, Hard: 2.0x)
    3. Time bonus/penalty (0-60min: +40%, 61-75min: +20%, 76-90min: 0%, 91+min: -10%)

    SECURITY: percentage_correct and difficulty used to come straight from
    the request body — plain numbers the client chose, with nothing to check
    them against — so any signed-in caller could award themselves the
    maximum XP on repeat. Both now come from the NvoAttempt row /nvo/submit
    wrote, which the server computed itself. The award is idempotent per
    attempt: xp_awarded plus the cached xp_result_json mean retrying or
    replaying the same exam_id can never grant XP twice.
    """
    attempt = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == current_user.id, NvoAttempt.exam_id == request.exam_id)
        .one_or_none()
    )
    if attempt is None:
        raise HTTPException(
            status_code=400,
            detail="Тестът трябва да бъде предаден (/nvo/submit), преди да получиш XP за него.",
        )

    if attempt.xp_awarded:
        if attempt.xp_result_json:
            return json.loads(attempt.xp_result_json)
        # Flagged as awarded with no cached payload should never happen going
        # forward; refuse rather than risk granting XP a second time.
        raise HTTPException(status_code=409, detail="XP за този тест вече е присъдено.")

    max_minutes = _EXAM_DURATION_MINUTES.get(attempt.format, _EXAM_DURATION_MINUTES["full"])
    minutes = max(0, min(request.minutes_taken, max_minutes))

    resolved_user_id = int(cast(int, current_user.id))
    service = ProgressService(db)
    result = service.award_nvo_exam_xp_detailed(
        user_id=resolved_user_id,
        percentage_correct=attempt.percentage_correct,
        difficulty=attempt.difficulty,
        minutes_taken=minutes,
        exam_id=request.exam_id,
    )
    service.evaluate_and_grant_badges(resolved_user_id)

    result = {
        **result,
        "leveled_up": result["level_info"]["level"] > result.get("level_before", 1),
    }

    attempt.xp_awarded = True
    attempt.xp_result_json = json.dumps(result, ensure_ascii=False)
    db.commit()

    return result


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
