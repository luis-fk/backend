.PHONY: setup install install-dev run migrate migrate-prod makemigrations seed \
        shell db-up db-down db-reset lint type-check test check prune-branches

# ── Setup ────────────────────────────────────────────────────────────────────

setup: backend/.env install-dev db-up migrate seed

backend/.env:
	cp backend/.env.example backend/.env

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
	uv run python manage.py migrate_all

migrate-prod:
	ENV_FILE=.env.production uv run python manage.py migrate_all --production

makemigrations:
	uv run python manage.py makemigrations plants
	uv run python manage.py makemigrations political_culture
	uv run python manage.py makemigrations cfflch
	uv run python manage.py makemigrations api_keys
	uv run python manage.py makemigrations news_podcast

seed:
	uv run python manage.py seed_plants
	uv run python manage.py seed_political_culture
	uv run python manage.py seed_cfflch

shell:
	uv run python manage.py shell

# ── Docker / Database ────────────────────────────────────────────────────────

db-up:
	docker compose up -d --wait

db-down:
	docker compose down

db-reset:
	docker compose down -v
	$(MAKE) db-up migrate seed

# ── Code quality ─────────────────────────────────────────────────────────────

lint:
	uv run ruff check --fix .
	uv run ruff format .

type-check:
	uv run mypy .

test:
	uv run pytest

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy .
	uv run pytest

# ── Git ───────────────────────────────────────────────────────────────────────

prune-branches:
	git fetch --prune
	git branch -vv | awk '/: gone]/{print $$1}' | xargs git branch -d
