"""Equations, inequalities, factoring and expression values.

Two things here are worth reading before adding a template.

*Interval items are a closed menu.* 2026 Q4, 2023 Q5, 2022 Q5 and 2021 Q5 all
present the same four options: one bound, and the four combinations of
direction and strictness. Nothing else is ever offered. `interval_variants`
produces exactly that menu, so these items are generated rather than authored.

*Short-answer items carry their own partial credit.* The 2026 key awards
"2 т., при един верен отговор" on the quadratic and "2 т., ако е написано 4x"
on the perimeter item. The points tuple and the solution text both have to
survive to the marking screen or the item is worth less than the real thing.
"""
from __future__ import annotations

import random
from fractions import Fraction

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.distractors import (
    bg_decimal,
    bg_number,
    factor_sign_variants,
    interval_variants,
    numeric_options,
    shuffle_options,
    sign_flip,
)
from app.nvo_gen.registry import GeneratedItem, Retry, template


def _coeff(n: int, var: str = "x") -> str:
    """Render a coefficient the way a printed paper does: `x`, not `1x`.

    Nothing catches this at grading time — `1x` is perfectly valid LaTeX and
    solves to the same root — but a paper that prints it does not look like an
    NVO paper, which is the whole point of the exercise.
    """
    if n == 1:
        return var
    if n == -1:
        return f"-{var}"
    return f"{n}{var}"


# ─── linear equations ────────────────────────────────────────────────────────

@template("linear_equation_simple", topics=["linear_equation"], kinds=["mc"], weight=1.3, band="easy")
def linear_equation_simple(rng: random.Random, slot: Slot) -> GeneratedItem:
    """ax + b = c — the 2026 Q2 shape, where the key is a unit fraction."""
    a = rng.choice(slot.profile.tier([2, 3, 4, 5], [4, 5, 6, 8],
                                     [12, 15, 18, 20, 24, 25],
                                     [14, 16, 21, 22, 26, 28, 33]))
    b = rng.randint(2, 9)
    # The real 2026 Q2 lands deliberately on a unit fraction. At the two
    # gentler levels the root comes out whole instead — same stem, same single
    # step, a number a student can check in their head.
    if slot.profile.code in ("easy", "medium"):
        c = b + a * rng.choice([1, 2])
    else:
        c = b + rng.choice([1, 2, 3])
    key = Fraction(c - b, a)

    wrong = [
        sign_flip(key),
        Fraction(c + b, a),
        Fraction(a, c - b),                 # reciprocal
        Fraction(c - b) * a,
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Коренът на уравнението ${a}x + {b} = {c}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"${a}x = {c - b}$, откъдето $x = {bg_number(key)}$",
        signature=f"lin_simple:{a}:{b}:{c}",
    )


@template("linear_equation_brackets", topics=["linear_equation"], kinds=["mc"], weight=1.1)
def linear_equation_brackets(rng: random.Random, slot: Slot) -> GeneratedItem:
    """a − (x − b) = −cx − d — the 2024 Q4 shape, with a bracket sign trap."""
    a = rng.randint(*slot.profile.tier((2, 5), (2, 7), (2, 9), (4, 14)))
    b = rng.randint(*slot.profile.tier((2, 5), (2, 7), (2, 9), (4, 14)))
    c = rng.choice(slot.profile.tier([2, 3], [2, 3], [2, 3, 4], [3, 4, 5, 6]))
    d = rng.randint(*slot.profile.tier((2, 5), (2, 7), (2, 9), (4, 14)))
    # a - x + b = -cx - d  →  (c-1)x = -d - a - b
    denom = c - 1
    numer = -d - a - b
    if denom == 0 or numer % denom:
        raise Retry("need an integer root")
    key = numer // denom

    wrong = [sign_flip(key), key + b, -(d + a - b) // denom if (d + a - b) % denom == 0 else key - 2, -d]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Коренът на уравнението ${a} - \\left(x - {b}\\right) = -{c}x - {d}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"${a} - x + {b} = -{c}x - {d}$, откъдето ${denom}x = {numer}$ и $x = {key}$",
        signature=f"lin_brackets:{a}:{b}:{c}:{d}",
    )


# ─── absolute value ──────────────────────────────────────────────────────────

