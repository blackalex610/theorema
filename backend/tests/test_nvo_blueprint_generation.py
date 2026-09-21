"""Tests for the blueprint-driven NVO generator.

The generator's job is to produce papers a Bulgarian maths teacher would accept
as real, so most of these assert against facts read off the official papers in
``NVOS/`` rather than against the implementation:

  * Part 1 is 65 points and Part 2 is 35, in every paper since 2015.
  * Options are Cyrillic А/Б/В/Г — a Latin "B" beside a Cyrillic "В" is the
    classic tell, and it silently breaks answer comparison at grading time.
  * The geometry items inside the multiple-choice block are contiguous, because
    the „не са начертани в мащаб“ notice introduces that run.

The independent-solver tests at the bottom matter most. Re-deriving a key from
the stem, with arithmetic written a second time, is what catches the class of
bug a schema check never will — during development it found two: an expression
that collapses to k(x+k) rather than x+k, and a cubic expansion whose normal
form was off by a factor.
"""
import random
import re
from collections import Counter
from fractions import Fraction

import pytest

from app.nvo_gen.assemble import AssemblyError, generate_paper
from app.nvo_gen.blueprints import BLUEPRINTS, get_blueprint, short_form
from app.nvo_gen.distractors import OPTION_LETTERS, is_clean_decimal
from app.nvo_gen.part2_bank import bank_for
from app.nvo_gen.registry import all_templates, coverage_report, templates_for
from app.nvo_gen.verify import check_paper, letter_histogram

ALL_CODES = sorted(BLUEPRINTS)


# ─── blueprints ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_part_totals_are_65_and_35(code):
    """True of every official paper from 2015 to 2026, whatever the task count."""
    bp = BLUEPRINTS[code]
    assert bp.part1_points == 65
    assert bp.part2_points == 35
    assert bp.total_points == 100


@pytest.mark.parametrize("code", ALL_CODES)
def test_positions_are_contiguous_from_one(code):
    bp = BLUEPRINTS[code]
    assert [s.position for s in bp.slots] == list(range(1, len(bp.slots) + 1))


@pytest.mark.parametrize("code", ALL_CODES)
def test_geometry_items_form_one_contiguous_run(code):
    bp = BLUEPRINTS[code]
    geom = [s.position for s in bp.mc_slots if s.topic.startswith("geom_")]
    assert geom == list(range(geom[0], geom[0] + len(geom)))


def test_the_two_blueprints_have_the_shapes_the_papers_had():
    classic, nvo2026 = BLUEPRINTS["classic"], BLUEPRINTS["nvo2026"]
    # 2024/2025: 20 multiple choice, no short-answer block, 3 extended.
    assert (len(classic.mc_slots), len(classic.short_slots), len(classic.open_slots)) == (20, 0, 3)
    assert classic.part1_minutes == 75
    # 2026: multiple choice cut to 14, short-answer block reinstated at 15–21.
    assert (len(nvo2026.mc_slots), len(nvo2026.short_slots), len(nvo2026.open_slots)) == (14, 7, 3)
    assert nvo2026.part1_minutes == 90
    assert [s.position for s in nvo2026.open_slots] == [22, 23, 24]


def test_unknown_blueprint_falls_back_rather_than_raising():
    """A stale client posting an old format must not 500 a student mid-exam."""
    assert get_blueprint("no-such-format").code in BLUEPRINTS
    assert get_blueprint(None).code in BLUEPRINTS


# ─── coverage ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_every_slot_has_at_least_one_template(code):
    """A slot with no template cannot be filled, so the whole paper fails."""
    bp = BLUEPRINTS[code]
    for slot in bp.slots:
        n = len(bank_for(slot.topic)) if slot.kind == "open" else len(templates_for(slot))
        assert n >= 1, f"slot {slot.position} ({slot.topic}/{slot.kind}) has no source"


def test_template_codes_are_unique():
    codes = [t.code for t in all_templates()]
    assert len(codes) == len(set(codes))


