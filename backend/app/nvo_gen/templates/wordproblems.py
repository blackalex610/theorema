"""Word problems — the block that closes Part 1 after the geometry run.

These are the items where a generator most easily gives itself away, because
the *numbers* have to come out clean and the *story* has to stay plausible.
Both are handled by constraining the parameter space rather than by fixing up
afterwards: a work-rate pair is drawn from times whose harmonic mean is whole,
a percent problem from percentages that divide the count exactly. A draw that
would produce 17,3333… minutes raises Retry instead of rounding, because a
rounded answer is not an answer any official key would print.

Names are drawn from the pool the real papers use (Петко, Матей, Ани, Ивет,
Бойко, Валя…) so the surface reads Bulgarian rather than translated.
"""
from __future__ import annotations

import math
import random
from fractions import Fraction

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.distractors import (
    bg_decimal,
    bg_number,
    numeric_options,
    off_by_factor,
    shuffle_options,
)
from app.nvo_gen.registry import GeneratedItem, Retry, template

_NAMES_M = ["Петко", "Матей", "Бойко", "Иван", "Георги", "Никола", "Асен"]
_NAMES_F = ["Ани", "Ивет", "Валя", "Мария", "Елена", "Дора", "Ралица"]

#: (what the first one does, what the second one does, what they do together).
#: Bulgarian needs all three written out — the second clause takes "същата/ия"
#: and the third moves to the plural, neither of which is a suffix rule.
_CHORES = [
    ("подреди детската стая", "подреди същата стая", "подредят стаята"),
    ("боядиса една стая", "боядиса същата стая", "боядисат стаята"),
    ("почисти двора", "почисти същия двор", "почистят двора"),
    ("опакова кашоните", "опакова същите кашони", "опаковат кашоните"),
]


# ─── joint work rate ─────────────────────────────────────────────────────────

@template("work_rate_two_people", topics=["work_rate"], kinds=["mc"], weight=1.4)
def work_rate_two_people(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two people working together — the 2026 Q8 shape.

    Only pairs whose harmonic mean is a whole number of minutes are allowed:
    (30,45)→18, (20,30)→12, (12,24)→8. The real paper uses 30 and 45.
    """
    # Every pair here has a whole-number harmonic mean; the harder tiers just
    # use bigger ones, where the common denominator is no longer obvious.
    a, b = rng.choice(slot.profile.tier(
        [(20, 30), (15, 30), (12, 24), (10, 40)],
        [(30, 45), (20, 30), (15, 30), (18, 36), (10, 40)],
        [(30, 45), (20, 30), (12, 24), (15, 30), (10, 40), (20, 80), (18, 36)],
        [(21, 28), (36, 45), (30, 70), (42, 56), (40, 60), (20, 80)]))
    together = Fraction(a * b, a + b)
    if together.denominator != 1:
        raise Retry("joint time must be whole minutes")
    key = together.numerator

    name_a, name_b = rng.sample(_NAMES_M, 2)
    first, second, joint = rng.choice(_CHORES)

    wrong = [
        (a + b) // 2,              # averaged the times
        a + b,                     # added them
        abs(a - b),
        min(a, b) // 2,
    ]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{name_a} може сам да {first} за {a} минути, а брат му {name_b} "
              f"може да {second} за {b} минути. "
              f"За колко минути двамата братя заедно ще {joint}?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"За една минута заедно вършат "
                  rf"$\frac{{1}}{{{a}}} + \frac{{1}}{{{b}}} = \frac{{1}}{{{key}}}$ "
                  rf"от работата, значи им трябват ${key}$ минути"),
        signature=f"work_rate:{a}:{b}",
    )


# ─── percent in context ──────────────────────────────────────────────────────

@template("percent_remainder_capacity",
          topics=["percent_word_problem"], kinds=["short", "mc"], weight=1.4)
def percent_remainder_capacity(rng: random.Random, slot: Slot) -> GeneratedItem:
    """p% of the seats are taken, n are free — find the total. 2026 Q18."""
    pct = rng.choice(slot.profile.tier([50, 75, 80], [75, 80, 60], [80, 75, 85, 60, 90],
                                       [85, 88, 92, 65, 95]))
    total = rng.choice(slot.profile.tier(
        [40, 60, 80, 100],
        [80, 100, 120, 150],
        [80, 90, 120, 150, 200, 240, 300],
        [240, 300, 400, 500, 600, 800]))
    free = total * (100 - pct) // 100
    if total * (100 - pct) % 100 or free < 6:
        raise Retry("free seats must be a whole, visible number")

    # Bulgarian needs the definite form in the closing question, and it is not
    # derivable from the nominative by suffixing (зала → залата, not залаа),
    # so both forms are stored.
    venue, venue_def, unit = rng.choice([
        ("киносалон", "киносалона", "места"),
        ("театрален салон", "театралния салон", "места"),
        ("концертна зала", "концертната зала", "места"),
        ("голяма аудитория", "аудиторията", "места"),
    ])
    stem = (f"На прожекция в {venue} зрителите заели {pct}% от местата, "
            f"а {free} {unit} останали свободни. Колко са всичките {unit} "
            f"в {venue_def}?")
    solution = (rf"Свободните са ${100 - pct}\%$ от всички, значи всички са "
                rf"${free} : {bg_decimal(Fraction(100 - pct, 100), places=3)} = {total}$")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=stem, correct_answer=f"{total} {unit}", difficulty="medium",
            solution=solution, signature=f"pct_capacity:{pct}:{total}",
        )

    wrong = [total * pct // 100, free * 100 // pct, total - free, free * 2]
    options, letter = numeric_options(total, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"pct_capacity:{pct}:{total}",
    )


@template("percent_part_of_whole",
          topics=["percent_word_problem", "word_problem_ratio"], kinds=["mc"], weight=1.0)
def percent_part_of_whole(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A group is a fraction of another; find the combined total. 2025 Q16."""
    num, den = rng.choice([(2, 5), (3, 4), (2, 3), (3, 5), (4, 5)])
    women = rng.choice([12, 18, 20, 24, 30, 36, 40])
    if women * den % num:
        raise Retry("men must come out whole")
    men = women * den // num
    key = men + women

    wrong = [men, women * den // num - women, women * num // den + women, men * 2]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Във фирма работят {women} жени, които са "
              rf"$\frac{{{num}}}{{{den}}}$ от броя на мъжете. "
              f"Общият брой на работещите мъже и жени във фирмата е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Мъжете са ${women} : \frac{{{num}}}{{{den}}} = {men}$, "
                  rf"а общо са ${men} + {women} = {key}$"),
        signature=f"pct_part:{num}:{den}:{women}",
    )


