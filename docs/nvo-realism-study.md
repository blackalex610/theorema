# NVO generator — realism and exhaustibility study (2026-09-23)

**Question:** is the NVO paper generator done and ready for students — as close
as possible to the real papers in `NVOS/`, and nearly inexhaustible?

**Answer before this study: no.** Part 1 was sound in structure but thin and
repetitive in places; Part 2 — the 35 points a student meets again most
often — had wrong or unsolvable items; and grading scored papers in a way no
НВО result is scored. All of it is fixed on branch `nvo-realism-study`; what
is still open is listed at the end.

---

## Method

1. Extracted the text of all 13 papers and keys in `NVOS/` (2015–2026, plus the
   ministry format memo) and read Part 1 and Part 2 of 2019–2026 item by item.
2. Generated papers in both blueprints and read them against the real paper at
   the same position.
3. Sampled every template in every slot it fills (300–1500 draws) and measured,
   per position, **distinct items** and **distinct wordings** (stem with the
   numbers blanked) — what a student perceives as "the same question again".
4. Re-derived Part 2 answers with exact arithmetic and against the ministry keys.
5. Read the grading path (`/nvo/submit`) end to end.

---

## Findings

### Correctness — Part 2 (severity: high)

| item | problem |
|---|---|
| `system_from_expressions` (2021 Q22) | Transcribed `x(x − 4)/9` for the paper's `x(0,5x − 4)/9`, so x² did not cancel: all 3 variants had irrational roots (e.g. 3x² − 14x − 85 = 0). Unsolvable in 7th grade. The paper's key is x = 15. |
| `factor_then_roots_then_inequality` | A fixed inequality solving to x > 125/59; key was the placeholder „Линейно неравенство след опростяване”. |
| `two_vehicles_meeting` (2025 Q22) | Stated the bus speed, the speed gap *and* a midpoint meeting — facts that force v = 5·Δ. No variant satisfied it (60 km/h bus: 120 km vs 125 km to the "midpoint"). |
| `two_brigades_work` (2023 Q22) | Part Б gave fractional days in 8 of 9 parameter combinations. |
| `parallelogram_height_proof` (2024 Q23) | The 60° variant is false: △AFK ≅ △DLK needs AK = DK, i.e. 45°. |
| three proof figures | L, P, Q, K placed at random along a side — the drawn bisector did not bisect, the "perpendicular" was not one, an isosceles triangle was drawn scalene. |
| keys | Seven answers were placeholders („Интервал”, „Доказателство за ромб”…), which is what the grader compared against. |

### Fidelity to the real papers (medium)

- **Currency.** Bulgaria uses the euro from 1 Jan 2026 and the June 2026 paper
  prices in „евро” (Q7). Five templates printed лв./лева.
- **„0,229”.** A distractor printed as a rounded repeating decimal (1/4 − 1/48).
  No option in 13 papers carries three decimals.
- **Dead template.** `adjacent_angle_ratio` was registered and counted in
  coverage but rejected on all 400 draws (geometry slots need a figure; it drew none).
- **Always 120°.** `angle_equals_neighbours` had one answer.
- **Grammar.** „броя на продадени велосипеда”, „Колко общо са продадени
  велосипеда”, „Заедно с Иван те подредят стаята”, an invisible soft hyphen in
  „масленост­та”.
- **Missing real shapes.** 2023–2025 contain item shapes the generator lacked:
  counting primes, letters on cards (КАРЛОВО), which |…| equation has no root,
  0,99² − 0,01², the factor that does NOT occur, a power quotient at x = −3, a
  mean that must reach a target, a map scale from two distances, and more.

### Exhaustibility (high for students who practise a lot)

- 104 of 118 template/kind pairs printed **one fixed sentence**; most drew
  numbers from a hand-picked list of ~7 values.
- Thinnest positions: shortcut multiplication **21** distinct items, work rate
  **24**, expression-at-value 36, expand/factor 39, expression-from-words 54.
- Part 2: 3 algebra shapes (28 items, 2 wrong), 3 word shapes (53, 2 wrong),
  5 geometry shapes (43).

### Grading (high)

- Every question counted **one point**. The 2026 paper is 65 + 35 with items
  worth 2–5 in Part 1 and 12/11/12 in Part 2; counted per question, Part 2 was
  12,5% of the score instead of 35%.
- No partial credit per sub-part, although the keys award it (Q17: А 2 т., Б 3 т.).
- Every short answer — „2026”, „0 и 25” — went to the language model; with no
  API key it raised 503 and **the paper could not be submitted at all**.
- The model never saw the marking scheme.

---

## What changed

