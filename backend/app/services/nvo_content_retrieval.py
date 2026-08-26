"""Deterministic metadata-filter retrieval over the NVO problem corpus.

Implements NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 1/3: the DB-backed read
path is used when `settings.NVO_USE_DB_RETRIEVAL` is on and the corpus has
content for every slot the caller needs; otherwise the caller falls back to
the file-based catalog (app.routers.nvo.load_nvo_catalog). This module never
raises on a missing/partial corpus — it returns None/empty and lets the
caller fall back.
"""
from __future__ import annotations

import json
import logging
import random

from sqlalchemy.orm import Session

from app.models.nvo_content import NvoProblem, NvoTopic

logger = logging.getLogger(__name__)


def get_slot_candidates(db: Session, slot_number: int, limit: int = 20) -> list[NvoProblem]:
    """Active problems eligible for one NVO template slot, best quality first."""
    return (
        db.query(NvoProblem)
        .filter(NvoProblem.slot_number == slot_number, NvoProblem.is_active.is_(True))
        .order_by(NvoProblem.quality_score.desc(), NvoProblem.id.asc())
        .limit(limit)
        .all()
    )


def build_slot_pool(db: Session, slot_numbers: list[int]) -> dict[int, list[NvoProblem]] | None:
    """Candidate lists for every requested slot, or None if any slot is empty.

    A partial corpus is treated as "not ready": generation must not silently
    mix a DB-sourced slot with the file catalog's slot for the same exam, so
    one missing slot fails the whole DB path and the caller uses the file
    catalog for all slots instead.
    """
    pool: dict[int, list[NvoProblem]] = {}
    for slot_number in slot_numbers:
        candidates = get_slot_candidates(db, slot_number)
        if not candidates:
            logger.info("NVO DB retrieval: slot %s has no active candidates; falling back", slot_number)
            return None
        pool[slot_number] = candidates
    return pool


def problem_to_variant(problem: NvoProblem) -> dict:
    """Shape one NvoProblem like a catalog `variants[]` entry."""
    return {
        "source": problem.external_ref,
        "question": problem.statement,
        "options": json.loads(problem.options_json) if problem.options_json else None,
        "open_parts": json.loads(problem.open_parts_json) if problem.open_parts_json else None,
        "correct_answer": json.loads(problem.correct_answer_json),
        "difficulty": problem.difficulty,
    }


def slot_pool_to_catalog(db: Session, pool: dict[int, list[NvoProblem]]) -> dict:
    """Shape a DB-sourced slot pool like `load_nvo_catalog()`'s `{"slots": {...}}`."""
    topics = {t.id: t for t in db.query(NvoTopic).all()}
    slots: dict[str, dict] = {}
    for slot_number, candidates in pool.items():
        topic = topics.get(candidates[0].topic_id)
        slots[str(slot_number)] = {
            "topic": topic.code if topic else "general",
            "notes": (topic.notes or "") if topic else "",
            "variants": [problem_to_variant(p) for p in candidates],
        }
    return {"slots": slots}


def select_variant_for_slot(candidates: list[NvoProblem]) -> NvoProblem:
    return random.choice(candidates)
