# M5.2 UX Severity Rubric and Release Decision Matrix

Status: Active  
Owner: QA + WebUI + Product  
Date: February 14, 2026  
Related:
- `.github/workflows/frontend-ux-gates.yml`
- `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`
- `apps/tldw-frontend/e2e/smoke/smoke.setup.ts`
- `Docs/Product/Completed/WebUI-related/M5_1_Smoke_Warning_HardGate_Allowlist_Policy_2026_02.md`

## 1) Purpose

Define a single severity model for UX defects so release decisions are consistent, auditable, and tied directly to gate evidence.

## 2) Severity Levels

| Severity | Definition | Typical Signals | Owner |
|---|---|---|---|
| UX-S0 | Core flow is blocked or unsafe to use | Crash/runtime overlay, blank screen without recovery, data-loss risk, authentication lockout in core journey | WebUI + Platform |
| UX-S1 | Severe degradation with partial workaround | Error boundary loops, broken primary CTA, inaccessible critical action, repeated hard-gate unexpected errors on core routes | WebUI |
| UX-S2 | Noticeable but non-blocking regression | Route-scoped warning bursts, non-core flow degradation, copy/wayfinding regressions with workaround | WebUI + Product |
| UX-S3 | Minor issue or cosmetic inconsistency | Visual polish defect, low-impact warning, minor spacing/content mismatch | WebUI |

## 3) Release Decision Matrix

| Highest Open Severity | Gate Outcome | Release Decision | Requirement to Proceed |
|---|---|---|---|
| UX-S0 | Hard fail | Stop-ship | Fix and rerun affected UX gates before merge/release |
| UX-S1 | Hard fail | Stop-ship by default | Product + QA exception required, with rollback and owner/date commitments |
| UX-S2 | Warning | Conditional ship | Must be documented in release notes with owner and remediation target date |
| UX-S3 | Info | Ship allowed | Track in backlog; no release block |

## 4) Classification Inputs

Use all of the following when assigning severity:

1. UX gate results from onboarding and smoke workflows.
2. Unexpected vs allowlisted diagnostics classification in smoke output.
3. Route scope (core routes: chat/media/knowledge/notes/prompts/settings vs non-core).
4. Accessibility impact (keyboard/focus/contrast failure elevates severity in core journeys).
5. Availability of a user-visible workaround.

## 5) SLA Targets

| Severity | Triage SLA | Mitigation/Fix SLA |
|---|---|---|
| UX-S0 | Same day | Same day or immediate rollback |
| UX-S1 | 1 business day | 2 business days |
| UX-S2 | 2 business days | Within current or next sprint |
| UX-S3 | Next triage cycle | Planned backlog slot |

## 6) Governance Rules

1. Severity is assigned by QA, confirmed by WebUI owner, and ratified by Product for UX-S1 exceptions.
2. No allowlist change may downgrade a UX-S0/UX-S1 issue without linked evidence.
3. Every UX-S1/UX-S2 release exception must include:
   - owner
   - expiry/remediation date
   - rollback trigger
4. Severity status is re-evaluated at each release-candidate cut.

## 7) Sign-Off Record (Per Release Candidate)

- [ ] QA severity classification completed
- [ ] WebUI owner decision recorded
- [ ] Product exception recorded (only if UX-S1 ships)
- [ ] Release notes updated with remaining UX-S1/UX-S2 items
