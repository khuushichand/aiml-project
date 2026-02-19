# Implementation Plan: Chat Dictionaries - Accessibility

## Scope

Components: dictionary table/list controls, entry manager interactions, collapse/region semantics, modal and confirmation dialog behavior in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
Finding IDs: `10.1` through `10.9`

## Finding Coverage

- Preserve existing strong accessible labeling patterns: `10.1`, `10.2`, `10.5`, `10.9`
- Keyboard-accessible active-state control gap: `10.3`
- Expand/collapse semantics and region exposure: `10.4`
- Contrast and non-color communication verification: `10.6`, `10.7`
- Nested modal focus-trap behavior verification: `10.8`

## Stage 1: Keyboard and Semantic Control Remediation
**Goal**: Ensure core dictionary actions are fully operable and understandable without a mouse.
**Success Criteria**:
- Active status is keyboard-actionable from list via semantic switch control.
- Expandable panels expose accurate `aria-expanded` and region associations.
- Collapsible validation/preview sections announce state changes clearly.
- All newly introduced controls include accessible names and focus styles.
**Tests**:
- Component tests for switch keyboard toggling (`Space`/`Enter`).
- Accessibility tests asserting `aria-expanded` states and labelled panel regions.
- Keyboard navigation integration tests across primary dictionaries workflows.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Confirmed keyboard toggle support for dictionary active-state switch via `Enter` interaction in list view.
- Added explicit region semantics to validation/preview collapse content:
  - `data-testid="dictionary-validation-panel"` with `role="region"`
  - `data-testid="dictionary-preview-panel"` with `role="region"`
- Added targeted accessibility regression coverage in:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.accessibilityStage1.test.tsx`
- Revalidated responsive/entry interactions to ensure no keyboard regressions:
  - `Manager.responsiveStage1.test.tsx`
  - `Manager.responsiveStage2.test.tsx`
  - `Manager.responsiveStage3.test.tsx`
  - `Manager.entryStage4.test.tsx`

## Stage 2: Focus Management and Modal Interaction Integrity
**Goal**: Guarantee predictable focus behavior in complex overlay workflows.
**Success Criteria**:
- Nested modal cases are removed or validated so outer content is inert.
- Focus trap and return-focus behavior work in entry edit and confirm dialogs.
- Screen-reader announcement order is stable during modal transitions.
- No focus loss occurs on async mutation success/failure states.
**Tests**:
- Integration tests for focus trap and restoration after close.
- Screen-reader-focused manual test checklist for modal transitions.
- E2E keyboard-only path tests for create/edit/delete flows.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added focus restoration integration coverage in:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.accessibilityStage2.test.tsx`
- New assertions verify focus returns to trigger controls after closing:
  - `Manage Entries` drawer
  - Nested `Edit Entry` modal inside the entries drawer (close + submit)
- Added focus-return refs and restoration hooks for additional top-level overlays:
  - `Create Dictionary` modal
  - `Import Dictionary` modal
  - `Quick assign` modal
  - `Dictionary Statistics` modal
- Added manual screen-reader/keyboard verification artifact:
  - `Docs/Plans/CHAT_DICTIONARIES_A11Y_STAGE2_MODAL_FOCUS_CHECKLIST_2026_02_18.md`

## Stage 3: Contrast Compliance and A11y Regression Gates
**Goal**: Keep status/validation visuals compliant across supported themes.
**Success Criteria**:
- Status icon/text color combinations meet WCAG 2.1 AA contrast thresholds.
- Non-color cues remain present for key state indicators.
- Automated a11y checks are added for dictionaries workspace regressions.
- Existing positive accessible behaviors are locked with regression tests.
**Tests**:
- Contrast audit checklist with measured ratios for light/dark themes.
- Axe-based component/integration tests for dictionaries pages.
- Regression tests for existing aria-label and context-aware label text.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added visible status text cues (`Check`, `Valid`, `Warn`, `Error`) alongside validation icons in the table status column so state is not color-only.
  - File: `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
- Fixed an accessibility naming gap for the entry-tools strict-validation toggle by adding an explicit switch label.
  - File: `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
- Added Stage 3 accessibility regression suite with:
  - axe-based list and entries-drawer checks for naming + ARIA validity
  - context-aware action-label assertions (dictionary name preserved in aria-labels)
  - non-color validation status text cue assertion
  - advanced-mode toggle `aria-expanded` regression assertion
  - File: `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.accessibilityStage3.test.tsx`
- Added theme token contrast regression coverage for dictionaries:
  - File: `apps/packages/ui/src/themes/__tests__/dictionaries-accessibility-contrast.stage10.test.ts`
- Added measured contrast audit artifact (light + dark preset minima):
  - File: `Docs/Plans/CHAT_DICTIONARIES_CONTRAST_AUDIT_STAGE3_2026_02_18.md`

## Dependencies

- Stage 1 active-toggle implementation shares code path with Category 1 Stage 2.
- Responsive/mobile adaptations from Category 9 must not degrade keyboard accessibility.
