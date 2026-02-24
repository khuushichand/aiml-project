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
- Next execution focus: Group 09 Stage 2 keyboard and focus-management hardening across modal/drawer flows.

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
- Group 04 Stage 5 completed: scale validation now covers 1/10/50 monitor and feed datasets in compact/advanced density modes, and a dedicated density QA checklist was published.
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
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts --maxWorkers=1 --no-file-parallelism`
  - `Docs/Plans/WATCHLISTS_MONITOR_DENSITY_SCALE_QA_CHECKLIST_2026_02_23.md`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage4_2026_02_23.json`
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
**Status**: In Progress

### Stage 4 Kickoff Notes (2026-02-23)

- Group 06 Stage 1 completed: reader prioritization baseline now includes explicit sort modes (`newest`, `oldest`, `unread-first`) with persistent sort preference and saved-view sort contract support.
- Group 06 Stage 1 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx --maxWorkers=1 --no-file-parallelism`
- Group 06 Stage 5 completed: source-list render windowing now protects high-volume source profiles with scroll expansion, dedicated responsive/scale test coverage is in place, and a reader mobile+scale QA checklist has been published.
- Group 06 Stage 5 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `Docs/Plans/WATCHLISTS_READER_SCALE_MOBILE_QA_CHECKLIST_2026_02_24.md`
  - `/tmp/bandit_watchlists_group06_stage5_2026_02_24.json`
- Group 09 Stage 1 completed: accessibility baseline gap registry now catalogs keyboard/focus/ARIA/signaling/localization gaps across Watchlists tabs, and focused accessibility regression coverage was added for Articles reader control labeling and text-based status signals.
- Group 09 Stage 1 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/shared/__tests__/StatusTag.accessibility.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `Docs/Plans/WATCHLISTS_ACCESSIBILITY_BASELINE_GAP_REGISTRY_2026_02_24.md`
  - `/tmp/bandit_watchlists_group09_stage1_2026_02_24.json`
- Group 09 Stage 2 completed: modal/drawer keyboard focus restoration now consistently covers monitor setup, monitor preview, guided setup, pipeline builder, and output preview close flows.
- Group 09 Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group09_stage2_2026_02_24.json`
- Group 09 Stage 3 completed: semantic accessibility contracts now cover monitor/feed table labeling, feed/article region naming, and article row accessible labels while preserving existing run/output live-region announcements.
- Group 09 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.load-error-retry.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group09_stage3_2026_02_24.json`
- Group 09 Stage 4 completed: monitor/feed active controls now expose explicit Enabled/Disabled text (not color-only switch state) and accessibility contracts cover semantic list/table discoverability plus state signaling.
- Group 09 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.load-error-retry.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobPreviewModal.focus.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.accessibility-baseline.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group09_stage4_2026_02_24.json`
- Group 09 Stage 5 completed: a dedicated Watchlists accessibility gate command and CI workflow are in place, PR checklist criteria now include Watchlists accessibility acceptance checks, and assistive-tech usage notes/constraints were published.
- Group 09 Stage 5 validation evidence:
  - `bun run test:watchlists:a11y`
  - `.github/workflows/ui-watchlists-a11y-gates.yml`
  - `.github/pull_request_template.md` (Watchlists accessibility checklist section)
  - `Docs/Plans/WATCHLISTS_ASSISTIVE_TECH_AUDIT_2026_02_24.md`
- Group 10 Stage 1 completed: scale profiles and per-surface budgets are now codified, benchmark harness coverage is in place, and baseline timings/constraints have been published.
- Group 10 Stage 1 validation evidence:
  - `bun run test:watchlists:scale`
  - `Docs/Plans/WATCHLISTS_SCALE_BASELINE_BUDGETS_2026_02_24.md`
