import json

import pytest

from app.models.nvo_content import NvoProblem, NvoTopic
from app.services.nvo_content_qa import qa_report


@pytest.fixture
def topic(db):
    # Clean up any leftover problems from previous tests since qa_report queries all active problems
    db.query(NvoProblem).delete(synchronize_session=False)
    db.commit()

    t = NvoTopic(code="qa_report_test_topic", name="T")
    db.add(t)
    db.flush()
    yield t
    db.query(NvoProblem).filter(NvoProblem.topic_id == t.id).delete(synchronize_session=False)
    db.query(NvoTopic).filter(NvoTopic.id == t.id).delete(synchronize_session=False)
    db.commit()


def _problem(db, topic, slot_number, answer_format="mcq", options=("А", "Б", "В", "Г"), correct="А"):
    p = NvoProblem(
        topic_id=topic.id,
        external_ref=f"ref-{slot_number}-{len(options) if options else 0}",
        slot_number=slot_number,
        answer_format=answer_format,
        statement="q",
        options_json=json.dumps(list(options), ensure_ascii=False) if options else None,
        correct_answer_json=json.dumps(correct, ensure_ascii=False),
        difficulty="easy",
    )
    db.add(p)
    db.commit()
    return p


def test_reports_missing_slots(db, topic):
    _problem(db, topic, slot_number=1)
    report = qa_report(db)
    assert 2 in report["missing_slots"]
    assert report["is_generation_ready"] is False


def test_flags_mcq_without_four_options(db, topic):
    _problem(db, topic, slot_number=1, options=("А", "Б"))
    report = qa_report(db)
    issue_types = {i for entry in report["integrity_issues"] for i in entry["issues"]}
    assert "mcq_without_4_options" in issue_types


def test_flags_answer_format_mismatch(db, topic):
    _problem(db, topic, slot_number=21, answer_format="mcq")  # slot 21 must be open
    report = qa_report(db)
    issue_types = {i for entry in report["integrity_issues"] for i in entry["issues"]}
    assert any(i.startswith("answer_format_mismatch") for i in issue_types)


def test_generation_ready_when_all_23_slots_present_and_clean(db, topic):
    for slot in range(1, 21):
        _problem(db, topic, slot_number=slot)
    for slot in (21, 22, 23):
        _problem(db, topic, slot_number=slot, answer_format="open", options=None, correct=["А) x"])

    report = qa_report(db)
    assert report["missing_slots"] == []
    assert report["integrity_issues"] == []
    assert report["is_generation_ready"] is True
