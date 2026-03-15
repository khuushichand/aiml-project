# Workspace Playground WebUI + Extension Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add scalable, shared `/workspace-playground` end-to-end parity coverage across WebUI and extension, with a fast PR gate and deeper nightly coverage.

**Architecture:** Build a shared Playwright contract in `apps/test-utils` and run it through thin WebUI and extension wrappers. Keep PR checks deterministic (baseline + studio critical actions) and move heavy real-backend matrix coverage to nightly workflows.

**Tech Stack:** Playwright, TypeScript, Bun, GitHub Actions, existing WebUI/extension E2E harness utilities.

---

### Task 1: Create Shared Workspace Parity Contract Skeleton

**Files:**
- Create: `apps/test-utils/workspace-playground/types.ts`
- Create: `apps/test-utils/workspace-playground/page.ts`
- Create: `apps/test-utils/workspace-playground/contract.ts`
- Create: `apps/test-utils/workspace-playground/index.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts`

**Step 1: Write the failing test**

```ts
// apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts
import { test } from "../utils/fixtures"
import { runWorkspacePlaygroundParityContract } from "../../../test-utils/workspace-playground"

test.describe("Workspace Playground Parity (WebUI)", () => {
  test("runs shared baseline contract", async ({ authedPage, diagnostics }) => {
    await runWorkspacePlaygroundParityContract({
      platform: "web",
      page: authedPage,
      diagnostics
    })
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: FAIL with module import/type errors because shared contract files do not exist.

**Step 3: Write minimal implementation**

```ts
// apps/test-utils/workspace-playground/contract.ts
export async function runWorkspacePlaygroundParityContract(_: unknown): Promise<void> {
  // minimal scaffold; real assertions added in next task
}
```

```ts
// apps/test-utils/workspace-playground/index.ts
export * from "./contract"
export * from "./types"
```

**Step 4: Run test to verify it passes import/boot**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: PASS or reach next failing assertion boundary (no missing module errors).

**Step 5: Commit**

```bash
git add apps/test-utils/workspace-playground apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts
git commit -m "test(e2e): scaffold shared workspace parity contract for webui"
```

### Task 2: Implement PR Baseline Assertions in Shared Contract

**Files:**
- Modify: `apps/test-utils/workspace-playground/types.ts`
- Modify: `apps/test-utils/workspace-playground/page.ts`
- Modify: `apps/test-utils/workspace-playground/contract.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts`

**Step 1: Write the failing test**

```ts
// in web parity spec or contract test entry
await expect(workspace.headerTitle).toBeVisible()
await expect(workspace.sourcesPanel).toBeVisible()
await expect(workspace.chatPanel).toBeVisible()
await expect(workspace.studioPanel).toBeVisible()
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: FAIL because contract/page object does not yet enforce baseline checks.

**Step 3: Write minimal implementation**

```ts
// apps/test-utils/workspace-playground/contract.ts
export async function runWorkspacePlaygroundParityContract(ctx: WorkspaceParityContext) {
  const page = createWorkspacePlaygroundPage(ctx.page)
  await page.gotoWorkspaceRoute(ctx.platform)
  await page.waitForReady()
  await page.assertBaselinePanesVisible()
  await ctx.assertNoCriticalIssues?.()
}
```

```ts
// apps/test-utils/workspace-playground/page.ts
export const createWorkspacePlaygroundPage = (page: Page) => ({
  async gotoWorkspaceRoute(platform: "web" | "extension") {
    await page.goto(platform === "web" ? "/workspace-playground" : `${(window as any).location.origin}#/workspace-playground`)
  },
  async waitForReady() { /* wait for workspaces button + main panel */ },
  async assertBaselinePanesVisible() { /* expect sources/chat/studio visible */ }
})
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: PASS for baseline boot checks with no critical diagnostics.

**Step 5: Commit**

```bash
git add apps/test-utils/workspace-playground apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts
git commit -m "test(e2e): add shared workspace parity baseline assertions"
```

### Task 3: Add Deterministic Studio Critical Actions to the Shared Contract

**Files:**
- Modify: `apps/test-utils/workspace-playground/contract.ts`
- Modify: `apps/test-utils/workspace-playground/page.ts`
- Create: `apps/test-utils/workspace-playground/fixtures.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts`

**Step 1: Write the failing test**

