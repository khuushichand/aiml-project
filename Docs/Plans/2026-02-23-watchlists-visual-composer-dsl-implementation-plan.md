# Watchlists Visual Composer DSL Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Visual template composer for Watchlists with full bidirectional Visual↔Code round-trip, RawCodeBlock fallback for unsupported Jinja, and manual-only inline section generation plus final flow-check.

**Architecture:** Keep Jinja `content` as runtime source of truth while introducing dual persistence for `composer_ast` metadata. Implement a CST-first parser/projection/compile path that preserves unsupported syntax as raw blocks. Extend TemplateEditor modal with Visual/Code/Preview modes and manual orchestration controls.

**Tech Stack:** FastAPI, Pydantic, Watchlists template store + schemas/endpoints, React + TypeScript + Ant Design, Vitest, pytest.

---

## Scope and Constraints

- Manual authoring/preview orchestration only in v1.
- No scheduled run auto-orchestration.
- Visual composer on by default.
- Mixed advanced syntax model via `RawCodeBlock`.
- Core v1 block set only.

## Skill References

- `@test-driven-development`
- `@systematic-debugging`
- `@verification-before-completion`

## Stage 1: Backend Contract and Storage Extensions
**Goal**: Add dual-storage fields to watchlists template API and template metadata persistence.
**Success Criteria**:
- `GET/POST /api/v1/watchlists/templates` round-trip optional composer fields.
- Legacy templates without composer fields continue to load/save.
**Tests**:
- New schema/endpoint tests for optional fields and backward compatibility.
**Status**: Not Started

### Task 1: Extend schema contracts for composer metadata

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Modify: `apps/packages/ui/src/types/watchlists.ts`
- Test: `tldw_Server_API/tests/Watchlists/test_templates_rendering.py` (extend) or create `tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_contract.py`

**Step 1: Write the failing test**

```python
def test_template_detail_accepts_optional_composer_fields(client):
    payload = {
        "name": "composer_contract_test",
        "format": "md",
        "content": "# {{ title }}",
        "overwrite": True,
        "composer_ast": {"nodes": [{"type": "HeaderBlock"}]},
        "composer_schema_version": "1.0.0",
        "composer_sync_hash": "abc123",
        "composer_sync_status": "in_sync",
    }
    create = client.post("/api/v1/watchlists/templates", json=payload)
    assert create.status_code == 200
    body = create.json()
    assert body["composer_schema_version"] == "1.0.0"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_contract.py::test_template_detail_accepts_optional_composer_fields`

Expected: FAIL with schema validation or missing response fields.

**Step 3: Write minimal implementation**

- Add optional fields to:
  - `WatchlistTemplateSummary`
  - `WatchlistTemplateDetail`
  - `WatchlistTemplateCreateRequest`
- Add TS type support in `WatchlistTemplate` and `WatchlistTemplateCreate`.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py apps/packages/ui/src/types/watchlists.ts tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_contract.py
git commit -m "feat(watchlists): extend template schema with composer metadata fields"
```

### Task 2: Persist composer metadata in template store

**Files:**
- Modify: `tldw_Server_API/app/core/Watchlists/template_store.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Watchlists/test_watchlists_template_store.py`

**Step 1: Write the failing test**

```python
def test_template_store_persists_composer_metadata(tmp_path, monkeypatch):
    # save template with composer metadata, reload, assert metadata present
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_watchlists_template_store.py -k composer_metadata`

Expected: FAIL due to absent metadata serialization.

**Step 3: Write minimal implementation**

- Extend `TemplateRecord` with optional composer fields.
- Persist/reload fields in `*.meta.json`.
- Ensure existing metadata history logic remains unchanged.
- Update endpoint mappers to pass through these fields.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Watchlists/template_store.py tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/tests/Watchlists/test_watchlists_template_store.py
git commit -m "feat(watchlists): persist composer metadata in template store"
```

