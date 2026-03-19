## Stage 1: Inventory Visible PR Feedback
**Goal**: Enumerate the currently visible non-empty PR comments/review bodies and distinguish them from resolved inline threads.
**Success Criteria**: Every visible review item is classified as actionable, already fixed, or historical/no-op.
**Tests**: None
**Status**: Complete

### Inventory Snapshot
- PR `#911` still shows many visible comments/reviews even though unresolved inline threads are `0`.
- The visible surface was audited by separating:
  - actionable correctness issues
  - already-fixed items that still remain visible in historical review bodies
  - historical/no-op suggestions that do not justify more churn on this branch

### Already Fixed Before This Batch
- `web_scraping_service.py`: dead/orphaned locals removed
- `claims_review_metrics_scheduler.py`: caller-owned DB no longer passed into `asyncio.to_thread()`
- `database_retrievers.py`: `_db_adapter` now stays in sync after attach and attach failures propagate
- `test_media_transcripts_upsert.py`: missing `@pytest.mark.unit` added

### Fixed In This Batch
- `claims_service.py`: SQLite admin override rebuild path now preserves watchlist notification evaluation
- `slides.py`: `generate_from_media(...)` now types the dependency as `MediaDbSession`
- `embeddings_abtest_service.py`: A/B test helpers now use `MediaDbLike` instead of `Any`
- `media_module.py`: ownership fallback no longer treats any DB-like object as module-owned, and `_get_semantic_retriever(...)` now has an explicit return annotation
- `media_db/runtime/session.py`: request-owned `MediaDbSession` teardown now releases owned backend resources instead of leaving a request-owned pool alive

### Historical Or Explicitly No-Op
- `claims_clustering.py`: docstring-only suggestion, no behavioral issue
- `document_processing_service.py`: logging consistency suggestion only
- `sync_coordinator.py`: abstraction/style suggestion, no verified correctness bug
- `test_connectors_worker_file_sync.py`: test-style/lifecycle tracking nit only
- `document_references.py`: endpoint/raw-SQL architecture suggestion is valid but too large for this PR tail
- `process_code.py`: cosmetic typing/name suggestion; previously evaluated and not worth verification churn here
- `media_module.py`: broader public/private DB API consistency suggestion reduced to the verified ownership fix above; no further correctness issue established
- Qodo top-level comment: the `fts.py` typing issue, `main.py` raw-SQL issue, and `runtime/factory.py` explicit-backend issue were already fixed on the current branch head by the time this inventory was rechecked

## Stage 2: Address Actionable Items
**Goal**: Implement and verify any remaining valid review findings still visible on the PR.
**Success Criteria**: Actionable items are fixed or explicitly rejected with technical rationale.
**Tests**: Focused pytest for touched scope; Bandit on touched production scope
**Status**: Complete

### Verification
- `test_claims_service_override_db.py`
- `test_claims_rebuild_health_persistence.py`
- `test_claims_webhook_delivery.py`
- `test_claims_watchlist_notifications.py`
- `app/core/MCP_unified/tests/test_media_retrieval.py`
- `test_media_db_api_imports.py` focused import surfaces
- `test_slides_api.py -k from_media`
- Bandit on touched production files: `0` findings

## Stage 3: Close the PR Loop Accurately
**Goal**: Post an accurate PR update summarizing what remains visible and why.
**Success Criteria**: PR comment reflects exact current state without conflating threads, reviews, and top-level comments.
**Tests**: `git status --short` clean after push
**Status**: Complete

### PR Update
- Posted accurate PR status note: `issuecomment-4087103017`
- The note distinguishes:
  - visible review history on the PR page
  - unresolved inline thread count
  - remaining technically actionable items on the branch head
