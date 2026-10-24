# AstroWeave web (Next.js)

The redesigned frontend — a Next.js App Router app, dependency-light, dark
"celestial minimal" theme with one vivid aqua accent. Four tabs:

- **Ask** — the multi-agent reading (`POST /run`)
- **Kundli Matching** — North Guna Milan + South poruthams + Manglik (`POST /match`)
- **My Chart** — deterministic classical profile (`GET /me/chart`, `/me/profile`)
- **Star Atlas** — the 27 nakshatras: symbol, North & South names, deity, ruler,
  gana, yoni, nadi, span (`GET /nakshatras`)

Stack: Next.js 16 (App Router) · React 19 · TypeScript. No UI framework —
hand-written CSS design system in `app/globals.css`.

## Run locally

Needs Node 20.9+.

```bash
cd web
cp .env.example .env.local        # point NEXT_PUBLIC_API_BASE at the backend
npm install
npm run dev                       # http://localhost:3000
```

The backend must be running (default `http://127.0.0.1:8000`) with its CORS
origins allowing `http://localhost:3000` (the dev default already does).

## Deploy (Vercel, free)

1. Import the repo on Vercel; set the project root directory to `web`.
2. Set `NEXT_PUBLIC_API_BASE` to the Render backend URL.
3. On the backend, set `ASTROWEAVE_CORS_ORIGINS` to the Vercel URL (and
   `ASTROWEAVE_PUBLIC_WEB_URL` to the same, for email links).
