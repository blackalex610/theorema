"""Item shapes the corpus study found in the real papers and the generator lacked.

Each one is named after the paper and position it comes from. They were found
by reading Part 1 of 2023–2025 against the template catalogue, and they are
registered to the position where the paper printed them, so they widen the
thinnest slots rather than adding topics the format does not have.

    2023 Q2   primes_in_list                 how many of these are prime
    2023 Q9   prob_letters_on_cards          a letter drawn from a word's cards
    2026 Q6   prob_number_property           a property of a number drawn from a range
    2025 Q8   mean_next_score                the score that lifts a mean to a target
    2023 Q10  mean_three_friends             three amounts with equal gaps and a mean
    2023 Q4   abs_equation_which_no_solution which equation has no / one / two roots
    2023 Q3   diff_squares_decimal           0,99² − 0,01² by the difference of squares
    2025 Q3   factor_diff_squares_signs      49 − x² against four sign permutations
    2025 Q6   factor_not_a_factor            the factor that does NOT occur
    2025 Q2   power_quotient_at_value        a quotient of powers at x = −3
    2023 Q6   map_scale_from_distances       the scale, from a real and a map distance
    2024 Q4   linear_equation_squares_cancel an equation that is linear once expanded
    2025 Q5   inequality_squares_cancel_integer  the extreme integer solution
    2024 Q16  expression_from_words_age      ages now and later as an expression in x
    2025 Q17  expression_from_words_price    two related prices as an expression in x
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
    shuffle_options,
)
from app.nvo_gen.poly import Poly, lin
from app.nvo_gen.registry import GeneratedItem, Retry, template


def _frac_tex(v: Fraction) -> str:
    v = Fraction(v)
    if v.denominator == 1:
        return str(v.numerator)
    sign = "-" if v < 0 else ""
    return rf"{sign}\frac{{{abs(v.numerator)}}}{{{v.denominator}}}"


def _is_prime(n: int) -> bool:
    return n >= 2 and all(n % d for d in range(2, int(n ** 0.5) + 1))


# ─── number sense ────────────────────────────────────────────────────────────

@template("primes_in_list", topics=["arithmetic_expression"], kinds=["mc"],
          weight=0.9, band="easy")
def primes_in_list(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q2: „Колко от числата 1, 3, 9, 11, 15, … са прости?”

    The traps are the paper's own: 1, which is not prime, and odd composites
    such as 9, 21 and 27, which look prime. Every list carries some of each.
    """
    hi = slot.profile.tier(30, 40, 60, 99)
    odd_composites = [n for n in range(9, hi + 1, 2) if not _is_prime(n)]
    primes = [n for n in range(2, hi + 1) if _is_prime(n)]
    evens = [n for n in range(4, hi + 1, 2)]
    k = rng.randint(3, 7)
    chosen = set(rng.sample(primes, k))
    chosen |= set(rng.sample(odd_composites, rng.randint(2, 4)))
    chosen |= set(rng.sample(evens, rng.randint(1, 2)))
    if rng.random() < 0.7:
        chosen.add(1)
    numbers = sorted(chosen)
    key = sum(_is_prime(n) for n in numbers)

    looks_prime = sum(1 for n in numbers if n % 2 and not _is_prime(n))
    wrong = [key + 1, key - 1, key + looks_prime, key + 2]
    options, letter = numeric_options(key, [w for w in wrong if w > 0], rng=rng,
                                      positive_only=True)
    listed = ", ".join(f"${n}$" for n in numbers)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Колко от числата {listed} са прости?",
        options=options, correct_answer=letter, difficulty="easy",
        solution=("Простите са " + ", ".join(f"${n}$" for n in numbers if _is_prime(n)) +
                  " — числото $1$ не е просто, а нечетните съставни числа се делят на $3$, "
                  "$5$ или $7$"),
        signature=f"primes:{'-'.join(map(str, numbers))}",
    )


# ─── probability ─────────────────────────────────────────────────────────────

