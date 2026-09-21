"""Probability, and reading charts and tables.

The ministry's 2015 optimisation memo commits explicitly to keeping these:
"запазване на броя на задачите, които тестват уменията на учениците да четат
диаграми и таблици, да извличат информация и да правят косвени изводи по тях".
Every paper in the corpus has at least one, and exactly one probability item in
Part 1, somewhere between positions 6 and 9.

Chart items are the easiest class to generate correctly — the figure is pure
data, so there is no geometry to get wrong — but the *numbers* still have to
behave: a "which month doubled" item is only well posed when exactly one month
doubles, and a mean is only a fair 3-point answer when it comes out whole. Both
are enforced by resampling, not by rounding.
"""
from __future__ import annotations

import random
from fractions import Fraction

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.distractors import (
    bg_number,
    complement_probability,
    numeric_options,
    reciprocal,
    shuffle_options,
)
from app.nvo_gen.registry import GeneratedItem, Retry, template
from app.nvo_gen.scene import bar_chart, data_table, grouped_bar_chart, pie_chart, schematic

_MONTHS = ["януари", "февруари", "март", "април", "май", "юни",
           "юли", "август", "септември", "октомври", "ноември", "декември"]


# ─── probability ─────────────────────────────────────────────────────────────

@template("prob_single_digit_divisible", topics=["probability"], kinds=["mc"], weight=1.3)
def prob_single_digit_divisible(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A single-digit non-negative number divisible by d — the 2026 Q6 shape.

    The trap is the sample space: "едноцифрено неотрицателно" is 0–9, ten
    numbers, and a student who forgets 0 gets 3/9 rather than 4/10.
    """
    d = rng.choice([2, 3, 4, 5])
    favourable = [n for n in range(10) if n % d == 0]
    key = Fraction(len(favourable), 10)

    # A probability greater than 1 is a free elimination, not a distractor —
    # the reciprocal family has to be filtered here rather than offered blind.
    candidates = [
        Fraction(len(favourable) - 1, 9),     # dropped zero from both counts
        complement_probability(key),
        Fraction(len(favourable), 9),
        Fraction(len(favourable) + 1, 10),
        Fraction(len(favourable) - 1, 10),
    ]
    wrong = [c for c in candidates if 0 < c <= 1]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Вероятността произволно избрано едноцифрено неотрицателно число "
              f"да се дели на ${d}$, е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(f"Едноцифрените неотрицателни числа са $10$ на брой, а тези, "
                  f"които се делят на ${d}$, са ${len(favourable)}$: "
                  f"${', '.join(str(n) for n in favourable)}$. "
                  rf"Вероятността е ${bg_number(key)}$"),
        signature=f"prob_digit:{d}",
    )


@template("prob_balls_in_a_box", topics=["probability"], kinds=["mc"], weight=1.2, band="easy")
def prob_balls_in_a_box(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Coloured balls, sometimes asking for the complement — 2022 Q9, 2021 Q9."""
    a = rng.randint(2, 5)
    b = rng.randint(2, 5)
    c = rng.randint(1, 4)
    total = a + b + c
    negate = rng.random() < 0.5
    key = Fraction(total - a, total) if negate else Fraction(a, total)

    candidates = [
        complement_probability(key),
        Fraction(b, total),
        Fraction(c, total),
        Fraction(a, total - a),
        Fraction(a + b, total),
    ]
    wrong = [c for c in candidates if 0 < c < 1]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    # Uppercase НЕ rather than bold markup — the stem is rendered as text with
    # KaTeX for the math, so any HTML here would show up literally.
    ask = ("Каква е вероятността изтегленото топче да НЕ е жълто?"
           if negate else "Каква е вероятността изтегленото топче да е жълто?")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В кутия са поставени ${a}$ жълти, ${b}$ зелени и ${c}$ червени "
              f"топчета. На случаен принцип се изтегля едно топче. {ask}"),
        options=options, correct_answer=letter, difficulty="easy",
        solution=(f"Общо топчетата са ${total}$, а благоприятните са "
                  f"${total - a if negate else a}$, значи вероятността е ${bg_number(key)}$"),
        signature=f"prob_balls:{a}:{b}:{c}:{negate}",
    )


