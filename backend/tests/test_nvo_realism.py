"""Does a generated paper read like the real one? Guards from the corpus study.

Each test here pins a way the generator used to diverge from the thirteen
official papers in NVOS/ — not a crash, but a paper a teacher would spot as
not-quite-НВО:

  * prices in leva, though the June 2026 paper prices in „евро”;
  * an option printed as a rounded repeating decimal („0,229”);
  * a registered template that could never pass the verifier;
  * a template whose answer never changed (always 120°).
"""
from __future__ import annotations

import random
import re

import pytest

from app.nvo_gen import registry
from app.nvo_gen.assemble import generate_paper
from app.nvo_gen.blueprints import BLUEPRINTS
from app.nvo_gen.registry import GeneratedItem, Retry
from app.nvo_gen.verify import check_item

PAPERS = [(code, seed) for code in ("nvo2026", "classic") for seed in range(100)]


def _all_text(item: GeneratedItem) -> str:
    bits = [item.stem, *(item.options or []), *(item.parts or [])]
    ans = item.correct_answer
    bits += ans if isinstance(ans, list) else [ans]
    return " ".join(bits)


def _slot(topic, kind="mc"):
    return next(s for bp in BLUEPRINTS.values() for s in bp.slots
                if s.topic == topic and s.kind == kind)


def test_no_paper_prices_anything_in_leva():
    leva = re.compile(r"(?<![А-Яа-я])(лв\.?|лева|стотинк\w*)(?![А-Яа-я])")
    for code, seed in PAPERS:
        for n, item, _slot_ in generate_paper(code, seed=seed).numbered():
            assert not leva.search(_all_text(item)), (code, seed, n, item.template_code)


def test_the_verifier_refuses_leva_and_three_decimal_options():
    slot = _slot("arithmetic_expression")
    base = dict(topic=slot.topic, kind="mc", points=slot.points,
                correct_answer="А", stem="Стойността на израза $1 - 2$ е:")
    ok = GeneratedItem(**base, options=["$-1$", "$1$", "$0$", "$3$"])
    assert check_item(ok, slot).ok

    rounded = GeneratedItem(**base, options=["$-1$", "$1$", "$0$", "$0{,}229$"])
    assert any("decimal" in e for e in check_item(rounded, slot).errors)

    leva = GeneratedItem(**{**base, "stem": "Една книга струва $12$ лв. Колко струват две?"},
                         options=["$24$", "$12$", "$6$", "$36$"])
    assert any("leva" in e for e in check_item(leva, slot).errors)


def test_no_option_on_any_paper_has_three_decimals():
    long_decimal = re.compile(r"\d(?:\{,\}|,)\d{3,}")
    for code, seed in PAPERS:
        for n, item, _slot_ in generate_paper(code, seed=seed).numbered():
            for opt in item.options or []:
                assert not long_decimal.search(opt), (code, seed, n, item.template_code, opt)


@pytest.mark.parametrize("tpl", registry.all_templates(), ids=lambda t: t.code)
def test_every_template_passes_the_verifier_in_every_slot_it_claims(tpl):
    """`adjacent_angle_ratio` was registered, counted in coverage, and rejected
    on all 400 draws because its slot requires a figure it never drew."""
    for bp in BLUEPRINTS.values():
        for slot in bp.slots:
            if not tpl.fits(slot):
                continue
            ok = 0
            for seed in range(120):
                try:
                    item = tpl.build(random.Random(seed), slot)
                except Retry:
                    continue
                ok += check_item(item, slot).ok
            assert ok >= 10, f"{tpl.code} passes only {ok}/120 draws at {bp.code} #{slot.position}"


_PART1_SLOTS = [(bp.code, s) for bp in BLUEPRINTS.values() for s in bp.slots if s.kind != "open"]


@pytest.mark.parametrize("code,slot", _PART1_SLOTS,
                         ids=lambda v: v if isinstance(v, str) else f"{v.position}-{v.topic}")
def test_every_position_has_room_for_many_papers(code, slot):
    """"Nearly inexhaustible" is a per-position claim, because a student meets
    each position once per paper. The study found positions reaching 21 items
    (shortcut multiplication) and 24 (work rate) — a student recognises those
    within a handful of papers. Every position now reaches 100+; the floor is
    set below that so a sampling seed cannot flake it, and far above 21."""
    distinct = set()
    for tpl in registry.templates_for(slot):
        for seed in range(200):
            try:
                item = tpl.build(random.Random(seed), slot)
            except Retry:
                continue
            if check_item(item, slot).ok:
                distinct.add(f"{tpl.code}:{item.signature}")
    assert len(distinct) >= 80, f"{code} #{slot.position} {slot.topic}: {len(distinct)} items"


def test_angle_equals_neighbours_is_no_longer_always_120():
    tpl = registry.get_template("angle_equals_neighbours")
    slot = _slot("geom_lines_angles")
    keys = set()
    for seed in range(200):
        try:
            item = tpl.build(random.Random(seed), slot)
        except Retry:
            continue
        keys.add(item.options[ord(item.correct_answer) - ord("А")])
    assert len(keys) >= 6, keys
