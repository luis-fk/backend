---
title: 'cfflch — Admission Persistence & Review Endpoints'
type: 'feature'
created: '2026-05-12'
status: 'in-review'
baseline_commit: 'c4db05ab4782172dff030a3ffc6ac6a394e25bb5'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The cfflch admission checker finds and streams results in real time but persists nothing — a human cannot later review, approve, or clean up results.

**Approach:** Add a dedicated `cfflch_db`, define three models (`ClassRoom`, `AdmissionResult`, `AdmissionPDF`), wire the checker to persist found results, and expose four REST endpoints for listing, editing, and deleting results.

## Boundaries & Constraints

**Always:**
- `cfflch_db` routes via `AppsRouter` automatically once added to `DATABASES` — never use `using=`
- Normalize student name and class name (accent-strip, lowercase, trim) using the existing `normalize_text()` in `cfflch/api/admission_status/utils.py` before any DB lookup or uniqueness check
- `student_name_normalized + year` must be unique — use `get_or_create` keyed on these two fields
- If `get_or_create` returns an existing `AdmissionResult`, append `AdmissionPDF` rows only for URLs not already stored; skip duplicates silently
- `ClassRoom` deduplication: normalize incoming `class_name`, `get_or_create` on `name_normalized`; always use the existing record if one matches
- `approved` defaults to `False`; never set by the checker — human-only via PATCH
- Never log `student_name`, `student_name_normalized`, or any class name
- `class_name` is optional in the checker request; `class_room` FK is nullable
- Session-based auth enforced on all new endpoints (same as existing routes)
- Follow existing cfflch structure: `routes.py`, `service.py`, `serializers.py`

**Never:**
- Soft-delete — deletion must be hard (`DELETE` + cascade)
- Encrypt name fields — plain storage is acceptable for this risk level
- Add endpoints to create `ClassRoom` from the frontend — creation is server-side only during the checker flow
- Cross-app imports

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Student found, new | Checker finds student, no existing `AdmissionResult` | Create `AdmissionResult` + `AdmissionPDF` row(s) | Log error, continue to next student |
| Student found, same URL | Existing record + URL already stored | Skip silently | — |
| Student found, new URL | Existing record + new PDF URL | Append `AdmissionPDF` row only | Log error, continue |
| Student not found | Checker finds no result | WebSocket message only, no DB write | — |
| `class_name` sent, new | Normalized name not in `ClassRoom` | Create `ClassRoom`, associate with result | Log error, skip association |
| `class_name` sent, exists | Normalized name matches existing `ClassRoom` | Use existing record | — |
| `class_name` absent | Request has no `class_name` | `class_room` FK stays null | — |
| List by year | `GET /cfflch/admission-results/?year=2025` | Returns all `AdmissionResult` for that year with nested PDF urls | 400 if `year` param missing or non-integer |
| PATCH approved | `PATCH /cfflch/admission-results/{id}/` `{"approved": true}` | Sets `approved=True` | 404 if not found |
| PATCH class_room | `PATCH` with `{"class_room_id": 3}` | Associates result with that classroom | 404 if classroom not found |
| DELETE | `DELETE /cfflch/admission-results/{id}/` | Deletes result + cascades PDFs | 404 if not found |

</frozen-after-approval>

## Code Map

- `cfflch/models.py` -- currently empty; add `ClassRoom`, `AdmissionResult`, `AdmissionPDF`
- `cfflch/migrations/` -- will receive new migration files
- `cfflch/api/admission_status/utils.py` -- contains `normalize_text()` to reuse
- `cfflch/api/admission_status/serializers.py` -- add optional `class_name` field
- `cfflch/api/admission_status/service.py` -- add persistence after student found
- `cfflch/api/admission_results/routes.py` -- new file: list, patch, delete endpoints
- `cfflch/api/admission_results/serializers.py` -- new file: response + patch serializers
- `cfflch/api/class_rooms/routes.py` -- new file: list endpoint
- `cfflch/api/class_rooms/serializers.py` -- new file: response serializer
- `cfflch/api/urls.py` -- wire new URL patterns
- `backend/settings.py` -- add `cfflch_db` to `DATABASES`
- `Makefile` -- add `cfflch_db` to migrate targets
- `db/init.sql` -- add `CREATE DATABASE cfflch_db;`

