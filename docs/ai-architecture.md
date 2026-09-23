# AI architecture: what each model is for, and what it must not touch

Status: plan, 2026-09-22. Scope is NVO. The practice-problems / curriculum
surface is deliberately sidelined — see *Sidelined* at the bottom.

---

## 1. The one decision everything else hangs off

The brief was: *"when a user clicks start test it picks templates from the pool,
edits them and so on, along with the predetermined solutions."*

That is exactly the right shape, and it is worth stating precisely because a
near-identical-sounding alternative would be a serious mistake.

| | the model **selects and reskins** | the model **generates the maths** |
|---|---|---|
| where the numbers come from | the template pool | the model |
| who guarantees the key is right | `verify.py` + the re-derivation tests | nobody |
| distinct papers available | 10⁴⁵–10⁵² today | unbounded, unverified |
| cost per paper | ~0.2–0.6 ¢ | similar |
| failure mode | a clumsy sentence | a wrong answer key, silently |

**The generator stays deterministic. The model is an editor on top of it.**

This is not caution for its own sake. The pool currently reaches 6.7 × 10⁴⁷
Part 1 combinations with every key re-derived from the stem by a second,
independently written piece of arithmetic (that test caught two real bugs).
An LLM asked to run an angle chase will get it right most of the time — and
"most of the time" is a wrong answer key in a student's hands, in a product
whose whole promise is that it is like the real exam.

### The contract

The editor model receives one generated item and may change **surface** only:

| may change | must not change |
|---|---|
| the story/context (a cyclist → a hiker) | any number in the stem |
| names of people, shops, towns | `correct_answer` |
| phrasing, sentence order | the option list (values — wording may change) |
| units prose where equivalent | `scene` (the figure) |
| | `points`, `topic`, `signature` |

Enforced, not merely requested — the model returns a patch, and the patch is
applied and then re-validated:

```
generate_paper()  ──►  item  ──►  LLM reskin  ──►  apply patch
                         │                              │
                         └──────── key, options, ───────┤
                                   scene carried        ▼
                                   through verbatim   verify.check_item
                                                        │
                                              reject ◄──┴──► accept
                                   (fall back to the un-reskinned item)
```

A rejected patch costs nothing: the original item is already correct and
shippable. That property is what makes this safe to ship fast.

### Latency: do not do this on the click

"Click start test" must not wait on 24 sequential LLM calls. Two mechanisms:

1. **Pre-warm.** Generate and reskin papers ahead of demand into
   `nvo_exam_store` (which already exists). A student gets a paper that was
   built minutes ago.
2. **Degrade, never block.** If no reskinned paper is ready, serve the raw
   generated one. It is a complete, correct NVO paper — the reskin is polish.

---

## 2. What already exists

More than the brief assumes. Worth knowing before anything is built:

| capability | state | where |
|---|---|---|
| deterministic item generation | **done**, 112 templates, 10⁴⁷ combinations | `app/nvo_gen/` |
| figures as data + renderer | **done**, 8 scene kinds | `scene.py`, `SceneRenderer.tsx` |
| item/paper verification | **done** | `verify.py` |
| exam persistence | **done** | `services/nvo_exam_store.py` |
| phone pairing + photo upload | **partly done** | `routers/mobile_uploads.py` |
| grade a photo with AI | **partly done**, `gpt-4o` hard-coded | `mobile_uploads._grade_photo_with_ai` |
| AI assistant chat | **done** | `services/ai_theory_service.generate_chat_reply` |
| corpus embeddings / retrieval | **done** | `services/nvo_content_embeddings.py` |

So the mobile pipeline is a **hardening** job, not a greenfield one. The
security comment already in `mobile_uploads.py` — *"was unauthenticated, i.e.
free gpt-4o vision inference for [anyone]"* — is the shape of the remaining
work: auth, quota, retention.

---

## 3. How many models? Roles first.

The app has **seven** distinct AI jobs, not two. Listing them is what makes the
model count fall out rather than being guessed:

