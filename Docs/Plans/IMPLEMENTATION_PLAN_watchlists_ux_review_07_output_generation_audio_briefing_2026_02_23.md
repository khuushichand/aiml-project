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

### Completion Note (2026-02-23)

- All Group 07 stages were executed and validated under the program coordination flow.
- Consolidated execution notes and validation evidence are tracked in:
  - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`
- Group 07 operational artifact:
  - `Docs/Plans/WATCHLISTS_UC2_TEXT_AUDIO_E2E_RUNBOOK_2026_02_23.md`
