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
import math
import random
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.nvo_content import NvoProblem, NvoProblemEmbedding, NvoTopic

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


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(
    db: Session, candidates: list[NvoProblem], query_embedding: list[float]
) -> list[tuple[NvoProblem, float]]:
    """Candidates ordered by cosine similarity to `query_embedding`, best first.

    A candidate with no cached embedding sorts last (score 0.0) rather than
    being dropped — an un-embedded row is still a valid metadata-filtered
    candidate, just not semantically ranked yet.
    """
    embeddings = {
        row.problem_id: json.loads(row.embedding_json)
        for row in db.query(NvoProblemEmbedding)
        .filter(NvoProblemEmbedding.problem_id.in_([c.id for c in candidates]))
        .all()
    }
    scored = [
        (c, cosine_similarity(embeddings[c.id], query_embedding) if c.id in embeddings else 0.0)
        for c in candidates
    ]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def _normalize_for_lexical_compare(text: str) -> str:
    return " ".join(text.lower().split())


def apply_diversity_filter(
    ranked: list[tuple[NvoProblem, float]],
    k: int,
    lexical_threshold: float = 0.85,
) -> list[NvoProblem]:
    """Take the top-scoring candidates while rejecting near-duplicates.

    Near-duplicate = statement text similarity (difflib ratio) at or above
    `lexical_threshold` against an already-selected item. Walks the
    similarity-ranked list in order, so ties still prefer the higher-ranked
    (more semantically relevant) variant.
    """
    selected: list[NvoProblem] = []
    for candidate, _score in ranked:
        candidate_text = _normalize_for_lexical_compare(candidate.statement)
        is_duplicate = any(
            SequenceMatcher(None, candidate_text, _normalize_for_lexical_compare(chosen.statement)).ratio()
            >= lexical_threshold
            for chosen in selected
        )
        if is_duplicate:
            continue
        selected.append(candidate)
        if len(selected) >= k:
            break
    return selected
