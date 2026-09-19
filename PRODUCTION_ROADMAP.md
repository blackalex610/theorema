# SMART NVO — Production Roadmap

> **Context:** SMART NVO is an AI-powered Bulgarian math learning platform for grades 5–7, focused on НВО (National External Assessment) preparation. Students learn theory, practice exercises, take full mock exams, track XP/progress, and optionally pair a phone for photo uploads during exams.
>
> **Audience for this doc:** developers preparing the app for real users (teachers, students, parents) in production — not a marketing doc.

---

## Table of Contents

1. [What Exists Today](#1-what-exists-today)
2. [Architecture Overview](#2-architecture-overview)
3. [Feature Completion Matrix](#3-feature-completion-matrix)
4. [Production Blockers (Must Fix)](#4-production-blockers-must-fix)
5. [Phased Next Steps](#5-phased-next-steps)
6. [Product Backlog (Remaining Features)](#6-product-backlog-remaining-features)
7. [Deployment Checklist](#7-deployment-checklist)
8. [Environment & Configuration](#8-environment--configuration)
9. [Security Hardening](#9-security-hardening)
10. [Testing Strategy](#10-testing-strategy)
11. [Technical Debt & Doc Drift](#11-technical-debt--doc-drift)
12. [Success Criteria for Launch](#12-success-criteria-for-launch)

---

## 1. What Exists Today

### Core learning loop (working end-to-end)

| Flow | Status | Notes |
|------|--------|-------|
| Browse curriculum (grades → topics → lessons) | ✅ Done | Practice path (`/grades`) + theory path (`/learn`) |
| AI-generated theory (3 detail levels) | ✅ Done | Concise / standard / detailed; fallback when no OpenAI key |
| AI-generated example problems | ✅ Done | Reveal answers, feedback buttons |
| AI-generated exercises per lesson | ✅ Done | Submit answers, XP toast, level-up modal |
| Progress dashboard (Coach + Classic) | ✅ Done | Toggle in Settings; Coach is default |
| XP, levels, streaks, daily missions | ✅ Done | Backend + sidebar + coach dashboard |
| Badges | ⚠️ Partial | Dev-only shelf; legacy schema fallback in backend |
| NVO full practice exam | ✅ Done | Async generation, timer, MCQ + open answers, diagrams |
| NVO difficulty + XP multipliers | ✅ Done | Easy 0.5× / Normal 1× / Hard 2× |
| NVO exam restore on refresh | ✅ Done | `localStorage` (`nvo-practice-state-v1`) |
| NVO attempt history + review | ✅ Done | Server-side via `GET /nvo/attempts`, merged into the local list; unfinished badge + resume; review mode exists. Per-question review stays device-local (24h exam TTL) — see REMAINING_FEATURES.md §5 |
| AI chat tutor | ✅ Done | Global sidebar; context shortcuts on theory/exercise/NVO pages |
| Google OAuth login | ✅ Done | JWT stored in `localStorage` |
| Guest mode | ✅ Done | Browse with zeroed/mock data; no token |
| Freemium plan limits UI | ✅ Done | AI exercises, chat, NVO, image scans — counters in sidebar |
| Dark mode | ⚠️ Partial | Settings toggle; coach dashboard + navbar fixed; classic pages lighter |
| Bug reporting + analytics events | ✅ Done | File-based backend logging (MVP) |
| Mobile photo capture + grading | ✅ Done | `/mobile-capture`, SSE live feed |
| Phone pairing (desktop ↔ phone) | ⚠️ Partial | Channel state is now durable across instances (see §4 #9); SSE fanout still single-instance. Experimental in Settings |

### Auth & accounts

| Item | Status |
|------|--------|
| Google Sign-In | ✅ Done |
| Guest access | ✅ Done |
| Email/password registration | ❌ UI only — not wired |
| `/register` page | ❌ Static form, no API |
| Route guards (protected routes) | ❌ All routes public |
| Logout clears token | ❌ Only removes `user`, not `token` |
| Refresh token / session renewal | ❌ 30-min JWT expiry, no refresh flow |

### Monetization

| Item | Status |
|------|--------|
| Plan status API (`free` / `premium`) | ✅ Done |
| Daily usage counters | ✅ Done |
| Upgrade UI in Settings | ✅ Done |
| Stripe / real payments | ❌ `POST /plan/upgrade` grants premium instantly |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Vercel (monorepo)                        │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │  Frontend (Vite/React)│    │  Backend (FastAPI serverless) │  │
│  │  Route: /             │    │  Route: /_/backend            │  │
│  └──────────┬───────────┘    └──────────────┬───────────────┘  │
└─────────────┼───────────────────────────────┼──────────────────┘
              │                               │
              │         ┌─────────────────────┤
              │         │                     │
              ▼         ▼                     ▼
     ┌────────────┐  ┌──────────────┐  ┌─────────────┐
     │ PostgreSQL │  │ OpenAI API   │  │ Google OAuth│
     │ (Supabase) │  │ (theory/NVO/ │  │             │
     │            │  │  chat/vision)│  │             │
     └────────────┘  └──────────────┘  └─────────────┘

     ┌────────────────────────────────────────┐
     │  Realtime Server (Node.js + Socket.IO) │  ← separate deploy
     │  Railway / Render / etc.               │     (not on Vercel)
     └────────────────────────────────────────┘
```

### Tech stack (actual, not README claims)

| Layer | Stack |
|-------|-------|
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS 4, React Router 7, Framer Motion, KaTeX |
| Backend | FastAPI, SQLAlchemy 2, Pydantic 2, python-jose JWT, google-auth |
| Realtime | Node.js, Socket.IO (`realtime-server/`) |
| DB | SQLite (local dev) → PostgreSQL/Supabase (production target) |
| State | React Context (`Settings`, `Xp`, `Pairing`, `DeveloperMode`) + `localStorage` |
| Deploy | Vercel experimental services (`vercel.json`) |

### Key frontend routes

| Route | Purpose |
|-------|---------|
| `/login` | Landing + Google + guest auth |
| `/dashboard` | Coach (default) or Classic dashboard |
| `/grades` → `/topics` → `/lessons` → `/exercises` | Practice flow |
| `/learn/grades` → … → `/theory` | Theory flow |
| `/nvo/practice` | Full NVO exam simulator |
| `/progress` | Detailed progress summary |
| `/controller` | Phone pairing companion |
| `/mobile-capture`, `/live-uploads` | Photo upload pipeline |
| `/playground` | Dev-only (triple-click Settings title to enable) |

### Key backend API groups

| Prefix | Responsibility |
|--------|----------------|
| `/auth` | Google OAuth → JWT |
| `/curriculum` | Grades, topics, lessons, exercises, AI theory |
| `/exercises` | Submit attempts (auth required) |
| `/progress` | XP, badges, missions, dashboard stats |
| `/ai` | Chat + diagram generation |
| `/nvo` | Exam generation jobs, grading, XP award |
| `/mobile` | Photo uploads, SSE stream, OCR grading |
| `/plan` | Usage limits + upgrade (stub) |
| `/companion` | Desktop↔phone pairing sessions |
| `/analytics`, `/bug-report`, `/feedback`, `/log-error` | Observability (MVP, file-based) |

---

## 3. Feature Completion Matrix

Legend: ✅ Production-ready · ⚠️ Works but needs hardening · ❌ Missing or stub

### Student-facing features

| Feature | FE | BE | Prod-ready? |
|---------|----|----|-------------|
| Curriculum browsing | ✅ | ✅ | ✅ |
| AI theory generation | ✅ | ✅ | ⚠️ Needs OpenAI key + rate limits enforced |
| AI exercises | ✅ | ✅ | ✅ Auth required for generation; cached exercises public |
| Exercise submission + XP | ✅ | ✅ | ✅ |
| Coach dashboard + missions | ✅ | ✅ | ✅ |
| Classic dashboard | ✅ | ✅ | ⚠️ Dark mode incomplete |
| NVO full exam | ✅ | ✅ | ⚠️ In-memory job state on serverless |
| NVO short exam | ❌ | ⚠️ API supports `format` | ❌ `NVOFormatSelector` not wired |
| NVO history (server) | ❌ | ❌ | ❌ localStorage only |
| Saved problems | ❌ | ❌ | ❌ |
| AI chat sidebar | ✅ | ✅ | ⚠️ |
| Phone pairing | ✅ | ✅ | ⚠️ Needs separate realtime deploy |
| Photo answer upload (NVO) | ✅ | ✅ | ⚠️ |
| Streaks + badges | ✅ | ⚠️ | ⚠️ Badge schema migration pending |
| Settings (theme, layout) | ✅ | — | ✅ |
| App-wide i18n (en/bg) | ❌ | — | ❌ Only LoginPage has local lang toggle |
| Premium upgrade | ⚠️ Demo | ❌ Stub | ❌ |

### Platform / ops

| Area | Status |
|------|--------|
| Automated tests | ❌ None (FE or BE) |
| DB migrations (Alembic) | ❌ Scaffold only; `create_all()` at runtime |
| CI/CD pipeline | ❌ Not configured |
| Error monitoring (Sentry etc.) | ❌ File logs only |
| Admin panel | ❌ Dev endpoints only |
| Email notifications | ❌ |
| GDPR / privacy policy pages | ❌ |
| Terms of service (linked from login) | ⚠️ Text only, no dedicated page |

---

## 4. Production Blockers (Must Fix)

> **Re-verified 2026-09-19** by reading current source (not by trusting prior doc text). Status legend: ✅ confirmed fixed with file:line evidence · ⚠️ still open · ❓ not reverified this pass.

These items block a safe, reliable public launch. Fix before marketing to real schools.

### P0 — Security & data integrity

1. **Rotate secrets** — ✅ `backend/app/config.py:77-104` `_resolve_secret_key()` now hard-fails startup in production if `SECRET_KEY` is empty, a known placeholder, or under 32 chars. ⚠️ `GOOGLE_CLIENT_ID` is still hardcoded as a fallback default in both `backend/app/config.py:47` and `frontend/src/config/google.ts:1-3` (`import.meta.env.VITE_GOOGLE_CLIENT_ID || '845529…'`) — low severity (client IDs aren't secret) but doesn't match "env vars only."
2. **Protect admin endpoints** — ✅ Fixed. `require_admin` (backend/app/auth/dependencies.py:95) + `users.is_admin` column now gate `/admin/migrate` (health.py:22-23), `/progress/admin/reset-all-xp` (progress.py:509-512), `/nvo/admin/reset-all-xp` (nvo.py:805-808), plus `bug_report.py`, `error_logs.py`, `curriculum.py`, `auth.py` admin routes.
3. **Enforce auth on paid features** — ✅ Fixed. `auth/dependencies.py:150` comment confirms the old `_optional_limit_check` bypass was replaced with mandatory `require_ai_chat` / `require_nvo_exam` / `require_image_scan` dependencies.
4. **Fix CORS** — ✅ Fixed. `main.py:75` uses `allow_origins=settings.CORS_ORIGINS`; the manual middleware (`main.py:55-66`) now reflects only allow-listed origins instead of stamping `*`.
5. **Fix logout** — ✅ Fixed. `frontend/src/services/api.ts:59-60` and `context/AuthContext.tsx:97-102` clear both `token` and `user` (plus stale dashboard/XP caches) on 401 and on explicit logout.
6. **Add route guards** — ✅ Fixed. `frontend/src/components/RequireAuth.tsx` + `App.tsx:60` wrap protected routes; unauthenticated visitors are redirected, with the visited path preserved (`utils/redirect.ts`).
7. **Disable or gate dev endpoints** — ✅ Fixed. `/bug-report/recent` (bug_report.py:106) and `/log-error/recent` (error_logs.py:46) now require `require_admin`.

### P0 — Serverless compatibility

8. **Persist NVO generation state** — ✅ Fixed. `nvo.py` now calls `nvo_exam_store.save_job/load_job/save_exam/load_exam`; no more in-memory `GENERATION_JOBS`/`GENERATED_EXAMS` dicts.
9. **Persist mobile upload/SSE state** — ✅ Fixed (2026-09-19). `upload_history` and `task_contexts` were still module-level dicts, and this was the worst instance of the class: both halves of the pairing flow are requests *from different devices*, so on serverless they were always read from an instance that had never seen the write. The desktop registered an answer key via `POST /mobile/tasks/context`; the phone's `POST /mobile/tasks/grade-photo` landed elsewhere and returned `404 Task context not found`. The phone uploaded a photo; the desktop polled `GET /mobile/uploads/latest` and saw nothing. Phone grading could not have worked in production at all. Both now persist through `app/services/channel_state_store.py` (`record_upload:97`, `save_task_context:194`) into `mobile_upload_records` / `mobile_task_contexts` (migration `b8c9d0e1f2a3`), on the same TTL clock as media retention, with `nvo_exam_store`'s failure policy: reads fall back to the in-process cache, writes log at ERROR rather than throwing away an upload the student already paid a scan credit for. 18 tests in `backend/tests/test_channel_state_store.py` drop the cache between write and read to reproduce the cross-instance case.

   ⚠️ **Still open: SSE fanout across instances.** `stream_subscribers` (`mobile_uploads.py:103`) deliberately stays in memory — an `asyncio.Queue` cannot be serialised and each SSE connection belongs to the one process holding it open. An event published on instance A still never reaches a subscriber on instance B. Correct fanout needs a broker (Redis pub/sub, or the existing realtime server). The clients' `/mobile/uploads/latest` polling is now durable, so the stream is a same-instance fast path rather than the only delivery route — the feature degrades instead of failing.
10. **External file storage** — ❓ Not reverified this pass.
11. **Rate limiter path mismatch** — ✅ Fixed. `ip_rate_limiter.py:20-27` `_GUARDED_PREFIXES` now matches real mount points (`/ai/`, `/nvo/`, `/mobile/`, `/curriculum/lessons/`, `/exercises/`).

### P0 — Database

12. **Real migrations** — ✅ Mostly fixed. ⚠️ **`alembic upgrade head` had never actually run to completion** — found and fixed 2026-09-19. The guest-users revision dropped a NOT NULL with a bare `op.alter_column`, which PostgreSQL accepts and SQLite cannot parse (`near "ALTER": syntax error`), so the chain died on revision 2 of 9 on every SQLite database — i.e. every local dev environment. Nothing caught it because the test suite builds its schema with `Base.metadata.create_all` and never ran the migrations. Now uses `op.batch_alter_table` (`alembic/versions/a1b2c3d4e5f6_guest_users.py:33,54`), which rebuilds the table on SQLite and emits the plain ALTER on PostgreSQL. `test_migrations.py::test_the_whole_chain_runs_on_a_fresh_database` walks the real chain against a throwaway database and fails without the fix. Alembic exists with a real baseline migration (`backend/alembic/versions/754e61405945_baseline_schema.py`). `main.py:42-53` still calls `Base.metadata.create_all()` at startup, but it's now guarded by an `_db_initialized` flag (runs once per process, not per request) and errors are logged instead of silently swallowed. ⚠️ Companion-session tables in `supabase_schema.sql` not reverified.
13. **Badge schema** — ✅ Fixed going forward. `badge_key` is in the Alembic baseline migration (`754e61405945_baseline_schema.py:81`). `progress_service.py:473-475` keeps a defensive try/except as a safety net for pre-Alembic databases only — no longer a swallowed-error bug, just a deliberate legacy fallback.
14. **Production PostgreSQL** — ✅ Fixed. The SQLite default in `config.py:15` is now only a dev convenience: `_resolve_database_url()` (`config.py:130-157`) hard-fails startup in production if `DATABASE_URL` is unset, exactly as `_resolve_secret_key` does, so a prod deploy can no longer silently boot on an ephemeral SQLite file.

### P1 — Payments & accounts

15. **Stripe integration** — ⚠️ Still open (by design). `backend/app/routers/plan.py:42-58` `POST /plan/upgrade` now deliberately returns `402` with a Bulgarian "not yet active" message instead of granting premium — safe, but Stripe still needs to be built.
16. **Decide on email auth** — ❓ Not reverified this pass.

### P1 — Deployment wiring

17. **Deploy realtime server** — ❓ Not reverified this pass.
18. **Fix env var naming drift** — ✅ Fixed. `DEPLOYMENT.md:42-45,132-142` now documents `SECRET_KEY` and `CORS_ORIGINS`, matching what `config.py:19,34` actually reads, and `DEPLOYMENT.md:51` explicitly warns that the old `JWT_SECRET` / `ALLOWED_ORIGINS` names silently misconfigure a deploy.
19. **Google OAuth production origins** — ❓ Not reverified this pass.
20. **Port consistency** — ❓ Not reverified this pass.

### Net effect

Of the 20 original P0/P1 blockers, **16 are now confirmed fixed** (12 previously,
plus #9 mobile upload/task-context persistence, #14 Postgres-in-prod, #18 env-var
doc drift, and the migration-chain half of #12). Two are confirmed still open —
the Stripe stub (#15, deliberate) and the SSE cross-instance fanout carved out of
#9 — plus the low-severity hardcoded Google client ID under #1.

Six were **not** reverified in this pass and should not be treated as green:
external file storage (#10), companion-session tables in `supabase_schema.sql`
(#12), the email-auth decision (#16), realtime-server deployment (#17), OAuth
production origins (#19) and port consistency (#20). Re-check these before a
launch go/no-go.

---

## 5. Phased Next Steps

### Phase 1 — Launchable MVP (2–4 weeks)

**Goal:** Safe, stable deployment for beta users (single classroom / pilot).

- [ ] PostgreSQL on Supabase with `supabase_schema.sql` + companion tables
- [ ] Alembic initial migration; remove runtime `create_all()` from hot path
- [ ] Env-based secrets; no hardcoded OAuth client IDs
- [ ] CORS locked to production + localhost
- [ ] Route guards + fix logout (clear `token` + `user` + caches)
- [ ] Protect all admin/dev endpoints (env flag or admin role)
- [ ] Require JWT for AI/NVO/upload limit enforcement
- [ ] Move NVO job state to DB or Redis
- [ ] Basic smoke tests: auth, curriculum read, exercise submit, NVO generate
- [ ] Deploy frontend + backend to Vercel; verify `/_/backend/docs`
- [ ] Privacy policy + terms pages (even minimal)
- [ ] Error boundary + user-facing "something went wrong" on API failures

### Phase 2 — Monetization & polish (2–3 weeks)

**Goal:** Ready to charge teachers/schools or offer freemium sustainably.

- [ ] Stripe Checkout + webhook → `users.plan = premium`
- [ ] Server-side NVO exam history table (replace localStorage as source of truth)
- [ ] Persist saved problems (backend table + API + UI)
- [ ] Wire NVO short format (`NVOFormatSelector` → `createNVOGenerationJob({ format })`)
- [ ] NVO history UX: "Недовършен" status, cap at 10, richer review breakdown
- [ ] App-wide Bulgarian copy (respect `SettingsContext.language`)
- [ ] Complete dark mode on Classic dashboard and older pages
- [ ] Sentry or similar for FE + BE errors
- [ ] Deploy realtime server; enable pairing for premium or all users

### Phase 3 — Scale & school readiness (ongoing)

**Goal:** Multiple schools, teacher visibility, reliability under load.

- [ ] Teacher/admin dashboard (class progress, assign missions)
- [ ] Redis for rate limiting + NVO job queue (replace in-memory)
- [ ] CDN/object storage for uploads
- [ ] Comprehensive test suite (pytest + Playwright)
- [ ] CI: lint, test, preview deploys on PR
- [ ] Performance: dashboard cache invalidation strategy, API pagination
- [ ] Accessibility audit (WCAG basics for student UI)
- [ ] Offline / PWA consideration for rural/low-bandwidth students
- [ ] Content moderation pipeline for AI-generated exercises
- [ ] Remove or fully hide `PlaygroundPage` and dev-only UI from production builds

---

## 6. Product Backlog (Remaining Features)

**Re-verified 2026-09-09 against actual code** (see `REMAINING_FEATURES.md` for full detail).

| # | Feature | Status | Next action |
|---|---------|--------|-------------|
| 1 | Saved problems (practice + NVO) | ❌ Not started — confirmed zero matches for `saved_problem`/`SavedProblem` anywhere in repo | Design `saved_problems` table; add save button on exercise + NVO question UI; list in jump bar |
| 2 | NVO flow lock on refresh | ✅ Done — `NVOPracticeExamPage.tsx:97,459-480` restores `nvo-practice-state-v1` on mount | QA edge cases: tab close, expired generation job, guest user |
| 3 | NVO short + full modes | ✅ Done (2026-09-09) — `NVOFormatSelector` now rendered in the pre-exam modal; format drives generation, timer duration, and history metadata; verified live (short format → 16Q/30:00 timer) | None |
| 4 | NVO difficulty + XP multipliers | ✅ Done — `NVODifficultySelector` rendered in a modal (`:1457-1476`), feeds `startNewExam(selectedDifficulty)`, XP shows `difficulty_multiplier` (`:1786-1788`) | None — fully wired end-to-end |
| 5 | NVO history improvements | ⚠️ Partial — "Недовършен" flair and cap-at-10 (`MAX_HISTORY_ATTEMPTS`) both done; history is still `localStorage`-only, not server-persisted | Add server-side history table + API; keep localStorage as offline cache only |
| 6 | Mission-to-practice routing | Not found broken — spot check of `mission.route` / `navigate(mission.route)` found no inconsistency, but a full audit of every mission definition wasn't done | Skip unless a specific routing bug is reported |
| 7 | Badge schema migration | ✅ Done for new/migrated DBs — `badge_key` is in the Alembic baseline migration; `progress_service.py:473-475` fallback is now a deliberate legacy-DB safety net, not a bug | Low priority: remove fallback once all environments confirmed on Alembic baseline |

### Additional product ideas (not in original backlog)

- **Email auth** — only if schools require non-Google accounts
- **Classroom codes** — teacher creates class, students join
- **Parent progress email** — weekly summary
- **Printable NVO results** — PDF export of attempt review
- **Curriculum admin UI** — edit topics/lessons without seed scripts
- **Bulgarian voice read-aloud** — accessibility for theory pages

---

## 7. Deployment Checklist

### Vercel (frontend + backend)

- [ ] Repo connected; `vercel.json` experimental services enabled
- [ ] `npm run build` succeeds (root `package.json` builds frontend)
- [ ] `VITE_API_URL` = `https://<domain>/_/backend`
- [ ] `VITE_GOOGLE_CLIENT_ID` set
- [ ] `VITE_GOOGLE_AUTH_ORIGIN` = production origin
- [ ] Backend env: `DATABASE_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `ENVIRONMENT=production`, `DEBUG=False`
- [ ] Smoke test: login → dashboard → start exercise → submit
- [ ] Smoke test: NVO generate → complete → XP awarded

### Realtime server (separate)

- [ ] Deploy `realtime-server/` to Railway/Render
- [ ] `VITE_REALTIME_URL` / `VITE_SOCKET_URL` set in Vercel
- [ ] CORS on realtime server allows production frontend origin
- [ ] Smoke test: pairing code appears in navbar → phone connects at `/controller`

### Supabase / PostgreSQL

- [ ] Run `supabase_schema.sql` + companion tables migration
- [ ] Seed curriculum (`seed_curriculum.py` / `seed_data.py`) on empty DB
- [ ] Connection pooling configured (NullPool on serverless is already in code)
- [ ] Backups enabled

### Google Cloud

- [ ] OAuth consent screen published (or in testing with test users)
- [ ] Authorized JavaScript origins: `localhost:5173`, production domain
- [ ] Authorized redirect URIs if using redirect flow

### OpenAI

- [ ] API key with spending limits
- [ ] Models: `gpt-4o-mini` (chat/theory), `gpt-4.1` (NVO), `gpt-4o` (vision) — confirm availability

---

## 8. Environment & Configuration

### Frontend (`frontend/.env.example`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_URL` | Yes (prod) | `/api` dev, `/_/backend` prod |
| `VITE_GOOGLE_CLIENT_ID` | Yes | Google Sign-In |
| `VITE_GOOGLE_AUTH_ORIGIN` | Recommended | OAuth origin normalization |
| `VITE_REALTIME_URL` | For pairing | WebSocket server URL |
| `VITE_SOCKET_URL` | Alt to above | Socket.IO endpoint |
| `VITE_YOUTUBE_KEY` | Optional | Theory page video search |

### Backend (`backend/.env.example`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes (prod) | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing — **must change** |
| `GOOGLE_CLIENT_ID` | Yes | Token verification |
| `OPENAI_API_KEY` | Yes for AI | Without it, fallbacks activate |
| `OPENAI_MODEL` | Optional | Default `gpt-4o-mini` |
| `OPENAI_NVO_MODEL` | Optional | Default `gpt-4.1` |
| `ENVIRONMENT` | Recommended | `production` |
| `DEBUG` | Recommended | `False` in prod |
| `CORS_ORIGINS` | ⚠️ Not wired | Should be implemented |

### Known doc vs code mismatches

| Document says | Code actually uses |
|---------------|-------------------|
| `JWT_SECRET` | `SECRET_KEY` |
| `ALLOWED_ORIGINS` | Hardcoded `*` CORS |
| Email/password auth (README) | Google OAuth only |
| React 18 (README) | React 19 |

---

## 9. Security Hardening

| Risk | Current state | Target state |
|------|---------------|--------------|
| JWT secret | Default placeholder in repo | Strong random secret in env only |
| Admin XP reset | Public or any authenticated user | Admin role + audit log |
| Free premium | `POST /plan/upgrade` no payment | Stripe webhook only |
| CORS | `*` | Explicit origin list |
| Rate limiting | In-memory, wrong paths | Redis-backed, correct route prefixes |
| File uploads | 10 MB cap, local disk | S3 + virus scan (optional) |
| AI prompt injection | Basic | Input sanitization, output filtering for student content |
| Guest data leakage | Caches cleared on guest login | ✅ Already clears `dashboard_cache_v1`, `xp_summary_cache` |
| PII in logs | Redaction in bug reports | Extend to all log paths |
| HTTPS | Vercel default | Enforce; HSTS |

---

## 10. Testing Strategy

**Current state:** No automated tests.

### Recommended minimum before production

| Layer | Tool | Priority tests |
|-------|------|----------------|
| Backend unit | pytest | XP calculation, freemium limits, answer grading |
| Backend API | pytest + httpx | Auth flow, curriculum endpoints, exercise submit |
| Frontend unit | Vitest | `userIdentity`, streak logic, NVO state restore |
| E2E | Playwright | Login (Google mock) → exercise → dashboard XP update |
| Manual QA script | Checklist | NVO full flow, guest mode, dark mode, mobile upload |

### Critical manual QA scenarios

1. Google login on production domain
2. Guest → browse → prompted to login for progress-saving features
3. Start NVO → refresh mid-exam → resume same exam
4. Complete NVO → XP increases → level-up modal
5. Hit free tier limit → upgrade prompt appears
6. Dark mode: navbar, sidebar, dashboard, NVO page readable
7. Phone pairing: code display → controller connect → photo appears in exam
8. Logout → cannot access authenticated API calls
9. Cold start on Vercel: NVO generation still completes (after Phase 1 DB fix)

---

## 11. Technical Debt & Doc Drift

| Item | Location | Status (2026-09-09) | Action |
|------|----------|------|--------|
| `passlib[bcrypt]` unused | `requirements.txt` | ❓ Not reverified | Remove or implement email auth |
| `create_all()` on every request | `backend/app/main.py` | ⚠️ Partially fixed — now runs once per process via `_db_initialized` guard (`main.py:40-53`), not per request; errors logged instead of swallowed | Fully remove after migrations are the only schema source |
| Outdated backend README | `backend/README.md` | ❓ Not reverified | Update (JWT "ready to implement" is false) |
| Outdated frontend README | `frontend/README.md` | ❓ Not reverified | Update routes + React version |
| Outdated root README | `README.md` | ❓ Not reverified | Fix auth section, React version |
| `DEPLOYMENT.md` env names | Root | ⚠️ Confirmed still wrong — `DEPLOYMENT.md:44,128` say `JWT_SECRET`/`ALLOWED_ORIGINS`; code uses `SECRET_KEY`/`CORS_ORIGINS` (`config.py:19,34`) | Align doc with `config.py` |
| `rewrite_login_page.py` | `frontend/` | ❓ Not reverified | Delete or move to scripts |
| Hardcoded Google client ID | `config.py:47`, `google.ts:1-3` | ⚠️ Confirmed still hardcoded as fallback default in both files | Env only (low severity — client IDs aren't secret) |
| In-memory analytics/feedback | Backend routers | ❓ Not reverified | Move to DB or external service |
| `PlaygroundPage` 4700+ lines | Dev only | ⚠️ Confirmed unchanged — still exactly 4,736 lines | Split or exclude from prod bundle |
| Login page always dark | `LoginPage.tsx` | ❓ Not reverified | Consider respecting global theme |

---

## 12. Success Criteria for Launch

### Beta launch (Phase 1 complete)

- [ ] 10+ pilot students complete full NVO practice exam without data loss
- [ ] No unauthenticated access to admin endpoints
- [ ] All secrets in environment variables
- [ ] PostgreSQL is single source of truth for users, progress, curriculum
- [ ] Error rate < 5% on core flows (login, exercise submit, NVO generate)
- [ ] Privacy policy and terms linked from login

### Public launch (Phase 2 complete)

- [ ] Stripe payments working; free tier limits enforced server-side
- [ ] NVO history persisted server-side
- [ ] Realtime pairing available in production
- [ ] Monitoring alerts on API 5xx errors
- [ ] Bulgarian UI consistent (or explicit "BG only" for v1)
- [ ] Dark mode complete on all student-facing pages

### School-ready (Phase 3)

- [ ] Teacher can view class aggregate progress
- [ ] 99% uptime over 30 days
- [ ] Automated test suite runs on every PR
- [ ] GDPR-compliant data export/delete for student accounts

---

## Quick Reference — What to Work on Next

If you have **one week**, do this in order:

1. Secrets + CORS + admin endpoint protection  
2. Route guards + logout fix  
3. PostgreSQL + Alembic migration  
4. NVO job persistence (DB)  
5. Deploy to Vercel + smoke tests  
6. Terms/privacy pages  

If you have **one month**, add:

7. Stripe  
8. NVO server-side history  
9. Saved problems  
10. Short NVO mode wiring  
11. Realtime server deploy  
12. Sentry + basic pytest  

---

*Generated from full codebase inspection. Update this file when phases complete or priorities shift.*
