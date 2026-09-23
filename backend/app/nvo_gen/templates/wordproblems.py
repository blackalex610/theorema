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
    is_clean_decimal,
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
    """Two people working together — the 2026 Q8 shape (30 and 45 minutes → 18).

    Any pair with a whole joint time. The easy levels keep the times small and
    one a multiple of the other; the harder ones use pairs such as 36 and 45,
    where the common denominator has to be found.
    """
    lo, hi = slot.profile.tier((10, 40), (10, 60), (10, 90), (20, 120))
    pool = [(a, b) for a in range(lo, hi) for b in range(a + 2, hi + 1)
            if (a * b) % (a + b) == 0 and (a % 2 == 0 or a % 5 == 0)]
    if slot.profile.tier(True, True, False, False):
        pool = [(a, b) for a, b in pool if b % a == 0] or pool
    a, b = rng.choice(pool)
    key = a * b // (a + b)

    name_a, name_b = rng.sample(_NAMES_M, 2)
    first, second, joint = rng.choice(_CHORES)

    wrong = [(a + b) // 2, a + b, b - a, min(a, b) // 2, key + 3]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
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


_GROUP_PAIRS = [
    # (sentence with {a} {num}/{den}, the asked total)
    ("Във фирма работят {a} жени, които са {f} от броя на мъжете.",
     "Общият брой на работещите мъже и жени във фирмата е:"),
    ("В училищен лагер има {a} момичета, които са {f} от броя на момчетата.",
     "Общият брой на децата в лагера е:"),
    ("В приют има {a} котки, които са {f} от броя на кучетата.",
     "Общият брой на котките и кучетата в приюта е:"),
    ("В библиотека има {a} речника, които са {f} от броя на енциклопедиите.",
     "Общият брой на речниците и енциклопедиите е:"),
]


@template("percent_part_of_whole",
          topics=["percent_word_problem", "word_problem_ratio"], kinds=["mc"], weight=1.0)
def percent_part_of_whole(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A group is a fraction of another; find the combined total. 2025 Q16."""
    den = rng.randint(3, 9)
    num = rng.randint(1, den - 1)
    if math.gcd(num, den) != 1:
        raise Retry("a reduced fraction")
    a = num * rng.randint(3, 15)
    if a > 60 or a < 6:
        raise Retry("a group size that reads naturally")
    other = a * den // num
    key = a + other

    wrong = [other, other - a, a * num // den + a if (a * num) % den == 0 else key + den,
             other * 2]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    told, asked = rng.choice(_GROUP_PAIRS)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=told.format(a=a, f=rf"$\frac{{{num}}}{{{den}}}$") + " " + asked,
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Другата група е ${a} : \frac{{{num}}}{{{den}}} = {other}$, "
                  rf"а общо са ${other} + {a} = {key}$"),
        signature=f"pct_part:{num}:{den}:{a}:{told[:12]}",
    )


# ─── mixture ─────────────────────────────────────────────────────────────────

_BLENDS = [
    # (liquid, property, property definite)
    ("прясно мляко", "масленост", "маслеността"),
    ("солен разтвор", "концентрация на сол", "концентрацията на сол"),
    ("оцет", "киселинност", "киселинността"),
    ("плодов сироп", "захарно съдържание", "захарното съдържание"),
]


@template("mixture_fat_content",
          topics=["word_problem_mixture"], kinds=["mc"], weight=1.3, band="hard")
def mixture_fat_content(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Blending two batches to a target percentage — the 2024 Q17 shape (milk fat)."""
    v1 = rng.randint(1, 6)
    v2 = rng.randint(1, 5)
    v_total = v1 + v2
    p1 = Fraction(rng.randint(10, 45), 10)            # 1,0 % … 4,5 %
    p_mix = Fraction(rng.randint(12, 60), 10)
    p2 = (v_total * p_mix - v1 * p1) / v2
    if p2 <= 0 or p2 > 12 or p2 == p1 or not is_clean_decimal(p2, places=1):
        raise Retry("second concentration must be a clean small percentage")

    wrong = [p_mix, p1, p2 + 1, p2 / 2]
    options, letter = numeric_options(
        p2, [w for w in wrong if is_clean_decimal(Fraction(w), places=2)], rng=rng,
        positive_only=True, fmt=lambda v: f"{bg_decimal(Fraction(v), places=2)}\\%")
    liquid, prop, prop_def = rng.choice(_BLENDS)
    litre = lambda n: "литър" if n == 1 else "литра"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Колко процента е {prop_def} на {liquid}, ако при смесването на "
              f"${v2}$ {litre(v2)} от него с ${v1}$ {litre(v1)} {liquid} с {prop} "
              f"${bg_decimal(p1, places=1)}\\%$ се получават ${v_total}$ литра {liquid} "
              f"с {prop} ${bg_decimal(p_mix, places=1)}\\%$?"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"${v1} \cdot {bg_decimal(p1, places=1)} + {v2}x = "
                  rf"{v_total} \cdot {bg_decimal(p_mix, places=1)}$, "
                  rf"откъдето $x = {bg_decimal(p2, places=1)}\%$"),
        signature=f"mix_fat:{v1}:{v2}:{p1}:{p_mix}:{liquid}",
    )