# ─── generated papers ────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_generated_paper_passes_its_own_verifier(code):
    for seed in range(25):
        paper = generate_paper(code, seed=seed)
        assert paper.report.ok, f"{code} seed {seed}: {paper.report.errors}"


@pytest.mark.parametrize("code", ALL_CODES)
def test_generated_paper_totals_one_hundred_points(code):
    for seed in range(10):
        assert generate_paper(code, seed=seed).total_points == 100


@pytest.mark.parametrize("code", ALL_CODES)
def test_generation_is_deterministic_for_a_seed(code):
    a = generate_paper(code, seed=1234)
    b = generate_paper(code, seed=1234)
    assert [i.stem for i in a.items] == [i.stem for i in b.items]
    assert [i.correct_answer for i in a.items] == [i.correct_answer for i in b.items]


@pytest.mark.parametrize("code", ALL_CODES)
def test_different_seeds_give_different_papers(code):
    stems = {tuple(i.stem for i in generate_paper(code, seed=s).items) for s in range(20)}
    assert len(stems) == 20, "20 seeds produced a duplicate paper"


@pytest.mark.parametrize("code", ALL_CODES)
def test_options_are_cyrillic_never_latin(code):
    """A Latin B beside a Cyrillic В is the classic generated-paper tell."""
    for seed in range(15):
        for item in generate_paper(code, seed=seed).items:
            if item.kind == "mc":
                assert item.correct_answer in OPTION_LETTERS
                assert not re.fullmatch(r"[ABCD]", str(item.correct_answer))


@pytest.mark.parametrize("code", ALL_CODES)
def test_answer_letters_stay_close_to_uniform(code):
    """2022 shipped 8 of 18 keys on Б. Rebalancing exists to prevent that."""
    for seed in range(20):
        hist = letter_histogram(generate_paper(code, seed=seed).items)
        assert max(hist.values()) - min(hist.values()) <= 1, hist


@pytest.mark.parametrize("code", ALL_CODES)
def test_no_template_is_used_twice_in_one_paper(code):
    for seed in range(20):
        codes = [i.template_code for i in generate_paper(code, seed=seed).items]
        assert len(codes) == len(set(codes)), Counter(codes).most_common(3)


@pytest.mark.parametrize("code", ALL_CODES)
def test_slots_that_expect_a_figure_get_one(code):
    for seed in range(10):
        paper = generate_paper(code, seed=seed)
        for item, slot in zip(paper.items, paper.slots):
            if slot.diagram:
                assert item.scene is not None, f"slot {slot.position} has no figure"


@pytest.mark.parametrize("code", ALL_CODES)
def test_no_cyrillic_inside_math_spans(code):
    """The router strips Cyrillic out of $…$; a stem that puts it there loses words."""
    for seed in range(15):
        for item in generate_paper(code, seed=seed).items:
            texts = [item.stem, *(item.parts or []), *(item.options or [])]
            for text in texts:
                for span in re.findall(r"\$([^$]*)\$", text):
                    assert not re.search(r"[А-Яа-я]", span), f"{span!r} in {text[:60]!r}"


@pytest.mark.parametrize("code", ALL_CODES)
def test_scale_notice_sits_before_the_geometry_block(code):
    paper = generate_paper(code, seed=3)
    assert paper.scale_notice_before is not None
    slot = paper.slots[paper.scale_notice_before - 1]
    assert slot.kind == "mc" and slot.topic.startswith("geom_")
    before = paper.slots[paper.scale_notice_before - 2]
    assert not before.topic.startswith("geom_")


@pytest.mark.parametrize("code", ALL_CODES)
def test_short_form_is_shorter_but_still_well_formed(code):
    paper = generate_paper(code, seed=5, short=True)
    assert 0 < len(paper.items) < len(BLUEPRINTS[code].slots)
    assert paper.report.ok, paper.report.errors


