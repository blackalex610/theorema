# NVO figure coverage

Derived from 209 figures extracted from the thirteen official papers in `NVOS/` (2015–2026), classified by reading all 24 contact sheets in `docs/nvo-figures/sheets/`.

## Headline

| | count |
|---|---|
| figures extracted | 209 |
| non-figures (instructions, marking tables, formula sheets, prose) | 69 |
| real figure archetypes | 59 |
| …already expressible by `scene.py` | 30 |
| …**uncovered, recurring in 2+ papers → BUILD** | **9** |
| …uncovered one-offs → catalogue only | 20 |

## Build list — ranked by recurrence

Uncovered archetypes appearing in two or more papers. These are the ones worth a parameterised layout builder.

| # | archetype | papers | years | evidence |
|---|---|---|---|---|
| 1 | `triangle_cevians_multi` | 5 | 2015, 2017, 2019, 2020, 2023 | `7kl_math_22052017_p04_4.png`, `7kl_math_22052017_p05_2.png` |
| 2 | `triangle_cevian_exterior_angle` | 3 | 2017, 2018, 2024 | `7kl-math_230518_p04_3.png`, `7kl_math_22052017_p04_2.png` |
| 3 | `triangle_exterior_angle` | 3 | 2015, 2022, 2023 | `7kl_nvo_math_16062022_p04_4.png`, `nvo_math_7klas_variant2_16.06.2023_p04_4.png` |
| 4 | `composite_area_rectilinear` | 2 | 2016, 2019 | `math_190619-7kl_p04_2.png`, `vo_7kl_math_20052016_p06_2.png` |
| 5 | `graph_distance_time_piecewise` | 2 | 2015, 2016 | `v3_math_7kl_may2015_p03_1.png`, `vo_7kl_math_20052016_p03_1.png` |
| 6 | `rectangle_diagonals` | 2 | 2017, 2026 | `7kl_math_22052017_p06_1.png`, `nvo26_matematika_7klasotgovori_19062026_p10_2.png` |
| 7 | `triangle_cevian_perpendicular` | 2 | 2018, 2025 | `7kl-math_230518_p04_10.png`, `nvo-7-klas-math-v2-otgovori-20.06.2025_p04_1.png` |
| 8 | `triangle_circumcentre_perp_bisectors` | 2 | 2019, 2025 | `math_190619-7kl_p04_3.png`, `nvo-7-klas-math-v2-otgovori-20.06.2025_p03_4.png` |
| 9 | `triangle_line_through_vertex` | 2 | 2019, 2025 | `math_190619-7kl_p03_4.png`, `nvo-7-klas-math-v2-otgovori-20.06.2025_p03_2.png` |

## Covered — already expressible

| archetype | papers | scene.py builder | item template |
|---|---|---|---|
| `data_table` | 8 | `data_table` | `table_share_of_total` |
| `triangle_perp_bisector_of_side` | 8 | `right_triangle` | `perp_bisector_of_hypotenuse` |
| `coordinate_grid_points` | 6 | `coordinate_grid` | `coordinate_fourth_vertex` |
| `lines_crossing_angles` | 6 | `Figure (point-built)` | `concurrent_lines_angle` |
| `bar_chart_simple` | 4 | `bar_chart` | `chart_peak_and_total` |
| `triangle_altitude_and_median` | 4 | `triangle_for_cevians` | `tri_height_and_bisector` |
| `parallelogram_with_cevians` | 3 | `parallelogram` | `parallelogram_isosceles_cut` |
| `parallels_transversal` | 3 | `two_parallel_lines` | `parallels_transversal_cointerior` |
| `triangles_congruent_pair` | 3 | `scalene_triangle x2` | `congruent_triangles_angle` |
| `triangles_on_a_line` | 3 | `Figure (point-built)` | `two_triangles_on_a_line` |
| `bar_chart_algebraic` | 2 | `bar_chart` | `chart_doubling_and_mean` |
| `bar_chart_grouped` | 2 | `grouped_bar_chart` | `chart_grouped_ratio` |
| `isosceles_triangle_cevian` | 2 | `isosceles_triangle` | `tri_bisector_isosceles` |
| `parallelogram_diagonals` | 2 | `parallelogram` | `parallelogram_angle_ratio` |
| `parallels_zigzag` | 2 | `two_parallel_lines` | `parallels_zigzag` |
| `rays_from_point_on_line` | 2 | `Figure (point-built)` | `adjacent_angle_ratio` |
| `right_triangle_sides` | 2 | `right_triangle` | `right_triangle_perimeter` |
| `schematic_road` | 2 | `schematic(road)` | `—` |
| `triangle_altitude_and_bisector` | 2 | `triangle_for_cevians` | `tri_height_and_bisector` |
| `triangle_incentre` | 2 | `triangle_for_cevians` | `incentre_angle` |
| `triangle_median` | 2 | `right_triangle` | `median_to_hypotenuse` |
| `triangle_plain` | 2 | `scalene_triangle` | `order_sides_by_angles` |
| `parallelogram_bisector` | 1 | `parallelogram` | `rhombus_bisector_angle` |
| `pie_chart_angles` | 1 | `pie_chart` | `chart_pie_sector` |
| `pie_chart_callouts` | 1 | `pie_chart` | `chart_pie_sector` |
| `pie_chart_percent` | 1 | `pie_chart` | `chart_pie_sector` |
| `solid_box` | 1 | `solid(box)` | `solid_box_volume` |
| `solid_cube` | 1 | `solid(cube)` | `solid_box_volume` |
| `solid_pyramid` | 1 | `solid(pyramid)` | `—` |
| `spinner` | 1 | `schematic(spinner)` | `prob_spinner` |