# ─── mixture ─────────────────────────────────────────────────────────────────

@template("mixture_fat_content",
          topics=["word_problem_mixture"], kinds=["mc"], weight=1.3, band="hard")
def mixture_fat_content(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Blending two milks to a target fat percentage — the 2024 Q17 shape."""
    v1 = rng.choice([2, 3, 4])
    v_total = v1 + rng.choice([1, 2, 3])
    v2 = v_total - v1
    p1 = Fraction(rng.choice([15, 20, 25, 30]), 10)          # 1,5 % … 3,0 %
    p_mix = Fraction(rng.choice([30, 32, 34, 36, 40]), 10)
    # v1·p1 + v2·p2 = v_total·p_mix
    p2 = (v_total * p_mix - v1 * p1) / v2
    if p2 <= 0 or p2 > 12 or (p2 * 10).denominator != 1:
        raise Retry("second concentration must be a clean small percentage")

    wrong = [p_mix, p1, p2 + 1, p2 / 2]
    options, letter = numeric_options(
        p2, wrong, rng=rng, positive_only=True,
        fmt=lambda v: f"{bg_decimal(Fraction(v), places=3)}\\%")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Колко процента е масленост­та на прясно мляко, ако при смесването му "
              f"с ${v1}$ литра прясно мляко с масленост ${bg_decimal(p1, places=3)}$% "
              f"се получават ${v_total}$ литра прясно мляко с масленост "
              f"${bg_decimal(p_mix, places=3)}$%?"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"${v1} \cdot {bg_decimal(p1, places=3)} + {v2}x = "
                  rf"{v_total} \cdot {bg_decimal(p_mix, places=3)}$, "
                  rf"откъдето $x = {bg_decimal(p2, places=3)}\%$"),
        signature=f"mix_fat:{v1}:{v2}:{p1}:{p_mix}",
    )


@template("mixture_three_part_ratio",
          topics=["word_problem_ratio", "word_problem_mixture"], kinds=["mc"], weight=1.2)
def mixture_three_part_ratio(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Three ingredients in ratio a:b:c within a fixed volume — 2024 Q18."""
    a, b, c = rng.choice([(1, 2, 5), (1, 3, 4), (2, 3, 5), (1, 2, 2), (3, 4, 5)])
    volume = rng.choice([100, 120, 160, 200, 240])
    parts = a + b + c
    if volume % parts:
        raise Retry("volume must divide into whole parts")
    unit = volume // parts
    key = b * unit

    wrong = [a * unit, c * unit, unit, b * unit * 2]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"При производството на козметично изделие се смесват три течни "
              f"съставки $X$, $Y$ и $Z$, съответно в отношение ${a} : {b} : {c}$. "
              f"Колко милилитра е съдържанието на съставката $Y$ в {volume} ml "
              f"от козметичното изделие?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Частите са ${parts}$, една част е ${volume} : {parts} = {unit}$ ml, "
                  rf"а $Y$ е ${b} \cdot {unit} = {key}$ ml"),
        signature=f"ratio3:{a}:{b}:{c}:{volume}",
    )


