# Watchlists UX Review Program Coordination Plan (2026-02-23)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Coordinate and execute all Watchlists UX review remediation groups in a dependency-safe, test-driven sequence.

**Architecture:** Use a phased program model with explicit dependencies, shared quality gates, and a central ledger mapping each issue group to implementation evidence and validation outcomes.

**Tech Stack:** React/TypeScript Watchlists frontend, watchlists backend APIs/workflows, Vitest + integration tests, accessibility checks, performance benchmarks, product telemetry.

---

## Plan Inventory and Coverage

| Group | Plan File | Issue Group | Primary Outcome |
|---|---|---|---|
| 01 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_01_information_architecture_navigation_2026_02_23.md` | Information architecture and navigation | Task-aligned navigation and terminology consistency |
| 02 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_02_first_run_experience_learnability_2026_02_23.md` | First-run experience and learnability | Faster onboarding and reduced concept burden |
| 03 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_03_core_workflow_feed_to_briefing_2026_02_23.md` | Core UC2 workflow coherence | Single coherent feed-to-briefing setup path |
| 04 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_04_information_density_cognitive_load_2026_02_23.md` | Information density and cognitive load | Lower setup overwhelm with preserved expert depth |
| 05 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_05_error_prevention_recovery_feedback_2026_02_23.md` | Error prevention and recovery | Consistent actionable feedback and recovery |
| 06 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_06_content_consumption_articles_reader_2026_02_23.md` | Articles consumption UX | Faster daily triage and scalable review workflows |
| 07 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_07_output_generation_audio_briefing_2026_02_23.md` | Outputs and audio briefing UX | Discoverable/testable text+audio briefing flow |
| 08 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_08_template_system_usability_2026_02_23.md` | Template system usability | Strong no-code path with expert fallback |
| 09 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_09_accessibility_inclusivity_2026_02_23.md` | Accessibility and inclusivity | Keyboard/screen-reader/mobile operability |
| 10 | `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_10_scalability_ux_2026_02_23.md` | Scalability of UX | Usable performance at high data volumes |

## Stage 1: Program Setup and Baseline Capture
**Goal**: Establish owners, baseline metrics, and execution sequencing across all groups.
**Success Criteria**:
- Group owner and reviewer assignments are recorded.
- Baseline UX metrics are captured for UC1 and UC2 completion funnels.
- Dependency and phase execution order is approved.
**Tests**:
- Verify baseline test suites run and outputs are archived.
- Verify each group plan status is initialized and tracked.
**Status**: Complete

### Stage 1 Kickoff Notes (2026-02-23)

- Isolated execution workspace created: `.worktrees/codex-watchlists-ux-stage1-20260223` on branch `codex/watchlists-ux-stage1-20260223`.
- Stage 1 baseline artifact created: `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_stage1_baseline_capture_2026_02_23.md`.
- Baseline verification outputs archived under `/tmp`:
  - `/tmp/watchlists_ux_stage1_baseline_watchlists_help_2026_02_23.txt`
  - `/tmp/watchlists_ux_stage1_baseline_ia_terms_routes_2026_02_23.txt`
  - `/tmp/watchlists_ux_stage1_baseline_telemetry_contracts_2026_02_23.txt`
  - `/tmp/watchlists_ux_stage1_plan_status_matrix_2026_02_23.txt`
- Stage 1 telemetry exports archived under `Docs/Plans`:
  - `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`
  - `Docs/Plans/watchlists_ux_stage1_telemetry_export_raw_2026_02_23.csv`
  - `Docs/Plans/watchlists_ux_stage1_telemetry_export_summary_2026_02_23.json`

### Stage 1 Baseline Funnel Snapshot (Telemetry Export)

| Funnel Metric | Baseline | Numerator / Denominator |
|---|---:|---:|
| UC1-F1 First source setup | 92.96% | 66 / 71 users |
| UC1-F2 Time-to-first-review (median) | 567.49s (0.16h) | sample size = 1 |
| UC1-F3 Triage completion (>=20/day) | 0.00% | 0 / 2 users |
| UC2-F1 Pipeline completion (source -> job -> run) | 56.72% | 38 / 67 users |
| UC2-F2 Text output success | 0.06% | 2 / 3182 completed runs |
| UC2-F3 Audio output success | 0.03% | 1 / 3182 completed runs |

## Stage 2: Foundation Execution (Groups 01, 02, 03)
**Goal**: Resolve IA, onboarding, and end-to-end workflow structure first.
**Success Criteria**:
- Navigation and terminology become consistent.
- Onboarding enables first successful run/report for new users.
- UC2 pipeline setup is coherent and testable.
**Tests**:
- Run cross-group flow tests from Overview to first generated report.
- Block progression if critical IA/onboarding regressions exist.
**Status**: Complete

### Stage 2 Kickoff Notes (2026-02-23)

- Group 01 Stage 1 completed: canonical terminology map + i18n/UI contract tests added.
- Group 02 Stage 1 completed: onboarding branch preference added to Overview + Settings with persistence tests.
- Group 03 Stage 1 completed: UC2 pipeline schema/payload contract helpers added with unit tests.
- Group 01 Stage 2 completed: task-view navigation strip (`Collect`, `Review`, `Briefings`) added with legacy-tab fallback mapping and experimental IA interaction coverage.
- Group 03 Stage 2 completed: dedicated Overview pipeline builder implemented with run-now output preview routing and rollback handling for partial failures.
- Group 02 Stage 2 completed: quick setup expanded for multi-feed UC2 setup, explicit audio toggle, and goal-based destination routing with failure-path coverage.
- Group 01 Stage 3 completed: cross-surface orientation guidance is now live with per-tab “what this is / what to do next” copy, explicit run->reports and item->monitor jump actions, and journey coverage for Overview->Feeds->Monitors->Activity->Reports.
- Group 01 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `/tmp/bandit_watchlists_group01_stage3_frontend_scope_2026_02_23.json`
- Group 01 Stage 4 completed: IA variant routing is now governed by controlled rollout resolution (override, persisted assignment, forced variant, percent rollout, baseline fallback), payload-contract telemetry coverage, and documented go/no-go/rollback criteria.
- Group 01 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts src/utils/__tests__/watchlists-ia-rollout.test.ts`
  - `Docs/Plans/WATCHLISTS_IA_EXPERIMENT_ROLLOUT_GONOGO_2026_02_23.md`
  - `/tmp/bandit_watchlists_group01_stage4_frontend_scope_2026_02_23.json`
