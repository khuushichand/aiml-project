# Implementation Plan: Characters Gap 06 - Scope Resolution for C-32 (2026-02-19)

## Issue Summary

Stage 10 closure is ambiguous because favorites are implemented while collections/folders scope remains unresolved.

## Stage 1: Product/Engineering Decision Record
**Goal**: Produce explicit ADR-style decision: implement collections/folders now or defer with formal follow-up.
**Success Criteria**:
- Decision owner and date are captured.
- Scope boundary between favorites and folders is explicit.
- Stage 10 status criteria are updated accordingly.
**Tests**:
- Documentation consistency review checklist.
- Acceptance checklist signed by maintainers.
**Status**: Complete
**Update (2026-02-19)**:
- Decision: implement **single-folder assignment** for characters now (no multi-folder in v1).
- Keep favorites behavior as-is; foldering is additive and orthogonal to favorites.
- Reuse existing Notes/Chat folder+keyword primitives as source of folder identity.
- Avoid new character DB schema in v1; use reserved folder token in character metadata/tags.

## Stage 2A: Implement Single-Folder v1 (Selected)
**Goal**: Ship minimum viable folder assignment for characters with lowest migration risk.
**Success Criteria**:
- Single folder can be assigned/cleared for each character from Characters Manager.
- Folder filter is available in Characters list/query flows.
- Reserved folder token is hidden from standard tag UX surfaces.
- Existing favorites/tags/search behavior remains backward compatible.
**Tests**:
- Frontend tests for assign/clear folder and folder filtering.
- Backend integration tests for query/filter behavior using folder token.
- Regression tests ensuring reserved token does not leak into user-visible tag chips.
**Status**: Not Started
**Implementation Contract (v1)**:
- Represent folder membership as one reserved token in character tags.
- Enforce one-folder rule by replacing any prior folder token on save/update.
- Recommended token shape (stable across folder renames): `__tldw_folder_id:<collection_id>`.
- Folder filter maps selected folder ID -> reserved token match.

## Stage 2B: Formal Deferral and Roadmap Hygiene (Not Selected)
**Goal**: Close ambiguity when collections/folders are deferred.
**Success Criteria**:
- N/A (single-folder v1 selected for immediate implementation).
**Tests**:
- N/A.
**Status**: Superseded

## Stage 3: Final Closure Criteria Validation
**Goal**: Ensure C-32 can be marked complete only under explicit, auditable criteria.
**Success Criteria**:
- Completion criteria mapped to Stage 2A single-folder outcomes.
- No conflicting “complete” labels remain in plan set.
- Final status update includes references to merged artifacts.
**Tests**:
- Cross-plan status audit.
- Release note checklist review.
**Status**: Not Started
