.PHONY: install install-dev run migrate makemigrations shell \
        db-up db-down db-reset lint type-check test prune-branches

# ── Install ──────────────────────────────────────────────────────────────────

install:
	uv sync --no-dev

install-dev:
	uv sync

# ── Dev server ───────────────────────────────────────────────────────────────

run:
	uv run daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# ── Django ───────────────────────────────────────────────────────────────────

migrate:
	uv run python manage.py migrate
	uv run python manage.py migrate --database=plants_db
	uv run python manage.py migrate --database=political_culture_db
	uv run python manage.py migrate --database=cfflch_db

makemigrations:
	uv run python manage.py makemigrations plants
	uv run python manage.py makemigrations political_culture
	uv run python manage.py makemigrations cfflch

shell:
	uv run python manage.py shell

# ── Docker / Database ────────────────────────────────────────────────────────

db-up:
	docker compose up -d

db-down:
	docker compose down

db-reset:
	docker compose down -v
	docker compose up -d

# ── Code quality ─────────────────────────────────────────────────────────────

lint:
	uv run ruff check --fix .
	uv run ruff format .

type-check:
	uv run mypy .

# ── Git ───────────────────────────────────────────────────────────────────────

prune-branches:
	git fetch --prune
	git branch -vv | awk '/: gone]/{print $$1}' | xargs git branch -d