- Group 01 Stage 5 completed: IA navigation/adoption playbook now documents navigation map + vocabulary matrix, QA checklist, and baseline/post-change adoption comparison framework; tab-by-tab context help routing coverage has been expanded.
- Group 01 Stage 5 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/shared/__tests__/help-docs.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/routes/__tests__/option-watchlists.route-state.test.tsx src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts src/utils/__tests__/watchlists-ia-rollout.test.ts`
  - `bun run test:watchlists:help`
  - `Docs/Plans/WATCHLISTS_IA_NAVIGATION_ADOPTION_PLAYBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group01_stage5_frontend_scope_2026_02_23.json`
- Group 02 Stage 3 completed: guided tour now explains monitor -> template -> output + audio relationships, contextual first-time teach points (cron, filters, templates) persist dismissals, and help-tooltip topics were reframed to task-oriented guidance.
- Group 02 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx -u`
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group02_stage3_frontend_scope_2026_02_23.json`
- Group 03 Stage 3 completed: cross-tab dependency visibility now includes monitor output-linkage summaries, run/report deep links, and run-detail linkage actions that expose upstream/downstream workflow relationships directly from Activity and Reports.
- Group 03 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - `/tmp/bandit_watchlists_group03_stage3_frontend_scope_2026_02_23.json`
- Group 03 Stage 4 completed: Overview quick setup now surfaces pre-commit candidate preview, template-style output preview, explicit audio/text outcome expectations, and test-generation destination guidance before setup submission.
- Group 03 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group03_stage4_frontend_scope_2026_02_23.json`
- Group 03 Stage 5 completed: UC2 onboarding telemetry now captures preview/test-run milestones and first run/output success milestones, emits a funnel snapshot contract with setup/run/output rates + drop-off/timing metrics, and ships with a dedicated UC2 regression gate plus KPI runbook.
- Group 03 Stage 5 validation evidence:
  - `bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `bun run test:watchlists:uc2`
  - `bun run test:watchlists:onboarding`
  - `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group03_stage5_frontend_scope_2026_02_23.json`
- Group 02 Stage 4 completed: onboarding copy now avoids backend model nouns on first-run surfaces, includes clearer next-step wording, and is protected by dedicated first-run terminology contracts plus onboarding copy snapshots.
- Group 02 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.onboarding-copy.snapshot.test.ts src/components/Option/Watchlists/__tests__/watchlists-first-run-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx -u`
  - `bun run test:watchlists:uc2`
  - `/tmp/bandit_watchlists_group02_stage4_frontend_scope_2026_02_23.json`
