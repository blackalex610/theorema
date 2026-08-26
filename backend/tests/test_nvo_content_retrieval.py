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
    # Delete problems first, then the topic
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
