# MCP Hub Navigation Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MCP Hub discoverable from the command palette, make `/settings/mcp-hub` behave like a real settings page, and restore MCP Hub route parity in the extension without duplicate command-palette entries.

**Architecture:** Keep the standalone MCP Hub route and the settings-shell MCP Hub route distinct. Use a dedicated shared settings-route wrapper for `/settings/mcp-hub`, add one top-level command-palette navigation command for MCP Hub, and dedupe command-palette results by target route so the existing settings search entry does not produce a duplicate result. Mirror the same route surface in the extension registry using its existing settings-route conventions.

**Tech Stack:** React, TypeScript, shared UI route registries, extension route registry, Vitest, React Testing Library

---

## File Structure

- `apps/packages/ui/src/routes/option-settings-mcp-hub.tsx`
  Purpose: dedicated shared settings-shell wrapper for `McpHubPage` so `/settings/mcp-hub` renders inside `SettingsRoute` and `SettingsLayout`.
- `apps/packages/ui/src/routes/route-registry.tsx`
  Purpose: keep the shared route contract aligned so `/settings/mcp-hub` points at the settings-shell route while `/mcp-hub` remains the standalone route.
- `apps/packages/ui/src/routes/option-settings-route-registry.tsx`
  Purpose: fix the actual runtime path used by `DeferredOptionsRoute` for `/settings/*`.
- `apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx`
  Purpose: keep source-level route registration for `/mcp-hub` and `/settings/mcp-hub` locked.
- `apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx`
  Purpose: prove the shared settings-shell wrapper renders MCP Hub with settings navigation present.
- `apps/packages/ui/src/components/Common/CommandPalette.tsx`
  Purpose: add the MCP Hub top-level navigation command and dedupe commands that target the same route.
- `apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx`
  Purpose: verify the default MCP Hub command appears and query-time results do not duplicate the same route.
- `apps/tldw-frontend/extension/routes/option-mcp-hub.tsx`
  Purpose: extension standalone MCP Hub route wrapper using the extension/web layout shell.
- `apps/tldw-frontend/extension/routes/route-registry.tsx`
  Purpose: register `/settings/mcp-hub` and `/mcp-hub` in the extension, with nav metadata on the settings path.
- `apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts`
  Purpose: lock extension MCP Hub route parity and nav token wiring.

## Task 1: Fix The Shared Settings-Shell Runtime For `/settings/mcp-hub`

**Files:**
- Create: `apps/packages/ui/src/routes/option-settings-mcp-hub.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/routes/option-settings-route-registry.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx`

- [ ] **Step 1: Write the failing shared settings-shell test**

Create `apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx` and assert the settings-shell route renders both the MCP Hub heading and the settings navigation container.

```tsx
render(
  <MemoryRouter initialEntries={["/settings/mcp-hub"]}>
    <Routes>
      <Route path="*" element={<OptionSettingsMcpHub />} />
    </Routes>
  </MemoryRouter>
)

expect(screen.getByTestId("settings-navigation")).toBeInTheDocument()
expect(screen.getByRole("heading", { name: /mcp hub/i })).toBeInTheDocument()
```

Mock expensive MCP Hub tab dependencies if needed so the test only proves shell wiring.

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx --reporter=verbose
```

Expected: FAIL because `OptionSettingsMcpHub` does not exist yet.

- [ ] **Step 3: Write the minimal shared settings-shell route**

Create `apps/packages/ui/src/routes/option-settings-mcp-hub.tsx` with a small wrapper that uses `SettingsRoute`, `PageShell`, and `McpHubPage`.

```tsx
import { SettingsRoute } from "./settings-route"
import { PageShell } from "@/components/Common/PageShell"
import { McpHubPage } from "@/components/Option/MCPHub"

const OptionSettingsMcpHub = () => (
  <SettingsRoute>
    <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
      <McpHubPage />
    </PageShell>
  </SettingsRoute>
)
```

Then update both shared registries so:

- `/settings/mcp-hub` points to `lazy(() => import("./option-settings-mcp-hub"))`
- `/mcp-hub` continues to point to the existing standalone `option-mcp-hub`

Also expand `mcp-hub-route.test.tsx` so it reads both `route-registry.tsx` and `option-settings-route-registry.tsx`, not just the main route registry.

- [ ] **Step 4: Re-run the shared route tests**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx \
  ../packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx \
  --reporter=verbose
```

Expected: PASS, with the settings-shell test finding both `settings-navigation` and the `MCP Hub` heading.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-settings-mcp-hub.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/routes/option-settings-route-registry.tsx \
  apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx
git commit -m "feat: route settings mcp hub through settings shell"
```

## Task 2: Add The MCP Hub Command-Palette Entry Without Duplicate Results

**Files:**
- Modify: `apps/packages/ui/src/components/Common/CommandPalette.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx`

- [ ] **Step 1: Write the failing command-palette tests**

Create `apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx` with two expectations:

1. when the palette opens with an empty query, `Go to MCP Hub` is present
2. when the user types `mcp`, only one MCP Hub route result is shown

```tsx
window.dispatchEvent(new CustomEvent("tldw:open-command-palette"))
expect(await screen.findByRole("option", { name: /go to mcp hub/i })).toBeInTheDocument()

await user.type(screen.getByPlaceholderText(/type a command/i), "mcp")
expect(screen.getAllByRole("option", { name: /mcp hub/i })).toHaveLength(1)
```

Mock `useTranslation` the same way the existing command-palette tests do.

- [ ] **Step 2: Run the new command-palette test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx --reporter=verbose
```

