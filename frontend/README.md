# Frontend

Next.js site with the UIs of three [backend](../backend/README.md) apps: plants, political-culture and cfflch. The first page of each app (`/plants`, `/political-culture`, `/cfflch`) is its login, which only asks for a name that already exists in the backend.

## Running locally
Needs Node.js 22 (`nvm use 22`) and the backend running. Create `frontend/.env`:

```
NEXT_PUBLIC_SERVER_URL=http://localhost:8000
SESSION_SECRET=<random string, e.g. openssl rand -base64 32>
```

Then:

```
npm ci
npm run dev         # http://localhost:3000
npm run lint
npm run typecheck
```

`NEXT_PUBLIC_SERVER_URL` is baked into the browser code by `next build`, so it must be set at build time; `next.config.ts` refuses to start without it.

## Deployment
Railway deploys `main` (Root Directory `/frontend`). Pull requests run lint and typecheck in CI.

Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).