#: Words and place names whose letters go on cards. Upper-case, as the paper
#: prints them; each has at least one repeated letter to make the count matter.
_CARD_WORDS = ["КАРЛОВО", "ПЛОВДИВ", "ГАБРОВО", "СОЗОПОЛ", "ВАРНА", "КАЗАНЛЪК",
               "МАТЕМАТИКА", "ПАРАЛЕЛОГРАМ", "ТРИЪГЪЛНИК", "КВАДРАТ", "УРАВНЕНИЕ",
               "БАНСКО", "СМОЛЯН", "ДОБРИЧ", "РАЗЛОГ", "ПАЗАРДЖИК", "ВЕЛИКО", "ТЕТЕВЕН",
               "КОПРИВЩИЦА", "НЕСЕБЪР", "БЕЛОГРАДЧИК", "ПРОЦЕНТ", "ОТСЕЧКА"]
_VOWELS = set("АЕИОУЪЮЯ")


@template("prob_letters_on_cards", topics=["probability"], kinds=["mc"],
          weight=1.1, band="easy")
def prob_letters_on_cards(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q9: the letters of КАРЛОВО on cards; the chance of drawing О is 2/7."""
    word = rng.choice(_CARD_WORDS)
    n = len(word)
    counts = {c: word.count(c) for c in word}
    ask = rng.choice(["letter", "letter", "not_letter", "vowel"])
    if ask == "vowel":
        fav = sum(1 for c in word if c in _VOWELS)
        what = "гласна буква"
    else:
        letter = rng.choice([c for c in counts if counts[c] > 1] or list(counts))
        fav = counts[letter] if ask == "letter" else n - counts[letter]
        what = f"буквата {letter}" if ask == "letter" else f"буква, различна от {letter}"
    key = Fraction(fav, n)
    if key in (0, 1):
        raise Retry("a certain or impossible event is not an item")

    distinct = len(counts)
    wrong = [Fraction(1, n), Fraction(fav, distinct) if fav < distinct else Fraction(1, distinct),
             Fraction(n - fav, n), Fraction(fav, n + 1), Fraction(fav + 1, n)]
    options, letter_key = numeric_options(key, [w for w in wrong if 0 < w < 1], rng=rng,
                                          positive_only=True)
    cards = ", ".join(word)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"На {n} еднакви картончета са написани буквите {cards}. Каква е "
              f"вероятността на произволно избрано картонче да е написана {what}?"),
        options=options, correct_answer=letter_key, difficulty="easy",
        solution=(rf"Благоприятните картончета са ${fav}$ от всичките ${n}$, "
                  rf"значи вероятността е ${_frac_tex(key)}$"),
        signature=f"prob_cards:{word}:{ask}:{what}",
    )


_RANGES = [
    # (description, numbers)
    ("едноцифрено неотрицателно число", range(0, 10)),
    ("едноцифрено естествено число", range(1, 10)),
    ("двуцифрено число", range(10, 100)),
    ("естествено число от $1$ до $20$", range(1, 21)),
    ("естествено число от $1$ до $30$", range(1, 31)),
    ("естествено число от $1$ до $50$", range(1, 51)),
]
_PROPERTIES = [
    ("се дели на {d}", lambda n, d: n % d == 0, [2, 3, 4, 5, 6, 9]),
    ("е просто", lambda n, d: _is_prime(n), [None]),
    ("е точен квадрат", lambda n, d: int(n ** 0.5) ** 2 == n, [None]),
    ("завършва на цифрата {d}", lambda n, d: n % 10 == d, [0, 3, 5, 7]),
]


@template("prob_number_property", topics=["probability"], kinds=["mc"],
          weight=1.1, band="medium")
def prob_number_property(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2026 Q6 widened: „вероятността произволно избрано едноцифрено
    неотрицателно число да се дели на 3” — any range, any countable property."""
    desc, numbers = rng.choice(_RANGES)
    phrase, test, params = rng.choice(_PROPERTIES)
    d = rng.choice(params)
    fav = sum(1 for n in numbers if test(n, d))
    total = len(numbers)
    key = Fraction(fav, total)
    if key in (0, 1) or fav < 2:
        raise Retry("the event must be possible, not certain, and not a single case")
    prop = phrase.format(d=f"${d}$")

    wrong = [Fraction(1, d) if d else Fraction(fav + 1, total), Fraction(fav, total - 1),
             Fraction(fav - 1, total), Fraction(total - fav, total), Fraction(fav + 1, total)]
    options, letter = numeric_options(key, [w for w in wrong if 0 < w < 1 and w != key],
                                      rng=rng, positive_only=True)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Вероятността произволно избрано {desc} да {prop}, е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Възможните числа са ${total}$, а благоприятните — ${fav}$, значи "
                  rf"вероятността е ${_frac_tex(key)}$"),
        signature=f"prob_prop:{desc}:{phrase}:{d}",
    )


