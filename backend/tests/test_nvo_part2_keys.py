"""Part 2 keys, re-derived from the printed stem — never from the builder.

The Part 2 bank shipped four items whose keys were wrong or impossible:

  * the 2021 Q22 equation transcribed with ``x(x − 4)/9`` instead of
    ``x(0,5x − 4)/9``, so every variant had irrational roots;
  * an inequality whose answer was x > 125/59, keyed as "Интервал";
  * a bus/car meeting that stated three facts that contradict each other;
  * a brigade problem whose day counts were fractions in 8 draws out of 9.

Each of those would have failed here. The algebra checks parse the LaTeX the
student actually reads (``_tex_eval`` is deliberately independent of
``poly.Expr``, which built it) and substitute the key back in. The word
problems pull the numbers out of the stem and check the key satisfies every
condition the story states.
"""
from __future__ import annotations

import random
import re
from fractions import Fraction as F

import pytest

from app.nvo_gen import part2_algebra as alg
from app.nvo_gen import part2_word as word
from app.nvo_gen.blueprints import BLUEPRINTS
from app.nvo_gen.part2_bank import bank_for
from app.nvo_gen.verify import check_item

SEEDS = range(80)


# ─── a small, separate reader for the stems' LaTeX ──────────────────────────

def _strip_group(s: str, i: int) -> tuple[str, int]:
    """Return the contents of the {...} group starting at s[i] and the index after it."""
    assert s[i] == "{", s[i:]
    depth, j = 0, i
    while True:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1


def _to_python(tex: str) -> str:
    out, i = "", 0
    while i < len(tex):
        for cmd in (r"\dfrac", r"\frac"):
            if tex.startswith(cmd, i):
                num, i = _strip_group(tex, i + len(cmd))
                den, i = _strip_group(tex, i)
                out += f"(({_to_python(num)})/({_to_python(den)}))"
                break
        else:
            out += tex[i]
            i += 1
    return out


def _tex_eval_src(tex: str) -> str:
    s = tex.replace("{,}", ".").replace(",", ".")
    s = _to_python(s)
    s = s.replace(r"\left|", " abs(").replace(r"\right|", ") ")
    s = s.replace(r"\left(", "(").replace(r"\right)", ")")
    s = s.replace(r"\cdot", "*")
    s = re.sub(r"\^\{?(\d+)\}?", r"**\1", s)
    s = re.sub(r"(\d+(?:\.\d+)?)", r"F('\1')", s)
    # implicit multiplication: 3x, 2(…), x(…), )(…), )x, x x
    s = re.sub(r"(\))\s*(?=[\w(])", r"\1*", s)
    s = re.sub(r"(F\('[\d.]+'\))\s*(?=[xy(])", r"\1*", s)
    s = re.sub(r"\b([xy])\s*(?=[(xyF])", r"\1*", s)
    s = s.replace("abs*(", "abs(")
    return s


def _tex_eval(tex: str, **env) -> F:
    return eval(_tex_eval_src(tex), {"F": F, "abs": abs}, dict(env))


def _math(text: str) -> list[str]:
    return re.findall(r"\$([^$]*)\$", text)


def _num(text: str) -> F:
    return F(text.replace(",", ".").replace("−", "-").strip())


REL = {"<": lambda a, b: a < b, ">": lambda a, b: a > b,
       r"\le": lambda a, b: a <= b, r"\ge": lambda a, b: a >= b,
       "≤": lambda a, b: a <= b, "≥": lambda a, b: a >= b}


def _split_rel(tex: str) -> tuple[str, str, str]:
    m = re.search(r"\s(\\le|\\ge|<|>)\s", tex)
    assert m, tex
    return tex[:m.start()], m.group(1), tex[m.end():]


def _check_inequality_answer(tex: str, answer: str, var: str) -> None:
    """The keyed half-line must be exactly the set where the printed inequality holds."""
    lhs, rel, rhs = _split_rel(tex)
    m = re.fullmatch(rf"{var} (<|>|≤|≥) (-?[\d,/]+)", answer.strip())
    assert m, answer
    arel, bound = m.group(1), _num(m.group(2)) if "/" not in m.group(2) else F(m.group(2))
    holds = lambda v: REL[rel](_tex_eval(lhs, **{var: v}), _tex_eval(rhs, **{var: v}))
    keyed = lambda v: REL[arel](v, bound)
    for probe in (bound - 3, bound - F(1, 100), bound, bound + F(1, 100), bound + 3):
        assert holds(probe) == keyed(probe), (tex, answer, probe)


