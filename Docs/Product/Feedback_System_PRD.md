# Feedback System (Chat + RAG) PRD

## Overview
This PRD defines a unified feedback system that supports chat responses and RAG results via a shared explicit feedback endpoint, expands data capture for granular issues, and turns on implicit feedback collection by default. The goal is to improve response quality and retrieval/reranking using existing backend infrastructure (UnifiedFeedbackSystem) while adding missing API/UI and schema pieces.

## Goals
- Ship a shared explicit feedback endpoint for chat + RAG, backed by UnifiedFeedbackSystem.
- Capture per-response helpfulness, relevance (1-5), issue categories, and notes.
- Support message-level feedback (conversation/message IDs) and source-level feedback (document/chunk IDs).
- Always-on implicit feedback by default (click/copy/expand/dwell/citation_used) for personalization signals; disable via feature flag in regulated environments.
- Add UI hooks for quick thumbs + detailed modal in modern chat UI.

## Non-Goals
- Training or offline labeling pipelines.
- Auto-moderation of feedback content.
- Full analytics dashboards (server metrics already exist; UI not in scope).

## Users & Use Cases
- End users: quick thumbs up/down on responses.
- Power users: provide structured issues and notes, rate sources.
- System: capture implicit signals to improve reranking and personalization.

## Functional Requirements
1) Explicit feedback (shared endpoint)
- Accepts chat and RAG feedback in the same API.
- Stores conversation/message linkage when available.
- Supports per-response helpfulness, relevance scores, issues, notes.
- Supports per-source feedback by accepting document_ids and chunk_ids.

2) Implicit feedback (always-on by default)
- Records click/expand/copy/dwell/citation_used signals without UI.
- Captures session_id, optional query, optional doc_id, and rank.
- Dwell time recorded once per response to avoid spam.

3) Chat UI
- Always-visible feedback row under assistant, system, and tool messages (all persisted message types).
- Thumbs up/down sends immediate explicit feedback.
- Modal for detail: rating + issue checklist + free-form notes.
- Optional per-source thumbs when sources are expanded (Pro mode, API always accepts).

## Data Model
### ChaChaNotes (per-user DB)
Add issues column to conversation_feedback table.
- issues TEXT (JSON-encoded array of strings).

Example conversation_feedback row (logical):
```json
{
  "conversation_id": "C_...",
  "message_id": "M_...",
  "query": "how to reset auth",
  "document_ids": ["doc_1", "doc_2"],
  "chunk_ids": ["chunk_9"],
  "relevance_score": 3,
  "helpful": false,
  "issues": ["incorrect_information", "missing_details"],
  "user_notes": "It missed the new reset flow.",
  "created_at": "2024-03-10T12:01:02Z"
}
```

### Analytics DB (server-side QA)
Reuse existing feedback_analytics fields:
- feedback_type, rating, categories, improvement_areas.
Map issues into categories or improvement_areas for reporting.

## API Design

### Explicit Feedback (shared endpoint)
Endpoint: POST /api/v1/feedback/explicit

Request body (proposed):
```json
{
  "conversation_id": "C_...",
  "message_id": "M_...",
  "feedback_type": "helpful",
  "helpful": true,
  "relevance_score": 4,
  "document_ids": ["doc_1"],
  "chunk_ids": ["chunk_9"],
  "corpus": "media_db",
  "issues": ["not_relevant"],
  "user_notes": "The answer was about a different feature.",
  "query": "how to reset auth",
  "session_id": "sess_abc123",
  "idempotency_key": "fb_01HXYZ..."
}
```

Response:
```json
{
  "ok": true,
  "feedback_id": "fb_1709999999999_ab12cd34"
}
```

Notes:
- feedback_type is used for analytics classification (helpful|relevance|report).
- For chat feedback, message_id is required and conversation_id can be derived server-side if omitted.
- document_ids/chunk_ids enable source-level feedback in RAG or cited sources.
- issues is a free-form list but should use a canonical set in UI.
- query is optional; when omitted and message_id is present, the server derives it from message content (assistant/system/tool text) for feedback_id generation and analytics. If message_id is absent (RAG-only feedback), query is required.
- idempotency_key is optional; if provided, the server dedupes repeated submissions with the same key.
- corpus disambiguates document_ids across collections when source-level feedback is submitted; it should match the corpus/namespace from the original RAG request. Treat corpus as transient metadata only (do not persist in ChaChaNotes).

Auth + rate limits:
- Same auth requirements as other chat/RAG endpoints (AuthNZ/JWT or API key).
- Add a lightweight per-user rate limit to the explicit feedback endpoint to prevent spam.

Idempotency rule (if idempotency_key is omitted):
- Best-effort dedupe by (conversation_id, message_id, feedback_type, helpful, relevance_score) within a short window (e.g., 5 minutes). If a follow-up submission adds issues or user_notes, the server merges those fields instead of dropping the request (union issues, overwrite user_notes).
- For RAG-only feedback (no message_id), dedupe by (query, feedback_type, helpful, relevance_score, document_ids, chunk_ids) within the same window.

### Implicit Feedback (existing endpoint, expanded)
Endpoint: POST /api/v1/rag/feedback/implicit

