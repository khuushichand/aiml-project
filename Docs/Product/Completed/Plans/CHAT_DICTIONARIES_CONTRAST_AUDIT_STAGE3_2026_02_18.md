# Chat Dictionaries Contrast Audit (Stage 3)

## Scope

- Feature: Chat Dictionaries workspace (`apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`)
- Theme source: `apps/packages/ui/src/themes/presets.ts`
- Contrast utility: `apps/packages/ui/src/themes/contrast.ts`
- Date: 2026-02-18

## Method

- Measured built-in presets in both `light` and `dark` modes.
- Evaluated token pairs used by dictionary list/table text and keyboard focus affordances.
- WCAG thresholds:
  - Text: `>= 4.5:1`
  - Non-text/focus indicators: `>= 3:1`

## Results

| Token Pair | WCAG Threshold | Minimum Observed | Worst Case Theme/Mode | Result |
| --- | --- | --- | --- | --- |
| `text/bg` | 4.5:1 | 6.657:1 | `rose-pine/light` | Pass |
| `text/surface` | 4.5:1 | 7.001:1 | `rose-pine/light` | Pass |
| `textMuted/surface` | 4.5:1 | 5.182:1 | `rose-pine/dark` | Pass |
| `textMuted/surface2` | 4.5:1 | 4.531:1 | `rose-pine/light` | Pass |
| `focus/surface` | 3.0:1 | 3.131:1 | `solarized/light` | Pass |

## Regression Gate

- Added automated coverage:
  - `apps/packages/ui/src/themes/__tests__/dictionaries-accessibility-contrast.stage10.test.ts`
- Documented floor thresholds enforced by tests:
  - `text/bg >= 6.5`
  - `text/surface >= 6.9`
  - `textMuted/surface >= 5.1`
  - `textMuted/surface2 >= 4.5`
  - `focus/surface >= 3.1`
