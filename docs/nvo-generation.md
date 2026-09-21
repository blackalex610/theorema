# NVO exam generation

How a practice paper is built, and how to add to it.

Everything here was derived from the thirteen official papers in `NVOS/`
(2015–2026) plus the Ministry's own post-2015 format memo, `tekst_nvo_bel_math.pdf`.

---

## Why this exists

The previous generator (`app.routers.nvo._fallback_generate_from_pool`) drew each
of 23 fixed slots from a pool of ~5 transcribed official variants. Two problems:

* **It repeats.** Five variants per slot is visibly finite — a student sitting a
  dozen papers sees the same questions.
* **It cannot express 2026.** The slot count and topics were hard-coded to the
  2024/2025 shape. The June 2026 paper is 24 slots, with a short-answer block
  that the 2024/2025 papers did not have at all.

The replacement generates from **item templates** — a parameter space plus the
functions that turn one sample of it into a stem, a key, distractors and a
figure — assembled against a **blueprint** that says what belongs at each
position.

---

## What is invariant (and is therefore asserted in tests)

Read off all thirteen papers:

| Fact | Since |
|---|---|
| Part 1 is worth exactly **65** points, Part 2 exactly **35** | 2015 |
| Four options, always Cyrillic **А Б В Г**, exactly one correct | 2015 |
| Part 1 runs an algebra/number/data block, then a contiguous geometry block | 2015 |
| „Чертежите са само за илюстрация…” prints inline at the geometry boundary | 2019 |
| Part 2 is three items: multi-part algebra, word problem, geometry proof | 2020 |
| Item weights ramp 2 → 3 → 4 across Part 1 | 2019 |

`Blueprint.validate()` enforces the point totals, contiguous positions,
contiguous geometry, and item-kind ordering at **import time**, so a malformed
blueprint fails on startup rather than mid-generation.

---

## The two blueprints

| | `classic` | `nvo2026` |
|---|---|---|
| Years | 2024, 2025 | 2026 |
| Part 1 | 75 min | 90 min |
| Multiple choice | 20 | 14 |
| Short answer | — | 7 (positions 15–21) |
| Extended | 3 (21–23) | 3 (22–24) |
| Slots | 23 | 24 |

Both total 100 points. A third era costs one entry in
`app/nvo_gen/blueprints.py` and nothing in the UI — the format picker reads
`GET /nvo/blueprints`.

---

## Pipeline

```
blueprint slot ─► eligible templates ─► sample params ─► stem + key + distractors + scene
                                              │                        │
                                              └── Retry on a bad draw   └─► verify.check_item
                                                                                  │
                        rebalance answer letters ◄── all slots filled ◄───────────┘
                                   │
                                   └─► verify.check_paper ─► Paper
```

Slots are filled **in order of scarcity**, not position order. Several templates
fit more than one topic (`incentre_angle` serves both `geom_triangle_cevians`
and `geom_bisectors_incentre`); a slot with five alternatives would otherwise
take the only template a later slot could have used.

---

## Adding an item template

One function, registered by decorator. It receives an `rng` and the `Slot` it is
filling, and returns a `GeneratedItem`.

```python
@template("incentre_angle",
          topics=["geom_bisectors_incentre", "geom_triangle_cevians"],
          kinds=["mc", "short"], weight=1.4, band="hard")
def incentre_angle(rng: random.Random, slot: Slot) -> GeneratedItem:
    gamma = rng.choice(slot.profile.tier([40, 60, 80],            # easy
                                         [40, 50, 60, 80],        # medium
                                         [30, 40, 50, 60, 70, 80],  # actual
                                         [34, 38, 46, 54, 62, 74])) # extra hard
    if gamma % 2:
        raise Retry("γ must be even so ∠AOB is whole")
    ...
```

Rules that are easy to get wrong:

* **Raise `Retry` for a bad draw**, never round. An angle chase that comes out
  at 63,5° is not an NVO item; a percentage that gives 17,333 minutes is not an
  answer any official key would print. Parameter spaces here are deliberately
  over-wide and narrowed by rejection.
* **Bulgarian prose outside `$…$`, maths inside.** The router's
  `_normalize_math_delimiters` strips Cyrillic out of math spans (a KaTeX
  noglyph workaround), so Bulgarian inside the maths silently loses words. The
  verifier rejects it.
* **Decimal comma, via `bg_number` / `bg_decimal`.** In maths mode the comma is
  written `{,}` so KaTeX sets it tight.
* **Check a decimal terminates with `is_clean_decimal`,** not
  `denominator <= 100` — 5/3 passes the latter and prints as 1,666…
* **Set a `signature`** so two items on one paper can't be the same draw.
* **Declare a `band`** — `"easy"`, `"medium"` or `"hard"`, describing how hard
  the *shape* is regardless of the numbers it gets. It is what the difficulty
  profile re-weights. Default is `"medium"`.
