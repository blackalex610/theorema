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


def test_embedding_flag_off_leaves_full_slot_pool_untouched(db, full_corpus):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True
    settings.NVO_USE_EMBEDDING_RETRIEVAL = False

    catalog, source = _load_catalog_or_db()
    assert source == "db"
    assert len(catalog["slots"]["1"]["variants"]) == 1  # unchanged: 1 seeded variant


def test_embedding_flag_on_with_unembedded_corpus_is_a_safe_passthrough(db, full_corpus):
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True
    settings.NVO_USE_EMBEDDING_RETRIEVAL = True
    # full_corpus seeds all 23 slots with one problem each; no embeddings seeded

    catalog, source = _load_catalog_or_db()
    assert source == "db"  # must not crash or fall back just because embeddings are missing


def test_embedding_flag_on_deduplicates_near_identical_variants(db):
    from app.models.nvo_content import NvoProblemEmbedding
    from app.routers.nvo import _load_catalog_or_db

    settings.NVO_USE_DB_RETRIEVAL = True
    settings.NVO_USE_EMBEDDING_RETRIEVAL = True

    open_slots = {21, 22, 23}
    topic_ids: list[int] = []
    problem_ids: list[int] = []
    embedded_problem_ids: list[int] = []

    topic1 = NvoTopic(code="dedup-t1", name="Dedup T1")
    db.add(topic1)
    db.flush()
    topic_ids.append(topic1.id)

    # "a" and "b" are near-duplicates that differ only by whitespace, so they
    # normalize to the same text (see apply_diversity_filter's
    # _normalize_for_lexical_compare) and collapse to one under its 0.85
    # lexical-similarity threshold; "c" is lexically distinct and survives.
    near_dup_variants = []
    for i, (ref, statement, vector) in enumerate([
        ("a", "почти еднакъв въпрос", [1.0, 0.0]),
        ("b", "почти  еднакъв   въпрос", [0.99, 0.01]),
        ("c", "съвсем различен въпрос", [0.0, 1.0]),
    ]):
        p = NvoProblem(
            topic_id=topic1.id, external_ref=ref, slot_number=1, answer_format="mcq",
            statement=statement, options_json=json.dumps(["А", "Б", "В", "Г"]),
            correct_answer_json=json.dumps("А"), difficulty="easy",
        )
        db.add(p)
        db.flush()
        problem_ids.append(p.id)
        emb = NvoProblemEmbedding(problem_id=p.id, embedding_json=json.dumps(vector), embedding_model="m")
        db.add(emb)
        db.flush()
        embedded_problem_ids.append(p.id)
        near_dup_variants.append(p)
    db.commit()

    for slot in list(range(2, 21)) + [21, 22, 23]:
        topic = NvoTopic(code=f"dedup-t{slot}", name=f"Dedup T{slot}")
        db.add(topic)
        db.flush()
        topic_ids.append(topic.id)
        problem = NvoProblem(
            topic_id=topic.id, external_ref=f"dedup-s{slot}", slot_number=slot,
            answer_format="open" if slot in open_slots else "mcq",
            statement=f"q{slot}",
            options_json=None if slot in open_slots else json.dumps(["А", "Б", "В", "Г"]),
            correct_answer_json=json.dumps(["a"]) if slot in open_slots else json.dumps("А"),
            difficulty="easy",
        )
        db.add(problem)
        db.flush()
        problem_ids.append(problem.id)
    db.commit()

    try:
        catalog, source = _load_catalog_or_db()
        assert source == "db"
        slot1_sources = {v["source"] for v in catalog["slots"]["1"]["variants"]}
        assert "c" in slot1_sources
        assert not {"a", "b"} <= slot1_sources  # near-duplicates a & b collapse to one
    finally:
        db.query(NvoProblemEmbedding).filter(NvoProblemEmbedding.problem_id.in_(embedded_problem_ids)).delete(synchronize_session=False)
        db.query(NvoProblem).filter(NvoProblem.id.in_(problem_ids)).delete(synchronize_session=False)
        db.query(NvoTopic).filter(NvoTopic.id.in_(topic_ids)).delete(synchronize_session=False)
        db.commit()