_THREE_INGREDIENTS = [
    # (sentence opening, names, unit, the whole)
    ("При производството на козметично изделие се смесват три течни съставки $X$, $Y$ и $Z$",
     ("$X$", "$Y$", "$Z$"), "ml", "милилитра", "{v} ml от козметичното изделие"),
    ("За бетонов разтвор се смесват цимент, пясък и чакъл",
     ("цимента", "пясъка", "чакъла"), "kg", "килограма", "{v} kg бетонов разтвор"),
    ("Торова смес се приготвя от азотен, фосфорен и калиев тор",
     ("азотния тор", "фосфорния тор", "калиевия тор"), "kg", "килограма", "{v} kg торова смес"),
    ("За плодова салата се смесват ябълки, круши и банани",
     ("ябълките", "крушите", "бананите"), "g", "грама", "{v} g плодова салата"),
]


@template("mixture_three_part_ratio",
          topics=["word_problem_ratio", "word_problem_mixture"], kinds=["mc"], weight=1.2)
def mixture_three_part_ratio(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Three ingredients in ratio a : b : c within a fixed total — 2024 Q18."""
    a, b, c = (rng.randint(1, 7) for _ in range(3))
    if math.gcd(math.gcd(a, b), c) != 1 or len({a, b, c}) < 2:
        raise Retry("a reduced ratio that is not all equal")
    parts = a + b + c
    unit = rng.choice([5, 8, 10, 12, 15, 20, 25, 30, 40, 50])
    volume = parts * unit
    which = rng.randrange(3)
    key = (a, b, c)[which] * unit
    opening, names, unit_sym, unit_word, whole = rng.choice(_THREE_INGREDIENTS)

    wrong = [v * unit for i, v in enumerate((a, b, c)) if i != which] + [unit, key * 2]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{opening}, съответно в отношение ${a} : {b} : {c}$. "
              f"Колко {unit_word} е количеството на {names[which]} в "
              f"{whole.format(v=volume)}?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Частите са ${parts}$, една част е ${volume} : {parts} = {unit}$ "
                  rf"{unit_sym}, търсеното количество е ${(a, b, c)[which]} \cdot {unit} = "
                  rf"{key}$ {unit_sym}"),
        signature=f"ratio3m:{a}:{b}:{c}:{volume}:{which}:{opening[:10]}",
    )


# ─── units ───────────────────────────────────────────────────────────────────

_COVERAGE = [
    # (what is spread, per what, the surface, the verb)
    ("За боядисване на $1$ m$^2$ стена се използват {g} грама боя.",
     "Колко килограма боя е необходима за боядисване на правоъгълна стена с размери ${w}$ m и ${h}$ m?"),
    ("За наторяване на $1$ m$^2$ градина са нужни {g} грама тор.",
     "Колко килограма тор са нужни за правоъгълна леха с размери ${w}$ m и ${h}$ m?"),
    ("За засяване на $1$ m$^2$ тревна площ се използват {g} грама семена.",
     "Колко килограма семена са нужни за правоъгълна поляна с размери ${w}$ m и ${h}$ m?"),
    ("За лепене на $1$ m$^2$ плочки се използват {g} грама лепило.",
     "Колко килограма лепило е нужно за правоъгълен под с размери ${w}$ m и ${h}$ m?"),
]


@template("units_paint_coverage",
          topics=["word_problem_units"], kinds=["mc"], weight=1.2)
def units_paint_coverage(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Grams per m² over a rectangle, answered in kg — the 2024 Q9 shape.

    The whole item is the gram-to-kilogram step, so the off-by-a-factor family
    supplies the distractors, with the perimeter-for-area slip beside them.
    """
    grams = rng.choice(range(100, 451, 10))
    w = rng.randint(3, 9)
    h = rng.randint(3, 12)
    if w == h:
        raise Retry("a rectangle that is not a square")
    area = w * h
    key = Fraction(grams * area, 1000)
    if not is_clean_decimal(key, places=2):
        raise Retry("answer must print as a short decimal")

    wrong = [key * 10, key / 10, Fraction(grams * 2 * (w + h), 1000), key * 2]
    options, letter = numeric_options(
        key, [v for v in wrong if is_clean_decimal(Fraction(v), places=2)], rng=rng,
        positive_only=True, fmt=lambda v: bg_decimal(Fraction(v), places=2))
    told, asked = rng.choice(_COVERAGE)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=told.format(g=grams) + " " + asked.format(w=w, h=h),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Лицето е ${area}$ m$^2$, нужни са ${grams} \cdot {area} = "
                  rf"{grams * area}$ g $= {bg_decimal(key, places=2)}$ kg"),
        signature=f"units_paint:{grams}:{w}:{h}",
    )