# ─── algebra ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_cube_expansion_key(seed):
    item = alg.cube_expansion_and_inequality(random.Random(seed))
    M = _math(item.stem)[0].split("=", 1)[1]
    normal = item.answers[0].split("=", 1)[1].replace(",", "{,}")
    for x in (F(-3), F(0), F(1, 2), F(2), F(7)):
        assert _tex_eval(M, x=x) == _tex_eval(normal, x=x), (item.stem, item.answers[0])
    _check_inequality_answer(_math(item.parts[1])[0], item.answers[1], "x")

    eq = _math(item.parts[2])[0]
    inner, f_ = eq.rsplit("=", 1)
    good, bad = re.findall(r"x = (-?[\d,]+)", item.answers[2])
    for r in (_num(good), _num(bad)):
        assert abs(_tex_eval(inner, x=r)) == _num(f_), (eq, r)
    lhs, rel, rhs = _split_rel(_math(item.parts[1])[0])
    passes = lambda v: REL[rel](_tex_eval(lhs, x=v), _tex_eval(rhs, x=v))
    assert passes(_num(good)) and not passes(_num(bad)), item.answers


@pytest.mark.parametrize("seed", SEEDS)
def test_fractional_equation_key(seed):
    item = alg.fractional_equation_and_inequality(random.Random(seed))
    eq, ineq = _math(item.stem)
    root = _num(item.answers[0].split("=")[1])
    lhs, rhs = eq.split(" = ")
    assert _tex_eval(lhs, x=root) == _tex_eval(rhs, x=root), (eq, root)
    # and the x² really cancelled: the equation is linear, so the root is unique
    diff = lambda v: _tex_eval(lhs, x=v) - _tex_eval(rhs, x=v)
    assert diff(root + 1) - diff(root) == diff(root + 2) - diff(root + 1) != 0
    _check_inequality_answer(ineq, item.answers[1], "y")
    ilhs, rel, irhs = _split_rel(ineq)
    inside = REL[rel](_tex_eval(ilhs, y=root), _tex_eval(irhs, y=root))
    assert ("не е" not in item.answers[2]) == inside


@pytest.mark.parametrize("seed", SEEDS)
def test_factor_then_inequality_key(seed):
    item = alg.factor_then_roots_then_inequality(random.Random(seed))
    P = _math(item.stem)[0].split("=", 1)[1]
    roots = [int(v) for v in re.findall(r"x_\d = (-?\d+)", item.answers[0])]
    assert len(set(roots)) == 2
    for r in roots:
        assert _tex_eval(P, x=F(r)) == 0
    ineq = _math(item.parts[1])[0]
    _check_inequality_answer(ineq, item.answers[1], "x")
    lhs, rel, rhs = _split_rel(ineq)
    for r in roots:
        inside = REL[rel](_tex_eval(lhs, x=F(r)), _tex_eval(rhs, x=F(r)))
        assert (f"{r} е решение" in item.answers[2]) == inside, (item.answers, r)


@pytest.mark.parametrize("seed", SEEDS)
def test_grouping_key(seed):
    item = alg.grouping_into_linear_factors(random.Random(seed))
    M = _math(item.stem)[0].split("=", 1)[1]
    product = item.answers[0].split("=", 1)[1].replace("(", r"\left(").replace(")", r"\right)")
    for x in (F(-4), F(-1, 3), F(0), F(5, 2), F(9)):
        assert _tex_eval(M, x=x) == _tex_eval(product, x=x)
    zeros = [int(v) for v in re.findall(r"x = (-?\d+)", item.answers[1])]
    assert zeros and all(_tex_eval(M, x=F(z)) == 0 for z in zeros)
    # every integer zero is listed (rational roots of a monic poly are integers
    # dividing the constant term)
    const = abs(_tex_eval(M, x=F(0)))
    for cand in range(-int(const) - 1, int(const) + 2):
        if _tex_eval(M, x=F(cand)) == 0:
            assert cand in zeros
    ineq = _math(item.parts[2])[0]
    lhs, rel, rhs = _split_rel(ineq)
    holds = lambda v: REL[rel](_tex_eval(lhs, x=F(v)), _tex_eval(rhs, x=F(v)))
    ext = int(item.answers[2])
    assert holds(ext)
    step = -1 if "най-малкото" in item.parts[2] else 1
    assert not holds(ext + step), (ineq, ext)


