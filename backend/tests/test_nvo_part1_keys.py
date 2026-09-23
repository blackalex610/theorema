"""Part 1 keys for the templates added or rewritten in the corpus study,
re-derived from what the student reads — the stem, the chart, the table.

Each check is written from the stem's wording, not from the template's code:
it pulls the numbers out of the printed text and does the arithmetic again.
A template whose options drift from its stem fails here even if it verifies.
"""
from __future__ import annotations

import math
import random
import re
from fractions import Fraction as F

import pytest

from app.nvo_gen import registry
from app.nvo_gen.blueprints import BLUEPRINTS
from app.nvo_gen.registry import Retry
from tests.test_nvo_part2_keys import REL, _split_rel, _tex_eval

SEEDS = range(60)


def _slot(code):
    t = registry.get_template(code)
    fitting = [s for bp in BLUEPRINTS.values() for s in bp.slots if t.fits(s)]
    return next((s for s in fitting if s.kind == "mc"), fitting[0])


def _items(code):
    t, slot = registry.get_template(code), _slot(code)
    out = []
    for seed in SEEDS:
        try:
            out.append(t.build(random.Random(seed), slot))
        except Retry:
            continue
    assert len(out) >= 10, f"{code} built only {len(out)} items"
    return out


def _value(text: str) -> F:
    """An option's number: $12$, $-\\frac{3}{4}$, $12{,}5$ km, $40\\%$."""
    t = text.replace("{,}", ".").replace("$", "").replace(r"\%", "").replace("−", "-")
    m = re.search(r"(-?)\\frac\{(-?\d+)\}\{(\d+)\}", t)
    if m:
        return F(int(m.group(2)), int(m.group(3))) * (-1 if m.group(1) else 1)
    return F(re.search(r"-?\d+(?:\.\d+)?", t).group(0))


def _key(item) -> str:
    if not item.options:                       # a short-answer item: the key is the answer
        return str(item.correct_answer)
    return item.options["АБВГ".index(item.correct_answer)]


def _nums(text: str) -> list[F]:
    return [F(v.replace("{,}", ".").replace(",", ".")) for v in
            re.findall(r"-?\d+(?:\{,\}\d+|,\d+(?=\D))?", text.replace(" ", ""))]


def _is_prime(n):
    return n > 1 and all(n % d for d in range(2, int(math.isqrt(n)) + 1))


# ─── number sense and probability ───────────────────────────────────────────

def test_primes_in_list():
    for it in _items("primes_in_list"):
        listed = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
        assert _value(_key(it)) == sum(_is_prime(n) for n in listed)


def test_prob_letters_on_cards():
    for it in _items("prob_letters_on_cards"):
        letters = re.search(r"буквите (.+?)\. ", it.stem).group(1).split(", ")
        if "гласна" in it.stem:
            fav = sum(c in "АЕИОУЪЮЯ" for c in letters)
        elif "различна от" in it.stem:
            c = re.search(r"различна от (\w)", it.stem).group(1)
            fav = len(letters) - letters.count(c)
        else:
            c = re.search(r"буквата (\w)\?", it.stem).group(1)
            fav = letters.count(c)
        assert _value(_key(it)) == F(fav, len(letters)), it.stem


def test_prob_number_property():
    ranges = {"едноцифрено неотрицателно число": range(0, 10),
              "едноцифрено естествено число": range(1, 10),
              "двуцифрено число": range(10, 100)}
    for it in _items("prob_number_property"):
        m = re.search(r"от \$1\$ до \$(\d+)\$", it.stem)
        nums = range(1, int(m.group(1)) + 1) if m else next(
            r for k, r in ranges.items() if k in it.stem)
        d = re.search(r"(?:на|цифрата) \$(\d+)\$", it.stem)
        if "се дели" in it.stem:
            fav = sum(n % int(d.group(1)) == 0 for n in nums)
        elif "завършва" in it.stem:
            fav = sum(n % 10 == int(d.group(1)) for n in nums)
        elif "просто" in it.stem:
            fav = sum(_is_prime(n) for n in nums)
        else:
            fav = sum(math.isqrt(n) ** 2 == n for n in nums)
        assert _value(_key(it)) == F(fav, len(nums)), it.stem