- Group 02 Stage 5 completed: onboarding telemetry now tracks first run/output success milestones, includes TTTV + drop-off snapshot metrics, and is validated through dedicated onboarding regression + runbook governance.
- Group 02 Stage 5 validation evidence:
  - `bun run test:watchlists:onboarding`
  - `bun run test:watchlists:uc2`
  - `bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx`
  - `Docs/Plans/WATCHLISTS_ONBOARDING_EFFECTIVENESS_VALIDATION_RUNBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group02_stage5_frontend_scope_2026_02_23.json`
- Next execution focus: Program Stage 5 closeout is complete; maintain `test:watchlists:program` on release candidates and operate post-release monitoring thresholds/escalation from the monitoring plan.

## Stage 3: Authoring and Reliability Execution (Groups 04, 05, 07, 08)
**Goal**: Improve complex configuration ergonomics and reduce failure risk.
**Success Criteria**:
- Monitor and template authoring complexity is reduced.
- Error prevention and recovery patterns are consistent across tabs.
- Output/audio flow is discoverable, testable, and trustworthy.
**Tests**:
- Run focused regression suite for monitor/template/output flows.
- Verify recovery behavior for source/run/template/output failure scenarios.
**Status**: Complete

### Stage 3 Kickoff Notes (2026-02-23)

