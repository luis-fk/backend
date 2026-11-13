# Backend context

## What this part does
The Django backend of the monorepo; the root `CLAUDE.md` has the repository layout, the rules shared with the frontend and the BMAD notes. Paths below are relative to `backend/`.
It hosts four independent apps: **plants** (plant data ingestion and an AI chatbot), **political_culture** (political text analysis and word counting with semantic search), **cfflch** (college admission status checker via web search and PDF parsing), and **news_podcast** (daily news audio briefing sent to Telegram).
The Next.js frontend that serves their UIs lives in `../frontend`. `README.md` covers setup and commands.

## Tech stack
- **Runtime:** Python 3.12+. `runtime.txt` asks Railway for the latest 3.12: Railpack installs Python with mise, which had no build of an exact old patch like 3.12.1. CI runs on the same 3.12 (`UV_PYTHON` in `backend-ci.yml`), not on the runner's Python
- **Frameworks:** Django 6, Django REST Framework, Django Channels (WebSockets)
- **ASGI server:** Daphne
- **Databases:** PostgreSQL — one database per app (`default` for auth and the API keys, `plants_db`, `political_culture_db`, `cfflch_db`, `news_podcast_db`). Redis for the Django Channels layer outside development; with `ENVIRONMENT=development` the layer is in memory.
- **ORM:** Django ORM, routed via a custom `AppsRouter` in `backend/apps_routers.py`
- **Auth:** Users log in to the frontend by name, and the frontend keeps the session. The API checks HS256 JWTs the frontend signs with `API_TOKEN_SECRET` (PyJWT, `backend/api_auth.py`); Bruno and anyone the owner gives access use API keys created in the Django admin (the `api_keys` app stores only their SHA-256 hash); a key acts as one person in one or more apps, keeping the person's id in each app's Users table (`ApiKey.users`), and the person and the apps are set once, when the key is created; each ESP32 sends its own device key as `X-Device-Key` (`Esp32Device`, created in the admin, which stores only its SHA-256 hash), checked in plants (`device_for_key`), and the key stops when the device is unticked or its owner is blocked. Only the owner can create accounts (Django admin). No public registration. Unticking a person's Active, or one of their apps, blocks them at once and keeps their data: the login, and every user token and API key (`can_use` in `api_keys/app_users.py`), need both the auth user and the person's row in the app's Users to be active.
- **AI/ML:** LangChain, LangGraph, OpenAI (`gpt-4.1-mini`, `gpt-4o-mini`), Tavily (web search), pgvector (semantic search — used in `political_culture`). news_podcast asks for text through LangChain too (langchain-google-genai and langchain-openai); its voice stays on Gemini over httpx
- **External APIs:** OpenWeather (used in `plants` for weather data)
- **HTTP client:** httpx (async)
- **Linting/formatting:** Ruff (both lint and format)

