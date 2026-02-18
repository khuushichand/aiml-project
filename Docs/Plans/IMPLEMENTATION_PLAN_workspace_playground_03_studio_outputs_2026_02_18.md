# Implementation Plan: Workspace Playground - Studio and Output Generation

## Scope

Components: `StudioPane`, artifact generation handlers, artifact viewer modals/actions
Finding IDs: `3.1` through `3.15`

## Finding Coverage

- Generation control and safety: `3.3`, `3.12`, `3.14`
- Output fidelity and workflow utility: `3.5`, `3.6`, `3.7`, `3.8`, `3.10`, `3.11`, `3.13`
- Discoverability and information clarity: `3.1`, `3.2`, `3.4`, `3.9`, `3.15`

## Stage 1: Generation Lifecycle Control
**Goal**: Make long-running generation operations interruptible and safe.
**Success Criteria**:
- Output generation supports cancellation via `AbortController`.
- Running state shows explicit `Cancel` action.
- Artifact deletion uses undo toast or confirmation.
- Regenerate supports `Replace existing` or `Create new version`.
**Tests**:
- Unit test for abort path and artifact status updates.
- Integration test for cancel during streaming generation.
- Component tests for delete undo and regenerate mode selection.
**Status**: Not Started

## Stage 2: Render Outputs as First-Class Artifacts
**Goal**: Replace raw text fallbacks with task-appropriate output renderers.
**Success Criteria**:
- Mermaid content renders as interactive mind map (zoom/pan + export image).
- Markdown tables parse into interactive sortable/filterable table with CSV export.
- Flashcards/quizzes render structured editable editors post-generation.
- Flashcards target deck can be selected before save.
- Quiz/flashcard generation supports multi-source inputs.
- Audio voice picker includes preview sample playback.
- Artifacts include `Discuss in chat` action.
**Tests**:
- Component tests for Mermaid renderer success/failure fallback.
- Integration tests for table parsing and CSV export.
- Unit tests for structured quiz/flashcard serialization and save edits.
- Integration tests for deck selection and multi-source generation payloads.
- Component test for discuss action sending context to chat.
**Status**: Not Started

## Stage 3: Information Architecture and UX Polish
**Goal**: Improve output type comprehension and reduce layout friction.
**Success Criteria**:
- Output types grouped by category with clear headings.
- Tooltips render descriptions from `OUTPUT_TYPES.description`.
- Generation status includes rough ETA based on type/source count heuristic.
- TTS settings appear contextually when selecting `Audio Overview`.
- Outputs/notes split supports resizing or adaptive dynamic height.
**Tests**:
- Component tests for grouped output categories and tooltip content.
- Unit test for ETA heuristic function.
- Responsive tests for contextual TTS controls and split resizing behavior.
**Status**: Not Started

## Dependencies

- `Discuss in chat` should share action contract with Category 6.
- Versioning links should align with Category 10 output history strategy.
