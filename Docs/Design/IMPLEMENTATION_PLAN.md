## Implementation Plan — Browser Extension

This document tracks staged implementation with concrete success criteria and test notes.

---

## Stage 1: Connectivity & Auth
**Goal**: Establish server connectivity and both auth modes (API Key and JWT).

**Success Criteria**:
- Options page captures server URL and credentials; health check returns OK.
- Background proxy injects headers; tokens never exposed to content scripts.
- 401 triggers single‑flight refresh and one retry; no duplicate requests.

**Tests**:
- Unit: auth storage, header injection, refresh queue.
- Integration: health endpoint, login/logout, API key validation.
- Manual: revoke permission and re‑grant host permission flow.

**Status**: Not Started

---

## Stage 2: Chat & Models
**Goal**: Streaming chat via `/api/v1/chat/completions` with model selection.

**Success Criteria**:
- Models/providers fetched and rendered; selection persisted per session.
- Non‑stream and SSE stream both work; cancel stops network within ~200ms.
- Exact path strings (no 307 redirects observed in logs).

**Tests**:
- Unit: SSE parser, backoff, abort controller.
- Integration: stream across two models; cancel and resume.
- Manual: slow network simulation; ensure UI stays responsive.

**Status**: Not Started

---

## Stage 3: RAG & Media
**Goal**: RAG search UI and URL ingest with progress notifications.

**Success Criteria**:
- RAG `/api/v1/rag/search` returns results; snippets insert into chat context.
- URL ingest calls `/api/v1/media/process`; user sees progress and final status.
- Errors are actionable (permission, size limits, server busy).

**Tests**:
- Unit: request builders, snippet insertion.
- Integration: RAG queries; media process happy path and failure modes.
- Manual: ingest current tab URL; verify server reflects new media.

**Status**: Not Started

---

## Stage 4: Notes/Prompts & STT
**Goal**: Notes/Prompts basic flows and STT upload/transcribe.

**Success Criteria**:
- Notes: create/search; export works; selection‑to‑note from content script.
- Prompts: browse/import/export; insert chosen prompt into chat input.
- STT: upload short clip; transcript displayed; non‑supported formats fail clearly.

**Tests**:
- Unit: notes/prompts stores; MIME/type validation.
- Integration: `/api/v1/notes/*`, `/api/v1/prompts/*`, `/api/v1/audio/transcriptions`.
- Manual: 20s audio clip round‑trip; error message clarity for oversized files.

**Status**: Not Started

---

## Stage 5: TTS & Polish
**Goal**: TTS synthesis/playback and UX polish.

**Success Criteria**:
- Voices list loads from `/api/v1/audio/voices/catalog`; selection persisted.
- `/api/v1/audio/speech` returns audio; playback controls functional.
- Accessibility audit passes key checks; performance within budgets.

**Tests**:
- Unit: audio player controls and error states.
- Integration: voices catalog and synthesis endpoints.
- Manual: latency spot checks; keyboard navigation.

**Status**: Not Started

---

## Notes
- Centralize route constants and validate against OpenAPI at startup (warn on mismatch).
- Keep tokens in background memory; only persist refresh tokens if strictly necessary.
- Use optional host permissions for user‑configured origins (Chrome/Edge MV3).