def test_five_hundred_papers_generate_without_a_single_failure():
    """The headline claim: papers come out clean, not mostly clean."""
    failures = []
    for code in ALL_CODES:
        for seed in range(250):
            try:
                paper = generate_paper(code, seed=seed)
            except AssemblyError as exc:
                failures.append(f"{code}/{seed}: {exc}")
                continue
            if not paper.report.ok:
                failures.append(f"{code}/{seed}: {paper.report.errors}")
    assert not failures, failures[:5]


# ─── independent re-solving ──────────────────────────────────────────────────
# These re-derive the key from the stem with arithmetic written a second time.
# Two real bugs were caught this way during development.

def _build(code: str, slot_position: int, blueprint: str, seed: int):
    """Build one item, resampling on Retry exactly as the assembler does.

    A template rejecting its own draw is normal behaviour, not a failure — the
    parameter spaces are deliberately over-wide and constrained by rejection.
    """
    from app.nvo_gen.registry import Retry, get_template

    bp = get_blueprint(blueprint)
    slot = bp.slot(slot_position)
    rng = random.Random(seed)
    template = get_template(code)
    for _ in range(60):
        try:
            return template.build(rng, slot)
        except Retry:
            continue
    pytest.fail(f"{code} produced no usable draw in 60 attempts from seed {seed}")


def _key_text(item) -> str:
    idx = OPTION_LETTERS.index(item.correct_answer)
    return (item.options or [])[idx]


def _numbers(text: str) -> list[Fraction]:
    """Pull numbers out of a rendered option, undoing the Bulgarian comma."""
    cleaned = text.replace("{,}", ".").replace("$", "")
    frac = re.match(r"^\s*(-?)\\frac\{(\d+)\}\{(\d+)\}\s*$", cleaned)
    if frac:
        sign = -1 if frac.group(1) else 1
        return [sign * Fraction(int(frac.group(2)), int(frac.group(3)))]
    return [Fraction(m) for m in re.findall(r"-?\d+(?:\.\d+)?", cleaned)]


def test_work_rate_key_is_the_harmonic_mean():
    for seed in range(40):
        item = _build("work_rate_two_people", 8, "nvo2026", seed)
        a, b = (int(n) for n in re.findall(r"за (\d+) минути", item.stem))
        expected = Fraction(a * b, a + b)
        assert expected.denominator == 1
        assert _numbers(_key_text(item)) == [expected]


def test_incentre_key_satisfies_the_ninety_plus_half_gamma_identity():
    for seed in range(40):
        item = _build("incentre_angle", 20, "nvo2026", seed)
        aob = int(re.search(r"AOB = (\d+)", item.stem).group(1))
        gamma = int(str(item.correct_answer).rstrip("°"))
        assert aob == 90 + gamma // 2
        assert gamma % 2 == 0


def test_median_to_hypotenuse_parts_are_half_and_double():
    for seed in range(40):
        item = _build("median_to_hypotenuse", 19, "nvo2026", seed)
        ab = int(re.search(r"дължина \$(\d+)\$ cm", item.stem).group(1))
        alpha = int(re.search(r"CAB = (\d+)", item.stem).group(1))
        cm, angle = item.correct_answer
        assert int(cm.split()[0]) == ab // 2
        assert int(angle.rstrip("°")) == 2 * alpha


def test_perp_bisector_of_hypotenuse_key_is_a_third_of_the_leg():
    for seed in range(30):
        item = _build("perp_bisector_of_hypotenuse", 13, "nvo2026", seed)
        ac = int(re.search(r"AC = (\d+)", item.stem).group(1))
        assert _numbers(_key_text(item)) == [Fraction(ac, 3)]


