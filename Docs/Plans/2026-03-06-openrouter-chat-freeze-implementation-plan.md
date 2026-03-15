# OpenRouter Chat Freeze (/chat) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent Firefox-level page freezes during OpenRouter streaming on WebUI `/chat` while preserving correct final output.

**Architecture:** Add cooperative yielding in stream transport to prevent long queue-drain monopolization, throttle character-stream UI updates, and use a lightweight assistant render path while the active message is streaming. Keep transport semantics and final markdown fidelity unchanged.

**Tech Stack:** TypeScript, React, Vitest, WXT browser runtime messaging, TanStack/Playground UI components.

---

### Task 1: Add cooperative-yield regression tests for stream transport

**Skills:** @test-driven-development

**Files:**
- Modify: `apps/packages/ui/src/services/__tests__/background-proxy.test.ts`
- Reference: `apps/packages/ui/src/services/background-proxy.ts`

**Step 1: Write the failing test**

```ts
it("yields to the browser during high-frequency queue drain", async () => {
  let rafCalls = 0
  ;(globalThis as any).requestAnimationFrame = (cb: FrameRequestCallback) => {
    rafCalls += 1
    cb(performance.now())
    return rafCalls
  }

  // emit many synchronous chunks through mocked runtime port transport
  // then collect stream output
  const chunks: string[] = []
  for await (const chunk of bgStream({
    path: "/api/v1/chat/completions",
    method: "POST",
    body: { stream: true }
  })) {
    chunks.push(chunk)
  }

  expect(chunks.length).toBeGreaterThan(100)
  expect(rafCalls).toBeGreaterThan(0)
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts -t "yields to the browser during high-frequency queue drain"`
Expected: FAIL because no cooperative yield exists yet.

**Step 3: Write minimal implementation**

```ts
const STREAM_DRAIN_BATCH_LIMIT = 32
const STREAM_DRAIN_MAX_SLICE_MS = 12

const yieldToBrowser = async () => {
  if (typeof requestAnimationFrame === "function") {
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    return
  }
  await new Promise<void>((resolve) => setTimeout(resolve, 0))
}
```

Integrate this into the `bgStream(...)` queue-drain loop with counters/time budget.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts -t "yields to the browser during high-frequency queue drain"`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/background-proxy.ts apps/packages/ui/src/services/__tests__/background-proxy.test.ts
git commit -m "fix(chat): add cooperative yielding to stream queue drain"
```

### Task 2: Preserve transport correctness with cooperative yielding

**Skills:** @test-driven-development

**Files:**
- Modify: `apps/packages/ui/src/services/__tests__/background-proxy.test.ts`
- Reference: `apps/packages/ui/src/services/background-proxy.ts`

**Step 1: Write failing/coverage tests**

```ts
it("preserves chunk ordering when cooperative yielding is active", async () => {
  const values: string[] = []
  for await (const chunk of bgStream({ path: "/api/v1/chat/completions", method: "POST", body: { stream: true } })) {
    values.push(chunk)
  }
  expect(values).toEqual([
    '{"choices":[{"delta":{"content":"A"}}]}',
    '{"choices":[{"delta":{"content":"B"}}]}',
    '{"choices":[{"delta":{"content":"C"}}]}'
  ])
})

it("still honors abort promptly during queue drain", async () => {
  const controller = new AbortController()
  const seen: string[] = []
  await expect(async () => {
    for await (const chunk of bgStream({
      path: "/api/v1/chat/completions",
      method: "POST",
      body: { stream: true },
      abortSignal: controller.signal
    })) {
      seen.push(chunk)
      controller.abort()
    }
  }).rejects.toThrow(/Aborted/i)
})
```