## Tasks & Acceptance

**Execution:**
- [x] `db/init.sql` -- add `CREATE DATABASE cfflch_db;` -- needed for local and Railway provisioning
- [x] `backend/settings.py` -- add `"cfflch_db": dj_database_url.config(default=env("CFFLCH_DATABASE_URL"))` to `DATABASES`
- [x] `Makefile` -- add `uv run python manage.py migrate --database=cfflch_db` to `migrate` target
- [x] `cfflch/models.py` -- define `ClassRoom` (id, name, name_normalized unique), `AdmissionResult` (id, student_name, student_name_normalized, year, approved=False, class_room FK nullable SET_NULL, created_at auto_now_add), `AdmissionPDF` (id, result FK CASCADE, url); add `unique_together = [("student_name_normalized", "year")]` on `AdmissionResult`
- [x] `cfflch/migrations/` -- run `makemigrations cfflch` to generate migration
- [x] `cfflch/api/admission_status/serializers.py` -- add optional `class_name = serializers.CharField(required=False, allow_null=True, default=None)`
- [x] `cfflch/api/admission_status/service.py` -- after student found, call persistence logic: normalize name → `get_or_create` `AdmissionResult` → for each PDF URL, `get_or_create` `AdmissionPDF`; if `class_name` present, normalize → `get_or_create` `ClassRoom` → associate; wrap ORM calls with `sync_to_async` since service is async
- [x] `cfflch/api/admission_results/serializers.py` -- new: `AdmissionResultSerializer` (read, nested `pdf_urls` as list of strings), `AdmissionResultPatchSerializer` (write, `approved` bool optional, `class_room_id` int optional)
- [x] `cfflch/api/admission_results/routes.py` -- new: `AdmissionResultsListApi` (GET, requires `?year=`), `AdmissionResultDetailApi` (PATCH + DELETE by pk); class-based `APIView`
- [x] `cfflch/api/class_rooms/serializers.py` -- new: `ClassRoomSerializer` (id, name)
- [x] `cfflch/api/class_rooms/routes.py` -- new: `ClassRoomsListApi` (GET, all classrooms ordered by name)
- [x] `cfflch/api/urls.py` -- add patterns: `api/cfflch/admission-results/`, `api/cfflch/admission-results/<int:pk>/`, `api/cfflch/class-rooms/`

**Acceptance Criteria:**
- Given a checker run that finds a student, when the async task completes, then an `AdmissionResult` row and at least one `AdmissionPDF` row exist in `cfflch_db`
- Given two checker runs for the same student+year with the same PDF URL, when both complete, then only one `AdmissionResult` and one `AdmissionPDF` row exist
- Given two checker runs for the same student+year with different PDF URLs, when both complete, then one `AdmissionResult` and two `AdmissionPDF` rows exist
- Given `GET /cfflch/admission-results/?year=2025`, when called authenticated, then only results for 2025 are returned with nested PDF urls
- Given `PATCH /cfflch/admission-results/{id}/` with `{"approved": true}`, when called, then `approved` is `True`
- Given `DELETE /cfflch/admission-results/{id}/`, when called, then the result and all its PDFs are deleted
- Given `GET /cfflch/class-rooms/`, when called, then all classrooms are returned ordered by name
- Given a checker request with `class_name` matching an existing normalized classroom, when processed, then no duplicate `ClassRoom` is created

## Design Notes

**Normalization reuse:** `normalize_text()` in `utils.py` already strips accents and lowercases. Use it directly for both `student_name_normalized` and `ClassRoom.name_normalized`.

**`sync_to_async` pattern** — service is async, ORM is sync:
```python
from asgiref.sync import sync_to_async

get_or_create_result = sync_to_async(AdmissionResult.objects.get_or_create)
result, _ = await get_or_create_result(
    student_name_normalized=normalize_text(name),
    year=year,
    defaults={"student_name": name, "class_room": classroom},
)
```

## Verification

**Commands:**
- `uv run python manage.py makemigrations cfflch` -- expected: new migration file created
- `uv run ruff check .` -- expected: no errors
- `uv run ruff format --check .` -- expected: no errors
- `uv run mypy .` -- expected: no errors