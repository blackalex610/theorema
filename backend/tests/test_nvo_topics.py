"""The canonical topic taxonomy, and the two vocabularies it has to cover.

Diagnostics aggregate on `topic_key`. If a raw topic from either generator
fails to resolve, its questions land in `other` and simply vanish from the
teacher's heatmap — silently, with the suite still green. These tests are the
guard: add a slot to a blueprint or the catalog without giving it a label and
the suite fails here rather than in a classroom.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import nvo_topics


def _catalog_topics() -> set[str]:
    path = Path(__file__).resolve().parent.parent / "nvo_question_catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    topics = set(catalog["slot_topics"].values())
    for slot in catalog["slots"].values():
        if slot.get("topic"):
            topics.add(slot["topic"])
    return topics


def _blueprint_topics() -> set[str]:
    """Every `topic` on every Slot the blueprints module exposes.

    Walked rather than hard-coded on purpose: a new blueprint added later is
    then covered by this test without anyone remembering to update it.
    """
    from app.nvo_gen import blueprints

    topics: set[str] = set()
    for name in dir(blueprints):
        value = getattr(blueprints, name)
        if isinstance(value, (str, bytes)):
            continue
        slots = getattr(value, "slots", None)
        if slots is None and isinstance(value, (list, tuple)):
            slots = value
        for slot in slots or []:
            topic = getattr(slot, "topic", None)
            if isinstance(topic, str) and topic:
                topics.add(topic)
    return topics


def test_every_catalog_slot_topic_resolves_to_a_real_key():
    unresolved = sorted(t for t in _catalog_topics() if nvo_topics.resolve(t) == nvo_topics.OTHER)
    assert unresolved == [], f"catalog topics with no canonical mapping: {unresolved}"


def test_every_blueprint_slot_topic_resolves_to_a_real_key():
    found = _blueprint_topics()
    assert found, "no blueprint slot topics discovered — the walker is broken, not the taxonomy"
    unresolved = sorted(t for t in found if nvo_topics.resolve(t) == nvo_topics.OTHER)
    assert unresolved == [], f"blueprint topics with no canonical mapping: {unresolved}"


def test_unknown_topic_resolves_to_other():
    assert nvo_topics.resolve("something_the_llm_invented") == nvo_topics.OTHER
    assert nvo_topics.resolve("") == nvo_topics.OTHER
    assert nvo_topics.resolve(None) == nvo_topics.OTHER


def test_resolution_is_insensitive_to_case_and_spacing():
    assert nvo_topics.resolve("  Linear_Equation  ") == nvo_topics.resolve("linear_equation")
    assert nvo_topics.resolve("linear equation") == nvo_topics.resolve("linear_equation")


@pytest.mark.parametrize("key", sorted(nvo_topics.TOPICS))
def test_every_topic_has_a_bulgarian_label_and_a_known_strand(key):
    topic = nvo_topics.TOPICS[key]
    assert topic.label_bg.strip(), f"{key} has no Bulgarian label"
    assert any(ch.isalpha() and ord(ch) > 127 for ch in topic.label_bg), (
        f"{key} label '{topic.label_bg}' is not Bulgarian — teachers read this screen"
    )
    assert topic.strand in nvo_topics.STRANDS, f"{key} sits in unknown strand {topic.strand}"


def test_other_is_not_itself_a_reportable_topic():
    """`other` is a catch-all, so it must never be offered as a weakness to work on."""
    assert nvo_topics.OTHER not in nvo_topics.TOPICS
    assert nvo_topics.label(nvo_topics.OTHER).strip()
