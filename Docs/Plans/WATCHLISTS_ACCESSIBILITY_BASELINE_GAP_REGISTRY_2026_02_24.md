# Watchlists Accessibility Baseline Gap Registry (2026-02-24)

## Scope

Stage 1 baseline audit for Group 09 (Accessibility and Inclusivity) covering keyboard/focus behavior, screen-reader semantics, status signaling, and localization consistency across Watchlists surfaces.

## Severity Legend

- Critical: Blocks core workflow completion with keyboard or assistive technology.
- Major: Significant friction or ambiguous state for assistive users.
- Minor: Usability quality gap with workaround available.
- Observation: Not a direct blocker, but worth standardization.

## Tab-by-Tab Gap Registry

| Surface | Keyboard/Focus | Screen Reader / ARIA | Status/Contrast Signaling | Localization / Cognitive | Severity |
|---|---|---|---|---|---|
| Overview | Guided-tour modal flow is operable; no baseline tab-order contract test yet. | Guided-tour controls are discoverable; no explicit landmark labeling contract for tour container. | Success banners include text and icon, not color-only. | Long descriptive text can be dense; no concise-mode baseline for first-run cognitive load. | Minor |
| Feeds | CRUD actions exposed via buttons; focus return after destructive confirmations is not centrally validated. | Key list/filter controls are present; source list container has no explicit SR label contract. | Health/status uses labels plus color chips in list detail views. | Terminology is mostly canonical (Feeds), but advanced actions remain jargon-heavy for new users. | Major |
| Monitors | Form controls are keyboard reachable; cross-section focus restoration coverage is incomplete. | Many controls rely on AntD semantics; section-level ARIA grouping is not contract-tested. | Live summary provides text states; density mode can hide rationale behind status chips. | Advanced schedule/filter/audio fields still high concept density for non-technical users. | Major |
| Activity | Existing live-region and table aria-label tests are in place. | Run status changes are announced and table labeling is covered by regression tests. | Status tags use text labels plus icons; progress includes aria-label. | Log/status language is mostly actionable; some failure details are still terse. | Observation |
| Articles | Keyboard shortcuts are covered and editable-target collision guard exists. | Live region exists for selection updates; no baseline SR label contract test on list regions yet. | Row state includes explicit Reviewed/Unread text (not dot-only). | Reader controls are dense but grouped; batch scope text reduces ambiguity. | Minor |
| Reports | Existing live-region and table aria-label tests are in place. | Delivery state announcements are covered; action buttons include aria labels. | Delivery status uses icon + text tags and issue banner text. | Filter language is clearer; provenance/detail text still compact for novice users. | Observation |
| Templates | Editor mode switching exists; keyboard focus flow for preview mode toggles not baseline-tested as a11y contract. | Mode controls rely on component semantics; no explicit live-region narration for preview state transitions. | Preview states include explicit warning/error text. | Jinja2 terminology remains cognitively heavy for beginner authors. | Major |
| Settings | Settings controls are keyboard accessible; no consolidated focus-order baseline test across sections. | Labels are mostly present via form controls; section landmarks not standardized. | Toggle/selection states include explicit labels. | Advanced config terms (TTL, claim clusters, backend mode) require contextual help. | Minor |

## Cross-Surface Priority Gaps

1. Major: Add consistent baseline ARIA label contracts for list containers and grouped controls (Feeds, Articles, Monitors).
2. Major: Add explicit keyboard-focus restoration checks for modal/drawer close flows beyond current spot tests.
3. Major: Expand beginner-oriented wording and context helpers for high-concept authoring areas (Monitors, Templates).
4. Minor: Standardize landmark semantics (`main`, section `aria-labelledby`) for predictable screen-reader navigation.
5. Minor: Create explicit mobile touch-target and reading-order a11y checks for dense list surfaces.

## Localization Gap Notes (Stage 1)

- Localization keys exist for core accessibility/live-region messages in Activity, Reports, and Articles.
- Remaining gap candidates are primarily conceptual clarity rather than missing keys:
  - Monitor advanced settings explanatory copy is still expert-oriented.
  - Template authoring copy still assumes Jinja familiarity.
- No blocking missing-key regressions identified in the Stage 1 focused surfaces.

## Stage 1 Baseline Test Matrix

- `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/StatusTag.accessibility.test.tsx`

## Stage 1 Exit Result

- Baseline registry completed.
- High-priority remediation targets are identified for Stage 2+ execution.
- Focused regression matrix is defined and executable.
