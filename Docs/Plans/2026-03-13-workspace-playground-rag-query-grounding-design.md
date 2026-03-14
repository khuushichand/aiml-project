# Workspace Playground RAG Query Grounding Design

## Problem

`/workspace-playground` studio outputs still fail live for some RAG-backed artifact types even after the shared success/failure validation work. The remaining failure path is not backend storage corruption and not the artifact parser itself.

Live reproduction showed:

- `include_media_ids` works when the query contains document-specific terms.
- The selected media records have valid content and FTS matches on source-title terms.
- The current studio generators use generic retrieval queries such as `entities attributes values relationships`.
- Those generic queries often retrieve zero documents from the selected sources, which causes unified RAG to return a generic no-context answer.
- The page then correctly rejects that fallback text as unusable content.

The root cause is that the workspace studio retrieval query is not grounded in the selected sources.

## Recommended Approach

Add one shared retrieval-query builder in `StudioPane/index.tsx` that derives a retrieval seed from the selected workspace sources, then let each RAG-backed generator append a small output-specific hint.

The retrieval query should be built from:

- selected source titles
- lightweight source-type descriptors when useful
- a short output-specific suffix such as `summary key findings` or `entities attributes values relationships`

This keeps authoring instructions in `generation_prompt`, keeps the fix local to the workspace page, and improves all RAG-backed outputs without changing backend retrieval semantics.

## Rejected Alternatives

### Patch only `data_table`

This would fix the currently visible failure, but the underlying problem affects the other RAG-backed outputs too. It would leave the page fragile and duplicate logic later.

### Change unified RAG backend retrieval semantics

The backend is already behaving correctly for media-filtered FTS when the query contains relevant terms. Changing backend retrieval would be broader, riskier, and unnecessary for this page bug.

## Design Details

### Shared Query Builder

In `StudioPane/index.tsx`:

- pull `getEffectiveSelectedSources()` from the workspace store
- add a helper that accepts the selected `WorkspaceSource[]`
- extract normalized title fragments from those sources
- include a small amount of type context like `video transcript`, `document text`, or `pdf document`
- join the title fragments into a compact retrieval-oriented query

The builder should stay conservative:

- prefer source titles over long content snippets
- cap the output length so it stays well under the existing RAG query limit
- produce a stable fallback string if the titles are unavailable

### Generator Changes

For `summary`, `report`, `timeline`, `compare_sources`, `mindmap`, `flashcards`, `audio_overview`, `slides` fallback, and `data_table`:

- keep the current `generation_prompt`
- replace the generic `query` with the grounded base query plus a short artifact-specific suffix

Example shape:

- grounded base: source titles and type hints
- summary suffix: `summary key findings main ideas`
- data table suffix: `entities attributes values relationships comparisons`

### Testing

Add focused regression tests in the StudioPane test suite to verify that:

- `summary` sends a RAG request whose `query` includes selected source titles and still uses `generation_prompt`
- `data_table` sends a grounded `query` instead of the old generic string

Keep the tests at the request-contract level. The goal is to lock the integration behavior that caused the live failure.

### Verification

After implementation:

- run targeted `StudioPane` Vitest coverage for the updated request contract
- rerun a live Playwright probe against `/workspace-playground`
- confirm `Data Table` now completes for the selected test sources instead of failing with `No usable data table content was returned.`

## Scope

In scope:

- workspace page studio query grounding
- request-contract tests
- live verification for the affected output flow

Out of scope:

- backend retrieval algorithm changes
- parser redesign for markdown tables
- non-workspace RAG caller changes