# ─── units ───────────────────────────────────────────────────────────────────

@template("units_paint_coverage",
          topics=["word_problem_units"], kinds=["mc"], weight=1.2)
def units_paint_coverage(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Grams per m² over a rectangular wall, answered in kg — the 2024 Q9 shape.

    The whole item is the gram-to-kilogram step, so the off-by-a-factor family
    supplies every distractor: the same digits at ×10, ×100 and ÷100.
    """
    grams = rng.choice([150, 200, 250, 300])
    w = rng.choice([4, 5, 6])
    h = rng.choice([5, 6, 7, 8])
    area = w * h
    key = Fraction(grams * area, 1000)
    if key.denominator != 1 and (key * 10).denominator != 1:
        raise Retry("answer must print as a short decimal")

    # The ×1000 "forgot to convert grams to kilograms" answer is the mistake
    # this item is built around, but it is a thousand times the key and the
    # plausibility filter discards it — along with ×100 — which left only two
    # usable options and made this template unbuildable. Swap in the in-band
    # mistakes: the one-step unit slips, and using the wall's perimeter where
    # its area belongs.
    wrong = [key * 10, key / 10, Fraction(grams * 2 * (w + h), 1000), key * 2]
    options, letter = numeric_options(
        key, wrong, rng=rng, positive_only=True,
        fmt=lambda v: bg_decimal(Fraction(v), places=4))
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"За боядисване на $1$ m$^2$ стена се използват {grams} грама боя. "
              f"Колко килограма боя е необходима за боядисване на правоъгълна "
              f"стена с размери ${w}$ m и ${h}$ m?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Лицето е ${area}$ m$^2$, боята е ${grams} \cdot {area} = "
                  rf"{grams * area}$ g $= {bg_decimal(key, places=4)}$ kg"),
        signature=f"units_paint:{grams}:{w}:{h}",
    )


@template("units_map_scale", topics=["word_problem_units"], kinds=["mc"], weight=1.1, band="easy")
def units_map_scale(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Map distance to real distance — the 2021 Q18 and 2023 Q6 shape."""
    cm_ref = rng.choice([3, 5, 6, 9])
    km_per_cm = rng.choice([100, 120, 200, 250, 410])
    km_ref = cm_ref * km_per_cm
    cm_q = rng.choice([2, 3, 4, 7])
    if cm_q == cm_ref:
        raise Retry("the asked distance should differ from the reference")
    key = cm_q * km_per_cm

    wrong = [km_per_cm, km_ref, key * 10, key // 2 if key % 2 == 0 else key + 100]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      fmt=lambda v: f"{v}", suffix="km")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"На географска карта на ${cm_ref}$ cm съответстват ${km_ref}$ km "
              f"действително разстояние. Ако разстоянието между два града на "
              f"картата е ${cm_q}$ cm, то действителното разстояние между тях "
              f"в километри е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"На $1$ cm съответстват ${km_per_cm}$ km, значи на ${cm_q}$ cm "
                  rf"съответстват ${key}$ km"),
        signature=f"units_scale:{cm_ref}:{km_per_cm}:{cm_q}",
    )


@template("units_speed_difference",
          topics=["word_problem_units"], kinds=["mc"], weight=1.0)