@template("prob_spinner", topics=["probability"], kinds=["mc"], weight=1.0)
def prob_spinner(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A wheel of equal sectors carrying repeated words — the 2024 Q8 shape."""
    words = ["успех", "късмет", "здраве"]
    sectors = rng.choice([6, 8])
    counts = _partition(sectors, len(words), rng)
    target = rng.randrange(len(words))
    key = Fraction(counts[target], sectors)

    candidates = [
        Fraction(1, sectors),
        complement_probability(key),
        Fraction(counts[(target + 1) % len(words)], sectors),
        Fraction(counts[target], sectors - 1),
        Fraction(counts[target] + 1, sectors),
    ]
    wrong = [c for c in candidates if 0 < c < 1]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    labels: list[str] = []
    for word, n in zip(words, counts):
        labels.extend([word] * n)
    rng.shuffle(labels)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Колело е разделено на ${sectors}$ еднакви сектора, във всеки от които "
              f"е написана по една от следните думи: {', '.join(words)}. Колелото е "
              f"завъртяно и след спирането стрелката сочи точно един сектор. Каква е "
              f"вероятността това да е сектор с думата „{words[target]}“?"),
        options=options, correct_answer=letter, difficulty="medium",
        scene=schematic(shape="spinner", labels={"sectors": ",".join(labels)},
                        aria=f"Колело с {sectors} равни сектора с думи"),
        solution=(f"Секторите с „{words[target]}“ са ${counts[target]}$ от общо "
                  f"${sectors}$, значи вероятността е ${bg_number(key)}$"),
        signature=f"prob_spinner:{sectors}:{'-'.join(map(str, counts))}:{target}",
    )


def _partition(total: int, buckets: int, rng: random.Random) -> list[int]:
    """Split `total` into `buckets` positive parts."""
    if total < buckets:
        raise Retry("not enough sectors to go round")
    cuts = sorted(rng.sample(range(1, total), buckets - 1))
    edges = [0, *cuts, total]
    return [edges[i + 1] - edges[i] for i in range(buckets)]


@template("prob_as_expression", topics=["probability_expression"], kinds=["mc"], weight=1.4)
def prob_as_expression(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Probability given symbolically — the 2024 Q20 shape.

    All four options are the same two symbols arranged four ways, so the
    reciprocal family supplies the distractors on its own.
    """
    k = rng.choice([8, 10, 12, 15])
    colour_a, colour_b = rng.choice([("червени", "черни"), ("сини", "жълти"),
                                     ("зелени", "бели")])
    correct = rf"\frac{{n - {k}}}{{n}}"
    wrongs = [rf"\frac{{n}}{{{k}}}", rf"\frac{{{k}}}{{n}}", rf"\frac{{n}}{{n - {k}}}"]
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В кутия има $n$ молива, от които ${k}$ са {colour_a}, а останалите "
              f"са {colour_b}. Вероятността случайно изваден молив да е "
              f"{colour_b[:-1]} се пресмята с израза:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Моливите {colour_b} са $n - {k}$, а всички са $n$, "
                  rf"значи вероятността е ${correct}$"),
        signature=f"prob_expr:{k}:{colour_a}",
    )


# ─── charts ──────────────────────────────────────────────────────────────────

_CHART_VALUES = (5, 10, 15, 20, 25, 30)


