# Backend

Django API for four independent apps:

- `plants`: stores ESP32 soil readings with the local weather and runs an AI chatbot.
- `political_culture`: political chatbot and word counter (pgvector for long texts).
- `cfflch`: searches college admission lists (PDFs) and streams the results over WebSocket.
- `news_podcast`: daily news podcast on Telegram, run by GitHub Actions ([README](news_podcast/README.md)).

The [frontend](../frontend/README.md) has the UIs of the first three.

## Running locally
Needs [uv](https://docs.astral.sh/uv/) and Docker. From `backend/`:

```
make db-up          # PostgreSQL 16 + pgvector, creates the four databases
make install-dev
make migrate
make run            # http://localhost:8000
```

Settings come from `backend/backend/.env`. Required: `SECRET_KEY`, `ENVIRONMENT=development`, `SERVER_URL`, `NGROK_URL`, `FRONT_END_URL`, `OPEN_WEATHER_API_KEY`, `OPENAI_API_KEY` and the four `*_DATABASE_URL`. cfflch and the plants web search also need `TAVILY_API_KEY`, and production needs `REDIS_URL`.

Users are created in the Django admin (`/admin/`).

Other commands: `make lint`, `make type-check`, `uv run pytest`, `make requirements` (regenerates `requirements.txt`, which Railway installs from).

## Deployment
Railway deploys `main` (Root Directory `/backend`). Pull requests run Ruff, mypy and pytest in CI.

Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).
