# Decision Record: World Book Entry Versioning

**Date**: 2026-02-18  
**Status**: Accepted  
**Scope**: World Books entry authoring and recovery workflow (`Manager.tsx`, import/export UX, user guidance)

## Context

The current world-book system tracks versioning and optimistic concurrency at the world-book level, but does not maintain a full revision timeline for individual entries.

Adding entry-level version history now would require:
- schema additions for entry revisions and diff storage
- revision-aware APIs and restore semantics
- significantly larger testing surface for merge/conflict behavior

This complexity is high relative to near-term user value compared with improving authoring diagnostics and reliability features.

## Decision

Defer full entry-level version history for now.

Use world-book export snapshots as the primary backup and rollback mechanism:
- encourage periodic exports during active editing sessions
- use timestamped exports before bulk operations or major rewrites
- recover by importing from a known-good snapshot

## Rationale

- Keeps implementation scope aligned with immediate authoring quality improvements.
- Uses existing, stable import/export paths that already preserve full entry payloads.
- Avoids introducing partially implemented revision UX that could create false confidence.

## Consequences

### Positive
- Faster delivery of high-impact authoring features.
- Lower operational risk than introducing incomplete revision semantics.
- Clear recovery path available today using exports.

### Negative
- No per-entry timeline, diff view, or one-click revert.
- Recovery is coarse-grained (book snapshot) rather than fine-grained (single entry revision).

## Revisit Criteria

Re-open this decision when any of the following are true:
- frequent user reports of accidental entry overwrite without easy recovery
- collaborative editing usage increases and requires auditability
- relationship/dependency tooling requires historical context per entry

