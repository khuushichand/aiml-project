# tldw_server Browser Extension — Product Requirements Document (PRD)

- Version: 1.0
- Owner: Product/Engineering (You)
- Stakeholders: tldw_server backend, Extension frontend, QA
- Target Browsers: Chrome/Edge (MV3), Firefox (MV2)

## Background
You’ve inherited the project and an in‑progress extension. The goal is to ship an official, whitelabeled extension that uses tldw_server as the single backend for chat, RAG, media ingestion, notes, prompts, and audio (STT/TTS). The server provides OpenAI‑compatible APIs and mature AuthNZ (single‑user API key and multi‑user JWT modes).

## Goals
- Deliver an integrated research assistant in the browser that:
  - Chats via `/api/v1/chat/completions` with streaming and model selection.
  - Searches via RAG (`POST /api/v1/rag/search` and `GET /api/v1/rag/simple` if exposed).
  - Ingests content (current page URL or manual URL) via `/api/v1/media/process` and related helpers.
  - Manages notes and prompts through their REST endpoints.
  - Transcribes audio via `/api/v1/audio/transcriptions`; synthesizes speech via `/api/v1/audio/speech`.
- Provide smooth setup (server URL + auth) and a robust, CORS‑safe network layer.
- Ship an MVP first and iterate with clear milestones.

## Non‑Goals
- Building a general proxy for arbitrary third‑party LLM services.
- Adding server features not exposed by tldw_server APIs.
- Collecting telemetry on user content or behavior.

## Personas
- Researcher/Student: Captures web content, asks questions, organizes notes.
- Developer/Analyst: Tries multiple models/providers, tweaks prompts, exports snippets.
- Power user: Uses voice (STT/TTS), batch ingest, and RAG filters.

## User Stories (MVP‑critical)
- As a user, I configure the server URL and authenticate (API key or login).
- As a user, I see available models/providers and select one for chat.
- As a user, I ask a question and receive streaming replies with cancel.
- As a user, I search with RAG and insert results into chat context.
- As a user, I send the current page URL to the server for processing and get status.
- As a user, I quickly capture selected text as a note and search/export notes.
- As a user, I upload a short audio clip for transcription and view the result.

## Scope

### MVP (v0)
- Settings: server URL, auth mode (single/multi), credentials, health check.
- Auth: X‑API‑KEY and JWT (login/refresh/logout); error UX for 401/403.
- Models: discover and select model/provider from server.
- Chat: non‑stream and SSE stream; cancel; basic local message history.
- RAG: simple search UI; insert snippets into chat context.
- Media: ingest current tab URL or entered URL; progress/status.
- Notes/Prompts: basic create/search/import/export.
- STT: upload wav/mp3/m4a; show transcript.

### v1
- TTS playback; voice catalog/picker.
- Context menu “Send to tldw_server”.
- Improved RAG filters (type/date/tags).
- Robust error recovery and queued retries.

### v1.x
- Batch operations; offscreen processing where safe.
- MCP surface (if required later).

## Functional Requirements

### Settings and Auth
- Allow any `serverUrl` (http/https); validate via a health check.
- Health check path: `GET /api/v1/health` (optional lightweight: `/healthz`, readiness: `/readyz`). Treat non-200 as not ready.
- Modes: Single‑User uses `X-API-KEY: <key>`. Multi‑User uses `Authorization: Bearer <access_token>`.
- Manage access token in memory; persist refresh token only when necessary.
- Auto‑refresh on 401 with single‑flight queue; one retry per request.
- Never log secrets; redact sensitive fields in errors.

- MV3 token lifecycle: persist refresh token in `chrome.storage.local` to survive service worker suspension/restart; keep access token in memory (or `chrome.storage.session`). On background start, attempt auto‑refresh when a refresh token exists; use single‑flight refresh queue on 401.

### Network Proxy (Background/Service Worker)
- All API calls originate from background; UI/content never handles tokens directly.
- Optional host permissions per configured origin at runtime; least privilege.
- SSE support: set `Accept: text/event-stream`, parse events (including handling `[DONE]` sentinel), keep‑alive handling, `AbortController` cancellation.
- Timeouts with exponential backoff (jitter). Offline queue for small writes.
- Propagate an `X-Request-ID` header per request for correlation and idempotent retries.

### API Path Hygiene
- Match the server’s OpenAPI exactly, including trailing slashes where specified, to avoid redirects and CORS quirks.
- Core endpoints:
  - Chat: `POST /api/v1/chat/completions`
  - RAG: `POST /api/v1/rag/search`, `POST /api/v1/rag/search/stream`, `GET /api/v1/rag/simple`
  - Media: `POST /api/v1/media/process`
  - Notes: `/api/v1/notes/...` (search may require a trailing slash; align to spec)
  - Prompts: `/api/v1/prompts/...`
  - STT: `POST /api/v1/audio/transcriptions`
  - TTS: `POST /api/v1/audio/speech`
  - Voices: `GET /api/v1/audio/voices/catalog`
  - Providers/Models: `GET /api/v1/llm/providers` (and `/llm/models` if present)
- Centralize route constants; do not rely on client‑side redirects.

