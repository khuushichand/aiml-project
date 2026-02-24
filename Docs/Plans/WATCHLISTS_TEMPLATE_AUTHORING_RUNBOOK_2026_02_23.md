# Watchlists Template Authoring Runbook (2026-02-23)

## Purpose

Operationalize validation for beginner and expert template authoring so custom report generation remains reliable.

## Coverage Areas

- Basic/no-code authoring path (recipes, guided fields, save flow).
- Advanced authoring path (versioning, validation, drift/reload handling).
- Preview confidence (static/live semantics, warnings, errors).
- Authoring telemetry and adoption signals.

## Validation Commands

Run from `apps/packages/ui`:

```bash
bunx vitest run \
  src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.mode-contract.test.tsx \
  src/components/Option/Watchlists/TemplatesTab/__tests__/template-mode.test.ts \
  src/components/Option/Watchlists/TemplatesTab/__tests__/template-recipes.test.ts \
  src/components/Option/Watchlists/TemplatesTab/__tests__/TemplatePreviewPane.live-preview.test.tsx \
  src/utils/__tests__/watchlists-prevention-telemetry.test.ts
```

## QA Checklist

1. Create template in basic mode and save without Jinja edits.
2. Switch to advanced mode, edit template, validate syntax, and save.
3. Load historical version, compare to latest, and restore latest.
4. Run preview in static and live contexts and verify warning/error messaging.

## Monitoring Thresholds

Investigate when either condition persists across two release candidates:

- Template save failure rate >5%.
- Preview render failure rate >5%.
- Basic-mode adoption drops >=10 percentage points after release.

## Release Candidate Evidence

- Validation command output.
- Sample basic-mode and advanced-mode authoring traces.
- Template preview success/failure counts and related remediation issues.
