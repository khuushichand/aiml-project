# Deep Research Chat Follow-Up Launch Design

**Date:** 2026-03-19

## Goal

Let a user start a new deep-research run directly from the current chat thread as an explicit composer action, optionally seeded from the currently attached research context.

The new run should remain linked to the same saved chat thread so the existing linked-run status stack and completion handoff continue to work without transcript pollution.

## User-Facing Outcome

For v1:

- saved chat threads expose a `Follow-up Research` composer action
- the action uses the current draft as the new research query
- if an attached research context exists, the launch flow offers `Use attached research as background`
- starting the follow-up run keeps the user in chat instead of navigating to `/research`
- the new run appears in the existing linked-run status surface for that thread
- the normal chat `Send` path is unchanged

## Non-Goals

This slice does not include:

- automatic prompt-to-research escalation
- launching follow-up research from temporary/local chats
- full-bundle or raw-artifact follow-up seeding
- editing the bounded research background inside the follow-up confirmation surface
- automatically attaching the new run back into chat on completion
- replacing the existing `Deep Research` button that opens the research console

## Constraints From The Current Codebase

The current code already provides:

- a composer-side deep-research launch button in [PlaygroundForm.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx) that navigates to `/research`
- durable chat linkage for research runs through `chat_handoff` in [research_runs_schemas.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py) and [ResearchSessionsDB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py)
- bounded attached research context already derived and stored on the chat surface in [research-chat-context.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts)
- a chat-linked runs status stack and completion handoff
- a package-side `getResearchBundle(...)` and `listChatResearchRuns(...)` client in [TldwApiClient.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/TldwApiClient.ts)

The current code does **not** provide:

- any package-side `createResearchRun(...)` method for direct in-chat launch
- any follow-up seed/background field on the research run create contract
- any persisted `follow_up` metadata on research sessions
- any planning hook that uses attached research context when building the initial deep-research plan
- any composer confirmation surface for `Follow-up Research`

Those gaps define the shape of this design.

## Recommended Approach

Use a direct in-chat launch path.

The composer should start a new research run through the existing `/api/v1/research/runs` backend endpoint, not by navigating to `/research` and relying on autorun query params.

That gives the best broader chat/research integration because:

- the user stays in the chat thread
- the new run immediately participates in the linked-run status stack
- the feature can use the existing chat attachment state directly
- it does not overload normal send behavior

The existing `Deep Research` button that opens `/research` can remain as-is for general research console navigation. `Follow-up Research` is a separate chat-native action.

## Architecture

### 1. Saved-Thread-Only Follow-Up Launch

V1 follow-up research should only be available for saved server-backed chat threads.

Reason:

- the slice is explicitly about keeping the new run linked back to the same chat thread
- that requires a real `chat_id`
- temporary/local chats have no durable chat linkage target

Behavior:

- if `serverChatId` exists and the draft is non-empty, enable `Follow-up Research`
- if the thread is temporary or the draft is empty, disable the action
- use the normal `chat_handoff.chat_id = serverChatId`

This keeps the contract simple and avoids inventing temporary-chat research linkage in the same slice.

Backend requirement:

- when `chat_handoff.chat_id` is provided for follow-up launch, the backend must verify that the chat exists and is owned by the current user before creating the linked research run
- invalid or foreign chat IDs must fail the create request instead of producing an orphaned linked run

### 2. Direct Launch From Chat

Add a package-side direct launch client:

- `tldwClient.createResearchRun(...)`

The composer action should:

1. read the current draft
2. optionally include bounded follow-up background when the user enables it
3. call `/api/v1/research/runs`
4. invalidate or refresh the chat-linked-runs query for the current `serverChatId`
5. keep the user in the same chat thread

The new run will then appear in the existing linked-run status stack without any transcript changes.

To keep the frontend contracts aligned, the web research client type in `apps/tldw-frontend/lib/api/researchRuns.ts` should also be extended with the same optional `follow_up` contract, even if v1 launch uses the package-side client only.

### 3. Follow-Up Payload Contract

Extend the research create contract with an optional `follow_up` object.

Suggested shape:

- `follow_up`
  - `from_run_id`
  - `mode`
    - `chat_attached_context`
  - `background`
    - bounded attached-context payload

The bounded background should reuse the same conceptual field set as chat-attached context:

- `run_id`
- `query`
- `question`
- `outline`
- `key_claims`
- `unresolved_questions`
- `verification_summary`
- `source_trust_summary`
- `research_url`

This remains intentionally bounded:

- no `report_markdown`
- no full `source_inventory`
- no raw artifacts
- no full claims corpus

V1 caps should be explicit and enforced on the backend create schema:

- `question` and `research_url` should keep request-safe max lengths
- `outline`: max `7` items
- `key_claims`: max `5` items
- `unresolved_questions`: max `5` items
- each outline title, claim text, and unresolved-question string should have a bounded max length

The follow-up request should reject oversized background payloads rather than silently persisting arbitrarily large `follow_up_json`.

### 4. Persisted Follow-Up Metadata On The Research Run

The follow-up seed cannot remain request-only because the planning job runs asynchronously after session creation.

Add a first-class `follow_up_json` field on `research_sessions`, parallel to:

- `limits_json`
- `provider_overrides_json`

Do **not** hide follow-up seed data inside `limits_json` or `provider_overrides_json`.

