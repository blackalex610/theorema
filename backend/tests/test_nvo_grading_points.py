"""A generated paper is scored in NVO points, the way the official key scores it.

Before: every question counted one point, a multi-part item was all-or-nothing,
and every short answer — „2026”, „0 и 25” — went to the language model, which
without an API key raised 503 and made the paper impossible to submit.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

import app.routers.nvo as nvo_module
from app.nvo_gen.api import exam_payload
from app.nvo_gen.assemble import generate_paper
from app.routers.nvo import NVOExam, NVOExamSubmitRequest, _store_exam, _strip_answer_key, submit_nvo_exam
from app.services.nvo_grading import grade_written, match_answer


def _no_ai(monkeypatch):
    """The deployment has no OpenAI key: the grader raises, as the real one does."""
    def refuse(**_kwargs):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    monkeypatch.setattr(nvo_module, "_ai_mark", refuse)


def _exam(exam_id: str, seed: int = 7) -> NVOExam:
    paper = generate_paper("nvo2026", seed=seed)
    exam = NVOExam(**{**exam_payload(paper), "exam_id": exam_id})
    _store_exam(exam)
    return exam


def _submit(exam_id, answers, user, db):
    payload = NVOExamSubmitRequest(exam_id=exam_id, answers=answers, open_answer_images=[])
    return asyncio.run(submit_nvo_exam(payload, current_user=user, db=db))


def _key_answers(exam: NVOExam, *, skip_part2: bool = True) -> dict:
    """What a student who knows every Part 1 answer would type."""
    answers: dict = {}
    for q in exam.questions:
        if q.kind == "open" and skip_part2:
            continue
        if q.options is not None:
            answers[str(q.number)] = q.correct_answer
        elif q.open_parts:
            answers[str(q.number)] = dict(zip(q.open_parts, q.correct_answer))
        else:
            answers[str(q.number)] = q.correct_answer
    return answers


def test_a_perfect_part_one_is_65_of_100_without_any_ai(db, make_user, monkeypatch):
    _no_ai(monkeypatch)
    exam = _exam("pts001")
    result = _submit("pts001", _key_answers(exam), make_user(), db)

    assert result.total_max_score == 100
    assert (result.part1_score, result.part1_max_score) == (65, 65)
    assert result.part2_max_score == 35 and result.part2_score == 0
    assert result.mcq_max_score == 35            # the 14 multiple-choice items of 2026
    assert result.total_score == 65
    assert result.percentage_correct == 65


@pytest.mark.parametrize("seed", range(12))
def test_every_short_answer_key_is_accepted_by_the_deterministic_checker(seed):
    """If the machine can't recognise its own key, a correct student is at the
    mercy of the model — or, with no key configured, marked wrong."""
    paper = generate_paper("nvo2026", seed=seed)
    for n, item, slot in paper.numbered():
        if item.kind != "short":
            continue
        keys = item.correct_answer if isinstance(item.correct_answer, list) else [item.correct_answer]
        for key in keys:
            assert match_answer(key, key) is True, (n, item.template_code, key)


def test_partial_credit_follows_the_sub_part_points(monkeypatch):
    _no_ai(monkeypatch)
    g = grade_written(
        statement="…", parts=["А", "Б"], correct=["май", "15 апартамента"], points=[2, 3],
        marking=None, raw_answer={"А": "V", "Б": "14"}, image_data_url=None,
        ai_mark=nvo_module._ai_mark, kind="short",
    )
    assert (g.score, g.max_score) == (2, 5)
    assert "15" in g.feedback


def test_part_two_is_thirty_five_percent_of_the_score(db, make_user, monkeypatch):
    """Three items worth 12 + 11 + 12, not 3 of 24 equal questions."""
    monkeypatch.setattr(nvo_module, "_ai_mark",
                        lambda **kw: ([p["max_points"] for p in kw["parts"]],
                                      ["ok"] * len(kw["parts"]), "x"))
    exam = _exam("pts002", seed=3)
    only_part2 = {str(q.number): ({p: "решение" for p in q.open_parts} if q.open_parts else "решение")
                  for q in exam.questions if q.kind == "open"}
    result = _submit("pts002", only_part2, make_user(), db)
    # every sub-part the machine can't check is accepted by the (stubbed) model;
    # sub-parts with numeric keys are checked exactly and "решение" fails them
    assert result.part2_max_score == 35
    assert result.part1_score == 0
    assert result.total_score == result.part2_score <= 35


def test_a_missing_ai_key_no_longer_blocks_submission(db, make_user, monkeypatch):
    _no_ai(monkeypatch)
    exam = _exam("pts003", seed=11)
    answers = _key_answers(exam, skip_part2=False)
    result = _submit("pts003", answers, make_user(), db)   # must not raise 503
    assert result.part1_score == 65


def test_the_marking_scheme_never_reaches_the_client():
    exam = NVOExam(**{**exam_payload(generate_paper("nvo2026", seed=1)), "exam_id": "pts004"})
    assert any(q.marking for q in exam.questions if q.kind == "open")
    stripped = _strip_answer_key(exam)
    assert all(q.marking is None and q.correct_answer is None for q in stripped.questions)


@pytest.mark.parametrize("key,student,expected", [
    ("0 и 25", "x₁ = 25, x₂ = 0", True),
    ("0 и 25", "0 и 5", False),
    ("5x", "5х", True),                     # Cyrillic х typed for x
    ("5x", "4x", False),
    ("май", "V", True),                     # the 2026 key: „или V, или 05”
    ("x ≤ 5/6", "(-∞; 5/6]", True),
    ("y > -8/5", "y > -1,6", True),
    ("16 h 45 min", "16:45", True),
    ("16 h", "16 ч.", True),
    ("35,91 L", "35.91", True),
    ("първата 7 дни, втората 6 дни", "6 и 7", None),   # order carries meaning
    ("M = (x - 2)(x - 2)(x - 2)(x + 2)", "(x-2)^3(x+2)", None),  # the model judges forms
    ("x = 3,2 е решение; x = -2,8 не е решение", "3,2", None),
])
def test_match_answer(key, student, expected):
    assert match_answer(student, key) is expected
