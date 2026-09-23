"""Part 2 geometry proofs transcribed from 2019–2021, each with the reason it
varies only as far as it does.

A proof item generalises only where the argument does. Each of these was
re-derived before transcription, and in each case the construction pins the
angles — so what varies is the given length or area, which scales the answers
without touching the reasoning:

    2021 Q23  heights_and_midpoint      △MKD is equilateral only at ∠A = 60°;
                                         the areas need ∠B, ∠C ∈ {45°, 75°}
    2019 Q25  equilateral_third_point   AM = CK needs CM = BC/3 exactly
    2020 Q23  bisector_meets_perp_bisector  BCK = MCK needs ∠C = 3∠A/2, and
                                         MKC = BKC needs ∠A = 30°

Figures are solved from their constructions, never placed by eye.
"""
from __future__ import annotations

import math
import random

from app.nvo_gen.part2_bank import Part2Item, part2
from app.nvo_gen.scene import Figure


def _place(maths: dict[str, tuple[float, float]], *, dots=frozenset(), span=200.0) -> Figure:
    xs = [p[0] for p in maths.values()]
    ys = [p[1] for p in maths.values()]
    k = span / max(max(xs) - min(xs), max(ys) - min(ys))
    f = Figure()
    for name, (x, y) in maths.items():
        f.put(name, (x * k, -y * k), dot=name in dots)
    return f


def _foot(p, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)
    return (ax + t * dx, ay + t * dy)


def _meet(p1, p2, p3, p4):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p1, p2, p3, p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    a, b = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


def _triangle(alpha: float, beta: float) -> dict[str, tuple[float, float]]:
    """A at the origin, AB along the x axis, angles α at A and β at B."""
    gamma = 180 - alpha - beta
    b = math.sin(math.radians(beta))                  # AC
    c = math.sin(math.radians(gamma))                 # AB
    ca = math.radians(alpha)
    return {"A": (0.0, 0.0), "B": (c, 0.0), "C": (b * math.cos(ca), b * math.sin(ca))}


# ─── 2021 Q23 ────────────────────────────────────────────────────────────────

@part2("open_geometry_proof", band="medium")
def heights_and_midpoint(rng: random.Random) -> Part2Item:
    """Angles 4 : 3 : 5, heights CD and BK, M the midpoint of BC.

    MK = MD = BC/2 as medians to the hypotenuses of △BKC and △BDC, and
    ∠KMD = 180° − 2∠A = 60°, so △MKD is equilateral with perimeter 3·BC/2.
    The areas come from the height to BC: in △BDC (∠B = 45°) it is BC/2, in
    △BKC (∠C = 75°, so ∠KMC = 30°) it is BC/4 — the 30° leg, which is the
    7th-grade way to an area that looks like it needs a sine.
    """
    bc = rng.choice(range(2, 17, 2))
    mirror = rng.random() < 0.4                      # 4 : 5 : 3 — B and C swap
    p, q, r = (4, 5, 3) if mirror else (4, 3, 5)
    beta, gamma = (75, 45) if mirror else (45, 75)
    s_small, s_big = bc * bc / 8, bc * bc / 4
    s_bkc, s_bdc = (s_big, s_small) if mirror else (s_small, s_big)
    fmt = lambda v: f"{v:g}".replace(".", ",")

    pts = _triangle(60, beta)
    A, B, C = pts["A"], pts["B"], pts["C"]
    pts["D"] = _foot(C, A, B)
    pts["K"] = _foot(B, A, C)
    pts["M"] = ((B[0] + C[0]) / 2, (B[1] + C[1]) / 2)
    f = _place(pts, dots={"D", "K", "M"})
    f.path(["A", "B", "C"], close=True)
    f.segs([("C", "D"), ("B", "K")])
    f.segs([("M", "K"), ("M", "D"), ("K", "D")], dash=True)
    f.right_angle("D", "C", "B")
    f.right_angle("K", "B", "C")
    f.tick("B", "M")
    f.tick("M", "C")
    scene = f.to_spec(aria=("Триъгълник ABC с височини CD и BK и среда M на страната BC, "
                            "свързана с петите на височините"), rng=rng, upright=True)

    return Part2Item(
        code=f"geo_heights_mid_{bc}_{int(mirror)}",
        topic="open_geometry_proof",
        stem=(f"В $\\triangle ABC$ отношението на ъглите е $\\sphericalangle CAB : "
              f"\\sphericalangle ABC : \\sphericalangle BCA = {p} : {q} : {r}$ и отсечките "
              f"$CD$ $(D \\in AB)$ и $BK$ $(K \\in AC)$ са височини на триъгълника. Ако точка "
              f"$M$ е средата на $BC$ и $BC = {bc}$ cm, намерете:"),
        parts=(
            "А) ъглите на $\\triangle ABC$;",
            "Б) обиколката на $\\triangle MKD$;",
            "В) лицата на $\\triangle BKC$ и $\\triangle BDC$.",
        ),
        points=(3, 5, 4),
        answers=(
            f"∠A = 60°, ∠B = {beta}°, ∠C = {gamma}°",
            f"{fmt(3 * bc / 2)} cm",
            f"S(BKC) = {fmt(s_bkc)} cm², S(BDC) = {fmt(s_bdc)} cm²",
        ),
        marking=(
            f"А) $({p} + {q} + {r})x = 180^\\circ$, $x = 15^\\circ$ — 2 т.; трите ъгъла "
            f"$60^\\circ$, ${beta}^\\circ$, ${gamma}^\\circ$ — 1 т.\n"
            f"Б) $MK = MD = \\frac{{BC}}{{2}} = {fmt(bc / 2)}$ cm като медиани към хипотенузите "
            f"— 2 т.; $\\sphericalangle KMD = 60^\\circ$, значи $\\triangle MKD$ е равностранен "
            f"— 2 т.; обиколка ${fmt(3 * bc / 2)}$ cm — 1 т.\n"
            f"В) височината от $D$ към $BC$ е $\\frac{{BC}}{{2}}$ (при $45^\\circ$), а от $K$ е "
            f"$\\frac{{BC}}{{4}}$ (катет срещу ъгъл от $30^\\circ$ в $\\triangle$ с медианата) "
            f"— 2 т.; $S_{{BKC}} = {fmt(s_bkc)}$ cm$^2$ и $S_{{BDC}} = {fmt(s_bdc)}$ cm$^2$ — 2 т."
        ),
        scene=scene,
    )


