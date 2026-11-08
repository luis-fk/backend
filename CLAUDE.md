# Repository context

## What this repository is
A personal monorepo used as a sandbox for prototyping ideas and improving coding skills.
The primary goal is learning — features are implemented carefully and with full understanding, not just shipped.

It has two independent parts, each with its own `CLAUDE.md` that Claude Code loads when working in that folder:
- **`backend/`** — Django backend with four apps: plants, political_culture, cfflch and news_podcast. See `backend/CLAUDE.md`.
- **`frontend/`** — Next.js frontend with the UIs for plants, political-culture and cfflch. See `frontend/CLAUDE.md`.

Until November 2026 they were separate repositories: this one was `luis-fk/backend`, renamed to `luis-fk/projects` when `luis-fk/frontend` was merged into it. The backend was moved into `backend/` with `git mv`, so `git log --follow <file>` shows a backend file's history from before the move. The frontend history was rewritten with `git filter-repo --to-subdirectory-filter frontend` before the merge, so plain `git log` works for its files, and the PR numbers in those old commits were rewritten to `luis-fk/frontend#N`.

## Layout
```
.github/workflows/   backend-ci.yml, frontend-ci.yml, news_podcast.yml (GitHub only reads workflows here)
.claude/ _bmad/      Claude Code skills and BMAD, shared by both parts (BMAD writes its working files to _bmad-output/, which is git-ignored)
backend/             Django project: manage.py, pyproject.toml, uv.lock, the apps, tests/
frontend/            Next.js app: package.json, src/
```

## Working in the repository
- Run backend commands from `backend/` (uv) and frontend commands from `frontend/` (npm). The root has no tooling of its own.
- The two parts share no code. The frontend talks to the backend only over HTTP and WebSocket (`NEXT_PUBLIC_SERVER_URL`); do not add shared packages or imports across the two folders.
- CI runs on pull requests and is filtered by path: `backend-ci.yml` (ruff, format, mypy, pytest) when `backend/` changes and `frontend-ci.yml` (lint, typecheck) when `frontend/` changes. `news_podcast.yml` is the daily podcast run, not CI.
- Deployment: one Railway project (`projects`) with one service per part. Each service uses its folder as Root Directory, watches only that folder, and deploys from `main`.
- The two parts are versioned separately: the backend version lives in `backend/pyproject.toml` and the frontend version in `frontend/package.json`, and a release bumps only the part that changed.

## Non-negotiables (both parts)
- **Learning-first approach.** This project exists to learn. Prefer solutions that are correct and well-understood over quick hacks. Always explain the why behind suggestions, not just the what.
- **Git is managed by the user.** Do not create commits, push branches, or open PRs unless explicitly asked.
- **Keep apps isolated.** In both parts each app is self-contained, and duplication is preferred over coupling. Each part's `CLAUDE.md` has the details.

## BMAD notes
- BMAD v6.6.0 is installed at the root (installed 2026-05-11) and serves both parts. The frontend had an identical copy, which was dropped when the repositories were merged.
- Most relevant agents for this project: **architect** and **developer**. PM, analyst, and other agents are likely overkill for a solo sandbox project.
- This is an **existing project** — skip all greenfield scaffolding workflows. There is no PRD phase for features that are already defined conversationally.
- When suggesting new features or refactors, always check what already exists before proposing a design — the codebase is the source of truth, not assumptions.
