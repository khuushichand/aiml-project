# Writing Workspace Draft/Manage Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a shared Draft/Manage writing workspace that defaults to Draft, preserves full feature coverage in Manage, and enforces visual parity across webui and extension.

**Architecture:** Keep one shared `WritingPlayground` implementation in `apps/packages/ui`, add a mode-aware section registry, and gate existing UI sections by `draft` vs `manage` rather than rewriting backend contracts. Use small extracted utils and guard tests to avoid regressions inside the current monolithic component.

**Tech Stack:** React 18, TypeScript, Ant Design, Zustand, `@plasmohq/storage`, TanStack Query, Vitest, Playwright.

---

### Task 1: Add Workspace Mode + Section Registry Utilities

**Files:**
- Create: `apps/packages/ui/src/components/Option/WritingPlayground/writing-workspace-mode-utils.ts`
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-utils.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import {
  DEFAULT_WRITING_WORKSPACE_MODE,
  WRITING_WORKSPACE_SECTIONS,
  getVisibleWritingWorkspaceSections
} from "../writing-workspace-mode-utils"

describe("writing workspace mode utils", () => {
  it("defaults to draft mode", () => {
    expect(DEFAULT_WRITING_WORKSPACE_MODE).toBe("draft")
  })

  it("keeps drafting sections hidden from manage-only set", () => {
    const draftIds = getVisibleWritingWorkspaceSections("draft").map((s) => s.id)
    expect(draftIds).toContain("draft-editor")
    expect(draftIds).not.toContain("manage-analysis")
  })

  it("declares stable section ids", () => {
    expect(WRITING_WORKSPACE_SECTIONS.map((s) => s.id)).toEqual([
      "sessions",
      "draft-editor",
      "draft-inspector",
      "manage-styling",
      "manage-generation",
      "manage-context",
      "manage-analysis"
    ])
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-utils.test.ts -v`  
Expected: FAIL with module not found for `writing-workspace-mode-utils`.

**Step 3: Write minimal implementation**

```ts
export type WritingWorkspaceMode = "draft" | "manage"

export type WritingWorkspaceSectionId =
  | "sessions"
  | "draft-editor"
  | "draft-inspector"
  | "manage-styling"
  | "manage-generation"
  | "manage-context"
  | "manage-analysis"

type WritingWorkspaceSection = {
  id: WritingWorkspaceSectionId
  modes: WritingWorkspaceMode[]
}

export const DEFAULT_WRITING_WORKSPACE_MODE: WritingWorkspaceMode = "draft"

export const WRITING_WORKSPACE_SECTIONS: WritingWorkspaceSection[] = [
  { id: "sessions", modes: ["draft", "manage"] },
  { id: "draft-editor", modes: ["draft"] },
  { id: "draft-inspector", modes: ["draft"] },
  { id: "manage-styling", modes: ["manage"] },
  { id: "manage-generation", modes: ["manage"] },
  { id: "manage-context", modes: ["manage"] },
  { id: "manage-analysis", modes: ["manage"] }
]

export const getVisibleWritingWorkspaceSections = (
  mode: WritingWorkspaceMode
) => WRITING_WORKSPACE_SECTIONS.filter((section) => section.modes.includes(mode))
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-utils.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground/writing-workspace-mode-utils.ts \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-utils.test.ts
git commit -m "feat: add writing workspace mode registry utilities"
```

### Task 2: Add Workspace Mode Preference Normalization Utilities

**Files:**
- Create: `apps/packages/ui/src/components/Option/WritingPlayground/writing-workspace-mode-prefs.ts`
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-prefs.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import {
  WRITING_WORKSPACE_MODE_STORAGE_KEY,
  normalizeWritingWorkspaceMode,
  resolveInitialWorkspaceMode
} from "../writing-workspace-mode-prefs"

describe("writing workspace mode prefs", () => {
  it("uses stable storage key", () => {
    expect(WRITING_WORKSPACE_MODE_STORAGE_KEY).toBe("writing:workspace-mode")
  })

  it("normalizes unknown values to draft", () => {
    expect(normalizeWritingWorkspaceMode("x")).toBe("draft")
    expect(normalizeWritingWorkspaceMode(undefined)).toBe("draft")
  })

  it("keeps valid values", () => {
    expect(normalizeWritingWorkspaceMode("draft")).toBe("draft")
    expect(normalizeWritingWorkspaceMode("manage")).toBe("manage")
  })

  it("applies mode precedence for first-load vs persisted value", () => {
    expect(resolveInitialWorkspaceMode(undefined)).toBe("draft")
    expect(resolveInitialWorkspaceMode("manage")).toBe("manage")
    expect(resolveInitialWorkspaceMode("draft")).toBe("draft")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-prefs.test.ts -v`  
Expected: FAIL with module not found.

**Step 3: Write minimal implementation**

```ts
import type { WritingWorkspaceMode } from "./writing-workspace-mode-utils"
import { DEFAULT_WRITING_WORKSPACE_MODE } from "./writing-workspace-mode-utils"

export const WRITING_WORKSPACE_MODE_STORAGE_KEY = "writing:workspace-mode"

export const normalizeWritingWorkspaceMode = (
  value: unknown
): WritingWorkspaceMode => {
  if (value === "draft" || value === "manage") return value
  return DEFAULT_WRITING_WORKSPACE_MODE
}

export const resolveInitialWorkspaceMode = (
  storedValue: unknown
): WritingWorkspaceMode => normalizeWritingWorkspaceMode(storedValue)
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-prefs.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground/writing-workspace-mode-prefs.ts \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-prefs.test.ts
git commit -m "feat: add writing workspace mode preference normalization"
```

### Task 3: Extend Writing Playground Store for Shared Mode State

**Files:**
- Modify: `apps/packages/ui/src/store/writing-playground.tsx`
- Test: `apps/packages/ui/src/store/__tests__/writing-playground-store.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { useWritingPlaygroundStore } from "../writing-playground"

describe("writing playground store", () => {
  it("defaults workspace mode to draft", () => {
    const state = useWritingPlaygroundStore.getState()
    expect(state.workspaceMode).toBe("draft")
  })

  it("updates workspace mode", () => {
    useWritingPlaygroundStore.getState().setWorkspaceMode("manage")
    expect(useWritingPlaygroundStore.getState().workspaceMode).toBe("manage")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/store/__tests__/writing-playground-store.test.ts -v`  
Expected: FAIL because `workspaceMode` and `setWorkspaceMode` do not exist.

**Step 3: Write minimal implementation**

```ts
type WritingWorkspaceMode = "draft" | "manage"

type WritingPlaygroundState = {
  activeSessionId: string | null
  activeSessionName: string | null
  workspaceMode: WritingWorkspaceMode
  setActiveSessionId: (activeSessionId: string | null) => void
  setActiveSessionName: (activeSessionName: string | null) => void
  setWorkspaceMode: (workspaceMode: WritingWorkspaceMode) => void
}

export const useWritingPlaygroundStore = createWithEqualityFn<WritingPlaygroundState>((set) => ({
  activeSessionId: null,
  activeSessionName: null,
  workspaceMode: "draft",
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setActiveSessionName: (activeSessionName) => set({ activeSessionName }),
  setWorkspaceMode: (workspaceMode) => set({ workspaceMode })
}))
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/store/__tests__/writing-playground-store.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/writing-playground.tsx \
  apps/packages/ui/src/store/__tests__/writing-playground-store.test.ts
git commit -m "feat: add writing workspace mode state to store"
```

### Task 4: Add Draft/Manage Mode Switch to Shared WritingPlayground UI

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WritingPlayground/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/WritingPlayground/index.tsx` (imports)
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode.guard.test.ts`

**Step 1: Write the failing guard test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing workspace mode guard", () => {
  it("includes draft/manage mode switch and test ids", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../index.tsx"),
      "utf8"
    )
    expect(source).toContain("writing-workspace-mode-switch")
    expect(source).toContain("writing-mode-draft")
    expect(source).toContain("writing-mode-manage")
    expect(source).toContain("writing-section-sessions")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode.guard.test.ts -v`  
Expected: FAIL because the strings are not present yet.

**Step 3: Write minimal implementation**

```tsx
const [storedWorkspaceMode, setStoredWorkspaceMode] = useStorage<string>(
  WRITING_WORKSPACE_MODE_STORAGE_KEY,
  DEFAULT_WRITING_WORKSPACE_MODE
)
const workspaceMode = normalizeWritingWorkspaceMode(storedWorkspaceMode)

<Segmented
  data-testid="writing-workspace-mode-switch"
  size="small"
  value={workspaceMode}
  onChange={(value) => setStoredWorkspaceMode(String(value))}
  options={[
    { value: "draft", label: <span data-testid="writing-mode-draft">Draft</span> },
    { value: "manage", label: <span data-testid="writing-mode-manage">Manage</span> }
  ]}
/>
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-mode.guard.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground/index.tsx \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-mode.guard.test.ts
git commit -m "feat: add writing workspace draft/manage mode switch"
```

### Task 5: Implement Draft Mode (Editor-First Fast Path)

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WritingPlayground/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-draft-mode.guard.test.ts`

**Step 1: Write the failing guard test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing draft mode guard", () => {
  it("keeps editor + quick controls in draft mode", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain("workspaceMode === \"draft\"")
    expect(source).toContain("writing-section-draft-editor")
    expect(source).toContain("writing-section-draft-inspector")
    expect(source).toContain("temperature")
    expect(source).toContain("max_tokens")
    expect(source).toContain("token_streaming")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-draft-mode.guard.test.ts -v`  
Expected: FAIL because draft-only section markers are missing.

**Step 3: Write minimal implementation**

```tsx
{workspaceMode === "draft" ? (
  <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
    <Card data-testid="writing-section-sessions">{/* existing sessions list */}</Card>
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card data-testid="writing-section-draft-editor">{/* existing editor card */}</Card>
      <Card data-testid="writing-section-draft-inspector">
        {/* quick controls only: temperature, max_tokens, streaming, basic stop mode */}
      </Card>
    </div>
  </div>
) : null}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-draft-mode.guard.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground/index.tsx \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-draft-mode.guard.test.ts
git commit -m "feat: add editor-first draft mode layout for writing workspace"
```

### Task 6: Implement Manage Mode (Full Control Surface)

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WritingPlayground/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-manage-mode.guard.test.ts`

**Step 1: Write the failing guard test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing manage mode guard", () => {
  it("keeps all advanced sections behind manage mode", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain("workspaceMode === \"manage\"")
    expect(source).toContain("writing-section-manage-styling")
    expect(source).toContain("writing-section-manage-generation")
    expect(source).toContain("writing-section-manage-context")
    expect(source).toContain("writing-section-manage-analysis")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-manage-mode.guard.test.ts -v`  
Expected: FAIL because manage section markers are not present.

**Step 3: Write minimal implementation**

```tsx
{workspaceMode === "manage" ? (
  <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
    <Card data-testid="writing-section-sessions">{/* existing sessions list */}</Card>
    <div className="grid grid-cols-1 gap-6">
      <Card data-testid="writing-section-manage-styling">{/* templates + themes */}</Card>
      <Card data-testid="writing-section-manage-generation">{/* core + advanced generation */}</Card>
      <Card data-testid="writing-section-manage-context">{/* memory/author/world/context preview */}</Card>
      <Card data-testid="writing-section-manage-analysis">{/* token tools + wordcloud + diagnostics */}</Card>
    </div>
  </div>
) : null}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-manage-mode.guard.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground/index.tsx \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-manage-mode.guard.test.ts
git commit -m "feat: add manage mode with full writing controls"
```

### Task 7: Add Route-Level Parity Guard Between WebUI and Extension Wrappers

**Files:**
- Create: `apps/tldw-frontend/extension/__tests__/writing-playground-route-parity.guard.test.ts`

**Step 1: Write the failing test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing playground route parity", () => {
  it("keeps shared PageShell and WritingPlayground mount parity", () => {
    const webRoute = fs.readFileSync(
      path.resolve(__dirname, "../../../packages/ui/src/routes/option-writing-playground.tsx"),
      "utf8"
    )
    const extRoute = fs.readFileSync(
      path.resolve(__dirname, "../routes/option-writing-playground.tsx"),
      "utf8"
    )

    expect(webRoute).toContain("PageShell className=\"py-6\" maxWidthClassName=\"max-w-7xl\"")
    expect(extRoute).toContain("PageShell className=\"py-6\" maxWidthClassName=\"max-w-7xl\"")
    expect(webRoute).toContain("<WritingPlayground />")
    expect(extRoute).toContain("<WritingPlayground />")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run extension/__tests__/writing-playground-route-parity.guard.test.ts -v`  
Expected: FAIL due missing file.

**Step 3: Write minimal implementation**

```ts
// Save the test file above with valid relative paths.
// No production code changes required if parity already matches.
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run extension/__tests__/writing-playground-route-parity.guard.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/extension/__tests__/writing-playground-route-parity.guard.test.ts
git commit -m "test: add writing playground webui-extension route parity guard"
```

### Task 8: Add E2E Coverage for Mode Parity, No-Loss Switching, and Accessibility

**Files:**
- Modify: `apps/extension/tests/e2e/writing-playground-themes-templates.spec.ts`
- Create: `apps/extension/tests/e2e/writing-playground-mode-parity.spec.ts`

**Step 1: Write the failing e2e assertion**

```ts
await expect(page.getByTestId("writing-workspace-mode-switch")).toBeVisible()
await expect(page.getByTestId("writing-mode-draft")).toBeVisible()
await expect(page.getByTestId("writing-section-draft-editor")).toBeVisible()
await expect(page.getByTestId("writing-section-manage-generation")).toBeHidden()

await page.getByTestId("writing-mode-manage").click()
await expect(page.getByTestId("writing-section-manage-generation")).toBeVisible()
await expect(page.getByTestId("writing-section-draft-editor")).toBeHidden()

// No-loss requirement across mode toggles
const editor = page.getByPlaceholder(/Start writing your prompt/i)
await editor.fill("Draft text that must survive mode toggle")
await page.getByTestId("writing-mode-manage").click()
await page.getByTestId("writing-mode-draft").click()
await expect(editor).toHaveValue("Draft text that must survive mode toggle")

// Keyboard and screen reader behavior
await page.keyboard.press("Tab")
await expect(page.getByTestId("writing-workspace-mode-switch")).toBeFocused()
await page.keyboard.press("ArrowRight")
await expect(page.getByTestId("writing-mode-manage")).toBeVisible()
await expect(page.getByTestId("writing-mode-live-region")).toContainText("Manage")
```

**Step 2: Run test to verify it fails**

Run: `cd apps/extension && bunx playwright test tests/e2e/writing-playground-themes-templates.spec.ts --reporter=line`  
Expected: FAIL before mode-switch implementation is complete.

**Step 3: Write minimal implementation**

```tsx
// Ensure data-testid attributes exist in WritingPlayground:
// writing-workspace-mode-switch
// writing-mode-draft
// writing-mode-manage
// writing-section-draft-editor
// writing-section-manage-generation
// writing-mode-live-region (aria-live=polite)
// preserve input/form state when switching modes instead of remount-reset
```

**Step 4: Run test to verify it passes**

Run: `cd apps/extension && bunx playwright test tests/e2e/writing-playground-themes-templates.spec.ts tests/e2e/writing-playground-mode-parity.spec.ts --reporter=line`  
Expected: PASS (or pass for targeted mode-switch assertions if split into a dedicated test block).

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/writing-playground-themes-templates.spec.ts \
  apps/extension/tests/e2e/writing-playground-mode-parity.spec.ts \
  apps/packages/ui/src/components/Option/WritingPlayground/index.tsx
git commit -m "test: cover writing workspace mode parity no-loss and a11y flows"
```

### Task 9: Copy, i18n, and Documentation Alignment

**Files:**
- Modify: `apps/packages/ui/src/public/_locales/en/option.json`
- Modify: `apps/extension/docs/Product/WIP/Writing-Playground-PRD.md`
- Modify: `docs/plans/2026-03-01-writing-parity-draft-manage-design.md`

**Step 1: Write failing i18n/doc guard test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing mode copy guard", () => {
  it("contains draft/manage labels in option locale", () => {
    const locale = fs.readFileSync(
      path.resolve(__dirname, "../../../public/_locales/en/option.json"),
      "utf8"
    )
    expect(locale).toContain("\"modeDraft\"")
    expect(locale).toContain("\"modeManage\"")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-copy.guard.test.ts -v`  
Expected: FAIL until locale keys are added.

**Step 3: Write minimal implementation**

```json
{
  "writingPlayground": {
    "modeDraft": "Draft",
    "modeManage": "Manage",
    "manageSettings": "Manage settings",
    "draftQuickControls": "Quick controls"
  }
}
```

Also update PRD/design docs to reference final Draft/Manage IA and parity contract.

**Step 4: Run test to verify it passes**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/WritingPlayground/__tests__/writing-workspace-copy.guard.test.ts -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/public/_locales/en/option.json \
  apps/extension/docs/Product/WIP/Writing-Playground-PRD.md \
  docs/plans/2026-03-01-writing-parity-draft-manage-design.md \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/writing-workspace-copy.guard.test.ts
git commit -m "docs: align writing playground draft/manage parity copy and specs"
```

### Task 10: Full Verification + Release Readiness

**Files:**
- Modify as needed from prior tasks only.

**Step 1: Run targeted unit/integration tests**

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-utils.test.ts \
  src/components/Option/WritingPlayground/__tests__/writing-workspace-mode-prefs.test.ts \
  src/components/Option/WritingPlayground/__tests__/writing-workspace-mode.guard.test.ts \
  src/components/Option/WritingPlayground/__tests__/writing-draft-mode.guard.test.ts \
  src/components/Option/WritingPlayground/__tests__/writing-manage-mode.guard.test.ts \
  src/components/Option/WritingPlayground/__tests__/writing-workspace-copy.guard.test.ts \
  src/store/__tests__/writing-playground-store.test.ts -v
```

Expected: PASS.

**Step 2: Run route parity and extension e2e checks**

```bash
cd apps/tldw-frontend && bunx vitest run extension/__tests__/writing-playground-route-parity.guard.test.ts -v
cd apps/extension && bunx playwright test tests/e2e/writing-playground-themes-templates.spec.ts tests/e2e/writing-playground-mode-parity.spec.ts --reporter=line
```

Expected: PASS.

**Step 3: Run measurable acceptance scripts**

```bash
cd apps/extension && bunx playwright test tests/e2e/writing-playground-mode-parity.spec.ts --grep "timed first generation" --reporter=line
cd apps/extension && TLDW_WRITING_CONTROL_BASELINE_COUNT=<pre_redesign_count> bunx playwright test tests/e2e/writing-playground-mode-parity.spec.ts --grep "control density delta" --reporter=line
```

Expected:
- timed first-generation path <= 60s at p95 for a 5-prompt scripted sample set.
- draft mode control count delta >= 35% reduction vs recorded pre-redesign baseline supplied via `TLDW_WRITING_CONTROL_BASELINE_COUNT`.

**Step 4: Run frontend lint on touched scopes**

```bash
cd apps/tldw-frontend && bun run lint
cd apps/packages/ui && bunx tsc --noEmit
```

Expected: no new errors in touched files.

**Step 5: Run security check gate required by project guidelines**

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WritingPlayground -f json -o /tmp/bandit_writing_parity.json
```

Expected: no new high-confidence findings in touched scope.

**Step 6: Commit verification artifacts and final implementation**

```bash
git add apps/packages/ui/src/components/Option/WritingPlayground \
  apps/packages/ui/src/store/writing-playground.tsx \
  apps/packages/ui/src/store/__tests__/writing-playground-store.test.ts \
  apps/packages/ui/src/public/_locales/en/option.json \
  apps/tldw-frontend/extension/__tests__/writing-playground-route-parity.guard.test.ts \
  apps/extension/tests/e2e/writing-playground-themes-templates.spec.ts \
  apps/extension/tests/e2e/writing-playground-mode-parity.spec.ts \
  apps/extension/docs/Product/WIP/Writing-Playground-PRD.md
git commit -m "feat: add draft/manage parity workflow for writing workspace"
```

## Notes for Implementation Session

1. Use `@superpowers/test-driven-development` for each task before code edits.
2. Use `@superpowers/verification-before-completion` before claiming completion.
3. Keep changes incremental and avoid broad refactors outside mode/parity scope.
4. Prefer extracting small pure utilities over deep component rewrites.
