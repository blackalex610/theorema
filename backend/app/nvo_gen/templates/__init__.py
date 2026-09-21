"""Item templates, grouped by strand.

Importing any of these modules registers its templates with
``app.nvo_gen.registry``. The registry imports them all lazily on first use —
see ``registry._ensure_loaded``.

  numbers       arithmetic, powers, percent, shortcut multiplication
  algebra       equations, inequalities, factoring, expression values
  wordproblems  work rate, mixture, ratio, units, percent in context
  data          probability and chart/table reading
  geometry      every geom_* topic, each with its figure
"""
