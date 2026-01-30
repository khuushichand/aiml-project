## Stage 1: Backend cache keys + rate limit alignment
**Goal**: Scope insights/references caching per user/DB and include max_content_length; replace per-process rate limiting with RBAC dependency.
**Success Criteria**: Insights cache key includes user id + DB scope + max_content_length; references endpoint uses cached responses; endpoints register RBAC rate limit dependency.
**Tests**: Unit tests for cache key builders; cached path returns without hitting DB/LLM.
**Status**: Complete

## Stage 2: External enrichment + async safety
**Goal**: Add Crossref + arXiv enrichment using existing third-party modules and avoid blocking the event loop.
**Success Criteria**: References enrichment uses Semantic Scholar, Crossref, and arXiv when applicable; synchronous calls run in threads; enrichment source reports all used providers.
**Tests**: Unit tests for Crossref/arXiv data application helpers.
**Status**: Complete

## Stage 3: Frontend references UX
**Goal**: Add DOI/citations filters and expandable details to References tab UI.
**Success Criteria**: Filters toggle reference list; details expand to show raw text/metadata.
**Tests**: UI unit test for filter behavior (vitest).
**Status**: Complete

## Stage 4: Endpoint integration tests
**Goal**: Add backend endpoint tests for insights and references.
**Success Criteria**: Tests cover 200 paths and no-content/reference extraction behavior without external calls.
**Tests**: AsyncClient tests for /media/{id}/insights and /media/{id}/references.
**Status**: Complete
