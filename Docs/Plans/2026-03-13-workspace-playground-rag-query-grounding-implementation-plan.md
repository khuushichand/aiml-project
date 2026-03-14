# Workspace Playground RAG Query Grounding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ground workspace studio RAG retrieval queries in the selected sources so live artifact generation retrieves relevant content instead of falling back to generic no-context answers.

**Architecture:** Add a shared retrieval-query builder in `StudioPane/index.tsx` that derives a compact source-grounded query from the effective selected workspace sources. Update RAG-backed generators to use that grounded query plus small artifact-specific hints while leaving `generation_prompt` responsible for authoring instructions.

**Tech Stack:** React, TypeScript, Zustand, Vitest, Playwright, unified RAG API

---

### Task 1: Add failing request-contract tests

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`

**Step 1: Write the failing test**

Add a `summary` regression test that:

- renders `StudioPane` with ready selected sources that have titles
- triggers `Summary`
- inspects the mocked `ragSearch` call
- expects `query` to include selected source-title terms
- expects `generation_prompt` to remain present

Add a `data_table` regression test that:

- triggers `Data Table`
- expects the `query` not to equal the old generic string alone
- expects the grounded query to include selected source-title terms and data-table hints

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
```

Expected:

- new assertions fail because current generators still use generic retrieval queries

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx
git commit -m "test: lock grounded workspace rag query contract"
```

### Task 2: Implement grounded retrieval query building

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- Reference: `apps/packages/ui/src/store/workspace.ts`
- Reference: `apps/packages/ui/src/types/workspace.ts`

**Step 1: Write minimal implementation**

In `StudioPane/index.tsx`:

- read `getEffectiveSelectedSources` from the workspace store
- add a helper that converts selected `WorkspaceSource[]` into a compact grounded retrieval string
- update the RAG-backed generators to accept selected sources and use grounded queries with small artifact-specific suffixes

Keep the change minimal:

- no backend schema changes
- no parser redesign
- no unrelated refactors

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
git commit -m "fix: ground workspace studio rag queries in selected sources"
```

### Task 3: Verify live workspace behavior

**Files:**
- Temporary verification only: `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 1: Run targeted live verification**

With the local frontend and backend running, execute the workspace output probe and confirm that `Data Table` no longer fails with `No usable data table content was returned.`

Run:

```bash
TLDW_WEB_URL=http://localhost:3000 TLDW_SERVER_URL=http://127.0.0.1:8002 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY TLDW_WEB_AUTOSTART=false bunx playwright test e2e/workflows/workspace-playground.output-matrix.probe.spec.ts --reporter=line --workers=1
```

Expected:

- the matrix probe passes for the covered outputs
- `Data Table` completes and exposes view/download actions

**Step 2: Run security validation on touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx -f json -o /tmp/bandit_workspace_rag_query_grounding.json
```

Expected:

- no new findings
- possible TypeScript parse warning only

**Step 3: Clean temporary verification artifact if no longer needed**

Delete:

- `apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts`

**Step 4: Commit**

```bash
git add -u apps/tldw-frontend/e2e/workflows/workspace-playground.output-matrix.probe.spec.ts
git commit -m "chore: remove temporary workspace output probe"
```
