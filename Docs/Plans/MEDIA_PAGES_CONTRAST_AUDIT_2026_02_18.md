# Media Pages Contrast Audit (Stage 15.3)

Date: 2026-02-18  
Scope: `/media`, `/media-multi`, `/media-trash` token pairings used by media reading and focus interactions.

## Method

- Measured built-in theme presets (`default`, `solarized`, `nord`, `high-contrast`, `rose-pine`) in light and dark modes.
- Ratios computed with `apps/packages/ui/src/themes/contrast.ts` (`contrastRatio`), then gated in automated tests.

## Measured Minimum Ratios

| Token Pair | WCAG Threshold | Minimum Observed | Worst Case Theme/Mode | Result |
| --- | --- | --- | --- | --- |
| `text/bg` | `>= 4.5` | `6.66` | `rose-pine/light` | Pass |
| `text/surface` | `>= 4.5` | `7.00` | `rose-pine/light` | Pass |
| `textMuted/surface2` | `>= 4.5` | `4.53` | `rose-pine/light` | Pass |
| `textSubtle/surface2` | `>= 3.0` | `3.03` | `rose-pine/dark` | Pass |
| `focus/surface` | `>= 3.0` | `3.13` | `solarized/light` | Pass |
| `focus/bg` | `>= 3.0` | `3.50` | `nord/light` | Pass |

## Outcome

- No token adjustments were required for the measured media-page text/focus combinations.
- Added regression coverage in `apps/packages/ui/src/themes/__tests__/media-pages-accessibility-contrast.stage15.test.ts` to prevent future contrast regressions against the measured floors.