# ─── means ───────────────────────────────────────────────────────────────────

_MEAN_SETTINGS = [
    ("Средният брой точки на ученик от {n} контролни работи е {m}.",
     "Колко точки трябва да получи на следващата контролна работа, така че средният брой "
     "точки от тези {n1} контролни да е {t}?", "точки"),
    ("През първите {n} дни от седмицата един магазин продавал средно по {m} хляба на ден.",
     "Колко хляба трябва да продаде на следващия ден, така че средното за {n1} дни да "
     "стане {t} хляба?", "хляба"),
    ("Бегач пробягал средно по {m} km на ден през първите {n} дни на тренировъчен лагер.",
     "Колко километра трябва да пробяга на следващия ден, за да стане средното за {n1} дни "
     "{t} km?", "km"),
]


@template("mean_next_score", topics=["word_problem_units"], kinds=["mc"],
          weight=1.0, band="medium")
def mean_next_score(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2025 Q8: a mean of 23,75 over four tests; what fifth score makes it 25?"""
    n = rng.randint(3, 6)
    t = rng.randint(12, 60)
    raise_by = Fraction(rng.choice([1, 2, 3, 4, 5, 6, 8, 10]), rng.choice([1, 2, 4]))
    m = t - raise_by
    if m <= 0 or not is_clean_decimal(m, places=2):
        raise Retry("the old mean must be a short decimal")
    key = (n + 1) * t - n * m
    if key.denominator != 1 or key > 3 * t:
        raise Retry("the needed value must be whole and believable")
    told, asked, unit = rng.choice(_MEAN_SETTINGS)

    wrong = [t, t + raise_by, 2 * t - m, key + n, t + n * raise_by - 1]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True,
                                      fmt=lambda v: bg_decimal(Fraction(v), places=2))
    mm = bg_decimal(m, places=2, math_mode=False)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(told.format(n=n, m=mm) + " " + asked.format(n1=n + 1, t=t)),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"Сборът трябва да стане ${n + 1}\cdot {t} = {(n + 1) * t}$, а досега е "
                  rf"${n}\cdot {bg_decimal(m, places=2)} = {bg_decimal(n * m, places=2)}$, "
                  rf"значи са нужни ${bg_number(key)}$"),
        signature=f"mean_next:{n}:{t}:{m}:{unit}",
    )


_TRIO = [("Бойко", "Ани", "Валя"), ("Петко", "Ивет", "Мария"), ("Никола", "Дора", "Елена"),
         ("Асен", "Ралица", "Калина")]


@template("mean_three_friends", topics=["word_problem_units"], kinds=["mc"],
          weight=0.9, band="medium")
def mean_three_friends(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q10: Бойко has 4 more than Ани and 4 fewer than Валя; the mean is 12.

    With equal gaps the middle amount *is* the mean, which is the insight; the
    distractors are the three amounts a student might stop at.
    """
    mid, low_name, high_name = rng.choice(_TRIO)
    d = rng.randint(2, 15)
    mean = rng.randint(d + 3, 60)
    ask_high = rng.random() < 0.6
    key = mean + d if ask_high else mean - d
    unit = rng.choice(["евро", "лепенки", "книги"])
    wrong = [mean, mean - d if ask_high else mean + d, mean + 2 * d, 3 * mean]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      positive_only=True)
    of_them = {"евро": "парите", "лепенки": "лепенките", "книги": "книгите"}[unit]
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{mid} има с ${d}$ {unit} повече от {low_name} и с ${d}$ {unit} по-малко "
              f"от {high_name}. Колко {unit} има "
              f"{high_name if ask_high else low_name}, ако средноаритметичното на "
              f"{of_them} на тримата е ${mean}$?"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"При равни разлики средното е числото по средата: {mid} има ${mean}$, "
                  rf"значи {high_name if ask_high else low_name} има ${key}$"),
        signature=f"mean3:{d}:{mean}:{ask_high}:{unit}",
    )


# ─── absolute value ──────────────────────────────────────────────────────────

def _abs_eq(a: int, rhs: int, *, shift: int = 0) -> str:
    inner = "x" if a == 0 else (f"x - {a}" if a > 0 else f"x + {-a}")
    left = rf"\left|{inner}\right|"
    if shift:
        left += f" + {shift}" if shift > 0 else f" - {-shift}"
    return f"${left} = {rhs}$"