def _one_doubling_series(rng: random.Random) -> list[int]:
    """Five bar heights in which exactly one month doubles its predecessor.

    Constructed rather than rejection-sampled. Drawing five values at random
    and retrying until exactly one doubling appears succeeds about a quarter of
    the time, which is fine until it isn't — it failed a whole paper roughly
    once in a thousand. Here the doubling is placed first and every other
    adjacent pair is then repaired, so the draw always succeeds.
    """
    idx = rng.randrange(1, 5)
    base = rng.choice([v for v in _CHART_VALUES if 2 * v in _CHART_VALUES])
    values = [rng.choice(_CHART_VALUES) for _ in range(5)]
    values[idx - 1] = base
    values[idx] = 2 * base

    for j in range(1, 5):
        if j == idx:
            continue
        # Repair any accidental second doubling by moving the later value.
        guard = 0
        while values[j] == 2 * values[j - 1] and guard < 12:
            candidates = [v for v in _CHART_VALUES if v != 2 * values[j - 1]]
            values[j] = rng.choice(candidates)
            guard += 1
        # Moving values[j] can create a doubling with values[j+1]; the loop
        # continues to j+1 next, so that case is handled on the following pass.

    if sum(1 for j in range(1, 5) if values[j] == 2 * values[j - 1]) != 1:
        raise Retry("repair left more than one doubling")
    return values


@template("chart_doubling_and_mean",
          topics=["data_chart"], kinds=["short"], weight=1.4)
def chart_doubling_and_mean(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Bar chart over five months: А) which month doubled Б) the mean.

    The 2026 Q17 item. Well posed only when exactly one month is exactly double
    its predecessor — otherwise part А has two answers — and only fair when the
    mean is a whole number, since the key prints "15", not "15,2".
    """
    if slot.parts != 2:
        raise Retry("this template fills a two-part slot")

    start = rng.randrange(0, 8)
    months = _MONTHS[start:start + 5]
    values = _one_doubling_series(rng)
    idx = next(i for i in range(1, 5) if values[i] == 2 * values[i - 1])
    # Every value is a multiple of 5, so the mean is always whole.
    mean = sum(values) // 5
    thing, unit_label = rng.choice([
        ("апартаменти", "Брой продадени апартаменти"),
        ("велосипеди", "Брой продадени велосипеди"),
        ("абонамента", "Брой нови абонаменти"),
    ])

    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=(f"Фирма продава {thing}. На диаграмата е представен броят на "
              f"{thing}те, продадени през месеците "
              f"{', '.join(months[:-1])} и {months[-1]}."),
        parts=[
            f"А) През кой от месеците продажбите на {thing} нарастват двойно "
            f"спрямо продажбите от предния месец?",
            f"Б) Каква е средната месечна продажба на {thing} за периода "
            f"{months[0]} – {months[-1]}?",
        ],
        correct_answer=[months[idx], str(mean)],
        difficulty="medium",
        scene=bar_chart(categories=months, values=values, y_label=unit_label,
                        y_step=5,
                        aria=(f"Стълбовидна диаграма за месеците {', '.join(months)} "
                              f"със стойности {', '.join(map(str, values))}")),
        solution=(f"А) През {months[idx]}: ${values[idx]} = 2 \\cdot {values[idx - 1]}$. "
                  f"Б) $({' + '.join(map(str, values))}) : 5 = {mean}$"),
        signature=f"chart_double:{'-'.join(map(str, values))}",
    )


@template("chart_pie_sector", topics=["data_chart"], kinds=["mc"], weight=1.3)
def chart_pie_sector(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Read a duration off a pie chart — the 2024 Q19 shape."""
    total_minutes = rng.choice([90, 120, 180, 60])
    a, b = rng.choice([(80, 150), (120, 90), (100, 140), (60, 180)])
    c = 90
    d = 360 - a - b - c
    if d <= 20:
        raise Retry("the remaining sector must be visible")
    key = Fraction(total_minutes * d, 360)
    if key.denominator != 1:
        raise Retry("the answer must be a whole number of minutes")
    key = key.numerator

    labels = ["театрални", "музикални", "танцови", "спортни"]
    wrong = [
        total_minutes * a // 360,
        total_minutes * c // 360,
        key * 2,
        d,
    ]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Училищно тържество е с продължителност {total_minutes} минути. "
              f"По данните от диаграмата продължителността на спортните изпълнения "
              f"в минути е:"),
        options=options, correct_answer=letter, difficulty="medium",
        scene=pie_chart(
            sectors=[(labels[0], a), (labels[1], b), (labels[2], c), (labels[3], d)],
            title="Видове изпълнения",
            aria=(f"Кръгова диаграма с четири сектора: {labels[0]} {a} градуса, "
                  f"{labels[1]} {b} градуса, {labels[2]} {c} градуса, "
                  f"{labels[3]} {d} градуса")),
        solution=(rf"Спортните са ${d}^\circ$ от ${360}^\circ$, значи "
                  rf"$\frac{{{d}}}{{360}} \cdot {total_minutes} = {key}$ минути"),
        signature=f"chart_pie:{total_minutes}:{a}:{b}:{c}",
    )