| # | job | stakes | volume | latency |
|---|---|---|---|---|
| 1 | read handwritten work from a photo (OCR) | high | medium | async ok |
| 2 | grade that work against a marking scheme | **highest** | medium | async ok |
| 3 | reskin generated items | low | **high** | pre-warmed |
| 4 | write the worked solution shown after marking | medium | medium | async ok |
| 5 | student assistant chat | medium | medium | **interactive** |
| 6 | escalation on a disputed/ambiguous grade | highest | very low | async ok |
| 7 | corpus embeddings for retrieval | low | batch | offline |

**Answer to "is more than two worth it": yes — but the seven roles collapse to
three models plus an embedder, not seven.** Splitting further buys nothing,
because the cheap tier is already capable enough for jobs 3 and 5, and the
workhorse is cheap enough that jobs 1, 2 and 4 do not justify a fourth.

---

## 4. Model routing — live OpenRouter prices

Pulled from `openrouter.ai/api/v1/models` on **2026-09-22**. USD per 1M tokens.
444 models available, 276 vision-capable. `cache` is the cached-input rate,
which matters a lot here because our prompts are highly repetitive.

### Recommended routing

| tier | model | in | out | cache | ctx | jobs |
|---|---|---|---|---|---|---|
| **A — cheap/bulk** | `openai/gpt-5-nano` | 0.05 | 0.40 | 0.005 | 400k | 3 reskin, 5 chat |
| **B — workhorse** | `openai/gpt-5.6-luna-pro` | **0.20** | **1.20** | 0.02 | 1050k | 1 OCR, 2 grading, 4 solutions |
| **C — escalation** | `openai/gpt-5.6-sol` | 2.00 | 10.00 | 0.20 | 1050k | 6 disputes only |
| **E — embeddings** | `text-embedding-3-small` (direct) | ~0.02 | — | — | — | 7 |

**`gpt-5.6-luna-pro` is the strongest option at this price point.**
At $0.20/$1.20 with vision and a 1M context it is priced like a mini model and
positioned like a frontier one. Concretely it *undercuts* several models it
outclasses:

| model | in | out | vision | note |
|---|---|---|---|---|
| `openai/gpt-5.6-luna-pro` | 0.20 | 1.20 | yes | **recommended workhorse** |
| `google/gemini-3.1-flash-lite` | 0.25 | 1.50 | yes | strictly more expensive |
| `openai/gpt-4o` *(what we use now for vision)* | 2.50 | 10.00 | yes | **12× the price** |
| `openai/gpt-4.1` *(what we use now for NVO)* | 2.00 | 8.00 | yes | 10× the price |

Moving vision from `gpt-4o` to `gpt-5.6-luna-pro` is a ~12× cost reduction and
almost certainly a quality *increase*. That single change is the highest-value
item in this document.

### Cheaper vision, if job 1 turns out to be easy

If OCR of handwritten Bulgarian maths proves reliable at the bottom tier:

| model | in | out | ctx |
|---|---|---|---|
| `openai/gpt-5-nano` | 0.05 | 0.40 | 400k |
| `google/gemini-2.5-flash-lite:batch` | 0.05 | 0.20 | 1048k |
| `qwen/qwen3.7-flash` | 0.03 | 0.13 | 1000k |
| `google/gemma-3-12b-it` | 0.05 | 0.15 | 131k |

**Do not assume this — measure it.** Handwritten fractions, radicals and
Cyrillic are exactly where cheap vision models fail, and a misread digit
becomes a wrong grade. §7 has the bake-off.

### Batch tier

OpenRouter exposes `:batch` variants at **50% off** for non-interactive work
(`gpt-5.6-luna-pro:batch` = $0.10/$0.60). Embeddings, pre-warming the paper
pool and re-grading backlogs should all use it. Interactive paths must not.

---

## 5. What this costs

Assumptions stated so they can be argued with: a paper is 24 items; a reskin
sends ~350 tokens and returns ~150; a graded photo is ~1.5k image tokens plus
~800 of marking scheme, returning ~400.

| action | tier | cost |
|---|---|---|
| reskin one whole paper (24 items) | A | **$0.0019** |
| reskin one whole paper | B | $0.0060 |
| OCR + grade one Part 2 photo | B | **$0.0010** |
| grade a whole Part 2 (3 photos) | B | $0.0030 |
| **one complete exam attempt, end to end** | A+B | **≈ $0.005** |