@template("abs_equation_which_no_solution", topics=["absolute_value_equation"],
          kinds=["mc"], weight=1.0, band="easy")
def abs_equation_which_no_solution(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q4: „Кое от уравненията няма решение?” — and its two siblings,
    „има точно един корен” and „има два корена”, over the same four forms."""
    a = rng.choice([v for v in range(-9, 10) if v])
    b = rng.randint(1, 9)
    kinds = {
        "none": [_abs_eq(a, -b), _abs_eq(a, b, shift=2 * b)],      # |…| = −b, |…| + 2b = b
        "one": [_abs_eq(a, 0), _abs_eq(a, b, shift=b)],            # |…| = 0, |…| + b = b
        "two": [_abs_eq(a, b), _abs_eq(-a, b, shift=-b)],          # |…| = b, |…| − b = b
    }
    ask = rng.choice(["none", "none", "one", "two"])
    question = {"none": "няма решение", "one": "има точно един корен",
                "two": "има два различни корена"}[ask]
    correct = rng.choice(kinds[ask])
    others = [rng.choice(v) for k, v in kinds.items() if k != ask]
    others.append(rng.choice([f for k, v in kinds.items() if k != ask for f in v
                              if f not in others]))
    options, letter = shuffle_options(correct, others, rng=rng)
    if len(set(options)) != 4:
        raise Retry("four different equations")
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Кое от уравненията {question}?",
        options=options, correct_answer=letter, difficulty="easy",
        solution=("Модулът е неотрицателен: $|A| = c$ няма решение при $c < 0$, има един "
                  "корен при $c = 0$ и два корена при $c > 0$"),
        signature=f"abs_which:{a}:{b}:{ask}",
    )


# ─── shortcut multiplication ─────────────────────────────────────────────────

@template("diff_squares_decimal", topics=["shortcut_multiplication", "expression_at_value"],
          kinds=["mc", "short"], weight=1.0, band="medium")
def diff_squares_decimal(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q3: 0,99² − 0,01². The sum a + b is round, so (a − b)(a + b) is easy
    and squaring either number first is not."""
    s = Fraction(rng.choice([1, 2, 10, 20, 100, 1000]))
    d = Fraction(rng.choice(range(2, 199, 2)), rng.choice([10, 100]))
    a, b = (s + d) / 2, (s - d) / 2
    if b <= 0 or not (is_clean_decimal(a) and is_clean_decimal(b)) or a == b:
        raise Retry("both numbers short positive decimals")
    key = s * d
    if not is_clean_decimal(key):
        raise Retry("a short decimal key")
    expr = rf"{bg_decimal(a)}^2 - {bg_decimal(b)}^2"
    stem = f"Стойността на израза ${expr}$ е:"
    solution = (rf"${expr} = \left({bg_decimal(a)} - {bg_decimal(b)}\right)"
                rf"\left({bg_decimal(a)} + {bg_decimal(b)}\right) = {bg_decimal(d)}\cdot "
                rf"{bg_decimal(s)} = {bg_decimal(key)}$")
    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"Намерете стойността на израза ${expr}$.",
            correct_answer=bg_decimal(key, math_mode=False), difficulty="medium",
            solution=solution, signature=f"dsq_dec:{a}:{b}",
        )
    wrong = [d, s, key * 10, (a - b) ** 2, key / 10]
    options, letter = numeric_options(key, [w for w in wrong if is_clean_decimal(Fraction(w))],
                                      rng=rng, positive_only=True,
                                      fmt=lambda v: bg_decimal(Fraction(v)))
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points, stem=stem,
        options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"dsq_dec:{a}:{b}",
    )


# ─── factoring ───────────────────────────────────────────────────────────────

def _factor_tex_leaf(p: Poly) -> str:
    """A linear factor the way the papers print it: „7 − x”, „x + 7”, „2x − 7”."""
    return rf"\left({lin(p.coeff(1), p.coeff(0)).tex()}\right)"


@template("factor_diff_squares_signs", topics=["expand_or_factor"], kinds=["mc"],
          weight=1.1, band="easy")
