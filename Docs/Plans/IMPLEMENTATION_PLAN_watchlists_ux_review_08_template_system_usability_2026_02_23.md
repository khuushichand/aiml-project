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

### Completion Note (2026-02-23)

- All Group 08 stages were executed and validated under the program coordination flow.
- Consolidated execution notes and validation evidence are tracked in:
  - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`
- Group 08 operational artifact:
  - `Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`
