"""Written answers earn part marks, the way an НВО examiner awards them.

Before: the model was asked "is this correct?" and a 12-point proof with the
right method and one slip earned 0; a photographed solution was all or none.
Now the model marks each sub-part from 0 to its maximum by the scheme, and the
official keys' own part marks for short answers are applied in code.
"""
from __future__ import annotations

import asyncio
import random

import pytest

import app.routers.nvo as nvo_module
from app.nvo_gen.api import exam_payload
from app.nvo_gen.assemble import generate_paper
from app.nvo_gen.blueprints import BLUEPRINTS
from app.routers.nvo import NVOExam, NVOExamSubmitRequest, _store_exam, submit_nvo_exam
from app.services.nvo_grading import (
    build_examiner_request,
    grade_written,
    parse_marks,
    short_partial_credit,
)


class Examiner:
    """A stand-in for the model: records what it was asked, awards set marks."""

    def __init__(self, award=lambda part: part["max_points"] // 2):
        self.calls = []
        self.award = award

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        parts = kwargs["parts"]
        return ([self.award(p) for p in parts], ["частично вярно"] * len(parts), "извлечено")


def _refuse(**_kw):
    raise RuntimeError("no model")


# ─── the official keys' part marks for short answers ────────────────────────

@pytest.mark.parametrize("given,expected", [
    ("0 и 25", 4), ("25", 2), ("0", 2), ("0 и 5", 2), ("0, 5, 7", 0), ("3", 0),
])
def test_one_correct_root_earns_half(given, expected):
    """2026 Q15 key: „0 и 25 — 4 т.; 2 т., при един верен отговор”."""
    g = grade_written(statement="…", parts=None, correct="0 и 25", points=[4], marking=None,
                      raw_answer=given, image_data_url=None, ai_mark=_refuse, kind="short")
    assert g.score == expected, g.feedback


@pytest.mark.parametrize("given,expected", [("5x", 4), ("4x", 2), ("4x и 5x", 3), ("6x", 0)])
def test_the_2026_q21_part_marks(given, expected):
    """„5x — 4 т.; 2 т., ако е написано 4x; 3 т., ако е написано 4x и 5x”."""
    g = grade_written(statement="…", parts=None, correct="5x", points=[4], marking=None,
                      raw_answer=given, image_data_url=None, ai_mark=_refuse, kind="short",
                      partial_credit={"4x": 2, "4x и 5x": 3})
    assert g.score == expected, g.feedback


def test_the_generated_items_carry_those_rules():
    slot = next(s for s in BLUEPRINTS["nvo2026"].slots if s.topic == "symbolic_perimeter")
    from app.nvo_gen import registry
    tpl = registry.get_template("isosceles_symbolic_perimeter")
    for seed in range(40):
        item = tpl.build(random.Random(seed), slot)
        if item.partial_credit:
            wrong = next(k for k, v in item.partial_credit.items() if v == 2)
            assert short_partial_credit(wrong, item.correct_answer, 4, item.partial_credit) == 2
            both = next(k for k, v in item.partial_credit.items() if v == 3)
            assert short_partial_credit(both, item.correct_answer, 4, item.partial_credit) == 3
            return
    pytest.fail("no 1 : k draw carried the key's part marks")


def test_the_simplified_form_earns_half_on_2026_q16():
    """„2026 — 4 т.; 2 т., при написано x + 1”."""
    g = grade_written(statement="…", parts=None, correct="2026", points=[4], marking=None,
                      raw_answer="x + 1", image_data_url=None, ai_mark=_refuse, kind="short",
                      partial_credit={"x + 1": 2})
    assert g.score == 2


# ─── the model as an examiner ───────────────────────────────────────────────

def test_the_examiner_marks_each_part_between_zero_and_full():
    examiner = Examiner(award=lambda p: {"А": 3, "Б": 0, "В": 4}[p["label"]])
    g = grade_written(
        statement="Даден е изразът M…", parts=["А", "Б", "В"],
        correct=["M = 4x^2 + 26x", "x ≤ 5/6", "x = 2,5 не е решение; x = -1,5 е решение"],
        points=[5, 2, 5], marking="А) … — 3 т.; … — 2 т.",
        raw_answer={"А": "M = 4x^2 + 20x", "Б": "x < 1", "В": "-1,5 е решение, защото…"},
        image_data_url=None, ai_mark=examiner, kind="open")
    assert (g.score, g.max_score) == (7, 12)
    assert "3 от 5 т." in g.feedback and "4 от 5 т." in g.feedback


def test_one_request_per_question_carrying_the_scheme_and_each_maximum():
    examiner = Examiner()
    grade_written(statement="Задача", parts=["А", "Б"], correct=["15", "y > -8/5"],
                  points=[5, 4], marking="Схема: А) … — 2 т.",
                  raw_answer={"А": "15", "Б": "y > 2"}, image_data_url=None,
                  ai_mark=examiner, kind="open")
    assert len(examiner.calls) == 1
    call = examiner.calls[0]
    assert call["marking"] == "Схема: А) … — 2 т."
    # А matched the key exactly and was settled without the model
    assert [(p["label"], p["max_points"]) for p in call["parts"]] == [("Б", 4)]


def test_a_part_two_answer_with_the_wrong_number_still_reaches_the_examiner():
    """A wrong final number is not 0 on a Part 2 item: the steps earn marks."""
    examiner = Examiner()
    g = grade_written(statement="…", parts=["А"], correct=["x = 15"], points=[5], marking="…",
                      raw_answer={"А": "15x - 5 = 10x + 25, x = 6"}, image_data_url=None,
                      ai_mark=examiner, kind="open")
    assert examiner.calls and g.score == 2


def test_a_short_answer_with_the_wrong_number_does_not():
    """Part 1 short answers are marked on the answer alone, as the key does."""
    examiner = Examiner()
    g = grade_written(statement="…", parts=None, correct="90 места", points=[4], marking=None,
                      raw_answer="80", image_data_url=None, ai_mark=examiner, kind="short")
    assert not examiner.calls and g.score == 0


def test_a_photographed_solution_is_marked_part_by_part():
    examiner = Examiner(award=lambda p: p["max_points"] - 1)
    g = grade_written(statement="…", parts=["А", "Б", "В"], correct=["a", "b", "c"],
                      points=[3, 4, 5], marking="…", raw_answer={}, image_data_url="data:image/png;base64,x",
                      ai_mark=examiner, kind="open")
    assert (g.score, g.max_score) == (9, 12)          # not 0, not 12
    assert examiner.calls[0]["image_data_url"].startswith("data:image/")


def test_an_examiner_outage_marks_nothing_but_does_not_fail():
    g = grade_written(statement="…", parts=["А"], correct=["proof"], points=[4], marking="…",
                      raw_answer={"А": "доказателство"}, image_data_url=None,
                      ai_mark=_refuse, kind="open")
    assert g.score == 0 and "Не може да бъде проверено" in g.feedback


# ─── reading the examiner's reply ───────────────────────────────────────────

PARTS = [{"label": "А", "key": "k", "max_points": 3, "answer": "a"},
         {"label": "Б", "key": "k", "max_points": 5, "answer": "b"}]


def test_parse_marks_clamps_and_maps_latin_labels():
    raw = '```json\n{"parts": [{"part": "A", "points": 9, "feedback": "x"},' \
          ' {"part": "Б)", "points": -2}], "extracted_answer": "e"}\n```'
    points, feedback, extracted = parse_marks(raw, PARTS)
    assert points == [3, 0] and extracted == "e"


def test_parse_marks_scores_a_missing_part_zero():
    points, feedback, _ = parse_marks('{"parts": [{"part": "Б", "points": 4}]}', PARTS)
    assert points == [0, 4] and "Няма оценка" in feedback[0]


def test_parse_marks_rejects_prose():
    with pytest.raises(ValueError):
        parse_marks("Решението е вярно.", PARTS)


def test_the_prompt_asks_for_part_marks_by_the_scheme():
    system, user = build_examiner_request(statement="Задача", marking="А) … — 2 т.",
                                          kind="open", parts=PARTS)
    assert "НЕ само 0 или максимума" in system and "междинен резултат" in system
    assert "максимум 3 т." in user and "максимум 5 т." in user and "А) … — 2 т." in user
    short_system, _ = build_examiner_request(statement="З", marking=None, kind="short", parts=PARTS)
    assert "кратък свободен отговор" in short_system


# ─── end to end ─────────────────────────────────────────────────────────────

def test_a_submitted_paper_earns_part_marks_on_part_two(db, make_user, monkeypatch):
    monkeypatch.setattr(nvo_module, "_ai_mark", Examiner())       # half of every part asked
    paper = generate_paper("nvo2026", seed=5)
    exam = NVOExam(**{**exam_payload(paper), "exam_id": "partial001"})
    _store_exam(exam)
    answers = {str(q.number): ({p: "моето решение" for p in q.open_parts} if q.open_parts
                               else "моето решение")
               for q in exam.questions if q.kind == "open"}
    payload = NVOExamSubmitRequest(exam_id="partial001", answers=answers, open_answer_images=[])
    result = asyncio.run(submit_nvo_exam(payload, current_user=make_user(), db=db))
    assert 0 < result.part2_score < result.part2_max_score == 35
    part2 = [r for r in result.open_results if r.max_score >= 11]
    assert all(0 < r.score < r.max_score for r in part2), [(r.score, r.max_score) for r in part2]
