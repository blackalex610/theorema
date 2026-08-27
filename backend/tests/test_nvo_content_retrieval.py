import json

import pytest

from app.models.nvo_content import NvoProblem, NvoTopic
from app.services.nvo_content_retrieval import (
    build_slot_pool,
    get_slot_candidates,
    problem_to_variant,
    select_variant_for_slot,
    slot_pool_to_catalog,
)


@pytest.fixture
def seeded_topic(db):
    topic = NvoTopic(
        code="arithmetic_expr_eval_1",
        name="Arithmetic",
        notes="Evaluate a numeric expression.",
    )
    db.add(topic)
    db.flush()
    yield topic
    # Clean up committed data since the db fixture only rolls back uncommitted changes
    # Delete embeddings first, then problems, then the topic
    from app.models.nvo_content import NvoProblemEmbedding

    problem_ids = db.query(NvoProblem.id).filter(NvoProblem.topic_id == topic.id).all()
    problem_ids = [pid[0] for pid in problem_ids]
    if problem_ids:
        db.query(NvoProblemEmbedding).filter(NvoProblemEmbedding.problem_id.in_(problem_ids)).delete()
    db.query(NvoProblem).filter(NvoProblem.topic_id == topic.id).delete()
    db.query(NvoTopic).filter(NvoTopic.id == topic.id).delete()
    db.commit()


def _make_problem(db, topic, slot_number=1, external_ref="2024_v1", is_active=True, quality_score=1.0):
    problem = NvoProblem(
        topic_id=topic.id,
        external_ref=external_ref,
        slot_number=slot_number,
        answer_format="mcq",
        statement="Стойността на израза е:",
        options_json=json.dumps(["А) 1", "Б) 2", "В) 3", "Г) 4"], ensure_ascii=False),
        correct_answer_json=json.dumps("В", ensure_ascii=False),
        difficulty="easy",
        is_active=is_active,
        quality_score=quality_score,
    )
    db.add(problem)
    db.commit()
    return problem


def test_get_slot_candidates_filters_inactive(db, seeded_topic):
    _make_problem(db, seeded_topic, slot_number=20, external_ref="t1_a", is_active=True)
    _make_problem(db, seeded_topic, slot_number=20, external_ref="t1_b", is_active=False)

    candidates = get_slot_candidates(db, slot_number=20)
    assert [c.external_ref for c in candidates] == ["t1_a"]


def test_get_slot_candidates_orders_by_quality(db, seeded_topic):
    _make_problem(db, seeded_topic, slot_number=21, external_ref="t2_low", quality_score=0.2)
    _make_problem(db, seeded_topic, slot_number=21, external_ref="t2_high", quality_score=0.9)

    candidates = get_slot_candidates(db, slot_number=21)
    assert [c.external_ref for c in candidates] == ["t2_high", "t2_low"]


def test_build_slot_pool_returns_none_when_any_slot_empty(db, seeded_topic):
    _make_problem(db, seeded_topic, slot_number=22, external_ref="t3_problem")
    assert build_slot_pool(db, [22, 23]) is None


def test_build_slot_pool_returns_candidates_for_every_slot(db, seeded_topic):
    _make_problem(db, seeded_topic, slot_number=24, external_ref="t4_a")
    _make_problem(db, seeded_topic, slot_number=24, external_ref="t4_b")

    pool = build_slot_pool(db, [24])
    assert set(pool.keys()) == {24}
    assert len(pool[24]) == 2


def test_problem_to_variant_matches_catalog_shape(db, seeded_topic):
    problem = _make_problem(db, seeded_topic, slot_number=25, external_ref="t5_problem")
    variant = problem_to_variant(problem)

    assert variant["source"] == problem.external_ref
    assert variant["correct_answer"] == "В"
    assert variant["options"] == ["А) 1", "Б) 2", "В) 3", "Г) 4"]


def test_slot_pool_to_catalog_shape(db, seeded_topic):
    _make_problem(db, seeded_topic, slot_number=26, external_ref="t6_problem")
    pool = build_slot_pool(db, [26])

    catalog = slot_pool_to_catalog(db, pool)
    assert catalog["slots"]["26"]["topic"] == "arithmetic_expr_eval_1"
    assert catalog["slots"]["26"]["notes"] == "Evaluate a numeric expression."
    assert len(catalog["slots"]["26"]["variants"]) == 1


