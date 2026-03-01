# M3.3 Decision Memo: Non-Core Theme Contrast Hard-Gate Cut Line

Status: Finalized  
Owner: WebUI + Accessibility  
Date: February 13, 2026  
Related: `Docs/Product/Completed/WebUI-related/M3_1_Design_Token_A11y_Baseline_2026_02.md`, `Docs/Product/Completed/WebUI-related/M3_Design_System_A11y_Execution_Plan_2026_02.md`, `Docs/Product/Completed/WebUI-related/M4_NonCore_Theme_Contrast_Remediation_Checklist_2026_02.md`

## 1) Decision

Adopt a two-phase hard-gating policy for theme contrast:

1. **M3.3 (current cycle):**
   - Keep CI hard gate on core themes only: `default`, `high-contrast`.
   - Treat non-core decorative theme contrast checks as advisory (reporting + remediation backlog).
2. **M4 cut line (promotion):**
   - Promote all shipped built-in themes to hard-gate once remediation is complete.
   - Block release on any new or regressed non-core contrast violation for WCAG targets below.

## 2) WCAG Targets for Promotion

Promotion from advisory to hard-gate requires:

1. Text contrast AA: `>= 4.5:1` for primary and muted text on core surfaces (`bg`, `surface`, `surface2`).
2. Non-text focus contrast: `>= 3:1` for focus ring tokens on `bg` and `surface`.
3. Subtle text floor: `>= 3:1` on `surface` and `surface2` for tertiary labels.

## 3) Scope Classification

Core themes (hard-gated now):

- `default`
- `high-contrast`

Decorative/non-core themes (advisory in M3.3, hard-gated in M4):

- `solarized/light`
- `rose-pine/light`
- `rose-pine/dark`
- Any additional optional built-in theme variants beyond core defaults.

## 4) Rationale

1. Core workflows depend on `default` and `high-contrast`; these must stay continuously protected.
2. Immediate hard-gating of all decorative themes would introduce avoidable delivery risk during ongoing remediation.
3. Advisory mode in M3.3 preserves visibility without blocking release, while still enforcing a dated escalation path to M4.

## 5) Enforcement Plan

M3.3:

1. Keep current contrast baseline tests as release gate for core themes.
2. Record non-core failing pairs in baseline docs and weekly M3 status update.
3. Prevent regressions by requiring no new failing token pairs in decorative themes.

M4:

1. Patch outstanding non-core token pairs to meet thresholds.
2. Expand contrast-baseline tests to enforce all shipped built-in themes.
3. Update release checklist to treat any contrast failure as stop-ship for WebUI release candidates.

## 6) Exit Criteria

M3.3 complete when:

1. This decision memo is linked in roadmap + M3 execution plan.
2. Advisory backlog list is explicit and owned.
3. M4 promotion checklist is committed and scheduled.

M3.3 completion evidence:

- Owned backlog + promotion checklist committed at `Docs/Product/Completed/WebUI-related/M4_NonCore_Theme_Contrast_Remediation_Checklist_2026_02.md`.
- Non-core theme token remediations landed in `apps/packages/ui/src/themes/presets.ts` with measured ratios recorded in the M4 checklist.
- Contrast hard-gate scope expanded to all built-in themes in `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`.
- M4+ stop-ship language added to `Docs/Product/Completed/WebUI-related/M3_Release_Checklist_A11y_Baseline_2026_02.md`.

M4 promotion complete when:

1. Expanded hard-gate test set passes for all shipped built-in themes.
2. Release checklist reflects all-theme WCAG enforcement.
