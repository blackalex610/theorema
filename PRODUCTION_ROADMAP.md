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
| NVO attempt history + review | ⚠️ Partial | Last 10 in localStorage; unfinished badge + resume; review mode exists |
| AI chat tutor | ✅ Done | Global sidebar; context shortcuts on theory/exercise/NVO pages |
| Google OAuth login | ✅ Done | JWT stored in `localStorage` |
| Guest mode | ✅ Done | Browse with zeroed/mock data; no token |
| Freemium plan limits UI | ✅ Done | AI exercises, chat, NVO, image scans — counters in sidebar |
| Dark mode | ⚠️ Partial | Settings toggle; coach dashboard + navbar fixed; classic pages lighter |
| Bug reporting + analytics events | ✅ Done | File-based backend logging (MVP) |
| Mobile photo capture + grading | ✅ Done | `/mobile-capture`, SSE live feed |
| Phone pairing (desktop ↔ phone) | ⚠️ Partial | Works when realtime server is deployed; experimental in Settings |

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

These items block a safe, reliable public launch. Fix before marketing to real schools.

### P0 — Security & data integrity

1. **Rotate secrets** — Replace default `SECRET_KEY`, remove hardcoded `GOOGLE_CLIENT_ID` from `backend/app/config.py` and `frontend/src/config/google.ts`; use env vars only.
2. **Protect admin endpoints** — `POST /progress/admin/reset-all-xp` has no auth; `POST /nvo/admin/reset-all-xp` has no role check; `POST /admin/migrate` is public.
3. **Enforce auth on paid features** — `_optional_limit_check` still allows anon bypass on **AI chat, NVO, and image uploads**. ✅ Fixed for **AI theory** and **AI exercises** generation.
4. **Fix CORS** — `CORS_ORIGINS` in config is unused; app sets `Access-Control-Allow-Origin: *`. Wire config and restrict to production domain.
5. **Fix logout** — Frontend `handleLogout` removes `user` but not `token`; 401 interceptor may behave inconsistently.
6. **Add route guards** — Unauthenticated users can open `/dashboard`, `/nvo/practice`, etc. Redirect to `/login` when no valid session (allow guest explicitly).
7. **Disable or gate dev endpoints** — `/bug-report/recent`, `/feedback/summary`, `/log-error/recent` exposed without admin auth.

### P0 — Serverless compatibility

8. **Persist NVO generation state** — `GENERATION_JOBS` and `GENERATED_EXAMS` are in-memory dicts; lost on Vercel cold start / multi-instance.
9. **Persist mobile upload/SSE state** — `upload_history`, `stream_subscribers`, `task_contexts` are in-process only.
10. **External file storage** — Uploads and logs write to local FS (`app/uploads/`, log files); Vercel FS is ephemeral/read-only. Move to S3/Supabase Storage.
11. **Rate limiter path mismatch** — IP rate limiter checks `/api/ai/` but actual routes are `/ai/`; likely ineffective everywhere.

### P0 — Database

12. **Real migrations** — Stop relying on `Base.metadata.create_all()` per request. Generate Alembic revisions; include `companion_sessions` tables missing from `supabase_schema.sql`.
13. **Badge schema** — Ensure `user_badges.badge_key` exists in all environments (see `REMAINING_FEATURES.md` #7).
14. **Production PostgreSQL** — SQLite + `/tmp` on Vercel is a dev fallback only; require `DATABASE_URL` pointing to Supabase/Postgres in prod.

### P1 — Payments & accounts

15. **Stripe integration** — Replace demo `POST /plan/upgrade` with webhook-verified subscription flow.
16. **Decide on email auth** — Either remove register UI or implement properly; current state confuses users.

### P1 — Deployment wiring

17. **Deploy realtime server** — Set `VITE_REALTIME_URL` / `VITE_SOCKET_URL` to Railway/Render instance; document in Vercel env.
18. **Fix env var naming drift** — `DEPLOYMENT.md` says `JWT_SECRET`, `ALLOWED_ORIGINS`; code uses `SECRET_KEY`, ignores `CORS_ORIGINS`.
19. **Google OAuth production origins** — Add Vercel domain to Google Cloud Console authorized origins.
20. **Port consistency** — `start.ps1` uses 8000; README/Vite proxy use 8001; align scripts.

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

Status as of codebase review. Original list: `REMAINING_FEATURES.md`.

| # | Feature | Status | Next action |
|---|---------|--------|-------------|
| 1 | Saved problems (practice + NVO) | ❌ Not started | Design `saved_problems` table; add save button on exercise + NVO question UI; list in jump bar |
| 2 | NVO flow lock on refresh | ✅ Mostly done | QA edge cases: tab close, expired generation job, guest user |
| 3 | NVO short + full modes | ⚠️ Partial | Wire `NVOFormatSelector` in `NVOPracticeExamPage`; pass `format` to API; save in history metadata |
| 4 | NVO difficulty + XP multipliers | ✅ Done | Verify hard mode question difficulty in generator |
| 5 | NVO history improvements | ⚠️ Partial | Add `status: unfinished` flair; server persistence; cap display at 10; scoring breakdown in review |
| 6 | Mission-to-practice routing | ⚠️ Partial | Audit all `mission.route` values; test `?mission_id=` deep links; align backend mission definitions |
| 7 | Badge schema migration | ❌ Not done | Alembic migration for `user_badges.badge_key`; remove runtime fallback in `progress_service.py` |

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

| Item | Location | Action |
|------|----------|--------|
| `passlib[bcrypt]` unused | `requirements.txt` | Remove or implement email auth |
| `create_all()` on every request | `backend/app/main.py` middleware | Remove after migrations |
| Outdated backend README | `backend/README.md` | Update (JWT "ready to implement" is false) |
| Outdated frontend README | `frontend/README.md` | Update routes + React version |
| Outdated root README | `README.md` | Fix auth section, React version |
| `DEPLOYMENT.md` env names | Root | Align with `config.py` |
| `rewrite_login_page.py` | `frontend/` | Delete or move to scripts |
| Hardcoded Google client ID | `config.py`, `google.ts` | Env only |
| In-memory analytics/feedback | Backend routers | Move to DB or external service |
| `PlaygroundPage` 4700+ lines | Dev only | Split or exclude from prod bundle |
| Login page always dark | `LoginPage.tsx` | Consider respecting global theme |

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
