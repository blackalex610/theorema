"""The rebuilt Part 2 proof figures assert what their stems claim.

These three used to place L, P, Q and K at random along a side. The scale
notice forgives a figure's proportions; it does not forgive a bisector that
does not bisect, or a "perpendicular" that is not one — and a proof figure is
the one a student stares at for twenty minutes. Every check runs on the posed
output, after the similarity transform ``to_spec`` applies.
"""
from __future__ import annotations

import math
import random
import re

import pytest

from app.nvo_gen import part2_bank as p2
from app.nvo_gen import part2_geometry as p2_geo


def _pts(item):
    return {k: tuple(v) for k, v in item.scene["points"].items()}


def _ang(v, a, b):
    ax, ay = a[0] - v[0], a[1] - v[1]
    bx, by = b[0] - v[0], b[1] - v[1]
    return math.degrees(math.acos((ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by))))


def _d(a, b):
    return math.dist(a, b)


@pytest.mark.parametrize("seed", range(30))
def test_rectangle_proof_figure(seed):
    p = _pts(p2.rectangle_bisectors_proof(random.Random(seed)))
    assert _ang(p["A"], p["B"], p["D"]) == pytest.approx(90, abs=0.2)
    assert _ang(p["D"], p["A"], p["Q"]) == pytest.approx(_ang(p["D"], p["Q"], p["B"]), abs=0.2)
    assert _ang(p["B"], p["D"], p["P"]) == pytest.approx(_ang(p["B"], p["P"], p["C"]), abs=0.2)
    # R on line CB beyond B, and ARBD a parallelogram
    assert _ang(p["B"], p["C"], p["R"]) == pytest.approx(180, abs=0.2)
    assert _d(p["A"], p["R"]) == pytest.approx(_d(p["B"], p["D"]), rel=1e-3)
    assert _d(p["A"], p["C"]) == pytest.approx(_d(p["A"], p["R"]), rel=1e-3)   # part Б


@pytest.mark.parametrize("seed", range(30))
def test_isosceles_rhombus_figure(seed):
    item = p2.isosceles_rhombus_proof(random.Random(seed))
    p = _pts(item)
    blc = int(re.search(r"BLC = (\d+)", item.stem).group(1))
    assert _d(p["C"], p["A"]) == pytest.approx(_d(p["C"], p["B"]), rel=1e-3)
    assert _ang(p["B"], p["A"], p["L"]) == pytest.approx(_ang(p["B"], p["L"], p["C"]), abs=0.2)
    assert _ang(p["L"], p["B"], p["C"]) == pytest.approx(blc, abs=0.2)
    assert _ang(p["M"], p["Q"], p["B"]) == pytest.approx(90, abs=0.2)
    assert _d(p["B"], p["M"]) == pytest.approx(_d(p["M"], p["L"]), rel=1e-3)
    sides = [_d(p["P"], p["B"]), _d(p["B"], p["Q"]), _d(p["Q"], p["L"]), _d(p["L"], p["P"])]
    assert max(sides) - min(sides) < 0.01 * max(sides)                       # part Б
    assert _d(p["A"], p["L"]) == pytest.approx(_d(p["B"], p["Q"]), rel=1e-3)  # part В
    assert _d(p["A"], p["P"]) > _d(p["P"], p["Q"])                             # part Г


@pytest.mark.parametrize("seed", range(10))
def test_parallelogram_height_figure(seed):
    p = _pts(p2.parallelogram_height_proof(random.Random(seed)))
    assert _ang(p["A"], p["B"], p["D"]) == pytest.approx(45, abs=0.2)
    assert _ang(p["A"], p["B"], p["C"]) == pytest.approx(15, abs=0.2)        # 2 : 1 split
    assert _ang(p["K"], p["D"], p["A"]) == pytest.approx(90, abs=0.2)
    assert _ang(p["H"], p["D"], p["A"]) == pytest.approx(90, abs=0.2)
    assert _ang(p["D"], p["A"], p["L"]) == pytest.approx(60, abs=0.2)        # part А
    assert _d(p["B"], p["C"]) == pytest.approx(2 * _d(p["D"], p["H"]), rel=1e-3)
    assert _d(p["A"], p["F"]) == pytest.approx(_d(p["D"], p["L"]), rel=1e-3)  # part Б


