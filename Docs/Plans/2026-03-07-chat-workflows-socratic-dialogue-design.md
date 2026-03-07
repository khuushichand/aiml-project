# Chat Workflows Socratic Dialogue Design

Date: 2026-03-07
Status: Approved
Issue: `#498`

## Summary

Extend Chat Workflows with a reusable moderated dialogue capability and ship a built-in `Socratic Dialogue` template on top of it. The first deliverable supports one human participant, one debate LLM, and one moderator LLM. The moderator may decide whether the dialogue continues or finishes after each round, and may also steer the next user prompt. Outputs remain inside the workflow transcript for now rather than writing into notes or PKM records.

## Approved Product Decisions

1. The first deliverable targets `user + one debate LLM + LLM moderator`.
2. The backend should gain reusable workflow capabilities, not just a one-off template.
3. V1 should also include a built-in `Socratic Dialogue` template that uses those capabilities.
4. The moderator may both decide `continue` vs `finish` and dynamically steer the next prompt.
5. Debate outputs stay in the workflow transcript only for now.

## Goals

- Extend Chat Workflows beyond fixed structured QA without replacing the existing product model.
- Support moderated multi-round dialogue inside a workflow run.
- Keep overall workflow progression predictable while allowing dynamic prompt steering within a dialogue step.
- Reuse the existing run/event infrastructure where possible.
- Ship a built-in Socratic template that demonstrates the new engine capability immediately.

## Non-Goals

- Full arbitrary branching across workflow steps.
- Two-LLM debate variants in the first deliverable.
- Human moderator support in the first deliverable.
- Automatic export of arguments, concessions, or synthesis into PKM tools.
- General-purpose multi-actor workflow authoring for every future pattern in the first increment.

## Existing Repo Anchors

This extension should build on the current Chat Workflows implementation instead of creating a parallel subsystem.

- Backend workflow runtime and API:
  - `tldw_Server_API/app/core/Chat_Workflows/service.py`
  - `tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py`
  - `tldw_Server_API/app/api/v1/endpoints/chat_workflows.py`
  - `tldw_Server_API/app/api/v1/schemas/chat_workflows.py`
- Frontend workflow page and shared types:
  - `apps/packages/ui/src/components/Option/ChatWorkflows/ChatWorkflowsPage.tsx`
  - `apps/packages/ui/src/types/chat-workflows.ts`
- Existing base design:
  - `Docs/Plans/2026-03-07-chat-workflows-design.md`

## Recommended Approach

Add a new workflow step type called `dialogue_round_step`.

This is the narrowest reusable extension that satisfies the issue:

- it keeps `ChatWorkflowRun` as the top-level execution model
- it avoids hard-coding a Socratic-only runtime
- it does not require redesigning all workflows into a generic agent turn engine

The built-in `Socratic Dialogue` template should then be implemented as a stock template using the new step type rather than a separate execution path.

## Architecture And Execution Model

The current system is built around one active workflow step at a time. That should remain true. The change is that one step type may own an internal round loop.

### Step Types

- `question_step`
  - existing structured QA behavior
- `dialogue_round_step`
  - new moderated multi-round dialogue behavior

### Dialogue Step Configuration

A `dialogue_round_step` should define:

- `goal_prompt`
- `opening_prompt_mode`
- `opening_prompt_text` nullable, required when `opening_prompt_mode=custom_prompt`
- `user_role_label`
- `debate_instruction_prompt`
- `moderator_instruction_prompt`
- `debate_llm_config`
- `moderator_llm_config`
- `context_refs`
- `max_rounds`
- `finish_conditions`

### LLM Config Contract

`debate_llm_config` and `moderator_llm_config` should be typed workflow-safe selectors rather than arbitrary provider payloads.

Allowed v1 fields:

- `model`
- `provider` optional
- `temperature` optional
- `max_tokens` optional
- `top_p` optional

Explicitly disallowed in workflow templates and run snapshots:

- API keys
- base URLs
- raw `extra_body` payloads
- arbitrary adapter/provider-specific options

At execution time, the dialogue runtime should resolve and normalize these fields through the existing Chat orchestration stack, then freeze the normalized provider/model settings into the run snapshot for reproducibility.

### Dialogue Step Runtime

