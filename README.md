# Theorema

**A math learning platform for Bulgarian students in grades 5–7, built around a deterministic generator of realistic NVO exam papers.**

Formerly developed under the name *SmartNVO*.

[Live demo](https://smartnvo.vercel.app) · [Generator design](docs/nvo-generation.md) · [Realism study](docs/nvo-realism-study.md) · [AI architecture](docs/ai-architecture.md)

---

## Recognition

- Presented at the **5th National Conference for Pupils, Students and PhD Candidates "Information Technologies and Automation" (ITA 2026)**, organized by the Department of Industrial Automation at the University of Chemical Technology and Metallurgy (UCTM), Sofia.
- **Awarded by National Company Industrial Zones EAD** (Национална компания „Индустриални зони“ ЕАД).
- Selected for publication in an upcoming issue of ***Science, Engineering & Education***, the peer-reviewed journal of UCTM.

---

## The problem

The NVO (Национално външно оценяване) is the national 7th-grade math exam in Bulgaria. Its result decides which high school a student can enter. Students preparing for it run out of official papers quickly: only one or two are released per year, and commercial practice books rarely match the real format, point scheme or style of wrong answers.

Theorema generates an unlimited supply of new papers that follow the official format exactly, grades them the way an examiner would, and wraps that in a full curriculum for grades 5–7.

## The NVO exam generator

The core of the project is `backend/app/nvo_gen/`, a blueprint-driven generator of about 11,000 lines of Python. It is fully deterministic: every number, answer key and figure comes from code, not from a language model.

**How a paper is built**

```
blueprint ──► slot ──► eligible templates ──► sample parameters ──► stem, key, distractors, figure
                                                                              │
                                              verify.check_item  ◄────────────┘
                                                      │
                             assemble 24 items ──► verify.check_paper ──► paper
```

1. **Blueprints as data.** The exam format was reverse-engineered from 13 official papers (2015–2026). Two blueprints encode the two eras: the classic format (20 multiple-choice items in Part 1, 75 minutes) and the 2026 format (14 multiple-choice plus 7 short-answer items, 90 minutes). Invariants such as *Part 1 is always 65 points, Part 2 always 35* are asserted, not assumed. A future format change costs one new blueprint entry.
2. **Item templates, not question banks.** 127 templates across numbers, algebra, data, word problems and geometry. Each one is a parameter space plus the functions that turn a sample into a Bulgarian stem, a correct key, four options and a figure. Templates declare an intrinsic difficulty band and scale their own number ranges to the requested difficulty.
3. **Distractors modeled on real student mistakes.** Every wrong option in the official papers falls into one of eight families: sign flip, stopping one step early, bracket or inequality permutation, supplement/complement, reading the wrong angle, reciprocal, factor-sign permutation and off-by-a-factor. The generator builds wrong answers from these families, so a student who picks one can see what went wrong. All arithmetic uses exact fractions, so a distractor can never equal the key through rounding.
4. **Figures as data.** Geometry, charts, grids, tables, 3D solids and schematics are emitted as declarative scene specs (8 kinds) and rendered on the client, instead of shipping images.
5. **A verification gate.** `verify.py` rejects malformed items (wrong option count, key not among options, Latin letters mixed with Cyrillic А/Б/В/Г, unrenderable math) and malformed papers (duplicate templates, skewed answer distribution, wrong point totals). A test suite re-derives every answer key with an independently written solver.
6. **Four difficulty levels.** Easy, medium, actual and extra hard. The structure of the paper never changes between levels. Only template selection, number complexity and time limits do, so a percentage means the same thing at every level.

The template pool yields on the order of 10⁴⁷ distinct Part 1 combinations.

**Grading like the official key.** `services/nvo_grading.py` scores each sub-part on its own and awards partial credit as the official marking schemes do. Numeric answers, sets, times and polynomials are compared exactly on the server at no cost. Only answers that cannot be checked mechanically, such as written geometry proofs, go to a model acting as an examiner with the marking scheme and a per-part point ceiling.

## Where AI is used, and where it is not

The language model is treated as an editor and an examiner, never as the source of mathematical truth.

| Task | Approach |
|---|---|
| Generating problems and answer keys | Deterministic code, verified. No LLM. |
| Rewording a generated problem | LLM may change context and names only. The patch is re-validated; on rejection the original item is served. |
| Grading written proofs | LLM receives the official-style marking scheme and awards points per step. |
| Reading handwritten work | Vision model on a photo taken with a paired phone. |
| Lesson theory and tutoring chat | LLM, grounded in the current lesson. |
| Retrieval over the exam corpus | Embeddings (`text-embedding-3-small`). |

The full reasoning, including model routing and cost per paper, is in [`docs/ai-architecture.md`](docs/ai-architecture.md).

## Platform features

- **Curriculum for grades 5–7**, organized as grade → topic → lesson → exercise, with theory, worked examples and exercises with instant feedback.
- **Full NVO simulations** with the official timing, question navigator, review marking and a detailed breakdown after submission.
- **Phone pairing.** A student scans a QR code, and their phone becomes a camera for uploading handwritten solutions during an exam. Pairing runs over an authenticated WebSocket channel.
- **Classrooms** for teachers to group students and follow their progress.
- **Progress tracking** with XP, levels and per-topic statistics.
- **Guest mode**, Google sign-in, GDPR data export and deletion.

## Tech stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI, KaTeX, Framer Motion |
| Backend | Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic v2 |
| Realtime | Node.js, Socket.IO, JWT-authenticated channels |
| AI | OpenAI models for grading, vision and chat; embeddings for retrieval |
| Quality | pytest (420+ backend tests), Vitest, ESLint, Sentry |
| Hosting | Vercel (frontend and API), Render (realtime server), Supabase Postgres |

## Repository layout

```
backend/
  app/
    nvo_gen/        exam generator: blueprints, templates, distractors, scenes, verification
    services/       grading, exam storage, retrieval, embeddings, progress, uploads
    routers/        REST API (auth, curriculum, exercises, NVO, classrooms, uploads)
    models/         SQLAlchemy models
  alembic/          database migrations
  tests/            pytest suite
frontend/           React application
realtime-server/    Socket.IO server for phone pairing
docs/               AI architecture, figure coverage report
scripts/            corpus tooling: figure extraction, coverage and capacity reports
NVOS/               official NVO papers (2015–2026) used as the reference corpus
```

## Running locally

**Prerequisites:** Python 3.11+, Node.js 20+, PostgreSQL.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set DATABASE_URL, SECRET_KEY, OPENAI_API_KEY
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173

# Realtime server (only needed for phone pairing)
cd realtime-server
npm install
npm start
```

API documentation is served at `http://localhost:8001/docs`.

**Tests**

```bash
cd backend && pytest
cd frontend && npm test
```

Deployment notes are in [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Author

**Nikolay Nikolaev**