* **Size parameter pools with `slot.profile.tier(...)`** where the numbers can
  reasonably scale. A template that ignores it generates the real paper's
  numbers at every level, which is correct but means that slot feels the same
  whichever difficulty the student picked.

### Distractors

Every wrong option in the corpus belongs to one of eight families, in
`distractors.py`: sign flip, arrested computation, bracket permutation,
supplement/complement, wrong-angle-in-figure, reciprocal, factor-sign
permutation, off-by-a-factor. Offer more candidates than you need —
`numeric_options` filters implausible ones (a negative length, a value 50× off)
and raises `DistractorError` (a `Retry`) if fewer than three survive.

Interval items are a closed menu: `interval_variants()` produces the four
bracket forms, which is literally all the 2026 Q4, 2023 Q5, 2022 Q5 and 2021 Q5
option lists contain.

---

## Figures

A figure is **data**, not a component. `scene.py` builds a spec — named points
already laid out in viewBox coordinates plus the marks to draw on them — and one
client component, `SceneRenderer.tsx`, draws any of it.

This works because every paper since 2018 prints *„Те не са начертани в мащаб и
не са предназначени за директно измерване на дължини и на ъгли.”* The figure
does not have to agree metrically with the stem. It has to be **topologically**
right: M really between A and B, the foot of a height really inside the side,
the marked angle on the correct side of a cevian.

Seven scene kinds: `figure` (plane geometry), `grid`, `bars`, `pie`, `solid`,
`schematic`, `table`.

```python
f = triangle_for_cevians(rng=rng)
A, B, C = f.points["A"], f.points["B"], f.points["C"]
H = f.put("H", foot_of_perpendicular(B, A, C))
f.put("L", lerp(A, H, rng.uniform(0.50, 0.74)))
f.path(["A", "B", "C"], close=True)
f.seg("B", "H"); f.seg("B", "L")
f.right_angle("H", "B", "C")
f.angle("C", "H", "B", label=deg(gamma), radius=22)
scene = f.to_spec(aria="Триъгълник ABC с височина BH и ъглополовяща BL…", rng=rng)
```

### Layouts are sampled, not fixed

A layout used to return the same three points every time, so every paper
printed the same triangle with different numbers on it — all 21 plane-geometry
templates emitted exactly one geometry across 60 papers. They now sample per
draw, and every figure is additionally *posed*: mirrored, rotated a few degrees
and rescaled in `to_spec(rng=...)`. A similarity transform preserves everything
a figure asserts, so posing is safe even for figures built point by point
rather than from a named layout.

Sampling is only safe because each layout **declares its contract**, and the
decorator resamples until it holds:

```python
@layout(invariants=[
    angle_below("A", "B", "C", 85.0),    # both base angles comfortably acute,
    angle_below("C", "A", "B", 85.0),    # so a perpendicular's foot lands inside
    angle_above("B", "A", "C", 24.0),
    sides_differ("A", "B", "C"),         # a scalene triangle must look scalene
    points_inside(),
])
def scalene_triangle(fig=None, *, flat=False, rng=None): ...
```

That contract used to live in a docstring, which is exactly why it broke once:
the old `scalene_triangle()` was 87.9° at C, so the foot of the perpendicular
from B landed on top of C and the figure contradicted its own stem —
`triangle_for_cevians()` exists because of that. As a predicate it fails in CI
instead. Called with no rng a layout still returns a fixed canonical sample,
and that sample is checked against the same contract.

A layout that cannot close raises `LayoutError`, which is a `Retry`: the
assembler resamples rather than failing the paper.

Three traps worth knowing:

* **Scene labels are plain SVG text.** `"$12$"` renders with the dollar signs
  showing. The verifier rejects markup in figure labels. Table cells are the
  exception — they are real DOM and go through KaTeX.
* **Guardrails are errors, not warnings.** Nobody eyeballs each figure now, so
  `verify.py` rejects any scene with overlapping labels (`MIN_LABEL_GAP`), a
  point near the box edge (`MIN_BOX_MARGIN`) or an arc too thin to read
  (`MIN_ANGLE_DEG`). The three constants are the tightest values the old
  hand-tuned figures produced, rounded down, so nothing that was acceptable
  before became an error.
* **Two items may not print the same picture.** `check_paper` compares
  `scene.geometry_hash()`, which ignores labels — so "same triangle, different
  angle written on it" counts as a repeat. This used to fire on half of all
  papers: `median_to_hypotenuse` and `median_hypotenuse_from_median` both drew
  the canonical right triangle.

### Coverage against the real papers

The figure set is not guesswork about what NVO prints — it was audited against
the thirteen papers. `scripts/extract_nvo_figures.py` crops every vector-drawing
cluster out of `NVOS/*.pdf` with its stem text; `scripts/build_contact_sheets.py`
tiles them; `scripts/build_coverage_report.py` joins a hand classification to
the template registry and writes `docs/nvo-figures/coverage.md`.