- Group 10 Stage 2 completed: runs client filtering now paginates beyond the first 200 rows, feeds group filtering caches OPML URL sets to reduce repeated overfetch, and reader smart-count requests now reuse short-lived cache entries for unchanged filters.
- Group 10 Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/runs-filter-fetch.test.ts src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/shared/__tests__/scale-benchmark.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.performance.test.ts --maxWorkers=1 --no-file-parallelism`
  - `bun run test:watchlists:scale`
- Group 10 Stage 3 completed: Articles bulk actions now expose live progress and terminal summaries, large batches keep the surface responsive during execution, and partial failures include a direct retry entrypoint that reruns only failed item IDs.
- Group 10 Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `bun run test:watchlists:scale`
  - `/tmp/bandit_watchlists_group10_stage3_2026_02_24.json`
- Group 10 Stage 4 completed: run notification polling now adapts by active tab/visibility and suppresses low-signal completion noise in Activity-focused contexts, overlapping poll requests are deduped in-flight, and Runs auto-refresh is gated to active+visible Activity sessions.
- Group 10 Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/run-notifications.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `bun run test:watchlists:scale`
  - `/tmp/bandit_watchlists_group10_stage4_2026_02_24.json`
- Next execution focus: Group 10 Stage 5 scale readiness validation and runbook closure.

## Stage 5: Program Closeout and Operationalization
**Goal**: Complete evidence-led closure and handoff for sustained quality.
**Success Criteria**:
- Each group is marked complete with test evidence references.
- Watchlists UX runbooks are updated (onboarding, recovery, scale, a11y).
- Post-release monitoring plan and thresholds are active.
**Tests**:
- Run final integrated Watchlists UX regression gate.
- Validate finding-to-fix coverage ledger for all 10 groups.
**Status**: Not Started

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
| 01 | Robert | Mike | 2 | In Progress | Stage 1 baseline artifact + telemetry exports + Group 01 Stage 1 completion notes | IA/navigation |
| 02 | Mike | Robert | 2 | In Progress | Stage 1 baseline artifact + telemetry exports + Group 02 Stage 1 and Stage 2 completion notes | onboarding/learnability |
| 03 | Robert | Mike | 2 | In Progress | Stage 1 baseline artifact + telemetry exports + Group 03 Stage 1 and Stage 2 completion notes | UC2 workflow |
| 04 | Mike | Robert | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 04 Stage 1/2 completion notes + Stage 3 cross-tab profile completion + Stage 4 summary/confirmation completion + Stage 5 1/10/50 scale validation + density QA checklist + focused Jobs/Sources/Runs/Outputs regressions + Bandit artifacts | density/cognitive load |
| 05 | Robert | Mike | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 05 Stage 1 taxonomy/locale-contract completion + Stage 2 blocker coverage + Stage 3 undo/recovery consistency coverage + Stage 4 delivery-status filtering coverage + Group 05 runbook artifact + focused Sources/Jobs/Outputs/shared regressions + Bandit artifacts | prevention/recovery |
| 06 | Mike | Robert | 4 | Complete | Stage 1 baseline artifact + telemetry exports + Group 06 Stage 1 prioritization/sort baseline + Stage 5 source-window/mobile/high-volume validation + reader scale QA checklist + ItemsTab focused regressions + Bandit stage artifact | articles/triage |
| 07 | Robert | Mike | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 07 Stage 1 output/audio contract completion + Group 07 Stage 2 audio discoverability completion + Group 07 Stage 3 audio test/preview completion + Group 07 Stage 4 delivery/recovery visibility completion + Group 07 Stage 5 UC2 runbook + fallback integration coverage + focused Jobs/Outputs/backend regressions + Bandit artifacts | outputs/audio |
| 08 | Mike | Robert | 3 | Complete | Stage 1 baseline artifact + telemetry exports + Group 08 Stage 1/2/3/4/5 completion notes + template mode/preview/telemetry regressions + Bandit stage artifacts + template authoring runbook | templates |
| 09 | Robert | Mike | 4 | Complete | Stage 1 baseline artifact + telemetry exports + Group 09 Stage 1 gap registry + Group 09 Stage 2 keyboard/focus restoration coverage + Group 09 Stage 3 semantics/live-region coverage + Group 09 Stage 4 visual/state-signaling coverage + Stage 5 Watchlists a11y CI gate + PR checklist criteria + assistive-tech audit notes + Sources/Runs/Items/Jobs/Overview/Outputs a11y regressions + Bandit stage artifacts | accessibility |
| 10 | Mike | Robert | 4 | In Progress | Stage 1 baseline artifact + telemetry exports + Group 10 Stage 1 scale profile/performance budget contract + benchmark harness coverage + baseline timing artifact + Stage 2 runs/source/reader high-volume optimization + Stage 3 batch progress/recovery model + Stage 4 adaptive polling/notification dedup model + scale/performance regression suites | scalability |

## Exit Criteria

- All 10 group plans are `Complete` with linked evidence.
- No open critical regressions in UC1 or UC2 workflows.
- Accessibility and scale gates pass on release candidate builds.
- Monitoring and ownership are assigned for post-release stabilization.
