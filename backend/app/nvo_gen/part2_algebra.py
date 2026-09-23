"""Part 2 extended algebra — five shapes, each a real paper's item generalised.

Every shape here is built on ``poly.Expr``: the tree that prints the stem is
the tree the key is computed from, so a stem and its answer cannot drift apart.
The families are chosen so the x² terms cancel by construction (a seventh
grader has no quadratic formula), and each draw is rejected unless its answers
are numbers a key would actually print.

    2026 Q22  cube_expansion_and_inequality
    2021 Q22  fractional_equation_and_inequality
    2023/2024 Q21  factor_then_roots_then_inequality
    2025 Q21  grouping_into_linear_factors
    2020 Q21  three_equations_equivalence
"""
from __future__ import annotations

import math
import random
from fractions import Fraction

from app.nvo_gen.part2_bank import Part2Item, part2
from app.nvo_gen.poly import (
    Expr,
    Poly,
    frac,
    interval_tex_named,
    leaf,
    lin,
    linear_root,
    num_plain,
    num_tex,
    satisfies,
    solve_linear_inequality,
    var,
)
from app.nvo_gen.registry import Retry

F = Fraction

REL_TEX = {"<": "<", ">": ">", r"\le": r"\le", r"\ge": r"\ge"}
REL_PLAIN = {"<": "<", ">": ">", r"\le": "≤", r"\ge": "≥"}
_ATTEMPTS = 400


def _nice_bound(v: Fraction, *, max_den: int = 6, cap: int = 12) -> bool:
    return v.denominator <= max_den and abs(v) <= cap and v.numerator != 0


def _decimal_root(v: Fraction) -> bool:
    """A root the key can print as an integer or a short decimal (2,5; -1,25)."""
    return 100 % v.denominator == 0 and abs(v) <= 20


# ─── inequalities and equations whose x² cancels ────────────────────────────
# Each family is one the corpus prints. The student has to expand both sides
# and watch the squares go — which is the skill being tested.

def _family_pair(rng: random.Random, name: str = "x",
                 families: tuple[int, ...] = (0, 1, 2, 3, 4)) -> tuple[Expr, Expr, int]:
    x = var(name)
    fam = rng.choice(families)
    if fam == 0:
        # 2024 Q21: (x + a)(b - x) - (x - c)/p  ?  q/r (x - s) - (x - t)²
        a, b, c = rng.randint(1, 5), rng.randint(1, 5), rng.randint(1, 5)
        p = rng.choice([2, 3, 6])
        q, r = rng.choice([(3, 2), (1, 2), (2, 3), (5, 2), (1, 3)])
        s, t = rng.randint(1, 4), rng.randint(2, 5)
        lhs = (x + a) * lin(-1, b, name) - frac(x - c, p)
        rhs = F(q, r) * (x - s) - (x - t) ** 2
    elif fam == 1:
        # (x - a)²/n - (x + b)(x - c)/n  ?  (x - d)/m
        a, b, c, d = (rng.randint(1, 6) for _ in range(4))
        n, m = rng.choice([2, 3, 4, 6]), rng.choice([2, 3, 4, 6])
        if n == m:
            raise Retry("same denominators make the item a one-liner")
        lhs = frac((x - a) ** 2, n) - frac((x + b) * (x - c), n)
        rhs = frac(x - d, m)
    elif fam == 2:
        # 2023 Q21: (kx - a)²/k - kx² - e  ?  f/k
        k = rng.choice([2, 3, 4])
        a = rng.randint(1, 5)
        e, f_ = rng.randint(1, 9), rng.randint(1, 5)
        if math.gcd(a, k) != 1:
            raise Retry("keep the square's constant coprime to k")
        lhs = frac(lin(k, -a, name) ** 2, k) - k * x ** 2 - e
        rhs = frac(lin(0, f_, name), k)
    elif fam == 3:
        # 2x(x - a) - (x + b)² - (x - c)(x + d)  ?  e
        a, b, c, d = (rng.randint(1, 6) for _ in range(4))
        e = rng.randint(-10, 10)
        lhs = lin(2, 0, name) * (x - a) - (x + b) ** 2 - (x - c) * (x + d)
        rhs = lin(0, e, name) if e else lin(0, 0, name)
        if e == 0:
            raise Retry("a zero right-hand side prints as a bare 0")
    else:
        # 2021 Q22: (αx + β)(γx - δ)  ?  (x + u)³ - (x - u)³, αγ = 6u
        u = rng.choice([1, 1, 2])
        alpha, gamma = rng.choice([(2, 3 * u), (3, 2 * u), (6 * u, 1), (u, 6)])
        beta, delta = rng.randint(1, 5), rng.randint(1, 5)
        lhs = lin(alpha, beta, name) * lin(gamma, -delta, name)
        rhs = (x + u) ** 3 - (x - u) ** 3
    diff = lhs.poly() - rhs.poly()
    if diff.degree != 1:
        raise Retry("family did not reduce to a linear relation")
    return lhs, rhs, fam