@template("units_map_scale", topics=["word_problem_units"], kinds=["mc"], weight=1.1, band="easy")
def units_map_scale(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Map distance to real distance — 2021 Q18 (a reference distance) and 2023
    Q6 (a scale written 1 : n). Both forms are drawn."""
    if rng.random() < 0.5:
        cm_ref = rng.randint(2, 9)
        km_per_cm = rng.choice([5, 10, 15, 20, 25, 40, 50, 60, 75, 80, 100, 120, 150, 200, 250])
        km_ref = cm_ref * km_per_cm
        cm_q = rng.randint(2, 12)
        if cm_q == cm_ref:
            raise Retry("the asked distance should differ from the reference")
        key = cm_q * km_per_cm
        stem = (f"На географска карта на ${cm_ref}$ cm съответстват ${km_ref}$ km "
                f"действително разстояние. Ако разстоянието между два града на "
                f"картата е ${cm_q}$ cm, то действителното разстояние между тях "
                f"в километри е:")
        wrong = [km_per_cm, km_ref, key * 10, key + km_per_cm]
        sig = f"units_scale:{cm_ref}:{km_per_cm}:{cm_q}"
    else:
        n = rng.choice([50_000, 100_000, 200_000, 250_000, 500_000, 1_000_000, 2_000_000])
        cm_q = Fraction(rng.choice(range(15, 121, 5)), 10)          # 1,5 … 12 cm
        key = cm_q * n / 100_000                                      # km
        if not is_clean_decimal(key, places=1):
            raise Retry("real distance must be a short decimal")
        n_tex = f"{n:,}".replace(",", r"\,")                       # 500\,000
        stem = (f"Мащабът на една карта е $1 : {n_tex}$. Разстоянието между две селища "
                f"на картата е ${bg_decimal(cm_q, places=1)}$ cm. Действителното "
                f"разстояние между тях в километри е:")
        wrong = [key * 10, key / 10, key * 2, key + 10]
        sig = f"units_ratio:{n}:{cm_q}"
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      fmt=lambda v: bg_decimal(Fraction(v), places=1),
                                      suffix="km")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="easy",
        solution=rf"Действителното разстояние е ${bg_decimal(Fraction(key), places=1)}$ km",
        signature=sig,
    )


@template("units_speed_difference",
          topics=["word_problem_units"], kinds=["mc"], weight=1.0)
def units_speed_difference(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two speeds in different units — the 2023 Q7 shape (m/s against m/min)."""
    who = rng.choice([("велосипедист", "велосипедист"), ("бегач", "бегач"),
                      ("скейтър", "скейтър"), ("кънкьор", "кънкьор")])
    v1 = rng.randint(slot.profile.tier(3, 4, 4, 5), slot.profile.tier(8, 12, 22, 25))
    delta_tenths = rng.choice([2, 4, 5, 6, 8, 10, 12, 15, 16, 20])
    v2 = Fraction(v1 * 10 + delta_tenths, 10)
    metres_per_minute = v2 * 60
    if metres_per_minute.denominator != 1:
        raise Retry("distance per minute must be a whole number of metres")
    key = v2 - v1

    wrong = [v2, v1, key * 10, key + v1]
    options, letter = numeric_options(
        key, wrong, rng=rng, positive_only=True,
        fmt=lambda v: bg_decimal(Fraction(v), places=2), suffix="m/s")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Един {who[0]} се движи със скорост ${v1}$ m/s, а друг {who[1]} "
              f"изминава ${metres_per_minute.numerator}$ m за $1$ минута. "
              f"С колко метра в секунда вторият е по-бърз от първия?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Вторият се движи с ${metres_per_minute.numerator} : 60 = "
                  rf"{bg_decimal(v2, places=2)}$ m/s, а разликата е "
                  rf"${bg_decimal(key, places=2)}$ m/s"),
        signature=f"units_speed:{who[0]}:{v1}:{delta_tenths}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Band partners for the word-problem and probability positions.
