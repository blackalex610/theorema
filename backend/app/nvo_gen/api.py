"""Translate a generated Paper into the shape the exam client already speaks.

The client contract predates this package, so the conversion here adapts to it
rather than the other way round:

  * options arrive prefixed with their Cyrillic letter ("А) $0$"); the client
    strips the prefix and re-sorts;
  * a multi-part item puts its sub-parts *in the question text*, one per line,
    and lists only the letters in ``open_parts`` — the client strips those
    lines back out of the text when it renders the parts separately;
  * figures ride along as ``diagram_type: "scene"`` with the scene spec in
    ``diagram_config``, which ``renderNvoDiagram`` routes to ``SceneRenderer``.
    The hand-written diagram components keep working for anything the old
    catalog generator still produces.

``part1_count`` is new and matters: the client used to infer the module from
``number <= 20``, which is right for a 2024/2025 paper and wrong for a 2026 one,
where Part 1 runs to 21.
"""
from __future__ import annotations

from typing import Any

from app.nvo_gen.assemble import Paper
from app.nvo_gen.blueprints import SCALE_NOTICE_BG
from app.nvo_gen.distractors import OPTION_LETTERS
from app.nvo_gen.registry import GeneratedItem

#: Sub-part labels, in order. Cyrillic to match the printed papers.
PART_LETTERS = ("А", "Б", "В", "Г", "Д")


def question_payload(number: int, item: GeneratedItem, topic: str) -> dict[str, Any]:
    """One question in the client's NVOQuestion shape."""
    text = item.stem
    open_parts: list[str] | None = None

    if item.parts:
        # Part prompts already carry their own "А)" prefix where the template
        # wrote one; add it where it didn't, so the client's strip regex fires.
        lines = []
        for i, part in enumerate(item.parts):
            letter = PART_LETTERS[i] if i < len(PART_LETTERS) else str(i + 1)
            lines.append(part if part.lstrip().startswith(f"{letter})") else f"{letter}) {part}")
        text = item.stem + "\n" + "\n".join(lines)
        open_parts = [PART_LETTERS[i] for i in range(len(item.parts))]

    options = None
    if item.kind == "mc" and item.options:
        options = [f"{letter}) {opt}" for letter, opt in zip(OPTION_LETTERS, item.options)]

    return {
        "number": number,
        "question": text,
        "topic": topic,
        "difficulty": item.difficulty,
        "diagram": item.scene is not None,
        "diagram_type": "scene" if item.scene is not None else None,
        "diagram_config": item.scene,
        "open_parts": open_parts,
        "options": options,
        "correct_answer": item.correct_answer,
        # Extra context the client may use and older clients simply ignore.
        "points": list(item.points),
        "kind": item.kind,
    }


def exam_payload(paper: Paper, *, difficulty: str | None = None,
                 format_: str = "full") -> dict[str, Any]:
    """The full NVOExam payload for one generated paper.

    ``difficulty`` is reported as the paper's *resolved* level rather than
    whatever string the caller passed, so a client that posted the legacy
    ``"standard"`` gets back ``"actual"`` and stores that on the attempt. The
    minutes are the official allowance scaled by the level — the only place
    difficulty is visible in the paper's shape.
    """
    questions = [question_payload(n, item, slot.topic) for n, item, slot in paper.numbered()]
    part1 = [s for s in paper.slots if s.section == "part1"]
    del difficulty  # the paper's own profile is the authority

    return {
        "exam_id": paper.exam_id,
        "questions": questions,
        "difficulty": paper.profile.code,
        "difficulty_label": paper.profile.label_bg,
        "format": format_,
        "blueprint": paper.blueprint.code,
        "blueprint_label": paper.blueprint.label_bg,
        "part1_count": len(part1),
        "part1_minutes": paper.part1_minutes,
        "part2_minutes": paper.part2_minutes,
        "total_points": paper.total_points,
        # Printed inline immediately before the first geometry item, exactly as
        # the official papers do from 2019 on.
        "scale_notice_before": paper.scale_notice_before,
        "scale_notice": SCALE_NOTICE_BG,
    }


def difficulty_catalogue() -> list[dict[str, Any]]:
    """What the difficulty picker shows. Ordered easiest-first."""
    from app.nvo_gen.difficulty import catalogue

    return catalogue()


def blueprint_catalogue() -> list[dict[str, Any]]:
    """What the format picker shows. Ordered newest-first."""
    from app.nvo_gen.blueprints import BLUEPRINTS

    order = {"nvo2026": 0, "classic": 1}
    out = []
    for code, bp in sorted(BLUEPRINTS.items(), key=lambda kv: order.get(kv[0], 9)):
        out.append({
            "code": code,
            "label": bp.label_bg,
            "subtitle": bp.subtitle_bg,
            "years": bp.years_bg,
            "questionCount": len(bp.slots),
            "mcCount": len(bp.mc_slots),
            "shortCount": len(bp.short_slots),
            "openCount": len(bp.open_slots),
            "part1Minutes": bp.part1_minutes,
            "part2Minutes": bp.part2_minutes,
            "totalPoints": bp.total_points,
        })
    return out
