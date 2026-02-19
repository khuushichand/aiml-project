# HCI Plan 10 Stage 2: Dark Mode Contrast Checklist (2026-02-18)

## Scope

- File audited: `admin-ui/app/globals.css` (`.dark` token set)
- Method: token contrast check against WCAG AA thresholds
- Automated gate: `cd admin-ui && bunx vitest run app/__tests__/dark-mode-contrast.test.ts`

## Token Pair Results

| Foreground token | Background token | Ratio | Threshold | Result |
| --- | --- | ---: | ---: | --- |
| `--foreground` | `--background` | 19.09:1 | 4.5:1 | Pass |
| `--card-foreground` | `--card` | 19.09:1 | 4.5:1 | Pass |
| `--secondary-foreground` | `--secondary` | 13.95:1 | 4.5:1 | Pass |
| `--muted-foreground` | `--muted` | 5.70:1 | 4.5:1 | Pass |
| `--primary-foreground` | `--primary` | 4.85:1 | 4.5:1 | Pass |
| `--destructive-foreground` | `--destructive` | 9.56:1 | 4.5:1 | Pass |
| `--border` | `--background` | 3.05:1 | 3.0:1 | Pass |
| `--chart-1` | `--background` | 5.44:1 | 3.0:1 | Pass |
| `--chart-2` | `--background` | 10.26:1 | 3.0:1 | Pass |

## Remediation Applied

- Updated dark mode border/input token values for AA UI component contrast:
  - `--border`: `217.2 32.6% 40%`
  - `--input`: `217.2 32.6% 40%`

## Regression Guard

- `app/__tests__/dark-mode-contrast.test.ts` verifies:
  - Required minimum ratios for core text/UI/chart pairs.
  - Snapshot of dark token values to catch future regressions.
