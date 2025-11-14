Auto-Generated Note Titles
==========================

Overview
--------
- Notes API can auto-generate a title from content when `auto_title=true`.
- MVP uses a fast heuristic extractor; no external calls.
- Max length defaults to 250 characters; configurable per-request.

Endpoints
---------
- POST `/api/v1/notes/` (create)
  - Provide `{ content, auto_title: true, title_max_len?: 250, language?: "en" }`.
  - If `title` is omitted or empty and `auto_title=true`, the server generates a title.
  - If `auto_title` is false/missing and `title` is empty, request is rejected (400).

- POST `/api/v1/notes/bulk` (bulk create)
  - Each item supports the same fields; titles are generated per-item when requested.

- POST `/api/v1/notes/title/suggest` (suggest-only)
  - Body: `{ content, title_max_len?: 250, language?: "en" }`.
  - Response: `{ title }`.

Parameters
----------
- `title_max_len` (int, default 250): truncate at word boundary when needed.
- `language` (optional): hint; heuristic does not translate or localize.

Behavior
--------
- Extracts the first non-empty, descriptive line/sentence from the note content.
- Strips Markdown headings, lists, code fences, and link syntax.
- Falls back to a timestamp-based title when content is empty or non-informative.

Phase 2 (LLM Strategy)
----------------------
- Enable LLM-backed generation and set default via config:
  - In `Config_Files/config.txt` add:
    [Notes]
    title_llm_enabled = true
    title_default_strategy = llm_fallback
  - Or via env vars:
    - `NOTES_TITLE_LLM_ENABLED=true`
    - `NOTES_TITLE_DEFAULT_STRATEGY=llm_fallback` (options: heuristic | llm | llm_fallback)
  - Server settings keys (for reference):
    - `NOTES_TITLE_LLM_ENABLED`: bool
    - `NOTES_TITLE_DEFAULT_STRATEGY`: string
