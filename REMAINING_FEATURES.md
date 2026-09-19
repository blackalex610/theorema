# Remaining Features (Not Implemented Yet)

> **Updated 2026-09-19** — every item below re-verified against actual source (file:line evidence), not against the old doc text. See `PRODUCTION_ROADMAP.md` §4/§6 for the security/infra blocker list; this file covers only the product-feature backlog.

## 1. Saved Problems System (Practice + NVO) — ❌ Not started

Confirmed: zero matches for `saved_problem` / `SavedProblem` anywhere in the repo outside this doc. No model, no endpoint, no UI.

- Add "Save problem" action on individual practice problems.
- Add "Save problem" action on NVO questions.
- Add a "Saved Problems" button in the right-side bottom popup/jump bar.
- Build a Saved Problems view/list with:
  - Problem content preview
  - Origin of saving (practice lesson / NVO exam + question number)
  - Date and time saved
- Allow opening saved problems directly from that list.

## 2. NVO Exam Flow Lock on Refresh — ✅ Done

`frontend/src/pages/NVOPracticeExamPage.tsx:97` defines `STORAGE_KEY = 'nvo-practice-state-v1'`; restore logic at `:459-480` reads it on mount and rehydrates the in-progress exam instead of dropping to a new-exam screen. Still worth a manual QA pass on tab-close / expired-job / guest-user edge cases, but the core mechanism works.

## 3. NVO Modes: Full + Shortened — ✅ Done (2026-09-09)

Wired `NVOFormatSelector` into the pre-exam modal in `NVOPracticeExamPage.tsx`, alongside the existing difficulty selector. `selectedFormat`/`examFormat` state (previously unused, underscore-prefixed) now drives `createNVOGenerationJob(difficulty, format)`, the exam timer duration (`getExamDurationSeconds` in `frontend/src/utils/nvoFormat.ts`), and is persisted on `ExamHistoryEntry.format`. Verified end-to-end in a real browser session: selecting "Кратък НВО" generated a 16-question exam with a 30:00 timer (vs. 23 questions / 90:00 for full). Covered by `src/utils/nvoFormat.test.ts` and `src/components/NVOFormatSelector.test.tsx` (new Vitest + React Testing Library suite — this was the first frontend test infra in the project).

## 4. NVO Difficulty Selector + XP Multipliers — ✅ Done

- `NVODifficultySelector` is imported and rendered in a modal (`NVOPracticeExamPage.tsx:1457-1476`).
- Selection feeds `startNewExam(selectedDifficulty)` (`:913-915`).
- XP result screen shows `xpAwardResult.difficulty_multiplier` (`:1786-1788`).

Fully wired end-to-end (easy 0.5×, normal 1×, hard 2×). No action needed.

## 5. NVO History Improvements — ✅ Done (2026-09-19)

Done:
- "Недовършен" (unfinished) status label at `:1382`.
- Capped at last 10 (`MAX_HISTORY_ATTEMPTS = 10`).
- Review mode with per-question breakdown exists.
- **Server-side history (new).** `/nvo/submit` had been writing an `NvoAttempt`
  row per graded sitting for a while, but nothing could read those rows back —
  the exam page built its list purely from localStorage, so a student switching
  devices or clearing browser data lost every past score. `GET /nvo/attempts`
  (`backend/app/routers/nvo.py:1127`) now returns the signed-in student's own
  attempts, newest first, scoped on `current_user.id` and capped (default 20,
  hard max 100). The exam page fetches them on mount and folds them into the
  local list (`frontend/src/pages/NVOPracticeExamPage.tsx:605`).

  Conflict rules, in `frontend/src/utils/nvoHistory.ts`: **the server owns the
  scores** (it graded against its own answer key; the local copy is a display
  cache), **the device owns the review payload** (questions and answers exist
  only in localStorage). An attempt left unfinished here but submitted
  elsewhere is promoted to completed rather than keeping a stale badge.

  Covered by `backend/tests/test_nvo_attempt_history.py` (9 tests, including
  cross-user isolation) and `frontend/src/utils/nvoHistory.test.ts` (11 tests).
  `/nvo/attempts` is pinned in the route-auth matrix as a personal-data route.

**Known limitation — per-question review stays local.** A synced attempt shows
its score but no "Преглед на теста"; the card says so in Bulgarian instead.
Generated exams live in `nvo_exam_store` behind a 24h TTL, so making review
durable would mean permanently storing every exam a student ever sat — a real
storage decision, not an oversight. Track it separately if cross-device review
is wanted.

## 6. Mission-to-Practice Routing Quality — no issue found (not exhaustively audited)

Spot check: `backend/app/models/progress.py:129` has a `mission_id` FK; `DashboardPage.tsx:327` calls `navigate(mission.route)` directly. No inconsistency surfaced. A full audit of every mission definition's route target vs. its lesson/topic/difficulty constraints was not performed — revisit only if a specific routing bug is reported.

## 7. Badge Schema Migration — ✅ Done going forward

`backend/alembic/versions/754e61405945_baseline_schema.py:81` includes `badge_key` in the **baseline** migration — new and freshly-migrated databases get it correctly, not via a bolted-on ALTER. `progress_service.py:473-475` still has a try/except around legacy schemas, but it's now a deliberate safety net for pre-Alembic databases, not a swallowed-error bug. Low-priority cleanup: remove the fallback once every environment is confirmed on the Alembic baseline.

---

## Priority order for remaining work

1. ~~NVO short/full format wiring (#3)~~ — done 2026-09-09.
2. ~~Server-side NVO history persistence (#5)~~ — done 2026-09-19.
3. **Saved Problems System (#1)** — full new feature (model + API + UI). Now the
   largest remaining product gap.
4. Durable cross-device NVO review (new, from #5) — needs a decision on storing
   every sat exam past the 24h exam TTL.
5. Badge legacy fallback cleanup (#7) — cosmetic, do whenever convenient.
6. Mission routing (#6) — skip unless a bug surfaces.

## Additional product ideas (not in original backlog, still just ideas)

- **Email auth** — only if schools require non-Google accounts
- **Classroom codes** — teacher creates class, students join
- **Parent progress email** — weekly summary
- **Printable NVO results** — PDF export of attempt review
- **Curriculum admin UI** — edit topics/lessons without seed scripts
- **Bulgarian voice read-aloud** — accessibility for theory pages
