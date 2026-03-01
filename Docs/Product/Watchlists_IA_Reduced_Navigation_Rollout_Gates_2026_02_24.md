# Watchlists IA Reduced Navigation Rollout Gates (2026-02-24)

## Purpose

Define a controlled rollout and go/no-go decision policy for making reduced Watchlists IA (task-first tabs with `More views`) the default navigation model.

## Rollout Controls

### Mode controls (highest to lowest precedence)

1. Runtime override (QA/debug):
   - `window.__TLDW_WATCHLISTS_IA_VARIANT__ = "baseline" | "experimental"`
   - Legacy compatibility: `window.__TLDW_WATCHLISTS_IA_EXPERIMENT__ = true | false`
2. Legacy env override:
   - `NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA=true|false`
3. Controlled rollout mode:
   - `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE=rollout|baseline|experimental`
   - `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT=0..100`
   - Local per-browser override key:
     - `tldw:feature-rollout:watchlists_ia_reduced_nav_v1:percentage`

### Sticky assignment

- Subject key: `tldw:feature-rollout:subject-id:v1`
- Assignment snapshot key: `watchlists:ia-rollout:v1`
- Telemetry session key: `watchlists:ia-experiment:v1`

## Telemetry Basis For Decision

Variant comparison uses `GET /api/v1/watchlists/telemetry/ia-experiment/summary`:

- `avg_transitions`
- `avg_visited_tabs`
- `reached_target_sessions / sessions`
- `avg_session_seconds`

UI emits transitions on tab changes and session heartbeat flushes on `pagehide` so drop-off/session-length signals are preserved even with low tab movement.

## Go Criteria (Promote Experimental IA to Default)

All criteria must hold across at least 7 consecutive days and >= 200 sessions per variant:

1. `avg_transitions` for `experimental` is >= 15% lower than `baseline`.
2. `reached_target_sessions / sessions` for `experimental` is not lower than `baseline`.
3. `avg_visited_tabs` for `experimental` is not higher than `baseline` by more than 5%.
4. No open P0/P1 navigation regressions (deep links, hidden tab access, tab state restoration).
5. QA confirms secondary-tab access (`Monitors`, `Activity`, `Templates`) remains reachable in reduced IA via `More views`.

## No-Go / Rollback Triggers

Rollback or hold rollout if any trigger occurs:

1. `experimental` transition reduction is < 5% for 3 consecutive days.
2. `reached_target_sessions / sessions` degrades by > 5% vs baseline.
3. Any critical regression in tab routing, deep links, or hidden-tab access.

## Rollback Procedure

1. Set `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE=baseline`.
2. Remove local rollout overrides if used for QA.
3. Verify baseline tab map + route behavior via Watchlists IA regression tests.

## Verification References

- `apps/packages/ui/src/utils/watchlists-ia-rollout.ts`
- `apps/packages/ui/src/utils/watchlists-ia-experiment-telemetry.ts`
- `apps/packages/ui/src/utils/__tests__/watchlists-ia-rollout.test.ts`
- `apps/packages/ui/src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts`
- `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`
