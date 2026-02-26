# Watchlists Template Authoring Runbook (2026-02-23)

## Purpose

This runbook defines a practical operator checklist for template authoring across beginner and advanced paths, with explicit validation steps for static and live preview behaviors.

## Beginner Recipes (No-Code Path)

1. Start in `Basic` mode.
2. Open `Recipe builder` and select one of:
- `Briefing (Markdown)` for daily digest output.
- `Newsletter (HTML)` for email-friendly layouts.
- `MECE analysis (Markdown)` for grouped analytical reports.
3. Apply recipe and verify that name/description defaults are auto-filled.
4. Adjust recipe options:
- Include source links
- Include executive summary (where supported)
- Include published timestamp
- Include tags
5. Use `Preview` tab:
- Confirm static preview renders expected sections.
- If a completed run is available, switch to live preview and verify data-backed rendering.

## Advanced Best Practices (Jinja2 Path)

1. Switch to `Advanced` mode only after confirming baseline structure in Basic mode.
2. Use `Quick insert snippets` to avoid syntax mistakes for loops/conditionals.
3. Keep high-risk edits isolated:
- Save smaller template changes incrementally.
- Validate each change with live preview before final save.
4. Use `Version tools` for safe rollback:
- Load historical version before major edits.
- Compare current drift indicator before save.
- Load latest to resync if historical experiments are abandoned.
5. Treat render warnings as blockers for production schedules unless intentionally accepted.

## QA Checklist

### Static Preview (No Run Required)

- [ ] Preview mode label clearly indicates static markup behavior.
- [ ] Markdown and HTML templates render safely in static mode.
- [ ] Empty-content state is clear and non-technical.

### Live Preview (Completed Run Required)

- [ ] Live mode label indicates run-data dependency.
- [ ] No-run warning appears when no completed runs exist.
- [ ] Run selector is visible and selectable when runs exist.
- [ ] Successful live render returns output and warning metadata when applicable.
- [ ] Warning list renders all returned warning entries.
- [ ] Error state includes remediation guidance and raw error context.

### Save and Validation

- [ ] Server-side syntax validation blocks invalid saves in Basic and Advanced modes.
- [ ] Validation marker count appears in advanced editor when errors are returned.
- [ ] Save success telemetry events are emitted with mode/context details.

## Telemetry Signals (Stage 5)

Track these events to monitor adoption and reliability:

- `watchlists_authoring_started`
- `watchlists_authoring_mode_changed`
- `watchlists_template_recipe_applied`
- `watchlists_authoring_saved`
- `watchlists_template_preview_mode_changed`
- `watchlists_template_preview_rendered`

Suggested weekly checks:

1. Basic vs advanced authoring start ratio.
2. Recipe usage distribution by recipe ID.
3. Live preview success/error ratio.
4. Mean warning count per live preview render.