def factor_diff_squares_signs(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2025 Q3: 49 − x² against (x − 7)(x + 7), (7 − x)(7 + x), (x − 7)(7 − x)…

    Every option is checked by expansion, so exactly one equals the expression
    whatever the draw — the sign bookkeeping *is* the item.
    """
    k = rng.randint(2, 4) if rng.random() < 0.3 else 1
    a = rng.randint(2, 12)
    if math.gcd(a, k) != 1:
        raise Retry("keep the two squares coprime")
    const_first = rng.random() < 0.6          # a² − k²x² rather than k²x² − a²
    target = (Poly.of(a * a, 0, -k * k) if const_first else Poly.of(-a * a, 0, k * k))
    target_tex = f"{a * a} - {k * k if k > 1 else ''}x^2" if const_first else target.tex()
    # the four linear factors a papers' options are built from: kx ± a and a ± kx
    forms = [Poly.of(a, k), Poly.of(-a, k), Poly.of(a, -k)]
    cands = [(f1, f2) for f1 in forms for f2 in forms]
    right = [c for c in cands if c[0] * c[1] == target]
    wrong = [c for c in cands if c[0] * c[1] != target]
    if not right:
        raise Retry("no sign arrangement matches")
    rng.shuffle(right); rng.shuffle(wrong)
    render = lambda pair: f"${_factor_tex_leaf(pair[0])}{_factor_tex_leaf(pair[1])}$"
    seen, wrong_txt = {render(right[0])}, []
    for c in wrong:
        t = render(c)
        if t not in seen:
            seen.add(t); wrong_txt.append(t)
    if len(wrong_txt) < 3:
        raise Retry("not enough distinct wrong factorisations")
    options, letter = shuffle_options(render(right[0]), wrong_txt[:3], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Изразът ${target_tex}$ е тъждествено равен на:",
        options=options, correct_answer=letter, difficulty="easy",
        solution=rf"Разлика на квадрати: ${target_tex} = {render(right[0])[1:-1]}$",
        signature=f"fds:{a}:{k}:{const_first}",
    )


@template("factor_not_a_factor", topics=["expand_or_factor"], kinds=["mc"],
          weight=1.0, band="hard")
def factor_not_a_factor(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2025 Q6: which factor does NOT occur in x⁴ − x³ − 4x² + 4x = x(x − 1)(x − 2)(x + 2)?

    The wrong option is a real factor with its sign flipped — the one a student
    who grouped carelessly would write down.
    """
    roots = rng.sample([v for v in range(-5, 6) if v], 3)
    if len({abs(r) for r in roots}) < 2:
        raise Retry("keep the roots visibly different")
    with_x = rng.random() < 0.6
    P = Poly.of(1)
    for r in roots:
        P = P * Poly.of(-r, 1)
    if with_x:
        P = P * Poly.of(0, 1)
    fake_root = rng.choice([-r for r in roots if -r not in roots] or [None])
    if fake_root is None:
        raise Retry("every sign-flip is also a root")
    factor = lambda r: f"${lin(1, -r).tex()}$"
    true = [factor(r) for r in roots]
    fake = factor(fake_root)
    options, letter = shuffle_options(fake, true, rng=rng)
    product = ("x" if with_x else "") + "".join(rf"\left({lin(1, -r).tex()}\right)" for r in roots)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Множителят, който НЕ участва в представянето на многочлена ${P.tex()}$ "
              f"като произведение на множители, е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=rf"${P.tex()} = {product}$",
        signature=f"notfactor:{sorted(roots)}:{with_x}:{fake_root}",
    )


# ─── powers ──────────────────────────────────────────────────────────────────

@template("power_quotient_at_value", topics=["expression_at_value", "powers"],
          kinds=["mc", "short"], weight=1.0, band="medium")
