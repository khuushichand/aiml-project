# Workspace Playground Studio Output Failure Design

Date: 2026-03-13
Status: Approved for planning

## Summary

Fix the `/workspace-playground` studio pane so right-side output actions only report success when they produce a usable artifact. Today several generators can return fallback error text as normal content, which causes the UI to show a success toast and a completed artifact while downloads contain failure text or route to the wrong backend endpoint.

This design keeps the fix narrow:

- validate generation results in the shared studio finalization path
- stop treating known fallback error strings as successful content
- route downloads by artifact type instead of overloading `serverId`
- add regression tests for both generation status and download behavior

## Problem Statement

The current studio flow marks an artifact as `completed` whenever a generator returns a `GenerationResult`, even if that result only contains local fallback strings such as `"Summary generation failed"` or other non-usable content.

This produces three user-visible failures:

- the success toast fires for outputs that did not really generate
- the artifact card looks successful even when the payload is junk
- downloading some artifact types can hit the wrong route because `serverId` is overloaded across incompatible backend resources

The bug appears cross-cutting because most right-side outputs share the same finalization and download plumbing.

## Goals

- Ensure studio success is tied to usable output, not merely a returned object.
- Convert invalid generation results into failed artifacts with actionable error text.
- Prevent broken downloads caused by generic `serverId` routing.
- Keep the fix local to the shared studio pipeline wherever possible.
- Add deterministic regression coverage for the identified failure modes.

## Non-Goals

- Re-architect every studio output around a new backend object model.
- Replace all local artifact content with server-backed downloads.
- Redesign the studio UI or output catalog.
- Change unrelated workspace behavior outside generation and download flows.

## Existing Repo Anchors

- Shared studio generation and download flow:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- Artifact types and artifact metadata:
  - `apps/packages/ui/src/types/workspace.ts`
- Generic outputs download client:
  - `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Quiz generation client and quiz resource model:
  - `apps/packages/ui/src/services/quizzes.ts`
- Existing studio regression tests:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`

## Reviewed Risks And Adjustments

### 1. Generic Result Validation Can Produce False Positives

Risk: a broad string-matching validator could reject legitimate user content that happens to mention an error phrase.

Adjustment:

- validate by artifact type first
- use exact local sentinel strings already produced by this module
- rely on structure and required fields before using generic error-pattern checks

### 2. Fixing Success State Alone Leaves Download Failures Behind

Risk: even after generation validation, downloads can remain broken if artifact routing still relies on a generic `serverId`.

Adjustment:

- make download handling artifact-type aware
- do not assume every `serverId` belongs to `/api/v1/outputs/{id}/download`
- keep quiz download local/JSON-backed instead of calling the outputs download endpoint

### 3. Audio Overview Can Still Lie About Success

Risk: non-browser audio generation currently falls back to script text and still looks successful, even though no audio was produced.

Adjustment:

- adopt stricter audio semantics for this fix
- non-browser `audio_overview` only succeeds when an `audioUrl` exists
- TTS failure should mark the artifact failed instead of returning a script-only success artifact

### 4. Local Helper Fallback Strings Keep Reintroducing The Same Bug

Risk: if generators continue returning strings like `"Report generation failed"` as content, future changes can bypass the shared validator.

Adjustment:

- remove local helper fallbacks that convert missing output into synthetic content
- require helpers to return usable content or throw

## Approved Design

### 1. Add Shared Studio Result Finalization

Introduce a typed finalization helper in `StudioPane/index.tsx`, such as `finalizeGenerationResult(type, result)` or `assertValidGenerationResult(type, result)`, and call it before `updateArtifactStatus(..., "completed", ...)`.

The helper should normalize and validate each artifact type:

- `summary`, `report`, `compare_sources`, `timeline`
  - require non-empty usable text content
  - reject exact fallback sentinel strings currently emitted by this module
- `mindmap`
  - require valid Mermaid payload or extractable Mermaid content
