# Deep Research Trust UI Design

**Date:** 2026-03-07

## Goal

Surface the new deep-research trust outputs in the existing run console so users can quickly assess claim support, contradictions, unsupported claims, and source trust without reading raw JSON artifacts.

## Motivation

The backend now emits trust artifacts and bundle fields for:

- verification summary
- unsupported claims
- contradictions
- source trust and snapshot policy

Those signals are useful only if the console exposes them in a readable form. Right now the data is technically available through bundle and artifact reads, but the page still treats it as generic JSON. That is enough for debugging, not for a usable research workflow.

The current console already has the right seams:

- selected-run state reducer in `apps/tldw-frontend/pages/research.tsx`
- lazy artifact reads via `getResearchArtifact(...)`
- lazy bundle reads via `getResearchBundle(...)`
- focused page tests in `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

This slice should build on those seams rather than introducing a second trust-specific page or new backend API contracts.

## Recommended Approach

Add a dedicated read-only trust section to the selected-run detail panel in:

- `apps/tldw-frontend/pages/research.tsx`

and extend the frontend research client types in:

- `apps/tldw-frontend/lib/api/researchRuns.ts`

Three approaches were considered:

1. Raw artifact viewers only.
   This is the smallest change, but it keeps trust outputs buried in generic JSON.

2. Dedicated trust panels in the selected-run detail.
   This adds lightweight summaries and lists for the trust outputs while reusing the existing run console structure.

3. Separate trust tab or drawer.
   This creates a cleaner separation, but adds navigation complexity without enough value for v1.

The recommended option is `2`.

It makes the trust work visible to users without fragmenting the research experience.

## Scope

This design covers:

- typed frontend trust models
- a trust summary section in the selected-run panel
- rendering from loaded bundle data when available
- lazy-loading trust artifacts when bundle data is not loaded yet
- focused console tests for trust rendering and empty states

This design does not cover:

- new backend APIs
- mutating trust workflows
- retry or rerun actions from trust findings
- a separate trust page
- cross-run trust dashboards

## Frontend Architecture

Keep this slice frontend-only.

The primary UI stays in:

- `apps/tldw-frontend/pages/research.tsx`

The client typing changes stay in:

- `apps/tldw-frontend/lib/api/researchRuns.ts`

Data precedence should be:

1. render trust data from `bundle` when the bundle has already been loaded
2. otherwise reuse any already loaded trust artifacts from the existing raw artifact viewer state
3. otherwise lazily fetch the trust artifacts on demand for the selected run when trust artifacts are actually available
4. otherwise show a neutral empty state while the run is still before synthesis

No SSE or backend contract changes are needed here. The current stream already keeps the selected run state current enough to know when trust data should exist, and the existing artifact and bundle endpoints already expose the underlying data.

## Data Model

Add explicit frontend types for:

- `ResearchVerificationSummary`
- `ResearchUnsupportedClaim`
- `ResearchContradiction`
- `ResearchSourceTrust`

The exact shapes can stay permissive where the backend is still heuristic, but they must be typed enough for rendering:

- verification summary:
  - supported and unsupported counts
  - contradiction count
  - warnings when present
- unsupported claims:
  - claim text
  - focus area
  - reason
  - supporting note or source references when present
- contradictions:
  - note snippet
  - focus area
  - source reference when present
- source trust:
  - source title
  - provider
  - trust tier
  - snapshot policy
  - trust labels

Inside `research.tsx`, derive one normalized trust view from either:

- bundle fields, or
- the lazy-loaded trust artifacts

That avoids duplicating render logic for bundle mode versus artifact mode.

The normalization helper should explicitly handle the current backend wrapper differences:

- bundle trust fields are direct values and arrays
- artifact reads return wrapped payloads such as:
  - `unsupported_claims.json` -> `{ "claims": [...] }`
  - `contradictions.json` -> `{ "contradictions": [...] }`
  - `source_trust.json` -> `{ "sources": [...] }`

The page should normalize those into one consistent trust view before rendering.

## Page Behavior

Add a `Research Trust` section to the selected-run detail column, below checkpoints and above the raw artifacts list.

The section should render four read-only blocks:

### Verification

Show:

- supported claim count
- unsupported claim count
- contradiction count
- top-level warnings when present

### Unsupported Claims

Show a compact list of:

- claim text
- focus area
- unsupported reason

### Contradictions

Show a compact list of:

- contradiction snippet
- focus area
- source reference when present

### Source Trust

Show a compact list or table of:

- source title
- provider
- trust tier
- snapshot policy
- trust labels

Loading behavior:

- if bundle data is already loaded, render immediately
- if trust artifacts were already loaded through the raw artifact viewer, reuse that state directly
- if no bundle data is loaded, show a `Load trust details` button only when trust artifact manifest entries exist or the run has reached a phase where trust artifacts should exist
- when clicked, lazily read:
  - `verification_summary.json`
  - `unsupported_claims.json`
  - `contradictions.json`
  - `source_trust.json`
- once trust details are loaded, the button should disappear rather than turning into a standing refresh action

Empty-state behavior:

- before synthesis or before packaging, show:
  - `Trust signals will appear after synthesis`

Cache behavior:

- if new trust artifact versions arrive through the run stream, invalidate the loaded trust artifact cache for those artifact names
- if the run moves back into `collecting` or `synthesizing` after recollection or resynthesis, clear the derived trust view so stale trust details are not shown as current

This section should complement the generic artifact viewer, not replace it.

## Error Handling

Trust rendering should be defensive:

- missing bundle trust fields should not break the page
- missing trust artifacts should fall back to the empty state
- unexpected payload shape should degrade to a small `Unable to render trust details` message instead of crashing the selected-run view
- trust loading failures should stay local to the trust section and show a small inline error instead of breaking the selected-run detail view

The trust section should never block the rest of the run console from rendering.

## Testing

Extend:

- `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

to cover:

- empty trust state before synthesis
- rendering trust data from a completed bundle
- lazy-loading trust artifacts when no bundle is loaded
- unsupported claims rendering
- contradictions rendering
- source trust rows with provider, trust tier, and snapshot policy

Keep this test coverage page-focused rather than adding a separate trust component test suite unless the page becomes too large to test directly.

## Risks And Tradeoffs

The main risk is shape drift between bundle trust fields and artifact trust fields. The UI should normalize both sources through one small helper path instead of assuming they are identical forever.

Another risk is noise. Contradictions and source trust can become large lists, so v1 should stay compact and avoid turning the trust section into a giant raw JSON dump.

Finally, this slice intentionally stays read-only. That means it improves trust visibility, not trust intervention. If users find contradictions or unsupported claims actionable, the next slice can wire those findings back into checkpoint review or rerun flows.

The last operational risk is stale trust data. Because research runs can loop back through recollection and resynthesis, the UI must treat trust artifacts as versioned outputs and invalidate previously loaded trust details when newer versions appear.
