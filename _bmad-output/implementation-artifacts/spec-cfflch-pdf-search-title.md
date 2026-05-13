---
title: 'Add search_title to AdmissionPDF'
type: 'feature'
created: '2026-05-13'
status: 'done'
route: 'one-shot'
---

## Intent

**Problem:** The Tavily search result title (human-readable source context) was captured in `StudentFoundResult` but never persisted — callers of the admission results API had no way to surface where a PDF was found.

**Approach:** Add `search_title` to `AdmissionPDF`, populate it when persisting results, and expose it alongside the URL in the admission results serializer.

## Suggested Review Order

- [`cfflch/models.py`](../../cfflch/models.py) — new `search_title` field on `AdmissionPDF`
- [`cfflch/migrations/0002_admissionpdf_search_title.py`](../../cfflch/migrations/0002_admissionpdf_search_title.py) — generated migration
- [`cfflch/api/admission_status/service.py`](../../cfflch/api/admission_status/service.py) — `search_title[:512]` passed to `create_pdf`
- [`cfflch/api/admission_results/serializers.py`](../../cfflch/api/admission_results/serializers.py) — `get_pdf_urls` now returns `list[dict]` with `url` + `search_title`
- [`cfflch/api/admission_results/routes.py`](../../cfflch/api/admission_results/routes.py) — added `prefetch_related("pdfs")` to `_get_object` to fix N+1