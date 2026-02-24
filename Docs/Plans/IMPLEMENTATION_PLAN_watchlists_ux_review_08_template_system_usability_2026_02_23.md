# Watchlists UX Review Group 08 - Template System Usability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make template authoring approachable for non-developer users while preserving advanced Jinja2 power for expert workflows.

**Architecture:** Strengthen the no-code authoring path with recipe- and block-oriented scaffolding, keep advanced editor and versioning intact, and improve preview clarity between static and live render modes.

**Tech Stack:** React, TypeScript, Template editor subcomponents, server template preview/validate APIs, Ant Design modal/tabs/forms, Monaco fallback editor, Vitest + component tests.

---

## Scope

- UX dimensions covered: template abstraction fit, editor scaffolding, preview quality, no-code viability.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatesTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/template-recipes.ts`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Key outcomes:
  - Strong beginner template path with low syntax burden.
  - Accurate and understandable preview behavior.
  - Clear progression from basic to advanced authoring.

## Stage 1: Authoring Mode Contract and User Segmentation
**Goal**: Define explicit beginner and expert capabilities in template authoring.
**Success Criteria**:
- Basic mode supports practical template outcomes without Jinja knowledge.
- Advanced mode exposes full snippet/docs/version controls.
- Mode switch behavior and hidden-context messaging are clear and consistent.
**Tests**:
- Add tests for mode switches, hidden-tool notices, and tab availability.
- Add tests for preserving content/version context across mode transitions.
**Status**: Complete

## Stage 2: Basic Mode Enhancements (No-Code Path)
**Goal**: Improve beginner authoring with structured generation and safer defaults.
**Success Criteria**:
- Recipe builder supports common output styles with clear options.
- Basic editor includes strong starter structures and guidance text.
- Generated templates remain editable and previewable without code knowledge.
**Tests**:
- Add tests for recipe application outputs and form field autofill behavior.
- Add tests for validation and save paths in basic mode.
**Status**: Complete

## Stage 3: Preview Clarity and Live Data Confidence
**Goal**: Ensure users understand static vs live preview semantics and trust outputs.
**Success Criteria**:
- Preview mode labels and descriptions are localized and explicit.
- Live preview clearly indicates run-data dependency and render warnings.
- Preview errors provide actionable remediation.
**Tests**:
- Add tests for static/live preview mode switching and messaging.
- Add tests for run selection, warning rendering, and error fallback behavior.
**Status**: Complete

## Stage 4: Advanced Path Productivity and Safety
**Goal**: Keep advanced users productive without introducing fragile template states.
**Success Criteria**:
- Snippet insertion, variables docs, and version tooling remain discoverable.
- Syntax validation and drift indicators are reliable and understandable.
- Advanced authoring has clear rollback/reload behavior for template versions.
**Tests**:
- Add tests for version load/latest load workflows and drift indicators.
- Add tests for validation errors and save blocking semantics.
**Status**: Complete

## Stage 5: Template UX Adoption and Governance
**Goal**: Validate that template usability improvements increase successful custom output usage.
**Success Criteria**:
- Metrics track basic-mode usage, advanced-mode usage, and preview success rates.
- Documentation includes beginner recipes and advanced best practices.
- QA checklist covers markdown/html templates with and without live preview data.
**Tests**:
- Add telemetry contract tests for authoring and preview events.
- Run template regression suite across create/edit/version flows.
**Status**: Complete

## Execution Notes

### 2026-02-23 - Stage 1 completion (authoring mode contract and segmentation)

- Added component-level authoring mode contract tests in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
- New coverage validates:
  - create flow defaults to Basic mode with no-code recipe path and hidden advanced tabs/tools,
  - edit flow defaults to Advanced mode with docs and version tools visible,
  - switching Advanced -> Basic from docs triggers hidden-tools messaging and returns users to the editor tab,
  - content and loaded-version drift context persist across mode toggles.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `/tmp/bandit_watchlists_group08_stage1_2026_02_23.json`

### 2026-02-23 - Stage 2 completion (basic-mode no-code enhancements)

- Expanded basic-mode `TemplateEditor` coverage in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
- Added tests for Stage 2 success criteria:
  - recipe application autofills starter name/description and generates beginner-ready markdown structure,
  - reapplying recipes preserves user-authored name/description fields,
  - save is blocked when server-side template validation fails in basic mode,
  - successful basic-mode save emits recipe-derived payloads without requiring Jinja2 editing.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `/tmp/bandit_watchlists_group08_stage2_2026_02_23.json`

### 2026-02-23 - Stage 3 completion (preview clarity and live-data confidence)

- Implemented preview semantics and remediation clarity updates in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added explicit static/live preview guidance, no-run live-preview messaging, and structured warning/error alerts with remediation copy.
- Added Stage 3 test coverage in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx`
  - Coverage includes:
    - static/live mode messaging,
    - run selection and render-warning handling,
    - no-run guidance for live mode,
    - actionable live-preview error fallback behavior.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts`
  - `/tmp/bandit_watchlists_group08_stage3_2026_02_23.json`

### 2026-02-23 - Stage 4 completion (advanced productivity and safety)

- Expanded advanced-mode safety and versioning coverage in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
- Added tests validating:
  - historical-version loading and latest-version reload behavior in advanced edit mode,
  - persisted drift/status hints across version changes,
  - server-side validation blocking for advanced saves with editor marker propagation.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group08_stage4_2026_02_23.json`

### 2026-02-23 - Stage 5 completion (adoption telemetry and governance)

- Added template preview telemetry events and counters in:
  - `apps/packages/ui/src/utils/watchlists-prevention-telemetry.ts`
- Added preview telemetry instrumentation in:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
- Added Stage 5 telemetry contract coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx`
  - `apps/packages/ui/src/utils/__tests__/watchlists-prevention-telemetry.test.ts`
- Added governance/runbook artifact:
  - `Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`
- Validation evidence:
  - `bunx vitest run src/utils/__tests__/watchlists-prevention-telemetry.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group08_stage5_2026_02_23.json`
