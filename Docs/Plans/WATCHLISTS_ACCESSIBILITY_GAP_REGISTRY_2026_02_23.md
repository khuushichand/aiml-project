# Watchlists Accessibility Baseline Gap Registry (2026-02-23)

## Scope and method

- Scope: all Watchlists tabs (`Overview`, `Feeds`, `Monitors`, `Activity`, `Articles`, `Reports`, `Templates`, `Settings`) with focused code inspection on:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
- Automated baseline checks:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`

## Severity legend

- `Critical`: blocks keyboard/screen-reader completion of UC1/UC2.
- `Major`: completion possible but with high friction or ambiguity.
- `Minor`: non-blocking quality/accessibility debt.
- `Observation`: currently acceptable baseline, monitor for regressions.

## Tab-by-tab gap registry

| Tab | Keyboard & Focus | Screen Reader / Semantics | Color / Visual Signaling | Localization | Severity |
|---|---|---|---|---|---|
| Overview | Primary actions are keyboard reachable. | Attention badges expose readable labels (`{{count}} attention items`). See `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx:535`. | Badge uses color + numeric text. | No blocking gap found in shell copy. | Observation |
| Feeds | Core table actions include explicit button labels on icon controls. | Status icons are decorative (`aria-hidden`) with adjacent status text; action buttons have labels. See `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx:90`, `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx:1245`. | Status not color-only in row actions. | No blocking gap identified in sampled controls. | Observation |
| Monitors | Advanced/basic flows are keyboard operable; high control density increases tab-stop burden. | Row actions have labels; form sections rely on visual grouping and can benefit from stronger section narration for SR users in future stages. | Dense forms may increase cognitive load but are not color-only by default. | No immediate localization break in sampled controls. | Minor |
| Activity | Table and action controls are keyboard reachable. | Live region + table label baseline confirmed. See `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx:803`, `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx:993`. | Progress/status include text labels. | No immediate localization gap identified. | Observation |
| Articles | Shortcut support and focus-return behavior are covered; batch controls are keyboard operable. | Row unread dot is visual-only indicator (`span` dot), though a textual reviewed/unread badge is also present. See `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx:1667`, `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx:1699`. | Dual signaling exists (dot + text badge), but dot remains color cue only. | No critical localization gap found in sampled reader controls. | Minor |
| Reports | Controls are keyboard reachable. | Live region + table label baseline confirmed. See `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx:558`, `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx:653`. | Delivery chips include icon + text channel/status labels. | No immediate localization gap identified. | Observation |
| Templates | Preview controls are keyboard operable in baseline harness. | Preview mode and run selector lack explicit accessible naming contract beyond visible text/placeholder; needs stronger SR labeling in follow-up. See `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx:98`, `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx:106`. | No critical color-only status dependency in preview pane. | Multiple user-facing strings in `TemplatePreviewPane` are hardcoded (not localized), including mode labels, run placeholder, warnings, and empty states. See `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx:98`, `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx:124`, `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx:149`. | Major |
| Settings | Core controls are keyboard reachable. | Cluster subscription toggles are rendered as unlabeled per-row `Switch` controls; add row-aware labels/`aria-labelledby`. See `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/SettingsTab.tsx:198`. | No major color-only signal issue in sampled sections. | No blocking localization gap identified in sampled settings labels. | Major |

## Prioritized Stage-2 candidates (from this baseline)

1. Add explicit accessible naming for template preview run selector and mode controls; bind to localized labels.
2. Add row-aware `aria-label` or `aria-labelledby` for cluster subscription toggles in Settings.
3. Add screen-reader-only text for Articles unread-status dot or mark decorative indicator as redundant while preserving textual status.

## Localization gaps identified (Stage-1 inventory)

- Missing i18n wiring in `TemplatePreviewPane` for:
  - `"Static markup"`, `"Live (render with run data)"`, `"Select a run…"`.
  - `"Select a run to preview the template with real data."`, `"Render warnings"`.
  - `"Nothing to preview yet."`, `"No preview content yet. The template will render after a short delay."`.