def units_speed_difference(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two cyclists, one given in m/min — the 2023 Q7 shape."""
    v1 = rng.choice([15, 18, 20, 22])
    delta_tenths = rng.choice([6, 8, 12, 16, 20])
    v2 = Fraction(v1 * 10 + delta_tenths, 10)
    metres_per_minute = v2 * 60
    if metres_per_minute.denominator != 1:
        raise Retry("distance per minute must be a whole number of metres")
    key = v2 - v1

    wrong = [v2, v1, key * 10, key + v1]
    options, letter = numeric_options(
        key, wrong, rng=rng, positive_only=True,
        fmt=lambda v: bg_decimal(Fraction(v), places=3), suffix="m/s")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Един велосипедист се движи със скорост ${v1}$ m/s, а друг "
              f"велосипедист изминава ${metres_per_minute.numerator}$ m за $1$ минута. "
              f"С колко метра в секунда вторият велосипедист е по-бърз от първия?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Вторият се движи с ${metres_per_minute.numerator} : 60 = "
                  rf"{bg_decimal(v2, places=3)}$ m/s, а разликата е "
                  rf"${bg_decimal(key, places=3)}$ m/s"),
        signature=f"units_speed:{v1}:{delta_tenths}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Band partners for the word-problem and probability positions.
# ═════════════════════════════════════════════════════════════════════════════

@template("work_rate_pipes", topics=["work_rate"], kinds=["mc"], weight=1.1,
          band="easy")
def work_rate_pipes(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two pipes filling a pool — the joint-rate item with friendly numbers.

    Same identity as the 2026 Q8 item, drawn from pairs small enough that the
    common denominator is obvious.
    """
    a, b = rng.choice([(3, 6), (4, 12), (6, 12), (5, 20), (10, 15), (6, 30), (4, 4)])
    together = Fraction(a * b, a + b)
    if together.denominator != 1:
        raise Retry("joint time must be whole hours")
    key = together.numerator

    wrong = [(a + b) // 2, a + b, abs(a - b), min(a, b) // 2, key + 1]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Първата тръба напълва един басейн за ${a}$ часа, а втората — "
              f"за ${b}$ часа. За колко часа ще напълнят басейна двете тръби "
              f"заедно?"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"За един час заедно напълват "
                  rf"$\frac{{1}}{{{a}}} + \frac{{1}}{{{b}}} = \frac{{1}}{{{key}}}$ "
                  rf"от басейна, значи им трябват ${key}$ часа"),
        signature=f"work_pipes:{a}:{b}",
    )


@template("work_rate_second_worker", topics=["work_rate"], kinds=["mc"], weight=1.0,
          band="hard")
def work_rate_second_worker(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Given one worker's time and the joint time, find the other's.

    The joint-rate identity run backwards, which is the version students get
    wrong: 1/b = 1/t − 1/a, not b = a − t. That subtraction is offered as the
    first distractor.
    """
    a, t = rng.choice([(6, 2), (12, 4), (12, 3), (20, 4), (15, 6), (6, 4),
                       (30, 10), (8, 6), (9, 6), (10, 5), (20, 15)])
    if a <= t:
        raise Retry("the joint time must be shorter than either alone")
    second = Fraction(a * t, a - t)
    if second.denominator != 1:
        raise Retry("the second time must be whole hours")
    key = second.numerator

    name_a, name_b = rng.sample(_NAMES_M, 2)
    first, _second_txt, joint = rng.choice(_CHORES)

    wrong = [a - t, a + t, 2 * t, a, key + t]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{name_a} сам може да {first} за ${a}$ часа. Заедно с {name_b} "
              f"те {joint} за ${t}$ часа. За колко часа {name_b} би свършил "
              f"същата работа сам?"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"$\frac{{1}}{{{t}}} - \frac{{1}}{{{a}}} = "
                  rf"\frac{{1}}{{{key}}}$, значи вторият сам работи ${key}$ часа "
                  rf"(а не ${a - t}$ — времената не се изваждат)"),
        signature=f"work_second:{a}:{t}",
    )


@template("percent_discount_price",
          topics=["percent_word_problem"], kinds=["short", "mc"], weight=1.1,
          band="easy")
def percent_discount_price(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A single p% discount off a marked price — one step, no remainder."""
    base = rng.choice([40, 60, 80, 120, 150, 200, 250, 300])
    pct = rng.choice([10, 20, 25, 50, 40])
    if base * pct % 100:
        raise Retry("the discount must be a whole number of leva")
    key = base * (100 - pct) // 100

    # The indefinite article agrees with the noun's gender and is not derivable
    # from the noun, so it is stored beside it — "едно яке" but "един велосипед".
    article, goods = rng.choice([
        ("едно", "яке"), ("един", "чифт обувки"), ("една", "раница"),
        ("един", "велосипед"), ("един", "часовник"), ("една", "тениска"),
    ])
    opening = f"Цената на {article} {goods} е ${base}$ лв."
    solution = (rf"Намалението е ${base * pct // 100}$ лв., а новата цена "
                rf"${base} - {base * pct // 100} = {key}$ лв.")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"{opening} Намерете новата цена при намаление от ${pct}\\%$.",
            correct_answer=f"{key} лв.",
            difficulty="easy", solution=solution,
            signature=f"pct_discount:{base}:{pct}",
        )

    stem = f"{opening} При намаление от ${pct}\\%$ новата цена е:"

    wrong = [base * pct // 100, base * (100 + pct) // 100, base - pct,
             base * (100 - pct) // 200]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      suffix="лв.")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="easy",
        solution=solution, signature=f"pct_discount:{base}:{pct}",
    )


