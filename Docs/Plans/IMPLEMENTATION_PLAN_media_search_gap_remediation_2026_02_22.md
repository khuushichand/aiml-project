# Media Search Gap Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all identified `/media` search experience gaps by fixing refetch/pagination behavior, making metadata mode filtering/pagination correct, implementing real relevance boosting behavior, and backfilling missing integration/e2e coverage.

**Architecture:** Keep existing `ViewMediaPage` UX and payload structures, but move from competing refetch effects to a single fetch-orchestration path keyed by applied query + filters + pagination. Shift metadata-mode secondary filtering/sorting from client-side post-processing to backend query constraints so totals/pages stay authoritative. Wire `boost_fields` through backend relevance scoring (SQLite first-class, PostgreSQL explicit fallback behavior).

**Tech Stack:** React + React Query + Vitest (`apps/packages/ui`), FastAPI + Media DB query layer + Pytest (`tldw_Server_API`), Bandit for security gate.

---

## Gap Coverage

- Gap 1: Pagination/refetch regression and duplicate fetch churn in `ViewMediaPage`.
- Gap 2: Metadata mode applies “standard filters” after server pagination, causing incorrect totals and missed records.
- Gap 3: `boost_fields` controls are exposed but not applied by backend search.
- Gap 4: Missing integration/e2e tests for Stage 3 and Stage 4 acceptance criteria.

## Stage 1: Refetch/Pagination Orchestration Fix (Gap 1)
**Goal:** Make query/filter/page synchronization deterministic with no forced page resets and no duplicate refetches.

**Success Criteria:**
- Page changes triggered by pagination/arrow keys persist and fetch once.
- Debounced query changes reset to page 1 only when query actually changes.
- Filter changes reset to page 1 and trigger exactly one fetch.
- No direct `refetch()` calls remain in filter-change handlers.

**Files:**
- Modify: `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`
- Modify: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.permalink.test.tsx`

**Tasks:**
1. Add failing tests for:
   - page navigation not bouncing back to page 1 without query/filter changes,
   - one refetch for filter change when starting on page > 1,
   - one refetch for debounced query update under active filters.
2. Refactor `ViewMediaPage` to a single fetch trigger effect keyed by:
   - applied query (debounced),
   - search mode + filters,
   - `page` + `pageSize`,
   - manual “Search” trigger nonce if immediate search is retained.
3. Remove overlapping refetch effects and keep only one authoritative execution path.
4. Re-run tests; confirm request-count expectations.

**Verification Commands:**
- `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx src/components/Review/__tests__/ViewMediaPage.permalink.test.tsx`

**Status:** Complete

## Stage 2: Metadata Mode Server-Side Constraints (Gap 2)
**Goal:** Ensure metadata mode applies non-metadata constraints before pagination so totals/pages are accurate and complete.

**Success Criteria:**
- `/api/v1/media/metadata-search` accepts optional standard constraints used in metadata mode:
  - text query, media types, include keywords, exclude keywords, date range, sort.
- DB query layer applies these constraints before `LIMIT/OFFSET`.
- Frontend metadata mode removes client-only post-pagination pruning for these constraints.
- Pagination totals in metadata mode remain server authoritative.

**Files:**
- Modify: `apps/packages/ui/src/components/Review/mediaMetadataSearchRequest.ts`
- Modify: `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`
- Modify: `apps/packages/ui/src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts`
- Add or modify: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/listing.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py`
- Modify: `tldw_Server_API/tests/e2e/test_media_update_propagation.py`

**Tasks:**
1. Add failing backend endpoint tests proving metadata-search forwards new standard constraints.
2. Extend `search_by_metadata` endpoint args and pass new constraint bundle to DB method.
3. Extend `search_by_safe_metadata` to apply standard constraints in SQL before pagination.
4. Add/adjust e2e test to verify DOI/PMID metadata lookup with constraints still returns expected media.
5. Update frontend path builder to serialize these optional constraints.
6. Remove metadata-mode client-side filtering/sorting that currently runs after server pagination.
7. Add frontend integration test for metadata mode pagination + totals under constraints.

**Verification Commands:**
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py`
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/e2e/test_media_update_propagation.py -k metadata_search_normalization`
- `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx`

**Status:** Complete

## Stage 3: Real Relevance Boosting (Gap 3)
**Goal:** Make `boost_fields` materially affect search ordering, or explicitly disable behavior where unsupported.

**Success Criteria:**
- API receives and forwards `boost_fields` into search execution.
- SQLite FTS relevance scoring uses title/content weighting when provided.
- PostgreSQL path has explicit behavior:
  - either weighted relevance implemented, or
  - deterministic fallback with documented/observable “unsupported” behavior.
