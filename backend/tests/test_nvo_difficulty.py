"""Tests for the four difficulty levels.

The contract these defend is a single sentence: **difficulty changes the items,
never the format.** A paper at "easy" and a paper at "extra_hard" have the same
positions, the same topics, the same points per position and the same А/Б/В/Г
menu as the real exam — because that skeleton is what makes a generated paper
recognisable as НВО at all. What moves is which template fills each slot, how
big the numbers are, and how long the clock runs.

So the tests come in three groups:

  * *Structure is invariant.* Asserted against every blueprint at every level,
    including the 65/35 split, which is true of every official paper since 2015.
  * *`actual` is the real paper.* The identity level must leave every knob
    alone — same seed, same blueprint, byte-identical to generating with no
    difficulty at all. If this ever fails, "като на НВО" is a lie.
  * *The levels actually differ.* A difficulty system that type-checks but
    produces the same paper four times is the failure mode worth guarding,
    and it is exactly what the first cut of this did.
"""
import random
from collections import Counter

import pytest

from app.nvo_gen.assemble import generate_paper
from app.nvo_gen.blueprints import BLUEPRINTS, with_profile
from app.nvo_gen.difficulty import (
    ACTUAL,
    BANDS,
    DEFAULT_DIFFICULTY,
    PROFILES,
    catalogue,
    get_profile,
    normalize,
)
from app.nvo_gen.registry import all_templates, get_template, templates_for

ALL_CODES = sorted(BLUEPRINTS)
LEVELS = ["easy", "medium", "actual", "extra_hard"]


# ─── the profiles themselves ─────────────────────────────────────────────────

def test_there_are_exactly_four_levels():
    assert sorted(PROFILES) == sorted(LEVELS)


def test_actual_is_the_default():
    assert DEFAULT_DIFFICULTY == "actual"
    assert get_profile(None) is ACTUAL
    assert get_profile("") is ACTUAL


@pytest.mark.parametrize("legacy,expected", [
    ("standard", "actual"),      # what the client sent before the rename
    ("hard", "extra_hard"),      # ditto
    ("STANDARD", "actual"),      # case is not meaningful
    ("extra hard", "extra_hard"),
    ("nonsense", "actual"),      # never raise mid-exam over an enum drift
    (None, "actual"),
])
def test_legacy_and_junk_difficulties_resolve_rather_than_raise(legacy, expected):
    """Stored attempts and un-reloaded clients still carry the old names."""
    assert normalize(legacy) == expected


def test_actual_leaves_every_knob_neutral():
    """`actual` must be the identity: it is the one level that is the real exam."""
    assert ACTUAL.time_scale == 1.0
    assert ACTUAL.xp_multiplier == 1.0
    assert ACTUAL.is_actual
    for band in BANDS:
        assert ACTUAL.weight_for(band) == 1.0, f"{band} is re-weighted at 'actual'"


def test_no_band_is_ever_weighted_to_zero():
    """A slot whose every template is one band must still be fillable."""
    for profile in PROFILES.values():
        for band in BANDS:
            assert profile.weight_for(band) > 0


def test_difficulty_ordering_is_monotonic_in_xp_and_time():
    ordered = sorted(PROFILES.values(), key=lambda p: p.rank)
    assert [p.code for p in ordered] == LEVELS
    assert [p.xp_multiplier for p in ordered] == sorted(p.xp_multiplier for p in ordered)
    # Harder means less time, so time_scale runs the other way.
    assert [p.time_scale for p in ordered] == sorted(
        (p.time_scale for p in ordered), reverse=True)


def test_catalogue_is_easiest_first_and_marks_the_real_one():
    rows = catalogue()
    assert [r["code"] for r in rows] == LEVELS
    assert [r for r in rows if r["isActual"]] == [r for r in rows if r["code"] == "actual"]
    for row in rows:
        assert row["label"] and row["blurb"] and row["emoji"]


# ─── structure does not move ─────────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
@pytest.mark.parametrize("level", LEVELS)
def test_structure_is_identical_at_every_difficulty(code, level):
    """Positions, topics, kinds and points must match the blueprint exactly."""
    blueprint = BLUEPRINTS[code]
    paper = generate_paper(code, seed=17, difficulty=level)

    assert [s.position for s in paper.slots] == [s.position for s in blueprint.slots]
    assert [s.topic for s in paper.slots] == [s.topic for s in blueprint.slots]
    assert [s.kind for s in paper.slots] == [s.kind for s in blueprint.slots]
    assert [s.points for s in paper.slots] == [s.points for s in blueprint.slots]


@pytest.mark.parametrize("code", ALL_CODES)
@pytest.mark.parametrize("level", LEVELS)
def test_points_stay_sixty_five_and_thirty_five(code, level):
    """A score means the same thing at every level — the XP multiplier is the reward."""
    paper = generate_paper(code, seed=23, difficulty=level)
    part1 = sum(i.total_points for i, s in zip(paper.items, paper.slots)
                if s.section == "part1")
    part2 = sum(i.total_points for i, s in zip(paper.items, paper.slots)
                if s.section == "part2")
    assert (part1, part2) == (65, 35)


@pytest.mark.parametrize("level", LEVELS)
def test_every_paper_passes_its_own_verifier_at_every_level(level):
    for code in ALL_CODES:
        for seed in range(12):
            paper = generate_paper(code, seed=seed, difficulty=level)
            assert paper.report.ok, (level, code, seed, paper.report.errors)


