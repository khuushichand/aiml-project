# /chat Typing Latency (WebUI + Extension) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce `/chat` typing latency in both WebUI and extension while preserving message correctness, composer behavior, and keyboard workflows.

**Architecture:** Instrument the shared composer path first, then isolate immediate input updates from non-critical expensive derivations. Keep send/caret/IME logic synchronous, but defer non-essential calculations and tighten layout work in textarea autosizing. Validate parity with focused unit/integration tests on shared `apps/packages/ui` code used by both surfaces.

**Tech Stack:** React 18, TypeScript, TanStack Query, Zustand, Vitest + React Testing Library, Bun, Playwright (optional manual profiling support)

---

### Task 1: Add Dev-Only Composer Perf Instrumentation

**Files:**
- Create: `apps/packages/ui/src/utils/perf/composer-perf.ts`
- Create: `apps/packages/ui/src/utils/perf/__tests__/composer-perf.test.ts`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { createComposerPerfTracker } from "@/utils/perf/composer-perf"

describe("createComposerPerfTracker", () => {
  it("records durations only when enabled", () => {
    const tracker = createComposerPerfTracker({ enabled: false })
    const end = tracker.start("input-change")
    end()
    expect(tracker.snapshot().length).toBe(0)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/utils/perf/__tests__/composer-perf.test.ts --reporter=line`  
Expected: FAIL because `composer-perf.ts` does not exist yet.

**Step 3: Write minimal implementation**

```ts
export function createComposerPerfTracker({ enabled }: { enabled: boolean }) {
  const entries: Array<{ label: string; durationMs: number }> = []
  return {
    start(label: string) {
      const start = performance.now()
      return () => {
        if (!enabled) return
        entries.push({ label, durationMs: performance.now() - start })
      }
    },
    snapshot() {
      return [...entries]
    }
  }
}
```

**Step 4: Wire instrumentation in composer hot paths**

- In `PlaygroundForm.tsx`, wrap:
  - textarea `onChange` handling
  - selected `form.values.message`-dependent derivations
- Gate with a dev flag (for example, `window.__TLDW_CHAT_PERF__ === true`) so production behavior is unchanged.

**Step 5: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/utils/perf/__tests__/composer-perf.test.ts --reporter=line`  
Expected: PASS

**Step 6: Commit**

```bash
git add apps/packages/ui/src/utils/perf/composer-perf.ts \
  apps/packages/ui/src/utils/perf/__tests__/composer-perf.test.ts \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx
git commit -m "test+feat(chat): add dev-only composer perf instrumentation"
```

### Task 2: Introduce Deferred Composer Input for Non-Critical Derivations

**Files:**
- Create: `apps/packages/ui/src/hooks/playground/useDeferredComposerInput.ts`
- Create: `apps/packages/ui/src/hooks/playground/__tests__/useDeferredComposerInput.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

**Step 1: Write the failing test**

```tsx
import { renderHook } from "@testing-library/react"
import { useDeferredComposerInput } from "@/hooks/playground/useDeferredComposerInput"

it("keeps live input immediate but exposes deferred input for heavy consumers", () => {
  const { result, rerender } = renderHook(
    ({ value }) => useDeferredComposerInput(value),
    { initialProps: { value: "a" } }
  )
  rerender({ value: "abc" })
  expect(result.current.liveInput).toBe("abc")
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/hooks/playground/__tests__/useDeferredComposerInput.test.tsx --reporter=line`  
Expected: FAIL because hook file is missing.

**Step 3: Write minimal implementation**

```ts
import React from "react"

export const useDeferredComposerInput = (value: string) => {
  const liveInput = value
  const deferredInput = React.useDeferredValue(value)
  return { liveInput, deferredInput }
}
```

**Step 4: Integrate into `PlaygroundForm.tsx`**

- Use `liveInput` for:
  - textarea value
  - send and enter semantics
  - mention/slash handling
- Use `deferredInput` for:
  - model recommendation generation
  - optional context-insight derivations not needed for immediate typing feedback

**Step 5: Run tests to verify pass**

Run:  
`bunx vitest run apps/packages/ui/src/hooks/playground/__tests__/useDeferredComposerInput.test.tsx --reporter=line`  
`bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.model-identity.guard.test.ts --reporter=line`  
Expected: PASS

**Step 6: Commit**

```bash
git add apps/packages/ui/src/hooks/playground/useDeferredComposerInput.ts \
  apps/packages/ui/src/hooks/playground/__tests__/useDeferredComposerInput.test.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx
git commit -m "feat(chat): defer non-critical composer derivations from live typing"
```

### Task 3: Reduce Textarea Autosize Layout Thrash

**Files:**
- Modify: `apps/packages/ui/src/hooks/useDynamicTextareaSize.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useDynamicTextareaSize.test.tsx`

**Step 1: Write the failing test**

```tsx
import { renderHook } from "@testing-library/react"
import useDynamicTextareaSize from "@/hooks/useDynamicTextareaSize"

it("does not force style writes when computed height is unchanged", () => {
  // create textarea mock and assert style mutation count
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/useDynamicTextareaSize.test.tsx --reporter=line`  
Expected: FAIL due missing optimization behavior.

**Step 3: Write minimal implementation**

```ts
// Keep last applied height in ref
// Batch measurement + mutation in requestAnimationFrame
// Skip style writes when next height equals previous
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/useDynamicTextareaSize.test.tsx --reporter=line`  
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useDynamicTextareaSize.tsx \
  apps/packages/ui/src/hooks/__tests__/useDynamicTextareaSize.test.tsx
git commit -m "perf(chat): optimize textarea autosize to avoid redundant reflows"
```

### Task 4: Keep Callback Stability by Removing Per-Key Dependency Churn

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Create: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.latest-message-submit.test.tsx`

**Step 1: Write the failing test**

```tsx
it("submits latest typed message even when heavy callbacks use refs", async () => {
  // type into composer, trigger submit, assert payload contains latest value
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.latest-message-submit.test.tsx --reporter=line`  
Expected: FAIL prior to ref-based callback stabilization.

**Step 3: Write minimal implementation**

```ts
const messageRef = React.useRef("")
React.useEffect(() => {
  messageRef.current = form.values.message || ""
}, [form.values.message])

// In non-typing-critical callbacks, read messageRef.current
// and remove form.values.message from callback dependency arrays.
```

**Step 4: Run tests to verify pass**

Run:  
`bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.latest-message-submit.test.tsx --reporter=line`  
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.latest-message-submit.test.tsx
git commit -m "perf(chat): stabilize composer callbacks without submit regressions"
```

### Task 5: Parity and Regression Safety for Shared /chat Behavior

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.search.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts`
- Create: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.typing-latency.guard.test.tsx`

**Step 1: Write failing regression assertions**

```tsx
it("keeps slash command and mentions behavior intact while typing rapidly", async () => {
  // rapid input updates + slash/mention interaction assertions
})
```

**Step 2: Run tests to verify they fail**

Run:  
`bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.typing-latency.guard.test.tsx --reporter=line`  
Expected: FAIL before new guard coverage.

**Step 3: Implement minimal test adjustments**

- Add high-frequency input-change test utilities to existing test fixtures.
- Ensure assertions cover:
  - latest input correctness on submit
  - mention menu still responds
  - slash menu still responds

**Step 4: Run targeted tests**

Run:  
`bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.typing-latency.guard.test.tsx --reporter=line`  
`bunx vitest run apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts --reporter=line`  
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.typing-latency.guard.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.search.integration.test.tsx \
  apps/packages/ui/src/components/Sidepanel/Chat/__tests__/form.mobile-toolbar.contract.test.ts
git commit -m "test(chat): add typing-latency regression guards for composer behavior"
```

### Task 6: Verification, Security Check, and Final Summary

**Files:**
- Modify: `Docs/Plans/2026-03-03-chat-typing-latency-design.md` (append measured before/after results)

**Step 1: Run focused frontend verification**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useDynamicTextareaSize.test.tsx --reporter=line
bunx vitest run apps/packages/ui/src/hooks/playground/__tests__/useDeferredComposerInput.test.tsx --reporter=line
bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.latest-message-submit.test.tsx --reporter=line
bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.typing-latency.guard.test.tsx --reporter=line
```

Expected: PASS

**Step 2: Run Bandit on touched scope (project requirement)**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/hooks apps/packages/ui/src/components/Option/Playground apps/packages/ui/src/utils/perf -f json -o /tmp/bandit_chat_typing_latency.json
```

Expected: no new actionable findings in changed code.

**Step 3: Update design doc with measured outcomes**

- Add baseline vs after metrics
- List residual risks and follow-up items (if any)

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-03-chat-typing-latency-design.md
git commit -m "docs(chat): record typing-latency verification results"
```

## Execution Notes

- Use @test-driven-development for each task.
- Use @verification-before-completion before declaring success.
- Keep commits small and isolated.
- Do not mix unrelated existing working tree changes into task commits.
