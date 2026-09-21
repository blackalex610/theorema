"""The generation loop: blueprint in, verified paper out.

For each slot the assembler picks a template that fits, samples it, and runs the
item through ``verify.check_item``. A template may reject its own draw (Retry),
and the verifier may reject the result; either way the assembler resamples a few
times and then moves on to a different template. Only if every eligible template
fails does a slot fail, which in practice means a coverage bug and should be
loud.

Two things happen after every slot is filled:

*Answer letters are rebalanced.* Per-item randomness alone drifts — the 2022
paper shipped 8 of 18 keys on Б. Rebalancing moves a key to a different position
within its own option list, which changes nothing about the item and everything
about how the paper reads.

*The paper is verified as a whole.* Points must total what the blueprint says,
no template may appear twice, no two items may share a parameter draw.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Sequence

from app.nvo_gen import part2_bank
from app.nvo_gen.blueprints import (
    SCALE_NOTICE_BG,
    Blueprint,
    Slot,
    get_blueprint,
    short_form,
    with_profile,
)
from app.nvo_gen.difficulty import ACTUAL, DifficultyProfile, get_profile
from app.nvo_gen.distractors import OPTION_LETTERS, reletter
from app.nvo_gen.registry import GeneratedItem, ItemTemplate, Retry, templates_for
from app.nvo_gen.verify import Report, check_item, check_paper, letter_histogram

#: How many times one template may resample before we try a different template.
#: Generous on purpose — a template whose parameter space is mostly invalid
#: draws (angle ratios that must divide 180° exactly, say) is common, and a
#: resample costs microseconds while failing the slot costs the whole paper.
SAMPLES_PER_TEMPLATE = 24


class AssemblyError(RuntimeError):
    """No template could fill a slot."""


@dataclass
class Paper:
    exam_id: str
    blueprint: Blueprint
    slots: tuple[Slot, ...]
    items: list[GeneratedItem]
    report: Report
    seed: int | None = None
    #: Position at which the "not to scale" notice prints, or None when the
    #: paper has no geometry block (a very short practice form).
    scale_notice_before: int | None = None
    #: The level this paper was generated at. ``ACTUAL`` reproduces the real
    #: exam; the others are the same format with different numbers, different
    #: template choices and a different clock.
    profile: DifficultyProfile = ACTUAL

    @property
    def total_points(self) -> int:
        return sum(i.total_points for i in self.items)

    @property
    def part1_minutes(self) -> int:
        return self.profile.minutes(self.blueprint.part1_minutes)

    @property
    def part2_minutes(self) -> int:
        return self.profile.minutes(self.blueprint.part2_minutes)

    def numbered(self) -> list[tuple[int, GeneratedItem, Slot]]:
        return [(i + 1, item, slot)
                for i, (item, slot) in enumerate(zip(self.items, self.slots))]


def generate_paper(
    blueprint_code: str | None = None,
    *,
    seed: int | None = None,
    short: bool = False,
    difficulty: str | None = None,
    rng: random.Random | None = None,
) -> Paper:
    """Build one complete paper for the given blueprint and difficulty.

    ``difficulty`` never changes the shape of the paper — same positions, same
    topics, same points. It re-weights which template fills each position and
    is handed to the templates so they can size their own numbers. See
    ``nvo_gen.difficulty``; an unknown or missing value means the real exam.
    """
    blueprint = get_blueprint(blueprint_code)
    profile = get_profile(difficulty)
    rng = rng or random.Random(seed)
    slots = with_profile(short_form(blueprint) if short else blueprint.slots, profile)

    used_codes: set[str] = set()
    used_signatures: set[str] = set()
    filled: dict[int, GeneratedItem] = {}

    # Fill the scarcest slots first. Several templates fit more than one topic
    # — `incentre_angle` serves both geom_triangle_cevians and
    # geom_bisectors_incentre — and a slot with five alternatives will happily
    # take the only template a later slot could have used. Claiming in
    # scarcity order removes that collision without any special-casing.
    for slot in sorted(slots, key=lambda s: (_option_count(s), s.position)):
        item = (_fill_open_slot(slot, rng, used_signatures)
                if slot.kind == "open"
                else _fill_slot(slot, rng, used_codes, used_signatures))
        filled[slot.position] = item
        if item.template_code:
            used_codes.add(item.template_code)
        if item.signature:
            used_signatures.add(item.signature)

    items: list[GeneratedItem] = [filled[s.position] for s in slots]

    _rebalance_letters(items, rng)

    report = check_paper(items, slots, blueprint if not short else None)
    notice_at = _scale_notice_position(slots)

    return Paper(
        exam_id=uuid.uuid4().hex[:8],
        blueprint=blueprint,
        slots=tuple(slots),
        items=items,
        report=report,
        seed=seed,
        scale_notice_before=notice_at,
        profile=profile,
    )


def _option_count(slot: Slot) -> int:
    """How many templates could fill this slot. Open slots draw from the bank."""
    if slot.kind == "open":
        return len(part2_bank.bank_for(slot.topic))
    return len(templates_for(slot))


def _fill_slot(slot: Slot, rng: random.Random, used_codes: set[str],
               used_signatures: set[str]) -> GeneratedItem:
    candidates = [t for t in templates_for(slot) if t.code not in used_codes]
    if not candidates:
        # Every fitting template is already on the paper. Allowing a repeat is
        # better than failing the whole paper, and the paper check downgrades
        # to a warning for short forms where slots outnumber templates.
        candidates = list(templates_for(slot))
    if not candidates:
        raise AssemblyError(
            f"no item template registered for slot {slot.position} ({slot.topic}/{slot.kind})")

    for tmpl in _weighted_order(candidates, slot, rng):
        item = _try_template(tmpl, slot, rng, used_signatures)
        if item is not None:
            return item

    raise AssemblyError(
        f"every template for slot {slot.position} ({slot.topic}) failed to produce "
        f"a valid item after {SAMPLES_PER_TEMPLATE} draws each")


def _try_template(tmpl: ItemTemplate, slot: Slot, rng: random.Random,
                  used_signatures: set[str]) -> GeneratedItem | None:
    for _ in range(SAMPLES_PER_TEMPLATE):
        try:
            item = tmpl.build(rng, slot)
        except Retry:
            continue
        except Exception as exc:  # a template bug, not a bad draw
            raise AssemblyError(f"template {tmpl.code!r} raised: {exc!r}") from exc

        if item.signature and item.signature in used_signatures:
            continue
        item.template_code = item.template_code or tmpl.code
        if check_item(item, slot).ok:
            return item
    return None


def _weighted_order(templates: Sequence[ItemTemplate], slot: Slot,
                    rng: random.Random) -> list[ItemTemplate]:
    """Shuffle templates so heavier ones tend to come first.

    Weight reflects how often a shape appears in the real papers, so a
    generated paper leans on the common shapes the way an official one does
    without ever being unable to reach the rarer ones.

    The slot's difficulty profile scales that weight by the template's band —
    which is the whole of how a level changes the character of a paper. At
    "actual" every band multiplier is 1.0, so the order here is exactly the
    order the real-paper weights alone produce. At the other levels a band is
    only made *rare*, never impossible: a slot whose every template is hard
    must still be fillable at "easy".
    """
    pool = list(templates)
    ordered: list[ItemTemplate] = []
    while pool:
        total = sum(t.weight_at(slot) for t in pool)
        pick = rng.uniform(0, total)
        run = 0.0
        for t in pool:
            run += t.weight_at(slot)
            if run >= pick:
                ordered.append(t)
                pool.remove(t)
                break
        else:
            ordered.append(pool.pop())
    return ordered


def _fill_open_slot(slot: Slot, rng: random.Random,
                    used_signatures: set[str]) -> GeneratedItem:
    exclude = {s.removeprefix("p2:") for s in used_signatures if s.startswith("p2:")}
    item = part2_bank.sample_part2(slot.topic, rng, slot, exclude=sorted(exclude))
    report = check_item(item, slot)
    if not report.ok:
        raise AssemblyError(
            f"curated Part 2 item {item.template_code!r} failed verification: "
            + "; ".join(report.errors))
    return item


def _rebalance_letters(items: list[GeneratedItem], rng: random.Random) -> None:
    """Even out А/Б/В/Г by moving keys within their own option lists.

    Repeatedly takes the most over-used letter and the least used one and moves
    one key from the former to the latter. Stops when the spread is at most one,
    or when no further move helps.
    """
    mc = [i for i in items if i.kind == "mc" and isinstance(i.correct_answer, str)]
    if len(mc) < 4:
        return

    for _ in range(len(mc) * 2):
        hist = letter_histogram(mc)
        most = max(hist, key=lambda k: hist[k])
        least = min(hist, key=lambda k: hist[k])
        if hist[most] - hist[least] <= 1:
            return

        movable = [i for i in mc if i.correct_answer == most]
        if not movable:
            return
        item = rng.choice(movable)
        current = OPTION_LETTERS.index(most)
        target = OPTION_LETTERS.index(least)
        options, letter = reletter(item.options or [], current, target)
        item.options = options
        item.correct_answer = letter


def _scale_notice_position(slots: Sequence[Slot]) -> int | None:
    """Where „Чертежите са само за илюстрация…” prints.

    Immediately before the first geometry item of the multiple-choice block —
    which is exactly where the official papers put it from 2019 on.
    """
    for i, slot in enumerate(slots):
        if slot.kind == "mc" and slot.topic.startswith("geom_"):
            return i + 1
    return None


def scale_notice() -> str:
    return SCALE_NOTICE_BG