## Stage 2: CST/AST Round-Trip Engine with RawCodeBlock Fallback
**Goal**: Implement parser/projection/compile primitives for full Visual↔Code round-trip behavior.
**Success Criteria**:
- Supported constructs round-trip without semantic drift.
- Unsupported constructs become preserved raw blocks.
**Tests**:
- Unit + property-style round-trip tests.
**Status**: Not Started

### Task 3: Create composer AST model and round-trip helpers

**Files:**
- Create: `tldw_Server_API/app/core/Watchlists/template_composer_ast.py`
- Create: `tldw_Server_API/app/core/Watchlists/template_composer_roundtrip.py`
- Test: `tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py`

**Step 1: Write the failing test**

```python
def test_supported_header_and_item_loop_roundtrip_is_stable():
    src = "# {{ title }}\n{% for item in items %}\n{{ item.title }}\n{% endfor %}"
    ast = parse_jinja_to_composer_ast(src)
    out = compile_composer_ast_to_jinja(ast)
    assert "{% for item in items %}" in out
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py::test_supported_header_and_item_loop_roundtrip_is_stable`

Expected: FAIL with import/function-not-found errors.

**Step 3: Write minimal implementation**

- Define v1 node dataclasses and `RawCodeBlock`.
- Implement `parse_jinja_to_composer_ast` for supported patterns.
- Implement `compile_composer_ast_to_jinja`.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Watchlists/template_composer_ast.py tldw_Server_API/app/core/Watchlists/template_composer_roundtrip.py tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py
git commit -m "feat(watchlists): add composer ast and initial roundtrip engine"
```

### Task 4: Add RawCodeBlock fallback for unsupported syntax

**Files:**
- Modify: `tldw_Server_API/app/core/Watchlists/template_composer_roundtrip.py`
- Test: `tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py`

**Step 1: Write the failing test**

```python
def test_unsupported_macro_preserved_as_raw_code_block():
    src = "{% macro card(x) %}{{ x }}{% endmacro %}{{ card(title) }}"
    ast = parse_jinja_to_composer_ast(src)
    assert any(node["type"] == "RawCodeBlock" for node in ast["nodes"])
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py -k raw_code_block`

Expected: FAIL because unsupported syntax is dropped or errors.

**Step 3: Write minimal implementation**

- Detect unsupported CST segments.
- Wrap them as `RawCodeBlock` with exact source slices.
- Ensure compile emits preserved raw source.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Watchlists/template_composer_roundtrip.py tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py
git commit -m "feat(watchlists): preserve unsupported jinja in raw code blocks"
```

## Stage 3: Manual Orchestration Endpoints (Section + Flow Check)
**Goal**: Add API endpoints for manual section generation and final flow-check diff workflow.
**Success Criteria**:
- Endpoints work with run-backed context and return deterministic payloads.
- No scheduled path integration.
**Tests**:
- New endpoint tests for happy/failure paths and mode handling.
**Status**: Not Started

### Task 5: Add section composition endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Watchlists/test_template_endpoints.py`

**Step 1: Write the failing test**

```python
def test_compose_section_returns_generated_text(client, seeded_run):
    payload = {"run_id": seeded_run.id, "block_id": "intro", "prompt": "Write concise intro"}
    res = client.post("/api/v1/watchlists/templates/compose/section", json=payload)
    assert res.status_code == 200
    assert "content" in res.json()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_template_endpoints.py -k compose_section`

Expected: FAIL (route not found).

**Step 3: Write minimal implementation**

- Add request/response schemas.
- Add endpoint skeleton with run lookup and placeholder generation path.
- Return `content`, `warnings`, `diagnostics`.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/tests/Watchlists/test_template_endpoints.py
git commit -m "feat(watchlists): add manual section composition endpoint"
```

### Task 6: Add final flow-check endpoint with suggest/auto-apply modes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Test: `tldw_Server_API/tests/Watchlists/test_template_endpoints.py`

**Step 1: Write the failing test**

```python
def test_flow_check_returns_diff_in_suggest_mode(client, seeded_run):
    payload = {
        "run_id": seeded_run.id,
        "mode": "suggest_only",
        "sections": [{"id": "intro", "content": "..."}, {"id": "body", "content": "..."}],
    }
    res = client.post("/api/v1/watchlists/templates/compose/flow-check", json=payload)
    assert res.status_code == 200
    assert "diff" in res.json()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_template_endpoints.py -k flow_check`

Expected: FAIL (route not found).

**Step 3: Write minimal implementation**

- Add suggest and auto-apply response branches.
- Include issue categories and reversible patch payload.
- Ensure no job scheduler bindings are introduced.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/tests/Watchlists/test_template_endpoints.py
git commit -m "feat(watchlists): add manual flow-check endpoint with dual modes"
```

