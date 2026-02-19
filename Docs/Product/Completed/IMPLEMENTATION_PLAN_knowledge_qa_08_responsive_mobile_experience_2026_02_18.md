# Implementation Plan: Knowledge QA - Responsive and Mobile Experience

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`, `HistorySidebar.tsx`, `SourceList.tsx`, `ExportDialog.tsx`, `FollowUpInput.tsx`
Finding IDs: `8.1` through `8.7`

## Finding Coverage

- Preserve strong responsive implementations: `8.2`, `8.4`
- Improve mobile layout density and small-screen affordances: `8.1`, `8.3`, `8.5`
- Address follow-up reachability and touch accessibility: `8.6`, `8.7`

## Stage 1: Mobile Layout Robustness and Small-Screen Adaptation
**Goal**: Eliminate overlap/cramping issues on narrow viewports.
**Success Criteria**:
- History FAB placement avoids collisions with header/nav elements during scroll (`8.1`).
- Source cards provide compact mobile variant to reduce scroll fatigue (`8.3`).
- Export format cards stack appropriately on very small screens (`8.5`).
- Existing search and settings panel responsive strengths remain unchanged (`8.2`, `8.4`).
**Tests**:
- Responsive component tests across 320px, 375px, 390px, and tablet breakpoints.
- Visual regression snapshots for FAB, source cards, and export layout.
- Existing search/settings responsive regression tests retained.
**Status**: Complete (2026-02-18)

## Stage 2: Mobile Follow-Up Reachability
**Goal**: Keep conversational flow available without deep scroll requirements.
**Success Criteria**:
- Mobile includes sticky bottom follow-up entry affordance (`8.6`).
- Sticky control does not obscure source/action controls and respects safe areas.
- Follow-up submission and New Topic actions remain available from sticky UI.
**Tests**:
- Integration tests for sticky follow-up visibility while scrolling long source lists.
- Mobile viewport tests for keyboard-open layout and safe-area behavior.
- E2E test for follow-up submit from sticky bar.
**Status**: Complete (2026-02-18)

## Stage 3: Touch-First Delete Interaction Accessibility
**Goal**: Ensure destructive history actions are discoverable and safe on touch devices.
**Success Criteria**:
- Delete affordance is available on touch without hover dependency (`8.7`).
- Interaction model keeps safety (confirm delete) while remaining accessible.
- Keyboard and mouse visibility behavior remains consistent with a11y expectations.
**Tests**:
- Touch interaction tests for always-visible or reveal-on-gesture delete action.
- Accessibility tests for focus-visible delete visibility states.
- Integration tests for two-step delete confirmation on mobile.
**Status**: Complete (2026-02-18)

## Dependencies

- Touch delete behavior should be implemented jointly with History accessibility fixes (`5.7`, `12.8`).

## Implementation Notes (2026-02-18)

- Updated the mobile history open FAB to fixed, safe-area-aware positioning to reduce overlap risk with parent scroll/layout contexts.
- Added compact mobile source-card density defaults (smaller spacing and excerpt typography) while preserving larger desktop spacing via `sm:` breakpoints.
- Updated export-format card layout to stack on small screens and switch to three columns at `sm` and above.
- Implemented a sticky mobile follow-up composer with safe-area bottom padding plus scroll-space reservation, keeping follow-up submit and New Topic reachable without deep scrolling.
- Ensured touch/mobile history delete actions stay visible without hover dependency while preserving existing two-step delete confirmation behavior.

## Verification (2026-02-18)

- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__`
