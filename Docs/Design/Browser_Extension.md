# Browser Extension — PRD (Compat v0.1)

Status: Active
Owner: Server/API + WebUI
Updated: 2025-11-03

Purpose
- This PRD defines the product and technical contract for the tldw_server browser extension as it integrates with the current backend. It is not a greenfield extension spec; it codifies compatibility requirements, endpoints, security posture, and UX flows so the existing extension can be brought to parity with the server.

Summary
- Provide a light, secure capture-and-interact surface that talks to tldw_server: chat, RAG search, reading capture, media ingest (URL/process), and audio (STT/TTS). Aligns with server AuthNZ (single-user API key and multi-user JWT) and uses a background proxy for all network I/O.

Goals
- Backend compatibility with current server APIs (Chat, RAG, Media, Reading, Audio, LLM models/providers).
- Minimal-permissions extension with background-only header injection.
- Reliable streaming (SSE) and WS STT handling in MV3 background.
- Basic UX: popup/sidepanel chat, quick capture, context-menu actions.

Non-Goals (initial)
- Headless JS rendering for JS-heavy sites; authenticated/session scraping.
- Public/social sharing; multi-tenant cloud distribution.
- Complex workflow editing inside the extension.

Personas
- Researcher/Analyst: search + summarize, capture links for later reading.
- Power User: model selection, quick ingest, audio utilities.
- Casual User: quick save + simple chat.

Success Metrics
- Connection success rate to configured server; auth error rate.
- Chat stream completion rate and cancel latency (<200ms average).
- RAG query success; ingest success vs. validation failures.
- STT/TTS success rates; WS connection stability.

Scope (MVP → v1)
- MVP:
  - Chat: POST /api/v1/chat/completions (non-stream + stream)
  - RAG: POST /api/v1/rag/search (+ /search/stream for previews)
  - Reading: POST /api/v1/reading/save, GET /api/v1/reading/items
  - Media: POST /api/v1/media/add; process-only via /api/v1/media/process-*
  - STT: POST /api/v1/audio/transcriptions; WS /api/v1/audio/stream/transcribe
  - TTS: POST /api/v1/audio/speech
- v1:
  - Models/providers browser (GET /api/v1/llm/{models,models/metadata,providers})
  - Optional Notes/Prompts basic flows; output toasts for ingest/results

Endpoint Mapping (server truth)
- Diagnostics
  - GET  /           (root info)
  - GET  /api/v1/health
  - GET  /api/v1/health/live
  - GET  /api/v1/health/ready
- Chat
  - POST /api/v1/chat/completions
- RAG
  - POST /api/v1/rag/search
  - POST /api/v1/rag/search/stream
- Items (unified list)
  - GET  /api/v1/items
- Media (process-only; no DB persistence)
  - POST /api/v1/media/process-videos
  - POST /api/v1/media/process-audios
  - POST /api/v1/media/process-pdfs
  - POST /api/v1/media/process-ebooks
  - POST /api/v1/media/process-documents
  - POST /api/v1/media/process-web-scraping
- Media (persist)
  - POST /api/v1/media/add
- Reading
  - POST /api/v1/reading/save
  - GET  /api/v1/reading/items
  - PATCH /api/v1/reading/items/{item_id}
  - Highlights (v1 optional):
    - POST /api/v1/reading/items/{item_id}/highlight
    - GET  /api/v1/reading/items/{item_id}/highlights
    - PATCH /api/v1/reading/highlights/{highlight_id}
    - DELETE /api/v1/reading/highlights/{highlight_id}
