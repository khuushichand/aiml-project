# Persona Garden Phase 4 Adaptive Retrieval Design

Date: 2026-03-08
Status: Approved

## Summary

Design a multi-phase adaptive retrieval layer for Persona Garden inspired by retrieval-conditioned roleplay prompting, without collapsing personas into either ordinary memory or oversized system prompts.

The approved direction is:

- add a first-class persona-owned exemplar bank
- keep exemplars separate from persona profile, state docs, memory, and policy
- retrieve a small, bounded set of exemplars per turn
- use multiple phases so manual curation lands before automated ingestion and evaluation

## Investigated Context

- Persona profiles are still relatively thin and do not yet include a rich example bank:
  - `tldw_Server_API/app/api/v1/schemas/persona.py`
- Persona Garden already has strong separation between:
  - profile/config
  - live session controls
  - state docs
  - policy rules
  - scope rules
- Persona state docs are currently the durable self-model:
  - `soul_md`
  - `identity_md`
  - `heartbeat_md`
- Persona memory already has its own read/write behavior and storage logic:
  - `tldw_Server_API/app/core/Persona/memory_integration.py`
- Ordinary persona chat now persists normalized assistant identity, but prompt assembly is still largely character-shaped in key paths:
  - `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`

## Problem Statement

The current persona model can store high-level identity and state, but it does not yet have a dedicated place to store curated voice/style/boundary demonstrations that can be retrieved at inference time.

That creates two problems:

1. if we want stronger in-character behavior, we are pushed toward overloading `system_prompt` or state docs
2. if we want hostile-prompt resistance, we currently lack a clean persona-owned retrieval layer for scenario-conditioned boundary examples

The design needs to add retrieval-style role conditioning without:

- turning state docs into prompt sludge
- writing exemplars into normal persona memory
- recreating a live dependency on the source character
- coupling ordinary persona chat to Persona Garden live-session transport

## Goals

- Add a persona-owned exemplar bank for role-conditioning snippets.
- Keep exemplars separate from memory and state docs.
- Support bounded per-turn retrieval for persona-backed chat.
- Expose exemplar curation in Persona Garden as a first-class configuration surface.
- Roll the feature out across multiple phases so manual curation lands before automated ingestion and heavier evaluation.

## Non-Goals

- Do not turn persona exemplars into normal memory entries.
- Do not store exemplar text inside `soul`, `identity`, or `heartbeat` docs.
- Do not require personas to retain a live dependency on the originating character.
- Do not optimize solely for textual imitation or catchphrase density.
- Do not allow exemplars to override policy, scope, or real system capability.

## Approved Approach

Use a phased adaptive retrieval design centered on a new `Persona Exemplars` layer.

This adds a fourth persona-conditioning layer:

- `Persona Profile`
- `Persona State Docs`
- `Persona Memory`
- `Persona Exemplars`

Policy and scope remain orthogonal control layers that constrain all of the above.

## Updated Persona Architecture

### Persona Profile

Owns:

- persona identity
- mode/config
- high-level configuration

### Persona State Docs

Own:

- enduring self-model
- stable identity/state framing
- long-lived persona worldview and role framing

Current fields remain:

- `soul_md`
- `identity_md`
- `heartbeat_md`

### Persona Memory

Owns:

- episodic/semantic memory
- summaries and retrieval from prior interaction history
- optional durable writeback behavior

Exemplars must not be written through this path.

### Persona Exemplars

Own:

- role-conditioning snippets
- style demonstrations
- scenario-conditioned reactions
- policy-aligned boundary examples
- tool behavior examples where appropriate

They are retrieved at inference time, not treated as conversation history.

## Exemplar Data Model

Add a persona-owned exemplar entity with the following shape:

- `id`
- `persona_id`
- `user_id`
- `kind`
- `content`
- `tone`
- `scenario_tags`
- `capability_tags`
- `priority`
- `enabled`
- `source_type`
- `source_ref`
- `notes`
- timestamps/versioning metadata

### Tag Format

Use normalized free-form strings for:

- `tone`
- `scenario_tags`
- `capability_tags`

Normalization rules:

- trim whitespace
- lowercase
- collapse duplicates
- reject empty values after normalization

This keeps the model flexible without forcing an enum migration every time prompt-taxonomy language evolves.

### Recommended `kind` values

- `style`
- `catchphrase`
- `boundary`
- `scenario_demo`
- `tool_behavior`

### Recommended `source_type` values

- `manual`
- `transcript_import`
- `character_seed`
- `generated_candidate`

### Exemplar Ownership Rule

If an exemplar is created from:

- a source character
- a transcript
- imported reference material

it becomes persona-owned immediately. Provenance may be preserved, but live dependence must not.

## Retrieval And Prompt Assembly

### Phase 1 Retrieval

Use deterministic matching only:

- active persona only
- `enabled=true` only
- prefer exact `scenario_tags`
- then `tone`
- then `kind` and `priority`

Inject a small bounded set:

- up to 1 `boundary` exemplar
- up to 2 `style` / `scenario_demo` exemplars
- up to 1 `catchphrase` or `tool_behavior` exemplar

