# M5.3 Release Note Template: UX Regression Reporting

Status: Active Template  
Owner: QA + WebUI  
Date: February 14, 2026  
Related:
- `Docs/Product/Completed/WebUI-related/M5_2_UX_Severity_Rubric_Release_Decisions_2026_02.md`
- `Docs/Product/Completed/WebUI-related/M5_1_Smoke_Warning_HardGate_Allowlist_Policy_2026_02.md`
- `Docs/Product/Completed/WebUI-related/M2_Release_Note_Template_Route_Recoverability_2026_02.md`
- `.github/workflows/frontend-ux-gates.yml`

## 1) When to Use

Use this template for every release candidate that includes WebUI changes covered by onboarding/smoke UX gates.

## 2) Required Inputs

Before drafting release notes, gather:

1. Latest onboarding gate result and artifact link.
2. Latest smoke gate result and artifact link.
3. Highest open UX severity (from M5.2 rubric).
4. Active allowlist exceptions changed in this release (added/removed/expired).
5. Any UX-S1/UX-S2 issues shipping with mitigation commitments.

## 3) User-Facing Release Notes Snippet

Copy/paste and replace bracketed fields.

```markdown
### Web UI quality and regression status

- UX gate status: **[pass/fail/conditional]** (onboarding + all-pages smoke).
- Highest open UX severity: **[UX-S0/UX-S1/UX-S2/UX-S3]**.
- Regressions fixed in this release:
  - [Fix 1]
  - [Fix 2]
- Known UX issues shipping with mitigation:
  - [Issue] (severity: [UX-S1/UX-S2], owner: [owner], target fix: [date])

If you encounter a new UI regression, include route path, screenshot, and timestamp in the bug report.
```

## 4) Internal Release Notes Addendum

```markdown
### UX Gate Evidence

- Onboarding gate run: [link/id], result: [pass/fail]
- Smoke gate run: [link/id], result: [pass/fail]
- Unexpected smoke diagnostics: [count]
- Allowlisted diagnostics: [count], changed rules: [ids]

### Severity Decision

- Highest open severity: [UX-S*]
- Decision: [stop-ship / conditional ship / ship]
- Approvers: QA=[name], WebUI=[name], Product=[name if exception]
- Rollback trigger (if conditional): [condition]
```

## 5) Conditional-Ship Rule

If highest open severity is UX-S1 or UX-S2:

1. A mitigation owner and target date must be listed in release notes.
2. A rollback trigger must be documented internally.
3. Product approval is required for UX-S1.

UX-S0 cannot ship.

## 6) Publication Checklist

- [ ] Onboarding and smoke gate outcomes copied into release notes draft
- [ ] Highest severity and decision captured
- [ ] Any UX-S1/UX-S2 exceptions include owner and target date
- [ ] Allowlist diffs summarized (new/removed/expired rules)
- [ ] QA + WebUI sign-off recorded
