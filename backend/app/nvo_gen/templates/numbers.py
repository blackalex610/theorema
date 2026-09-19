"""Arithmetic, powers, percent — the opening block of Part 1.

Position 1 is the same item in all six modern papers: a short expression with a
sign trap, worth 2 points. 2026 ran `1/5 − 1/5·10`; 2025 `2025 − 225·(−1/5)`;
2024 `2,25 + 0,75·(−4/3)`; 2022 `−20,5 + 0,5·(−1/5)`; 2021 `2021 − 2020·(−0,1)`.
Same skeleton every time — a term, an operator, and a product whose sign or
fraction is the whole test.

The distractor that matters here is the left-to-right one: a student who
evaluates `a − b·c` as `(a − b)·c`. It appears as an option in every one of
those five papers.
"""
from __future__ import annotations

import random
from fractions import Fraction

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.distractors import (
    bg_decimal,
    bg_number,
    is_clean_decimal,
    numeric_options,
    off_by_factor,
    sign_flip,
)
from app.nvo_gen.registry import GeneratedItem, Retry, template


# ─── position 1: arithmetic expression ───────────────────────────────────────

@template("arith_whole_minus_negative_product",
          topics=["arithmetic_expression"], kinds=["mc"], weight=1.4, band="easy")
def arith_whole_minus_negative_product(rng: random.Random, slot: Slot) -> GeneratedItem:
    """n − m·(−1/k)  — the 2025 and 2021 shape."""
    k = rng.choice(slot.profile.tier([2, 5, 10], [2, 4, 5, 10], [2, 4, 5, 10]))
    m = rng.choice(slot.profile.tier(
        [10, 20, 50, 100],
        [50, 100, 150, 200],
        [100, 125, 150, 200, 225, 250, 320],
        [225, 250, 320, 375, 425, 480]))
    if m % k:
        raise Retry("m must divide by k for a whole-number key")
    n = rng.choice(slot.profile.tier(
        [10, 20, 50, 100],
        [100, 200, 500, 1000],
        [1000, 1250, 1500, 2020, 2024, 2025, 2026],
        [2024, 2025, 2026, 12500, 20250]))
    product = Fraction(m, k)
    key = n + product

    wrong = [
        n - product,                       # sign flip: treated the minus as subtraction
        (n - m) * Fraction(-1, k),         # left to right
        product,                           # arrested: computed only the product
        n + product * k,                   # dropped the fraction
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    expr = rf"{n} - {m}\cdot\left(-\frac{{1}}{{{k}}}\right)"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=f"${expr} = {n} + {bg_number(product)} = {bg_number(key)}$",
        signature=f"arith_wmnp:{n}:{m}:{k}",
    )


@template("arith_unit_fraction_chain",
          topics=["arithmetic_expression"], kinds=["mc"], weight=1.2, band="easy")
def arith_unit_fraction_chain(rng: random.Random, slot: Slot) -> GeneratedItem:
    """1/k − 1/k·m  — the 2026 shape, answer is a negative decimal."""
    k = rng.choice(slot.profile.tier([2, 4, 5], [4, 5, 10], [4, 5, 8, 10, 20],
                                     [8, 20, 25, 40]))
    m = rng.choice(slot.profile.tier([2, 3, 4], [4, 6, 8], [6, 8, 10, 12, 15],
                                     [12, 15, 18, 24]))
    key = Fraction(1, k) - Fraction(m, k)
    if key == 0 or not is_clean_decimal(key, places=3):
        raise Retry("key must be a clean decimal")

    wrong = [
        sign_flip(key),
        Fraction(1, k) * (1 - m) * -1,                 # sign slip inside the bracket
        (Fraction(1, k) - Fraction(1, k)) * m,          # left to right → 0
        Fraction(1, k) - Fraction(1, k * m),            # divided instead of multiplied
    ]
    options, letter = numeric_options(
        key, wrong, rng=rng, fmt=lambda v: bg_decimal(v, places=3))
    expr = rf"\frac{{1}}{{{k}}} - \frac{{1}}{{{k}}}\cdot {m}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=f"${expr} = {bg_decimal(Fraction(1, k), places=3)} - "
                 f"{bg_decimal(Fraction(m, k), places=3)} = {bg_decimal(key, places=3)}$",
        signature=f"arith_ufc:{k}:{m}",
    )