@template("abs_equation_roots", topics=["absolute_value_equation"], kinds=["mc"], weight=1.3, band="easy")
def abs_equation_roots(rng: random.Random, slot: Slot) -> GeneratedItem:
    """|x − a| − b = −c, asking for both roots — the 2026 Q3 shape."""
    a = rng.randint(*slot.profile.tier((1, 5), (2, 7), (3, 9), (6, 20)))
    b = rng.randint(*slot.profile.tier((3, 7), (4, 9), (5, 12), (11, 26)))
    c = rng.randint(1, b - 1)
    rhs = b - c                              # |x - a| = b - c
    if rhs <= 0:
        raise Retry("need a positive right-hand side")
    r1, r2 = a + rhs, a - rhs
    if r1 == r2:
        raise Retry("want two distinct roots")

    def pair(u: int, v: int) -> str:
        return f"${u}$ и ${v}$"

    correct = pair(r1, r2)
    wrongs = [
        pair(-r1, -r2),                      # sign flip on both
        pair(a + b + c, a - b - c),          # added instead of subtracting
        pair(r1 + c, r2 - c),
    ]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Корените на уравнението $\\left|x - {a}\\right| - {b} = -{c}$ са:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"$\left|x - {a}\right| = {rhs}$, откъдето $x = {r1}$ или $x = {r2}$",
        signature=f"abs_roots:{a}:{b}:{c}",
    )


@template("abs_equation_sum_of_roots",
          topics=["absolute_value_equation"], kinds=["mc"], weight=1.1)
def abs_equation_sum_of_roots(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Sum of the roots of |x − a| − b = −c — the 2025 Q4 / 2024 Q6 shape.

    The sum is always 2a, which is the point: a student who solves both roots
    and adds gets it, and a student who only finds one root lands on a
    distractor that is exactly one root.
    """
    a = rng.randint(4, 9)
    b = rng.randint(5, 12)
    c = rng.randint(1, b - 1)
    rhs = b - c
    if rhs <= 0:
        raise Retry("need a positive right-hand side")
    key = 2 * a

    wrong = [a, a + rhs, a - rhs, sign_flip(key), rhs * 2]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Сборът от корените на уравнението $\\left|x - {a}\\right| - {b} = -{c}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"Корените са ${a + rhs}$ и ${a - rhs}$, а сборът им е ${key}$",
        signature=f"abs_sum:{a}:{b}:{c}",
    )


# ─── inequalities ────────────────────────────────────────────────────────────

@template("inequality_to_interval", topics=["inequality_interval"], kinds=["mc"], weight=1.4)
def inequality_to_interval(rng: random.Random, slot: Slot) -> GeneratedItem:
    """a − px ≤ b − qx, answer given as an interval — the 2026 Q4 shape."""
    p, q = rng.choice([(2, 1), (3, 1), (3, 2), (4, 1), (5, 2)])
    bound = rng.randint(2, 9)
    b = rng.randint(1, 12)
    a = b + (p - q) * bound                  # so the bound comes out whole
    strict = rng.random() < 0.5
    rel = "<" if strict else r"\le"

    # a - px (<|≤) b - qx  →  a - b (<|≤) (p-q)x  →  x (>|≥) bound
    options, letter = _interval_item(bound, direction="ge", closed=not strict, rng=rng)

    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Решението на неравенството "
              f"${a} - {_coeff(p)} {rel} {b} - {_coeff(q)}$ е интервалът:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"${a} - {b} {rel} {_coeff(p - q)}$, откъдето "
                  rf"$x \{'gt' if strict else 'ge'} {bound}$"),
        signature=f"ineq_interval:{a}:{p}:{b}:{q}:{strict}",
    )


def _interval_item(bound: int, *, direction: str, closed: bool,
                   rng: random.Random) -> tuple[list[str], str]:
    forms = interval_variants(str(bound), direction=direction, closed=closed)
    rendered = [f"${f}$" for f in forms]
    return shuffle_options(rendered[0], rendered[1:], rng=rng)


@template("inequality_integer_bound",
          topics=["inequality_integer_bound"], kinds=["mc"], weight=1.3)
def inequality_integer_bound(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Largest / smallest integer solution — the 2025 Q5 and 2024 Q5 shape."""
    want_largest = rng.random() < 0.5
    a = rng.randint(2, 8)
    b = rng.randint(1, 9)
    k = rng.choice([3, 4, 5, 6, 7])

    if want_largest:
        # a - x > k(x - b)  →  a + kb > (k+1)x  →  x < (a + kb)/(k+1)
        num, den = a + k * b, k + 1
        crit = Fraction(num, den)
        key = _largest_strictly_below(crit)
        stem = (f"Най-голямото цяло число, което е решение на неравенството "
                f"${a} - x > {k}\\left(x - {b}\\right)$, е:")
        neighbours = [key + 1, key - 1, key + 2, -key]
    else:
        # a x + b ≥ (a-1) x + k·b  →  x ≥ k·b - b
        key = k * b - b
        stem = (f"Най-малкото цяло число, което е решение на неравенството "
                f"${a}x + {b} \\ge {a - 1}x + {k * b}$, е:")
        neighbours = [key - 1, key + 1, key - 2, -key]
    if abs(key) > 40:
        raise Retry("keep the bound small enough to read")

    options, letter = numeric_options(key, neighbours, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Решението е $x < {bg_number(Fraction(a + k * b, k + 1))}$, "
                  rf"а най-голямото цяло число в него е ${key}$")
        if want_largest else
        (rf"Решението е $x \ge {key}$, а най-малкото цяло число в него е ${key}$"),
        signature=f"ineq_int:{want_largest}:{a}:{b}:{k}",
    )


