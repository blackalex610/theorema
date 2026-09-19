"""The two exam shapes, as data.

Both were read off the official papers in ``NVOS/``. What is load-bearing and
identical in every paper since 2015:

  * Part 1 is worth exactly 65 points and Part 2 exactly 35, whatever the
    task count — so ``assert sum(points) == 65`` is a real invariant, not a
    coincidence of one year.
  * Four options, always Cyrillic А/Б/В/Г, exactly one correct.
  * Part 1 runs an algebra/number/data block and *then* a geometry block. The
    papers print „Чертежите са само за илюстрация…” inline at the boundary.
  * Part 2 is always the same three genres in the same order: multi-part
    algebra, a word problem, a geometry proof.

What moved, and why there are two blueprints rather than one:

  CLASSIC (2024 + 2025)   Part 1 · 75 min · 20 multiple choice, no short answer
  NVO2026 (2026)          Part 1 · 90 min · 14 multiple choice + 7 short answer

2026 also renumbers Part 2 to 22–24. Nothing here may be hard-coded in the
generator; a third era will arrive and should cost one dict entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from app.nvo_gen.difficulty import ACTUAL, DifficultyProfile, get_profile

SectionKind = Literal["part1", "part2"]
ItemKind = Literal["mc", "short", "open"]

#: Printed between the last algebra item and the first geometry item in every
#: paper from 2019 on. The student is told the figure is not to scale, which is
#: exactly what lets us lay figures out canonically instead of solving for them.
SCALE_NOTICE_BG = (
    "Чертежите са само за илюстрация. Те не са начертани в мащаб "
    "и не са предназначени за директно измерване на дължини и на ъгли."
)


@dataclass(frozen=True)
class Slot:
    """One numbered position in a paper."""

    position: int
    section: SectionKind
    kind: ItemKind
    topic: str
    #: Points per sub-part. A single-part item is a 1-tuple. The real keys
    #: award partial credit per sub-part ("2 т., при един верен отговор"), so
    #: this is a tuple from day one rather than a retrofit.
    points: tuple[int, ...]
    #: True when the official papers ship a figure at this position.
    diagram: bool = False
    #: The difficulty this position is being generated at. Stamped on by the
    #: assembler, never by a blueprint literal — a blueprint describes the
    #: *format*, which is the same at every level. Templates read it to size
    #: their own parameter pools (``slot.profile.tier(...)``); a template that
    #: ignores it simply generates the real paper's numbers at every level.
    profile: DifficultyProfile = ACTUAL

    @property
    def total_points(self) -> int:
        return sum(self.points)

    @property
    def parts(self) -> int:
        return len(self.points)


@dataclass(frozen=True)
class Blueprint:
    code: str
    label_bg: str
    subtitle_bg: str
    years_bg: str
    part1_minutes: int
    part2_minutes: int
    slots: tuple[Slot, ...] = field(repr=False)

    # ── derived views ────────────────────────────────────────────────────
    @property
    def part1(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.section == "part1")

    @property
    def part2(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.section == "part2")

    @property
    def mc_slots(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind == "mc")

    @property
    def short_slots(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind == "short")

    @property
    def open_slots(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind == "open")

    @property
    def part1_points(self) -> int:
        return sum(s.total_points for s in self.part1)

    @property
    def part2_points(self) -> int:
        return sum(s.total_points for s in self.part2)

    @property
    def total_points(self) -> int:
        return self.part1_points + self.part2_points

    @property
    def geometry_starts_at(self) -> int:
        """Position of the first geometry item — where the scale notice prints."""
        for slot in self.part1:
            if slot.topic.startswith("geom_"):
                return slot.position
        return len(self.part1) + 1

    def slot(self, position: int) -> Slot:
        for s in self.slots:
            if s.position == position:
                return s
        raise KeyError(f"{self.code} has no slot at position {position}")

    def validate(self) -> None:
        """Fail loudly at import time rather than mid-generation."""
        positions = [s.position for s in self.slots]
        expected = list(range(1, len(self.slots) + 1))
        if positions != expected:
            raise ValueError(f"{self.code}: positions must be 1..n contiguous, got {positions}")
        if self.part1_points != 65:
            raise ValueError(f"{self.code}: Part 1 must total 65 points, got {self.part1_points}")
        if self.part2_points != 35:
            raise ValueError(f"{self.code}: Part 2 must total 35 points, got {self.part2_points}")
        # The geometry items inside the multiple-choice block form ONE
        # contiguous run — that run is what the scale notice introduces. Word
        # problems and data items legitimately resume after it (2024 runs
        # geometry at 10–15 and is back to word problems at 16), so this is a
        # contiguity check, not a "geometry comes last" check.
        geom_mc = [s.position for s in self.mc_slots if s.topic.startswith("geom_")]
        if geom_mc and geom_mc != list(range(geom_mc[0], geom_mc[0] + len(geom_mc))):
            raise ValueError(
                f"{self.code}: geometry MC items must be contiguous, got {geom_mc}"
            )
        # Every multiple-choice item precedes every short-answer item, which
        # precedes Part 2 — matches how the papers are laid out.
        order = {"mc": 0, "short": 1, "open": 2}
        ranks = [order[s.kind] for s in self.slots]
        if ranks != sorted(ranks):
            raise ValueError(f"{self.code}: item kinds are out of order: {ranks}")


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIC — the 2024 and 2025 papers
# ─────────────────────────────────────────────────────────────────────────────
# Point vector taken verbatim from the 21 June 2024 key (Вариант 1):
#   2,2,2,3,3,3,3,3,3,3,4,3,3,4,4,4,4,4,4,4  →  65
# 2025 differs only in where the 4s fall; the shape is the same.

_CLASSIC_SLOTS: tuple[Slot, ...] = (
    Slot(1,  "part1", "mc", "arithmetic_expression",      (2,)),
    Slot(2,  "part1", "mc", "expression_at_value",        (2,)),
    Slot(3,  "part1", "mc", "expand_or_factor",           (2,)),
    Slot(4,  "part1", "mc", "linear_equation",            (3,)),
    Slot(5,  "part1", "mc", "inequality_integer_bound",   (3,)),
    Slot(6,  "part1", "mc", "absolute_value_equation",    (3,)),
    Slot(7,  "part1", "mc", "shortcut_multiplication",    (3,)),
    Slot(8,  "part1", "mc", "probability",                (3,)),
    Slot(9,  "part1", "mc", "word_problem_units",         (3,)),
    Slot(10, "part1", "mc", "geom_lines_angles",          (3,), diagram=True),
    Slot(11, "part1", "mc", "geom_two_triangles",         (4,), diagram=True),
    Slot(12, "part1", "mc", "geom_quadrilateral",         (3,), diagram=True),
    Slot(13, "part1", "mc", "geom_triangle_cevians",      (3,), diagram=True),
    Slot(14, "part1", "mc", "geom_right_triangle",        (4,), diagram=True),
    Slot(15, "part1", "mc", "geom_side_ordering",         (4,), diagram=True),
    Slot(16, "part1", "mc", "expression_from_words",      (4,)),
    Slot(17, "part1", "mc", "word_problem_mixture",       (4,)),
    Slot(18, "part1", "mc", "word_problem_ratio",         (4,)),
    Slot(19, "part1", "mc", "data_chart",                 (4,), diagram=True),
    Slot(20, "part1", "mc", "probability_expression",     (4,)),
    Slot(21, "part2", "open", "open_algebra",             (12,)),
    Slot(22, "part2", "open", "open_word_problem",        (11,)),
    Slot(23, "part2", "open", "open_geometry_proof",      (12,), diagram=True),
)

# ─────────────────────────────────────────────────────────────────────────────
# NVO2026 — the 19 June 2026 paper
# ─────────────────────────────────────────────────────────────────────────────
# MC 1–14:    2,2,2,3,2,3,2,3,3,2,2,3,3,3          → 35
# Short 15–21: 4,4,(2+3),4,(2+3),4,4                → 30
# Part 2 22–24: 12, 11, 12                          → 35

_NVO2026_SLOTS: tuple[Slot, ...] = (
    Slot(1,  "part1", "mc", "arithmetic_expression",      (2,)),
    Slot(2,  "part1", "mc", "linear_equation",            (2,)),
    Slot(3,  "part1", "mc", "absolute_value_equation",    (2,)),
    Slot(4,  "part1", "mc", "inequality_interval",        (3,)),
    Slot(5,  "part1", "mc", "powers",                     (2,)),
    Slot(6,  "part1", "mc", "probability",                (3,)),
    Slot(7,  "part1", "mc", "percent_interest",           (2,)),
    Slot(8,  "part1", "mc", "work_rate",                  (3,)),
    Slot(9,  "part1", "mc", "expand_or_factor",           (3,)),
    Slot(10, "part1", "mc", "geom_coordinate",            (2,), diagram=True),
    Slot(11, "part1", "mc", "geom_triangle_cevians",      (2,), diagram=True),
    Slot(12, "part1", "mc", "geom_parallel_lines",        (3,), diagram=True),
    Slot(13, "part1", "mc", "geom_right_triangle",        (3,), diagram=True),
    Slot(14, "part1", "mc", "geom_quadrilateral",         (3,), diagram=True),
    Slot(15, "part1", "short", "quadratic_by_factoring",  (4,)),
    Slot(16, "part1", "short", "expression_at_value",     (4,)),
    Slot(17, "part1", "short", "data_chart",              (2, 3), diagram=True),
    Slot(18, "part1", "short", "percent_word_problem",    (4,)),
    Slot(19, "part1", "short", "geom_median_hypotenuse",  (2, 3), diagram=True),
    Slot(20, "part1", "short", "geom_bisectors_incentre", (4,), diagram=True),
    Slot(21, "part1", "short", "symbolic_perimeter",      (4,)),
    Slot(22, "part2", "open", "open_algebra",             (12,)),
    Slot(23, "part2", "open", "open_word_problem",        (11,)),
    Slot(24, "part2", "open", "open_geometry_proof",      (12,), diagram=True),
)


CLASSIC = Blueprint(
    code="classic",
    label_bg="Класически НВО",
    subtitle_bg="Формат 2024 – 2025",
    years_bg="както на изпитите през 2024 и 2025 г.",
    part1_minutes=75,
    part2_minutes=90,
    slots=_CLASSIC_SLOTS,
)

NVO2026 = Blueprint(
    code="nvo2026",
    label_bg="НВО 2026",
    subtitle_bg="Новият формат",
    years_bg="както на изпита през юни 2026 г.",
    part1_minutes=90,
    part2_minutes=90,
    slots=_NVO2026_SLOTS,
)

BLUEPRINTS: dict[str, Blueprint] = {bp.code: bp for bp in (CLASSIC, NVO2026)}

DEFAULT_BLUEPRINT = NVO2026.code

for _bp in BLUEPRINTS.values():
    _bp.validate()


def with_profile(slots: tuple[Slot, ...], profile: DifficultyProfile) -> tuple[Slot, ...]:
    """Stamp a difficulty onto every slot of a paper being generated.

    The blueprint literals stay at ``ACTUAL`` — they describe the format, and
    the format does not change with difficulty. This is what carries the
    student's chosen level down to the templates, which read ``slot.profile``.
    """
    if profile is ACTUAL:
        return slots
    return tuple(replace(s, profile=profile) for s in slots)


def get_blueprint(code: str | None) -> Blueprint:
    """Resolve a blueprint code, falling back to the current official format.

    Unknown codes fall back rather than raising: a stale client that still
    posts ``format='full'`` must keep working, and a student mid-exam should
    never see a 500 because an enum drifted.
    """
    if code and code in BLUEPRINTS:
        return BLUEPRINTS[code]
    return BLUEPRINTS[DEFAULT_BLUEPRINT]


def short_form(blueprint: Blueprint, *, mc: int = 12, short: int = 2, open_: int = 1) -> tuple[Slot, ...]:
    """A trimmed sitting for practice mode: a prefix-balanced subset of Part 1.

    Keeps the algebra-then-geometry order and the diagram positions, so a short
    paper still *reads* like the real thing — it is just shorter. Points no
    longer total 65, which is expected and is why the verifier checks the
    points total against the slots it was given rather than the constant.
    """
    mc_slots = list(blueprint.mc_slots)
    geom = [s for s in mc_slots if s.topic.startswith("geom_")]
    algebra = [s for s in mc_slots if not s.topic.startswith("geom_")]

    # Split the multiple-choice budget the way the real papers do — roughly
    # 1:1 algebra to geometry, per the ministry's own 2015 optimisation memo.
    want_geom = min(len(geom), max(1, mc // 2))
    want_alg = min(len(algebra), mc - want_geom)
    chosen = algebra[:want_alg] + geom[:want_geom]

    chosen += list(blueprint.short_slots)[:short]
    chosen += list(blueprint.open_slots)[:open_]
    return tuple(sorted(chosen, key=lambda s: s.position))
