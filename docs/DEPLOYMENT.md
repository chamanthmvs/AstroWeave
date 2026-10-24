# Deploying AstroWeave (free tier)

AstroWeave runs on free plans end to end. The LLM API (Anthropic) is the only
paid dependency, and that cost is separate from hosting.

- **Backend + chart service** → Render (free web services + free Postgres),
  provisioned from [`render.yaml`](../render.yaml).
- **Frontend** → Vercel (free), once the Next.js UI lands.

Nothing here requires you to hand-create a database: the blueprint provisions
Postgres and injects `DATABASE_URL` automatically.

## 1. Backend on Render

1. Push this repo to GitHub.
2. On Render: **New + → Blueprint**, select the repo. Render reads `render.yaml`
   and creates `astroweave-db` (Postgres), `astroweave-api`, and
   `astroweave-chart`.
3. After the first deploy, set the dashboard values marked `sync: false`:
   - `ANTHROPIC_API_KEY` — your Anthropic key.
   - `ASTROWEAVE_CHART_SERVICE_URL` — the chart service's URL
     (`https://astroweave-chart.onrender.com`, or whatever Render named it).
   - `ASTROWEAVE_ADMIN_EMAILS` — your email, so you can open `/admin`.
   - `ASTROWEAVE_CORS_ORIGINS` — your Vercel URL (e.g. `https://astroweave.vercel.app`).
   - `ASTROWEAVE_CORS_ORIGIN_REGEX` *(optional)* — to allow Vercel preview URLs,
     e.g. `^https://astroweave-.*\.vercel\.app$`.
   - `ASTROWEAVE_PUBLIC_WEB_URL` — your Vercel URL (used in email links).
4. Redeploy. `DATABASE_URL` and `ASTROWEAVE_AUTH_SECRET` are wired automatically.

Free Render services sleep after ~15 min idle and cold-start on the next
request; the first call after a nap is slow. Free Postgres has a limited
lifetime — see **Durable database** below.

## 2. Database: local vs cloud

The app chooses its database from `DATABASE_URL`:

- **Unset** (local dev, tests) → a SQLite file at `app/data/astroweave.db`. Zero
  setup.
- **Set** → Postgres. The whole app (auth/users, conversations, rate limits,
  and the usage data behind the admin dashboard) uses it.

A `postgres://` URL is normalized automatically to the psycopg driver.

### Durable database (optional, still free)

Render's free Postgres expires. For something longer-lived, create a free
[Neon](https://neon.tech) database and copy its connection string into the
`DATABASE_URL` env var on `astroweave-api` (change it from `fromDatabase` to a
literal value). No code change; the admin dashboard follows `DATABASE_URL`.

## 3. Email (optional, free)

Email verification and password reset work without any email provider: in the
default `console` backend the link is logged (and reset links are also available
to an admin via `POST /admin/reset-token`). Signup is never blocked.

To send real email for free, set on `astroweave-api`:

```
ASTROWEAVE_EMAIL_BACKEND=smtp
ASTROWEAVE_SMTP_HOST=smtp.gmail.com
ASTROWEAVE_SMTP_PORT=587
ASTROWEAVE_SMTP_USER=you@gmail.com
ASTROWEAVE_SMTP_PASSWORD=<gmail app password>   # free; create under Google Account → App passwords
ASTROWEAVE_EMAIL_FROM=you@gmail.com
```

To require a verified email before `/run`, set
`ASTROWEAVE_REQUIRE_EMAIL_VERIFICATION=true` (leave it `false` until SMTP is on,
so nobody is locked out).

## 4. Environment variable reference

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | auto / manual | SQLite (unset) or Postgres (set) |
| `ASTROWEAVE_AUTH_SECRET` | auto (generated) | HMAC signing for tokens; **required in production** |
| `ANTHROPIC_API_KEY` | manual | LLM provider key |
| `ASTROWEAVE_CHART_SERVICE_URL` | manual | URL of the chart service |
| `ASTROWEAVE_ADMIN_EMAILS` | manual | comma-separated admin allowlist |
| `ASTROWEAVE_CORS_ORIGINS` | manual | comma-separated allowed frontend origins |
| `ASTROWEAVE_CORS_ORIGIN_REGEX` | optional | regex for preview origins |
| `ASTROWEAVE_PUBLIC_WEB_URL` | manual | base URL used in email links |
| `ASTROWEAVE_EMAIL_BACKEND` | `console`/`smtp` | email delivery mode |
| `ASTROWEAVE_SMTP_*`, `ASTROWEAVE_EMAIL_FROM` | optional | SMTP settings |
| `ASTROWEAVE_REQUIRE_EMAIL_VERIFICATION` | optional | gate `/run` on verified email |
| `ASTROWEAVE_RATE_LIMIT_PER_DAY` | optional | per-user daily `/run` cap (default 50) |
