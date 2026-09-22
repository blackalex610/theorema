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
from app.nvo_gen.scene import (
    bar_chart,
    data_table,
    grouped_bar_chart,
    line_graph,
    pie_chart,
    schematic,
)

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


# ─── journey graphs ──────────────────────────────────────────────────────────
# The distance-against-time plot the 2015 and 2016 papers print: a leg, a flat
# stretch where the traveller rested, another leg. Unlike a plane figure this
# is drawn to scale on purpose -- the student is asked to read values off it,
# so the scale notice does not apply and the renderer maps data coordinates
# faithfully.


def _axis(span: int, *, max_ticks: int = 7) -> tuple[int, int]:
    """Pick a tick step and an axis end that keep the numbers readable.

    A 55-minute journey stepped by 5 prints twelve labels along 250 pixels,
    which is unreadable at exam size. Widening the step until the labels fit,
    then rounding the axis out to land on one, is what the papers do.
    """
    for step in (5, 10, 15, 20, 30, 60):
        end = span + (-span % step or step)
        if end // step <= max_ticks:
            return step, end
    return 60, span + (-span % 60 or 60)


@template("chart_journey_average_speed",
          topics=["data_chart"], kinds=["mc", "short"], weight=1.2, band="medium")
def chart_journey_average_speed(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A cyclist rides, rests, rides again; find the average speed overall.

    The trap the distractors are built around is dividing by the *moving* time
    instead of the elapsed time. A student who ignores the flat stretch gets a
    plausible, wrong, larger number — which is exactly the misreading the flat
    stretch is in the graph to test.
    """
    leg1 = rng.choice(slot.profile.tier([10, 15], [10, 15, 20], [10, 12, 15, 20],
                                        [9, 12, 14, 18, 21]))
    rest = rng.choice(slot.profile.tier([10], [5, 10], [5, 10, 15], [5, 8, 10, 12, 15]))
    leg2 = rng.choice(slot.profile.tier([10, 15], [10, 15, 20], [10, 15, 20, 25],
                                        [9, 12, 16, 18, 24]))
    d1 = rng.choice([2, 3, 4])
    d2 = d1 + rng.choice([1, 2, 3])

    total_min = leg1 + rest + leg2
    if (d2 * 60) % total_min:
        raise Retry("the average speed must be a whole number of km/h")
    key = d2 * 60 // total_min
    if not 8 <= key <= 30:
        raise Retry("the average speed must be plausible for a cyclist")

    moving = leg1 + leg2
    trap = Fraction(d2 * 60, moving)                       # ignored the rest

    # Axis ranges are rounded out to the tick so the last gridline is the edge.
    x_step, x_max = _axis(total_min)
    y_step = 1
    y_max = d2 + 1

    scene = line_graph(
        series=[[(0, 0), (leg1, d1), (leg1 + rest, d1), (total_min, d2)]],
        x_range=(0, x_max), y_range=(0, y_max),
        x_step=x_step, y_step=y_step,
        x_label="min", y_label="km", grid=True,
        aria=(f"Графика на изминат път в километри спрямо времето в минути: "
              f"изкачване до {d1} km за {leg1} минути, хоризонтален участък "
              f"{rest} минути и изкачване до {d2} km на {total_min}-ата минута"),
    )

    stem = ("Графиката показва изминатия път на велосипедист. "
            "Средната му скорост за цялото време на движение по маршрута")
    solution = (rf"Общият изминат път е ${d2}$ km за ${total_min}$ min $= "
                rf"\frac{{{total_min}}}{{60}}$ h. Средната скорост е "
                rf"$\frac{{{d2}}}{{{total_min}/60}} = {key}$ km/h. Почивката се "
                rf"включва във времето — тя не се изважда.")

    if slot.kind == "short":
        # The short slot is worth two marks then three, so it asks the reading
        # and the computation separately — which is also the kinder order: a
        # student who misreads the flat stretch loses the first mark, not both.
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=("Графиката показва изминатия път на велосипедист, който по "
                  "време на маршрута си е почивал веднъж."),
            parts=["А) Колко минути е почивал велосипедистът?",
                   "Б) Каква е средната му скорост за цялото време по маршрута?"],
            correct_answer=[f"{rest} min", f"{key} km/h"],
            difficulty="medium", scene=scene, solution=solution,
            signature=f"journey:{leg1}:{rest}:{leg2}:{d2}",
        )

    candidates = [int(trap) if trap.denominator == 1 else key + 2,
                  key + 1, key - 1, d2 * 60 // leg1 if leg1 else key + 3, key * 2]
    options, letter = numeric_options(key, candidates, rng=rng,
                                      positive_only=True, suffix=r"\ \text{km/h}")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem + " е:", options=options, correct_answer=letter,
        difficulty="medium", scene=scene, solution=solution,
        signature=f"journey:{leg1}:{rest}:{leg2}:{d2}",
    )


@template("chart_journey_rest_length",
          topics=["data_chart"], kinds=["mc", "short"], weight=1.0, band="easy")
def chart_journey_rest_length(rng: random.Random, slot: Slot) -> GeneratedItem:
    """How long was the rest — the flat stretch read straight off the graph.

    Deliberately an easy item: the whole skill is knowing that a horizontal
    stretch on a distance-time plot means the distance is not changing.
    """
    leg1 = rng.choice(slot.profile.tier([10, 15], [10, 15, 20], [10, 15, 20, 25],
                                        [8, 12, 16, 18, 24]))
    rest = rng.choice(slot.profile.tier([10, 15], [5, 10, 15], [5, 10, 15, 20],
                                        [4, 6, 8, 12, 14, 18]))
    leg2 = rng.choice(slot.profile.tier([10, 15], [10, 15, 20], [10, 15, 20, 25],
                                        [8, 12, 16, 18, 24]))
    d1 = rng.choice([2, 3, 4])
    d2 = d1 + rng.choice([1, 2, 3])
    total_min = leg1 + rest + leg2

    x_step, x_max = _axis(total_min)

    scene = line_graph(
        series=[[(0, 0), (leg1, d1), (leg1 + rest, d1), (total_min, d2)]],
        x_range=(0, x_max), y_range=(0, d2 + 1),
        x_step=x_step, y_step=1,
        x_label="min", y_label="km", grid=True,
        aria=(f"Графика на изминат път спрямо време с хоризонтален участък "
              f"между {leg1}-ата и {leg1 + rest}-ата минута"),
    )
    solution = (rf"Хоризонталният участък е между ${leg1}$-ата и ${leg1 + rest}$-ата "
                rf"минута — през него изминатият път не се променя. "
                rf"Почивката е ${leg1 + rest} - {leg1} = {rest}$ минути.")
    stem = ("Графиката показва изминатия път на турист, който по време на "
            "прехода си е почивал веднъж. Времето на почивката")

    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=("Графиката показва изминатия път на турист, който по време на "
                  "прехода си е почивал веднъж."),
            parts=["А) Колко километра е изминал туристът до почивката?",
                   "Б) Колко минути е продължила почивката?"],
            correct_answer=[f"{d1} km", f"{rest} min"],
            difficulty="easy", scene=scene,
            solution=(solution + rf" До почивката е изминал ${d1}$ km."),
            signature=f"rest:{leg1}:{rest}:{leg2}:{d2}",
        )

    options, letter = numeric_options(
        rest, [leg1, leg2, leg1 + rest, total_min, rest * 2], rng=rng,
        positive_only=True, suffix=r"\ \text{min}")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=stem + " е:", options=options, correct_answer=letter,
        difficulty="easy", scene=scene, solution=solution,
        signature=f"rest:{leg1}:{rest}:{leg2}:{d2}",
    )