@pytest.mark.parametrize("seed", SEEDS)
def test_three_equations_key(seed):
    item = alg.three_equations_equivalence(random.Random(seed))
    e1, e2, e3 = [m.split(r"\ ", 1)[1] for m in _math(item.stem) if m.startswith("(")]
    r1 = _num(item.answers[0].split("=")[1])
    l, r = e1.split(" = ")
    assert _tex_eval(l, x=r1) == _tex_eval(r, x=r1)

    def roots_of(eq, answer):
        vals = [_num(v) for v in answer.split("=")[1].split(" и ")]
        l, r = eq.split(" = ")
        for v in vals:
            assert _tex_eval(l, x=v) == _tex_eval(r, x=v), (eq, v)
        # nothing else on a wide integer/half grid solves it
        grid = [F(n, 2) for n in range(-60, 61)]
        found = {v for v in grid if _tex_eval(l, x=v) == _tex_eval(r, x=v)}
        assert found <= set(vals)
        return frozenset(vals)

    s1, s2, s3 = frozenset([r1]), roots_of(e2, item.answers[1]), roots_of(e3, item.answers[2])
    pairs = {"(1) и (2)": s1 == s2, "(1) и (3)": s1 == s3, "(2) и (3)": s2 == s3}
    expected = [k for k, v in pairs.items() if v]
    if expected:
        assert item.answers[3] == expected[0] and len(expected) == 1
    else:
        assert item.answers[3].startswith("няма")


# ─── word problems ──────────────────────────────────────────────────────────

def _ints(text: str) -> list[F]:
    return [_num(v) for v in re.findall(r"\$(-?[\d{},]+)\$", text.replace("{,}", ","))]


@pytest.mark.parametrize("seed", SEEDS)
def test_gold_key(seed):
    item = word.gold_carat_mixture(random.Random(seed))
    mass, carats = _ints(item.parts[0])
    m1, c1, m2, c2 = _ints(item.parts[1])
    hi, plate, lo = _ints(item.parts[2])
    assert _num(item.answers[0].split()[0]) == mass * carats / 24
    assert _num(item.answers[1].split()[0]) == (m1 * c1 + m2 * c2) / (m1 + m2)
    total = _num(item.answers[2].split()[0])
    assert plate * hi == total * lo            # pure gold is conserved


@pytest.mark.parametrize("seed", SEEDS)
def test_meeting_key(seed):
    item = word.two_vehicles_meeting(random.Random(seed))
    nums = _ints(item.stem)
    hours = [n for n in nums]
    # stem order: start h [start min], delay, Δ, meet h [meet min]
    times = re.findall(r"\$(\d+)\$ часà(?: и \$(\d+)\$ минути)?", item.stem)
    (h0, m0), (h1, m1) = times
    start = int(h0) * 60 + int(m0 or 0)
    meet = int(h1) * 60 + int(m1 or 0)
    delay = int(re.search(r"След \$(\d+)\$ минути", item.stem).group(1))
    delta = int(re.search(r"с \$(\d+)\$ km/h по-голяма", item.stem).group(1))
    car = _num(item.answers[0].split(" km/h")[0])
    dist = _num(item.answers[0].split("; ")[1].split()[0])
    bus = car - delta
    # both cover half the route by the meeting time — the condition the old item broke
    assert bus * F(meet - start, 60) == dist / 2
    assert car * F(meet - start - delay, 60) == dist / 2
    litres = _num(_math(item.parts[1])[0].replace("{,}", ","))
    assert _num(item.answers[1].split()[0]) * (dist / 2) / 100 == litres
    del hours


