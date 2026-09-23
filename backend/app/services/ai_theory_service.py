from openai import OpenAI, RateLimitError, AuthenticationError
from openai.types.chat import ChatCompletionMessageParam
from app.config import settings
import json
from typing import Any


class AIQuotaExceededError(RuntimeError):
    pass


class AIConfigurationError(RuntimeError):
    pass


class AIServiceError(RuntimeError):
    pass


def _raise_ai_error(exc: Exception) -> None:
    message = str(exc).lower()
    if isinstance(exc, RateLimitError) and "insufficient_quota" in message:
        raise AIQuotaExceededError(
            "OpenRouter quota exceeded. Update billing or replace OPENROUTER_API_KEY in backend/.env."
        ) from exc
    if isinstance(exc, AuthenticationError):
        raise AIConfigurationError(
            "Invalid OpenRouter API key. Check OPENROUTER_API_KEY in backend/.env."
        ) from exc
    if "insufficient_quota" in message:
        raise AIQuotaExceededError(
            "OpenRouter quota exceeded. Update billing or replace OPENROUTER_API_KEY in backend/.env."
        ) from exc
    raise AIServiceError("AI request failed. Please try again.") from exc


def _get_client() -> OpenAI:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured")
    return OpenAI(api_key=settings.OPENROUTER_API_KEY, base_url=settings.OPENROUTER_BASE_URL)


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        loaded = json.loads(text[start : end + 1])
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return None

    return None


def _fallback_diagram_from_text(problem_text: str) -> dict[str, Any]:
    text = problem_text.lower()

    if "успоред" in text or "правите" in text:
        return {
            "type": "parallel_lines",
            "elements": {
                "lines": [
                    {"y": 60, "label": "c"},
                    {"y": 120, "label": "d"},
                ],
                "transversal": {
                    "from": {"x": 30, "y": 20},
                    "to": {"x": 170, "y": 180},
                },
                "angles": {
                    "alpha": "?",
                },
            },
        }

    if "координат" in text or "ос" in text:
        return {
            "type": "coordinate_plane",
            "elements": {
                "points": [
                    {"x": 2, "y": 3, "label": "A"},
                    {"x": -2, "y": 3, "label": "B"},
                ],
                "grid": True,
                "axes": True,
            },
        }

    if "правоъгълник" in text:
        return {
            "type": "rectangle",
            "elements": {
                "points": [
                    {"x": 40, "y": 40, "label": "A"},
                    {"x": 160, "y": 40, "label": "B"},
                    {"x": 160, "y": 120, "label": "C"},
                    {"x": 40, "y": 120, "label": "D"},
                ],
                "sides": [["A", "B"], ["B", "C"], ["C", "D"], ["D", "A"]],
                "angles": {"A": 90, "B": 90, "C": 90, "D": 90},
            },
        }

    if "куб" in text:
        return {
            "type": "cube",
            "elements": {
                "front_face": [
                    {"x": 50, "y": 70, "label": "A"},
                    {"x": 120, "y": 70, "label": "B"},
                    {"x": 120, "y": 140, "label": "C"},
                    {"x": 50, "y": 140, "label": "D"},
                ],
                "back_face": [
                    {"x": 80, "y": 40, "label": "E"},
                    {"x": 150, "y": 40, "label": "F"},
                    {"x": 150, "y": 110, "label": "G"},
                    {"x": 80, "y": 110, "label": "H"},
                ],
            },
        }

    return {
        "type": "triangle",
        "elements": {
            "points": [
                {"x": 50, "y": 150, "label": "A"},
                {"x": 160, "y": 150, "label": "B"},
                {"x": 100, "y": 60, "label": "C"},
            ],
            "sides": [["A", "B"], ["B", "C"], ["C", "A"]],
            "angles": {"A": "?", "B": "?", "C": "?"},
        },
    }


