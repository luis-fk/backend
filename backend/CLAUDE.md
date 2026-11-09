# Backend context

## What this part does
The Django backend of the monorepo; the root `CLAUDE.md` has the repository layout, the rules shared with the frontend and the BMAD notes. Paths below are relative to `backend/`.
It hosts four independent apps: **plants** (plant data ingestion and an AI chatbot), **political_culture** (political text analysis and word counting with semantic search), **cfflch** (college admission status checker via web search and PDF parsing), and **news_podcast** (daily news audio briefing sent to Telegram).
The Next.js frontend that serves their UIs lives in `../frontend`. `README.md` covers setup and commands.

## Tech stack
- **Runtime:** Python 3.12+. `runtime.txt` asks Railway for the latest 3.12: Railpack installs Python with mise, which had no build of an exact old patch like 3.12.1
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

## Current state
**Complete (stable):**
- `political_culture`: a shared texts library (`api/texts/`), the word counter with LLM extraction, and a political chatbot with tools. pgvector is used to semantically search long reference texts that would otherwise exceed context limits. Library decisions:
  - Any user lists the library and adds PDFs of up to 100 MB. Only the Django admin edits or deletes a text, since a delete would remove it for everyone.
  - A PDF already in the library, by its SHA-256 (`Texts.file_hash`), or still being read (a set in memory, enough for the single process) is refused with 409, so it isn't read and paid for twice.
  - A book takes minutes, so `POST /api/political-culture/texts` answers 202 and a thread reads the PDF: embeddings, then title, author and summary, then word count, saved in one transaction. The result goes to the uploader's socket `ws/political-culture/texts/<userId>`, which isn't re-delivered, with the `upload_id` the page picked and sent: a PDF that fails at once may answer on the socket before the 202 arrives. A restart mid-reading loses the upload, and the user sends it again.
  - Text from PyPDF loses its NUL characters and lone surrogate halves, and the model's title and author are cut to their columns: PostgreSQL refuses them, and the whole reading would fail after being paid for.
  - The word picker gets only the 200 most frequent words (`MAX_PICKER_WORDS`): the analyses compare each text's key terms, and in a book about two thirds of the top 100 are function words, which the model drops.
  - Each user ticks the library texts the AI uses in their analyses (`Texts.selected_by`, set with `PUT /api/political-culture/texts/<id>/selection`). Every text, old or new, starts unticked. The tools that read the library are built per user (`user_tools` in `chatbot/tools.py`), so they see only that user's ticked texts and the texts they pasted in the chat.
- `cfflch`: admission status checker — searches Tavily for PDFs, downloads and parses them, streams results over WebSocket. Has its own dedicated database (`cfflch_db`).
- `plants`: ESP32 data ingestion, OpenWeather integration for weather data, AI chatbot. The chatbot now has an extra `respond` node after tool execution so tool output is surfaced to the user correctly.

- `news_podcast`: runs as `python manage.py news_podcast [episode|chat-id]`, daily on a Railway cron service (`episode --scheduled`, cron `40 9 * * *`, sent around 07:00 BRT; setup in `news_podcast/README.md`). Its settings and run history live in `news_podcast_db` and are edited in the Django admin. Decisions:
  - **Schedule:** runs only on Railway (by hand: Run now or `railway cron run`); do not move runs back to GitHub, which delayed or dropped scheduled runs and can't reach the database. The episode goes out as soon as it is ready, with no wait in the process: a process waiting for the hour could die with a paid-for episode, and with no notice or history, which come after the send. It is named after the next full hour after the start (`next_send`) and its news ends at the full hour before, so the Railway cron alone sets the time and frequency, starting about 20 minutes before that hour: no schedule in a UI or a variable.
  - **Settings:** length, speed, the Gemini models (free text) with their prices, the prompts and the voice styles are one `PodcastSettings` row; `clean()` refuses bad values on save, so they never reach a run. `config.py` and `prompts.py` only hold the starting values. The admin's permissions must not query this database (the admin checks them on every page). `paused` stops the `--scheduled` runs. Prices are edited by hand (they double on 2027-01-01).
  - **History:** every run saves an `Episode` row (status, length, paid-plan cost in USD, tokens, failed step and error), never the audio; a failed run keeps the cost of the answers it got, broken ones included. The admin shows costs in BRL with the fixed `BRL_PER_USD` (no exchange-rate API). The command uses the ORM only outside the event loop and renews the connection before writing the history, since a run can last close to an hour (with the voice retries).
  - **Length and speed:** length is the delivered file's duration, so a faster speed means a longer script and more voice cost; `max minutes × speed` is capped at `MAX_SPEECH_MINUTES` (30) to fit the free tier's 10 voice requests a day. Speed defaults to 1.0, since listeners use Telegram's speed button.
  - **Episode:** a single Telegram voice message (OGG/Opus via `sendVoice`) with a one-line caption, because only voice messages get the speed button. It opens with a TV-news "escalada" (3–5 short headlines, read with the emphatic headline style), without copying any real show. The voice model and styles were chosen by ear; the TTS has no speaking-rate parameter, so pace comes from the style, and `NATURAL_WORDS_PER_MINUTE` (170) must be recalibrated when the voice or the style changes.
  - **Feeds:** only open-access sites whose domain is in `FULL_TEXT_DOMAINS` (no paywalls, no sites that block automated reading); never bypass bot protection.
  - **Chats:** `TELEGRAM_CHAT_ID` is a single chat (a group, to reach more people). Error notices and the `chat-id` list go to `TELEGRAM_ADMIN_CHAT_ID`, falling back to `TELEGRAM_CHAT_ID`.
  - **Text answers:** structured output. Each step sends its Pydantic model's serialization schema (`responseJsonSchema`), where every field is required and the field descriptions in `schemas.py` (in Portuguese) explain the format, so Gemini can only write JSON that follows it and the prompts never ask for JSON. An answer cut short can still break: the log shows the finish reason of an answer that stopped early and where its JSON breaks.
  - **Fallbacks:** text falls back to the fallback model after a second try on the same one (`ANSWERS_PER_MODEL`), and a model that fails (5xx, timeouts, quota) is skipped for the rest of the run. Voice has no fallback (the user prefers no episode over another voice): it retries after `VOICE_RETRY_MINUTES` and then fails with a Telegram message.
  - **Kept out on purpose:** voice and plan variables, the Microsoft voice and the `samples` action; do not add them back unless asked.

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