def test_parallels_zigzag_key_is_the_sum_of_the_two_supplements():
    for seed in range(30):
        item = _build("parallels_zigzag", 12, "nvo2026", seed)
        # The two given angles live on the figure, not in the stem — which is
        # the point of the item, so read them back off the scene.
        angles = [int(a["label"].rstrip("°")) for a in item.scene["angles"] if a.get("label")]
        assert len(angles) == 2
        expected = sum(180 - a for a in angles)
        assert _numbers(_key_text(item)) == [Fraction(expected)]


def test_collapsing_expression_value_is_k_times_x_plus_k():
    """The bug this caught: (x+k)² − x(x+k) is k(x+k), and equals x+k only at k=1."""
    for seed in range(40):
        item = _build("value_of_collapsing_expression", 16, "nvo2026", seed)
        k = int(re.search(r"\\left\(x \+ (\d+)\\right\)\^2", item.stem).group(1))
        x = int(re.search(r"за \$x = (\d+)\$", item.stem).group(1))
        assert int(str(item.correct_answer)) == k * (x + k)


def test_quadratic_by_factoring_roots_are_zero_and_k_over_a():
    """ax² = kx has roots 0 and k/a — the 0 is the one students lose."""
    for seed in range(30):
        item = _build("quadratic_by_factoring", 15, "nvo2026", seed)
        lead = re.search(r"\$(\d*)x\^2 = (\d+)x\$", item.stem)
        a = int(lead.group(1) or 1)
        k = int(lead.group(2))
        assert k % a == 0
        assert str(item.correct_answer) == f"0 и {k // a}"


def test_percent_capacity_key_matches_the_free_seats():
    for seed in range(40):
        item = _build("percent_remainder_capacity", 18, "nvo2026", seed)
        pct = int(re.search(r"заели (\d+)%", item.stem).group(1))
        free = int(re.search(r"а (\d+) места", item.stem).group(1))
        total = int(str(item.correct_answer).split()[0])
        assert total * (100 - pct) == free * 100


def test_congruent_triangles_third_angle_closes_the_triangle():
    for seed in range(30):
        item = _build("congruent_triangles_angle", 11, "nvo2026", seed)
        alpha = int(re.search(r"CAB = (\d+)", item.stem).group(1))
        gamma = int(re.search(r"MPN = (\d+)", item.stem).group(1))
        assert _numbers(_key_text(item)) == [Fraction(180 - alpha - gamma)]


def test_interval_options_are_the_four_bracket_variants():
    """2026 Q4, 2023 Q5, 2022 Q5 and 2021 Q5 all offer exactly this menu."""
    for seed in range(30):
        item = _build("inequality_to_interval", 4, "nvo2026", seed)
        bounds = {tuple(_numbers(o)) for o in item.options}
        assert len(bounds) == 1, "every option must carry the same bound"
        assert len(set(item.options)) == 4, "the four bracket forms must differ"


def test_every_probability_option_is_a_real_probability():
    """A value above 1 among the options is a free elimination, not a distractor."""
    for name, position in (("prob_single_digit_divisible", 6),
                           ("prob_balls_in_a_box", 6),
                           ("prob_spinner", 6)):
        for seed in range(25):
            item = _build(name, position, "nvo2026", seed)
            for option in item.options or []:
                for value in _numbers(option):
                    assert 0 <= value <= 1, f"{name}: option {option!r} is not a probability"


def test_decimal_answers_terminate_within_a_few_places():
    """No NVO key prints 0,58333… ."""
    for code in ALL_CODES:
        for seed in range(30):
            for item in generate_paper(code, seed=seed).items:
                for option in item.options or []:
                    if "{,}" not in option:
                        continue
                    decimals = re.findall(r"\{,\}(\d+)", option)
                    for d in decimals:
                        assert len(d) <= 3, f"{option!r} has {len(d)} decimal places"


def test_is_clean_decimal_rejects_a_repeating_third():
    assert is_clean_decimal(Fraction(1, 4))
    assert is_clean_decimal(Fraction(7, 10))
    assert not is_clean_decimal(Fraction(5, 3))
    assert not is_clean_decimal(Fraction(1, 7))