## Stage 4: Visual Composer UI in TemplateEditor
**Goal**: Implement Visual mode in existing modal with block editing and orchestration controls.
**Success Criteria**:
- Visual mode usable for v1 core block set.
- Code and preview modes remain functional.
**Tests**:
- New component tests for block CRUD, mode switching, and manual orchestration actions.
**Status**: Not Started

### Task 7: Introduce composer types/state and Visual mode scaffolding

**Files:**
- Create: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/composer-types.ts`
- Create: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/VisualComposerPane.tsx`
- Modify: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx`
- Test: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.visual-mode.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders Visual mode and core block controls", async () => {
  render(<TemplateEditor open template={null} onClose={vi.fn()} />)
  expect(screen.getByText("Visual")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.visual-mode.test.tsx`

Expected: FAIL (missing mode and components).

**Step 3: Write minimal implementation**

- Add authoring mode toggle entries.
- Render `VisualComposerPane` with placeholder block list and add/remove actions.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/composer-types.ts apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/VisualComposerPane.tsx apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.visual-mode.test.tsx
git commit -m "feat(watchlists-ui): add visual composer mode scaffold"
```

### Task 8: Implement Visual↔Code sync and RawCodeBlock presentation

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx`
- Modify: `apps/packages/ui/src/services/watchlists.ts`
- Create: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/composer-roundtrip.ts`
- Test: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.roundtrip.test.tsx`

**Step 1: Write the failing test**

```tsx
it("preserves unsupported code as RawCodeBlock after code edits", async () => {
  // seed editor with macro in Code mode
  // switch to Visual mode
  // assert RawCodeBlock appears
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.roundtrip.test.tsx`

Expected: FAIL due to no round-trip adapter.

**Step 3: Write minimal implementation**

