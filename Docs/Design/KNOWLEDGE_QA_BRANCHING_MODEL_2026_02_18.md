# Knowledge QA Conversation Branching Model (Stage 3 Discovery)

## Scope

This note defines how branching should work for Knowledge QA follow-up conversations without changing current linear thread persistence behavior.

## Current Baseline

- Conversations are linear and append-only within one `conversationId`.
- Follow-ups preserve context by sending the next question in the same thread.
- Prior turns can now be reused into the main search box for re-ask/edit workflows.

## Proposed Branch Semantics

1. A branch starts from a specific historical user/assistant turn pair.
2. Branch creation produces a new server conversation with:
   - `parent_conversation_id` set to the source thread.
   - Branch metadata storing the source turn message id.
   - Initial messages seeded from the source turn context snapshot.
3. New branch questions append only to the branch conversation.
4. Parent and sibling branches are immutable from each other.

## Persistence Rules

- Keep existing `messages-with-context` payload contract unchanged for linear threads.
- Add optional branch metadata fields only when branching is enabled.
- History sidebar should group branches under their parent only when branch metadata exists.
- Export behavior should support:
  - Parent-only export.
  - Single-branch export.
  - Parent + branch family export (future enhancement).

## Feature Gating

- Guard branching UI and API invocation behind `ff_knowledgeQaBranching`.
- Default is `false`.
- When disabled, no branching controls are shown.
- When enabled, surface staged controls with explicit “coming soon” messaging until API integration is complete.

## Rollout Notes

1. Phase A: UI affordance + model guardrails only (current stage).
2. Phase B: API contract + branch creation endpoint integration.
3. Phase C: history visualization for branch trees and comparison workflows.
