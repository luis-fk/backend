# cfflch context

College admission status checker: searches Tavily for PDFs, downloads and parses them, streams results over WebSocket. Has its own dedicated database (`cfflch_db`). This file holds the app's decisions; `backend/CLAUDE.md` has the rules every app follows. Paths are relative to `backend/`.

## Decisions
- `AdmissionPDF` has a `search_title` field (max 512 chars) — populated from Tavily search result title
- `pdf_urls` in the admission results serializer returns `list[dict]` with `url` and `search_title` keys (was `list[str]`); the frontend reads `item.url`
- Admission results endpoint accepts optional `class_room_id` query param filter
- Searched students are saved to DB, found or not (no PDFs = not found). A search that can't run (a Tavily error or no key) or can't read any of the lists it found is sent with `failed: true` and not saved, so searching the name again runs a new search
- Re-searching a known student (same name + year) skips Tavily and returns existing data immediately
- If a known student is re-searched with a different classroom, the classroom is updated
- PDF URL detection uses `.pdf` anywhere in the URL (not just `.endswith`)
- Tavily query includes keywords: `aprovado classificado convocado selecionado vestibular`
- PDF downloads are concurrent via `asyncio.gather`
- Name matching looks for the normalized name as whole words in the normalized text (not fuzzy/per-line matching), so "Ana de Tal" doesn't match "Joana de Tal"
- **WebSocket timing in `cfflch`:** the client must connect via WebSocket *before* the POST request is made, otherwise the result message is missed. This is a known limitation — do not try to fix it with polling or re-delivery unless explicitly asked.
