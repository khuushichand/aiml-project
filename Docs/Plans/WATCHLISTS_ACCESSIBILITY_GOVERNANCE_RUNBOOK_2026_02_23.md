# Watchlists Accessibility Governance Runbook (2026-02-23)

## Watchlists PR Accessibility Checklist

Use this checklist for every Watchlists UI PR before merge.

- [ ] Keyboard-only path verified for the touched flow (Tab/Shift+Tab, Enter/Space, Escape where applicable).
- [ ] Focus returns to the launch control after closing touched modal/drawer flows.
- [ ] New interactive controls have an accessible name (`aria-label`, visible label, or `aria-labelledby`).
- [ ] New status signals are not color-only (text and/or icon accompaniment present).
- [ ] User-facing copy is localized in `apps/packages/ui/src/assets/locale/en/watchlists.json`.
- [ ] `npm`/`bun` a11y Watchlists regression script passes locally.

## CI Gate Command

Run from `apps/packages/ui`:

```bash
bun run test:watchlists:a11y
```

This script is defined in:

- `apps/packages/ui/package.json`

## Assistive-Tech Notes

- Activity and Reports expose SR live regions for status changes.
- Articles now exposes a live region for selection-change announcements and row-level contextual labels.
- Source form, monitor form, run detail drawer, and output preview drawer focus-return behavior is covered in tests.
- Cluster subscription switches in Settings now expose cluster-specific accessible labels.

## Known Constraints (Current Baseline)

- Template preview pane still has hardcoded UI strings pending full localization migration (tracked in Group 09 follow-up backlog).
- Mobile touch-target validation is currently covered in focused flow tests; a full device matrix pass should run before release candidate cut.

## Release Smoke Set (Accessibility)

Run these tests before Watchlists release candidate sign-off:

```bash
bunx vitest run \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx \
  src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx \
  src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx \
  src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx \
  src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx \
  src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx
```