### Phase 2 Retrieval

Add lightweight per-turn classification:

- scenario
- tone/risk
- capability intent

Recommended scenario labels:

- `small_talk`
- `hostile_user`
- `meta_prompt`
- `tool_request`
- `knowledge_question`
- `bio_question`
- `coding_request`

Recommended risk labels:

- `neutral`
- `heated`
- `manipulative`
- `jailbreak_like`

Rank exemplars by:

- scenario match
- boundary relevance
- tone match
- capability tag match
- priority
- token budget cost

### Capability Truth Source

`capability_tags` are advisory retrieval hints, not the source of truth.

Real capability truth must come from live runtime constraints such as:

- persona policy rules
- tool confirmation requirements
- actual configured/default tool availability
- any assistant/runtime capability checks already in force

If an exemplar's `capability_tags` disagree with runtime truth, runtime truth wins and the exemplar is dropped or ignored.

### Prompt Assembly Rule

Exemplars are their own prompt section.

Recommended order:

1. persona/system layer
2. persona state-doc context
3. memory/summary context
4. persona exemplars
5. current conversation messages

### Budgeting And Conflict Rules

Extend prompt budgeting to include:

- `persona_exemplars`
- `persona_boundary`

Rules:

- policy wins over exemplars
- scope wins over exemplars
- real current capability wins over exemplars
- conflicting exemplars are dropped rather than partially merged

### Debug Visibility

Prompt preview/debug should show:

- selected exemplars
- why they matched
- which were dropped
- whether the drop reason was budget, conflict, or rank

## Persona Garden UI

Add a new Persona Garden section:

- `Voice & Examples`

This section is distinct from `State Docs`.

### Phase 1 UI

Manual curation only:

- exemplar list
- create/edit/archive
- filter by `kind`, `tone`, `scenario tag`, `enabled`
- duplicate exemplar action
- prompt preview of exemplar injection

Authoring form fields:

- `Kind`
- `Content`
- `Tone`
- `Scenario tags`
- `Capability tags`
- `Priority`
- `Enabled`
- `Notes`
- provenance readout if available

### Phase 2 UI

Expose runtime visibility:

- selected exemplars for a given turn
- skipped exemplars
- skip reasons

### Phase 3 UI

Add assisted ingestion:

- import transcript/source text
- extract candidate exemplars
- review queue
- approve/edit/reject candidates

## Safety Model

The right adaptation of the paper is not "stay in character at all costs."

The correct rule for this repo is:

`stay in character while remaining policy- and capability-truthful`

That means:

- exemplars cannot claim unavailable capabilities
- exemplars cannot suppress real allowed capabilities unnecessarily
- boundary exemplars must align with policy and tool confirmation requirements
- retrieval should strengthen character consistency, not undermine system truthfulness

### Boundary Exemplars

Boundary exemplars are explicit records, not hidden in general style examples.

Good pattern:

- characterful refusal or redirection that remains truthful about what the persona/system can do

Bad pattern:

- false claims like "I am not an LLM" when the runtime clearly can use tools or perform assistant tasks

## Evaluation Strategy

Phase 4 should add persona-focused evaluation in two buckets.

### In-Character Stability

- neutral Q&A
- emotionally varied prompts
- meta-prompt attempts
- prompt-reveal attempts
- capability-bait prompts

### Boundary Adherence

- policy-sensitive requests
- tool confirmation requests
- capability mismatch prompts
- adversarial override prompts

### Metrics

Use a blended evaluation set:

- human or LLM-judge preference for in-character quality
- boundary adherence pass/fail
- capability-truthfulness pass/fail
- exemplar utilization diagnostics for debugging only

Token-overlap style metrics may be useful as internal diagnostics, but should not become the primary product KPI because they can reward mimicry over good behavior.

## Rollout Plan

### Phase 1: Exemplar Foundation

- add exemplar data model
- add Persona Garden `Voice & Examples`
- add manual CRUD
- add deterministic retrieval
- land retrieval through a shared persona prompt-assembly seam that ordinary persona chat uses first

### Phase 2: Adaptive Retrieval

- add turn classification
- rank exemplars by scenario/tone/boundary relevance
- add prompt-budget and conflict handling
- add prompt preview/debug visibility
- wire the same shared retrieval layer into the live Persona Garden runtime once the backend assembly seam is shared

### Phase 3: Assisted Ingestion

- import transcript/source text
- extract candidate exemplars
- add review/approval flow
- preserve provenance while keeping persona ownership

### Phase 4: Evaluation And Tuning

- add hostile-prompt evaluation suite
- add in-character stability evaluation
- add boundary-adherence evaluation
- tune retrieval heuristics and defaults

## Recommended Initial Constraint

Start with:

- persona-backed ordinary chat
- Persona Garden configuration surfaces
- prompt preview/debug integration

The live Persona Garden websocket path should consume the same retrieval layer once the backend assembly seam is shared. Do not duplicate retrieval logic separately for ordinary chat and live persona.
