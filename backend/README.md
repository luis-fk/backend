# Backend

Django API for four independent apps:

- `plants`: stores ESP32 soil readings with the local weather and runs an AI chatbot.
- `political_culture`: political chatbot, a shared library of texts (PDFs) and their word counts (pgvector for long texts).
- `cfflch`: searches college admission lists (PDFs) and streams the results over WebSocket.
- `news_podcast`: daily news podcast on Telegram, run by a Railway cron service, with its settings and cost history in the Django admin ([README](news_podcast/README.md)).

The [frontend](../frontend/README.md) has the UIs of the first three.

## Running locally
Needs [uv](https://docs.astral.sh/uv/) and Docker. From `backend/`:

```
make db-up          # PostgreSQL 16 + pgvector, creates the five databases
make install-dev
make migrate
make run            # http://localhost:8000
```

Settings come from `backend/backend/.env`. Required: `SECRET_KEY`, `API_TOKEN_SECRET`, `ESP32_DEVICE_KEY`, `ENVIRONMENT=development`, `SERVER_URL`, `NGROK_URL`, `FRONT_END_URL`, `OPEN_WEATHER_API_KEY`, `OPENAI_API_KEY` and the five `*_DATABASE_URL`. cfflch and the plants web search also need `TAVILY_API_KEY`, and production needs `REDIS_URL`.

Users are created in the Django admin (`/admin/`).

Other commands: `make lint`, `make type-check`, `uv run pytest` (with `make db-up` running), `make requirements` (regenerates `requirements.txt`, which Railway installs from).

## API access
Every API endpoint checks a token ([`backend/api_auth.py`](backend/api_auth.py)); `/admin/` keeps Django's login. The frontend signs JWTs (HS256) with `API_TOKEN_SECRET`, so both services need the same value, with at least 32 characters (`openssl rand -base64 32`). The browser sends the logged-in user's token as `Authorization: Bearer <token>`, or as the WebSocket subprotocols `bearer` and `<token>`, and the login Server Actions send a 60-second login token to `/api/<app>/users/<name>`.

The ESP32 sends the header `X-Device-Key: <ESP32_DEVICE_KEY>` to `/api/esp32/humidity-data`.

To call the API from Bruno, or to give someone access, create an API key in the Django admin (**API keys → Add**, in production too): a name saying who or what it is for, the app, and the user id (the `id` in that app's Users table). The admin shows the key once and stores only its hash, so a lost key is replaced with a new one. Send it as `Authorization: Bearer <key>`: it works like that user's token in that app, except on the WebSockets. To revoke it, uncheck **Active** (in the list or on its page) and save; it stops working at once.

The Bruno collection in [`bruno/`](bruno/) documents the API. Its Local environment takes each app's API key and user id, the device key and, for the WebSockets, a user token, as secret variables, which Bruno keeps outside the files. The Production environment stays out of git.

## Deployment
Railway deploys `main` (Root Directory `/backend`). Pull requests run Ruff, mypy and pytest in CI.

Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).
