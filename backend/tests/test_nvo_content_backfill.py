import json

import pytest

from app.models.nvo_content import NvoProblem, NvoSourceExam, NvoTopic
from app.services.nvo_content_backfill import backfill_catalog


@pytest.fixture
def tiny_catalog_with_cleanup(db):
    """Fixture that provides a tiny catalog and cleans up committed data afterward."""
    catalog = _tiny_catalog()
    yield catalog
    # Clean up committed data since the db fixture only rolls back uncommitted changes
    db.query(NvoProblem).filter(
        NvoProblem.slot_number.in_([1, 21])
    ).delete()
    db.query(NvoTopic).filter(
        NvoTopic.code.in_([
            "arithmetic_expression_evaluation_bf_test",
            "open_inequality_plus_equation_plus_check"
        ])
    ).delete()
    db.query(NvoSourceExam).filter(
        NvoSourceExam.year.in_([2023])
    ).delete()
    db.commit()


def _tiny_catalog() -> dict:
    return {
        "slots": {
            "1": {
                "topic": "arithmetic_expression_evaluation_bf_test",
                "notes": "Evaluate a numeric expression.",
                "variants": [
                    {
                        "source": "2023_v1",
                        "question": "Стойността на израза ...",
                        "options": ["А) 1", "Б) 2", "В) 3", "Г) 4"],
                        "correct_answer": "В",
                        "difficulty": "easy",
                    },
                ],
            },
            "21": {
                "topic": "open_inequality_plus_equation_plus_check",
                "notes": "Solve inequality then equation.",
                "variants": [
                    {
                        "source": "2023_v2",
                        "question": "А) Решете ...",
                        "open_parts": ["А", "Б"],
                        "correct_answer": ["А) x>1", "Б) x=2"],
                        "difficulty": "hard",
                    },
                ],
            },
        },
    }


def test_backfill_creates_topics_sources_and_problems(db, tiny_catalog_with_cleanup):
    summary = backfill_catalog(db, tiny_catalog_with_cleanup)

    assert summary == {"created": 2, "updated": 0, "slots": 2}
    assert db.query(NvoTopic).filter_by(code="arithmetic_expression_evaluation_bf_test").count() == 1
    assert db.query(NvoSourceExam).filter_by(year=2023, variant="v1").count() == 1
    assert db.query(NvoProblem).count() == 2


def test_backfill_sets_answer_format_by_slot(db, tiny_catalog_with_cleanup):
    backfill_catalog(db, tiny_catalog_with_cleanup)

    mcq = db.query(NvoProblem).filter_by(slot_number=1).one()
    open_q = db.query(NvoProblem).filter_by(slot_number=21).one()
    assert mcq.answer_format == "mcq"
    assert open_q.answer_format == "open"
    assert json.loads(open_q.correct_answer_json) == ["А) x>1", "Б) x=2"]


def test_backfill_is_idempotent_on_rerun(db, tiny_catalog_with_cleanup):
    catalog = tiny_catalog_with_cleanup
    backfill_catalog(db, catalog)
    summary_second_run = backfill_catalog(db, catalog)

    assert summary_second_run == {"created": 0, "updated": 2, "slots": 2}
    assert db.query(NvoProblem).count() == 2


def test_backfill_updates_changed_fields(db, tiny_catalog_with_cleanup):
    catalog = tiny_catalog_with_cleanup
    backfill_catalog(db, catalog)

    catalog["slots"]["1"]["variants"][0]["correct_answer"] = "Б"
    backfill_catalog(db, catalog)

    problem = db.query(NvoProblem).filter_by(slot_number=1, external_ref="2023_v1").one()
    assert json.loads(problem.correct_answer_json) == "Б"
