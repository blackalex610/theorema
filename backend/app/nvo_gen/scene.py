"""Declarative figure specs, and the builders that produce them.

The old approach was one hand-written React component per exam question —
``RhombusCOMDiagram``, ``PerpBisecBCDiagram``, twelve of them, each with its own
inlined trigonometry. Adding a thirteenth shape cost a developer a day, so the
content team was permanently blocked on engineering.

Here a figure is *data*: named points already laid out in viewBox coordinates,
plus the marks to draw on them. One renderer on the client
(``SceneRenderer.tsx``) draws any scene, so a new figure is a new builder
function — or just a different call to an existing one — and never a new
component.

Why we can lay figures out canonically instead of solving for them: every
official paper since 2018 prints „Те не са начертани в мащаб и не са
предназначени за директно измерване на дължини и на ъгли.” The figure does not
have to agree metrically with the numbers in the stem. It has to be
*topologically* right — M actually between A and B, the label on the outside,
an obtuse angle visibly obtuse. That turns a constraint-solving problem into
point placement, which is arithmetic.

Scene kinds
  figure     plane geometry: points, segments, rays, lines, angle arcs, ticks
  grid       coordinate system with plotted points and an optional polygon
  bars       single or grouped bar chart
  pie        pie chart with sector angles
  solid      3D illustration (cube/box/pyramid/cone/cylinder) with label slots
  schematic  real-world sketch (pole and cable, road, spinner)
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from app.nvo_gen.registry import Retry

Pt = tuple[float, float]

# Default drawing box. Chosen to match the proportions of the figures printed
# beside a question in the real papers — roughly 3:2, a little wider than tall.
W, H = 260.0, 170.0

# ─── legibility guardrails ───────────────────────────────────────────────────
# Layouts are sampled rather than hand-placed, so nobody is eyeballing each
# figure any more. These are the limits the verifier enforces on every scene.
# They are not invented: they are the tightest values the hand-tuned figures
# actually produced, measured across 80 papers and rounded down, so nothing
# that was acceptable before becomes an error now.
#   label gap 47.6 → 22 · box margin 14.0 → 10 · marked angle 15.8° → 14

#: Minimum distance between two drawn point labels, in viewBox units.
MIN_LABEL_GAP = 22.0
#: Minimum clearance between any point and the edge of the drawing box.
MIN_BOX_MARGIN = 10.0
#: Narrowest marked angle whose arc is still readable.
MIN_ANGLE_DEG = 14.0


# ─── vector helpers ──────────────────────────────────────────────────────────

def lerp(a: Pt, b: Pt, t: float) -> Pt:
    """Point at parameter t along AB. t=0 → A, t=1 → B."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def midpoint(a: Pt, b: Pt) -> Pt:
    return lerp(a, b, 0.5)


def sub(a: Pt, b: Pt) -> Pt:
    return (a[0] - b[0], a[1] - b[1])


def add(a: Pt, b: Pt) -> Pt:
    return (a[0] + b[0], a[1] + b[1])


def scale(a: Pt, k: float) -> Pt:
    return (a[0] * k, a[1] * k)


def norm(a: Pt) -> float:
    return math.hypot(a[0], a[1])


def unit(a: Pt) -> Pt:
    n = norm(a)
    return (0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n)


def foot_of_perpendicular(p: Pt, a: Pt, b: Pt) -> Pt:
    """Foot of the perpendicular from P onto line AB — where a height lands."""
    ab = sub(b, a)
    denom = ab[0] * ab[0] + ab[1] * ab[1]
    if denom == 0:
        return a
    t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / denom
    return lerp(a, b, t)


def line_intersection(a1: Pt, a2: Pt, b1: Pt, b2: Pt) -> Pt | None:
    """Intersection of lines A1A2 and B1B2, or None when they are parallel."""
    d1, d2 = sub(a2, a1), sub(b2, b1)
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / den
    return lerp(a1, a2, t)


def polar(origin: Pt, radius: float, degrees: float) -> Pt:
    """Point at a bearing from origin. 0° is east; y grows downward (SVG)."""
    r = math.radians(degrees)
    return (origin[0] + radius * math.cos(r), origin[1] - radius * math.sin(r))


def angle_bisector_point(vertex: Pt, p: Pt, q: Pt, length: float) -> Pt:
    """A point along the bisector of angle P-VERTEX-Q, `length` away."""
    d = unit(add(unit(sub(p, vertex)), unit(sub(q, vertex))))
    return add(vertex, scale(d, length))


# ─── the spec ────────────────────────────────────────────────────────────────

