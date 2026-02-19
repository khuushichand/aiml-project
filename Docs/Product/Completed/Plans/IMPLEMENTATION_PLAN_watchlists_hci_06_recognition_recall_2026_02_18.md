# Implementation Plan: Watchlists H6 - Recognition Rather Than Recall

## Scope

Route/components: `JobsTab`, `RunDetailDrawer`, `JobFormModal`, help text/tooltips across watchlists  
Finding IDs: `H6.1` through `H6.4`

## Finding Coverage

- Job summaries hide meaningful details behind edit flow: `H6.1`, `H6.2`
- Run details require ID memorization vs clear naming: `H6.3`
- Domain and technical concepts are unexplained in-context: `H6.4`

## Stage 1: Expand Inline Context in List Views
**Goal**: Reduce modal drilling and memorization for routine checks.
**Success Criteria**:
- Jobs table can reveal scope names (sources/groups/tags) via expandable row or structured tooltip.
- Filter column shows compact rule summary instead of raw count only.
- Run detail source reference displays source name with fallback to ID.
**Tests**:
- Component tests for scope/filter summary rendering.
- Unit tests for summary truncation and overflow behavior.
- Regression tests ensuring table performance with expanded metadata.
**Status**: Complete

## Stage 2: Contextual Learning Aids
**Goal**: Explain advanced terms where users encounter them.
**Success Criteria**:
- Tooltips/help chips added for OPML, Jinja2 templates, cron scheduling, and TTL retention.
- Settings concepts (for example cluster claims) include short explanation and docs link.
- Help content is concise and reusable via shared copy registry/i18n keys.
**Tests**:
- Snapshot tests for tooltip/help content presence.
- Link validation tests for in-product documentation URLs.
- Accessibility checks for tooltip trigger discoverability (keyboard + screen reader).
**Status**: Complete

## Stage 3: Predictive Previews in Authoring Flows
**Goal**: Show "what this means" before users submit.
**Success Criteria**:
- Job setup displays live summary panel (sources included, schedule interpretation, filters outcome).
- Filter builder can preview sample matches for current rule set (when data available).
- Template editor links to variable reference and sample context payload.
**Tests**:
- Integration tests for live summary update as form fields change.
- Component tests for preview panel fallback states.
- E2E test for creating a job without opening advanced sections.
**Status**: Complete

## Dependencies

- Copy and terminology should inherit wording decisions from H2.
- Template/help artifacts should align with H10 documentation governance.

## Progress Notes

- `2026-02-18`: Stage 1 delivered.
- Jobs table now uses structured scope tooltips with feed/group/tag names and overflow handling.
- Jobs filter column now renders compact rule previews and full per-rule tooltip summaries.
- Run detail item source column now resolves source names with `#id` fallback.
- Added tests:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx`
- `2026-02-18`: Stage 2 delivered.
- Added shared docs-link registry and reusable help tooltip:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/help-docs.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/WatchlistsHelpTooltip.tsx`
- Added contextual help chips:
  - OPML import hint (`SourcesBulkImport`)
  - cron scheduling (`SchedulePicker`)
  - Jinja2 template context + TTL retention (`JobFormModal`, `TemplateEditor`)
  - claim cluster explanation + docs link (`SettingsTab`)
- Added locale-backed help topic copy under `watchlists:help.*`.
- Added tests:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx` (snapshot + accessibility)
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/help-docs.test.ts` (docs URL validation)
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx`
  - updated `SourcesBulkImport` and `JobFormModal` test coverage for help trigger presence
- `2026-02-18`: Stage 3 delivered.
- Added predictive authoring previews:
  - Live setup summary in `JobFormModal` (name, scope, schedule interpretation, filters, preview outcome).
  - Sample filter preview evaluation helper and preview panel states in `FilterBuilder`.
  - Template editor docs deep-link and embedded sample context payload.
- Added tests:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/FilterBuilder.preview.test.tsx`
  - updated `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.template-sources.test.tsx`
  - `apps/extension/tests/e2e/watchlists.spec.ts` coverage for monitor creation without opening advanced sections
