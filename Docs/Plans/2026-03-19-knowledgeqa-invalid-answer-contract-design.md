# KnowledgeQA Invalid Answer Contract Design

Date: 2026-03-19
Status: Approved

## Summary

Define a stricter `/knowledge` answer contract so Knowledge QA only renders human-readable, grounded answer text. Placeholder-like outputs such as `<template>` must be treated as invalid generated answers, not as successful AI answers. Retrieval results should remain visible, and the UI should fall back to a specific recovery state instead of showing a generic transport error.

## Problem

A user reported that a fresh `/knowledge` search returned the normal Knowledge QA shell but displayed a useless answer value:

- `Conversation thread 0 turns comparison workspace`
- `AI answer: <template>`

This indicates that retrieval and page rendering did not fail outright. The bug is that invalid generated answer content crossed the backend/frontend boundary and was rendered as if it were a legitimate answer.

## Product Decisions (Approved)

1. `/knowledge` must only show answers that are human-readable and grounded.
2. Placeholder output such as `<template>` must be treated as an invalid answer, not rendered directly.
3. Retrieval results should remain visible when answer generation fails, so the query is still partially useful.
4. Invalid generated answers should surface a specific no-answer or recovery state, not collapse into a generic `Search failed` banner.
5. The fix should cover fresh searches, including streaming, not just restored or shared conversation threads.
6. Streaming search must emit an explicit terminal status event so the frontend can distinguish `valid`, `invalid`, and `no-answer` outcomes.
7. Invalid-answer searches must not create durable assistant turns or pollute Knowledge QA comparison/history surfaces.

## Goals

- Prevent invalid placeholder outputs from rendering in Knowledge QA.
- Enforce a clear answer-validity contract at the backend/frontend boundary.
- Preserve successful retrieval results even when answer generation fails.
- Protect fresh searches from stale or malformed `generation_prompt` values.
- Add regression coverage for standard search, streaming search, and the `/knowledge` UI contract.

## Non-Goals

- Redesigning the broader RAG abstention UX.
- Rejecting normal readable abstention text such as "I don’t have sufficient grounded evidence..."
- Refactoring unrelated RAG retrieval, reranking, or citation systems.
- Standardizing every other RAG consumer in the repo in this design phase.

## Existing Repo Anchors

- Frontend Knowledge QA state and rendering:
  - `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
  - `apps/packages/ui/src/services/rag/unified-rag.ts`
- Frontend request transport:
  - `apps/packages/ui/src/services/tldw/domains/chat-rag.ts`
- Backend RAG endpoints and pipeline:
  - `tldw_Server_API/app/api/v1/endpoints/rag_unified.py`
  - `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
  - `tldw_Server_API/app/core/RAG/rag_service/generation.py`
