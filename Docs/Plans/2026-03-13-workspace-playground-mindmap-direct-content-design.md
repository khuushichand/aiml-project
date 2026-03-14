# Workspace Playground Mind Map Direct-Content Design

## Problem

`/workspace-playground` `Mind Map` generation still fails live even after the `Data Table` path was repaired.

The current failure path is:

- the workspace page calls unified RAG for `mindmap`
- the retrieval query is `central theme main branches subtopics`
- the backend returns zero retrieved documents for the selected test sources
- generation falls back to generic no-context prose
- the page rejects that response because `Mind Map` completion currently requires valid Mermaid content

The page behavior is correct, but the generation path is not reliable enough to satisfy it.

## Recommended Approach

Keep the existing success/failure gate for `Mind Map`, but change `mindmap` generation to use selected source content directly instead of the current RAG retrieval path.

The new flow should:

- fetch selected media content through `tldwClient.getMediaDetails(..., include_content: true)`
- clip source text to a bounded prompt budget
- call `tldwClient.createChatCompletion(...)` with a strict Mermaid `mindmap` prompt
- extract Mermaid code from the model response
- keep the existing completion rule that fails when no valid Mermaid diagram is produced

This mirrors the working `Data Table` fix and avoids depending on brittle retrieval semantics for a format-sensitive output.

## Rejected Alternatives

### Relax the `Mind Map` completion rule

That would allow arbitrary prose or generic fallback answers to be marked successful. It would hide the generation problem instead of fixing it.

### Keep RAG and only tune the retrieval query

The current backend FTS behavior has already shown that generic multi-word queries are unreliable for these workspace outputs. This would still leave `Mind Map` fragile.

### Change backend RAG retrieval semantics

That is broader than the page bug. The workspace page already has a proven direct-content fallback pattern that is smaller and lower risk.

## Design Details

### Source Context Collection

Use the same selected-source inputs already available in `StudioPane`.

For `mindmap`:

- fetch media details with content included
- prefer `content.text`
- fall back only to existing safe extracted-text fields already used in the page
- enforce per-source and total character caps to keep the prompt bounded

### Mind Map Generation Request

Send a non-stream `/api/v1/chat/completions` request that:

- resolves a usable chat model the same way `Data Table` now does
- uses a strict system prompt requiring Mermaid `mindmap` output only
- includes the selected source titles and clipped source content
- preserves current provider and generation controls where applicable

### Validation

Keep the current `Mind Map` completion rule:

- require non-empty text content
- require `artifact.data.mermaid`
- require the extracted Mermaid code to look like a Mermaid diagram

If the model returns prose, fenced non-Mermaid code, or generic fallback text, the artifact should still fail.

### Testing

Add a request-contract regression that proves:

- `Mind Map` fetches selected source content directly
- it uses `createChatCompletion(...)`
- it does not call `ragSearch(...)`
- it stores the returned Mermaid code in `artifact.data.mermaid`

Add a second regression proving that when no model is selected, `Mind Map` falls back to the first available chat model instead of sending an undefined model.

### Verification

After implementation:

- rerun the `StudioPane` stage suites
- rerun the focused workspace output probe against the live page
- rerun the broader workspace page Playwright suite
- run Bandit on the touched frontend scope and record the expected TypeScript parse limitation

## Scope

In scope:

- workspace `Mind Map` reliability
- direct-content generation inside `StudioPane`
- request-contract coverage
- live workspace verification

Out of scope:

- backend RAG retrieval changes
- Mermaid renderer changes
- non-workspace callers of mind-map generation
