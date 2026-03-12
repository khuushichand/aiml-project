# Deep Research Design

Date: 2026-03-07
Status: Approved

## Summary

Add a reusable deep research backend that can run durable, long-horizon research sessions across both the local corpus and external sources, produce structured research artifacts, and support both autonomous and checkpointed human-in-the-loop execution.

The design is backend-first. It treats deep research as a platform capability that can later power workflows, chat/RAG deep-research mode, watchlists, and Prompt Studio instead of being tied to a single UI surface.

## Product Decisions (Approved)

- Primary shape: backend pipeline first.
- Source scope: local corpus and external sources from day one.
- Canonical output: research package with reusable intermediate artifacts.
- Execution model: long-running, resumable async jobs.
- Human control: support both autonomous and checkpointed runs.

## Goals

- Support multi-stage research sessions that can plan, collect, synthesize, and package outputs.
- Reuse existing repo primitives for Jobs, RAG/search, research adapters, outputs, and artifacts.
- Preserve provenance across search results, fetched sources, evidence notes, claims, and final outputs.
- Allow a run to pause for human review without keeping a worker lease active.
- Provide a stable backend contract that later consumers can reuse.

## Non-Goals

- Building the full collaborative Co-STORM style discourse UI in v1.
- Introducing free-form agent tool use without typed action contracts.
- Making final report prose the primary persisted object.
- Replacing the existing RAG unified endpoint in v1.
- Shipping full-web-page archival for every fetched source.

## Design Review Corrections

The approved design was tightened after review against the current repo:

- Use `research_session` as the canonical domain record, not a custom long-lived job state machine.
- Use core Jobs only for active execution slices; waiting for human input must not consume a leased job.
- Keep Jobs payloads minimal because payloads are size-limited, secret-scanned, and JSON-only.
- Store internal research artifacts behind a manifest store, and use File Artifacts only for exported deliverables.
- Replace boolean-only approval with patchable checkpoints.
- Add explicit budget, storage, and provider guardrails.

## Architecture

### 1. Core Domain

Add a new backend domain under:

- `tldw_Server_API/app/core/Research/`

Primary components:

- `research_service.py`
  - public orchestration surface for create, inspect, pause, resume, cancel, approve, and export
- `planner.py`
  - decomposes a research question into focus areas, subquestions, source policy, and stop criteria
- `broker.py`
  - selects retrieval/fetch actions across local corpus, web search, academic search, and targeted URL fetch
- `collector.py`
  - normalizes raw source results into source records and evidence notes
- `synthesizer.py`
  - generates outline, report sections, concise answer, bibliography, and confidence metadata
- `checkpoint_service.py`
  - manages human-review checkpoints and patch application
- `artifact_store.py`
  - persists and versions internal research artifacts behind a session manifest
- `limits.py`
  - enforces search, fetch, runtime, token, and storage budgets

### 2. Existing Systems To Reuse

- Core Jobs for execution slices, retries, leases, queue controls, SSE/event streaming, and quotas.
- Existing RAG retrieval and the current iterative search loop from `rag_service/research_agent.py` as implementation seed material.
- Research workflow adapters for academic search and bibliography operations.
- Existing outputs and file-artifact export paths for final downloadable deliverables only.

### 3. Canonical Identity Model

There are two separate concepts:

- `research_session`
  - the durable domain object
- `job`
  - an execution slice for one active phase of a session

The session owns business state. Jobs only execute work.

This avoids trying to force deep-research checkpoint states such as `awaiting_plan_review` into the Jobs state machine.

## Session Lifecycle

### Session Phases

The `research_session` phase model:

1. `drafting_plan`
2. `awaiting_plan_review`
3. `collecting`
4. `awaiting_source_review`
5. `synthesizing`
6. `awaiting_outline_review`
7. `packaging`
8. `completed`
9. `failed`
10. `cancelled`

Only phases with active execution enqueue a Job.

### Checkpoint Model

Checkpoint types:

- `plan_review`
- `sources_review`
- `outline_review`

Each checkpoint stores:

