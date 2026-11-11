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
make setup          # .env, dependencies, PostgreSQL 16 + pgvector, migrations, sample data
make run            # http://localhost:8000
```

Settings come from `backend/backend/.env`, which `make setup` copies from [`backend/.env.example`](backend/.env.example) when there is none: the local databases, development secrets and placeholder keys. Required: `SECRET_KEY`, `API_TOKEN_SECRET`, `ENVIRONMENT=development`, `SERVER_URL`, `NGROK_URL`, `FRONT_END_URL`, `OPEN_WEATHER_API_KEY`, `OPENAI_API_KEY` and the five `*_DATABASE_URL`. cfflch and the plants web search also need `TAVILY_API_KEY`, and production needs `REDIS_URL`. The frontend's `.env` takes the same `API_TOKEN_SECRET`.

The sample data (`make seed`) belongs to `demo`, the name to log in with in plants, political culture and cfflch: two plants with 30 days of readings (the command prints each device's key, to send readings from Bruno), a fictional pirate ideology with a library text, and six students of the current year. Running it again replaces only that data. `make migrate`, `make seed` and the tests refuse databases outside this machine.

Users are created in the Django admin (`/admin/`); `make superuser` creates its first login.

Other commands: `make test` (with the database up), `make check` (what CI runs, without changing any file), `make lint`, `make type-check`, `make db-down` (stops PostgreSQL and keeps the data), `make db-reset` (deletes the local databases and makes them again, sample data included), `make requirements` (regenerates `requirements.txt`, which Railway installs from).

## API access
Every API endpoint checks a token ([`backend/api_auth.py`](backend/api_auth.py)); `/admin/` keeps Django's login. The frontend signs JWTs (HS256) with `API_TOKEN_SECRET`, so both services need the same value, with at least 32 characters (`openssl rand -base64 32`). The browser sends the logged-in user's token as `Authorization: Bearer <token>`, or as the WebSocket subprotocols `bearer` and `<token>`, and the login Server Actions send a 60-second login token to `/api/<app>/users/<name>`.

Each ESP32 is created in the Django admin (**Plants → Esp32 devices → Add**): its plant's nickname, its owner and the soil calibration. The admin shows its key once; flash it into the ESP32, which sends it as `X-Device-Key` with `{analogValue, digitalValue}` to `/api/esp32/humidity-data`. The backend adds the weather at the owner's location (latitude and longitude on their plants Users row); without a location, or when OpenWeather fails, the reading is saved without the weather. A device stops when it is unticked or its owner is blocked. A lost key is replaced with the admin action **Generate a new key**, which keeps the plant's history.

To call the API from Bruno, or to give someone access, create an API key in the Django admin (**API keys → Add**, in production too): a name saying who or what it is for, the person, and the apps the key works in, one or several (the person must be able to use each one; their user page gives the access). The admin shows the key once and stores only its hash, so a lost key is replaced with a new one. Send it as `Authorization: Bearer <key>`: in each of its apps it works like that person's token, except on the WebSockets. To revoke it, uncheck **Active** (in the list or on its page) and save; it stops working at once.

To give someone access to the site, add them in **Users → Add** and tick their apps: the user form creates their row in each app's Users table, and the user list shows each person's apps. Unticking an app on their page blocks them in it, and unticking **Active** (on their page or in the list) blocks them everywhere: both act at once, on the login, every API call and their API keys, and keep their data, so ticking again gives the access back.

The Bruno collection in [`bruno/`](bruno/) documents the API. Its Local environment takes each app's API key and user id, the device key, the plants device's id and, for the WebSockets, a user token, as secret variables, which Bruno keeps outside the files. The Production environment stays out of git.

## Deployment
Railway deploys `main` (Root Directory `/backend`). Pull requests run Ruff, mypy and pytest in CI. The migrations run from the owner's machine: `make migrate-prod` reads `backend/backend/.env.production`, a copy of `.env` with the production database URLs that git ignores, shows their hosts and asks for `yes`.

Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).