@template("arith_decimal_times_fraction",
          topics=["arithmetic_expression"], kinds=["mc"], weight=1.0, band="easy")
def arith_decimal_times_fraction(rng: random.Random, slot: Slot) -> GeneratedItem:
    """d1 + d2·(−p/q)  — the 2024 and 2022 shape."""
    q = rng.choice([3, 4, 5])
    p = rng.choice([2, 3, 4, 5])
    if p == q:
        raise Retry("p/q must not be 1")
    d2 = Fraction(rng.choice([25, 50, 75, 125, 150]), 100)
    d1 = Fraction(rng.choice([-2050, -1025, 225, 325, 450, 1250]), 100)
    product = d2 * Fraction(p, q)
    key = d1 - product
    # An NVO answer is a short decimal, never 0,5833… . Both the product and
    # the key must terminate within two places, which rules out most (d2, q)
    # pairs — cheaper to reject the draw than to constrain q up front.
    if not (is_clean_decimal(product) and is_clean_decimal(key)):
        raise Retry("both the product and the key must be two-place decimals")

    wrong = [
        d1 + product,
        (d1 - d2) * Fraction(p, q),
        -product,
        d1 - d2,
    ]
    options, letter = numeric_options(
        key, wrong, rng=rng, fmt=lambda v: bg_decimal(v, places=2))
    expr = (rf"{bg_decimal(d1, places=2)} + {bg_decimal(d2, places=2)}"
            rf"\cdot\left(-\frac{{{p}}}{{{q}}}\right)")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Числената стойност на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=f"$= {bg_decimal(d1, places=2)} - {bg_decimal(product, places=2)} "
                 f"= {bg_decimal(key, places=2)}$",
        signature=f"arith_dtf:{d1}:{d2}:{p}:{q}",
    )


# ─── powers ──────────────────────────────────────────────────────────────────

@template("powers_same_base_ratio", topics=["powers"], kinds=["mc"], weight=1.3)
def powers_same_base_ratio(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(b^n − b^m)/(b^n + b^m) — the 2026 Q5 shape. Factor out b^m."""
    b = rng.choice(slot.profile.tier([2, 3], [2, 3], [2, 3, 5], [2, 3, 5, 7]))
    m = rng.randint(*slot.profile.tier((2, 3), (2, 4), (3, 6), (5, 9)))
    n = m + 1
    key = Fraction(b - 1, b + 1)

    wrong = [
        Fraction(b + 1, b - 1),           # reciprocal
        Fraction(1, b),
        Fraction(b - 1, b),
        Fraction(0, 1),                   # "the powers cancel"
        Fraction(1, 1),
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    expr = rf"\frac{{{b}^{{{n}}} - {b}^{{{m}}}}}{{{b}^{{{n}}} + {b}^{{{m}}}}}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е равна на:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"Изнасяме ${b}^{{{m}}}$ пред скоби: "
                 rf"$\frac{{{b}^{{{m}}}({b}-1)}}{{{b}^{{{m}}}({b}+1)}} = {bg_number(key)}$",
        signature=f"pow_ratio:{b}:{m}",
    )


@template("powers_negative_exponent", topics=["powers"], kinds=["mc"], weight=1.0)
def powers_negative_exponent(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x^a·(x^b/x^c)^(−d) evaluated at a negative x — the 2025 Q2 shape."""
    b, c = 3, 2
    d = rng.choice(slot.profile.tier([2], [2, 3], [2, 3, 4, 6], [3, 4, 6, 8]))
    a = rng.choice(slot.profile.tier([2, 3], [2, 3, 4], [2, 3, 4], [3, 4, 5, 6]))
    x = rng.choice(slot.profile.tier([2, 3], [-2, 2, 3], [-3, -2, 2, 3],
                                     [-5, -3, -2, 2, 3, 5]))
    exponent = a - d * (b - c)
    key = Fraction(x) ** exponent
    if abs(key.numerator) > 200 or key.denominator > 200:
        raise Retry("keep the value printable")

    wrong = [
        sign_flip(key),
        Fraction(x) ** (-exponent) if exponent else Fraction(1),
        Fraction(x) ** (a + d * (b - c)),
        Fraction(x) ** (exponent + 1),
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    expr = rf"x^{{{a}}}\cdot\left(\frac{{x^{{{b}}}}}{{x^{{{c}}}}}\right)^{{-{d}}}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ при $x = {x}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"$= x^{{{a}}}\cdot x^{{{-d * (b - c)}}} = x^{{{exponent}}} = {bg_number(key)}$",
        signature=f"pow_neg:{a}:{d}:{x}",
    )


# ─── shortcut multiplication (съкратено умножение) ───────────────────────────

@template("shortcut_square_of_difference",
          topics=["shortcut_multiplication"], kinds=["mc"], weight=1.2)
def shortcut_square_of_difference(rng: random.Random, slot: Slot) -> GeneratedItem:
    """N² − 2·M·N + M²  recognised as (N − M)² — the 2024 Q7 shape."""
    n = rng.choice([1012, 1015, 1020, 1025, 2013])
    m = rng.choice([1000, 1010, 2000])
    if n <= m:
        raise Retry("need n > m so the answer is positive")
    diff = n - m
    key = diff * diff

    # Every candidate has to land inside the plausibility band (within ×50 of
    # the key) or `numeric_options` discards it. `n² − m²` and `(n + m)²` are
    # the mistakes a student actually makes here, but both are four orders of
    # magnitude above `diff²`, so they were being discarded every single time
    # and this template could never build. The in-band mistakes are the ones
    # about the subtraction itself: off by one before squaring, forgot to
    # square, or doubled instead of squared.
    wrong = [(diff - 1) ** 2, (diff + 1) ** 2, 2 * key, diff]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    expr = rf"{n}^2 - {2 * m}\cdot {n} + {m}^2"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"$= ({n} - {m})^2 = {diff}^2 = {key}$",
        signature=f"short_sqdiff:{n}:{m}",
    )


