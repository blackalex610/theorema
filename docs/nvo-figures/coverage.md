# NVO figure coverage

Derived from 209 figures extracted from the thirteen official papers in `NVOS/` (2015–2026), classified by reading all 24 contact sheets in `docs/nvo-figures/sheets/`.

## Headline

| | count |
|---|---|
| figures extracted | 209 |
| non-figures (instructions, marking tables, formula sheets, prose) | 69 |
| real figure archetypes | 59 |
| …already expressible by `scene.py` | 48 |
| …**uncovered, recurring in 2+ papers → BUILD** | **0** |
| …uncovered one-offs → catalogue only | 11 |

## Build list — ranked by recurrence

Uncovered archetypes appearing in two or more papers. These are the ones worth a parameterised layout builder.

| # | archetype | papers | years | evidence |
|---|---|---|---|---|

## Covered — already expressible

| archetype | papers | scene.py builder | item template |
|---|---|---|---|
| `data_table` | 8 | `data_table` | `table_share_of_total` |
| `triangle_perp_bisector_of_side` | 8 | `right_triangle` | `perp_bisector_of_hypotenuse` |
| `coordinate_grid_points` | 6 | `coordinate_grid` | `coordinate_fourth_vertex` |
| `lines_crossing_angles` | 6 | `Figure (point-built)` | `concurrent_lines_angle` |
| `triangle_cevians_multi` | 5 | `triangle_for_three_cevians` | `tri_height_bisector_median` |
| `bar_chart_simple` | 4 | `bar_chart` | `chart_peak_and_total` |
| `triangle_altitude_and_median` | 4 | `triangle_for_cevians` | `tri_height_and_bisector` |
| `parallelogram_with_cevians` | 3 | `parallelogram` | `parallelogram_isosceles_cut` |
| `parallels_transversal` | 3 | `two_parallel_lines` | `parallels_transversal_cointerior` |
| `triangle_cevian_exterior_angle` | 3 | `triangle_for_three_cevians` | `tri_cevian_exterior_angle` |
| `triangle_exterior_angle` | 3 | `triangle_with_extended_side` | `tri_exterior_angle_at_base` |
| `triangles_congruent_pair` | 3 | `scalene_triangle x2` | `congruent_triangles_angle` |
| `triangles_on_a_line` | 3 | `Figure (point-built)` | `two_triangles_on_a_line` |
| `bar_chart_algebraic` | 2 | `bar_chart` | `chart_doubling_and_mean` |
| `bar_chart_grouped` | 2 | `grouped_bar_chart` | `chart_grouped_ratio` |
| `composite_area_rectilinear` | 2 | `Figure.fill_region` | `symbolic_area_notched_rectangle` |
| `graph_distance_time_piecewise` | 2 | `line_graph` | `chart_journey_average_speed` |
| `isosceles_triangle_cevian` | 2 | `isosceles_triangle` | `tri_bisector_isosceles` |
| `parallelogram_diagonals` | 2 | `parallelogram` | `parallelogram_angle_ratio` |
| `parallels_zigzag` | 2 | `two_parallel_lines` | `parallels_zigzag` |
| `rays_from_point_on_line` | 2 | `Figure (point-built)` | `adjacent_angle_ratio` |
| `rectangle_diagonals` | 2 | `parallelogram(rect)` | `rect_diagonals_angle` |
| `right_triangle_sides` | 2 | `right_triangle` | `right_triangle_perimeter` |
| `schematic_road` | 2 | `schematic(road)` | `—` |
| `triangle_altitude_and_bisector` | 2 | `triangle_for_cevians` | `tri_height_and_bisector` |
| `triangle_cevian_perpendicular` | 2 | `triangle_for_three_cevians` | `tri_perpendicular_from_side_point` |
| `triangle_circumcentre_perp_bisectors` | 2 | `triangle_for_circumcentre` | `tri_circumcentre_central_angle` |
| `triangle_incentre` | 2 | `triangle_for_cevians` | `incentre_angle` |
| `triangle_line_through_vertex` | 2 | `triangle_for_three_cevians` | `line_through_vertex_angles` |
| `triangle_median` | 2 | `right_triangle` | `median_to_hypotenuse` |
| `triangle_plain` | 2 | `scalene_triangle` | `order_sides_by_angles` |
| `isosceles_triangle_height` | 1 | `isosceles_triangle` | `isosceles_height_apex_angle` |
| `parallelogram_bisector` | 1 | `parallelogram` | `rhombus_bisector_angle` |
| `parallelogram_height` | 1 | `parallelogram` | `parallelogram_height_area` |
| `parallelogram_on_grid` | 1 | `coordinate_grid` | `coordinate_fourth_vertex` |
| `pie_chart_angles` | 1 | `pie_chart` | `chart_pie_sector` |
| `pie_chart_callouts` | 1 | `pie_chart` | `chart_pie_sector` |
| `pie_chart_percent` | 1 | `pie_chart` | `chart_pie_sector` |
| `segment_algebraic_parts` | 1 | `Figure (point-built)` | `segment_parts_algebraic` |
| `solid_box` | 1 | `solid(box)` | `solid_box_volume` |
| `solid_cube` | 1 | `solid(cube)` | `solid_box_volume` |
| `solid_pyramid` | 1 | `solid(pyramid)` | `—` |
| `spinner` | 1 | `schematic(spinner)` | `prob_spinner` |
| `square_with_cevians` | 1 | `parallelogram(square)` | `square_diagonal_angle` |
| `trapezoid_with_perpendicular` | 1 | `right_trapezoid` | `trapezoid_cointerior_angle` |
| `triangle_bisector` | 1 | `isosceles_triangle` | `tri_bisector_isosceles` |
| `triangle_midsegment` | 1 | `triangle_for_three_cevians` | `triangle_midsegment_perimeter` |
| `triangle_on_grid_shaded` | 1 | `coordinate_grid(shaded)` | `coordinate_shaded_triangle_area` |

## Catalogue only — uncovered one-offs

Appear in a single paper. Flagged as candidates for the curated `part2_bank.py` rather than a generator template.

| archetype | year | evidence |
|---|---|---|
| `dot_lattice` | 2015 | `v3_math_7kl_may2015_p05_3.png` |
| `graph_rays_from_origin` | 2016 | `vo_7kl_math_20052016_p05_2.png` |
| `kite_axis_symmetry` | 2022 | `7kl_nvo_math_16062022_p06_4.png` |
| `number_line_inequality` | 2024 | `nvo_math-7klotgovori_21062024_p09_2.png` |
| `parallels_transversal_panel` | 2018 | `7kl-math_230518_p04_1.png` |
| `schematic_ladder_wall` | 2025 | `nvo-7-klas-math-v2-otgovori-20.06.2025_p05_2.png` |
| `symmetry_marks_figure` | 2019 | `math_190619-7kl_p05_4.png` |
| `tessellation_pattern` | 2019 | `math_190619-7kl_p06_3.png` |
| `triangle_equal_segments_chain` | 2022 | `7kl_nvo_math_16062022_p12_1.png` |
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