- Add API contract calls for composer parse/projection data if required.
- Implement client adapter for code-to-visual sync.
- Render RawCodeBlock with warning and code-mode edit guidance.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/composer-roundtrip.ts apps/packages/ui/src/services/watchlists.ts apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.roundtrip.test.tsx
git commit -m "feat(watchlists-ui): implement visual code roundtrip with raw block fallback"
```

## Stage 5: Manual Section Generation and Flow-Check Diff UX
**Goal**: Wire section generation and final flow-check modes into preview workflow.
**Success Criteria**:
- User can run section generation per block.
- User can run flow-check in suggest-only or auto-apply mode and review diffs.
**Tests**:
- Component tests for action states, diff acceptance/revert.
**Status**: Not Started

### Task 9: Add manual section generation controls

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/VisualComposerPane.tsx`
- Modify: `apps/packages/ui/src/services/watchlists.ts`
- Test: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/VisualComposerPane.section-generation.test.tsx`

**Step 1: Write the failing test**

```tsx
it("runs section generation and updates block content", async () => {
  // click Generate section
  // assert service called and content updated
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/VisualComposerPane.section-generation.test.tsx`

Expected: FAIL (button/action missing).

**Step 3: Write minimal implementation**

- Add `Generate section` action per prompt-capable block.
- Handle pending/error/success states.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/VisualComposerPane.tsx apps/packages/ui/src/services/watchlists.ts apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/VisualComposerPane.section-generation.test.tsx
git commit -m "feat(watchlists-ui): add manual section generation in visual composer"
```

### Task 10: Add final flow-check UI with suggest/auto-apply

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx`
- Create: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/FlowCheckDiffPanel.tsx`
- Test: `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/FlowCheckDiffPanel.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders flow-check diff and supports accept/reject actions", async () => {
  render(<FlowCheckDiffPanel diff={mockDiff} onAcceptChunk={vi.fn()} onRejectChunk={vi.fn()} />)
  expect(screen.getByText("Accept")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/FlowCheckDiffPanel.test.tsx`

Expected: FAIL (component missing).

**Step 3: Write minimal implementation**

- Create diff panel component.
- Add mode selector (`suggest-only`, `auto-apply`).
- Wire accept/reject/revert handlers.

**Step 4: Run test to verify it passes**

Run: same command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatePreviewPane.tsx apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/FlowCheckDiffPanel.tsx apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/__tests__/FlowCheckDiffPanel.test.tsx
git commit -m "feat(watchlists-ui): add final flow-check diff workflow"
```

## Stage 6: Verification, Security Scan, and Documentation
**Goal**: Prove quality gates and update docs for maintainers/users.
**Success Criteria**:
- Targeted tests pass.
- Bandit scan on touched backend files is clean for new findings.
- Docs updated for manual-only orchestration semantics.
**Tests**:
- Pytest/Vitest targeted suites + Bandit command.
**Status**: Not Started

### Task 11: Run verification suite and Bandit

**Files:**
- Verify: touched backend/frontend files
- Modify (if needed): failing tests/docs discovered during verification

**Step 1: Run backend targeted tests**

Run:
`source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Watchlists/test_watchlists_template_store.py tldw_Server_API/tests/Watchlists/test_template_endpoints.py tldw_Server_API/tests/Watchlists/test_watchlists_template_composer_roundtrip.py`

Expected: PASS.

**Step 2: Run frontend targeted tests**

Run:
`cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.visual-mode.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/TemplateEditor.roundtrip.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/VisualComposerPane.section-generation.test.tsx src/components/Option/Watchlists/TemplatesTab/__tests__/FlowCheckDiffPanel.test.tsx`

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:
`source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/app/core/Watchlists/template_store.py tldw_Server_API/app/core/Watchlists/template_composer_roundtrip.py -f json -o /tmp/bandit_watchlists_visual_composer.json`

Expected: No new high-confidence findings in changed code.

**Step 4: Fix findings/tests if needed and re-run**

- Apply minimal fixes.
- Re-run failed command(s) until green.

**Step 5: Commit**

```bash
git add tldw_Server_API apps/packages/ui Docs/Plans
git commit -m "chore(watchlists): verify visual composer implementation and security checks"
```

### Task 12: Update user/developer docs

**Files:**
- Modify: `Docs/API-related/Watchlists_API.md`
- Modify: `Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`
- Optional: `apps/packages/ui/src/assets/locale/en/watchlists.json` help text keys

**Step 1: Write failing docs test or contract check (if available)**

If no docs test exists, define manual checklist item in runbook and treat as required validation artifact.

**Step 2: Update docs with new behavior**

- Visual composer overview.
- RawCodeBlock fallback explanation.
- Manual-only orchestration explicit statement.
- Flow-check modes and limits.

**Step 3: Verify docs links and examples**

Run:
`cd /Users/macbook-dev/Documents/GitHub/tldw_server2 && rg -n "compose/section|compose/flow-check|RawCodeBlock|manual-only" Docs/API-related/Watchlists_API.md Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md`

Expected: expected strings present with consistent terminology.

**Step 4: Commit**

```bash
git add Docs/API-related/Watchlists_API.md Docs/Plans/WATCHLISTS_TEMPLATE_AUTHORING_RUNBOOK_2026_02_23.md
git commit -m "docs(watchlists): document visual composer and manual flow-check workflow"
```

---

## Execution Notes

- Keep commits frequent and scoped to one task.
- Use `RawCodeBlock` fallback rather than dropping unsupported syntax.
- Never enable scheduled orchestration in this plan.
- If round-trip parser issues repeat 3 times, stop and apply `@systematic-debugging`.

