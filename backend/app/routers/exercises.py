import ast
import operator
import re
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.auth.dependencies import get_optional_user
from app.database import get_db
from app.config import settings
from app.services.openai_client import openai_client
from app.models.curriculum import Exercise as ExerciseModel, ExerciseAttempt as ExerciseAttemptModel
from app.models.user import User
from app.schemas.curriculum import ExerciseAttemptCreate, ExerciseSubmissionResponse
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/exercises", tags=["Exercises"])


def _resolve_user_id(current_user: Optional[User], user_id: Optional[int]) -> int:
    if current_user is not None:
        return int(cast(int, current_user.id))
    raise HTTPException(status_code=401, detail="Not authenticated")


def normalize_answer(answer: str) -> str:
    """
    Normalize answer for comparison (remove spaces, convert to lowercase)
    """
    return answer.strip().lower().replace(" ", "")


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _latex_to_math_expr(value: str) -> str:
    expr = value or ""
    expr = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", expr)
    expr = expr.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    expr = expr.replace("^", "**")
    return expr


def _safe_eval_math(expr: str) -> float:
    node = ast.parse(expr, mode="eval")

    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.operand))
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        raise ValueError("Unsupported expression")

    return float(_eval(node))


def _numbers_from_text(value: str) -> list[float]:
    raw = value.replace(",", ".")
    parts = re.findall(r"-?\d+(?:\.\d+)?", raw)
    return [float(p) for p in parts]


def _local_equivalence_check(submitted_answer: str, correct_answer: str) -> bool:
    submitted_norm = normalize_answer(submitted_answer)
    correct_norm = normalize_answer(correct_answer)
    if submitted_norm == correct_norm:
        return True

    # Try numeric expression equivalence
    try:
        s_val = _safe_eval_math(_latex_to_math_expr(submitted_norm))
        c_val = _safe_eval_math(_latex_to_math_expr(correct_norm))
        if abs(s_val - c_val) <= 1e-9:
            return True
    except Exception:
        pass

    # Try unordered roots/solution lists (e.g., x1=2,x2=3 vs x1=3,x2=2)
    try:
        s_nums = sorted(_numbers_from_text(submitted_norm))
        c_nums = sorted(_numbers_from_text(correct_norm))
        if s_nums and c_nums and len(s_nums) == len(c_nums):
            if all(abs(a - b) <= 1e-9 for a, b in zip(s_nums, c_nums)):
                return True
    except Exception:
        pass

    return False


def _ai_equivalence_check(question: str, submitted_answer: str, correct_answer: str, solution: str | None) -> bool:
    if not settings.OPENAI_API_KEY:
        return False

    client = openai_client()
    system_prompt = (
        "You are a strict Bulgarian math answer checker. "
        "Decide whether student's answer is mathematically equivalent to the reference answer. "
        "Accept equivalent forms, reordered roots, simplified fractions, and algebraically identical expressions. "
        "Return ONLY JSON: {\"is_equivalent\": true|false}."
    )
    user_prompt = (
        f"Question: {question}\n"
        f"Reference answer: {correct_answer}\n"
        f"Student answer: {submitted_answer}\n"
        f"Reference solution: {solution or ''}"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        import json
        data = json.loads(raw)
        return bool(data.get("is_equivalent", False))
    except Exception:
        return False


@router.post("/{exercise_id}/submit", response_model=ExerciseSubmissionResponse)
async def submit_exercise(
    exercise_id: int,
    submission: ExerciseAttemptCreate,
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Submit an answer to an exercise
    
    - Checks if the answer is correct
    - Stores the attempt in the database
    - Returns whether it's correct and the solution
    """
    # Get the exercise
    exercise = db.query(ExerciseModel).filter(ExerciseModel.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    
    # SECURITY: resolve the caller BEFORE any OpenAI call. _ai_equivalence_check
    # embeds attacker-supplied text in a prompt, so running it ahead of the auth
    # check let an anonymous caller burn our OpenAI key and only then get a 401.
    resolved_user_id = _resolve_user_id(current_user, user_id)

    # Multi-stage correctness check: local strict/equivalence first, then AI equivalence.
    canonical_answer = str(exercise.answer)
    is_correct = _local_equivalence_check(submission.answer, canonical_answer)
    if not is_correct:
        # Off the event loop: a blocking completion here stalled every other
        # request the process was serving until it returned.
        is_correct = await run_in_threadpool(
            _ai_equivalence_check,
            question=str(exercise.question),
            submitted_answer=submission.answer,
            correct_answer=canonical_answer,
            solution=str(exercise.solution) if exercise.solution is not None else None,
        )

    # Create exercise attempt for the authenticated user.
    attempt = ExerciseAttemptModel(
        user_id=resolved_user_id,
        exercise_id=exercise_id,
        submitted_answer=submission.answer,
        is_correct=is_correct
    )
    
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    # Update progress tracking
    progress_service = ProgressService(db)
    progress_service.update_progress_after_submission(user_id=resolved_user_id, exercise_id=exercise_id)

    xp_before = progress_service.get_xp_summary(user_id=resolved_user_id)
    level_before = xp_before["level"]

    xp_gained = progress_service.award_exercise_xp(user_id=resolved_user_id, exercise_id=exercise_id, is_correct=is_correct)

    xp_after = progress_service.get_xp_summary(user_id=resolved_user_id) if xp_gained > 0 else xp_before
    level_after = xp_after["level"]

    # Evaluate badges after every submission
    progress_service.evaluate_and_grant_badges(user_id=resolved_user_id)

    # Return response
    return ExerciseSubmissionResponse(
        correct=is_correct,
        solution=str(exercise.solution) if exercise.solution is not None else "Решението не е налично.",
        submitted_answer=submission.answer,
        correct_answer=str(exercise.answer) if not is_correct else None,
        xp_gained=xp_gained,
        leveled_up=level_after > level_before,
        new_level=level_after,
    )


@router.get("/{exercise_id}/attempts")
async def get_exercise_attempts(
    exercise_id: int,
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get all attempts for a specific exercise (for analytics/debugging)
    """
    exercise = db.query(ExerciseModel).filter(ExerciseModel.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    
    resolved_user_id = _resolve_user_id(current_user, user_id)

    attempts = db.query(ExerciseAttemptModel).filter(
        ExerciseAttemptModel.exercise_id == exercise_id,
        ExerciseAttemptModel.user_id == resolved_user_id,
    ).order_by(ExerciseAttemptModel.created_at.desc()).limit(50).all()
    
    return {
        "exercise_id": exercise_id,
        "total_attempts": len(attempts),
        "correct_attempts": sum(1 for a in attempts if a.is_correct is True),
        "attempts": [
            {
                "id": a.id,
                "submitted_answer": a.submitted_answer,
                "is_correct": a.is_correct,
                "created_at": a.created_at
            }
            for a in attempts
        ]
    }
