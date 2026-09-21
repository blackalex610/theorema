"""Figures: the guardrails, the layout sampler, and figure-level deduplication.

``test_nvo_blueprint_generation`` asserts that a paper is *mathematically* sound.
This file asserts that its figures are *drawable* — which is a different failure
mode and used to be caught only by a human opening the contact sheet by hand.

Three things are checked here.

*The guardrails.* A scene spec can verify cleanly and still draw a label on top
of a vertex, a point off the edge of the box, or an angle arc too thin to read.
All three have shipped. They are cheap to detect from the spec, so they are
errors now rather than something a student notices first.

*The layout sampler.* Figures used to be laid out at fixed coordinates, so every
paper printed the same triangle with different numbers on it. Layouts are now
sampled per draw, which means the topology they promise — the foot of a height
strictly inside the side, an angle that is genuinely acute — has to be asserted
rather than assumed, because nobody is eyeballing each one any more.

*Figure-level dedup.* Two items on one paper must not print the same picture.
This used to happen in half of all papers, because ``median_to_hypotenuse`` and
``median_hypotenuse_from_median`` both drew the canonical right triangle and
nothing compared them.

The thresholds below are not invented. They are the tightest values the
hand-tuned figures actually produced, measured across 80 papers, rounded down:
label gap 47.6 → 22, box margin 14.0 → 10, marked angle 15.8° → 14.
"""
import math
from collections import Counter

import pytest

from app.nvo_gen.assemble import generate_paper
from app.nvo_gen.blueprints import BLUEPRINTS, Slot
from app.nvo_gen.registry import GeneratedItem
from app.nvo_gen.scene import (
    Figure,
    LayoutError,
    MIN_ANGLE_DEG,
    MIN_BOX_MARGIN,
    MIN_LABEL_GAP,
    geometry_hash,
    scalene_triangle,
)
from app.nvo_gen.verify import check_item, check_paper

ALL_CODES = sorted(BLUEPRINTS)
SEEDS = range(24)


def mc_slot(**kw) -> Slot:
    base = dict(position=10, section="part1", kind="mc", topic="geom_lines_angles",
                points=(3,), diagram=True)
    base.update(kw)
    return Slot(**base)


def mc_item(scene: dict, **kw) -> GeneratedItem:
    base = dict(
        topic="geom_lines_angles", kind="mc", points=(3,),
        stem="На чертежа е показан $\\triangle ABC$. Мярката на ъгъла е:",
        options=["$1^\\circ$", "$2^\\circ$", "$3^\\circ$", "$4^\\circ$"],
        correct_answer="А", scene=scene, template_code="probe",
    )
    base.update(kw)
    return GeneratedItem(**base)


def errors_for(scene: dict) -> str:
    return " | ".join(check_item(mc_item(scene), mc_slot()).errors)


# ─── guardrails ──────────────────────────────────────────────────────────────

def test_verifier_rejects_labels_drawn_on_top_of_each_other():
    """Two labelled points a hair apart put their glyphs in the same place.

    The label placer scores eight compass directions for clearance, so it
    usually separates them — but it cannot when there is nowhere to go, and the
    result is unreadable rather than merely ugly.
    """
    f = Figure()
    f.put("A", (40.0, 120.0))
    f.put("B", (200.0, 120.0))
    f.put("C", (120.0, 40.0))
    f.put("M", (121.0, 41.0), dot=True)      # all but on top of C
    f.path(["A", "B", "C"], close=True)

    assert "label" in errors_for(f.to_spec(aria="проба"))


def test_verifier_rejects_a_point_outside_the_drawing_box():
    """Anything past the viewBox is simply not drawn — silently."""
    f = Figure()
    f.put("A", (40.0, 120.0))
    f.put("B", (200.0, 120.0))
    f.put("C", (120.0, -30.0))               # above the top edge
    f.path(["A", "B", "C"], close=True)

    assert "box" in errors_for(f.to_spec(aria="проба"))


def test_verifier_rejects_a_marked_angle_too_thin_to_read():
    """An arc across 4° is a smudge, and the student cannot tell what is marked."""
    f = Figure()
    f.put("O", (40.0, 130.0))
    f.put("P", (230.0, 130.0))
    f.put("Q", (230.0, 117.0))               # ~4° from OP
    f.seg("O", "P")
    f.seg("O", "Q")
    f.angle("O", "P", "Q", label="4°")

    assert "angle" in errors_for(f.to_spec(aria="проба"))


def test_a_well_formed_figure_passes_all_three_guardrails():
    """The negative tests above must fail for their own reason, not in general."""
    f = scalene_triangle()
    f.path(["A", "B", "C"], close=True)
    f.angle("A", "B", "C", label="50°")

    assert check_item(mc_item(f.to_spec(aria="проба")), mc_slot()).ok


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_generated_figure_clears_the_guardrails(code):
    """The property the sampler must not break. This is the real regression net."""
    for seed in SEEDS:
        paper = generate_paper(code, seed=seed)
        for item in paper.items:
            if item.scene and item.scene["kind"] == "figure":
                report = check_item(item, _slot_of(paper, item))
                assert report.ok, f"{code}/{seed} {item.template_code}: {report.errors}"


def _slot_of(paper, item) -> Slot:
    return next(s for i, s in zip(paper.items, paper.slots) if i is item)


# ─── the geometry hash ───────────────────────────────────────────────────────

