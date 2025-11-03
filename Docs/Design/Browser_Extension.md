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
- RAG (streaming)
  - Request: `POST /api/v1/rag/search/stream`
  - Body minimal: `{ "query": "impact of CRISPR on gene therapy", "enable_generation": true, "top_k": 5 }`
  - Stream events: `delta` (answer tokens), optional `claims_overlay`, and final summary. Content-type `application/x-ndjson` or SSE with `data:` lines.
- Media add (persist)
  - `POST /api/v1/media/add` with JSON `{ "url": "https://example.com/article" }`
- Media process (no DB)
  - JSON URL: `POST /api/v1/media/process-pdfs` with `{ "urls": ["https://host/file.pdf"] }`
  - File upload: multipart to `/api/v1/media/process-pdfs` with `files=@/path/file.pdf`.
- STT (multipart)
  - `POST /api/v1/audio/transcriptions`
  - Fields: `file=@/path/audio.wav`, `model=whisper-1`, optional `language=en`, `response_format=json`.
  - Example cURL: `curl -X POST "$BASE/api/v1/audio/transcriptions" -H "Authorization: Bearer TOKEN" -F "file=@/abs/audio.wav" -F "model=whisper-1" -F "language=en"`


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