```ts
await pageObject.seedDeterministicCompletedArtifact()
await pageObject.openGeneratedOutputsIfCollapsed()
await pageObject.expectArtifactActions({
  primary: ["View", "Download"],
  secondary: ["Regenerate options", "Discuss in chat", "Delete"]
})
await pageObject.assertRegenerateMenuOpens()
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: FAIL due missing seed/action helper methods.

**Step 3: Write minimal implementation**

```ts
// apps/test-utils/workspace-playground/fixtures.ts
export const DETERMINISTIC_SUMMARY_ARTIFACT = {
  id: "artifact-parity-summary",
  type: "summary",
  title: "Parity Summary",
  status: "completed",
  content: "Deterministic summary content for parity checks"
}
```

```ts
// apps/test-utils/workspace-playground/page.ts (example helper)
async function seedDeterministicCompletedArtifact() {
  await page.evaluate((artifact) => {
    const store = (window as any).__tldw_useWorkspaceStore
    const state = store?.getState?.()
    if (!state?.generatedArtifacts) return
    state.generatedArtifacts = [artifact, ...state.generatedArtifacts]
  }, DETERMINISTIC_SUMMARY_ARTIFACT)
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line`
Expected: PASS for deterministic studio action checks.

**Step 5: Commit**

```bash
git add apps/test-utils/workspace-playground apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts
git commit -m "test(e2e): add deterministic workspace studio action parity checks"
```

### Task 4: Add Extension Wrapper Using the Same Shared Contract

**Files:**
- Create: `apps/extension/tests/e2e/workspace-playground.parity.spec.ts`
- Modify: `apps/test-utils/workspace-playground/types.ts`
- Modify: `apps/test-utils/workspace-playground/contract.ts`
- Modify: `apps/extension/package.json`

**Step 1: Write the failing test**

```ts
// apps/extension/tests/e2e/workspace-playground.parity.spec.ts
import { test } from "@playwright/test"
import { launchWithBuiltExtensionOrSkip } from "./utils/real-server"
import { runWorkspacePlaygroundParityContract } from "../../../test-utils/workspace-playground"

test("Workspace Playground parity (extension)", async () => {
  const { context, page, optionsUrl } = await launchWithBuiltExtensionOrSkip(test)
  try {
    await runWorkspacePlaygroundParityContract({
      platform: "extension",
      page,
      optionsUrl
    })
  } finally {
    await context.close()
  }
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/extension && bunx playwright test tests/e2e/workspace-playground.parity.spec.ts --reporter=line`
Expected: FAIL with navigation/context mismatches until extension adapter support is implemented.

**Step 3: Write minimal implementation**

```ts
// contract driver logic
if (ctx.platform === "extension") {
  await ctx.page.goto(`${ctx.optionsUrl}#/workspace-playground`, { waitUntil: "domcontentloaded" })
}
```

```json
// apps/extension/package.json script
"test:e2e:workspace-parity": "playwright test tests/e2e/workspace-playground.parity.spec.ts --reporter=line"
```

**Step 4: Run test to verify it passes**

Run: `cd apps/extension && bunx playwright test tests/e2e/workspace-playground.parity.spec.ts --reporter=line`
Expected: PASS with same shared baseline+studio contract.

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/workspace-playground.parity.spec.ts apps/extension/package.json apps/test-utils/workspace-playground
git commit -m "test(e2e): add extension wrapper for shared workspace parity contract"
```

### Task 5: Wire PR Gate (Fast Deterministic) for WebUI + Extension Parity

**Files:**
- Create: `.github/workflows/ui-workspace-playground-parity.yml`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `apps/extension/package.json`
- Modify: `docs/Development/Testing.md`

**Step 1: Write the failing gate config**

```yaml
# workflow initially references commands/scripts not yet present
- run: bun run e2e:workspace-parity
  working-directory: apps/tldw-frontend
- run: bun run test:e2e:workspace-parity
  working-directory: apps/extension
```

**Step 2: Run local workflow-equivalent commands to verify failure**

Run:
- `cd apps/tldw-frontend && bun run e2e:workspace-parity`
- `cd apps/extension && bun run test:e2e:workspace-parity`
Expected: FAIL if scripts do not exist yet.

**Step 3: Write minimal implementation**

```json
// apps/tldw-frontend/package.json
"e2e:workspace-parity": "playwright test e2e/workflows/workspace-playground.parity.spec.ts --reporter=line"
```

```json
// apps/extension/package.json
"test:e2e:workspace-parity": "playwright test tests/e2e/workspace-playground.parity.spec.ts --reporter=line"
```

```yaml
# .github/workflows/ui-workspace-playground-parity.yml
name: UI Workspace Playground Parity
on:
  pull_request:
    branches: [main, dev]
    paths:
      - "apps/packages/ui/src/components/Option/WorkspacePlayground/**"
      - "apps/test-utils/workspace-playground/**"
      - "apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts"
      - "apps/extension/tests/e2e/workspace-playground.parity.spec.ts"
      - ".github/workflows/ui-workspace-playground-parity.yml"
  workflow_dispatch:
jobs:
  parity:
    runs-on: ubuntu-latest
    steps:
      # checkout, setup bun/python/server, run both parity scripts
```

**Step 4: Run commands to verify pass**

Run:
- `cd apps/tldw-frontend && bun run e2e:workspace-parity`
- `cd apps/extension && bun run test:e2e:workspace-parity`
Expected: PASS in local environment.

**Step 5: Commit**

```bash
git add .github/workflows/ui-workspace-playground-parity.yml apps/tldw-frontend/package.json apps/extension/package.json docs/Development/Testing.md
git commit -m "ci(e2e): add workspace playground parity pr gate for webui and extension"
```

### Task 6: Add Nightly Deep Workflow and Real-Backend Matrix Hooks

**Files:**
- Create: `.github/workflows/ui-workspace-playground-nightly.yml`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `apps/extension/package.json`
- Modify: `docs/Development/Testing.md`

**Step 1: Write the failing nightly commands**

```bash
# scripts referenced but not defined yet
bun run e2e:workspace-playground:real-backend
bun run test:e2e:workspace-playground:real-backend
```

**Step 2: Run commands to verify failure**

Run:
- `cd apps/tldw-frontend && bun run e2e:workspace-playground:real-backend`
- `cd apps/extension && bun run test:e2e:workspace-playground:real-backend`
Expected: FAIL with missing scripts.

**Step 3: Write minimal implementation**

```json
// apps/tldw-frontend/package.json
"e2e:workspace-playground:real-backend": "playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line"
```

```json
// apps/extension/package.json
"test:e2e:workspace-playground:real-backend": "playwright test tests/e2e/workspace-playground.parity.spec.ts --grep \"real backend\" --reporter=line"
```

```yaml
# .github/workflows/ui-workspace-playground-nightly.yml
name: UI Workspace Playground Nightly
on:
  schedule:
    - cron: "0 7 * * *"
  workflow_dispatch:
jobs:
  deep-workspace-e2e:
    runs-on: ubuntu-latest
    steps:
      # checkout, setup, backend boot, run webui+extension real-backend commands, upload artifacts
```

**Step 4: Run targeted deep commands to verify pass**

Run:
- `cd apps/tldw-frontend && bun run e2e:workspace-playground:real-backend`
- `cd apps/extension && bun run test:e2e:workspace-playground:real-backend`
Expected: PASS when local backend is healthy and configured.

**Step 5: Commit**

```bash
git add .github/workflows/ui-workspace-playground-nightly.yml apps/tldw-frontend/package.json apps/extension/package.json docs/Development/Testing.md
git commit -m "ci(e2e): add nightly deep workspace playground parity workflow"
```

### Task 7: Final Verification and Handoff

**Files:**
- Modify (if needed): `docs/Development/Testing.md`
- Modify (if needed): `apps/extension/docs/Testing-Guide.md`

**Step 1: Write final verification checklist test (failing if commands missing)**

```md
- [ ] WebUI parity command passes
- [ ] Extension parity command passes
- [ ] WebUI real-backend command passes
- [ ] Extension real-backend command passes
- [ ] New workflows validate with actionlint/yamllint (if available)
```

**Step 2: Run verification commands**

Run:
- `cd apps/tldw-frontend && bun run e2e:workspace-parity`
- `cd apps/extension && bun run test:e2e:workspace-parity`
- `cd apps/tldw-frontend && bun run e2e:workspace-playground:real-backend`
- `cd apps/extension && bun run test:e2e:workspace-playground:real-backend`
- `source .venv/bin/activate && python -m bandit -r apps/test-utils apps/tldw-frontend/e2e apps/extension/tests/e2e -f json -o /tmp/bandit_workspace_parity.json`

Expected: parity and deep commands PASS; Bandit returns no new high-severity issues in touched scope.

**Step 3: Apply minimal fixes for any failing check**

```ts
// Example: replace brittle selector with role/testid stable selector
const regenerate = page.getByRole("button", { name: "Regenerate options" })
await expect(regenerate).toBeVisible()
```

**Step 4: Re-run full verification to green**

Run the same command list from Step 2.
Expected: all required checks green.

**Step 5: Commit**

```bash
git add docs/Development/Testing.md apps/extension/docs/Testing-Guide.md
git commit -m "docs(testing): document workspace playground parity gates and nightly runs"
```

## Notes for Execution

- Keep assertions in shared contract; keep wrappers thin.
- Prefer stable `role` and existing `data-testid` selectors.
- Do not expand PR scope beyond baseline + deterministic studio critical actions.
- Use `@superpowers/test-driven-development` and `@superpowers/verification-before-completion` during implementation.