def generate_theory_content(
    *,
    lesson_title: str,
    topic_title: str,
    grade_number: int,
    detail_level: str = "standard",
) -> str:
    """Generate Bulgarian theory content for a lesson using OpenAI.

    detail_level: "concise" | "standard" | "detailed"
    """
    client = _get_client()

    system_prompt = (
        "You are a Bulgarian math teacher for 5th-7th grade students. "
        "Write clear and age-appropriate lesson theory in Bulgarian. "
        "Use plain language, step-by-step examples, and short sections."
    )

    if detail_level == "concise":
        detail_instruction = (
            "Write a SHORT summary only. "
            "Include: 'Накратко' (2-3 sentences overview), 'Формула / Правило' (key formula or rule), "
            "'Пример' (one brief worked example). "
            "Total length: ~150 words. No extra sections."
        )
    elif detail_level == "detailed":
        detail_instruction = (
            "Write a COMPREHENSIVE explanation. "
            "Include these sections with Bulgarian headings: "
            "'Какво ще научим', 'Защо е важно', 'Обяснение стъпка по стъпка', "
            "'Пример 1', 'Пример 2', 'Пример 3', "
            "'Чести грешки', 'Допълнителни бележки', 'Бърза проверка'. "
            "Be thorough — include all edge cases, additional notes, and multiple worked examples. "
            "Total length: ~500 words."
        )
    else:  # standard
        detail_instruction = (
            "Write a balanced explanation. "
            "Include these sections with Bulgarian headings: "
            "'Какво ще научим', 'Обяснение', 'Пример 1', 'Пример 2', "
            "'Чести грешки', 'Бърза проверка'. "
            "Keep it concise but useful. Total length: ~250 words."
        )


    user_prompt = f"""
Generate lesson theory in Bulgarian for:
- Grade: {grade_number}
- Topic category: {topic_title}
- Concept/Lesson: {lesson_title}

Requirements:
1) Output ALL lesson text as Markdown (headings, lists, bold, italics, tables, code blocks, blockquotes, etc. where appropriate). DO NOT use markdown code fences.
2) {detail_instruction}
3) Use simple formulas inline where helpful, using LaTeX math in $...$ for inline and $$...$$ for display math.
4) Use clear section headings and structure for readability.
5) Use tables, lists, and formatting to make the content visually appealing and easy to read.
""".strip()


    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ai_theory_service")

    print(f"[DEBUG] BEFORE OpenAI call: lesson='{lesson_title}', topic='{topic_title}', grade={grade_number}, detail_level={detail_level}")
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        print(f"[DEBUG] AFTER OpenAI call: lesson='{lesson_title}' (length={len(response.choices[0].message.content) if response.choices and response.choices[0].message.content else 0})")
    except Exception as e:
        print(f"[DEBUG] ERROR during OpenAI completion: {e}")
        _raise_ai_error(e)

    return response.choices[0].message.content or "Няма генерирано съдържание."


def generate_theory_from_standard(
    *,
    standard_content: str,
    lesson_title: str,
    detail_level: str,
) -> str:
    """Generate a concise or detailed variation of an existing standard explanation."""
    client = _get_client()

    if detail_level == "concise":
        instruction = (
            "Rewrite the theory below as a SHORT summary in Bulgarian. "
            "Keep ONLY: 'Накратко' (2-3 sentences overview), 'Формула / Правило' (key formula), "
            "'Пример' (one brief worked example). ~150 words total. "
            "Use the same Markdown + LaTeX ($...$ inline, $$...$$ display) style."
        )
    else:  # detailed
        instruction = (
            "Expand the theory below into a COMPREHENSIVE explanation in Bulgarian. "
            "Add more worked examples (at least 3), explain edge cases, add 'Чести грешки' "
            "(common mistakes) and 'Допълнителни бележки' sections. ~500 words total. "
            "Use the same Markdown + LaTeX ($...$ inline, $$...$$ display) style."
        )

    user_prompt = f"""
Here is the standard explanation for "{lesson_title}":

{standard_content}

---
{instruction}
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a Bulgarian math teacher. Rewrite lesson content as instructed."},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        _raise_ai_error(e)

    return response.choices[0].message.content or "Няма генерирано съдържание."


def generate_video_search_queries(*, lesson_title: str, topic_title: str, grade_number: int) -> list[str]:
    """Generate Bulgarian YouTube-friendly search phrases for a lesson."""
    client = _get_client()

    system_prompt = (
        "You create short Bulgarian YouTube search phrases for school math topics. "
        "Return only plain lines, one query per line, no numbering."
    )

    user_prompt = f"""
Generate 6 short YouTube search queries in Bulgarian for:
- Grade: {grade_number}
- Category: {topic_title}
- Concept: {lesson_title}

Rules:
1) Keep each query short and natural.
2) Include variants with simpler wording.
3) Include one broad query and one exam-oriented query.
4) Output only the queries, one per line.
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.5,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        _raise_ai_error(exc)

    raw = response.choices[0].message.content or ""
    queries = []
    for line in raw.splitlines():
        clean = line.strip().lstrip("-•0123456789. ")
        if clean:
            queries.append(clean)

    # De-duplicate while preserving order
    unique_queries = list(dict.fromkeys(queries))
    return unique_queries[:6]


def generate_example_problems(*, lesson_title: str, topic_title: str, grade_number: int) -> list[dict[str, str]]:
    """Generate short example problems with solutions in Bulgarian."""
    client = _get_client()

    system_prompt = (
        "You are a Bulgarian math teacher for 5th-7th grade students. "
        "Generate concise example problems with clean, correct solutions."
    )

    user_prompt = f"""
Generate exactly 4 example problems for:
- Grade: {grade_number}
- Category: {topic_title}
- Concept: {lesson_title}

Return ONLY valid JSON in this exact format (no markdown, no code fences):
{{
  "examples": [
    {{"difficulty": "easy", "problem": "...", "solution": "..."}},
    {{"difficulty": "easy", "problem": "...", "solution": "..."}},
    {{"difficulty": "medium", "problem": "...", "solution": "..."}},
    {{"difficulty": "hard", "problem": "...", "solution": "..."}}
  ]
}}

Rules:
1) Write everything in Bulgarian.
2) Keep each problem short and practical.
3) Keep each solution short and step-by-step.
4) Use exactly: 2 easy, 1 medium, 1 hard.
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.5,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        _raise_ai_error(exc)

    raw = response.choices[0].message.content or ""
    try:
        data = _parse_json_object(raw) or {}
        raw_examples = data.get("examples", [])
        examples: list[dict[str, str]] = []
        for item in raw_examples:
            difficulty = str(item.get("difficulty", "medium")).strip().lower()
            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"
            problem = str(item.get("problem", "")).strip()
            solution = str(item.get("solution", "")).strip()
            if problem and solution:
                examples.append({"difficulty": difficulty, "problem": problem, "solution": solution})
        return examples[:4]
    except Exception:
        return []


def generate_exercises(*, lesson_title: str, topic_title: str, grade_number: int) -> list[dict]:
    """Generate practice exercises with answers for a lesson using OpenAI."""
    client = _get_client()

    system_prompt = (
        "You are a Bulgarian math teacher for 5th-7th grade students. "
        "Generate practice exercises that test understanding of the lesson concept."
    )

    user_prompt = f"""
