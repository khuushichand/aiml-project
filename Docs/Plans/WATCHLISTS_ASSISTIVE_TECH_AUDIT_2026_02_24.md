# Watchlists Assistive-Tech Audit Notes (2026-02-24)

## Scope

Manual validation notes for Group 09 Stage 5 across keyboard, screen-reader semantics, and touch/mobile behaviors on the Watchlists flow:

1. `Overview`
2. `Feeds`
3. `Monitors`
4. `Activity`
5. `Articles`
6. `Reports`
7. `Templates`
8. `Settings`

## Keyboard Validation Path

1. Start on `Overview`, open and close quick setup, verify focus returns to trigger control.
2. Navigate to `Feeds`, toggle feed active state, verify explicit `Enabled`/`Disabled` text is present.
3. Navigate to `Monitors`, open/close monitor form and preview, verify focus restoration.
4. Navigate to `Activity`, open run details drawer, verify controls remain reachable and close returns focus.
5. Navigate to `Articles`, verify source list, article list, and reader actions are keyboard reachable.
6. Navigate to `Reports`, open/close preview drawer and regenerate modal, verify focus restoration.
7. Navigate to `Templates`, switch static/live preview modes and run selection without pointer.
8. Navigate to `Settings`, verify onboarding mode select is keyboard operable and persisted.

## Screen Reader Notes

- Feeds/Monitors tables expose explicit aria labels (`Feeds table`, `Monitors table`).
- Articles surface includes named regions for source list, article list, and article reader.
- Activity and Reports continue to use live-region announcements for status updates.
- Error states use action-oriented language and avoid color-only signaling.

## Mobile and Touch Notes

- Reader source list windowing retains clear context at high source counts.
- Dense list controls remain readable in compact mode, with advanced details opt-in.
- Modal/drawer close and action buttons preserve clear tap targets and recovery paths.

## Known Constraints

- The current test gate validates semantic contracts and keyboard flows, not full screen-reader narration parity per AT product/version.
- Audio sample playback UX depends on browser autoplay/media-permission policy and can require explicit user interaction.
- Very large datasets can still increase cognitive load; compact defaults reduce this but do not eliminate high-volume review effort.

## Evidence Suites

- `src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx`
- `src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.load-error-retry.test.tsx`
- `src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- `src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx`
- `src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
- `src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx`
- `src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
- `src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
- `src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx`
- `src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx`
- `src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx`
- `src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx`

## Gate Command and CI Wiring

```bash
cd apps/packages/ui
bun run test:watchlists:a11y --reporter=dot
```

- CI workflow: `.github/workflows/ui-watchlists-a11y-gates.yml`
- PR checklist integration: `.github/pull_request_template.md` (Watchlists Accessibility Checklist section)
