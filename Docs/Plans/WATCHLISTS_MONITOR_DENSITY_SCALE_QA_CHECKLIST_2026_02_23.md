# Watchlists Monitor Density Scale QA Checklist (2026-02-23)

## Purpose

Validate Group 04 Stage 5 outcomes for monitor/source table density and quick setup completion under realistic feed counts.

## Scenario Matrix

| Scenario | Dataset Size | Primary Path | Expected Outcome |
|---|---:|---|---|
| S1 | 1 feed / 1 monitor | Beginner quick setup | User can complete setup without advanced controls and no hidden-state confusion |
| S2 | 10 feeds / 10 monitors | Beginner quick setup + compact tables | User can identify scope/filter summaries and complete setup with no validation detours |
| S3 | 50 feeds / 50 monitors | Advanced operator flow + advanced table columns | User can switch compact/advanced density modes and inspect detailed scope/tags efficiently |

## Manual Steps

1. Seed sources and monitors for each dataset size (1, 10, 50).
2. In compact mode, verify row-level summary chips are present for all rows.
3. Toggle advanced mode and verify detailed scope/tags columns become visible.
4. Complete quick setup for briefing goal (`run now` on and off) and confirm destination routing remains correct.
5. Verify no unexpected submit blockers for valid schedule/email/audio combinations.

## Automated Coverage Mapping

- `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
- `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts`

## Exit Criteria

- Compact summary rendering passes for 1/10/50 datasets.
- Advanced density toggle remains functional for 1/10/50 datasets.
- Quick setup task completion remains successful for beginner defaults with no new misconfiguration regressions.