- Notes (optional v1 scope)
  - Notes core
    - POST /api/v1/notes/            (create)
    - GET  /api/v1/notes/            (list; limit/offset)
    - GET  /api/v1/notes/{note_id}   (get)
    - PATCH /api/v1/notes/{note_id}  (update; requires header expected-version)
    - PUT  /api/v1/notes/{note_id}   (update variant; requires header expected-version)
    - DELETE /api/v1/notes/{note_id} (soft delete; requires header expected-version)
    - GET  /api/v1/notes/search/     (search?query=...)
  - Keywords and links
    - POST /api/v1/notes/keywords/              (create keyword)
    - GET  /api/v1/notes/keywords/              (list keywords)
    - GET  /api/v1/notes/keywords/{keyword_id}  (get keyword)
    - GET  /api/v1/notes/keywords/text/{text}   (lookup by text)
    - GET  /api/v1/notes/keywords/search/       (search keywords)
    - POST   /api/v1/notes/{note_id}/keywords/{keyword_id} (link)
    - DELETE /api/v1/notes/{note_id}/keywords/{keyword_id} (unlink)
    - GET    /api/v1/notes/{note_id}/keywords/  (list keywords on note)
    - GET    /api/v1/notes/keywords/{keyword_id}/notes/ (list notes for keyword)
- Prompts (optional v1 scope)
  - Core
    - GET  /api/v1/prompts                 (list)
    - POST /api/v1/prompts                 (create)
    - GET  /api/v1/prompts/{prompt_id}     (get)
    - PUT  /api/v1/prompts/{prompt_id}     (update)
    - DELETE /api/v1/prompts/{prompt_id}   (delete)
    - POST /api/v1/prompts/search          (search)
    - GET  /api/v1/prompts/export          (export)
  - Keywords
    - POST /api/v1/prompts/keywords/                 (add keyword)
    - GET  /api/v1/prompts/keywords/                 (list keywords)
    - DELETE /api/v1/prompts/keywords/{keyword_text} (delete keyword)
- Audio
  - POST /api/v1/audio/transcriptions
  - WS   /api/v1/audio/stream/transcribe (token query param)
  - POST /api/v1/audio/speech
  - GET  /api/v1/audio/voices/catalog (voice listing)
- Flashcards (optional v1 scope)
  - Decks
    - POST /api/v1/flashcards/decks         (create deck)
    - GET  /api/v1/flashcards/decks         (list decks; limit/offset)
  - Cards
    - POST   /api/v1/flashcards             (create card)
    - POST   /api/v1/flashcards/bulk        (bulk create)
    - GET    /api/v1/flashcards             (list; deck_id/tag/q/due_status filters)
    - GET    /api/v1/flashcards/id/{uuid}   (get by uuid)
    - PATCH  /api/v1/flashcards/{uuid}      (update; expected_version in body)
    - DELETE /api/v1/flashcards/{uuid}      (delete; expected_version query)
    - PUT    /api/v1/flashcards/{uuid}/tags (replace tags)
    - GET    /api/v1/flashcards/{uuid}/tags (list tags)
  - Import/Export/Review
    - POST /api/v1/flashcards/import        (TSV/CSV import; admin caps opt)
    - GET  /api/v1/flashcards/export        (CSV or APKG; deck/tag filters)
    - POST /api/v1/flashcards/review        (spaced-rep review submission)
- LLM Discovery
  - GET /api/v1/llm/models
  - GET /api/v1/llm/models/metadata
  - GET /api/v1/llm/providers
  - Note: `/api/v1/llm/models` includes image backends (`image/<backend>`). Use `type=chat` or `output_modality=text` when building chat-only lists.