## Catalogue only — uncovered one-offs

Appear in a single paper. Flagged as candidates for the curated `part2_bank.py` rather than a generator template.

| archetype | year | evidence |
|---|---|---|
| `dot_lattice` | 2015 | `v3_math_7kl_may2015_p05_3.png` |
| `graph_rays_from_origin` | 2016 | `vo_7kl_math_20052016_p05_2.png` |
| `isosceles_triangle_height` | 2022 | `7kl_nvo_math_16062022_p04_5.png` |
| `kite_axis_symmetry` | 2022 | `7kl_nvo_math_16062022_p06_4.png` |
| `number_line_inequality` | 2024 | `nvo_math-7klotgovori_21062024_p09_2.png` |
| `parallelogram_height` | 2017 | `7kl_math_22052017_p05_3.png` |
| `parallelogram_on_grid` | 2021 | `nvo-math_7kl_18062021_p05_1.png` |
| `parallels_transversal_panel` | 2018 | `7kl-math_230518_p04_1.png` |
| `schematic_ladder_wall` | 2025 | `nvo-7-klas-math-v2-otgovori-20.06.2025_p05_2.png` |
| `segment_algebraic_parts` | 2015 | `v3_math_7kl_may2015_p05_2.png` |
| `square_with_cevians` | 2016 | `vo_7kl_math_20052016_p07_5.png` |
| `symmetry_marks_figure` | 2019 | `math_190619-7kl_p05_4.png` |
| `tessellation_pattern` | 2019 | `math_190619-7kl_p06_3.png` |
| `trapezoid_with_perpendicular` | 2016 | `vo_7kl_math_20052016_p04_5.png` |
| `triangle_bisector` | 2016 | `vo_7kl_math_20052016_p03_5.png` |
| `triangle_equal_segments_chain` | 2022 | `7kl_nvo_math_16062022_p12_1.png` |
| `triangle_midsegment` | 2016 | `vo_7kl_math_20052016_p04_4.png` |
| `triangle_on_grid_shaded` | 2016 | `vo_7kl_math_20052016_p03_6.png` |
| `triangles_congruence_construction` | 2025 | `nvo-7-klas-math-v2-otgovori-20.06.2025_p10_2.png` |
| `triangles_right_shared_side` | 2019 | `math_190619-7kl_p04_4.png` |

## Archetype × paper matrix