def _inequality(rng: random.Random, name: str = "x", *, max_den: int = 6,
                families: tuple[int, ...] = (0, 1, 2, 3, 4)):
    for _ in range(_ATTEMPTS):
        try:
            lhs, rhs, _fam = _family_pair(rng, name, families)
        except Retry:
            continue
        rel = rng.choice(["<", ">", r"\le", r"\ge"])
        rel2, bound = solve_linear_inequality(lhs.poly(), rhs.poly(), rel)
        if _nice_bound(bound, max_den=max_den):
            return lhs, rhs, rel, rel2, bound
    raise Retry("no inequality with a printable bound")


def _equation(rng: random.Random, name: str = "x",
              families: tuple[int, ...] = (0, 1, 2, 3, 4)):
    for _ in range(_ATTEMPTS):
        try:
            lhs, rhs, fam = _family_pair(rng, name, families)
        except Retry:
            continue
        root = linear_root(lhs.poly() - rhs.poly())
        if root.denominator <= 2 and root != 0 and abs(root) <= 20:
            return lhs, rhs, root, fam
    raise Retry("no equation with a printable root")


def _ineq_tex(lhs: Expr, rel: str, rhs: Expr) -> str:
    return f"{lhs.tex()} {REL_TEX[rel]} {rhs.tex()}"


def _answer_rel(rel: str, bound: Fraction, name: str = "x") -> str:
    return f"{name} {REL_PLAIN[rel]} {num_plain(bound)}"


# ═══════════════════════════════════════════════════════════════════════════

@part2("open_algebra")
def cube_expansion_and_inequality(rng: random.Random) -> Part2Item:
    """2026 Q22: normal form of a cubic expression, an inequality, and which
    roots of an absolute-value equation satisfy it.

    The paper's own choice is M = (x + 3)³ − x(x + 1)² − 3(x² + 9), which is
    the k = 3, s = 1 member of the family below; its part Б writes the normal
    form back into the inequality, and part В hides |6x − 3| = 12 inside an
    expression that simplifies to it. Both tricks are kept.
    """
    x = var()
    for _ in range(_ATTEMPTS):
        k = rng.choice([2, 3, 4, 5])
        s = rng.randint(1, k - 1)
        sign = rng.choice([1, -1])
        if sign > 0:
            M = (x + k) ** 3 - x * (x + s) ** 2 - k * (x ** 2 + k * k)
        else:
            M = (x - k) ** 3 - x * (x - s) ** 2 + k * (x ** 2 + k * k)
        P = M.poly()
        a2, a1 = P.coeff(2), P.coeff(1)
        if P.coeff(0) != 0 or a2 == 0 or a1 == 0:
            continue

        # Б) P − c  rel  a2·x(x + t)
        t = rng.choice([v for v in range(-6, 10) if v])
        c = rng.randint(1, 24)
        lhs_b = leaf(P) - c
        rhs_b = lin(a2, 0) * (x + t)
        rel = rng.choice(["<", ">", r"\le", r"\ge"])
        rel2, bound = solve_linear_inequality(lhs_b.poly(), rhs_b.poly(), rel)
        if not _nice_bound(bound, cap=6):
            continue

        # В) |P − a2·x(x + h) − e| = f   reduces to   |g·x − e| = f
        g = rng.choice([v for v in range(-8, 9) if abs(v) >= 2])
        h = (a1 - g) / a2
        if h.denominator != 1 or h == 0:
            continue
        h = int(h)
        e, f_ = rng.randint(-15, 15), rng.randint(2, 20)
        roots = sorted({F(e + f_, g), F(e - f_, g)})
        if len(roots) != 2 or not all(_decimal_root(r) for r in roots):
            continue
        passing = [r for r in roots if satisfies(r, rel2, bound)]
        if len(passing) != 1:
            continue
        # subtract a2·x(x + h) — written as "+ |a2|x(…)" when a2 is negative
        inner = (leaf(P) - lin(a2, 0) * (x + h) if a2 > 0
                 else leaf(P) + lin(-a2, 0) * (x + h)) - e
        if inner.poly() != Poly.of(-e, g):
            continue                      # construction guard
        break
    else:
        raise Retry("no cube-expansion draw closed")

    good, bad = passing[0], next(r for r in roots if r not in passing)
    return Part2Item(
        code=f"alg_cube_{sign}_{k}_{s}_{t}_{c}_{rel2}_{g}_{e}_{f_}",
        topic="open_algebra",
        stem=f"Даден е изразът $M = {M.tex()}$.",
        parts=(
            "А) Представете $M$ в нормален вид.",
            f"Б) Решете неравенството ${_ineq_tex(lhs_b, rel, rhs_b)}$.",
            f"В) Кои от корените на уравнението $\\left|{inner.tex()}\\right| = {f_}$ "
            "са решения на неравенството от подточка Б)? Обосновете отговора си.",
        ),
        points=(5, 2, 5),
        answers=(
            f"M = {P.tex().replace('{,}', ',')}",
            _answer_rel(rel2, bound),
            f"x = {num_plain(good)} е решение; x = {num_plain(bad)} не е решение",
        ),
        marking=(
            f"А) Разкриване на скобите — 3 т.; привеждане в нормален вид "
            f"$M = {P.tex()}$ — 2 т.\n"
            f"Б) Свеждане до линейно неравенство и отговор "
            f"${interval_tex_named(rel2, bound, 'x')}$ — 2 т.\n"
            f"В) Опростяване до $\\left|{leaf(Poly.of(-e, g)).tex()}\\right| = {f_}$ — 1 т.; "
            f"корени $x_1 = {num_tex(roots[0])}$ и $x_2 = {num_tex(roots[1])}$ — 2 т. "
            f"(по 1 т.); извод, че ${num_tex(good)}$ е решение, а ${num_tex(bad)}$ не е, "
            f"с обосновка (сравняване с ${num_tex(bound)}$ или интервал) — 2 т."
        ),
    )


