# Deep Research Module Roadmap

**Date:** 2026-03-07

## Goal

Define the next major development program for the deep research module now that the backend pipeline, live run console, replayable SSE, and core discovery surfaces are in place.

## Current Baseline

The module already provides:

- Jobs-backed research sessions with planning, collecting, synthesizing, and packaging
- provider-backed collection and synthesis with durable artifacts
- run controls and replayable per-run SSE
- a dedicated `/research` console for creating, monitoring, and exporting runs
- approve-only checkpoint handling

The next phase should turn this from a strong execution engine into a trustworthy, steerable, and broadly integrated product capability.

## Program Order

### 1. Editable Checkpoint Review

This is the highest-priority next workstream.

Reason:

- the core engine is already usable, but users cannot meaningfully steer a run once it starts
- checkpoint editing upgrades deep research from a monitor to a collaborative workspace
- typed checkpoint editing creates better artifacts and user intent signals for later trust and integration work

### 2. Research Quality And Trust Hardening

This is the second workstream.

Reason:

- once users can steer runs, the next bottleneck is trust in the outputs
- stronger citation verification, contradiction handling, and evaluation fixtures make the module reliable enough for broader rollout
- this work should land before deep research becomes a first-class mode in chat and workflows

### 3. Product Integration

This is the third workstream.

Reason:

- the module should ultimately become a shared platform capability, not a standalone page
- integration is most valuable after checkpoint editing and trust artifacts stabilize the launch and output contracts

## Program Milestones

### Milestone A: Collaborative Review Foundation

Outcome:

- users can edit `plan_review`, `sources_review`, and `outline_review` checkpoints
- the system stores structured patch history and resumes execution from edited state

Success gate:

- a checkpointed research run can be materially changed by a user without manual artifact editing

### Milestone B: Trustworthy Research Output

Outcome:

- major claims are explicitly verified against collected evidence
- contradictions and unsupported claims are surfaced
- source trust metadata and snapshot policy are recorded
- evaluation fixtures can detect regressions in claim coverage and citation correctness

Success gate:

- deep research reports are auditable and regressions in evidence quality are measurable

### Milestone C: Cross-Surface Research Capability

Outcome:

- chat and workflow surfaces can launch, monitor, and consume deep research sessions through the same backend model

Success gate:

- users can start a deep research run outside the dedicated page and still land on the same session, bundle, and artifact model

## Recommended Sequencing

### Track 1: Checkpoint Editing

Start immediately.

Primary dependencies:

- existing checkpoint creation and approval flow in the research service
- current console checkpoint display

### Track 2: Trust Hardening

Start after checkpoint patch contracts are stable, but some foundational pieces can begin in parallel with late-stage checkpoint UI work.

Parallelizable early work:

- evaluation fixture scaffolding
- citation verification artifact design

### Track 3: Product Integration

Start after:

- checkpoint editing makes session steering real
- trust artifacts define what downstream surfaces should show

Safe early prep work:

- define shared launch contracts
- define minimal bundle-consumption rules for chat and workflows

## Cross-Cutting Requirements

All three workstreams should preserve these constraints:

- keep `research_session` as the canonical domain object
- keep Jobs as the execution mechanism for active phases
- preserve typed artifacts and replayable event semantics
- prefer additive changes over replacing the current run console or service contracts
- keep UI surfaces thin over the same session, artifact, and bundle model

## Risks To Manage Across The Program

### Contract Drift

If checkpoint patches, synthesis outputs, and downstream consumers each invent their own shapes, the module will fragment quickly.

Mitigation:

- define typed patch contracts and typed verification artifacts before wider integration

### UI Surface Fragmentation

If chat, workflows, and the dedicated console each implement separate research state models, the product will become inconsistent.

Mitigation:

- reuse the same launch, status, checkpoint, and bundle contracts everywhere

### Trust Gaps

If integration expands faster than verification hardening, low-confidence or weakly cited results will be amplified into more surfaces.

Mitigation:

- treat trust hardening as a release gate for deeper product integration

## Deliverables

This roadmap should be executed as three follow-on workstream plans:

- `2026-03-07-deep-research-checkpoint-editing-plan.md`
- `2026-03-07-deep-research-quality-trust-plan.md`
- `2026-03-07-deep-research-product-integration-plan.md`

## Exit Condition

The program is complete when deep research is:

- collaboratively steerable during execution
- auditable and measurable for evidence quality
- launchable and consumable from the main product surfaces beyond the dedicated run console
