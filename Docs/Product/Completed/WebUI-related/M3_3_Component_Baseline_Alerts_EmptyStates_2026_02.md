# M3.3 Component Baseline: Alerts and Empty States

Status: Active Baseline  
Owner: WebUI + Accessibility  
Date: February 13, 2026  
Execution Plan: `Docs/Product/Completed/WebUI-related/M3_Design_System_A11y_Execution_Plan_2026_02.md`

## 1) Purpose

Define enforceable component-level token and focus contracts for alert and empty-state patterns used across core and non-core WebUI routes.

## 2) Scope

Component families in this baseline:

1. Alert surfaces (`info`, `success`, `warning`, `error`)
2. Empty-state blocks (feature empty + route recovery empty/failure states)
3. Empty/error action controls (primary + secondary CTAs)

## 3) Token Contract

## 3.1 Alert Variants

| Variant | Token Intent | Required Contrast/Behavior |
|---|---|---|
| `info` | `primary` accent + `text` on `surface` | Message content readable at AA on surface container |
| `success` | `success` accent + `text` on `surface` | Semantic success cue; no color-only dependency |
| `warning` | `warn` accent + `text` on `surface` | Warning cue with icon/label, not color-only |
| `error` | `danger` accent + `text` on `surface` | Error cue with recovery guidance when actionable |

Implementation anchors:

- `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`
- `apps/packages/ui/src/components/Option/Settings/tldw.tsx` (connection/status alerts)
- `apps/packages/ui/src/components/Option/Settings/health-status.tsx` (diagnostic alerts)

## 3.2 Empty-State Variants

| Element | Token/Class Contract | Notes |
|---|---|---|
| Container surface | `bg-surface/90`, `border-border/80`, `text-text` | Primary card readability and separation |
| Supporting text | `text-text-muted` | Secondary explanatory copy |
| Tertiary/icon tone | `text-text-subtle`, `bg-surface2/80` | Visual hierarchy without overpowering content |
| Primary CTA | `type="primary"` + keyboard focus ring | Actionable next step |
| Secondary CTA | neutral button + keyboard focus ring | Alternate/recovery path |

Implementation anchors:

- `apps/packages/ui/src/components/Common/FeatureEmptyState.tsx`
- `apps/packages/ui/src/components/Common/ConnectionProblemBanner.tsx`
- `apps/packages/ui/src/components/Option/Prompt/index.tsx` (empty prompt states)

## 4) Keyboard/Focus Contract (M3.3)

All alert and empty-state actions must include visible keyboard focus styles:

- `focus-visible:ring-2`
- `focus-visible:ring-focus`
- `focus-visible:ring-offset-2`
- `focus-visible:ring-offset-bg`

Expanded non-shell toolbar targets covered in this cycle:

- `apps/packages/ui/src/components/Folders/FolderToolbar.tsx`
- `apps/packages/ui/src/components/Timeline/TimelineToolbar.tsx`
- `apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/ViewerToolbar.tsx`

## 5) Automated Coverage

Validation tests:

- `apps/packages/ui/src/components/Common/__tests__/FeatureEmptyState.test.tsx`
- `apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.test.tsx`
- `apps/packages/ui/src/components/Folders/__tests__/FolderToolbar.focus.test.tsx`
- `apps/packages/ui/src/components/Timeline/__tests__/TimelineToolbar.focus.test.tsx`
- `apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/ViewerToolbar.focus.test.tsx`

## 6) Release-Gate Linkage

This baseline is a required input to:

- `Docs/Product/Completed/WebUI-related/M3_Release_Checklist_A11y_Baseline_2026_02.md`

## 7) Exit Criteria

- [x] Alert and empty-state token contracts published.
- [x] Focus-visible behavior codified for empty/error actions.
- [x] Non-shell toolbar focus assertions added for high-frequency controls.
- [x] Release checklist linkage documented.