@template("percent_of_route_two_days",
          topics=["percent_word_problem"], kinds=["short", "mc"], weight=1.2,
          band="medium")
def percent_of_route_two_days(rng: random.Random, slot: Slot) -> GeneratedItem:
    """p% of a route on day one, q% of the *remainder* on day two, L km left.

    The 2025 Q18 shape. The whole item is that the second percentage is taken of
    what is left, not of the whole route — so the distractor built from
    (100 − p − q)% is the one that catches the misreading.
    """
    p, q = rng.choice([(40, 25), (30, 50), (20, 25), (50, 40), (25, 20),
                       (60, 50), (20, 50), (40, 50)])
    total = rng.choice([100, 120, 150, 200, 240, 300, 400, 500])
    left = Fraction(total * (100 - p), 100) * Fraction(100 - q, 100)
    if left.denominator != 1 or left < 10:
        raise Retry("the remaining distance must be a whole, visible number")
    key = total
    l = left.numerator

    stem = (f"Турист изминал ${p}\\%$ от маршрута през първия ден, а през "
            f"втория ден — ${q}\\%$ от останалата част. Ако му остават още "
            f"${l}$ km, колко километра е целият маршрут?")
    solution = (rf"След първия ден остават ${100 - p}\%$, а след втория — "
                rf"${100 - q}\%$ от тях. Значи "
                rf"${l} = T\cdot\frac{{{100 - p}}}{{100}}\cdot"
                rf"\frac{{{100 - q}}}{{100}}$ и $T = {key}$ km")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=stem, correct_answer=f"{key} km", difficulty="medium",
            solution=solution, signature=f"pct_route:{p}:{q}:{total}",
        )

    cands = []
    for value in (Fraction(l * 100, 100 - p),          # forgot the second day
                  Fraction(l * 100, 100 - q),          # applied q to the whole route
                  Fraction(total - l),                 # gave the distance covered
                  Fraction(2 * l)):
        if value.denominator == 1:
            cands.append(value.numerator)
    if len(cands) < 3:
        raise Retry("not enough whole-number distractors for this draw")

    options, letter = numeric_options(key, cands, rng=rng, positive_only=True,
                                      suffix="km")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"pct_route:{p}:{q}:{total}",
    )


@template("ratio_three_parts", topics=["word_problem_ratio"], kinds=["mc"],
          weight=1.1, band="easy")
