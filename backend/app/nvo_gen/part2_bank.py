"""Curated extended-response items for Part 2.

Part 1 is generated; Part 2 is not. The reasoning, stated plainly:

  * A Part 2 item is an 11–12 point multi-part proof whose marking scheme
    awards credit for *intermediate* results — "1 т. за съставяне и опростяване
    на уравнението", "по 0,5 т. на верен отговор". Generating a stem is the
    easy half; generating a defensible marking scheme is not.
  * These items are graded by a person (or by the vision grader in
    ``mobile_uploads``), so an item that is subtly ill-posed is not caught by a
    key comparison the way a multiple-choice item is.
  * The cost of being wrong is asymmetric. A flawed Part 1 item wastes two
    minutes; a flawed proof wastes twenty and teaches the student a false
    method.

So each entry here is hand-authored against the structure of the real papers,
with light parameterisation where the numbers genuinely do not change the
reasoning. A student gets an unlimited supply of Part 1 and a deep but finite
Part 2 — which is the right trade, because nobody sits enough papers to
exhaust a few dozen proofs.

Every item declares its own sub-part points; the sum must equal the blueprint
slot total (12 / 11 / 12), which ``verify`` enforces.
"""
from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Callable, Sequence

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.registry import GeneratedItem, Retry
from app.nvo_gen.scene import Figure, lerp, line_intersection, midpoint, parallelogram, right_triangle, scalene_triangle


@dataclass(frozen=True)
class Part2Item:
    code: str
    topic: str
    stem: str
    parts: tuple[str, ...]
    points: tuple[int, ...]
    answers: tuple[str, ...]
    marking: str
    scene: dict | None = None
    difficulty: str = "hard"

    def to_generated(self, slot: Slot) -> GeneratedItem:
        return GeneratedItem(
            topic=slot.topic, kind="open", points=self.points,
            stem=self.stem, parts=list(self.parts),
            correct_answer=list(self.answers),
            scene=self.scene, difficulty=self.difficulty,
            solution=self.marking, signature=f"p2:{self.code}",
            template_code=self.code,
        )


Builder = Callable[[random.Random], Part2Item]
_BANK: dict[str, list[Builder]] = {
    "open_algebra": [],
    "open_word_problem": [],
    "open_geometry_proof": [],
}
#: Band per builder, keyed by the function object. No item here is banded
#: "easy" — a twelve-point proof never is — so the levels choose between
#: "medium" (the most tractable item of its topic) and "hard" (the gnarliest).
_BANDS: dict[Builder, str] = {}


#: How often a builder may reject its own draw before the bank gives up on it.
#: Builders solve for their derived quantities and raise ``Retry`` when a draw
#: does not close; callers — the assembler, the capacity script, the tests —
#: call a builder directly, so the retry lives here rather than in each of them.
_BUILD_ATTEMPTS = 60


def part2(topic: str, *, band: str = "hard") -> Callable[[Builder], Builder]:
    def decorate(fn: Builder) -> Builder:
        @functools.wraps(fn)
        def build(rng: random.Random) -> Part2Item:
            for _ in range(_BUILD_ATTEMPTS - 1):
                try:
                    return fn(rng)
                except Retry:
                    continue
            return fn(rng)
        _BANK[topic].append(build)
        _BANDS[build] = band
        return build
    return decorate


def bank_for(topic: str) -> tuple[Builder, ...]:
    return tuple(_BANK.get(topic, ()))


def band_of(builder: Builder) -> str:
    return _BANDS.get(builder, "hard")


# ═══════════════════════════════════════════════════════════════════════════
# OPEN ALGEBRA — 12 points, and OPEN WORD PROBLEM — 11 points
# ═══════════════════════════════════════════════════════════════════════════
# These live in part2_algebra.py and part2_word.py, which register into this
# bank when imported at the bottom of this module.


# ═══════════════════════════════════════════════════════════════════════════
# OPEN GEOMETRY PROOF — 12 points
# ═══════════════════════════════════════════════════════════════════════════

