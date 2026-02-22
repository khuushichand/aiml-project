# Chat Page (Playground) Group 04 - Composer Complexity and Input Ergonomics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce composer cognitive load while preserving advanced controls for power users.

**Architecture:** Recompose composer controls into layered interactions (primary, context, advanced), then expose context stack diagnostics and guided control semantics for presets, mentions, JSON mode, and cost.

**Tech Stack:** React, TypeScript, textarea/input hooks, toolbar components, Vitest interaction tests.

---

## Scope

- Findings: `UX-021`, `UX-022`, `UX-023`, `UX-024`, `UX-025`, `UX-026`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundForm.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/ComposerToolbar.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/ComposerToolbarOverflow.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/MentionsDropdown.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/AttachmentsSummary.tsx`

## Stage 1: Composer Layering and Control Hierarchy
**Goal**: Separate high-frequency actions from advanced tuning controls.
**Success Criteria**:
- Primary row contains send/stop, input, attachments, voice, and model selector.
- Context strip shows active behavior modifiers as chips.
- Advanced drawer contains lower-frequency configuration controls.
**Tests**:
- Add layout tests for control placement by viewport.
- Add integration tests for drawer persistence and toggle behavior.
**Status**: Complete

## Stage 2: Context Stack Transparency and Conflict Prevention
**Goal**: Make stacked contexts visible before send.
**Success Criteria**:
- Context stack popover shows token footprint by source (history/system/character/rag/files).
- Conflicting states trigger pre-send warnings with one-click fixes.
- Context contributors can be removed/disabled from chip actions.
**Tests**:
- Add unit tests for context budget calculations.
- Add integration tests for conflict warnings and chip action effects.
**Status**: Complete

## Stage 3: Mentions and Command Discoverability
**Goal**: Improve structured input discoverability without clutter.
**Success Criteria**:
- Composer placeholder and first-use hint explain `@` and `/` affordances.
- Mention menu supports categories and keyboard navigation.
- Slash commands include concise descriptions and examples.
**Tests**:
- Add mention/command trigger tests.
- Add keyboard navigation tests for menu traversal and selection.
**Status**: Complete

## Stage 4: Preset, JSON Mode, Attachment, and Cost Explainability
**Goal**: Clarify intent and impact of advanced toggles.
**Success Criteria**:
- Presets display parameter deltas in plain language.
- JSON mode uses explicit "Structured Output" copy and validation hint.
- Attachment chips support quick preview/removal and size warnings.
- Cost estimates pair with mitigation actions (cheaper model, lower max tokens).
**Tests**:
- Add mapping tests for preset parameter application.
- Add integration tests for JSON mode and attachment remove interactions.
**Status**: Complete

## Stage 5: Composer Usability Validation
**Goal**: Verify reduced friction with no feature regression.
**Success Criteria**:
- Time-to-send and mode-misconfiguration rates improve in QA telemetry.
- No loss of advanced capability discoverability for expert users.
- Mobile keyboard scenario remains usable with layered controls.
**Tests**:
- Run focused UX regression suite for composer variants.
- Add targeted manual QA checklist for desktop/tablet/mobile composer interactions.
**Status**: Complete

## Dependencies

- Requires Group 01 and Group 02 state/signal primitives.
- Must align with Group 05 compare continuation controls and Group 06 mobile behavior.

## Exit Criteria

- Composer default state is simple, advanced state is explicit, and stacked context behavior is predictable.

## Progress Notes (2026-02-22)

- Confirmed layered composer structure, context-stack signals, and attachment/advanced-control interactions through `ComposerToolbar.test.tsx`, `ContextFootprintPanel.*`, and `AttachmentsSummary.integration.test.tsx`.
- Verified associated guard contracts through `PlaygroundForm.signals.guard.test.ts`.
- Stage 3 closure evidence:
  - Added hostname-category grouping + keyboard selection regression coverage in `src/components/Option/Playground/__tests__/MentionsDropdown.integration.test.tsx`.
  - Added slash-command trigger/description regression coverage in `src/hooks/playground/__tests__/useSlashCommands.test.tsx`.
- Stage 5 closure evidence:
  - Added checklist artifact: `Docs/Plans/CHAT_PLAYGROUND_COMPOSER_USABILITY_CHECKLIST_2026_02_22.md`.
  - Focused composer suite passes via `bun run test:playground:composer --reporter=dot` (`6 files / 24 tests passed`).