def ratio_three_parts(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Three quantities in a given ratio summing to T — the 2024 Q18 shape."""
    parts = rng.choice([(1, 2, 5), (2, 3, 5), (1, 3, 4), (1, 2, 3),
                        (2, 2, 5), (1, 4, 5), (3, 4, 5)])
    unit = rng.choice([4, 5, 6, 8, 10, 12])
    total = sum(parts) * unit
    key = max(parts) * unit

    wrong = [min(parts) * unit, total // len(parts), total - key,
             sum(parts) * unit // max(parts)]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    ratio = " : ".join(str(p) for p in parts)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Три числа се отнасят както ${ratio}$, а сборът им е ${total}$. "
              f"Най-голямото от трите числа е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"Частите са ${sum(parts)}$ и една част е "
                  rf"${total} : {sum(parts)} = {unit}$, "
                  rf"откъдето най-голямото число е ${max(parts)}\cdot {unit} = {key}$"),
        signature=f"ratio3:{parts}:{unit}",
    )


@template("mixture_alloy_addition", topics=["word_problem_mixture"], kinds=["mc"],
          weight=1.1, band="medium")
def mixture_alloy_addition(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Adding pure silver to an alloy to dilute it to a target purity.

    The 2026 Q23 mixture genre reduced to a single multiple-choice step: the
    mass of gold is unchanged, so M·p = (M + x)·q.
    """
    mass = rng.choice([200, 300, 400, 500, 600])
    p = rng.choice([60, 75, 80, 90])
    q = rng.choice([40, 50, 60, 25])
    if q >= p:
        raise Retry("the target purity must be lower than the original")
    added = Fraction(mass * (p - q), q)
    if added.denominator != 1 or added > 3 * mass:
        raise Retry("the added mass must be whole and sensible")
    key = added.numerator

    wrong = [mass * (p - q) // 100, mass * q // p, mass + key, key * 2]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      suffix="g")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Сплав с маса ${mass}$ g съдържа ${p}\\%$ злато. Колко грама "
              f"сребро трябва да се добавят към нея, за да се получи сплав "
              f"с ${q}\\%$ злато?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Златото е ${mass * p // 100}$ g и не се променя. "
                  rf"От ${mass * p // 100} = \left({mass} + x\right)\cdot"
                  rf"\frac{{{q}}}{{100}}$ следва $x = {key}$ g"),
        signature=f"alloy_add:{mass}:{p}:{q}",
    )


# ─── probability written as an expression ────────────────────────────────────

@template("prob_expression_two_colours",
          topics=["probability_expression"], kinds=["mc"], weight=1.1, band="easy")
def prob_expression_two_colours(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x of one colour and k of another — the probability as an expression in x."""
    k = rng.choice([4, 5, 6, 7, 8, 9, 10])
    # The singular feminine is not a suffix rule in Bulgarian — бели → бяла,
    # not бела — so both forms are stored rather than derived.
    first, second, singular = rng.choice([
        ("червени", "сини", "червена"),
        ("бели", "черни", "бяла"),
        ("зелени", "жълти", "зелена"),
        ("сини", "червени", "синя"),
    ])
    correct = rf"$\frac{{x}}{{x + {k}}}$"
    wrongs = [
        rf"$\frac{{{k}}}{{x + {k}}}$",
        rf"$\frac{{x}}{{{k}}}$",
        rf"$\frac{{x + {k}}}{{x}}$",
    ]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В една кутия има $x$ на брой {first} топки и ${k}$ {second} "
              f"топки. Вероятността случайно извадена топка да е {singular} е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"Благоприятните случаи са $x$, а всички възможни — "
                  rf"$x + {k}$, откъдето вероятността е $\frac{{x}}{{x + {k}}}$"),
        signature=f"prob_expr_two:{k}:{first}",
    )


@template("prob_expression_after_removal",
          topics=["probability_expression"], kinds=["mc"], weight=1.0, band="hard")
def prob_expression_after_removal(rng: random.Random, slot: Slot) -> GeneratedItem:
    """n balls, w white, m non-white removed — the 2024 Q20 shape.

    Only the denominator moves: removing non-white balls leaves the count of
    white ones alone. The distractor that subtracts m from the numerator as
    well is the mistake the real item is built around.
    """
    white = rng.choice([5, 6, 8, 10, 12])
    removed = rng.choice([3, 4, 5, 10])
    if removed >= white:
        raise Retry("keep the removed count clearly smaller than the white count")

    correct = rf"$\frac{{{white}}}{{n - {removed}}}$"
    wrongs = [
        rf"$\frac{{{white} - {removed}}}{{n - {removed}}}$",
        rf"$\frac{{{white}}}{{n}}$",
        rf"$\frac{{n - {removed}}}{{{white}}}$",
    ]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В една урна има $n$ топки, ${white}$ от които са бели. "
              f"От урната са извадени ${removed}$ топки, нито една от които "
              f"не е бяла. Вероятността следващата случайно извадена топка "
              f"да е бяла е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"Белите топки остават ${white}$, а всички топки стават "
                  rf"$n - {removed}$, откъдето вероятността е "
                  rf"$\frac{{{white}}}{{n - {removed}}}$"),
        signature=f"prob_expr_removed:{white}:{removed}",
    )
