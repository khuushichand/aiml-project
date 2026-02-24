# Watchlists UX Review Group 09 - Accessibility and Inclusivity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure Watchlists is operable and understandable for keyboard, screen-reader, low-vision, and cognitive-load-sensitive users across desktop and mobile contexts.

**Architecture:** Apply cross-tab accessibility hardening on semantic structure, live-region announcements, focus management, contrast/signaling, and responsive interaction patterns while preserving performance and power-user shortcuts.

**Tech Stack:** React, TypeScript, Ant Design accessibility patterns, ARIA/live-region updates, i18n, responsive CSS/Tailwind utility usage, Vitest + accessibility-focused tests.

---

## Scope

- UX dimensions covered: keyboard nav, screen readers, contrast signaling, touch/mobile, cognitive accessibility.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Key outcomes:
  - End-to-end keyboard and assistive-tech operability.
  - Better status signaling beyond color-only indicators.
  - Improved mobile and cognitive accessibility consistency.

## Stage 1: Accessibility Baseline Audit and Gap Registry
**Goal**: Establish current a11y baseline and prioritized remediation list for Watchlists.
**Success Criteria**:
- Component-level a11y gap registry exists for each tab.
- Keyboard, focus, ARIA, and contrast issues are categorized by severity.
- Required localization gaps for hardcoded UI strings are identified.
**Tests**:
- Run automated accessibility checks on primary tab surfaces.
- Add baseline accessibility regression tests for existing live regions and labels.
**Status**: Complete

### Stage 1 Execution Notes (2026-02-23)

- Added baseline accessibility regression coverage for Watchlists shell, runs, outputs, and template preview surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
- Published component-level baseline gap registry with severity categorization and localization inventory:
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_GAP_REGISTRY_2026_02_23.md`
- Localization baseline finding: `TemplatePreviewPane` contains multiple hardcoded user-facing strings that are not mapped into `watchlists.json`.

### Stage 1 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
- `/tmp/bandit_watchlists_group09_stage1_frontend_scope_2026_02_23.json`

## Stage 2: Keyboard and Focus Management Hardening
**Goal**: Guarantee predictable keyboard navigation and focus restoration.
**Success Criteria**:
- All modal/drawer flows restore focus appropriately on close.
- Keyboard-only users can complete UC1 and UC2 critical tasks.
- Shortcut handlers avoid collisions with editable and assistive contexts.
**Tests**:
- Add keyboard navigation tests for tabs, forms, lists, and reader interactions.
- Add focus trap/restore tests for modal and drawer components.
**Status**: Complete

### Stage 2 Execution Notes (2026-02-23)

- Added explicit focus-restore lifecycle to output preview drawer:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx`
- Added regression tests to guarantee focus handoff after close for output preview drawer and monitor modal:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- Tightened keyboard shortcut collision coverage to include contenteditable targets in Articles reader:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`

### Stage 2 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
- `/tmp/bandit_watchlists_group09_stage2_frontend_scope_2026_02_23.json`

## Stage 3: Screen Reader Semantics and Live Status Updates
**Goal**: Improve semantic structure and narrated state changes.
**Success Criteria**:
- Interactive lists and tables expose meaningful labels and roles.
- Live regions announce run and delivery changes with useful context.
- Reader pane state and action controls are screen-reader comprehensible.
**Tests**:
- Add tests for aria-label/role attributes on key controls.
- Add tests verifying live-region announcement content changes.
**Status**: Complete

### Stage 3 Execution Notes (2026-02-23)

- Added reader-side live region announcements for selection changes and ensured first auto-selection does not create noisy startup announcements:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
- Added explicit row-level SR labels for article list rows to improve list navigation context:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
- Added/updated regression coverage for live announcements and row semantics:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
- Added locale contract entries for new Items SR announcement copy:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`

### Stage 3 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
- `/tmp/bandit_watchlists_group09_stage3_frontend_scope_2026_02_23.json`

## Stage 4: Visual and Cognitive Accessibility Improvements
**Goal**: Reduce ambiguity and cognitive burden for status-heavy interfaces.
**Success Criteria**:
- Status indicators use icon/text combinations, not color alone.
- Copy and control grouping reduce memory burden in dense forms.
- Mobile layouts maintain clear hierarchy and touch targets.
**Tests**:
- Add visual tests for status badge/icon combinations.
- Add responsive behavior tests for small-screen interactions.
**Status**: Complete

### Stage 4 Execution Notes (2026-02-23)

- Strengthened cognitive accessibility for Settings cluster subscriptions by adding descriptive switch labels and explicit yes/no switch state labels:
  - `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/SettingsTab.tsx`
- Added regression coverage ensuring switch controls expose meaningful cluster-specific labels:
  - `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx`
- Reinforced reader comprehension patterns introduced in Stage 3 (row-level contextual labels + live selection announcements), reducing ambiguity in dense article triage lists:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`

### Stage 4 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx`
- `/tmp/bandit_watchlists_group09_stage4_frontend_scope_2026_02_23.json`

## Stage 5: Accessibility Governance and Regression Gates
**Goal**: Prevent accessibility regressions as Watchlists evolves.
**Success Criteria**:
- Accessibility acceptance criteria are included in Watchlists PR checklist.
- Targeted a11y test suites run in CI for key Watchlists surfaces.
- Documentation includes assistive-tech usage notes and known constraints.
**Tests**:
- Add CI a11y gate commands for Watchlists component tests.
- Re-run accessibility smoke checks on all 8 tabs before release.
**Status**: Complete

### Stage 5 Execution Notes (2026-02-23)

- Added dedicated Watchlists accessibility CI gate script:
  - `apps/packages/ui/package.json` (`test:watchlists:a11y`)
- Published governance runbook with:
  - PR accessibility acceptance checklist
  - CI gate command
  - assistive-tech usage notes and known constraints
  - release smoke set command list
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_GOVERNANCE_RUNBOOK_2026_02_23.md`
- Re-ran targeted accessibility smoke suite through the new scripted entrypoint.

### Stage 5 Validation Evidence

- `bun run test:watchlists:a11y`
- `/tmp/bandit_watchlists_group09_stage5_frontend_scope_2026_02_23.json`
