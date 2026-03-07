# Unified Chat Request Queue for WebUI + Extension Design

Date: 2026-03-07
Owner: Codex collaboration session
Status: Approved (design)

## Context and Problem

The repo already has partial queued-message behavior, but it only solves the offline case and it is too limited for the workflow the user wants.

Existing anchors:

- `apps/packages/ui/src/store/option/slices/core-slice.ts`
  - stores `queuedMessages` as `{ message, image }[]`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  - queues messages only when connection is unavailable
- `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
  - duplicates similar offline queue behavior for the extension sidepanel
- `apps/packages/ui/src/store/playground-session.tsx`
  - already persists WebUI playground session state locally
- `apps/packages/ui/src/store/sidepanel-chat-tabs.tsx`
  - already persists sidepanel tab snapshots, including queued messages
- `apps/extension/tests/e2e/queued-messages.spec.ts`
  - already verifies offline queue banners and flush behavior

Current gaps:

1. Users cannot stage follow-up prompts while a response is still streaming.
2. Queued items cannot be edited, reordered, or selectively run.
3. The queue captures too little state (`message` + `image` only).
4. WebUI and extension use duplicated queue logic instead of a shared queue model.
5. Queue behavior is not defined for reconnect, restart, tab switching, or force-running a queued item.

## Goals

1. Add one unified per-conversation queue for both `busy` and `offline` cases.
2. Allow users to queue multiple requests, edit or delete pending items, and reorder them.
3. Support `Cancel current & run now` for a queued item where transcript safety allows it.
4. Persist queued items locally so they survive refresh, restart, and route/tab switches.
5. Keep WebUI and extension behavior aligned through shared `apps/packages/ui` state and components.

## Non-Goals

1. Building a server-backed cross-device request queue.
2. Running queued requests after the WebUI tab or extension chat surface is closed.
3. Adding a full jobs admin UI or cost accounting system.
4. Reworking chat persistence/storage beyond what is needed for queue safety.

## User Decisions Captured During Brainstorming

1. Scope: one unified queue for both `request already running` and `offline/disconnected`.
2. Snapshot level: hybrid snapshot, not text-only and not full raw UI state.
3. Execution context: queued items run against the latest conversation state at execution time.
4. Force-run semantics: the interrupted turn should be removed, not preserved as a partial transcript.
5. Persistence: the queue should survive refreshes, tab switches, and browser restarts on the local device.

## Design Summary

Use a shared client-side queue domain model in `apps/packages/ui` and treat the queue as part of the active conversation state.

Key decisions:

1. Queue scope is per conversation/tab, not global across the application.
2. The live queue is owned by the shared chat store, then serialized through existing surface-specific persistence:
   - WebUI: playground session persistence
   - Extension: sidepanel tab snapshots
3. Only one request can be active per conversation at a time.
4. Queue drain is automatic while the conversation surface is open, connected, authenticated, and not manually paused by an error condition.
5. Pending items remain fully editable until dispatch begins.

## Queue Data Model

Replace the current `{ message, image }[]` queue payload with a richer `QueuedRequest` model.

Required fields:

- `id`
  - stable local queue row id
- `clientRequestId`
  - stable id used to avoid local duplicate dispatch on reconnect/retry
- `conversationId`
  - history id, server chat id, or sidepanel tab id, depending on surface state
- `promptText`
- `image`
- `attachments`
  - selected documents, uploaded files, context file references, or empty
- `sourceContext`
  - materialized ephemeral context captured at queue time when needed
  - examples: selected page text, page URL, active tab metadata, mention payloads
- `snapshot`
  - hybrid request settings captured at queue time
- `status`
  - `queued`, `blocked`, or `sending`
- `blockedReason`
  - `offline`, `auth`, `missing_attachment`, `server_backed_force_run_unsupported`, or similar
- `attemptCount`
- `createdAt`
- `updatedAt`

## Snapshot Contract

The hybrid snapshot should explicitly include the settings that materially change output and are already represented in shared store state.

Recommended snapshot contents:

- `selectedModel`
- `compareMode` and `compareSelectedModels` when enabled
- `chatMode`
- `selectedSystemPrompt`
- `selectedQuickPrompt`
- `selectedCharacter`
- `webSearch`
- `toolChoice`
- `useOCR`
- `messageSteeringMode`
- `messageSteeringForceNarrate`
- `documentContext`
- `selectedDocuments`
- `uploadedFiles` / `contextFiles` references or materialized safe metadata

Explicit exclusions:

- full conversation history
- transient render state
- live streaming chunks
- viewport/layout state

## UI Surfaces

### Shared behavior

Keep queue controls next to the composer instead of creating a separate route.

Composer rules:

1. When the chat is idle and healthy, the primary action stays `Send`.
2. When a request is streaming, the primary action becomes `Queue`.
3. When the app is offline or blocked on auth, the primary action becomes `Queue`.
4. Keyboard submit should follow the same visible mode and show a confirmation toast/banner when it queues instead of sends.

Queue affordances:

1. A compact queue strip above the composer shows count and next item summary.
2. `View queue` opens an inline drawer/panel, not a blocking modal.
3. Each row shows:
   - prompt preview
   - model/mode badges
   - attachment/source-context indicators
   - status badge
4. Each pending row supports:
   - `Edit`
   - `Delete`
   - `Move up`
   - `Move down`
   - `Run now`

### WebUI playground

Implement in the shared `PlaygroundForm` surface and persist through the existing playground session store.

### Extension sidepanel

Implement in the shared `Sidepanel` composer and persist through the existing sidepanel tab snapshot model.

## Dispatch Semantics

1. Queue order is FIFO by default.
2. `Run now` promotes the selected item to the front of the queue.
3. When the active request completes successfully, the next queued item dispatches automatically.
4. Reconnect/auth recovery resumes the queue one item at a time. It must not flood-dispatch the whole queue.
5. If dispatch fails before the request is accepted, the item returns to `blocked` or `queued` with visible retry state.
6. Editing is allowed only in `queued` and `blocked` states.

## Force-Run and Cancellation Rules

Desired product behavior remains: `Cancel current & run now`.

However, there is a safety caveat for server-backed chats:

- If the active turn has already been durably appended to `/api/v1/chats`, hard-removing it only in the UI would desync local and server state.

Design decision:

1. Treat the in-flight turn as provisional until completion where current plumbing allows it.
2. If a conversation is in a server-backed state and rollback is not available, the UI should degrade safely:
   - allow `Cancel current`
   - allow `Queue for next`
   - suppress destructive `Cancel current & run now` until rollback/delete is defined
3. Local/Dexie-backed chats can support the full `Cancel current & run now` flow in v1.

This preserves the requested workflow without introducing silent transcript divergence.

## Persistence Rules

### WebUI

- Extend `usePlaygroundSessionPersistence` / `usePlaygroundSessionStore` to serialize the richer queue state.
- Persist queue state locally.
- On restore, queued items come back as pending or blocked exactly as stored.
- Auto-drain resumes only when the chat surface is open and connection/auth are healthy.

### Extension

- Extend `SidepanelChatSnapshot` so queued requests are part of each tab snapshot.
- Restore queue state when switching tabs or reopening the sidepanel.
- The queue remains per tab/conversation rather than global across all sidepanel tabs.

### Attachment/source validation

- Revalidate attachment handles and ephemeral context before dispatch.
- If an attachment or source context cannot be resolved, keep the item in queue but mark it `blocked` with a visible repair action.

## Clear/Close Behavior

1. `Clear chat` must explicitly mention queued requests and offer:
   - clear transcript only
   - clear transcript and queued items
2. Closing a sidepanel tab with queued items must confirm whether to:
   - keep queued items with the tab snapshot
   - discard queued items
3. The safer default is to preserve queued items unless the user explicitly discards them.

## Failure Handling

Expected blocked reasons:

- offline / unreachable backend
- auth expired or invalid
- missing attachment
- missing ephemeral context
- server-backed force-run not supported
- selected model unavailable

UX rules:

1. Block reasons should be user-visible and actionable.
2. The queue panel should expose `Retry` or `Repair` instead of silently dropping items.
3. If a queued item becomes invalid because a model or attachment disappears, it remains in the queue until the user edits, repairs, or deletes it.

## Risks and Mitigations

1. Duplicate sends on reconnect/retry
   - Mitigation: use `clientRequestId` and local attempt tracking to avoid repeated local dispatch.
2. Server-backed transcript divergence
   - Mitigation: safe degradation for destructive force-run until rollback exists.
3. Context drift
   - Mitigation: use latest conversation execution semantics, but capture ephemeral source context at queue time and show snapshot badges in the queue UI.
4. UI surprise when send becomes queue
   - Mitigation: explicit button label/state changes and clear feedback when an item is queued.
5. Large local queues becoming expensive or confusing
   - Mitigation: apply a soft queue cap and show a lightweight warning for unusually large queues.

## Testing Strategy

### Unit / store / hook

- queue reducer/helper tests for add/edit/delete/reorder/promote/block/restore
- queue orchestration hook tests for:
  - auto-drain
  - reconnect resume
  - blocked attachment handling
  - clear-chat behavior

### Component

- Playground composer tests for explicit `Queue` mode and queue panel interactions
- Sidepanel composer tests for the same queue affordances
- shared queue panel tests for row actions and blocked states

### End-to-end

- extend extension `queued-messages.spec.ts` to cover:
  - queue while streaming
  - edit/delete pending item
  - promote item with `Run now`
- add WebUI queue workflow coverage for:
  - queue while busy
  - restore after refresh
  - reconnect resume

## Success Criteria

1. A user can queue multiple follow-up prompts while the current request is still running.
2. The same queue model works in WebUI and extension.
3. Pending queued items can be edited, deleted, and reordered before dispatch.
4. Local persistence restores the queue after refresh/restart.
5. Queue behavior is explicit and safe in server-backed conversations.