Request body (expanded):
```json
{
  "event_type": "copy",
  "query": "how to reset auth",
  "doc_id": "doc_1",
  "rank": 2,
  "impression_list": ["doc_1", "doc_2", "doc_3"],
  "session_id": "sess_abc123",
  "conversation_id": "C_...",
  "message_id": "M_..."
}
```

Notes:
- Add event_type values: click|expand|copy|dwell_time|citation_used.
- Add dwell_ms for dwell_time events (required when event_type=dwell_time).
- citation_used should include doc_id and/or chunk_ids when available; otherwise omit and record as aggregate.
- Dwell time capture: emit once per response after a minimum threshold (e.g., 3s visible) and stop when the user sends a new message or navigates away.
- Citation used capture: emit when a user explicitly uses citations (copy-with-citations, insert citation, or similar UI action) and include the cited doc_id/chunk_ids when available.

## UX Requirements (Modern Chat UI)

### Quick Feedback Row
ASCII wireframe:
```text
+----------------------------------------------------+
| Assistant: The main function handles...            |
| ...                                                |
|                                                    |
| [Copy] [Regenerate] [Fork] [Reply]                 |
|                                                    |
| Was this helpful?  [Thumbs Up] [Thumbs Down] [...] |
+----------------------------------------------------+
```
- Show for assistant/system/tool messages (persisted message_id required).
- Thumb click sends immediate feedback with helpful=true|false.
- [...] opens detailed modal.

### Detailed Feedback Modal
```text
+-----------------------------------------------+
| Feedback                                  [X] |
+-----------------------------------------------+
| How would you rate this response?             |
| [*] [*] [*] [ ] [ ]  3/5                      |
| What was the issue? (select all that apply)   |
| [ ] Incorrect information                     |
| [ ] Not relevant to my question               |
| [ ] Missing important details                 |
| [ ] Sources were unhelpful                    |
| [ ] Too verbose / Too brief                   |
| [ ] Other                                     |
| Additional comments (optional)                |
| [.........................................]   |
| [Cancel]  [Submit Feedback]                   |
+-----------------------------------------------+
```
- issues uses canonical strings (see taxonomy below).
- Submitting sends relevance_score, issues, and user_notes.

### Source-Level Feedback (Pro mode)
```text
Sources (3)
+-----------------------------------+
| main.py:42                  [UP][DOWN] |
| utils.py:15                 [UP][DOWN] |
| docs.example.com            [UP][DOWN] |
+-----------------------------------+
```
- Emits explicit feedback with document_ids/chunk_ids and corpus.
- Pro mode is a client capability toggle only; API always accepts source-level feedback.

## Issue Taxonomy (Canonical IDs)
- incorrect_information
- not_relevant
- missing_details
- sources_unhelpful
- too_verbose
- too_brief
- other

## Non-Functional Requirements
- Always-on collection by default; implicit events can be disabled via feature flag IMPLICIT_FEEDBACK_ENABLED=false for regulated environments.
- Rate-limit explicit feedback to prevent spam.
- Implicit events are best-effort and non-blocking.
- No PII stored beyond existing user/session identifiers.

## Implementation Plan (Phases)
### Phase 1: API + Schema
- Add ExplicitFeedbackRequest + ExplicitFeedbackResponse.
- Implement POST /api/v1/feedback/explicit.
- Extend ImplicitFeedbackEvent schema for new event types + fields (dwell_ms, citation_used).
- Update UnifiedFeedbackSystem.submit_feedback to accept message_id and issues; handle corpus/idempotency at the endpoint (transient metadata + in-memory dedupe).
- Migration: add issues column to conversation_feedback (SQLite + Postgres).
- Add feature flag IMPLICIT_FEEDBACK_ENABLED (default true) to gate implicit events.

### Phase 2: Modern Chat UI (Quick Feedback)
- Track assistant/system/tool message IDs in chat UI (fetch with IDs).
- Add thumbs up/down row + optimistic UI.
- Wire to explicit feedback endpoint.

### Phase 3: Detailed Modal
- Add modal with rating, issues checklist, notes.
- Submit full payload with relevance_score, issues, user_notes.

### Phase 4: Source-Level + Implicit
- Add per-source feedback UI where sources are shown.
- Emit implicit signals (copy/click/expand/dwell/citation_used) with dwell_ms and citation identifiers when available.

## Risks & Mitigations
- Missing message IDs in UI: add optional message ID sidecar in chat messages API.
- Over-collection/noise: debounce implicit events; one dwell event per response.
- Schema drift: keep backward-compatible defaults and allow optional fields.

## Testing
- Unit tests: explicit feedback endpoint; schema validation; DB insertions.
- Integration tests: verify conversation_feedback.issues persisted.
- UI tests: thumbs submit path; modal submit path.
- Implicit tests: verify dwell_time requires dwell_ms and event_type expansion.
- Idempotency tests: repeated submissions dedupe as expected.

## Open Questions
- Explicit feedback for anonymous users with a fallback conversation_id: No.
- Feedback allowed on system/tool messages: Yes, allow both assistant and system/tool messages.
- Add a feature flag to disable implicit events in regulated environments: Yes.