def _placed(maths: dict[str, tuple[float, float]], *, dots: set[str] = frozenset(),
            span: float = 200.0) -> Figure:
    """Lay out points given in maths coordinates (y up) as a Figure, scaled to fit.

    Every proof figure below is *solved*, not sketched: the bisector's foot is
    where the bisector theorem puts it, the perpendicular really is one. The old
    figures placed those points at random along a side, so the picture printed
    beside a proof contradicted the proof — L was not on the bisector, PQ was
    not perpendicular to BL, and an isosceles triangle was drawn scalene.
    """
    xs = [p[0] for p in maths.values()]
    ys = [p[1] for p in maths.values()]
    k = span / max(max(xs) - min(xs), max(ys) - min(ys))
    f = Figure()
    for name, (x, y) in maths.items():
        f.put(name, (x * k, -y * k), dot=name in dots)
    return f


def _foot_on_line(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    return (ax + t * dx, ay + t * dy)


def _meet(p1, p2, p3, p4):
    """Intersection of line p1p2 with line p3p4."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p1, p2, p3, p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


def _on_segment_by_ratio(a, b, ra: float, rb: float):
    """The point dividing AB with AX : XB = ra : rb."""
    t = ra / (ra + rb)
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def _rectangle_with_bisectors(rng: random.Random) -> dict:
    """ABCD, the bisectors DQ of ∠ADB and BP of ∠DBC, and R with ARBD a parallelogram."""
    w = 1.0
    h = rng.uniform(0.52, 0.72)
    A, B, C, D = (0.0, 0.0), (w, 0.0), (w, h), (0.0, h)
    bd = math.hypot(w, h)
    Q = _on_segment_by_ratio(A, B, h, bd)          # AQ : QB = DA : DB
    P = _on_segment_by_ratio(C, D, h, bd)          # CP : PD = BC : BD
    R = (A[0] + B[0] - D[0], A[1] + B[1] - D[1])   # ARBD is a parallelogram
    O = (w / 2, h / 2)
    f = _placed({"A": A, "B": B, "C": C, "D": D, "O": O, "P": P, "Q": Q, "R": R},
                dots={"O", "P", "Q"})
    f.path(["A", "B", "C", "D"], close=True)
    f.segs([("A", "C"), ("B", "D"), ("B", "P"), ("D", "Q"), ("A", "R"), ("B", "R")])
    f.right_angle("B", "A", "C")
    return f.to_spec(aria=("Правоъгълник ABCD с пресечна точка O на диагоналите, "
                           "ъглополовящи DQ и BP и точка R на правата CB, за която AR е "
                           "успоредна на BD"), rng=rng, upright=True)


@part2("open_geometry_proof")
def rectangle_bisectors_proof(rng: random.Random) -> Part2Item:
    """2026 Q24: congruence, an equal-length proof, an area identity, then a ratio.

    The statement does not depend on the rectangle's proportions until part Г
    fixes ∠DBC = 2∠ABD, so there is one item, printed on a solved figure.
    """
    return Part2Item(
        code="geo_rect_bisectors",
        topic="open_geometry_proof",
        stem=("В правоъгълника $ABCD$ диагоналите се пресичат в точка $O$. "
              "Ъглополовящите на $\\sphericalangle DBC$ и $\\sphericalangle ADB$ "
              "пресичат $CD$ и $AB$ съответно в точките $P$ и $Q$. През точка $A$ е "
              "построена права, успоредна на $BD$, която пресича правата $CB$ в точка $R$."),
        parts=(
            "А) Докажете, че $\\triangle DQO \\cong \\triangle BPO$.",
            "Б) Докажете, че $AC = AR$.",
            "В) Докажете, че сборът от лицата на $\\triangle ADQ$ и $\\triangle QBP$ "
            "е равен на половината от лицето на $ABCD$.",
            "Г) Ако $\\sphericalangle DBC = 2\\sphericalangle ABD$, докажете, че "
            "$AQ : AB = 1 : 3$, и намерете мярката на $\\sphericalangle RAC$.",
        ),
        points=(3, 3, 2, 4),
        answers=(
            "△DQO ≅ △BPO по I признак: DQ = BP (QBPD е успоредник), DO = BO, ∠ODQ = ∠OBP",
            "ARBD е успоредник, значи AR = BD = AC",
            "S(ADQ) + S(QBP) = AD·(AQ + QB)/2 = AD·AB/2 = S(ABCD)/2",
            "∠ABD = 30°, DQ = QB = 2AQ, AQ : AB = 1 : 3; ∠RAC = 60°",
        ),
        marking=(
            "А) $\\sphericalangle ODQ = \\sphericalangle OBP$ — 1 т.; $DO = BO$ — 1 т.; "
            "$DQ = BP$ — 1 т.\n"
            "Б) $ARBD$ е успоредник — 1 т.; $BR = AD = BC$ — 1 т.; $\\triangle ARC$ е "
            "равнобедрен — 1 т.\n"
            "В) Изразяване на двете лица чрез $AD$, $AQ$ и $QB$ — 1 т.; сумиране до "
            "$\\frac{S_{ABCD}}{2}$ — 1 т.\n"
            "Г) Намиране, че $\\sphericalangle ABD = 30^\\circ$ — 1 т.; $DQ = QB = 2AQ$ — 1 т.; "
            "$AQ : AB = 1 : 3$ — 1 т.; $\\sphericalangle RAC = 60^\\circ$ — 1 т."
        ),
        scene=_rectangle_with_bisectors(rng),
    )


def _isosceles_rhombus_figure(alpha: int, rng: random.Random) -> dict:
    """AC = BC with base angle α; BL the bisector; PQ the perpendicular bisector of BL."""
    ta = math.tan(math.radians(alpha))
    A, B = (0.0, 0.0), (1.0, 0.0)
    C = (0.5, 0.5 * ta)
    ab, bc = 1.0, math.hypot(0.5, 0.5 * ta)
    L = _on_segment_by_ratio(A, C, ab, bc)          # AL : LC = AB : BC
    M = ((B[0] + L[0]) / 2, (B[1] + L[1]) / 2)
    perp = (M[0] - (L[1] - B[1]), M[1] + (L[0] - B[0]))
    P = _meet(M, perp, A, B)
    Q = _meet(M, perp, B, C)
    f = _placed({"A": A, "B": B, "C": C, "L": L, "P": P, "Q": Q, "M": M},
                dots={"L", "P", "Q"})
    f.path(["A", "B", "C"], close=True)
    f.segs([("B", "L"), ("P", "Q"), ("P", "L"), ("Q", "L")])
    f.right_angle("M", "Q", "B")
    f.tick("A", "C", count=2)
    f.tick("B", "C", count=2)
    f.tick("B", "M")
    f.tick("M", "L")
    return f.to_spec(aria=("Равнобедрен триъгълник ABC с AC = BC, ъглополовяща BL и права "
                           "PQ, перпендикулярна на BL през средата ѝ M"), rng=rng, upright=True)


@part2("open_geometry_proof", band="medium")
def isosceles_rhombus_proof(rng: random.Random) -> Part2Item:
    """2023 Q23: a bisector, the perpendicular through its midpoint, and a rhombus.

    The paper has ∠BLC = 60°, so α = 40°. The chain holds for every base angle
    α: ∠BLC = α + α/2 is the exterior angle of △ABL; PQ is the perpendicular
    bisector of BL, so PB = PL, QB = QL, and with ∠PBL = ∠LBQ the four sides
    are equal; QL ∥ AB then gives ∠CLQ = ∠CQL = α, so CL = CQ and AL = BQ.
    Part Г, AP > PQ, compares AP = 2s·cos α with PQ = 2s·sin(α/2), which needs
    α < 60° — hence the cap below.
    """
    alpha = rng.choice([32, 36, 40, 44, 48, 52, 56])
    blc = alpha * 3 // 2
    gamma = 180 - 2 * alpha
    return Part2Item(
        code=f"geo_iso_rhombus_{blc}",
        topic="open_geometry_proof",
        stem=(f"В $\\triangle ABC$ $AC = BC$, $BL$ $(L \\in AC)$ е ъглополовящата на "
              f"$\\sphericalangle ABC$ и $\\sphericalangle BLC = {blc}^\\circ$. През "
              f"средата на $BL$ е построена права $PQ$ така, че $PQ \\perp BL$ "
              f"$(P \\in AB,\\ Q \\in BC)$."),
        parts=(
            "А) Намерете ъглите на $\\triangle ABC$.",
            "Б) Докажете, че $PBQL$ е ромб.",
            "В) Докажете, че $AL = BQ$.",
            "Г) Докажете, че $AP > PQ$.",
        ),
        points=(3, 3, 3, 3),
        answers=(
            f"∠BAC = ∠ABC = {alpha}°, ∠ACB = {gamma}°",
            "PQ е симетрала на BL: PB = PL, QB = QL; ∠PBL = ∠QBL, значи PB = BQ и PBQL е ромб",
            "QL ∥ AB, ∠CLQ = ∠CQL, значи CL = CQ и AL = AC − CL = BC − CQ = BQ",
            f"AL = PL, ∠APL = {alpha}° < ∠ALP; в △APL AP лежи срещу по-големия ъгъл; "
            f"PQ < AP",
        ),
        marking=(
            f"А) $\\sphericalangle BLC$ е външен за $\\triangle ABL$: "
            f"$\\alpha + \\frac{{\\alpha}}{{2}} = {blc}^\\circ$ — 1 т.; "
            f"$\\alpha = {alpha}^\\circ$ — 1 т.; $\\sphericalangle ACB = {gamma}^\\circ$ — 1 т.\n"
            "Б) $PQ$ е симетрала на $BL$, значи $PB = PL$ и $QB = QL$ — 2 т.; извод за "
            "ромб — 1 т.\n"
            "В) $QL \\parallel AB$ и $\\triangle CLQ$ е равнобедрен — 2 т.; извод — 1 т.\n"
            "Г) Сравняване на страни срещу различни ъгли — 2 т.; извод — 1 т."
        ),
        scene=_isosceles_rhombus_figure(alpha, rng),
    )


def _parallelogram_height_figure(rng: random.Random) -> dict:
    """∠BAD = 45°, AC splitting it 2 : 1, DK ⊥ AB, DH ⊥ AC meeting AB at L."""
    s = math.sqrt(0.5)
    d = 1.0
    b = d * s * (1 / math.tan(math.radians(15)) - 1)   # makes ∠BAC = 15°
    A, B = (0.0, 0.0), (b, 0.0)
    D = (d * s, d * s)
    C = (B[0] + D[0], D[1])
    K = (D[0], 0.0)
    F_ = _meet(D, K, A, C)
    H = _foot_on_line(D, A, C)
    L = _meet(D, H, A, B)
    f = _placed({"A": A, "B": B, "C": C, "D": D, "K": K, "F": F_, "H": H, "L": L},
                dots={"K", "F", "H", "L"})
    f.path(["A", "B", "C", "D"], close=True)
    f.segs([("A", "C"), ("D", "K"), ("D", "L")])
    f.right_angle("K", "D", "B")
    f.right_angle("H", "D", "C")
    return f.to_spec(aria=("Успоредник ABCD с ъгъл 45° при A, височина DK към AB, диагонал "
                           "AC и перпендикуляр DH към AC, пресичащ AB в L"), rng=rng, upright=True)


@part2("open_geometry_proof")
def parallelogram_height_proof(rng: random.Random) -> Part2Item:
    """2024 Q23: a height, a diagonal, and areas expressed through two segments.

    Only ∠BAD = 45° works: part Б needs AK = DK, which is △AKD being an
    isosceles right triangle, and part А's BC : DH = 2 : 1 needs ∠DAC = 30°.
    The old item also offered 60°, for which both statements are false.
    """
    return Part2Item(
        code="geo_par_height_45",
        topic="open_geometry_proof",
        stem=("В успоредника $ABCD$ $(AB > AD)$ $\\sphericalangle BAD = 45^\\circ$ и "
              "височината $DK$ $(K \\in AB)$ към страната $AB$ пресича диагонала $AC$ в "
              "точка $F$. През върха $D$ е построена права, перпендикулярна на $AC$, "
              "която пресича диагонала $AC$ и страната $AB$ съответно в точките $H$ и $L$."),
        parts=(
            "А) Ако $\\sphericalangle DAC : \\sphericalangle BAC = 2 : 1$, намерете "
            "ъглите на $\\triangle ADL$ и определете отношението $BC : DH$.",
            "Б) Докажете, че $\\triangle AFK \\cong \\triangle DLK$.",
            "В) Ако $AF = m$ и $CH = n$, изразете лицата на $\\triangle DLC$ и на "
            "успоредника $ABCD$ чрез $m$ и $n$.",
        ),
        points=(4, 4, 4),
        answers=(
            "∠DAL = 45°, ∠ADL = 60°, ∠ALD = 75°; BC : DH = 2 : 1",
            "△AFK ≅ △DLK по II признак (AK = DK, ∠AKF = ∠DKL = 90°, ∠KAF = ∠KDL), AF = DL",
            "S(DLC) = m·n/2; S(ABCD) = m·n",
        ),
        marking=(
            "А) $\\sphericalangle DAC = 30^\\circ$, $\\sphericalangle BAC = 15^\\circ$ — 1 т.; "
            "ъглите на $\\triangle ADL$: $45^\\circ$, $60^\\circ$, $75^\\circ$ — 2 т.; "
            "$DH = \\frac{AD}{2}$ (срещу ъгъл от $30^\\circ$), $BC : DH = 2 : 1$ — 1 т.\n"
            "Б) $AK = DK$ ($\\triangle AKD$ е равнобедрен правоъгълен) — 1 т.; "
            "$\\sphericalangle KAF = \\sphericalangle KDL$ — 2 т.; извод по признак — 1 т.\n"
            "В) $AF = DL = m$, $S_{DLC} = \\frac{DL \\cdot CH}{2} = \\frac{mn}{2}$ — 2 т.; "
            "$S_{ABCD} = 2S_{ACD}$, $S_{ACD} = S_{DLC}$ (обща основа $DC$, $AL \\parallel DC$), "
            "$S_{ABCD} = mn$ — 2 т."
        ),
        scene=_parallelogram_height_figure(rng),
    )


def sample_part2(topic: str, rng: random.Random, slot: Slot,
                 *, exclude: Sequence[str] = ()) -> GeneratedItem:
    """Draw one curated item for `topic`, avoiding codes already on the paper.

    The slot's difficulty profile biases *which* of the topic's items is
    reached, the same way it biases Part 1 template choice — a gentler level
    tends toward the more tractable proof. It is only a bias: every item stays
    reachable at every level, because the bank is small and a student who sits
    several papers should still see all of it.
    """
    builders = list(bank_for(topic))
    if not builders:
        raise LookupError(f"no curated Part 2 items for topic {topic!r}")
    _shuffle_by_band(builders, slot, rng)
    first: Part2Item | None = None
    for build in builders:
        item = build(rng)
        first = first or item
        if item.code not in exclude:
            return item.to_generated(slot)
    assert first is not None
    return first.to_generated(slot)


def _shuffle_by_band(builders: list[Builder], slot: Slot, rng: random.Random) -> None:
    """Shuffle in place, weighting each builder by its band at this difficulty."""
    weighted = sorted(
        builders,
        key=lambda b: rng.random() ** (1.0 / max(slot.profile.weight_for(band_of(b)), 1e-6)),
        reverse=True,
    )
    builders[:] = weighted


# ─── two isosceles triangles on the extensions, then a parallelogram ─────────
# Transcribed from 2025 Q23. The paper fixes the ratio at 1 : 9 : 2, but the
# whole construction turns out to depend on the obtuse angle alone:
#
#     ∠BCP = ∠BAM = ∠MDP = 2β − 180       ∠CBP = ∠CPB = ∠ABM = ∠AMB
#                                          = ∠DMP = ∠DPM = 180 − β
#
# which the ministry's own solution shows in the β = 135 case and which holds
# for every β > 90 (checked numerically over the whole admissible range, and
# asserted in tests). So the item parameterises over the ratio rather than
# being pinned to the one the paper printed.


def _angle_ratios(cap: int = 12) -> list[tuple[int, int, int]]:
    """Ratios p : q : r that make the construction work and read like a paper.

    The middle angle must be obtuse, or P and M do not lie beyond B the way
    the stem says. It is capped below 160° so the triangle is not a sliver and
    2β − 180 stays a reportable angle. Components are capped because „1 : 9 : 2”
    is the register the papers write ratios in — „2 : 19 : 9” is not, even
    though it produces perfectly good angles.
    """
    out: set[tuple[int, int, int]] = set()
    for total in range(3, 31):
        if 180 % total:
            continue
        k = 180 // total
        for p in range(1, total):
            for q in range(1, total):
                r = total - p - q
                if r < 1 or gcd(gcd(p, q), r) != 1 or max(p, q, r) > cap:
                    continue
                alpha, beta, gamma = p * k, q * k, r * k
                # 15° is the floor for the two acute angles. Below it the
                # triangle draws as a sliver: A and B end up almost on top of
                # each other and the six labels around them stop separating.
                if not 105 <= beta <= 150 or alpha < 15 or gamma < 15:
                    continue
                out.add((p, q, r))
    return sorted(out)


_RATIOS = _angle_ratios()


def _two_isosceles_figure(alpha: int, beta: int, gamma: int,
                          rng: random.Random) -> dict:
    """Place A, B, C, P, M and D exactly, then let `to_spec` fit them to the box.

    Built from the real construction rather than laid out by eye, because this
    figure carries several equalities at once — BC = PC, AB = AM, AD = CP — and
    a drawing that merely suggests them would contradict the tick marks on it.
    A similarity transform keeps every one of them, so posing is still safe.
    """
    a = math.sin(math.radians(alpha))        # BC, opposite A
    c = math.sin(math.radians(gamma))        # AB, opposite C
    cb, sb = math.cos(math.radians(beta)), math.sin(math.radians(beta))

    # Maths coordinates, y upward: B at the origin, A along the positive x axis.
    maths = {
        "B": (0.0, 0.0),
        "A": (c, 0.0),
        "C": (a * cb, a * sb),
        "P": (2 * a * cb, 0.0),              # CP = CB puts P at twice the foot
        "M": (2 * c * cb * cb, 2 * c * cb * sb),
        "D": (c + a * cb, a * sb),           # ABCD is a parallelogram
    }
    xs = [p[0] for p in maths.values()]
    ys = [p[1] for p in maths.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    k = 190.0 / span

    f = Figure()
    for name, (x, y) in maths.items():
        f.put(name, (x * k, -y * k))         # SVG y runs downward

    f.path(["A", "B", "P"])
    f.segs([("A", "C"), ("B", "C"), ("C", "P")])
    f.segs([("B", "M"), ("A", "M")])
    f.segs([("A", "D"), ("D", "C")])
    f.segs([("M", "D"), ("D", "P"), ("M", "P")])
    f.tick("C", "B")
    f.tick("C", "P")
    f.tick("A", "B", count=2)
    f.tick("A", "M", count=2)
    if 2 * beta - 180 == 90:
        f.right_angle("A", "M", "B")
        f.right_angle("C", "B", "P")
    return f.to_spec(
        aria=(f"Триъгълник ABC с ъгли {alpha}, {beta} и {gamma} градуса; точка P върху "
              f"продължението на AB отвъд B с BC = PC, точка M върху продължението на "
              f"CB отвъд B с AM = AB, и точка D, в която се пресичат успоредните на AB "
              f"през C и на BC през A"),
        # A, B and P are collinear by construction and the papers print that
        # line horizontal; posing would tilt it by up to 7° for no gain, since
        # the mirror and the rescale already vary the figure between papers.
        rng=rng, upright=True,
    )


@part2("open_geometry_proof")
def two_isosceles_and_parallelogram(rng: random.Random) -> Part2Item:
    """2025 Q23, generalised: the whole chain depends only on the obtuse angle.

    Part В is the one that earns the marks. It is not an angle chase — it needs
    the congruence △MAD ≅ △DCP, which the ministry's solution gets from
    AD = CP, AM = DC and ∠DAM = ∠PCD = β. MD = DP follows, and ∠MDP is then
    ∠ADC less the two angles that the congruence shows sum to 180 − β.
    """
    p, q, r = rng.choice(_RATIOS)
    k = 180 // (p + q + r)
    alpha, beta, gamma = p * k, q * k, r * k
    base = 180 - beta                       # the equal angles, everywhere
    apex = 2 * beta - 180                   # ∠BCP = ∠BAM = ∠MDP

    return Part2Item(
        code=f"geo_two_iso_{p}_{q}_{r}",
        topic="open_geometry_proof",
        stem=("В $\\triangle ABC$ отношението на ъглите е, както следва "
              f"$\\sphericalangle BAC : \\sphericalangle ABC : \\sphericalangle ACB "
              f"= {p} : {q} : {r}$. Точка $P$ лежи на лъча $AB$, като $B$ е между $A$ "
              "и $P$ и $BC = PC$. Точка $M$ лежи на лъча $CB$, като $B$ е между $C$ "
              "и $M$ и $AM = AB$."),
        parts=(
            "А) Намерете мерките на ъглите на $\\triangle ABC$.",
            "Б) Намерете мерките на ъглите на $\\triangle BCP$ и на $\\triangle AMB$.",
            "В) През точка $C$ е построена права $c \\parallel AB$, а през точка $A$ — "
            "права $a \\parallel BC$, като $a \\cap c = D$. Намерете мерките на "
            "ъглите на $\\triangle MDP$.",
        ),
        points=(3, 4, 5),
        answers=(
            f"{alpha}°, {beta}°, {gamma}°",
            f"△BCP: {base}°, {base}°, {apex}°; △AMB: {base}°, {base}°, {apex}°",
            f"{apex}°, {base}°, {base}°",
        ),
        marking=(
            f"А) От $\\alpha : \\beta : \\gamma = {p} : {q} : {r}$ следва "
            f"$({p} + {q} + {r})k = 180^\\circ$ — 1 т.; $k = {k}^\\circ$ — 1 т.; "
            f"$\\sphericalangle BAC = {alpha}^\\circ$, $\\sphericalangle ABC = "
            f"{beta}^\\circ$, $\\sphericalangle ACB = {gamma}^\\circ$ — 1 т.\n"
            f"Б) $\\sphericalangle CBP = 180^\\circ - {beta}^\\circ = {base}^\\circ$ "
            f"като съседен на $\\sphericalangle ABC$ — 1 т.; от $BC = PC$ следва, че "
            f"$\\triangle BCP$ е равнобедрен, значи $\\sphericalangle BPC = "
            f"{base}^\\circ$ — 1 т.; $\\sphericalangle BCP = {apex}^\\circ$ — 1 т.; "
            f"аналогично за $\\triangle AMB$ от $AM = AB$: $\\sphericalangle ABM = "
            f"\\sphericalangle AMB = {base}^\\circ$ и $\\sphericalangle MAB = "
            f"{apex}^\\circ$ — 1 т.\n"
            f"В) $ABCD$ е успоредник, защото $DC \\parallel AB$ и $AD \\parallel BC$ "
            f"— 1 т.; $AD = BC = CP$ и $AM = AB = DC$ — 1 т.; $\\sphericalangle DAM = "
            f"\\sphericalangle PCD = {beta}^\\circ$ — 1 т.; следователно "
            f"$\\triangle MAD \\cong \\triangle DCP$ по I признак, откъдето $MD = DP$ "
            f"— 1 т.; $\\sphericalangle ADM + \\sphericalangle PDC = 180^\\circ - "
            f"{beta}^\\circ = {base}^\\circ$, значи $\\sphericalangle MDP = "
            f"\\sphericalangle ADC - {base}^\\circ = {beta}^\\circ - {base}^\\circ = "
            f"{apex}^\\circ$, а $\\triangle MDP$ е равнобедрен с ъгли при основата "
            f"{base}$^\\circ$ — 1 т."
        ),
        scene=_two_isosceles_figure(alpha, beta, gamma, rng),
    )


# ─── right triangle, bisector, parallel, midpoint ────────────────────────────
# Transcribed from 2022 Q23. Unlike the 2025 item, this one does *not*
# generalise: NA = NL and LM = BN/2 hold for any acute angle, but
# △AML ≅ △BNL and the equilateral △NML are both specific to ∠CAB = 60°
# (checked numerically at 50°, 60° and 70° — only 60° closes). So the ratio
# stays as the paper printed it and the given length is what varies, which is
# the honest parameterisation rather than a wider one that would be wrong.


@part2("open_geometry_proof", band="medium")
def right_triangle_bisector_midpoint(rng: random.Random) -> Part2Item:
    """A 30–60–90 triangle whose bisector and midline produce an equilateral one.

    The chain: LN ∥ AC makes ∠ALN = ∠CAL, so △ALN is isosceles on NA = NL.
    LN ∥ AC and AC ⊥ CB give ∠NLB = 90°, so LM is the median to the hypotenuse
    of △NLB and LM = BN/2. At ∠CAB = 60° the side NL is also BN/2, and △NML
    comes out equilateral — which is what makes part Г a single multiplication
    rather than a surd.
    """
    bn = rng.choice([4, 6, 8, 10, 12, 14, 16])
    perimeter = 3 * bn // 2

    # The construction, solved rather than sketched: right angle at C, ∠A = 60°.
    tan60 = math.sqrt(3.0)
    ac, ab, cb = 1.0, 2.0, tan60
    cl = cb * ac / (ac + ab)                 # bisector theorem: CL:LB = AC:AB
    maths = {
        "C": (0.0, 0.0),
        "A": (1.0, 0.0),
        "B": (0.0, cb),
        "L": (0.0, cl),
        "N": (1.0 - cl / cb, cl),            # LN ∥ AC, so N is at L's height
    }
    maths["M"] = ((maths["B"][0] + maths["N"][0]) / 2.0,
                  (maths["B"][1] + maths["N"][1]) / 2.0)

    xs = [p[0] for p in maths.values()]
    ys = [p[1] for p in maths.values()]
    k = min(196.0 / (max(xs) - min(xs)), 132.0 / (max(ys) - min(ys)))

    f = Figure()
    for name, (x, y) in maths.items():
        f.put(name, (x * k, -y * k), dot=name in {"L", "N", "M"})
    f.path(["A", "B", "C"], close=True)
    f.segs([("A", "L"), ("L", "N"), ("L", "M")])
    f.right_angle("C", "A", "B")
    f.right_angle("L", "N", "B")
    f.angle("A", "C", "L", arcs=2, radius=26)
    f.angle("A", "L", "B", arcs=2, radius=34)
    f.tick("N", "M")
    f.tick("M", "B")

    return Part2Item(
        code=f"geo_rt_bisector_{bn}",
        topic="open_geometry_proof",
        stem=("Правоъгълният $\\triangle ABC$ е с хипотенуза $AB$, $AL$ "
              "$(L \\in BC)$ е ъглополовящата на $\\sphericalangle CAB$ и "
              "$\\sphericalangle CAB : \\sphericalangle ABC = 2 : 1$. През точка $L$ "
              "е построена права, успоредна на $AC$, която пресича $AB$ в точка $N$, "
              "а точка $M$ е средата на $BN$."),
        parts=(
            "А) Намерете градусните мерки на острите ъгли на $\\triangle ABC$.",
            "Б) Определете вида на $\\triangle ALN$ според страните и според ъглите.",
            "В) Докажете, че $\\triangle AML \\cong \\triangle BNL$.",
            f"Г) Пресметнете периметъра на $\\triangle NML$, ако $BN = {bn}$ cm.",
        ),
        points=(3, 3, 3, 3),
        answers=(
            "60° и 30°",
            "равнобедрен (NA = NL) и тъпоъгълен (∠ANL = 120°)",
            "△AML ≅ △BNL по III признак",
            f"{perimeter} cm",
        ),
        marking=(
            "А) Острите ъгли се допълват до $90^\\circ$ и са в отношение $2 : 1$ — 1 т.; "
            "$3k = 90^\\circ$, $k = 30^\\circ$ — 1 т.; $\\sphericalangle CAB = 60^\\circ$ "
            "и $\\sphericalangle ABC = 30^\\circ$ — 1 т.\n"
            "Б) От $LN \\parallel AC$ следва $\\sphericalangle ALN = \\sphericalangle CAL "
            "= 30^\\circ$ — 1 т.; заедно с $\\sphericalangle LAN = 30^\\circ$ дава "
            "$NA = NL$, т.е. равнобедрен — 1 т.; $\\sphericalangle ANL = 120^\\circ$, "
            "значи е тъпоъгълен — 1 т.\n"
            "В) $LN \\parallel AC$ и $AC \\perp CB$ дават $\\sphericalangle NLB = 90^\\circ$, "
            "затова $LM$ е медиана към хипотенузата и $LM = \\dfrac{BN}{2} = NL$ — 1 т.; "
            "$AL = BL$, защото $\\triangle ALB$ е равнобедрен "
            "($\\sphericalangle LAB = \\sphericalangle LBA = 30^\\circ$) — 1 т.; "
            "$AM = BN$ и извод по III признак — 1 т.\n"
            f"Г) $NM = MB = \\dfrac{{BN}}{{2}} = {bn // 2}$ cm — 1 т.; "
            f"$LM = \\dfrac{{BN}}{{2}} = {bn // 2}$ cm като медиана към хипотенузата и "
            f"$NL = \\dfrac{{BN}}{{2}} = {bn // 2}$ cm срещу ъгъл от $30^\\circ$ — 1 т.; "
            f"$\\triangle NML$ е равностранен и периметърът му е ${perimeter}$ cm — 1 т."
        ),
        scene=f.to_spec(
            aria=("Правоъгълен триъгълник ABC с прав ъгъл при C, ъглополовяща AL към "
                  "страната BC, отсечка LN успоредна на AC с N върху AB, и точка M — "
                  "среда на BN"),
            rng=rng, upright=True,
        ),
    )


# Registers the algebra and word-problem shapes into _BANK.
from app.nvo_gen import part2_algebra, part2_word  # noqa: E402,F401
