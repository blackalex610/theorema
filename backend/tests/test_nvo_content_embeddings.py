import json

import pytest

from app.models.nvo_content import NvoProblem, NvoProblemEmbedding, NvoTopic
from app.services import nvo_content_embeddings as embeddings_module
from app.services.nvo_content_embeddings import backfill_embeddings, problems_needing_embeddings


@pytest.fixture
def topic(db):
    t = NvoTopic(code="embeddings_t", name="T")
    db.add(t)
    db.flush()
    yield t
    # Clean up committed data since the db fixture only rolls back uncommitted changes
    # Delete embeddings first, then problems, then the topic
    problem_ids = {p.id for p in db.query(NvoProblem).filter(NvoProblem.topic_id == t.id).all()}
    if problem_ids:
        db.query(NvoProblemEmbedding).filter(NvoProblemEmbedding.problem_id.in_(problem_ids)).delete()
    db.query(NvoProblem).filter(NvoProblem.topic_id == t.id).delete()
    db.query(NvoTopic).filter(NvoTopic.id == t.id).delete()
    db.commit()


def _problem(db, topic, ref="a"):
    p = NvoProblem(
        topic_id=topic.id, external_ref=ref, slot_number=1, answer_format="mcq",
        statement=f"statement {ref}", options_json=json.dumps(["А", "Б", "В", "Г"]),
        correct_answer_json=json.dumps("А"), difficulty="easy",
    )
    db.add(p)
    db.commit()
    return p


def test_problems_needing_embeddings_excludes_already_embedded(db, topic):
    p1 = _problem(db, topic, "a")
    p2 = _problem(db, topic, "b")
    db.add(NvoProblemEmbedding(problem_id=p1.id, embedding_json=json.dumps([0.1, 0.2]), embedding_model="m"))
    db.commit()

    pending = problems_needing_embeddings(db, "m")
    assert [p.id for p in pending] == [p2.id]


def test_backfill_embeddings_stores_vectors(db, topic, monkeypatch):
    p1 = _problem(db, topic, "a")
    p2 = _problem(db, topic, "b")

    monkeypatch.setattr(
        embeddings_module, "embed_texts",
        lambda texts, model: [[float(i)] * 3 for i in range(len(texts))],
    )

    summary = backfill_embeddings(db, model="test-model")

    assert summary == {"embedded": 2, "model": "test-model"}
    rows = db.query(NvoProblemEmbedding).all()
    assert {r.problem_id for r in rows} == {p1.id, p2.id}


def test_backfill_embeddings_is_a_noop_when_nothing_pending(db, topic, monkeypatch):
    _problem(db, topic, "a")
    monkeypatch.setattr(embeddings_module, "embed_texts", lambda texts, model: [[0.0] for _ in texts])
    backfill_embeddings(db, model="test-model")

    calls = []
    monkeypatch.setattr(
        embeddings_module, "embed_texts",
        lambda texts, model: (calls.append(texts), [])[1],
    )
    summary = backfill_embeddings(db, model="test-model")

    assert summary == {"embedded": 0, "model": "test-model"}
    assert calls == []


def test_embed_texts_requires_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ValueError):
        embeddings_module.embed_texts(["x"], "m")
