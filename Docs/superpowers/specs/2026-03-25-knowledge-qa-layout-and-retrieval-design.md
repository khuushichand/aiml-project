# Knowledge QA Layout And Retrieval Design

Date: 2026-03-25
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Improve the desktop Knowledge QA workspace so the main column uses the full available horizontal space, and fix the retrieval path that currently returns no evidence for natural-language questions against media that is already ingested but not chunk-indexed.

The approved product direction is:

- desktop research mode should use the full remaining width while keeping the evidence rail roughly as-is
- media-page usage should keep broad-source search behavior rather than hard-filtering to the current media item
- retrieval should still surface the current media item when it is relevant, even if it has no chunk rows yet

## Problem

Two separate issues are showing up in the current Knowledge QA experience.

### 1. The page looks cramped on desktop

The route already allows full width:

- [`option-knowledge.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-knowledge.tsx)

But the actual Knowledge QA layout reintroduces narrow caps inside the page shell:

- [`KnowledgeQALayout.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx)
- [`SearchBar.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx)

Current desktop research mode applies:

- `max-w-3xl` around the search shell and results shell
- `max-w-4xl` around the inner content
- `max-w-3xl` again inside the search form

This compresses the main workspace into a centered column even when there is ample room beside the history sidebar and evidence rail.

### 2. Retrieval can miss ingested media that should be findable

The reported example is media `892` queried with:

- `What was wrong with frieza's new form`

Observed UI outcome:

- no evidence sources
- no relevant context surfaced in the answer state

Local runtime investigation against the active user database found:

- media `892` exists in [`Media_DB_v2.db`](/Users/macbook-dev/Documents/GitHub/tldw_server2/Databases/user_databases/1/Media_DB_v2.db)
- the media row contains the Frieza transcript text in `Media.content`
- the item is not deleted or trashed
- the item has zero `MediaChunks`
- the item has zero `UnvectorizedMediaChunks`
- `media_fts` can match terms like `frieza` and `weakness`
- the current backend search path still returns zero documents for the full natural-language query

This means the UI is not inventing the empty state. The retrieval layer is returning no usable evidence for that query/media combination.

## Goals

- Remove unnecessary desktop width constraints from the main Knowledge QA workspace.
- Preserve the current compact behavior for simple mode, empty-state onboarding, and mobile.
- Keep media-page Knowledge QA in broad-source mode instead of forcing search to only the current media item.
- Make unchunked but ingested media discoverable through Knowledge QA when media-level content clearly matches the user question.
- Improve natural-language retrieval behavior without redesigning the full RAG pipeline.
- Preserve existing source filters such as `include_media_ids` and `include_note_ids`.

## Non-Goals

- Redesign the evidence rail itself.
- Change the product model so media-page Knowledge QA becomes single-media-only search.
- Rebuild or reprocess all historical media as part of this fix.
- Replace the full RAG ranking strategy or preset system.
- Redesign the mobile Knowledge QA layout.

## Current State

### Layout

The route shell already opts into full width:

- [`option-knowledge.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-knowledge.tsx)

The remaining desktop width loss comes from internal layout caps:

- [`KnowledgeQALayout.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx)
- [`SearchBar.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx)

### Retrieval

Knowledge QA currently defaults to:

- `search_mode: "hybrid"`
- `fts_level: "chunk"`

Defined in:

- [`unified-rag.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/rag/unified-rag.ts)

The retrieval path flows through:

- [`KnowledgeQAProvider.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx)
- [`chat-rag.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/services/tldw/domains/chat-rag.ts)
- [`unified_pipeline.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py)
- [`database_retrievers.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py)
- [`Media_DB_v2.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)

Relevant runtime finding:

- media-level retrieval currently routes through `search_media_db()`
- `search_media_db()` treats the natural-language question as one exact FTS/LIKE phrase
- the full sentence does not appear verbatim in the transcript, so the query returns zero matches even though important terms do appear

## Root Cause

The retrieval miss appears to be caused by two compounding issues.

### 1. Chunk-first defaults hide unchunked media

Knowledge QA defaults `fts_level` to `chunk`, but media `892` has no chunk rows.

That means chunk-level FTS has no material to search for this item even though the transcript is present in `Media.content`.

### 2. The media-level fallback is too strict for natural-language questions

When retrieval falls back to media-level search, it uses `search_media_db()` with the full sentence-like query. That path currently combines:

- `media_fts MATCH ?`
- a full-string `LIKE "%what was the issue with friezes new form%"`

This behaves more like exact-phrase matching than broad term retrieval. It misses relevant rows that contain the concepts but not the full sentence verbatim.

## Proposed Design

### 1. Expand the desktop research layout

Update the desktop research-mode layout in:

- [`KnowledgeQALayout.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx)
- [`SearchBar.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx)

Behavior changes:

- remove the `max-w-3xl` cap from the desktop research search/results shells
- remove the `max-w-4xl` cap from the desktop research inner content wrapper
- remove the search bar’s internal `max-w-3xl` limit when used in research mode
- keep prose-heavy answer text on a readable line length even when the surrounding workspace expands
- preserve existing centered/narrow behavior for simple mode
- preserve existing mobile behavior
- keep the evidence rail width approximately unchanged

Result:

- the main workspace uses the available width left by the history pane and evidence rail
- the page still feels structured because the evidence rail remains a fixed side column
- long-form answer content does not stretch into an unreadably wide measure on large displays

### 2. Keep media-page search broad, but let the current media stay competitive

No product change to force media-page Knowledge QA into single-item-only mode.

Behavior remains:

- search across the selected sources
- preserve the current ability to pin or include specific media ids
- do not hard-lock the query to only `media_id=892`

This matches the approved product direction and avoids suppressing useful nearby context from other sources.

### 3. Improve media retrieval query normalization for natural-language questions

Adjust the media-level retrieval path so natural-language questions can fall back to a broader FTS-friendly query instead of always being treated as one exact sentence.

Desired behavior:

- preserve explicit phrases only when the incoming query is already explicitly quoted
- keep the current strict sentence-like query as the first attempt
- only if that strict media-level attempt returns zero results, derive a second-pass fallback query
- build the fallback query from extracted search terms rather than the full sentence string
- discard obvious filler words such as `what`, `was`, `the`, `with`
- keep high-signal terms such as entities and domain words like `frieza`, `golden`, `form`, `weakness`
- avoid requiring the full sentence to appear verbatim in `title` or `content`

Implementation direction:

- reuse existing FTS normalization utilities where possible
- keep the change localized to the media retrieval path used by RAG
- do not change the public API contract of `/api/v1/rag/search`
- do not replace the current first-pass behavior globally for all `search_media_db()` callers
- use a bounded fallback strategy that prioritizes precision:
  - first pass: existing strict query behavior
  - second pass on zero results only: term-based media-level FTS fallback
  - respect current limits, ranking, and explicit media filters

### 4. Add an explicit fallback from chunk-level media retrieval to media-level retrieval

For Media DB retrieval only:

- if `fts_level == "chunk"` and chunk-level FTS returns no results
- fall back to media-level retrieval against `Media.content`
- if the media-level strict query also returns no results, allow the second-pass term-based fallback described above

This fallback should still respect:

- `allowed_media_ids`
- media type filters
- deleted/trash guards

This solves the case where content has been ingested into the media row but has not yet been chunked into `UnvectorizedMediaChunks` or `MediaChunks`.

### 5. Preserve existing filter semantics

The fix must not break:

- `include_media_ids`
- `include_note_ids`
- source selection
- hybrid search settings
- evidence rail rendering

The current media item should be able to surface strongly because it matches the query, not because the system silently converts broad-source search into a single-media search.

## Testing

### Frontend

Update Knowledge QA layout coverage to assert:

- desktop research mode no longer applies the narrow width caps to the main workspace
- desktop research mode still keeps answer prose within a readable content width
- simple mode still keeps the compact centered layout
- mobile remains unchanged

Likely touchpoints:

- [`KnowledgeQA.golden-layout.test.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx)

### Backend

Add focused retrieval tests to cover:

- an ingested media item with transcript text in `Media.content` but no chunk rows is still retrievable through the media retriever fallback
- a natural-language query like the Frieza example first misses under the strict media-level phrase path, then succeeds through the bounded term-based fallback
- explicit `include_media_ids` filtering still limits results correctly
- chunk-level retrieval still works normally when chunk rows do exist
- broadening remains bounded enough that the fallback does not ignore explicit filters or return an unbounded noisy set

Likely touchpoints:

- [`database_retrievers.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py)
- corresponding RAG retrieval tests under [`tldw_Server_API/tests`](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests)

### Verification

Before considering implementation complete:

- run targeted frontend Knowledge QA tests
- run targeted backend retrieval tests
- run at least one API-level integration test covering the real `/api/v1/rag/search` endpoint for the reproduced query shape
- run Bandit on the touched paths per repo policy
- manually confirm the query against media `892` returns evidence
- manually confirm the desktop Knowledge QA page uses the available horizontal space

## Risks

### Retrieval broadening risk

Broader media-level FTS can increase false positives if the normalization becomes too loose.

Mitigation:

- apply the broadening only to the media retrieval path that currently behaves too strictly
- keep result limits and scoring in place
- add tests that preserve explicit media filtering behavior

### Layout regression risk

Removing desktop width caps can make the page feel too loose if applied in the wrong mode.

Mitigation:

- limit the change to research mode on desktop
- leave simple mode and mobile untouched

## Open Questions

None for the approved design. The implementation plan can proceed directly from this spec.