| archetype | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `data_table` | ● | ● | ● | ● |  |  | ● | ● | ● |  | ● |  |
| `triangle_perp_bisector_of_side` | ● |  |  | ● |  | ● | ● | ● | ● | ● |  | ● |
| `coordinate_grid_points` |  |  |  |  | ● | ● | ● |  | ● |  | ● | ● |
| `lines_crossing_angles` |  |  | ● |  |  | ● | ● | ● |  | ● | ● |  |
| `triangle_cevians_multi` | ● |  | ● |  | ● | ● |  |  | ● |  |  |  |
| `bar_chart_simple` |  | ● |  | ● |  |  |  |  | ● |  |  | ● |
| `triangle_altitude_and_median` |  |  |  | ● | ● | ● | ● |  |  |  |  |  |
| `parallelogram_with_cevians` |  |  |  | ● |  |  |  |  |  | ● |  | ● |
| `parallels_transversal` |  |  |  |  | ● | ● | ● |  |  |  |  |  |
| `triangle_cevian_exterior_angle` |  |  | ● | ● |  |  |  |  |  | ● |  |  |
| `triangle_exterior_angle` | ● |  |  |  |  |  |  | ● | ● |  |  |  |
| `triangles_congruent_pair` |  |  |  | ● |  | ● | ● |  |  |  |  |  |
| `triangles_on_a_line` |  |  | ● |  |  |  |  |  | ● | ● |  |  |
| `bar_chart_algebraic` |  |  |  |  |  |  | ● | ● |  |  |  |  |
| `bar_chart_grouped` |  |  |  |  |  | ● |  | ● |  |  |  |  |
| `composite_area_rectilinear` |  | ● |  |  | ● |  |  |  |  |  |  |  |
| `graph_distance_time_piecewise` | ● | ● |  |  |  |  |  |  |  |  |  |  |
| `isosceles_triangle_cevian` | ● |  |  |  |  |  | ● |  |  |  |  |  |
| `parallelogram_diagonals` |  |  |  |  |  | ● |  |  | ● |  |  |  |
| `parallels_zigzag` |  |  |  |  |  |  |  |  | ● |  |  | ● |
| `rays_from_point_on_line` |  |  |  |  | ● |  |  | ● |  |  |  |  |
| `rectangle_diagonals` |  |  | ● |  |  |  |  |  |  |  |  | ● |
| `right_triangle_sides` |  |  |  |  |  |  | ● |  | ● |  |  |  |
| `schematic_road` |  |  |  |  |  |  |  | ● |  |  | ● |  |
| `triangle_altitude_and_bisector` |  |  |  |  |  | ● |  |  |  |  |  | ● |
| `triangle_cevian_perpendicular` |  |  |  | ● |  |  |  |  |  |  | ● |  |
| `triangle_circumcentre_perp_bisectors` |  |  |  |  | ● |  |  |  |  |  | ● |  |
| `triangle_incentre` |  |  |  |  |  | ● |  |  |  |  |  | ● |
| `triangle_line_through_vertex` |  |  |  |  | ● |  |  |  |  |  | ● |  |
| `triangle_median` |  |  | ● |  |  |  |  |  |  |  |  | ● |
| `triangle_plain` |  |  |  | ● |  |  |  |  |  | ● |  |  |
| `dot_lattice` | ● |  |  |  |  |  |  |  |  |  |  |  |
| `graph_rays_from_origin` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `isosceles_triangle_height` |  |  |  |  |  |  |  | ● |  |  |  |  |
| `kite_axis_symmetry` |  |  |  |  |  |  |  | ● |  |  |  |  |
| `number_line_inequality` |  |  |  |  |  |  |  |  |  | ● |  |  |
| `parallelogram_bisector` |  |  |  |  |  |  |  | ● |  |  |  |  |
| `parallelogram_height` |  |  | ● |  |  |  |  |  |  |  |  |  |
| `parallelogram_on_grid` |  |  |  |  |  |  | ● |  |  |  |  |  |
| `parallels_transversal_panel` |  |  |  | ● |  |  |  |  |  |  |  |  |
| `pie_chart_angles` |  |  |  |  |  |  |  |  |  | ● |  |  |
| `pie_chart_callouts` |  |  |  |  | ● |  |  |  |  |  |  |  |
| `pie_chart_percent` |  |  | ● |  |  |  |  |  |  |  |  |  |
| `schematic_ladder_wall` |  |  |  |  |  |  |  |  |  |  | ● |  |
| `segment_algebraic_parts` | ● |  |  |  |  |  |  |  |  |  |  |  |
| `solid_box` |  |  |  |  |  |  |  | ● |  |  |  |  |
| `solid_cube` |  |  |  |  |  | ● |  |  |  |  |  |  |
| `solid_pyramid` |  |  |  |  |  |  | ● |  |  |  |  |  |
| `spinner` |  |  |  |  |  |  |  |  |  | ● |  |  |
| `square_with_cevians` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `symmetry_marks_figure` |  |  |  |  | ● |  |  |  |  |  |  |  |
| `tessellation_pattern` |  |  |  |  | ● |  |  |  |  |  |  |  |
| `trapezoid_with_perpendicular` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `triangle_bisector` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `triangle_equal_segments_chain` |  |  |  |  |  |  |  | ● |  |  |  |  |
| `triangle_midsegment` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `triangle_on_grid_shaded` |  | ● |  |  |  |  |  |  |  |  |  |  |
| `triangles_congruence_construction` |  |  |  |  |  |  |  |  |  |  | ● |  |
| `triangles_right_shared_side` |  |  |  |  | ● |  |  |  |  |  |  |  |
