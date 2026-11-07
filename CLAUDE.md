# Project context

## What this project does
A personal Django backend used as a sandbox for prototyping ideas and improving coding skills.
The primary goal is learning — features are implemented carefully and with full understanding, not just shipped. It hosts four independent apps: **plants** (plant data ingestion and an AI chatbot), **political_culture** (political text analysis and word counting with semantic search), **cfflch** (college admission status checker via web search and PDF parsing), and **news_podcast** (daily news audio briefing sent to Telegram).
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
- **news_podcast:** Gemini API over raw httpx (text with `generateContent`, TTS with the Interactions API), edge-tts (Microsoft voice, used only when explicitly chosen), feedparser, trafilatura, googlenewsdecoder, ffmpeg, Telegram Bot API
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
- `cfflch`: admission status checker — searches Tavily for PDFs, downloads and parses them, streams results over WebSocket. Has its own dedicated database (`cfflch_db`).
- `plants`: ESP32 data ingestion, OpenWeather integration for weather data, AI chatbot. The chatbot now has an extra `respond` node after tool execution so tool output is surfaced to the user correctly.

- `news_podcast`: no models and no database. Runs as `python manage.py news_podcast [episode|samples|chat-id]` from the GitHub Actions workflow `.github/workflows/news_podcast.yml` (daily at 06:10 BRT with cron `10 9 * * *`, sends at 07:00), not on Railway. The send time is pinned in the workflow env as `NEWS_PODCAST_SEND_AT: "07:00"` to match the cron. v2.3.0 tried an hourly cron with a `check-time` job to make the time configurable, but GitHub fired only 1 of about 10 hourly runs the first night and the episode was lost, so v2.3.1 went back to the fixed cron. The user plans to move the podcast to a Railway cron later and make the time configurable there; do not retry hourly GitHub schedules. Length and speed are optional GitHub variables (`NEWS_PODCAST_MINUTES` like `12-18`, `NEWS_PODCAST_SPEECH_SPEED`); they and the send time are parsed in `api/episode/options.py`, and invalid values fail the run with a Telegram message instead of silently falling back (the user wants to know). The news window closes at :00 of the hour before the send time. Length is the duration of the delivered file, so a faster speed means a longer script and more voice cost; `max minutes × speed` is capped at `MAX_SPEECH_MINUTES` (30) to fit the free tier's 10 voice requests a day. The story count (one per 1.5 min), the podcast name ("Resumo das {hour}") and the greeting (bom dia/boa tarde/boa noite) follow the options. Feeds come from `news_podcast/feeds.opml` and must be open-access sites whose domain is in `FULL_TEXT_DOMAINS` (Folha and Estadão were removed for their paywalls, and UOL because it blocks automated reading with 403; do not try to bypass bot protection); settings live in `news_podcast/api/episode/config.py`; editorial rules in `prompts.py`. Episodes are sent as Telegram voice messages (OGG/Opus via `sendVoice`) because only voice messages get Telegram's playback-speed button; the listener picks the speed there, so the default speech speed (ffmpeg `atempo`) is 1.0 and files target 12–18 minutes at 1x (8–12 at 1.5x). The Gemini TTS API has no speaking-rate parameter; pace comes from the brisk `TTS_STYLE`, which the user chose to keep. The default voice is `gemini-flash-lite` (picked by ear with the `samples` action, and cheaper). `NATURAL_WORDS_PER_MINUTE` (170) was calibrated from a real episode (words ÷ minutes of audio); short samples underestimate it. The script opens with a TV-news "escalada" (3–5 short, punchy headlines alternating between the hosts, then greeting and date, then straight into the first story) instead of a chatty preview: the user wants a short, impactful intro, in the format of Brazilian TV news but without copying any real show. Headline turns are marked `"headline": true` in the script JSON and synthesized with the emphatic `HEADLINE_TTS_STYLE` (the TTS accepts a style per turn). Delivery: the voice message carries only a one-line caption (title and date) and is followed by a separate text message with sources and a compact cost summary, because text messages are wider than captions. Costs are shown in BRL with a fixed `BRL_PER_USD`; the exchange-rate API calls were removed on purpose. Recalibrate whenever the voice or style changes. Text falls back from `gemini-3.8-flash` to `gemini-3.6-flash`, and once a model is unavailable (5xx, timeouts, quota) the rest of the run skips it. Voice has no automatic fallback: the user prefers no episode over the Microsoft voice, so on temporary unavailability it waits `VOICE_RETRY_MINUTES` (10, then 20) and tries again; on daily quota or persistent failure the episode fails with a Telegram error message.