def _largest_strictly_below(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    return floor - 1 if Fraction(floor) == value else floor


# ─── expanding and factoring ─────────────────────────────────────────────────

@template("factor_common_bracket", topics=["expand_or_factor"], kinds=["mc"], weight=1.3)
def factor_common_bracket(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(a − k)² − 2a(a − k) — the 2026 Q9 shape. Factor out (a − k)."""
    k = rng.choice([4, 5, 6, 7, 8, 9])
    var = rng.choice(["a", "b", "y"])
    # (v-k)^2 - 2v(v-k) = (v-k)(v-k-2v) = (v-k)(-v-k) = (k-v)(v+k)
    correct = rf"\left({k} - {var}\right)\left({var} + {k}\right)"
    wrongs = [
        rf"\left({var} - {k}\right)\left(1 - 2{var}\right)",
        rf"3\left({var} - {k}\right)\left({var} - 2\right)",
        rf"\left({k} + {var}\right)\left(2{var} - 1\right)",
    ]
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    expr = rf"\left({var} - {k}\right)^2 - 2{var}\left({var} - {k}\right)"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Изразът ${expr}$ е тъждествено равен на:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"$\left({var} - {k}\right)\left({var} - {k} - 2{var}\right) = "
                  rf"\left({var} - {k}\right)\left(-{var} - {k}\right) = {correct}$"),
        signature=f"fac_common:{k}:{var}",
    )


@template("factor_by_grouping", topics=["expand_or_factor"], kinds=["mc"], weight=1.1)
def factor_by_grouping(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x² − ax − xy + ay — the 2023 Q8 and 2022 Q3 shape."""
    a = rng.choice([3, 4, 5, 6, 8])
    expr = rf"x^2 - {a}x - xy + {a}y"
    forms = factor_sign_variants("x - y", f"x - {a}")
    options, letter = shuffle_options(f"${forms[0]}$", [f"${f}$" for f in forms[1:]], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Изразът ${expr}$ е тъждествено равен на израза:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"$x\left(x - {a}\right) - y\left(x - {a}\right) = \left(x - y\right)\left(x - {a}\right)$",
        signature=f"fac_group:{a}",
    )


@template("expand_square_of_binomial", topics=["expand_or_factor"], kinds=["mc"], weight=1.0, band="easy")
def expand_square_of_binomial(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(a − bx)² — the 2024 Q3 shape. Every option is a sign permutation."""
    a = rng.choice([2, 3, 4, 5])
    b = rng.choice([2, 3, 4, 5])
    a2, ab2, b2 = a * a, 2 * a * b, b * b
    correct = rf"{a2} - {ab2}x + {b2}x^2"
    wrongs = [
        rf"{a2} - {ab2}x - {b2}x^2",
        rf"{a2} + {ab2}x + {b2}x^2",
        rf"{a2} + {ab2}x - {b2}x^2",
    ]
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=rf"Изразът $\left({a} - {b}x\right)^2$ е тъждествено равен на израза:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"$\left({a} - {b}x\right)^2 = {a2} - {ab2}x + {b2}x^2$",
        signature=f"expand_sq:{a}:{b}",
    )


# ─── expression values ───────────────────────────────────────────────────────

@template("value_of_collapsing_expression",
          topics=["expression_at_value"], kinds=["mc", "short"], weight=1.3)
def value_of_collapsing_expression(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(x+k)² − x(x+k) = k(x+k) — the 2026 Q16 shape.

    Note the factor k: the common factor is (x+k) and the bracket that remains
    is (x + k − x) = k, so the value is k(x+k) and equals x+k only at k = 1,
    which is the case the official paper uses. Set at a year-like x so the
    answer is a recognisable number, as the real item does (x = 2025 → 2026).
    """
    k = rng.choice([1, 1, 2, 3])          # k = 1 is the canonical form
    x = rng.choice([2024, 2025, 2026, 1999, 2000])
    key = k * (x + k)
    expr = rf"\left(x + {k}\right)^2 - x\left(x + {k}\right)"
    collapsed = rf"x + {k}" if k == 1 else rf"{k}\left(x + {k}\right)"
    solution = (rf"$\left(x + {k}\right)\left(x + {k} - x\right) = {collapsed}$, "
                rf"което при $x = {x}$ дава ${key}$")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"Намерете числената стойност на израза ${expr}$ за $x = {x}$.",
            correct_answer=str(key), difficulty="medium",
            solution=solution, signature=f"val_collapse:{k}:{x}",
        )

    # x itself (dropped the +k), the unfactored value, the factor-free value,
    # and a neighbour — all of them things a student actually writes down.
    wrong = [x, x + 2 * k, k * x, key + k, key - k, 2 * key]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ при $x = {x}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"val_collapse:{k}:{x}",
    )


@template("value_of_square_difference",
          topics=["expression_at_value"], kinds=["mc", "short"], weight=1.1)
def value_of_square_difference(rng: random.Random, slot: Slot) -> GeneratedItem:
    """a² − b² at two near-equal decimals — the 2021 Q2 shape."""
    whole = rng.randint(6, 14)
    a = Fraction(whole * 10 + 5, 10)
    b = Fraction(whole * 10 - 5, 10)
    key = (a - b) * (a + b)
    expr = r"a^2 - b^2"
    given = f"$a = {bg_decimal(a, places=3)}$ и $b = {bg_decimal(b, places=3)}$"

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"Намерете числената стойност на израза ${expr}$ при {given}.",
            correct_answer=bg_decimal(key, places=3, math_mode=False),
            difficulty="medium",
            solution=rf"$(a-b)(a+b) = 1 \cdot {bg_decimal(a + b, places=3)} = {bg_decimal(key, places=3)}$",
            signature=f"val_sqdiff:{whole}",
        )

    wrong = [a + b, a - b, key + 1, key * 2]
    options, letter = numeric_options(key, wrong, rng=rng,
                                      fmt=lambda v: bg_decimal(v, places=3))
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ при {given} е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"$(a-b)(a+b) = 1 \cdot {bg_decimal(a + b, places=3)} = {bg_decimal(key, places=3)}$",
        signature=f"val_sqdiff:{whole}",
    )