- Group 04 Stage 1 completed: disclosure behavior and decision-sequence ordering validated with existing monitor authoring interaction coverage.
- Group 04 Stage 2 completed: monitor confidence panel added in `JobFormModal` with explicit readiness status and unresolved-risk messaging.
- Group 04 Stage 3 completed: dense list profiles now covered across Jobs, Sources, Runs, and Outputs with compact-vs-advanced disclosure test coverage.
- Group 04 Stage 4 completed: live summary now includes delivery/audio consequences and hidden advanced settings, with explicit recurring-delivery confirmation gating before save/create.
- Group 04 Stage 5 completed: scale-path usability validation now covers 1/10/50 feed monitor setup and high-density list rendering regressions for Sources, Monitors, Activity, and Reports.
- Group 05 Stage 1 completed: shared Watchlists error taxonomy now includes validation/timeout refinements with locale-contract coverage for remediation keys.
- Group 05 Stage 2 completed: prevention-before-commit coverage now includes explicit test coverage for too-frequent schedule and invalid email recipient submit blockers in `JobFormModal`.
- Group 05 Stage 3 completed: reversible-delete messaging now consistently surfaces undo windows for single and bulk delete flows, with partial bulk-restore next-step guidance coverage.
- Group 05 Stage 4 completed: Reports now includes advanced delivery-status filtering so failed/partial delivery outcomes are immediately visible and filterable.
- Group 05 Stage 5 completed: operational recovery runbook published with QA scenario matrix and monitoring escalation thresholds.
- Group 07 Stage 1 completed: output/audio contract updated with explicit provenance metadata in preview, audio artifact labeling, and regenerate constraints for audio outputs.
- Group 07 Stage 2 completed: monitor list now flags audio-enabled jobs and monitor setup includes practical audio defaults guidance; Overview already exposes audio setup controls.
- Group 07 Stage 3 completed: monitor setup now supports inline audio sample testing with loading/success/error states, playback preview, and advanced background URI validation.
- Group 07 Stage 4 completed: outputs now highlights delivery incidents with direct remediation actions (`Show failed only`, `Open failed runs`) while preserving delivery status filtering and live-region status change announcements.
- Group 07 Stage 5 completed: UC2 text+audio runbook published, reliability metrics defined, and outputs API fallback integration tests added for `skipped` and `enqueue_failed` audio briefing states.
- Group 08 Stage 1 completed: template authoring mode contract is now explicitly validated for beginner/expert segmentation, hidden-tool messaging, tab availability, and context preservation across mode transitions.
- Group 08 Stage 2 completed: basic-mode no-code path now has explicit recipe autofill, save-blocking validation, and successful-save payload coverage in `TemplateEditor` tests.
- Group 08 Stage 3 completed: preview pane now provides localized static/live semantics, no-run guidance, structured render warnings, and actionable live-preview error remediation.
- Group 08 Stage 4 completed: advanced template workflows now include explicit test coverage for historical version load/latest reload paths, drift visibility, and save-blocking validation marker behavior.
- Group 08 Stage 5 completed: preview telemetry events/counters, authoring telemetry contract coverage, and template governance runbook are now in place.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage2_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage3_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage4_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `Docs/Plans/WATCHLISTS_MONITOR_DENSITY_SCALE_QA_CHECKLIST_2026_02_23.md`
  - `/tmp/bandit_watchlists_group04_stage5_frontend_scope_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group05_stage1_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/source-undo.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group05_stage2_stage3_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts`
  - `/tmp/bandit_watchlists_group05_stage4_2026_02_23.json`
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
  - `bunx vitest run src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage1_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage2_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage3_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `/tmp/bandit_watchlists_group07_stage4_2026_02_23.json`
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "generate_audio_payload_triggers_workflow_and_updates_run_stats or generate_audio_false_does_not_trigger_workflow or generate_audio_trigger_returns_none_marks_skipped_metadata or generate_audio_trigger_failure_marks_enqueue_failed_metadata"`
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_audio_briefing_workflow.py -k "trigger_enqueues_workflow or trigger_skips_when_no_items or trigger_handles_scheduler_failure"`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `Docs/Plans/WATCHLISTS_UC2_TEXT_AUDIO_E2E_RUNBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group07_stage5_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `/tmp/bandit_watchlists_group08_stage1_2026_02_23.json`
  - `/tmp/bandit_watchlists_group08_stage2_2026_02_23.json`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts`
  - `/tmp/bandit_watchlists_group08_stage3_2026_02_23.json`
  - `/tmp/bandit_watchlists_group08_stage4_2026_02_23.json`
  - `bunx vitest run src/utils/__tests__/watchlists-prevention-telemetry.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group08_stage5_2026_02_23.json`
  - `Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`

## Stage 4: Consumption, Accessibility, and Scale Execution (Groups 06, 09, 10)
**Goal**: Ensure daily-use efficiency, inclusive access, and high-volume resilience.
**Success Criteria**:
- Articles triage remains fast and clear at scale.
- Accessibility gates pass for critical workflows.
- Large dataset interactions remain responsive and reliable.
**Tests**:
- Run reader + accessibility + scale scenario suites.
- Block release if mobile/a11y/scale core flows regress.
**Status**: Complete

### Stage 4 Kickoff Notes (2026-02-23)

- Group 06 Stage 1 completed: reader prioritization model now includes explicit sort modes (`newest`, `oldest`, `unreadFirst`, `reviewedFirst`) with saved-view persistence.
- Group 06 Stage 1 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage1_frontend_scope_2026_02_23.json`
- Group 06 Stage 2 completed: batch review scale/recovery coverage now includes all-filtered confirmation flows and partial-failure reconciliation semantics.
- Group 06 Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage2_frontend_scope_2026_02_23.json`
- Group 06 Stage 3 completed: shortcut discoverability coverage now explicitly verifies list navigation shortcuts are blocked while shortcut help is open.
- Group 06 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage3_frontend_scope_2026_02_23.json`
- Group 06 Stage 4 completed: reader cross-action flow now includes explicit include-in-briefing state-transition coverage alongside existing Monitor/Run/Reports jump behavior.
- Group 06 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage4_frontend_scope_2026_02_23.json`
- Group 06 Stage 5 completed: mobile/high-volume reader validation now includes narrow-viewport operability checks, high-volume batch regression coverage, and a 5/50/200 profile QA checklist.
- Group 06 Stage 5 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `Docs/Plans/WATCHLISTS_ARTICLES_READER_SCALE_QA_CHECKLIST_2026_02_23.md`
  - `/tmp/bandit_watchlists_group06_stage5_frontend_scope_2026_02_23.json`
- Group 09 Stage 1 completed: baseline a11y regression contracts now cover shell labels, runs/outputs live-region attributes, and template preview control naming checks; tab-level severity registry and localization inventory were published.
- Group 09 Stage 1 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_GAP_REGISTRY_2026_02_23.md`
  - `/tmp/bandit_watchlists_group09_stage1_frontend_scope_2026_02_23.json`