- Existing Knowledge QA tests:
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`

## Approaches Considered

### 1. UI-only guard

Detect `<template>` and similar placeholders only in Knowledge QA UI state and refuse to render them.

Pros:

- Smallest blast radius
- Fastest user-facing fix

Cons:

- Leaves the backend contract undefined
- Allows other RAG consumers to keep receiving invalid answers
- Does not explain or classify the failure cause

### 2. Backend-only contract

Validate generated answers in the unified RAG pipeline and return `null` plus metadata when output is invalid.

Pros:

- Establishes a single source of truth
- Protects all callers using the endpoint

Cons:

- Higher blast radius
- Older or alternate clients could still mishandle malformed payloads

### 3. Layered fix (Recommended)

Validate invalid answers in the backend, keep a narrow defensive guard in Knowledge QA UI, and normalize risky `generation_prompt` input before request dispatch.

Pros:

- Fixes the root cause and the immediate UX symptom
- Protects `/knowledge` even if an older server or alternate path returns malformed output
- Preserves retrieval results with explicit failure semantics

Cons:

- Slightly larger implementation than a UI-only patch

## Recommended Design

### Answer Contract

Knowledge QA should only treat an answer as valid when it is:

- non-empty after trimming
- plausibly human-readable
- not a known placeholder sentinel

Invalid outputs must be normalized to `null` and annotated with structured metadata instead of rendered directly.

### Invalid Answer Detection

The detector should be conservative and sentinel-based. In v1, reject only outputs that are clearly unusable as user-facing answers:

- empty or whitespace-only strings
- exact placeholder sentinel values from a shared normalized denylist
- single-tag strings only when the tag name itself is on that sentinel denylist

Do not reject:

- explicit abstention text
- readable low-confidence guidance
- short but valid answers

Initial denylist for this fix:

- `<template>`

Any future additions must be explicit, shared across backend and frontend normalization, and backed by regression tests. Generic markup or code-looking output alone is not sufficient reason to reject an answer.

### Request-Time Guarding

Before dispatching a Knowledge QA request, the frontend should normalize persisted and in-session settings:

- if `generation_prompt` is blank, omit it
- if `generation_prompt` matches a placeholder sentinel such as `<template>`, omit it
- optionally record a debug or warning signal in Knowledge QA state so the issue is diagnosable without breaking the request

This protects fresh searches from stale persisted settings.

The backend must also apply the same guard to incoming `generation_prompt` values so older clients or non-Knowledge QA callers cannot force placeholder prompt configuration through the API surface.

### Backend Response Normalization

The unified RAG pipeline should validate the final generated answer before returning from standard search responses. If invalid:

- set the answer field to `null`
- keep retrieval results intact
- attach machine-readable metadata such as:
  - `generation_attempted: true`
  - `answer_status: "invalid"`
  - `answer_rejection_reason: "placeholder_output"` or `"invalid_generation_prompt"`

If the invalid state was caused by a rejected `generation_prompt`, the backend should drop that prompt from generation rather than forwarding it as a template name and record a distinct rejection/configuration reason.

### Streaming Completion Contract

The streaming endpoint needs an explicit terminal event so the frontend can finalize state without guessing from stream closure alone.

Recommended final event shape:

```json
{
  "type": "final",
  "generation_attempted": true,
  "answer_status": "valid",
  "answer_rejection_reason": null,
  "metadata": {}
}
```

Required fields:

- `type: "final"`
- `generation_attempted: boolean`
- `answer_status: "valid" | "invalid" | "none"`
- `answer_rejection_reason: string | null`

Rules:

- `valid`: the accumulated streamed answer is safe to commit as the visible answer
- `invalid`: generation ran but the accumulated answer was rejected
- `none`: no answer was attempted or no answer content was produced

Streaming must not rely on silent EOF to communicate invalid-answer status.

### Frontend Response Normalization

Knowledge QA should keep a defensive normalization step in `KnowledgeQAProvider`:

- standard response extraction treats invalid placeholder answers as `null`
- streaming accumulation keeps answer text in a provisional buffer
- if the provisional buffer exactly matches or is a strict prefix of a known sentinel such as `<template>`, it stays hidden
- streamed answer state is finalized only after the terminal `final` event confirms `answer_status`

This ensures `/knowledge` never renders `<template>` even if an older server or alternate endpoint path returns malformed content.

### UI State Selection

The UI should distinguish among three states:

1. generation disabled
   - existing "Enable in Settings" guidance remains
2. generation attempted but invalid
   - show retrieval results
   - suppress the AI answer card
   - show a specific recovery state indicating that answer generation returned invalid output
3. valid answer
   - current Knowledge QA answer experience remains

Recommended recovery copy direction:

- "Sources were found, but answer generation returned invalid output."
- "Retry the search or review custom generation settings."

This is materially different from a connection or timeout error and should not reuse the generic error banner.

### Thread And History Persistence

Invalid-answer searches need explicit persistence rules so the UI does not create confusing empty thread shells.

For invalid-answer searches:

- do not persist a durable assistant message
- do not add a ConversationThread turn for comparison or prior-turn previews
- do not create a Knowledge QA history item in v1
- keep retrieval results and recovery UI visible only in the current active search state

If the current implementation creates a thread or persists the user message before answer classification, the implementation should either:

- defer durable persistence until answer validity is known, or
- roll back / suppress newly created user-only thread state when `answer_status = invalid`

The intended user experience is that invalid-answer searches remain visible as current-state search results, but do not become durable conversation artifacts.

## Data Flow

### Standard Search

1. Frontend builds request from persisted settings.
2. `generation_prompt` is normalized or dropped if clearly invalid.
3. Backend runs retrieval and generation.
4. Backend validates `generated_answer`.
5. Backend returns:
   - `answer: null` when invalid
   - retrieval results as usual
   - metadata describing invalid-answer status
6. Frontend uses metadata plus normalized answer value to choose the correct UI state.

### Streaming Search

1. Frontend starts streaming request.
2. Retrieval contexts may stream immediately and remain visible.
3. Answer deltas are buffered locally.
4. If the provisional buffer matches a known sentinel or sentinel prefix, it remains hidden.
5. The backend emits a terminal `final` event with answer validity status.
6. Frontend commits the buffered answer only when `answer_status = valid`.
7. If the final accumulated text is invalid, frontend keeps answer state as `null` and falls back to the invalid-answer recovery state.

## Error Handling

Invalid generated answers should be treated as a partial-success contract failure:

- retrieval succeeded
- answer generation ran
- generated output was rejected

That should not be surfaced as:

- offline
- timeout
- generic `Search failed`
- no results

Instead, the system should expose a specific reason code and use targeted recovery copy. This keeps debugging clear and avoids training users to mistrust all search failures equally.

## Testing Strategy

### Backend Unit Tests

Add focused tests covering the invalid-answer validator and pipeline normalization:

- readable prose answer passes unchanged
- whitespace-only answer becomes `null`
- `<template>` becomes `null` with invalid-answer metadata
- readable abstention text remains valid

Cover both:

- standard unified RAG response path
- streaming/finalization path, including the terminal `final` event payload

### Frontend Unit Tests

Add Knowledge QA tests covering:

- standard search returning `answer: "<template>"` suppresses answer rendering
- retrieval results still render
- invalid-answer recovery state appears
- streaming `<template>` does not become visible during or after search
- terminal `final` event with `answer_status = invalid` keeps answer state `null`
- placeholder `generation_prompt` in stored settings is not forwarded into live searches
- invalid-answer searches do not create durable thread/history artifacts

### End-to-End Contract Test

Extend the `/knowledge` workflow E2E coverage with deterministic stubs:

- `/api/v1/rag/search` returns one or more results plus `answer: "<template>"`
- `/api/v1/rag/search/stream` returns retrieval contexts, invalid placeholder output, and a terminal `final` event with `answer_status = invalid`

Assertions:

- the literal `<template>` is never visible
- retrieval/evidence content still renders
- the page shows the targeted recovery state instead of a generic error banner
- no new durable Knowledge QA turn/history artifact is exposed after the invalid-answer run

## Risks And Mitigations

### Risk: Over-aggressive invalid-answer detection

Mitigation:

- Keep the detector narrow and sentinel-based
- Add explicit tests for valid abstention text and short valid answers

### Risk: Standard and streaming paths diverge

Mitigation:

- Share answer validation logic conceptually and test both paths with the same sentinel cases

### Risk: UI masks backend regressions silently

Mitigation:

- Preserve backend metadata for invalid-answer classification
- Keep E2E assertions focused on both visible behavior and response shape where practical

## Recommendation

Implement the layered fix:

- backend answer validation and metadata
- frontend defensive guard for standard and streaming Knowledge QA responses
- request-time normalization of placeholder `generation_prompt`

This is the smallest design that addresses both the user-visible bug and the underlying contract gap without broad RAG redesign.