# ─── short-answer algebra ────────────────────────────────────────────────────

@template("quadratic_by_factoring",
          topics=["quadratic_by_factoring"], kinds=["short"], weight=1.4)
def quadratic_by_factoring(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x² = kx — the 2026 Q15 shape. Partial credit for one root only.

    The trap is dividing both sides by x, which loses the root 0 — which is
    exactly why the key awards half marks for a single root.
    """
    k = rng.randint(4, 60)
    a = rng.choice([1, 1, 1, 2, 3, 4, 5])  # leading coefficient
    if a > 1 and k % a:
        raise Retry("the non-zero root must stay whole")
    root = k // a
    lhs = "x^2" if a == 1 else f"{a}x^2"
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=f"Намерете корените на уравнението ${lhs} = {k}x$.",
        correct_answer=f"0 и {root}", difficulty="medium",
        solution=(rf"${lhs} - {k}x = 0$, тоест "
                  rf"${'x' if a == 1 else f'{a}x'}\left(x - {root}\right) = 0$, "
                  rf"откъдето $x_1 = 0$ и $x_2 = {root}$. "
                  f"(Половината точки при само един верен корен — делението "
                  f"на $x$ губи нулевия.)"),
        signature=f"quad_factor:{a}:{k}",
    )


@template("isosceles_symbolic_perimeter",
          topics=["symbolic_perimeter"], kinds=["short"], weight=1.4, band="hard")
def isosceles_symbolic_perimeter(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Isosceles triangle, two sides in ratio p : q, perimeter in terms of x.

    The 2026 Q21 item (1 : 2 → 5x), and a genuinely sharp one: with the legs
    as the shorter side the triangle is degenerate, so the legs must be the
    longer one. Only ratios where that is the *only* possibility are drawn
    (q ≥ 2p), and only where the answer is a whole multiple of x, as the key
    prints it. The official key gives partial credit for the degenerate
    reading, which is recorded in the solution.
    """
    p, q = rng.choice([(1, k) for k in range(2, 8)] + [(2, k) for k in (5, 7, 9, 11)])
    key = 1 + 2 * q // p                       # legs (q/p)x, base x
    degenerate = 2 + q // p if p == 1 else None
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=(f"Две от страните на равнобедрен триъгълник се отнасят както "
              f"${p}:{q}$. Ако по-малката му страна е $x$ cm, "
              f"изразете и запишете чрез $x$ периметъра на триъгълника."),
        correct_answer=f"{key}x", difficulty="hard",
        solution=(f"Ако бедрата са по-късите страни, неравенството на триъгълника не е "
                  f"изпълнено. Следователно бедрата са "
                  f"${'' if q == p else bg_number(Fraction(q, p))}x$, основата е $x$ "
                  f"и периметърът е ${key}x$."
                  + (f" (Частични точки за ${degenerate}x$.)" if degenerate else "")),
        signature=f"iso_perimeter:{p}:{q}",
    )


