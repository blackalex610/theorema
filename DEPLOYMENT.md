# Deployment Guide — Vercel

This guide explains how to deploy the Математика project to Vercel using the experimental services feature for monorepo support.

## Prerequisites

1. **GitHub Repository**: Push your code to GitHub (see README for instructions)
2. **Vercel Account**: Create a free account at https://vercel.com
3. **Environment Variables**: Have these ready to configure in Vercel

## Deployment Steps

### Step 1: Connect to Vercel

1. Go to https://vercel.com/new
2. Click "Continue with GitHub"
3. Authorize Vercel to access your GitHub account
4. Select your `smartnvo` repository
5. Click "Import"

### Step 2: Configure Project Settings

**Root Directory**: Leave as default (root of repo)

**Build & Development Settings**:
- Build Command: `npm run build`
- Install Command: `npm install`
- Output Directory: `frontend/dist`

### Step 3: Set Environment Variables

Add the following environment variables in Vercel dashboard:

#### Frontend Environment Variables
```
VITE_API_URL=https://your-deployment-url/_/backend
VITE_REALTIME_URL=your-realtime-server-url
```

#### Backend Environment Variables
```
DATABASE_URL=your-postgresql-connection-string
OPENAI_API_KEY=your-openai-api-key
SECRET_KEY=your-jwt-signing-key
CORS_ORIGINS=https://your-deployment-url
GOOGLE_CLIENT_ID=your-google-oauth-client-id
ENVIRONMENT=production
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

`CORS_ORIGINS` takes one origin or a comma-separated list, with no trailing
slash. The frontend and backend share one origin on Vercel (`/_/backend` is a
path, not a host), so list only *other* origins that call the API, e.g. a
custom domain. Before 2026-09-24 only a JSON list worked, and the plain form
shown here crashed the backend at startup.

`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are required for photo uploads —
see [Photo storage](#photo-storage-supabase) below. Without them the app runs,
but photo uploads return 503.

<!-- These are the names the code actually reads (app/config.py) — a deploy
     that follows outdated names like JWT_SECRET or ALLOWED_ORIGINS silently
     falls back to defaults instead of erroring, which is worse. -->

### Step 4: Deploy

Click "Deploy" and Vercel will:
1. Install dependencies for frontend and backend
2. Build the frontend (Vite)
3. Set up the backend as serverless functions
4. Deploy everything together

## Photo storage (Supabase)

Students photograph their written answers. Vercel's function disk is
read-only and not shared between instances, so photos go to a private
Supabase Storage bucket (`backend/app/services/media_storage.py`):

1. Supabase dashboard → **Storage** → **New bucket**, named `homework-photos`
   (or set `SUPABASE_STORAGE_BUCKET` to your name). **Leave "Public bucket"
   off.** The backend reads it with the service-role key and hands browsers
   10-minute signed links; nothing else should be able to list it.
2. Project Settings → API: copy the project URL into `SUPABASE_URL` and the
   `service_role` key into `SUPABASE_SERVICE_ROLE_KEY`. This key bypasses
   row-level security, so set it on the backend only, never as a `VITE_`
   variable.
3. Redeploy. Photos are deleted after `MEDIA_RETENTION_HOURS` (default 24) by
   a sweep that runs on upload; `POST /_/backend/mobile/admin/purge-expired-uploads`
   (admin) runs it on demand.

Local development needs none of this: with no Supabase settings, photos are
stored in `backend/app/uploads/` (git-ignored).

## Premium subscriptions (Stripe)

Premium is a monthly Stripe subscription (`backend/app/services/billing.py`).
Until all three `STRIPE_*` variables are set, the upgrade button explains that
payments aren't switched on and `/plan/upgrade` answers 402.

1. **Price.** Stripe dashboard → Product catalogue → add a product ("Smart NVO
   Premium") with a **recurring, monthly** price in EUR. Copy its `price_…` id
   into `STRIPE_PRICE_ID`. The upgrade card reads the amount from Stripe, so
   changing the price there changes it in the app.
2. **Secret key.** Developers → API keys → the secret key into
   `STRIPE_SECRET_KEY`. Start with the test-mode key (`sk_test_…`).
3. **Webhook.** Developers → Webhooks → add endpoint
   `https://<your-domain>/_/backend/plan/webhook` with the events
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated` and `customer.subscription.deleted`. Copy
   its signing secret (`whsec_…`) into `STRIPE_WEBHOOK_SECRET`. The plan only
   ever changes here, after the signature checks out.
4. **Customer portal.** Settings → Billing → Customer portal: activate it and
   allow cancelling and updating the payment method. "Управление на
   абонамента" in the app opens it.
5. **`APP_URL`** = the site's public address (e.g. `https://smartnvo.vercel.app`),
   where Stripe sends the browser back after paying.
6. Redeploy, then buy Premium with test card `4242 4242 4242 4242` (any future
   date, any CVC). The dashboard should say "Premium е активен" within a few
   seconds. When that works, repeat steps 2–3 with the live-mode key and a
   live webhook.

Guests can't subscribe (they are asked to sign in with Google first), so a
subscription is never tied to a session that can be lost. A failed renewal
keeps Premium while Stripe retries; `premium_until` plus a 3-day grace period
switches it off even if a cancellation webhook were missed.

## Database migrations

Alembic owns the schema. On its first request after a cold start the backend
runs `alembic upgrade head` itself, inside one transaction holding a
PostgreSQL advisory lock, so instances starting together don't race. A
database created by older versions of the app (tables but no
`alembic_version`) is detected, brought up to date and stamped automatically.

- To run migrations yourself instead, set `DB_AUTO_MIGRATE=false` and run
  `cd backend && DATABASE_URL=... alembic upgrade head` as a deploy step.
- `POST /_/backend/admin/migrate` (admin only) runs the same migration on demand.
- `GET /_/backend/health/ready` returns 503 while the database is unreachable or
  behind the latest migration. Point your uptime monitor here, not at `/health`.
- New schema changes: `cd backend && alembic revision --autogenerate -m "..."`,
  review the generated file, commit it. Never change the schema any other way.

## Architecture

```
Your Vercel Deployment
├── Frontend (Vite)
│   └── Served at: https://your-deployment-url/
├── Backend API (FastAPI)
│   └── Served at: https://your-deployment-url/_/backend/
└── Real-time Server (separate deployment)
    └── Served at: https://realtime-url/ (separate Node.js hosting)
```

## Post-Deployment

After successful deployment:

1. **Test the Frontend**
   - Visit https://your-deployment-url
   - Check console for any API errors

2. **Test the Backend API**
   - Visit https://your-deployment-url/_/backend/docs
   - Should show FastAPI Swagger documentation
   - Visit https://your-deployment-url/_/backend/health/ready — expect
     `"status": "ready"` (database reachable, schema at head)

3. **Configure Real-time Server**
   - The real-time server (WebSocket) needs separate hosting
   - Options: Railway, Render, AWS EC2, Heroku
   - Update `VITE_REALTIME_URL` with the actual deployment URL

## Troubleshooting

### Issue: Frontend can't reach backend API

**Solution**: Ensure `VITE_API_URL` environment variable is set to the correct Vercel URL with `/_/backend` prefix.

### Issue: CORS errors

**Solution**: Update `CORS_ORIGINS` in backend environment variables to include your Vercel domain.

### Issue: Database connection fails

**Solution**: Verify `DATABASE_URL` is correct and your database is accessible from Vercel (may need to whitelist Vercel IPs or use Vercel Postgres).

### Issue: Photo uploads return 503

**Solution**: Photo storage isn't configured. Set `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` (see "Photo storage") and redeploy. The function
log says `Photo upload attempted with no usable media storage` when this is
the cause; a bucket that exists but rejects the key logs `Storing an uploaded
photo failed`.

### Issue: `/health/ready` reports `schema_behind`

**Solution**: The migration on first request failed; the function log has
`Database migration failed` with the reason. Fix it, then call
`POST /_/backend/admin/migrate` as an admin or redeploy.

### Issue: Missing dependencies

**Solution**: Ensure all Python requirements are in `backend/requirements.txt` and `backend/venv` is in `.gitignore`.

## Environment Variables Reference

### Frontend (.env)

```env
# API endpoint for backend calls
VITE_API_URL=https://your-deployment-url/_/backend

# Real-time server for WebSocket connections
VITE_REALTIME_URL=https://realtime-server-url

# Google OAuth (optional)
VITE_GOOGLE_CLIENT_ID=your-google-client-id

# App name
VITE_APP_NAME=Математика
```

### Backend (environment)

```env
# Database — required in production; the app refuses to start without a real
# value here rather than silently falling back to an ephemeral SQLite file.
DATABASE_URL=postgresql://user:password@host:port/database

# Authentication — required in production (>= 32 chars, not a placeholder);
# the app refuses to start otherwise. ALGORITHM and ACCESS_TOKEN_EXPIRE_MINUTES
# are optional — shown here at their code defaults (app/config.py).
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# API Configuration: one origin or a comma-separated list, no trailing slash
CORS_ORIGINS=https://your-deployment-url,http://localhost:3000

# Schema: migrate to Alembic head on first request (default true)
DB_AUTO_MIGRATE=true

# Homework photo storage — required on Vercel (see "Photo storage" above)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_BUCKET=homework-photos
MEDIA_RETENTION_HOURS=24

# Google OAuth (token verification)
GOOGLE_CLIENT_ID=your-google-oauth-client-id

# AI Service
OPENAI_API_KEY=your-openai-api-key
# Per-attempt timeout and retries for every model call (defaults shown)
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=1
# Optional OpenAI-compatible endpoint, e.g. https://openrouter.ai/api/v1
OPENAI_BASE_URL=
OPENAI_VISION_MODEL=gpt-4o

# Premium subscriptions — see "Premium subscriptions (Stripe)" above
STRIPE_SECRET_KEY=sk_live_or_test_key
STRIPE_WEBHOOK_SECRET=whsec_signing_secret
STRIPE_PRICE_ID=price_monthly_id
APP_URL=https://your-deployment-url

# Error monitoring (optional — omit to leave Sentry disabled entirely)
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.0

# Server
DEBUG=False
ENVIRONMENT=production
```

## Real-time Server Deployment

The real-time server (WebSocket) needs separate hosting since Vercel's serverless functions don't support persistent WebSocket connections.

### Option 1: Railway (Recommended)

1. Go to https://railway.app
2. Connect your GitHub repository
3. Set `Root Directory` to `realtime-server`
4. Add environment variables
5. Deploy

### Option 2: Render

Easiest path is the blueprint: **New → Blueprint**, point it at this repo, and
Render reads `render.yaml` and prompts for the two required secrets.

Creating the service by hand instead:

1. Go to https://render.com
2. New → Web Service
3. Connect GitHub
4. Set `Root Directory` to `realtime-server`
5. Build command `npm install`, start command `npm start`
6. **Add the environment variables below — the service will not start without them**
7. Deploy

#### Required environment variables

| Variable | Value |
|---|---|
| `REALTIME_JWT_SECRET` | Exactly the backend's `SECRET_KEY` |
| `CORS_ORIGINS` | Comma-separated frontend origins, e.g. `https://smartnvo.vercel.app` |
| `ALLOW_LOCAL_NETWORK` | `false` in production |

`REALTIME_JWT_SECRET` must be **byte-identical** to the backend's `SECRET_KEY`.
The realtime server verifies the same HS256 tokens the backend signs, so a
mismatch produces a service that starts cleanly and then rejects every socket
with `UNAUTHORIZED` — which looks nothing like a configuration problem.

Note that on Vercel a *Sensitive* environment variable cannot be read back by
anyone, dashboard or CLI. If `SECRET_KEY` was created that way and was not
saved elsewhere, the only way to get a value you can also give Render is to
rotate it: set a new one on both Vercel and Render, and redeploy both. Rotating
signs out every logged-in user, because tokens last 7 days and there is no
revocation — so do it when nobody is part-way through a 150-minute practice
exam.

#### Troubleshooting

**`❌ REALTIME_JWT_SECRET (or SECRET_KEY) is not set` then `Exited with status 1`**
The variable is missing. This is deliberate — the alternative is a server that
runs but rejects every socket. Add it under Environment and redeploy.

**Sockets rejected with `UNAUTHORIZED` although the service is up**
The secret does not match the backend's, or the backend was not redeployed
after its `SECRET_KEY` changed. Vercel environment changes do not reach a
running deployment until it is redeployed.

**`Blocked disallowed origin` in the logs**
`CORS_ORIGINS` is missing or does not list the frontend's exact origin
(scheme and host must match, no trailing slash).

### Option 3: Heroku

```bash
# Install Heroku CLI and login
heroku create smartnvo-realtime
heroku config:set NODE_ENV=production
git subtree push --prefix realtime-server heroku main
```

## Monitoring & Logs

### View Vercel Logs

1. Go to your Vercel project dashboard
2. Click "Deployments" tab
3. Click on the latest deployment
4. View build logs and runtime logs

### Health checks

- `/_/backend/health` — liveness only (the process answers).
- `/_/backend/health/ready` — database reachable and schema at head; 503
  otherwise. Use this one for uptime alerts.

### View Backend Errors

- Check CloudWatch or Vercel's function logs
- Errors will appear in deployment details

## Performance Tips

1. **Enable Vercel Analytics**: Dashboard → Settings → Analytics
2. **Use Image Optimization**: Vercel automatically optimizes images
3. **Monitor Function Duration**: Keep backend functions under 10s
4. **Use Caching**: Set proper cache headers in frontend

## Limitations & Considerations

- **Function Timeout**: Vercel serverless functions timeout after 10-60 seconds (depending on plan)
- **WebSockets**: Must use separate Node.js hosting for real-time features
- **Database**: Use Vercel Postgres or external PostgreSQL service
- **File Storage**: Photos go to Supabase Storage (see "Photo storage"); the
  function disk is read-only
- **Request size**: Vercel rejects request bodies over 4.5 MB. The frontend
  downscales every photo to 1600 px (~300–500 KB) before sending it

## Support

For Vercel-specific issues, check:
- https://vercel.com/docs
- https://vercel.com/support

For project-specific issues, check the GitHub repository issues.
