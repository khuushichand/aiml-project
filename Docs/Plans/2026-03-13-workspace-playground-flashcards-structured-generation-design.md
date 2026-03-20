# Workspace Playground Flashcards Structured Generation Design

## Problem

`/workspace-playground` currently generates flashcards by sending a free-form RAG request and then parsing the returned text for exact `Front:` / `Back:` pairs. Live browser verification showed this path is brittle: the model can return semantically valid flashcards in a different format, the workspace reports a generation failure, and no downloadable artifact is produced.

## Root Cause

- The workspace flashcard generator relies on unstructured text output.
- `parseFlashcards()` only accepts a narrow line-oriented format.
- The codebase already has a dedicated `/api/v1/flashcards/generate` endpoint that returns structured flashcard drafts and is used elsewhere.

## Recommended Fix

Replace the workspace flashcard RAG-text path with the existing structured flashcard generation endpoint.

### Behavior

- Load selected source content directly from `getMediaDetails(...include_content=true)`.
- Build a bounded combined source text payload from the selected sources.
- Call `/api/v1/flashcards/generate` through the existing UI service.
- Pass the resolved workspace provider/model when available so generation remains consistent with studio settings.
- Persist the returned drafts into the selected deck or a created deck, as before.
- Format artifact content from the structured drafts using the existing `formatFlashcardsContent()` helper.

### Why this is better

- It removes the brittle parser from the generation path.
- It matches an existing supported backend contract.
- It keeps artifact editing/downloading behavior intact because the artifact still stores normalized `Front:` / `Back:` text plus structured draft data.

## Risks

- The endpoint may still fail if the selected provider requires an explicit model and none is resolved. Mitigation: reuse `resolveStudioChatModel()` when wiring the request.
- Source text limits must stay bounded. Mitigation: reuse the existing studio source-content loader and combine the clipped source contexts into a capped request body.

## Validation

- Add stage-2 tests proving workspace flashcards use the structured generation service and selected source content.
- Add a stage-2 regression proving the workspace falls back to the first available chat model for flashcard generation when no model is selected.
- Re-run workspace stage-1/stage-2 suites.
- Re-run the live workspace output-matrix Playwright probe.