#### Trailing Slash Rules (Notes/Prompts)
- Notes:
  - List/Create: `GET/POST /api/v1/notes/` (trailing slash required)
  - Search: `GET /api/v1/notes/search/` (trailing slash required)
  - Item: `GET/DELETE/PATCH /api/v1/notes/{id}` (no trailing slash)
  - Keywords collections use trailing slash, e.g., `/api/v1/notes/keywords/`, `/api/v1/notes/keywords/search/`, `/api/v1/notes/{note_id}/keywords/`
- Prompts:
  - Base: `GET/POST /api/v1/prompts` (no trailing slash)
  - Search: `POST /api/v1/prompts/search` (no trailing slash)
  - Export: `GET /api/v1/prompts/export` (no trailing slash)
  - Keywords collection: `/api/v1/prompts/keywords/` (trailing slash)

### API Semantics
- Chat SSE shape: Expect OpenAI-style chunks with "delta" objects, then "[DONE]". Parse lines like `data: {"choices":[{"delta":{"role":"assistant","content":"..."}}]}` and terminate on `[DONE]`.
- RAG streaming is NDJSON (not SSE). Treat each line as a complete JSON object; do not expect `[DONE]`. Endpoints: `POST /api/v1/rag/search/stream` (stream), `GET /api/v1/rag/simple` (simple retrieval).
- Health signals: `GET /api/v1/health` returns status "ok" (200) or "degraded" (206). Treat any non-200 as not ready during setup. Use `/readyz` (readiness) and `/healthz` (liveness) for lightweight probes.

