# Personal projects

A sandbox for prototyping ideas and practicing software engineering. One repository, two independent parts:

| Folder | What it is | Stack |
|---|---|---|
| [`backend/`](backend/) | Django API with four apps: plants, political_culture, cfflch and news_podcast | Python, Django, DRF, Channels, PostgreSQL, uv |
| [`frontend/`](frontend/) | Next.js site with the UIs for plants, political-culture and cfflch | Next.js, React, TypeScript, plain CSS, npm |

The two parts share no code. The frontend talks to the backend over HTTP and WebSocket, at the URL in `NEXT_PUBLIC_SERVER_URL`.

## Running locally

You need [uv](https://docs.astral.sh/uv/) and Docker for the backend, and Node.js 22 for the frontend (`nvm use 22`). The READMEs of [`backend/`](backend/README.md) and [`frontend/`](frontend/README.md) list the environment variables and the other commands.

Backend, from `backend/` (settings come from `backend/backend/.env`):

```
make db-up        # PostgreSQL with pgvector in Docker
make install-dev
make migrate
make run          # http://localhost:8000
```

Frontend, from `frontend/` (settings come from `frontend/.env`):

```
npm ci
npm run dev       # http://localhost:3000
```

The daily news podcast runs on GitHub Actions; see [`backend/news_podcast/README.md`](backend/news_podcast/README.md).

## CI and deployment

- `.github/workflows/backend-ci.yml` (Ruff, mypy, pytest) and `frontend-ci.yml` (lint, typecheck) run on pull requests that touch their folder. `news_podcast.yml` is the daily podcast run, not CI.
- Both parts deploy to Railway from `main`, as two services of the same project. Each service uses its folder as Root Directory.
