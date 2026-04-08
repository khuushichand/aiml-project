# Study Suggestions Grounding And Normalization V2 Design

Date: 2026-04-08
Status: Proposed
Owner: Codex brainstorming session

## Summary

Build a deterministic `grounding + normalization v2` upgrade for the existing `StudySuggestions` engine.

This phase is intentionally narrow:

- improve topic grounding quality for quiz attempts and flashcard review sessions
- introduce a stable `topic_key` model without breaking existing frozen snapshots
- refactor topic extraction ownership so adapters emit structured evidence and the pipeline owns canonicalization
- keep snapshots permission-safe and backward-compatible
- prepare the engine for later analytics and cross-service expansion without introducing LLM dependency in this phase

This is the first follow-up phase after the merged quiz/flashcard study-suggestions MVP. It should improve recommendation quality inside the existing study loop before adding analytics or expanding to other services.

## Problem

The current engine works, but the quality ceiling is limited by four structural issues:

1. Topic identity is too label-driven.
2. Extraction logic is concentrated in snapshot assembly rather than clearly split between adapters and the topic pipeline.
3. Flashcard suggestions currently do not feed rich enough provenance or performance signals into the ranking path.
4. The current system has no explicit normalization-version contract, which makes future analytics and canonicalization upgrades risky.

The result is a v1 that can produce useful recommendations, but is still vulnerable to:

- duplicate or drifting topic labels
- unstable semantics when labels are renamed or refreshed
- weak flashcard grounding quality
- difficulty measuring whether the same topic recurs across sessions

## Goals

- Add stable semantic topic identity through `topic_key`.
- Preserve separate snapshot-local topic identity for UI editing and reopening history.
- Move extraction boundaries toward:
  - adapters produce structured evidence inputs
  - pipeline performs normalization, canonicalization, merge, and ranking
  - snapshot service orchestrates and serializes
- Improve flashcard suggestion quality by feeding real provenance and performance signals into the pipeline.
- Keep snapshot payloads permission-safe.
- Maintain backward compatibility for existing snapshots and existing follow-up action flows.
- Introduce `normalization_version` so canonicalization rules can evolve safely.
- Prepare phase 2 analytics to measure user interaction by stable topic identity.

## Non-Goals

- Add LLM-based topic extraction or enrichment.
- Add embeddings-based topic similarity.
- Introduce a persistent global topic catalog table in this phase.
- Expand the suggestion engine to notes, chat, research, or presentations yet.
- Redesign the study-suggestions UI beyond minor evidence/copy improvements.
- Replace the existing suggestion snapshot model or action model from scratch.

## Current State

### Current Topic Pipeline

The current topic pipeline is intentionally minimal and label-driven.

See:

- `tldw_Server_API/app/core/StudySuggestions/topic_pipeline.py`
- `tldw_Server_API/app/core/StudySuggestions/types.py`

Notable properties today:

- canonicalization is based on a small inline synonym map
- identity is effectively the canonical label string
- there is no stable `topic_key`
- there is no `normalization_version`
- evidence classes are limited to `grounded`, `weakly_grounded`, and `derived`

### Current Snapshot Assembly

Topic extraction logic currently lives largely in snapshot assembly.

See:

- `tldw_Server_API/app/core/StudySuggestions/snapshot_service.py`

Notable properties today:

- quiz extraction, label collection, weakness/adjacency assignment, and topic payload construction happen directly inside the snapshot path
- flashcard snapshots are assembled from shallow derived labels
- snapshot topic rows use a snapshot-local `"id"` such as `topic-1`

### Current Follow-Up Action Model

Follow-up actions currently resolve selected topics from the frozen snapshot payload using snapshot-local topic ids and labels.

See:

- `tldw_Server_API/app/core/StudySuggestions/actions.py`

Notable properties today:

- selection fingerprints are label-based
- renamed topics change the labels used downstream
- there is no stable semantic topic identifier in fingerprints or future analytics

### Current UI Contract

The UI currently expects topic rows with:

- `id`
- `display_label`
- `type`
- `status`
- `selected`

See:

- `apps/packages/ui/src/components/StudySuggestions/StudySuggestionsPanel.tsx`

