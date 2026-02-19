# Decision Record: Watchlists H8 Stage 3 IA Experiment (2026-02-19)

## Context

Watchlists currently exposes a high-density seven-tab top-level IA. H8 Stage 3 introduced a reduced, feature-flagged tab map to evaluate whether first-run navigation improves without losing access to advanced surfaces.

## Decision

Adopt an experiment-first rollout:

1. Keep legacy IA as the default/fallback.
2. Gate reduced IA behind `NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA=true`.
3. Preserve access to non-primary tabs (`Monitors`, `Articles`, `Templates`) through `More views`.
4. Preserve deep-link route integrity by rendering the active hidden tab when selected.

## Measurement Plan

Track comparative indicators using experiment telemetry key `watchlists:ia-experiment:v1`:

1. `transitions`: tab-hop count per session.
2. `visited_tabs`: breadth of tab traversal before reaching `runs`/`outputs`.
3. Session timing proxies (`first_seen_at`, `last_seen_at`) for relative flow duration analysis.

Primary success signal: fewer tab transitions before reaching `runs` or `outputs` in the experimental layout.

## Operational Telemetry Update (Stage 5, 2026-02-19)

Measurement moved from local-only storage to dual-path capture:

1. Local fallback snapshot remains in `watchlists:ia-experiment:v1`.
2. Server sink captures per-session snapshots via:
   - `POST /api/v1/watchlists/telemetry/ia-experiment`
   - `GET /api/v1/watchlists/telemetry/ia-experiment/summary`
3. Summary reports comparative aggregates for `baseline` and `experimental` variants:
   - `events`, `sessions`, `reached_target_sessions`
   - `avg_transitions`, `avg_visited_tabs`, `avg_session_seconds`

This provides a queryable telemetry source for staged rollout decisions without blocking UI behavior when telemetry delivery fails.

## Rollout Gates

Promote reduced IA only when all gates hold over a stable observation window:

1. `avg_transitions` (experimental) is at least 15% lower than baseline.
2. `reached_target_sessions / sessions` is not lower than baseline.
3. `avg_visited_tabs` does not increase versus baseline.
4. No deep-link or hidden-tab route regressions in QA.

## Migration Plan

1. Run staged evaluation with the feature flag enabled for QA and opt-in environments.
2. Compare transition/visited-tab patterns against legacy baseline.
3. If experimental IA improves primary signals and no route-regression issues appear, promote reduced IA to default.
4. Keep `More views` affordance for advanced surfaces after promotion.

## Fallback Plan

1. Disable experiment by setting `NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA=false` (or unset).
2. Immediate runtime override for tests/diagnostics: `window.__TLDW_WATCHLISTS_IA_EXPERIMENT__ = false`.
3. Existing legacy tab map remains intact and requires no data migration.

## Verification References

- `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
