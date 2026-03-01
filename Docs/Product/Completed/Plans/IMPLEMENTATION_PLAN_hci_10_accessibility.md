# Implementation Plan: HCI Review - Accessibility

## Scope

Components: `components/ui/*`, `components/ResponsiveLayout.tsx`, all pages
Finding IDs: `10.1` through `10.7`

## Finding Coverage

- `10.1` (Critical): No skip-to-main-content link
- `10.2` (Important): Form fields lack `aria-invalid` and `aria-describedby` for errors
- `10.3` (Important): Dynamic content changes not announced (data loads, status updates)
- `10.4` (Important): Color contrast not verified in dark mode
- `10.5` (Nice-to-Have): Tables lack proper `<caption>` elements
- `10.6` (Nice-to-Have): Icon-only buttons in some places may lack `aria-label`
- `10.7` (Nice-to-Have): No focus management on page navigation

## Key Files

- `admin-ui/components/ResponsiveLayout.tsx` -- Main layout (skip link location)
- `admin-ui/components/ui/button.tsx` -- Button component
- `admin-ui/components/ui/accessible-icon-button.tsx` -- Accessible icon button wrapper (enforces aria-label)
- `admin-ui/components/ui/table.tsx` -- Table component (needs caption)
- `admin-ui/components/ui/toast.tsx` -- Toast notifications (already has role="alert")
- `admin-ui/components/ui/status-indicator.tsx` -- Status display (already has role="status")
- `admin-ui/app/globals.css` -- Global styles including dark mode CSS variables
- All form-containing pages (users, organizations, teams, roles, resource-governor, voice-commands, data-ops, flags, monitoring)

## Stage 1: Skip Link + Form Error Announcements

**Goal**: Fix the most critical accessibility barriers affecting keyboard and screen reader users.
**Success Criteria**:
- Skip-to-main-content link added as first child of `<body>` or root layout.
- Link styled: `sr-only` by default, visible on `:focus` with high-contrast styling.
- Target element `id="main-content"` on main content container with `tabIndex={-1}`.
- Skip link works correctly on both desktop (sidebar layout) and mobile (drawer layout).
- New `FormField` wrapper component or `Input` enhancement that supports:
  - `error` prop (string): when set, adds `aria-invalid="true"` to the input.
  - `errorId` prop (auto-generated): used for `aria-describedby` linking input to error message.
  - Error message rendered as `<span id={errorId} role="alert">`.
- Audit all form pages and update to use the new error announcement pattern.
- Target pages: user create dialog, org create, team create, role create, resource-governor policy form, voice command create/edit, flag create, data-ops backup/retention forms.
**Tests**:
- Unit test: skip link renders, has correct href, is visible on focus.
- Unit test: FormField with error sets aria-invalid and aria-describedby.
- Unit test: error message has role="alert" for immediate announcement.
- Integration test: form submission with validation errors announces errors to screen reader.
**Status**: Complete

## Stage 2: Live Regions + Color Contrast Audit

**Goal**: Ensure dynamic content updates are announced and all color combinations meet WCAG AA.
**Success Criteria**:
- Data containers that update asynchronously wrapped in `aria-live="polite"` regions:
  - Dashboard StatsGrid: announces updated metric values.
  - Monitoring health grid: announces status changes.
  - Alert count displays: announces new alert arrivals.
  - Job queue stats: announces queue state changes.
- `aria-live` additions do not create excessive announcements (only wrap the container, not individual items).
- Status changes (e.g., health healthy→degraded) use `aria-live="assertive"` for critical transitions.
- Full color contrast audit of dark mode theme:
  - All text meets 4.5:1 ratio (AA normal text).
  - All large text (18px+ or 14px+ bold) meets 3:1 ratio (AA large text).
  - All UI components and graphical objects meet 3:1 ratio.
- Document audit results in a contrast checklist.
- Fix any failing combinations by adjusting CSS variable values in `globals.css`.
- Focus on high-risk areas: muted text on muted backgrounds, badge text on colored backgrounds, chart labels.
**Tests**:
- Unit test: verify aria-live attributes present on key containers.
- Automated contrast test: use axe-core or similar to check all component color combinations.
- Snapshot test for any CSS variable changes (to catch regressions).
**Status**: Complete
- Evidence:
  - Live regions added in `admin-ui/components/dashboard/StatsGrid.tsx`, `admin-ui/app/monitoring/components/SystemStatusPanel.tsx`, `admin-ui/app/monitoring/page.tsx`, and `admin-ui/app/jobs/page.tsx`.
  - Contrast audit checklist: `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_hci_10_accessibility.md`.
  - Automated checks: `admin-ui/app/__tests__/dark-mode-contrast.test.ts`, axe smoke checks via `bun run test:a11y`, and updated live-region tests.

## Stage 3: Table Captions + Icon Button Audit + Focus Management

**Goal**: Complete the remaining Nice-to-Have accessibility improvements.
**Success Criteria**:
- `Table` component adds optional `caption` prop rendering as `<caption className="sr-only">`.
- All data tables across the app have descriptive captions (e.g., "List of 47 users", "5 active alerts").
- Caption text includes item count for dynamic context.
- Full audit of icon-only buttons across all pages:
  - Identify all `<Button>` usage with icon children and no visible text.
  - Migrate to `AccessibleIconButton` or add `aria-label` directly.
  - Document audit results as a checklist.
- Focus management on client-side navigation:
  - After route change, focus moves to `<main>` or page `<h1>`.
  - Implemented via Next.js `usePathname` + `useEffect` to focus main content.
  - Focus movement only on user-initiated navigation (not on data refreshes).
**Tests**:
- Unit test: Table with caption prop renders `<caption>` element.
- Audit test: script to find icon-only buttons missing aria-label.
- Unit test: focus moves to main content on pathname change.
**Status**: Complete
- Evidence:
  - `Table` now renders explicit captions when provided and auto-generates sr-only descriptive captions (header summary + row count) when omitted in `admin-ui/components/ui/table.tsx`.
  - Table caption behavior covered by `admin-ui/components/ui/table.test.tsx`.
  - Focus management on route changes implemented in `admin-ui/components/ResponsiveLayout.tsx` and tested in `admin-ui/components/ResponsiveLayout.test.tsx`.
  - Icon-only button audit gate added in `admin-ui/app/__tests__/icon-button-audit.test.ts`; checklist documented in `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_hci_10_accessibility.md`.

## Cross-Reference

- Finding `10.1` (skip link) overlaps with `8.1` in the Cross-Cutting UX plan. Implementation should happen in ONE plan only; the other references it.
- This plan owns the implementation of `10.1`. The Cross-Cutting UX plan (8.1) should reference this plan's Stage 1.

## Dependencies

- All changes in this plan are frontend-only with no backend dependencies.
- Stage 1 is self-contained and can be implemented immediately.
- Stage 2 contrast audit may require design input for color variable adjustments.
- Stage 3 icon button audit requires manual review of all pages; automated grep for `<Button` with icon imports can assist.

## Accessibility Testing Tools

- **axe-core**: Automated accessibility testing in unit tests via `@axe-core/react` or `jest-axe`.
- **Lighthouse**: CI audit for accessibility score.
- **Manual testing**: VoiceOver (macOS) and NVDA (Windows) for screen reader verification.
- **Keyboard-only testing**: Tab through all workflows without mouse.
