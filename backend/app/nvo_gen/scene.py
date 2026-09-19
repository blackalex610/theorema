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

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

Pt = tuple[float, float]

# Default drawing box. Chosen to match the proportions of the figures printed
# beside a question in the real papers — roughly 3:2, a little wider than tall.
W, H = 260.0, 170.0


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

    def to_spec(self, *, aria: str) -> dict[str, Any]:
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


def deg(value: float) -> str:
    """Format an angle the way the papers print it."""
    return f"{value:g}°"


# ─── canonical layouts ───────────────────────────────────────────────────────
# Each returns a Figure with the named points already placed. Builders below
# add the marks. Coordinates are chosen once, by eye, to look like the printed
# figures — never derived from the stem's numbers, which is exactly the licence
# the scale notice grants.

def scalene_triangle(fig: Figure | None = None, *, flat: bool = False) -> Figure:
    """A, B along the bottom; C up and to the right. The default triangle."""
    f = fig or Figure()
    f.put("A", (26.0, 138.0))
    f.put("B", (228.0, 138.0))
    f.put("C", (176.0, 46.0) if not flat else (196.0, 60.0))
    return f


def right_triangle(fig: Figure | None = None) -> Figure:
    """Right angle at C, hypotenuse AB along the bottom.

    C sits on the circle with diameter AB, so the angle at C really is 90° and
    the right-angle mark lands on a right angle. The figure needn't be to
    scale, but a square drawn on a visibly 96° corner reads as a mistake.
    """
    f = fig or Figure()
    f.put("A", (26.0, 138.0))
    f.put("B", (234.0, 138.0))
    # Centre (130, 138), radius 104, at 55° — up and to the right, matching how
    # the official papers orient this triangle.
    f.put("C", (190.0, 53.0))
    return f


def triangle_for_cevians(fig: Figure | None = None) -> Figure:
    """A triangle whose angles at A and C are both clearly acute.

    That is exactly the condition for the foot of the height from B to land
    strictly *inside* AC. The generic scalene layout is nearly right-angled at
    C, which put the foot on top of C and made the figure contradict its own
    stem.
    """
    f = fig or Figure()
    f.put("A", (30.0, 140.0))
    f.put("B", (200.0, 140.0))
    f.put("C", (130.0, 26.0))
    return f


def isosceles_triangle(fig: Figure | None = None) -> Figure:
    """AC = BC, apex C centred over AB."""
    f = fig or Figure()
    f.put("A", (44.0, 138.0))
    f.put("B", (216.0, 138.0))
    f.put("C", (130.0, 36.0))
    return f


def parallelogram(fig: Figure | None = None, *, rhombus: bool = False,
                  rect: bool = False) -> Figure:
    """ABCD counter-clockwise from the bottom-left, D above A."""
    f = fig or Figure()
    if rect:
        f.put("A", (40.0, 136.0))
        f.put("B", (222.0, 136.0))
        f.put("C", (222.0, 42.0))
        f.put("D", (40.0, 42.0))
    else:
        skew = 42.0 if not rhombus else 52.0
        base = 150.0 if rhombus else 158.0
        f.put("A", (34.0, 136.0))
        f.put("B", (34.0 + base, 136.0))
        f.put("D", (34.0 + skew, 46.0))
        f.put("C", (34.0 + skew + base, 46.0))
    return f


def two_parallel_lines(fig: Figure | None = None) -> Figure:
    """Horizontal lines b (top) and a (bottom), with anchors for a transversal."""
    f = fig or Figure()
    f.put("bL", (18.0, 38.0), hidden=True)
    f.put("bR", (242.0, 38.0), hidden=True)
    f.put("aL", (18.0, 140.0), hidden=True)
    f.put("aR", (242.0, 140.0), hidden=True)
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
