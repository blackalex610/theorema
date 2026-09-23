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
    """Probability given symbolically — the 2024 Q20 shape: n things, k of one
    kind; the chance of the *other* kind (or of this one) as an expression."""
    k = rng.randint(3, 30)
    things, one, colour_a, colour_b, sg_a, sg_b = rng.choice([
        ("молива", "молив", "червени", "черни", "червен", "черен"),
        ("книги", "книга", "романи", "стихосбирки", "роман", "стихосбирка"),
        ("картички", "картичка", "цветни", "черно-бели", "цветна", "черно-бяла"),
        ("бонбона", "бонбон", "шоколадови", "карамелени", "шоколадов", "карамелен"),
    ])
    ask_rest = rng.random() < 0.7
    correct = rf"\frac{{n - {k}}}{{n}}" if ask_rest else rf"\frac{{{k}}}{{n}}"
    wrongs = ([rf"\frac{{n}}{{{k}}}", rf"\frac{{{k}}}{{n}}", rf"\frac{{n}}{{n - {k}}}"] if ask_rest
              else [rf"\frac{{n - {k}}}{{n}}", rf"\frac{{n}}{{{k}}}", rf"\frac{{{k}}}{{n - {k}}}"])
    options, letter = shuffle_options(f"${correct}$", [f"${w}$" for w in wrongs], rng=rng)
    target = sg_b if ask_rest else sg_a
    fem = one in ("книга", "картичка")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"В кутия има $n$ {things}, от които ${k}$ са {colour_a}, а останалите "
              f"са {colour_b}. Вероятността случайно изва{'дена' if fem else 'ден'} {one} "
              f"да е {target} се пресмята с израза:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Благоприятните са ${'n - ' + str(k) if ask_rest else k}$, а всички са $n$, "
                  rf"значи вероятността е ${correct}$"),
        signature=f"prob_expr:{k}:{things}:{ask_rest}",
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


#: (what the whole is, its unit and count word, title, four sector labels,
#:  the question with {label})
_PIES = [
    ("Училищно тържество е с продължителност {t} минути.", "минути", "Видове изпълнения",
     ["театрални", "музикални", "танцови", "спортни"],
     "По данните от диаграмата продължителността на {label} изпълнения в минути е:"),
    ("Семейство разпределя месечния си бюджет от {t} евро.", "евро", "Разходи",
     ["храна", "сметки", "транспорт", "развлечения"],
     "По данните от диаграмата сумата за {label} в евро е:"),
    ("В анкета участвали {t} ученици, всеки от които посочил любимия си спорт.", "ученици",
     "Любим спорт", ["футбол", "волейбол", "баскетбол", "плуване"],
     "По данните от диаграмата броят на учениците, посочили {label}, е:"),
    ("Земеделски производител засял {t} декара.", "декара", "Засети култури",
     ["пшеница", "царевица", "слънчоглед", "ечемик"],
     "По данните от диаграмата площта, засята с {label}, в декари е:"),
]