At 1,000 students sitting one paper each: **about $5**. With prompt caching and
the batch tier on pre-warming, less.

**Cost is not your constraint at this stage — correctness and latency are.**
That should settle any temptation to pick a weaker model to save money. Budget
for the good one.

---

## 6. Phone → profile → AI pipeline

Already partly built. What remains, in order:

1. **Bind the channel to the user.** `channel_id` currently identifies a
   session; it must be derived from, and checked against, the authenticated
   account. The existing security note in the file says this was the hole.
2. **Quota and rate-limit per account**, not per IP. `ip_rate_limiter.py`
   exists; vision calls need a per-user budget because one loop in a client
   can spend real money.
3. **Retention.** `media_retention.py` exists — confirm photos of minors' work
   are deleted on a schedule and that the schedule is short.
4. **Route the vision call through the tier table** rather than the hard-coded
   `model="gpt-4o"` at `mobile_uploads.py:499`.
5. **Grade against the marking scheme, part by part.** Part 2 items carry
   per-sub-part points, and the marking scheme is prose in `marking`. The
   grader should return credit per sub-part, not one holistic score — that is
   the whole reason the points are a tuple.

---

## 7. The one experiment worth running before committing

A two-hour bake-off that de-risks the most expensive mistake:

* Take **30 real photos** of handwritten Part 2 work — varied handwriting,
  lighting, some deliberately messy.
* Run OCR + grading through `gpt-5-nano`, `gemini-2.5-flash-lite`,
  `gpt-5.6-luna-pro` and today's `gpt-4o`.
* Score against a hand-marked ground truth: **per-sub-part credit**, not
  overall.
* Pick the cheapest tier that matches hand-marking; escalate the rest to C.

Without this, the routing table above is an educated guess. With it, it is a
measurement.

---

## 8. Sequencing

The stated goal is NVO AI layer, then school-centred (another agent), then
teacher portals, then UI rework, then pitch — **this week**.

An honest read: the *AI layer* below is a few days of work and most of it is
low-risk because of the fallback design. Teacher portals and a UI rework are
each multi-day on their own. I would plan the week as:

| order | work | risk |
|---|---|---|
| 1 | swap vision + NVO models to the tier table (config only) | very low, immediate 10× saving |
| 2 | harden mobile auth/quota/retention | low, unblocks demoing on a phone |
| 3 | reskin service + patch validation + pre-warm | medium |
| 4 | per-sub-part grading against the marking scheme | medium |
| 5 | OCR bake-off (§7) | low, informs 1 and 4 |
| 6 | school-centred (parallel, other agent) | — |
| 7 | teacher portals | high — likely the week's casualty |
| 8 | UI rework + pitch | high |

Items 1 and 2 are worth doing first regardless of what else lands, because
they pay off immediately and are independent of everything below them.

If the pitch is the fixed point, **1–4 plus a rehearsed demo path is a stronger
pitch than 1–8 half-finished**, and the generator's 10⁴⁷ number is already a
good slide.

---

## 9. Open decisions

1. **Reskin scope.** Reskin every item, or only the word problems (where
   context actually varies) and leave pure algebra alone? Cheaper, and
   arguably better — nobody needs a novel framing for "solve 2x + 3 = 11".
2. **OpenRouter as sole provider.** One key and heavy discounts are real
   advantages at this stage. The cost is a dependency on their availability
   in front of every provider. Recommendation: use it now, keep the model id
   in config (as `OPENAI_MODEL` already is) so a direct-provider fallback is
   a config change.
3. **Assistant personality/scope** — is it a tutor that explains, or a hint
   engine that refuses to give answers? Materially changes the prompt and the
   tier.

## Sidelined

Curriculum/theory generation (`ai_theory_service.generate_theory_content`,
`generate_example_problems`, `generate_exercises`, `generate_video_search_queries`)
and the practice-problems surface are **out of scope** for this pass, per the
brief. They are the highest-volume LLM consumers in the app, so when they come
back they should come back on tier A with caching.
