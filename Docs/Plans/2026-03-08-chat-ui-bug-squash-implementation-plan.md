# Chat UI Bug Squash Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the shared chat UI so chat discovery, chat loading, chat switching, and chat mutations remain reliable under transient failures, stale metadata, and low-risk UX edge cases.

**Architecture:** Keep the current shared UI architecture and improve it incrementally. Treat the sidebar as discovery state, the active chat loader as the authority for the selected chat, and the API client as the place that owns stale-version recovery for chat-level mutations. Use one explicit sidebar return contract from `useServerChatHistory` so the list can distinguish `empty`, `stale-but-usable`, and `unavailable` without inventing ad hoc component logic. Add explicit UI state handling rather than reworking the full store model.

**Tech Stack:** TypeScript, React, Zustand, TanStack Query, Ant Design, Vitest

---

### Task 1: Preserve Sidebar Data On Recoverable Refresh Failures

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`

**Step 1: Write the failing test**

Add tests that lock in the exact hook contract for recoverable refresh failures. The hook must return:

```ts
{
  data: ServerChatHistoryItem[]
  sidebarRefreshState: "idle" | "ready" | "recoverable-error" | "hard-error"
  hasUsableData: boolean
  isShowingStaleData: boolean
}
```

Add one pure helper test and one hook-level test:

```ts
it("derives recoverable-error state when prior chat data is still usable", () => {
  const previous = mapServerChatHistoryItems([createChat(1), createChat(2)])
  const next = deriveServerChatHistoryViewState({
    previousData: previous,
    error: Object.assign(new Error("rate_limited"), { status: 429 })
  })

  expect(next.data).toEqual(previous)
  expect(next.sidebarRefreshState).toBe("recoverable-error")
  expect(next.hasUsableData).toBe(true)
  expect(next.isShowingStaleData).toBe(true)
})

it("keeps previously rendered chat rows visible after a recoverable refresh failure", async () => {
  // renderHook useServerChatHistory with a QueryClientProvider
  // first fetch resolves with chats, second fetch rejects with a recoverable error
  // assert result.current.data still contains the first chat list
  // assert result.current.sidebarRefreshState === "recoverable-error"
})

