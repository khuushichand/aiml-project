## Stage 1: Design + alignment
**Goal**: Draft a design document for Collections feed ingestion with future email/webhook sources.
**Success Criteria**: Design doc exists in `Docs/Design/Collections_Feeds_Ingestion.md` with goals, data model, flows, and reference patterns.
**Tests**: N/A (doc-only).
**Status**: Complete

## Stage 2: Feed origin wiring (Watchlists -> Collections)
**Goal**: Allow RSS watchlists sources to land in Collections with an overridable origin.
**Success Criteria**: Watchlists pipeline supports `collections_origin` override; RSS items can be stored with origin `feed` without changing defaults.
**Tests**: `tldw_Server_API/tests/Watchlists/test_watchlists_pipeline.py::test_pipeline_origin_override_feed`.
**Status**: Complete

## Stage 3: Collections feed subscriptions wrapper (API)
**Goal**: Add a minimal Collections feed subscription API that provisions watchlists sources/jobs.
**Success Criteria**: Endpoints to create/list/delete feeds map to watchlists sources with `collections_origin=feed`.
**Tests**: New unit/integration tests for feed endpoints.
**Status**: Complete

## Stage 4: WebSub + email/webhook ingestion (future)
**Goal**: Add WebSub subscriptions plus email/webhook ingestion paths that target Collections.
**Success Criteria**: Design-approved schema + endpoints exist for WebSub callbacks, email inboxes, and webhook sources.
**Tests**: WebSub verification + callback tests; email/webhook ingestion tests.
**Status**: Not Started