## Architecture
- Django monolith; the Next.js frontend in `../frontend` serves the UIs and talks to it only over HTTP and WebSocket
- Each app follows the structure: `<app>/api/<feature>/routes.py`, `service.py`, `serializers.py`, and additional files as needed (e.g. `consumers.py` for WebSockets, `utils.py`, `prompts.py`)
- **Parnas decomposition is intentional:** each app owns its full logic stack. Do not extract shared utilities across apps even if code looks duplicated — duplication is preferred over coupling. The exceptions, approved by the owner, are two pieces of project infrastructure, like `settings.py` and `asgi.py`: `backend/api_auth.py`, with the token and API key checks every app uses, and the `api_keys` app, with the `ApiKey` model and its admin, and the admin's user pages. The apps never import `api_keys`; it finds their Users models by name (`app_users.py`).
- **People and apps:** a person is an auth user, and each app's `Users` row points to them by `auth_user_id`, since every app has its own database; login looks the name up in auth, then in the app. The admin's user form sets the apps a person can use: unticking one turns off `active` on their row there, which blocks them and keeps their data (deleting the row would delete the data, so that is left to the app's Users table, which lists what goes with it). Active sits next to the apps on the user page and in the user list, which also shows each person's apps; each app's Users table shows and searches the name and filters by `active`.
- The `AppsRouter` automatically routes models to their app-specific database; Django's own apps and `api_keys` go to `default` (`DEFAULT_DB_APPS`). Never use `using=` manually in queries — the router handles it.
- **Local data and commands:** `make seed` runs one command per app (`seed_plants`, `seed_political_culture`, `seed_cfflch`) for the person `demo`, who is also the local admin login (password `demo`); a second run replaces only what the seed made. The seeds, `make migrate` and the tests refuse databases outside this machine, since `backend/.env` may hold the production URLs: the project's code (`migrate_all`, the tests) uses `backend/local_databases.py`, and each seed has its own copy of the check, because the apps share no code. The project package `backend` is an installed app only for its commands.
- Separation of concerns: routes handle HTTP only, services contain business logic, serializers handle validation. Keep functions small.
- **API documentation:** the Bruno collection in `bruno/`, with no Swagger. A new or changed endpoint updates its request there. Values that belong to one person (API keys, user ids, tokens) are secret variables of the Local environment, and bodies use made-up names, so the committed files stay generic.

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
## Apps
Each app keeps its decisions in its own `CLAUDE.md`, which Claude Code loads when working in that folder:
- `plants/CLAUDE.md`: ESP32 devices and readings, OpenWeather, the plant-care chat and its tools.
- `political_culture/CLAUDE.md`: the texts library, the word counter, the chat and its tools, pgvector search.
- `cfflch/CLAUDE.md`: the admission status checker (Tavily, PDFs, results over WebSocket).
- `news_podcast/CLAUDE.md`: the daily news episode on a Railway cron, with its settings and history in the admin.

## Testing
- Unit tests run in CI (`uv run pytest` in `.github/workflows/backend-ci.yml` at the repository root) on every pull request that changes `backend/`.
- **Target:** unit tests only, written cleanly and with full understanding — not just for coverage
- **Location:** `tests/` folder (next to `manage.py`) mirroring the app structure
- **Coverage:** all four apps have tests in `tests/<app>/`; the API auth also has `tests/backend/test_api_auth.py` and `tests/api_keys/`
- **Setup:** pytest-django. Tests mock the LLMs and the external APIs and never reach the network. The databases are real in the tests that ask for them with `@pytest.mark.django_db(databases=["default", "<app>_db"])`: always list `default`, or a file run on its own fails with "Circular dependency in TEST[DEPENDENCIES]". Add `transaction=True` only when the code under test closes connections or queries from worker threads. Every token check also reads the person (`can_use`): `tests/conftest.py` lets everyone in, so tests can make up user ids, except in the tests marked `access_check`, which save the person (`saved_person` in `tests/api_tokens.py`). The consumers tidy their thread's connections when a socket opens, so the socket tests ask for the database. pytest-django creates and drops a `test_` copy of each database, on the local PostgreSQL (run `make db-up` first; `tests/conftest.py` stops the run when a database isn't on this machine, where pytest-django would create those copies) or on in-memory SQLite in CI, and the tests must pass on both, so pgvector searches (`CosineDistance`, which SQLite lacks) stay out of the database tests. The settings need `API_TOKEN_SECRET`; CI sets a dummy, plus `OPENAI_API_KEY` because the chatbot views build their clients on import

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **Keep apps isolated.** Each app is self-contained. Do not suggest cross-app imports or shared utility modules (`backend/api_auth.py` and the `api_keys` app are the only shared code).
- **Every endpoint checks a token.** A new view or consumer starts with a check from `backend/api_auth.py`: `require_user_token` (and `require_same_user` for one user's data) or `require_login_token` in DRF views, `has_valid_user_token` in plain Django views (the ESP32 view checks its device key with plants' `device_for_key`), `websocket_user_id` in consumers (through `database_sync_to_async`, since it reads the database), which accept with `subprotocol="bearer"`. Over HTTP, `require_user_token` and `has_valid_user_token` accept a user token or an API key (`Authorization: Bearer pk_...`); every check reads the database (the person must still be able to use the app), so async views call `has_valid_user_token` through `sync_to_async`. Consumers take user tokens only. Add 401/403 tests in `tests/<app>/`, with keys too.
- **PostgreSQL only.** Do not suggest alternative databases.
- **Multi-DB setup is fixed.** The `AppsRouter` is the source of truth for routing. Adding a new app requires a `<app>_db` entry in `DATABASES`, its URL in `backend/.env.example` and in the CI's environment, its `CREATE DATABASE` in `db/init.sql`, and its `makemigrations` line in the Makefile (`migrate_all` runs every database) — but don't do this until explicitly asked.
- **LangChain APIs change frequently.** Avoid deprecated patterns: `AgentExecutor` is gone, `hub.pull` is not used — prompts live locally in `prompts.py` files. Prefer `llm.bind_tools([...]).invoke(...)`, and run the tool calls it returns and send the results back (`_answer_with_tools` in `political_culture/api/chatbot/agents.py`): a single invoke never runs a tool. When the text is at hand, give it to the model instead of a search tool (the word counter's `extract_text_info`).
- **Railway deployment:** the backend runs on Railway as its own service, with Root Directory `/backend` and watch paths limited to `/backend/**`. The Start Command (set in the Railway dashboard) runs `collectstatic` and starts Daphne, with no migrations: the owner runs them from their machine (`make migrate-prod`: `ENV_FILE` points the settings at `backend/.env.production`, and `migrate_all --production` shows where each database is and asks for `yes`, so `.env` always keeps the local databases). Railpack installs the dependencies with uv from `uv.lock` (`uv sync --locked --no-dev`, which checks every file's hash) on the Python of `runtime.txt`. The project has no `[build-system]`, so uv installs only the dependencies and the code runs from the folder, as Daphne and `manage.py` expect.
- **Package manager:** uv only. Do not suggest pip or poetry commands.