it("returns unavailable state when recoverable failure happens before any data was loaded", () => {
  const next = deriveServerChatHistoryViewState({
    previousData: [],
    error: new Error("The operation was aborted.")
  })

  expect(next.data).toEqual([])
  expect(next.sidebarRefreshState).toBe("recoverable-error")
  expect(next.hasUsableData).toBe(false)
  expect(next.isShowingStaleData).toBe(false)
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
```

Expected: FAIL because the hook does not yet expose the sidebar refresh contract and still returns `[]` on recoverable failures.

**Step 3: Write minimal implementation**

In `useServerChatHistory.ts`:

- add a small exported helper, for example `deriveServerChatHistoryViewState`
- preserve previous data when recoverable failures happen and prior data exists
- expose the exact sidebar refresh contract described above
- avoid returning a fresh successful empty result when the latest refresh failed

Minimal shape:

```ts
export const deriveServerChatHistoryViewState = ({
  previousData,
  error
}: {
  previousData: ServerChatHistoryItem[]
  error: unknown
}) => ({
  data: previousData,
  sidebarRefreshState: "recoverable-error" as const,
  hasUsableData: previousData.length > 0,
  isShowingStaleData: previousData.length > 0
})
```

Then wire the hook to return that status instead of silently replacing the list with a fresh empty success state. Keep the return contract stable so `ServerChatList` can rely on it directly.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useServerChatHistory.ts apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
git commit -m "fix(chat-ui): preserve sidebar chats on recoverable refresh failures"
```

### Task 2: Make Selected-Chat Loading End In Loaded Or Failed State

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/store/option/types.ts`
- Modify: `apps/packages/ui/src/store/option/slices/server-chat-slice.ts`
- Modify: `apps/packages/ui/src/store/option/slices/core-slice.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts`
- Test: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx`

**Step 1: Write the failing test**

Add tests for two behaviors:

```ts
it("ignores stale load completion after a newer chat selection wins", async () => {
  // select chat-a, then chat-b, resolve chat-a last
  // assert only chat-b messages are committed
})

it("records a failed load state instead of leaving the pane blank", async () => {
  // force getChat/listChatMessages to reject
  // assert serverChatLoadState === "failed"
  // assert an error message is available for rendering
})
```

For the component-level test, render `PlaygroundChat` with a failed selected-chat state and assert visible failure copy instead of an empty shell.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx
```

Expected: FAIL because the store does not yet carry an explicit selected-chat load state and the pane does not render a dedicated failed state.

**Step 3: Write minimal implementation**

In `server-chat-slice.ts`, add state like:

```ts
serverChatLoadState: "idle" | "loading" | "loaded" | "failed"
serverChatLoadError: string | null
```

In `useSelectServerChat.ts`:

- set `serverChatLoadState` to `"loading"`
- clear previous `serverChatLoadError`
- keep the current selected chat target authoritative

In `useServerChatLoader.ts`:

- set `"loaded"` only when the current request still matches the selected chat
- on non-abort failure, set `"failed"` and store a user-facing error string
- avoid committing stale results from older aborted or superseded loads

In `PlaygroundChat`, render a minimal failure state when:

- a server chat is selected
- the loader state is `"failed"`

In `types.ts` and `core-slice.ts`:

- thread the new fields through the store type definitions
- make sure local-history switches clear the new selected-chat load state and load error alongside the existing server-chat fields

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/option/types.ts apps/packages/ui/src/store/option/slices/server-chat-slice.ts apps/packages/ui/src/store/option/slices/core-slice.ts apps/packages/ui/src/hooks/chat/useSelectServerChat.ts apps/packages/ui/src/hooks/chat/useServerChatLoader.ts apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx
git commit -m "fix(chat-ui): add explicit selected-chat load and failure states"
```

### Task 3: Stop Settings Sync From Bumping Chat Versions When Nothing Changed

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/services/chat-settings.ts`
- Create: `apps/packages/ui/src/services/__tests__/chat-settings.sync.test.ts`

**Step 1: Write the failing test**

Add tests that prove settings sync is a no-op when local and remote values are already equivalent:

```ts
it("does not push chat settings back to the server when merged settings are unchanged", async () => {
  // local settings and remote settings are semantically identical
  // assert updateChatSettings is not called
})

it("pushes chat settings only when the merged result differs from the remote copy", async () => {
  // local settings contain a newer meaningful value
  // assert updateChatSettings is called once
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/chat-settings.sync.test.ts
```

Expected: FAIL because `syncChatSettingsForServerChat` currently writes whenever the merged timestamp is newer, even if the merged settings payload is effectively unchanged.

**Step 3: Write minimal implementation**

In `chat-settings.ts`:

- add a small equivalence helper for normalized settings payloads
- compare the merged settings against the remote settings before calling `updateChatSettings`
- keep the local cache write behavior, but no-op the server write when there is no meaningful difference

Minimal pattern:

```ts
if (remoteSettings && areEquivalentChatSettings(merged, remoteSettings)) {
  await saveChatSettingsForKey(serverKey, merged)
  return merged
}
```

This task addresses the root cause that can churn chat `version` during load even when nothing user-visible changed.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/chat-settings.sync.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/chat-settings.ts apps/packages/ui/src/services/__tests__/chat-settings.sync.test.ts
git commit -m "fix(chat-ui): avoid no-op server chat settings writes"
```

### Task 4: Add Stale-Version Recovery For Chat Mutations In The API Client

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Test: `apps/packages/ui/src/services/__tests__/tldw-api-client.chat-trash.test.ts`
- Create: `apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts`

**Step 1: Write the failing test**

Add tests for one-retry stale-version recovery:

```ts
it("fetches the latest chat version and retries delete once after conflict", async () => {
  // first DELETE => 409
  // GET /api/v1/chats/:id => version 7
  // second DELETE => success
})

it("fetches current version before restore when expectedVersion is omitted", async () => {
  // GET /api/v1/chats/:id => version 4
  // POST /restore?expected_version=4 => success
})

it("retries updateChat once with the latest version after conflict", async () => {
  // first PUT => 409
  // GET chat => latest version
  // second PUT => success
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.chat-trash.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts
```

Expected: FAIL because delete and restore do not currently fetch-and-retry, and update only prefetches opportunistically.

**Step 3: Write minimal implementation**

In `TldwApiClient.ts`:

- add a small internal helper for `isVersionConflictError`
- add a helper that fetches current chat metadata with `getChat(id)`
- update `deleteChat`, `restoreChat`, and `updateChat` to retry once on conflict

Minimal pattern:

```ts
if (isVersionConflictError(error) && !hasRetried) {
  const latest = await this.getChat(cid)
  return await retryWithVersion(latest.version)
}
```

Keep the retry count at exactly one.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.chat-trash.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-trash.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts
git commit -m "fix(chat-ui): retry chat mutations once on version conflict"
```

### Task 5: Surface Distinct Sidebar States And Conflict-Specific Mutation Feedback

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Common/ChatSidebar/ServerChatList.tsx`
- Create: `apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ServerChatList.reliability.test.tsx`

**Step 1: Write the failing test**

Add component tests for:

```tsx
it("shows a recoverable refresh warning when old chat data is still usable", async () => {
  // mock hook => data present + sidebarRefreshState "recoverable-error" + isShowingStaleData true
  // assert warning copy is rendered
})

it("shows an unavailable message instead of an empty state when refresh failed without usable data", async () => {
  // mock hook => [] + sidebarRefreshState "recoverable-error" + hasUsableData false
  // assert not 'No server chats yet'
})

it("shows conflict-specific delete feedback when delete still fails after retry", async () => {
  // mock deleteChat => throws version conflict
  // assert message references chat changed on server
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ServerChatList.reliability.test.tsx
```

Expected: FAIL because the sidebar currently does not render a recoverable-warning state and mutation feedback is generic.

**Step 3: Write minimal implementation**

In `ServerChatList.tsx`:

- read the exact sidebar contract returned by `useServerChatHistory`
- render an inline warning when usable cached data is being shown after refresh failure
- render a distinct unavailable state when there is no usable data
- detect version-conflict errors in delete, restore, rename, and topic update callbacks
- swap generic mutation error copy for conflict-aware messages where relevant

Prefer to reuse an existing version-conflict detection pattern already present elsewhere in the UI if it fits cleanly, instead of inventing a fourth regex implementation in the codebase.

Minimal conflict copy example:

```ts
message.error(
  isVersionConflictError(err)
    ? t("common:chatChangedRetryFailed", { defaultValue: "This chat changed on the server. Refresh and try again." })
    : t("common:deleteChatError", { defaultValue: "Failed to move chat to trash." })
)
```

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ServerChatList.reliability.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/ChatSidebar/ServerChatList.tsx apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ServerChatList.reliability.test.tsx
git commit -m "fix(chat-ui): clarify sidebar refresh and mutation failure states"
```

### Task 6: Final Verification And Cleanup

**Status:** In Progress

**Files:**
- Modify: `Docs/Plans/2026-03-08-chat-ui-bug-squash-design.md` only if implementation reality requires minor notes
- Verify: touched frontend files from Tasks 1-5

**Step 1: Run the focused frontend test suite**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts \
  apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.sync.test.ts \
  apps/packages/ui/src/services/__tests__/tldw-api-client.chat-trash.test.ts \
  apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts \
  apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ServerChatList.reliability.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx
```

Expected: PASS

**Step 2: Run one broader chat-related safety suite**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.search.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.per-model-routing.integration.test.tsx apps/packages/ui/src/hooks/chat/__tests__/useChatActions.error-recovery.guard.test.ts
```

Expected: PASS

**Step 3: Confirm no unintended file drift**

Run:

```bash
git status --short
```

Expected: only intended implementation files remain changed.

**Step 4: Commit final polish if needed**

```bash
git add <touched-files>
git commit -m "test(chat-ui): verify bug squash regression coverage"
```

**Step 5: Prepare review handoff**

Document:

- which user complaints were directly covered
- which remaining risks were intentionally left out of scope
- which tests prove the fixes

Bandit note: this plan is frontend-only unless implementation introduces Python changes. If Python files are touched during execution, run Bandit on the touched Python scope before completion.
