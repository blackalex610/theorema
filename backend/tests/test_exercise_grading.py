"""Smoke tests for the offline answer evaluator.

`_local_equivalence_check` is the only grader that runs without an OpenAI key,
so it decides most students' marks. It must accept genuinely equivalent
answers, reject wrong ones, and never evaluate attacker-supplied code.
"""
import pytest

from app.routers.exercises import (
    _local_equivalence_check,
    _safe_eval_math,
    normalize_answer,
)


# ─── Normalisation ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("  42  ", "42"),
    ("X = 5", "x=5"),
    ("2 + 3", "2+3"),
])
def test_normalize_answer(raw, expected):
    assert normalize_answer(raw) == expected


# ─── Accepting correct answers ───────────────────────────────────────────────

@pytest.mark.parametrize("submitted,correct", [
    ("42", "42"),
    ("  42 ", "42"),
    ("X = 5", "x=5"),
    ("2+3", "5"),                       # numeric equivalence
    ("10/4", "2.5"),
    ("2^3", "8"),
    (r"\frac{1}{2}", "0.5"),            # LaTeX fraction
    (r"3 \cdot 4", "12"),
    ("x1=3,x2=2", "x1=2,x2=3"),         # unordered root list
])
def test_equivalent_answers_are_accepted(submitted, correct):
    assert _local_equivalence_check(submitted, correct) is True


# ─── Rejecting wrong answers ─────────────────────────────────────────────────

@pytest.mark.parametrize("submitted,correct", [
    ("41", "42"),
    ("2+3", "6"),
    ("x1=2,x2=4", "x1=2,x2=3"),
    ("", "42"),
    ("не знам", "42"),
])
def test_wrong_answers_are_rejected(submitted, correct):
    assert _local_equivalence_check(submitted, correct) is False


def test_unparseable_input_does_not_raise():
    """A junk answer must grade as wrong, not blow up the request."""
    assert _local_equivalence_check("((((", "42") is False


# ─── The evaluator must not be an eval() ─────────────────────────────────────

@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo pwned')",
    "open('/etc/passwd').read()",
    "[].__class__.__mro__",
    "1 if True else 2",
])
def test_safe_eval_rejects_non_arithmetic(expr):
    with pytest.raises((ValueError, SyntaxError, TypeError)):
        _safe_eval_math(expr)


def test_safe_eval_handles_plain_arithmetic():
    assert _safe_eval_math("2+3*4") == pytest.approx(14.0)
    assert _safe_eval_math("-(2**3)") == pytest.approx(-8.0)


def test_malicious_answer_string_is_graded_not_executed():
    """A student-supplied payload reaches the grader; it must just be wrong."""
    assert _local_equivalence_check("__import__('os').system('id')", "42") is False
