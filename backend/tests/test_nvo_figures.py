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


# ─── the layouts added by the figure-coverage audit ──────────────────────────
# docs/nvo-figures/coverage.md found nine archetypes that recur across two or
# more of the thirteen official papers and that nothing could draw. Seven were
# built, on three new layouts. Each layout's contract is asserted here rather
# than described in its docstring, which is the mistake the original
# scalene_triangle made.

import random as _random

from app.nvo_gen.registry import Retry, all_templates, get_template
from app.nvo_gen.scene import (
    angle_deg,
    circumcentre,
    foot_of_perpendicular,
    midpoint,
    norm,
    parallelogram,
    right_trapezoid,
    sub,
    triangle_for_circumcentre,
    triangle_for_three_cevians,
    triangle_with_extended_side,
)

NEW_LAYOUTS = (
    triangle_for_three_cevians,
    triangle_with_extended_side,
    triangle_for_circumcentre,
    right_trapezoid,
)

NEW_TEMPLATES = (
    # the archetypes recurring in two or more papers
    "tri_height_bisector_median",
    "tri_exterior_angle_at_base",
    "tri_cevian_exterior_angle",
    "rect_diagonals_angle",
    "tri_perpendicular_from_side_point",
    "tri_circumcentre_central_angle",
    "line_through_vertex_angles",
    "chart_journey_average_speed",
    "symbolic_area_notched_rectangle",
    # one-offs built to widen the thinnest slots
    "chart_journey_rest_length",
    "parallelogram_height_area",
    "square_diagonal_angle",
    "trapezoid_cointerior_angle",
    "triangle_midsegment_perimeter",
    "isosceles_height_apex_angle",
    "segment_parts_algebraic",
    "coordinate_shaded_triangle_area",
)


@pytest.mark.parametrize("build", NEW_LAYOUTS, ids=lambda f: f.__name__)
def test_a_new_layout_closes_on_every_draw(build):
    """Sampling must not be a coin flip.

    A layout whose contract is satisfiable only occasionally still "works" —
    the decorator resamples — but it burns 80 tries per figure and eventually
    raises LayoutError under load. Every draw closing is the real bar.
    """
    build()  # the canonical sample is checked against the same contract
    for seed in range(300):
        build(rng=_random.Random(seed))


def test_three_cevians_layout_keeps_the_feet_apart():
    """The height's foot and the median's must be visibly different points.

    A near-isosceles triangle puts them on top of each other, and a figure
    captioned "CP is a height and CM is a median" that draws one segment
    contradicts its own stem.
    """
    for seed in range(300):
        f = triangle_for_three_cevians(rng=_random.Random(seed))
        A, B, C = f.points["A"], f.points["B"], f.points["C"]
        gap = norm(sub(foot_of_perpendicular(C, A, B), midpoint(A, B)))
        assert gap >= 22.0, f"seed {seed}: feet only {gap:.1f} apart"


def test_apex_left_really_puts_the_height_foot_on_the_a_side():
    """`tri_height_bisector_median` states α > β, and the figure must agree.

    AB is horizontal, so the foot of the height from C sits directly under C:
    an apex left of the midpoint is exactly ∠A > ∠B. The template relies on
    this instead of drawing freely and rejecting half its samples.
    """
    for seed in range(200):
        f = triangle_for_three_cevians(lopsided=True, apex_left=True,
                                       rng=_random.Random(seed))
        A, B, C = f.points["A"], f.points["B"], f.points["C"]
        foot = foot_of_perpendicular(C, A, B)
        assert foot[0] < midpoint(A, B)[0], f"seed {seed}: foot on the wrong side"
        assert angle_deg(A, B, C) > angle_deg(B, A, C), f"seed {seed}: α must exceed β"


def test_extended_side_anchor_stays_reachable():
    """E is hidden, so `points_inside` exempts it — but an arc is drawn there.

    This is the case that motivated `inside_box`: extending a slanted side
    instead of the base ran E off the top of the box within a few draws, and
    nothing in the generic contract would have caught it.
    """
    for seed in range(300):
        f = triangle_with_extended_side(rng=_random.Random(seed))
        x, y = f.points["E"]
        assert 16.0 <= x <= f.width - 16.0, f"seed {seed}: E off the box at x={x:.0f}"
        assert 16.0 <= y <= f.height - 16.0, f"seed {seed}: E off the box at y={y:.0f}"
        assert norm(sub(f.points["E"], f.points["B"])) >= 26.0, (
            f"seed {seed}: extension too short for a readable arc")