@dataclass
class Figure:
    """A plane-geometry scene under construction."""

    width: float = W
    height: float = H
    points: dict[str, Pt] = field(default_factory=dict)
    segments: list[dict[str, Any]] = field(default_factory=list)
    rays: list[dict[str, Any]] = field(default_factory=list)
    lines: list[dict[str, Any]] = field(default_factory=list)
    angles: list[dict[str, Any]] = field(default_factory=list)
    right_angles: list[dict[str, Any]] = field(default_factory=list)
    ticks: list[dict[str, Any]] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    #: Names that carry a drawn dot. Vertices of a polygon usually don't; a
    #: marked point on a side usually does, which is how the papers print them.
    dots: set[str] = field(default_factory=set)
    #: Names deliberately not labelled (helper points used only for layout).
    hidden: set[str] = field(default_factory=set)

    # ── construction ─────────────────────────────────────────────────────
    def put(self, name: str, p: Pt, *, dot: bool = False, hidden: bool = False) -> Pt:
        self.points[name] = p
        if dot:
            self.dots.add(name)
        if hidden:
            self.hidden.add(name)
        return p

    def seg(self, a: str, b: str, *, dash: bool = False, weight: float = 1.3) -> None:
        self.segments.append({"from": a, "to": b, "dash": dash, "weight": weight})

    def segs(self, pairs: Iterable[tuple[str, str]], **kw: Any) -> None:
        for a, b in pairs:
            self.seg(a, b, **kw)

    def path(self, names: Sequence[str], *, close: bool = False, **kw: Any) -> None:
        for a, b in zip(names, names[1:]):
            self.seg(a, b, **kw)
        if close and len(names) > 2:
            self.seg(names[-1], names[0], **kw)

    def ray(self, a: str, b: str, *, extend: float = 26.0, arrow: bool = True, dash: bool = False) -> None:
        self.rays.append({"from": a, "to": b, "extend": extend, "arrow": arrow, "dash": dash})

    def line(self, a: str, b: str, *, label: str | None = None, dash: bool = False,
             pad: float = 22.0) -> None:
        """A full line drawn through two points and past them by `pad`."""
        self.lines.append({"from": a, "to": b, "label": label, "dash": dash, "pad": pad})

    def angle(self, at: str, frm: str, to: str, *, label: str | None = None,
              arcs: int = 1, fill: bool = False, radius: float = 20.0,
              reflex: bool = False) -> None:
        self.angles.append({
            "at": at, "from": frm, "to": to, "label": label,
            "arcs": arcs, "fill": fill, "r": radius, "reflex": reflex,
        })

    def right_angle(self, at: str, frm: str, to: str, *, size: float = 9.0, dot: bool = True) -> None:
        self.right_angles.append({"at": at, "from": frm, "to": to, "size": size, "dot": dot})

    def tick(self, a: str, b: str, *, count: int = 1) -> None:
        """Equal-length marks — the single/double strokes the papers use."""
        self.ticks.append({"from": a, "to": b, "count": count})

    def text(self, at: Pt, value: str, *, anchor: str = "middle", size: float = 10.5,
             italic: bool = False) -> None:
        self.texts.append({"x": round(at[0], 2), "y": round(at[1], 2), "text": value,
                           "anchor": anchor, "size": size, "italic": italic})

    def label_along(self, a: str, b: str, value: str, *, offset: float = 11.0, t: float = 0.5) -> None:
        """Put a measurement beside segment AB, pushed off to the outer side."""
        pa, pb = self.points[a], self.points[b]
        base = lerp(pa, pb, t)
        d = unit(sub(pb, pa))
        n = (-d[1], d[0])
        centre = self._centroid()
        if (base[0] + n[0] - centre[0]) ** 2 + (base[1] + n[1] - centre[1]) ** 2 < \
           (base[0] - n[0] - centre[0]) ** 2 + (base[1] - n[1] - centre[1]) ** 2:
            n = (-n[0], -n[1])
        self.text(add(base, scale(n, offset)), value)

    # ── output ───────────────────────────────────────────────────────────
    def _centroid(self) -> Pt:
        visible = [p for name, p in self.points.items() if name not in self.hidden]
        if not visible:
            return (self.width / 2, self.height / 2)
        return (sum(p[0] for p in visible) / len(visible),
                sum(p[1] for p in visible) / len(visible))

    #: Eight compass directions a label may sit in, as unit vectors (SVG y-down).
    _COMPASS: tuple[Pt, ...] = (
        (0.0, -1.0), (0.71, -0.71), (1.0, 0.0), (0.71, 0.71),
        (0.0, 1.0), (-0.71, 0.71), (-1.0, 0.0), (-0.71, -0.71),
    )

    def _label_offsets(self) -> dict[str, list[float]]:
        """Place each point label in the compass direction with most clearance.

        "Push it away from the centroid" is not enough on its own: when two
        labelled points are close together — the foot of a height and the
        vertex it is near, say — both get pushed the same way and the glyphs
        collide. Scoring the eight directions by how far the label lands from
        every other point, with a tie-break toward the outside of the figure,
        separates them for the cost of 8n distance checks on a figure with
        fewer than a dozen points.
        """
        centre = self._centroid()
        radius = 13.0
        visible = [(n, p) for n, p in self.points.items() if n not in self.hidden]
        placed: list[Pt] = []
        out: dict[str, list[float]] = {}

        for name, p in visible:
            outward = unit(sub(p, centre)) or (0.0, 1.0)
            best: Pt = outward
            best_score = float("-inf")
            for d in self._COMPASS:
                spot = add(p, scale(d, radius))
                # Distance to the nearest other labelled point, and to the
                # nearest label already placed — both matter.
                clearance = min(
                    [norm(sub(spot, q)) for n2, q in visible if n2 != name] or [99.0]
                )
                crowding = min([norm(sub(spot, q)) for q in placed] or [99.0])
                outwardness = d[0] * outward[0] + d[1] * outward[1]
                score = min(clearance, 40.0) + min(crowding, 30.0) * 0.8 + outwardness * 6.0
                if score > best_score:
                    best_score, best = score, d
            spot = add(p, scale(best, radius))
            placed.append(spot)
            # +4 on y because SVG text sits on its baseline, so a label placed
            # "below" a point needs to clear the glyph height.
            out[name] = [round(best[0] * 11.0, 2), round(best[1] * 13.0 + 4.0, 2)]
        return out

    # ── pose ─────────────────────────────────────────────────────────────
    def pose(self, rng: random.Random) -> None:
        """Mirror, rotate and rescale the whole figure a little.

        A similarity transform preserves everything a figure asserts — equal
        segments stay equal, a right angle stays right, a point between two
        others stays between them — so it is the one variation that is safe to
        apply to *any* figure, including the ones built point by point rather
        than from a named layout. The official papers orient the same
        construction differently from year to year, so this is fidelity as much
        as variety.

        Rotation is kept small because printed NVO figures are very nearly
        axis-aligned: a triangle tilted 30° reads as a mistake, not a variant.
        The mirror is the bigger lever and costs nothing.
        """
        flip = -1.0 if rng.random() < 0.5 else 1.0
        theta = math.radians(rng.uniform(-7.0, 7.0))
        k = rng.uniform(0.94, 1.06)
        cos, sin = math.cos(theta) * k, math.sin(theta) * k
        cx, cy = self._centroid()

        def move(p: Pt) -> Pt:
            x, y = (p[0] - cx) * flip, p[1] - cy
            return (cx + x * cos - y * sin, cy + x * sin + y * cos)

        self.points = {n: move(p) for n, p in self.points.items()}
        for t in self.texts:
            t["x"], t["y"] = (round(v, 2) for v in move((t["x"], t["y"])))
        self._refit()

    def _refit(self) -> None:
        """Bring every point back inside the box, shrinking only if it must.

        A pose can push a corner past the edge. Translating is free and keeps
        the figure the size it was drawn; scaling is the fallback, applied
        uniformly so proportions survive.
        """
        pad = MIN_BOX_MARGIN + 6.0
        pts = list(self.points.values()) + [(t["x"], t["y"]) for t in self.texts]
        if not pts:
            return
        lo_x, hi_x = min(p[0] for p in pts), max(p[0] for p in pts)
        lo_y, hi_y = min(p[1] for p in pts), max(p[1] for p in pts)

        span_x, span_y = hi_x - lo_x, hi_y - lo_y
        room_x, room_y = self.width - 2 * pad, self.height - 2 * pad
        k = min(1.0, room_x / span_x if span_x else 1.0, room_y / span_y if span_y else 1.0)

        # Scale about the bounding box's centre, then centre it in the box.
        mid_x, mid_y = (lo_x + hi_x) / 2.0, (lo_y + hi_y) / 2.0
        to_x, to_y = self.width / 2.0, self.height / 2.0

        def fit(p: Pt) -> Pt:
            return (to_x + (p[0] - mid_x) * k, to_y + (p[1] - mid_y) * k)

        self.points = {n: fit(p) for n, p in self.points.items()}
        for t in self.texts:
            t["x"], t["y"] = (round(v, 2) for v in fit((t["x"], t["y"])))

    def to_spec(self, *, aria: str, rng: random.Random | None = None) -> dict[str, Any]:
        """Freeze the figure into the spec the client renderer speaks.

        Passing an rng poses the figure first, which is what stops two papers
        printing the same picture. It is applied here rather than in each
        builder so that a figure assembled by hand gets it too.
        """
        if rng is not None:
            self.pose(rng)
        return {
            "kind": "figure",
            "width": self.width,
            "height": self.height,
            "points": {k: [round(v[0], 2), round(v[1], 2)] for k, v in self.points.items()},
            "hidden": sorted(self.hidden),
            "dots": sorted(self.dots),
            "segments": self.segments,
            "rays": self.rays,
            "lines": self.lines,
            "angles": self.angles,
            "rightAngles": self.right_angles,
            "ticks": self.ticks,
            "texts": self.texts,
            "labelOffsets": self._label_offsets(),
            "aria": aria,
        }


