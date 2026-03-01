# repo2txt Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for parallelizable tasks (or superpowers:executing-plans for strictly sequential execution).

**Goal:** Ship a V1 repo2txt page in tldw options/web (webapp + extension options) with GitHub + Local providers and preview/copy/download output parity.

**Architecture:** Implement a new shared `@tldw/ui` options route (`/repo2txt`) and port repo2txt core modules into a new feature folder under shared UI. Keep state route-scoped, wire route discovery in options/web navigation surfaces, and keep sidepanel as link-out only for V1.

**Tech Stack:** React 18, TypeScript, Zustand, React Router, Vitest, JSZip, gpt-tokenizer Web Worker, Next.js wrapper (`ssr: false`), WXT extension options runtime.

---

### Task 0: Create isolated worktree and capture baseline

**Files:**
- N/A (git worktree + baseline verification output)

**Step 1: Create isolated branch/worktree**

```bash
cd <repo_root>
git worktree add -b codex/repo2txt-v1 ../tldw_server2-repo2txt
```

Expected: new worktree at `<repo_worktree>` on branch `codex/repo2txt-v1`.

**Step 2: Run baseline verification in the new worktree**

Run:

```bash
cd <repo_worktree> && bun install
cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona-locale-keys.test.ts src/tutorials/__tests__/locale-mirror.test.ts
cd <repo_worktree>/apps/tldw-frontend && bun run compile
cd <repo_worktree>/apps/extension && bun run compile
```

Expected: baseline is green (or existing failures are recorded before feature work starts).

**Step 3: Capture baseline notes**

Record any pre-existing failures and proceed only after they are understood/scoped as unrelated.

**Step 4: Commit**

No commit (setup-only task).

**Step 5: Use worktree root for all remaining tasks**

From Task 1 onward, run all commands from:

- `<repo_worktree>`

### Task 1: Add route skeleton and failing route test

**Files:**
- Create: `apps/packages/ui/src/routes/option-repo2txt.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-repo2txt.route.test.tsx`

**Step 1: Write the failing route test**

```tsx
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { RouteShell } from "@/routes/app-route"

describe("repo2txt option route", () => {
  it("renders repo2txt page at /repo2txt", async () => {
    render(
      <MemoryRouter initialEntries={["/repo2txt"]}>
        <Routes>
          <Route path="*" element={<RouteShell kind="options" />} />
        </Routes>
      </MemoryRouter>
    )
    expect(await screen.findByTestId("repo2txt-route-root")).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/option-repo2txt.route.test.tsx`

Expected: FAIL with route not found or missing test id.

**Step 3: Write minimal implementation**

```tsx
// src/routes/option-repo2txt.tsx
export default function OptionRepo2TxtRoute() {
  return <div data-testid="repo2txt-route-root">repo2txt</div>
}
```

```tsx
// src/routes/route-registry.tsx
const OptionRepo2Txt = lazy(() => import("./option-repo2txt"))
// ...
{
  kind: "options",
  path: "/repo2txt",
  element: <OptionRepo2Txt />,
  nav: {
    group: "workspace",
    labelToken: "option:repo2txt.nav",
    icon: FileText,
    order: 7
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/option-repo2txt.route.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/routes/option-repo2txt.tsx apps/packages/ui/src/routes/route-registry.tsx apps/packages/ui/src/routes/route-paths.ts apps/packages/ui/src/routes/__tests__/option-repo2txt.route.test.tsx
git commit -m "feat(ui): add repo2txt route scaffold"
```

### Task 2: Create feature shell and loading/error state contract

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/Repo2TxtPage.tsx`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/index.ts`
- Modify: `apps/packages/ui/src/routes/option-repo2txt.tsx`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.smoke.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Repo2TxtPage } from "../Repo2TxtPage"

