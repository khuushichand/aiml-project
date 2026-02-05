## Stage 1: Audit & Baseline
**Goal**: Identify current Knowledge QA flow, required APIs, and gaps for web fallback + persistence.
**Success Criteria**: Documented touchpoints (UI, API client, backend endpoints) and chosen approach.
**Tests**: None (inspection only).
**Status**: Complete

## Stage 2: Web Fallback Controls + Forced Enable
**Goal**: Add web fallback settings to RAG config, expose in Knowledge QA settings, and force-enable in requests.
**Success Criteria**: Knowledge QA sends `enable_web_fallback=true` and supports threshold/engine/merge settings in UI.
**Tests**: Manual query in Knowledge QA; confirm request payload includes web fallback fields.
**Status**: Complete

## Stage 3: Persist Knowledge QA Conversations
**Goal**: Create server-backed Knowledge QA threads and persist user/assistant messages + RAG context.
**Success Criteria**: A Knowledge QA search creates a server conversation, adds messages, and stores RAG context; Export uses server conversation ID.
**Tests**: Manual: run a query, verify messages saved via `/api/v1/chats/{id}/messages` and rag context endpoint.
**Status**: Complete
