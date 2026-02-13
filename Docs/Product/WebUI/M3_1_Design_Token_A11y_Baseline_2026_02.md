# M3.1 Design Token + Accessibility Baseline (Core Flows)

Status: In Progress  
Owner: WebUI + Accessibility  
Date: February 13, 2026  
Execution Plan: `Docs/Product/WebUI/M3_Design_System_A11y_Execution_Plan_2026_02.md`

## 1) Scope

This baseline covers core route shell and high-frequency workflows:

- Chat (`/chat`)
- Media (`/media`)
- Knowledge QA (`/knowledge`)
- Notes (`/notes`)
- Prompts (`/prompts`)
- Settings (`/settings/tldw`)

## 2) Token Inventory (Core UX Surfaces)

| Token | CSS Variable | Primary Use |
|---|---|---|
| `bg` | `--color-bg` | App background / page canvas |
| `surface` | `--color-surface` | Cards, containers, primary panels |
| `surface2` | `--color-surface-2` | Inputs, secondary panels, hover layers |
| `text` | `--color-text` | Primary body copy |
| `textMuted` | `--color-text-muted` | Secondary content, helper text |
| `textSubtle` | `--color-text-subtle` | Tertiary labels, metadata |
| `border` | `--color-border` | Standard control and panel borders |
| `primary` | `--color-primary` | Primary action emphasis |
| `focus` | `--color-focus` | Focus ring / keyboard affordance |
| `danger` | `--color-danger` | Destructive or error emphasis |
| `warn` | `--color-warn` | Warning emphasis |
| `success` | `--color-success` | Success emphasis |

## 3) Automated Guardrails Added

New utilities:

- `apps/packages/ui/src/themes/contrast.ts`
  - `contrastRatio(...)`
  - `meetsTextContrast(...)`
  - `meetsNonTextContrast(...)`
  - `auditThemeTextContrast(...)`

New tests:

- `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`

Hard-gated checks (core themes: `default`, `high-contrast`):

1. Text contrast AA (`>= 4.5:1`) on `bg`, `surface`, `surface2`
2. Muted text AA (`>= 4.5:1`) on `surface`, `surface2`
3. Subtle text minimum readability (`>= 3:1`) on `surface`, `surface2`
4. Focus ring non-text contrast (`>= 3:1`) on `bg` and `surface`

## 4) Implemented Improvements

1. Increased default light `focus` token contrast to satisfy non-text focus guidance:
   - from `31 181 159`
   - to `13 134 119`

Updated files:

- `apps/packages/ui/src/themes/presets.ts`
- `apps/packages/ui/src/assets/tailwind-shared.css`

2. Added explicit focus-visible ring styles to high-frequency shell controls:

- `apps/packages/ui/src/components/Layouts/ChatHeader.tsx`
- `apps/packages/ui/src/components/Common/ChatSidebar.tsx`

## 5) Validation Evidence

Command:

- `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/components/Common/ChatSidebar/__tests__/shortcut-active.test.ts`

Outcome:

- `3 files passed`
- `10 tests passed`

## 6) Advisory Findings (Non-Core Built-in Themes)

During baseline calibration, additional built-in themes were observed with contrast gaps that are not yet hard-gated:

- `solarized/light`: muted text below AA on `surface`/`surface2`
- `rose-pine/light`: muted + subtle text below target on `surface`/`surface2`
- `rose-pine/dark`: subtle text below `3:1` on `surface2`
- Focus ring `3:1` gaps on some light-mode decorative themes (`default` before fix, `solarized`, `nord`, `rose-pine`)

Disposition:

- Tracked as M3.3 remediation backlog; core themes are hard-gated now.

## 7) Exit Criteria for M3.1

- [x] Core token inventory documented.
- [x] Contrast guardrail utility and tests added.
- [x] Default theme focus contrast remediated.
- [ ] Advisory theme remediation plan approved for hard-gating expansion.
