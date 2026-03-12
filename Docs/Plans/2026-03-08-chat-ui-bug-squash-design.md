# Chat UI Bug Squash Design

Date: 2026-03-08
Status: Approved
Scope: Broad chat UI reliability pass with low-risk UX cleanup

## Summary

This design defines a bounded bug-squash pass for the shared chat UI. The goal is to improve correctness and reliability across chat discovery, chat loading, chat switching, and chat mutations while also cleaning up low-risk UX states that currently make failures look like empty or broken UI.

The pass is intentionally not a rewrite. It should harden the current architecture, add regression coverage around the reported failure modes, and avoid large visual or state-model redesign.

## Problem Statement

Recent user feedback indicates the chat UI can feel extremely buggy when:

- loading the chat page
- loading an existing chat
- switching between chats
- deleting a chat

The most likely failure patterns in the current implementation are:

- transient list-fetch failures that collapse into an empty chat list
- chat selection flows that clear the pane before a new chat is fully loaded
- stale optimistic-lock versions causing delete or restore operations to fail
- background settings sync mutating chat versions without the sidebar reflecting the new value
- ambiguous UI states where loading, empty, offline, and failed states are hard to distinguish

## Goals

- Preserve a stable, understandable chat list during transient failures.
- Make chat selection and switching converge to either a fully loaded state or a clearly failed state.
- Make rename, topic update, delete, and restore more tolerant of stale client metadata.
- Clarify loading, empty, offline, recoverable-error, and hard-error UI states.
- Add regression tests for the real failure surfaces instead of relying on happy-path behavior.

## Non-Goals

- Re-architecting the full store model.
- Large visual redesign of the chat experience.
- Replacing optimistic locking on the backend.
- Broad backend API redesign beyond narrow compatibility fixes if needed.

## Recommended Approach

Use a structured bug-squash pass across four reliability surfaces:

1. Sidebar and session discovery
2. Chat selection and load lifecycle
3. Chat mutations and stale-version handling
4. User-facing UX states

This is preferred over a narrow patch because the reported bugs span more than one path, and it is preferred over a refactor because the goal is fast, bounded reliability improvements with low regression risk.

## Reliability Surfaces

### 1. Sidebar and Session Discovery

The server chat list should not silently degrade into an empty state on recoverable failures such as:

- temporary auth drift
- request aborts during navigation
- transient rate limiting
- short-lived connectivity issues

The sidebar should preserve the last known good data when possible and expose a recoverable-refresh failure state when a new fetch fails. Empty-state rendering should only happen when the data source is truly empty, not when the latest refresh was unsuccessful.

### 2. Chat Selection and Load Lifecycle

Selecting a chat should follow an explicit lifecycle:

- `idle`
- `loading`
- `loaded`
- `failed`

The active pane should not be left blank without explanation. In-flight loads should be cancellable, stale requests should not overwrite newer selections, and metadata/message fetch failures should resolve into a visible error state rather than a half-reset view.

### 3. Chat Mutations and Stale-Version Handling

Chat-level mutations currently depend too much on cached sidebar metadata. This is risky because chat settings sync and other background updates can bump the server-side chat version.

The mutation layer should preserve optimistic locking but become tolerant of stale client versions by:

- using fresh metadata when no local version is available
- retrying once after conflict with the latest server version
- surfacing conflict-specific feedback when retry still fails

This applies to:

- rename
- topic update
- delete
- restore
- any other chat-level metadata edits that use the shared API client

### 4. User-Facing UX States

The bug-squash pass should make these states visually and behaviorally distinct:

- loading chats
- unable to refresh chats
- no chats yet
- trash empty
- loading selected chat
- failed to load selected chat
- chat unavailable or deleted
- offline or disconnected

This is low-risk UX cleanup because it clarifies existing system behavior without changing the core product flow.

## Concrete Design

### Sidebar Behavior

The server chat history query should treat the sidebar cache as a user-facing resilience layer.

Desired behavior:

