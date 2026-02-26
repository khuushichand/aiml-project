# Watchlists UX Review Group 07 - Output Generation and Audio Briefing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make text and audio briefing generation discoverable, understandable, and testable without expert-level setup effort.

**Architecture:** Elevate audio and report generation into first-class workflow elements by improving setup discoverability, preview/test affordances, and run/output traceability from creation to playback/download.

**Tech Stack:** React, TypeScript, Watchlists outputs services, audio workflow backend integration points, Ant Design table/modal/drawer, Vitest + integration tests.

---

## Scope

- UX dimensions covered: outputs, regeneration flow, audio discoverability, run->output traceability.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py`
  - `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Key outcomes:
  - Audio briefing is visible and understandable early in setup.
  - Users can test audio settings before full workflow runs.
  - Report regeneration and provenance are clear.

## Stage 1: Output and Audio UX Contract
**Goal**: Define unified user model for report vs audio outputs and their lifecycle.
**Success Criteria**:
- UI language clearly distinguishes generated report artifacts and audio variants.
- Run-output relationship is explicit in outputs list and preview.
- Regeneration options are documented and constrained to valid combinations.
**Tests**:
- Add tests for output metadata labeling and provenance rendering.
- Add tests for regenerate modal defaults and validation.
**Status**: Complete

## Stage 2: Audio Discoverability in Setup and Overview
**Goal**: Surface audio briefing capability where users decide workflow intent.
**Success Criteria**:
- Overview and monitor setup explicitly call out audio availability.
- Monitor list surfaces indicate when audio is enabled.
- Help content includes practical audio setup guidance.
**Tests**:
- Add tests for audio badge/chip rendering in relevant tabs.
- Add tests for onboarding and monitor-form copy visibility.
**Status**: Complete

## Stage 3: Audio Configuration Testing and Preview
**Goal**: Let users validate voice/speed/style choices before committing recurring runs.
**Success Criteria**:
- A lightweight audio test action exists in monitor configuration.
- Test output clearly reports success/failure and playable sample when available.
- Advanced audio options include validation and safe defaults.
**Tests**:
- Add tests for audio test trigger, loading, error, and preview states.
- Add tests for advanced audio JSON/URI validation behaviors.
**Status**: Complete

## Stage 4: Output Delivery and Recovery Visibility
**Goal**: Improve confidence in generated content reaching intended destinations.
**Success Criteria**:
- Delivery statuses are visible, filterable, and linked to remediation actions.
- Failed delivery states are highlighted in overview and outputs surfaces.
- Output preview drawer presents template/version/delivery context consistently.
**Tests**:
- Add tests for delivery status announcements and overflow disclosure behavior.
- Add tests for preview drawer metadata blocks across format types.
**Status**: Complete

## Stage 5: End-to-End UC2 Validation for Text+Audio
**Goal**: Verify full briefing pipeline reliability with audio enabled.
**Success Criteria**:
- Documented end-to-end test scenario from monitor creation to output playback/download.
- Reliability metrics defined for audio enqueue, generation, and fallback paths.
- QA runbook covers no-item, failed-TTS, and fallback behaviors.
**Tests**:
- Add integration tests for generate-audio output prefs paths.
- Run end-to-end workflow checks across success and fallback cases.
**Status**: Complete

## Execution Notes

### 2026-02-23 - Stage 1 completion (output/audio UX contract)

- Implemented output/audio contract and provenance clarity across Outputs surfaces:
  - Audio artifact labeling now uses explicit `Audio briefing` contract in:
    - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/outputMetadata.ts`
  - Output preview now always shows provenance metadata (monitor, run, artifact):
    - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputPreviewDrawer.tsx`
  - Regenerate modal now constrains template overrides for audio outputs and documents the rule:
    - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - Locale copy added for provenance and regenerate constraints:
    - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added/updated Stage 1 test coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/source-undo.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group07_stage1_2026_02_23.json`

### 2026-02-23 - Stage 2 completion (audio discoverability in setup and overview)

- Confirmed Overview setup already exposes audio briefing controls in quick setup and pipeline setup.
- Implemented monitor-list discoverability and practical setup guidance in:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added/updated Stage 2 test coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage2_2026_02_23.json`

### 2026-02-23 - Stage 3 completion (audio configuration testing and preview)

- Added lightweight audio sample testing in monitor configuration:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/services/watchlists.ts`
- Added inline audio test loading/success/error states and playable sample rendering in monitor setup.
- Added advanced audio validation for background track URI format (`https://`, `http://`, `file://`) for both test and save flows.
- Added/updated Stage 3 test coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage3_2026_02_23.json`

### 2026-02-23 - Stage 4 completion (output delivery and recovery visibility)

- Added outputs-level delivery issue highlight with direct remediation actions:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - Banner now surfaces failed/partial delivery incidents with:
    - `Show failed only` (applies delivery filter and resets paging)
    - `Open failed runs` (routes to Activity with failed-run status context)
- Added locale and plain-language coverage for recovery guidance:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
- Added Stage 4 regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.regenerate-modal.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/outputMetadata.test.ts src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage4_2026_02_23.json`

### 2026-02-23 - Stage 5 completion (UC2 text+audio end-to-end validation)

- Added Stage 5 runbook with:
  - documented UC2 happy-path scenario from monitor setup to output consumption,
  - reliability metric definitions for enqueue/generation/fallback signals,
  - QA matrix for no-item, enqueue failure, disabled-audio, and fallback paths:
    - `Docs/Plans/WATCHLISTS_UC2_TEXT_AUDIO_E2E_RUNBOOK_2026_02_23.md`
- Added integration test coverage for missing audio fallback metadata paths in outputs API:
  - `tldw_Server_API/tests/Watchlists/test_watchlists_api.py`
  - New assertions now verify:
    - `audio_briefing_status=skipped` when workflow trigger returns `None`
    - `audio_briefing_status=enqueue_failed` with preserved error context when trigger raises
- Validation evidence:
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "generate_audio_payload_triggers_workflow_and_updates_run_stats or generate_audio_false_does_not_trigger_workflow or generate_audio_trigger_returns_none_marks_skipped_metadata or generate_audio_trigger_failure_marks_enqueue_failed_metadata"`
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_audio_briefing_workflow.py -k "trigger_enqueues_workflow or trigger_skips_when_no_items or trigger_handles_scheduler_failure"`
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group07_stage5_2026_02_23.json`