# ─── means ───────────────────────────────────────────────────────────────────

def test_mean_next_score():
    for it in _items("mean_next_score"):
        s = it.stem.replace("$", "")
        n = int(re.search(r"(\d+) (?:контролни работи|дни от|дни на)", s).group(1))
        n1 = int(re.search(r"(?:тези|за) (\d+)", s).group(1))
        t = F(re.findall(r"(\d+)(?: хляба| km)?\?", s)[-1])
        m = F(re.search(r"(?<!\w)(?:е|по) (\d+(?:,\d+)?)(?: хляба| km)?(?: на ден)?[ .]", s).group(1)
              .replace(",", "."))
        assert n1 == n + 1, s
        assert _value(_key(it)) == n1 * t - n * m, s


def test_mean_three_friends():
    for it in _items("mean_three_friends"):
        d1, d2, mean = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
        assert d1 == d2
        names = re.findall(r"^(\w+) има с|от (\w+) и|от (\w+)\. ", it.stem)
        high = re.search(r"по-малко от (\w+)\.", it.stem).group(1)
        asked = re.search(r"има (\w+), ако", it.stem).group(1)
        want = mean + d1 if asked == high else mean - d1
        assert _value(_key(it)) == want, it.stem
        del names


# ─── absolute value, shortcuts, factoring, powers ────────────────────────────

def _abs_solutions(eq: str) -> int:
    m = re.fullmatch(r"\$\\left\|x(?: ([+-]) (\d+))?\\right\|(?: ([+-]) (\d+))? = (-?\d+)\$", eq)
    assert m, eq
    shift = int(m.group(4) or 0) * (1 if m.group(3) == "+" else -1)
    rhs = int(m.group(5)) - shift
    return 0 if rhs < 0 else 1 if rhs == 0 else 2


def test_abs_equation_which():
    for it in _items("abs_equation_which_no_solution"):
        want = 0 if "няма решение" in it.stem else 1 if "един корен" in it.stem else 2
        counts = [_abs_solutions(o) for o in it.options]
        assert counts["АБВГ".index(it.correct_answer)] == want
        assert counts.count(want) == 1, (it.stem, it.options)


def test_diff_squares_decimal():
    for it in _items("diff_squares_decimal"):
        a, b = [F(v.replace("{,}", ".")) for v in re.findall(r"([\d{},]+)\^2", it.stem)]
        assert _value(_key(it)) == a * a - b * b


def _option_poly_equal(expr_tex: str, target_tex: str) -> bool:
    return all(_tex_eval(expr_tex, x=F(v)) == _tex_eval(target_tex, x=F(v)) for v in (-3, 1, 2, 5))


def test_factor_diff_squares_signs():
    for it in _items("factor_diff_squares_signs"):
        target = re.search(r"\$(.+?)\$", it.stem).group(1)
        matches = [_option_poly_equal(o.strip("$"), target) for o in it.options]
        assert matches.count(True) == 1 and matches["АБВГ".index(it.correct_answer)], it.options


def test_factor_not_a_factor():
    for it in _items("factor_not_a_factor"):
        P = re.search(r"многочлена \$(.+?)\$", it.stem).group(1)
        zero = [_tex_eval(P, x=F(-_value(o.replace("x", "").replace(" ", "")) if "+" in o
                                  else _value(o.replace("x", "").replace(" ", "").replace("-", ""))))
                == 0 for o in it.options]
        assert zero.count(False) == 1 and not zero["АБВГ".index(it.correct_answer)], it.options


def test_power_quotient_at_value():
    for it in _items("power_quotient_at_value"):
        expr = re.search(r"израза \$(.+?)\$", it.stem).group(1)
        x = _value(re.search(r"x = (.+?)\$", it.stem).group(1))
        assert _value(_key(it)) == _tex_eval(expr, x=x), it.stem


