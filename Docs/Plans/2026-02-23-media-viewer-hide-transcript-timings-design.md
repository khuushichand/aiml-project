# Media Viewer Hide Transcript Timings Design

## Summary

Implement a display-only transcript timing toggle for media viewing surfaces so users can hide transcript timings while preserving the raw stored transcript.

## Decisions (Approved)

1. Keep ingestion defaults unchanged.
2. Add viewer-side hide/show transcript timing controls.
3. Default behavior is to hide timings during viewing.
4. When timings are hidden, `Copy content` copies the displayed stripped text.

## Goals

1. Improve readability of transcript content in media views.
2. Preserve raw transcript fidelity in storage and API responses.
3. Keep behavior consistent across WebUI and browser extension.

## Non-Goals

1. No backend API contract changes.
2. No migration or rewriting of stored transcript content.
3. No ingestion pipeline default changes.

## Affected Surfaces

1. `/media` (single-item viewer via shared `ContentViewer`).
2. `/media-multi` (multi-item comparison/review surface).
3. Shared UI package used by both WebUI and extension.

## Proposed Architecture

1. Add a shared text utility that strips transcript timing prefixes from line starts.
2. Add a shared persisted setting for "hide transcript timings" (default `true`).
3. Derive `displayContent` from `rawContent` in each viewer:
   - `displayContent = hideTimings ? stripTranscriptTimings(rawContent) : rawContent`
4. Keep all non-display data paths raw unless explicitly tied to displayed output (copy action).

## Component-Level Design

### 1) Shared transcript text utility

Create a utility in `apps/packages/ui/src/utils/` to:

1. Detect common leading timestamp patterns (e.g. `[00:12]`, `00:12:34 -`, `00:12:`).
2. Remove only leading timestamp tokens and adjacent separators.
3. Preserve line breaks and non-timestamp content exactly.
4. Avoid stripping timestamps that appear in the middle of a sentence.

### 2) `/media` integration (`ContentViewer`)

In `apps/packages/ui/src/components/Media/ContentViewer.tsx`:

1. Add a hide/show timings control in the content toolbar.
2. Apply stripping to rendered text when hide mode is enabled.
3. Disable timestamp-seek chip rendering when timings are hidden (chips require visible timestamps).
4. Ensure copy action uses the effective displayed content.

### 3) `/media-multi` integration (`MediaReviewPage`)

In `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`:

1. Add matching hide/show timings control (same label/semantics).
2. Apply stripping for content display in cards when hide mode is enabled.
3. Ensure copy action uses stripped content when hide mode is enabled.

### 4) Shared setting/state

Add a persisted UI setting (default `true`) in shared settings plumbing so both surfaces read/write the same preference.

## Data Flow

1. API returns raw transcript content.
2. UI computes `displayContent` from raw content + hide setting.
3. Rendering uses `displayContent`.
4. Copy uses `displayContent` (approved behavior).
5. Raw content remains unchanged in memory/state used for storage/update calls unless explicitly edited.

## Error Handling and Edge Cases

1. If stripping utility fails unexpectedly, fail open by returning original text.
2. If a line contains only timestamp tokens, preserve an empty line boundary to maintain readable paragraph spacing.
3. If content is not transcript-like, utility should behave as pass-through.
4. Avoid overly broad regex patterns that can remove legitimate textual data.

## Testing Strategy

### Unit tests

1. Utility tests for:
   - Bracketed timestamp format.
   - Plain timestamp with separators.
   - Mixed timestamp/non-timestamp lines.
   - Mid-sentence timestamps that must remain.
   - No-op behavior on plain text.

### Component tests

1. `ContentViewer`:
   - Default hide mode on.
   - Toggle show/hide updates rendered text.
   - Copy uses stripped text when hidden.
   - Timestamp seek chips render only when timings are shown.

2. `MediaReviewPage`:
   - Default hide mode on.
   - Toggle applies consistently across rendered cards.
   - Copy uses stripped text when hidden.

### Regression checks

1. Existing embedded media playback behavior remains intact.
2. Existing content display modes (plain/markdown/html/auto) continue to work.
3. No changes in ingestion behavior.

## Rollout Notes

1. This is a safe UI-only change with no API/schema migration risk.
2. Existing users may notice transcripts look cleaner by default; a toggle provides immediate reversal.