def power_quotient_at_value(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2025 Q2: a quotient of powers of x evaluated at x = −3. Simplify first —
    x^a·x^b / (x^c)^d = x^(a+b−cd) — and only then substitute; the sign of a
    negative base under an odd exponent is the trap."""
    x0 = Fraction(rng.choice([-3, -2, 2, 3, -1, 5, -5]) if rng.random() < 0.8
                  else rng.choice([Fraction(1, 2), Fraction(-1, 2), Fraction(1, 3)]))
    # choose the simplified exponent first, then exponents that reach it
    e = rng.choice([-3, -2, -1, 1, 2, 3])
    c, d = rng.randint(2, 4), rng.randint(2, 3)
    s = e + c * d                            # a + b
    if s < 4 or s > 18:
        raise Retry("a + b out of range")
    a = rng.randint(max(2, s - 9), min(9, s - 2))
    b = s - a
    if abs(x0) == 1 and e % 2 == 0:
        raise Retry("(±1)^even is a giveaway")
    key = x0 ** e
    if abs(key.numerator) > 250 or key.denominator > 250:
        raise Retry("keep the value readable")
    expr = rf"\dfrac{{x^{{{a}}}\cdot x^{{{b}}}}}{{\left(x^{{{c}}}\right)^{{{d}}}}}"
    at = _frac_tex(x0)
    solution = (rf"${expr} = x^{{{a} + {b} - {c * d}}} = x^{{{e}}}$, а при $x = {at}$ "
                rf"стойността е ${_frac_tex(key)}$")
    if slot.kind == "short":
        return GeneratedItem(
            topic=slot.topic, kind="short", points=slot.points,
            stem=f"Намерете стойността на израза ${expr}$ при $x = {at}$.",
            correct_answer=(str(key.numerator) if key.denominator == 1
                            else f"{key.numerator}/{key.denominator}"),
            difficulty="medium", solution=solution, signature=f"powq:{a}:{b}:{c}:{d}:{x0}",
        )
    wrong = [-key, 1 / key if key else 1, x0 ** (a + b + c * d) if abs(a + b + c * d) < 4 else key * x0,
             -1 / key if key else 2, key * x0]
    options, letter = numeric_options(key, [w for w in wrong if w != key], rng=rng,
                                      fmt=_frac_tex)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Стойността на израза ${expr}$ при $x = {at}$ е:",
        options=options, correct_answer=letter, difficulty="medium",
        solution=solution, signature=f"powq:{a}:{b}:{c}:{d}:{x0}",
    )


# ─── units ───────────────────────────────────────────────────────────────────

@template("map_scale_from_distances", topics=["word_problem_units"], kinds=["mc"],
          weight=0.9, band="medium")
def map_scale_from_distances(rng: random.Random, slot: Slot) -> GeneratedItem:
    """2023 Q6: 40 km in reality, 8 cm on the map — the scale is 1 : 500 000.

    The options are the paper's: the right digits at the wrong power of ten,
    which is exactly the km-to-cm conversion being tested.
    """
    per_cm_km = rng.choice([Fraction(1, 2), 1, 2, 5, 10, 20, 25, 50])
    cm = rng.randint(2, 15)
    km = per_cm_km * cm
    if km.denominator != 1:
        raise Retry("a whole number of kilometres")
    n = int(per_cm_km * 100_000)
    fmt = lambda v: "$" + rf"1 : {int(v):,}".replace(",", r"\,") + "$"
    # The paper's options sit powers of ten apart (1 : 5 … 1 : 5 000 000), far
    # outside numeric_options' plausibility band, so they are rendered here.
    wrong = []
    for w in (n * 10, n // 10, n // 100_000, n // 100, n * 100):
        if w >= 1 and w != n and fmt(w) not in wrong:
            wrong.append(fmt(w))
    options, letter = shuffle_options(fmt(n), wrong[:3], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"Действителното разстояние между два града е ${int(km)}$ километра. Ако на "
              f"географска карта разстоянието между тези градове е ${cm}$ cm, то мащабът на "
              f"картата е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"${int(km)}$ km $= {int(km) * 100_000:,}$ cm, а "
                  rf"${int(km) * 100_000:,} : {cm} = {n:,}$").replace(",", r"\,"),
        signature=f"map_scale_rev:{km}:{cm}",
    )


# ─── linear equations and inequalities where the squares cancel ─────────────
# Part 2's families (part2_algebra._family_pair) reduced to a one-step Part 1
# item: 2024 Q4 „2 − (x − 3)/… = …” and 2025 Q5 „8 − x ≥ 6(x − 1)” are the
# same reduction with fewer terms.

def _linear_family(rng: random.Random, name: str = "x"):
    from app.nvo_gen.poly import frac as _frac, lin as _lin, var as _var
    x = _var(name)
    fam = rng.randrange(4)
    if fam == 0:                 # (x + a)² − x(x + b) = c
        a, b = rng.randint(1, 7), rng.randint(1, 9)
        lhs, rhs = (x + a) ** 2 - x * (x + b), _lin(0, rng.randint(-20, 40), name)
    elif fam == 1:               # (x − a)/p − (x + b)/q = c
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        p, q = rng.sample([2, 3, 4, 5, 6], 2)
        lhs, rhs = _frac(x - a, p) - _frac(x + b, q), _lin(0, rng.randint(-5, 5), name)
    elif fam == 2:               # a − (x − b)/p = (x + c)/q
        a, b, c = rng.randint(1, 9), rng.randint(1, 9), rng.randint(1, 9)
        p, q = rng.sample([2, 3, 4, 6], 2)
        lhs, rhs = _lin(0, a, name) - _frac(x - b, p), _frac(x + c, q)
    else:                        # (x − a)(x + b) − (x − c)² = d
        a, b, c = rng.randint(1, 8), rng.randint(1, 8), rng.randint(1, 8)
        lhs, rhs = (x - a) * (x + b) - (x - c) ** 2, _lin(0, rng.randint(-20, 20), name)
    diff = lhs.poly() - rhs.poly()
    if diff.degree != 1:
        raise Retry("did not reduce to a linear relation")
    return lhs, rhs, diff


@template("linear_equation_squares_cancel", topics=["linear_equation"], kinds=["mc"],
          weight=1.0, band="hard")
def linear_equation_squares_cancel(rng: random.Random, slot: Slot) -> GeneratedItem:
    """An equation that looks quadratic or fractional and is linear once expanded."""
    lhs, rhs, diff = _linear_family(rng)
    root = -diff.coeff(0) / diff.coeff(1)
    if root == 0 or root.denominator > 4 or abs(root) > 20:
        raise Retry("a root the key would print")
    wrong = [-root, root + 1, root - 1, 2 * root, 1 / root]
    options, letter = numeric_options(root, [w for w in wrong if w != root], rng=rng,
                                      fmt=_frac_tex)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=f"Коренът на уравнението ${lhs.tex()} = {rhs.tex()}$ е:",
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"След разкриване на скобите и освобождаване от знаменателите: "
                  rf"${diff.tex()} = 0$, откъдето $x = {_frac_tex(root)}$"),
        signature=f"lin_cancel:{lhs.tex()}={rhs.tex()}",
    )


@template("inequality_squares_cancel_integer", topics=["inequality_integer_bound"],
          kinds=["mc"], weight=1.0, band="hard")
def inequality_squares_cancel_integer(rng: random.Random, slot: Slot) -> GeneratedItem:
    """The largest/smallest integer solution of an inequality that reduces to a
    linear one — 2024 Q5 and 2025 Q5, with the Part 2 families' brackets."""
    from app.nvo_gen.poly import solve_linear_inequality
    lhs, rhs, _diff = _linear_family(rng)
    rel = rng.choice(["<", ">", r"\le", r"\ge"])
    rel2, bound = solve_linear_inequality(lhs.poly(), rhs.poly(), rel)
    if bound.denominator > 6 or abs(bound) > 15:
        raise Retry("a bound a key would print")
    if rel2 in (">", r"\ge"):
        which = "Най-малкото"
        ext = math.floor(bound) + 1 if rel2 == ">" else math.ceil(bound)
    else:
        which = "Най-голямото"
        ext = math.ceil(bound) - 1 if rel2 == "<" else math.floor(bound)
    boundary_slip = math.floor(bound) if which == "Най-малкото" else math.ceil(bound)
    wrong = [ext + 1, ext - 1, -ext if ext else 2, boundary_slip, ext + 2]
    options, letter = numeric_options(ext, [w for w in wrong if w != ext], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{which} цяло число, което е решение на неравенството "
              f"${lhs.tex()} {rel} {rhs.tex()}$, е:"),
        options=options, correct_answer=letter, difficulty="hard",
        solution=(rf"Неравенството се свежда до $x {rel2} {_frac_tex(bound)}$, откъдето "
                  rf"търсеното число е ${ext}$"),
        signature=f"ineq_cancel:{lhs.tex()}{rel}{rhs.tex()}",
    )


