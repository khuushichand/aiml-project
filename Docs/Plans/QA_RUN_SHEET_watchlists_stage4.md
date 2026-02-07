# Watchlists Stage 4 QA Run Sheet

Updated: 2026-02-07
Scope: Output template preview coverage and Reading List bulk actions

## Automated Checks

- [x] `TldwApiClient` reading bulk endpoint wiring
- [x] Reading bulk failure-summary helper behavior
- [x] Collections template preview render path (select item -> generate preview)

## Latest Run (2026-02-07)

Command:

```bash
bun run test -- src/services/__tests__/tldw-api-client.reading-import-export.test.ts src/components/Option/Collections/ReadingList/__tests__/bulkActions.test.ts src/components/Option/Collections/Templates/__tests__/TemplatePreview.test.tsx
```

Result:
- Test files: `3 passed`
- Tests: `8 passed`

## Manual QA Checklist

- [ ] Enter Reading tab, toggle selection mode, and select multiple items.
- [ ] Run bulk status update and verify mixed-success summary modal when a stale/invalid ID is present.
- [ ] Run bulk add/remove tags and verify list refresh.
- [ ] Run bulk favorite toggle and verify icon/state updates.
- [ ] Run bulk delete and verify items disappear from current page.
- [ ] Run bulk generate output with a template and confirm success modal.