| commit | change |
|---|---|
| `a3f7457` | Part 2 algebra and word problems rebuilt on `poly.Expr` (one tree renders the stem and computes the key); 5 algebra and 6 word shapes, each a real item generalised by drawing free quantities and solving for the rest; geometry proofs get solved figures and real keys. |
| `bd98749` | Euro everywhere, rescaled to euro price levels; verifier refuses leva and 3-decimal options; `adjacent_angle_ratio` and `angle_equals_neighbours` rebuilt; chart grammar fixed. |
| `b12c795` | Submit scores in NVO points with Part 1/Part 2 subtotals and per-sub-part credit; short answers checked exactly in code (`services/nvo_grading.py`); marking scheme passed to the model; a model outage no longer blocks submission. |
| `ed0fce5` | 26 hand-picked angle lists → full drawable ranges (the level still sets how round the numbers are); word problems get pools of settings. |
| `c66bf03` | 15 new item shapes from the real papers (`templates/corpus.py`); thin positions rewritten with generated pools. |
| `6f3475c` | Last thin pools widened; per-position variety floor pinned in tests. |
| `baed4a7` | Three more Part 2 proofs transcribed (2019 Q25, 2020 Q23, 2021 Q23), each generalised exactly as far as its argument allows. |

## Numbers (lower bounds, `scripts/measure_capacity.py`)

| | before | after |
|---|---|---|
| thinnest Part 1 position | 21 items | 203 items |
| Part 1 combinations (2026 format) | 6,7 · 10⁴⁷ | 2,9 · 10⁶¹ |
| Part 2 algebra | 3 shapes / 28 items | 5 shapes / 7 468 items |
| Part 2 word problems | 3 shapes / 53 items | 6 shapes / 6 899 items |
| Part 2 geometry | 5 shapes / 43 items | 12 figures, 98 question sets / ~2 000 items |
| templates | 112 | 127 |

## How correctness is now defended

- `test_nvo_part2_keys.py` — every Part 2 key re-derived from the printed stem
  with a LaTeX reader independent of the code that built it; fails on each of
  the four Part 2 bugs above.
- `test_nvo_part1_keys.py` — the same for every new or rewritten Part 1 template.
- `test_nvo_part2_figures.py` — every claim of every proof pool is measured on
  its own drawn figure; marking steps add up; dependencies point backwards.
- `test_nvo_partial_marks.py` — the examiner awards part marks per sub-part.
- `test_nvo_realism.py` — no leva, no 3-decimal options, every template passes
  the verifier in every slot it claims, every position ≥ 80 distinct items.
- `test_nvo_grading_points.py` — a perfect Part 1 scores 65/100 with no AI
  available; partial credit follows the sub-part points; the marking scheme
  never reaches the client.

Full backend suite: 1853 passed. Frontend: 46 passed.

---

## Still open — decide before calling it finished

1. **Part 2 geometry — closed as far as the corpus allows.** All twelve real
   proofs (2015–2026) are transcribed, and each is a *pool of claims*: a paper
   asks 3–4 of 6–10 verified claims totalling 12 points, easy to hard. 12 figures,
   98 distinct question sets, ~2 000 distinct items (`part2_proofs.py`). A student
   who sits many papers will recognise a figure, but will be asked something new
   about it — as the real exam reuses its standard configurations. Beyond this
   needs generated constructions (proposed, not built).
2. **Proof grading still depends on the model** — but it now marks like an
   examiner: each sub-part gets any whole number of points from 0 to its
   maximum by the scheme, typed or photographed (`ai_mark` in
   `services/nvo_grading.py`, pinned by `tests/test_nvo_partial_marks.py`).
   The keys' own short-answer part marks (2026 Q15, Q16, Q21) are applied in
   code. Two limits remain: points are whole (the keys occasionally award
   0,5 т.), and how *well* the model follows a scheme has only been tested
   with a stub, not measured against real marked scripts.
3. **Scores changed meaning.** Percentages and XP are now points-based. The same
   performance can give a different percentage than before (Part 2 now weighs
   35%). Old attempts in history were scored the old way.
4. **Not exercised in a running app.** The results-screen change type-checks and
   the endpoint is tested, but I did not click through a sitting in the browser.
   Worth one manual sitting before release.
5. **Share-table cells** (`75% от n`) render through KaTeX in the app; the offline
   contact sheet cannot show them, so that path was not eyeballed.
6. **Branch base.** This branch sits on `worktree-nvo-figure-templates`, which is
   itself unmerged; merge that first (or this, which contains it). The main
   checkout also holds an older uncommitted draft of the same figure work in
   `backend/app/nvo_gen/` — superseded by that branch, so it can be discarded
   once the branches land.