**Recent cfflch changes (v2.0.0):**
- `AdmissionPDF` has a `search_title` field (max 512 chars) — populated from Tavily search result title
- `pdf_urls` in the admission results serializer now returns `list[dict]` with `url` and `search_title` keys (was `list[str]`) — **frontend must read `item.url` instead of the element directly**
- Admission results endpoint accepts optional `class_room_id` query param filter
- All searched students are saved to DB regardless of found/not-found (no PDFs = not found)
- Re-searching a known student (same name + year) skips Tavily and returns existing data immediately
- If a known student is re-searched with a different classroom, the classroom is updated
- PDF URL detection uses `.pdf` anywhere in the URL (not just `.endswith`)
- Tavily query includes keywords: `aprovado classificado convocado selecionado vestibular`
- PDF downloads are concurrent via `asyncio.gather`
- Name matching uses substring match on normalized text (not fuzzy/per-line matching)

**Planned (no timeline):**
- Write unit tests for `plants`, `political_culture` and `cfflch` (pytest, top-level `tests/` folder)
- Add API documentation
- Add project-level docs

## Testing
- Unit tests run in CI (`uv run pytest` in `.github/workflows/ci.yml`) on every pull request.
- **Target:** unit tests only, written cleanly and with full understanding — not just for coverage
- **Location:** top-level `tests/` folder mirroring the app structure
- **Coverage:** only `news_podcast` has tests (`tests/news_podcast/`, no network); `plants`, `political_culture` and `cfflch` have none — do not assume coverage there

## Non-negotiables
- **Learning-first approach.** This project exists to learn. Prefer solutions that are correct and well-understood over quick hacks. Always explain the why behind suggestions, not just the what.
- **Git is managed by the user.** Do not create commits, push branches, or open PRs unless explicitly asked.
- **Keep apps isolated.** Each app is self-contained. Do not suggest cross-app imports or shared utility modules.
- **PostgreSQL only.** Do not suggest alternative databases.
- **Multi-DB setup is fixed.** The `AppsRouter` is the source of truth for routing. Adding a new app requires adding a `<app>_db` entry to `DATABASES` and updating the Makefile — but don't do this until explicitly asked.
- **LangChain APIs change frequently.** Avoid deprecated patterns: `AgentExecutor` is gone, `hub.pull` is not used — prompts live locally in `prompts.py` files. Prefer `llm.bind_tools([...]).invoke(...)`.
- **WebSocket timing in `cfflch`:** the client must connect via WebSocket *before* the POST request is made, otherwise the result message is missed. This is a known limitation — do not try to fix it with polling or re-delivery unless explicitly asked.
- **Railway deployment:** the project runs on Railway. Start Command (set in Railway dashboard) runs migrations and starts Daphne. `requirements.txt` is kept in sync (generated with `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`) so Railway uses pip instead of auto-detecting Poetry.
- **Package manager:** uv only. Do not suggest pip or poetry commands.

## BMAD notes
- BMAD v6.6.0 is installed (installed 2026-05-11).
- Most relevant agents for this project: **architect** and **developer**. PM, analyst, and other agents are likely overkill for a solo sandbox project.
- This is an **existing project** — skip all greenfield scaffolding workflows. There is no PRD phase for features that are already defined conversationally.
- When suggesting new features or refactors, always check what already exists before proposing a design — the codebase is the source of truth, not assumptions.