# Unified Chat Request Queue for WebUI + Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current offline-only queued-message behavior with a shared, persistent per-conversation request queue that works for both busy and offline states in WebUI and extension chat surfaces.

**Architecture:** Add a shared queue domain model in `apps/packages/ui`, expose queue orchestration through a shared chat hook, and integrate that hook into both `PlaygroundForm` and sidepanel composer flows. Persist queue state through the existing WebUI playground session store and sidepanel tab snapshot store, then prove parity with shared component tests plus WebUI/extension E2E coverage.

**Tech Stack:** TypeScript, React, Zustand, existing `apps/packages/ui` chat hooks/components, Vitest, Playwright, extension locale sync script.

---

### Task 1: Replace the Flat Offline Queue With a Shared Queue Domain Model

**Files:**
- Create: `apps/packages/ui/src/utils/chat-request-queue.ts`
- Create: `apps/packages/ui/src/utils/__tests__/chat-request-queue.test.ts`
- Modify: `apps/packages/ui/src/store/option/types.ts`
- Modify: `apps/packages/ui/src/store/option/slices/core-slice.ts`
- Modify: `apps/packages/ui/src/store/playground-session.tsx`
- Modify: `apps/packages/ui/src/store/sidepanel-chat-tabs.tsx`

**Step 1: Write the failing test**

```ts
// apps/packages/ui/src/utils/__tests__/chat-request-queue.test.ts
import {
  buildQueuedRequest,
  moveQueuedRequestToFront,
  blockQueuedRequest
} from "@/utils/chat-request-queue"

it("promotes the selected queued request while preserving the remaining order", () => {
  const a = buildQueuedRequest({ promptText: "first" })
  const b = buildQueuedRequest({ promptText: "second" })
  const c = buildQueuedRequest({ promptText: "third" })

  const reordered = moveQueuedRequestToFront([a, b, c], c.id)

  expect(reordered.map((item) => item.promptText)).toEqual([
    "third",
    "first",
    "second"
  ])
})

it("marks a queued request blocked without losing its snapshot", () => {
  const item = buildQueuedRequest({
    promptText: "needs repair",
    snapshot: { selectedModel: "gpt-4o-mini", chatMode: "normal" }
  })

  const blocked = blockQueuedRequest(item, "missing_attachment")

  expect(blocked.status).toBe("blocked")
  expect(blocked.snapshot.selectedModel).toBe("gpt-4o-mini")
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/utils/__tests__/chat-request-queue.test.ts`

Expected: FAIL because `chat-request-queue.ts` and the richer queue types do not exist yet.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/utils/chat-request-queue.ts
import { generateID } from "@/db/dexie/helpers"

export type QueueStatus = "queued" | "blocked" | "sending"

export type QueuedRequestSnapshot = {
  selectedModel: string | null
  chatMode: "normal" | "rag" | "vision"
  webSearch?: boolean
}

export type QueuedRequest = {
  id: string
  clientRequestId: string
  promptText: string
  image: string
  attachments: unknown[]
  sourceContext: Record<string, unknown> | null
  snapshot: QueuedRequestSnapshot
  status: QueueStatus
  blockedReason: string | null
  attemptCount: number
  createdAt: number
  updatedAt: number
}

export const buildQueuedRequest = (
  partial: Partial<QueuedRequest> & { promptText: string }
): QueuedRequest => {
  const now = Date.now()
  return {
    id: partial.id ?? generateID(),
    clientRequestId: partial.clientRequestId ?? generateID(),
    promptText: partial.promptText,
    image: partial.image ?? "",
    attachments: partial.attachments ?? [],
    sourceContext: partial.sourceContext ?? null,
    snapshot:
      partial.snapshot ?? { selectedModel: null, chatMode: "normal" },
    status: partial.status ?? "queued",
    blockedReason: partial.blockedReason ?? null,
    attemptCount: partial.attemptCount ?? 0,
    createdAt: partial.createdAt ?? now,
    updatedAt: partial.updatedAt ?? now
  }
}