- Keep prior chat list data visible when a recoverable refresh fails.
- Only return an empty list when the source of truth is genuinely empty.
- Expose enough status to render a non-destructive inline warning when the refresh failed.
- Avoid making recoverable failures look identical to successful empty results.

### Chat Selection Behavior

Chat selection should set the target chat immediately, clear stale transient state, and place the main pane into a visible loading state. The selected chat should only commit messages and metadata after the loader confirms that the response still matches the currently active target.

Desired behavior:

- Selecting a new chat aborts stale in-flight requests.
- Only the newest selection can commit messages to the pane.
- Metadata and messages should be committed together as a coherent loaded state.
- Loader failures should keep the current chat shell usable and render an explicit failure state.

### Mutation Behavior

The API client should own stale-version recovery for chat-level mutations instead of duplicating that logic in individual UI components.

Desired behavior:

- If a mutation is called without a version, fetch current chat metadata first.
- If a mutation is called with a version and the server returns a conflict, fetch the latest chat metadata and retry once.
- If the retry fails, surface a conflict-specific error so the user understands the action failed because the chat changed, not because the system is generically broken.

This design keeps optimistic locking intact while removing the most common stale-version footgun from the UI.

### UX Copy and States

The sidebar and main pane should use explicit state-specific copy instead of generic empty or generic error rendering.

Desired examples:

- Sidebar: "Unable to refresh chats. Showing your last loaded list."
- Sidebar: "Server chats unavailable right now."
- Main pane: "Loading chat..."
- Main pane: "Failed to load this chat. Retry or select another chat."
- Mutation feedback: "This chat changed on the server. Retrying with the latest version."

Exact copy can be tuned during implementation, but the state distinction is part of the design and should be tested.

## Components and Files in Scope

Primary frontend scope:

- `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- `apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`
- `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- `apps/packages/ui/src/components/Common/ChatSidebar/ServerChatList.tsx`
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

Potential backend touchpoint only if required for compatibility:

- `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`

## Error Handling

The implementation should separate:

- recoverable fetch errors
- hard fetch errors
- stale-version conflicts
- deleted or unavailable resources
- user-aborted requests

Abort-like transitions should remain silent. Recoverable failures should avoid destructive UI resets. Hard failures should be visible. Conflicts should use mutation-specific messaging.

## Testing Strategy

Regression coverage should be added for the following scenarios:

- recoverable sidebar fetch failure preserves the last known chat list
- sidebar empty state only renders when the server result is truly empty
- selecting chat B after chat A aborts or ignores chat A’s stale load completion
- failed chat load leaves a visible failed state instead of a blank pane
- delete succeeds when the initial local version is stale but the latest server version is valid
- restore succeeds under the same stale-version conditions
- rename and topic updates follow the same stale-version recovery path
- settings sync no longer makes the next delete attempt fail permanently

Tests should stay focused on behavior, not implementation details.

## Risks and Mitigations

Risk: Preserving prior sidebar data could hide the fact that refresh failed.
Mitigation: pair preserved data with a clear inline refresh warning.

Risk: Retry-on-conflict could mask real multi-client contention.
Mitigation: retry only once and preserve explicit conflict feedback on final failure.

Risk: Load-state cleanup could accidentally regress existing happy-path selection behavior.
Mitigation: add tests for selection ordering, abort behavior, and successful load commits.

Risk: Low-risk UX cleanup could sprawl into redesign work.
Mitigation: limit changes to state clarity, copy, and layout behavior for existing components.

## Acceptance Criteria

- A transient sidebar fetch failure does not make chats appear to disappear.
- Switching chats cannot leave the pane blank without a loading or failure state.
- Delete and restore no longer fail solely because the sidebar carried a stale version after background sync.
- Mutation failures provide actionable, state-specific feedback.
- New regression tests cover the observed bug surfaces.

## Implementation Notes

This design is intended to feed directly into a multi-stage implementation plan. The implementation should remain incremental, test-driven where practical, and validated with targeted frontend tests before broader verification.
