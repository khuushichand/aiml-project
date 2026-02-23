# Watchlists Template Authoring Runbook (2026-02-23)

## Purpose

Operationalize validation for beginner and expert template authoring so custom report generation remains reliable.

## Coverage Areas

- Basic/no-code authoring path (recipes, guided fields, save flow).
- Advanced authoring path (versioning, validation, drift/reload handling).
- Visual block composer path (block CRUD, Visual↔Code sync, RawCodeBlock fallback).
- Manual section generation controls (run-scoped prompt orchestration).
- Manual final flow-check modes (`suggest_only`, `auto_apply`) and diff handling.
- Preview confidence (static/live semantics, warnings, errors).
- Authoring telemetry and adoption signals.

## Validation Commands

Run from `apps/packages/ui`:

```bash
bunx vitest run \
  src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.visual-mode.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.roundtrip.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/VisualComposerPane.section-generation.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/FlowCheckDiffPanel.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts \
  src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts \
  src/components/Option/Watchlists/TemplatesTab/__tests__/template-usage.test.ts \
  src/utils/__tests__/watchlists-prevention-telemetry.test.ts
```

Run backend composer/template contracts from repo root:

```bash
source .venv/bin/activate && python -m pytest -q \
  tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_contract.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_template_store.py \
  tldw_Server_API/tests/Watchlists/test_template_endpoints.py \
  tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py
```

## QA Checklist

1. Create template in basic mode and save without Jinja edits.
2. Switch to Visual mode, add core blocks, and confirm content sync in Code mode.
3. Paste unsupported Jinja (`macro/include`) in Code mode and verify `RawCodeBlock` appears in Visual mode.
4. Run manual section generation for a prompt-capable block and confirm block content updates.
5. Run final flow-check in both `suggest_only` and `auto_apply`; validate diff accept/reject behavior.
6. Load historical version, compare to latest, and restore latest.
7. Run preview in static and live contexts and verify warning/error messaging.

## Monitoring Thresholds

Investigate when either condition persists across two release candidates:

- Template save failure rate >5%.
- Preview render failure rate >5%.
- Basic-mode adoption drops >=10 percentage points after release.
- Section-generation endpoint error rate >5%.
- Flow-check endpoint error rate >5%.

## Release Candidate Evidence

- Validation command output.
- Sample basic, advanced, and visual authoring traces.
- RawCodeBlock fallback screenshot/log for unsupported syntax.
- Manual section-generation and flow-check request/response samples.
- Template preview success/failure counts and related remediation issues.

## Guardrails

- Manual-only scope: section generation and flow-check must not auto-trigger jobs/schedules.
- Keep runtime render source as template `content`; composer metadata is auxiliary.
- Preserve unsupported syntax as RawCodeBlock; never silently drop or rewrite unsupported constructs.
