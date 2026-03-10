# Persona Garden Live Runtime Exemplars Design

## Goal

Bring the live Persona Garden websocket/session runtime up to parity with the shipped ordinary persona-backed chat flow by reusing the shared persona exemplar retrieval and prompt-assembly seam during live `user_message` handling.

This follow-up also refreshes the stale Persona module README so it matches the current persisted persona architecture.

## Scope

This change applies only to the live Persona Garden websocket/session runtime and its supporting docs.

In scope:

- classify incoming live websocket `user_message` turns
- retrieve enabled persona exemplars for the active persona
- reuse the shared exemplar prompt-assembly helper already used by ordinary persona-backed chat
- feed assembled exemplar guidance into live planning/generation inputs
- persist compact exemplar selection metadata into persona session turn metadata
- refresh the Persona module README

Out of scope:

- websocket payload/schema changes
- live client-side exemplar debug rendering
- new exemplar CRUD behavior
- retrieval algorithm changes
- ordinary persona-backed chat behavior changes beyond shared helper reuse

## Recommended Approach

Use the existing shared exemplar classifier, retrieval, and assembly helpers in the live websocket `user_message` path before `_propose_plan(...)` is called.

This is the recommended approach because it:

- avoids a websocket-only exemplar implementation
- keeps ordinary persona-backed chat and live Persona Garden aligned
- minimizes regression risk by reusing already-tested retrieval and assembly behavior
- leaves websocket debug payload expansion to a later dedicated PR

Rejected alternatives:

1. Websocket-only exemplar logic embedded directly in `persona_stream`
   This would immediately diverge from ordinary persona-backed chat and create maintenance drift.

2. Exposing live selected/dropped exemplar debug payloads in this PR
   This is useful, but it expands the websocket protocol and frontend scope beyond the runtime parity goal.

## Runtime Integration

The integration point is the `user_message` branch in `tldw_Server_API/app/api/v1/endpoints/persona.py`.

Recommended flow:

1. Resolve the active persona/session runtime context as the websocket already does.
2. Load enabled exemplars for `runtime_persona_id`.
3. Build exemplar classification input from the incoming websocket message.
4. Call the shared persona exemplar prompt-assembly helper.
5. Pass the assembled exemplar guidance text into the live planning/proposal path.
6. Persist compact exemplar selection metadata with `_record_turn(...)`.

Important constraint:

- do not introduce a second websocket-specific retrieval or formatting implementation
- do not persist exemplar text as conversation or session messages
- do not change websocket event payloads in this PR

## Persisted Metadata

Live persona websocket turns should persist only compact exemplar diagnostics.

Recommended metadata shape:

- `persona_exemplar_selection`
  - `applied`
  - `selected_ids`
  - `selected_count`
  - `rejected`
    - list of `{id, reason}`
  - `rejected_count`
  - `classifier`
    - normalized scenario/tone/risk/capability labels used for retrieval

This metadata should be attached through the existing `_record_turn(...)` flow so it is available in persisted persona session history and local runtime snapshots.

Do not store full exemplar content snapshots in turn metadata.

## Planning And Prompting Behavior

The live websocket path should pass the assembled exemplar guidance text into `_propose_plan(...)`, not raw exemplar rows.

This preserves the intended layer boundaries:

- profile/state docs define durable persona identity
- memory handles retrieved experience
- policy/scope still wins on capability and tool rules
- exemplars shape tone, boundary handling, and in-character responses

The goal is for live Persona Garden planning to benefit from the same persona-conditioned guidance that ordinary persona-backed chat already uses.

## Testing

Add websocket-focused regression coverage for:

- live `user_message` handling uses the shared exemplar retrieval/assembly seam
- selected exemplar IDs and rejected reasons are persisted into recorded turn metadata
- exemplar text is not persisted into metadata
- personas with no enabled exemplars keep current live behavior

The ordinary persona-backed chat prompt-assembly tests should remain the source of truth for the shared helper behavior; live runtime tests only need to prove the websocket path is wired into that seam correctly.

## Documentation

Refresh `tldw_Server_API/app/core/Persona/README.md` so it no longer describes Persona as:

- a static placeholder catalog only
- a no-database feature
- an in-memory-only session scaffold

The README should reflect the current architecture:

- persisted persona profiles and sessions
- persona state docs
- scope and policy rules
- persona exemplar bank and adaptive retrieval
- shared exemplar retrieval and prompt assembly used by ordinary chat and live Persona Garden
- current limitation that websocket-specific exemplar debug visibility is not yet exposed to clients

## Follow-Up

The next PR can expand websocket-specific observability by exposing selected/dropped exemplar details directly in live websocket events, if that becomes necessary for Persona Garden debugging UX.
