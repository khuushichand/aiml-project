# Extension, Performance, and Accessibility Audit Plan

## Stage 1: Inventory Existing Coverage
**Goal**: Map the current extension-flow, performance, and accessibility audit surface so the next pass targets real gaps instead of duplicating existing coverage.
**Success Criteria**: Relevant test files, helpers, and route coverage are identified; likely weak spots are listed.
**Tests**: Read-only repo inspection (`rg`, `rg --files`, focused file reads).
**Status**: Complete

## Stage 2: Extension Flow Audit
**Goal**: Audit the browser-extension-specific surfaces and supporting review harnesses for broken routes, stale assumptions, or missing smoke coverage.
**Success Criteria**: Real extension-flow issues are either fixed or documented with reproduction and file references.
**Tests**: Targeted host/browser checks and any relevant extension-oriented e2e or review scripts.
**Status**: Complete

## Stage 3: Performance Audit
**Goal**: Use existing performance capture points and live route probes to identify significant slow routes or wasteful UI patterns.
**Success Criteria**: Outlier routes or codepaths are identified; actionable fixes or guardrails are added where practical.
**Tests**: Existing UX audit performance data, targeted Playwright reruns, focused vitest guards where needed.
**Status**: Complete

## Stage 4: Accessibility Audit
**Goal**: Deepen the current accessibility checks beyond the existing high-risk smoke slice.
**Success Criteria**: Additional real a11y issues are found and fixed, or the current coverage is shown to be clean with stronger evidence.
**Tests**: Existing axe/accessibility specs, targeted route reruns, and focused UI assertions/guards.
**Status**: Complete

## Notes

- Extension-flow inventory showed the main automated coverage gap was route-registry parity for newly stabilized surfaces, not a verified runtime extension regression.
- Added extension parity coverage now pins:
  - `/settings/image-gen` alias redirect to `/settings/image-generation`
  - `/admin/mlx`
  - `/quick-chat-popout`
- Performance review of `ux-audit-v3` data showed the slowest routes are still dominated by dev-server compile time rather than clear runtime UI regressions. Current top outliers include `/moderation-playground`, `/for/researchers`, `/for/osint`, `/kanban`, and `/settings/image-generation`, but these measurements were taken against the webpack dev server and are not reliable enough to justify product fixes by themselves.
- Deeper accessibility coverage was added for:
  - `/companion`
  - `/admin/mlx`
  - `/quick-chat-popout`
  - `/workspace-playground`
  - `/settings/image-generation`
- The expanded axe pass came back clean on all five added routes, so this slice increased evidence without uncovering a new blocking a11y defect.
