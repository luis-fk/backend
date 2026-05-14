---
title: 'User lookup API for all apps + cfflch Users model'
type: 'refactor'
created: '2026-05-14'
status: 'ready-for-dev'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `plants` user API returns `id + username` and does not verify the user exists in the app-specific `Users` table. `political_culture` has a `Users` model but no user API. `cfflch` has neither a `Users` model nor a user API.

**Approach:** Add a `Users` model to `cfflch` (mirroring the pattern in `plants` and `political_culture`), add a `GET /api/<app>/users/<username>` endpoint to `political_culture` and `cfflch`, and refactor `plants`' existing endpoint — all three must validate the user against both the auth DB and the app-specific `Users` table, returning only the app `Users.id`.

## Boundaries & Constraints

**Always:**
- Each app's `Users` model stores only `auth_user_id` (FK reference as `IntegerField` to `default` DB auth user — no cross-DB ForeignKey)
- User lookup flow: (1) get auth user from `default` DB by `username`, (2) get app `Users` row by `auth_user_id`, (3) return app `Users.id`
- Return shape: `{"id": <app_users_id>}` only — no username, no auth id
- Error shape: `{"error": "..."}` with appropriate status code
- Each app is fully isolated — no shared utilities, no cross-app imports
- `AppsRouter` handles DB routing automatically — never use `using=` except for the explicit `default` DB lookup on the auth user

**Ask First:**
- If any existing data depends on the current `plants` user API response shape (`id + username`), halt before changing it

**Never:**
- Do not add `latitude`/`longitude` or any extra fields to `cfflch.Users` — keep it minimal like `political_culture.Users`
- Do not add auth enforcement (permissions/authentication_classes) to any endpoint
- Do not cross-import between apps

## I/O & Edge-Case Matrix

| Scenario | Input | Expected Output | Error Handling |
|----------|-------|-----------------|----------------|
| Valid user, exists in both DBs | `GET /api/<app>/users/joao` | `{"id": 3}` (app Users.id), 200 | — |
| Username not in auth DB | `GET /api/<app>/users/ghost` | `{"error": "User not found."}`, 404 | catch `DoesNotExist` on auth lookup |
| Auth user exists but not in app Users | `GET /api/<app>/users/joao` | `{"error": "User not found."}`, 404 | catch `DoesNotExist` on app Users lookup |

</frozen-after-approval>

## Code Map

- `plants/models.py` -- `Users` model with `auth_user_id`, already correct
- `plants/api/users/routes.py` -- existing user API, needs refactor (drop username from response, add app Users check)
- `plants/api/users/serializers.py` -- returns `id + username`, needs to return only `id`
- `political_culture/models.py` -- `Users` model with `auth_user_id`, already correct
- `political_culture/api/users/` -- does not exist, needs creating
- `political_culture/api/urls.py` -- needs new user URL added
- `cfflch/models.py` -- no `Users` model yet, needs adding
- `cfflch/migrations/` -- needs new migration for `Users`
- `cfflch/api/users/` -- does not exist, needs creating
- `cfflch/api/urls.py` -- needs new user URL added

## Tasks & Acceptance

**Execution:**

- [ ] `plants/api/users/serializers.py` -- change `fields` to `["id"]` only, remove `username`
- [ ] `plants/api/users/routes.py` -- after auth user lookup, add `Users.objects.get(auth_user_id=auth_user.id)` and return its `.id`; catch `Users.DoesNotExist` → 404
- [ ] `political_culture/api/users/__init__.py` -- create empty file
- [ ] `political_culture/api/users/serializers.py` -- create `UserSerializer` with `fields = ["id"]`
- [ ] `political_culture/api/users/routes.py` -- create `UserApi` mirroring plants pattern: auth lookup → app Users lookup → return `{"id": app_user.id}`
- [ ] `political_culture/api/urls.py` -- add `GET api/political-culture/users/<str:username>` route
- [ ] `cfflch/models.py` -- add `Users(auth_user_id=IntegerField(unique=True))`
- [ ] `cfflch/migrations/0003_users.py` -- generate via `python manage.py makemigrations cfflch`
- [ ] `cfflch/api/users/__init__.py` -- create empty file
- [ ] `cfflch/api/users/serializers.py` -- create `UserSerializer` with `fields = ["id"]`
- [ ] `cfflch/api/users/routes.py` -- create `UserApi` mirroring plants pattern
- [ ] `cfflch/api/urls.py` -- add `GET api/cfflch/users/<str:username>` route

**Acceptance Criteria:**
- Given a username that exists in auth DB and in app `Users`, when `GET /api/<app>/users/<username>`, then response is `{"id": <app_users_id>}` with 200 — for all three apps
- Given a username not in auth DB, when `GET /api/<app>/users/<username>`, then `{"error": "User not found."}` 404
- Given a username in auth DB but not in app `Users`, when `GET /api/<app>/users/<username>`, then `{"error": "User not found."}` 404
- `plants` response no longer contains `username` field

## Verification

**Commands:**
- `uv run ruff check --fix .` -- expected: no errors
- `uv run ruff format .` -- expected: no errors
- `uv run mypy .` -- expected: no errors
- `uv run python manage.py makemigrations --check` -- expected: no pending migrations (after generating cfflch migration)