1. The run enters the `dialogue_round_step`.
2. The user sees an opening prompt or the latest moderator-supplied next prompt.
3. The user submits their response.
4. The debate LLM generates its reply.
5. The moderator LLM evaluates the exchange and emits structured control output.
6. If the moderator returns `continue`, the same workflow step remains active and the next round opens.
7. If the moderator returns `finish`, the dialogue step completes and the parent workflow advances to its next step or finishes the run.

### Moderator Authority Boundaries

The moderator may emit:

- `continue`
- `finish`
- `next_user_prompt`
- `moderator_summary`

The moderator may not:

- jump to arbitrary workflow steps
- alter the template structure
- mutate stored prior rounds

This keeps the overall workflow predictable while still supporting the issue requirement that the moderator may steer the next prompt dynamically.

## Data Model

The current workflow model needs a round layer inside a step.

### Template Step Changes

`ChatWorkflowTemplateStep` should gain:

- `step_type`
- `dialogue_config_json` nullable

Rules:

- `question_step` uses the current question fields and leaves `dialogue_config_json` empty.
- `dialogue_round_step` requires `dialogue_config_json`.

### Run State Changes

`ChatWorkflowRun` should gain lightweight runtime state so the server can resume an in-progress dialogue step cleanly:

- `active_round_index`
- `step_runtime_state_json`

Both debate and moderator model/provider configuration should be frozen into the run snapshot at start time, not resolved from mutable live defaults during execution.

`active_round_index` should always mean the next expected round index for the active `dialogue_round_step`, using zero-based indexing. The current step kind should be derived from `current_step_index` plus the frozen template snapshot rather than duplicated as a separate persisted source of truth.

### New Round Record

Add `ChatWorkflowRound` as the source of truth for dialogue state.

Suggested fields:

- `id`
- `run_id`
- `step_index`
- `round_index`
- `user_message`
- `debate_llm_message`
- `moderator_decision`
- `moderator_summary`
- `next_user_prompt`
- `status`
- timestamps

Transcript rendering should remain a derived view over structured answer and round records rather than becoming the primary persistence format.

### Transcript Projection

Transcript projection should have one canonical source per step type:

- `question_step`
  - transcript messages come from `chat_workflow_answers`
- `dialogue_round_step`
  - transcript messages come from `ChatWorkflowRound` records only

Workflow events remain audit-only and should not be projected as user-visible transcript entries.

For dialogue rounds, the transcript API should preserve explicit participant roles instead of collapsing everything into assistant/user pairs:

- `user`
- `debate_llm`
- `moderator`

This avoids ambiguity in the UI and keeps retry or partial-failure events from leaking into the visible conversation history.

### Event Additions

Keep the append-only event stream and add event types such as:

- `dialogue_round_started`
- `dialogue_user_submitted`
- `dialogue_debate_generated`
- `dialogue_moderated`
- `dialogue_step_completed`

## API Design

### Template APIs

Extend existing template CRUD payloads to support:

- `step_type`
- `dialogue_config`

Validation rules should enforce that:

- `question_step` payloads remain compatible with the current API
- `dialogue_round_step` requires valid LLM configs, round caps, and moderation prompts

### Run APIs

Extend run detail responses to return:

- current step
- current round index
- prior dialogue rounds for the active step
- the current user-facing prompt
- allowed next action

Add a round-response endpoint, for example:

- `POST /api/v1/chat-workflows/runs/{id}/rounds/{round_index}/respond`

From the caller's perspective, this endpoint should behave as one synchronous round submission. Internally it should use a two-phase claim/execute/finalize flow so the SQLite write lock is never held while waiting on LLM calls.

Internal flow:

1. atomically validate the expected run state and claim the round attempt
2. release the DB transaction
3. generate the debate LLM reply
4. generate the moderator decision
5. atomically finalize the claimed round if the run is still on the expected step/round
6. either keep the step active or mark it complete

The endpoint should remain idempotent for safe retry behavior.

## Runtime Rules And Failure Handling

### V1 Runtime Rules

- one human participant only
- one debate LLM only
- one moderator LLM only
- dialogue remains inside a single workflow step until completion
- max-round limits may force finish even if the moderator would continue

### Output Contracts

The moderator must return structured output, not free text control parsing.

Minimum shape:

- `decision`
- `moderator_summary`
- `next_user_prompt`

If structured parsing fails:

- fail the round
- keep the workflow step active
- allow safe retry
- do not partially advance the run

Both the debate reply and moderator reply should be executed through the existing Chat orchestration layer, not through bespoke provider-specific call paths. That keeps provider resolution, metrics, fallback, and error normalization consistent with the rest of the chat stack.

