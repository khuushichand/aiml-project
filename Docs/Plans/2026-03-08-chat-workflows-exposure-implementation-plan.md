# Chat Workflows Exposure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the Chat Workflows route in the Next.js web shell and verify intended navigation/launcher surfaces resolve to a working `/chat-workflows` page.

**Architecture:** The shared UI route registry already owns the Chat Workflows feature definition, so implementation should stay in the web-shell routing layer. Add the missing Next.js page shim, then add focused parity and discoverability tests so route metadata and web-shell exposure do not drift again.

**Tech Stack:** Next.js pages router, React dynamic imports, shared UI route registry, Vitest

---

### Task 1: Add the missing Next.js page shim

**Files:**
- Create: `apps/tldw-frontend/pages/chat-workflows.tsx`
- Reference: `apps/tldw-frontend/pages/mcp-hub.tsx`
- Reference: `apps/tldw-frontend/pages/workflow-editor.tsx`

**Step 1: Write the failing test**

Add or extend a route-parity test that asserts the web shell contains a `chat-workflows.tsx` page file and that it dynamically imports `@/routes/option-chat-workflows`.

Example assertion shape:

```ts
const source = readFileSync("apps/tldw-frontend/pages/chat-workflows.tsx", "utf8")
expect(source).toMatch(/dynamic\(\(\) => import\("@\/routes\/option-chat-workflows"\)/)
expect(source).toMatch(/ssr:\s*false/)
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run <route-parity-test-file>`

Expected: FAIL because `apps/tldw-frontend/pages/chat-workflows.tsx` does not exist yet.

**Step 3: Write minimal implementation**

Create `apps/tldw-frontend/pages/chat-workflows.tsx` with the same structure as peer routes.

Implementation target:

```ts
import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-chat-workflows"), {
  ssr: false
})
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run <route-parity-test-file>`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/pages/chat-workflows.tsx <route-parity-test-file>
git commit -m "fix(web): expose chat workflows route"
```

### Task 2: Verify shared route wiring stays aligned

**Files:**
- Test: `apps/packages/ui/src/routes/__tests__/chat-workflows-route.test.tsx`
- Reference: `apps/packages/ui/src/routes/route-registry.tsx`
- Reference: `apps/packages/ui/src/routes/option-chat-workflows.tsx`

**Step 1: Review the existing test**

Confirm the test already asserts:
- `/chat-workflows` exists in the shared route registry
- `OptionChatWorkflows` lazy-loads `./option-chat-workflows`

**Step 2: Run test to establish baseline**

Run: `cd apps/packages/ui && bunx vitest run src/routes/__tests__/chat-workflows-route.test.tsx`

Expected: PASS

**Step 3: Tighten only if coverage is incomplete**

If the test misses the route label or nav metadata, add a minimal assertion such as:

```ts
expect(routeRegistrySource).toMatch(/labelToken:\s*"option:header.chatWorkflows"/)
```

Do not add broad route-registry snapshot coverage.

**Step 4: Re-run test**

Run: `cd apps/packages/ui && bunx vitest run src/routes/__tests__/chat-workflows-route.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/__tests__/chat-workflows-route.test.tsx
git commit -m "test(ui): lock chat workflows shared route wiring"
```

### Task 3: Verify launcher/discoverability entry points

**Files:**
- Test: `apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`
- Reference: `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Reference: `apps/packages/ui/src/routes/route-registry.tsx`

**Step 1: Review current discoverability coverage**

Confirm the existing Playground test asserts the launcher action navigates to `/chat-workflows`.

Expected existing shape:

```ts
fireEvent.click(screen.getByTestId("playground-chat-workflows-trigger"))
expect(routerState.navigate).toHaveBeenCalledWith("/chat-workflows")
```

**Step 2: Run the targeted test**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`

Expected: PASS

**Step 3: Add minimal coverage only if needed**

If no test covers discoverability, add one focused test for the launcher button without expanding into full navigation snapshots.

**Step 4: Re-run the test**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx
git commit -m "test(ui): verify chat workflows launcher path"
```

### Task 4: Verify end-to-end route exposure in the web shell

**Files:**
- Modify or create: appropriate web-shell route parity test under `apps/tldw-frontend/__tests__/`
- Reference: `apps/tldw-frontend/pages/chat-workflows.tsx`
- Reference: `apps/tldw-frontend/pages/mcp-hub.tsx`
- Reference: `apps/tldw-frontend/pages/workflow-editor.tsx`

**Step 1: Add a focused web-shell parity test**

Prefer a file-system based test that checks the page exists and imports the correct route module. Keep it narrow to the missing-page regression.

Example:

```ts
import { existsSync, readFileSync } from "node:fs"

it("exposes chat workflows through a Next page shim", () => {
  expect(existsSync("pages/chat-workflows.tsx")).toBe(true)
  const source = readFileSync("pages/chat-workflows.tsx", "utf8")
  expect(source).toContain('import("@/routes/option-chat-workflows")')
})
```

**Step 2: Run the targeted web-shell test**

Run: `cd apps/tldw-frontend && bunx vitest run <web-shell-route-test-file>`

Expected: PASS

**Step 3: Check for redundant overlap**

If Task 1’s test already fully covers this regression in the correct package, remove duplication and keep only one authoritative test.

**Step 4: Run the final chosen test set**

Run:
- `cd apps/tldw-frontend && bunx vitest run <web-shell-route-test-file>`
- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/chat-workflows-route.test.tsx`
- `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add <web-shell-route-test-file>
git commit -m "test(web): prevent chat workflows route parity regression"
```

### Task 5: Verify changed scope and security checks

**Files:**
- Verify touched frontend files
- Optional verify no backend files changed

**Step 1: Run targeted frontend verification**

Run:
- `cd apps/tldw-frontend && bunx vitest run <web-shell-route-test-file>`
- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/chat-workflows-route.test.tsx`
- `cd apps/packages/ui && bunx vitest run src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`

Expected: PASS

**Step 2: Run Bandit on touched backend scope**

Because this fix is frontend-only, either:
- run Bandit only if any backend files were touched, or
- explicitly record that no backend Python files changed and Bandit is not applicable.

Expected: No new backend security findings in changed code.

**Step 3: Review git diff**

Run: `git diff --stat`

Expected: only the page shim and focused tests are changed.

**Step 4: Create final integration commit**

```bash
git add apps/tldw-frontend/pages/chat-workflows.tsx \
  apps/packages/ui/src/routes/__tests__/chat-workflows-route.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx \
  <web-shell-route-test-file>
git commit -m "fix(web): restore chat workflows route exposure"
```

**Step 5: Prepare handoff notes**

Document:
- direct route now resolves
- launcher/nav paths still target `/chat-workflows`
- tests added or confirmed
- no backend contract changes