@template("chart_pie_sector", topics=["data_chart"], kinds=["mc"], weight=1.3)
def chart_pie_sector(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Read a share off a pie chart — the 2024 Q19 shape, in four settings.

    Sectors are multiples of 10°, the whole is chosen so the asked sector is a
    whole number, and the question may name any sector — the right angle one
    included, since reading 90° as a quarter is the step being tested.
    """
    while True:
        angles = [rng.choice(range(30, 181, 10)) for _ in range(3)]
        last = 360 - sum(angles)
        if 30 <= last <= 180:
            break
    angles.append(last)
    rng.shuffle(angles)
    opening, unit, title, labels, question = rng.choice(_PIES)
    ask = rng.randrange(4)
    total = rng.choice([60, 90, 120, 180, 240, 360, 720, 1080, 1200, 1800, 2400, 3600])
    key = Fraction(total * angles[ask], 360)
    if key.denominator != 1:
        raise Retry("the answer must be whole")
    key = key.numerator

    wrong = [Fraction(total * a, 360) for i, a in enumerate(angles) if i != ask]
    wrong += [angles[ask], key * 2]
    wrong = [int(w) for w in wrong if Fraction(w).denominator == 1]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    label_q = {"спортни": "спортните", "театрални": "театралните", "музикални": "музикалните",
               "танцови": "танцовите"}.get(labels[ask], labels[ask])
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=opening.format(t=total) + " " + question.format(label=label_q),
        options=options, correct_answer=letter, difficulty="medium",
        scene=pie_chart(
            sectors=list(zip(labels, angles)), title=title,
            aria=("Кръгова диаграма: " +
                  ", ".join(f"{l} {a} градуса" for l, a in zip(labels, angles)))),
        solution=(rf"Секторът е ${angles[ask]}^\circ$ от ${360}^\circ$, значи "
                  rf"$\frac{{{angles[ask]}}}{{360}} \cdot {total} = {key}$"),
        signature=f"chart_pie:{title}:{total}:{angles}:{ask}",
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


#: shares a table can print, as (TeX, value)
_SHARES = [(r"$\frac{n}{2}$", Fraction(1, 2)), (r"$\frac{n}{4}$", Fraction(1, 4)),
           (r"$75\%$ от $n$", Fraction(3, 4)), (r"$\frac{n}{3}$", Fraction(1, 3)),
           (r"$\frac{2n}{3}$", Fraction(2, 3)), (r"$2n$", Fraction(2)),
           (r"$50\%$ от $n$", Fraction(1, 2)), (r"$\frac{3n}{2}$", Fraction(3, 2)),
           (r"$25\%$ от $n$", Fraction(1, 4))]
_TABLES = [
    ("В книжарница за един месец са продадени общо {t} книги от видовете: {kinds}. В "
     "таблицата е представено разпределението на броя продадени книги по видове. Колко "
     "броя книги {ask} са продадени за този месец?",
     ["фантастика", "детска литература", "техническа литература", "художествена литература"]),
    ("Плодов магазин продал за седмица общо {t} kg плодове: {kinds}. В таблицата е "
     "представено разпределението на продадените килограми по видове. Колко килограма "
     "{ask} са продадени?",
     ["ябълки", "круши", "портокали", "банани"]),
    ("В училищни клубове участват общо {t} ученици: {kinds}. В таблицата е представено "
     "разпределението на учениците по клубове. Колко ученици са в клуба по {ask}?",
     ["шах", "роботика", "театър", "журналистика"]),
]


@template("table_share_of_total", topics=["data_chart"], kinds=["mc"], weight=1.0, band="hard")
def table_share_of_total(rng: random.Random, slot: Slot) -> GeneratedItem:
    """A table of shares expressed in terms of n — the 2025 Q19 shape.

    One column is n itself and the others are fractions or percentages of it;
    the total fixes n. Any mix of shares the papers use, any column asked.
    """
    others = rng.sample(_SHARES, 3)
    if len({v for _, v in others}) < 3:
        raise Retry("three different shares")
    coeff = 1 + sum(v for _, v in others)
    n = rng.randint(3, 20) * 12              # totals near the paper's 1200, not 5000
    total = coeff * n
    if total.denominator != 1:
        raise Retry("the total must be whole")
    cells = [t for t, _ in others] + ["$n$"]
    values = [v * n for _, v in others] + [Fraction(n)]
    template_text, kinds = rng.choice(_TABLES)
    order = list(range(4))
    rng.shuffle(order)
    headers = [kinds[i] for i in order]
    row = [cells[i] for i in order]
    ask = rng.randrange(4)
    key = values[order[ask]]
    if key.denominator != 1:
        raise Retry("the asked amount must be whole")
    key = int(key)
    wrong = [int(v) for v in values if v != key and v.denominator == 1] + [int(total) - key, n // 2]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=template_text.format(t=int(total), kinds=", ".join(kinds), ask=headers[ask]),
        options=options, correct_answer=letter, difficulty="hard",
        scene=data_table(headers=headers, rows=[row],
                         aria="Таблица с четири вида, изразени чрез n"),
        solution=(rf"Сборът е ${bg_number(coeff)}n = {int(total)}$, откъдето $n = {n}$, а "
                  rf"търсеното количество е ${key}$"),
        signature=f"table_share:{template_text[:6]}:{[str(v) for _, v in others]}:{n}:{order}:{ask}",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Band partners for the data-reading position.
#
# The ministry's 2015 memo commits to keeping a chart- or table-reading item in
# every paper, and the corpus bears that out — one or two, never zero. These
# are the short-answer forms: two sub-parts, marked separately, exactly as the
# 2026 Q17 key does it ("2 т.", "3 т.").
# ═════════════════════════════════════════════════════════════════════════════

_MONTHS = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август",
           "септември", "октомври", "ноември", "декември"]

#: Each context is written out whole. Building the sentences from one noun
#: phrase is what printed „броя на продадени велосипеда” and „Колко общо са
#: продадени велосипеда” — the count form after a non-number, and no article.
#: (intro, А question, Б-total question, Б-difference question with {a} {b},
#:  answer unit)
_CHART_CONTEXTS = [
    ("Диаграмата показва броя на продадените велосипеди в един магазин",
     "През кой месец са продадени най-много велосипеди?",
     "Колко велосипеда общо са продадени през показаните месеци?",
     "С колко велосипеда повече са продадени през {a}, отколкото през {b}?",
     "велосипеда"),
    ("Диаграмата показва броя на посетителите на една изложба",
     "През кой месец изложбата е имала най-много посетители?",
     "Колко посетители общо е имала изложбата през показаните месеци?",
     "С колко посетители повече е имало през {a}, отколкото през {b}?",
     "посетители"),
    ("Диаграмата показва броя на издадените читателски карти в една библиотека",
     "През кой месец са издадени най-много читателски карти?",
     "Колко читателски карти общо са издадени през показаните месеци?",
     "С колко карти повече са издадени през {a}, отколкото през {b}?",
     "карти"),
    ("Строителна фирма продава апартаменти. Диаграмата показва броя на "
     "продадените апартаменти",
     "През кой месец са продадени най-много апартаменти?",
     "Колко апартамента общо са продадени през показаните месеци?",
     "С колко апартамента повече са продадени през {a}, отколкото през {b}?",
     "апартамента"),
    ("Диаграмата показва броя на нощувките в един хотел",
     "През кой месец в хотела е имало най-много нощувки?",
     "Колко нощувки общо е имало в хотела през показаните месеци?",
     "С колко нощувки повече е имало през {a}, отколкото през {b}?",
     "нощувки"),
    ("Диаграмата показва броя на продадените билети в едно кино",
     "През кой месец са продадени най-много билети?",
     "Колко билета общо са продадени през показаните месеци?",
     "С колко билета повече са продадени през {a}, отколкото през {b}?",
     "билета"),
    ("Диаграмата показва броя на засадените дръвчета в един парк",
     "През кой месец са засадени най-много дръвчета?",
     "Колко дръвчета общо са засадени през показаните месеци?",
     "С колко дръвчета повече са засадени през {a}, отколкото през {b}?",
     "дръвчета"),
]


@template("chart_peak_and_total",
          topics=["data_chart"], kinds=["short"], weight=1.2, band="easy")
def chart_peak_and_total(rng: random.Random, slot: Slot) -> GeneratedItem:
    """Read the tallest bar, then total the series or compare two bars — the
    easiest questions you can ask of a bar chart, which is what the gentler
    levels need here. The months are a sliding window, as in 2026 Q17
    (април – август), rather than always starting in January."""
    n = rng.choice([5, 6])
    first = rng.randint(0, 12 - n)
    labels = _MONTHS[first:first + n]
    scale = rng.choice([1, 1, 2, 10])
    values = [rng.choice([5, 10, 15, 20, 25, 30, 35, 40]) * scale for _ in labels]
    peak = max(values)
    if values.count(peak) != 1:
        raise Retry("the tallest bar must be unique")
    peak_month = labels[values.index(peak)]
    intro, q_peak, q_total, q_diff, unit = rng.choice(_CHART_CONTEXTS)

    if rng.random() < 0.55:
        q_b = q_total
        ans_b = sum(values)
        sol_b = f"${' + '.join(str(v) for v in values)} = {ans_b}$"
        sig_b = "total"
    else:
        i, j = rng.sample(range(n), 2)
        if values[i] <= values[j]:
            i, j = j, i
        if values[i] == values[j]:
            raise Retry("the two compared bars must differ")
        q_b = q_diff.format(a=labels[i], b=labels[j])
        ans_b = values[i] - values[j]
        sol_b = f"${values[i]} - {values[j]} = {ans_b}$"
        sig_b = f"diff{i}{j}"

    scene = bar_chart(
        categories=labels, values=values, y_label="брой", y_step=5 * scale,
        aria=(intro + " по месеци: " +
              ", ".join(f"{m} — {v}" for m, v in zip(labels, values))),
    )
    return GeneratedItem(
        topic=slot.topic, kind="short", points=slot.points,
        stem=f"{intro} през месеците от {labels[0]} до {labels[-1]}.",
        parts=[f"А) {q_peak}", f"Б) {q_b}"],
        correct_answer=[peak_month, f"{ans_b} {unit}"],
        difficulty="easy", scene=scene,
        solution=(f"А) Най-високият стълб е за месец {peak_month} — ${peak}$. "
                  f"Б) {sol_b}."),
        signature=f"chart_peak:{first}:{'-'.join(map(str, values))}:{sig_b}",
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