@template("rectangle_symbolic_perimeter",
          topics=["symbolic_perimeter", "expression_from_words"],
          kinds=["short", "mc"], weight=1.0)
def rectangle_symbolic_perimeter(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Perimeter of a rectangle whose length is stated relative to its width:
    „с a cm по-голяма”, „k пъти по-голяма”, „с a cm по-малка от удвоената”."""
    form = rng.choice(["more", "times", "less_double"])
    a = rng.randint(1, 15)
    k = rng.randint(2, 5)
    if form == "more":
        length_txt = f"с ${a}$ cm по-голяма от ширината"
        length = f"x + {a}"
        c1, c0 = 4, 2 * a
    elif form == "times":
        length_txt = f"${k}$ пъти по-голяма от ширината"
        length = f"{k}x"
        c1, c0 = 2 + 2 * k, 0
    else:
        length_txt = f"с ${a}$ cm по-малка от удвоената ширина"
        length = f"2x - {a}"
        c1, c0 = 6, -2 * a
    key = f"{c1}x" + (f" + {c0}" if c0 > 0 else f" - {-c0}" if c0 < 0 else "")
    stem = (f"Ширината на правоъгълник е $x$ cm, а дължината му е {length_txt}. "
            f"Изразете и запишете чрез $x$ периметъра на правоъгълника.")
    solution = (rf"Дължината е ${length}$, а периметърът е "
                rf"$2\left(x + {length}\right) = {key}$")
    sig = f"rect_perimeter:{form}:{a if form != 'times' else k}"

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=stem, correct_answer=key, difficulty="medium",
            solution=solution, signature=sig,
        )

    half = f"{c1 // 2}x" + (f" + {c0 // 2}" if c0 > 0 else f" - {-c0 // 2}" if c0 < 0 else "")
    wrongs = {half, f"{c1}x" + (f" + {c0 // 2}" if c0 > 0 else f" - {-c0 // 2}" if c0 < 0 else f" + {k}"),
              f"{c1 - 2}x" + (f" + {c0}" if c0 > 0 else f" - {-c0}" if c0 < 0 else ""),
              f"{c1 + 2}x" + (f" + {c0}" if c0 > 0 else f" - {-c0}" if c0 < 0 else "")}
    wrongs.discard(key)
    options, letter = shuffle_options(f"${key}$", [f"${w}$" for w in list(wrongs)[:3]], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem.replace("Изразете и запишете чрез $x$ периметъра на правоъгълника.",
                          "Периметърът на правоъгълника, изразен чрез $x$, е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=sig,
    )


@template("expression_from_words_tariff",
          topics=["expression_from_words"], kinds=["mc"], weight=1.2, band="easy")
def expression_from_words_tariff(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A fixed charge plus a per-unit rate — the 2025 Q17 taxi shape."""
    # euro fares since 2026: a flag-fall of a euro or two, under a euro per km
    base = Fraction(rng.choice([120, 150, 180, 200, 250]), 100)
    rate = Fraction(rng.choice([70, 80, 90, 110, 120]), 100)
    b, r = bg_decimal(base, places=3), bg_decimal(rate, places=3)

    correct = rf"{b} + {r}x"
    wrongs = [rf"{r}x - {b}", rf"{r}\cdot{b}x", rf"{r}x"]
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Първоначалната такса при ползване на такси е ${b}$ евро. "
              f"За всеки изминат километър се заплаща по ${r}$ евро. "
              f"Кой от изразите представя сумата в евро, която клиент трябва "
              f"да заплати при изминаване на $x$ километра?"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=f"Постоянната такса ${b}$ плюс ${r}$ за всеки от $x$ километра: ${correct}$",
        signature=f"expr_tariff:{base}:{rate}",
    )


@template("expression_from_words_purchase",
          topics=["expression_from_words"], kinds=["mc"], weight=1.0)