- `data_table`
  - require usable content and prefer a parsed markdown table payload
- `slides`
  - succeed if `presentationId` exists
  - otherwise require a valid fallback slide-outline artifact
- `quiz`
  - require parsed/generated questions in structured data
- `flashcards`
  - require parsed/generated flashcards in structured data
- `audio_overview`
  - for non-browser generation, require `audioUrl`
  - browser mode may still succeed with text/script-only output because the browser is the playback engine

If validation fails, the helper should throw a descriptive error so the artifact is finalized as `failed` and the success toast never fires.

### 2. Stop Returning Fallback Error Strings As Content

The RAG-based helper functions in `StudioPane/index.tsx` should stop returning placeholder strings such as:

- `"Summary generation failed"`
- `"Report generation failed"`
- `"Timeline generation failed"`
- `"Compare sources generation failed"`
- `"Mind map generation failed"`
- `"Slides generation failed"`
- `"Data table generation failed"`

Instead:

- return real usable content, or
- throw an error with a meaningful message derived from the backend response

If the backend returns HTTP success but no usable `generation` or `answer`, treat that as failure and surface a real error to the artifact card.

### 3. Make Download Routing Artifact-Type Aware

`handleDownloadArtifact` should no longer use `artifact.serverId` as a generic signal for `/api/v1/outputs/{id}/download`.

Approved routing rules:

- text-first artifacts (`summary`, `report`, `compare_sources`, `timeline`, `mindmap`, `data_table`)
  - download from local `artifact.content`
- `slides`
  - use `presentationId` export flow when available
  - otherwise fall back to local content download
- `audio_overview`
  - download from `audioUrl`
- `quiz`
  - download local artifact content or generated JSON payload
  - do not call `tldwClient.downloadOutput`
- `flashcards`
  - download local artifact content

This keeps artifact download semantics honest without requiring a larger metadata redesign in this change.

### 4. Preserve Failure Visibility In The Existing UI

When validation fails, the artifact should still appear in the generated outputs list but with:

- `status: "failed"`
- a descriptive `errorMessage`
- no success toast

This preserves user visibility into the failed attempt and matches the current card model better than silently deleting invalid artifacts.

## Data And Contract Notes

The current `GeneratedArtifact.serverId` field is semantically overloaded. In this fix:

- keep the field for compatibility
- treat it as resource-specific, not universally downloadable
- let artifact type decide whether that identifier is usable for a download path

Longer term, the cleaner model would be explicit artifact download metadata rather than one overloaded `serverId`, but that is outside this change.

## Testing Strategy

Add regression coverage in `StudioPane.stage1.test.tsx` for the shared failure modes:

1. `ragSearch` returns no usable `generation` or `answer`
   - artifact becomes `failed`
   - success toast does not fire
2. `ragSearch` returns a local sentinel fallback string
   - artifact becomes `failed`
   - artifact shows a meaningful error message
3. valid summary generation still succeeds
   - artifact becomes `completed`
   - success toast fires once
4. quiz download is type-aware
   - the quiz download action does not call `tldwClient.downloadOutput`
   - it downloads local content or a local JSON export path instead
5. non-browser audio TTS failure is strict
   - artifact becomes `failed`
   - no completed audio artifact without an `audioUrl`

The tests should focus on observable behavior, not helper implementation details.

## Recommended Implementation Order

1. Add and test shared result finalization for text outputs.
2. Remove local fallback error-string returns from RAG helper functions.
3. Fix type-aware download routing, starting with quiz.
4. Tighten non-browser audio success semantics.
5. Run focused studio tests, then broader touched-scope verification.

## Expected Outcome

After this change:

- studio actions only show success for usable artifacts
- failed generations stay visible as failed cards instead of fake successful downloads
- quiz downloads no longer route through the generic outputs download endpoint
- audio overview no longer claims success when TTS failed to produce audio
