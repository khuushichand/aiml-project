# Knowledge QA Layout And Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen desktop Knowledge QA research mode so the main workspace uses the available horizontal space, and fix RAG retrieval so natural-language questions can still surface relevant ingested media when chunk rows are absent but `Media.content` matches.

**Architecture:** Keep the desktop layout change localized to the Knowledge QA shell and composer path, with a separate readability guard for answer prose. Keep the retrieval fix localized to `MediaDBRetriever` so the existing `/api/v1/rag/search` contract, source-selection semantics, and generic `search_media_db()` callers remain unchanged. Use a bounded two-pass fallback: chunk FTS first, then strict media retrieval, then term-based media retrieval only on zero results.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Vitest, Testing Library, Python 3, FastAPI, SQLite FTS5, pytest, Bandit

---

## File Map

- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
  Responsibility: remove the desktop research-mode width caps from the main workspace shell while preserving simple-mode and mobile behavior.
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`
  Responsibility: make the search form width opt-in so research mode can render full-width without changing every `SearchBar` consumer.
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/composer/KnowledgeComposer.tsx`
  Responsibility: pass the research-mode width behavior into `SearchBar` without changing unrelated call sites.
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
  Responsibility: preserve readable answer measure after the desktop shell expands.
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
  Responsibility: assert the research-mode shell is no longer artificially capped.
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx`
  Responsibility: guard the new search-bar width mode so only the intended usage loses the internal `max-w-3xl` cap.
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
  Responsibility: add chunk-to-media fallback and bounded natural-language media fallback while preserving `allowed_media_ids`, deleted/trash guards, and existing first-pass behavior.
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py`
  Responsibility: cover zero-result chunk fallback, second-pass media fallback, and filter preservation at the retriever level.
- Modify: `tldw_Server_API/tests/RAG/test_rag_selection_filters.py`
  Responsibility: lock in `allowed_media_ids` behavior after the retriever fallback path changes.
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py`
  Responsibility: verify the real `/api/v1/rag/search` path returns relevant media documents for the reproduced natural-language query shape used by Knowledge QA.
- Reference only: `Docs/superpowers/specs/2026-03-25-knowledge-qa-layout-and-retrieval-design.md`
  Responsibility: approved behavior contract and guardrails for implementation.

## Implementation Notes

- Do not change the product behavior so media-page Knowledge QA becomes single-media-only search.
- Do not change generic `search_media_db()` semantics for unrelated callers unless implementation proves the retriever-layer fix is impossible.
- Keep the evidence rail width approximately unchanged; widen only the main desktop research workspace.
- Preserve a readable text measure for answer prose even when the surrounding shell becomes full-width.
- Preserve filter semantics for `include_media_ids` / `allowed_media_ids` and existing deleted/trash exclusions.
- Keep the unrelated quick-ingest worktree edits out of staging and out of any commits for this task.

### Task 1: Guard The Desktop Research Layout Before Changing Classes

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/composer/KnowledgeComposer.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`

- [ ] **Step 1: Add failing desktop layout assertions**

Update `KnowledgeQA.golden-layout.test.tsx` so research mode expects:

- `knowledge-search-shell` to avoid the current `max-w-3xl` desktop cap
- `knowledge-results-shell` to avoid the current `max-w-3xl` desktop cap
- the research inner wrapper to avoid the current `max-w-4xl` cap

Update `SearchBar.behavior.test.tsx` so the new research-mode path proves:

- default `SearchBar` still keeps the compact `max-w-3xl` form width
- the opt-in wide mode removes that cap without changing accessibility or submission behavior

- [ ] **Step 2: Run the focused frontend tests to verify the current code fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx
```

Expected:
- FAIL because research mode still uses the internal `max-w-3xl` / `max-w-4xl` caps
- FAIL because `SearchBar` does not yet expose a research-mode width variant

- [ ] **Step 3: Implement the minimal desktop layout widening**

Make the smallest change set that satisfies the layout tests:

- remove the desktop research-mode shell caps in `KnowledgeQALayout.tsx`
- add a narrow-by-default width prop or equivalent explicit branch in `SearchBar.tsx`
- thread that opt-in through `KnowledgeComposer.tsx`
- add a prose-width guard in `AnswerPanel.tsx` so long answers stay readable after the shell expands

Guardrails:

- simple mode stays compact
- mobile stays unchanged
- evidence rail width stays roughly current size

- [ ] **Step 4: Re-run the focused frontend tests and then the nearby layout regressions**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx
```

Expected:
- PASS for the new research-mode width assertions
- PASS for existing layout and answer-state regressions