Expected: FAIL because there is no dedicated MCP Hub navigation command and the query path will surface the settings-search entry only.

- [ ] **Step 3: Implement the minimal command and dedupe contract**

Update `CommandPalette.tsx` to:

- add `targetPath?: string` to `CommandItem`
- set `targetPath` for route-based navigation commands and setting-derived commands
- add a top-level `Go to MCP Hub` command that navigates to `/settings/mcp-hub`
- dedupe commands in `allCommands` by `targetPath`, preferring non-`setting` commands over `setting` duplicates

```tsx
const dedupedCommands = new Map<string, CommandItem>()
for (const cmd of [...defaultCommands, ...additionalCommands, ...settingCommands]) {
  const dedupeKey = cmd.targetPath ?? cmd.id
  const existing = dedupedCommands.get(dedupeKey)
  if (!existing || (existing.category === "setting" && cmd.category !== "setting")) {
    dedupedCommands.set(dedupeKey, cmd)
  }
}
return [...dedupedCommands.values()]
```

Use MCP-aware keywords like `["mcp", "hub", "acp", "policy", "server"]`.

- [ ] **Step 4: Re-run the command-palette tests**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx \
  ../packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx \
  --reporter=verbose
```

Expected: PASS, with the MCP Hub default command visible on open and the `mcp` query returning a single MCP Hub option.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/CommandPalette.tsx \
  apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx
git commit -m "feat: expose mcp hub in command palette"
```

## Task 3: Add MCP Hub Route Parity To The Extension

**Files:**
- Create: `apps/tldw-frontend/extension/routes/option-mcp-hub.tsx`
- Modify: `apps/tldw-frontend/extension/routes/route-registry.tsx`
- Create: `apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts`
- Test: `apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts`

- [ ] **Step 1: Write the failing extension parity test**

Create `apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts` as a source-level contract test.

```ts
expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/settings\/mcp-hub"/)
expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/mcp-hub"/)
expect(extensionRouteRegistrySource).toMatch(/labelToken:\s*"settings:mcpHubNav"/)
```

- [ ] **Step 2: Run the extension parity test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/extension/route-registry.mcp-hub.test.ts --reporter=verbose
```

Expected: FAIL because the extension registry currently has no MCP Hub route entries.

- [ ] **Step 3: Implement the minimal extension route parity**

Create `apps/tldw-frontend/extension/routes/option-mcp-hub.tsx` as the standalone extension wrapper:

```tsx
import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { McpHubPage } from "@/components/Option/MCPHub"

const OptionMcpHub = () => (
  <OptionLayout>
    <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
      <McpHubPage />
    </PageShell>
  </OptionLayout>
)
```

Then update `apps/tldw-frontend/extension/routes/route-registry.tsx` to:

- add a lazy import for the standalone `./option-mcp-hub`
- add a settings-shell route for `/settings/mcp-hub` using the extension `createSettingsRoute(() => import("~/components/Option/MCPHub"), "McpHubPage")`
- add nav metadata with `labelToken: "settings:mcpHubNav"`
- add `/mcp-hub` as a plain options route pointing to the standalone wrapper

- [ ] **Step 4: Re-run the extension parity tests**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  __tests__/extension/route-registry.persona.test.ts \
  __tests__/extension/route-registry.acp.test.ts \
  __tests__/extension/route-registry.mcp-hub.test.ts \
  --reporter=verbose
```

Expected: PASS, with the new MCP Hub assertions green and the existing registry contract tests still green.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/extension/routes/option-mcp-hub.tsx \
  apps/tldw-frontend/extension/routes/route-registry.tsx \
  apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts
git commit -m "feat: add mcp hub extension route parity"
```

## Task 4: Run Final Focused Verification And Record The Clean State

**Files:**
- Test: `apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx`
- Test: `apps/tldw-frontend/__tests__/extension/route-registry.persona.test.ts`
- Test: `apps/tldw-frontend/__tests__/extension/route-registry.acp.test.ts`
- Test: `apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts`

- [ ] **Step 1: Run the shared UI route and command-palette test batch**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx \
  ../packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx \
  ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx \
  ../packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 2: Run the extension registry test batch**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  __tests__/extension/route-registry.persona.test.ts \
  __tests__/extension/route-registry.acp.test.ts \
  __tests__/extension/route-registry.mcp-hub.test.ts \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 3: Verify no extra MCP Hub result appears for `mcp` query during final manual check**

Do a quick interactive spot-check in the command-palette test or local app:

- open the palette
- type `mcp`
- confirm only one MCP Hub option is shown
- select it and confirm the UI lands in the settings shell

If you automate this in a test during earlier tasks, just re-run that test instead of adding a second mechanism.

- [ ] **Step 4: Record final verification notes**

Note in the implementation summary:

- `/settings/mcp-hub` now renders inside settings navigation
- the palette default list includes MCP Hub
- typed `mcp` searches return one MCP Hub result
- extension route parity is restored for `/settings/mcp-hub` and `/mcp-hub`

- [ ] **Step 5: Commit any final test adjustments**

```bash
git add apps/packages/ui/src/routes/__tests__/option-settings-mcp-hub.test.tsx \
  apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx \
  apps/packages/ui/src/components/Common/__tests__/CommandPalette.mcp-hub.test.tsx \
  apps/tldw-frontend/__tests__/extension/route-registry.mcp-hub.test.ts
git commit -m "test: verify mcp hub navigation parity"
```

