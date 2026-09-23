"""What a generated item is, and which templates may fill which slot.

The unit an author writes is an **item template**, not a question: a parameter
space plus the functions that turn one sample of it into a stem, a key,
distractors and a figure. The same template can therefore fill position 11 of a
2026 paper and position 13 of a classic one — the blueprint decides where, the
template decides what.

Registering is a decorator:

    @template("incentre_angle", topics=["geom_bisectors_incentre",
                                        "geom_triangle_cevians"])
    def build_incentre_angle(rng, slot):
        ...
        return GeneratedItem(...)

A template may raise ``Retry`` when its sample turns out unusable (a degenerate
triangle, a non-integer answer). The assembler resamples it a few times and only
then moves to another template, so a rare bad draw costs nothing.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from app.nvo_gen.blueprints import Slot
from app.nvo_gen.difficulty import BANDS


class Retry(Exception):
    """This parameter draw is unusable — sample again.

    ``distractors.DistractorError`` subclasses this: a draw that cannot yield
    four plausible options is a bad draw, not a broken template, and should
    cost a resample rather than fail the paper.
    """


@dataclass
class GeneratedItem:
    """One finished question, ready to be numbered into a paper."""

    topic: str
    kind: str                                   # "mc" | "short" | "open"
    stem: str                                   # Bulgarian; math inside $...$
    points: tuple[int, ...]
    #: Rendered option strings, in display order. None for short/open items.
    options: list[str] | None = None
    #: "А".."Г" for multiple choice; the answer text for a short item; one
    #: entry per sub-part for a multi-part item.
    correct_answer: str | list[str] = ""
    #: Sub-part prompts ("А) Намерете…"), one per entry in `points` when >1.
    parts: list[str] | None = None
    scene: dict[str, Any] | None = None
    difficulty: str = "medium"
    #: A short worked answer shown in review. Not the full marking scheme —
    #: Part 2 items carry that separately.
    solution: str | None = None
    #: Identifies the *shape* of this item so the assembler can refuse two
    #: items built from the same template, and the near-duplicate check can
    #: spot the same numbers coming round twice.
    signature: str = ""
    template_code: str = ""

    @property
    def total_points(self) -> int:
        return sum(self.points)


BuildFn = Callable[[random.Random, Slot], GeneratedItem]


@dataclass(frozen=True)
class ItemTemplate:
    code: str
    topics: frozenset[str]
    kinds: frozenset[str]
    build: BuildFn = field(repr=False)
    #: Relative weight when several templates fit one slot. Raise it for the
    #: shapes that appear in most real papers, lower it for the rarities.
    weight: float = 1.0
    #: How hard this *shape* is, independent of the numbers it is given —
    #: "easy" for a one-step read-off, "hard" for a multi-step chase. The
    #: difficulty profile re-weights the bands when a slot has several
    #: candidates, which is how a level changes the character of a paper
    #: without changing its structure. See ``nvo_gen.difficulty``.
    band: str = "medium"

    def fits(self, slot: Slot) -> bool:
        return slot.topic in self.topics and slot.kind in self.kinds

    def weight_at(self, slot: Slot) -> float:
        """This template's selection weight at the slot's difficulty."""
        return max(self.weight * slot.profile.weight_for(self.band), 1e-6)


_REGISTRY: dict[str, ItemTemplate] = {}


def template(
    code: str,
    *,
    topics: Sequence[str],
    kinds: Sequence[str] = ("mc",),
    weight: float = 1.0,
    band: str = "medium",
) -> Callable[[BuildFn], BuildFn]:
    def decorate(fn: BuildFn) -> BuildFn:
        if code in _REGISTRY:
            raise ValueError(f"duplicate item template code: {code}")
        if band not in BANDS:
            raise ValueError(f"{code}: band must be one of {BANDS}, got {band!r}")
        _REGISTRY[code] = ItemTemplate(
            code=code,
            topics=frozenset(topics),
            kinds=frozenset(kinds),
            build=fn,
            weight=weight,
            band=band,
        )
        return fn

    return decorate


def all_templates() -> tuple[ItemTemplate, ...]:
    _ensure_loaded()
    return tuple(_REGISTRY.values())


def templates_for(slot: Slot) -> tuple[ItemTemplate, ...]:
    _ensure_loaded()
    return tuple(t for t in _REGISTRY.values() if t.fits(slot))


def get_template(code: str) -> ItemTemplate:
    _ensure_loaded()
    return _REGISTRY[code]


_loaded = False


def _ensure_loaded() -> None:
    """Import the template modules once, on first use.

    Deferred rather than imported at package top level so that
    ``app.nvo_gen.blueprints`` stays importable on its own — the router reads
    blueprint metadata on paths that never generate anything.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True
    from app.nvo_gen.templates import (  # noqa: F401  (import for side effects)
        algebra,
        corpus,
        data,
        geometry,
        numbers,
        wordproblems,
    )


def coverage_report(blueprint_slots: Iterable[Slot]) -> dict[str, int]:
    """How many templates can fill each slot — 0 means the paper cannot build.

    Used by the test suite to guarantee every position of every blueprint has
    somewhere to draw from before anything ships.
    """
    _ensure_loaded()
    return {f"{s.position}:{s.topic}": len(templates_for(s)) for s in blueprint_slots}
