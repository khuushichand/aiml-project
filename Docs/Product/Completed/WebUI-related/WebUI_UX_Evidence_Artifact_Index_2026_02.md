# WebUI UX Evidence Artifact Index

Status: Active Index  
Owner: WebUI + QA  
Date: February 14, 2026

## Purpose

Roadmap and milestone docs reference evidence bundles produced by Playwright and CI UX gate workflows. Most raw artifacts are generated per run and not committed; this index documents where to retrieve them.

## Evidence Sources

1. GitHub Actions artifacts from `.github/workflows/frontend-ux-gates.yml`:
   - `onboarding-evidence`
   - `ux-smoke-artifacts`
2. Local Playwright output paths during manual execution:
   - `apps/tldw-frontend/test-results/`
   - `apps/tldw-frontend/playwright-report/`

## Historical Evidence Bundle Names

- `m1_2_label_alignment_2026_02_13`
- `m3_2_a11y_focus_2026_02_13`
- `m4_3_onboarding_<tag>`

## Retrieval Notes

- For CI validation, download artifacts from the corresponding workflow run.
- For local validation, preserve the relevant output directory before cleanup and attach it to release evidence.
