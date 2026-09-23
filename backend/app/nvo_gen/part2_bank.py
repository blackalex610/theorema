"""The Part 2 bank: extended items, registered by topic, drawn one per slot.

Every Part 2 item is a real paper's item, transcribed with its marking scheme
and generalised exactly as far as its reasoning allows:

  * ``part2_algebra.py`` and ``part2_word.py`` — the 2020–2026 algebra and word
    problems, generated inside their shape (stem and key from one expression
    tree; free quantities drawn, the rest solved for);
  * ``part2_proofs.py`` — the twelve geometry proofs of 2015–2026, each a pool
    of claims from which a paper asks three or four.

Why transcribed and not invented: a Part 2 item is marked on intermediate
results, it is graded by a person or the model rather than a key comparison,
and a flawed proof wastes twenty minutes and teaches a false method.

Every item declares its own sub-part points; the sum must equal the blueprint
slot total (12 / 11 / 12), which ``verify`` enforces.
"""
from __future__ import annotations

import functools
import random
from dataclasses import dataclass
from typing import Callable, Sequence

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.registry import GeneratedItem, Retry


@dataclass(frozen=True)
class Part2Item:
    code: str
    topic: str
    stem: str
    parts: tuple[str, ...]
    points: tuple[int, ...]
    answers: tuple[str, ...]
    marking: str
    scene: dict | None = None
    difficulty: str = "hard"

    def to_generated(self, slot: Slot) -> GeneratedItem:
        return GeneratedItem(
            topic=slot.topic, kind="open", points=self.points,
            stem=self.stem, parts=list(self.parts),
            correct_answer=list(self.answers),
            scene=self.scene, difficulty=self.difficulty,
            solution=self.marking, signature=f"p2:{self.code}",
            template_code=self.code,
        )


Builder = Callable[[random.Random], Part2Item]
_BANK: dict[str, list[Builder]] = {
    "open_algebra": [],
    "open_word_problem": [],
    "open_geometry_proof": [],
}
#: Band per builder, keyed by the function object. No item here is banded
#: "easy" — a twelve-point proof never is — so the levels choose between
#: "medium" (the most tractable item of its topic) and "hard" (the gnarliest).
_BANDS: dict[Builder, str] = {}


#: How often a builder may reject its own draw before the bank gives up on it.
#: Builders solve for their derived quantities and raise ``Retry`` when a draw
#: does not close; callers — the assembler, the capacity script, the tests —
#: call a builder directly, so the retry lives here rather than in each of them.
_BUILD_ATTEMPTS = 60


def part2(topic: str, *, band: str = "hard") -> Callable[[Builder], Builder]:
    def decorate(fn: Builder) -> Builder:
        @functools.wraps(fn)
        def build(rng: random.Random) -> Part2Item:
            for _ in range(_BUILD_ATTEMPTS - 1):
                try:
                    return fn(rng)
                except Retry:
                    continue
            return fn(rng)
        _BANK[topic].append(build)
        _BANDS[build] = band
        return build
    return decorate


def bank_for(topic: str) -> tuple[Builder, ...]:
    return tuple(_BANK.get(topic, ()))


def band_of(builder: Builder) -> str:
    return _BANDS.get(builder, "hard")


# ═══════════════════════════════════════════════════════════════════════════
# OPEN ALGEBRA — 12 points, and OPEN WORD PROBLEM — 11 points
# ═══════════════════════════════════════════════════════════════════════════
# These live in part2_algebra.py and part2_word.py, which register into this
# bank when imported at the bottom of this module.


# ═══════════════════════════════════════════════════════════════════════════
# OPEN GEOMETRY PROOF — 12 points
# ═══════════════════════════════════════════════════════════════════════════
# part2_proofs.py: twelve real configurations, each a pool of claims.


def sample_part2(topic: str, rng: random.Random, slot: Slot,
                 *, exclude: Sequence[str] = ()) -> GeneratedItem:
    """Draw one curated item for `topic`, avoiding codes already on the paper.

    The slot's difficulty profile biases *which* of the topic's items is
    reached, the same way it biases Part 1 template choice — a gentler level
    tends toward the more tractable shape. It is only a bias: every shape stays
    reachable at every level.
    """
    builders = list(bank_for(topic))
    if not builders:
        raise LookupError(f"no curated Part 2 items for topic {topic!r}")
    _shuffle_by_band(builders, slot, rng)
    first: Part2Item | None = None
    for build in builders:
        item = build(rng)
        first = first or item
        if item.code not in exclude:
            return item.to_generated(slot)
    assert first is not None
    return first.to_generated(slot)


def _shuffle_by_band(builders: list[Builder], slot: Slot, rng: random.Random) -> None:
    """Shuffle in place, weighting each builder by its band at this difficulty."""
    weighted = sorted(
        builders,
        key=lambda b: rng.random() ** (1.0 / max(slot.profile.weight_for(band_of(b)), 1e-6)),
        reverse=True,
    )
    builders[:] = weighted


# Registers the algebra, word-problem and geometry-proof shapes into _BANK.
from app.nvo_gen import part2_algebra, part2_proofs, part2_word  # noqa: E402,F401
