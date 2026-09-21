"""QA report over the NVO problem corpus: coverage, balance, and integrity checks.

Implements NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 2's "run QA report and fix
low-confidence records". Read-only — flags problems for a human to review,
never mutates or deactivates anything automatically.
"""
from __future__ import annotations

import json
from collections import Counter

from sqlalchemy.orm import Session

from app.models.nvo_content import NvoProblem

_REQUIRED_SLOTS = set(range(1, 24))
_OPEN_SLOTS = {21, 22, 23}
_MIN_VARIANTS_PER_SLOT = 3


def qa_report(db: Session) -> dict:
    problems = db.query(NvoProblem).filter(NvoProblem.is_active.is_(True)).all()

    by_slot: dict[int, list[NvoProblem]] = {}
    for p in problems:
        by_slot.setdefault(p.slot_number, []).append(p)

    missing_slots = sorted(_REQUIRED_SLOTS - set(by_slot.keys()))
    thin_slots = sorted(
        slot for slot, rows in by_slot.items() if len(rows) < _MIN_VARIANTS_PER_SLOT
    )

    integrity_issues: list[dict] = []
    for p in problems:
        issues = []
        if not p.statement or not p.statement.strip():
            issues.append("empty_statement")
        if not p.correct_answer_json:
            issues.append("missing_correct_answer")
        expected_format = "open" if p.slot_number in _OPEN_SLOTS else "mcq"
        if p.answer_format != expected_format:
            issues.append(f"answer_format_mismatch:expected_{expected_format}")
        if p.answer_format == "mcq":
            options = json.loads(p.options_json) if p.options_json else []
            if len(options) != 4:
                issues.append("mcq_without_4_options")
        if issues:
            integrity_issues.append({"problem_id": p.id, "slot_number": p.slot_number, "issues": issues})

    difficulty_distribution = Counter(p.difficulty for p in problems)

    return {
        "total_active_problems": len(problems),
        "missing_slots": missing_slots,
        "thin_slots": thin_slots,
        "integrity_issues": integrity_issues,
        "difficulty_distribution": dict(difficulty_distribution),
        "is_generation_ready": not missing_slots and not integrity_issues,
    }