#: Scene keys that say what a figure *says* rather than what it *looks like*.
#: Dropped before hashing, so "same picture, different numbers on it" collapses
#: to one hash — which is what figure-level dedup has to mean. Comparing raw
#: JSON would be satisfied by relabelling a single angle.
_LABEL_KEYS = frozenset({"aria", "texts", "labelOffsets", "labels", "unitLabel",
                         "yLabel", "title", "headers", "rows"})


def geometry_hash(scene: dict[str, Any]) -> str:
    """A stable fingerprint of the picture a scene draws, ignoring its labels.

    Two items on one paper may not print the same figure. Before this existed
    nothing compared them, and half of all papers shipped with one repeated —
    ``median_to_hypotenuse`` and ``median_hypotenuse_from_median`` both drew the
    canonical right triangle, down to the pixel.
    """
    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in sorted(value.items())
                    if k not in _LABEL_KEYS and k != "label"}
        if isinstance(value, (list, tuple)):
            return [strip(v) for v in value]
        if isinstance(value, float):
            # Pose transforms leave irrational coordinates; round so that two
            # figures identical to within a rendering pixel hash alike.
            return round(value, 1)
        return value

    payload = json.dumps(strip(scene), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.blake2s(payload.encode("utf-8"), digest_size=8).hexdigest()


def deg(value: float) -> str:
    """Format an angle the way the papers print it."""
    return f"{value:g}°"


# ─── layout contracts ────────────────────────────────────────────────────────
# A layout used to be a constant: `scalene_triangle()` returned the same three
# points every time, so every paper printed the same triangle with different
# numbers written on it. Layouts are now *sampled* per draw.
#
# That is only safe because each one declares what must stay true of every
# sample it produces. The contract used to live in a docstring, which is why it
# broke silently once: the old scalene layout was 87.9° at C, so the foot of the
# perpendicular from B landed on top of C and the figure contradicted its own
# stem. `triangle_for_cevians` exists because of that. Stated as a predicate
# instead, the same mistake fails in CI.
#
# Called with no rng a layout still returns a fixed canonical sample, and that
# sample is checked against the same contract — so a hand-written layout cannot
# drift out of its own family either.


class LayoutError(Retry):
    """A layout could not produce a sample satisfying its own invariants.

    A ``Retry``, like ``distractors.DistractorError``: a parameter draw the
    layout cannot close is a bad draw, not a broken template. Left as an
    ordinary exception it would reach ``assemble._try_template``, become an
    ``AssemblyError``, fail the whole paper, and send the student down the
    router's OpenAI fallback — a worse paper, generated slower, for a condition
    that means nothing more than "sample again".
    """


def angle_deg(vertex: Pt, a: Pt, b: Pt) -> float:
    """Degrees in ∠a-vertex-b, as drawn.

    Public because a template sometimes has to check an angle it just built:
    `verify.py` rejects an arc under MIN_ANGLE_DEG, and an item that would draw
    one is better off raising Retry than failing the paper.
    """
    d1, d2 = sub(a, vertex), sub(b, vertex)
    n1, n2 = norm(d1), norm(d2)
    if not n1 or not n2:
        return 0.0
    cos = max(-1.0, min(1.0, (d1[0] * d2[0] + d1[1] * d2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


_angle_deg = angle_deg


def angle_below(vertex: str, a: str, b: str, limit: float) -> Any:
    """∠a-vertex-b must stay under `limit`. 85° is "comfortably acute"."""
    def check(f: "Figure") -> str | None:
        d = _angle_deg(f.points[vertex], f.points[a], f.points[b])
        return None if d < limit else f"angle {a}{vertex}{b} is {d:.1f}°, wanted < {limit}°"
    return check


def angle_above(vertex: str, a: str, b: str, limit: float) -> Any:
    """∠a-vertex-b must stay over `limit` — a sliver of a triangle reads badly."""
    def check(f: "Figure") -> str | None:
        d = _angle_deg(f.points[vertex], f.points[a], f.points[b])
        return None if d > limit else f"angle {a}{vertex}{b} is {d:.1f}°, wanted > {limit}°"
    return check


def points_inside(margin: float = MIN_BOX_MARGIN + 6.0) -> Any:
    """Every visible point must sit clear of the drawing box's edge.

    Hidden points are exempt: they are layout anchors for lines that are meant
    to run out to the edge of the figure.
    """
    def check(f: "Figure") -> str | None:
        for name, (x, y) in f.points.items():
            if name in f.hidden:
                continue
            if min(x, y, f.width - x, f.height - y) < margin:
                return f"point {name} at ({x:.0f}, {y:.0f}) is too near the edge"
        return None
    return check


def sides_differ(a: str, b: str, c: str, *, by: float = 12.0) -> Any:
    """A scalene triangle has to *look* scalene, or its tick marks mislead."""
    def check(f: "Figure") -> str | None:
        pa, pb, pc = f.points[a], f.points[b], f.points[c]
        lengths = sorted((norm(sub(pa, pb)), norm(sub(pb, pc)), norm(sub(pc, pa))))
        if lengths[1] - lengths[0] < by or lengths[2] - lengths[1] < by:
            return f"sides {[round(v) for v in lengths]} are too close to equal"
        return None
    return check


def legs_equal(apex: str, a: str, b: str, *, tol: float = 1.5) -> Any:
    """The two legs from `apex` must be drawn equal, since ticks will say so."""
    def check(f: "Figure") -> str | None:
        la = norm(sub(f.points[a], f.points[apex]))
        lb = norm(sub(f.points[b], f.points[apex]))
        return None if abs(la - lb) <= tol else f"legs differ by {abs(la - lb):.1f}"
    return check


def circumcentre(a: Pt, b: Pt, c: Pt) -> Pt | None:
    """Where the three perpendicular bisectors meet, or None if degenerate."""
    mab, mac = midpoint(a, b), midpoint(a, c)
    dab, dac = sub(b, a), sub(c, a)
    nab, nac = (-dab[1], dab[0]), (-dac[1], dac[0])
    return line_intersection(mab, add(mab, nab), mac, add(mac, nac))


def inside_box(name: str, margin: float = MIN_BOX_MARGIN + 6.0) -> Any:
    """One named point must sit clear of the edge, hidden or not.

    `points_inside` exempts hidden points because they are anchors for lines
    meant to run off the figure. An extension point that an arc will be drawn
    around is the opposite case: it is hidden, but it must be reachable.
    """
    def check(f: "Figure") -> str | None:
        x, y = f.points[name]
        if min(x, y, f.width - x, f.height - y) < margin:
            return f"point {name} at ({x:.0f}, {y:.0f}) is too near the edge"
        return None
    return check


def points_apart(a: str, b: str, *, by: float = 20.0) -> Any:
    """Two points must be far enough apart that their labels do not collide.

    `verify.py` rejects a scene whose labels overlap, which would turn a layout
    that occasionally draws two cevian feet on top of each other into an
    intermittent paper failure. Asserting the separation here makes it a
    resample instead.
    """
    def check(f: "Figure") -> str | None:
        d = norm(sub(f.points[a], f.points[b]))
        return None if d >= by else f"{a} and {b} are {d:.1f} apart, wanted >= {by}"
    return check


def foot_and_midpoint_apart(apex: str, a: str, b: str, *, by: float = 22.0) -> Any:
    """The altitude's foot and the median's must be visibly different points.

    A triangle near-isosceles about `apex` puts them on top of each other, and
    a figure captioned "CP is a height and CM is a median" that draws one
    segment contradicts its own stem.
    """
    def check(f: "Figure") -> str | None:
        pa, pb, pc = f.points[a], f.points[b], f.points[apex]
        d = norm(sub(foot_of_perpendicular(pc, pa, pb), midpoint(pa, pb)))
        return None if d >= by else f"foot and midpoint are {d:.1f} apart, wanted >= {by}"
    return check


def circumcentre_inside(a: str, b: str, c: str, *, margin: float = 16.0) -> Any:
    """The circumcentre must land strictly inside, clear of every side.

    True exactly when the triangle is acute. An obtuse one puts the meeting
    point of the perpendicular bisectors outside the triangle, which is
    correct mathematics and an unreadable figure at this size.
    """
    def check(f: "Figure") -> str | None:
        pa, pb, pc = f.points[a], f.points[b], f.points[c]
        o = circumcentre(pa, pb, pc)
        if o is None:
            return "degenerate triangle has no circumcentre"
        for p, q in ((pa, pb), (pb, pc), (pc, pa)):
            if norm(sub(o, foot_of_perpendicular(o, p, q))) < margin:
                return f"circumcentre sits {margin:.0f} or less from a side"
        return None
    return check


#: How many samples a layout may draw before it admits defeat. Generous: a
#: rejected sample costs microseconds, a LayoutError costs a whole paper.
LAYOUT_TRIES = 80


def layout(*, invariants: Sequence[Any] = (), tries: int = LAYOUT_TRIES) -> Any:
    """Re-sample the decorated layout until every invariant holds.

    With no rng the function is deterministic, so it is called once and its
    canonical sample is still checked — a canonical layout that violates its
    own contract is a bug that should fail at test time, not a figure that
    quietly contradicts its stem.
    """
    def decorate(fn):
        @functools.wraps(fn)
        def build(*args: Any, **kw: Any) -> "Figure":
            attempts = tries if kw.get("rng") is not None else 1
            problem = ""
            for _ in range(attempts):
                f = fn(*args, **kw)
                problem = next((msg for inv in invariants if (msg := inv(f))), "")
                if not problem:
                    return f
            raise LayoutError(f"{fn.__name__} after {attempts} tries: {problem}")
        return build
    return decorate


# ─── the layouts ─────────────────────────────────────────────────────────────
# Each returns a Figure with the named points already placed; the builders in
# templates/ add the marks. Coordinates are never derived from the stem's
# numbers — that is exactly the licence the scale notice grants.

@layout(invariants=[
    angle_below("A", "B", "C", 85.0),
    angle_below("C", "A", "B", 85.0),
    angle_above("B", "A", "C", 24.0),
    sides_differ("A", "B", "C"),
    points_inside(),
])
def scalene_triangle(fig: "Figure | None" = None, *, flat: bool = False,
                     rng: random.Random | None = None) -> "Figure":
    """A, B along the bottom; C up and to the right. The default triangle.

    Both base angles are kept comfortably acute, which is exactly the condition
    for the foot of a perpendicular from either base vertex to land strictly
    inside the opposite side. The old fixed layout missed that by a hair.
    """
    f = fig or Figure()
    if rng is None:
        base_y, ax, bx = 138.0, 26.0, 228.0
        t, cy = (0.74, 38.0) if not flat else (0.78, 44.0)
    else:
        base_y = rng.uniform(130.0, 143.0)
        ax = rng.uniform(22.0, 34.0)
        bx = rng.uniform(210.0, 236.0)
        t = rng.uniform(0.56, 0.78) if not flat else rng.uniform(0.70, 0.80)
        cy = rng.uniform(26.0, 48.0) if not flat else rng.uniform(34.0, 48.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", (ax + t * (bx - ax), cy))
    return f


@layout(invariants=[
    angle_above("A", "B", "C", 20.0),
    angle_above("B", "A", "C", 20.0),
    points_inside(),
])
def right_triangle(fig: "Figure | None" = None, *,
                   rng: random.Random | None = None) -> "Figure":
    """Right angle at C, hypotenuse AB along the bottom.

    C is placed *on* the circle with diameter AB, so the angle at C really is
    90° and the right-angle mark lands on a right angle. The figure needn't be
    to scale, but a square drawn on a visibly 96° corner reads as a mistake —
    which is why C is constructed from the circle rather than sampled freely.
    """
    f = fig or Figure()
    if rng is None:
        base_y, ax, bx, bearing = 138.0, 26.0, 234.0, 55.0
    else:
        base_y = rng.uniform(130.0, 142.0)
        ax = rng.uniform(22.0, 34.0)
        bx = rng.uniform(214.0, 238.0)
        # Keeps both acute angles roughly between 25° and 65°.
        bearing = rng.uniform(42.0, 138.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", polar(((ax + bx) / 2.0, base_y), (bx - ax) / 2.0, bearing))
    return f


@layout(invariants=[
    angle_below("A", "B", "C", 80.0),
    angle_below("C", "A", "B", 80.0),
    angle_above("A", "B", "C", 26.0),
    angle_above("C", "A", "B", 26.0),
    points_inside(),
])
def triangle_for_cevians(fig: "Figure | None" = None, *,
                         rng: random.Random | None = None) -> "Figure":
    """A triangle whose angles at A and C are both clearly acute.

    Tighter than `scalene_triangle` on purpose: two cevian feet — the height's
    and the bisector's — have to fit between the vertices without their labels
    colliding, so both base angles get more room than the generic layout needs.
    """
    f = fig or Figure()
    if rng is None:
        ax, bx, base_y, cx, cy = 30.0, 200.0, 140.0, 130.0, 26.0
    else:
        ax = rng.uniform(24.0, 38.0)
        bx = rng.uniform(186.0, 214.0)
        base_y = rng.uniform(132.0, 145.0)
        cx = ax + rng.uniform(0.44, 0.66) * (bx - ax)
        cy = rng.uniform(22.0, 42.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", (cx, cy))
    return f


@layout(invariants=[
    legs_equal("C", "A", "B"),
    angle_above("C", "A", "B", 30.0),
    angle_below("C", "A", "B", 108.0),
    points_inside(),
])
def isosceles_triangle(fig: "Figure | None" = None, *,
                       rng: random.Random | None = None) -> "Figure":
    """AC = BC, apex C centred over AB."""
    f = fig or Figure()
    if rng is None:
        ax, bx, base_y, cy = 44.0, 216.0, 138.0, 36.0
    else:
        half = rng.uniform(76.0, 92.0)
        centre_x = rng.uniform(124.0, 136.0)
        ax, bx = centre_x - half, centre_x + half
        base_y = rng.uniform(132.0, 144.0)
        cy = rng.uniform(28.0, 56.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", ((ax + bx) / 2.0, cy))
    return f


@layout(invariants=[points_inside()])
def parallelogram(fig: "Figure | None" = None, *, rhombus: bool = False,
                  rect: bool = False, rng: random.Random | None = None) -> "Figure":
    """ABCD counter-clockwise from the bottom-left, D above A.

    A rhombus is drawn with all four sides genuinely equal and a rectangle with
    genuine right angles, because in both cases the marks on the figure assert
    it. Only the generic parallelogram is free to vary its skew.
    """
    f = fig or Figure()
    if rect:
        if rng is None:
            ax, bx, top, bottom = 40.0, 222.0, 42.0, 136.0
        else:
            ax = rng.uniform(32.0, 48.0)
            bx = rng.uniform(204.0, 230.0)
            top = rng.uniform(32.0, 52.0)
            bottom = rng.uniform(128.0, 142.0)
        f.put("A", (ax, bottom))
        f.put("B", (bx, bottom))
        f.put("C", (bx, top))
        f.put("D", (ax, top))
        return f

    if rhombus:
        # A real rhombus, with all four sides equal — the old layout drew sides
        # of 150 and 104 and called it one, which reads as a plain
        # parallelogram next to a stem that says „ромб“. Equal sides force the
        # skew, and the skew makes the figure wide, so it is centred in the box
        # rather than pinned to a left margin that would push C off the edge.
        if rng is None:
            side, rise, bottom = 118.0, 86.0, 132.0
        else:
            side = rng.uniform(106.0, 126.0)
            rise = rng.uniform(78.0, 96.0)
            bottom = rng.uniform(126.0, 138.0)
        skew = math.sqrt(max(side * side - rise * rise, 1.0))
        base = side
        ax = (f.width - (skew + base)) / 2.0
    elif rng is None:
        ax, bottom, rise, skew, base = 34.0, 136.0, 90.0, 42.0, 158.0
    else:
        ax = rng.uniform(26.0, 42.0)
        bottom = rng.uniform(130.0, 142.0)
        rise = rng.uniform(78.0, 98.0)
        skew = rng.uniform(28.0, 56.0)
        base = rng.uniform(144.0, 166.0)

    f.put("A", (ax, bottom))
    f.put("B", (ax + base, bottom))
    f.put("D", (ax + skew, bottom - rise))
    f.put("C", (ax + skew + base, bottom - rise))
    return f


@layout(invariants=[])
def two_parallel_lines(fig: "Figure | None" = None, *,
                       rng: random.Random | None = None) -> "Figure":
    """Horizontal lines b (top) and a (bottom), with anchors for a transversal."""
    f = fig or Figure()
    if rng is None:
        top, bottom = 38.0, 140.0
    else:
        top = rng.uniform(30.0, 48.0)
        bottom = rng.uniform(126.0, 146.0)
    f.put("bL", (18.0, top), hidden=True)
    f.put("bR", (242.0, top), hidden=True)
    f.put("aL", (18.0, bottom), hidden=True)
    f.put("aR", (242.0, bottom), hidden=True)
    return f


@layout(invariants=[
    angle_below("A", "B", "C", 80.0),
    angle_below("B", "A", "C", 80.0),
    angle_above("A", "B", "C", 27.0),
    angle_above("B", "A", "C", 27.0),
    foot_and_midpoint_apart("C", "A", "B"),
    points_inside(),
])
def triangle_for_three_cevians(fig: "Figure | None" = None, *, lopsided: bool = False,
                               apex_left: bool = False,
                               rng: random.Random | None = None) -> "Figure":
    """A triangle that can carry a height, a median and a bisector from C at once.

    Three feet have to fit along AB with their labels legible, which is a
    stronger demand than `triangle_for_cevians` makes for two. Both base angles
    are held between 30° and 78° so every foot lands strictly inside AB, and
    the triangle is kept away from isosceles so the height's foot and the
    median's are visibly different points — see `foot_and_midpoint_apart`.

    This is the shape of the densest recurring figure in the corpus: it appears
    in the 2015, 2017, 2019, 2020 and 2023 papers.

    `lopsided` pushes the apex further off-centre. An item that *marks* the
    angle between two of the cevians needs that: the arc it draws spans roughly
    the foot-to-foot distance over the height, so a merely off-centre triangle
    yields 8°, under the legibility floor `verify.py` enforces.

    `apex_left` fixes which side the apex falls on. Since AB is horizontal, the
    height's foot sits directly under C, so an apex left of centre is exactly
    the condition "∠A > ∠B" — which a stem that names both angles has already
    committed to. Letting the layout choose freely and rejecting half the draws
    in the template wastes half the samples for nothing.
    """
    f = fig or Figure()
    if rng is None:
        ax, bx, base_y, cy = 28.0, 214.0, 140.0, 28.0
        t = (0.24 if apex_left else 0.76) if lopsided else 0.62
    else:
        ax = rng.uniform(22.0, 34.0)
        bx = rng.uniform(200.0, 222.0)
        base_y = rng.uniform(134.0, 146.0)
        # Deliberately off-centre: t near 0.5 is the near-isosceles case the
        # foot/midpoint invariant would reject anyway.
        spread = (0.16, 0.28) if lopsided else (0.30, 0.42)
        left = rng.uniform(*spread)
        t = left if apex_left else rng.choice((left, 1.0 - left))
        cy = rng.uniform(24.0, 44.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", (ax + t * (bx - ax), cy))
    return f


@layout(invariants=[
    angle_above("A", "B", "C", 26.0),
    angle_above("B", "A", "C", 26.0),
    angle_below("C", "A", "B", 96.0),
    inside_box("E"),
    points_apart("B", "E", by=26.0),
    points_inside(),
])
def triangle_with_extended_side(fig: "Figure | None" = None, *,
                                rng: random.Random | None = None) -> "Figure":
    """Triangle ABC with AB produced beyond B to a hidden anchor E.

    The exterior angle the papers mark is ∠CBE, supplementary to ∠ABC. The
    base is the side to produce: extending a slanted side instead runs the
    anchor off the top of a 260×170 box within a few tries, since the apex is
    already near it. B is therefore kept left of centre to leave the extension
    room.

    E is hidden, so `points_inside` exempts it — but an arc gets drawn around
    it, so it must actually be reachable. `inside_box("E")` asserts that, and
    `points_apart` keeps the extension long enough for the arc to read.
    """
    f = fig or Figure()
    if rng is None:
        ax, bx, base_y, t, cy, reach = 28.0, 168.0, 140.0, 0.40, 46.0, 0.34
    else:
        ax = rng.uniform(24.0, 34.0)
        bx = rng.uniform(150.0, 175.0)
        base_y = rng.uniform(130.0, 144.0)
        t = rng.uniform(0.30, 0.55)
        cy = rng.uniform(34.0, 60.0)
        reach = rng.uniform(0.25, 0.42)
    A = f.put("A", (ax, base_y))
    B = f.put("B", (bx, base_y))
    f.put("C", (ax + t * (bx - ax), cy))
    f.put("E", add(B, scale(sub(B, A), reach)), hidden=True)
    return f


@layout(invariants=[
    angle_below("A", "B", "C", 76.0),
    angle_below("B", "A", "C", 76.0),
    angle_below("C", "A", "B", 76.0),
    angle_above("A", "B", "C", 34.0),
    circumcentre_inside("A", "B", "C"),
    points_inside(),
])
def triangle_for_circumcentre(fig: "Figure | None" = None, *,
                              rng: random.Random | None = None) -> "Figure":
    """An acute triangle whose perpendicular bisectors meet well inside it.

    Every angle is held under 76°, which is what puts the circumcentre inside
    with room to spare; `circumcentre_inside` then checks the consequence
    rather than trusting the bound. The 2019 and 2025 papers both print this
    figure with two of the three bisectors drawn.
    """
    f = fig or Figure()
    # Holding every angle under 76° is a constraint on the *proportions*: for an
    # apex over the middle of the base it needs height > 1.28 × half-base. A
    # triangle as wide as the generic layouts draw cannot satisfy it inside a
    # 260×170 box, so this one is deliberately narrower and taller.
    if rng is None:
        ax, bx, base_y, t, cy = 42.0, 192.0, 140.0, 0.50, 22.0
    else:
        ax = rng.uniform(36.0, 48.0)
        bx = rng.uniform(185.0, 200.0)
        base_y = rng.uniform(134.0, 144.0)
        t = rng.uniform(0.42, 0.58)
        cy = rng.uniform(18.0, 30.0)
    f.put("A", (ax, base_y))
    f.put("B", (bx, base_y))
    f.put("C", (ax + t * (bx - ax), cy))
    return f


# ─── non-figure scenes ───────────────────────────────────────────────────────

def coordinate_grid(
    *,
    points: Sequence[tuple[str, int, int]],
    x_range: tuple[int, int] = (-2, 7),
    y_range: tuple[int, int] = (-2, 6),
    polygon: Sequence[str] = (),
    unit_label: str | None = None,
    aria: str = "",
) -> dict[str, Any]:
    """Oxy grid with labelled lattice points, optionally joined into a polygon."""
    return {
        "kind": "grid",
        "xRange": list(x_range),
        "yRange": list(y_range),
        "points": [{"name": n, "x": x, "y": y} for n, x, y in points],
        "polygon": list(polygon),
        "unitLabel": unit_label,
        "aria": aria,
    }


def bar_chart(
    *,
    categories: Sequence[str],
    values: Sequence[float],
    y_label: str = "",
    y_max: float | None = None,
    y_step: float = 5,
    series_label: str | None = None,
    aria: str = "",
) -> dict[str, Any]:
    top = y_max if y_max is not None else (math.ceil(max(values) / y_step) * y_step + y_step)
    return {
        "kind": "bars",
        "categories": list(categories),
        "series": [{"name": series_label, "values": [float(v) for v in values]}],
        "yLabel": y_label,
        "yMax": float(top),
        "yStep": float(y_step),
        "aria": aria,
    }


def grouped_bar_chart(
    *,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    y_label: str = "",
    y_step: float = 5,
    aria: str = "",
) -> dict[str, Any]:
    flat = [v for _, vals in series for v in vals]
    top = math.ceil(max(flat) / y_step) * y_step + y_step
    return {
        "kind": "bars",
        "categories": list(categories),
        "series": [{"name": n, "values": [float(v) for v in vals]} for n, vals in series],
        "yLabel": y_label,
        "yMax": float(top),
        "yStep": float(y_step),
        "aria": aria,
    }


def pie_chart(*, sectors: Sequence[tuple[str, float]], title: str | None = None,
              show_degrees: bool = True, aria: str = "") -> dict[str, Any]:
    """Sectors as (label, degrees). The papers print the angle inside the slice."""
    return {
        "kind": "pie",
        "sectors": [{"label": lab, "deg": float(d)} for lab, d in sectors],
        "title": title,
        "showDegrees": show_degrees,
        "aria": aria,
    }


def solid(*, shape: str, labels: dict[str, str], aria: str = "") -> dict[str, Any]:
    """A 3D illustration with text slots.

    These figures carry no varying mathematical structure — only the dimension
    strings change between papers — so a fixed drawing per shape is enough, and
    is what the real papers do too.
    """
    return {"kind": "solid", "shape": shape, "labels": dict(labels), "aria": aria}


def schematic(*, shape: str, labels: dict[str, str], aria: str = "") -> dict[str, Any]:
    """A real-world sketch: pole and cable, a road, a spinner."""
    return {"kind": "schematic", "shape": shape, "labels": dict(labels), "aria": aria}


def data_table(*, headers: Sequence[str], rows: Sequence[Sequence[str]], aria: str = "") -> dict[str, Any]:
    return {"kind": "table", "headers": list(headers), "rows": [list(r) for r in rows], "aria": aria}


#: Every scene kind the client renderer knows how to draw. The verifier checks
#: against this so a typo in a builder fails in CI rather than as a blank box
#: in front of a student.
SCENE_KINDS = frozenset({"figure", "grid", "bars", "pie", "solid", "schematic", "table"})

SOLID_SHAPES = frozenset({"cube", "box", "pyramid", "cone", "cylinder"})
SCHEMATIC_SHAPES = frozenset({"pole_cable", "spinner", "road"})
