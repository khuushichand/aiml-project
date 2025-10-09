# Dual-Backend RAG Regression Coverage Plan

This note captures the test strategy for validating that ingestion and RAG
flows behave consistently across the SQLite and PostgreSQL content backends.

## Goals
- Exercise the end-to-end ingestion + retrieval pipeline against both
  backends within the pytest suite (no external services beyond Postgres).
- Verify that claims, media search, and ChaCha notes retrieval produce
  equivalent results regardless of backend.
- Reuse the database backend factory to initialize either SQLite (tmpdir) or
  PostgreSQL (env-driven) instances without duplicating bootstrapping logic.

## Test Matrix
1. **Media ingestion parity** ✅
   - Implemented in `tests/RAG/test_dual_backend_end_to_end.py::test_dual_backend_media_and_claims_retrieval`.
   - Seeds media + claims and asserts `MediaDatabase.search_claims`,
     `ClaimsRetriever`, and `MediaDBRetriever` yield results on both backends.

2. **ChaCha notes/keywords parity** ✅
   - Implemented in `tests/RAG/test_dual_backend_end_to_end.py::test_dual_backend_notes_retrieval`.
   - Exercises `CharactersRAGDB` FTS rebuild/search and `NotesDBRetriever` for
     both SQLite and Postgres.

3. **Combined RAG query** ⏳
   - Future work: instantiate the full `DatabaseRetrieverSet` with hybrid
     scoring (including vector fallback) to ensure merged results remain
     consistent across backends.

## Implementation Notes
- Shared fixture `dual_backend_env` (see `tests/RAG/conftest.py`) now yields
  parametrised `(label, media_db, chacha_db)` pairs for SQLite and Postgres,
  resetting the Postgres schema before each test run.
- Tests seed data via the public database APIs to mirror production flows and
  rebuild FTS structures to guarantee parity.
- Postgres parametrisations are skipped automatically when psycopg2 or the
  required env vars are absent, keeping local developer runs lightweight.

## CI Hook
- GitHub Actions Postgres job now invokes `test_dual_backend_end_to_end.py`
  alongside the existing backend regression suite.

## Follow-Up Tasks
- Expand coverage to hybrid/vector retrieval once deterministic embedding
  fixtures are available in CI.
- Exercise ChaCha conversations/messages and analytics once their Postgres
  migrations are complete.
- Evaluate whether to reuse API-level e2e fixtures for a full-stack parity
  check after backend-level regression stabilises.