- `checkpoint_id`
- `session_id`
- `checkpoint_type`
- `status`
- `proposed_payload`
- `user_patch_payload`
- `resume_policy`
- `created_at`
- `resolved_at`

Supported user actions:

- approve as-is
- patch and approve
- reject and regenerate
- cancel session

## Execution Model

### Why Jobs

Deep research is user-facing, long-running, and needs retries, queue controls, quotas, and durable status. That matches the repo’s Jobs guidance better than Scheduler.

### Job Strategy

Each executable phase enqueues a scoped job with a minimal payload:

```json
{
  "session_id": "rs_123",
  "phase": "collecting",
  "checkpoint_id": "cp_456",
  "policy_version": 1
}
```

The worker:

- loads session state
- loads the latest committed artifacts for the phase
- executes one bounded phase slice
- writes new artifacts
- advances the session phase or opens a checkpoint

### Resumability

Resumability happens at committed artifact boundaries, not arbitrary in-memory points.

Each phase must define:

- input artifacts
- output artifacts
- idempotency key
- side-effect policy

Examples:

- planning idempotency key: normalized question + scope policy + constraints hash
- source record dedupe key: canonical URL or provider-native source ID + content hash
- synthesis artifact version key: session ID + outline version + evidence snapshot version

## Retrieval And Research Behavior

### 1. Planning Stage

The planner creates:

- normalized brief
- 3-7 focus areas
- subquestions
- source policy
- stop criteria
- initial budget allocation

Borrow from STORM:

- perspective-guided decomposition

Do not copy in v1:

- full simulated multi-agent conversations
- dynamic mind map collaboration UI

### 2. Collection Stage

The broker chooses typed actions:

- local corpus retrieval
- external web search
- academic search
- targeted URL fetch or scrape

The broker tracks explicit information gaps:

- missing background
- missing primary source
- missing contradiction
- missing recency confirmation
- missing local-corpus grounding

### 3. Distillation Stage

Convert raw retrieval/fetch results into normalized evidence:

- source records
- evidence notes
- quoted excerpts
- claim candidates
- contradiction flags
- trust and provenance metadata

### 4. Synthesis Stage

Generate:

- concise answer
- outline
- report sections
- bibliography
- unresolved questions
- confidence notes

The synthesizer should consume distilled evidence, not raw search results.

### 5. Verification Stage

Before packaging:

- every major claim must have citation bindings
- unsupported sections are flagged
- weak-source-only sections are flagged
- required local-grounding tasks are checked for local evidence coverage

## Source Policy

Supported session source policies:

- `local_first`
- `external_first`
- `balanced`
- `local_only`
- `external_only`

This policy affects broker choice, scoring, and stop criteria.

Default for v1: `balanced`, unless the user explicitly requests otherwise.

## Artifact Model

### Internal Artifacts

Persist internal artifacts behind a manifest store keyed by session ID and artifact version.

Core artifacts:

- `brief.json`
- `plan.json`
- `search_log.jsonl`
- `source_registry.json`
- `evidence_notes.jsonl`
- `outline_vN.json`
- `report_vN.md`
- `final_package.json`

Manifest metadata should include:

- artifact name
- version
- content type
- byte size
- checksum
- created_at
- producing phase
- producing job ID

### Exported Deliverables

User-facing exports such as markdown, HTML, PDF, or packaged ZIP outputs should go through the existing file-artifacts/export path, not the internal artifact store.

### Snapshot Policy

Default external-source persistence:

- canonical URL
- provider/source ID
- title and metadata
- fetched timestamp
- excerpt(s)
- normalized hash

Full source snapshots should be limited to:

- user-owned local corpus content
- explicitly ingested documents
- allowlisted providers or explicit export mode

## Data Model

Start with the smallest useful schema:

- `research_sessions`
- `research_checkpoints`
- `research_source_index`
- `research_artifact_manifest`

Avoid splitting claims into standalone DB tables in v1 unless the existing claims subsystem can be reused cleanly.

Suggested `research_sessions` fields:

- `id`
- `owner_user_id`
- `status`
- `phase`
- `query`
- `normalized_brief_json`
- `source_policy`
- `autonomy_mode`
- `limits_json`
- `latest_checkpoint_id`
- `current_plan_version`
- `current_outline_version`
- `result_artifact_name`
- `created_at`
- `updated_at`
- `completed_at`

## API Contract

Add a new API surface, likely:

- `POST /api/v1/research/runs`
- `GET /api/v1/research/runs/{id}`
- `POST /api/v1/research/runs/{id}/pause`
- `POST /api/v1/research/runs/{id}/resume`
- `POST /api/v1/research/runs/{id}/cancel`
- `GET /api/v1/research/runs/{id}/checkpoints/{checkpoint_id}`
- `POST /api/v1/research/runs/{id}/checkpoints/{checkpoint_id}/approve`
- `POST /api/v1/research/runs/{id}/checkpoints/{checkpoint_id}/patch-and-approve`
- `POST /api/v1/research/runs/{id}/checkpoints/{checkpoint_id}/reject`
- `GET /api/v1/research/runs/{id}/package`
- `GET /api/v1/research/runs/{id}/artifacts/{artifact_name}`

`research_runs` is the user-facing route name for continuity, but the backend domain model should still use `research_session`.

## Progress And Events

Do not invent a parallel streaming system.

Reuse:

- Jobs progress fields
- Jobs event outbox
- Jobs SSE/event streaming endpoints

Session status endpoints should return domain-specific state. Live progress should piggyback on the existing Jobs event stream.

## Limits And Guardrails

Define explicit per-session limits:

- max searches
- max fetched docs
- max runtime
- max internal artifact bytes
- max tokens
- max external provider spend
- max synthesis retries

Guardrails:

- no free-form tool calls inside the core loop
- no final prose output without citation bindings and source registry
- no secret-bearing provider config persisted into Jobs payloads
- no unbounded source snapshotting

## Error Handling

- provider/search failures reduce coverage and log evidence gaps; they should not immediately fail the session
- repeated parse or synthesis failures consume retry budget and then fail the phase
- required checkpoints must block forward progress until resolved
- cancelled sessions must stop enqueueing new jobs and mark open checkpoints terminal

## Testing Strategy

### Unit

- planner decomposition
- source-policy routing
- gap tracking
- source dedupe
- checkpoint patch merge behavior
- citation binding validation
- stop-condition evaluation
- limits enforcement

### Integration

- API create, inspect, patch, approve, resume, cancel
- Jobs worker lifecycle across planning, collection, and synthesis
- artifact manifest creation and lookup
- file-artifact export of final deliverables

### Property / Invariant

- every packaged claim reference resolves to a source record
- every artifact manifest entry points to exactly one produced artifact
- checkpoint resolution is idempotent
- re-running the same phase idempotently does not duplicate source records

### E2E

- hybrid local + mocked web research task
- checkpointed session with user patch
- autonomous session with bounded completion
- failure and resume path

## Rollout Strategy

Phase 1:

- backend domain objects
- planning and collection
- internal artifact store
- checkpoint API

Phase 2:

- synthesis and export
- workflow integration
- chat deep-research integration

Phase 3:

- watchlists and Prompt Studio integration
- richer evaluation metrics
- optional collaborative features

## Acceptance Criteria

- A user can create a deep-research run that uses both local and external sources.
- The run can pause at a checkpoint without an active leased job.
- The run can resume from committed artifacts instead of restarting from scratch.
- The final exported package contains answer, report, citations, source inventory, and unresolved questions.
- Internal artifacts are persisted via a manifest store, while exported deliverables use the existing file-artifacts path.
- Progress and status are observable through the existing Jobs infrastructure.

## Reference Patterns

- STORM: outline-first research and writing split
- Automated-AI-Web-Researcher-Ollama: prioritized focus areas, long-running trail, operator controls
- ThinkDepth Deep Research: stage-aware information-gap closing before final prose optimization
- Onyx: deep research as reusable platform capability rather than a one-off page