@part2("open_algebra", band="medium")
def fractional_equation_and_inequality(rng: random.Random) -> Part2Item:
    """2021 Q22: an equation with fractions, an inequality in y, and a check.

    The paper's equation is 5/6·(x − (1 − x)/3) + x(0,5x − 4)/9 = (x + 5)²/18,
    root 15, and the inequality (3y + 2)(2y − 3) < (y + 1)³ − (y − 1)³, answer
    y > −1,6. The first family below is that equation with its numbers freed;
    the x² terms cancel because 0,5/9 = 1/18 whatever the other numbers are.
    """
    x = var()
    for _ in range(_ATTEMPTS):
        if rng.random() < 0.55:
            p, q = rng.choice([(5, 6), (2, 3), (1, 2), (7, 6), (4, 3), (5, 3), (1, 6)])
            u, e, k = rng.randint(1, 5), rng.randint(1, 8), rng.randint(1, 7)
            lhs = F(p, q) * (x - frac(u - x, 3)) + frac(x * lin(F(1, 2), -e), 9)
            rhs = frac((x + k) ** 2, 18)
            d = lhs.poly() - rhs.poly()
            if d.degree != 1:
                continue
            root = linear_root(d)
            if not (root.denominator <= 2 and root != 0 and abs(root) <= 30):
                continue
            fam = -1
        else:
            try:
                # the families whose equation actually carries fractions
                lhs, rhs, root, fam = _equation(rng, families=(0, 1))
            except Retry:
                continue
        try:
            il, ir, rel, rel2, bound = _inequality(
                rng, "y", max_den=5, families=tuple(f for f in (0, 1, 2, 3, 4) if f != fam))
        except Retry:
            continue
        inside = satisfies(root, rel2, bound)
        break
    else:
        raise Retry("no fractional-equation draw closed")

    verdict = "е решение" if inside else "не е решение"
    return Part2Item(
        code=f"alg_frac_{lhs.tex()}={rhs.tex()}|{il.tex()}{rel}{ir.tex()}",
        topic="open_algebra",
        stem=(f"Дадени са уравнението ${lhs.tex()} = {rhs.tex()}$ и неравенството "
              f"${_ineq_tex(il, rel, ir)}$."),
        parts=(
            "А) Решете уравнението.",
            "Б) Решете неравенството и представете решенията му графично.",
            "В) Проверете дали коренът на уравнението е решение на неравенството. "
            "Обосновете отговора си.",
        ),
        points=(5, 4, 3),
        answers=(
            f"x = {num_plain(root)}",
            _answer_rel(rel2, bound, "y"),
            f"{num_plain(root)} {verdict} на неравенството",
        ),
        marking=(
            "А) Освобождаване от знаменателите и разкриване на скобите — 2 т.; "
            f"свеждане до линейно уравнение — 2 т.; корен $x = {num_tex(root)}$ — 1 т.\n"
            "Б) Разкриване на скобите от двете страни — 2 т.; "
            f"${interval_tex_named(rel2, bound, 'y')}$ — 1 т.; графично представяне — 1 т.\n"
            f"В) Сравняване на ${num_tex(root)}$ с ${num_tex(bound)}$ — 2 т.; "
            f"извод, че ${num_tex(root)}$ {verdict} — 1 т."
        ),
    )


