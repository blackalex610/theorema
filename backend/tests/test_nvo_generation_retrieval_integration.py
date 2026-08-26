"""Integration tests for DB-backed vs file-catalog NVO generation source selection."""
import json

import pytest

from app.config import settings
from app.models.nvo_content import NvoGenerationRun, NvoProblem, NvoTopic


@pytest.fixture(autouse=True)
def _reset_flags():
    original_db = settings.NVO_USE_DB_RETRIEVAL
    original_emb = settings.NVO_USE_EMBEDDING_RETRIEVAL
    yield
    settings.NVO_USE_DB_RETRIEVAL = original_db
    settings.NVO_USE_EMBEDDING_RETRIEVAL = original_emb


def test_flag_off_always_uses_file_catalog(db):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = False
    catalog, source = _load_catalog_or_db()
    assert source == "file_catalog"
    assert "slots" in catalog


def test_flag_on_with_empty_db_falls_back_to_file_catalog(db):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True
    catalog, source = _load_catalog_or_db()
    assert source == "file_catalog"


def _seed_full_corpus(db):
    open_slots = {21, 22, 23}
    for slot in range(1, 24):
        topic = NvoTopic(code=f"topic-{slot}", name=f"Topic {slot}")
        db.add(topic)
        db.flush()
        db.add(NvoProblem(
            topic_id=topic.id,
            external_ref=f"seed-{slot}",
            slot_number=slot,
            answer_format="open" if slot in open_slots else "mcq",
            statement=f"question {slot}",
            options_json=None if slot in open_slots else json.dumps(["А", "Б", "В", "Г"]),
            correct_answer_json=json.dumps(["a"]) if slot in open_slots else json.dumps("А"),
            difficulty="easy",
        ))
    db.commit()


def test_flag_on_with_full_corpus_uses_db(db):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True
    _seed_full_corpus(db)

    catalog, source = _load_catalog_or_db()
    assert source == "db"
    assert len(catalog["slots"]) == 23


def test_record_generation_run_persists_row(db):
    from app.routers.nvo import NVOExam, _record_generation_run

    exam = NVOExam(exam_id="abc123", questions=[])
    _record_generation_run(profile={"format": "full"}, source="file_catalog", exam=exam, model=None)

    run = db.query(NvoGenerationRun).order_by(NvoGenerationRun.id.desc()).first()
    assert run is not None
    assert run.source == "file_catalog"
    assert json.loads(run.requested_profile_json) == {"format": "full"}