# ═════════════════════════════════════════════════════════════════════════════

#: Every pair (a, b), a < b ≤ 60, whose joint time ab/(a + b) is whole.
_WHOLE_JOINT_PAIRS = [(a, b) for b in range(3, 61) for a in range(2, b)
                      if (a * b) % (a + b) == 0]

_TWO_MACHINES = [
    # (first does it in {a}, second in {b}, together …, unit)
    ("Първата тръба напълва един басейн за ${a}$ {u}, а втората — за ${b}$ {u}.",
     "За колко {u} ще напълнят басейна двете тръби заедно?"),
    ("Една помпа изпразва резервоар за ${a}$ {u}, а друга — за ${b}$ {u}.",
     "За колко {u} двете помпи заедно ще изпразнят резервоара?"),
    ("Един принтер отпечатва поръчка за ${a}$ {u}, а друг принтер — за ${b}$ {u}.",
     "За колко {u} ще отпечатат поръчката двата принтера заедно?"),
    ("Един комбайн ожънва нива за ${a}$ {u}, а друг комбайн — за ${b}$ {u}.",
     "За колко {u} ще ожънат нивата двата комбайна заедно?"),
    ("Едната машина измива съдовете в ресторант за ${a}$ {u}, а другата — за ${b}$ {u}.",
     "За колко {u} ще ги измият двете машини заедно?"),
    ("Един кран пълни цистерна за ${a}$ {u}, а втори кран — за ${b}$ {u}.",
     "За колко {u} ще я напълнят двата крана заедно?"),
]


@template("work_rate_pipes", topics=["work_rate"], kinds=["mc"], weight=1.1,
          band="easy")