@pytest.mark.parametrize("level", LEVELS)
def test_scale_notice_still_sits_before_the_geometry_block(level):
    for code in ALL_CODES:
        paper = generate_paper(code, seed=5, difficulty=level)
        assert paper.scale_notice_before is not None
        first_geom = next(i for i, s in enumerate(paper.slots, start=1)
                          if s.kind == "mc" and s.topic.startswith("geom_"))
        assert paper.scale_notice_before == first_geom


# ─── `actual` is the real paper ──────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_actual_matches_generating_with_no_difficulty_at_all(code):
    """The identity level must not perturb the generator in any way."""
    plain = generate_paper(code, seed=99)
    explicit = generate_paper(code, seed=99, difficulty="actual")
    legacy = generate_paper(code, seed=99, difficulty="standard")
    assert [i.stem for i in plain.items] == [i.stem for i in explicit.items]
    assert [i.stem for i in plain.items] == [i.stem for i in legacy.items]


@pytest.mark.parametrize("code", ALL_CODES)
def test_actual_keeps_the_official_clock(code):
    blueprint = BLUEPRINTS[code]
    paper = generate_paper(code, seed=3, difficulty="actual")
    assert paper.part1_minutes == blueprint.part1_minutes
    assert paper.part2_minutes == blueprint.part2_minutes


@pytest.mark.parametrize("code", ALL_CODES)
def test_gentler_levels_get_more_time_and_the_hardest_gets_less(code):
    minutes = {lvl: generate_paper(code, seed=3, difficulty=lvl).part1_minutes
               for lvl in LEVELS}
    assert minutes["easy"] > minutes["medium"] > minutes["actual"] > minutes["extra_hard"]


# ─── the levels actually differ ──────────────────────────────────────────────

def test_the_same_seed_gives_different_papers_at_different_levels():
    """The failure mode worth guarding: a system that wires up but does nothing."""
    stems = {lvl: [i.stem for i in generate_paper("nvo2026", seed=3, difficulty=lvl).items]
             for lvl in LEVELS}
    assert stems["easy"] != stems["actual"]
    assert stems["extra_hard"] != stems["actual"]
    assert stems["easy"] != stems["extra_hard"]


def _band_mix(level, papers=40):
    counts = Counter()
    for code in ALL_CODES:
        for seed in range(papers):
            for item in generate_paper(code, seed=seed, difficulty=level).items:
                if item.kind != "open" and item.template_code:
                    counts[get_template(item.template_code).band] += 1
    total = sum(counts.values())
    return {band: counts[band] / total for band in BANDS}


def test_easy_leans_on_easy_templates_and_extra_hard_on_hard_ones():
    easy = _band_mix("easy")
    hard = _band_mix("extra_hard")
    actual = _band_mix("actual")

    assert easy["easy"] > actual["easy"] > hard["easy"]
    assert hard["hard"] > actual["hard"] > easy["hard"]
    # Not merely a nudge — the character of the paper has to change.
    assert easy["easy"] > 0.4, easy
    assert hard["hard"] > 0.4, hard


def test_every_level_still_reaches_every_band_somewhere():
    """Weights make a band rare, never impossible."""
    for level in LEVELS:
        mix = _band_mix(level, papers=40)
        for band in BANDS:
            assert mix[band] > 0, f"{level} never produced a {band} item"


# ─── the pool difficulty rests on ────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_every_slot_has_several_templates_to_choose_between(code):
    """With one candidate per slot the difficulty profile has nothing to pick.

    Three is the floor at which re-weighting can express a preference; the open
    Part 2 slots are excluded because they draw from the curated bank instead.
    """
    thin = {f"{s.position}:{s.topic}": len(templates_for(s))
            for s in BLUEPRINTS[code].slots
            if s.kind != "open" and len(templates_for(s)) < 3}
    assert not thin, f"slots with fewer than 3 templates: {thin}"


def test_every_template_declares_a_known_band():
    for tmpl in all_templates():
        assert tmpl.band in BANDS, f"{tmpl.code} has band {tmpl.band!r}"


def test_the_pool_is_spread_across_bands():
    """A pool that is all one band cannot express difficulty however it is weighted."""
    mix = Counter(t.band for t in all_templates())
    for band in BANDS:
        assert mix[band] >= 8, f"only {mix[band]} templates in band {band}: {mix}"


def test_every_registered_template_can_actually_build_something():
    """A template whose every draw is rejected is dead weight that inflates coverage.

    Three shipped in exactly that state — their distractor pools sat entirely
    outside the plausibility band, so `numeric_options` raised on every draw and
    the slot silently fell through to another template.
    """
    from app.nvo_gen.registry import Retry

    dead = []
    for tmpl in all_templates():
        slots = [s for bp in BLUEPRINTS.values() for s in bp.slots if tmpl.fits(s)]
        assert slots, f"{tmpl.code} fits no slot in any blueprint"
        rng = random.Random(4)
        built = False
        for slot in with_profile(tuple(slots), ACTUAL):
            for _ in range(60):
                try:
                    tmpl.build(rng, slot)
                except Retry:
                    continue
                built = True
                break
            if built:
                break
        if not built:
            dead.append(tmpl.code)
    assert not dead, f"templates that never produce an item: {dead}"
