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
  - Searches via RAG (`/api/v1/rag/search` and `simple` if exposed).
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
- Modes: Single‑User uses `X-API-KEY: <key>`. Multi‑User uses `Authorization: Bearer <access_token>`.
- Manage access token in memory; persist refresh token only when necessary.
- Auto‑refresh on 401 with single‑flight queue; one retry per request.
- Never log secrets; redact sensitive fields in errors.

### Network Proxy (Background/Service Worker)
- All API calls originate from background; UI/content never handles tokens directly.
- Optional host permissions per configured origin at runtime; least privilege.
- SSE support: set `Accept: text/event-stream`, parse events, keep‑alive handling, `AbortController` cancellation.
- Timeouts with exponential backoff (jitter). Offline queue for small writes.

### API Path Hygiene
- Match the server’s OpenAPI exactly, including trailing slashes where specified, to avoid redirects and CORS quirks.
- Core endpoints:
  - Chat: `POST /api/v1/chat/completions`
  - RAG: `POST /api/v1/rag/search` (and `/rag/simple` if exposed)
  - Media: `POST /api/v1/media/process`
  - Notes: `/api/v1/notes/...` (search may require a trailing slash; align to spec)
  - Prompts: `/api/v1/prompts/...`
  - STT: `POST /api/v1/audio/transcriptions`
  - TTS: `POST /api/v1/audio/speech`
  - Voices: `GET /api/v1/audio/voices/catalog`
  - Providers/Models: `GET /api/v1/llm/providers` (and `/llm/models` if present)
- Centralize route constants; do not rely on client‑side redirects.

### Chat
- Support `stream: true|false`, model selection, and OpenAI‑compatible request fields.
- Pause/cancel active streams; display partial tokens.
- Error UX: connection lost, server errors, token expiration.

### RAG
- Query field, minimal filters; result list with snippet, source, timestamp.
- Insert selected snippets into chat as system/context or user attachment.

### Media Ingestion
- Current tab URL ingestion; allow manual URL input.
- Show progress/toasts and final status; handle failures gracefully.

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
- SSE: Streaming responses parsed without memory leaks; cancel stops network within ~200ms.
- Retry/Refresh: 401 triggers single‑flight refresh; queued requests replay once; exponential backoff with jitter for network errors.
- Permissions: Optional host permissions requested only for user‑configured origin; revocation handled gracefully.
- Media: Ingest current tab URL; show progress and final status; errors actionable.
- STT/TTS: Supported formats accepted; errors surfaced with clear messages.

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

## Open Questions
- Confirm canonical API key header name: proceeding with `X-API-KEY`. Any alternate accepted?
- Is `/api/v1/llm/models` present alongside `/api/v1/llm/providers`? If both, which is authoritative for selection?
- Do Notes/Prompts endpoints require trailing slash on search routes in current server build?
- Preferred handling for self‑signed HTTPS during development?

## Glossary
- SSE: Server‑Sent Events; streaming over HTTP.
- MV3: Chrome Manifest V3.
- Background Proxy: Service worker owning all network I/O and auth.