- UI behavior matches backend capability (no silent no-op).

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/listing.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Modify: `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
- Modify: `apps/packages/ui/src/components/Review/mediaSearchRequest.ts` (only if serialization/capability signaling changes)
- Modify: `apps/packages/ui/src/components/Review/__tests__/mediaSearchRequest.test.ts`
- Modify: `apps/packages/ui/src/components/Media/FilterPanel.tsx` and `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx` (if unsupported-mode UX is added)

**Tasks:**
1. Add failing DB-level search test showing score/order changes when title/content weights differ.
2. Thread `boost_fields` from endpoint to DB query.
3. Implement weighted relevance in SQLite FTS branch (`bm25(media_fts, title_w, content_w)`).
4. Implement or explicitly gate PostgreSQL behavior and test it.
5. If any backend path cannot honor weights, expose that in UI state (disable control or show warning).

**Verification Commands:**
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -k search`
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/DB_Management/test_media_postgres_support.py -k search`
- `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx`

**Status:** Complete

### Stage 3 completion (2026-02-22)
- Implemented backend `boost_fields` threading from `/api/v1/media/search` to DB search execution:
  - `tldw_Server_API/app/api/v1/endpoints/media/listing.py`
- Added `boost_fields` support in `search_media_db(...)` with value sanitization/clamping (`0.05` to `50.0`), and applied weighting in relevance sort paths:
  - SQLite: `bm25(media_fts, title_w, content_w)`
  - PostgreSQL: weighted `ts_rank(...)` expression with explicit weight vector literal.
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Stage 3 red tests now pass:
  - `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py::TestDatabaseFTS::test_fts_relevance_respects_boost_fields`
  - `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py::test_search_media_db_postgres_uses_weighted_ts_rank_when_boost_fields_set`
  - `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py::test_media_search_forwards_boost_fields`
- Additional targeted verification:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -k search` → `8 passed`
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/DB_Management/test_media_postgres_support.py -k search` → `2 passed`
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx` → `2 passed` files, `12 passed` tests.

## Stage 4: Test Coverage Backfill and Regression Net (Gap 4)
**Goal:** Close plan/implementation test gaps with integration-focused coverage and request-churn assertions.

**Success Criteria:**
- Integration coverage for no-results recovery actions from `ViewMediaPage` level:
  - clear search,
  - clear filters,
  - quick ingest event dispatch.
- Integration coverage for metadata mode end-to-end flow (DOI/PMID path) at UI level.
- Request-count test under rapid typing with active filters enabled.
- Regression test for “default path unchanged when advanced controls unused.”

**Files:**
- Add or modify: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/__tests__/mediaSearchRequest.test.ts`
- Optional: `apps/packages/ui/src/components/Media/__tests__/ResultsList.test.tsx` (retain component-level guardrails)

**Tasks:**
1. Add failing integration test for no-results recovery wiring in `ViewMediaPage`.
2. Add failing integration test that metadata mode query path is used and UI renders metadata snippets from response.
3. Add request-count test for rapid typing with at least one active filter.
4. Re-run full targeted media-search suite and ensure no flaky async timing assumptions.

**Verification Commands:**
- `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/ResultsList.test.tsx`

**Status:** Complete

### Stage 4 completion (2026-02-22)
- Expanded `ViewMediaPage` integration coverage in:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx`
- Added/verified integration coverage for no-results recovery wiring at `ViewMediaPage` level:
  - clear search (`onClearSearch`),
  - clear filters (`onClearFilters`),
  - quick-ingest event dispatch (`tldw:open-quick-ingest`).
- Extended metadata-mode integration assertion to verify UI rendering of metadata-derived snippets from backend response.
- Confirmed request-churn regression test remains in place under rapid typing with an active filter:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx`
    (`debounces rapid query changes before triggering refetch with active filters`)
- Confirmed default-path regression remains covered when advanced controls are unused:
  - `apps/packages/ui/src/components/Review/__tests__/mediaSearchRequest.test.ts`
    (`builds default payload with relevance sort`)
- Verification run:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/ResultsList.test.tsx`
  - Result: `4 passed` test files, `20 passed` tests.

## Stage 5: Final Security + Full Validation Gate
**Goal:** Verify touched scopes pass tests and security scan before declaring completion.

**Success Criteria:**
- All stage-targeted tests pass.
- Bandit shows no new findings in touched backend paths.
- Final summary maps each original gap to implemented fix + test evidence.

**Files:**
- No feature files; validation only.

**Tasks:**
1. Run frontend targeted suite for media search.
2. Run backend targeted suite for metadata search + search scoring.
3. Run Bandit on touched backend files.
4. Capture outputs in final execution note.

**Verification Commands:**
- `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx`
- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -k \"search or metadata\"`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media/listing.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py -f json -o /tmp/bandit_media_search_gap_remediation_2026_02_22.json`

**Status:** Complete

### Stage 5 completion (2026-02-22)
- Frontend targeted validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx src/components/Review/__tests__/ViewMediaPage.search-experience.integration.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx`
  - Result: `6 passed` test files, `34 passed` tests.
- Backend targeted validation:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/MediaDB2/test_metadata_endpoints_more.py tldw_Server_API/tests/MediaDB2/test_safe_metadata_endpoints.py tldw_Server_API/tests/MediaDB2/test_sqlite_db.py -k "search or metadata"`
  - Result: `18 passed`, `30 deselected`.
- Security validation (Bandit):
  - `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media/listing.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py -f json -o /tmp/bandit_media_search_gap_remediation_2026_02_22.json`
  - Result: no findings (`results: []`).

## Dependency Order

1. Stage 1 (frontend orchestration) first, because Stage 4 request-count assertions depend on stabilized refetch logic.
2. Stage 2 (metadata server constraints) before Stage 4 metadata integration tests.
3. Stage 3 (boost_fields backend support) can run after Stage 1; independent from Stage 2 except shared endpoint file.
4. Stage 5 last.

## Definition of Done (for this remediation)

- [x] Gap 1 fixed and covered by request-count + pagination persistence tests.
- [x] Gap 2 fixed with server-authoritative metadata totals/pages under constraints.
- [x] Gap 3 fixed with measurable boost effect (or explicit unsupported UX path).
- [x] Gap 4 fixed with integration/e2e coverage matching original plan expectations.
- [x] Bandit clean on touched backend scope.
