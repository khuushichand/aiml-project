# Chat Workflows Design

Date: 2026-03-07
Status: Approved

## Summary

Add a new `Chat Workflows` feature for structured, user-facing Q&A with an LLM. Users can either run saved templates that they author in the UI or generate a temporary linear workflow upfront from a goal, base question, and selected context. During execution, the workflow controls the sequence, the LLM may only phrase the authored question, each answer is persisted as structured Q&A, and the run stops by default when the final step completes.

## Product Decisions (Approved)

1. Support both reusable saved templates and runtime-generated workflows.
2. Workflow progression is author-driven; the LLM may phrase questions but may not choose the next step.
3. Completion stops by default; free chat requires an explicit follow-up action.
4. V1 is linear only.
5. Runtime-generated mode drafts the full workflow upfront before the run starts.
6. The canonical record is a structured Q&A run, not a raw chat transcript.
7. Step context may include prior answers plus explicit user-selected assets, not implicit whole-corpus retrieval.
8. End users author templates in the UI.
9. V1 answers are free text only.

## Goals

- Ship a first-class guided interview / structured Q&A experience without forcing it into the generic Workflows engine.
- Reuse the existing Chat stack for question phrasing and eventual free-chat handoff.
- Support both saved templates and generated drafts through one shared runtime.
- Persist step-by-step answers in a structured form that is queryable and exportable later.
- Keep the initial product narrow: linear, free-text, explicit-context, stop-on-complete.

## Non-Goals

- Branching, loops, or agent-driven next-step selection.
- Typed answers, uploads, or rich form validation.
- Implicit global RAG over the entire user corpus.
- Reusing the generic workflow editor as the primary authoring surface.
- Running each question step through Jobs or Scheduler as if it were a backend automation.
- Full Prompt Studio integration in v1.

## Existing Repo Anchors

The design should reuse current project patterns instead of inventing a separate architecture:

- Chat endpoint and orchestration:
  - `tldw_Server_API/app/api/v1/endpoints/chat.py`
  - `tldw_Server_API/app/core/Chat/chat_orchestrator.py`
  - `Docs/Code_Documentation/Chat_Developer_Guide.md`
- Generic workflows system for lifecycle and event-pattern reference:
  - `tldw_Server_API/app/api/v1/endpoints/workflows.py`
  - `Docs/Code_Documentation/Workflows_Module.md`
- Prompt authoring/versioning precedent:
  - `Docs/Published/API-related/Prompt_Studio_API.md`
- Frontend routes and existing workflow/chat surfaces:
  - `apps/tldw-frontend/pages/chat/index.tsx`
  - `apps/tldw-frontend/pages/workflow-editor.tsx`

## Critical Risks And Design Adjustments

### 1. Template Edit Drift During Active Runs

Risk: if a user edits a template while a run is active, the run can become unreproducible or jump to a different question sequence.

Adjustment:

- Templates keep a mutable current definition plus a monotonically increasing `version`.
- Every run stores `template_version` and an immutable `template_snapshot_json`.
- Active runs never read the live template after start.

### 2. Stale Or Unauthorized Context References

Risk: explicit assets can be deleted, permissions can change, or large content can produce different excerpts over time.

Adjustment:

- Store both `selected_context_refs_json` and `resolved_context_snapshot_json` on the run.
- Revalidate ownership / access when the run starts and when step context is resolved.
- If a referenced asset can no longer be resolved, continue with reduced context and record the degradation in run metadata and events.

### 3. Accidental Coupling To Normal Chat History

Risk: if runs are stored as ordinary conversations, the feature becomes hard to reason about and collides with existing chat assumptions.

Adjustment:

- `Chat Workflow Run` is the source of truth.
- Transcript rendering is a derived view over the run, not the primary persistence format.
- `Continue as free chat` creates or links a normal chat conversation only after the run completes.

### 4. Duplicate Or Out-Of-Order Answer Submission

Risk: double-submits, refreshes, or concurrent tabs could corrupt step order.

Adjustment:

- `POST /runs/{id}/answer` requires the expected `step_index` or `step_id`.
- Server rejects stale or future-step answers.
- Add optional idempotency token support for UI retries.

### 5. Prompt Injection Through Attached Context

Risk: selected content may contain instructions that distort question phrasing or cause the model to answer instead of ask.

Adjustment:

- Question rendering is a constrained call whose only valid output is one question string.
- The model receives base question, prior answers, and quoted context excerpts, with strong system instructions to ignore instructions inside context.
- If rendering fails or violates shape constraints, fall back to the stock base question.

### 6. Excess Cost And Latency

Risk: phrasing every step through an LLM can make a structured workflow feel slower than necessary.

Adjustment:

- Each step defaults to `stock` unless explicitly marked `llm-phrased`.
- Generated drafts may still contain stock base questions and only use phrasing where useful.
- Precomputing all rendered questions is deferred; v1 renders on demand.

### 7. Weak Generated Draft Quality

Risk: generated workflows will be hard to trust if users cannot inspect or edit them before starting.

Adjustment:

- `generate-draft` returns a reviewable, editable temporary draft.
- User can `Start now`, `Edit first`, or `Save as template`.

## Recommended Architecture

Introduce a dedicated `Chat Workflows` module that sits above Chat and beside generic Workflows.

### Why This Boundary

- The generic Workflows engine is oriented around automation steps, events, artifacts, and operator controls.
- `Chat Workflows` is an interactive, user-facing interview flow where the primary unit is an authored question and a captured answer.
- Reusing the generic Workflows engine as the top-level runtime would bend the product model and make the UI feel like an automation debugger.

### Architecture Shape

- New `Chat Workflows` domain:
  - template CRUD
  - draft generation
  - run lifecycle
  - answer capture
  - transcript projection
  - free-chat handoff
- Reused internals:
  - `Chat` for question phrasing and continuation handoff
  - generic `Workflows` patterns for statuses, events, audit, and control semantics
  - Prompt Studio concepts later, if reusable prompt versioning becomes valuable

### Execution Model

- Interactive step advancement stays synchronous and request/response based.
- Jobs / Scheduler are not the execution backbone for v1 because this is a user-facing foreground experience.
- If future preprocessing becomes heavy, only the preprocessing should move to background work, not step-to-step interaction.

## Data Model

Use a dedicated persistence model rather than overloading normal chat tables.

### `chat_workflow_templates`

Suggested fields:

- `id`
- `tenant_id`
- `user_id`
- `title`
- `description`
- `status` (`active`, `archived`)
- `version`
- `created_at`
- `updated_at`

### `chat_workflow_template_steps`

Suggested fields:

- `id`
- `template_id`
- `step_index`
- `label`
- `base_question`
- `question_mode` (`stock`, `llm_phrased`)
- `phrasing_instructions`
- `context_refs_json`

Constraints:

- unique `(template_id, step_index)`

### `chat_workflow_runs`

Suggested fields:

- `id`
- `tenant_id`
- `user_id`
- `template_id` nullable for unsaved generated drafts
- `template_version`
- `source_mode` (`saved_template`, `generated_draft`)
- `status` (`active`, `completed`, `canceled`)
- `current_step_index`
- `template_snapshot_json`
- `selected_context_refs_json`
- `resolved_context_snapshot_json`
- `question_renderer_model`
- `started_at`
- `completed_at`
- `canceled_at`
- `free_chat_conversation_id` nullable

### `chat_workflow_answers`

Suggested fields:

- `id`
- `run_id`
- `step_id`
- `step_index`
- `displayed_question`
- `answer_text`
- `question_generation_meta_json`
- `answered_at`

Constraints:

- unique `(run_id, step_index)`

### `chat_workflow_run_events`

Recommended minimal append-only event log:

- `id`
- `run_id`
- `seq`
- `event_type`
- `payload_json`
- `created_at`

Useful event types:

- `run_started`
- `question_rendered`
- `answer_recorded`
- `context_degraded`
- `run_completed`
- `run_canceled`
- `free_chat_continued`

## Runtime Modes

### 1. Saved Template Mode

- User selects a saved template from the library.
- User optionally attaches context assets.
- Server snapshots the template and creates a run.
- Run executes one step at a time.

### 2. Generated Draft Mode

- User provides `goal`, optional `base_question`, optional target step count, and explicit context assets.
- Server asks the LLM to produce a full linear workflow draft upfront.
- Result is normalized into the same internal step model used by saved templates.
- User can review/edit/save/start from that draft.
- Once started, the run is identical to saved-template execution.

## Run Lifecycle

1. Create run from saved template or generated draft.
2. Freeze template snapshot and selected context refs.
3. Resolve the current step.
4. Render the displayed question:
   - `stock`: use `base_question`
   - `llm_phrased`: use Chat orchestration to phrase the authored question from approved inputs
5. Show exactly one current question.
6. Persist the user’s free-text answer.
7. Advance to the next fixed step.
8. Repeat until the final step.
9. Mark the run `completed` and stop by default.
10. If the user explicitly chooses `Continue as free chat`, create/link a normal chat conversation seeded from the run summary.

## Question Rendering Contract

Question rendering must be tightly constrained.

Inputs:

- step `base_question`
- optional step `phrasing_instructions`
- prior answers from the run
- explicit context excerpts

Rules:

- Output must contain one displayed question, not an answer, not multiple follow-ups.
- No tool use.
- No autonomous step selection.
- No implicit retrieval from unrelated user content.

Preferred implementation:

