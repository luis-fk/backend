---
project_name: 'backend'
user_name: 'Felipe'
date: '2026-05-13'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'anti_patterns', 'deployment']
status: 'complete'
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- Python 3.13
- Django 6.0.5 + Django REST Framework 3.17.1
- Django Channels 4.3.2 + Daphne 4.2.1 (ASGI server) + channels-redis 4.3.0
- PostgreSQL — psycopg2-binary 2.9.12 (not psycopg3 — do not suggest migrating)
- pgvector 0.4.2
- LangChain 1.2.18 + LangGraph 1.1.10 + langchain-openai 1.2.1 + langchain-community 0.4.1
- OpenAI model: gpt-4o-mini
- Tavily python client 0.7.24 (AsyncTavilyClient)
- httpx (AsyncClient for all outbound HTTP)
- pypdf 6.11.0
- dj-database-url 3.1.2 + django-environ 0.13.0
- Ruff 0.15.12 (lint + format, target py312)
- mypy 1.15.0 (strict mode) + django-stubs 6.0.4 + djangorestframework-stubs 3.16.9
- pytest 9.0.3
- Package manager: uv only

## Language-Specific Rules

- Type hints are mandatory on all function parameters and return types; only trivially obvious assignments (e.g. `name = "Felipe"`) may omit them
- mypy strict mode is enforced — all code must pass `uv run mypy .` before committing
- `Optional[X]` and `X | None` are both acceptable; be consistent within a file
- Use `cast()` from `typing` only when the type system cannot infer correctly — do not use it to silence errors
- Async is used throughout for IO-bound work — prefer `async def` for any function that touches the DB, network, or filesystem
- Background tasks use `asyncio.ensure_future()` with a `done_callback` for error logging — not `asyncio.create_task()` or threading
- CPU-bound work inside async context wraps via `asyncio.to_thread()`
- Concurrent fan-out uses `asyncio.gather()`
- `logging` module is used everywhere — never `print()` for observability; always get a logger per module with `logging.getLogger(__name__)`
- No comments unless the *why* is non-obvious — naming should be self-explanatory

## Framework-Specific Rules

### Django

- Never use `using=` in ORM queries — `AppsRouter` handles all DB routing automatically
- Databases: `default` (auth), `plants_db`, `political_culture_db`, `cfflch_db` — each app has its own dedicated DB
- Adding a new app requires: a `<app>_db` entry in `DATABASES` (settings.py) and a corresponding entry in the Makefile migrate targets
- API endpoints use kebab-case (e.g. `/admission-status/`)
- Each app's URLs are defined in `<app>/api/urls.py` and merged in `backend/urls.py`
- Session-based auth only — no JWT, no public registration
- Return structured JSON errors with appropriate HTTP status codes; never let exceptions bubble up as 500s
- `backend/settings.py` is excluded from mypy and Ruff — do not add type annotations there

### Django REST Framework

- Routes use class-based `APIView` — no function-based views
- Serializers handle all input validation — routes must not contain validation logic
- Services contain all business logic — routes call services, never contain logic directly

### Django Channels / WebSockets

- ASGI application is defined in `backend/asgi.py` via `ProtocolTypeRouter`
- WebSocket URL patterns live in `<app>/api/<feature>/routing.py`
- Consumers extend `AsyncWebsocketConsumer`
- In `cfflch`: the client must connect via WebSocket *before* the POST request — results are not re-delivered if the client connects late

### LangChain / LangGraph

- Import from `langchain_openai`, not `langchain.chat_models` — the monolith path is broken in 1.x
- Import embeddings from `langchain_openai import OpenAIEmbeddings` — same split applies
- `AgentExecutor` is removed — all orchestration via `StateGraph` or `llm.bind_tools().invoke()`
- Never use `hub.pull` — prompts live locally in `<app>/api/<feature>/prompts.py`
- LangGraph `StateGraph` requires an explicit `TypedDict` state schema — no implicit dict merging
- Structured output: `llm.with_structured_output(schema=MySchema, method="json_schema")`
- Tools are defined with the `@tool` decorator from `langchain_core.tools`
- After a tool-calling node in a LangGraph graph, always add a follow-up LLM node that reads the tool result and formulates the response — tool output is not automatically surfaced to the user

## Code Quality & Style Rules

### Naming

- Files and functions: `snake_case`
- Classes: `PascalCase`
- DB columns: `snake_case`
- API endpoints: `kebab-case`

