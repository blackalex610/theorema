"""Dump sample scenes for the templates the figure audit added.

Feeds SceneRenderer.contactsheet.test.tsx, which turns them into an HTML sheet
that can be looked at. A scene that verifies cleanly can still read wrong to a
human -- a label crowding a vertex, an arc on the wrong side of a cevian -- and
nothing but looking catches that.

    python scripts/dump_new_scenes.py
    cd frontend && SCENES_JSON=... SCENES_HTML=... npx vitest run \
        src/components/SceneRenderer.contactsheet.test.tsx
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from app.nvo_gen import registry                      # noqa: E402
from app.nvo_gen.blueprints import BLUEPRINTS         # noqa: E402
from app.nvo_gen.registry import Retry                # noqa: E402

NEW = [
    "tri_height_bisector_median",
    "tri_exterior_angle_at_base",
    "tri_cevian_exterior_angle",
    "rect_diagonals_angle",
    "tri_perpendicular_from_side_point",
    "tri_circumcentre_central_angle",
    "line_through_vertex_angles",
]

SAMPLES = 3
OUT = Path("docs/nvo-figures/generated/scenes.json")


def main() -> int:
    slots = {}
    for bp in BLUEPRINTS.values():
        for s in bp.slots:
            slots.setdefault((s.topic, s.kind), s)

    out = []
    for code in NEW:
        tpl = registry.get_template(code)
        slot = next(s for (t, k), s in slots.items()
                    if t in tpl.topics and k in tpl.kinds)
        kept = 0
        for seed in range(4000):
            if kept >= SAMPLES:
                break
            try:
                item = tpl.build(random.Random(seed), slot)
            except Retry:
                continue
            if not item.scene:
                continue
            kept += 1
            out.append({"title": f"{code}  #{kept}",
                        "stem": item.stem[:150],
                        "scene": item.scene})
        if kept < SAMPLES:
            print(f"warning: only {kept} samples for {code}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} scenes -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
