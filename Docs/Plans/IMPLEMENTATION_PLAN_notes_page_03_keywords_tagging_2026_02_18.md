# Implementation Plan: Notes Page - Keywords & Tagging

## Scope

Components/pages: keyword select controls, keyword picker modal, backend keyword lifecycle endpoints/services.
Finding IDs: `3.1` through `3.7`

## Finding Coverage

- Preserve strong current patterns: `3.1`, `3.2`, `3.7`
- Frequency and prioritization visibility: `3.3`
- Hierarchy/visual differentiation improvements: `3.4`
- Keyword management lifecycle (rename/merge/delete): `3.5`
- Assisted keyword generation: `3.6`

## Stage 1: Frequency-Aware Keyword Selection UX
**Goal**: Improve keyword decision speed with data-informed signals.
**Success Criteria**:
- Show per-keyword note counts in filter dropdown and picker modal.
- Add sorting options by frequency and lexical order.
- Add recently used keyword section in picker modal.
**Tests**:
- Component tests for count rendering and sort-mode toggles.
- Integration tests for count accuracy against backend responses.
- Accessibility tests for grouped keyword navigation in modal.
**Status**: Not Started

## Stage 2: Keyword Management Surface
**Goal**: Enable safe cleanup of keyword taxonomy drift.
**Success Criteria**:
- Provide keyword management entry point from browse-keywords modal.
- Add rename, merge, and delete workflows with confirmation and conflict handling.
- Extend backend API if required to support rename/merge operations atomically.
**Tests**:
- API tests for rename/merge/delete transactional correctness.
- Integration tests for UI state updates after management actions.
- Regression tests ensuring note-keyword relationships remain intact post-merge.
**Status**: Not Started

## Stage 3: Visual Hierarchy and Assisted Suggestions
**Goal**: Improve keyword readability and reduce manual tagging overhead.
**Success Criteria**:
- Add optional visual hierarchy cues (frequency tint or user-defined color tags).
- Introduce AI-assisted keyword suggestion flow from note content.
- Keep suggestion acceptance explicit (no silent auto-attach).
**Tests**:
- Component tests for color/frequency rendering fallbacks.
- Integration tests for suggestion generation and selective acceptance.
- Safety tests ensuring no keywords attach without explicit user action.
**Status**: Not Started

## Dependencies

- Keyword counts and filter semantics must align with Plans 01 and 04.
- AI suggestion strategy should reuse model/provider controls from Plan 08 where possible.
