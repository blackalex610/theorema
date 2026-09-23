"""Part 2 geometry proofs: twelve real configurations, each with a pool of claims.

Every НВО paper since 2015 has one geometry proof, so the thirteen papers in
NVOS/ hold twelve. A student preparing for the exam has those twelve to
practise on, and so does this bank — but a figure supports far more true,
provable statements than the three or four the paper printed. The 2020 figure
also gives „△AMC is isosceles”, „∠BKC = 60°”, „CK bisects ∠MCB”…

So each configuration here is the paper's construction (its stem and a figure
solved from it) plus a **pool of claims**. A paper draws three or four claims
whose points add up to exactly 12 and orders them from easy to hard, the way
the papers do. (No proof is forced: the 2017 and 2021 items have none.) A student meets a familiar
figure with different questions — which is how the real exam reuses its
standard configurations.

Every claim carries:
  * its prompt, its key, and a marking scheme whose steps add up to its points
    (``test_nvo_proof_pools`` sums them);
  * a ``check`` — a predicate over the drawn, posed figure that measures the
    claim (a congruence as equal sides, a ratio as a ratio). A claim that is not
    true of its own figure fails in CI, before a student ever sees it;
  * ``requires`` — claims it builds on, which must be on the same paper and
    earlier in it.

Configurations and where their numbers may vary — each re-derived before
transcription; the notes on each builder say why they stop where they do:

    2026 Q24  rect_bisectors        fixed; the ratio claim draws its own 30° figure
    2025 Q23  two_isosceles         the angle ratio (every β in 105°–150°)
    2024 Q23  parallelogram_height  fixed at 45° (the claims fail elsewhere)
    2023 Q23  iso_rhombus           the base angle α < 60°
    2022 Q23  rt_bisector           the given length only (60° is essential)
    2021 Q23  heights_midpoint      BC, and the mirrored ratio 4 : 5 : 3
    2020 Q23  bisector_perp         the given length only (30°/45° essential)
    2019 Q25  equilateral_third     the given area only (CM = BC/3 essential)
    2018 Q24  heights_45_30         fixed (45° and 30° are the item)
    2017 Q24  altitude_point        the distance d and AB (acute triangles only)
    2016 Q24  rect_diagonal_bisector  ∠DBC — the whole chain holds for every β
    2015 Q23  iso_mnp               fixed (k = 3 is what makes △NKL isosceles)
"""
from __future__ import annotations

import itertools
import math
import random
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Sequence

from app.nvo_gen.part2_bank import Part2Item, part2
from app.nvo_gen.scene import Figure

Pts = dict[str, tuple[float, float]]
TOTAL = 12


@dataclass(frozen=True)
class Claim:
    key: str
    prompt: str                       # without the letter: „Докажете, че …”
    answer: str
    marking: str                      # steps, each ending „— k т.”
    points: int
    rank: int                         # papers ask easy → hard
    check: Callable[[Pts], bool] | None = field(default=None, compare=False)
    requires: tuple[str, ...] = ()

    @property
    def proof(self) -> bool:
        return self.prompt.startswith("Докажете")


@dataclass
class Setup:
    """One drawn configuration: the numbers it was drawn with, and its claims."""
    code: str
    stem: str
    claims: list[Claim]
    figure: Callable[[set[str], random.Random], dict]   # selected keys -> scene
    aria: str
    band: str = "hard"


# ─── geometry helpers ────────────────────────────────────────────────────────

def dist(a, b) -> float:
    return math.dist(a, b)


