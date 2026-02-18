# Implementation Plan Index: Watchlists UX/HCI Audit Group Plans

## Source Audit

Primary audit document: `Docs/Design/UX_HCI_AUDIT_WATCHLISTS_2026_02_18.md`  
Audit date: `2026-02-18`  
Route scope: `/watchlists` (Sources, Jobs, Runs, Items, Outputs, Templates, Settings)

## Group Plan Documents

1. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_01_visibility_status_2026_02_18.md` (`H1.1`-`H1.7`)
2. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_02_match_real_world_2026_02_18.md` (`H2.1`-`H2.6`)
3. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_03_user_control_freedom_2026_02_18.md` (`H3.1`-`H3.5`)
4. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_04_consistency_standards_2026_02_18.md` (`H4.1`-`H4.5`)
5. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_05_error_prevention_2026_02_18.md` (`H5.1`-`H5.5`)
6. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_06_recognition_recall_2026_02_18.md` (`H6.1`-`H6.4`)
7. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_07_flexibility_efficiency_2026_02_18.md` (`H7.1`-`H7.5`)
8. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_08_aesthetic_minimalism_2026_02_18.md` (`H8.1`-`H8.3`)
9. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_09_error_recovery_2026_02_18.md` (`H9.1`-`H9.3`)
10. `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_hci_10_help_documentation_2026_02_18.md` (`H10.1`-`H10.3`)

## Execution Waves

- Wave 1 (quick wins): H1, H5, H6, H7, H8
- Wave 2 (workflow hardening): H2, H3, H9
- Wave 3 (information architecture and onboarding maturity): H4, H10

## Cross-Plan Dependencies

- H1 dashboard and notifications depend on terminology/help updates from H2 and H10.
- H3 undo and cancellation controls require prevention guardrails from H5.
- H7 keyboard and batch workflows should share interaction patterns defined in H4.
- H10 guided onboarding should reuse dashboard and quick-create paths from H1 and H7.

## Program Completion Criteria

- All catastrophic and major findings in the audit are mapped to shipped code and regression tests.
- `/watchlists` first-run workflow (source -> schedule -> first result) is achievable without reading external docs.
- At-a-glance health, remediation guidance, and bulk triage controls are available without leaving the route.
- Remaining minor/cosmetic findings are tracked with explicit disposition (ship, defer, or reject with rationale).
