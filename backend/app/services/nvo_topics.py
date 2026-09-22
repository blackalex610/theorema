"""One canonical topic taxonomy for NVO questions, in Bulgarian.

Why this module exists: the codebase carries **two** unrelated topic
vocabularies, and a third is whatever the LLM path happens to emit.

* ``nvo_question_catalog.json`` labels its 23 slots with compound names that
  describe the official paper's position — ``inequality_smallest_or_largest_integer``,
  ``geometry_rhombus_or_circumcenter_diagram``.
* ``app/nvo_gen/blueprints.py`` labels its slots with generator-side template
  families — ``inequality_integer_bound``, ``geom_median_hypotenuse``.

Those are the *same mathematics* under different names. Aggregating a class's
results on the raw strings would split one real topic across two or three
buckets and hand a teacher numbers that look precise and are wrong. So every
raw topic resolves here to one canonical key with one Bulgarian label a
teacher can act on.

Two deliberate decisions:

* **Compound catalog slots map to their primary topic.** Slot 20 is
  "geometry word problem *or* probability expression"; it resolves to the
  geometry application key. Splitting one stored question across two topics
  would make the percentages stop summing, which is worse than a documented
  approximation.
* **An unrecognised topic becomes ``other``, never a guess.** Heuristic
  prefix-matching on an LLM's invented label would mislabel quietly, and a
  quietly wrong diagnosis is the one failure mode this whole feature exists
  to prevent. ``other`` is excluded from the "work on this next" ranking —
  see ``reportable_keys``.

``tests/test_nvo_topics.py`` pins every topic in both vocabularies to a real
key, so adding a slot without labelling it fails the suite.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Returned for anything the taxonomy does not recognise.
OTHER = "other"
OTHER_LABEL_BG = "Друго"


@dataclass(frozen=True)
class Topic:
    key: str
    label_bg: str
    strand: str


#: The five curriculum strands a teacher thinks in, plus Part 2's extended
#: items, which are pedagogically their own thing: a student who can do the
#: algebra can still lose every mark for not writing up a proof.
STRANDS: dict[str, str] = {
    "arithmetic": "Аритметика",
    "algebra": "Алгебра",
    "geometry": "Геометрия",
    "word_problems": "Текстови задачи",
    "data_probability": "Данни и вероятности",
    "extended": "Разширени задачи (Част 2)",
}


def _t(key: str, label_bg: str, strand: str) -> tuple[str, Topic]:
    return key, Topic(key=key, label_bg=label_bg, strand=strand)


TOPICS: dict[str, Topic] = dict(
    [
        # ── Аритметика ──────────────────────────────────────────────────
        _t("arithmetic_expression", "Числови изрази", "arithmetic"),
        _t("powers", "Степени и съкратено умножение", "arithmetic"),
        # ── Алгебра ─────────────────────────────────────────────────────
        _t("expression_value", "Стойност на алгебричен израз", "algebra"),
        _t("factoring_identities", "Разлагане и тъждества", "algebra"),
        _t("linear_equation", "Линейни уравнения", "algebra"),
        _t("absolute_value", "Уравнения с модул", "algebra"),
        _t("inequality", "Неравенства", "algebra"),
        # ── Геометрия ───────────────────────────────────────────────────
        _t("geom_lines_angles", "Прави и ъгли", "geometry"),
        _t("geom_coordinate", "Координатна система", "geometry"),
        _t("geom_triangle", "Триъгълник", "geometry"),
        _t("geom_quadrilateral", "Четириъгълници", "geometry"),
        _t("geom_solid", "Обем и повърхнина", "geometry"),
        _t("geom_application", "Геометрични приложни задачи", "geometry"),
        # ── Текстови задачи ─────────────────────────────────────────────
        _t("word_problem_general", "Текстови задачи", "word_problems"),
        _t("word_problem_expression", "Съставяне на израз по условие", "word_problems"),
        _t("word_problem_percent", "Проценти и смеси", "word_problems"),
        _t("word_problem_ratio", "Отношения и пропорции", "word_problems"),
        _t("word_problem_motion_work", "Движение и съвместна работа", "word_problems"),
        # ── Данни и вероятности ─────────────────────────────────────────
        _t("probability", "Вероятност", "data_probability"),
        _t("data_reading", "Четене на диаграми и таблици", "data_probability"),
        # ── Разширени задачи (Част 2) ───────────────────────────────────
        _t("open_algebra", "Разширена задача: уравнение и неравенство", "extended"),
        _t("open_word_problem", "Разширена задача: текстова", "extended"),
        _t("open_geometry_proof", "Разширена задача: доказателство", "extended"),
    ]
)


#: raw topic string -> canonical key. Both vocabularies, spelled out rather
#: than pattern-matched, so that every mapping is a decision someone made.
_ALIASES: dict[str, str] = {
    # ── app/nvo_gen/blueprints.py ───────────────────────────────────────
    "arithmetic_expression": "arithmetic_expression",
    "powers": "powers",
    "shortcut_multiplication": "powers",
    "expression_at_value": "expression_value",
    "symbolic_perimeter": "expression_value",
    "expand_or_factor": "factoring_identities",
    "quadratic_by_factoring": "factoring_identities",
    "linear_equation": "linear_equation",
    "absolute_value_equation": "absolute_value",
    "inequality_integer_bound": "inequality",
    "inequality_interval": "inequality",
    "geom_lines_angles": "geom_lines_angles",
    "geom_parallel_lines": "geom_lines_angles",
    "geom_coordinate": "geom_coordinate",
    "geom_right_triangle": "geom_triangle",
    "geom_two_triangles": "geom_triangle",
    "geom_triangle_cevians": "geom_triangle",
    "geom_bisectors_incentre": "geom_triangle",
    "geom_median_hypotenuse": "geom_triangle",
    "geom_side_ordering": "geom_triangle",
    "geom_quadrilateral": "geom_quadrilateral",
    "expression_from_words": "word_problem_expression",
    "word_problem_units": "word_problem_general",
    "word_problem_mixture": "word_problem_percent",
    "percent_word_problem": "word_problem_percent",
    "percent_interest": "word_problem_percent",
    "word_problem_ratio": "word_problem_ratio",
    "work_rate": "word_problem_motion_work",
    "probability": "probability",
    "probability_expression": "probability",
    "data_chart": "data_reading",
    "open_algebra": "open_algebra",
    "open_word_problem": "open_word_problem",
    "open_geometry_proof": "open_geometry_proof",
    # ── backend/nvo_question_catalog.json ───────────────────────────────
    # Compound names resolve to the slot's primary topic; see module docstring.
    "arithmetic_expression_evaluation": "arithmetic_expression",
    "algebraic_expression_at_value": "expression_value",
    "algebraic_identity_or_factoring": "factoring_identities",
    "equation_root_or_abs_value_sum": "linear_equation",
    "inequality_smallest_or_largest_integer": "inequality",
    "abs_value_equation_or_factoring_exclude": "absolute_value",
    # The catalog spells slot 6 two different ways: `slot_topics` omits the
    # `_sum` that the slot's own `topic` field carries. Both are live.
    "abs_value_equation_sum_or_factoring_exclude": "absolute_value",
    "powers_or_shortcut_multiplication": "powers",
    "probability_or_average": "probability",
    "arithmetic_word_problem_no_diagram": "word_problem_general",
    "geometry_lines_angles_or_coordinate_diagram": "geom_lines_angles",
    "geometry_triangle_bisector_or_parallel_diagram": "geom_triangle",
    "geometry_rhombus_or_circumcenter_diagram": "geom_quadrilateral",
    "geometry_isosceles_triangle_or_3d_volume_diagram": "geom_triangle",
    "geometry_triangle_angle_side_diagram": "geom_triangle",
    "geometry_parallelogram_or_side_ordering_diagram": "geom_quadrilateral",
    "word_problem_linear_expression_no_diagram": "word_problem_expression",
    "word_problem_mixture_or_percent_no_diagram": "word_problem_percent",
    "word_problem_ratio_proportion_no_diagram": "word_problem_ratio",
    "data_reading_chart_or_table_no_diagram": "data_reading",
    "geometry_word_problem_or_probability_expression": "geom_application",
    "open_inequality_plus_equation_plus_check": "open_algebra",
    "open_word_problem_motion_work_or_percent": "open_word_problem",
    "open_geometry_proof_and_calculation_diagram": "open_geometry_proof",
    # Volume/surface items reach the taxonomy only through the 3D half of
    # slot 13 today, but the key is real curriculum and templates for it are
    # expected; naming it here keeps that arrival from being a migration.
    "geom_solid": "geom_solid",
    "geometry_volume_or_surface": "geom_solid",
}


def _normalise(raw: str | None) -> str:
    if not raw:
        return ""
    return " ".join(str(raw).strip().lower().split()).replace(" ", "_").replace("-", "_")


def resolve(raw: str | None) -> str:
    """Canonical topic key for a raw topic string, or ``OTHER``.

    Never guesses: an unrecognised label is reported as unknown rather than
    approximated into a neighbouring topic.
    """
    normalised = _normalise(raw)
    if not normalised:
        return OTHER
    if normalised in _ALIASES:
        return _ALIASES[normalised]
    if normalised in TOPICS:
        return normalised
    return OTHER


def label(key: str) -> str:
    """Bulgarian label for a canonical key. Teacher-facing."""
    topic = TOPICS.get(key)
    return topic.label_bg if topic else OTHER_LABEL_BG


def strand_of(key: str) -> str | None:
    topic = TOPICS.get(key)
    return topic.strand if topic else None


def strand_label(strand: str) -> str:
    return STRANDS.get(strand, OTHER_LABEL_BG)


def reportable_keys() -> list[str]:
    """Keys that may be shown to a teacher as "work on this next".

    Excludes ``other`` by construction: a bucket of questions the taxonomy
    could not identify is a data-quality signal for us, not a teaching
    instruction for them.
    """
    return sorted(TOPICS)