- Group 09 Stage 2 completed: focus restore is now covered for output preview drawer + monitor modal close paths, and keyboard shortcut collision coverage now includes contenteditable contexts.
- Group 09 Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
  - `/tmp/bandit_watchlists_group09_stage2_frontend_scope_2026_02_23.json`
- Group 09 Stage 3 completed: Items reader now exposes row-level SR labels and selection-change live announcements; live-status baseline remains covered across Activity and Reports.
- Group 09 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx`
  - `/tmp/bandit_watchlists_group09_stage3_frontend_scope_2026_02_23.json`
- Group 09 Stage 4 completed: Settings cluster subscription controls now provide descriptive switch labels and explicit yes/no state text; reader semantics regressions remain covered.
- Group 09 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.focus-management.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.accessibility-baseline.test.tsx src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx`
  - `/tmp/bandit_watchlists_group09_stage4_frontend_scope_2026_02_23.json`
- Group 09 Stage 5 completed: accessibility governance is now operationalized with a dedicated Watchlists a11y CI gate command and runbook-backed PR checklist/smoke protocol.
- Group 09 Stage 5 validation evidence:
  - `bun run test:watchlists:a11y`
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_GOVERNANCE_RUNBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group09_stage5_frontend_scope_2026_02_23.json`
- Group 10 Stage 1 completed: scale-profile benchmark harness and baseline budget registry published for sources/items/notifications at 5/50/200 and high-volume item profiles.
- Group 10 Stage 1 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
  - `Docs/Plans/WATCHLISTS_SCALE_PROFILE_BASELINE_2026_02_23.md`
- Group 10 Stage 2 completed: Items reader source sidebar now uses bounded initial rendering with scroll-driven expansion, source-cap messaging is explicit at the 1000-feed ceiling, and selection/filter responsiveness has dedicated scale regressions.
- Group 10 Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-behavior.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
  - `/tmp/bandit_watchlists_group10_stage2_frontend_scope_2026_02_23.json`
- Group 10 Stage 3 completed: high-volume batch review operations now expose chunked progress status, terminal success/failure summaries, and explicit retry for failed IDs without blocking the reader surface.
- Group 10 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-behavior.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
  - `bun run test:watchlists:a11y`
  - `/tmp/bandit_watchlists_group10_stage3_frontend_scope_2026_02_23.json`
- Group 10 Stage 4 completed: run-notification polling now adapts by visibility/workload, prevents overlapping in-flight requests, and uses reduced payload size when idle/hidden; shared polling utilities now standardize active-run detection across shell and Activity surfaces.
- Group 10 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/polling-utils.test.ts src/components/Option/Watchlists/RunsTab/__tests__/run-notifications.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
  - `bun run test:watchlists:a11y`
  - `/tmp/bandit_watchlists_group10_stage4_frontend_scope_2026_02_23.json`
- Group 10 Stage 5 completed: scale readiness is now operationalized with a dedicated runbook, scripted scale regression gate, and updated baseline constraints/mitigations aligned with adaptive polling implementation.
- Group 10 Stage 5 validation evidence:
  - `bun run test:watchlists:scale`
  - `Docs/Plans/WATCHLISTS_SCALE_READINESS_RUNBOOK_2026_02_23.md`
  - `/tmp/bandit_watchlists_group10_stage5_frontend_scope_2026_02_23.json`

## Stage 5: Program Closeout and Operationalization
**Goal**: Complete evidence-led closure and handoff for sustained quality.
**Success Criteria**:
- Each group is marked complete with test evidence references.
- Watchlists UX runbooks are updated (onboarding, recovery, scale, a11y).
- Post-release monitoring plan and thresholds are active.
**Tests**:
- Run final integrated Watchlists UX regression gate.
- Validate finding-to-fix coverage ledger for all 10 groups.
**Status**: Complete

### Stage 5 Kickoff Notes (2026-02-23)

- Program-level Watchlists regression gate now runs through a single command (`test:watchlists:program`) chaining help, onboarding, UC2, accessibility, and scale suites.
- Cross-group plan hygiene normalized: Group 05, Group 07, and Group 08 stage statuses are explicitly marked `Complete` across all five stages.
- Missing Stage 3 runbook references were reconciled and published:
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
  - `Docs/Plans/WATCHLISTS_UC2_TEXT_AUDIO_E2E_RUNBOOK_2026_02_23.md`
  - `Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`
- Program closeout governance artifacts are now in place:
  - `Docs/Plans/WATCHLISTS_UX_FINDING_TO_FIX_COVERAGE_LEDGER_2026_02_23.md`
  - `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`

- Stage 5 validation evidence:
  - `bun run test:watchlists:program`
  - `Docs/Plans/WATCHLISTS_UX_FINDING_TO_FIX_COVERAGE_LEDGER_2026_02_23.md`
  - `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
  - `/tmp/bandit_watchlists_program_stage5_frontend_scope_2026_02_23.json`