def expression_from_words_purchase(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x of one item and a multiple of another — the 2024 Q16 balloon shape."""
    mult = rng.choice([2, 3, 4])
    price = Fraction(rng.choice([40, 50, 60, 80, 120]), 100)
    total_each = price * (1 + mult)
    p = bg_decimal(price, places=3)
    correct = rf"{bg_decimal(total_each, places=3)}x"
    wrongs = [
        rf"{mult}x + {p}",
        rf"{mult + 1}x + {p}",
        rf"{bg_decimal(price * mult, places=3)}x",
    ]
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Ива купила $x$ на брой бели балона и ${mult}$ пъти повече сини. "
              f"Един балон струва ${p}$ евро. Общата стойност на покупката, "
              f"изразена чрез $x$, е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Балоните са $x + {mult}x = {mult + 1}x$, а стойността е "
                  rf"${mult + 1}x \cdot {p} = {correct}$"),
        signature=f"expr_purchase:{mult}:{price}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Second and third variants per position.
#
# Every slot needs more than one template before difficulty can mean anything —
# with a single candidate the assembler has nothing to choose between and
# "easy" and "extra_hard" produce the same item. Each shape below is one the
# corpus actually contains (the year is named in the docstring) and each
# declares a band, which is what the profile re-weights.
# ═════════════════════════════════════════════════════════════════════════════

@template("linear_equation_proportion",
          topics=["linear_equation"], kinds=["mc"], weight=1.0, band="hard")
def linear_equation_proportion(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(x − a)/p = (x + b)/q — cross-multiply, then collect. The 2019 Q6 shape.

    ``q = p + 1`` is not decoration: it makes the coefficient of x collect to
    exactly 1, so the root is the whole number ``qa + pb`` on every draw
    instead of a fraction that would have to be rejected.
    """
    p = rng.choice(slot.profile.tier([2, 3], [2, 3, 4], [2, 3, 4, 5], [4, 5, 6, 7]))
    q = p + 1
    a = rng.randint(*slot.profile.tier((1, 4), (1, 6), (1, 9), (3, 14)))
    b = rng.randint(*slot.profile.tier((1, 4), (1, 6), (1, 9), (3, 14)))
    key = q * a + p * b

    wrong = [
        q * a - p * b,           # sign slip on the right-hand numerator
        p * a + q * b,           # multiplied each side by its own denominator
        a + b,                   # arrested: never cleared the fractions
        key + q,
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Коренът на уравнението "
              f"$\\frac{{x - {a}}}{{{p}}} = \\frac{{x + {b}}}{{{q}}}$ е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"${q}\left(x - {a}\right) = {p}\left(x + {b}\right)$, тоест "
                  rf"${q}x - {q * a} = {p}x + {p * b}$ и $x = {key}$"),
        signature=f"lin_prop:{p}:{a}:{b}",
    )


@template("abs_equation_nested",
          topics=["absolute_value_equation"], kinds=["mc"], weight=0.9, band="hard")
def abs_equation_nested(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Largest root of ||x − a| − b| = c — the 2021 Q3 nested-modulus shape.

    Four roots when b > c: the inner modulus is b + c or b − c, and each opens
    to two. The largest is a + b + c and the other three are the distractors,
    which is what makes the item honest — every wrong option really is a root,
    just not the biggest one.
    """
    a = rng.randint(*slot.profile.tier((3, 8), (4, 10), (5, 12), (8, 20)))
    b = rng.randint(*slot.profile.tier((3, 6), (4, 8), (4, 9), (7, 15)))
    c = rng.randint(1, max(1, b - 1))
    if b <= c:
        raise Retry("need four distinct roots")

    roots = sorted({a + b + c, a - b - c, a + b - c, a - b + c})
    if len(roots) != 4:
        raise Retry("roots collapsed")
    key = max(roots)

    wrong = [r for r in roots if r != key] + [a + b, b + c]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Най-големият корен на уравнението "
              f"$\\left|\\left|x - {a}\\right| - {b}\\right| = {c}$ е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"$\left|x - {a}\right| = {b + c}$ или "
                  rf"$\left|x - {a}\right| = {b - c}$, откъдето корените са "
                  rf"${', '.join(str(r) for r in roots)}$, а най-големият е ${key}$"),
        signature=f"abs_nested:{a}:{b}:{c}",
    )


@template("value_of_cubic_identity",
          topics=["expression_at_value"], kinds=["mc", "short"], weight=1.0, band="hard")
def value_of_cubic_identity(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(x + a)³ − x³ − 3ax(x + a), which collapses to a³ for every x.

    The 2026 Q16 family: an expression whose whole point is that the variable
    cancels, so the enormous value of x printed on the page is a red herring
    rather than a calculation. Expanding gives 3ax² + 3a²x + a³ and the last
    term removes the first two.
    """
    a = rng.choice(slot.profile.tier([2, 3], [2, 3, 4], [2, 3, 4, 5], [4, 5, 6, 7]))
    x = rng.choice(slot.profile.tier([10, 20], [100, 250], [2024, 2025, 2026],
                                     [20250, 20260]))
    key = a ** 3
    expr = rf"\left(x + {a}\right)^3 - x^3 - {3 * a}x\left(x + {a}\right)"
    solution = (rf"$\left(x+{a}\right)^3 - x^3 = {3 * a}x^2 + {3 * a * a}x + {key}$, "
                rf"а ${3 * a}x\left(x + {a}\right) = {3 * a}x^2 + {3 * a * a}x$, "
                rf"така че изразът е равен на ${key}$ за всяко $x$")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"Намерете стойността на израза ${expr}$ при $x = {x}$.",
            correct_answer=str(key), difficulty="hard",
            solution=solution, signature=f"cubic_id:{a}:{x}",
        )

    wrong = [a * a, 3 * a * a, key + a, 2 * key]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ при $x = {x}$ е:",
        options=options, correct_answer=letter, difficulty="hard",
        solution=solution, signature=f"cubic_id:{a}:{x}",
    )