This contract must continue to work for old snapshots after phase 1 lands.

## Design Principles

### 1. Dual Identity, Not Single Identity

Each topic must have two separate identities:

- `snapshot_topic_id`
  - frozen row identity local to one snapshot
  - used by the UI for selection, editing, and reset behavior
- `topic_key`
  - stable semantic identity derived from deterministic normalization
  - used for dedupe, analytics, and future cross-service reuse

`display_label` remains user-facing presentation text and may change without changing `topic_key`.

### 2. Version Canonicalization

Every computed topic row must carry a `normalization_version`.

This version identifies the alias dictionary and canonicalization rules that produced the row. It prevents future upgrades from silently changing semantic identity without traceability.

### 3. Adapters Produce Evidence, Pipeline Produces Topics

Phase 1 should clarify ownership:

- `quiz_adapter.py`
  - emits structured quiz evidence inputs
- `flashcard_adapter.py`
  - emits structured flashcard evidence inputs
- `topic_pipeline.py`
  - cleans labels
  - resolves aliases
  - generates `topic_key`
  - merges evidence
  - assigns evidence classes
  - ranks topics
- `snapshot_service.py`
  - loads anchor data
  - invokes adapters and pipeline
  - serializes permission-safe payloads

This removes the current ambiguity where extraction and ranking logic are mixed into snapshot assembly.

### 4. Permission-Safe Frozen Snapshots

Frozen snapshots must remain lightweight and permission-safe.

Allowed in snapshot payload:

- topic ids
- topic keys
- canonical and display labels
- evidence class
- rank reason
- counts
- light source refs
- safe evidence reasons

Not allowed in snapshot payload:

- source excerpts
- question text
- source summaries
- note body fragments
- media transcript content

Detailed evidence remains live-resolved when the snapshot is reopened.

### 5. Compatibility First

Phase 1 must not break:

- reopened legacy snapshots
- current UI rendering
- follow-up action flows for old snapshots
- duplicate detection for pre-phase-1 outputs

Compatibility behavior must be explicit rather than incidental.

## Proposed Data Model

### Topic Payload V2

Each topic row in a new snapshot payload should carry:

- `id`
  - snapshot-local identifier, for example `topic-1`
- `topic_key`
  - stable deterministic semantic key
- `normalization_version`
  - deterministic canonicalization version, starting with something like `norm-v2`
- `canonical_label`
  - canonical normalized label
- `display_label`
  - user-facing label
- `type`
  - evidence class
- `status`
  - rank reason
- `selected`
  - default selection state
- `source_count`
  - number of lightweight source refs contributing to this topic
- `evidence_reasons`
  - compact structured reasons such as `["missed_question", "source_citation"]`
- optional `source_type`
- optional `source_id`

### Identity Rules

- `id` must remain snapshot-local and stable for the lifetime of that snapshot.
- `topic_key` must be stable across snapshots as long as the canonicalization rules and source semantics remain unchanged.
- `display_label` may change due to user edits or improved formatting without changing `topic_key`.

## Proposed Backend Changes

### `types.py`

Extend topic-related types to include:

- `topic_key`
- `normalization_version`
- `source_count`
- `evidence_reasons`

Add an explicit `exploratory` evidence class if needed by the serialized payload contract. If the code keeps `exploratory` only as a rank reason, the spec should still require a consistent mapping from rank/evidence to UI copy.

### `topic_pipeline.py`

Refactor the pipeline into explicit stages:

1. label cleaning
2. token and phrase normalization
3. alias resolution
4. canonical label selection
5. `topic_key` generation
6. evidence merge across sources
7. ranking

New deterministic inputs:

- alias dictionary module
- phrase-level replacements
- safe singular/plural collapsing where supported
- stopword trimming
- domain synonym groups

New deterministic outputs:

- canonical label
- topic key
- normalization version
- merged evidence metadata

### `quiz_adapter.py`

Refactor quiz evidence extraction out of `snapshot_service.py` and into the adapter.

The adapter should emit structured inputs such as:

- source-backed labels from citations
- tag-backed labels from questions or quiz metadata
- weakness evidence from incorrect answers
- adjacency evidence from correct/covered related topics
- lightweight source refs associated with evidence

The adapter should prefer:

