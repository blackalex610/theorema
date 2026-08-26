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


def test_tables_are_created(nvo_db):
    inspector = inspect(nvo_db.get_bind())
    tables = set(inspector.get_table_names())
    assert {
        "nvo_source_exams",
        "nvo_topics",
        "nvo_skills",
        "nvo_problems",
        "nvo_problem_skills",
    } <= tables


def test_problem_round_trip(nvo_db):
    source = NvoSourceExam(title="2024 official exam", year=2024, variant="v1")
    topic = NvoTopic(code="arithmetic_expression_evaluation", name="Arithmetic expressions")
    nvo_db.add_all([source, topic])
    nvo_db.flush()

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
    nvo_db.add(problem)
    nvo_db.commit()

    fetched = nvo_db.query(NvoProblem).filter_by(external_ref="2024_v1", slot_number=1).one()
    assert fetched.topic_id == topic.id
    assert fetched.is_active is True
    assert fetched.quality_score == 1.0
    assert fetched.content_version == 1


def test_slot_and_external_ref_must_be_unique_together(nvo_db):
    topic = NvoTopic(code="dup_topic", name="Dup")
    nvo_db.add(topic)
    nvo_db.flush()

    nvo_db.add(NvoProblem(
        topic_id=topic.id, external_ref="2024_v1", slot_number=1,
        answer_format="mcq", statement="a", correct_answer_json=json.dumps("А"),
    ))
    nvo_db.commit()

    nvo_db.add(NvoProblem(
        topic_id=topic.id, external_ref="2024_v1", slot_number=1,
        answer_format="mcq", statement="b", correct_answer_json=json.dumps("Б"),
    ))
    with pytest.raises(Exception):
        nvo_db.commit()
    nvo_db.rollback()


def test_problem_skill_join_round_trip(nvo_db):
    topic = NvoTopic(code="t", name="T")
    nvo_db.add(topic)
    nvo_db.flush()
    problem = NvoProblem(
        topic_id=topic.id, external_ref="r", slot_number=1,
        answer_format="mcq", statement="s", correct_answer_json=json.dumps("А"),
    )
    skill = NvoSkill(code="skill-1", name="Skill 1")
    nvo_db.add_all([problem, skill])
    nvo_db.flush()

    nvo_db.add(NvoProblemSkill(problem_id=problem.id, skill_id=skill.id, weight=0.7))
    nvo_db.commit()

    link = nvo_db.query(NvoProblemSkill).one()
    assert link.problem_id == problem.id
    assert link.weight == 0.7