def test_circumcentre_layout_is_acute_and_holds_its_centre_inside():
    """Only an acute triangle puts O inside, and the figure has to show it."""
    for seed in range(300):
        f = triangle_for_circumcentre(rng=_random.Random(seed))
        A, B, C = f.points["A"], f.points["B"], f.points["C"]
        for vertex, u, v in (("A", B, C), ("B", A, C), ("C", A, B)):
            assert angle_deg(f.points[vertex], u, v) < 90.0, (
                f"seed {seed}: triangle is not acute at {vertex}")
        o = circumcentre(A, B, C)
        assert o is not None
        for p, q in ((A, B), (B, C), (C, A)):
            assert norm(sub(o, foot_of_perpendicular(o, p, q))) >= 16.0, (
                f"seed {seed}: circumcentre crowds a side")


@pytest.mark.parametrize("code", NEW_TEMPLATES)
def test_a_new_template_builds_figures_that_clear_the_guardrails(code):
    """Every draw that is not a declared Retry must pass the item verifier.

    `Retry` is a bad parameter draw and costs a resample. Anything else — a
    label collision, an arc under the legibility floor, a point off the box —
    is a bug in the template, and the assembler cannot recover from it by
    trying again with the same shape.
    """
    tpl = get_template(code)
    slots = [s for bp in BLUEPRINTS.values() for s in bp.slots
             if s.topic in tpl.topics and s.kind in tpl.kinds]
    assert slots, f"{code} declares topics/kinds that no blueprint slot offers"
    slot = slots[0]

    built = 0
    for seed in range(250):
        try:
            item = tpl.build(_random.Random(seed), slot)
        except Retry:
            continue
        report = check_item(item, slot)
        assert not report.errors, f"{code} seed {seed}: {report.errors}"
        built += 1
    assert built >= 25, f"{code} produced only {built} items in 250 draws"


def test_the_audit_templates_are_all_registered():
    """A template that silently fails to register is invisible, not absent.

    `coverage_report` counts what is registered, so a typo'd topic would leave
    the gap the audit found still open while every test and report claimed it
    was closed.
    """
    registered = {t.code for t in all_templates()}
    missing = [c for c in NEW_TEMPLATES if c not in registered]
    assert not missing, f"not registered: {missing}"


# ─── a figure must assert what its stem claims ───────────────────────────────

def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _between(p, a, b, tol=1.0):
    """p lies on segment ab (within tolerance)."""
    return abs(_dist(a, p) + _dist(p, b) - _dist(a, b)) < tol


def _perpendicular(p, q, a, b, tol=0.02):
    u = (q[0] - p[0], q[1] - p[1])
    v = (b[0] - a[0], b[1] - a[1])
    return abs(u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v)) < tol


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _parallel(a, b, c, d, tol=0.02):
    u = (b[0] - a[0], b[1] - a[1])
    v = (d[0] - c[0], d[1] - c[1])
    cross = u[0] * v[1] - u[1] * v[0]
    return abs(cross) / (math.hypot(*u) * math.hypot(*v)) < tol


def _axis_parallel(a, b, tol=0.6):
    """The edge runs along x or along y — no 7° tilt from posing."""
    return abs(a[0] - b[0]) < tol or abs(a[1] - b[1]) < tol