export const moveQueuedRequestToFront = (
  queue: QueuedRequest[],
  requestId: string
) => {
  const target = queue.find((item) => item.id === requestId)
  if (!target) return queue
  return [target, ...queue.filter((item) => item.id !== requestId)]
}

export const blockQueuedRequest = (
  item: QueuedRequest,
  blockedReason: string
): QueuedRequest => ({
  ...item,
  status: "blocked",
  blockedReason,
  updatedAt: Date.now()
})
```

Also update the existing option store types and persistence models so they reference `QueuedRequest[]` instead of `{ message, image }[]`.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/utils/__tests__/chat-request-queue.test.ts`

Expected: PASS, and the store/persistence types compile with the richer queue model.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/utils/chat-request-queue.ts apps/packages/ui/src/utils/__tests__/chat-request-queue.test.ts apps/packages/ui/src/store/option/types.ts apps/packages/ui/src/store/option/slices/core-slice.ts apps/packages/ui/src/store/playground-session.tsx apps/packages/ui/src/store/sidepanel-chat-tabs.tsx
git commit -m "feat(chat): add shared queued request domain model"
```

### Task 2: Add Shared Queue Orchestration for Dispatch, Retry, and Clear Semantics

**Files:**
- Create: `apps/packages/ui/src/hooks/chat/useQueuedRequests.ts`
- Create: `apps/packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx`
- Modify: `apps/packages/ui/src/hooks/useMessageOption.tsx`
- Modify: `apps/packages/ui/src/hooks/useMessage.tsx`
- Modify: `apps/packages/ui/src/hooks/chat/useClearChat.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx
import { renderHook, act } from "@testing-library/react"
import { useQueuedRequests } from "@/hooks/chat/useQueuedRequests"
import { buildQueuedRequest } from "@/utils/chat-request-queue"