@part2("open_algebra", band="medium")
def factor_then_roots_then_inequality(rng: random.Random) -> Part2Item:
    """2023 Q21 and 2024 Q21: factor a quadratic, solve an inequality in which
    the squares cancel, and say which of the roots satisfy it."""
    x = var()
    for _ in range(_ATTEMPTS):
        r1, r2 = rng.sample([v for v in range(-9, 10) if v], 2)
        if r1 + r2 == 0:
            continue                       # x² − a²: a different item
        P = (x - r1) * (x - r2)
        try:
            il, ir, rel, rel2, bound = _inequality(rng)
        except Retry:
            continue
        passing = [r for r in (r1, r2) if satisfies(F(r), rel2, bound)]
        if len(passing) == 1 or (passing and rng.random() < 0.15) or (not passing and rng.random() < 0.1):
            break
    else:
        raise Retry("no factoring draw closed")

    lo, hi = sorted((r1, r2))
    factored = (x - lo) * (x - hi)
    fails = [r for r in (lo, hi) if r not in passing]
    verdict = "; ".join([f"{r} е решение" for r in passing] +
                        [f"{r} не е решение" for r in fails])
    return Part2Item(
        code=f"alg_factor_{lo}_{hi}|{il.tex()}{rel}{ir.tex()}",
        topic="open_algebra",
        stem=f"Даден е многочленът $P = {P.poly().tex()}$.",
        parts=(
            "А) Разложете $P$ на множители и решете уравнението $P = 0$.",
            f"Б) Решете неравенството ${_ineq_tex(il, rel, ir)}$ и представете "
            "решението върху числовата ос.",
            "В) Определете кои от корените на уравнението от подточка А) са "
            "решения и на неравенството.",
        ),
        points=(4, 5, 3),
        answers=(
            f"P = {factored.tex().replace(chr(92) + 'left', '').replace(chr(92) + 'right', '')}; "
            f"x_1 = {lo}, x_2 = {hi}",
            _answer_rel(rel2, bound),
            verdict,
        ),
        marking=(
            f"А) Разлагане $P = {factored.tex()}$ — 2 т.; корени $x_1 = {lo}$ и "
            f"$x_2 = {hi}$ — 2 т.\n"
            "Б) Разкриване на скобите — 2 т.; привеждане към линейно неравенство — 1 т.; "
            f"${interval_tex_named(rel2, bound, 'x')}$ — 1 т.; изобразяване върху "
            "числовата ос — 1 т.\n"
            "В) Проверка на всеки от двата корена — по 1 т.; верен окончателен извод — 1 т."
        ),
    )


@part2("open_algebra")
def grouping_into_linear_factors(rng: random.Random) -> Part2Item:
    """2025 Q21: factor by grouping into first-degree factors, find the zeros,
    then the extreme integer solution of an inequality.

    The paper's M = x⁴ − 2x³ + 2x − 1 = (x − 1)³(x + 1) is the a = 1 quartic
    below: grouping x⁴ − 1 against −2x(x² − 1) is the step the marks are for.
    """
    x = var()
    fam = rng.randrange(3)
    if fam == 0:
        a = rng.choice([1, 1, 2])
        sgn = rng.choice([1, -1])
        # (x − sa)³(x + sa)
        M = (x - sgn * a) ** 3 * (x + sgn * a)
        factors = [lin(1, -sgn * a)] * 3 + [lin(1, sgn * a)]
        zeros = sorted({sgn * a, -sgn * a})
    else:
        a, b = rng.sample(range(1, 8), 2)
        if fam == 1:
            factors = [lin(1, -a), lin(1, -b), lin(1, b)]
        else:
            factors = [lin(1, a), lin(1, -b), lin(1, b)]
        M = factors[0] * factors[1] * factors[2]
        zeros = sorted({-f.poly().coeff(0) for f in factors})
        zeros = [int(z) for z in zeros]
    P = M.poly()

    il, ir, rel, rel2, bound = _inequality(rng, max_den=5)
    if rel2 in (">", r"\ge"):
        which = "най-малкото цяло"
        extreme = math.floor(bound) + 1 if rel2 == ">" else math.ceil(bound)
    else:
        which = "най-голямото цяло"
        extreme = math.ceil(bound) - 1 if rel2 == "<" else math.floor(bound)

    product_tex = "".join(rf"\left({f.tex()}\right)" for f in factors)
    product_plain = "".join(f"({f.tex()})" for f in factors)
    return Part2Item(
        code=f"alg_group_{fam}_{P.tex()}|{il.tex()}{rel}{ir.tex()}",
        topic="open_algebra",
        stem=f"Даден е многочленът $M = {P.tex()}$.",
        parts=(
            "А) Представете многочлена $M$ като произведение на множители от "
            "първа степен.",
            "Б) Намерете всички стойности на $x$, за които многочленът $M$ приема "
            "стойност $0$.",
            f"В) Намерете {which} решение на неравенството ${_ineq_tex(il, rel, ir)}$.",
        ),
        points=(4, 3, 5),
        answers=(
            f"M = {product_plain}",
            ", ".join(f"x = {z}" for z in zeros),
            f"{extreme}",
        ),
        marking=(
            f"А) Групиране — 2 т.; разлагане $M = {product_tex}$ — 2 т.\n"
            f"Б) Нулите: " + ", ".join(f"${z}$" for z in zeros) + " — 3 т.\n"
            f"В) Свеждане до линейно неравенство — 2 т.; "
            f"${interval_tex_named(rel2, bound, 'x')}$ — 2 т.; {which} решение "
            f"${extreme}$ — 1 т."
        ),
    )


