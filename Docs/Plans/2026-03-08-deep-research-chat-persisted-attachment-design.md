# Deep Research Chat Persisted Attachment Design

## Summary

Persist one active attached deep-research context per saved server-backed chat thread, and auto-restore it when that thread is reopened.

This extends the current live-session attachment flow without changing transcript behavior:

- attachments stay out of chat history
- only saved server-backed chats persist attachments
- each chat stores at most one active attachment
- reopening the same chat auto-restores the attachment into the composer chip, baseline state, and outbound request path

## Goals

- Preserve the existing `Use in Chat` / preview-debug attachment model across reloads for saved chats.
- Keep persisted data bounded to the same chat-safe subset already used in live attachment state.
- Reuse the existing per-chat settings persistence seam instead of introducing a second attachment store.
- Ensure thread switching restores the correct attachment per chat and never leaks one chat's attachment into another.

## Non-Goals

- No persistence for temporary or local-only chats.
- No attachment history per thread.
- No transcript insertion or hidden message persistence.
- No change to the canonical research bundle or research run state.

## Approaches Considered

### 1. Persist in existing chat settings

Store one bounded `deepResearchAttachment` object inside the existing per-chat conversation settings JSON.

Pros:

- Reuses `GET/PUT /api/v1/chats/{chat_id}/settings`
- already user-scoped and versioned
- already mirrored through package-side `chat-settings` helpers
- matches the feature's ownership boundary: thread-local, out-of-band chat state

Cons:

- requires explicit validation for the new nested attachment payload

### 2. Add a dedicated chat attachment table

Create a first-class backend record keyed by `chat_id`.

Pros:

- clean domain separation

Cons:

- more schema/API work than the feature needs
- duplicates existing chat settings behavior for a single bounded object

### 3. Persist in client storage only

Use only local storage/Dexie keyed by `serverChatId`.

Pros:

- fastest implementation

Cons:

- not truly server-backed
- wrong for cross-session/device continuity

## Recommended Approach

Use existing conversation settings as the persistence seam.

The attachment is thread-local chat UI state, not transcript content and not research-core state. Existing conversation settings already own this kind of per-thread, out-of-band behavior and are mirrored between backend and package-side storage.

## Architecture

Persist a bounded `deepResearchAttachment` object inside conversation settings, and auto-restore it into `Playground` state when a saved chat thread loads.

Flow:

1. User attaches research via `Use in Chat` or applies edits from the request preview/debug modal.
2. `Playground` updates its existing active and baseline attached-context state.
3. If the thread has a `serverChatId`, the active attachment is mirrored into chat settings as `deepResearchAttachment`.
4. When a saved chat thread is opened or restored, the chat settings payload is loaded and the persisted attachment is restored into:
   - active attached context
   - baseline attached context
5. Removing the attachment clears `deepResearchAttachment` from chat settings.
6. Switching to another saved chat restores that thread's persisted attachment, or clears local attachment state if none exists.

## Data Contract

Persist only the bounded attached-context snapshot, not the full research bundle.

`deepResearchAttachment`:

- `run_id`
- `query`
- `question`
- `outline`
- `key_claims`
- `unresolved_questions`
- `verification_summary`
- `source_trust_summary`
- `research_url`
- `attached_at`
- `updatedAt`

### Validation Rules

Backend validation should enforce:

- no unknown keys inside `deepResearchAttachment`
- required identity fields are strings
- list fields stay bounded to the same caps as the live attachment builder
- summary objects only allow the compact count fields currently used by chat
- `updatedAt` must be an ISO timestamp string
- the existing overall chat-settings byte cap still applies

Frontend normalization should:

- accept only valid bounded attachment shape
- ignore malformed persisted attachment safely
- avoid crashing the thread on bad data
- strip malformed `deepResearchAttachment` values before any merge or write-back path
- clear malformed server-backed attachment on the next successful settings write

Top-level chat settings handling should also be tightened for this slice:

- do not rely on `ChatSettingsRecord & Record<string, unknown>` for the persisted attachment path
- make `deepResearchAttachment` an explicit typed field in the package-side settings model
- if other top-level settings remain permissive for compatibility, the persisted-attachment path must still use explicit normalization and explicit merge rules rather than blind object spread

## Integration Shape

### Backend

Use the existing chat settings endpoints:

- `GET /api/v1/chats/{chat_id}/settings`
- `PUT /api/v1/chats/{chat_id}/settings`

No new endpoint is required.

Extend `_validate_chat_settings_payload(...)` so it recognizes and validates `deepResearchAttachment`.

### Frontend

Use the existing package-side settings helpers:

- `apps/packages/ui/src/services/chat-settings.ts`
- `apps/packages/ui/src/hooks/chat/useChatSettingsRecord.ts`

`Playground.tsx` remains the live source of truth for the active session, but it gains persistence behavior:

- restore persisted attachment from reconciled server-scoped chat settings on saved-thread load
- persist active attachment on attach/apply/reset/remove
- clear persisted attachment on remove
- ignore persistence entirely for temporary/local chats

To avoid write churn, persistence happens only on committed attachment state changes:

- attach from bundle
- apply edits
- reset to baseline
- remove attachment

It must not persist on every keystroke in the preview/debug draft editor.

`deepResearchAttachment` also needs its own merge semantics:

- treat `deepResearchAttachment.updatedAt` as the authoritative timestamp for attachment merges
- do not let unrelated top-level `updatedAt` changes clobber a newer attachment snapshot
- merge the attachment field explicitly inside chat-settings reconciliation instead of letting whole-object winner-take-all behavior decide

## Error Handling

- Temporary or local chats: do not attempt persistence.
- Settings fetch failure: keep local attachment behavior only; do not block the thread.
- Settings update failure: keep the live local attachment, log/warn quietly, and allow later writes to reconcile.
- Malformed persisted attachment: ignore locally and overwrite/clear on the next valid save path.
- Saved-thread restore must wait for the reconciled server-scoped settings copy, not a pre-sync local snapshot.

This feature is additive convenience, not a chat-critical path. Persistence failures should degrade to the existing live-session behavior.

## Testing

### Backend

- chat settings accepts valid `deepResearchAttachment`
- unknown keys under `deepResearchAttachment` are rejected
- oversized attachment payload is rejected by settings limits
- get/update round-trip preserves the attachment shape
- attachment-specific merge semantics keep a newer `deepResearchAttachment.updatedAt` even when unrelated top-level settings changed later

### Frontend

- saved thread auto-restores persisted attachment into chip and baseline state
- removing attachment clears persisted settings entry
- switching between two saved chats restores the correct attachment per thread
- temporary chats never attempt persistence
- malformed persisted attachment is ignored safely
- preview/debug `Apply` persists the new active attachment, but draft keystrokes do not
- restore happens only after server-chat settings reconciliation, so stale pre-sync attachment state is not flashed into the wrong thread

## Risks

- write churn if persistence happens too often during editing
- race conditions on thread switch if restore and local clear happen out of order
- stale attachment leaking across chats if `serverChatId` guards are weak
- newer attachment snapshots being overwritten by unrelated chat-settings merges

## Mitigations

- persist only on committed state transitions
- key restore/clear effects strictly to `serverChatId`
- keep local active state authoritative once restored for the current session
- use explicit attachment normalization before merge/write so malformed values are stripped
- use explicit attachment merge rules keyed by `deepResearchAttachment.updatedAt`
- restore from the reconciled `server:` settings copy after `syncChatSettingsForServerChat(...)` has run

## Out of Scope

- attachment history per thread
- transcript persistence
- auto-refreshing attached context when the underlying research run changes later
- persistence for temporary/local chats