- Stage 5 execution outcome (2026-02-23): integrated Watchlists regression gate passed across help, onboarding, UC2, accessibility, and scale suites; closeout frontend Bandit scope recorded zero findings.

## Dependency Matrix

| Depends On | Required By | Reason |
|---|---|---|
| Group 01 | Groups 02, 03, 04 | Shared vocabulary and navigation scaffolding |
| Group 02 | Groups 03, 06 | First-run flow and discoverability prerequisites |
| Group 03 | Groups 05, 07, 10 | Core workflow contract for reliability and scale |
| Group 04 | Groups 07, 08 | Reduced configuration complexity before feature depth |
| Group 05 | Group 07, Group 10 | Error/recovery consistency for output and scale paths |
| Group 06 | Group 10 | Reader interaction model influences scale behavior |
| Group 08 | Group 07 | Template usability impacts report/audio quality setup |
| Group 09 | Program Closeout | Accessibility compliance gate before release |
| Group 10 | Program Closeout | Scale readiness gate before release |

## Tracking Ledger (Initialized 2026-02-23)

| Group | Owner (Assignee) | Reviewer (Assignee) | Phase | Status | Validation Evidence | Notes |
|---|---|---|---|---|---|---|
| 01 | Robert | Mike | 2 | Complete | Stage 1 baseline artifact + telemetry exports + Group 01 Stage 1 terminology contracts + Group 01 Stage 2 task-navigation/experimental-IA coverage + Group 01 Stage 3 orientation guidance + journey coverage + Group 01 Stage 4 controlled rollout resolver + telemetry contract tests + go/no-go runbook + Group 01 Stage 5 navigation/adoption playbook + expanded help-routing regressions + Bandit artifacts | IA/navigation |
| 02 | Mike | Robert | 2 | Complete | Stage 1 baseline artifact + telemetry exports + Group 02 Stage 1 and Stage 2 completion notes + Group 02 Stage 3 guided-tour/teach-point/help-topic coverage + Group 02 Stage 4 onboarding copy reduction + first-run terminology contracts + onboarding snapshot coverage + Group 02 Stage 5 onboarding milestone telemetry (first run/output success), TTTV/drop-off snapshot metrics, onboarding regression gate, and onboarding effectiveness runbook + Bandit artifacts | onboarding/learnability |
| 03 | Robert | Mike | 2 | Complete | Stage 1 baseline artifact + telemetry exports + Group 03 Stage 1 and Stage 2 completion notes + Group 03 Stage 3 cross-tab dependency visibility + relationship deep-link regressions + Group 03 Stage 4 candidate/template preview + test-generation routing regressions + Group 03 Stage 5 UC2 milestone telemetry (including first run/output success) + funnel snapshot rates/drop-off/timings + UC2 + onboarding regression gates + KPI runbook + Bandit artifacts | UC2 workflow |
| 04 | Mike | Robert | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 04 Stage 1/2 completion notes + Stage 3 cross-tab profile completion + Stage 4 summary/confirmation completion + Stage 5 scale-path usability regressions + density QA checklist + Bandit artifacts | density/cognitive load |
| 05 | Robert | Mike | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 05 Stage 1 taxonomy/locale-contract completion + Stage 2 blocker coverage + Stage 3 undo/recovery consistency coverage + Stage 4 delivery-status filtering coverage + Group 05 runbook artifact + focused Sources/Jobs/Outputs/shared regressions + Bandit artifacts | prevention/recovery |
| 06 | Mike | Robert | 4 | Complete | Stage 1 baseline artifact + telemetry exports + Group 06 Stage 1 sort/prioritization + saved-view persistence coverage + Group 06 Stage 2 all-filtered and partial-failure batch coverage + Group 06 Stage 3 shortcut discoverability reinforcement + Group 06 Stage 4 cross-action/statefulness coverage + Group 06 Stage 5 mobile/high-volume validation + QA checklist + ItemsTab focused regressions + Bandit artifacts | articles/triage |
| 07 | Robert | Mike | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 07 Stage 1 output/audio contract completion + Group 07 Stage 2 audio discoverability completion + Group 07 Stage 3 audio test/preview completion + Group 07 Stage 4 delivery/recovery visibility completion + Group 07 Stage 5 UC2 runbook + fallback integration coverage + focused Jobs/Outputs/backend regressions + Bandit artifacts | outputs/audio |
| 08 | Mike | Robert | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 08 Stage 1/2/3/4/5 completion notes + template mode/preview/telemetry regressions + Bandit stage artifacts + template authoring runbook | templates |
| 09 | Robert | Mike | 4 | Complete | Stage 1 baseline artifact + telemetry exports + Group 09 Stage 1 accessibility baseline test coverage + gap registry + Stage 2 focus/shortcut hardening regressions + Stage 3 reader semantics/live announcements + Stage 4 settings cognitive/switch labeling + Stage 5 governance runbook + scripted a11y gate + Bandit artifacts | accessibility |
| 10 | Mike | Robert | 4 | Complete | Stage 1 baseline artifact + telemetry exports + Group 10 Stage 1 benchmark baseline profile + Group 10 Stage 2 high-volume list/reader optimization regressions + Group 10 Stage 3 batch-progress/retry recovery coverage + Group 10 Stage 4 adaptive polling/no-overlap coverage + Group 10 Stage 5 scale-readiness runbook + scripted scale gate + Bandit artifacts | scalability |

## Exit Criteria

- All 10 group plans are `Complete` with linked evidence.
- No open critical regressions in UC1 or UC2 workflows.
- Accessibility and scale gates pass on release candidate builds.
- Monitoring and ownership are assigned for post-release stabilization.

## Follow-on Workstream (2026-02-23)

- Release Candidate operations plan:
  - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_rc_operations_workstream_2026_02_23.md`
- Release Candidate operations design:
  - `Docs/Plans/2026-02-23-watchlists-rc-operations-design.md`
- Release Candidate runbook:
  - `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`
