# Chat Page Rate-Limit Lazy Hydration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce `/chat` and extension chat request bursts by moving optional data behind explicit engagement gates, removing implicit provider refreshes from the send path, and unifying server-chat hydration semantics.

**Architecture:** Add a shared chat-surface coordinator store in `apps/packages/ui` that owns visibility, engagement, freshness, and cooldown policy while leaving fetch logic in the existing hooks and services. Then refactor server history, MCP/audio probes, model validation, and server-chat hydration to opt into that policy, finishing with scoped persistence and request-budget regression tests.

**Tech Stack:** TypeScript, React, Zustand, TanStack Query, existing `apps/packages/ui` chat hooks and stores, Vitest, React Testing Library.

---

### Task 1: Add a Shared Chat-Surface Coordinator Store

**Files:**
- Create: `apps/packages/ui/src/store/chat-surface-coordinator.ts`
- Create: `apps/packages/ui/src/store/__tests__/chat-surface-coordinator.test.ts`
- Modify: `apps/packages/ui/src/components/Layouts/Layout.tsx`
- Modify: `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`

**Step 1: Write the failing test**

```ts
// apps/packages/ui/src/store/__tests__/chat-surface-coordinator.test.ts
import { describe, expect, it } from "vitest"
import {
  createChatSurfaceCoordinatorStore,
  shouldEnableOptionalResource
} from "@/store/chat-surface-coordinator"

describe("chat surface coordinator", () => {
  it("keeps server history disabled until the user engages the panel", () => {
    const store = createChatSurfaceCoordinatorStore()

    store.getState().setRouteContext({ routeId: "chat", surface: "webui" })
    store.getState().setPanelVisible("server-history", true)

    expect(
      shouldEnableOptionalResource(store.getState(), "server-history")
    ).toBe(false)

    store.getState().markPanelEngaged("server-history")

    expect(
      shouldEnableOptionalResource(store.getState(), "server-history")
    ).toBe(true)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/chat-surface-coordinator.test.ts`

Expected: FAIL because the coordinator store and helper do not exist yet.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/store/chat-surface-coordinator.ts
import { createStore } from "zustand/vanilla"

type OptionalPanelId =
  | "server-history"
  | "mcp-tools"
  | "audio-health"
  | "model-catalog"

type CoordinatorState = {
  routeId: string | null
  surface: "webui" | "extension" | null
  visiblePanels: Record<OptionalPanelId, boolean>
  engagedPanels: Record<OptionalPanelId, boolean>
  setRouteContext: (value: {
    routeId: string
    surface: "webui" | "extension"
  }) => void
  setPanelVisible: (panel: OptionalPanelId, visible: boolean) => void
  markPanelEngaged: (panel: OptionalPanelId) => void
}

export const createChatSurfaceCoordinatorStore = () =>
  createStore<CoordinatorState>((set) => ({
    routeId: null,
    surface: null,
    visiblePanels: {
      "server-history": false,
      "mcp-tools": false,
      "audio-health": false,
      "model-catalog": false
    },
    engagedPanels: {
      "server-history": false,
      "mcp-tools": false,
      "audio-health": false,
      "model-catalog": false
    },
    setRouteContext: (value) => set(value),
    setPanelVisible: (panel, visible) =>
      set((state) => ({
        visiblePanels: { ...state.visiblePanels, [panel]: visible }
      })),
    markPanelEngaged: (panel) =>
      set((state) => ({
        engagedPanels: { ...state.engagedPanels, [panel]: true }
      }))
  }))

export const shouldEnableOptionalResource = (
  state: CoordinatorState,
  panel: OptionalPanelId
) => Boolean(state.visiblePanels[panel] && state.engagedPanels[panel])
```

Wire the new store into layout and chat roots so WebUI and extension surfaces can report route context and panel engagement centrally.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/chat-surface-coordinator.test.ts`

Expected: PASS, with the chat roots able to toggle optional panel state without fetching anything yet.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/chat-surface-coordinator.ts apps/packages/ui/src/store/__tests__/chat-surface-coordinator.test.ts apps/packages/ui/src/components/Layouts/Layout.tsx apps/packages/ui/src/components/Common/ChatSidebar.tsx apps/packages/ui/src/components/Option/Playground/Playground.tsx
git commit -m "feat(chat): add chat surface coordinator policy store"
```

### Task 2: Split Server History Into Overview and Search Modes

**Files:**
- Modify: `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- Modify: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`
- Modify: `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- Modify: `apps/packages/ui/src/components/Common/ChatSidebar/ServerChatList.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/Sidebar.tsx`
- Create: `apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ChatSidebar.lazy-history.test.tsx`

