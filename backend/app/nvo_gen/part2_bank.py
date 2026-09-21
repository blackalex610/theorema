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

import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.registry import GeneratedItem
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


def part2(topic: str, *, band: str = "hard") -> Callable[[Builder], Builder]:
    def decorate(fn: Builder) -> Builder:
        _BANK[topic].append(fn)
        _BANDS[fn] = band
        return fn
    return decorate


def bank_for(topic: str) -> tuple[Builder, ...]:
    return tuple(_BANK.get(topic, ()))


def band_of(builder: Builder) -> str:
    return _BANDS.get(builder, "hard")


# ═══════════════════════════════════════════════════════════════════════════
# OPEN ALGEBRA — 12 points
# ═══════════════════════════════════════════════════════════════════════════

@part2("open_algebra")
def cube_expansion_and_inequality(rng: random.Random) -> Part2Item:
    """Normal form of a cubic expansion, then an inequality, then the overlap.

    The 2026 Q22 structure: expand, solve, and decide which roots of a separate
    equation satisfy the inequality. Part В is the one that separates a 5 from
    a 6 — it needs the student to hold two results at once.
    """
    k = rng.choice([2, 3, 4])
    # (x+k)³ − x(x−k)(x+k) − k(x²−k²)
    #   = (x³ + 3kx² + 3k²x + k³) − (x³ − k²x) − (kx² − k³)
    #   = 2k·x² + 4k²·x + 2k³
    a2, a1, a0 = 2 * k, 4 * k * k, 2 * k ** 3
    normal = f"{a2}x^2 + {a1}x + {a0}"

    # Part Б must reduce to a *linear* inequality, so the right-hand side has
    # to carry the same x² coefficient; the constant then fixes the bound.
    bound = rng.choice([0, 1, 2])
    rhs_const = a0 + a1 * bound
    # |x − 1| = 2 has roots 3 and −1. With a bound in {0,1,2} exactly one of
    # them satisfies the inequality, which is what makes part В worth asking.
    passing = [r for r in (3, -1) if r < bound]
    failing = [r for r in (3, -1) if r >= bound]

    return Part2Item(
        code=f"alg_cube_{k}_{bound}",
        topic="open_algebra",
        stem=(f"Даден е изразът $M = \\left(x + {k}\\right)^3 - x\\left(x - {k}\\right)"
              f"\\left(x + {k}\\right) - {k}\\left(x^2 - {k}^2\\right)$."),
        parts=(
            "А) Представете $M$ в нормален вид.",
            f"Б) Решете неравенството $M < {a2}x^2 + {rhs_const}$.",
            "В) Кои от корените на уравнението $\\left|x - 1\\right| = 2$ са решения "
            "на неравенството от подточка Б)? Обосновете отговора си.",
        ),
        points=(5, 4, 3),
        answers=(
            f"M = {normal}",
            f"x < {bound}",
            ("; ".join(f"{r} е решение" for r in passing) + "; " +
             "; ".join(f"{r} не е решение" for r in failing)),
        ),
        marking=(
            f"А) Разкриване на $\\left(x+{k}\\right)^3$ — 2 т.; на останалите произведения "
            f"— 2 т.; привеждане до $M = {normal}$ — 1 т.\n"
            f"Б) Съкращаване на ${a2}x^2$ от двете страни — 1 т.; свеждане до "
            f"${a1}x < {a1 * bound}$ — 2 т.; верен отговор $x < {bound}$ — 1 т.\n"
            f"В) Намиране на корените $x_1 = 3$ и $x_2 = -1$ — 1 т.; проверка на всеки "
            f"срещу границата ${bound}$ — 1 т.; изричен извод с обосновка — 1 т."
        ),
    )


