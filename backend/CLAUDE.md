# Backend context

## What this part does
The Django backend of the monorepo; the root `CLAUDE.md` has the repository layout, the rules shared with the frontend and the BMAD notes. Paths below are relative to `backend/`.
It hosts four independent apps: **plants** (plant data ingestion and an AI chatbot), **political_culture** (political text analysis and word counting with semantic search), **cfflch** (college admission status checker via web search and PDF parsing), and **news_podcast** (daily news audio briefing sent to Telegram).
The Next.js frontend that serves their UIs lives in `../frontend`. `README.md` covers setup and commands.

## Tech stack
- **Runtime:** Python 3.12+ (`runtime.txt` pins 3.12.1 for Railway)
- **Frameworks:** Django 6, Django REST Framework, Django Channels (WebSockets)
- **ASGI server:** Daphne
- **Databases:** PostgreSQL — one database per app (`default` for auth and the API keys, `plants_db`, `political_culture_db`, `cfflch_db`, `news_podcast_db`). Redis for the Django Channels layer outside development; with `ENVIRONMENT=development` the layer is in memory.
- **ORM:** Django ORM, routed via a custom `AppsRouter` in `backend/apps_routers.py`
- **Auth:** Users log in to the frontend by name, and the frontend keeps the session. The API checks HS256 JWTs the frontend signs with `API_TOKEN_SECRET` (PyJWT, `backend/api_auth.py`); Bruno and anyone the owner gives access use API keys created in the Django admin (the `api_keys` app stores only their SHA-256 hash); the ESP32 sends `X-Device-Key`. Only the owner can create accounts (Django admin). No public registration.
- **AI/ML:** LangChain, LangGraph, OpenAI (`gpt-4.1-mini`, `gpt-4o-mini`), Tavily (web search), pgvector (semantic search — used in `political_culture`)
- **External APIs:** OpenWeather (used in `plants` for weather data)
- **news_podcast:** Gemini API over raw httpx (text with `generateContent`, TTS with the Interactions API), feedparser, trafilatura, googlenewsdecoder, ffmpeg, Telegram Bot API
- **HTTP client:** httpx (async)
- **Linting/formatting:** Ruff (both lint and format)

## Architecture
- Django monolith; the Next.js frontend in `../frontend` serves the UIs and talks to it only over HTTP and WebSocket
- Each app follows the structure: `<app>/api/<feature>/routes.py`, `service.py`, `serializers.py`, and additional files as needed (e.g. `consumers.py` for WebSockets, `utils.py`, `prompts.py`)
- **Parnas decomposition is intentional:** each app owns its full logic stack. Do not extract shared utilities across apps even if code looks duplicated — duplication is preferred over coupling. The exceptions, approved by the owner, are two pieces of project infrastructure, like `settings.py` and `asgi.py`: `backend/api_auth.py`, with the token, API key and device key checks every app uses, and the `api_keys` app, with the `ApiKey` model and its admin. The apps never import `api_keys`; its admin finds their Users models by name.
- The `AppsRouter` automatically routes models to their app-specific database; Django's own apps and `api_keys` go to `default` (`DEFAULT_DB_APPS`). Never use `using=` manually in queries — the router handles it.
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
- `cfflch`: admission status checker — searches Tavily for PDFs, downloads and parses them, streams results over WebSocket. Has its own dedicated database (`cfflch_db`).
- `plants`: ESP32 data ingestion, OpenWeather integration for weather data, AI chatbot. The chatbot now has an extra `respond` node after tool execution so tool output is surfaced to the user correctly.