def test_geometry_hash_ignores_labels_and_aria():
    """Two figures that draw the same picture hash the same, whatever it says.

    This is what makes figure-level dedup mean "same picture" rather than
    "same JSON", which would be satisfied by changing one angle label.
    """
    def build(label: str, aria: str) -> dict:
        f = scalene_triangle()
        f.path(["A", "B", "C"], close=True)
        f.angle("A", "B", "C", label=label)
        return f.to_spec(aria=aria)

    assert geometry_hash(build("50°", "едно")) == geometry_hash(build("70°", "друго"))


def test_geometry_hash_separates_figures_drawn_differently():
    f = scalene_triangle()
    f.path(["A", "B", "C"], close=True)
    g = scalene_triangle()
    g.path(["A", "B", "C"], close=True)
    g.put("M", (120.0, 138.0), dot=True)
    g.seg("C", "M")

    assert geometry_hash(f.to_spec(aria="x")) != geometry_hash(g.to_spec(aria="x"))


# ─── figure-level deduplication ──────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_no_two_items_on_a_paper_print_the_same_picture(code):
    """Used to fail on half of all seeds (`median_to_hypotenuse` vs
    `median_hypotenuse_from_median`, identical right triangles)."""
    for seed in SEEDS:
        paper = generate_paper(code, seed=seed)
        hashes = [geometry_hash(i.scene) for i in paper.items
                  if i.scene and i.scene["kind"] == "figure"]
        dupes = [h for h, n in Counter(hashes).items() if n > 1]
        assert not dupes, f"{code}/{seed}: {len(dupes)} repeated figure(s)"


def test_check_paper_reports_a_repeated_figure():
    """The backstop, independent of whether the assembler avoided it."""
    f = scalene_triangle()
    f.path(["A", "B", "C"], close=True)
    scene = f.to_spec(aria="проба")

    slots = (mc_slot(position=1), mc_slot(position=2))
    items = [mc_item(scene, stem="Първа задача за $\\triangle ABC$.", template_code="a"),
             mc_item(scene, stem="Втора задача за $\\triangle ABC$.", template_code="b")]

    assert any("figure" in e for e in check_paper(items, slots).errors)


# ─── the layout sampler ──────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ALL_CODES)
def test_figure_layouts_actually_vary_between_papers(code):
    """The whole point. Every plane-geometry template used to emit exactly one
    geometry across 60 papers — the same triangle with different numbers."""
    shapes: dict[str, set[str]] = {}
    draws: Counter = Counter()
    for seed in SEEDS:
        for item in generate_paper(code, seed=seed).items:
            if item.scene and item.scene["kind"] == "figure":
                draws[item.template_code] += 1
                shapes.setdefault(item.template_code, set()).add(geometry_hash(item.scene))

    # Judge only templates drawn often enough that one shape would be damning.
    frozen = {c: len(shapes[c]) for c in shapes if draws[c] >= 4 and len(shapes[c]) < 3}
    assert not frozen, f"{code}: layouts still frozen: {frozen}"


def test_sampled_scalene_triangle_keeps_its_invariants():
    """Sampling is only safe because the layout declares what must stay true.

    A scalene layout with an obtuse or near-right angle at C puts the foot of
    the perpendicular from B on top of C, which is exactly the bug that made
    ``triangle_for_cevians`` necessary in the first place.
    """
    import random

    for seed in range(200):
        f = scalene_triangle(rng=random.Random(seed))
        A, B, C = f.points["A"], f.points["B"], f.points["C"]
        for vertex, u, v in (("A", B, C), ("C", A, B)):
            p = f.points[vertex]
            d1 = (u[0] - p[0], u[1] - p[1])
            d2 = (v[0] - p[0], v[1] - p[1])
            cos = (d1[0] * d2[0] + d1[1] * d2[1]) / (math.hypot(*d1) * math.hypot(*d2))
            assert math.degrees(math.acos(max(-1.0, min(1.0, cos)))) < 85.0, (
                f"seed {seed}: angle at {vertex} is not comfortably acute")


def test_thresholds_are_the_measured_ones():
    """Guard against someone loosening a guardrail to make a bad figure pass."""
    assert (MIN_LABEL_GAP, MIN_BOX_MARGIN, MIN_ANGLE_DEG) == (22.0, 10.0, 14.0)


# ─── a layout that cannot close is a bad draw, not a broken paper ────────────

def test_a_layout_that_cannot_satisfy_its_contract_costs_only_a_resample():
    """`LayoutError` must reach the assembler as a `Retry`.

    Sampled layouts reject their own bad draws, so this fires in normal
    operation. If it escaped as an ordinary exception, `_try_template` would
    turn it into an `AssemblyError`, the paper would fail, and the router would
    quietly demote the student to the OpenAI fallback path — a worse paper,
    generated slower, for a condition that means nothing more than "try again".
    """
    from app.nvo_gen.assemble import _try_template
    from app.nvo_gen.registry import ItemTemplate, Retry

    assert issubclass(LayoutError, Retry)

    def always_fails(rng, slot):
        raise LayoutError("probe: never closes")

    tmpl = ItemTemplate(code="probe", topics=frozenset({"geom_lines_angles"}),
                        kinds=frozenset({"mc"}), build=always_fails)
    import random
    assert _try_template(tmpl, mc_slot(), random.Random(0), set()) is None
