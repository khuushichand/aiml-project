# M4 Checklist: Non-Core Theme Contrast Remediation

Status: In Progress (Pre-M4 Technical Tasks Completed)  
Owner: WebUI + Accessibility  
Date: February 13, 2026  
Input Baseline: `Docs/Product/WebUI/M3_1_Design_Token_A11y_Baseline_2026_02.md`  
Policy Memo: `Docs/Product/WebUI/M3_3_NonCore_Theme_Contrast_HardGate_Decision_2026_02.md`

## 1) Objective

Convert M3.3 advisory non-core theme contrast findings into M4 ship-blocking hard-gate readiness tasks.

## 2) Backlog by Theme/Token Pair

| Theme | Mode | Token Pair | Current Finding | Target | Owner | Status |
|---|---|---|---|---|---|---|
| `solarized` | `light` | `textMuted/surface` | Below AA | `>= 4.5:1` | WebUI theme owner | Complete (`5.23:1`) |
| `solarized` | `light` | `textMuted/surface2` | Below AA | `>= 4.5:1` | WebUI theme owner | Complete (`4.72:1`) |
| `rose-pine` | `light` | `textMuted/surface` | Below AA | `>= 4.5:1` | WebUI theme owner | Complete (`5.24:1`) |
| `rose-pine` | `light` | `textMuted/surface2` | Below AA | `>= 4.5:1` | WebUI theme owner | Complete (`4.53:1`) |
| `rose-pine` | `light` | `textSubtle/surface` | Below subtle floor | `>= 3:1` | WebUI theme owner | Complete (`3.64:1`) |
| `rose-pine` | `light` | `textSubtle/surface2` | Below subtle floor | `>= 3:1` | WebUI theme owner | Complete (`3.15:1`) |
| `rose-pine` | `dark` | `textSubtle/surface2` | Below subtle floor | `>= 3:1` | WebUI theme owner | Complete (`3.03:1`) |
| `solarized` | `light` | `focus/bg`, `focus/surface` | Focus contrast gap | `>= 3:1` | WebUI theme owner | Complete (`3.56:1`, `3.13:1`) |
| `nord` | `light` | `focus/bg`, `focus/surface` | Focus contrast gap | `>= 3:1` | WebUI theme owner | Complete (`3.50:1`, `3.31:1`) |
| `rose-pine` | `light` | `focus/bg`, `focus/surface` | Focus contrast gap | `>= 3:1` | WebUI theme owner | Complete (`3.71:1`, `3.91:1`) |

## 3) Promotion Tasks for Hard-Gate

- [x] Patch non-core theme tokens in `apps/packages/ui/src/themes/presets.ts`.
- [x] Expand contrast baseline test set to include all built-in themes in `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`.
- [x] Update WebUI release checklist to classify any non-core contrast failure as stop-ship for M4+.
- [x] Attach before/after contrast ratio report per adjusted token pair.

## 4) Validation Commands (M4)

- `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
- `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation|Wayfinding|Route Error Boundaries" --reporter=line`
- `bun /tmp/m4_contrast_audit.ts` (all-theme failure scan; no output indicates pass)
- `bun /tmp/m4_pair_ratios.ts` (patched-pair ratio evidence)

## 5) Exit Criteria

- [x] All listed theme/token rows marked complete with measured ratios.
- [x] Contrast baseline tests hard-gate all shipped built-in themes.
- [ ] Release checklist updated and used by QA sign-off.
