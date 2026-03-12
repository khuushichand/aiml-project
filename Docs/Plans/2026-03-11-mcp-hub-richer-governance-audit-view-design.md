# MCP Hub Richer Governance Audit View Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Upgrade the MCP Hub `Audit` tab from a flat, lightly filtered list into a more
scanable read-only findings dashboard.

The richer view should:

- keep using the existing computed governance findings feed
- group rows by `finding_type`
- expose more useful filters, including relationship presence
- preserve the existing `Open` drill-through behavior
- remain read-only

This slice is intentionally UI-first. It should improve triage and navigation
without introducing new governance semantics or inline remediation.

## Scope

This slice covers:

- richer presentation of the existing governance findings feed
- client-side grouping by `finding_type`
- client-side filtering for relationship presence and available value sets
- fixed section ordering for predictable scanning
- better relationship labeling on findings that already carry related object
  metadata

This slice does not cover:

- new governance finding families
- new risk heuristics or subjective scoring
- inline remediation or edit actions beyond existing `Open`
- nested graphs or tree views
- route-level navigation changes

## Review Corrections

### 1. Keep `has related object` client-side

The current finding DTO already carries:

- `related_object_kind`
- `related_object_id`
- `related_object_label`

That is enough to support a `has related object` filter without changing the
backend endpoint contract.

### 2. Prefer one full fetch, then client-side grouping/filtering

The current audit tab refetches on filter changes, and the endpoint already
supports some server-side filters. For this richer audit pass, the cleaner
model is:

- fetch all visible findings once
- derive available filters from the returned rows
- apply grouping and filtering client-side

That keeps counts, available filter options, and section contents consistent.
It also avoids adding UI-specific backend metadata just for filter chips.

### 3. Keep top counts scoped to the current filtered subset

Once grouping and more filters are present, the summary row should reflect what
is currently visible after filters are applied.

That means:

- `N findings`
- `X errors`
- `Y warnings`

all refer to the current filtered subset, not the original unfiltered dataset.

### 4. Relationship labels must stay secondary

The backend already emits both root-cause findings and consumer findings with
optional relationship metadata. The richer audit view should make those
relationships easier to notice, but should not turn them into a second primary
target on the row.

The first pass should therefore use a simple secondary line:

- `Related to: <label>`

### 5. Group ordering should be fixed

Grouping by finding type is useful only if section ordering stays stable. The
UI should define one explicit section order rather than sorting alphabetically
by whichever findings happen to be present.

## UI Model

The richer audit view remains a read-only top-level MCP Hub tab.

Layout:

- summary row
  - total filtered findings
  - filtered errors
  - filtered warnings
- filter chips / selectors
  - scope
  - severity
  - finding type
  - object kind
  - `has related object`
- grouped findings list
  - one section per `finding_type`
  - section header includes a count
  - rows remain flat inside the section

Each row should show:

- severity badge
- object label
- message
- scope badge
- object kind badge
- optional `Related to: ...` secondary label
- `Open` button using the existing drill-through contract

## Grouping Semantics

Grouping happens client-side after filtering.

Recommended fixed section order:

1. `assignment_validation_blocker`
2. `workspace_source_readiness_warning`
3. `shared_workspace_overlap_warning`
4. `external_server_configuration_issue`
5. `external_binding_issue`

Within each section:

- `error` before `warning`
- then sort by `object_label`

If a section has zero items after filters, it should not render.

## Filter Semantics

This slice should keep filtering simple and consistent.

Filters:

- `severity`
  - `all`
  - `error`
  - `warning`
- `finding type`
  - `all`
  - one of the known finding families present in the current result set
- `object kind`
  - `all`
  - one of the object kinds present in the current result set
- `scope`
  - `all visible scopes`
  - derived from the current result set
- `has related object`
  - off by default
  - when enabled, show only rows with a related object label/id

All of these should be applied client-side over the single loaded result set.

## Relationship Display

Relationship fields are already part of the finding DTO.

Use them as follows:

- if `related_object_label` exists:
  - render `Related to: <label>`
- if `related_object_kind` exists too:
  - append it subtly, e.g. `Related to: Primary Workspace Set (workspace_set_object)`

This should stay secondary to the main finding message.

## Backend Contract

The backend should keep returning a flat findings response.

For this slice, no new required fields are necessary if the client performs one
full fetch and derives filter values locally.

The existing normalized audit feed remains the source of truth:

- `items`
- `counts`
- `total`

The richer audit view should not require a second aggregation endpoint.

## Testing

### Frontend

Add or update tests for:

- grouping by `finding_type`
- fixed section ordering
- filtered summary counts
- `has related object` filtering
- object kind filtering
- scope filtering
- relationship label rendering
- `Open` still working from grouped rows

### Backend

No new backend logic is required for the first pass beyond existing audit feed
coverage, unless a small endpoint adjustment becomes necessary during
implementation.

## Recommendation

Keep this slice narrowly focused on scanability:

- one full audit fetch
- client-side grouping and filtering
- relationship labels
- stable section ordering
- existing `Open` drill-through unchanged

That yields a meaningfully better audit experience without expanding the
backend audit model or inventing new governance logic.
