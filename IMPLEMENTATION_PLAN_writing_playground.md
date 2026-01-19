## Stage 1: Design + contracts
**Goal**: Lock down UI scope, data model, and server API contract for Writing Playground.
**Success Criteria**: Design doc completed; endpoints and storage schema agreed (ChaChaDB tables w/ soft-delete + versioning); extension route naming confirmed; capabilities handshake defined.
**Tests**: N/A (design only).
**Status**: Complete

## Stage 2: Server persistence + token utilities
**Goal**: Implement Writing Playground persistence endpoints, capability handshake, and tokenization utilities in tldw_server.
**Success Criteria**: ChaChaDB tables + migrations (soft-delete/versioning); CRUD for sessions/templates/themes; token count/tokenize endpoints; capabilities endpoint; AuthNZ + RBAC + rate limits; OpenAPI updated.
**Tests**: Unit tests for DB layer (versioning/soft-delete); integration tests for API endpoints + auth; contract tests for capabilities payload.
**Status**: Complete

## Stage 3: Extension playground UI + state
**Goal**: Build new Writing Playground page with full feature parity wired to server endpoints.
**Success Criteria**: Editor/overlay, sidebar controls, modals, TTS, import/export all functional; uses server-backed persistence; capability handshake gates unsupported features per provider; CSP-safe bundling (no external imports); one-time migration path from local storage if present.
**Tests**: Component tests for state actions; import/export JSON validation tests; markdown sanitization tests; smoke tests for core flows.
**Status**: In Progress

## Stage 4: Integration + validation
**Goal**: End-to-end validation and polish.
**Success Criteria**: Streaming generation works with logprobs; token highlighting + logit bias functional; provider gating verified; no CSP violations.
**Tests**: Integration tests for streaming + provider capability fallbacks; manual UI regression checklist.
**Status**: Not Started