@template("chart_grouped_ratio", topics=["data_chart"], kinds=["mc"], weight=1.1)
def chart_grouped_ratio(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Two series; find the year with the largest ratio — the 2022 Q7 shape."""
    start = rng.choice([2018, 2019, 2020, 2021])
    years = [str(start + i) for i in range(4)]
    club_a = [rng.choice([16, 20, 24, 28, 32, 36]) for _ in range(4)]
    club_b = [rng.choice([16, 18, 24, 28, 32, 36]) for _ in range(4)]

    ratios = [Fraction(a, b) for a, b in zip(club_a, club_b)]
    best = max(range(4), key=lambda i: ratios[i])
    if sum(1 for r in ratios if r == ratios[best]) != 1:
        raise Retry("the winning year must be unique")

    correct = years[best]
    wrongs = [y for i, y in enumerate(years) if i != best]
    options, letter = shuffle_options(correct, wrongs, rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=("По данните от диаграмата определете годината, в която отношението "
              "на участниците в клуб „Умник“ към участниците в клуб „Атлет“ "
              "е най-голямо."),
        options=options, correct_answer=letter, difficulty="medium",
        scene=grouped_bar_chart(
            categories=years,
            series=[("Клуб Умник", club_a), ("Клуб Атлет", club_b)],
            y_label="Брой участници", y_step=5,
            aria=("Групирана стълбовидна диаграма с два клуба за годините "
                  + ", ".join(years))),
        solution=(f"Отношенията са " +
                  ", ".join(f"${y}: {bg_number(r)}$" for y, r in zip(years, ratios)) +
                  f"; най-голямо е през ${correct}$"),
        signature=f"chart_grouped:{'-'.join(map(str, club_a))}:{'-'.join(map(str, club_b))}",
    )


@template("table_share_of_total", topics=["data_chart"], kinds=["mc"], weight=1.0, band="hard")
def table_share_of_total(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A table of shares expressed in terms of n — the 2025 Q19 shape."""
    total = rng.choice([1200, 1600, 2000, 2400])
    # 0,75n + n/2 + n/4 + n = total  →  n = total / 2.5
    n = Fraction(total * 2, 5)
    if n.denominator != 1:
        raise Retry("n must come out whole")
    n = n.numerator

    key = n
    wrong = [n // 2, n // 4, n * 3 // 4, total - n]
    options, letter = numeric_options(key, wrong, rng=rng, positive_only=True)
    headers = ["фантастика", "детска литература", "техническа литература",
               "художествена литература"]
    rows = [["$75\\%$ от $n$", "$\\frac{n}{2}$", "$\\frac{n}{4}$", "$n$"]]
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В книжарница за един месец са продадени общо {total} книги от видовете: "
              f"художествена литература, детска литература, техническа литература и "
              f"фантастика. В таблицата е представено разпределението на броя продадени "
              f"книги по видове. Колко броя книги художествена литература са продадени "
              f"за този месец?"),
        options=options, correct_answer=letter, difficulty="hard",
        scene=data_table(headers=headers, rows=rows,
                         aria="Таблица с четири вида книги, изразени чрез n"),
        solution=(rf"$0{{,}}75n + \frac{{n}}{{2}} + \frac{{n}}{{4}} + n = {total}$, "
                  rf"откъдето $2{{,}}5n = {total}$ и $n = {n}$"),
        signature=f"table_share:{total}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Band partners for the data-reading position.
#
# The ministry's 2015 memo commits to keeping a chart- or table-reading item in
# every paper, and the corpus bears that out — one or two, never zero. These
# are the short-answer forms: two sub-parts, marked separately, exactly as the
# 2026 Q17 key does it ("2 т.", "3 т.").
# ═════════════════════════════════════════════════════════════════════════════

@template("chart_peak_and_total",
          topics=["data_chart"], kinds=["short"], weight=1.2, band="easy")
def chart_peak_and_total(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Read the tallest bar, then total the series — the two easiest questions
    you can ask of a bar chart, which is what the gentler levels need here."""
    months = ["януари", "февруари", "март", "април", "май", "юни"]
    labels = months[: rng.choice([5, 6])]
    values = [rng.choice([5, 10, 15, 20, 25, 30, 35, 40]) for _ in labels]
    peak = max(values)
    if values.count(peak) != 1:
        raise Retry("the tallest bar must be unique")
    total = sum(values)
    peak_month = labels[values.index(peak)]

    what, unit = rng.choice([
        ("продадени велосипеда", "броя"),
        ("посетители на изложбата", "души"),
        ("издадени читателски карти", "броя"),
    ])
    scene = bar_chart(
        categories=labels, values=values, y_label=unit, y_step=5,
        aria=("Стълбовидна диаграма на " + what + " по месеци: " +
              ", ".join(f"{m} — {v}" for m, v in zip(labels, values))),
    )
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=(f"Диаграмата показва броя на {what} през всеки от месеците."),
        parts=[f"А) През кой месец броят на {what} е най-голям?",
               f"Б) Колко общо са {what} за всички показани месеци?"],
        correct_answer=[peak_month, f"{total} {unit}"],
        difficulty="easy", scene=scene,
        solution=(f"А) Най-високият стълб е за месец {peak_month} — ${peak}$. "
                  f"Б) Сборът на всички стойности е "
                  f"${' + '.join(str(v) for v in values)} = {total}$."),
        signature=f"chart_peak:{'-'.join(map(str, values))}",
    )


@template("table_share_and_difference",
          topics=["data_chart"], kinds=["short"], weight=1.0, band="hard")
def table_share_and_difference(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A table read twice: a percentage of the total, then a difference.

    The percentage part is what makes this the hard member of the topic — the
    numbers are chosen so the share is whole, but the student still has to
    total the column first rather than reading an answer straight off.
    """
    kinds_bg = ["романи", "поезия", "детски книги", "енциклопедии"]
    # Pick counts that total to 100·k, so the requested share is a whole percent.
    unit = rng.choice([2, 4, 5, 10])
    parts = rng.sample([10, 15, 20, 25, 30], 4)
    if sum(parts) != 100:
        parts = [10, 20, 30, 40]
        rng.shuffle(parts)
    counts = [p * unit for p in parts]
    total = sum(counts)

    idx = rng.randrange(4)
    other = (idx + 1) % 4
    share = counts[idx] * 100 // total
    diff = abs(counts[idx] - counts[other])
    if diff == 0:
        raise Retry("the two categories must differ")

    scene = data_table(
        headers=["Вид литература", "Брой книги"],
        rows=[[k, str(c)] for k, c in zip(kinds_bg, counts)],
        aria=("Таблица с броя книги по вид: " +
              ", ".join(f"{k} — {c}" for k, c in zip(kinds_bg, counts))),
    )
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=("Таблицата показва броя на книгите в един училищен "
              "библиотечен фонд по вид литература."),
        parts=[f"А) Колко процента от всички книги са {kinds_bg[idx]}?",
               f"Б) С колко броя {kinds_bg[idx]} са повече или по-малко "
               f"от {kinds_bg[other]}?"],
        correct_answer=[f"{share}%", f"{diff} броя"],
        difficulty="hard", scene=scene,
        solution=(f"А) Всички книги са ${total}$, а {kinds_bg[idx]} са "
                  f"${counts[idx]}$, откъдето "
                  rf"$\frac{{{counts[idx]}}}{{{total}}}\cdot 100\% = {share}\%$. "
                  f"Б) Разликата е $\\left|{counts[idx]} - {counts[other]}\\right| "
                  f"= {diff}$."),
        signature=f"table_share:{'-'.join(map(str, counts))}:{idx}:{other}",
    )