# ─── 2019 Q25 ────────────────────────────────────────────────────────────────

@part2("open_geometry_proof", band="medium")
def equilateral_third_point(rng: random.Random) -> Part2Item:
    """Equilateral ABC, M on BC with CM = BC/3, MK ⊥ AB, and S(KCM) given.

    BM = 2a/3 and ∠B = 60°, so BK = BM/2 = a/3 — part А. Then AK = 2a/3 = BM
    and △ABM ≅ △CAK by SAS, so AM = CK — part Б, which holds only for the
    one-third point. △KCM has base a/3 and height (a/3)·sin 60°, a ninth of
    △ABC; △ACM is a third of it, so S(ACM) = 3·S(KCM) — part В.
    """
    s = rng.randint(1, 15)
    a = 1.0
    A, B, C = (0.0, 0.0), (a, 0.0), (a / 2, a * math.sqrt(3) / 2)
    M = (C[0] + (B[0] - C[0]) / 3, C[1] + (B[1] - C[1]) / 3)
    K = _foot(M, A, B)
    f = _place({"A": A, "B": B, "C": C, "M": M, "K": K}, dots={"M", "K"})
    f.path(["A", "B", "C"], close=True)
    f.segs([("M", "K"), ("C", "K"), ("A", "M")])
    f.right_angle("K", "M", "B")
    f.tick("A", "B"); f.tick("B", "C"); f.tick("C", "A")
    scene = f.to_spec(aria=("Равностранен триъгълник ABC, точка M на BC с CM равно на "
                            "една трета от BC, перпендикуляр MK към AB и отсечки CK и AM"),
                      rng=rng, upright=True)
    return Part2Item(
        code=f"geo_equilateral_third_{s}",
        topic="open_geometry_proof",
        stem=("Точката $M$ лежи на страната $BC$ на равностранен $\\triangle ABC$ така, че "
              "$CM = \\dfrac{1}{3}BC$. Построена е отсечка $MK$, перпендикулярна на $AB$ "
              f"$(K \\in AB)$. Лицето на $\\triangle KCM$ е ${s}$ cm$^2$."),
        parts=(
            "А) Изразете отсечката $KB$ чрез страната $AB$.",
            "Б) Докажете, че $AM = CK$.",
            "В) Намерете лицето на $\\triangle ACM$.",
        ),
        points=(3, 5, 4),
        answers=(
            "KB = AB/3",
            "△ABM ≅ △CAK по I признак (AB = CA, BM = AK = 2AB/3, ∠B = ∠A = 60°), значи AM = CK",
            f"{3 * s} cm²",
        ),
        marking=(
            "А) $BM = \\frac{2}{3}AB$ — 1 т.; в $\\triangle BKM$ $\\sphericalangle BMK = 30^\\circ$ "
            "— 1 т.; $KB = \\frac{BM}{2} = \\frac{AB}{3}$ — 1 т.\n"
            "Б) $AK = AB - KB = \\frac{2}{3}AB = BM$ — 2 т.; $\\triangle ABM \\cong \\triangle CAK$ "
            "по I признак — 2 т.; извод $AM = CK$ — 1 т.\n"
            f"В) $S_{{KCM}} = \\frac{{1}}{{9}}S_{{ABC}}$ — 2 т.; $S_{{ABC}} = {9 * s}$ cm$^2$ — 1 т.; "
            f"$S_{{ACM}} = \\frac{{1}}{{3}}S_{{ABC}} = {3 * s}$ cm$^2$ — 1 т."
        ),
        scene=scene,
    )


