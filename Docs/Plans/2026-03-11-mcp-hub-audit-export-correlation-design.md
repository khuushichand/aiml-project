# MCP Hub Audit Export And Correlation Summary Design

Date: 2026-03-11
Status: Implemented

## Goal

Extend the richer MCP Hub `Audit` tab with:

- client-side export/share actions for the current filtered view
- a compact related-object correlation summary strip

This slice stays read-only and UI-only. It should improve triage and reporting
without adding backend export endpoints, saved snapshots, or share links.

## Scope

This slice covers:

- `Copy Report`
- `Download JSON`
- `Download Markdown`
- export of the current filtered audit view only
- a compact summary strip for top related objects
- optional client-side related-object focus from summary chips
- explicit success/failure UX for copy/download actions

This slice does not cover:

- persisted share links
- saved audit snapshots
- backend export endpoints
- inline remediation
- new governance finding families

## Review Corrections

### 1. Export needs explicit success and failure UX

Clipboard and download flows can fail. This slice should surface clear UI
feedback for:

- copy succeeded
- copy failed
- download started
- download failed

The feedback should be lightweight and local to the audit tab.

### 2. JSON export must include filter context

Because export is scoped to the current filtered view, the JSON payload should
include:

- `generated_at`
- current filters
- current related-object focus
- filtered counts
- exported findings

This preserves the context of why the exported subset looks the way it does.

### 3. Related-object summary needs stable ordering

The summary strip should aggregate by:

- `related_object_kind`
- `related_object_id`

with a display label from:

- `related_object_label`
- or fallback `related_object_id`

Ordering should be stable:

1. total findings descending
2. error count descending
3. label ascending

### 4. The summary strip must be labeled as pre-focus context

The summary strip is computed from the currently filtered findings before the
optional related-object focus is applied. The UI should make that explicit with
copy like:

- `Top related objects in current filtered findings`

### 5. Active related-object focus needs an explicit clear affordance

The audit tab should show:

- a visible active-focus tag/badge
- an obvious clear action

This keeps the export state and the current grouped rows understandable.

### 6. Keep pure formatting helpers separate from browser side effects

Pure helpers:

- `groupAuditFindings(...)`
- `summarizeRelatedObjects(...)`
- `buildAuditMarkdownReport(...)`
- `buildAuditJsonExport(...)`

Effect helpers:

- `copyAuditReportToClipboard(...)`
- `downloadAuditBlob(...)`

This keeps the component easier to test.

### 7. Markdown export should include the summary strip

The Markdown report should include:

- filtered counts
- active filters
- active related-object focus
- top related-object summary
- grouped findings

That keeps the exported report aligned with what made the on-screen view useful.

## Export Model

The audit tab should add three actions:

- `Copy Report`
- `Download JSON`
- `Download Markdown`

All actions operate on the final current view:

1. apply base filters
2. compute related-object summary from that filtered subset
3. apply optional related-object focus
4. export the final visible subset

### JSON export

Shape:

- `generated_at`
- `filters`
- `related_object_focus`
- `counts`
- `items`

### Markdown export

Sections:

1. title
2. generated timestamp
3. filtered counts
4. active filters
5. active related-object focus
6. top related-object summary
7. grouped findings by finding type

### Copy report

Copies the Markdown report text to clipboard.

## Related-Object Summary Strip

The summary strip sits above grouped findings and remains compact.

It should show the top 3-5 related objects from the current filtered findings
before related-object focus is applied.

Each chip/card shows:

- label
- object kind
- finding count

Example:

- `Primary Workspace Set · workspace_set_object · 3 findings`
- `Docs Managed · external_server · 2 findings`

## Related-Object Focus

Clicking a summary chip should apply a client-side related-object focus.

Rules:

- focus is exact to `related_object_kind + related_object_id`
- focused state narrows the final visible findings
- focus does not change the base filter chips
- focus can be cleared explicitly

The summary strip itself should still represent the broader filtered set before
focus, not collapse to only the selected object.

## UI Behavior

Recommended layout additions above the grouped findings:

- export/share actions row
- export status feedback
- related-object summary strip
- active related-object focus badge with clear action

The current grouped findings list and `Open` drill-through remain unchanged.

## Testing

### Frontend

Add or update tests for:

- summary strip rendering
- stable summary ordering
- related-object focus interaction
- clear related-object focus
- JSON export payload contents
- Markdown report contents
- clipboard success/failure handling
- download helper invocation

### Backend

No backend changes are required for the first pass.

## Recommendation

Keep this slice strictly client-side:

- export the current filtered view
- summarize root causes from existing related-object metadata
- preserve the current drill-through model

That gives immediate practical value without changing the governance model or
the backend audit feed.
