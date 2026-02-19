# Decision Record: Notes Revision History (Plan 10 Stage 3)

**Date**: 2026-02-18  
**Scope**: Notes versioning UX (`/notes`) and backend revision capabilities

## Decision

Defer full revision-history and diff delivery (revisions table + compare UI) to a later milestone.

For the current increment, keep the minimum viable history context in-product:
- explicit version metadata
- last-saved timestamp metadata
- proactive stale-version warning prior to save

## Rationale

- Existing backend guarantees optimistic locking via `expected_version`; this is sufficient for correctness in MVP.
- Full revision history introduces schema, API, retention, and diff UX complexity that exceeds current plan bandwidth.
- Users receive immediate confidence improvements without blocking core roadmap work.

## Consequences

- Users can detect stale edits and conflicts early, but cannot yet browse historical snapshots or diffs.
- Conflict recovery remains version-based (reload/restore workflows) rather than revision-browser based.

## Follow-up Milestones

1. Add revisions table with immutable snapshots per note update.
2. Add revision list endpoint with pagination and retention policy.
3. Add side-by-side diff UI in notes editor.
4. Add restore-to-revision action with conflict-safe version bumping.