@template("shortcut_difference_of_squares",
          topics=["shortcut_multiplication"], kinds=["mc"], weight=1.0)
def shortcut_difference_of_squares(rng: random.Random, slot: Slot) -> GeneratedItem:
    """a² − b² with near-equal decimals — the 2023 Q3 shape (0,99² − 0,01²)."""
    hundredths = rng.choice([1, 2, 5])
    a = Fraction(100 - hundredths, 100)
    b = Fraction(hundredths, 100)
    key = (a - b) * (a + b)

    # (a−b)² and a²+b² both run to four decimal places here, which no NVO
    # option list does — keep only the candidates that print as cleanly as the
    # key does.
    candidates = [a - b, a + b, (a - b) * (a - b), a * a + b * b, key - b, key + b]
    wrong = [c for c in candidates if is_clean_decimal(c, places=2)]
    options, letter = numeric_options(
        key, wrong, rng=rng, fmt=lambda v: bg_decimal(v, places=2), positive_only=True)
    expr = rf"{bg_decimal(a, places=2)}^2 - {bg_decimal(b, places=2)}^2"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"$= ({bg_decimal(a, places=2)} - {bg_decimal(b, places=2)})"
                 rf"({bg_decimal(a, places=2)} + {bg_decimal(b, places=2)}) "
                 rf"= {bg_decimal(key, places=2)}$",
        signature=f"short_diffsq:{hundredths}",
    )


# ─── percent and simple interest ─────────────────────────────────────────────

@template("percent_annual_interest",
          topics=["percent_interest"], kinds=["mc"], weight=1.3, band="easy")
