"""Join the figure classification to the template registry and report coverage.

CLASSIFICATION was produced by reading all 24 contact sheets. COVERAGE maps each
archetype to the scene.py builder and item template that can express it, or to
None where nothing can. Everything else -- which papers an archetype appears in,
which gaps clear the two-paper bar -- is computed from inventory.json so the
matrix cannot drift from the evidence.

    python scripts/build_coverage_report.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("docs/nvo-figures")

# The year regex in the extractor mis-reads filenames that embed a date without
# a separator ("22052017" yields "2052"). Thirteen papers is few enough to name.
YEARS = {
    "v3_math_7kl_may2015": 2015,
    "vo_7kl_math_20052016": 2016,
    "7kl_math_22052017": 2017,
    "7kl-math_230518": 2018,
    "math_190619-7kl": 2019,
    "nvo-viikl-math_17062020": 2020,
    "nvo-math_7kl_18062021": 2021,
    "7kl_nvo_math_16062022": 2022,
    "nvo_math_7klas_variant2_16.06.2023": 2023,
    "nvo_math-7klotgovori_21062024": 2024,
    "nvo-7-klas-math-v2-otgovori-20.06.2025": 2025,
    "nvo26_matematika_7klasotgovori_19062026": 2026,
    "tekst_nvo_bel_math": 0,
}

# Not figures. They cluster like one but carry no geometry to parameterise.
NOISE = {
    "instruction_glyph", "text_only", "marking_table", "matching_table",
    "formula_sheet", "statement_list_box", "photo_illustration",
}

CLASSIFICATION: dict[int, str] = {}


def _tag(archetype: str, *indices: int) -> None:
    for i in indices:
        CLASSIFICATION[i] = archetype


# --- noise ------------------------------------------------------------------
_tag("instruction_glyph", 1, 2, 21, 157, 179)
_tag("text_only", 10, 12, 16, 23, 28, 35, 36, 37, 114, 119, 124, 125, 126,
     129, 130, 131, 139, 142, 144, 161, 162, 163, 170, 176, 177, 178, 192,
     202, 203, 204, 205, 207, 208, 209)
_tag("marking_table", 17, 18, 19, 20, 40, 41, 42, 44, 45, 46, 83, 127, 141,
     171, 172, 173, 174, 198, 199, 200)
_tag("matching_table", 11, 33, 34, 186)
_tag("formula_sheet", 60, 61, 62)
_tag("statement_list_box", 168)
_tag("photo_illustration", 80, 194)

# --- data and charts --------------------------------------------------------
_tag("bar_chart_simple", 13, 120, 152, 191)
_tag("bar_chart_algebraic", 55, 98)
_tag("bar_chart_grouped", 47, 111)
_tag("pie_chart_percent", 38)
_tag("pie_chart_callouts", 70)
_tag("pie_chart_angles", 140)
_tag("data_table", 14, 39, 43, 58, 81, 85, 96, 155, 166, 167, 189, 195, 196, 201)
_tag("graph_distance_time_piecewise", 159, 180, 181, 182, 183)
_tag("graph_rays_from_origin", 190)
_tag("spinner", 132)
_tag("dot_lattice", 165)
_tag("number_line_inequality", 143)
_tag("segment_algebraic_parts", 164)

# --- lines and angles -------------------------------------------------------
_tag("lines_crossing_angles", 24, 48, 78, 93, 102, 103, 133)
_tag("rays_from_point_on_line", 51, 65)
_tag("parallels_transversal", 63, 90, 104)
_tag("parallels_transversal_panel", 4)
_tag("parallels_zigzag", 118, 147)

# --- triangles --------------------------------------------------------------
_tag("triangle_plain", 8, 138)
_tag("triangle_exterior_angle", 49, 151, 158)
_tag("triangle_cevian_exterior_angle", 7, 25, 136)
_tag("triangle_altitude_and_median", 15, 66, 99, 100, 109)
_tag("triangle_altitude_and_bisector", 106, 116)
_tag("triangle_incentre", 108, 123)
_tag("triangle_perp_bisector_of_side", 6, 52, 92, 107, 117, 137, 149, 160)
_tag("triangle_circumcentre_perp_bisectors", 68, 77)
_tag("triangle_cevian_perpendicular", 5, 79)
_tag("triangle_median", 26, 122)
_tag("triangle_bisector", 184)
_tag("triangle_cevians_multi", 74, 113, 156, 175, 27, 30)
_tag("triangle_equal_segments_chain", 59)
_tag("triangle_line_through_vertex", 64, 75)
_tag("triangle_midsegment", 187)
_tag("isosceles_triangle_height", 50)
_tag("isosceles_triangle_cevian", 91, 169)
_tag("right_triangle_sides", 95, 148)
_tag("triangles_congruent_pair", 3, 89, 105)
_tag("triangles_on_a_line", 22, 29, 134, 150)
_tag("triangles_congruence_construction", 86, 87)
_tag("triangles_right_shared_side", 69)
_tag("triangle_on_grid_shaded", 185)

# --- quadrilaterals and solids ----------------------------------------------
_tag("parallelogram_with_cevians", 9, 121, 135, 145, 146)
_tag("parallelogram_height", 31)
_tag("parallelogram_bisector", 54)
_tag("parallelogram_on_grid", 94)
_tag("parallelogram_diagonals", 112, 153)
_tag("rectangle_diagonals", 32, 128)
_tag("square_with_cevians", 197, 206)
_tag("trapezoid_with_perpendicular", 188)
_tag("kite_axis_symmetry", 56)
_tag("solid_cube", 101)
_tag("solid_box", 53)
_tag("solid_pyramid", 88)

# --- coordinate, composite, misc --------------------------------------------
_tag("coordinate_grid_points", 73, 76, 97, 110, 115, 154)
_tag("composite_area_rectilinear", 67, 193)
_tag("schematic_road", 57, 84)
_tag("schematic_ladder_wall", 82)
_tag("symmetry_marks_figure", 71)
_tag("tessellation_pattern", 72)

# --- what scene.py can already express --------------------------------------
# value = (scene.py builder, item template) or None when nothing produces it.
COVERAGE: dict[str, tuple[str, str] | None] = {
    "bar_chart_simple": ("bar_chart", "chart_peak_and_total"),
    "bar_chart_algebraic": ("bar_chart", "chart_doubling_and_mean"),
    "bar_chart_grouped": ("grouped_bar_chart", "chart_grouped_ratio"),
    "pie_chart_percent": ("pie_chart", "chart_pie_sector"),
    "pie_chart_callouts": ("pie_chart", "chart_pie_sector"),
    "pie_chart_angles": ("pie_chart", "chart_pie_sector"),
    "data_table": ("data_table", "table_share_of_total"),
    "spinner": ("schematic(spinner)", "prob_spinner"),
    "schematic_road": ("schematic(road)", "—"),
    "solid_cube": ("solid(cube)", "solid_box_volume"),
    "solid_box": ("solid(box)", "solid_box_volume"),
    "solid_pyramid": ("solid(pyramid)", "—"),
    "coordinate_grid_points": ("coordinate_grid", "coordinate_fourth_vertex"),
    "parallels_transversal": ("two_parallel_lines", "parallels_transversal_cointerior"),
    "parallels_zigzag": ("two_parallel_lines", "parallels_zigzag"),
    "lines_crossing_angles": ("Figure (point-built)", "concurrent_lines_angle"),
    "rays_from_point_on_line": ("Figure (point-built)", "adjacent_angle_ratio"),
    "triangle_plain": ("scalene_triangle", "order_sides_by_angles"),
    "triangle_altitude_and_median": ("triangle_for_cevians", "tri_height_and_bisector"),
    "triangle_altitude_and_bisector": ("triangle_for_cevians", "tri_height_and_bisector"),
    "triangle_incentre": ("triangle_for_cevians", "incentre_angle"),
    "triangle_perp_bisector_of_side": ("right_triangle", "perp_bisector_of_hypotenuse"),
    "triangle_median": ("right_triangle", "median_to_hypotenuse"),
    "right_triangle_sides": ("right_triangle", "right_triangle_perimeter"),
    "isosceles_triangle_cevian": ("isosceles_triangle", "tri_bisector_isosceles"),
    "triangles_congruent_pair": ("scalene_triangle x2", "congruent_triangles_angle"),
    "triangles_on_a_line": ("Figure (point-built)", "two_triangles_on_a_line"),
    "parallelogram_with_cevians": ("parallelogram", "parallelogram_isosceles_cut"),
    "parallelogram_bisector": ("parallelogram", "rhombus_bisector_angle"),
    "parallelogram_diagonals": ("parallelogram", "parallelogram_angle_ratio"),

    # --- built to close the audit's gaps -------------------------------------
    "triangle_cevians_multi": ("triangle_for_three_cevians", "tri_height_bisector_median"),
    "triangle_exterior_angle": ("triangle_with_extended_side", "tri_exterior_angle_at_base"),
    "triangle_cevian_exterior_angle": ("triangle_for_three_cevians", "tri_cevian_exterior_angle"),
    "rectangle_diagonals": ("parallelogram(rect)", "rect_diagonals_angle"),
    "triangle_cevian_perpendicular": ("triangle_for_three_cevians",
                                      "tri_perpendicular_from_side_point"),
    "triangle_circumcentre_perp_bisectors": ("triangle_for_circumcentre",
                                             "tri_circumcentre_central_angle"),
    "triangle_line_through_vertex": ("triangle_for_three_cevians",
                                     "line_through_vertex_angles"),
    "graph_distance_time_piecewise": ("line_graph", "chart_journey_average_speed"),
    "composite_area_rectilinear": ("Figure.fill_region", "symbolic_area_notched_rectangle"),
    "parallelogram_height": ("parallelogram", "parallelogram_height_area"),
    "square_with_cevians": ("parallelogram(square)", "square_diagonal_angle"),
    "trapezoid_with_perpendicular": ("right_trapezoid", "trapezoid_cointerior_angle"),
    "triangle_midsegment": ("triangle_for_three_cevians", "triangle_midsegment_perimeter"),
    "isosceles_triangle_height": ("isosceles_triangle", "isosceles_height_apex_angle"),
    "segment_algebraic_parts": ("Figure (point-built)", "segment_parts_algebraic"),
    "triangle_on_grid_shaded": ("coordinate_grid(shaded)", "coordinate_shaded_triangle_area"),
    "parallelogram_on_grid": ("coordinate_grid", "coordinate_fourth_vertex"),
    "triangle_bisector": ("isosceles_triangle", "tri_bisector_isosceles"),

    # --- still uncovered, with the reason ------------------------------------
    # Each of these appears once in thirteen papers AND needs machinery that
    # nothing else would reuse. The note is what a future reader needs.
    "parallels_transversal_panel": None,      # four mini-figures AS the options
    "graph_rays_from_origin": None,           # linegraph exists; no item written
    "number_line_inequality": None,           # needs a number-line scene kind
    "dot_lattice": None,                      # needs a dotted-lattice scene kind
    "kite_axis_symmetry": None,               # needs a kite layout
    "triangle_equal_segments_chain": None,    # chained equalities, Part 2 shaped
    "triangles_right_shared_side": None,      # needs a two-right-triangle layout
    "triangles_congruence_construction": None,  # a Part 2 proof figure
    "schematic_ladder_wall": None,            # needs a `ladder` schematic shape
    "symmetry_marks_figure": None,            # decorative; no item behind it
    "tessellation_pattern": None,             # decorative; no item behind it
}


def main() -> int:
    index = json.loads((ROOT / "sheet_index.json").read_text(encoding="utf-8"))
    by_i = {e["i"]: e for e in index}

    papers: dict[str, set[int]] = defaultdict(set)   # archetype -> years
    crops: dict[str, list[str]] = defaultdict(list)
    unclassified: list[int] = []

    for e in index:
        arch = CLASSIFICATION.get(e["i"])
        if arch is None:
            unclassified.append(e["i"])
            continue
        papers[arch].add(YEARS.get(e["paper"], 0))
        crops[arch].append(e["crop"])

    real = {a: yrs for a, yrs in papers.items() if a not in NOISE}
    covered = {a: v for a, v in real.items() if COVERAGE.get(a) is not None}
    uncovered = {a: v for a, v in real.items() if COVERAGE.get(a) is None}
    build = {a: v for a, v in uncovered.items() if len(v) >= 2}
    catalogue = {a: v for a, v in uncovered.items() if len(v) < 2}

    years = sorted({y for y in YEARS.values() if y})

    out: list[str] = []
    w = out.append
    w("# NVO figure coverage\n")
    w(f"Derived from {len(index)} figures extracted from the thirteen official "
      "papers in `NVOS/` (2015–2026), classified by reading all 24 contact "
      "sheets in `docs/nvo-figures/sheets/`.\n")
    w("## Headline\n")
    w(f"| | count |\n|---|---|")
    w(f"| figures extracted | {len(index)} |")
    w(f"| non-figures (instructions, marking tables, formula sheets, prose) | "
      f"{sum(len(crops[a]) for a in crops if a in NOISE)} |")
    w(f"| real figure archetypes | {len(real)} |")
    w(f"| …already expressible by `scene.py` | {len(covered)} |")
    w(f"| …**uncovered, recurring in 2+ papers → BUILD** | **{len(build)}** |")
    w(f"| …uncovered one-offs → catalogue only | {len(catalogue)} |")
    w("")

    w("## Build list — ranked by recurrence\n")
    w("Uncovered archetypes appearing in two or more papers. These are the ones "
      "worth a parameterised layout builder.\n")
    w("| # | archetype | papers | years | evidence |")
    w("|---|---|---|---|---|")
    for n, (a, yrs) in enumerate(sorted(build.items(),
                                        key=lambda kv: (-len(kv[1]), kv[0])), 1):
        ev = ", ".join(f"`{c}`" for c in sorted(crops[a])[:2])
        w(f"| {n} | `{a}` | {len(yrs)} | {', '.join(map(str, sorted(yrs)))} | {ev} |")
    w("")

    w("## Covered — already expressible\n")
    w("| archetype | papers | scene.py builder | item template |")
    w("|---|---|---|---|")
    for a, yrs in sorted(covered.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        builder, tpl = COVERAGE[a]
        w(f"| `{a}` | {len(yrs)} | `{builder}` | `{tpl}` |")
    w("")

    w("## Catalogue only — uncovered one-offs\n")
    w("Appear in a single paper. Flagged as candidates for the curated "
      "`part2_bank.py` rather than a generator template.\n")
    w("| archetype | year | evidence |")
    w("|---|---|---|")
    for a, yrs in sorted(catalogue.items()):
        ev = ", ".join(f"`{c}`" for c in sorted(crops[a])[:1])
        w(f"| `{a}` | {', '.join(map(str, sorted(yrs)))} | {ev} |")
    w("")

    w("## Archetype × paper matrix\n")
    w("| archetype | " + " | ".join(str(y) for y in years) + " |")
    w("|---" * (len(years) + 1) + "|")
    for a, yrs in sorted(real.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cells = " | ".join("●" if y in yrs else "" for y in years)
        w(f"| `{a}` | {cells} |")
    w("")

    if unclassified:
        w(f"## Unclassified\n\n{len(unclassified)} figures carry no tag: "
          + ", ".join(f"#{i}" for i in unclassified) + "\n")

    (ROOT / "coverage.md").write_text("\n".join(out), encoding="utf-8")
    (ROOT / "archetypes.json").write_text(json.dumps(
        {a: {"years": sorted(y), "crops": sorted(crops[a]),
             "covered_by": COVERAGE.get(a), "noise": a in NOISE}
         for a, y in sorted(papers.items())},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"figures        {len(index)}")
    print(f"archetypes     {len(real)} real, {len(papers) - len(real)} noise classes")
    print(f"covered        {len(covered)}")
    print(f"BUILD (2+)     {len(build)}")
    print(f"catalogue      {len(catalogue)}")
    print(f"unclassified   {len(unclassified)}")
    print(f"-> {ROOT / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