def work_rate_pipes(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two machines on one job — the joint-rate identity of 2026 Q8 without people.

    Seven hand-picked pairs and one swimming pool became every pair up to 60
    whose joint time is whole, in six settings. The level decides how big the
    numbers are, which is how obvious the common denominator is.
    """
    pool = [p for p in _WHOLE_JOINT_PAIRS
            if p[1] <= slot.profile.tier(12, 24, 40, 60) and p[1] >= slot.profile.tier(3, 4, 6, 12)]
    a, b = rng.choice(pool)
    key = a * b // (a + b)
    unit = rng.choice(["часа", "минути"]) if b > 12 else "часа"

    wrong = [(a + b) // 2, a + b, b - a, max(key - 1, 1), key + 2]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    told, asked = rng.choice(_TWO_MACHINES)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=told.format(a=a, b=b, u=unit) + " " + asked.format(u=unit),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"За единица време заедно вършат "
                  rf"$\frac{{1}}{{{a}}} + \frac{{1}}{{{b}}} = \frac{{1}}{{{key}}}$ "
                  rf"от работата, значи им трябват ${key}$ {unit}"),
        signature=f"work_pipes:{a}:{b}",
    )


@template("work_rate_second_worker", topics=["work_rate"], kinds=["mc"], weight=1.0,
          band="hard")
def work_rate_second_worker(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Given one worker's time and the joint time, find the other's.

    The joint-rate identity run backwards, which is the version students get
    wrong: 1/b = 1/t − 1/a, not b = a − t. That subtraction is offered first.
    The stem used to read „Заедно с Иван те подредят стаята за 2 часа” — the
    subjunctive where the future belongs; it now says „ще подредят”.
    """
    pairs = [(a, t) for a in range(4, 61) for t in range(2, a)
             if (a * t) % (a - t) == 0 and a * t // (a - t) <= 90]
    a, t = rng.choice(pairs)
    key = a * t // (a - t)
    unit = "часа" if a <= 12 else rng.choice(["часа", "минути"])

    name_a, name_b = rng.sample(_NAMES_M, 2)
    first, _second_txt, joint = rng.choice(_CHORES)

    wrong = [a - t, a + t, 2 * t, a, key + t]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{name_a} сам може да {first} за ${a}$ {unit}. Ако работи заедно с "
              f"{name_b}, двамата ще {joint} за ${t}$ {unit}. За колко {unit} "
              f"{name_b} би свършил същата работа сам?"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"$\frac{{1}}{{{t}}} - \frac{{1}}{{{a}}} = "
                  rf"\frac{{1}}{{{key}}}$, значи вторият сам работи ${key}$ {unit} "
                  rf"(а не ${a - t}$ — времената не се изваждат)"),
        signature=f"work_second:{a}:{t}:{unit}",
    )


@template("percent_discount_price",
          topics=["percent_word_problem"], kinds=["short", "mc"], weight=1.1,
          band="easy")