it("promotes a queued request to the front and stops streaming before run-now", async () => {
  const stopStreamingRequest = vi.fn()
  const queue = [
    buildQueuedRequest({ promptText: "one" }),
    buildQueuedRequest({ promptText: "two" })
  ]
  const setQueue = vi.fn()

  const { result } = renderHook(() =>
    useQueuedRequests({
      isConnectionReady: true,
      isStreaming: true,
      queue,
      setQueue,
      sendQueuedRequest: vi.fn(),
      stopStreamingRequest
    })
  )

  await act(async () => {
    await result.current.runNow(queue[1].id)
  })

  expect(stopStreamingRequest).toHaveBeenCalledTimes(1)
  expect(setQueue).toHaveBeenCalledWith([queue[1], queue[0]])
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx`

Expected: FAIL because `useQueuedRequests` does not exist and the current chat hooks do not expose the required orchestration API.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/hooks/chat/useQueuedRequests.ts
import React from "react"
import { buildQueuedRequest, moveQueuedRequestToFront } from "@/utils/chat-request-queue"

export function useQueuedRequests(opts: {
  isConnectionReady: boolean
  isStreaming: boolean
  queue: QueuedRequest[]
  setQueue: (queue: QueuedRequest[]) => void
  sendQueuedRequest: (item: QueuedRequest) => Promise<void>
  stopStreamingRequest: () => void
}) {
  const enqueue = React.useCallback(
    (partial: Omit<QueuedRequest, "id" | "clientRequestId" | "status" | "blockedReason" | "attemptCount" | "createdAt" | "updatedAt"> & { promptText: string }) => {
      opts.setQueue([...opts.queue, buildQueuedRequest(partial)])
    },
    [opts]
  )

  const runNow = React.useCallback(
    async (requestId: string) => {
      const reordered = moveQueuedRequestToFront(opts.queue, requestId)
      opts.setQueue(reordered)
      if (opts.isStreaming) {
        opts.stopStreamingRequest()
      }
      return reordered[0] ?? null
    },
    [opts]
  )

  const flushNext = React.useCallback(async () => {
    const next = opts.queue[0]
    if (!next || opts.isStreaming || !opts.isConnectionReady) return
    await opts.sendQueuedRequest(next)
  }, [opts])

  return { enqueue, runNow, flushNext }
}
```

Then thread the hook through `useMessageOption` / `useMessage` so both chat surfaces can share the same queue orchestration instead of hand-rolled queue loops.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx`

Expected: PASS, with clear-chat behavior updated to preserve or discard queued requests intentionally instead of always wiping them silently.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/chat/useQueuedRequests.ts apps/packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx apps/packages/ui/src/hooks/useMessageOption.tsx apps/packages/ui/src/hooks/useMessage.tsx apps/packages/ui/src/hooks/chat/useClearChat.ts apps/packages/ui/src/hooks/chat/useChatActions.ts
git commit -m "feat(chat): add shared queued request orchestration"
```

### Task 3: Build a Shared Queue Panel and Integrate It Into WebUI Playground

**Files:**
- Create: `apps/packages/ui/src/components/Common/ChatQueuePanel.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/ChatQueuePanel.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/hooks/usePlaygroundSessionPersistence.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/playground.json`
- Test: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx
it("shows queue mode while streaming and lets the user edit a queued request", async () => {
  render(<PlaygroundForm droppedFiles={[]} />)

  expect(screen.getByRole("button", { name: /queue/i })).toBeInTheDocument()
  expect(screen.getByText(/next:/i)).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /run now/i })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx`

Expected: FAIL because the playground composer still renders the old offline-only banner and has no shared queue panel.

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Common/ChatQueuePanel.tsx
export const ChatQueuePanel = ({
  queue,
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  onRunNow
}: {
  queue: QueuedRequest[]
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onMoveUp: (id: string) => void
  onMoveDown: (id: string) => void
  onRunNow: (id: string) => void
}) => {
  if (queue.length === 0) return null
  return (
    <section aria-label="Queued requests">
      <p>{queue.length} queued</p>
      <p>{`Next: ${queue[0]?.promptText ?? ""}`}</p>
      {queue.map((item) => (
        <article key={item.id}>
          <span>{item.promptText}</span>
          <button onClick={() => onRunNow(item.id)}>Run now</button>
        </article>
      ))}
    </section>
  )
}
```

Update `PlaygroundForm` so busy/offline states show explicit `Queue` behavior instead of silently overloading `Send`, and persist the richer queue data through `usePlaygroundSessionPersistence`.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Common/__tests__/ChatQueuePanel.test.tsx ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx`

Expected: PASS, with the playground surface showing the shared queue UI and preserving queue state in the session store.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/ChatQueuePanel.tsx apps/packages/ui/src/components/Common/__tests__/ChatQueuePanel.test.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx apps/packages/ui/src/hooks/usePlaygroundSessionPersistence.tsx apps/packages/ui/src/assets/locale/en/playground.json
git commit -m "feat(chat): add queued request panel to playground"
```

### Task 4: Integrate the Shared Queue Into the Extension Sidepanel and Tab Snapshots

**Files:**
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/QueuedMessagesBanner.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-chat.tsx`
- Modify: `apps/packages/ui/src/store/sidepanel-chat-tabs.tsx`
- Test: `apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx
it("restores a queued request from the active sidepanel tab snapshot and exposes run-now actions", async () => {
  render(<SidepanelForm dropedFile={undefined} />)

  expect(screen.getByRole("button", { name: /run now/i })).toBeInTheDocument()
  expect(screen.getByText(/queued requests/i)).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx`

Expected: FAIL because the sidepanel still expects the old `{ message, image }[]` banner-only queue model.

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Sidepanel/Chat/QueuedMessagesBanner.tsx
import { ChatQueuePanel } from "@/components/Common/ChatQueuePanel"

export const QueuedMessagesBanner = (props: {
  queue: QueuedRequest[]
  onRunNow: (id: string) => void
  onDelete: (id: string) => void
}) => {
  return (
    <ChatQueuePanel
      queue={props.queue}
      onEdit={() => {}}
      onDelete={props.onDelete}
      onMoveUp={() => {}}
      onMoveDown={() => {}}
      onRunNow={props.onRunNow}
    />
  )
}
```

Update sidepanel tab snapshots to store the richer queue model, wire `Cancel current & run now` through the shared queue orchestration hook, and add the close/clear confirmations that mention queued requests explicitly.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx`

Expected: PASS, with sidepanel tab switching preserving the queue and sidepanel UI using the same queue semantics as WebUI.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Sidepanel/Chat/form.tsx apps/packages/ui/src/components/Sidepanel/Chat/QueuedMessagesBanner.tsx apps/packages/ui/src/routes/sidepanel-chat.tsx apps/packages/ui/src/store/sidepanel-chat-tabs.tsx apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx
git commit -m "feat(chat): add queued request parity to sidepanel chat"
```

### Task 5: Add Cross-Surface Regression Coverage, Sync Locales, and Verify the Whole Flow

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/chat-queued-requests.spec.ts`
- Modify: `apps/extension/tests/e2e/queued-messages.spec.ts`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `apps/extension/package.json`
- Generated by command: `apps/packages/ui/src/public/_locales/*`

**Step 1: Write the failing test**

```ts
// apps/tldw-frontend/e2e/workflows/chat-queued-requests.spec.ts
import { test, expect } from "../utils/fixtures"

test("queues follow-up prompts while streaming and restores them after reload", async ({ authedPage }) => {
  await authedPage.goto("/chat")
  await authedPage.getByRole("textbox").fill("First request")
  await authedPage.getByRole("button", { name: /send/i }).click()

  await authedPage.getByRole("textbox").fill("Second request")
  await authedPage.getByRole("button", { name: /queue/i }).click()

  await expect(authedPage.getByText(/1 queued/i)).toBeVisible()
  await authedPage.reload()
  await expect(authedPage.getByText(/1 queued/i)).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/chat-queued-requests.spec.ts --reporter=line`

Run: `cd apps/extension && bunx playwright test tests/e2e/queued-messages.spec.ts --reporter=line`

Expected: FAIL because WebUI has no queue workflow spec yet and extension tests still assert only the old offline queue behavior.

**Step 3: Write minimal implementation**

```json
// apps/tldw-frontend/package.json
"e2e:chat-queued-requests": "playwright test e2e/workflows/chat-queued-requests.spec.ts --reporter=line"
```

```json
// apps/extension/package.json
"test:e2e:queued-requests": "playwright test tests/e2e/queued-messages.spec.ts --reporter=line"
```

Then update the extension spec to cover:

- queue while streaming
- edit/delete queued item
- blocked attachment or offline recovery state
- `Run now` / safe fallback for server-backed chats

After the English locale changes, regenerate public locale mirrors:

Run: `cd apps/extension && bun run locales:sync`

**Step 4: Run verification to ensure it all passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/utils/__tests__/chat-request-queue.test.ts ../packages/ui/src/hooks/__tests__/useQueuedRequests.test.tsx ../packages/ui/src/components/Common/__tests__/ChatQueuePanel.test.tsx ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.queue.integration.test.tsx ../packages/ui/src/components/Sidepanel/Chat/__tests__/form.queue.contract.test.tsx`

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/chat-queued-requests.spec.ts --reporter=line`

Run: `cd apps/extension && bunx playwright test tests/e2e/queued-messages.spec.ts --reporter=line`

Expected: PASS across shared Vitest coverage, WebUI queue workflow coverage, and extension parity coverage.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/chat-queued-requests.spec.ts apps/extension/tests/e2e/queued-messages.spec.ts apps/tldw-frontend/package.json apps/extension/package.json apps/packages/ui/src/public/_locales
git commit -m "test(chat): add queued request parity coverage for webui and extension"
```
