# Workspace Playground Mind Map Direct-Content Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/workspace-playground` `Mind Map` generation reliable by replacing the brittle unified-RAG retrieval path with selected-source content extraction plus constrained Mermaid chat completion.

**Architecture:** Keep the current `Mind Map` completion validation, but switch the generator to the same direct-content pattern used for `Data Table`. Resolve a usable chat model, fetch selected source text, ask for Mermaid `mindmap` output only, then store the extracted Mermaid code on the artifact.

**Tech Stack:** React, TypeScript, Zustand, Vitest, Playwright, existing `tldwClient` media and chat APIs

---

### Task 1: Add failing request-contract tests

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`

**Step 1: Write the failing test**

Add a `Mind Map` regression test that:

- renders `StudioPane` with selected sources
- triggers `Mind Map`
- expects `getMediaDetails(...)` to be called for each selected media id
- expects `createChatCompletion(...)` to receive a Mermaid-specific prompt
- expects `ragSearch(...)` not to be called
- expects the artifact to complete with Mermaid content and `data.mermaid`

Add a second regression proving `Mind Map` resolves the first available chat model when no explicit model is selected.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
```

Expected:

- the new `Mind Map` assertions fail because the generator still uses RAG

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
git commit -m "test: lock workspace mind map direct-content contract"
```

### Task 2: Implement the direct-content mind-map path

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`

**Step 1: Write minimal implementation**

In `StudioPane/index.tsx`:

- add a `Mind Map` direct-content generator parallel to the existing `Data Table` helper
- reuse the media-detail text extraction and chat-model resolution patterns
- prompt the model to return Mermaid `mindmap` output only
- extract Mermaid code and save it in `GenerationResult.data.mermaid`
- update the `mindmap` switch case to call the new generator

Keep the change minimal:

- no backend changes
- no changes to the Mermaid renderer
- no relaxation of completion validation

**Step 2: Run tests to verify they pass**

Run:

```bash
bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
```

Expected:

- the updated suite passes

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
git commit -m "fix: generate workspace mind maps from selected source content"
```

### Task 3: Verify the live workspace page

**Files:**
- Temporary verification only: `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 1: Run focused live verification**

Run:

```bash
TLDW_WEB_URL=http://localhost:3000 TLDW_SERVER_URL=http://127.0.0.1:8002 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY TLDW_WEB_AUTOSTART=false bunx playwright test e2e/workflows/workspace-playground.output-matrix.probe.spec.ts --reporter=line --workers=1
```

Expected:

- `Mind Map` completes
- `Data Table` still completes
- downloads remain usable for the covered outputs

**Step 2: Run broader workspace verification**

Run:

```bash
TLDW_WEB_URL=http://localhost:3000 TLDW_SERVER_URL=http://127.0.0.1:8002 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY TLDW_WEB_AUTOSTART=false bunx playwright test e2e/workflows/workspace-playground.parity.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts e2e/workflows/workspace-playground.spec.ts --reporter=line --workers=1
```

Expected:

- the workspace interaction suites pass

**Step 3: Run security validation**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx -f json -o /tmp/bandit_workspace_mindmap_fix.json
```

Expected:

- no security findings
- TypeScript AST parse errors only

**Step 4: Clean temporary verification artifact if no longer needed**

Delete:

- `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 5: Commit**

```bash
git add -u apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts
git commit -m "chore: remove temporary workspace output probe"
```