def percent_discount_price(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A single p% discount off a marked price — one step, no remainder."""
    base = rng.choice([40, 60, 80, 120, 150, 200, 250, 300])
    pct = rng.choice([10, 20, 25, 50, 40])
    if base * pct % 100:
        raise Retry("the discount must be a whole number of euros")
    key = base * (100 - pct) // 100

    # The indefinite article agrees with the noun's gender and is not derivable
    # from the noun, so it is stored beside it — "едно яке" but "един велосипед".
    article, goods = rng.choice([
        ("едно", "яке"), ("един", "чифт обувки"), ("една", "раница"),
        ("един", "велосипед"), ("един", "часовник"), ("една", "тениска"),
    ])
    opening = f"Цената на {article} {goods} е ${base}$ евро."
    solution = (rf"Намалението е ${base * pct // 100}$ евро, а новата цена "
                rf"${base} - {base * pct // 100} = {key}$ евро.")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"{opening} Намерете новата цена при намаление от ${pct}\\%$.",
            correct_answer=f"{key} евро",
            difficulty="easy", solution=solution,
            signature=f"pct_discount:{base}:{pct}",
        )

    stem = f"{opening} При намаление от ${pct}\\%$ новата цена е:"

    wrong = [base * pct // 100, base * (100 + pct) // 100, base - pct,
             base * (100 - pct) // 200]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True,
                                      suffix="евро")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="easy",
        solution=solution, signature=f"pct_discount:{base}:{pct}",
    )


_TWO_STAGES = [
    # (first stage, second stage, what is left, unit, the whole)
    ("Турист изминал ${p}\\%$ от маршрута през първия ден, а през втория ден — "
     "${q}\\%$ от останалата част.", "Ако му остават още ${l}$ km, колко километра е целият маршрут?",
     "km"),
    ("Велосипедист изминал ${p}\\%$ от трасето преди обяд, а след обяд — ${q}\\%$ "
     "от остатъка.", "Ако му остават още ${l}$ km, колко километра е цялото трасе?", "km"),
    ("Ученик прочел ${p}\\%$ от страниците на една книга в събота, а в неделя — "
     "${q}\\%$ от останалите.", "Ако са му останали още ${l}$ страници, колко страници има книгата?",
     "страници"),
    ("Работници боядисали ${p}\\%$ от една ограда през първия ден, а през втория — "
     "${q}\\%$ от остатъка.", "Ако остават небоядисани още ${l}$ m, колко метра е оградата?",
     "m"),
]


@template("percent_of_route_two_days",
          topics=["percent_word_problem"], kinds=["short", "mc"], weight=1.2,
          band="medium")
def percent_of_route_two_days(rng: random.Random, slot: Slot) -> GeneratedItem:
    """p% of a whole, then q% of the *remainder*, L left — the 2025 Q18 shape.

    The whole item is that the second percentage is taken of what is left, not
    of the whole — so the distractor built from (100 − p − q)% is the one that
    catches the misreading.
    """
    p = rng.choice(range(10, 71, 5))
    q = rng.choice(range(10, 71, 5))
    total = rng.choice(range(60, 801, 20))
    left = Fraction(total * (100 - p), 100) * Fraction(100 - q, 100)
    if left.denominator != 1 or left < 10:
        raise Retry("the remaining amount must be a whole, visible number")
    key = total
    l = left.numerator
    told, asked, unit = rng.choice(_TWO_STAGES)
    stem = told.format(p=p, q=q) + " " + asked.format(l=l)
    solution = (rf"След първия етап остават ${100 - p}\%$, а след втория — "
                rf"${100 - q}\%$ от тях. Значи "
                rf"${l} = T\cdot\frac{{{100 - p}}}{{100}}\cdot"
                rf"\frac{{{100 - q}}}{{100}}$ и $T = {key}$")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=stem, correct_answer=f"{key} {unit}", difficulty="medium",
            solution=solution, signature=f"pct_route:{p}:{q}:{total}:{unit}",
        )

    cands = []
    for value in (Fraction(l * 100, 100 - p),
                  Fraction(l * 100, 100 - q),
                  Fraction(l * 100, 100 - p - q) if p + q < 100 else Fraction(0),
                  Fraction(total - l),
                  Fraction(2 * l)):
        if value.denominator == 1 and value > 0 and value != key:
            cands.append(value.numerator)
    if len(cands) < 3:
        raise Retry("not enough whole-number distractors for this draw")

    options, letter = numeric_options(key, cands, rng=rng, positive_only=True,
                                      suffix=unit if unit != "страници" else "")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem, options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"pct_route:{p}:{q}:{total}:{unit}",
    )


_THREE_WAY = [
    # (setting with {r} {t}, question for largest/smallest, unit)
    ("Три числа се отнасят както ${r}$, а сборът им е ${t}$.",
     ("Най-голямото от трите числа е:", "Най-малкото от трите числа е:"), ""),
    ("Трима приятели разделили ${t}$ евро в отношение ${r}$.",
     ("Колко евро е най-голямата част?", "Колко евро е най-малката част?"), " евро"),
    ("Три паралелки събрали общо ${t}$ kg хартия за рециклиране в отношение ${r}$.",
     ("Колко килограма е събрала паралелката с най-много хартия?",
      "Колко килограма е събрала паралелката с най-малко хартия?"), " kg"),
]


@template("ratio_three_parts", topics=["word_problem_ratio"], kinds=["mc"],
          weight=1.1, band="easy")
def ratio_three_parts(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Three quantities in a given ratio summing to T — the 2024 Q18 shape."""
    parts = sorted(rng.sample(range(1, 10), 3))
    if math.gcd(math.gcd(*parts[:2]), parts[2]) != 1:
        raise Retry("a reduced ratio")
    rng.shuffle(parts)
    unit = rng.choice(slot.profile.tier([2, 5, 10], [4, 5, 6, 10, 12], list(range(3, 26)),
                                        list(range(12, 41))))
    total = sum(parts) * unit
    largest = rng.random() < 0.6
    key = (max(parts) if largest else min(parts)) * unit

    wrong = [(min(parts) if largest else max(parts)) * unit, total // 3, total - key,
             sorted(parts)[1] * unit]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    ratio = " : ".join(str(p) for p in parts)
    setting, questions, _unit = rng.choice(_THREE_WAY)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=setting.format(r=ratio, t=total) + " " + questions[0 if largest else 1],
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"Частите са ${sum(parts)}$ и една част е "
                  rf"${total} : {sum(parts)} = {unit}$, "
                  rf"откъдето търсената е ${(max(parts) if largest else min(parts))}\cdot "
                  rf"{unit} = {key}$"),
        signature=f"ratio3:{parts}:{unit}:{largest}:{setting[:8]}",
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

