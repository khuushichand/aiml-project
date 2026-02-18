# Implementation Plan: Media Pages - Analysis and AI Features

## Scope

Pages/components: `AnalysisModal.tsx`, `AnalysisEditModal.tsx`, analysis generation flow from media detail
Finding IDs: `6.1` through `6.4`

## Finding Coverage

- Preserve strong current analysis workflows: `6.1`, `6.2`, `6.3`
- Add streaming cancel/abort control: `6.4`

## Stage 1: Abortable Streaming Plumbing
**Goal**: Add robust cancellation capability to streaming analysis generation.
**Success Criteria**:
- Streaming requests are wired with `AbortController`.
- Active generation exposes cancellation callback through modal state.
- Abort path cleanly closes stream and updates request lifecycle state.
**Tests**:
- Unit tests for stream controller lifecycle.
- Integration tests for cancel during active stream.
- Error-path tests for cancellation vs server/network failure differentiation.
**Status**: Complete

## Stage 2: Cancel UX, Recovery, and Messaging
**Goal**: Make cancellation visible, predictable, and safe for user edits.
**Success Criteria**:
- Cancel button appears only during active streaming and is keyboard accessible.
- UI communicates cancelled state and allows restart without stale partial state.
- Elapsed timer and preview behavior stop/update immediately on abort.
**Tests**:
- Component tests for conditional cancel button rendering.
- Integration tests for cancel -> restart flow.
- Regression test for timer reset and preview cleanup.
**Status**: Complete

## Stage 3: Protect Existing Analysis Feature Quality
**Goal**: Ensure cancellation support does not regress mature analysis/edit flows.
**Success Criteria**:
- Preset selection and custom prompts remain unchanged.
- Edit modal save/save-as-version/send-to-chat flows remain stable.
- Streaming auto-save behavior remains correct when not cancelled.
**Tests**:
- Regression integration tests for preset and custom generation flows.
- Component tests for edit modal limits/word count warnings.
- End-to-end analysis generation test including non-cancel path.
**Status**: Complete

## Dependencies

- Stage 1 should reuse existing streaming request abstractions used by chat/audio where possible.
