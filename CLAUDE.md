# Project context

## What this project does
A personal Django backend used as a sandbox for prototyping ideas and improving coding skills.
The primary goal is learning — features are implemented carefully and with full understanding, not just shipped. It hosts three independent apps: **plants** (plant data ingestion and an AI chatbot), **political_culture** (political text analysis and word counting with semantic search), and **cfflch** (college admission status checker via web search and PDF parsing).
The React frontend is a separate app.

## Tech stack
- **Runtime:** Python 3.13
- **Frameworks:** Django 5.x, Django REST Framework, Django Channels (WebSockets)
- **ASGI server:** Daphne
- **Databases:** PostgreSQL — one database per app (`default` for auth, `plants_db`, `political_culture_db`); `cfflch` currently shares `default` until a dedicated DB is added. Redis for Django Channels layer.
- **ORM:** Django ORM, routed via a custom `AppsRouter` in `backend/apps_routers.py`
- **Auth:** Session-based with basic username authentication. Only the owner can create accounts. No public registration.
- **AI/ML:** LangChain, LangGraph, OpenAI (GPT-4.x), Tavily (web search), pgvector (semantic search — used in `political_culture`)
- **External APIs:** OpenWeather (used in `plants` for weather data)
- **HTTP client:** httpx (async)
- **Linting/formatting:** Ruff (both lint and format)

## Architecture
- Django monolith backend; separate React frontend app serving multiple apps
- Each app follows the structure: `<app>/api/<feature>/routes.py`, `service.py`, `serializers.py`, and additional files as needed (e.g. `consumers.py` for WebSockets, `utils.py`, `prompts.py`)
- **Parnas decomposition is intentional:** each app owns its full logic stack. Do not extract shared utilities across apps even if code looks duplicated — duplication is preferred over coupling.
- The `AppsRouter` automatically routes models to their app-specific database. Never use `using=` manually in queries — the router handles it.
- Separation of concerns: routes handle HTTP only, services contain business logic, serializers handle validation. Keep functions small.

## Coding conventions
- **Files and functions:** `snake_case`
- **Classes:** `PascalCase`
- **DB columns:** `snake_case`
- **API endpoints:** `kebab-case` (dashes, e.g. `/admission-status/`)
- **Linter/formatter:** Ruff — always run before committing
- **Type hints:** mandatory everywhere except trivially obvious assignments (e.g. `name = "Felipe"` needs no annotation). Return types are always annotated.
- **Comments:** not used — code should be self-explanatory through naming. Only add a comment when the *why* is non-obvious (a hidden constraint, a workaround, a subtle invariant).
- **Error handling:** return structured JSON errors with appropriate HTTP status codes. Prefer fine-grained error responses over generic 500s. Log errors at service level with `logging`, don't swallow them silently.
- **Async:** used throughout for IO-bound work. Background tasks use `asyncio.ensure_future` with a `done_callback` for error logging. `asyncio.gather` for concurrent fan-out.

## Current state
**Complete (stable):**
- `political_culture`: word counter with LLM extraction, political chatbot with tools. pgvector is used to semantically search long reference texts that would otherwise exceed context limits. No near-term work planned.
- `cfflch`: admission status checker — searches Tavily for PDFs, downloads and parses them, streams results over WebSocket. Needs a dedicated database added eventually.
- `plants`: ESP32 data ingestion, OpenWeather integration for weather data, AI chatbot.

**In progress:**
- Improving the `plants` chatbot to be more plant-specific
- Minor adjustments to `cfflch`

**Planned (no timeline):**
- Add a dedicated database for `cfflch`
- Write unit tests (pytest, top-level `tests/` folder)
- Add API documentation
- Add project-level docs

## Testing
- No tests exist yet. Pytest is installed and ready.
- **Target:** unit tests only, written cleanly and with full understanding — not just for coverage
- **Location:** top-level `tests/` folder mirroring the app structure
- **Coverage:** none currently — do not assume any test coverage exists

## Non-negotiables
- **Learning-first approach.** This project exists to learn. Prefer solutions that are correct and well-understood over quick hacks. Always explain the why behind suggestions, not just the what.
- **Git is managed by the user.** Do not create commits, push branches, or open PRs unless explicitly asked.
- **Keep apps isolated.** Each app is self-contained. Do not suggest cross-app imports or shared utility modules.
- **PostgreSQL only.** Do not suggest alternative databases.
- **Multi-DB setup is fixed.** The `AppsRouter` is the source of truth for routing. Adding a new app requires adding a `<app>_db` entry to `DATABASES` and updating the Makefile — but don't do this until explicitly asked.
- **LangChain APIs change frequently.** Avoid deprecated patterns: `AgentExecutor` is gone, `hub.pull` is not used — prompts live locally in `prompts.py` files. Prefer `llm.bind_tools([...]).invoke(...)`.
- **WebSocket timing in `cfflch`:** the client must connect via WebSocket *before* the POST request is made, otherwise the result message is missed. This is a known limitation — do not try to fix it with polling or re-delivery unless explicitly asked.
- **Railway deployment:** the project runs on Railway. Any solution that works locally must also work in a Railway environment. Avoid local-only workarounds (e.g. hardcoded paths, localhost assumptions, dev-only env vars without production equivalents).
- **Package manager:** uv only. Do not suggest pip or poetry commands.

## BMAD notes
- BMAD is not installed yet — setup is pending.
- Most relevant agents for this project: **architect** and **developer**. PM, analyst, and other agents are likely overkill for a solo sandbox project.
- This is an **existing project** — skip all greenfield scaffolding workflows. There is no PRD phase for features that are already defined conversationally.
- When suggesting new features or refactors, always check what already exists before proposing a design — the codebase is the source of truth, not assumptions.