def percent_annual_interest(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Deposit grows over a year; find the rate — the 2026 Q7 shape."""
    principal = rng.choice([8_000, 12_000, 15_000, 20_000, 25_000])
    rate = rng.choice([2, 3, 4, 5, 6])
    interest = principal * rate // 100
    total = principal + interest

    wrong = [
        Fraction(rate, 10),                 # arrested: misplaced the decimal
        Fraction(100 + rate, 100),          # gave the growth factor as a percent
        rate * 10,
        Fraction(interest, principal),
    ]
    options, letter = numeric_options(
        rate, wrong, rng=rng, positive_only=True,
        fmt=lambda v: f"{bg_decimal(Fraction(v), places=3)}\\%")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В инвестиционен фонд вложили {principal:,} евро и след една година "
              f"сумата нараснала на {total:,} евро. Колко е бил годишният лихвен процент?"
              ).replace(",", " "),
        options=options, correct_answer=letter, difficulty="easy",
        solution=f"Лихвата е ${interest}$ евро, а ${interest} : {principal} = {bg_decimal(Fraction(rate, 100), places=4)} = {rate}\\%$",
        signature=f"pct_interest:{principal}:{rate}",
    )


@template("percent_of_a_quantity",
          topics=["percent_interest"], kinds=["mc"], weight=1.0, band="easy")
def percent_of_a_quantity(rng: random.Random, slot: Slot) -> GeneratedItem:
    """What percent of a class are girls — the 2022 Q6 shape."""
    total = rng.choice([20, 25, 40, 50])
    boys = rng.choice([12, 14, 16, 18, 22, 28])
    if not 0 < boys < total or (total - boys) * 100 % total:
        raise Retry("need a whole-number percentage")
    girls = total - boys
    key = girls * 100 // total

    wrong = [boys * 100 // total, girls, boys, 100 - key * 2]
    options, letter = numeric_options(
        key, wrong, rng=rng, positive_only=True, fmt=lambda v: f"{v}\\%")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В един клас има {total} ученици, от които {boys} са момчета. "
              f"Колко процента са момичетата в този клас?"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"Момичетата са ${girls}$, а $\frac{{{girls}}}{{{total}}} = {key}\%$",
        signature=f"pct_of:{total}:{boys}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Band partners, so the opening block has a real choice at every difficulty.
# ═════════════════════════════════════════════════════════════════════════════

@template("powers_product_quotient", topics=["powers"], kinds=["mc"], weight=1.1,
          band="easy")
def powers_product_quotient(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(bᵐ · bⁿ)/bᵏ — one application each of the product and quotient rules."""
    b = rng.choice([2, 3, 5])
    m = rng.randint(2, 4)
    n = rng.randint(2, 4)
    k = rng.randint(2, 5)
    e = m + n - k
    if not 1 <= e <= 4:
        raise Retry("keep the resulting power small enough to evaluate")
    key = b ** e

    wrong = [b ** (e + 1), b ** (e - 1), b * e, key + b]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    expr = rf"\frac{{{b}^{{{m}}}\cdot {b}^{{{n}}}}}{{{b}^{{{k}}}}}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"$= {b}^{{{m} + {n} - {k}}} = {b}^{{{e}}} = {key}$",
        signature=f"pow_pq:{b}:{m}:{n}:{k}",
    )


@template("powers_sum_factored", topics=["powers"], kinds=["mc"], weight=1.0,
          band="hard")
def powers_sum_factored(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(bⁿ⁺¹ + bⁿ)/bⁿ⁻¹, which is b(b + 1) whatever n is.

    The 2026 Q5 move — factor the common power out of the sum — but with the
    exponent left symbolic, so no amount of arithmetic substitutes for seeing
    that bⁿ⁺¹ + bⁿ = bⁿ(b + 1).
    """
    b = rng.choice([2, 3, 5])
    n = rng.randint(3, 7)
    key = b * (b + 1)

    wrong = [b + 1, b * b, b * (b - 1), b * b + 1, (b + 1) * (b + 1)]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    expr = rf"\frac{{{b}^{{{n + 1}}} + {b}^{{{n}}}}}{{{b}^{{{n - 1}}}}}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"Изнасяме ${b}^{{{n}}}$ пред скоби: "
                  rf"$\frac{{{b}^{{{n}}}\left({b} + 1\right)}}{{{b}^{{{n - 1}}}}} "
                  rf"= {b}\left({b} + 1\right) = {key}$"),
        signature=f"pow_sumfac:{b}:{n}",
    )


@template("shortcut_product_near_hundred",
          topics=["shortcut_multiplication"], kinds=["mc"], weight=1.1, band="easy")
def shortcut_product_near_hundred(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(100 − k)(100 + k) read as 10000 − k² — the plainest difference of squares."""
    k = rng.choice([1, 2, 3, 4, 5, 6, 7])
    key = 10000 - k * k

    wrong = [10000 + k * k, 10000, (100 - k) ** 2, (100 + k) ** 2]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на произведението ${100 - k}\\cdot {100 + k}$ е:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"$\left(100 - {k}\right)\left(100 + {k}\right) = "
                  rf"100^2 - {k}^2 = 10000 - {k * k} = {key}$"),
        signature=f"short_near100:{k}",
    )