@part2("open_algebra", band="medium")
def factor_then_roots_then_inequality(rng: random.Random) -> Part2Item:
    """Factor a quadratic, solve it, then test the roots against an inequality.

    The 2024 Q21 and 2023 Q21 structure.
    """
    r1 = rng.choice([2, 3, 4, 6])
    r2 = -rng.choice([5, 6, 7, 9])
    b = -(r1 + r2)
    c = r1 * r2
    b_txt = f"+ {b}x" if b > 0 else f"- {abs(b)}x"
    c_txt = f"+ {c}" if c > 0 else f"- {abs(c)}"
    return Part2Item(
        code=f"alg_factor_{r1}_{r2}",
        topic="open_algebra",
        stem=f"Даден е многочленът $P = x^2 {b_txt} {c_txt}$.",
        parts=(
            "А) Разложете $P$ на множители и решете уравнението $P = 0$.",
            "Б) Решете неравенството $\\left(x + 2\\right)\\left(2 - x\\right) - "
            "\\dfrac{x - 1}{3} < \\dfrac{3}{2}\\left(x - \\dfrac{1}{3}\\right) - "
            "\\left(x - 4\\right)^2$ и представете решението върху числовата ос.",
            "В) Определете кои от корените на уравнението от подточка А) са "
            "решения и на неравенството.",
        ),
        points=(4, 5, 3),
        answers=(
            f"P = (x - {r1})(x + {abs(r2)}); x_1 = {r1}, x_2 = {r2}",
            "Линейно неравенство след опростяване",
            "Проверка на всеки корен",
        ),
        marking=(
            f"А) Вярно разлагане $\\left(x - {r1}\\right)\\left(x + {abs(r2)}\\right)$ — 2 т.; "
            f"корени $x_1 = {r1}$ и $x_2 = {r2}$ — 2 т.\n"
            "Б) Разкриване на скобите — 2 т.; привеждане към линейно неравенство — 1 т.; "
            "верен интервал — 1 т.; изобразяване върху числовата ос — 1 т.\n"
            "В) Проверка на всеки от двата корена — по 1 т.; верен окончателен извод — 1 т."
        ),
    )