#: What each stem promises, as a predicate over the drawn points. Every one of
#: these survives the similarity transform `to_spec` applies, so they are
#: checked on the posed output rather than the raw layout.
STEM_CLAIMS = {
    "tri_height_bisector_median": lambda p: (
        _between(p["P"], p["A"], p["B"])
        and _between(p["L"], p["P"], p["M"])
        and _perpendicular(p["C"], p["P"], p["A"], p["B"])
        and _dist(p["M"], _mid(p["A"], p["B"])) < 0.6
    ),
    "tri_exterior_angle_at_base": lambda p: _between(p["B"], p["A"], p["E"]),
    "tri_cevian_exterior_angle": lambda p: _between(p["D"], p["A"], p["B"]),
    "rect_diagonals_angle": lambda p: (
        max(_dist(p["O"], p[v]) for v in "ABCD")
        - min(_dist(p["O"], p[v]) for v in "ABCD") < 0.8
    ),
    "tri_perpendicular_from_side_point": lambda p: (
        _between(p["N"], p["B"], p["C"])
        and _between(p["M"], p["A"], p["B"])
        and _perpendicular(p["N"], p["M"], p["A"], p["B"])
    ),
    "tri_circumcentre_central_angle": lambda p: (
        max(_dist(p["O"], p[v]) for v in "ABC")
        - min(_dist(p["O"], p[v]) for v in "ABC") < 0.8
        and _dist(p["P"], _mid(p["A"], p["B"])) < 0.6
        and _dist(p["Q"], _mid(p["A"], p["C"])) < 0.6
    ),
    "line_through_vertex_angles": lambda p: _between(p["C"], p["K"], p["M"]),

    # --- the one-offs --------------------------------------------------------
    "parallelogram_height_area": lambda p: (
        _between(p["H"], p["A"], p["B"])
        and _perpendicular(p["D"], p["H"], p["A"], p["B"])
    ),
    # A square's diagonal bisects its corner and a rectangle's does not, so an
    # item that says „квадрат" and is drawn on an oblong contradicts itself.
    "square_diagonal_angle": lambda p: (
        max(_dist(p[u], p[v]) for u, v in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")))
        - min(_dist(p[u], p[v]) for u, v in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")))
        < 0.8
        and _between(p["M"], p["D"], p["C"])
    ),
    "trapezoid_cointerior_angle": lambda p: (
        _parallel(p["A"], p["B"], p["D"], p["C"])
        and _perpendicular(p["A"], p["D"], p["A"], p["B"])
    ),
    "triangle_midsegment_perimeter": lambda p: (
        _dist(p["M"], _mid(p["A"], p["C"])) < 0.6
        and _dist(p["N"], _mid(p["B"], p["C"])) < 0.6
    ),
    "isosceles_height_apex_angle": lambda p: (
        abs(_dist(p["C"], p["A"]) - _dist(p["C"], p["B"])) < 1.0
        and _dist(p["H"], _mid(p["A"], p["B"])) < 0.6
        and _perpendicular(p["C"], p["H"], p["A"], p["B"])
    ),
    "segment_parts_algebraic": lambda p: (
        _between(p["C"], p["A"], p["B"])
        and _between(p["D"], p["C"], p["B"])
    ),
    # The L-shape is cut from a rectangle, so every edge must stay axis-parallel
    # — which is exactly what `upright` posing is for.
    "symbolic_area_notched_rectangle": lambda p: all(
        _axis_parallel(p[u], p[v]) for u, v in
        (("A", "N1"), ("N1", "N2"), ("N2", "N3"), ("N3", "C"), ("C", "D"), ("D", "A"))
    ),
}


@pytest.mark.parametrize("code", sorted(STEM_CLAIMS))
def test_a_new_figure_asserts_what_its_stem_claims(code):
    """The figure need not be to scale, but it must be topologically honest.

    „Чертежите са само за илюстрация…” licenses a figure whose angles do not
    match its stem's numbers. It does not license one where M is not actually
    the midpoint, or where a segment called a perpendicular is not one — a
    student reading the picture would be reading a lie. This is the guarantee
    the scale notice does *not* cover, so it is asserted directly.
    """
    claim = STEM_CLAIMS[code]
    tpl = get_template(code)
    slot = next(s for bp in BLUEPRINTS.values() for s in bp.slots
                if s.topic in tpl.topics and s.kind in tpl.kinds)

    checked = 0
    for seed in range(250):
        try:
            item = tpl.build(_random.Random(seed), slot)
        except Retry:
            continue
        points = {k: tuple(v) for k, v in item.scene["points"].items()}
        assert claim(points), f"{code} seed {seed}: figure contradicts its stem"
        checked += 1
    assert checked >= 25, f"{code} produced only {checked} figures to check"


def test_a_square_layout_draws_a_square_and_not_an_oblong():
    """`rect=True` is a rectangle; only `square=True` is a square.

    The distinction is load-bearing rather than cosmetic: a square's diagonal
    bisects its corner and a rectangle's does not, so `square_diagonal_angle`
    drawn on `rect=True` states 45° in its solution over a figure where the
    angle is not 45°.
    """
    for seed in range(200):
        f = parallelogram(square=True, rng=_random.Random(seed))
        sides = [_dist(f.points[u], f.points[v])
                 for u, v in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"))]
        assert max(sides) - min(sides) < 0.8, f"seed {seed}: sides {sides}"
        assert angle_deg(f.points["A"], f.points["B"], f.points["D"]) == pytest.approx(90.0, abs=0.5)


def test_upright_posing_keeps_horizontals_horizontal():
    """`upright` must drop the rotation while keeping mirror and rescale.

    Without it a rectilinear figure comes out tilted by up to 7°, which reads
    as a sloppy drawing rather than a variant — the same argument that caps the
    rotation at 7° in the first place, taken to its conclusion.
    """
    seen_widths = set()
    for seed in range(120):
        f = parallelogram(rect=True, rng=_random.Random(seed))
        f.pose(_random.Random(seed), upright=True)
        A, B, C = f.points["A"], f.points["B"], f.points["C"]
        assert _axis_parallel(A, B), f"seed {seed}: AB is no longer horizontal"
        assert _axis_parallel(B, C), f"seed {seed}: BC is no longer vertical"
        seen_widths.add(round(_dist(A, B)))
    # Rescaling must still vary the figure, or upright would make every draw
    # of a rectilinear template print the identical picture.
    assert len(seen_widths) > 5, "upright posing collapsed all draws to one size"


# ─── the curated Part 2 geometry proofs ──────────────────────────────────────
# Part 2 is the generator's ceiling: Part 1 reaches 10^45 combinations and Part
# 2 reaches tens of thousands, so these items are what a student meets again.
# They are also the ones where being wrong is expensive -- a flawed proof wastes
# twenty minutes and teaches a false method -- so the figure is checked against
# the claim the marking scheme makes, exactly as for Part 1.

from app.nvo_gen import part2_bank as _p2


def _p2_slot():
    return next(s for bp in BLUEPRINTS.values() for s in bp.slots
                if s.topic == "open_geometry_proof")


@pytest.mark.parametrize("build", _p2.bank_for("open_geometry_proof"),
                         ids=lambda b: b.__name__)
def test_a_curated_proof_verifies_and_its_points_add_up(build):
    """Sub-part points must sum to the slot total, and the item must verify.

    `verify` enforces the sum, which is the check that matters: a twelve-point
    item whose parts add to eleven silently mis-scores every student who sits
    it, and nothing downstream would notice.
    """
    slot = _p2_slot()
    for seed in range(60):
        item = build(_random.Random(seed))
        assert sum(item.points) == slot.total_points, (
            f"{item.code}: parts sum to {sum(item.points)}, slot wants "
            f"{slot.total_points}")
        assert len(item.parts) == len(item.answers), f"{item.code}: parts/answers differ"
        report = check_item(item.to_generated(slot), slot)
        assert not report.errors, f"{item.code}: {report.errors}"


# The per-proof figure checks that lived here (two isosceles, right triangle)
# are now claim checks in test_nvo_part2_figures.py, which measures every
# claim of every proof pool on its own figure.


def test_every_curated_proof_states_a_real_answer():
    """An answer of "Доказателство" gives a grader nothing to check against.

    Part 2 is marked by a person or by the vision grader, both of which compare
    against `correct_answer`. A placeholder there is not a small blemish: it is
    the difference between a key and a reminder that a key was meant to go
    here. The last two exemptions (geo_par_height, geo_iso_rhombus) were
    closed with real keys, so there is no allowlist any more; the full check
    across all three Part 2 topics lives in test_nvo_part2_keys.py.
    """
    vague = {"доказателство", "ъглите и отношението", "лицата чрез m и n"}

    offenders = []
    for topic in ("open_geometry_proof",):
        for build in _p2.bank_for(topic):
            item = build(_random.Random(0))
            for answer in item.answers:
                if answer.strip().lower() in vague:
                    offenders.append((item.code, answer))
    assert not offenders, f"placeholder answers: {offenders}"