### Round Claim And Retry Rules

The dialogue runtime should distinguish:

- `pending`
  - a round has been claimed and is currently being executed
- `completed`
  - a round has a persisted debate reply and moderator decision
- `failed`
  - execution failed and the same round may be retried safely

Idempotency rules:

- same `idempotency_key` + same payload after completion returns the stored result
- same `idempotency_key` while a round is still `pending` returns a deterministic conflict or retryable status
- different payload for the same claimed round returns `409`

### Partial Failure Handling

If debate generation fails:

- do not mark the round complete
- do not run moderation
- allow retry with idempotency

If moderation fails:

- do not mark the round complete
- do not advance the workflow
- allow retry with idempotency

If context resolution degrades:

- continue with reduced context
- record the degradation in round or run metadata and events

### Free Chat Handoff Boundary

`Continue as free chat` should not replay moderator control scaffolding into a normal conversation. If later work chooses to seed the free-chat conversation with workflow context, it should use either:

- no seed transcript at all
- or a distilled summary that excludes `decision` and `next_user_prompt` control fields

## Security And Reliability Risks

### Prompt Injection Into Moderator Control

Risk:
debate content or external context may try to influence the moderator into emitting invalid control actions.

Adjustment:

- use strong system instructions for the moderator
- pass quoted debate/context content as untrusted material
- constrain moderator output to a strict response schema
- never allow moderator output to carry raw provider-execution parameters

### Duplicate Round Submission

Risk:
retries or concurrent tabs can create duplicate or conflicting rounds.

Adjustment:

- require expected `round_index`
- keep idempotency-key support
- reject stale or conflicting retries with deterministic errors

### Confusing Debate Content With Moderator Guidance

Risk:
users may not understand which text is argumentative content and which text is workflow control.

Adjustment:

- render debate reply and moderator summary as separate transcript blocks
- render the next input prompt from moderator guidance distinctly

### Mutable Provider Configuration Drift

Risk:
live provider/model settings can change mid-run and break reproducibility.

Adjustment:

- freeze debate and moderator LLM config inside the run snapshot

## Frontend Design

### Template Builder

Add a step-type selector:

- `Question`
- `Dialogue Round`

For `Dialogue Round`, render fields for:

- dialogue goal
- round cap
- debate model/provider
- moderator model/provider
- debate instructions
- moderator instructions
- context refs

### Run Screen

The active step UI should support both the workflow level and the round level.

Show:

- workflow progress such as `Step 2 of 3`
- round progress such as `Round 3 of 6`
- prior rounds as locked transcript history
- debate reply separate from moderator summary
- input box label driven by the moderator-supplied next prompt when present

### Completion UX

When the moderator finishes the dialogue step:

- advance to the next workflow step if one exists
- otherwise mark the run complete
- preserve the existing explicit `Continue as free chat` handoff only after workflow completion

## Built-In Template

Ship a stock `Socratic Dialogue` template in v1.

Recommended initial shape:

- optional setup `question_step` for the user thesis or discussion goal
- one `dialogue_round_step` for moderated debate
- optional closing `question_step` for the user’s final reflection

This should be stored as an ordinary workflow template definition so that it exercises the same APIs and UI as user-authored templates.

## Testing Strategy

### Backend

- schema validation for mixed step types
- run-state validation for dialogue-round progression
- round persistence and idempotent retry handling
- malformed moderator output handling
- max-round forced completion
- built-in Socratic template creation and execution

### Frontend

- template builder support for `dialogue_round_step`
- run screen rendering for round transcript and moderator guidance
- completion transitions from dialogue step to next step or workflow completion

### Regression Coverage

- existing `question_step` workflows should remain unchanged
- transcript and continue-chat behavior should remain intact for ordinary workflows

## Deferred Follow-On Work

- `two LLMs + human moderator`
- `two LLMs + LLM moderator`
- moderator-driven branching across workflow steps
- export of arguments/concessions/final synthesis into notes or PKM records
- more generic multi-actor turn orchestration beyond the dialogue-step model

## Recommendation

Implement this as a reusable `dialogue_round_step` extension to Chat Workflows and ship the built-in `Socratic Dialogue` template on top of it. This keeps the scope contained, preserves compatibility with the current structured QA model, and creates a path for later multi-party dialogue variants without forcing a full workflow-engine redesign.
