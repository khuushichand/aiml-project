# Watchlists IA Experiment Rollout and Go/No-Go Criteria (2026-02-23)

## Purpose

Define controlled rollout behavior for reduced IA navigation and establish release decision criteria for making experimental IA the default.

## Rollout Controls

Resolved in priority order by `apps/packages/ui/src/utils/watchlists-ia-rollout.ts`:

1. Runtime override: `window.__TLDW_WATCHLISTS_IA_EXPERIMENT__` (`true`/`false` or `experimental`/`baseline`)
2. Persisted assignment: `localStorage["watchlists:ia-rollout:v1"]`
3. Forced variant env: `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT`
4. Percent rollout env: `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT` (`0-100`)
5. Safe fallback: `baseline`

## Safety/Fallback Rules

- Invalid rollout config must always fall back to `baseline`.
- Runtime overrides are highest-priority and non-destructive.
- Rollout assignment is sticky per browser session context via local storage to avoid random variant flapping.
- If telemetry ingest fails, local telemetry state still persists (non-blocking UX).

## Telemetry Decision Inputs

Source endpoint:

- `GET /api/v1/watchlists/telemetry/ia-experiment/summary`

Primary metrics:

- `reached_target_sessions`
- `avg_transitions`
- `avg_visited_tabs`
- `avg_session_seconds`

## Go/No-Go Criteria

Promote experimental IA to default only when all are true:

1. `experimental.reached_target_sessions >= 30`
2. `experimental.avg_transitions >= baseline.avg_transitions * 0.95`
3. `experimental.avg_visited_tabs >= baseline.avg_visited_tabs * 0.95`
4. No increase in critical IA/navigation defects during release candidate QA.
5. Stage regression gate passes:
   - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts src/utils/__tests__/watchlists-ia-rollout.test.ts`

No-Go (keep baseline default) if any criterion fails.

## Rollback Procedure

If experimental IA causes regressions in production:

1. Set `NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT=baseline`
2. Redeploy frontend bundle
3. Keep telemetry summary collection active for postmortem comparison