# ─── quadratics: the same "don't divide by x" trap at two levels ─────────────

@template("quadratic_common_factor",
          topics=["quadratic_by_factoring"], kinds=["short"], weight=1.1, band="easy")
def quadratic_common_factor(rng: random.Random, slot: Slot) -> GeneratedItem:
    """ax² + bx = 0 — the gentlest form of the 2026 Q15 trap."""
    a = rng.randint(1, 6)
    m = rng.randint(2, 20)
    b = a * m
    lhs = "x^2" if a == 1 else f"{a}x^2"
    factored = "x" if a == 1 else f"{a}x"
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=f"Намерете корените на уравнението ${lhs} + {b}x = 0$.",
        correct_answer=f"0 и -{m}", difficulty="easy",
        solution=(rf"${factored}\left(x + {m}\right) = 0$, откъдето $x_1 = 0$ "
                  rf"и $x_2 = -{m}$. "
                  "(Половината точки при само един верен корен — делението "
                  "на $x$ губи нулевия.)"),
        signature=f"quad_common:{a}:{m}",
    )


@template("quadratic_shared_factor",
          topics=["quadratic_by_factoring"], kinds=["short"], weight=1.0, band="hard")
def quadratic_shared_factor(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x² − a² = k(x − a) — the same lost-root trap, one layer deeper.

    Both sides carry the factor (x − a). Cancelling it gives x = k − a and
    silently discards x = a, which is exactly what the official keys award half
    marks against.
    """
    a = rng.randint(2, 15)
    k = rng.randint(3, 25)
    other = k - a
    if other == a or other == 0:
        raise Retry("want two distinct, non-trivial roots")
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=(f"Намерете корените на уравнението "
              f"$x^2 - {a * a} = {k}\\left(x - {a}\\right)$."),
        correct_answer=f"{a} и {other}", difficulty="hard",
        solution=(rf"$\left(x - {a}\right)\left(x + {a}\right) = "
                  rf"{k}\left(x - {a}\right)$, тоест "
                  rf"$\left(x - {a}\right)\left(x + {a} - {k}\right) = 0$ и "
                  rf"$x_1 = {a}$, $x_2 = {other}$. "
                  rf"(Съкращаването на $\left(x - {a}\right)$ губи корена "
                  rf"${a}$ — оттам и частичните точки.)"),
        signature=f"quad_shared:{a}:{k}",
    )


# ─── inequalities: an easy and a hard partner for each existing item ─────────

@template("inequality_largest_integer_simple",
          topics=["inequality_integer_bound"], kinds=["mc"], weight=1.1, band="easy")
def inequality_largest_integer_simple(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Largest integer solution of x + a < b — one step, no sign flip."""
    a = rng.randint(1, 9)
    b = a + rng.randint(3, 20)
    key = b - a - 1
    wrong = [key + 1, key - 1, key + 2, b - a + 1]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Най-голямото цяло число, което е решение на неравенството "
              f"$x + {a} < {b}$, е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"$x < {b - a}$, а най-голямото цяло число в решението е ${key}$",
        signature=f"ineq_simple:{a}:{b}",
    )


@template("inequality_integer_bound_fractional",
          topics=["inequality_integer_bound"], kinds=["mc"], weight=1.0, band="hard")