## Testing
- Unit tests run in CI (`uv run pytest` in `.github/workflows/backend-ci.yml` at the repository root) on every pull request that changes `backend/`.
- **Target:** unit tests only, written cleanly and with full understanding — not just for coverage
- **Location:** `tests/` folder (next to `manage.py`) mirroring the app structure
- **Coverage:** all four apps have tests in `tests/<app>/`; the API auth also has `tests/backend/test_api_auth.py` and `tests/api_keys/`
- **Setup:** pytest-django. Tests mock the LLMs and the external APIs and never reach the network. The databases are real in the tests that ask for them with `@pytest.mark.django_db(databases=["default", "<app>_db"])`: always list `default`, or a file run on its own fails with "Circular dependency in TEST[DEPENDENCIES]". Add `transaction=True` only when the code under test closes connections or queries from worker threads. pytest-django creates and drops a `test_` copy of each database, on the local PostgreSQL (run `make db-up` first) or on in-memory SQLite in CI, and the tests must pass on both, so pgvector searches (`CosineDistance`, which SQLite lacks) stay out of the database tests. The settings need `API_TOKEN_SECRET` and `ESP32_DEVICE_KEY`; CI sets dummies, plus `OPENAI_API_KEY` because the chatbot views build their clients on import

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **Keep apps isolated.** Each app is self-contained. Do not suggest cross-app imports or shared utility modules (`backend/api_auth.py` and the `api_keys` app are the only shared code).
- **Every endpoint checks a token.** A new view or consumer starts with a check from `backend/api_auth.py`: `require_user_token` (and `require_same_user` for one user's data) or `require_login_token` in DRF views, `has_valid_user_token` or `has_valid_device_key` in plain Django views, `websocket_user_id` in consumers, which accept with `subprotocol="bearer"`. Over HTTP, `require_user_token` and `has_valid_user_token` accept a user token or an API key (`Authorization: Bearer pk_...`); a key takes a database query, so async views call `has_valid_user_token` through `sync_to_async`. Consumers take user tokens only. Add 401/403 tests in `tests/<app>/`, with keys too.
- **PostgreSQL only.** Do not suggest alternative databases.
- **Multi-DB setup is fixed.** The `AppsRouter` is the source of truth for routing. Adding a new app requires adding a `<app>_db` entry to `DATABASES` and updating the Makefile — but don't do this until explicitly asked.
- **LangChain APIs change frequently.** Avoid deprecated patterns: `AgentExecutor` is gone, `hub.pull` is not used — prompts live locally in `prompts.py` files. Prefer `llm.bind_tools([...]).invoke(...)`, and run the tool calls it returns and send the results back (`_answer_with_tools` in `political_culture/api/chatbot/agents.py`): a single invoke never runs a tool. When the text is at hand, give it to the model instead of a search tool (the word counter's `extract_text_info`).
- **WebSocket timing in `cfflch`:** the client must connect via WebSocket *before* the POST request is made, otherwise the result message is missed. This is a known limitation — do not try to fix it with polling or re-delivery unless explicitly asked.
- **Railway deployment:** the backend runs on Railway as its own service, with Root Directory `/backend` and watch paths limited to `/backend/**`. The Start Command (set in the Railway dashboard) only starts Daphne; the owner runs the migrations from their machine (`make migrate` with the production URLs). `requirements.txt` is kept in sync (generated with `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`) so Railway uses pip instead of auto-detecting Poetry.
- **Package manager:** uv only. Do not suggest pip or poetry commands.