1. citation/source labels
2. structured tags
3. deterministic derived labels only when needed

### `flashcard_adapter.py`

This phase must explicitly improve flashcard evidence quality before expecting better ranking.

The adapter should consume or derive:

- real `cards_reviewed`
- real `correct_count` or similar performance signals
- session source bundle when available
- deck provenance and study-pack lineage
- card-level source metadata when recoverable
- tag-filter context

The adapter should distinguish:

- genuinely grounded sessions
- weakly grounded tag/deck sessions
- exploratory/manual sessions

If provenance is thin, the adapter should mark the session exploratory rather than over-claiming adjacency.

### `snapshot_service.py`

Refactor snapshot service responsibilities to:

- load raw anchor data
- request structured evidence from the appropriate adapter
- invoke the topic pipeline
- serialize the V2 topic rows

The snapshot service should no longer own the majority of quiz extraction logic directly.

### `actions.py`

Update topic selection and fingerprint resolution rules:

- prefer `topic_key` when present
- fall back to legacy label normalization when it is absent
- preserve snapshot-local `id` for selection targeting

New follow-up fingerprints should include:

- `snapshot_id`
- `target_service`
- `target_type`
- selected `topic_key`s when present
- `action_kind`
- `generator_version`
- `normalization_version`

For legacy snapshots:

- continue using normalized labels as the fallback fingerprint input

## UI Impact

This phase should keep the UI mostly stable.

Expected UI changes:

- compatibility mapper for topic rows that may or may not contain `topic_key`
- optional copy/badge improvements for stronger provenance explanation
- no major workflow changes

The `StudySuggestionsPanel` should continue to work with:

- old snapshots that only have `id` and `display_label`
- new snapshots that also include `topic_key`, `canonical_label`, and richer evidence metadata

## Backward Compatibility

### Legacy Snapshots

Old snapshots should continue to render without forced refresh.

Compatibility rules:

- if `topic_key` is missing, UI falls back to the old contract
- if `normalization_version` is missing, treat it as legacy
- follow-up actions should resolve selected topics from `id` and label as they do today

### Legacy Fingerprints

Do not rewrite old generation links or old fingerprints.

Instead:

- existing links remain valid
- new snapshots use the new fingerprint composition
- duplicate detection continues to work within each generation style

### Refresh Behavior

Refreshing an old snapshot may produce a new child snapshot with the V2 payload shape.

This is acceptable and desirable, as long as:

- the original snapshot remains unchanged
- the new snapshot explicitly carries the new normalization version

## Testing Strategy

Add or extend tests for:

- deterministic `topic_key` stability under raw-label drift
- alias collapse across source labels, tags, and derived labels
- `normalization_version` propagation into snapshot payloads and fingerprints
- legacy snapshot compatibility in follow-up action resolution
- flashcard provenance downgrade behavior
- quiz weakness vs adjacency ordering
- snapshot payload safety guarantees
- UI compatibility with mixed old/new snapshot shapes

## Rollout Plan

Phase 1 should land in this order:

1. introduce new topic types and compatibility-safe payload schema
2. refactor adapters to emit structured evidence
3. refactor topic pipeline to emit `topic_key` and `normalization_version`
4. upgrade snapshot serialization
5. upgrade action fingerprinting with legacy fallback
6. add UI compatibility handling
7. add targeted tests

This order keeps the system working at every step and avoids breaking frozen history.

## Success Criteria

Phase 1 is successful when:

- repeated semantically equivalent labels map to the same `topic_key`
- old snapshots still render and generate follow-up artifacts successfully
- new snapshots carry richer, stable topic identity
- flashcard suggestions show noticeably better grounding behavior
- future analytics can key on `topic_key` instead of only display labels

## Follow-On Phases

### Phase 2

Add feedback and analytics around:

- selected topics
- ignored topics
- generated vs opened-existing follow-ups
- downstream completion outcomes

Phase 2 should use `topic_key` as the primary analytic identity.

### Phase 3

Generalize the suggestion engine for other internal services such as:

- notes
- chat
- research
- presentations

That later expansion should reuse:

- the adapter boundary
- `topic_key`
- `normalization_version`
- permission-safe frozen snapshots

