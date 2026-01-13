## Stage 1: Reading Enhancements
**Goal**: Ship reading highlights UI and Pocket/Instapaper import/export.
**Success Criteria**: Users can create/edit/delete highlights in WebUI; import/export endpoints handle Pocket/Instapaper payloads and round-trip tags/status/notes.
**Tests**: Unit tests for import parsers; integration tests for /api/v1/reading/import and /api/v1/reading/export; UI smoke checks for highlights CRUD.
**Status**: Complete

## Stage 2: Outputs MECE/TTS Automation
**Goal**: Automate MECE/narrative + TTS output generation and expose Media DB ingest toggles.
**Success Criteria**: Outputs can generate MECE + TTS variants from a run or filter; toggles correctly ingest artifacts into Media DB when enabled.
**Tests**: Unit tests for template rendering variants; integration tests for /api/v1/outputs with MECE/TTS and ingest toggle.
**Status**: Complete

## Stage 3: Watchlists Streaming + Forums Phase 3
**Goal**: Add run streaming over WebSocket and gated forum ingestion.
**Success Criteria**: WS endpoint streams run status/logs; forum sources can be enabled via feature flag with safe throttling.
**Tests**: Integration tests for WS run stream; API tests for forum feature-flag gating.
**Status**: Complete

## Stage 4: Embeddings Worker Hardening
**Goal**: Validate embeddings queues and worker reliability under partial failures.
**Success Criteria**: Worker retries and backoff verified; offline Redis behavior covered; smoke test for full queue → embedding → retrieval path.
**Tests**: Embeddings jobs worker retry/backoff test; queue → embedding → retrieval smoke test; best-effort enqueue when queue unavailable.
**Status**: Complete

## Stage 5: Postgres Enablement
**Goal**: Make Collections/Watchlists schema and migrations Postgres-compatible.
**Success Criteria**: Migrations run on Postgres; core watchlists/collections flows pass against Postgres backend.
**Tests**: Postgres integration smoke tests for Collections and Watchlists tables via isolated fixture.
**Status**: Complete