@part2("open_algebra", band="medium")
def three_equations_equivalence(rng: random.Random) -> Part2Item:
    """2020 Q21: solve three equations — linear with fractions, absolute value,
    quadratic by factoring — and say which of them are equivalent."""
    x = var()
    lhs1, rhs1, r, _fam = _equation(rng)
    mode = rng.choice(["abs_quad", "abs_quad", "lin_quad", "none"])
    m = rng.randint(-5, 6)
    n = rng.randint(1, 6)
    abs_roots = sorted({m - n, m + n})
    k = rng.choice([1, 1, 2, 3])

    if mode == "abs_quad":
        quad_roots = abs_roots
    elif mode == "lin_quad":
        if r.denominator != 1:
            raise Retry("a double root needs an integer linear root")
        quad_roots = [int(r)]
    else:
        p, q = rng.sample([v for v in range(-8, 9)], 2)
        quad_roots = sorted({p, q})
        if set(quad_roots) == set(abs_roots) or quad_roots == [r]:
            raise Retry("meant to be the no-equivalence case")
    if len(quad_roots) == 1:
        Q = (x - quad_roots[0]) ** 2
    else:
        Q = (x - quad_roots[0]) * (x - quad_roots[1])
    inner = x - m
    abs_tex = (f"{k if k > 1 else ''}\\left|{inner.tex()}\\right| = {k * n}")
    if mode == "abs_quad":
        answer_d = "(2) и (3)"
    elif mode == "lin_quad":
        answer_d = "(1) и (3)"
    else:
        answer_d = "няма еквивалентни уравнения"

    fmt = lambda roots: " и ".join(num_plain(F(v)) for v in roots)
    return Part2Item(
        code=f"alg_equiv_{lhs1.tex()}={rhs1.tex()}|{m}_{n}_{k}|{Q.poly().tex()}",
        topic="open_algebra",
        stem=(f"Дадени са уравненията: $(1)\\ {lhs1.tex()} = {rhs1.tex()}$, "
              f"$(2)\\ {abs_tex}$ и $(3)\\ {Q.poly().tex()} = 0$."),
        parts=(
            "А) Решете уравнението $(1)$.",
            "Б) Решете уравнението $(2)$.",
            "В) Решете уравнението $(3)$.",
            "Г) Намерете кои от дадените уравнения са еквивалентни.",
        ),
        points=(3, 3, 3, 3),
        answers=(
            f"x = {num_plain(r)}",
            f"x = {fmt(abs_roots)}",
            f"x = {fmt(quad_roots)}",
            answer_d,
        ),
        marking=(
            f"А) Освобождаване от знаменателите и опростяване — 2 т.; $x = {num_tex(r)}$ — 1 т.\n"
            f"Б) $\\left|{inner.tex()}\\right| = {n}$ — 1 т.; корени "
            + ", ".join(f"${v}$" for v in abs_roots) + " — 2 т.\n"
            f"В) Разлагане ${Q.tex()} = 0$ — 2 т.; корени — 1 т.\n"
            f"Г) Сравняване на множествата от корени — 2 т.; отговор: {answer_d} — 1 т."
        ),
    )