Store the normalized follow-up metadata there so:

- session creation remains deterministic
- planning jobs can read the same bounded background later
- follow-up provenance is inspectable for debugging

The persisted payload should remain the same normalized bounded shape accepted at the API boundary. It should not re-expand into bundle-sized data at persistence time.

### 5. Planning Hook

The current planning phase only uses:

- `session.query`
- `session.source_policy`
- `session.autonomy_mode`

That is not enough for seeded follow-up research to behave differently.

Extend the planning hook so `build_initial_plan(...)` can accept optional follow-up background and use it to bias the new plan.

For v1, keep this conservative:

- treat the draft query as authoritative
- use attached background only as bounded additional context
- bias focus-area generation using:
  - attached `question`
  - attached `key_claims`
  - attached `unresolved_questions`
- do not mutate the user’s new query

This keeps the feature useful without turning it into a full plan-editing system.

### 6. Composer Confirmation Surface

Place `Follow-up Research` in the existing composer tools/send-options area.

When triggered:

- show a small confirmation surface in `PlaygroundForm.tsx`
- show the exact query that will be used from the current draft
- if an active attached context exists, show:
  - `Use attached research as background`
- actions:
  - `Start research`
  - `Cancel`

Default behavior:

- the background toggle is shown only when an active attachment exists
- it defaults to enabled

This keeps the feature explicit and close to the draft that will launch the new run.

### 7. Success And Failure Behavior

On success:

- close the confirmation surface
- invalidate the linked-runs query for the current chat
- keep the user in chat
- preserve the existing attached context unchanged

The draft should remain unchanged in v1.

Reason:

- this action starts background research but does not send a chat message
- preserving the draft avoids destructive surprise on a non-send action

Duplicate-launch protection is required:

- disable `Start research` while a follow-up launch is in flight
- ignore repeated clicks while pending
- the minimum v1 guarantee is that one double-click does not create two runs

On failure:

- show a local action-level error or toast consistent with existing composer launch failures
- do not create a transcript message
- do not mutate the attached context

## UI Contract

### Entry Point

`Follow-up Research` lives in the composer tools/send-options area, not in the transcript or the attached-context chip.

### Availability

- enabled only when:
  - `serverChatId` exists
  - draft text is non-empty
- disabled for temporary/local chats

### Confirmation Surface

Contents:

- title or label: `Follow-up Research`
- draft query preview
- optional checkbox:
  - `Use attached research as background`
- actions:
  - `Start research`
  - `Cancel`

### No Transcript Pollution

Launching follow-up research must not:

- append a user message
- append an assistant message
- alter existing message history

The run becomes visible through the linked-run status stack and later the normal completion handoff.

## API And Schema Changes

### Backend

In [research_runs_schemas.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py):

- add bounded follow-up request models
- extend `ResearchRunCreateRequest` with optional `follow_up`

In [ResearchSessionsDB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py):

- add `follow_up_json` column
- add it to `ResearchSessionRow`
- normalize it to `{}` when absent or malformed

In [service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/service.py):

- accept `follow_up`
- persist it via `follow_up_json`
- verify `chat_handoff.chat_id` ownership before persisting linkage for follow-up launches

In [planner.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/planner.py) and [jobs.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/jobs.py):

- thread the optional follow-up background into `build_initial_plan(...)`
- use it to bias initial focus-area generation

### Frontend

In [TldwApiClient.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/TldwApiClient.ts):

- add typed follow-up request interfaces
- add `createResearchRun(...)`

In [researchRuns.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/lib/api/researchRuns.ts):

- extend `ResearchRunCreateRequest` with the same optional `follow_up` type so frontend research API contracts do not drift

In [PlaygroundForm.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx):

- add the composer action
- add the confirmation surface
- wire direct launch and linked-run query invalidation
- add a pending launch lock so duplicate clicks cannot create duplicate runs

The linked-run stack itself does not need a structural change.

## Testing Requirements

### Backend

- research run create endpoint accepts optional bounded `follow_up`
- research run create rejects foreign or nonexistent `chat_handoff.chat_id` for follow-up launches
- malformed or oversized follow-up background is rejected cleanly
- service persists `follow_up_json`
- planning uses follow-up background to influence focus-area generation
- ordinary research run creation without `follow_up` is unchanged

### Frontend

- `Follow-up Research` appears in the composer tools/send-options area
- it is disabled for empty drafts
- it is disabled for temporary chats
- the background toggle appears only when attached research exists
- starting research is single-flight and repeat clicks while pending do not create duplicate launches
- starting research calls the package-side client with:
  - `query`
  - `chat_handoff.chat_id`
  - optional `follow_up`
- success invalidates the linked-runs query without sending a chat message
- the web research client type stays aligned with the backend request contract
- the normal `Send` path remains unchanged

## Risks

- prompt duplication if the draft query and attached background overlap too heavily
- schema drift if the bounded attached-context shape diverges between chat requests and research follow-up launch
- overcoupling the composer to research launch details if the UI surface grows beyond a small confirmation step
- confusion between the existing `Deep Research` console-launch button and the new `Follow-up Research` in-chat launch action if labels are not clear

## Success Criteria

- saved chat threads can launch a new linked deep-research run directly from the composer
- attached research can optionally seed that new run as bounded background
- the new run appears in the same chat thread’s linked-run status surface
- no transcript pollution or normal-send regression is introduced
