"""How many genuinely different papers can the generator actually produce?

"Infinite" is the wrong question: the generator samples a finite parameter
space, and `signature` is precisely the field that says when two draws are the
same item. This counts the reachable space slot by slot and multiplies out.

Deliberately conservative. Distinct signatures are measured by sampling, so
every count here is a lower bound on the true space, never an over-estimate.

    python scripts/measure_capacity.py
"""

from __future__ import annotations

import random
import sys
from math import prod
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from app.nvo_gen import part2_bank, registry                      # noqa: E402
from app.nvo_gen.blueprints import BLUEPRINTS                     # noqa: E402
from app.nvo_gen.registry import Retry                            # noqa: E402

DRAWS = 1500


def signatures(tpl, slot) -> set[str]:
    """Distinct signatures this template reaches for this slot."""
    seen: set[str] = set()
    for seed in range(DRAWS):
        try:
            item = tpl.build(random.Random(seed), slot)
        except Retry:
            continue
        except Exception:
            continue
        if item.signature:
            seen.add(item.signature)
    return seen


def main() -> int:
    for code, bp in BLUEPRINTS.items():
        print(f"\n{'=' * 74}\n{code}: {len(bp.slots)} slots\n{'=' * 74}")
        print(f"{'pos':>3} {'topic':<30} {'kind':<6} {'tpls':>4} {'distinct items':>15}")
        per_slot: list[int] = []
        thin: list[str] = []

        for slot in bp.slots:
            if slot.kind == "open":
                n = len(part2_bank.bank_for(slot.topic))
                per_slot.append(max(n, 1))
                print(f"{slot.position:>3} {slot.topic:<30} {slot.kind:<6} "
                      f"{n:>4} {'(curated bank)':>15}")
                continue

            tpls = registry.templates_for(slot)
            total = 0
            for tpl in tpls:
                total += len(signatures(tpl, slot))
            per_slot.append(max(total, 1))
            flag = "  <-- thin" if len(tpls) < 3 or total < 20 else ""
            if flag:
                thin.append(f"{slot.position} {slot.topic}")
            print(f"{slot.position:>3} {slot.topic:<30} {slot.kind:<6} "
                  f"{len(tpls):>4} {total:>15,}{flag}")

        combos = prod(per_slot)
        part1 = prod(n for n, s in zip(per_slot, bp.slots) if s.kind != "open")
        part2 = prod(n for n, s in zip(per_slot, bp.slots) if s.kind == "open")
        print(f"\n  Part 1 distinct combinations : {part1:.3e}")
        print(f"  Part 2 distinct combinations : {part2:,}")
        print(f"  whole-paper combinations     : {combos:.3e}")
        if thin:
            print(f"  thinnest slots: {'; '.join(thin)}")

    print(f"\n{'=' * 74}")
    print("Counts are lower bounds: signatures are sampled over "
          f"{DRAWS} seeds per template, not enumerated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