- `news_podcast`: its settings and run history live in its own database (`news_podcast_db`) and are edited in the Django admin (`news_podcast/models.py`, `admin.py`). Runs as `python manage.py news_podcast [episode|chat-id]`: daily on a Railway cron service (`episode --scheduled`, cron `10 9 * * *`, 06:10 BRT, sent at 07:00; setup in `news_podcast/README.md`), and by hand with the service's Run now in Railway or `railway cron run`, which run the same `--scheduled` command. GitHub's own schedule was dropped because it delayed runs by hours or dropped them (v2.3.0's hourly cron lost episodes too), and the workflow for runs by hand went away with the database, which GitHub cannot reach; do not move runs back to GitHub. The send time is the next full hour after the run starts (`next_send`), so the Railway cron alone sets the time and frequency: the user chose to edit them in Railway rather than in a UI or a variable. Length, speed, the Gemini models (text, fallback and voice, as free text) with their paid-plan prices, the prompts and the two voice styles are fields of `PodcastSettings`, a single row: the admin's list opens its form and creates it on first use, and the admin's permissions never query this database (the admin checks them on every page). `clean()` refuses bad values on save (the ranges, `max minutes × speed`, and any `{placeholder}` a prompt cannot use, listed in `prompts.py`, or that has a format, like `{today:%d}`), so they never reach a run. `config.py` and `prompts.py` only hold the starting values: editing them does not change a database that already has its row. `paused` makes `--scheduled` runs (the cron and Run now) end without an episode; a run by hand without the flag still works. The prices are edited by hand (they double on 2027-01-01): since the models are free text, the user chose prices next to them over a price table in code. The news window closes at :00 of the hour before the send time. Length is the duration of the delivered file, so a faster speed means a longer script and more voice cost; `max minutes × speed` is capped at `MAX_SPEECH_MINUTES` (30) to fit the free tier's 10 voice requests a day. The story count (one per 1.5 min), the podcast name ("Resumo das {hour}") and the greeting (bom dia/boa tarde/boa noite) follow the options. The user removed the voice and plan variables, the Microsoft voice and the `samples` action to keep the app simple; do not add them back unless asked. Feeds come from `news_podcast/feeds.opml` and must be open-access sites whose domain is in `FULL_TEXT_DOMAINS` (Folha and Estadão were removed for their paywalls, and UOL because it blocks automated reading with 403; do not try to bypass bot protection); the other settings live in `news_podcast/api/episode/config.py`. The episode is a single Telegram voice message (OGG/Opus via `sendVoice`) with a one-line caption, because only voice messages get Telegram's playback-speed button; the listener picks the speed there, so the default speech speed (ffmpeg `atempo`) is 1.0 and files target 12–18 minutes at 1x (8–12 at 1.5x). The starting voice model is `gemini-3.8-flash-lite-tts` (picked by ear, and cheaper). The Gemini TTS API has no speaking-rate parameter; pace comes from the brisk voice style (starting value `TTS_STYLE`), which the user chose to keep. `NATURAL_WORDS_PER_MINUTE` (170) was calibrated from a real episode (words ÷ minutes of audio); recalibrate whenever the voice or style changes. The script opens with a TV-news "escalada" (3–5 short, punchy headlines alternating between the hosts, then greeting and date, then straight into the first story): the user wants a short, impactful intro in the format of Brazilian TV news, without copying any real show. Headline turns are marked `"headline": true` and synthesized with the emphatic headline voice style. Every `episode` run saves an `Episode` row: status, length, paid-plan cost in USD at the admin's prices, the tokens of each Gemini answer, and the failed step and error; never the audio, by the user's choice. A failed run keeps the cost of the answers it got, broken ones included: `generate_json` returns the raw answer, and the service counts its usage before reading the JSON. The command reads the settings and writes the history outside the event loop, where the ORM runs without threads, and calls `close_old_connections()` before the write: a run lasts an hour or more, and the connection that read the settings may be gone by then. The admin shows the history in BRL with a fixed `BRL_PER_USD` (the exchange-rate API calls were removed on purpose) and the total of the filtered list. Sources and the cost summary (`episode_details`) also go to the run's log. `TELEGRAM_CHAT_ID` is a single chat: to reach more people the user chose a Telegram group over a list of chat ids. Error notices and the `chat-id` list go to `TELEGRAM_ADMIN_CHAT_ID` (the owner's private chat), falling back to `TELEGRAM_CHAT_ID`, so they stay out of the group; on first setup, with no chat configured, `chat-id` sends each chat its own id. Text falls back from the text model to the fallback model (`gemini-3.8-flash` and `gemini-3.6-flash` to start), and once a model is unavailable (5xx, timeouts, quota) the rest of the run skips it. Voice has no fallback: the user prefers no episode over another voice, so on temporary unavailability it waits `VOICE_RETRY_MINUTES` (10, then 20) and tries again; on daily quota or persistent failure the episode fails with a Telegram error message.

**cfflch behavior (since v2.0.0):**
- `AdmissionPDF` has a `search_title` field (max 512 chars) — populated from Tavily search result title
- `pdf_urls` in the admission results serializer returns `list[dict]` with `url` and `search_title` keys (was `list[str]`); the frontend reads `item.url`
- Admission results endpoint accepts optional `class_room_id` query param filter
- All searched students are saved to DB regardless of found/not-found (no PDFs = not found)
- Re-searching a known student (same name + year) skips Tavily and returns existing data immediately
- If a known student is re-searched with a different classroom, the classroom is updated
- PDF URL detection uses `.pdf` anywhere in the URL (not just `.endswith`)
- Tavily query includes keywords: `aprovado classificado convocado selecionado vestibular`
- PDF downloads are concurrent via `asyncio.gather`
- Name matching uses substring match on normalized text (not fuzzy/per-line matching)

**Planned (no timeline):**
- Write unit tests for `plants`, `political_culture` and `cfflch` beyond the API auth (pytest, in `tests/`)
- Add API documentation

## Testing
- Unit tests run in CI (`uv run pytest` in `.github/workflows/backend-ci.yml` at the repository root) on every pull request that changes `backend/`.
- **Target:** unit tests only, written cleanly and with full understanding — not just for coverage
- **Location:** `tests/` folder (next to `manage.py`) mirroring the app structure
- **Coverage:** `news_podcast` has tests (`tests/news_podcast/`, no network). For `plants`, `political_culture` and `cfflch` only the API auth is tested (`tests/<app>/`, plus `tests/backend/test_api_auth.py` and `tests/api_keys/`); do not assume other coverage there
- **Setup:** pytest-django. Tests mock the app data, the LLMs and the external APIs. Two databases are real, in the tests that ask for them with `@pytest.mark.django_db`: `default`, for the API keys and the admin, and `news_podcast_db`, for the podcast settings and history. pytest-django creates and drops a `test_` copy of each, on the local PostgreSQL (run `make db-up` first) or on SQLite in CI. The settings need `API_TOKEN_SECRET` and `ESP32_DEVICE_KEY`; CI sets dummies, plus `OPENAI_API_KEY` because the chatbot views build their clients on import

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **Keep apps isolated.** Each app is self-contained. Do not suggest cross-app imports or shared utility modules (`backend/api_auth.py` and the `api_keys` app are the only shared code).
- **Every endpoint checks a token.** A new view or consumer starts with a check from `backend/api_auth.py`: `require_user_token` (and `require_same_user` for one user's data) or `require_login_token` in DRF views, `has_valid_user_token` or `has_valid_device_key` in plain Django views, `websocket_user_id` in consumers, which accept with `subprotocol="bearer"`. Over HTTP, `require_user_token` and `has_valid_user_token` accept a user token or an API key (`Authorization: Bearer pk_...`); a key takes a database query, so async views call `has_valid_user_token` through `sync_to_async`. Consumers take user tokens only. Add 401/403 tests in `tests/<app>/`, with keys too.
- **PostgreSQL only.** Do not suggest alternative databases.
- **Multi-DB setup is fixed.** The `AppsRouter` is the source of truth for routing. Adding a new app requires adding a `<app>_db` entry to `DATABASES` and updating the Makefile — but don't do this until explicitly asked.
- **LangChain APIs change frequently.** Avoid deprecated patterns: `AgentExecutor` is gone, `hub.pull` is not used — prompts live locally in `prompts.py` files. Prefer `llm.bind_tools([...]).invoke(...)`.
- **WebSocket timing in `cfflch`:** the client must connect via WebSocket *before* the POST request is made, otherwise the result message is missed. This is a known limitation — do not try to fix it with polling or re-delivery unless explicitly asked.
- **Railway deployment:** the backend runs on Railway as its own service, with Root Directory `/backend` and watch paths limited to `/backend/**`. Start Command (set in Railway dashboard) runs migrations and starts Daphne. `requirements.txt` is kept in sync (generated with `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`) so Railway uses pip instead of auto-detecting Poetry.
- **Package manager:** uv only. Do not suggest pip or poetry commands.