@template("percent_two_stage_price",
          topics=["percent_interest"], kinds=["mc"], weight=1.0, band="hard")
def percent_two_stage_price(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A price raised p% then cut q% — successive percentages don't add.

    The distractor that matters is the one a student reaches by netting the two
    percentages into a single (p − q)%, which is wrong precisely because the
    second percentage is taken of the *new* price. It is offered first.
    """
    p, q = rng.choice([(20, 10), (25, 20), (10, 10), (50, 20), (30, 10),
                       (20, 25), (40, 25), (25, 40)])
    base = rng.choice([200, 400, 500, 800, 1000, 1200, 1500, 2000])
    raised = Fraction(base * (100 + p), 100)
    final = raised * Fraction(100 - q, 100)
    if final.denominator != 1 or raised.denominator != 1:
        raise Retry("both stages must land on whole leva")
    key = final.numerator

    naive = base * (100 + p - q) // 100          # netted the percentages
    wrong = [naive, raised.numerator, base * (100 - q) // 100, base]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      suffix="лв.")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Цената на един артикул е ${base}$ лв. Първо тя се увеличава с "
              f"${p}\\%$, а след това новата цена се намалява с ${q}\\%$. "
              f"Крайната цена на артикула е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"След увеличението цената е ${raised.numerator}$ лв., "
                  rf"а след намалението ${raised.numerator}\cdot "
                  rf"\frac{{{100 - q}}}{{100}} = {key}$ лв. "
                  rf"(Не е ${naive}$ лв. — второто намаление е от новата цена.)"),
        signature=f"pct_two_stage:{base}:{p}:{q}",
    )


@template("arith_bracket_divided_by_fraction",
          topics=["arithmetic_expression"], kinds=["mc"], weight=0.9, band="hard")
def arith_bracket_divided_by_fraction(rng: random.Random, slot: Slot) -> GeneratedItem:
    """(a − b/c) : (−d/e) — the opener with a division by a negative fraction.

    Position 1 is the same item in every modern paper: one term, one operator,
    one product or quotient whose sign is the real test. This is that item at
    its heaviest — dividing by a fraction *and* keeping the minus.
    """
    a = rng.randint(1, 4)
    b, c = rng.choice([(1, 2), (1, 4), (3, 4), (2, 5), (1, 5), (3, 5)])
    d, e = rng.choice([(1, 2), (2, 3), (3, 4), (1, 5), (3, 5), (2, 7)])
    inner = a - Fraction(b, c)
    key = inner * Fraction(-e, d)
    if key == 0 or abs(key.numerator) > 200 or key.denominator > 20:
        raise Retry("keep the value printable")

    wrong = [
        -key,                                     # lost the minus
        inner * Fraction(-d, e),                  # multiplied instead of dividing
        Fraction(a) * Fraction(-e, d) - Fraction(b, c),   # no bracket
        key + 1,
    ]
    options, letter = numeric_options(key, wrong, rng=rng)
    expr = (rf"\left({a} - \frac{{{b}}}{{{c}}}\right) : "
            rf"\left(-\frac{{{d}}}{{{e}}}\right)")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ е:",
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"В скобата: ${bg_number(inner)}$. Делението на "
                  rf"$-\frac{{{d}}}{{{e}}}$ е умножение по "
                  rf"$-\frac{{{e}}}{{{d}}}$, откъдето ${bg_number(key)}$"),
        signature=f"arith_bdf:{a}:{b}:{c}:{d}:{e}",
    )
