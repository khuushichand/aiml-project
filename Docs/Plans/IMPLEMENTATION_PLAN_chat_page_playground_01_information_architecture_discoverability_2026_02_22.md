# Chat Page (Playground) Group 01 - Information Architecture and Discoverability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make core chat structure and major mode entry points immediately understandable for first-time and returning users.

**Architecture:** Introduce a stable conversation state layer shared by header and composer, then rework discovery surfaces (empty state, mode launcher, and persistent chips) so users can see where they are and what is active before they send.

**Tech Stack:** React, TypeScript, Zustand/local state stores, existing Playground UI components, Vitest + Testing Library.

---

## Scope

- Findings: `UX-001`, `UX-002`, `UX-003`, `UX-004`, `UX-005`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/Playground.tsx`
  - `apps/tldw-frontend/src/components/Layouts/ChatHeader.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundForm.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/ComposerToolbar.tsx`
  - `apps/tldw-frontend/src/components/Common/ChatSidebar/*`

## Stage 1: Layout Semantics and Region Identity
**Goal**: Make left sidebar, center timeline/composer, and right artifacts panel relationship explicit at all sizes.
**Success Criteria**:
- Region headers/labels are visible and consistent across desktop/tablet/mobile variants.
- Collapsed regions show persistent affordances with clear labels.
- Empty state includes jump actions to each primary region.
**Tests**:
- Add component tests for region labels and collapse affordances.
- Add responsive tests for desktop/tablet/mobile layout semantics.
**Status**: Complete

## Stage 2: Major Capability Discoverability
**Goal**: Make compare mode, character mode, RAG, and voice discoverable without tutorials.
**Success Criteria**:
- A single "Modes" launcher exposes compare, character, knowledge, and voice with one-line descriptions.
- Empty-state starter cards map to those same mode actions.
- Icon-only controls receive text labels/tooltips and keyboard discoverability.
**Tests**:
- Add interaction tests for launcher open/select/close.
- Add keyboard navigation tests for mode activation.
**Status**: Complete

## Stage 3: Session and Chat-Type Clarity
**Goal**: Distinguish saved chat, temporary chat, and character chat at creation time and in active chat state.
**Success Criteria**:
- Header creation actions use plain language (`New Saved Chat`, `Temporary Chat`, `Character Chat`).
- Temporary mode displays a persistent non-saving badge.
- Character-active state is visible in both header and composer context chips.
**Tests**:
- Add tests validating creation route state and resulting badges.
- Add persistence tests confirming temporary sessions do not save to history.
**Status**: Complete

## Stage 4: Model and Character State Legibility
**Goal**: Ensure users can always identify which model/provider and character context influence responses.
**Success Criteria**:
- Persistent state bar shows active provider/model and character context status.
- Model selector rows include capability and price-band badges.
- Character chip reveals concise "affects next response" explanation.
**Tests**:
- Add component tests for state-bar chip rendering from store state.
- Add integration tests for model/character state changes reflected pre-send.
**Status**: Complete

## Stage 5: Adoption Validation and UX Docs
**Goal**: Validate that discoverability and mode clarity changed behavior.
**Success Criteria**:
- Telemetry captures first-use activation of compare, character, RAG, and voice.
- UX copy matrix documents control labels and helper text.
- Quick usage doc added for QA and onboarding references.
**Tests**:
- Add analytics event schema tests where applicable.
- Run focused UX regression test suite for header/sidebar/composer discoverability.
**Status**: Complete

## Dependencies

- Foundation plan for all later groups; complete before Groups 03, 04, and 05.

## Exit Criteria

- First-message path is self-explanatory with no hidden activation dependencies.
- Active conversation state is visible before every send.

## Progress Notes (2026-02-22)

- Verified Stage 1 through Stage 4 behavior in current code paths across `Playground.tsx`, `PlaygroundEmpty.tsx`, `PlaygroundForm.tsx`, `ComposerToolbar.tsx`, and `ChatHeader.tsx`.
- Ran focused validation suite (29 tests passing):
  - `bunx vitest run src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx src/components/Option/Playground/__tests__/Playground.responsive-parity.guard.test.ts src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts src/components/Layouts/__tests__/ChatHeader.test.tsx --reporter=dot`
- Stage 5 closure evidence:
  - Telemetry event contract now covers first-use starter activations (`general/compare/character/rag`) plus voice activation (`mode: "voice"`).
  - Added discoverability copy matrix: `Docs/Plans/CHAT_PLAYGROUND_DISCOVERABILITY_COPY_MATRIX_2026_02_22.md`.
  - Added QA/onboarding quick usage guide: `Docs/Plans/CHAT_PLAYGROUND_QUICK_USAGE_QA_GUIDE_2026_02_22.md`.
  - Regression confirmation included in consolidated closure run (`10 files / 45 tests passed`).
