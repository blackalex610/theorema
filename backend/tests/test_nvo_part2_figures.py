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
