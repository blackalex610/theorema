"""Backfill NvoTopic/NvoSourceExam/NvoProblem rows from nvo_question_catalog.json.

Implements NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 2. Idempotent: re-running
upserts by (slot_number, external_ref) instead of duplicating rows, so it is
safe to run again after every catalog edit.

Run directly: `python -m app.services.nvo_content_backfill`
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.nvo_content import NvoProblem, NvoSourceExam, NvoTopic

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parents[2] / "nvo_question_catalog.json"
_OPEN_SLOTS = {21, 22, 23}
_SOURCE_RE = re.compile(r"^(\d{4})_v(\d+)$")


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_or_create_topic(db: Session, code: str, notes: str) -> NvoTopic:
    topic = db.query(NvoTopic).filter_by(code=code).one_or_none()
    if topic is None:
        topic = NvoTopic(code=code, name=code.replace("_", " ").capitalize(), notes=notes)
        db.add(topic)
        db.flush()
    elif notes and topic.notes != notes:
        topic.notes = notes
    return topic


def _get_or_create_source_exam(db: Session, source_ref: str) -> NvoSourceExam | None:
    match = _SOURCE_RE.match(source_ref)
    if not match:
        return None
    year, variant = int(match.group(1)), f"v{match.group(2)}"
    exam = (
        db.query(NvoSourceExam)
        .filter_by(year=year, variant=variant, source_type="official")
        .one_or_none()
    )
    if exam is None:
        exam = NvoSourceExam(
            title=f"{year} NVO official exam ({variant})",
            year=year,
            variant=variant,
            source_type="official",
        )
        db.add(exam)
        db.flush()
    return exam


def backfill_catalog(db: Session, catalog: dict) -> dict:
    """Upsert every slot/variant in `catalog` into the DB. Returns a summary dict."""
    slots = catalog.get("slots", {})
    created, updated = 0, 0

    for slot_key, slot in slots.items():
        slot_number = int(slot_key)
        answer_format = "open" if slot_number in _OPEN_SLOTS else "mcq"
        topic = _get_or_create_topic(db, slot.get("topic", "general"), slot.get("notes", ""))

        for variant in slot.get("variants", []):
            external_ref = str(variant.get("source", ""))
            if not external_ref:
                logger.warning("Skipping slot %s variant with no source ref", slot_number)
                continue

            source_exam = _get_or_create_source_exam(db, external_ref)
            existing = (
                db.query(NvoProblem)
                .filter_by(slot_number=slot_number, external_ref=external_ref)
                .one_or_none()
            )

            options = variant.get("options")
            open_parts = variant.get("open_parts")
            fields = dict(
                source_exam_id=source_exam.id if source_exam else None,
                topic_id=topic.id,
                answer_format=answer_format,
                statement=str(variant.get("question", "")),
                options_json=json.dumps(options, ensure_ascii=False) if options else None,
                correct_answer_json=json.dumps(variant.get("correct_answer"), ensure_ascii=False),
                open_parts_json=json.dumps(open_parts, ensure_ascii=False) if open_parts else None,
                difficulty=variant.get("difficulty", "medium"),
            )

            if existing is None:
                db.add(NvoProblem(slot_number=slot_number, external_ref=external_ref, **fields))
                created += 1
            else:
                for key, value in fields.items():
                    setattr(existing, key, value)
                updated += 1

    db.commit()
    return {"created": created, "updated": updated, "slots": len(slots)}


def run() -> dict:
    catalog = load_catalog()
    db = SessionLocal()
    try:
        return backfill_catalog(db, catalog)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(), indent=2, ensure_ascii=False))
