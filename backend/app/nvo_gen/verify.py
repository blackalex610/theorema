"""The gate every item and every paper has to clear.

Nothing reaches a student that has not passed through here. The checks are
split in two because the failures are different in kind:

  * ``check_item`` catches a template producing something malformed — four
    options that are not four, a key that is not one of them, a figure that
    references a point it never placed. These are bugs, and they fail loudly.
  * ``check_paper`` catches an *assembly* that is individually fine but
    collectively wrong — the same template twice, every answer on Б, a points
    total that is not 65.

Two checks look pedantic and are not:

*Latin letters in the option key.* A Latin "B" beside a Cyrillic "В" is the
single most common way a generated Bulgarian paper gives itself away, and it
silently breaks answer comparison at grading time.

*Cyrillic inside ``$…$``.* The router's ``_normalize_math_delimiters`` strips
Cyrillic out of math spans to work around KaTeX noglyph boxes. A stem that puts
Bulgarian inside the math therefore arrives at the student with words missing.
The fix is to never write it, so it is an error here rather than a surprise
there.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.nvo_gen.blueprints import Blueprint, Slot
from app.nvo_gen.distractors import OPTION_LETTERS
from app.nvo_gen.registry import GeneratedItem
from app.nvo_gen.scene import SCENE_KINDS, SCHEMATIC_SHAPES, SOLID_SHAPES

_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_MATH_SPAN = re.compile(r"\$([^$]*)\$")
#: Unfilled-template markers. Deliberately NOT `\{\w*\}` — LaTeX is full of
#: legitimate braces (`\frac{1}{5}`, `x^{2}`), so that pattern flags every
#: correct stem. Empty braces, on the other hand, are neither valid LaTeX nor
#: anything a template means to emit.
_PLACEHOLDER = re.compile(r"\{\s*\}|\bTODO\b|\bFIXME\b|\bNone\b|\bnan\b")
_LATIN_OPTION = re.compile(r"^[ABCD]$")


class VerificationError(ValueError):
    """An item or a paper failed a check it must not fail."""


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def merge(self, other: "Report") -> "Report":
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self

    def raise_if_failed(self, context: str) -> None:
        if self.errors:
            raise VerificationError(f"{context}: " + "; ".join(self.errors))


# ─── item-level ──────────────────────────────────────────────────────────────

def check_item(item: GeneratedItem, slot: Slot) -> Report:
    r = Report()

    if item.kind != slot.kind:
        r.errors.append(f"kind {item.kind!r} does not match slot kind {slot.kind!r}")
    if item.total_points != slot.total_points:
        r.errors.append(
            f"points {item.points} sum to {item.total_points}, slot wants {slot.total_points}")

    _check_text(item.stem, "stem", r)
    if not _CYRILLIC.search(item.stem):
        r.errors.append("stem contains no Cyrillic — an NVO stem is written in Bulgarian")

    if item.kind == "mc":
        _check_multiple_choice(item, r)
    else:
        _check_written(item, slot, r)

    _check_parts(item, slot, r)
    _check_scene(item, slot, r)
    return r


def _check_text(text: str, label: str, r: Report) -> None:
    if not text or not text.strip():
        r.errors.append(f"{label} is empty")
        return
    if text.count("$") % 2:
        r.errors.append(f"{label} has an unbalanced math delimiter")
    if _PLACEHOLDER.search(text):
        r.errors.append(f"{label} still contains a placeholder: {_PLACEHOLDER.search(text).group()!r}")
    for span in _MATH_SPAN.findall(text):
        if _CYRILLIC.search(span):
            r.errors.append(
                f"{label} has Cyrillic inside a math span (\"{span[:40]}\") — it will be "
                f"stripped before the student sees it")


def _check_multiple_choice(item: GeneratedItem, r: Report) -> None:
    options = item.options or []
    if len(options) != 4:
        r.errors.append(f"expected 4 options, got {len(options)}")
        return
    for i, opt in enumerate(options):
        _check_text(opt, f"option {OPTION_LETTERS[i] if i < 4 else i}", r)
    if len(set(options)) != len(options):
        dupes = [o for o, n in Counter(options).items() if n > 1]
        r.errors.append(f"duplicate options: {dupes}")

    key = item.correct_answer
    if not isinstance(key, str):
        r.errors.append(f"multiple-choice key must be a letter, got {type(key).__name__}")
        return
    if _LATIN_OPTION.match(key):
        r.errors.append(f"key {key!r} is a Latin letter — NVO options are Cyrillic А/Б/В/Г")
    elif key not in OPTION_LETTERS:
        r.errors.append(f"key {key!r} is not one of {OPTION_LETTERS}")


def _check_written(item: GeneratedItem, slot: Slot, r: Report) -> None:
    if item.options:
        r.errors.append(f"{item.kind} item must not carry options")
    answers = item.correct_answer
    if slot.parts > 1:
        if not isinstance(answers, list):
            r.errors.append(f"{slot.parts}-part item needs a list of answers")
        elif len(answers) != slot.parts:
            r.errors.append(f"expected {slot.parts} answers, got {len(answers)}")
    elif isinstance(answers, list):
        if not answers:
            r.errors.append("answer list is empty")
    elif not str(answers).strip():
        r.errors.append("answer is empty")


def _check_parts(item: GeneratedItem, slot: Slot, r: Report) -> None:
    if slot.parts > 1:
        if not item.parts:
            r.errors.append(f"slot has {slot.parts} parts but the item declares none")
        elif len(item.parts) != slot.parts:
            r.errors.append(f"item declares {len(item.parts)} parts, slot wants {slot.parts}")
        else:
            for i, part in enumerate(item.parts):
                _check_text(part, f"part {i + 1}", r)
    elif item.parts and item.kind != "open":
        r.errors.append("single-part slot must not declare sub-parts")


def _check_scene(item: GeneratedItem, slot: Slot, r: Report) -> None:
    if slot.diagram and item.scene is None:
        r.errors.append("slot expects a figure but the item produced none")
    if item.scene is None:
        return

    kind = item.scene.get("kind")
    if kind not in SCENE_KINDS:
        r.errors.append(f"unknown scene kind {kind!r}")
        return
    if not item.scene.get("aria"):
        r.warnings.append("figure has no aria description")

    if kind == "solid" and item.scene.get("shape") not in SOLID_SHAPES:
        r.errors.append(f"unknown solid shape {item.scene.get('shape')!r}")
    if kind == "schematic" and item.scene.get("shape") not in SCHEMATIC_SHAPES:
        r.errors.append(f"unknown schematic shape {item.scene.get('shape')!r}")
    _check_scene_text_is_plain(item.scene, r)
    if kind == "figure":
        _check_figure(item.scene, r)
    if kind == "bars":
        _check_bars(item.scene, r)


def _check_scene_text_is_plain(scene: dict, r: Report) -> None:
    """Scene labels are drawn as SVG <text>, so LaTeX in them renders literally.

    A label written as "$12$" shows the dollar signs to the student. The table
    scene is the exception — its cells go through the normal text renderer, so
    math markup there is correct.
    """
    if scene.get("kind") == "table":
        return

    suspect: list[str] = [t.get("text", "") for t in scene.get("texts", [])]
    suspect += [str(a.get("label") or "") for a in scene.get("angles", [])]
    suspect += [str(ln.get("label") or "") for ln in scene.get("lines", [])]
    suspect += [str(v) for v in (scene.get("labels") or {}).values()]

    for text in suspect:
        if "$" in text or "\\frac" in text or "\\sphericalangle" in text:
            r.errors.append(f"figure label {text!r} contains markup that will render literally")


def _check_figure(scene: dict, r: Report) -> None:
    """Every mark must reference a point the figure actually placed."""
    names = set(scene.get("points", {}))
    if not names:
        r.errors.append("figure has no points")
        return

    def ref(value: str | None, where: str) -> None:
        if value is not None and value not in names:
            r.errors.append(f"{where} references undefined point {value!r}")

    for seg in scene.get("segments", []):
        ref(seg.get("from"), "segment"); ref(seg.get("to"), "segment")
    for ray in scene.get("rays", []):
        ref(ray.get("from"), "ray"); ref(ray.get("to"), "ray")
    for line in scene.get("lines", []):
        ref(line.get("from"), "line"); ref(line.get("to"), "line")
    for ang in scene.get("angles", []):
        for k in ("at", "from", "to"):
            ref(ang.get(k), "angle")
    for ang in scene.get("rightAngles", []):
        for k in ("at", "from", "to"):
            ref(ang.get(k), "right angle")
    for tick in scene.get("ticks", []):
        ref(tick.get("from"), "tick"); ref(tick.get("to"), "tick")

    width = scene.get("width", 0)
    height = scene.get("height", 0)
    for name, (x, y) in scene.get("points", {}).items():
        if not (-40 <= x <= width + 40 and -40 <= y <= height + 40):
            r.warnings.append(f"point {name} at ({x}, {y}) sits far outside the {width}×{height} box")


def _check_bars(scene: dict, r: Report) -> None:
    cats = scene.get("categories", [])
    for series in scene.get("series", []):
        if len(series.get("values", [])) != len(cats):
            r.errors.append(
                f"series {series.get('name')!r} has {len(series.get('values', []))} values "
                f"for {len(cats)} categories")
    y_max = scene.get("yMax", 0)
    for series in scene.get("series", []):
        for v in series.get("values", []):
            if v > y_max:
                r.errors.append(f"bar value {v} exceeds the axis maximum {y_max}")


# ─── paper-level ─────────────────────────────────────────────────────────────

#: How far the А/Б/В/Г counts may drift from uniform before we rebalance.
#: 2022 shipped 8 of 18 on Б, which is the kind of thing a student notices.
LETTER_TOLERANCE = 2


def check_paper(items: Sequence[GeneratedItem], slots: Sequence[Slot],
                blueprint: Blueprint | None = None) -> Report:
    r = Report()

    if len(items) != len(slots):
        r.errors.append(f"{len(items)} items for {len(slots)} slots")
        return r

    for item, slot in zip(items, slots):
        r.merge(check_item(item, slot))

    total = sum(i.total_points for i in items)
    expected = sum(s.total_points for s in slots)
    if total != expected:
        r.errors.append(f"paper totals {total} points, slots want {expected}")

    codes = [i.template_code for i in items if i.template_code]
    repeated = [c for c, n in Counter(codes).items() if n > 1]
    if repeated:
        r.errors.append(f"template used more than once: {repeated}")

    sigs = [i.signature for i in items if i.signature]
    dup_sigs = [s for s, n in Counter(sigs).items() if n > 1]
    if dup_sigs:
        r.errors.append(f"identical parameter draw appears twice: {dup_sigs}")

    stems = [i.stem for i in items]
    dup_stems = [s for s, n in Counter(stems).items() if n > 1]
    if dup_stems:
        r.errors.append(f"identical stem appears twice: {[s[:50] for s in dup_stems]}")

    r.merge(check_letter_balance(items))

    if blueprint is not None and len(slots) == len(blueprint.slots):
        if sum(i.total_points for i, s in zip(items, slots) if s.section == "part1") != 65:
            r.errors.append("Part 1 must total exactly 65 points")
        if sum(i.total_points for i, s in zip(items, slots) if s.section == "part2") != 35:
            r.errors.append("Part 2 must total exactly 35 points")

    return r


def check_letter_balance(items: Iterable[GeneratedItem]) -> Report:
    r = Report()
    letters = [i.correct_answer for i in items
               if i.kind == "mc" and isinstance(i.correct_answer, str)]
    if len(letters) < 8:
        return r
    counts = Counter(letters)
    target = len(letters) / 4
    for letter in OPTION_LETTERS:
        drift = abs(counts.get(letter, 0) - target)
        if drift > LETTER_TOLERANCE + 0.75:
            r.warnings.append(
                f"answer letter {letter} appears {counts.get(letter, 0)} times "
                f"against a target of {target:.1f}")
    return r


def letter_histogram(items: Iterable[GeneratedItem]) -> dict[str, int]:
    counts = Counter(i.correct_answer for i in items
                     if i.kind == "mc" and isinstance(i.correct_answer, str))
    return {letter: counts.get(letter, 0) for letter in OPTION_LETTERS}
