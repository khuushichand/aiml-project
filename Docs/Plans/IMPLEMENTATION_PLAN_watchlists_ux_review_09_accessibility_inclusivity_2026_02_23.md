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

## Stage 3: Screen Reader Semantics and Live Status Updates
**Goal**: Improve semantic structure and narrated state changes.
**Success Criteria**:
- Interactive lists and tables expose meaningful labels and roles.
- Live regions announce run and delivery changes with useful context.
- Reader pane state and action controls are screen-reader comprehensible.
**Tests**:
- Add tests for aria-label/role attributes on key controls.
- Add tests verifying live-region announcement content changes.
**Status**: Not Started

## Stage 4: Visual and Cognitive Accessibility Improvements
**Goal**: Reduce ambiguity and cognitive burden for status-heavy interfaces.
**Success Criteria**:
- Status indicators use icon/text combinations, not color alone.
- Copy and control grouping reduce memory burden in dense forms.
- Mobile layouts maintain clear hierarchy and touch targets.
**Tests**:
- Add visual tests for status badge/icon combinations.
- Add responsive behavior tests for small-screen interactions.
**Status**: Not Started

## Stage 5: Accessibility Governance and Regression Gates
**Goal**: Prevent accessibility regressions as Watchlists evolves.
**Success Criteria**:
- Accessibility acceptance criteria are included in Watchlists PR checklist.
- Targeted a11y test suites run in CI for key Watchlists surfaces.
- Documentation includes assistive-tech usage notes and known constraints.
**Tests**:
- Add CI a11y gate commands for Watchlists component tests.
- Re-run accessibility smoke checks on all 8 tabs before release.
**Status**: Not Started

## Execution Notes

### 2026-02-24 - Stage 1 completion (baseline audit + gap registry)

- Published component-level accessibility gap registry with severity categories and localization gap notes:
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_BASELINE_GAP_REGISTRY_2026_02_24.md`
- Added baseline accessibility regression coverage for Articles reader control labels and explicit text-based status signaling:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx`
- Stage 1 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/shared/__tests__/StatusTag.accessibility.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group09_stage1_2026_02_24.json`

### 2026-02-24 - Stage 2 completion (keyboard + focus hardening)

- Added focus restoration coverage for key Watchlists modal/drawer flows used in UC1/UC2 setup and output review:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobPreviewModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx`
- Added regression tests proving focus returns to launch controls after close:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx`
- Stage 2 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group09_stage2_2026_02_24.json`
