# Frontend

Next.js site with the UIs of three [backend](../backend/README.md) apps: plants, political-culture and cfflch. The first page of each app (`/plants`, `/political-culture`, `/cfflch`) is its login, which only asks for a name that already exists in the backend. After 5 wrong names within an hour, the visitor is blocked for an hour.

## Running locally
Needs Node.js 22 (`nvm use 22`) and the backend running. Create `frontend/.env`:

```
NEXT_PUBLIC_SERVER_URL=http://localhost:8000
SESSION_SECRET=<at least 32 random characters, e.g. openssl rand -base64 32>
API_TOKEN_SECRET=<the same value as the backend's API_TOKEN_SECRET>
```

Then:

```
npm ci
npm run dev         # http://localhost:3000
npm run lint
npm run typecheck
```

`NEXT_PUBLIC_SERVER_URL` is baked into the browser code by `next build`, so it must be set at build time; `next.config.ts` refuses to start without it.

`API_TOKEN_SECRET` signs the tokens that every call to the backend carries, so it must match the backend's, or the backend answers 401. Like `SESSION_SECRET`, it stays on the server.

## Deployment
Railway deploys `main` (Root Directory `/frontend`). Pull requests run lint and typecheck in CI.

Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).