- Chats (resource model; optional v1 scope)
  - /api/v1/chats/* (create/list/get/update/delete sessions; messages CRUD; complete/stream where available)

Watchlists (v1 optional)
- Sources
  - POST /api/v1/watchlists/sources               (create)
  - GET  /api/v1/watchlists/sources               (list)
  - GET  /api/v1/watchlists/sources/export        (export OPML)
  - POST /api/v1/watchlists/sources/import        (import OPML)
  - GET  /api/v1/watchlists/sources/{id}          (get)
  - PATCH/DELETE /api/v1/watchlists/sources/{id}  (update/delete)
- Tags & Groups
  - GET  /api/v1/watchlists/tags                  (list tags)
  - POST /api/v1/watchlists/groups                (create group)
  - GET  /api/v1/watchlists/groups                (list groups)
  - PATCH/DELETE /api/v1/watchlists/groups/{id}   (update/delete)
- Jobs
  - POST /api/v1/watchlists/jobs                  (create)
  - GET  /api/v1/watchlists/jobs                  (list)
  - GET  /api/v1/watchlists/jobs/{id}             (get)
  - PATCH/DELETE /api/v1/watchlists/jobs/{id}     (update/delete)
  - POST /api/v1/watchlists/jobs/{id}/filters:add (append filters)
  - PATCH /api/v1/watchlists/jobs/{id}/filters    (replace filters)
  - POST /api/v1/watchlists/jobs/{id}/preview     (dry-run preview)
  - POST /api/v1/watchlists/jobs/{id}/run         (trigger run)
- Runs
  - GET  /api/v1/watchlists/jobs/{id}/runs        (list by job)
  - GET  /api/v1/watchlists/runs                  (list all)
  - GET  /api/v1/watchlists/runs/{run_id}         (get)
  - GET  /api/v1/watchlists/runs/{run_id}/details (stats + logs)
  - GET  /api/v1/watchlists/runs/{run_id}/tallies.csv (filter tallies)
- Items & Outputs
  - GET  /api/v1/watchlists/items                 (list scraped items; filters)
  - GET  /api/v1/watchlists/items/{item_id}       (get)
  - PATCH /api/v1/watchlists/items/{item_id}      (update flags)
  - POST /api/v1/watchlists/outputs               (render output)
  - GET  /api/v1/watchlists/outputs               (list outputs)
  - GET  /api/v1/watchlists/outputs/{id}          (get output metadata)
  - GET  /api/v1/watchlists/outputs/{id}/download (download)
- Templates
  - GET  /api/v1/watchlists/templates             (list)
  - GET  /api/v1/watchlists/templates/{name}      (get)
  - POST /api/v1/watchlists/templates             (create/update)
  - DELETE /api/v1/watchlists/templates/{name}    (delete)

Schema Notes
- Notes optimistic concurrency
  - Update: `PATCH /api/v1/notes/{id}` or `PUT /api/v1/notes/{id}` requires header `expected-version: <int>`.
  - Delete: `DELETE /api/v1/notes/{id}` requires header `expected-version: <int>`.
  - On version mismatch: returns 409 conflict with details; clients should reload and retry.
- Flashcards import limits
  - Environment caps: `FLASHCARDS_IMPORT_MAX_LINES` (default 10000), `FLASHCARDS_IMPORT_MAX_LINE_LENGTH` (default 32768 bytes), `FLASHCARDS_IMPORT_MAX_FIELD_LENGTH` (default 8192 bytes).
  - Optional query overrides (admin only): `max_lines`, `max_line_length`, `max_field_length` can lower (not raise) env caps.
  - Formats: TSV/CSV (default tab delimiter). Fields include Deck, Front, Back, Notes, Extra, ModelType (basic|basic_reverse|cloze), Reverse (bool), Tags (comma/semicolon separated).

Example Requests
- Chat (streaming)
  - Request: `POST /api/v1/chat/completions` with JSON body including `stream: true`.
  - Example body:
    `{ "model": "openai/gpt-4o-mini", "stream": true, "messages": [{"role":"user","content":"Summarize https://example.com"}] }`
  - Headers: `Accept: text/event-stream` for SSE; server emits NDJSON/SSE lines ending with `[DONE]`.
  - Expected response (stream lines):
    - `data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello"}}]}`
    - `data: {"choices":[{"delta":{"content":" world"}}]}`
    - `data: [DONE]`
- RAG (streaming)
  - Request: `POST /api/v1/rag/search/stream`
  - Body minimal: `{ "query": "impact of CRISPR on gene therapy", "enable_generation": true, "top_k": 5 }`
  - Stream events: `delta` (answer tokens), optional `claims_overlay`, and final summary. Content-type `application/x-ndjson` or SSE with `data:` lines.
  - Expected response (ndjson lines):
    - `{ "event": "delta", "data": { "content": "Genome editing ..." } }`
    - `{ "event": "claims_overlay", "data": { "citations": [{"url":"...","span":[12,34]}] } }`
    - `{ "event": "done" }`
- Media add (persist)
  - `POST /api/v1/media/add` as multipart form.
  - Minimum fields for URL ingest:
    - `media_type=document|video|audio|pdf|ebook|email|code`
    - `urls=https://example.com/article` (repeat `urls` for multiple items)
  - Example:
    - `curl -X POST "$SERVER/api/v1/media/add" -H "X-API-KEY: $KEY" -F "media_type=document" -F "urls=https://example.com/article"`
  - Expected response (shape):
    - `{ "results": [ { "status": "Success", "input_ref": "https://...", "media_type": "document", "db_id": 456, "db_message": "Media added to database.", "summary": "..." } ] }`
- Media ingest jobs (async; preferred for browser URL ingest)
  - Submit: `POST /api/v1/media/ingest/jobs` (multipart form, same `media_type` + `urls` fields as `/media/add`)
  - Poll: `GET /api/v1/media/ingest/jobs/{job_id}`
  - Batch list: `GET /api/v1/media/ingest/jobs?batch_id=<uuid>`
  - Example submit:
    - `curl -X POST "$SERVER/api/v1/media/ingest/jobs" -H "X-API-KEY: $KEY" -F "media_type=video" -F "urls=https://www.youtube.com/watch?v=..."`
  - Expected response (shape):
    - `{ "batch_id": "...", "jobs": [ { "id": 123, "status": "queued", "source": "https://..." } ], "errors": [] }`
  - Expected status payload (shape):
    - `{ "id": 123, "status": "completed", "result": { "status": "Success", "media_id": 456 } }`
- Media process (no DB)
  - JSON URL: `POST /api/v1/media/process-pdfs` with `{ "urls": ["https://host/file.pdf"] }`
  - File upload: multipart to `/api/v1/media/process-pdfs` with `files=@/path/file.pdf`.
  - Expected response (shape):
    - `{ "processed_count": 1, "errors_count": 0, "errors": [], "results": [ { "status": "Success", "input_ref": "https://.../file.pdf", "media_type": "pdf", "content": "...", "chunks": [ ... ] } ] }`
- STT (multipart)
  - `POST /api/v1/audio/transcriptions`
  - Fields: `file=@/path/audio.wav`, `model=whisper-1`, optional `language=en`, `response_format=json`.
  - Example cURL: `curl -X POST "$BASE/api/v1/audio/transcriptions" -H "Authorization: Bearer TOKEN" -F "file=@/abs/audio.wav" -F "model=whisper-1" -F "language=en"`
  - Expected response (json):
    - `{ "text": "hello world", "language": "en", "segments": [ {"start":0.0,"end":0.8,"text":"hello"}, {"start":0.8,"end":1.5,"text":"world"} ] }`

- Reading — save & list
  - Save current tab: `POST /api/v1/reading/save`
    - Body:
      `{
        "url": "https://example.com/ai/rag-intro",
        "title": "RAG Intro",
        "tags": ["ai","rag"],
        "status": "saved",
        "favorite": false
      }`
    - Expected response (ReadingItem):
      `{
        "id": 1456,
        "media_id": 8123,
        "title": "RAG Intro",
        "url": "https://example.com/ai/rag-intro",
        "domain": "example.com",
        "summary": null,
        "published_at": null,
        "status": "saved",
        "favorite": false,
        "tags": ["ai","rag"],
        "created_at": "2025-10-19T08:00:10Z",
        "updated_at": "2025-10-19T08:00:10Z"
      }`
  - List items: `GET /api/v1/reading/items?status=saved&tags=ai&page=1&size=20`
    - Expected response (ReadingItemsListResponse):
      `{
        "items": [ { "id": 1456, "title": "RAG Intro", "url": "https://example.com/ai/rag-intro", "status": "saved", "favorite": false, "tags": ["ai","rag"], "created_at": "..." } ],
        "total": 1,
        "page": 1,
        "size": 20
      }`

  - Update item: `PATCH /api/v1/reading/items/{item_id}`
    - Body: `{ "status": "reading", "favorite": true, "tags": ["ai","rag","priority"] }`
    - Expected response (ReadingItem):
      `{ "id": 1456, "title": "RAG Intro", "status": "reading", "favorite": true, "tags": ["ai","rag","priority"], "updated_at": "2025-10-19T09:15:00Z" }`

  - List filters (query param variants):
    - Multi-filter: `GET /api/v1/reading/items?status=saved&status=reading&tags=ai&tags=ml&favorite=true&q=vector%20search&domain=example.com&page=2&size=50`
    - Text search only: `GET /api/v1/reading/items?q=rag&page=1&size=10`
    - Tag filter only: `GET /api/v1/reading/items?tags=ai`
    - Notes:
      - Repeat `status` and `tags` keys to pass multiple values (FastAPI parses as list).
      - `favorite` accepts `true|false`.
      - `status` allowed values: `saved|reading|read|archived`.
    - cURL examples:
      - Multi-filter:
        `curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/reading/items?status=saved&status=reading&tags=ai&tags=ml&favorite=true&q=vector%20search&domain=example.com&page=2&size=50"`
      - Text search only:
        `curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/reading/items?q=rag&page=1&size=10"`
      - Tag filter only:
        `curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/reading/items?tags=ai"`

  - Minimal PATCH examples (single-field updates):
    - Toggle favorite: `PATCH /api/v1/reading/items/{id}` body `{ "favorite": true }`
    - Update tags only: `PATCH /api/v1/reading/items/{id}` body `{ "tags": ["ai","priority"] }`
    - Update status only: `PATCH /api/v1/reading/items/{id}` body `{ "status": "read" }`
    - cURL (PATCH):
      - Toggle favorite:
        `curl -sS -X PATCH "$BASE/api/v1/reading/items/1456" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"favorite": true}'`
      - Update tags:
        `curl -sS -X PATCH "$BASE/api/v1/reading/items/1456" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"tags": ["ai","priority"]}'`
      - Update status:
        `curl -sS -X PATCH "$BASE/api/v1/reading/items/1456" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"status": "read"}'`

- Reading — highlights
  - Create highlight: `POST /api/v1/reading/items/{item_id}/highlight`
  - Example body:
    `{
      "item_id": 456,
      "quote": "The mitochondrion is the powerhouse of the cell.",
      "start_offset": 128,
      "end_offset": 178,
      "color": "yellow",
      "note": "Key definition",
      "anchor_strategy": "fuzzy_quote"
    }`
  - Expected response (Highlight):
    `{ "id": 1001, "item_id": 456, "quote": "The mitochondrion is the powerhouse of the cell.", "start_offset":128, "end_offset":178, "color":"yellow", "note":"Key definition", "created_at":"2025-10-19T08:00:10Z", "anchor_strategy":"fuzzy_quote", "content_hash_ref": "sha256:...", "context_before": "... power...", "context_after": "... cell ...", "state": "active" }`
  - List highlights for item: `GET /api/v1/reading/items/{item_id}/highlights`
    - Expected response (array of Highlight):
      `[{ "id": 1001, "item_id": 456, "quote": "...", "color":"yellow", "note":"Key definition", "created_at":"2025-10-19T08:00:10Z", "anchor_strategy":"fuzzy_quote", "state":"active" }]`
  - Update highlight: `PATCH /api/v1/reading/highlights/{highlight_id}`
    - Body: `{ "note": "Refined takeaway", "color": "green", "state": "active" }`
    - Expected response: updated Highlight object
  - Delete highlight: `DELETE /api/v1/reading/highlights/{highlight_id}` → `{ "success": true }`

- Notes — keyword link/unlink
  - Precondition: a note exists (`note_id` is a UUID string) and a keyword exists (`keyword_id` is an integer). Create keyword with `POST /api/v1/notes/keywords/` body `{ "keyword": "biology" }` if needed.
  - Link keyword to note: `POST /api/v1/notes/{note_id}/keywords/{keyword_id}`
    - Expected response: `{ "success": true, "message": "Note linked to keyword successfully." }`
  - List keywords on note: `GET /api/v1/notes/{note_id}/keywords/`
    - Expected response:
      `{ "note_id": "a3f0...", "keywords": [ { "id": 17, "keyword": "biology", "created_at": "2025-10-18T07:01:02Z", "last_modified": "2025-10-18T07:01:02Z", "version": 1, "client_id": "api_client", "deleted": false } ] }`
  - List notes for a keyword: `GET /api/v1/notes/keywords/{keyword_id}/notes/?limit=50&offset=0`
    - Expected response (shape): `{ "keyword_id": 17, "notes": [ { "id": "a3f0...", "title": "Mitochondria", "version": 3, "deleted": false, "keywords": [ {"id":17, "keyword": "biology", ...} ] } ] }`
  - Unlink keyword from note: `DELETE /api/v1/notes/{note_id}/keywords/{keyword_id}`
    - Expected response: `{ "success": true, "message": "Note unlinked from keyword successfully." }`
  - Errors: `404 { "detail": "Note with ID '...' not found." }`, `404 { "detail": "Keyword with ID '...' not found." }`

- Prompts — search
  - Request: `POST /api/v1/prompts/search?search_query=embedding&search_fields=name&search_fields=details&page=1&results_per_page=10`
  - Expected response (PromptSearchResponse):
    `{
      "items": [
        {
          "id": 12,
          "uuid": "c9d3...",
          "name": "Dense Retrieval Prompt",
          "author": "alice",
          "details": "Guidelines for embedding-based retrieval...",
          "system_prompt": "You are a helpful...",
          "user_prompt": "Given the query ...",
          "keywords": ["retrieval","embedding"],
          "last_modified": "2025-10-18T10:00:00Z",
          "version": 4,
          "deleted": false,
          "relevance_score": 0.91
        }
      ],
      "total_matches": 3,
      "page": 1,
      "per_page": 10
    }`

- Prompts — export
  - Request (CSV): `GET /api/v1/prompts/export?export_format=csv&filter_keywords=retrieval&include_system=true&include_user=true&include_details=false&include_author=true&include_associated_keywords=true`
  - Request (Markdown): `GET /api/v1/prompts/export?export_format=markdown&markdown_template_name=Basic%20Template`
  - Expected response (ExportResponse):
    `{
      "message": "Export successful (2 prompts)",
      "file_content_b64": "UE5HLE5hbWUsQXV0aG9yLk4uLi4="
    }`

- Prompts — keywords export (CSV)
  - Request: `GET /api/v1/prompts/keywords/export-csv`
  - Expected response (ExportResponse):
    `{
      "message": "Successfully exported 12 active prompt keywords",
      "file_content_b64": "a2V5d29yZCxwcm9tcHRzX2NvdW50XG5SQUcsMTA..."
    }`

- Watchlists — generate output
  - Request: `POST /api/v1/watchlists/outputs`
  - Example body:
    `{
      "run_id": 123,
      "item_ids": [1001, 1002, 1007],
      "title": "Daily Tech Briefing",
      "type": "briefing_markdown",
      "format": "md",
      "template_name": "daily_md",
      "temporary": true,
      "deliveries": {
        "email": {
          "enabled": true,
          "recipients": ["me@example.com"],
          "attach_file": true,
          "body_format": "auto"
        },
        "chatbook": {
          "enabled": true,
          "title": "Tech Briefing",
          "description": "Auto-generated from watchlist run 123"
        }
      }
    }`
  - Notes: omit `item_ids` to include all ingested items for the run.
  - Expected response (WatchlistOutput):
    - `{ "id": 9001, "run_id": 123, "job_id": 77, "type": "briefing_markdown", "format": "md", "title": "Daily Tech Briefing", "content": "# Daily Tech...", "metadata": { "item_count": 3, "template_name": "daily_md" }, "version": 2, "expires_at": "2025-10-20T08:00:00Z", "created_at": "2025-10-19T08:00:10Z" }`

- Watchlists — list and download outputs
  - List: `GET /api/v1/watchlists/outputs?run_id=123&page=1&size=50`
  - Get metadata: `GET /api/v1/watchlists/outputs/{output_id}` (returns `format`, `title`, `expires_at`, etc.)
  - Download: `GET /api/v1/watchlists/outputs/{output_id}/download`
    - Content-Disposition filename uses title and `.{md|html}` based on `format`.
  - Expected list response:
    - `{ "items": [ { "id": 9001, "run_id": 123, "format": "md", "title": "Daily Tech Briefing", "expired": false, "created_at": "..." } ], "total": 1 }`

- Flashcards — import TSV/CSV
  - Request: `POST /api/v1/flashcards/import`
  - Body (JSON):
    `{
      "delimiter": "\t",
      "has_header": true,
      "content": "Deck\tFront\tBack\tTags\tNotes\nDefault\tWhat is RAG?\tRetrieval-Augmented Generation\tAI;RAG\tcore concept\nDefault\tCloze example {{c1::mask}}\t\tcloze;example\t"
    }`
  - Response: `{ "imported": N, "items": [{"uuid":"...","deck_id":1}, ...], "errors": [...] }`
  - Limits: see “Flashcards import limits” in Schema Notes.
  - Sample error entries in `errors`:
    - `{ "line": null, "error": "Maximum import line limit reached (10000)" }`
    - `{ "index": 3, "error": "Field too long: Front (> 8192 bytes)" }`
    - `{ "index": 7, "error": "Invalid cloze: Front must contain one or more {{cN::...}} patterns" }`

- Flashcards — APKG export
  - Request (CSV): `GET /api/v1/flashcards/export?deck_id=1&format=csv&include_header=true&delimiter=%09`
  - Request (APKG): `GET /api/v1/flashcards/export?deck_id=1&format=apkg`
  - Example cURL: `curl -L "$BASE/api/v1/flashcards/export?deck_id=1&format=apkg" -H "Authorization: Bearer $TOKEN" -o deck.apkg`
  - Expected response (APKG):
    - Binary stream; headers include `Content-Type: application/octet-stream` and `Content-Disposition: attachment; filename="<deck>.apkg"`.

Sample Error Responses
- Watchlists outputs (POST /watchlists/outputs)
  - `404 { "detail": "run_not_found" }`
  - `404 { "detail": "job_not_found" }`
  - `400 { "detail": "items_must_belong_to_run" }`
  - `400 { "detail": "no_items_available" }`
  - `400 { "detail": "invalid_template_name" }`
  - `404 { "detail": "template_not_found" }`
  - `400 { "detail": "invalid_format" }`
- Notes update/delete without correct version header
  - `409 { "detail": "version_conflict" }`

- Watchlists — create job
  - Request: `POST /api/v1/watchlists/jobs`
  - Example body:
    `{
      "name": "Tech Daily",
      "description": "Top tech headlines",
      "scope": {"sources": [1,2], "groups": [10], "tags": ["ai","ml"]},
      "schedule_expr": "0 8 * * *",
      "timezone": "UTC+8",
      "active": true,
      "max_concurrency": 4,
      "per_host_delay_ms": 1500,
      "output_prefs": {"template": "daily_md", "retention_days": 7},
      "job_filters": {
        "filters": [
          {"type": "keyword", "action": "include", "value": {"terms": ["AI","LLM"], "scope": "title"}, "priority": 1},
          {"type": "regex", "action": "exclude", "value": {"pattern": "(?i)rumor|sponsored"} }
        ],
        "require_include": true
      }
    }`

- Watchlists — preview candidates (no ingest)
  - Request: `POST /api/v1/watchlists/jobs/{job_id}/preview?limit=20&per_source=10`
  - Example response (shape):
    `{
      "items": [
        {"source_id": 1, "source_type": "rss", "url": "https://...", "title": "...", "summary": "...", "decision": "ingest", "matched_action": "include"},
        {"source_id": 2, "source_type": "site", "url": "https://...", "title": "...", "summary": "...", "decision": "filtered", "matched_action": "exclude", "matched_filter_key": "regex:rumor"}
      ],
      "total": 25,
      "ingestable": 12,
      "filtered": 13
    }`

- Notes — optimistic concurrency (error)
  - Update requires header `expected-version: <int>`; stale version triggers 409.
  - Example request: `PATCH /api/v1/notes/{id}` with body `{ "content": "New text" }` and header `expected-version: 3`.
  - Example 409 response:
    `{ "detail": "version_conflict" }`
  - Clients should re-fetch the note, read the current `version`, and retry with the latest value.


AuthNZ & Headers
- Modes: single_user (X-API-KEY) and multi_user (Authorization: Bearer <JWT>)
- Background-only header injection; never expose tokens to content scripts.
- WS STT: token passed as query param (?token=...) as supported by server.

Architecture
- MV3 background service worker owns all network I/O (fetch/SSE) and WS STT.
- Content scripts do not call server directly; they message background.
- Streaming: background uses fetch + ReadableStream to parse SSE; forwards frames to UI via ports.
- Drift guard: On startup, background optionally fetches /openapi.json and logs missing required paths (advisory).

Permissions & CSP (least privilege)
- Chromium: use optional_host_permissions for the configured server origin; do not request broad host globs by default.
- Firefox: minimize host wildcards; no webRequest/webRequestBlocking unless absolutely required.
- Remove unused permissions (e.g., declarativeNetRequest) to ease store review.

Security & Privacy
- Token storage policy: access tokens in background memory or session storage; refresh tokens optionally persisted in local storage; never store or expose tokens in content scripts; never log tokens.
- No telemetry; local-first.
- Sanitize and re-set auth headers in background before each fetch.

SSE & WS Behavior
- Headers: Accept: text/event-stream; Cache-Control: no-cache; Connection: keep-alive.
- Idle timeout: default ≥45s; reset on any event/data; abort on idle.
- Cancel: AbortController used to cancel long streams quickly.
- WS STT: binary frames; handle connection errors; fall back to file-based STT when blocked.

UX Flows (high level)
- Popup/Sidepanel
  - Tabs: Chat, RAG, Reading (Save Current Tab), Ingest (Process-only), Audio (STT/TTS)
  - Model/provider picker (optional)
- Context Menu
  - “Send to tldw_server” → POST /api/v1/media/add { url }
  - “Process page (no save)” → POST /api/v1/media/process-*
- Options Page
  - Server URL, auth mode, credentials; permissions grant to server origin
  - Stream idle timeout; connect tester; show OpenAPI drift warnings

Error Handling & Observability
- 401 refresh (multi-user) single-flight retry; show actionable messages on 429/402 with backoff.
- Surface friendly errors for size/type validation and unsupported URLs.
- Optional dev toggle for stream debug logging.

Testing Strategy
- Unit: SSE parser, header injection, request builders, URL→process-* classifier.
- Integration: chat stream with cancel; rag search; reading save; media add/process; STT/TTS.
- Manual: service worker suspend/resume, optional host permission grant/revoke.

Rollout & Compatibility
- Chrome MV3 first; Firefox MV2 compatibility tracked; Safari after.
- Require server exposing endpoints listed above; use drift guard to warn on mismatches.

Risks & Mitigations
- MV3 worker suspend: hold streams via long-lived ports; use idle timeout resets.
- Anti-scraping limits: rely on server throttling and robots compliance.
- Content variability: prefer URL submission to server; avoid raw DOM capture.

References
- Server APIs: see tldw_Server_API/README.md and Docs/Product/Content_Collections_PRD.md
- Extension implementation plan lives in the separate extension repo’s Extension-Plan-1.md