def ang(v, a, b) -> float:
    """The angle at v between va and vb, in degrees."""
    ax, ay, bx, by = a[0] - v[0], a[1] - v[1], b[0] - v[0], b[1] - v[1]
    c = (ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def area(a, b, c) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2


def close(x, y, tol=1e-3) -> bool:
    return abs(x - y) <= tol * max(1.0, abs(x), abs(y))


def near(x, y, tol=0.2) -> bool:
    return abs(x - y) <= tol


def between(p, a, b) -> bool:
    return close(dist(a, p) + dist(p, b), dist(a, b))


def parallel(a, b, c, d) -> bool:
    """AB ∥ CD within half a degree — a posed figure's coordinates are rounded,
    which alone tilts a short segment by a few hundredths of a degree."""
    ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
    return abs(ux * vy - uy * vx) <= math.sin(math.radians(0.5)) * math.hypot(ux, uy) * math.hypot(vx, vy)


def foot(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    return (a[0] + t * dx, a[1] + t * dy)


def meet(p1, p2, p3, p4):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p1, p2, p3, p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    a, b = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def ratio_point(a, b, ra, rb):
    """X on AB with AX : XB = ra : rb."""
    t = ra / (ra + rb)
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def triangle(alpha: float, beta: float) -> Pts:
    """A at the origin, AB along the x axis, angle α at A and β at B."""
    gamma = 180 - alpha - beta
    b = math.sin(math.radians(beta))
    c = math.sin(math.radians(gamma))
    return {"A": (0.0, 0.0), "B": (c, 0.0),
            "C": (b * math.cos(math.radians(alpha)), b * math.sin(math.radians(alpha)))}


def place(maths: Pts, *, dots=(), hidden=(), span=200.0) -> Figure:
    xs = [p[0] for p in maths.values()]
    ys = [p[1] for p in maths.values()]
    k = span / max(max(xs) - min(xs), max(ys) - min(ys))
    f = Figure()
    for name, (x, y) in maths.items():
        f.put(name, (x * k, -y * k), dot=name in dots, hidden=name in hidden)
    return f


def fmt(v) -> str:
    """A key value as the papers print it: 12, 7,5."""
    v = Fraction(v).limit_denominator(1000)
    return str(v.numerator) if v.denominator == 1 else f"{float(v):g}".replace(".", ",")


# ─── choosing the claims for one paper ──────────────────────────────────────

def choose(claims: Sequence[Claim], rng: random.Random, *, total: int = TOTAL) -> list[Claim]:
    valid = []
    for r in (3, 4):
        for combo in itertools.combinations(claims, r):
            if sum(c.points for c in combo) != total:
                continue
            keys = {c.key for c in combo}
            if any(q not in keys for c in combo for q in c.requires):
                continue
            valid.append(combo)
    if not valid:
        raise ValueError("no claim set adds up to the slot's points")
    return sorted(rng.choice(valid), key=lambda c: (c.rank, c.key))


def valid_selections(claims: Sequence[Claim], *, total: int = TOTAL) -> int:
    """How many different sets of questions this configuration can ask."""
    n = 0
    for r in (3, 4):
        for combo in itertools.combinations(claims, r):
            keys = {c.key for c in combo}
            if (sum(c.points for c in combo) == total
                    and all(q in keys for c in combo for q in c.requires)):
                n += 1
    return n


LETTERS = "АБВГД"


def assemble(setup: Setup, rng: random.Random, *, topic="open_geometry_proof") -> Part2Item:
    picked = choose(setup.claims, rng)
    keys = {c.key for c in picked}
    scene = setup.figure(keys, rng)
    return Part2Item(
        code=f"geo_{setup.code}_{'+'.join(c.key for c in picked)}",
        topic=topic,
        stem=setup.stem,
        parts=tuple(f"{LETTERS[i]}) {c.prompt}" for i, c in enumerate(picked)),
        points=tuple(c.points for c in picked),
        answers=tuple(c.answer for c in picked),
        marking="\n".join(f"{LETTERS[i]}) {c.marking}" for i, c in enumerate(picked)),
        scene=scene,
        difficulty=setup.band,
    )


#: every configuration builder, so tests can reach the unselected claims too
CONFIGS: dict[str, Callable[[random.Random], Setup]] = {}


def config(name: str, *, band: str = "hard"):
    """Register a configuration: it becomes a Part 2 builder of its own."""
    def decorate(fn: Callable[[random.Random], Setup]):
        CONFIGS[name] = fn

        def build(rng: random.Random) -> Part2Item:
            return assemble(fn(rng), rng)
        build.__name__ = name
        build.__doc__ = fn.__doc__
        part2("open_geometry_proof", band=band)(build)
        return fn
    return decorate


A = r"\sphericalangle"
T = r"\triangle"


# ═══════════════════════════════════════════════════════════════════════════
# 2026 Q24 — rectangle, two bisectors, a parallel through A
# ═══════════════════════════════════════════════════════════════════════════

@config("rect_bisectors")
def rect_bisectors(rng: random.Random) -> Setup:
    """Nothing numeric varies: every claim but the ratio holds for any
    rectangle, and the ratio claim brings its own condition (∠DBC = 2∠ABD),
    so the figure is drawn at ∠ABD = 30° when that claim is on the paper."""
    aspect = rng.uniform(0.50, 0.72)

    def pts(keys) -> Pts:
        h = math.tan(math.radians(30)) if "ratio" in keys else aspect
        A_, B_, C_, D_ = (0.0, 0.0), (1.0, 0.0), (1.0, h), (0.0, h)
        bd = math.hypot(1.0, h)
        return {"A": A_, "B": B_, "C": C_, "D": D_, "O": (0.5, h / 2),
                "P": ratio_point(C_, D_, h, bd), "Q": ratio_point(A_, B_, h, bd),
                "R": (1.0, -h)}

    def figure(keys, r):
        f = place(pts(keys), dots={"O", "P", "Q"})
        f.path(["A", "B", "C", "D"], close=True)
        f.segs([("A", "C"), ("B", "D"), ("B", "P"), ("D", "Q"), ("A", "R"), ("B", "R")])
        f.right_angle("B", "A", "C")
        return f.to_spec(aria=("Правоъгълник ABCD, ъглополовящи DQ и BP, права през A, "
                               "успоредна на BD, до пресичането ѝ R с правата CB"),
                         rng=r, upright=True)

    claims = [
        Claim("parallelogram", "Докажете, че четириъгълникът $QBPD$ е успоредник.",
              "∠QDB = ∠DBP (половини на равните кръстни ∠ADB и ∠DBC), значи DQ ∥ BP; DP ∥ QB",
              f"${A} QDB = {A} DBP$ като половини на равни кръстни ъгли — 1 т.; "
              "$DQ \\parallel BP$ — 1 т.; $DP \\parallel QB$ и извод — 1 т.", 3, 1,
              lambda p: parallel(p["D"], p["Q"], p["P"], p["B"]) and parallel(p["D"], p["P"], p["Q"], p["B"])),
        Claim("B_mid", "Докажете, че $B$ е среда на отсечката $CR$.",
              "ARBD е успоредник (AR ∥ BD, AD ∥ BR), значи BR = AD = BC",
              "$ARBD$ е успоредник — 1 т.; $BR = AD = BC$ — 1 т.", 2, 1,
              lambda p: close(dist(p["B"], p["R"]), dist(p["B"], p["C"])) and between(p["B"], p["C"], p["R"])),
        Claim("angle_ARB", f"Докажете, че ${A} ARB = {A} DBC$.",
              "AR ∥ BD и точките R, B, C лежат на една права — съответни ъгли",
              f"$AR \\parallel BD$ — 1 т.; ${A} ARB$ и ${A} DBC$ са съответни — 1 т.", 2, 1,
              lambda p: near(ang(p["R"], p["A"], p["B"]), ang(p["B"], p["D"], p["C"]))),
        Claim("congruent", f"Докажете, че ${T} DQO \\cong {T} BPO$.",
              "△DQO ≅ △BPO по I признак: DQ = BP, DO = BO, ∠ODQ = ∠OBP",
              f"${A} ODQ = {A} OBP$ — 1 т.; $DO = BO$ — 1 т.; $DQ = BP$ — 1 т.", 3, 2,
              lambda p: close(dist(p["D"], p["Q"]), dist(p["B"], p["P"]))
              and close(dist(p["O"], p["Q"]), dist(p["O"], p["P"]))),
        Claim("AC_AR", "Докажете, че $AC = AR$.",
              "ARBD е успоредник, значи AR = BD = AC",
              f"$ARBD$ е успоредник — 1 т.; $BR = AD = BC$ — 1 т.; ${T} ARC$ е равнобедрен — 1 т.",
              3, 2, lambda p: close(dist(p["A"], p["C"]), dist(p["A"], p["R"]))),
        Claim("O_mid", "Докажете, че $O$ е среда на отсечката $PQ$.",
              "диагоналите QP и BD на успоредника QBPD се разполовяват, а O е среда на BD",
              "диагоналите на успоредника $QBPD$ се разполовяват — 1 т.; $O$ е среда на $BD$, "
              "значи и на $PQ$ — 1 т.", 2, 3,
              lambda p: close(dist(p["O"], p["P"]), dist(p["O"], p["Q"])) and between(p["O"], p["P"], p["Q"]),
              requires=("parallelogram",)),
        Claim("areas", f"Докажете, че сборът от лицата на ${T} ADQ$ и ${T} QBP$ е равен на "
                       "половината от лицето на $ABCD$.",
              "S(ADQ) + S(QBP) = AD·(AQ + QB)/2 = AD·AB/2 = S(ABCD)/2",
              "изразяване на двете лица чрез $AD$, $AQ$ и $QB$ — 1 т.; сумиране до "
              "$\\frac{S_{ABCD}}{2}$ — 1 т.", 2, 3,
              lambda p: close(area(p["A"], p["D"], p["Q"]) + area(p["Q"], p["B"], p["P"]),
                              area(p["A"], p["B"], p["C"]))),
        Claim("ratio", f"Ако ${A} DBC = 2{A} ABD$, докажете, че $AQ : AB = 1 : 3$, и намерете "
                       f"мярката на ${A} RAC$.",
              "∠ABD = 30°, DQ = QB = 2AQ, AQ : AB = 1 : 3; ∠RAC = 60°",
              f"${A} ABD = 30^\\circ$ — 1 т.; $DQ = QB = 2AQ$ — 1 т.; $AQ : AB = 1 : 3$ — 1 т.; "
              f"${A} RAC = 60^\\circ$ — 1 т.", 4, 4,
              lambda p: close(dist(p["A"], p["Q"]) * 3, dist(p["A"], p["B"]))
              and near(ang(p["A"], p["R"], p["C"]), 60)),
    ]
    stem = ("В правоъгълника $ABCD$ диагоналите се пресичат в точка $O$. Ъглополовящите на "
            f"${A} DBC$ и ${A} ADB$ пресичат $CD$ и $AB$ съответно в точките $P$ и $Q$. През "
            "точка $A$ е построена права, успоредна на $BD$, която пресича правата $CB$ в точка $R$.")
    return Setup("rect_bisectors", stem, claims, figure, "rectangle")


# ═══════════════════════════════════════════════════════════════════════════
# 2025 Q23 — two isosceles triangles on the extensions, then a parallelogram
# ═══════════════════════════════════════════════════════════════════════════

def _angle_ratios(cap: int = 12) -> list[tuple[int, int, int]]:
    out = set()
    for tot in range(3, 31):
        if 180 % tot:
            continue
        k = 180 // tot
        for p in range(1, tot):
            for q in range(1, tot):
                r = tot - p - q
                if r < 1 or math.gcd(math.gcd(p, q), r) != 1 or max(p, q, r) > cap:
                    continue
                if 105 <= q * k <= 150 and p * k >= 15 and r * k >= 15:
                    out.add((p, q, r))
    return sorted(out)


_RATIOS = _angle_ratios()


@config("two_isosceles")
def two_isosceles(rng: random.Random) -> Setup:
    """The whole construction depends on the obtuse angle β alone: ∠BCP = ∠BAM
    = ∠MDP = 2β − 180 and the base angles are 180 − β, for every β > 90°."""
    p_, q_, r_ = rng.choice(_RATIOS)
    k = 180 // (p_ + q_ + r_)
    al, be, ga = p_ * k, q_ * k, r_ * k
    base, apex = 180 - be, 2 * be - 180

    a = math.sin(math.radians(al))
    c = math.sin(math.radians(ga))
    cb, sb = math.cos(math.radians(be)), math.sin(math.radians(be))
    maths = {"B": (0.0, 0.0), "A": (c, 0.0), "C": (a * cb, a * sb), "P": (2 * a * cb, 0.0),
             "M": (2 * c * cb * cb, 2 * c * cb * sb), "D": (c + a * cb, a * sb)}

    def figure(keys, r):
        f = place(maths)
        f.path(["A", "B", "P"])
        f.segs([("A", "C"), ("B", "C"), ("C", "P"), ("B", "M"), ("A", "M"),
                ("A", "D"), ("D", "C"), ("M", "D"), ("D", "P"), ("M", "P")])
        f.tick("C", "B"); f.tick("C", "P")
        f.tick("A", "B", count=2); f.tick("A", "M", count=2)
        return f.to_spec(aria="Триъгълник ABC, точки P и M върху продълженията на AB и CB, "
                              "и точка D, в която се пресичат успоредните през C и A",
                         rng=r, upright=True)

    claims = [
        Claim("abc", f"Намерете мерките на ъглите на ${T} ABC$.",
              f"{al}°, {be}°, {ga}°",
              f"$({p_} + {q_} + {r_})k = 180^\\circ$ — 1 т.; $k = {k}^\\circ$ — 1 т.; "
              f"${al}^\\circ$, ${be}^\\circ$, ${ga}^\\circ$ — 1 т.", 3, 1,
              lambda p: near(ang(p["B"], p["A"], p["C"]), be)),
        Claim("mbp", f"Намерете мярката на ${A} MBP$.", f"{be}°",
              f"${A} MBP$ и ${A} ABC$ са противоположни — 1 т.; ${A} MBP = {be}^\\circ$ — 1 т.",
              2, 2, lambda p: near(ang(p["B"], p["M"], p["P"]), be), requires=("abc",)),
        Claim("ad_cp", "Докажете, че $AD = CP$.",
              "ABCD е успоредник, значи AD = BC = CP",
              "$ABCD$ е успоредник — 1 т.; $AD = BC = CP$ — 1 т.", 2, 2,
              lambda p: close(dist(p["A"], p["D"]), dist(p["C"], p["P"]))),
        Claim("bcp_amb", f"Намерете мерките на ъглите на ${T} BCP$ и на ${T} AMB$.",
              f"△BCP: {base}°, {base}°, {apex}°; △AMB: {base}°, {base}°, {apex}°",
              f"${A} CBP = {base}^\\circ$ като съседен на ${A} ABC$ — 1 т.; ${A} BPC = {base}^\\circ$ "
              f"— 1 т.; ${A} BCP = {apex}^\\circ$ — 1 т.; ъглите на ${T} AMB$ — 1 т.", 4, 2,
              lambda p: near(ang(p["C"], p["B"], p["P"]), apex) and near(ang(p["A"], p["M"], p["B"]), apex),
              requires=("abc",)),
        Claim("mad_dcp", f"Докажете, че ${T} MAD \\cong {T} DCP$.",
              "по I признак: AD = BC = CP, AM = AB = DC, ∠DAM = ∠PCD",
              f"$AD = CP$ — 1 т.; $AM = DC$ — 1 т.; ${A} DAM = {A} PCD$ — 1 т.; извод — 1 т.", 4, 3,
              lambda p: close(dist(p["M"], p["A"]), dist(p["D"], p["C"]))
              and close(dist(p["A"], p["D"]), dist(p["C"], p["P"]))
              and near(ang(p["A"], p["D"], p["M"]), ang(p["C"], p["P"], p["D"])), requires=("abc",)),
        Claim("md_dp", "Докажете, че $MD = DP$.",
              "△MAD ≅ △DCP по I признак (AD = CP, AM = DC, ∠DAM = ∠PCD), значи MD = DP",
              f"$AD = CP$ и $AM = AB = DC$ — 1 т.; ${A} DAM = {A} PCD$ — 1 т.; "
              f"${T} MAD \\cong {T} DCP$ и $MD = DP$ — 1 т.", 3, 3,
              lambda p: close(dist(p["M"], p["D"]), dist(p["D"], p["P"]))),
        Claim("mdp", f"Намерете мерките на ъглите на ${T} MDP$.",
              f"{apex}°, {base}°, {base}°",
              f"$ABCD$ е успоредник — 1 т.; $AD = CP$, $AM = DC$ — 1 т.; ${A} DAM = {A} PCD$ — 1 т.; "
              f"${T} MAD \\cong {T} DCP$, $MD = DP$ — 1 т.; ${A} MDP = {apex}^\\circ$, "
              f"при основата ${base}^\\circ$ — 1 т.", 5, 4,
              lambda p: near(ang(p["D"], p["M"], p["P"]), apex), requires=("abc",)),
    ]
    stem = (f"В ${T} ABC$ отношението на ъглите е, както следва ${A} BAC : {A} ABC : {A} ACB = "
            f"{p_} : {q_} : {r_}$. Точка $P$ лежи на лъча $AB$, като $B$ е между $A$ и $P$ и "
            "$BC = PC$. Точка $M$ лежи на лъча $CB$, като $B$ е между $C$ и $M$ и $AM = AB$. "
            f"През точка $C$ е построена права $c \\parallel AB$, а през точка $A$ — права "
            f"$a \\parallel BC$, като $a \\cap c = D$.")
    # the paper builds D only in its last part; here the stem builds it up front,
    # in the paper's words, so that any claim may use it
    return Setup(f"two_iso_{p_}_{q_}_{r_}", stem, claims, figure, "two isosceles")


# ═══════════════════════════════════════════════════════════════════════════
# 2024 Q23 — a 45° parallelogram, a height, a diagonal, a perpendicular to it
# ═══════════════════════════════════════════════════════════════════════════

@config("parallelogram_height")
def parallelogram_height(rng: random.Random) -> Setup:
    """Fixed at 45°: △AFK ≅ △DLK needs AK = DK, and BC : DH = 2 : 1 needs
    ∠DAC = 30°. The figure is the paper's 2 : 1 split, which every claim fits."""
    s = math.sqrt(0.5)
    b = s * (1 / math.tan(math.radians(15)) - 1)
    A_, B_, D_ = (0.0, 0.0), (b, 0.0), (s, s)
    C_ = (B_[0] + D_[0], D_[1])
    K = (D_[0], 0.0)
    F_ = meet(D_, K, A_, C_)
    H = foot(D_, A_, C_)
    L = meet(D_, H, A_, B_)
    maths = {"A": A_, "B": B_, "C": C_, "D": D_, "K": K, "F": F_, "H": H, "L": L}

    def figure(keys, r):
        f = place(maths, dots={"K", "F", "H", "L"})
        f.path(["A", "B", "C", "D"], close=True)
        f.segs([("A", "C"), ("D", "K"), ("D", "L")])
        f.right_angle("K", "D", "B")
        f.right_angle("H", "D", "C")
        return f.to_spec(aria="Успоредник ABCD с ъгъл 45° при A, височина DK, диагонал AC и "
                              "перпендикуляр DH към AC, пресичащ AB в L", rng=r, upright=True)

    claims = [
        Claim("akd", f"Докажете, че ${T} AKD$ е равнобедрен правоъгълен триъгълник.",
              "∠AKD = 90°, ∠KAD = 45°, значи ∠ADK = 45° и AK = DK",
              f"${A} ADK = 45^\\circ$ — 1 т.; $AK = DK$ — 1 т.", 2, 1,
              lambda p: close(dist(p["A"], p["K"]), dist(p["D"], p["K"]))),
        Claim("kdl", f"Докажете, че ${A} KDL = {A} KAF$.",
              "и двата ъгъла допълват ∠ALD до 90°",
              f"${A} KDL = 90^\\circ - {A} ALD$ — 1 т.; ${A} KAF = 90^\\circ - {A} ALD$ — 1 т.",
              2, 1, lambda p: near(ang(p["D"], p["K"], p["L"]), ang(p["A"], p["K"], p["F"]))),
        Claim("afk_dlk", f"Докажете, че ${T} AFK \\cong {T} DLK$.",
              "△AFK ≅ △DLK по II признак (AK = DK, ∠AKF = ∠DKL = 90°, ∠KAF = ∠KDL), AF = DL",
              f"$AK = DK$ — 1 т.; ${A} KAF = {A} KDL$ — 2 т.; извод по признак — 1 т.", 4, 2,
              lambda p: close(dist(p["A"], p["F"]), dist(p["D"], p["L"]))
              and close(dist(p["F"], p["K"]), dist(p["L"], p["K"]))),
        Claim("fk_kl", "Докажете, че $FK = KL$.", "от △AFK ≅ △DLK",
              f"${T} AFK \\cong {T} DLK$ — 1 т.; $FK = KL$ — 1 т.", 2, 3,
              lambda p: close(dist(p["F"], p["K"]), dist(p["K"], p["L"])), requires=("afk_dlk",)),
        Claim("adl", f"Ако ${A} DAC : {A} BAC = 2 : 1$, намерете ъглите на ${T} ADL$ и определете "
                     "отношението $BC : DH$.",
              "∠DAL = 45°, ∠ADL = 60°, ∠ALD = 75°; BC : DH = 2 : 1",
              f"${A} DAC = 30^\\circ$, ${A} BAC = 15^\\circ$ — 1 т.; $45^\\circ$, $60^\\circ$, "
              f"$75^\\circ$ — 2 т.; $DH = \\frac{{AD}}{{2}}$, $BC : DH = 2 : 1$ — 1 т.", 4, 3,
              lambda p: near(ang(p["D"], p["A"], p["L"]), 60) and close(dist(p["B"], p["C"]), 2 * dist(p["D"], p["H"]))),
        Claim("areas", f"Ако $AF = m$ и $CH = n$, изразете лицата на ${T} DLC$ и на успоредника "
                       "$ABCD$ чрез $m$ и $n$.",
              "S(DLC) = m·n/2; S(ABCD) = m·n",
              "$DL = AF = m$, $S_{DLC} = \\frac{DL \\cdot CH}{2} = \\frac{mn}{2}$ — 2 т.; "
              "$S_{ABCD} = 2S_{ACD} = 2S_{DLC} = mn$ — 2 т.", 4, 4,
              lambda p: close(area(p["D"], p["L"], p["C"]), dist(p["A"], p["F"]) * dist(p["C"], p["H"]) / 2)
              and close(2 * area(p["A"], p["C"], p["D"]), dist(p["A"], p["F"]) * dist(p["C"], p["H"])),
              requires=("afk_dlk",)),
    ]
    stem = (f"В успоредника $ABCD$ $(AB > AD)$ ${A} BAD = 45^\\circ$ и височината $DK$ "
            "$(K \\in AB)$ към страната $AB$ пресича диагонала $AC$ в точка $F$. През върха $D$ е "
            "построена права, перпендикулярна на $AC$, която пресича диагонала $AC$ и страната "
            "$AB$ съответно в точките $H$ и $L$.")
    return Setup("par_height", stem, claims, figure, "parallelogram")


# ═══════════════════════════════════════════════════════════════════════════
# 2023 Q23 — isosceles, a bisector, the perpendicular bisector of it, a rhombus
# ═══════════════════════════════════════════════════════════════════════════

@config("iso_rhombus", band="medium")
def iso_rhombus(rng: random.Random) -> Setup:
    """Holds for every base angle α (∠BLC = 3α/2); AP > PQ needs α < 60°."""
    al = rng.choice([32, 36, 40, 44, 48, 52, 56])
    blc, ga = al * 3 // 2, 180 - 2 * al
    ta = math.tan(math.radians(al))
    A_, B_, C_ = (0.0, 0.0), (1.0, 0.0), (0.5, 0.5 * ta)
    L = ratio_point(A_, C_, 1.0, math.hypot(0.5, 0.5 * ta))
    M = mid(B_, L)
    perp = (M[0] - (L[1] - B_[1]), M[1] + (L[0] - B_[0]))
    maths = {"A": A_, "B": B_, "C": C_, "L": L, "M": M,
             "P": meet(M, perp, A_, B_), "Q": meet(M, perp, B_, C_)}

    def figure(keys, r):
        f = place(maths, dots={"L", "P", "Q"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("B", "L"), ("P", "Q"), ("P", "L"), ("Q", "L")])
        f.right_angle("M", "Q", "B")
        f.tick("A", "C", count=2); f.tick("B", "C", count=2)
        f.tick("B", "M"); f.tick("M", "L")
        return f.to_spec(aria="Равнобедрен триъгълник ABC с ъглополовяща BL и права PQ, "
                              "перпендикулярна на BL през средата ѝ M", rng=r, upright=True)

    claims = [
        Claim("angles", f"Намерете ъглите на ${T} ABC$.",
              f"∠BAC = ∠ABC = {al}°, ∠ACB = {ga}°",
              f"${A} BLC$ е външен за ${T} ABL$: $\\alpha + \\frac{{\\alpha}}{{2}} = {blc}^\\circ$ — 1 т.; "
              f"$\\alpha = {al}^\\circ$ — 1 т.; ${A} ACB = {ga}^\\circ$ — 1 т.", 3, 1,
              lambda p: near(ang(p["A"], p["B"], p["C"]), al)),
        Claim("rhombus", "Докажете, че $PBQL$ е ромб.",
              "PQ е симетрала на BL: PB = PL, QB = QL; BL е ъглополовяща, значи PB = BQ",
              "$PB = PL$ и $QB = QL$ ($PQ$ е симетрала на $BL$) — 2 т.; $PB = BQ$ "
              "($BM$ е ъглополовяща и височина в $\\triangle PBQ$) — 1 т.; извод — 1 т.", 4, 2,
              lambda p: max(dist(p["P"], p["B"]), dist(p["B"], p["Q"]), dist(p["Q"], p["L"]), dist(p["L"], p["P"]))
              - min(dist(p["P"], p["B"]), dist(p["B"], p["Q"]), dist(p["Q"], p["L"]), dist(p["L"], p["P"]))
              < 1e-3 * dist(p["P"], p["B"])),
        Claim("plb", f"Намерете мярката на ${A} PLB$.", f"{fmt(Fraction(al, 2))}°",
              f"$PL \\parallel BC$ (срещуположни страни на ромба) — 1 т.; ${A} PLB = {A} LBC = "
              f"{fmt(Fraction(al, 2))}^\\circ$ — 1 т.", 2, 3,
              lambda p: near(ang(p["L"], p["P"], p["B"]), al / 2), requires=("rhombus",)),
        Claim("al_bq", "Докажете, че $AL = BQ$.",
              "QL ∥ AB, ∠CLQ = ∠CQL, значи CL = CQ и AL = AC − CL = BC − CQ = BQ",
              f"$QL \\parallel AB$ и ${T} CLQ$ е равнобедрен — 2 т.; извод — 1 т.", 3, 3,
              lambda p: close(dist(p["A"], p["L"]), dist(p["B"], p["Q"])), requires=("rhombus",)),
        Claim("clq", f"Докажете, че ${T} CLQ$ е равнобедрен.",
              "QL ∥ AB, значи ∠CLQ = ∠CAB = ∠CBA = ∠CQL",
              f"$QL \\parallel AB$ — 1 т.; ${A} CLQ = {A} CAB$ и ${A} CQL = {A} CBA$ — 1 т.; "
              "извод — 1 т.", 3, 3,
              lambda p: close(dist(p["C"], p["L"]), dist(p["C"], p["Q"])), requires=("rhombus",)),
        Claim("ap_pq", "Докажете, че $AP > PQ$.",
              f"AL = PL, ∠APL = {al}° < ∠ALP; в △APL AP лежи срещу по-големия ъгъл; PQ < AP",
              "сравняване на страни срещу различни ъгли — 2 т.; извод — 1 т.", 3, 4,
              lambda p: dist(p["A"], p["P"]) > dist(p["P"], p["Q"])),
    ]
    stem = (f"В ${T} ABC$ $AC = BC$, $BL$ $(L \\in AC)$ е ъглополовящата на ${A} ABC$ и "
            f"${A} BLC = {blc}^\\circ$. През средата на $BL$ е построена права $PQ$ така, че "
            "$PQ \\perp BL$ $(P \\in AB,\\ Q \\in BC)$.")
    return Setup(f"iso_rhombus_{al}", stem, claims, figure, "rhombus", band="medium")


# ═══════════════════════════════════════════════════════════════════════════
# 2022 Q23 — right triangle, bisector, parallel, midpoint
# ═══════════════════════════════════════════════════════════════════════════

@config("rt_bisector", band="medium")
def rt_bisector(rng: random.Random) -> Setup:
    """△AML ≅ △BNL and the equilateral △NML hold only at ∠CAB = 60°, so the
    given length varies and the ratio stays as printed."""
    bn = rng.choice(range(4, 21, 2))
    cb = math.sqrt(3.0)
    cl = cb / 3
    maths = {"C": (0.0, 0.0), "A": (1.0, 0.0), "B": (0.0, cb), "L": (0.0, cl),
             "N": (1.0 - cl / cb, cl)}
    maths["M"] = mid(maths["B"], maths["N"])

    def figure(keys, r):
        f = place(maths, dots={"L", "N", "M"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("A", "L"), ("L", "N"), ("L", "M")])
        f.right_angle("C", "A", "B")
        f.right_angle("L", "N", "B")
        f.tick("N", "M"); f.tick("M", "B")
        return f.to_spec(aria="Правоъгълен триъгълник ABC, ъглополовяща AL, отсечка LN, "
                              "успоредна на AC, и среда M на BN", rng=r, upright=True)

    claims = [
        Claim("acute", f"Намерете градусните мерки на острите ъгли на ${T} ABC$.", "60° и 30°",
              "$3k = 90^\\circ$ — 1 т.; $k = 30^\\circ$ — 1 т.; $60^\\circ$ и $30^\\circ$ — 1 т.", 3, 1,
              lambda p: near(ang(p["A"], p["C"], p["B"]), 60)),
        Claim("al_bl", "Докажете, че $AL = BL$.",
              "∠LAB = ∠LBA = 30°, значи △ALB е равнобедрен",
              f"${A} LAB = {A} LBA = 30^\\circ$ — 1 т.; извод — 1 т.", 2, 2,
              lambda p: close(dist(p["A"], p["L"]), dist(p["B"], p["L"])), requires=("acute",)),
        Claim("aln", f"Определете вида на ${T} ALN$ според страните и според ъглите.",
              "равнобедрен (NA = NL) и тъпоъгълен (∠ANL = 120°)",
              f"${A} ALN = {A} CAL = 30^\\circ$ — 1 т.; $NA = NL$ — 1 т.; ${A} ANL = 120^\\circ$ — 1 т.",
              3, 2, lambda p: close(dist(p["N"], p["A"]), dist(p["N"], p["L"])), requires=("acute",)),
        Claim("lm_half", "Докажете, че $LM = \\dfrac{BN}{2}$.",
              "∠NLB = 90° (LN ∥ AC ⊥ CB), LM е медиана към хипотенузата на △NLB",
              f"${A} NLB = 90^\\circ$ — 1 т.; медиана към хипотенузата — 1 т.", 2, 2,
              lambda p: close(2 * dist(p["L"], p["M"]), dist(p["B"], p["N"]))),
        Claim("aml_bnl", f"Докажете, че ${T} AML \\cong {T} BNL$.",
              "△AML ≅ △BNL по III признак (AL = BL, LM = NL, AM = BN)",
              "$LM = NL = \\frac{BN}{2}$ — 1 т.; $AL = BL$ — 1 т.; $AM = BN$ и извод — 1 т.", 3, 3,
              lambda p: close(dist(p["A"], p["M"]), dist(p["B"], p["N"])), requires=("acute",)),
        Claim("cl_lb", "Намерете отношението $CL : LB$.", "1 : 2",
              f"${A} CAL = 30^\\circ$ — 1 т.; $CL = \\frac{{AL}}{{2}}$ — 1 т.; $AL = BL$ — 1 т.; "
              "$CL : LB = 1 : 2$ — 1 т.", 4, 4,
              lambda p: close(2 * dist(p["C"], p["L"]), dist(p["L"], p["B"])), requires=("acute",)),
        Claim("perimeter", f"Пресметнете периметъра на ${T} NML$, ако $BN = {bn}$ cm.",
              f"{fmt(Fraction(3 * bn, 2))} cm",
              f"$NM = MB = {fmt(Fraction(bn, 2))}$ cm — 1 т.; $LM = NL = {fmt(Fraction(bn, 2))}$ cm — 1 т.; "
              f"${T} NML$ е равностранен, $P = {fmt(Fraction(3 * bn, 2))}$ cm — 1 т.", 3, 4,
              lambda p: close(dist(p["N"], p["L"]) + dist(p["L"], p["M"]) + dist(p["M"], p["N"]),
                              1.5 * dist(p["B"], p["N"]))),
    ]
    stem = (f"Правоъгълният ${T} ABC$ е с хипотенуза $AB$, $AL$ $(L \\in BC)$ е ъглополовящата на "
            f"${A} CAB$ и ${A} CAB : {A} ABC = 2 : 1$. През точка $L$ е построена права, успоредна "
            "на $AC$, която пресича $AB$ в точка $N$, а точка $M$ е средата на $BN$.")
    return Setup(f"rt_bisector_{bn}", stem, claims, figure, "right triangle", band="medium")


# ═══════════════════════════════════════════════════════════════════════════
# 2021 Q23 — angles 4 : 3 : 5, two heights, the midpoint of BC
# ═══════════════════════════════════════════════════════════════════════════

@config("heights_midpoint", band="medium")
def heights_midpoint(rng: random.Random) -> Setup:
    """△MKD is equilateral only at ∠A = 60°, and the areas BC²/8, BC²/4 need
    {∠B, ∠C} = {45°, 75°}; so BC varies, and the ratio may mirror to 4 : 5 : 3."""
    bc = rng.choice(range(2, 17, 2))
    mirror = rng.random() < 0.4
    p_, q_, r_ = (4, 5, 3) if mirror else (4, 3, 5)
    be, ga = (75, 45) if mirror else (45, 75)
    s_bkc, s_bdc = (bc * bc / 4, bc * bc / 8) if mirror else (bc * bc / 8, bc * bc / 4)
    maths = triangle(60, be)
    A_, B_, C_ = maths["A"], maths["B"], maths["C"]
    maths.update({"D": foot(C_, A_, B_), "K": foot(B_, A_, C_), "M": mid(B_, C_)})

    def figure(keys, r):
        f = place(maths, dots={"D", "K", "M"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("C", "D"), ("B", "K")])
        f.segs([("M", "K"), ("M", "D"), ("K", "D")], dash=True)
        f.right_angle("D", "C", "B"); f.right_angle("K", "B", "C")
        f.tick("B", "M"); f.tick("M", "C")
        return f.to_spec(aria="Триъгълник ABC с височини CD и BK и среда M на BC",
                         rng=r, upright=True)

    claims = [
        Claim("angles", f"Намерете ъглите на ${T} ABC$.", f"∠A = 60°, ∠B = {be}°, ∠C = {ga}°",
              f"$({p_} + {q_} + {r_})x = 180^\\circ$ — 1 т.; $x = 15^\\circ$ — 1 т.; "
              f"$60^\\circ$, ${be}^\\circ$, ${ga}^\\circ$ — 1 т.", 3, 1,
              lambda p: near(ang(p["A"], p["B"], p["C"]), 60)),
        Claim("mk_md", "Докажете, че $MK = MD$.",
              "MK и MD са медиани към хипотенузата BC в правоъгълните △BKC и △BDC, значи MK = MD = BC/2",
              "$MK = \\frac{BC}{2}$ — 1 т.; $MD = \\frac{BC}{2}$ — 1 т.", 2, 2,
              lambda p: close(dist(p["M"], p["K"]), dist(p["M"], p["D"]))),
        Claim("kmd", f"Намерете мярката на ${A} KMD$.", "60°",
              f"${A} BMD = 180^\\circ - 2{A} B$ — 1 т.; ${A} CMK = 180^\\circ - 2{A} C$ — 1 т.; "
              f"${A} KMD = 60^\\circ$ — 1 т.", 3, 3,
              lambda p: near(ang(p["M"], p["K"], p["D"]), 60), requires=("angles",)),
        Claim("bmd", f"Докажете, че ${T} BMD$ е равнобедрен, и намерете ъглите му.",
              f"MB = MD = BC/2; ъгли {be}°, {be}°, {180 - 2 * be}°",
              f"$MB = MD = \\frac{{BC}}{{2}}$ — 1 т.; ${A} MDB = {A} MBD = {be}^\\circ$ — 1 т.; "
              f"${A} BMD = {180 - 2 * be}^\\circ$ — 1 т.", 3, 2,
              lambda p: close(dist(p["M"], p["B"]), dist(p["M"], p["D"]))
              and near(ang(p["M"], p["B"], p["D"]), 180 - 2 * be), requires=("angles",)),
        Claim("area_bkc", f"Ако $BC = {bc}$ cm, намерете лицето на ${T} BKC$.", f"{fmt(s_bkc)} cm²",
              f"височината от $K$ към $BC$ е ${fmt(Fraction(bc, 4) if not mirror else Fraction(bc, 2))}$ cm "
              f"— 1 т.; $S_{{BKC}} = {fmt(s_bkc)}$ cm$^2$ — 1 т.", 2, 3,
              lambda p: close(area(p["B"], p["K"], p["C"]) / dist(p["B"], p["C"]) ** 2, s_bkc / bc ** 2),
              requires=("angles",)),
        Claim("area_bdc", f"Ако $BC = {bc}$ cm, намерете лицето на ${T} BDC$.", f"{fmt(s_bdc)} cm²",
              f"височината от $D$ към $BC$ е ${fmt(Fraction(bc, 2) if not mirror else Fraction(bc, 4))}$ cm "
              f"— 1 т.; $S_{{BDC}} = {fmt(s_bdc)}$ cm$^2$ — 1 т.", 2, 3,
              lambda p: close(area(p["B"], p["D"], p["C"]) / dist(p["B"], p["C"]) ** 2, s_bdc / bc ** 2),
              requires=("angles",)),
        Claim("equilateral", f"Докажете, че ${T} MKD$ е равностранен.",
              "MK = MD = BC/2 и ∠KMD = 60°",
              f"$MK = MD = \\frac{{BC}}{{2}}$ — 2 т.; ${A} KMD = 60^\\circ$ — 2 т.; извод — 1 т.", 5, 3,
              lambda p: close(dist(p["M"], p["K"]), dist(p["K"], p["D"]))
              and close(dist(p["K"], p["D"]), dist(p["D"], p["M"])), requires=("angles",)),
        Claim("kd", f"Ако $BC = {bc}$ cm, намерете дължината на $KD$.", f"{fmt(Fraction(bc, 2))} cm",
              f"${T} MKD$ е равностранен — 2 т.; $KD = {fmt(Fraction(bc, 2))}$ cm — 1 т.", 3, 4,
              lambda p: close(2 * dist(p["K"], p["D"]), dist(p["B"], p["C"])), requires=("angles",)),
        Claim("perimeter", f"Ако $BC = {bc}$ cm, намерете обиколката на ${T} MKD$.",
              f"{fmt(Fraction(3 * bc, 2))} cm",
              f"$MK = MD = {fmt(Fraction(bc, 2))}$ cm — 2 т.; ${A} KMD = 60^\\circ$ и ${T} MKD$ е "
              f"равностранен — 2 т.; обиколка ${fmt(Fraction(3 * bc, 2))}$ cm — 1 т.", 5, 4,
              lambda p: close(dist(p["M"], p["K"]) + dist(p["K"], p["D"]) + dist(p["D"], p["M"]),
                              1.5 * dist(p["B"], p["C"])), requires=("angles",)),
        Claim("areas", f"Ако $BC = {bc}$ cm, намерете лицата на ${T} BKC$ и ${T} BDC$.",
              f"S(BKC) = {fmt(s_bkc)} cm², S(BDC) = {fmt(s_bdc)} cm²",
              f"височините към $BC$ са $\\frac{{BC}}{{2}}$ и $\\frac{{BC}}{{4}}$ — 2 т.; "
              f"$S_{{BKC}} = {fmt(s_bkc)}$ cm$^2$ — 1 т.; $S_{{BDC}} = {fmt(s_bdc)}$ cm$^2$ — 1 т.", 4, 4,
              lambda p: close(area(p["B"], p["K"], p["C"]) / dist(p["B"], p["C"]) ** 2, s_bkc / bc ** 2)
              and close(area(p["B"], p["D"], p["C"]) / dist(p["B"], p["C"]) ** 2, s_bdc / bc ** 2),
              requires=("angles",)),
    ]
    stem = (f"В ${T} ABC$ отношението на ъглите е ${A} CAB : {A} ABC : {A} BCA = {p_} : {q_} : {r_}$ "
            "и отсечките $CD$ $(D \\in AB)$ и $BK$ $(K \\in AC)$ са височини на триъгълника. "
            "Точка $M$ е средата на $BC$.")
    return Setup(f"heights_mid_{bc}_{int(mirror)}", stem, claims, figure, "heights", band="medium")


# ═══════════════════════════════════════════════════════════════════════════
# 2020 Q23 — angles 2 : 7 : 3, the perpendicular bisector of AC meets the bisector of A
# ═══════════════════════════════════════════════════════════════════════════

@config("bisector_perp")
def bisector_perp(rng: random.Random) -> Setup:
    """∠BCK = ∠MCK needs ∠C = 3∠A/2 and ∠MKC = ∠BKC needs ∠A = 30°: the angles
    are the item, so only the given length AM + MK varies."""
    s = rng.choice(range(4, 25))
    maths = triangle(30, 105)
    A_, B_, C_ = maths["A"], maths["B"], maths["C"]
    N = mid(A_, C_)
    perp = (N[0] - (C_[1] - A_[1]), N[1] + (C_[0] - A_[0]))
    bis = (math.cos(math.radians(15)), math.sin(math.radians(15)))
    maths.update({"N": N, "K": meet(N, perp, A_, B_), "M": meet(N, perp, A_, bis)})

    def figure(keys, r):
        f = place(maths, dots={"K", "M", "N"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("N", "K"), ("A", "M"), ("C", "M"), ("C", "K")])
        f.right_angle("N", "A", "M")
        f.tick("A", "N"); f.tick("N", "C")
        f.angle("A", "B", "M", arcs=1, radius=36); f.angle("A", "M", "C", arcs=1, radius=44)
        return f.to_spec(aria="Триъгълник ABC със симетрала на AC, пресичаща ъглополовящата "
                              "на ъгъл A в M и страната AB в K", rng=r, upright=True)

    claims = [
        Claim("angles", f"Намерете ъглите на ${T} ABC$.", "∠A = 30°, ∠B = 105°, ∠C = 45°",
              "$2x + 7x + 3x = 180^\\circ$ — 1 т.; $x = 15^\\circ$ — 1 т.; $30^\\circ$, $105^\\circ$, "
              "$45^\\circ$ — 1 т.", 3, 1, lambda p: near(ang(p["A"], p["B"], p["C"]), 30)),
        Claim("amc", f"Докажете, че ${T} AMC$ е равнобедрен.",
              "M лежи на симетралата на AC, значи MA = MC",
              "$M$ лежи на симетралата на $AC$ — 1 т.; $MA = MC$ — 1 т.", 2, 1,
              lambda p: close(dist(p["M"], p["A"]), dist(p["M"], p["C"]))),
        Claim("bkc", f"Намерете мярката на ${A} BKC$.", "60°",
              f"$KA = KC$, ${A} KCA = 30^\\circ$ — 1 т.; ${A} BKC$ е външен за ${T} AKC$ — 1 т.; "
              f"${A} BKC = 60^\\circ$ — 1 т.", 3, 2,
              lambda p: near(ang(p["K"], p["B"], p["C"]), 60), requires=("angles",)),
        Claim("ck_bis", f"Докажете, че $CK$ е ъглополовяща на ${A} MCB$.",
              "∠MCK = ∠ACK − ∠ACM = 30° − 15° = 15° и ∠KCB = 45° − 30° = 15°",
              f"${A} ACM = 15^\\circ$ и ${A} ACK = 30^\\circ$ — 1 т.; ${A} MCK = 15^\\circ$ — 1 т.; "
              f"${A} KCB = 15^\\circ$ — 1 т.", 3, 2,
              lambda p: near(ang(p["C"], p["M"], p["K"]), ang(p["C"], p["K"], p["B"])),
              requires=("angles",)),
        Claim("kmc_kbc", f"Докажете, че ${T} KMC \\cong {T} KBC$.",
              "△KMC ≅ △KBC по II признак (∠MCK = ∠BCK = 15°, ∠MKC = ∠BKC = 60°, CK обща)",
              f"${A} MCK = {A} BCK = 15^\\circ$ — 1 т.; ${A} MKC = {A} BKC = 60^\\circ$ — 2 т.; "
              "извод по II признак — 1 т.", 4, 3,
              lambda p: close(dist(p["C"], p["B"]), dist(p["C"], p["M"]))
              and close(dist(p["B"], p["K"]), dist(p["M"], p["K"])), requires=("angles",)),
        Claim("bcm", f"Докажете, че ${T} BCM$ е равнобедрен.",
              "CB = CM от еднаквостта на △KMC и △KBC",
              "$CB = CM$ от еднаквостта — 1 т.; извод — 1 т.", 2, 4,
              lambda p: close(dist(p["C"], p["B"]), dist(p["C"], p["M"])), requires=("kmc_kbc",)),
        Claim("perimeter", f"Пресметнете обиколката на четириъгълника $BCMK$, ако $AM + MK = {s}$ cm.",
              f"{2 * s} cm",
              "$CM = AM$, $CB = CM$, $BK = MK$ — 2 т.; "
              f"$P_{{BCMK}} = 2\\left(AM + MK\\right) = {2 * s}$ cm — 1 т.", 3, 5,
              lambda p: close(dist(p["B"], p["C"]) + dist(p["C"], p["M"]) + dist(p["M"], p["K"])
                              + dist(p["K"], p["B"]), 2 * (dist(p["A"], p["M"]) + dist(p["M"], p["K"]))),
              requires=("kmc_kbc",)),
    ]
    stem = (f"За ${T} ABC$ е дадено, че градусните мерки на ъглите му са в следното отношение: "
            f"${A} CAB : {A} CBA : {A} ACB = 2 : 7 : 3$. Симетралата на страната $AC$ пресича "
            f"последователно ъглополовящата на ${A} BAC$ и страната $AB$ в точките $M$ и $K$.")
    return Setup(f"bisector_perp_{s}", stem, claims, figure, "bisector")


# ═══════════════════════════════════════════════════════════════════════════
# 2019 Q25 — equilateral triangle, the one-third point, a perpendicular
# ═══════════════════════════════════════════════════════════════════════════

@config("equilateral_third", band="medium")
def equilateral_third(rng: random.Random) -> Setup:
    """AM = CK needs CM = BC/3 exactly (AK = BM only then), so the given area
    of △KCM is what varies: S(ACM) = 3s and S(ABC) = 9s."""
    s = rng.randint(1, 15)
    A_, B_, C_ = (0.0, 0.0), (1.0, 0.0), (0.5, math.sqrt(3) / 2)
    M = (C_[0] + (B_[0] - C_[0]) / 3, C_[1] + (B_[1] - C_[1]) / 3)
    maths = {"A": A_, "B": B_, "C": C_, "M": M, "K": foot(M, A_, B_)}

    def figure(keys, r):
        f = place(maths, dots={"M", "K"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("M", "K"), ("C", "K"), ("A", "M")])
        f.right_angle("K", "M", "B")
        f.tick("A", "B"); f.tick("B", "C"); f.tick("C", "A")
        return f.to_spec(aria="Равностранен триъгълник ABC, точка M на BC с CM = BC/3, "
                              "перпендикуляр MK към AB", rng=r, upright=True)

    claims = [
        Claim("bmk", f"Намерете мярката на ${A} BMK$.", "30°",
              f"${A} MBK = 60^\\circ$, ${A} BKM = 90^\\circ$ — 1 т.; ${A} BMK = 30^\\circ$ — 1 т.", 2, 1,
              lambda p: near(ang(p["M"], p["B"], p["K"]), 30)),
        Claim("kb", "Изразете отсечката $KB$ чрез страната $AB$.", "KB = AB/3",
              f"$BM = \\frac{{2}}{{3}}AB$ — 1 т.; ${A} BMK = 30^\\circ$ — 1 т.; "
              "$KB = \\frac{BM}{2} = \\frac{AB}{3}$ — 1 т.", 3, 1,
              lambda p: close(3 * dist(p["K"], p["B"]), dist(p["A"], p["B"]))),
        Claim("ak_bm", "Докажете, че $AK = BM$.", "AK = AB − KB = 2AB/3 = BM",
              "$KB = \\frac{AB}{3}$ — 1 т.; $AK = \\frac{2}{3}AB = BM$ — 1 т.", 2, 2,
              lambda p: close(dist(p["A"], p["K"]), dist(p["B"], p["M"]))),
        Claim("am_ck", "Докажете, че $AM = CK$.",
              "△ABM ≅ △CAK по I признак (AB = CA, BM = AK, ∠B = ∠A = 60°), значи AM = CK",
              f"$AK = \\frac{{2}}{{3}}AB = BM$ — 2 т.; ${T} ABM \\cong {T} CAK$ по I признак — 2 т.; "
              "$AM = CK$ — 1 т.", 5, 3,
              lambda p: close(dist(p["A"], p["M"]), dist(p["C"], p["K"]))),
        Claim("area_abc", f"Ако лицето на ${T} KCM$ е ${s}$ cm$^2$, намерете лицето на ${T} ABC$.",
              f"{9 * s} cm²",
              f"$S_{{KCM}} = \\frac{{1}}{{9}}S_{{ABC}}$ — 2 т.; $S_{{ABC}} = {9 * s}$ cm$^2$ — 1 т.", 3, 3,
              lambda p: close(area(p["A"], p["B"], p["C"]), 9 * area(p["K"], p["C"], p["M"]))),
        Claim("area_acm", f"Ако лицето на ${T} KCM$ е ${s}$ cm$^2$, намерете лицето на ${T} ACM$.",
              f"{3 * s} cm²",
              f"$S_{{KCM}} = \\frac{{1}}{{9}}S_{{ABC}}$ — 2 т.; $S_{{ACM}} = \\frac{{1}}{{3}}S_{{ABC}}$ — 1 т.; "
              f"$S_{{ACM}} = {3 * s}$ cm$^2$ — 1 т.", 4, 4,
              lambda p: close(area(p["A"], p["C"], p["M"]), 3 * area(p["K"], p["C"], p["M"]))),
    ]
    stem = (f"Точката $M$ лежи на страната $BC$ на равностранен ${T} ABC$ така, че "
            "$CM = \\dfrac{1}{3}BC$. Построена е отсечка $MK$, перпендикулярна на $AB$ $(K \\in AB)$.")
    return Setup(f"equilateral_third_{s}", stem, claims, figure, "equilateral", band="medium")


# ═══════════════════════════════════════════════════════════════════════════
# 2018 Q24 — a height, AH = CH = HM, and a point N with HN = MN + NB
# ═══════════════════════════════════════════════════════════════════════════

@config("heights_45_30")
def heights_45_30(rng: random.Random) -> Setup:
    """AH = CH makes ∠A = 45° and HM = CH = BC/2 makes ∠B = 30°: the angles
    are the item, and nothing numeric is given, so the claims are what vary.

    The ministry's solution builds P on HN with NP = MN; then HP = NB,
    △HPM ≅ △BNM, △NPM is equilateral and ∠NMB = 30°, so NM = NB and
    HN : BN = 2 : 1. The areas NMH : CMH come to 2 : 3."""
    maths = triangle(45, 30)
    A_, B_, C_ = maths["A"], maths["B"], maths["C"]
    H = foot(C_, A_, B_)
    M = mid(B_, C_)
    q = mid(M, B_)
    perp = (q[0] - (B_[1] - M[1]), q[1] + (B_[0] - M[0]))
    maths.update({"H": H, "M": M, "N": meet(q, perp, A_, B_)})

    def figure(keys, r):
        f = place(maths, dots={"H", "M", "N"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("C", "H"), ("H", "M"), ("M", "N")])
        f.right_angle("H", "C", "B")
        f.tick("A", "H"); f.tick("C", "H"); f.tick("H", "M")
        return f.to_spec(aria="Триъгълник ABC с височина CH, среда M на BC и точка N на HB",
                         rng=r, upright=True)

    claims = [
        Claim("angles", f"Намерете мерките на ${A} CAB$ и ${A} ABC$.", "∠CAB = 45°, ∠ABC = 30°",
              f"${T} ACH$ е равнобедрен правоъгълен, ${A} CAB = 45^\\circ$ — 1 т.; "
              f"$HM = \\frac{{BC}}{{2}}$ — 1 т.; $CH = \\frac{{BC}}{{2}}$, ${A} ABC = 30^\\circ$ — 1 т.", 3, 1,
              lambda p: near(ang(p["A"], p["B"], p["C"]), 45) and near(ang(p["B"], p["A"], p["C"]), 30)),
        Claim("chm", f"Докажете, че ${T} CHM$ е равностранен.",
              "HM = CM = BC/2 (медиана към хипотенузата) и CH = HM по условие",
              "$HM = CM = \\frac{BC}{2}$ — 1 т.; $CH = HM$ и извод — 1 т.", 2, 2,
              lambda p: close(dist(p["C"], p["H"]), dist(p["C"], p["M"]))
              and close(dist(p["C"], p["M"]), dist(p["H"], p["M"]))),
        Claim("acb", f"Намерете мерките на ${A} ACB$ и ${A} HCM$.", "∠ACB = 105°, ∠HCM = 60°",
              f"${A} ACB = 180^\\circ - 45^\\circ - 30^\\circ = 105^\\circ$ — 1 т.; "
              f"${A} HCM = 90^\\circ - 30^\\circ = 60^\\circ$ — 1 т.", 2, 2,
              lambda p: near(ang(p["C"], p["A"], p["B"]), 105) and near(ang(p["C"], p["H"], p["M"]), 60),
              requires=("angles",)),
        Claim("hmb", f"Докажете, че ${T} HMB$ е равнобедрен, и намерете ъглите му.",
              "HM = MB = BC/2; ъгли 30°, 30°, 120°",
              f"$HM = MB$ — 1 т.; ${A} MHB = {A} MBH = 30^\\circ$ — 1 т.; ${A} HMB = 120^\\circ$ — 1 т.",
              3, 2, lambda p: close(dist(p["H"], p["M"]), dist(p["M"], p["B"]))
              and near(ang(p["M"], p["H"], p["B"]), 120), requires=("angles",)),
        Claim("nm_nb", "Докажете, че $NM = NB$.",
              "P на HN с NP = MN: HP = NB, △HPM ≅ △BNM, △NPM е равностранен, ∠NMB = 30° = ∠NBM",
              f"построяване на $P$ с $NP = MN$ и $HP = NB$ — 1 т.; ${T} HPM \\cong {T} BNM$ — 1 т.; "
              f"${T} NPM$ е равностранен — 1 т.; ${A} NMB = 30^\\circ$ и $NM = NB$ — 1 т.", 4, 3,
              lambda p: close(dist(p["N"], p["M"]), dist(p["N"], p["B"]))
              and close(dist(p["H"], p["N"]), dist(p["M"], p["N"]) + dist(p["N"], p["B"])),
              requires=("angles",)),
        Claim("hn_bn", "Намерете отношението $HN : BN$.", "2 : 1",
              "$HN = MN + NB = 2NB$ — 1 т.; $HN : BN = 2 : 1$ — 1 т.", 2, 4,
              lambda p: close(dist(p["H"], p["N"]), 2 * dist(p["N"], p["B"])), requires=("nm_nb",)),
        Claim("hn_hb", "Намерете отношението $HN : HB$.", "2 : 3",
              "$HN = 2NB$ — 1 т.; $HN : HB = 2 : 3$ — 1 т.", 2, 4,
              lambda p: close(3 * dist(p["H"], p["N"]), 2 * dist(p["H"], p["B"])), requires=("nm_nb",)),
        Claim("areas", f"Намерете отношението на лицата $S_{{NMH}} : S_{{CMH}}$.", "2 : 3",
              f"височина $HT$ в ${T} CHM$ — 1 т.; $HT = \\frac{{HB}}{{2}}$ — 1 т.; изразяване на "
              f"$S_{{CHM}}$ — 1 т.; изразяване на $S_{{NHM}}$ — 1 т.; отношение $2 : 3$ — 1 т.", 5, 4,
              lambda p: close(3 * area(p["N"], p["M"], p["H"]), 2 * area(p["C"], p["M"], p["H"])),
              requires=("nm_nb",)),
    ]
    stem = (f"В ${T} ABC$ отсечката $CH$ е височина и точка $H$ е вътрешна за отсечката $AB$. "
            "Точката $M$ е средата на $BC$ и $AH = CH = HM$. Точката $N$ е от отсечката $HB$ и е "
            "такава, че $HN = MN + NB$.")
    return Setup("heights_45_30", stem, claims, figure, "heights 45 30")


# ═══════════════════════════════════════════════════════════════════════════
# 2017 Q24 — a height, a point P on BC at equal distances, a perpendicular to BC
# ═══════════════════════════════════════════════════════════════════════════

@config("altitude_point", band="medium")
def altitude_point(rng: random.Random) -> Setup:
    """CP = d and CM = 2d force ∠CMP = 30°, ∠B = 30°, BC = 3d and CH = 1,5d
    for every d. AB is drawn only where the triangle really is acute: the
    paper's own AB = 14 cm with d = 4 cm makes ∠C ≈ 91°."""
    d = rng.choice([2, 4, 6, 8])
    # BH = 3d·cos 30°; the triangle is acute while AH < CH·tan 30° ≈ 0,87d, and
    # H must stay clear of A to be drawn, so AH is kept within [0,2d; 0,8d]
    bh = 3 * d * math.cos(math.radians(30))
    ab = rng.choice([v for v in range(1, 60) if 0.2 * d <= v - bh <= 0.8 * d])
    c30 = math.cos(math.radians(30))
    B_, C_ = (0.0, 0.0), (3 * d * c30, 1.5 * d)
    H, A_ = (3 * d * c30, 0.0), (float(ab), 0.0)
    P = (C_[0] + (B_[0] - C_[0]) / 3, C_[1] + (B_[1] - C_[1]) / 3)
    perp = (P[0] - (C_[1] - B_[1]), P[1] + (C_[0] - B_[0]))
    maths = {"A": A_, "B": B_, "C": C_, "H": H, "P": P, "M": meet(P, perp, C_, H)}
    area_abc = Fraction(ab) * Fraction(3 * d, 2) / 2

    def figure(keys, r):
        f = place(maths, dots={"H", "P", "M"})
        f.path(["A", "B", "C"], close=True)
        f.segs([("C", "M"), ("P", "M")])
        f.right_angle("H", "C", "B"); f.right_angle("P", "M", "C")
        return f.to_spec(aria="Триъгълник ABC с височина CH, точка P на BC и перпендикуляр "
                              "през P, пресичащ правата CH в M", rng=r, upright=True)

    claims = [
        Claim("cmp", f"Намерете мярката на ${A} CMP$.", "30°",
              f"в правоъгълния ${T} CPM$ $CP = \\frac{{CM}}{{2}}$ — 2 т.; ${A} CMP = 30^\\circ$ — 1 т.",
              3, 1, lambda p: near(ang(p["M"], p["C"], p["P"]), 30)),
        Claim("cbh", f"Намерете мярката на ${A} CBH$.", "30°",
              f"${A} PCM = 60^\\circ$ — 1 т.; в ${T} BHC$ ${A} CBH = 30^\\circ$ — 2 т.", 3, 2,
              lambda p: near(ang(p["B"], p["C"], p["H"]), 30), requires=("cmp",)),
        Claim("pb", "Докажете, че $PB = 2CP$.",
              f"разстоянието от P до AB е {d} cm и е катет срещу 30°, значи PB = {2 * d} cm = 2CP",
              "разстоянието от $P$ до $AB$ е катет срещу ъгъл от $30^\\circ$ — 2 т.; $PB = 2CP$ — 1 т.",
              3, 3, lambda p: close(dist(p["P"], p["B"]), 2 * dist(p["C"], p["P"])), requires=("cbh",)),
        Claim("bc", "Намерете дължината на страната $BC$.", f"{3 * d} cm",
              f"$PB = 2 \\cdot {d} = {2 * d}$ cm — 2 т.; $BC = {3 * d}$ cm — 1 т.", 3, 3,
              lambda p: close(dist(p["B"], p["C"]), 3 * dist(p["C"], p["P"])), requires=("cbh",)),
        Claim("area", f"Намерете лицето на ${T} ABC$, ако $AB = {ab}$ cm.", f"{fmt(area_abc)} cm²",
              f"$BC = {3 * d}$ cm — 1 т.; $CH = \\frac{{BC}}{{2}} = {fmt(Fraction(3 * d, 2))}$ cm — 1 т.; "
              f"$S = {fmt(area_abc)}$ cm$^2$ — 1 т.", 3, 4,
              lambda p: close(dist(p["C"], p["H"]), 1.5 * dist(p["C"], p["P"])), requires=("cbh",)),
        Claim("ratio", "Определете отношението $CM : CH$.", "4 : 3",
              f"$CH = \\frac{{BC}}{{2}} = {fmt(Fraction(3 * d, 2))}$ cm — 2 т.; $CM : CH = 4 : 3$ — 1 т.",
              3, 4, lambda p: close(3 * dist(p["C"], p["M"]), 4 * dist(p["C"], p["H"])), requires=("cbh",)),
    ]
    stem = (f"Даден е остроъгълен ${T} ABC$ с височина $CH$ $(H \\in AB)$. Върху страната $BC$ е "
            f"взета точка $P$ такава, че разстоянията от нея до върха $C$ и до страната $AB$ са "
            f"равни на ${d}$ cm. През точка $P$ е построена права, перпендикулярна на $BC$, която "
            f"пресича правата $CH$ в точка $M$ и $CM = {2 * d}$ cm.")
    return Setup(f"altitude_point_{d}_{ab}", stem, claims, figure, "altitude", band="medium")


# ═══════════════════════════════════════════════════════════════════════════
# 2016 Q24 — rectangle, the bisector of ∠ABD, a perpendicular to it
# ═══════════════════════════════════════════════════════════════════════════

@config("rect_diagonal_bisector")
def rect_diagonal_bisector(rng: random.Random) -> Setup:
    """With ∠DBC = β and γ = (90° − β)/2 the whole chain holds for every β:
    ∠MND = β + γ = 90° − γ = ∠DMN, so DM = DN, and both halves of ∠DLH are γ,
    so LM bisects it. β stops at 54°: past it the rectangle is so wide that
    K, M and H crowd into D and the labels collide (measured: 30°–54° always
    draw cleanly, 58° and above never do). The paper's β = 50° is one of 13."""
    be = rng.choice(range(30, 55, 2))
    ga = (90 - be) // 2
    h = rng.randint(3, 15)
    w = math.tan(math.radians(be))
    A_, B_, C_, D_ = (0.0, 0.0), (w, 0.0), (w, 1.0), (0.0, 1.0)
    L = ratio_point(A_, D_, w, math.hypot(w, 1.0))
    perp = (L[0] - (L[1] - B_[1]), L[1] + (L[0] - B_[0]))
    M = meet(L, perp, B_, D_)
    maths = {"A": A_, "B": B_, "C": C_, "D": D_, "L": L, "M": M, "N": meet(L, perp, D_, C_),
             "H": foot(L, B_, D_), "K": foot(M, A_, D_)}

    def figure(keys, r):
        f = place(maths, dots={"L", "M", "N", "H", "K"})
        f.path(["A", "B", "C", "D"], close=True)
        f.segs([("B", "D"), ("B", "L"), ("L", "N"), ("L", "H")])
        f.seg("M", "K", dash=True)
        f.right_angle("L", "B", "M"); f.right_angle("H", "L", "B")
        return f.to_spec(aria="Правоъгълник ABCD, ъглополовяща BL на ъгъл ABD, перпендикуляр към "
                              "BL през L и перпендикуляр LH към диагонала BD", rng=r, upright=True)

    claims = [
        Claim("abl", f"Намерете мярката на ${A} ABL$.", f"{ga}°",
              f"${A} ABD = 90^\\circ - {be}^\\circ = {90 - be}^\\circ$ — 1 т.; ${A} ABL = {ga}^\\circ$ — 1 т.",
              2, 1, lambda p: near(ang(p["B"], p["A"], p["L"]), ga)),
        Claim("bh_ab", "Докажете, че $BH = AB$.",
              "△ABL ≅ △HBL (обща хипотенуза BL, ∠ABL = ∠HBL), значи BH = AB",
              f"${A} ABL = {A} HBL$ и обща хипотенуза — 1 т.; $BH = AB$ — 1 т.", 2, 2,
              lambda p: close(dist(p["B"], p["H"]), dist(p["A"], p["B"]))),
        Claim("mnd", f"Намерете ъглите на ${T} MND$.",
              f"∠MDN = {90 - be}°, ∠DMN = ∠DNM = {90 - ga}°",
              f"${A} BDC = {90 - be}^\\circ$ — 1 т.; ${A} DMN = {A} BML = {90 - ga}^\\circ$ — 1 т.; "
              f"${A} MND = {90 - ga}^\\circ$ — 1 т.", 3, 2,
              lambda p: near(ang(p["D"], p["M"], p["N"]), 90 - be) and near(ang(p["M"], p["D"], p["N"]), 90 - ga)),
        Claim("lm_bis", f"Докажете, че $LM$ е ъглополовяща на ${A} DLH$.",
              f"∠MLH = 90° − ∠LMH = {ga}° и ∠DLN = 90° − ∠LND = {ga}°",
              f"${A} MLH = {ga}^\\circ$ — 1 т.; ${A} DLN = {ga}^\\circ$ — 1 т.; извод — 1 т.", 3, 3,
              lambda p: near(ang(p["L"], p["M"], p["H"]), ang(p["L"], p["D"], p["N"]))),
        Claim("dist", f"Намерете разстоянието от точката $M$ до правата $AD$, ако $MH = {h}$ cm.",
              f"{h} cm",
              f"$LM$ е ъглополовяща на ${A} DLH$ — 2 т.; $MK = MH = {h}$ cm — 1 т.", 3, 3,
              lambda p: close(dist(p["M"], p["K"]), dist(p["M"], p["H"]))),
        Claim("sum", "Докажете, че $BH + DM = AB + DN$.", "BH = AB и DM = DN (△MND е равнобедрен)",
              "$BH = AB$ — 1 т.; $DM = DN$ — 1 т.", 2, 3,
              lambda p: close(dist(p["B"], p["H"]) + dist(p["D"], p["M"]),
                              dist(p["A"], p["B"]) + dist(p["D"], p["N"])), requires=("mnd",)),
        Claim("ineq", "Докажете, че $BM < BH + DM$.",
              "BM = BH + HM, а HM = MK < DM (катет и хипотенуза в △DKM)",
              "$BM = BH + HM$ — 1 т.; $HM = MK < DM$ — 1 т.", 2, 4,
              lambda p: dist(p["B"], p["M"]) < dist(p["B"], p["H"]) + dist(p["D"], p["M"])
              and between(p["H"], p["B"], p["M"])),
        Claim("sum_ineq", "Докажете, че $BH + DM = AB + DN$ и $BM < BH + DM$.",
              "BH = AB, DM = DN; BM = BH + HM и HM = MK < DM",
              "$BM = BH + HM$ — 1 т.; $BH = AB$ — 1 т.; $BH + DM = AB + DN$ — 1 т.; "
              "$HM < DM$ — 1 т.", 4, 4,
              lambda p: close(dist(p["B"], p["H"]) + dist(p["D"], p["M"]),
                              dist(p["A"], p["B"]) + dist(p["D"], p["N"]))
              and dist(p["B"], p["M"]) < dist(p["B"], p["H"]) + dist(p["D"], p["M"])),
    ]
    stem = (f"В правоъгълника $ABCD$ ${A} DBC = {be}^\\circ$. Ъглополовящата на ${A} ABD$ пресича "
            "страната $AD$ в точка $L$. През точката $L$ е построена права, перпендикулярна на "
            "правата $BL$, която пресича диагонала $BD$ и страната $CD$ съответно в точките $M$ и "
            "$N$. От точката $L$ е спуснат перпендикуляр $LH$ $(H \\in BD)$ към диагонала $BD$.")
    return Setup(f"rect_diag_{be}_{h}", stem, claims, figure, "rectangle bisector")


# ═══════════════════════════════════════════════════════════════════════════
# 2015 Q23 — isosceles MNP, the bisector ML, a point K with ∠MNK = α, ∠PNK = 3α
# ═══════════════════════════════════════════════════════════════════════════

@config("iso_mnp")
def iso_mnp(rng: random.Random) -> Setup:
    """△NKL is isosceles only for the 1 : 3 split (∠NKL = (k + 3)α/2 = kα
    forces k = 3), and the congruence fixes α = 10°. α stays a letter, as in
    the paper; the claims vary. The figure is drawn at α = 10° when a claim
    about that case is on the paper, and at a nearby α otherwise."""
    other_alpha = rng.choice([8, 9, 11, 12, 13])

    def pts(keys) -> Pts:
        a = 10 if keys & {"alpha", "tkm"} else other_alpha
        M_, N_ = (0.0, 0.0), (1.0, 0.0)
        P_ = (0.5, 0.5 * math.tan(math.radians(4 * a)))
        ray = (math.cos(math.radians(2 * a)), math.sin(math.radians(2 * a)))
        from_n = (1.0 - math.cos(math.radians(a)), math.sin(math.radians(a)))
        L_ = meet(M_, ray, N_, P_)
        K_ = meet(M_, ray, N_, from_n)
        S_ = mid(N_, K_)
        perp = (S_[0] - (K_[1] - N_[1]), S_[1] + (K_[0] - N_[0]))
        return {"M": M_, "N": N_, "P": P_, "L": L_, "K": K_, "S": S_, "T": meet(S_, perp, M_, N_)}

    def figure(keys, r):
        f = place(pts(keys), dots={"L", "K", "T"}, hidden={"S"})
        f.path(["M", "N", "P"], close=True)
        f.segs([("M", "L"), ("N", "K"), ("T", "L")])
        f.right_angle("S", "N", "T")
        # no arc for α: at 8°–13° it is under the 14° legibility floor, and the
        # stem names both angles at N anyway
        f.tick("M", "P"); f.tick("N", "P")
        return f.to_spec(aria="Равнобедрен триъгълник MNP с ъглополовяща ML, точка K на нея и "
                              "симетрала на NK, пресичаща MN в T", rng=r, upright=True)

    a_of = lambda p: ang(p["N"], p["M"], p["K"])          # the drawn α
    claims = [
        Claim("base", f"Изразете чрез $\\alpha$ ъглите на ${T} MNP$.",
              "∠PMN = ∠PNM = 4α, ∠MPN = 180° − 8α",
              f"${A} PNM = \\alpha + 3\\alpha = 4\\alpha$ — 1 т.; ${A} MPN = 180^\\circ - 8\\alpha$ — 1 т.",
              2, 1, lambda p: near(ang(p["M"], p["P"], p["N"]), 4 * a_of(p))),
        Claim("mln", f"Изразете чрез $\\alpha$ мярката на ${A} MLN$.", "∠MLN = 180° − 6α",
              f"${A} NML = 2\\alpha$ — 1 т.; от ${T} MNL$ ${A} MLN = 180^\\circ - 6\\alpha$ — 1 т.", 2, 1,
              lambda p: near(ang(p["L"], p["M"], p["N"]), 180 - 6 * a_of(p))),
        Claim("nkl", f"Изразете чрез $\\alpha$ мярката на ${A} NKL$ и докажете, че ${T} NKL$ е "
                     "равнобедрен.",
              "∠NKL = 3α = ∠KNL, значи LK = LN",
              f"${A} NKL$ е външен за ${T} MNK$: $2\\alpha + \\alpha = 3\\alpha$ — 1 т.; "
              f"${A} KNL = 3\\alpha$ — 1 т.; $LK = LN$ — 1 т.", 3, 2,
              lambda p: near(ang(p["K"], p["N"], p["L"]), 3 * a_of(p))
              and close(dist(p["L"], p["K"]), dist(p["L"], p["N"]))),
        Claim("mkn", f"Изразете чрез $\\alpha$ мярката на ${A} MKN$.", "∠MKN = 180° − 3α",
              f"${A} KMN = 2\\alpha$ и ${A} KNM = \\alpha$ — 1 т.; ${A} MKN = 180^\\circ - 3\\alpha$ — 1 т.",
              2, 2, lambda p: near(ang(p["K"], p["M"], p["N"]), 180 - 3 * a_of(p))),
        Claim("tl_bis", f"Докажете, че $LT$ е ъглополовяща на ${A} KLN$.",
              "△NKL е равнобедрен с основа NK, а симетралата на основата е ъглополовяща на ъгъла при върха",
              f"$LT$ е симетрала на $NK$ — 1 т.; ${T} NKL$ е равнобедрен — 1 т.; извод — 1 т.", 3, 3,
              lambda p: near(ang(p["L"], p["K"], p["T"]), ang(p["L"], p["T"], p["N"])),
              requires=("nkl",)),
        Claim("l_perp", "Докажете, че симетралата на отсечката $NK$ минава през точка $L$.",
              "LK = LN, значи L е на еднакво разстояние от N и K",
              "$LK = LN$ — 1 т.; извод — 1 т.", 2, 3,
              lambda p: close(dist(p["L"], p["K"]), dist(p["L"], p["N"]))
              and parallel(p["S"], p["T"], p["S"], p["L"]), requires=("nkl",)),
        Claim("alpha", f"Намерете стойността на $\\alpha$, за която ${T} MTL \\cong {T} MPL$.", "α = 10°",
              f"обща страна $ML$ и ${A} TML = {A} PML$ — 1 т.; ${A} MLT = 90^\\circ - 3\\alpha$ — 1 т.; "
              f"${A} MLP = 6\\alpha$ — 1 т.; $\\alpha = 10^\\circ$ — 1 т.", 4, 4,
              lambda p: not near(a_of(p), 10) or (close(dist(p["M"], p["T"]), dist(p["M"], p["P"]))
                                                 and close(dist(p["L"], p["T"]), dist(p["L"], p["P"]))),
              requires=("nkl",)),
        Claim("tkm", f"Ако $\\alpha = 10^\\circ$, намерете мярката на ${A} TKM$.", "140°",
              f"${A} MKN = 180^\\circ - 3\\alpha = 150^\\circ$ — 1 т.; ${A} NKT = {A} TNK = 10^\\circ$ — 1 т.; "
              f"${A} TKM = 140^\\circ$ — 1 т.", 3, 5,
              lambda p: not near(a_of(p), 10) or near(ang(p["K"], p["T"], p["M"]), 140)),
    ]
    stem = (f"Даден е равнобедрен ${T} MNP$ $(MP = NP)$. Върху ъглополовящата $ML$ $(L \\in NP)$ "
            f"на ${A} NMP$ е избрана точка $K$ такава, че ${A} MNK = \\alpha$ и "
            f"${A} PNK = 3\\alpha$. Симетралата на отсечката $NK$ пресича страната $MN$ в точка $T$.")
    return Setup("iso_mnp", stem, claims, figure, "isosceles MNP")