def inequality_integer_bound_fractional(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Smallest integer solution of x/p − x/q ≥ c, where the bound is fractional.

    q − p = 2 is chosen so the critical value c·pq/2 lands on a half as often as
    not — which is the whole difficulty, because the smallest integer solution
    is then strictly above the bound rather than equal to it.
    """
    p, q = rng.choice([(3, 5), (4, 6), (2, 4), (5, 7)])
    c = rng.randint(1, 5)
    crit = Fraction(c * p * q, q - p)
    key = -(-crit.numerator // crit.denominator)          # exact ceiling
    if key > 60:
        raise Retry("keep the bound readable")

    wrong = [key - 1, key + 1, crit.numerator // crit.denominator, key + 2]
    options, letter = numeric_options(key, wrong, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Най-малкото цяло число, което е решение на неравенството "
              f"$\\frac{{x}}{{{p}}} - \\frac{{x}}{{{q}}} \\ge {c}$, е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"$\frac{{x\left({q} - {p}\right)}}{{{p * q}}} \ge {c}$, значи "
                  rf"$x \ge {bg_number(crit)}$, а най-малкото цяло число "
                  rf"в решението е ${key}$"),
        signature=f"ineq_frac:{p}:{q}:{c}",
    )


@template("inequality_interval_one_step",
          topics=["inequality_interval"], kinds=["mc"], weight=1.1, band="easy")
def inequality_interval_one_step(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x + a ≤ b as an interval — the closed four-bracket menu, one step to the bound."""
    a = rng.randint(2, 12)
    b = rng.randint(a + 1, a + 20)
    bound = b - a
    strict = rng.random() < 0.5
    rel = "<" if strict else r"\le"
    variants = interval_variants(str(bound), direction="le", closed=not strict)
    opts, letter = shuffle_options(f"${variants[0]}$",
                                   [f"${v}$" for v in variants[1:]], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Решенията на неравенството $x + {a} {rel} {b}$ "
              f"са всички числа от интервала:"),
        options=opts, correct_answer=letter, difficulty="easy",
        solution=rf"$x {rel} {bound}$",
        signature=f"ineq_iv_one:{a}:{b}:{strict}",
    )


@template("inequality_interval_sign_flip",
          topics=["inequality_interval"], kinds=["mc"], weight=1.0, band="hard")
def inequality_interval_sign_flip(rng: random.Random, slot: Slot) -> GeneratedItem:
    """a(x − b) ≥ c(x + d) with a < c, so dividing flips the inequality.

    c = a + 1 makes the collected coefficient exactly −1: the bound stays a
    whole number and the entire item is whether the student remembers to turn
    the sign round. Every option is the same bound, per the closed menu these
    interval items always use (2026 Q4, 2023 Q5, 2022 Q5, 2021 Q5).
    """
    a = rng.randint(2, 7)
    c = a + 1
    b = rng.randint(1, 9)
    d = rng.randint(1, 9)
    bound = -(a * b + c * d)                 # (a − c)x ≥ ab + cd  →  −x ≥ …
    strict = rng.random() < 0.5
    rel = ">" if strict else r"\ge"
    flipped = "<" if strict else r"\le"
    variants = interval_variants(str(bound), direction="le", closed=not strict)
    opts, letter = shuffle_options(f"${variants[0]}$",
                                   [f"${v}$" for v in variants[1:]], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Решенията на неравенството "
              f"${a}\\left(x - {b}\\right) {rel} {c}\\left(x + {d}\\right)$ "
              f"са всички числа от интервала:"),
        options=opts, correct_answer=letter, difficulty="hard",
        solution=(rf"${a}x - {a * b} {rel} {c}x + {c * d}$, откъдето "
                  rf"$-x {rel} {a * b + c * d}$; след деление на $-1$ знакът "
                  rf"се обръща и $x {flipped} {bound}$"),
        signature=f"ineq_iv_flip:{a}:{b}:{d}:{strict}",
    )


@template("isosceles_symbolic_perimeter_simple",
          topics=["symbolic_perimeter", "expression_from_words"], kinds=["short", "mc"],
          weight=1.1, band="easy")
def isosceles_symbolic_perimeter_simple(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Base x, legs x + a — the symbolic perimeter without the degeneracy trap.

    The 2026 Q21 item is sharp because the ratio forces you to notice that one
    assignment of the sides is degenerate. This one states which side is which,
    so it is the same skill (collect like terms, answer in x) with the trap
    removed — which is what makes it the easy member of the topic.
    """
    a = rng.randint(2, 9)
    key = f"3x + {2 * a}"

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=(f"Основата на равнобедрен триъгълник е $x$ cm, а всяко от "
                  f"бедрата му е с ${a}$ cm по-дълго от основата. Изразете "
                  f"чрез $x$ периметъра на триъгълника."),
            correct_answer=f"{key} cm", difficulty="easy",
            solution=(rf"Бедрата са по $x + {a}$, значи периметърът е "
                      rf"$x + 2\left(x + {a}\right) = {key}$ cm"),
            signature=f"iso_perim_simple:{a}",
        )

    wrongs = [f"$3x + {a}$", f"$2x + {2 * a}$", f"$3x + {3 * a}$"]
    options, letter = shuffle_options(f"${key}$", wrongs, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Основата на равнобедрен триъгълник е $x$ cm, а всяко от бедрата "
              f"му е с ${a}$ cm по-дълго от основата. Периметърът на "
              f"триъгълника, изразен чрез $x$, е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"$x + 2\left(x + {a}\right) = {key}$"),
        signature=f"iso_perim_simple:{a}",
    )
