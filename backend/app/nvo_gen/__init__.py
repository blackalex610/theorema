"""Blueprint-driven NVO exam generation.

The old path (``app.routers.nvo._fallback_generate_from_pool``) hard-coded a
23-slot exam and drew each slot from a fixed pool of ~5 transcribed official
variants. That caps the product at 5^23 *visibly repeating* papers and cannot
express the 2026 format at all, which is 24 slots — 14 multiple choice, a
reinstated 7-item short-answer block, and 3 extended items.

This package replaces the pool with *item templates*: a parameter space plus
the functions that turn one sample of it into a stem, a key, distractors and a
figure. A blueprint says what belongs at each position; the assembler samples a
template per slot and the verifier refuses anything that does not hold up.

Layout:
  blueprints.py  — the two exam shapes, as data
  scene.py       — declarative figure spec + the builders that emit one
  distractors.py — the eight wrong-answer families found in the real papers
  templates/     — item templates, grouped by strand
  registry.py    — which templates may fill which slot
  part2_bank.py  — curated extended items (not generated)
  verify.py      — the gate every item and every paper must clear
  assemble.py    — the generation loop
"""
from app.nvo_gen.blueprints import BLUEPRINTS, Blueprint, Slot, get_blueprint

__all__ = ["BLUEPRINTS", "Blueprint", "Slot", "get_blueprint"]