#: (plural, plural, singular of the first, object plural, object is feminine)
_TWO_KINDS = [
    ("червени", "сини", "червена", "синя", "топки"),
    ("бели", "черни", "бяла", "черна", "топки"),
    ("зелени", "жълти", "зелена", "жълта", "топки"),
    ("шоколадови", "плодови", "шоколадов", "плодов", "бонбона"),
    ("сини", "червени", "синя", "червена", "химикалки"),
    ("ябълкови", "портокалови", "ябълков", "портокалов", "сока"),
]


@template("prob_expression_two_colours",
          topics=["probability_expression"], kinds=["mc"], weight=1.1, band="easy")
def prob_expression_two_colours(rng: random.Random, slot: Slot) -> GeneratedItem:
    """x of one kind and k of another — the probability as an expression in x,
    asked of either kind. The singular is stored, not derived (бели → бяла)."""
    k = rng.randint(2, 30)
    first, second, one_first, one_second, things = rng.choice(_TWO_KINDS)
    ask_first = rng.random() < 0.6
    num = "x" if ask_first else str(k)
    correct = rf"$\frac{{{num}}}{{x + {k}}}$"
    other = str(k) if ask_first else "x"
    wrongs = [rf"$\frac{{{other}}}{{x + {k}}}$", rf"$\frac{{x}}{{{k}}}$" if ask_first else rf"$\frac{{{k}}}{{x}}$",
              rf"$\frac{{x + {k}}}{{{num}}}$"]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    what = one_first if ask_first else one_second
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В една кутия има $x$ на брой {first} {things} и ${k}$ {second} "
              f"{things}. Вероятността случайно изваден{'а' if things in ('топки', 'химикалки') else ''} "
              f"{'топка' if things == 'топки' else 'химикалка' if things == 'химикалки' else 'бонбон' if things == 'бонбона' else 'сок'} "
              f"да е {what} е:"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(rf"Благоприятните случаи са ${num}$, а всички възможни — "
                  rf"$x + {k}$, откъдето вероятността е ${correct[1:-1]}$"),
        signature=f"prob_expr_two:{k}:{first}:{things}:{ask_first}",
    )


@template("prob_expression_after_removal",
          topics=["probability_expression"], kinds=["mc"], weight=1.0, band="hard")
def prob_expression_after_removal(rng: random.Random, slot: Slot) -> GeneratedItem:
    """n balls, w white, m removed — the 2024 Q20 shape.

    If none of the removed balls is white, only the denominator moves; if all of
    them are, both do. Each form's distractor is the other form's answer, which
    is exactly the misreading the real item is built around.
    """
    white = rng.randint(4, 20)
    removed = rng.randint(2, 12)
    removed_white = rng.random() < 0.35
    if removed_white and removed >= white:
        raise Retry("cannot remove more white balls than there are")
    colour, colour_sg, colour_pl = rng.choice([("бели", "бяла", "бели"), ("червени", "червена", "червени"),
                                               ("зелени", "зелена", "зелени")])
    # numerators printed computed, as a student would write them
    num_ok = f"{white - removed}" if removed_white else f"{white}"
    correct = rf"$\frac{{{num_ok}}}{{n - {removed}}}$"
    if not removed_white and removed >= white:
        raise Retry("the „w − m” distractor would be zero or negative")
    other_num = f"{white}" if removed_white else f"{white - removed}"
    wrongs = [
        rf"$\frac{{{other_num}}}{{n - {removed}}}$",
        rf"$\frac{{{white}}}{{n}}$",
        rf"$\frac{{n - {removed}}}{{{white}}}$",
    ]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    which = f"всичките са {colour_pl}" if removed_white else f"нито една от които не е {colour_sg}"
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В една урна има $n$ топки, ${white}$ от които са {colour}. "
              f"От урната са извадени ${removed}$ топки, {which}. Вероятността "
              f"следващата случайно извадена топка да е {colour_sg} е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"Топките, които са {colour}, стават ${num_ok}$, а всички топки — "
                  rf"$n - {removed}$, откъдето вероятността е ${correct[1:-1]}$"),
        signature=f"prob_expr_removed:{white}:{removed}:{removed_white}:{colour}",
    )