# ─── 2020 Q23 ────────────────────────────────────────────────────────────────

@part2("open_geometry_proof")
def bisector_meets_perp_bisector(rng: random.Random) -> Part2Item:
    """Angles 2 : 7 : 3; the perpendicular bisector of AC meets the bisector of
    ∠BAC at M and AB at K. △KMC ≅ △KBC, △BCM is isosceles, and the
    quadrilateral BCMK has perimeter 2(AM + MK).

    Both equalities are specific to ∠A = 30°, ∠C = 45° (see the module note),
    so the ratio stays as printed and the given length AM + MK varies.
    """
    s = rng.choice(range(4, 25))
    pts = _triangle(30, 105)
    A, B, C = pts["A"], pts["B"], pts["C"]
    N = ((A[0] + C[0]) / 2, (A[1] + C[1]) / 2)
    perp = (N[0] - (C[1] - A[1]), N[1] + (C[0] - A[0]))
    K = _meet(N, perp, A, B)
    bis = (math.cos(math.radians(15)), math.sin(math.radians(15)))
    M = _meet(N, perp, A, bis)
    pts.update({"N": N, "K": K, "M": M})
    f = _place(pts, dots={"K", "M", "N"})
    f.path(["A", "B", "C"], close=True)
    f.segs([("N", "K"), ("A", "M"), ("C", "M"), ("C", "K")])
    f.right_angle("N", "A", "M")
    f.tick("A", "N"); f.tick("N", "C")
    f.angle("A", "B", "M", arcs=1, radius=36)
    f.angle("A", "M", "C", arcs=1, radius=44)
    scene = f.to_spec(aria=("Триъгълник ABC със симетрала на AC, която пресича ъглополовящата "
                            "на ъгъл A в точка M и страната AB в точка K"), rng=rng, upright=True)
    return Part2Item(
        code=f"geo_bisector_perp_{s}",
        topic="open_geometry_proof",
        stem=("За $\\triangle ABC$ е дадено, че градусните мерки на ъглите му са в следното "
              "отношение: $\\sphericalangle CAB : \\sphericalangle CBA : \\sphericalangle ACB = "
              "2 : 7 : 3$. Симетралата на страната $AC$ пресича последователно ъглополовящата "
              "на $\\sphericalangle BAC$ и страната $AB$ в точките $M$ и $K$."),
        parts=(
            "А) Намерете ъглите на $\\triangle ABC$.",
            "Б) Докажете, че $\\triangle KMC \\cong \\triangle KBC$.",
            "В) Докажете, че $\\triangle BCM$ е равнобедрен.",
            f"Г) Пресметнете обиколката на четириъгълника $BCMK$, ако $AM + MK = {s}$ cm.",
        ),
        points=(3, 4, 2, 3),
        answers=(
            "∠A = 30°, ∠B = 105°, ∠C = 45°",
            "△KMC ≅ △KBC по II признак (∠MCK = ∠BCK = 15°, ∠MKC = ∠BKC = 60°, CK обща)",
            "CB = CM (от еднаквостта), значи △BCM е равнобедрен",
            f"{2 * s} cm",
        ),
        marking=(
            "А) $2x + 7x + 3x = 180^\\circ$, $x = 15^\\circ$ — 2 т.; $30^\\circ$, $105^\\circ$, "
            "$45^\\circ$ — 1 т.\n"
            "Б) $\\sphericalangle MCK = \\sphericalangle BCK = 15^\\circ$ — 1 т.; "
            "$\\sphericalangle MKC = \\sphericalangle BKC = 60^\\circ$ — 2 т.; извод по II признак — 1 т.\n"
            "В) $CB = CM$ от еднаквостта — 2 т.\n"
            f"Г) $CM = AM$, $CB = CM$, $BK = MK$ — 2 т.; $P_{{BCMK}} = 2\\left(AM + MK\\right) = "
            f"{2 * s}$ cm — 1 т."
        ),
        scene=scene,
    )