def test_map_scale_from_distances():
    for it in _items("map_scale_from_distances"):
        km, cm = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
        scale = int(_key(it).replace(r"\,", "").split(":")[1].strip(" $"))
        assert scale == km * 100_000 // cm and km * 100_000 % cm == 0


# ─── equations and inequalities that reduce to linear ───────────────────────

def test_linear_equation_squares_cancel():
    for it in _items("linear_equation_squares_cancel"):
        eq = re.search(r"\$(.+)\$", it.stem).group(1)
        lhs, rhs = eq.split(" = ")
        root = _value(_key(it))
        assert _tex_eval(lhs, x=root) == _tex_eval(rhs, x=root), eq


def test_inequality_squares_cancel_integer():
    for it in _items("inequality_squares_cancel_integer"):
        ineq = re.search(r"\$(.+)\$", it.stem).group(1)
        lhs, rel, rhs = _split_rel(ineq)
        holds = lambda v: REL[rel](_tex_eval(lhs, x=F(v)), _tex_eval(rhs, x=F(v)))
        ext = int(_value(_key(it)))
        step = -1 if it.stem.startswith("Най-малкото") else 1
        assert holds(ext) and not holds(ext + step), ineq


# ─── expressions from words ──────────────────────────────────────────────────

def test_expression_from_words_age():
    for it in _items("expression_from_words_age"):
        a, b = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
        x = F(11)
        if "сборът от годините им ще" in it.stem:
            want = x + b + x + a + b
        elif "Преди" in it.stem:
            want = x - b + x + a - b
        else:
            want = x + a + b
        assert _tex_eval(_key(it).strip("$"), x=x) == want, it.stem


def test_expression_from_words_price():
    for it in _items("expression_from_words_price"):
        a = F(re.search(r"с \$([\d{},]+)\$ евро", it.stem).group(1).replace("{,}", "."))
        n, m = [int(v) for v in re.findall(r"на \$(\d+)\$ .+? и \$(\d+)\$", it.stem)[0]]
        x = F(7)
        second = x - a if "по-евтин" in it.stem else x + a
        assert _tex_eval(_key(it).strip("$"), x=x) == n * x + m * second, it.stem


# ─── word problems ───────────────────────────────────────────────────────────

def test_work_rate_pipes_and_people():
    for code in ("work_rate_pipes", "work_rate_two_people"):
        for it in _items(code):
            a, b = [int(v) for v in re.findall(r"(\d+)\$? (?:часа|минути)", it.stem)][:2]
            assert _value(_key(it)) == F(a * b, a + b), it.stem


def test_work_rate_second_worker():
    for it in _items("work_rate_second_worker"):
        a, t = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
        assert F(1, t) - F(1, a) == 1 / _value(_key(it)), it.stem


def test_percent_annual_interest():
    for it in _items("percent_annual_interest"):
        p, total = [int(v.replace(" ", "")) for v in re.findall(r"(\d[\d ]*\d) евро", it.stem)]
        assert _value(_key(it)) == F(total - p, p) * 100, it.stem


def test_percent_of_a_quantity():
    for it in _items("percent_of_a_quantity"):
        total, given = [int(v) for v in re.findall(r"(\d+)", it.stem)][:2]
        assert _value(_key(it)) == F(total - given, total) * 100, it.stem


def test_percent_of_route_two_days():
    for it in _items("percent_of_route_two_days"):
        p, q, left = [int(v) for v in re.findall(r"\$(\d+)", it.stem)]
        whole = _value(_key(it))
        assert whole * F(100 - p, 100) * F(100 - q, 100) == left, it.stem


def test_percent_part_of_whole():
    for it in _items("percent_part_of_whole"):
        a = int(re.search(r"има (\d+)|работят (\d+)", it.stem).group(1) or
                re.search(r"работят (\d+)", it.stem).group(1))
        num, den = [int(v) for v in re.search(r"\\frac\{(\d+)\}\{(\d+)\}", it.stem).groups()]
        assert _value(_key(it)) == a + a * F(den, num), it.stem


