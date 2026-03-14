# Workspace Playground Data Table Reliability Design

## Problem

`/workspace-playground` still had one live studio output failure after the shared success-state validation work: `Data Table`.

The failure mode was specific:

- the page reported generation success for other output types after earlier fixes
- `Data Table` still often failed with `No usable data table content was returned.`
- selected workspace sources were valid and had real stored content
- backend unified RAG returned generic no-context output for the workspace `data_table` request even when `include_media_ids` was correct

Investigation showed that the current workspace `data_table` flow was the weak point, not backend storage corruption:

- the studio request used a generic retrieval query (`entities attributes values relationships`)
- SQLite FTS phrase handling meant generic multi-word queries frequently retrieved zero documents
- the dedicated `/api/v1/data-tables/generate` backend path was not reliable in this local environment because jobs remained queued without a running worker

That left the page with no dependable end-to-end path for `Data Table`.

## Recommended Approach

Keep the existing RAG-backed flow for the other studio outputs, but change `Data Table` to a direct source-content generation path inside `StudioPane/index.tsx`.

The new `Data Table` flow should:

- read the selected source metadata already available in the workspace store
- fetch full content for the selected media with `tldwClient.getMediaDetails(..., include_content: true)`
- build a bounded source-context payload from those source texts
- call `tldwClient.createChatCompletion(...)` with a strict prompt that requires markdown-table-only output
- parse the returned markdown table and store the parsed structure on the artifact

This avoids the brittle RAG retrieval step for `Data Table` without changing backend retrieval semantics for the rest of the studio pane.

## Rejected Alternatives

### Ground all workspace RAG queries in source titles

This was the initial hypothesis, but direct API probing showed it was not reliable enough. Multi-word grounded queries still frequently collapsed into zero-document phrase searches, so this would not have been a durable fix for `Data Table`.

### Switch the workspace page to the backend data-tables job API

The API exists, but in the current local/dev environment the table job stayed queued and `wait_for_completion` could return `data_table_not_found`. Depending on a background worker would not have produced a reliable page fix.

### Change backend unified RAG retrieval semantics

That is broader than this bug and was unnecessary once the page had a reliable direct-content path for `Data Table`.

## Design Details

### Data Table Source Context

In `StudioPane/index.tsx`:

- read `getEffectiveSelectedSources()` from the workspace store
- derive the effective selected source list from the currently selected media ids
- fetch media details for those sources with content included
- extract usable text from `content.text` first, then any safe fallback text fields already exposed by the media detail payload
- cap per-source and total character budgets so the prompt stays bounded

### Data Table Generation Request

Use `tldwClient.createChatCompletion(...)` rather than unified RAG for `Data Table`.

The request should:

- include a strict system prompt telling the model to return only a markdown table
- include a user prompt with the selected source titles and clipped source content
- preserve the current workspace generation controls such as model, provider, temperature, top-p, and max tokens

### Output Validation

The existing shared studio finalization path remains in place.

For `data_table`, success requires:

- non-empty text content
- a successfully parsed markdown table saved in `artifact.data.table`

If the model returns commentary, plain prose, or empty output, the artifact should fail instead of downloading unusable content.

### Testing

Add request-contract coverage that proves:

- `Data Table` fetches media details for each selected source
- it uses `createChatCompletion(...)`
- it does not call `ragSearch(...)`
- the generated artifact stores both the markdown table content and parsed table structure

Keep the existing RAG contract coverage for `summary` and `compare_sources` unchanged, because those outputs still use unified RAG.

### Verification

After implementation:

- run targeted `StudioPane` Vitest suites
- run Bandit on the touched scope and record the expected TypeScript AST parse limitation
- run a live Playwright workspace probe focused on `Data Table` and the broader output matrix to confirm the page now completes and downloads usable content

## Scope

In scope:

- workspace `Data Table` reliability
- direct-content fallback inside the page
- request-contract tests and live verification

Out of scope:

- backend unified RAG retrieval changes
- background data-table worker fixes
- non-workspace callers of the data-tables API