@pytest.mark.parametrize("seed", SEEDS)
def test_brigades_key(seed):
    item = word.two_brigades_work(random.Random(seed))
    ra, rb, surplus = _ints(item.stem)
    words = {"двама": 2, "трима": 3, "четирима": 4, "петима": 5}
    fewer = words[re.search(r"с (\w+) по-малко", item.stem).group(1)]
    join = words[re.search(r"още (\w+) работници", item.parts[1]).group(1)]
    total = _ints(item.parts[1])[0]
    a, b = [int(v) for v in re.findall(r"\d+", item.answers[0])]
    assert b == a - fewer and ra * a + surplus == rb * b
    d1, d2 = [int(v) for v in re.findall(r"\d+", item.answers[1])]
    assert d1 == d2 + 1
    assert ra * a * d1 + rb * (b + join) * d2 == total


@pytest.mark.parametrize("seed", SEEDS)
def test_plan_versus_actual_key(seed):
    item = word.plan_versus_actual_output(random.Random(seed))
    p, q, early, surplus = [_num(v) for v in re.findall(r"\$(\d+)", item.stem)]
    T = int(item.answers[0].split()[0])
    assert q * (T - early) == p * T + surplus
    planned, actual = [int(v) for v in re.findall(r"(?:планирано|реално) (\d+)", item.answers[1])]
    assert (planned, actual) == (p * T, q * (T - early))
    assert _num(item.answers[2].rstrip("%")) == F(surplus * 100, planned)


@pytest.mark.parametrize("seed", SEEDS)
def test_two_tanks_key(seed):
    item = word.two_tanks_of_fuel(random.Random(seed))
    add, use, gap, ci, _100a, cs, _100b = _ints(item.stem)
    m = 2 if "два пъти" in item.stem else 3
    big_thursday = _num(item.answers[2].split()[0])
    x = big_thursday / m
    stoyan = 100 * (x + add) / cs
    ivan = 100 * (m * x - use) / ci
    assert stoyan - ivan == gap
    assert _num(item.answers[3].split()[0]) == stoyan


@pytest.mark.parametrize("seed", SEEDS)
def test_car_catches_truck_key(seed):
    item = word.car_catches_truck(random.Random(seed))
    ab = _ints(item.stem)[0]
    vt, vc = [int(v) for v in re.findall(r"скорост \$(\d+)\$ km/h", item.stem)]
    rest = int(re.search(r"камиона \$(\d+)\$ km преди", item.stem).group(1))
    times = re.findall(r"\$(\d+)\$ часà(?: и \$(\d+)\$ минути)?", item.stem)
    (h0, m0), (h1, m1) = times
    t_truck, t_car = int(h0) * 60 + int(m0 or 0), int(h1) * 60 + int(m1 or 0)

    def clock(s):
        h, *rest_ = re.findall(r"\d+", s)
        return int(h) * 60 + (int(rest_[0]) if rest_ else 0)

    catch = clock(item.answers[0])
    # same place at the catch-up time
    assert F(vc * (catch - t_car), 60) == ab + F(vt * (catch - t_truck), 60)
    assert clock(item.answers[1]) == catch + F(rest * 60, vc)
    ac = _num(item.answers[2].split()[0])
    assert ac == F(vc * (catch - t_car), 60) + rest
    per100 = _ints(item.parts[3])[-1]
    assert _num(item.answers[3].split()[0]) == ac * per100 / 100


# ─── every Part 2 item, every topic ─────────────────────────────────────────

def _slot(topic):
    return next(s for bp in BLUEPRINTS.values() for s in bp.slots if s.topic == topic)


@pytest.mark.parametrize("topic", ["open_algebra", "open_word_problem", "open_geometry_proof"])
def test_every_part2_item_verifies_and_carries_a_real_key(topic):
    slot = _slot(topic)
    placeholders = {"интервал", "единствен корен", "обоснован извод", "доказателство",
                    "проверка на всеки корен", "ъглите и отношението", "лицата чрез m и n",
                    "разход в литри на 100 km", "брой работници в двете бригади",
                    "брой дни за всяка бригада", "линейно неравенство след опростяване",
                    "трите ъгъла", "доказателство за ромб", "доказателство за лицата"}
    for build in bank_for(topic):
        for seed in range(40):
            item = build(random.Random(seed))
            assert sum(item.points) == slot.total_points, item.code
            assert len(item.parts) == len(item.answers) == len(item.points), item.code
            report = check_item(item.to_generated(slot), slot)
            assert not report.errors, (item.code, report.errors)
            for a in item.answers:
                assert a.strip().lower() not in placeholders, (item.code, a)