@part2("open_algebra", band="medium")
def system_from_expressions(rng: random.Random) -> Part2Item:
    """An equation with fractions plus a parametric check — the 2021 Q22 shape."""
    d = rng.choice([6, 9, 12])
    return Part2Item(
        code=f"alg_system_{d}",
        topic="open_algebra",
        stem=(f"Дадени са уравнението $\\dfrac{{5}}{{{d}}}\\left(x - \\dfrac{{1 - x}}{{3}}\\right) "
              f"+ \\dfrac{{x\\left(x - 4\\right)}}{{9}} = \\dfrac{{\\left(x + 5\\right)^2}}{{18}}$ "
              f"и неравенството $\\left(3y + 2\\right)\\left(2y - 3\\right) < "
              f"\\left(y + 1\\right)^3 - \\left(y - 1\\right)^3$."),
        parts=(
            "А) Решете уравнението.",
            "Б) Решете неравенството и представете решенията му графично.",
            "В) Ако $x$ е коренът на уравнението, докажете дали $x$ е решение "
            "на неравенството.",
        ),
        points=(5, 4, 3),
        answers=("Единствен корен", "Интервал", "Обоснован извод"),
        marking=(
            "А) Освобождаване от знаменателите — 2 т.; привеждане в нормален вид — 2 т.; "
            "верен корен — 1 т.\n"
            "Б) Разкриване на скобите от двете страни — 2 т.; верен интервал — 1 т.; "
            "графично представяне — 1 т.\n"
            "В) Заместване — 1 т.; сравнение с границата — 1 т.; изричен извод — 1 т."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# OPEN WORD PROBLEM — 11 points
# ═══════════════════════════════════════════════════════════════════════════

@part2("open_word_problem")
def gold_carat_mixture(rng: random.Random) -> Part2Item:
    """Purity fractions, alloy blending, and adding a diluent — the 2026 Q23 item.

    A genuinely good problem: three parts of rising difficulty over one idea
    (a carat is a twenty-fourth), and part В needs an equation rather than
    arithmetic.
    """
    # Every mass here is a multiple of 24/gcd so the pure-gold mass comes out
    # whole; part Б draws from blends that also land on a whole carat count,
    # because "13,5 карата" is not something a jeweller — or a key — would say.
    mass = rng.choice([96, 120, 144, 168])
    carats = rng.choice([14, 18])
    pure = Fraction(mass * carats, 24)
    (m1, c1), (m2, c2), blended = rng.choice([
        ((40, 9), (50, 18), 14),
        ((30, 12), (60, 18), 16),
        ((60, 9), (30, 18), 12),
        ((50, 12), (50, 18), 15),
    ])
    return Part2Item(
        code=f"word_gold_{mass}_{carats}_{m1}_{m2}",
        topic="open_word_problem",
        stem=("Мярката за чистота на златото се нарича карат и показва каква част от "
              "дадена златна сплав е чисто злато. Злато $1$ карат означава, че "
              "$\\dfrac{1}{24}$ от масата на сплавта е чисто злато. За изработване на "
              "бижута се използва най-често злато $9$, $14$ или $18$ карата."),
        parts=(
            f"А) Намерете колко грама чисто злато има в ${mass}$ g злато ${carats}$ карата.",
            f"Б) Златар смесил ${m1}$ g злато ${c1}$ карата и ${m2}$ g злато ${c2}$ карата. "
            f"Колко карата е получената сплав?",
            "В) Ани наследила златна плочка от $18$ карата с маса $10,5$ g. Тя поръчала "
            "от плочката да ѝ направят гривна, като добавят сребро така, че златото да "
            "стане $14$ карата. Колко грама ще тежи гривната? (Среброто не се измерва "
            "в карати.)",
        ),
        points=(2, 4, 5),
        answers=(f"{pure} g", f"{blended} карата", "13,5 g"),
        marking=(
            f"А) Записване, че златото е $\\frac{{{carats}}}{{24}}$ от сплавта — 1 т.; "
            f"отговор ${pure}$ g — 1 т.\n"
            f"Б) Съставяне на уравнение за общото количество чисто злато — 3 т.; "
            f"отговор ${blended}$ карата — 1 т.\n"
            "В) Означаване на среброто с $x$ — 1 т.; съставяне на "
            "$\\frac{18}{24} \\cdot 10{,}5 = \\frac{14}{24}\\left(10{,}5 + x\\right)$ — 2 т.; "
            "решаване — 1 т.; отговор $13{,}5$ g — 1 т."
        ),
    )


@part2("open_word_problem", band="medium")
def two_vehicles_meeting(rng: random.Random) -> Part2Item:
    """Two vehicles, one overtaking, plus a fuel-consumption tail — 2025 Q22."""
    v_bus = rng.choice([60, 65, 70])
    delta = rng.choice([15, 20, 25])
    litres_tenths = rng.choice([70, 78, 84])
    litres = f"{litres_tenths // 10}{{,}}{litres_tenths % 10}"
    return Part2Item(
        code=f"word_meet_{v_bus}_{delta}",
        topic="open_word_problem",
        stem=(f"В $9$ часà от град $A$ към град $B$ потегля автобус, който се движи с "
              f"постоянна скорост ${v_bus}$ km/h. След $20$ минути от град $B$ към град $A$ "
              f"с пълен резервоар потегля автомобил. Той се движи с постоянна скорост, "
              f"която е с ${delta}$ km/h по-голяма от скоростта на автобуса. В $11$ часà "
              f"превозните средства се срещат на бензиностанция по средата на пътя "
              f"между град $A$ и град $B$."),
        parts=(
            "А) Намерете скоростта на автомобила и разстоянието между двата града.",
            f"Б) На бензиностанцията шофьорът на автомобила допълва резервоара с "
            f"${litres}$ литра гориво. Намерете разхода на гориво на автомобила "
            f"за $100$ km.",
        ),
        points=(7, 4),
        answers=(f"{v_bus + delta} km/h", "Разход в литри на 100 km"),
        marking=(
            "А) Означаване на скоростта на автомобила — 1 т.; изразяване на времето на "
            "движение на всяко превозно средство — 2 т.; съставяне на уравнение от "
            "равните половини на пътя — 2 т.; решаване — 1 т.; отговор за разстоянието — 1 т.\n"
            "Б) Намиране на изминатия от автомобила път — 2 т.; съставяне на пропорция — 1 т.; "
            "верен отговор — 1 т."
        ),
    )


@part2("open_word_problem", band="medium")
def two_brigades_work(rng: random.Random) -> Part2Item:
    """Two teams with different head-counts and rates — the 2023 Q22 shape."""
    rate_a = rng.choice([2, 3])
    rate_b = rate_a + 1
    fewer = rng.choice([2, 3])
    rooms_total = rng.choice([180, 200, 240])
    return Part2Item(
        code=f"word_brigades_{rate_a}_{fewer}_{rooms_total}",
        topic="open_word_problem",
        stem=(f"Две строителни бригади боядисват комплекс, състоящ се от еднакви стаи. "
              f"В едната бригада всеки от работниците боядисва по ${rate_a}$ стаи дневно. "
              f"В другата бригада работниците са с ${fewer}$ по-малко от първата и всеки "
              f"от тях боядисва по ${rate_b}$ стаи дневно. За един ден работниците от "
              f"втората бригада боядисват с ${fewer}$ стаи повече от тези от първата."),
        parts=(
            "А) Намерете броя на работниците във всяка от бригадите.",
            f"Б) Двете бригади заедно трябва да боядисат ${rooms_total}$ стаи от комплекса. "
            f"Първата бригада започва работа един ден по-рано, а към втората бригада се "
            f"присъединяват още четирима работници. По колко дни е работила всяка "
            f"от бригадите?",
        ),
        points=(5, 6),
        answers=("Брой работници в двете бригади", "Брой дни за всяка бригада"),
        marking=(
            "А) Означаване с $x$ на работниците в първата бригада — 1 т.; съставяне на "
            "уравнение — 2 т.; решаване — 1 т.; отговор за двете бригади — 1 т.\n"
            "Б) Изразяване на дневната производителност след промяната — 2 т.; съставяне "
            "на уравнение за общия брой стаи — 2 т.; решаване — 1 т.; отговор за двете "
            "бригади — 1 т."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# OPEN GEOMETRY PROOF — 12 points
# ═══════════════════════════════════════════════════════════════════════════

def _rectangle_with_bisectors(rng: random.Random) -> dict:
    f = parallelogram(rect=True, rng=rng)
    A, B, C, D = (f.points[k] for k in "ABCD")
    O = f.put("O", midpoint(A, C), dot=True)
    f.path(["A", "B", "C", "D"], close=True)
    f.seg("A", "C")
    f.seg("B", "D")
    f.put("P", lerp(D, C, rng.uniform(0.54, 0.70)), dot=True)
    f.put("Q", lerp(A, B, rng.uniform(0.30, 0.46)), dot=True)
    f.seg("B", "P")
    f.seg("D", "Q")
    return f.to_spec(aria=("Правоъгълник ABCD с пресечна точка O на диагоналите и "
                           "ъглополовящи BP и DQ"), rng=rng)


@part2("open_geometry_proof")
def rectangle_bisectors_proof(rng: random.Random) -> Part2Item:
    """Congruence, an equal-length proof, an area identity, then a ratio.

    The 2026 Q24 structure — four parts, the last of which asks for a numeric
    answer on top of a proof.
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
        answers=("Доказателство по I признак", "AC = AR", "Доказателство за лицата", "60°"),
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


def isosceles_with_cevian(rng: random.Random) -> Figure:
    """Triangle ABC, bisector BL to AC, and the perpendicular PQ through its midpoint."""
    f = scalene_triangle(rng=rng)
    A, B, C = f.points["A"], f.points["B"], f.points["C"]
    L = f.put("L", lerp(A, C, rng.uniform(0.48, 0.62)), dot=True)
    f.path(["A", "B", "C"], close=True)
    f.seg("B", "L")
    f.put("P", lerp(A, B, rng.uniform(0.28, 0.40)), dot=True)
    f.put("Q", lerp(B, C, rng.uniform(0.40, 0.54)), dot=True)
    f.seg("P", "Q", dash=True)
    return f


@part2("open_geometry_proof", band="medium")
def isosceles_rhombus_proof(rng: random.Random) -> Part2Item:
    """A bisector, a perpendicular through its midpoint, and a rhombus — 2023 Q23."""
    blc = rng.choice([60, 66, 72])
    f = isosceles_with_cevian(rng)
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
        answers=("Трите ъгъла", "Доказателство за ромб", "AL = BQ", "AP > PQ"),
        marking=(
            "А) Използване на външния ъгъл при $L$ — 1 т.; съставяне на уравнение за "
            "ъглите — 1 т.; трите мерки — 1 т.\n"
            "Б) $PQ$ е симетрала на $BL$, значи $PB = PL$ и $QB = QL$ — 2 т.; извод за "
            "ромб — 1 т.\n"
            "В) Доказване на равенство на съответните триъгълници — 2 т.; извод — 1 т.\n"
            "Г) Сравняване на страни срещу различни ъгли — 2 т.; извод — 1 т."
        ),
        scene=f.to_spec(aria=("Триъгълник ABC с ъглополовяща BL и права PQ, "
                              "перпендикулярна на BL през средата ѝ"), rng=rng),
    )


@part2("open_geometry_proof")
def parallelogram_height_proof(rng: random.Random) -> Part2Item:
    """A height, a diagonal, and an area expressed through two segments — 2024 Q23."""
    angle = rng.choice([45, 60])
    f = parallelogram()
    A, B, C, D = (f.points[k] for k in "ABCD")
    f.path(["A", "B", "C", "D"], close=True)
    f.seg("A", "C")
    K = f.put("K", lerp(A, B, 0.52), dot=True)
    f.seg("D", "K")
    F = line_intersection(D, K, A, C)
    if F is not None:
        f.put("F", F, dot=True)
    f.right_angle("K", "D", "B")
    return Part2Item(
        code=f"geo_par_height_{angle}",
        topic="open_geometry_proof",
        stem=(f"В успоредника $ABCD$ $(AB > AD)$ $\\sphericalangle BAD = {angle}^\\circ$ и "
              f"височината $DK$ $(K \\in AB)$ към страната $AB$ пресича диагонала $AC$ в "
              f"точка $F$. През върха $D$ е построена права, перпендикулярна на $AC$, "
              f"която пресича диагонала $AC$ и страната $AB$ съответно в точките $H$ и $L$."),
        parts=(
            "А) Ако $\\sphericalangle DAC : \\sphericalangle BAC = 2 : 1$, намерете "
            "ъглите на $\\triangle ADL$ и определете отношението $BC : DH$.",
            "Б) Докажете, че $\\triangle AFK \\cong \\triangle DLK$.",
            "В) Ако $AF = m$ и $CH = n$, изразете лицата на $\\triangle DLC$ и на "
            "успоредника $ABCD$ чрез $m$ и $n$.",
        ),
        points=(4, 4, 4),
        answers=("Ъглите и отношението", "Доказателство", "Лицата чрез m и n"),
        marking=(
            "А) Разделяне на ъгъла в отношение $2 : 1$ — 1 т.; трите ъгъла на "
            "$\\triangle ADL$ — 2 т.; отношението $BC : DH$ — 1 т.\n"
            "Б) Два равни ъгъла — 2 т.; равна страна — 1 т.; извод по признак — 1 т.\n"
            "В) Лице на $\\triangle DLC$ — 2 т.; лице на успоредника — 2 т."
        ),
        scene=f.to_spec(aria=("Успоредник ABCD с височина DK към AB и диагонал AC, "
                              "пресичащи се в точка F"), rng=rng),
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