**Step 1: Write the failing test**

```ts
// apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
it("does not fetch server chat history when overview mode is disabled", async () => {
  const listChatsWithMeta = vi.spyOn(tldwClient, "listChatsWithMeta")

  renderHook(() =>
    useServerChatHistory("", {
      enabled: false,
      mode: "overview"
    })
  )

  await waitFor(() => {
    expect(listChatsWithMeta).not.toHaveBeenCalled()
  })
})

it("uses a search-specific fetch path instead of overview pagination when search is active", async () => {
  const listChatsWithMeta = vi.spyOn(tldwClient, "listChatsWithMeta")

  renderHook(() =>
    useServerChatHistory("quota", {
      enabled: true,
      mode: "search"
    })
  )

  await waitFor(() => {
    expect(listChatsWithMeta).toHaveBeenCalledWith(
      expect.objectContaining({ query: "quota" }),
      expect.anything()
    )
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`

Expected: FAIL because `useServerChatHistory` does not support `mode`, engagement gating, or a dedicated search path.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/hooks/useServerChatHistory.ts
type UseServerChatHistoryOptions = {
  enabled?: boolean
  includeDeleted?: boolean
  deletedOnly?: boolean
  mode?: "overview" | "search"
}

const isSearchMode = options?.mode === "search"

const query = useQuery({
  queryKey: [
    "serverChatHistory",
    { includeDeleted, deletedOnly, mode: options?.mode ?? "overview", q: isSearchMode ? normalizedQuery : "" }
  ],
  enabled: isEnabled,
  queryFn: async ({ signal }) => {
    if (isSearchMode) {
      const response = await tldwClient.listChatsWithMeta(
        {
          limit: 50,
          offset: 0,
          ordering: "-updated_at",
          query: normalizedQuery
        },
        { signal }
      )
      return mapServerChatHistoryItems(response.chats)
    }

    const chats = await fetchAllServerChatPages(...)
    return mapServerChatHistoryItems(chats)
  }
})
```

Update both sidebars so:

- overview fetches only when the coordinator says the panel is engaged
- search switches the hook into explicit search mode instead of relying on page-one filtering
- badge counts stop depending on full overview data

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts ../packages/ui/src/components/Common/ChatSidebar/__tests__/ChatSidebar.lazy-history.test.tsx`

Expected: PASS, with overview mode idle until user engagement and search no longer depending on an all-pages sweep.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useServerChatHistory.ts apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts apps/packages/ui/src/components/Common/ChatSidebar.tsx apps/packages/ui/src/components/Common/ChatSidebar/ServerChatList.tsx apps/packages/ui/src/components/Sidepanel/Chat/Sidebar.tsx apps/packages/ui/src/components/Common/ChatSidebar/__tests__/ChatSidebar.lazy-history.test.tsx
git commit -m "feat(chat): gate server history overview and split search mode"
```

### Task 3: Gate MCP and Audio Probes Behind Explicit Engagement

**Files:**
- Modify: `apps/packages/ui/src/hooks/useMcpTools.tsx`
- Modify: `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useMcpTools.gating.test.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.gating.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/hooks/__tests__/useMcpTools.gating.test.tsx
it("does not poll MCP endpoints until the tools surface is engaged", async () => {
  const apiSendMock = vi.spyOn(apiSendModule, "apiSend")

  renderHook(() => useMcpTools({ enabled: false }))

  await waitFor(() => {
    expect(apiSendMock).not.toHaveBeenCalled()
  })
})

// apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.gating.test.tsx
it("does not probe audio health until voice UI is engaged", async () => {
  const apiSendMock = vi.spyOn(apiSendModule, "apiSend")

  renderHook(() => useTldwAudioStatus({ enabled: false }))

  await waitFor(() => {
    expect(apiSendMock).not.toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useMcpTools.gating.test.tsx ../packages/ui/src/hooks/__tests__/useTldwAudioStatus.gating.test.tsx`

Expected: FAIL because both hooks start queries as soon as capabilities say the feature exists.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/hooks/useMcpTools.tsx
export const useMcpTools = (options: { enabled?: boolean } = {}) => {
  const coordinatorEnabled = options.enabled ?? false
  const hasMcp = Boolean(capabilities?.hasMcp) && !loading
  const shouldQuery = hasMcp && coordinatorEnabled

  const healthQuery = useQuery({
    queryKey: ["mcp-health"],
    enabled: shouldQuery,
    ...
  })
  ...
}

// apps/packages/ui/src/hooks/useTldwAudioStatus.tsx
export const useTldwAudioStatus = (
  options: Options & { enabled?: boolean } = {}
) => {
  const shouldProbe = options.enabled === true

  const ttsHealthQuery = useQuery({
    enabled: hasTts && shouldProbe,
    ...
  })
  ...
}
```

Update `PlaygroundForm` so it marks the MCP tools panel or voice surface engaged before enabling those hooks, and render explicit `Not checked yet` or `Check availability` states instead of implying hard unavailability.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useMcpTools.gating.test.tsx ../packages/ui/src/hooks/__tests__/useTldwAudioStatus.gating.test.tsx`

Expected: PASS, with no MCP or audio health traffic until the user opens the relevant feature.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useMcpTools.tsx apps/packages/ui/src/hooks/useTldwAudioStatus.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/hooks/__tests__/useMcpTools.gating.test.tsx apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.gating.test.tsx
git commit -m "feat(chat): lazy-load MCP and audio probes"
```

### Task 4: Remove Implicit Provider Refresh From the Send Path

**Files:**
- Modify: `apps/packages/ui/src/hooks/useMessage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useMessage.model-refresh-policy.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/hooks/__tests__/useMessage.model-refresh-policy.test.tsx
it("does not force-refresh chat models on submit when the selected model is stale", async () => {
  const fetchChatModels = vi
    .spyOn(tldwServerModule, "fetchChatModels")
    .mockResolvedValue([{ model: "openrouter/test-model" }] as any)

  const { result } = renderHook(() => useMessage())

  await act(async () => {
    await result.current.onSubmit({
      message: "hello",
      image: ""
    })
  })

  expect(fetchChatModels).not.toHaveBeenCalledWith(
    expect.objectContaining({ forceRefresh: true })
  )
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useMessage.model-refresh-policy.test.tsx`

Expected: FAIL because the current send path can force provider refresh, including OpenRouter-sensitive refreshes.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/hooks/useMessage.tsx
const ensureSelectedChatModelIsAvailable = React.useCallback(
  async (selectedModelId: string) => {
    const models = await fetchChatModels({ returnEmpty: true })
    const availableIds = buildAvailableChatModelIds(models as any[])
    const unavailableModel = findUnavailableChatModel(
      [normalizeChatModelId(selectedModelId)],
      availableIds
    )

    if (!unavailableModel) {
      return true
    }

    notification.warning({
      message: t("error"),
      description: t(
        "playground:composer.modelPossiblyStale",
        "Selected model may be stale or unavailable. Refresh models or pick another model."
      )
    })
    return false
  },
  [notification, t]
)
```

Then add explicit `Refresh models` UI in `PlaygroundForm` that calls a manual single-flight refresh path with cooldown and user feedback.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/hooks/__tests__/useMessage.model-refresh-policy.test.tsx`

Expected: PASS, with send flow warning the user instead of silently forcing a provider refresh.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useMessage.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/hooks/__tests__/useMessage.model-refresh-policy.test.tsx
git commit -m "feat(chat): remove implicit provider refresh from submit path"
```

### Task 5: Make Server-Backed Conversation Loading Two-Phase and Canonical

**Files:**
- Modify: `apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- Modify: `apps/packages/ui/src/hooks/useMessage.tsx`
- Modify: `apps/tldw-frontend/extension/routes/sidepanel-chat.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx
it("renders transcript content before persona enrichment resolves", async () => {
  const slowPersona = deferredPromise()
  vi.spyOn(tldwClient, "getPersonaProfile").mockReturnValueOnce(
    slowPersona.promise as any
  )

  render(<PlaygroundChat />)

  await waitFor(() => {
    expect(screen.getByText("Server transcript message")).toBeInTheDocument()
  })

  expect(screen.queryByText("Persona display name")).not.toBeInTheDocument()

  slowPersona.resolve({ id: "persona-1", name: "Persona display name" })

  await waitFor(() => {
    expect(screen.getByText("Persona display name")).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx`

Expected: FAIL because transcript rendering still waits on assistant enrichment inside the current loader flow.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/hooks/chat/useServerChatLoader.ts
const list = await fetchAllServerChatMessages(...)
const mappedMessages = mapServerChatMessagesToPlaygroundMessages(...)

setHistory(...)
setMessages(mappedMessages)

void hydrateAssistantIdentity({
  assistantKind,
  assistantId,
  characterId
}).catch(() => null)
```

Also remove or simplify duplicate metadata hydration in `useMessage.tsx` and sidepanel route code so the canonical loader is the only path that owns transcript and minimal metadata loading for a selected server-backed conversation.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx`

Expected: PASS, with transcript content visible before persona or character enrichment completes.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/chat/useServerChatLoader.ts apps/packages/ui/src/hooks/chat/useSelectServerChat.ts apps/packages/ui/src/hooks/useMessage.tsx apps/tldw-frontend/extension/routes/sidepanel-chat.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.server-load-state.test.tsx
git commit -m "refactor(chat): make server chat hydration canonical and two-phase"
```

### Task 6: Scope Persisted Snapshots by Server and Auth Context

**Files:**
- Create: `apps/packages/ui/src/services/chat-surface-scope.ts`
- Create: `apps/packages/ui/src/services/__tests__/chat-surface-scope.test.ts`
- Modify: `apps/packages/ui/src/store/playground-session.tsx`
- Modify: `apps/packages/ui/src/hooks/usePlaygroundSessionPersistence.tsx`
- Modify: `apps/packages/ui/src/store/chat-surface-coordinator.ts`

**Step 1: Write the failing test**

```ts
// apps/packages/ui/src/services/__tests__/chat-surface-scope.test.ts
import { buildChatSurfaceScopeKey } from "@/services/chat-surface-scope"

it("changes the scope key when the server URL or auth mode changes", () => {
  expect(
    buildChatSurfaceScopeKey({
      serverUrl: "http://localhost:8000",
      authMode: "single-user",
      orgId: null,
      userId: null
    })
  ).not.toBe(
    buildChatSurfaceScopeKey({
      serverUrl: "https://prod.example.com",
      authMode: "multi-user",
      orgId: 7,
      userId: 42
    })
  )
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/chat-surface-scope.test.ts`

Expected: FAIL because no chat-surface scope helper exists and session persistence is not keyed to server/auth context.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/services/chat-surface-scope.ts
export const buildChatSurfaceScopeKey = (input: {
  serverUrl: string | null
  authMode: string | null
  orgId: number | null
  userId: number | null
}) =>
  [
    String(input.serverUrl || "").trim().toLowerCase(),
    String(input.authMode || "unknown"),
    input.orgId == null ? "org:none" : `org:${input.orgId}`,
    input.userId == null ? "user:none" : `user:${input.userId}`
  ].join("|")
```

Then extend playground session persistence so restored snapshots are ignored when their stored scope does not match the current server/auth context.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/chat-surface-scope.test.ts`

Expected: PASS, with persisted chat-surface snapshots now scoped the same way model caches already are.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/chat-surface-scope.ts apps/packages/ui/src/services/__tests__/chat-surface-scope.test.ts apps/packages/ui/src/store/playground-session.tsx apps/packages/ui/src/hooks/usePlaygroundSessionPersistence.tsx apps/packages/ui/src/store/chat-surface-coordinator.ts
git commit -m "feat(chat): scope chat snapshots by server and auth context"
```

### Task 7: Add Request-Budget Regression Tests for Initial Mount and First Send

**Files:**
- Create: `apps/packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Common/ChatSidebar.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx
it("does not call optional endpoints on initial chat mount", async () => {
  render(<Playground />)

  await waitFor(() => {
    expect(apiSend).not.toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/mcp/health" })
    )
    expect(apiSend).not.toHaveBeenCalledWith(
      expect.objectContaining({ path: "/api/v1/audio/health" })
    )
    expect(listChatsWithMeta).not.toHaveBeenCalled()
  })
})

it("does not force a provider refresh during the first successful send", async () => {
  render(<Playground />)

  await user.type(screen.getByPlaceholderText(/message/i), "hello")
  await user.click(screen.getByRole("button", { name: /send/i }))

  expect(fetchChatModels).not.toHaveBeenCalledWith(
    expect.objectContaining({ forceRefresh: true })
  )
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx`

Expected: FAIL because initial mount still triggers optional endpoints and the first-send path still reaches provider refresh behavior until the earlier tasks are complete.

**Step 3: Write minimal implementation**

```ts
// apps/packages/ui/src/components/Option/Playground/Playground.tsx
// No new fetch logic belongs here. The fix is to consume coordinator state
// and avoid mounting or enabling optional resources until the user engages
// them. The test should pass by wiring existing surfaces into the coordinator
// created in Task 1 and the hook changes from Tasks 2-4.
```

Tighten the Playground, form, and sidebar wiring until the test only sees conversation-critical requests on initial mount.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx`

Expected: PASS, proving the request-budget contract in a way future refactors can preserve.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx apps/packages/ui/src/components/Option/Playground/Playground.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/components/Common/ChatSidebar.tsx
git commit -m "test(chat): add request budget guards for lazy hydration"
```