def test_ratio_and_mixture_three_parts():
    for code in ("ratio_three_parts", "mixture_three_part_ratio"):
        for it in _items(code):
            ratio = [int(v) for v in re.search(r"\$(\d+) : (\d+) : (\d+)\$", it.stem).groups()]
            total = int(re.search(r"(?:сборът им е|разделили|общо|в) \$?(\d+)\$?", it.stem).group(1))
            unit = F(total, sum(ratio))
            got = _value(_key(it))
            assert got in {unit * r for r in ratio}, it.stem
            if code == "ratio_three_parts":
                want = max(ratio) if "най-голям" in it.stem.lower() or "най-много" in it.stem else min(ratio)
                assert got == unit * want, it.stem


def test_mixture_fat_content():
    for it in _items("mixture_fat_content"):
        v2, v1, p1, vt, pm = [F(v.replace("{,}", ".")) for v in
                              re.findall(r"\$([\d{},]+)(?:\\%)?\$", it.stem)]
        assert v1 * p1 + v2 * _value(_key(it)) == vt * pm, it.stem


def test_units_map_scale():
    for it in _items("units_map_scale"):
        if "Мащабът" in it.stem:
            n = int(re.search(r"1 : ([\d\\,]+)\$", it.stem).group(1).replace(r"\,", ""))
            cm = F(re.search(r"е \$([\d{},]+)\$ cm", it.stem).group(1).replace("{,}", "."))
            assert _value(_key(it)) == cm * n / 100_000, it.stem
        else:
            cm_ref, km_ref, cm_q = [int(v) for v in re.findall(r"\$(\d+)\$", it.stem)]
            assert _value(_key(it)) == F(km_ref, cm_ref) * cm_q, it.stem


# ─── data ────────────────────────────────────────────────────────────────────

def test_chart_pie_sector():
    for it in _items("chart_pie_sector"):
        total = int(re.search(r"(\d+)", it.stem).group(1))
        sectors = {s["label"]: F(s["deg"]).limit_denominator() for s in it.scene["sectors"]}
        asked = next(l for l in sectors if l in it.stem or l.rstrip("и") in it.stem)
        assert _value(_key(it)) == F(total * sectors[asked], 360), it.stem


def test_table_share_of_total():
    shares = {r"$\frac{n}{2}$": F(1, 2), r"$\frac{n}{4}$": F(1, 4), r"$75\%$ от $n$": F(3, 4),
              r"$\frac{n}{3}$": F(1, 3), r"$\frac{2n}{3}$": F(2, 3), r"$2n$": F(2),
              r"$50\%$ от $n$": F(1, 2), r"$\frac{3n}{2}$": F(3, 2), r"$25\%$ от $n$": F(1, 4),
              "$n$": F(1)}
    for it in _items("table_share_of_total"):
        total = int(re.search(r"общо (\d+)", it.stem).group(1))
        headers, row = it.scene["headers"], it.scene["rows"][0]
        n = F(total) / sum(shares[c] for c in row)
        asked = next(h for h in headers if re.search(rf"(книги|килограма|клуба по) {re.escape(h)}", it.stem))
        assert _value(_key(it)) == n * shares[row[headers.index(asked)]], it.stem


def test_side_ordering():
    for it in _items("order_angles_by_sides"):
        bc, ac, ab = [int(v) for v in re.findall(r"= (\d+)\$ cm", it.stem)]
        opp = {"BAC": bc, "ABC": ac, "ACB": ab}
        chain = re.findall(r"sphericalangle (\w+)", _key(it))
        assert [opp[c] for c in chain] == sorted(opp.values()), it.stem
    for it in _items("order_sides_two_given_angles"):
        given = dict(re.findall(r"sphericalangle (\w+) = (\d+)", it.stem))
        angles = {k: int(v) for k, v in given.items()}
        missing = ({"BAC", "ABC", "ACB"} - set(angles)).pop()
        angles[missing] = 180 - sum(angles.values())
        side_of = {"BAC": "BC", "ABC": "AC", "ACB": "AB"}
        want = " < ".join(side_of[k] for k, _ in sorted(angles.items(), key=lambda kv: kv[1]))
        assert _key(it).strip("$") == want, it.stem