- [ ] **Step 5: Commit the frontend layout slice**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx apps/packages/ui/src/components/Option/KnowledgeQA/composer/KnowledgeComposer.tsx apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx
git commit -m "feat: widen desktop knowledge qa workspace"
```

### Task 2: Add Retriever Red Tests For Unchunked Natural-Language Media Fallback

**Files:**
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py`
- Modify: `tldw_Server_API/tests/RAG/test_rag_selection_filters.py`
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`

- [ ] **Step 1: Add failing retriever tests for the reproduced failure mode**

Extend `test_retrieval.py` with focused cases that cover all three behaviors:

- chunk-level retrieval returns zero rows, then falls back to media-level retrieval for the same media database item
- strict media search for a natural-language question returns zero rows, then a bounded term-based fallback returns the expected media document
- explicit `allowed_media_ids` still restrict the fallback results

Implementation preference for tests:

- use a temporary or in-memory `MediaDatabase`
- seed a media row with Frieza-like transcript text in `Media.content`
- do not add chunk rows for the fallback scenario
- keep at least one control case where chunk-level retrieval still returns chunk docs normally

Update `test_rag_selection_filters.py` only if the existing coverage needs a fallback-path assertion to prevent filter regressions.

- [ ] **Step 2: Run the backend unit tests to verify they fail for the intended reason**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py tldw_Server_API/tests/RAG/test_rag_selection_filters.py
```

Expected:
- FAIL because `MediaDBRetriever.retrieve()` currently returns early on empty chunk-level results
- FAIL because `_retrieve_via_backend()` currently treats the full sentence as one strict query with no bounded second pass

- [ ] **Step 3: Implement the minimal retriever-layer fallback**

In `database_retrievers.py`, implement the smallest change set that satisfies the new tests:

- when `fts_level == "chunk"` and `_retrieve_chunk_fts(...)` returns no documents, continue into media-level retrieval instead of returning immediately
- keep the current strict media query as the first pass
- if strict media retrieval returns zero results, derive a bounded term query from the natural-language input and retry once
- preserve `allowed_media_ids`, date filters, deleted/trash guards, and current max-result behavior

Prefer helper functions inside `database_retrievers.py` rather than changing the external API or broadening `search_media_db()` globally.

- [ ] **Step 4: Re-run the unit tests and the existing chunk-related regressions**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py tldw_Server_API/tests/RAG/test_rag_selection_filters.py tldw_Server_API/tests/RAG_NEW/unit/test_chunk_fts_integration.py tldw_Server_API/tests/RAG_NEW/unit/test_media_chunk_fts_metadata.py
```

Expected:
- PASS for the new fallback tests
- PASS for existing chunk-level metadata and integration coverage

- [ ] **Step 5: Commit the backend retriever slice**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py tldw_Server_API/tests/RAG/test_rag_selection_filters.py
git commit -m "fix: add knowledge qa media retrieval fallback"
```

### Task 3: Add API-Level Regression Coverage And Final Verification

**Files:**
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py`
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py` (only if the API-level test reveals missing plumbing)

- [ ] **Step 1: Add a failing `/api/v1/rag/search` regression test**

Add an integration test in `test_rag_doc_researcher_api.py` that exercises the real route with the same effective Knowledge QA request shape:

- source includes `media_db`
- search mode remains `hybrid` or `fts` as appropriate for the existing fixture style
- request explicitly uses `fts_level: "chunk"` so the route exercises the same chunk-first behavior the WebUI relies on
- seeded media has transcript text in `Media.content` but no chunk rows

Assertions:

- status code is `200`
- returned documents are non-empty
- the relevant media document is present in the response
- evidence metadata still respects explicit media filters when they are supplied

- [ ] **Step 2: Run the API integration test to verify it fails before any final adjustments**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py -k "natural_language_media_fallback"
```

Expected:
- FAIL if any route-level plumbing still drops the fallback result set or bypasses the intended chunk-level behavior

- [ ] **Step 3: Apply the smallest route-compatible fix if the API test exposes one**

Only if needed, adjust the retrieval plumbing so `/api/v1/rag/search` preserves the retriever fallback behavior under the same settings the frontend uses. Do not change the public request or response contract.

- [ ] **Step 4: Run the full targeted verification set**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx
bun run test:run -- ../packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx

source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py tldw_Server_API/tests/RAG/test_rag_selection_filters.py tldw_Server_API/tests/RAG_NEW/unit/test_chunk_fts_integration.py tldw_Server_API/tests/RAG_NEW/unit/test_media_chunk_fts_metadata.py
python -m pytest -q tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py -k "natural_language_media_fallback"
python -m bandit -r tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py -f json -o /tmp/bandit_knowledge_qa_layout_and_retrieval.json
```

Manual verification before merge:

- reproduce the original Knowledge QA query against the local app
- confirm the desktop layout uses the wider workspace
- confirm the evidence rail still renders normally
- confirm the Frieza query now returns evidence instead of `No relevant context found.`

- [ ] **Step 5: Commit any final API-level regression coverage or plumbing adjustments**

```bash
git add tldw_Server_API/tests/RAG_NEW/integration/test_rag_doc_researcher_api.py tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py
git commit -m "test: cover knowledge qa retrieval fallback at api level"
```
