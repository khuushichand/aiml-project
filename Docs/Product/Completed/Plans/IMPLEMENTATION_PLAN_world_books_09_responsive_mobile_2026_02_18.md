# Implementation Plan: World Books - Responsive and Mobile Experience

## Scope

Components: World-books list table responsiveness, entries drawer mobile layout, action target sizing, matrix modal mobile alternative, modal overflow behavior.
Finding IDs: `9.1` through `9.5`

## Finding Coverage

- Main world-books list usability on small screens: `9.1`
- Entry drawer and action control mobile ergonomics: `9.2`, `9.3`
- Character matrix mobile fallback requirement: `9.4`
- Modal viewport/scroll resilience: `9.5`

## Stage 1: Make Main World-Books List Mobile-Usable
**Goal**: Ensure primary list workflows are functional below `md` breakpoint.
**Success Criteria**:
- Hide/deprioritize low-value columns (`Description`, `Attached To`) on mobile.
- Collapse row actions into overflow menu on narrow widths.
- Preserve quick access to critical actions (`Entries`, `Edit`, `Delete`).
**Tests**:
- Responsive component tests for column visibility rules by breakpoint.
- Integration tests for overflow menu actions parity with desktop buttons.
- Manual viewport QA checklist for 320px, 375px, 414px widths.
**Status**: Complete

## Stage 2: Optimize Entries Drawer for Touch Workflows
**Goal**: Keep entry editing and browsing comfortable on phones.
**Success Criteria**:
- Hide lower-priority table columns in drawer on mobile (priority/enabled moved to detail/edit context).
- Increase tap target size to at least 44px for icon-heavy actions on mobile breakpoints.
- Maintain keyboard and desktop density behavior without regression.
**Tests**:
- Responsive tests for drawer table column adaptation.
- Component tests for touch-target sizing class/application.
- Accessibility tests for focus ring visibility and target hit area.
**Status**: Complete

## Stage 3: Provide Mobile Alternative to Character Matrix
**Goal**: Replace unusable dense grid interaction on small screens.
**Success Criteria**:
- On mobile, switch matrix to list-oriented attach UI (or paginated subset matrix).
- Keep attach/detach operations and feedback equivalent to desktop matrix.
- Ensure the fallback is discoverable and does not require horizontal micro-scroll.
**Tests**:
- Responsive integration tests for matrix-to-list fallback activation.
- Interaction tests for attach/detach parity in fallback mode.
- Usability smoke tests on common mobile viewport presets.
**Status**: Complete

## Stage 4: Harden Modal Scrolling on Short Viewports
**Goal**: Prevent clipped or inaccessible controls in short-height contexts.
**Success Criteria**:
- Apply modal max-height and internal scrolling defaults where content may exceed viewport.
- Verify create/edit/statistics modals remain fully navigable in landscape mobile.
- Keep sticky footer/action areas visible when scrolling content body.
**Tests**:
- Component tests for modal max-height/overflow style application.
- End-to-end viewport tests for landscape mobile completion of create/edit flows.
- Accessibility test for focus retention while scrolling modal content.
**Status**: Complete

## Dependencies

- Breakpoint behavior should align with app-wide responsive utility conventions.
- Matrix mobile fallback should reuse attachment APIs already used by desktop matrix.