What it found, and what the numbers mean for anyone adding to this:

| | |
|---|---|
| figures extracted | 209 |
| of those, not actually figures | 69 — instruction glyphs, marking tables, formula sheets, prose |
| real archetypes | 59 |
| already expressible | 30 |
| uncovered but recurring in 2+ papers | 9 |
| uncovered one-offs | 20 |

Seven of the nine were built (`tri_height_bisector_median`,
`tri_exterior_angle_at_base`, `tri_cevian_exterior_angle`,
`rect_diagonals_angle`, `tri_perpendicular_from_side_point`,
`tri_circumcentre_central_angle`, `line_through_vertex_angles`) on three new
layouts. **Two were not**, and they are the interesting ones: a piecewise
distance–time graph and shaded rectilinear composite areas both need a *new
scene kind*, not a new layout — `scene.py` has no line-graph kind and no shaded
region, so they would touch `SceneRenderer.tsx` as well.

The one-off archetypes are catalogued rather than built, on the reasoning that
a layout builder generating one item ever is worse value than a hand-authored
entry in `part2_bank.py`.

Two lessons from building the seven are worth carrying forward:

* **A hidden point that gets an arc drawn round it needs `inside_box`.**
  `points_inside` deliberately exempts hidden points, since they anchor lines
  meant to run off the figure. The exterior-angle layout's anchor is hidden and
  yet must be reachable; extending a slanted side instead of the base put it
  off the box in 137 of 200 draws.
* **Solve for a constrained position, don't sample and hope.** In
  `tri_height_bisector_median` the bisector's foot must clear `M` by 25 for the
  labels and sit at least `h·tan 16°` from `P` for the arc. Sampling the
  segment satisfied both so rarely that the template retried on essentially
  every draw; computing the admissible interval fixed it outright.

### Looking at the figures

```bash
# 1. dump one sample scene per template
cd backend && python -c "
import json
from app.nvo_gen.assemble import generate_paper
scenes, seen = [], set()
for code in ('nvo2026', 'classic'):
    for seed in range(40):
        for n, item, slot in generate_paper(code, seed=seed).numbered():
            if item.scene and item.template_code not in seen:
                seen.add(item.template_code)
                scenes.append({'title': item.template_code,
                               'stem': item.stem[:130], 'scene': item.scene})
open('/tmp/scenes.json', 'w', encoding='utf-8').write(json.dumps(scenes, ensure_ascii=False))
"

# 2. render them to a contact sheet
cd ../frontend && SCENES_JSON=/tmp/scenes.json SCENES_HTML=/tmp/scenes.html \
  npx vitest run src/components/SceneRenderer.contactsheet.test.tsx

# 3. open /tmp/scenes.html
```

---

## Part 2 is curated, not generated

`part2_bank.py` holds hand-authored extended items with their own marking
schemes. The reasoning:

* An 11–12 point proof is marked on *intermediate* results — "1 т. за съставяне
  и опростяване на уравнението". Generating a stem is the easy half.
* These are graded by a person (or the vision grader), so an ill-posed one is
  not caught by a key comparison the way a multiple-choice item is.
* The cost of being wrong is asymmetric: a flawed Part 1 item wastes two
  minutes, a flawed proof wastes twenty and teaches a false method.

A student therefore gets an unlimited supply of Part 1 and a deep but finite
Part 2, which is the right trade — nobody sits enough papers to exhaust a few
dozen proofs. Items carry light parameterisation where the numbers genuinely do
not change the reasoning.

Each entry declares its own sub-part points; the sum must equal the blueprint
slot total (12 / 11 / 12), which the verifier enforces.

---

## Partial credit

`Slot.points` is a tuple, not an int, from day one. The real keys award credit
per sub-part — "2 т., при един верен отговор" on the 2026 quadratic, "2 т., ако
е написано 4x" on the perimeter item — and retrofitting a points structure onto
items already in the database costs far more than carrying it from the start.
It reaches the client as `NVOQuestion.points`.

---

## Difficulty

Four levels — `easy`, `medium`, `actual`, `extra_hard` — defined in
`difficulty.py` and offered by `GET /nvo/difficulties`.

**The format never moves.** Every level generates the same positions, the same
topics, the same points per position and the same А/Б/В/Г menu, because that
skeleton is what makes a paper recognisable as НВО. `actual` *is* the real
exam: every knob neutral, byte-identical to generating with no difficulty at
all (asserted in `test_actual_matches_generating_with_no_difficulty_at_all`).
The other three are versions of it. What changes is only:

