# Deep Research Checkpoint Editing Plan

**Date:** 2026-03-07

## Goal

Turn deep research checkpoint handling from approve-only review into structured human-in-the-loop editing for `plan_review`, `sources_review`, and `outline_review`.

## Why This Is Next

The current module already supports:

- checkpoint creation
- checkpoint snapshots and SSE events
- patch-and-approve semantics in the backend
- read-only checkpoint cards in the run console

What is missing is the user-facing ability to steer a run without editing raw artifacts or restarting the session. This is the highest-leverage next improvement because it changes deep research from a passive run monitor into an active research workspace.

## Architecture Direction

Use typed checkpoint patch contracts instead of free-form JSON editing.

The backend should:

- validate checkpoint patches by checkpoint type
- apply patches to canonical artifacts and session state
- record the applied patch in checkpoint resolution metadata

The frontend should:

- render checkpoint-type-specific editors
- submit structured patch payloads
- continue using the same selected-run reducer and replayable SSE flow

## Scope

This workstream covers:

- typed patch models for `plan_review`, `sources_review`, and `outline_review`
- backend validation and application logic
- structured editors in the `/research` console
- resume behavior after edited approval
- tests for patch-and-resume flows

This workstream does not cover:

- arbitrary free-form artifact editing
- collaborative multi-user editing
- version diff viewers for every artifact revision

## Stage 1: Patch Contract Foundation

### Outcome

The system has explicit patch schemas and validation rules for each checkpoint type.

### Deliverables

- typed patch request models in the research API schemas
- checkpoint-type-specific validation in the service layer
- persistent storage of applied patch payloads and summary metadata

### Key Decisions

- `plan_review` patches should edit focus areas, scope, constraints, open questions, and stop criteria
- `sources_review` patches should support pin, drop, prioritize, and “need more like this” semantics
- `outline_review` patches should support section order, add/remove section, rename section, and priority changes

### Success Criteria

- invalid patch keys are rejected deterministically
- the backend can explain why a patch is invalid
- checkpoint approval continues to work unchanged when no patch is supplied

## Stage 2: Plan Review Editing

### Outcome

Users can adjust the research plan before collection resumes.

### Deliverables

- plan editor UI in the run console
- backend patch application that updates `plan.json` and any derived approved-plan artifact
- checkpoint summary updates that reflect edited plan state

### Success Criteria

- a user can change focus areas or constraints and see the next collection slice honor those edits
- resumed collection uses the edited plan rather than the pre-checkpoint draft

## Stage 3: Source Review Editing

### Outcome

Users can curate the collected source set before synthesis resumes.

### Deliverables

- source review UI with pin, drop, and priority actions
- backend patch application against `source_registry.json` and related source-selection summaries
- support for simple source guidance, such as “collect more contradictory evidence” or “keep only pinned sources for synthesis”

### Success Criteria

- dropped sources are excluded from later synthesis
- pinned sources remain prominent in synthesis inputs
- the resumed run records source curation decisions as part of provenance

## Stage 4: Outline Review Editing

### Outcome

Users can shape the structure of the final report before packaging.

### Deliverables

- outline editor UI that operates on sections rather than raw JSON
- backend patch application against `outline_v1.json`
- synthesis/package handoff that uses the approved edited outline

### Success Criteria

- section order and structure changes are preserved into final packaging
- the final report and bundle reflect the approved outline rather than the original machine draft

## Stage 5: UX And Safety Hardening

### Outcome

Checkpoint editing behaves predictably under real session conditions.

### Deliverables

- clear invalid-state messaging for paused, cancelling, or stale checkpoints
- optimistic refresh rules that cooperate with SSE and list polling
- tests for patch replay, resume, and event consistency

### Success Criteria

- editing a checkpoint does not desynchronize the selected-run UI from persisted backend state
- session control rules still block invalid checkpoint approvals
- replayed SSE events preserve the final approved checkpoint state cleanly

## Risks

### Artifact Drift

If patches update UI state but not canonical artifacts, later phases will ignore user edits.

Mitigation:

- treat artifact mutation as the source of truth, not UI reducer state

### Overly Generic Patch Models

If patch payloads stay too free-form, validation and downstream guarantees will erode quickly.

Mitigation:

- use checkpoint-type-specific models and narrow operation sets

### Review UX Bloat

If the first editors try to support every possible research action, the slice will stall.

Mitigation:

- ship only the highest-value structured edits first and keep everything else out of scope

## Exit Condition

This workstream is complete when a checkpointed run can be materially redirected through structured UI editing at each checkpoint stage and then resumed through the same session lifecycle already in production.