# ─── expressions from words ──────────────────────────────────────────────────

@template("expression_from_words_age", topics=["expression_from_words"], kinds=["mc"],
          weight=1.0, band="medium")
def expression_from_words_age(rng: random.Random, slot: Slot) -> GeneratedItem:
    """„Мария е на x години, а майка ѝ е с a години по-възрастна. След b години
    сборът от годините им ще бъде:” — the expression-from-words skill of 2024
    Q16 and 2025 Q17 in an age setting."""
    # (child, relative, agreement, relative with the definite article)
    child, parent, rel, parent_def = rng.choice([
        ("Мария", "майка ѝ", "по-възрастна", "майката"),
        ("Петко", "баща му", "по-възрастен", "бащата"),
        ("Ани", "леля ѝ", "по-възрастна", "лелята"),
        ("Иван", "дядо му", "по-възрастен", "дядото"),
    ])
    a = rng.randint(18, 60)
    b = rng.randint(2, 15)
    ask = rng.choice(["sum_later", "sum_before", "parent_later"])
    if ask == "sum_later":
        q = f"След ${b}$ години сборът от годините им ще бъде:"
        key, wr = f"2x + {a + 2 * b}", [f"2x + {a + b}", f"x + {a + 2 * b}", f"2x + {a}"]
    elif ask == "sum_before":
        q = f"Преди ${b}$ години сборът от годините им е бил:"
        c = a - 2 * b
        if c <= 0:
            raise Retry("keep the constant positive")
        key, wr = f"2x + {c}", [f"2x + {a - b}", f"2x + {a + 2 * b}", f"x + {c}"]
    else:
        q = f"След ${b}$ години годините на {parent_def} ще бъдат:"
        key, wr = f"x + {a + b}", [f"x + {a}", f"x + {b}", f"2x + {a + b}"]
    options, letter = shuffle_options(f"${key}$", [f"${w}$" for w in wr], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{child} е на $x$ години, а {parent} е с ${a}$ години {rel}. {q}"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=rf"Търсеният израз е ${key}$",
        signature=f"expr_age:{a}:{b}:{ask}:{child}",
    )