describe("Repo2TxtPage", () => {
  it("shows provider panel and output panel placeholders", () => {
    render(<Repo2TxtPage />)
    expect(screen.getByTestId("repo2txt-provider-panel")).toBeInTheDocument()
    expect(screen.getByTestId("repo2txt-output-panel")).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.smoke.test.tsx`

Expected: FAIL with missing component/module.

**Step 3: Write minimal implementation**

```tsx
export function Repo2TxtPage() {
  return (
    <section data-testid="repo2txt-route-root">
      <div data-testid="repo2txt-provider-panel" />
      <div data-testid="repo2txt-output-panel" />
    </section>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.smoke.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt apps/packages/ui/src/routes/option-repo2txt.tsx
git commit -m "feat(ui): add repo2txt page shell"
```

### Task 3: Port GitHub provider with tests (GitHub-only V1 remote provider)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/providers/BaseProvider.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/providers/types.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/providers/GitHubProvider.ts`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/providers/__tests__/GitHubProvider.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { GitHubProvider } from "../GitHubProvider"

describe("GitHubProvider", () => {
  it("parses owner/repo from github URL", () => {
    const provider = new GitHubProvider()
    const parsed = provider.parseUrl("https://github.com/facebook/react")
    expect(parsed.isValid).toBe(true)
    expect(parsed.owner).toBe("facebook")
    expect(parsed.repo).toBe("react")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/providers/__tests__/GitHubProvider.test.ts`

Expected: FAIL with missing provider module.

**Step 3: Write minimal implementation**

```ts
export class GitHubProvider extends BaseProvider {
  // parseUrl + validateUrl + fetchTree + fetchFile
  // limited to V1 behavior from repo2txt with token support
}
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/providers/__tests__/GitHubProvider.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt/providers
git commit -m "feat(ui): port repo2txt github provider"
```

### Task 4: Port Local provider (directory/zip) with tests

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/providers/LocalProvider.ts`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/providers/__tests__/LocalProvider.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { LocalProvider } from "../LocalProvider"

describe("LocalProvider", () => {
  it("initializes directory mode and returns blob nodes", async () => {
    const provider = new LocalProvider()
    const file = new File(["const a=1"], "src/a.ts", { type: "text/plain" })
    await provider.initialize({ source: "directory", files: { 0: file, length: 1 } as any })
    const tree = await provider.fetchTree("local://directory")
    expect(tree.some((node) => node.path.includes("a.ts"))).toBe(true)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/providers/__tests__/LocalProvider.test.ts`

Expected: FAIL with missing LocalProvider.

**Step 3: Write minimal implementation**

```ts
export class LocalProvider extends BaseProvider {
  // initialize(directory|zip), fetchTree, fetchFile
  // JSZip-backed zip parsing + FileReader for directory files
}
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/providers/__tests__/LocalProvider.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt/providers/LocalProvider.ts apps/packages/ui/src/components/Option/Repo2Txt/providers/__tests__/LocalProvider.test.ts
git commit -m "feat(ui): port repo2txt local provider"
```

### Task 5: Port file tree store/filter logic with tests

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/store/types.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/store/fileTreeSlice.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/store/index.ts`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/store/__tests__/fileTreeSlice.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { createRepo2TxtStore } from "../index"

describe("repo2txt file tree slice", () => {
  it("auto-selects common code extensions", () => {
    const store = createRepo2TxtStore()
    store.getState().setNodes([{ path: "src/app.ts", type: "blob" }])
    expect(store.getState().selectedPaths.has("src/app.ts")).toBe(true)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/store/__tests__/fileTreeSlice.test.ts`

Expected: FAIL with missing store module.

**Step 3: Write minimal implementation**

```ts
export const createRepo2TxtStore = () => create<Repo2TxtState>()(
  devtools((...a) => ({
    ...createFileTreeSlice(...a),
    // provider/ui slices as needed for V1
  }))
)
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/store/__tests__/fileTreeSlice.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt/store
git commit -m "feat(ui): add repo2txt file tree state"
```

### Task 6: Port formatter + tokenizer worker with tests

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/formatter/Formatter.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/formatter/TokenizerWorker.ts`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/workers/tokenizer.worker.ts`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/formatter/__tests__/Formatter.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"
import { Formatter } from "../Formatter"

describe("Formatter", () => {
  it("returns directory tree and token count", async () => {
    const output = await Formatter.formatAsync(
      [{ name: "a.ts", path: "a.ts", type: "file" }],
      [{ path: "a.ts", text: "const a=1" }]
    )
    expect(output.directoryTree).toContain("a.ts")
    expect(output.tokenCount).toBeGreaterThan(0)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/formatter/__tests__/Formatter.test.ts`

Expected: FAIL with missing formatter module.

**Step 3: Write minimal implementation**

```ts
export class Formatter {
  static async formatAsync(tree, fileContents, onProgress?) {
    // generate tree text + tokenize via worker + return counters
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/formatter/__tests__/Formatter.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt/formatter apps/packages/ui/src/components/Option/Repo2Txt/workers
git commit -m "feat(ui): add repo2txt formatter and tokenizer worker"
```

### Task 7: Build provider/file-tree/output UI and wire end-to-end page state

**Files:**
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/components/ProviderSelector.tsx`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/components/AdvancedFilters.tsx`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/components/FileTree.tsx`
- Create: `apps/packages/ui/src/components/Option/Repo2Txt/components/OutputPanel.tsx`
- Modify: `apps/packages/ui/src/components/Option/Repo2Txt/Repo2TxtPage.tsx`
- Test: `apps/packages/ui/src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.flow.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { Repo2TxtPage } from "../Repo2TxtPage"

describe("Repo2TxtPage flow", () => {
  it("keeps Generate disabled until a source is loaded", async () => {
    render(<Repo2TxtPage />)
    const generate = screen.getByRole("button", { name: /generate output/i })
    expect(generate).toBeDisabled()
    await userEvent.click(screen.getByRole("button", { name: /github/i }))
    expect(generate).toBeDisabled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.flow.test.tsx`

Expected: FAIL due to missing UI contract.

**Step 3: Write minimal implementation**

```tsx
// Repo2TxtPage orchestrates provider load, selection, formatAsync, and output panel state
// ProviderSelector emits source actions; OutputPanel handles copy/download.
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Option/Repo2Txt/__tests__/Repo2TxtPage.flow.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/components/Option/Repo2Txt
git commit -m "feat(ui): wire repo2txt page interactions"
```

### Task 8: Add required options/web discoverability surfaces

**Files:**
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/packages/ui/src/services/settings/ui-settings.ts`
- Modify (if currently used by the header shell): `apps/packages/ui/src/components/Layouts/ModeSelector.tsx`
- Test: `apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx` (extend existing harness)

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { HeaderShortcuts } from "../HeaderShortcuts"

describe("Header shortcuts repo2txt entry", () => {
  it("shows repo2txt shortcut item", () => {
    render(
      <MemoryRouter>
        <HeaderShortcuts expanded={true} onExpandedChange={() => {}} />
      </MemoryRouter>
    )
    expect(screen.getByText(/repo2txt/i)).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`

Expected: FAIL because repo2txt entry does not exist.

**Step 3: Write minimal implementation**

```ts
// add "repo2txt" to HeaderShortcutId list + header shortcut groups + settings/workspace navigation grouping.
// if ModeSelector is wired in the current header shell, also add repo2txt there; otherwise skip ModeSelector edits for V1.
// update HeaderShortcuts.test.tsx fixture lists (e.g., ALL_SHORTCUT_IDS) so visibility tests include repo2txt.
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/HeaderShortcuts.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/routes/route-registry.tsx apps/packages/ui/src/components/Layouts/header-shortcut-items.ts apps/packages/ui/src/services/settings/ui-settings.ts apps/packages/ui/src/components/Layouts/__tests__/HeaderShortcuts.test.tsx
git commit -m "feat(ui): expose repo2txt in options navigation"
```

### Task 8.1: Add i18n locale coverage for repo2txt copy

**Files:**
- Modify: `apps/packages/ui/src/assets/locale/en/option.json`
- Modify: `apps/packages/ui/src/assets/locale/*/option.json` (all locales required by repo parity policy)
- Generated update via sync: `apps/packages/ui/src/public/_locales/*/option.json`
- Test: `apps/packages/ui/src/routes/__tests__/repo2txt-locale-keys.test.ts`

**Step 1: Write the failing test**

```ts
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"
import enOption from "@/assets/locale/en/option.json"

const REQUIRED_KEYS = [
  "repo2txt.nav",
  "repo2txt.title",
  "repo2txt.description",
  "repo2txt.generate",
  "header.modeRepo2txt"
] as const

describe("repo2txt locale keys", () => {
  it("has required English option locale keys", () => {
    for (const key of REQUIRED_KEYS) {
      const value = key.split(".").reduce<any>((acc, seg) => acc?.[seg], enOption as any)
      expect(typeof value).toBe("string")
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })

  it("keeps repo2txt option keys present across locale directories", () => {
    const localeRoot = path.resolve(process.cwd(), "src/assets/locale")
    for (const locale of fs.readdirSync(localeRoot)) {
      const optionPath = path.join(localeRoot, locale, "option.json")
      expect(fs.existsSync(optionPath)).toBe(true)
      const parsed = JSON.parse(fs.readFileSync(optionPath, "utf8"))
      for (const key of REQUIRED_KEYS) {
        const value = key.split(".").reduce<any>((acc, seg) => acc?.[seg], parsed)
        expect(typeof value).toBe("string")
      }
    }
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/repo2txt-locale-keys.test.ts`

Expected: FAIL because repo2txt keys are missing.

**Step 3: Write minimal implementation**

```json
// Add repo2txt key group under option locale namespace in en + parity locales.
// Ensure keys align with route/nav tokens introduced in this plan:
// - option:repo2txt.nav
// - option:header.modeRepo2txt
```

Run locale sync/coverage checks:

```bash
cd <repo_worktree>/apps/extension && bun run locales:sync option.json
cd <repo_worktree>/apps/extension && bun run check:i18n:coverage
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd <repo_worktree>/apps/extension && bun run locales:sync option.json
cd <repo_worktree>/apps/extension && bun run check:i18n:coverage
cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/repo2txt-locale-keys.test.ts src/routes/__tests__/sidepanel-persona-locale-keys.test.ts src/tutorials/__tests__/locale-mirror.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/packages/ui/src/assets/locale apps/packages/ui/src/public/_locales apps/packages/ui/src/routes/__tests__/repo2txt-locale-keys.test.ts
git commit -m "feat(ui): add repo2txt locale keys and parity guard"
```

### Task 9: Add Next.js web page wrapper and test

**Files:**
- Create: `apps/tldw-frontend/pages/repo2txt.tsx`
- Modify: `apps/tldw-frontend/pages/_app.tsx` (optional prefetch inclusion if desired)
- Test: `apps/tldw-frontend/__tests__/pages/repo2txt.test.tsx`

**Step 1: Write the failing test**

```tsx
import { describe, expect, it } from "vitest"
import Repo2TxtPage from "@web/pages/repo2txt"

describe("web repo2txt page", () => {
  it("exports a page component", () => {
    expect(Repo2TxtPage).toBeTypeOf("function")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd <repo_worktree>/apps/tldw-frontend && bunx vitest run __tests__/pages/repo2txt.test.tsx`

Expected: FAIL because page file is missing.

**Step 3: Write minimal implementation**

```tsx
import dynamic from "next/dynamic"
export default dynamic(() => import("@/routes/option-repo2txt"), { ssr: false })
```

**Step 4: Run test to verify it passes**

Run: `cd <repo_worktree>/apps/tldw-frontend && bunx vitest run __tests__/pages/repo2txt.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/tldw-frontend/pages/repo2txt.tsx apps/tldw-frontend/__tests__/pages/repo2txt.test.tsx apps/tldw-frontend/pages/_app.tsx
git commit -m "feat(web): add repo2txt route wrapper"
```

### Task 10: Verify extension options compatibility, sidepanel link-out behavior, and host permissions

**Files:**
- Modify (if needed): `apps/extension/wxt.config.ts`
- Test: `apps/extension/tests/e2e/repo2txt-options.spec.ts` (new)
- Test: `apps/extension/tests/e2e/repo2txt-sidepanel-linkout.spec.ts` (new; for sidepanel affordance behavior)
- Modify (if needed): sidepanel action/menu module that exposes repo2txt as options link-out (`data-testid="sidepanel-open-repo2txt"`)

**Step 1: Write the failing tests**

```ts
import { expect, test } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"

test("repo2txt route loads in options", async () => {
  const { context, page, optionsUrl } = await launchWithBuiltExtension()
  await page.goto(`${optionsUrl}#/repo2txt`, { waitUntil: "domcontentloaded" })
  await expect(page.getByTestId("repo2txt-route-root")).toBeVisible()
  await context.close()
})
```

```ts
import { expect, test } from "@playwright/test"
import { launchWithBuiltExtension } from "./utils/extension-build"

test("sidepanel repo2txt affordance opens options link-out", async () => {
  const { context, openSidepanel } = await launchWithBuiltExtension()
  const sidepanel = await openSidepanel()
  const menuTrigger = sidepanel.getByRole("button", { name: /more options|menu|ingest/i }).first()
  if ((await menuTrigger.count()) > 0) {
    await menuTrigger.click()
  }
  const affordance = sidepanel.getByTestId("sidepanel-open-repo2txt")
  if ((await affordance.count()) === 0) {
    // V1 variant without a sidepanel affordance: ensure no accidental in-panel repo2txt entry exists.
    await expect(affordance).toHaveCount(0)
    await expect(sidepanel).not.toHaveURL(/repo2txt/i)
    await context.close()
    return
  }
  const [optionsPage] = await Promise.all([
    context.waitForEvent("page"),
    affordance.click()
  ])
  await optionsPage.waitForLoadState("domcontentloaded")
  await expect(optionsPage).toHaveURL(/options\.html#\/repo2txt/)
  await context.close()
})
```

**Step 2: Build extension and run tests to verify they fail**

Run:

```bash
cd <repo_worktree>/apps/extension && bun run build:chrome
cd <repo_worktree>/apps/extension && bun run test:e2e tests/e2e/repo2txt-options.spec.ts tests/e2e/repo2txt-sidepanel-linkout.spec.ts
```

Expected: FAIL when route wiring or sidepanel behavior is incomplete.

**Step 3: Write minimal implementation**

```ts
// Ensure options route resolves in extension options build.
// Ensure sidepanel repo2txt behavior is explicit:
// - if affordance exists, it opens `/options.html#/repo2txt` as link-out (not in-panel render)
// - if no affordance in V1, sidepanel has no repo2txt in-panel action.
// Add a stable affordance selector for E2E (e.g. `data-testid="sidepanel-open-repo2txt"`).
// Add api.github.com host permission only if runtime failures prove it is required.
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd <repo_worktree>/apps/extension && bun run build:chrome
cd <repo_worktree>/apps/extension && bun run test:e2e tests/e2e/repo2txt-options.spec.ts tests/e2e/repo2txt-sidepanel-linkout.spec.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/extension/wxt.config.ts apps/extension/tests/e2e/repo2txt-options.spec.ts apps/extension/tests/e2e/repo2txt-sidepanel-linkout.spec.ts
git commit -m "feat(extension): verify repo2txt options route and sidepanel link-out"
```

### Task 11: Full verification gate and docs update

**Files:**
- Modify: `apps/DEVELOPMENT.md` (optional short note for new route)
- Modify: `apps/tldw-frontend/README.md` (optional route mention)
- Modify: `apps/extension/README.md` (optional options route mention)

**Step 1: Write failing documentation check (optional)**

```md
Add one short "repo2txt route" note in each relevant doc.
```

**Step 2: Run verification commands**

Run:

```bash
cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/option-repo2txt.route.test.tsx src/components/Option/Repo2Txt/**/*.test.ts* src/components/Layouts/__tests__/HeaderShortcuts.test.tsx
cd <repo_worktree>/apps/packages/ui && bunx vitest run src/routes/__tests__/repo2txt-locale-keys.test.ts src/routes/__tests__/sidepanel-persona-locale-keys.test.ts src/tutorials/__tests__/locale-mirror.test.ts
cd <repo_worktree>/apps/tldw-frontend && bunx vitest run __tests__/pages/repo2txt.test.tsx
cd <repo_worktree>/apps/tldw-frontend && bun run compile
cd <repo_worktree>/apps/extension && bun run compile
cd <repo_worktree>/apps/extension && bun run build:chrome
cd <repo_worktree>/apps/extension && bun run test:e2e tests/e2e/repo2txt-options.spec.ts tests/e2e/repo2txt-sidepanel-linkout.spec.ts
```

Expected: all PASS with no typecheck errors.

**Step 3: Address any regressions with minimal fixes**

```ts
// Only fix failing assertions/types introduced by this feature.
```

**Step 4: Re-run verification**

Run the same verification command set; expected all PASS.

**Step 5: Commit**

```bash
cd <repo_worktree>
git add apps/DEVELOPMENT.md apps/tldw-frontend/README.md apps/extension/README.md
git commit -m "docs: document repo2txt options route"
```

## Final rollout checklist

- [ ] Route accessible at `/repo2txt` in web and extension options
- [ ] GitHub + Local provider flows pass manual smoke
- [ ] Output preview/copy/download validated
- [ ] i18n locale keys for repo2txt are present and parity checks pass
- [ ] Sidepanel repo2txt affordance (if present) remains link-out only for V1
- [ ] No regression in existing options/route shell