Generate exactly 5 practice exercises for:
- Grade: {grade_number}
- Category: {topic_title}
- Concept: {lesson_title}

Return ONLY valid JSON in this exact format:
{{
  "exercises": [
    {{
      "question": "...",
      "answer": "...",
      "solution": "...",
      "difficulty": "easy|medium|hard",
      "exercise_type": "numeric|multiple_choice|text"
    }}
  ]
}}

Rules:
1) Write everything in Bulgarian.
2) Each question must be unique and test a different aspect of the concept.
3) Include a mix of difficulties: 2 easy, 2 medium, 1 hard.
4) Include a brief step-by-step solution for each.
5) No markdown code fences.
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.5,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        _raise_ai_error(exc)

    raw = response.choices[0].message.content or ""
    try:
        data = _parse_json_object(raw) or {}
        raw_exercises = data.get("exercises", [])
        exercises: list[dict] = []
        for item in raw_exercises:
            difficulty = str(item.get("difficulty", "medium")).strip().lower()
            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"
            exercise_type = str(item.get("exercise_type", "numeric")).strip().lower()
            if exercise_type not in {"numeric", "multiple_choice", "text"}:
                exercise_type = "numeric"
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            solution = str(item.get("solution", "")).strip()
            if question and answer:
                exercises.append({
                    "question": question,
                    "answer": answer,
                    "solution": solution,
                    "difficulty": difficulty,
                    "exercise_type": exercise_type,
                })
        return exercises[:5]
    except Exception:
        return []


def generate_chat_reply(*, messages: list[dict], lesson_title: str | None = None) -> str:
    """Generate a conversational math tutoring reply using OpenAI."""
    client = _get_client()

    context = f" The student is currently studying: {lesson_title}." if lesson_title else ""

    system_prompt = (
        "You are a friendly and helpful Bulgarian math tutor for 5th-7th grade students."
        f"{context} "
        "Answer questions clearly in Bulgarian, use simple language, "
        "provide step-by-step explanations when needed, and encourage the student. "
        "Keep responses concise and focused on math."
    )

    typed_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "assistant":
            typed_messages.append({"role": "assistant", "content": content})
        else:
            typed_messages.append({"role": "user", "content": content})

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.6,
            messages=typed_messages,
        )
    except Exception as exc:
        _raise_ai_error(exc)

    return response.choices[0].message.content or "Съжалявам, не успях да генерирам отговор."


def generate_diagram_json(*, problem_text: str) -> dict[str, Any]:
    """Generate structured diagram JSON for a Bulgarian math problem."""
    client = _get_client()

    system_prompt = """
You are an AI that generates structured diagram data for math problems.

Your job is NOT to generate images.
Your job is to output clean JSON that can be rendered as SVG in a React application.

IMPORTANT:
- Output ONLY JSON
- Do NOT include explanations
- The JSON must be consistent and predictable

SUPPORTED DIAGRAM TYPES:
1. triangle
2. parallel_lines
3. coordinate_plane
4. rectangle
5. cube

GENERAL FORMAT:
{
  "type": "triangle | parallel_lines | coordinate_plane | rectangle | cube",
  "elements": { ... }
}

RULES:
- Use simple coordinates (0–200 range)
- Always include labels (A, B, C, etc.)
- Keep diagrams clean and readable
- If angles are involved, include them in "angles"
- If lengths are given, include them in "lengths"
""".strip()

    user_prompt = f"""
Given the following Bulgarian math problem, generate one diagram JSON.

Problem:
{problem_text}

Return ONLY valid JSON.
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        _raise_ai_error(exc)

    raw = (response.choices[0].message.content or "").strip()

    # Handle common model wrappers like markdown fences and extra text.
    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return _fallback_diagram_from_text(problem_text)
        snippet = cleaned[start : end + 1]
        try:
            data = json.loads(snippet)
        except Exception:
            return _fallback_diagram_from_text(problem_text)

    diagram_type = data.get("type")
    if diagram_type not in {"triangle", "parallel_lines", "coordinate_plane", "rectangle", "cube"}:
        return _fallback_diagram_from_text(problem_text)

    if not isinstance(data.get("elements"), dict):
        return _fallback_diagram_from_text(problem_text)

    return data
