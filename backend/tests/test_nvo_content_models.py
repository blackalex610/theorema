import json

import pytest
from sqlalchemy import inspect

from app.models.nvo_content import (
    NvoProblem,
    NvoProblemSkill,
    NvoSkill,
    NvoSourceExam,
    NvoTopic,
)


def test_tables_are_created(db):
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())
    assert {
        "nvo_source_exams",
        "nvo_topics",
        "nvo_skills",
        "nvo_problems",
        "nvo_problem_skills",
    } <= tables


def test_problem_round_trip(db):
    source = NvoSourceExam(title="2024 official exam", year=2024, variant="v1")
    topic = NvoTopic(code="arithmetic_expression_evaluation", name="Arithmetic expressions")
    db.add_all([source, topic])
    db.flush()

    problem = NvoProblem(
        source_exam_id=source.id,
        topic_id=topic.id,
        external_ref="2024_v1",
        slot_number=1,
        answer_format="mcq",
        statement="Стойността на израза ... е:",
        options_json=json.dumps(["А) 1", "Б) 2", "В) 3", "Г) 4"], ensure_ascii=False),
        correct_answer_json=json.dumps("В", ensure_ascii=False),
        difficulty="easy",
    )
    db.add(problem)
    db.commit()

    fetched = db.query(NvoProblem).filter_by(external_ref="2024_v1", slot_number=1).one()
    assert fetched.topic_id == topic.id
    assert fetched.is_active is True
    assert fetched.quality_score == 1.0
    assert fetched.content_version == 1

    db.query(NvoProblem).filter_by(id=fetched.id).delete()
    db.query(NvoTopic).filter_by(id=topic.id).delete()
    db.query(NvoSourceExam).filter_by(id=source.id).delete()
    db.commit()


def test_slot_and_external_ref_must_be_unique_together(db):
    topic = NvoTopic(code="dup_topic", name="Dup")
    db.add(topic)
    db.flush()

    db.add(NvoProblem(
        topic_id=topic.id, external_ref="dup-ref", slot_number=1,
        answer_format="mcq", statement="a", correct_answer_json=json.dumps("А"),
    ))
    db.commit()

    db.add(NvoProblem(
        topic_id=topic.id, external_ref="dup-ref", slot_number=1,
        answer_format="mcq", statement="b", correct_answer_json=json.dumps("Б"),
    ))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()

    db.query(NvoProblem).filter_by(topic_id=topic.id).delete()
    db.query(NvoTopic).filter_by(id=topic.id).delete()
    db.commit()


def test_problem_skill_join_round_trip(db):
    topic = NvoTopic(code="t", name="T")
    db.add(topic)
    db.flush()
    problem = NvoProblem(
        topic_id=topic.id, external_ref="r", slot_number=1,
        answer_format="mcq", statement="s", correct_answer_json=json.dumps("А"),
    )
    skill = NvoSkill(code="skill-1", name="Skill 1")
    db.add_all([problem, skill])
    db.flush()

    db.add(NvoProblemSkill(problem_id=problem.id, skill_id=skill.id, weight=0.7))
    db.commit()

    link = db.query(NvoProblemSkill).one()
    assert link.problem_id == problem.id
    assert link.weight == 0.7

    db.query(NvoProblemSkill).filter_by(problem_id=problem.id).delete()
    db.query(NvoProblem).filter_by(id=problem.id).delete()
    db.query(NvoSkill).filter_by(id=skill.id).delete()
    db.query(NvoTopic).filter_by(id=topic.id).delete()
    db.commit()


def test_generation_run_round_trip(db):
    from app.models.nvo_content import NvoGenerationRun

    run = NvoGenerationRun(
        requested_profile_json=json.dumps({"format": "full", "difficulty": "standard"}),
        source="file_catalog",
        status="completed",
    )
    db.add(run)
    db.commit()

    fetched = db.query(NvoGenerationRun).one()
    assert fetched.source == "file_catalog"
    assert fetched.status == "completed"
    assert fetched.selected_problem_ids_json is None


def test_problem_embedding_round_trip(db):
    from app.models.nvo_content import NvoProblemEmbedding

    topic = NvoTopic(code="emb-topic", name="Emb")
    db.add(topic)
    db.flush()
    problem = NvoProblem(
        topic_id=topic.id, external_ref="e1", slot_number=1,
        answer_format="mcq", statement="s", correct_answer_json=json.dumps("А"),
    )
    db.add(problem)
    db.flush()

    db.add(NvoProblemEmbedding(
        problem_id=problem.id,
        embedding_json=json.dumps([0.1, 0.2, 0.3]),
        embedding_model="text-embedding-3-small",
    ))
    db.commit()

    fetched = db.query(NvoProblemEmbedding).filter_by(problem_id=problem.id).one()
    assert json.loads(fetched.embedding_json) == [0.1, 0.2, 0.3]

    # Clean up committed data since the db fixture only rolls back uncommitted changes
    # Delete embedding first, then problem, then topic (FK order)
    db.query(NvoProblemEmbedding).filter_by(problem_id=problem.id).delete()
    db.query(NvoProblem).filter_by(id=problem.id).delete()
    db.query(NvoTopic).filter_by(id=topic.id).delete()
    db.commit()
