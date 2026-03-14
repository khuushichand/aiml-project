# Workspace Playground Data Table Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/workspace-playground` `Data Table` generation reliable by replacing the brittle unified-RAG retrieval path with direct selected-source content extraction plus constrained chat-completion formatting.

**Architecture:** Keep the existing shared studio result validation and the existing unified-RAG flows for other output types. For `data_table` only, fetch the selected source content directly from the media API, build a bounded source-context payload, generate markdown-table output through chat completion, then parse that table into structured artifact data.

**Tech Stack:** React, TypeScript, Zustand, Vitest, Playwright, existing `tldwClient` media and chat APIs

---

### Task 1: Add failing request-contract tests

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`

**Step 1: Write the failing test**

Add a `Data Table` regression test that:

- renders `StudioPane` with multiple selected sources
- triggers `Data Table`
- expects `getMediaDetails(...)` to be called for each selected media id
- expects `createChatCompletion(...)` to receive the selected source titles and source text
- expects `ragSearch(...)` not to be called
- expects the resulting artifact to store both raw markdown and parsed table data

Keep the existing `summary` and `compare_sources` tests unchanged so they continue locking the current RAG request contract.

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
```

Expected:

- the new `Data Table` assertions fail because the page still uses generic RAG generation

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
git commit -m "test: lock workspace data table direct-content contract"
```

### Task 2: Implement the direct-content data-table path

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- Reference: `apps/packages/ui/src/store/workspace.ts`
- Reference: `apps/packages/ui/src/types/workspace.ts`

**Step 1: Write minimal implementation**

In `StudioPane/index.tsx`:

- read `getEffectiveSelectedSources()` from the workspace store
- derive the selected source records for the current media ids
- add helper extraction for usable media-detail text
- fetch source content through `tldwClient.getMediaDetails(...)`
- clip per-source and total prompt payload size
- send the bounded source context to `tldwClient.createChatCompletion(...)`
- parse the markdown table and return it in `GenerationResult.data.table`

Keep the change minimal:

- no backend schema changes
- no new background job dependency
- no changes to other output generators unless needed for shared helper reuse

**Step 2: Run tests to verify they pass**

Run:

```bash
bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
```

Expected:

- both updated suites pass

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
git commit -m "fix: generate workspace data tables from selected source content"
```

### Task 3: Verify live workspace behavior

**Files:**
- Temporary verification only: `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 1: Run targeted live verification**

With the local frontend and backend running, execute the workspace output probe and confirm that `Data Table` now completes and yields a usable download.

Run:

```bash
TLDW_WEB_URL=http://localhost:3000 TLDW_SERVER_URL=http://127.0.0.1:8002 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY TLDW_WEB_AUTOSTART=false bunx playwright test e2e/workflows/workspace-playground.output-matrix.probe.spec.ts --reporter=line --workers=1
```

Expected:

- the probe passes for the covered outputs
- `Data Table` no longer fails with `No usable data table content was returned.`

**Step 2: Run security validation on touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx -f json -o /tmp/bandit_workspace_data_table_fix.json
```

Expected:

- no security findings
- TypeScript AST parse errors only

**Step 3: Clean temporary verification artifact if no longer needed**

Delete:

- `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 4: Commit**

```bash
git add -u apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts
git commit -m "chore: remove temporary workspace output probe"
```