### Ruff

- Two separate commands: `uv run ruff check --fix .` (lint) and `uv run ruff format .` (formatting)
- Both must pass before committing — CI enforces `ruff check` and `ruff format --check`
- Excluded paths: `.claude/`, `_bmad/`, `*/migrations/*`, `backend/settings.py`
- Target: `py312`

### Code Organization

- Each app is fully self-contained — no cross-app imports, ever
- Duplication across apps is intentional (Parnas decomposition) — do not extract shared utilities
- Structure per feature: `routes.py`, `service.py`, `serializers.py`, plus `prompts.py` / `agents.py` / `nodes.py` / `graph.py` / `tools.py` / `schemas.py` as needed
- `consumers.py` for WebSocket consumers, `routing.py` for WebSocket URL patterns

### Error Handling

- Log errors at service level with `logger.error()` — never swallow silently
- Return structured JSON with appropriate HTTP status codes from routes
- Prefer fine-grained error responses over generic 500s

## Testing Rules

- No tests exist yet — pytest 9.0.3 is installed and ready
- Test files go in the top-level `tests/` folder, mirroring app structure (e.g. `tests/plants/`, `tests/cfflch/`)
- Unit tests only — no E2E or integration tests planned yet
- Use fake/mock DB connections — do not hit real databases in tests
- Run with: `uv run pytest`
- CI does not currently run pytest (no tests exist) — add a pytest step to `.github/workflows/ci.yml` when first tests are written
- Write tests with full understanding of what they verify — coverage for its own sake is not a goal

## Critical Don't-Miss Rules

### Database

- Never use `using=` in ORM queries — `AppsRouter` routes automatically
- Never cross-query models from different apps — each app owns its own DB
- `cfflch` uses `cfflch_db` — all four apps now have dedicated databases
- `migrations/` folders are excluded from Ruff and should not be manually edited

### cfflch-specific

- `AdmissionPDF.search_title` max length is 512 — always truncate with `[:512]` before saving
- `pdf_urls` serializer field returns `list[dict]` with `url` and `search_title` keys — not `list[str]`
- Use `obj.pdfs.all()` (not `.values()`) in the serializer to hit the prefetch cache and avoid N+1
- Name matching uses normalized substring: `normalized_name in normalize_text(text)` — do not use fuzzy or per-line matching
- PDF URL detection: check `.pdf` anywhere in the URL with `".pdf" in url.lower()` — not `.endswith(".pdf")`
- Deduplication is keyed on `student_name_normalized + year` — same name + different year = new record
- Re-searching a known student skips Tavily entirely and fires the WebSocket with existing DB data

### LangChain / LangGraph

- `from langchain.chat_models import ChatOpenAI` — WRONG, broken in 1.x
- `from langchain_openai import ChatOpenAI` — correct
- `AgentExecutor` does not exist — do not generate it
- `hub.pull(...)` is not used — prompts are local files
- LangGraph nodes that return state must return the full state dict with `{**state, "key": value}` — partial returns lose state

### httpx

- Never instantiate `httpx.AsyncClient()` at module or class level — resource leak
- Always use `async with httpx.AsyncClient() as client:` inside the function

### pypdf

- `from pypdf import PdfReader` — not `from PyPDF2 import PdfReader` (`PyPDF2` is not installed)

### App Isolation

- Do not create shared utility modules across apps — duplication is intentional
- Do not import from one app into another under any circumstance

### Deployment

- Project runs on Railway — avoid hardcoded paths, localhost assumptions, or dev-only env vars without production equivalents
- ASGI server is Daphne — not gunicorn (gunicorn is installed but unused; Daphne handles both HTTP and WebSocket)
- `requirements.txt` must be kept in sync: `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt` — this causes Railway to use pip instead of auto-detecting Poetry
- Never include `-e .` in `requirements.txt` — always use `--no-emit-project` flag
- Railway Start Command (set in dashboard, not Procfile) runs migrations for all 4 databases then starts Daphne
- After bumping version in `pyproject.toml`, run `uv lock` to regenerate `uv.lock`

---

## Usage Guidelines

**For AI Agents:** Read this file before implementing any code. Follow all rules exactly as documented. When in doubt, prefer the more restrictive option.

**For Humans:** Keep this file lean. Update when the technology stack changes. Remove rules that become obvious over time.

_Last updated: 2026-05-13_