def test_select_variant_for_slot_picks_from_candidates(db, seeded_topic):
    a = _make_problem(db, seeded_topic, slot_number=27, external_ref="t7_a")
    b = _make_problem(db, seeded_topic, slot_number=27, external_ref="t7_b")
    chosen = select_variant_for_slot([a, b])
    assert chosen in (a, b)


def test_cosine_similarity_identical_vectors_is_one():
    from app.services.nvo_content_retrieval import cosine_similarity

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    from app.services.nvo_content_retrieval import cosine_similarity

    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_handles_zero_vector():
    from app.services.nvo_content_retrieval import cosine_similarity

    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_rank_by_similarity_orders_best_match_first(db, seeded_topic):
    from app.models.nvo_content import NvoProblemEmbedding
    from app.services.nvo_content_retrieval import rank_by_similarity

    close = _make_problem(db, seeded_topic, slot_number=28, external_ref="close")
    far = _make_problem(db, seeded_topic, slot_number=28, external_ref="far")
    db.add_all([
        NvoProblemEmbedding(problem_id=close.id, embedding_json=json.dumps([1.0, 0.0]), embedding_model="m"),
        NvoProblemEmbedding(problem_id=far.id, embedding_json=json.dumps([0.0, 1.0]), embedding_model="m"),
    ])
    db.commit()

    ranked = rank_by_similarity(db, [far, close], query_embedding=[1.0, 0.0])
    assert [p.external_ref for p, _score in ranked] == ["close", "far"]


def test_rank_by_similarity_unembedded_candidate_sorts_last(db, seeded_topic):
    from app.models.nvo_content import NvoProblemEmbedding
    from app.services.nvo_content_retrieval import rank_by_similarity

    embedded = _make_problem(db, seeded_topic, slot_number=29, external_ref="embedded")
    unembedded = _make_problem(db, seeded_topic, slot_number=29, external_ref="unembedded")
    db.add(NvoProblemEmbedding(problem_id=embedded.id, embedding_json=json.dumps([1.0, 0.0]), embedding_model="m"))
    db.commit()

    ranked = rank_by_similarity(db, [unembedded, embedded], query_embedding=[1.0, 0.0])
    assert ranked[0][0].external_ref == "embedded"
    assert ranked[-1][1] == 0.0


def test_diversity_filter_drops_near_duplicate_statements(db, seeded_topic):
    from app.services.nvo_content_retrieval import apply_diversity_filter

    original = _make_problem(db, seeded_topic, slot_number=30, external_ref="a")
    original.statement = "Стойността на израза 2+2 е:"
    near_dup = _make_problem(db, seeded_topic, slot_number=30, external_ref="b")
    near_dup.statement = "Стойността на израза  2 + 2  е:"
    distinct = _make_problem(db, seeded_topic, slot_number=30, external_ref="c")
    distinct.statement = "Реши уравнението x^2 - 4 = 0"
    db.commit()

    ranked = [(original, 0.9), (near_dup, 0.8), (distinct, 0.5)]
    selected = apply_diversity_filter(ranked, k=2)

    assert original in selected
    assert near_dup not in selected
    assert distinct in selected
    assert len(selected) == 2


def test_diversity_filter_stops_at_k(db, seeded_topic):
    from app.services.nvo_content_retrieval import apply_diversity_filter

    problems = [_make_problem(db, seeded_topic, slot_number=31, external_ref=f"p{i}") for i in range(5)]
    # Create statements that are clearly distinct (not just differing by a digit)
    statements = [
        "Какво е резултатът на 2+2?",
        "Реши уравнението x^2 - 4 = 0",
        "Намери средното на числата 1, 2, 3",
        "Какво е площта на триъгълник с основа 5 и височина 3?",
        "Разложи на множители: x^2 - 9",
    ]
    for i, p in enumerate(problems):
        p.statement = statements[i]
    db.commit()

    ranked = [(p, 1.0 - i * 0.1) for i, p in enumerate(problems)]
    selected = apply_diversity_filter(ranked, k=3)
    assert len(selected) == 3