# ─── 2019–2021 transcriptions (part2_geometry.py) ────────────────────────────

import re as _re


@pytest.mark.parametrize("seed", range(30))
def test_heights_and_midpoint_figure_and_key(seed):
    item = p2_geo.heights_and_midpoint(random.Random(seed))
    p = _pts(item)
    assert _ang(p["A"], p["B"], p["C"]) == pytest.approx(60, abs=0.2)
    assert _ang(p["D"], p["C"], p["B"]) == pytest.approx(90, abs=0.2)
    assert _ang(p["K"], p["B"], p["C"]) == pytest.approx(90, abs=0.2)
    mk, md, kd = _d(p["M"], p["K"]), _d(p["M"], p["D"]), _d(p["K"], p["D"])
    assert mk == pytest.approx(md, rel=1e-3) and kd == pytest.approx(mk, rel=1e-3)
    bc = int(_re.search(r"BC = (\d+)", item.stem).group(1))
    assert item.answers[1] == f"{3 * bc / 2:g}".replace(".", ",") + " cm"
    # areas, from the drawn figure scaled to the stated BC
    k = bc / _d(p["B"], p["C"])
    area = lambda a, b, c: abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    s_bkc = area(p["B"], p["K"], p["C"]) * k * k
    s_bdc = area(p["B"], p["D"], p["C"]) * k * k
    got = [float(v.replace(",", ".")) for v in _re.findall(r"= ([\d,]+) cm²", item.answers[2])]
    assert got == pytest.approx([s_bkc, s_bdc], rel=1e-3)


@pytest.mark.parametrize("seed", range(30))
def test_equilateral_third_point_figure_and_key(seed):
    item = p2_geo.equilateral_third_point(random.Random(seed))
    p = _pts(item)
    side = _d(p["A"], p["B"])
    assert _d(p["B"], p["C"]) == pytest.approx(side, rel=1e-3)
    assert _d(p["C"], p["M"]) == pytest.approx(side / 3, rel=1e-3)
    assert _ang(p["K"], p["M"], p["B"]) == pytest.approx(90, abs=0.2)
    assert _d(p["K"], p["B"]) == pytest.approx(side / 3, rel=1e-3)          # part А
    assert _d(p["A"], p["M"]) == pytest.approx(_d(p["C"], p["K"]), rel=1e-3)  # part Б
    area = lambda a, b, c: abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    s = int(_re.search(r"е \$(\d+)\$ cm", item.stem).group(1))
    ratio = area(p["A"], p["C"], p["M"]) / area(p["K"], p["C"], p["M"])
    assert int(item.answers[2].split()[0]) == pytest.approx(s * ratio, rel=1e-3)   # part В


@pytest.mark.parametrize("seed", range(30))
def test_bisector_meets_perp_bisector_figure_and_key(seed):
    item = p2_geo.bisector_meets_perp_bisector(random.Random(seed))
    p = _pts(item)
    assert _ang(p["A"], p["B"], p["C"]) == pytest.approx(30, abs=0.2)
    assert _ang(p["B"], p["A"], p["C"]) == pytest.approx(105, abs=0.2)
    assert _d(p["M"], p["A"]) == pytest.approx(_d(p["M"], p["C"]), rel=1e-3)
    assert _d(p["K"], p["A"]) == pytest.approx(_d(p["K"], p["C"]), rel=1e-3)
    assert _ang(p["A"], p["B"], p["M"]) == pytest.approx(15, abs=0.2)
    # the congruence the item asks for: KMC ≅ KBC, so CB = CM and BK = MK
    assert _d(p["C"], p["B"]) == pytest.approx(_d(p["C"], p["M"]), rel=1e-3)
    assert _d(p["B"], p["K"]) == pytest.approx(_d(p["M"], p["K"]), rel=1e-3)
    s = int(_re.search(r"AM \+ MK = (\d+)", item.parts[3]).group(1))
    scale = s / (_d(p["A"], p["M"]) + _d(p["M"], p["K"]))
    perim = (_d(p["B"], p["C"]) + _d(p["C"], p["M"]) + _d(p["M"], p["K"]) + _d(p["K"], p["B"])) * scale
    assert int(item.answers[3].split()[0]) == pytest.approx(perim, rel=1e-3)