#: (first item with its article, its count form, second item with article,
#:  its count form, the adjective ending that agrees with the second item)
_TWO_GOODS = [
    ("Една тетрадка", "тетрадки", "една химикалка", "химикалки", "а"),
    ("Една книга", "книги", "едно списание", "списания", "о"),
    ("Един билет за кино", "билета за кино", "един пакет пуканки", "пакета пуканки", ""),
    ("Една тениска", "тениски", "една шапка", "шапки", "а"),
    ("Един сандвич", "сандвича", "една бутилка вода", "бутилки вода", "а"),
]


@template("expression_from_words_price", topics=["expression_from_words"], kinds=["mc"],
          weight=1.0, band="medium")
def expression_from_words_price(rng: random.Random, slot: Slot) -> GeneratedItem:
    """„Една тетрадка струва x евро, а една химикалка е с a евро по-евтина. Цената
    на n тетрадки и m химикалки е:” — two goods priced relative to each other.
    Every noun carries its own article and agreement; none is derived."""
    first, first_pl, second, second_pl, end = rng.choice(_TWO_GOODS)
    a = Fraction(rng.choice([20, 30, 50, 80, 100, 120, 150, 200, 250]), 100)
    n, m = rng.randint(2, 6), rng.randint(2, 6)
    cheaper = rng.random() < 0.6
    a_txt = bg_decimal(a, places=2)
    c0 = -m * a if cheaper else m * a
    sign = "+" if c0 > 0 else "-"
    c0_txt = bg_decimal(abs(c0), places=2)
    key = f"{n + m}x {sign} {c0_txt}"
    wr = [f"{n + m}x {sign} {a_txt}", f"{n}x {sign} {c0_txt}",
          f"{n + m}x {'-' if sign == '+' else '+'} {c0_txt}"]
    if len({key, *wr}) < 4:
        raise Retry("four distinct expressions")
    options, letter = shuffle_options(f"${key}$", [f"${w}$" for w in wr], rng=rng)
    return GeneratedItem(
        topic=slot.topic, kind="mc", points=slot.points,
        stem=(f"{first} струва $x$ евро, а {second} е с ${a_txt}$ евро "
              f"по-{'евтин' if cheaper else 'скъп'}{end}. Цената на ${n}$ {first_pl} и "
              f"${m}$ {second_pl}, изразена чрез $x$, е:"),
        options=options, correct_answer=letter, difficulty="medium",
        solution=(rf"${n}x + {m}\left(x {'-' if cheaper else '+'} {a_txt}\right) = {key}$"),
        signature=f"expr_price:{first}:{a}:{n}:{m}:{cheaper}",
    )