**Step 2: Run tests to verify failures**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts -t "preserves chunk ordering|still honors abort promptly"`
Expected: At least one FAIL before implementation adjustments.

**Step 3: Implement minimal correctness fixes**

```ts
if (queue.length > 0) {
  yield queue.shift() as string
  drainedCount += 1
  if (drainedCount >= STREAM_DRAIN_BATCH_LIMIT || Date.now() - sliceStartedAt >= STREAM_DRAIN_MAX_SLICE_MS) {
    await yieldToBrowser()
    drainedCount = 0
    sliceStartedAt = Date.now()
  }
}
```

Ensure abort checks remain effective.

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts`
Expected: PASS for stream transport suite.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/background-proxy.ts apps/packages/ui/src/services/__tests__/background-proxy.test.ts
git commit -m "test(chat): guard stream ordering and abort with cooperative yield"
```

### Task 3: Throttle character-stream message updates in chat actions

**Skills:** @test-driven-development

**Files:**
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Test: `apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx`
- Reference: `apps/packages/ui/src/hooks/chat-modes/chatModePipeline.ts`

**Step 1: Write failing integration test**

```tsx
it("coalesces rapid character stream chunks into bounded UI updates", async () => {
  // mock streamCharacterChatCompletion to emit 200 tiny chunks rapidly
  // trigger onSubmit in character mode
  // assert final message is complete
  // assert setMessages updates are significantly fewer than chunk count
  expect(setMessagesCallCount).toBeLessThan(80)
  expect(finalAssistantMessage).toContain("complete response")
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx`
Expected: FAIL due current per-token updates.

**Step 3: Write minimal implementation**

```ts
const STREAMING_UPDATE_INTERVAL_MS = 80
let streamingTimer: ReturnType<typeof setTimeout> | null = null
let pendingText = ""
let pendingReasoning = 0

const scheduleStreamingUpdate = (text: string, reasoning: number) => {
  pendingText = text
  pendingReasoning = reasoning
  if (streamingTimer) return
  streamingTimer = setTimeout(() => {
    streamingTimer = null
    setMessages((prev) => prev.map((m) => m.id === generateMessageId ? updateActiveVariant(m, { message: pendingText, reasoning_time_taken: pendingReasoning }) : m))
  }, STREAMING_UPDATE_INTERVAL_MS)
}
```

Use `scheduleStreamingUpdate` inside the character stream loop; flush before final completion update.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/chat/useChatActions.ts apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx
git commit -m "fix(chat): throttle character stream UI updates"
```

### Task 4: Add lightweight rendering for active streaming assistant message

**Skills:** @test-driven-development

**Files:**
- Modify: `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Test: `apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx`

**Step 1: Write failing component tests**

```tsx
it("renders lightweight plain text for active streaming assistant", () => {
  render(<PlaygroundMessage {...baseProps} isBot isStreaming currentMessageIndex={2} totalMessages={3} message="hello▋" />)
  expect(screen.getByTestId("playground-streaming-plain-text")).toHaveTextContent("hello▋")
  expect(screen.queryByTestId("mock-markdown")).not.toBeInTheDocument()
})

it("returns to markdown rendering after stream completes", () => {
  render(<PlaygroundMessage {...baseProps} isBot isStreaming={false} isProcessing={false} message="final" />)
  expect(screen.getByTestId("mock-markdown")).toBeInTheDocument()
})
```

**Step 2: Run tests to verify failures**

Run: `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx`
Expected: FAIL because lightweight branch does not exist.

**Step 3: Write minimal implementation**

```tsx
const shouldRenderStreamingLite =
  props.isBot &&
  isLastMessage &&
  props.isStreaming &&
  !errorPayload &&
  !renderGreetingMarkdown

if (shouldRenderStreamingLite) {
  return (
    <p data-testid="playground-streaming-plain-text" className={`whitespace-pre-wrap ${assistantTextClass}`}>
      {props.message}
    </p>
  )
}
```

Keep existing markdown path untouched for non-streaming messages.

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/Playground/Message.tsx apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx
git commit -m "fix(chat): use lightweight render for active streaming assistant"
```

### Task 5: End-to-end regression checks for `/chat` OpenRouter-like chunk bursts

**Skills:** @verification-before-completion

**Files:**
- Modify/Test: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.search.integration.test.tsx`
- Optional new test: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.openrouter-streaming-responsiveness.integration.test.tsx`

**Step 1: Add failing integration scenario**

```tsx
it("remains interactive while receiving many tiny assistant chunks", async () => {
  // simulate rapid tiny chunks from chat stream
  // assert stop button remains enabled and clickable before completion
  // assert final assistant text equals concatenated chunks
  expect(stopButton).toBeEnabled()
  expect(finalAssistantText).toBe(expected)
})
```

**Step 2: Run test to verify behavior**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.openrouter-streaming-responsiveness.integration.test.tsx`
Expected: FAIL before full fix; PASS after Tasks 1-4.

**Step 3: Finalize minimal support code for test reliability**

```ts
// keep test-specific stream mock deterministic
const tinyChunks = Array.from({ length: 300 }, (_, i) => ({ choices: [{ delta: { content: i % 10 === 0 ? " " : "x" } }] }))
```

**Step 4: Run full targeted suite**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.openrouter-streaming-responsiveness.integration.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/__tests__/background-proxy.test.ts apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx apps/packages/ui/src/components/Common/Playground/Message.tsx apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.openrouter-streaming-responsiveness.integration.test.tsx
git commit -m "test(chat): add openrouter tiny-chunk responsiveness regression coverage"
```

### Task 6: Final verification, security scan, and docs update

**Skills:** @verification-before-completion

**Files:**
- Modify: `Docs/Plans/2026-03-06-openrouter-chat-freeze-design.md` (optional validation notes)

**Step 1: Run verification commands**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/background-proxy.test.ts apps/packages/ui/src/hooks/chat/__tests__/useChatActions.character-stream-throttle.integration.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/Message.streaming-lite.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.openrouter-streaming-responsiveness.integration.test.tsx
```

Expected: PASS.

**Step 2: Run Bandit on touched scope (project requirement)**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/services apps/packages/ui/src/hooks/chat apps/packages/ui/src/components/Common/Playground -f json -o /tmp/bandit_openrouter_chat_freeze.json
```

Expected: completes without new High findings in touched code paths.

**Step 3: Manual validation checklist**

1. Firefox + `/chat` + OpenRouter model.
2. No browser “Stop this page?” prompt during long stream.
3. Stop button remains responsive during stream.
4. Final markdown formatting appears correctly after completion.

**Step 4: Commit final polish**

```bash
git add Docs/Plans/2026-03-06-openrouter-chat-freeze-design.md
git commit -m "docs(chat): record validation for openrouter stream freeze fix"
```

