# Watchlists Consistency QA Checklist

## Cross-Tab Visual Consistency

- [ ] Sources/Monitors/Activity/Reports/Templates tables show an `Actions` column with consistent placement.
- [ ] Action columns in the above tabs remain visually aligned (target width parity).
- [ ] Icon-only controls expose matching tooltip text and `aria-label`.
- [ ] Disabled controls that are not obvious include rationale copy.

## Layout Model Consistency

- [ ] `Items` remains the only full 3-pane reader workflow.
- [ ] Management tabs remain table-first (no ad hoc pane divergence).
- [ ] Sources sidebar acts as a filter/navigation aid, not a competing detail pane.

## Empty-State Consistency

- [ ] Empty states include clear reason text.
- [ ] Empty states include contextual CTA(s) where action is possible.
- [ ] Terminology matches H2 vocabulary (`Feeds`, `Monitors`, `Activity`, `Articles`, `Reports`).

## Accessibility Consistency

- [ ] Tooltip-triggering icon buttons are keyboard reachable and visible on focus.
- [ ] Destructive actions always include confirm affordance and explicit copy.
- [ ] No hover-only affordances for critical actions.

## Validation Commands

- `bunx vitest run src/components/Option/Watchlists --reporter=dot`
- `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx --reporter=verbose`
- `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/group-hierarchy.test.ts --reporter=verbose`