| knob | effect |
|---|---|
| `band_weights` | re-weights template choice by the template's `band`, so a slot with several candidates leans easy or hard. Never zero — a slot whose every template is hard must still be fillable. |
| `slot.profile.tier(...)` | lets a template size its own parameter pools. This is the lever that works even where a slot has one candidate. |
| `time_scale` | stretches or squeezes the blueprint's official minutes. |
| `xp_multiplier` | 0.5 / 0.8 / 1.0 / 2.0. |

Points are deliberately **not** a knob: Part 1 is 65 and Part 2 is 35 at every
level, so a percentage means the same thing across levels and the XP multiplier
— not a shorter paper — is what rewards taking the harder one.

`normalize()` resolves the pre-rename names (`standard` → `actual`, `hard` →
`extra_hard`) and anything unrecognised to `actual`, so stored attempts and
un-reloaded clients keep working and nothing 500s mid-exam over an enum.

For difficulty to mean anything a slot needs **several templates to choose
between**; `test_every_slot_has_several_templates_to_choose_between` holds the
floor at three.

---

## Where things live

```
backend/app/nvo_gen/
  blueprints.py   the two exam shapes, validated at import
  difficulty.py   the four levels and the knobs they turn
  scene.py        figure specs and the builders that emit them
  distractors.py  the eight wrong-answer families, Bulgarian number formatting
  registry.py     GeneratedItem, the @template decorator, slot eligibility
  templates/      numbers · algebra · wordproblems · data · geometry
  part2_bank.py   curated extended items
  verify.py       the gate — item-level and paper-level
  assemble.py     the generation loop
  api.py          translation to the client's existing NVOQuestion shape

frontend/src/components/
  SceneRenderer.tsx          draws any scene
  NVOBlueprintSelector.tsx   the format picker
  NVODifficultySelector.tsx  the difficulty picker

scripts/                     analysis tools, not shipped with the server
  extract_nvo_figures.py     crops every figure out of NVOS/*.pdf
  build_contact_sheets.py    tiles the crops for classification
  build_coverage_report.py   archetypes × papers, and the gap list
  dump_new_scenes.py         sample scenes for the renderer contact sheet

docs/nvo-figures/            the audit's evidence
  crops/                     209 figures, one PNG each, with provenance
  sheets/                    24 labelled contact sheets
  inventory.json             provenance, stem text, item number per crop
  archetypes.json            archetype → papers, crops, covering template
  coverage.md                the report
```

The `scripts/` tools need `pymupdf` and `pillow`, which are deliberately **not**
in `requirements.txt` — they are analysis dependencies, and the server never
imports them.

`renderNvoDiagram` routes `diagram_type: "scene"` to `SceneRenderer`; the twelve
hand-written diagram components stay for anything the legacy catalog generator
still produces.

---

## Tests

`backend/tests/test_nvo_blueprint_generation.py`. The ones that earn their keep
are at the bottom: they **re-derive each key from the stem** with the arithmetic
written a second time. That caught two real bugs during development —
`(x+k)² − x(x+k)` collapses to `k(x+k)` and not `x+k`, and a cubic expansion
whose normal form was off by a factor.

`test_five_hundred_papers_generate_without_a_single_failure` is the headline
claim and should stay green.

`backend/tests/test_nvo_difficulty.py` defends the one-sentence contract —
difficulty changes the items, never the format — plus two things worth naming:

* `test_the_same_seed_gives_different_papers_at_different_levels` and
  `test_easy_leans_on_easy_templates_and_extra_hard_on_hard_ones` guard the
  failure mode where the system type-checks but produces the same paper four
  times. The first cut did exactly that, because most slots had one template.
* `test_every_registered_template_can_actually_build_something` catches a
  template whose every draw is rejected. Three shipped in that state — their
  distractor pools sat entirely outside the plausibility band, so
  `numeric_options` raised on every draw and the slot silently fell through to
  another template while `coverage_report` still counted them.

`backend/tests/test_nvo_figures.py` holds the figure guarantees. Beyond the
three guardrails and `geometry_hash`, the one to know about is
`test_a_new_figure_asserts_what_its_stem_claims`.

The scale notice („Чертежите са само за илюстрация…”) licenses a figure whose
angles do not match its stem's numbers. It does **not** license one where `M` is
not really the midpoint, or where a segment the stem calls a perpendicular is
not perpendicular — a student reading that picture is reading a lie, and no
guardrail in `verify.py` would notice. So each figure template declares the
topology its stem promises as a predicate over the drawn points, and it is
checked on the *posed* output: every claim used — betweenness, midpoints,
perpendicularity, equal radii, collinearity — survives the similarity transform
`to_spec` applies, which is exactly why posing is safe.

`test_a_new_layout_closes_on_every_draw` is a lower bar than it looks. A layout
whose contract holds only sometimes still "works", because the decorator
resamples — but it burns tries per figure and raises `LayoutError` under load.
Every draw closing is the real bar.