References:
- Chat SSE generator: `tldw_Server_API/app/api/v1/endpoints/chat.py:1256`
- RAG endpoints: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py:664, 1110, 1174`
- Health endpoints: `tldw_Server_API/app/api/v1/endpoints/health.py:97, 110`

### Chat
- Support `stream: true|false`, model selection, and OpenAI‑compatible request fields.
- Pause/cancel active streams; display partial tokens.
- Error UX: connection lost, server errors, token expiration.
- SSE streaming must detect and handle the `[DONE]` sentinel to terminate cleanly; keep the service worker alive during streams (e.g., via a long‑lived Port from the side panel).

### RAG
- Query field, minimal filters; result list with snippet, source, timestamp.
- Insert selected snippets into chat as system/context or user attachment.

### Media Ingestion
- Current tab URL ingestion; allow manual URL input.
- Show progress/toasts and final status; handle failures gracefully.
- Display progress logs from the server response where present; if a job identifier is returned, poll status with exponential backoff and provide cancel.

### Notes and Prompts
- Create note from selection or input; tag and search.
- Browse/import/export prompts; insert prompt into chat.

### STT
- Upload short audio (<= 25 MB MVP); show transcript with copy.
- Validate mime types; surface server validation errors.

### TTS (v1)
- Voice list fetch; synthesize short text; playback controls; save last voice.

## Non‑Functional Requirements

### Security & Privacy
- No telemetry; no content analytics; local‑only diagnostics toggled by user.
- Keep access tokens in memory in background; persist refresh tokens only if required.
- Never expose tokens to content scripts; sanitize logs.

### Performance
- Background memory budget < 50 MB steady‑state.
- Chat stream first token < 1.5s on LAN server.
- Bundle size targets: side panel < 500 KB gz (MVP); route‑level code splitting.

### Reliability
- Resilient to server restarts; retries with backoff; idempotent UI state.
- Offline queue for small writes (e.g., notes) with visible status.

### Compatibility
- Chrome/Edge MV3 using service worker; Firefox MV2 fallback.
- Feature‑detect offscreen API; don’t hard‑rely on it.

### Accessibility & i18n
- Keyboard navigation, ARIA roles for side panel.
- Strings ready for localization; English default.

## Architecture Overview

### Background/Service Worker
- Central fetch proxy, SSE parsing, retries, 401 refresh queue, permission prompts.

### UI Surfaces
- Side panel (chat, RAG, notes/prompts, STT/TTS).
- Options page (server/auth/settings).
- Popup (quick actions/status).

### Content Script
- Selection capture; page metadata for ingest; no secret handling.

### State & Storage Policy
- Background state store; message bus to UIs; `chrome.storage` for non‑sensitive prefs.
- Do not store user content by default beyond session state.
- Optional local cache for small artifacts with TTL and user clear.
- Persist only refresh tokens (encrypted at rest if available) in `chrome.storage.local`; keep access tokens ephemeral (memory or `chrome.storage.session`).

## CORS & Server Config
- Prefer background‑origin requests with explicit `host_permissions`/`optional_host_permissions`.
- Server should allow CORS for the extension origin; for dev, wildcard allowed on localhost.
- Avoid blocking `webRequest` in MV3; use direct fetch and headers in background.

## Success Metrics
- 80%+ users complete setup within 2 minutes.
- < 5% request error rate in normal operation.
- Streaming starts within 1.5s on LAN; steady memory < 50 MB.
- > 90% of API paths hit without 307 redirects (path hygiene).

## Milestones and Deliverables

### Milestone 1: Connectivity & Auth (Week 1–2)
- Options page with server URL and auth.
- Background proxy with health check.
- Acceptance: Successful health ping; auth tokens handled; 401 refresh working.

### Milestone 2: Chat & Models (Week 3–4)
- Fetch providers/models; chat non‑stream and stream; cancel.
- Acceptance: Streaming chat across at least two models; SSE cancel; exact path matching.

### Milestone 3: RAG & Media (Week 5–6)
- RAG search with snippet insertion; URL ingest with progress.
- Acceptance: RAG returns results; snippet insert; ingest completes with status notifications.

### Milestone 4: Notes/Prompts & STT (Week 7–8)
- Notes CRUD + search; prompts browse/import/export; STT upload/transcribe.
- Acceptance: Notes searchable; prompts import/export; successful transcript for a ~20s clip.

### Milestone 5: TTS & Polish (Week 9–10)
- TTS synthesis/playback; voice list; UX polish and accessibility checks.
- Acceptance: Voice picker works; playable audio from `/api/v1/audio/speech`.

## Acceptance Criteria (Key)
- Path Hygiene: All requests hit exact API paths defined by OpenAPI; no 307s observed in logs.
- Security: Tokens never appear in UI or console logs; content scripts lack access to tokens.
- SSE: Streaming responses parsed without memory leaks; recognizes `[DONE]`; cancel stops network within ~200ms.
- Retry/Refresh: 401 triggers single‑flight refresh; queued requests replay once; exponential backoff with jitter for network errors.
- Permissions: Optional host permissions requested only for user‑configured origin; revocation handled gracefully.
- Media: Ingest current tab URL; show progress and final status; errors actionable.
- STT/TTS: Supported formats accepted; errors surfaced with clear messages.
- 429 Handling: Honors `Retry-After` on rate limits; UI presents retry timing.
- Streaming Memory: No unbounded memory growth during 5‑minute continuous streams; remains within budget.

## Dependencies
- Server availability and correct CORS config.
- Accurate OpenAPI spec and stability of endpoints.
- Browser APIs: `storage`, `side_panel`, `contextMenus`, `notifications`, `offscreen` (optional), message passing.

## Risks & Mitigations
- Endpoint variance (e.g., trailing slashes): Centralize route constants; validate against OpenAPI on startup and warn.
- Large uploads: Enforce size caps in UI; add chunking later if required.
- Firefox MV2 constraints: Document broader host permissions; polyfill SSE parsing if needed.

## Out of Scope (for MVP)
- Full chat history sync with server.
- Advanced MCP tools integration.
- Batch operations and resumable uploads.

## Resolved Decisions
- Canonical API key header: `X-API-KEY` (single‑user). Multi‑user uses `Authorization: Bearer <token>`.
- Model discovery: Prefer `GET /api/v1/llm/providers` (authoritative provider→models); `GET /api/v1/llm/models` available as aggregate.
- Trailing slashes: See “Trailing Slash Rules (Notes/Prompts)” above (notes search and collections require trailing slash; prompts base/search do not).
- Dev HTTPS: Prefer HTTP on localhost; for HTTPS, trust a local CA or enable Chrome’s localhost invalid‑cert exception; ensure server CORS allows the extension origin.

## Developer Validation Checklist
- Connectivity & Auth
  - Set server URL and verify `GET /api/v1/health` succeeds.
  - Single‑user: requests with `X-API-KEY` succeed; Multi‑user: login/refresh/logout succeeds and access token auto‑refreshes after service worker suspend/resume.
- Path Hygiene
  - All calls are 2xx without redirects (no 307); Notes/Prompts follow trailing‑slash rules.
- Chat
  - Non‑stream and SSE stream both work; `[DONE]` handled; cancel closes network <200ms; models list loads from `/api/v1/llm/providers`.
- RAG
  - `POST /api/v1/rag/search` returns results; `GET /api/v1/rag/simple` works; `POST /api/v1/rag/search/stream` NDJSON parsed correctly.
- Media
  - Current tab URL ingest works; progress logs displayed; failures surface actionable errors; job polling (if job id present) functions with backoff.
- Notes & Prompts
  - Notes CRUD + `GET /api/v1/notes/search/` (with slash) work; Prompts base/search work; keywords endpoints reachable.
- Audio
  - STT accepts <= 25 MB and returns transcript; TTS synthesizes and plays; voices catalog fetched.
- Reliability
  - 429 responses respect `Retry-After`; 5xx/network use exponential backoff with jitter; offline queue for small writes visible.
- Permissions
  - Only the configured server origin is granted host permission; revocation handled gracefully.
- CORS/HTTPS
  - Extension origin allowed by server; dev HTTP works; dev HTTPS usable with trusted cert or localhost exception.
- Metrics/Headers
  - `X-Request-ID` sent on requests and echoed; `traceparent` present in responses.
- Performance
  - Background steady memory < 50 MB; streaming memory stable over 5 minutes; first chat token < 1.5s on LAN.

## Glossary
- SSE: Server‑Sent Events; streaming over HTTP.
- MV3: Chrome Manifest V3.
- Background Proxy: Service worker owning all network I/O and auth.
