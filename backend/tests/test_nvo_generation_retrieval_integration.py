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


@pytest.fixture
def full_corpus(db):
    """Seed all 23 slots with one active problem each; clean up on teardown.

    The shared `db` fixture only rolls back *uncommitted* changes, and this
    helper must commit (build_slot_pool queries via a separate SessionLocal()
    session in app.routers.nvo), so the rows it creates are tracked by id and
    explicitly deleted here rather than left to leak into later tests/runs.
    """
    open_slots = {21, 22, 23}
    topic_ids: list[int] = []
    problem_ids: list[int] = []
    for slot in range(1, 24):
        topic = NvoTopic(code=f"topic-{slot}", name=f"Topic {slot}")
        db.add(topic)
        db.flush()
        topic_ids.append(topic.id)
        problem = NvoProblem(
            topic_id=topic.id,
            external_ref=f"seed-{slot}",
            slot_number=slot,
            answer_format="open" if slot in open_slots else "mcq",
            statement=f"question {slot}",
            options_json=None if slot in open_slots else json.dumps(["А", "Б", "В", "Г"]),
            correct_answer_json=json.dumps(["a"]) if slot in open_slots else json.dumps("А"),
            difficulty="easy",
        )
        db.add(problem)
        db.flush()
        problem_ids.append(problem.id)
    db.commit()

    yield

    db.query(NvoProblem).filter(NvoProblem.id.in_(problem_ids)).delete(synchronize_session=False)
    db.query(NvoTopic).filter(NvoTopic.id.in_(topic_ids)).delete(synchronize_session=False)
    db.commit()


def test_flag_on_with_full_corpus_uses_db(db, full_corpus):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True

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
    assert json.loads(run.output_json) == {"exam_id": "abc123"}

    db.query(NvoGenerationRun).filter_by(id=run.id).delete()
    db.commit()