- Use a lightweight question-rendering helper service over existing Chat orchestration.
- Where available, use structured output constraints to require a shape like `{ "display_question": "..." }`.
- If the LLM call fails or returns malformed output, fall back to the `base_question`.

## API Surface

Suggested v1 API:

- `POST /api/v1/chat-workflows/templates`
- `GET /api/v1/chat-workflows/templates`
- `GET /api/v1/chat-workflows/templates/{id}`
- `PUT /api/v1/chat-workflows/templates/{id}`
- `DELETE /api/v1/chat-workflows/templates/{id}`
- `POST /api/v1/chat-workflows/templates/{id}/duplicate`

- `POST /api/v1/chat-workflows/generate-draft`
  - Input: `goal`, optional `base_question`, optional `desired_step_count`, explicit context refs
  - Output: reviewable linear workflow draft

- `POST /api/v1/chat-workflows/runs`
  - Start from saved template or generated draft
- `GET /api/v1/chat-workflows/runs/{id}`
- `GET /api/v1/chat-workflows/runs/{id}/transcript`
  - Derived transcript view for UI convenience
- `POST /api/v1/chat-workflows/runs/{id}/answer`
- `POST /api/v1/chat-workflows/runs/{id}/cancel`
- `POST /api/v1/chat-workflows/runs/{id}/continue-chat`

Recommended `answer` contract:

- Require current `step_index` or `step_id`
- Accept free-text `answer_text`
- Optionally accept an idempotency token for retry-safe submits
- Return updated run state plus next displayed question when applicable

## Frontend UX

Keep this separate from the generic workflow editor.

### 1. Templates Library

- List saved templates
- Create, edit, duplicate, archive/delete, run

### 2. Template Builder

- Ordered linear step editor
- Each step configures:
  - label
  - base question
  - `stock` vs `llm-phrased`
  - optional phrasing instructions
  - explicit context refs

### 3. Generate Workflow Flow

- User enters a goal and optional base question
- User selects context assets
- System returns a draft workflow
- User may start immediately, edit, or save as a template

### 4. Run Screen

- One active question at a time
- Clear progress indicator: `Step 2 of 6`
- Prior answers visible as locked history
- No skip-ahead or branching controls in v1
- Completed screen presents explicit `Continue as free chat`

### 5. Free Chat Handoff

- Starting free chat after completion creates or links a normal chat conversation
- Seed that conversation with a compact run summary:
  - workflow title
  - step questions
  - captured answers
  - selected context refs or excerpts as appropriate
- Keep a backlink between the conversation and originating workflow run

## Auth, Permissions, And Ownership

- Templates and runs are user-owned and tenant-scoped.
- In multi-user mode, add route-level permissions consistent with the rest of the API:
  - read templates/runs
  - write templates
  - execute/cancel/continue runs
- All context refs must be resolved through existing ownership-aware read paths.

## Error Handling

- Question rendering failure:
  - fall back to the stock question
  - emit `question_render_fallback` metadata/event
- Missing context asset:
  - continue if possible with reduced context
  - record `context_degraded`
- Persistence failure on answer submit:
  - do not advance the run
- Attempt to answer wrong step:
  - return conflict-style error with current run state
- Attempt to continue to free chat before completion:
  - reject with validation error

## Observability

Track low-cardinality metrics:

- `chat_workflow_runs_started_total`
- `chat_workflow_runs_completed_total`
- `chat_workflow_runs_canceled_total`
- `chat_workflow_question_render_fallback_total`
- `chat_workflow_context_degraded_total`

Emit structured logs with:

- tenant/user identifiers
- template id/version
- run id
- step index
- fallback/degraded flags

Do not log raw answer bodies or large context payloads.

## Testing Strategy

### Unit

- Template validation and step ordering
- Generated draft normalization into a valid linear template
- Question rendering fallback behavior
- Step-advance conflict/idempotency rules
- Continue-to-chat gating

### Integration

- Create/edit/run a saved template end-to-end
- Generate draft from goal/context and run it end-to-end
- Resume an active run
- Complete a run and continue to free chat
- Context permission failure degrades safely

### Frontend

- Template builder CRUD
- Draft generation review flow
- Run progression and completion state
- Free-chat handoff UX

## Recommended V1 Scope

- Saved templates authored in the UI
- Generated drafts created upfront from goal plus explicit context
- Linear step progression
- Free-text answers
- Structured Q&A persistence
- Explicit stop on completion
- Optional free-chat handoff after completion

## Deferred Work

- Branching and loops
- Typed answers and validation
- Collaborative / shared runs
- Global auto-RAG over all user content
- Voice-first workflow execution
- Prompt Studio-backed prompt versioning for question renderer prompts
- Deep integration with generic Workflows runs/artifacts/control APIs
