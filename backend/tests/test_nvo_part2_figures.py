"""Every claim in every Part 2 proof pool is true of its own figure.

A pool configuration (``part2_proofs``) is a real paper's construction with
6–9 claims; a paper asks 3–4 of them. The scale notice forgives a figure's
proportions, but not a bisector that does not bisect or a "congruence" whose
sides differ — so each claim is measured on the drawn, posed figure, including
the claims a given paper did not pick. Also checked: each marking scheme adds
up to its claim's points, dependencies point backwards, and every assembled
item passes the verifier with exactly 12 points.
"""
from __future__ import annotations

import random
import re

import pytest

from app.nvo_gen import part2_proofs as pp
from app.nvo_gen.blueprints import BLUEPRINTS
from app.nvo_gen.part2_bank import bank_for
from app.nvo_gen.verify import check_item

SEEDS = range(25)
CONFIGS = sorted(pp.CONFIGS)


def _pts(scene) -> pp.Pts:
    return {k: tuple(v) for k, v in scene["points"].items()}


def _slot():
    return next(s for bp in BLUEPRINTS.values() for s in bp.slots if s.topic == "open_geometry_proof")


@pytest.mark.parametrize("name", CONFIGS)
def test_every_claim_holds_on_its_own_figure(name):
    for seed in SEEDS:
        setup = pp.CONFIGS[name](random.Random(seed))
        every = {c.key for c in setup.claims}
        whole = _pts(setup.figure(every, random.Random(seed)))
        for c in setup.claims:
            assert c.check is not None, f"{name}.{c.key} has no check"
            # alone, as a paper that asks only this claim would draw it …
            alone = _pts(setup.figure({c.key, *c.requires}, random.Random(seed + 100)))
            assert c.check(alone), f"{name} seed {seed}: {c.key} is false on its figure"
            # … and on the figure drawn for every claim at once
            assert c.check(whole), f"{name} seed {seed}: {c.key} is false on the full figure"


@pytest.mark.parametrize("name", CONFIGS)
def test_marking_adds_up_and_dependencies_point_backwards(name):
    setup = pp.CONFIGS[name](random.Random(0))
    keys = {c.key: c for c in setup.claims}
    assert len(keys) == len(setup.claims), "duplicate claim keys"
    for c in setup.claims:
        steps = [int(v) for v in re.findall(r"— (\d+) т\.", c.marking)]
        assert sum(steps) == c.points, f"{name}.{c.key}: steps {steps} ≠ {c.points}"
        assert 2 <= c.points <= 5
        for q in c.requires:
            assert q in keys, f"{name}.{c.key} requires unknown {q}"
            assert keys[q].rank < c.rank, f"{name}.{c.key} requires the later {q}"
        assert c.answer.strip() and c.answer.strip().lower() not in {"доказателство", "интервал"}


@pytest.mark.parametrize("name", CONFIGS)
def test_each_configuration_can_ask_several_different_papers(name):
    setup = pp.CONFIGS[name](random.Random(0))
    assert pp.valid_selections(setup.claims) >= 3, name


def test_the_pools_together_ask_about_a_hundred_different_proofs():
    total = sum(pp.valid_selections(fn(random.Random(0)).claims) for fn in pp.CONFIGS.values())
    assert total >= 90, total


@pytest.mark.parametrize("build", bank_for("open_geometry_proof"), ids=lambda b: b.__name__)
def test_every_assembled_proof_verifies_and_reads_easy_to_hard(build):
    slot = _slot()
    for seed in SEEDS:
        item = build(random.Random(seed))
        assert sum(item.points) == 12 and 3 <= len(item.parts) <= 4, item.code
        assert [p[0] for p in item.parts] == list("АБВГ"[:len(item.parts)])
        report = check_item(item.to_generated(slot), slot)
        assert not report.errors, (item.code, report.errors)


def test_twelve_configurations_from_twelve_papers():
    assert len(pp.CONFIGS) == 12


# ─── construction details the claims do not measure ─────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_2017_triangle_really_is_acute(seed):
    """The paper's own AB = 14 cm with d = 4 cm gives ∠C ≈ 91°; ours must not."""
    setup = pp.altitude_point(random.Random(seed))
    p = _pts(setup.figure(set(), random.Random(seed)))
    for v, a, b in (("A", "B", "C"), ("B", "A", "C"), ("C", "A", "B")):
        assert pp.ang(p[v], p[a], p[b]) < 89.5, (setup.code, v)
    assert pp.between(p["H"], p["A"], p["B"])


@pytest.mark.parametrize("seed", SEEDS)
def test_2016_points_lie_where_the_stem_puts_them(seed):
    setup = pp.rect_diagonal_bisector(random.Random(seed))
    p = _pts(setup.figure(set(), random.Random(seed)))
    assert pp.between(p["L"], p["A"], p["D"])
    assert pp.between(p["M"], p["B"], p["D"])
    assert pp.between(p["N"], p["D"], p["C"])
    assert pp.between(p["H"], p["B"], p["D"])


@pytest.mark.parametrize("seed", SEEDS)
def test_2015_points_lie_where_the_stem_puts_them(seed):
    setup = pp.iso_mnp(random.Random(seed))
    for keys in (set(), {"alpha"}):
        p = _pts(setup.figure(keys, random.Random(seed)))
        assert pp.between(p["L"], p["N"], p["P"])
        assert pp.between(p["K"], p["M"], p["L"])
        assert pp.between(p["T"], p["M"], p["N"])


@pytest.mark.parametrize("seed", SEEDS)
def test_2018_n_satisfies_the_stem(seed):
    setup = pp.heights_45_30(random.Random(seed))
    p = _pts(setup.figure(set(), random.Random(seed)))
    assert pp.between(p["N"], p["H"], p["B"])
    assert pp.close(pp.dist(p["H"], p["N"]), pp.dist(p["M"], p["N"]) + pp.dist(p["N"], p["B"]))
