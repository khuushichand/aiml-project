# Prompt Schema Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared structured prompt-definition foundation for Prompt Studio and the regular Prompts workspace, with server-side validation and assembly, legacy compatibility rendering, and phased UI adoption.

**Architecture:** Add a new backend `structured_prompts` package that owns the canonical prompt-definition model, validation, assembly, compatibility rendering, and preview output. Extend both prompt persistence layers to store explicit `legacy` versus `structured` formats, then wire Prompt Studio and the regular Prompts workspace to consume the shared backend contract rather than editing or executing raw prompt strings as the source of truth.

**Tech Stack:** FastAPI, Pydantic v2, Loguru, SQLite-backed prompt stores and migrations, existing Prompt Studio services, Dexie, React, Ant Design, TanStack Query, Vitest, pytest, Bandit.

**Implementation scope note:** v1 supports ordered blocks plus variables only. Do not introduce conditionals, loops, Jinja execution, or a general prompt DSL while executing this plan.

**Migration discipline note:** Do not edit historical Prompt Studio migrations once this work starts. Add new additive migrations for schema changes and let fresh databases reach the new shape by applying the full ordered migration chain.

---

### Task 1: Create the Shared Structured Prompt Domain Models and Validator

**Files:**
- Create: `tldw_Server_API/app/core/Prompt_Management/structured_prompts/__init__.py`
- Create: `tldw_Server_API/app/core/Prompt_Management/structured_prompts/models.py`
- Create: `tldw_Server_API/app/core/Prompt_Management/structured_prompts/validator.py`
- Create: `tldw_Server_API/tests/Prompt_Management/test_structured_prompt_validator.py`

**Step 1: Write the failing test**

```python
def test_validator_rejects_duplicate_variable_names():
    definition = {
        "schema_version": 1,
        "format": "structured",
        "variables": [
            {"name": "topic", "required": True, "input_type": "textarea"},
            {"name": "topic", "required": False, "input_type": "text"},
        ],
        "blocks": [],
    }

    errors = validate_prompt_definition(definition)

    assert errors[0].code == "duplicate_variable_name"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_validator.py::test_validator_rejects_duplicate_variable_names -v
```

Expected: FAIL with import errors because the structured prompt package does not exist yet.

**Step 3: Write minimal implementation**

```python
class PromptVariableDefinition(BaseModel):
    name: str
    required: bool = False
    input_type: str = "text"


class PromptBlock(BaseModel):
    id: str
    name: str
    role: Literal["system", "developer", "user", "assistant"]
    content: str
    enabled: bool = True
    order: int
    is_template: bool = False


def validate_prompt_definition(definition: dict[str, Any]) -> list[ValidationIssue]:
    ...
```

Keep validation strict and boring. Reject duplicate variable names, invalid roles, duplicate block ids, and unsupported schema versions.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_validator.py -v
```

Expected: PASS for validation coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Prompt_Management/structured_prompts/__init__.py \
        tldw_Server_API/app/core/Prompt_Management/structured_prompts/models.py \
        tldw_Server_API/app/core/Prompt_Management/structured_prompts/validator.py \
        tldw_Server_API/tests/Prompt_Management/test_structured_prompt_validator.py
git commit -m "feat: add structured prompt models and validator"
```

### Task 2: Build the Shared Prompt Assembler and Legacy Renderer

**Files:**
- Create: `tldw_Server_API/app/core/Prompt_Management/structured_prompts/assembler.py`
- Create: `tldw_Server_API/app/core/Prompt_Management/structured_prompts/legacy_renderer.py`
- Create: `tldw_Server_API/tests/Prompt_Management/test_structured_prompt_assembler.py`

**Step 1: Write the failing test**

```python
def test_assembler_returns_canonical_messages_and_legacy_snapshot():
    definition = make_definition(
        blocks=[
            {"id": "sys", "name": "Identity", "role": "system", "content": "You are precise.", "order": 10},
            {"id": "task", "name": "Task", "role": "user", "content": "Summarize {{topic}}", "order": 20, "is_template": True},
        ],
        variables=[{"name": "topic", "required": True, "input_type": "text"}],
    )

    result = assemble_prompt_definition(definition, {"topic": "SQLite FTS"})

    assert result.messages == [
        {"role": "system", "content": "You are precise."},
        {"role": "user", "content": "Summarize SQLite FTS"},
    ]
    assert result.legacy.system_prompt == "You are precise."
    assert result.legacy.user_prompt == "Summarize SQLite FTS"
```

```python
def test_assembler_inserts_few_shot_examples_and_modules_at_fixed_points():
    definition = make_definition(...)

    result = assemble_prompt_definition(
        definition,
        {"topic": "SQLite FTS"},
        extras={
            "few_shot_examples": [
                {
                    "inputs": {"topic": "Indexes"},
                    "outputs": {"answer": "Use the covering index."},
                }
            ],
            "modules_config": [
                {"type": "style_rules", "enabled": True, "config": {"tone": "concise"}}
            ],
        },
    )

    assert any(message["role"] == "assistant" for message in result.messages)
    assert "concise" in result.legacy.system_prompt
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_assembler.py::test_assembler_returns_canonical_messages_and_legacy_snapshot -v
```

Expected: FAIL because no assembler exists yet.

**Step 3: Write minimal implementation**

```python
def assemble_prompt_definition(definition: PromptDefinition, variables: dict[str, Any], extras: dict[str, Any] | None = None) -> PromptAssemblyResult:
    ...


def render_legacy_snapshot(messages: list[dict[str, str]]) -> PromptLegacySnapshot:
    ...
```

Use one strict `{{variable}}` substitution engine. Do not call Jinja for structured prompts. Preserve block order, collapse `system` and `developer` into legacy system output, and collapse `user` blocks into legacy user output.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_assembler.py -v
```

Expected: PASS, including missing-variable, compatibility-rendering, and extras insertion tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Prompt_Management/structured_prompts/assembler.py \
        tldw_Server_API/app/core/Prompt_Management/structured_prompts/legacy_renderer.py \
        tldw_Server_API/tests/Prompt_Management/test_structured_prompt_assembler.py
git commit -m "feat: add structured prompt assembler and legacy renderer"
```

### Task 3: Extend the Regular Prompts Persistence Layer for Structured Prompts

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/prompts_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/prompts.py`
- Create: `tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_structured_api.py`

**Step 1: Write the failing test**

```python
def test_create_structured_prompt_persists_definition_and_format(client, auth_headers):
    payload = {
        "name": "Structured Summarizer",
        "prompt_format": "structured",
        "prompt_schema_version": 1,
        "prompt_definition": make_prompt_definition_payload(),
        "keywords": ["summary"],
    }

    response = client.post("/api/v1/prompts", json=payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["prompt_format"] == "structured"
    assert body["prompt_definition"]["schema_version"] == 1
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_structured_api.py::test_create_structured_prompt_persists_definition_and_format -v
```

Expected: FAIL because the API and DB schema do not accept structured prompt fields.

**Step 3: Write minimal implementation**

```python
class PromptCreate(PromptBase):
    prompt_format: Literal["legacy", "structured"] = "legacy"
    prompt_schema_version: int | None = None
    prompt_definition: dict[str, Any] | None = None
```

Extend the `Prompts` table and stored payload logic so structured prompts persist:

- `prompt_format`
- `prompt_schema_version`
- `prompt_definition_json`
- derived compatibility/system-user snapshots

Update read/write and export paths without breaking legacy rows.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_structured_api.py -v
```

Expected: PASS for create, get, list, update, and conversion coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Prompts_DB.py \
        tldw_Server_API/app/api/v1/schemas/prompts_schemas.py \
        tldw_Server_API/app/api/v1/endpoints/prompts.py \
        tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_structured_api.py
git commit -m "feat: add structured prompt support to prompts api"
```

### Task 4: Extend Prompt Studio Versioned Prompts for Structured Definitions

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/migrations/005_prompt_studio_structured_prompts.sql`
- Modify: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_prompts.py`
- Create: `tldw_Server_API/tests/prompt_studio/test_structured_prompt_versions.py`

**Step 1: Write the failing test**

```python
def test_prompt_studio_update_creates_new_structured_prompt_version(prompt_studio_db):
    created = prompt_studio_db.create_prompt(
        project_id=1,
        name="Structured Evaluator",
        version_number=1,
        prompt_format="structured",
        prompt_schema_version=1,
        prompt_definition=make_prompt_definition_payload(),
        client_id="test-client",
    )

    updated = prompt_studio_db.update_prompt(
        created["id"],
        {
            "change_description": "Adjust instructions",
            "prompt_definition": make_prompt_definition_payload(task_text="Evaluate {{input}} carefully."),
        },
    )

    assert updated["version_number"] == 2
    assert updated["prompt_definition"]["blocks"][1]["content"] == "Evaluate {{input}} carefully."
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_versions.py::test_prompt_studio_update_creates_new_structured_prompt_version -v
```

Expected: FAIL because Prompt Studio does not version structured prompt definitions yet.

**Step 3: Write minimal implementation**

```python
class PromptBase(BaseModel):
    ...
    prompt_format: Literal["legacy", "structured"] = "legacy"
    prompt_schema_version: int | None = None
    prompt_definition: dict[str, Any] | None = None
```

Add migration-backed support in Prompt Studio for:

- storing prompt format/version
- storing the full structured definition snapshot per version
- returning derived compatibility fields in responses

Use the new `005_prompt_studio_structured_prompts.sql` migration for additive schema changes. Do not back-edit `001_prompt_studio_schema.sql`, because fresh databases should converge by applying the ordered migration chain rather than by maintaining two incompatible sources of schema truth.

Do not break legacy Prompt Studio prompts or current history/revert behavior.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_versions.py -v
```

Expected: PASS for create, update, history, revert, and list coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/migrations/005_prompt_studio_structured_prompts.sql \
        tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py \
        tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py \
        tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_prompts.py \
        tldw_Server_API/tests/prompt_studio/test_structured_prompt_versions.py
git commit -m "feat: add structured prompt versions to prompt studio"
```

### Task 5: Add Shared Preview and Conversion Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/prompts.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_prompts.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/prompts_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py`
- Create: `tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompt_preview_api.py`
- Create: `tldw_Server_API/tests/prompt_studio/test_prompt_preview_api.py`

**Step 1: Write the failing test**

```python
def test_preview_endpoint_matches_assembled_messages(client, auth_headers):
    response = client.post(
        "/api/v1/prompts/preview",
        json={
            "prompt_definition": make_prompt_definition_payload(),
            "variables": {"topic": "Prompt engineering"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["messages"][1]["content"] == "Summarize Prompt engineering"
    assert body["legacy"]["user_prompt"] == "Summarize Prompt engineering"
```

```python
def test_preview_endpoint_reflects_few_shot_examples_and_modules(client, auth_headers):
    response = client.post(
        "/api/v1/prompts/preview",
        json={
            "prompt_definition": make_prompt_definition_payload(),
            "variables": {"topic": "Prompt engineering"},
            "few_shot_examples": [
                {"inputs": {"topic": "Caching"}, "outputs": {"answer": "Use prompt caching."}}
            ],
            "modules_config": [
                {"type": "style_rules", "enabled": True, "config": {"tone": "concise"}}
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "concise" in body["legacy"]["system_prompt"]
    assert any(message["role"] == "assistant" for message in body["messages"])
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompt_preview_api.py \
  tldw_Server_API/tests/prompt_studio/test_prompt_preview_api.py -v
```

Expected: FAIL because preview and conversion endpoints do not exist yet.

**Step 3: Write minimal implementation**

```python
@router.post("/preview")
async def preview_prompt(...):
    return preview_prompt_definition(...)


@router.post("/convert-to-structured")
async def convert_prompt_to_structured(...):
    ...
```

Add preview and conversion endpoints for both APIs. Preview must always call the shared assembler. Conversion must wrap legacy `system_prompt` and `user_prompt` into default blocks and infer variables from existing placeholders where possible.

Preview endpoints must also accept and render existing Prompt Studio `few_shot_examples` and `modules_config` payloads through the same assembler extras path used by runtime execution.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompt_preview_api.py \
  tldw_Server_API/tests/prompt_studio/test_prompt_preview_api.py -v
```

Expected: PASS with parity between preview messages and derived legacy snapshots.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/prompts.py \
        tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_prompts.py \
        tldw_Server_API/app/api/v1/schemas/prompts_schemas.py \
        tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py \
        tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompt_preview_api.py \
        tldw_Server_API/tests/prompt_studio/test_prompt_preview_api.py
git commit -m "feat: add structured prompt preview and conversion endpoints"
```

### Task 6: Route Prompt Studio Execution Through the Shared Assembler

**Files:**
- Modify: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_executor.py`
- Modify: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/test_runner.py`
- Modify: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/evaluation_manager.py`
- Create: `tldw_Server_API/tests/prompt_studio/test_structured_prompt_execution.py`

**Step 1: Write the failing test**

```python
async def test_prompt_executor_uses_structured_assembly_for_prompt_studio(db):
    prompt = create_structured_prompt_in_db(db)
    executor = PromptExecutor(db)

    result = await executor.execute(prompt["id"], {"topic": "retrieval"}, provider="openai", model="gpt-4o-mini")

    assert result["success"] is True
    assert result["metadata"]["assembled_messages"][1]["content"] == "Summarize retrieval"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_execution.py::test_prompt_executor_uses_structured_assembly_for_prompt_studio -v
```

Expected: FAIL because `PromptExecutor` still performs direct string substitution and ignores the new prompt definition.

**Step 3: Write minimal implementation**

```python
if prompt.get("prompt_format") == "structured":
    assembled = assemble_prompt_definition(
        ...,
        extras={
            "few_shot_examples": prompt.get("few_shot_examples"),
            "modules_config": prompt.get("modules_config"),
        },
    )
    messages = assembled.messages
    legacy = assembled.legacy
else:
    ...
```

Use canonical assembled messages for execution metadata and provider calls. Pass existing `few_shot_examples` and `modules_config` through assembler extras so preview and execution stay aligned for Prompt Studio prompts that already depend on those fields. Keep compatibility rendering only as an adapter for providers that still rely on `system_message + user prompt`.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_execution.py -v
```

Expected: PASS, including preview-versus-execution parity tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_executor.py \
        tldw_Server_API/app/core/Prompt_Management/prompt_studio/test_runner.py \
        tldw_Server_API/app/core/Prompt_Management/prompt_studio/evaluation_manager.py \
        tldw_Server_API/tests/prompt_studio/test_structured_prompt_execution.py
git commit -m "feat: route prompt studio execution through structured assembly"
```

### Task 7: Add Structured Prompt Types to Dexie and Sync Plumbing

**Files:**
- Modify: `apps/packages/ui/src/db/dexie/types.ts`
- Modify: `apps/packages/ui/src/db/dexie/helpers.ts`
- Modify: `apps/packages/ui/src/services/prompt-sync.ts`
- Modify: `apps/packages/ui/src/services/prompt-studio.ts`
- Create: `apps/packages/ui/src/services/__tests__/prompt-sync.structured-prompts.test.ts`

**Step 1: Write the failing test**

```ts
it("preserves structured prompt definitions when syncing from workspace to studio", async () => {
  const local = makeLocalPrompt({
    promptFormat: "structured",
    promptSchemaVersion: 1,
    structuredPromptDefinition: makeStructuredPromptDefinition(),
  })

  const payload = localToServerPayload(local, 42)

  expect(payload.prompt_format).toBe("structured")
  expect(payload.prompt_definition?.schema_version).toBe(1)
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/prompt-sync.structured-prompts.test.ts
```

Expected: FAIL because local prompt types and sync payloads do not know about structured prompts.

**Step 3: Write minimal implementation**

```ts
export type Prompt = {
  ...
  promptFormat?: "legacy" | "structured"
  promptSchemaVersion?: number | null
  structuredPromptDefinition?: StructuredPromptDefinition | null
  syncPayloadVersion?: number | null
}
```

Update sync hashing and conflict detection to hash canonical structured content when present. Keep legacy hashing for legacy prompts.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/prompt-sync.structured-prompts.test.ts
```

Expected: PASS for local-to-server, server-to-local, and conflict-hash coverage.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/db/dexie/types.ts \
        apps/packages/ui/src/db/dexie/helpers.ts \
        apps/packages/ui/src/services/prompt-sync.ts \
        apps/packages/ui/src/services/prompt-studio.ts \
        apps/packages/ui/src/services/__tests__/prompt-sync.structured-prompts.test.ts
git commit -m "feat: add structured prompt sync plumbing"
```

### Task 8: Build the Structured Prompt Studio Editor and Preview

**Files:**
- Create: `apps/packages/ui/src/components/Option/Prompt/Structured/StructuredPromptEditor.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/Structured/BlockListPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/Structured/BlockEditorPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/Structured/VariableEditorPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/Structured/AssemblyPreviewPanel.tsx`
- Modify: `apps/packages/ui/src/components/Option/Prompt/Studio/Prompts/PromptEditorDrawer.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/__tests__/StructuredPromptEditor.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders reordered blocks in preview order", async () => {
  render(<StructuredPromptEditor initialDefinition={makeDefinition()} />)

  await dragBlock("Task", "Identity")

  expect(screen.getByTestId("assembly-preview")).toHaveTextContent("Task")
  expect(screen.getByTestId("assembly-preview")).toHaveTextContent("Identity")
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/StructuredPromptEditor.test.tsx
```

Expected: FAIL because the structured editor components do not exist yet.

**Step 3: Write minimal implementation**

```tsx
export function StructuredPromptEditor(...) {
  return (
    <>
      <BlockListPanel ... />
      <BlockEditorPanel ... />
      <VariableEditorPanel ... />
      <AssemblyPreviewPanel ... />
    </>
  )
}
```

Start with Prompt Studio only. Use the shared preview endpoint for the right-hand preview instead of local assembly logic.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/StructuredPromptEditor.test.tsx
```

Expected: PASS for reorder, enable/disable, variable editing, and preview updates.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Prompt/Structured/StructuredPromptEditor.tsx \
        apps/packages/ui/src/components/Option/Prompt/Structured/BlockListPanel.tsx \
        apps/packages/ui/src/components/Option/Prompt/Structured/BlockEditorPanel.tsx \
        apps/packages/ui/src/components/Option/Prompt/Structured/VariableEditorPanel.tsx \
        apps/packages/ui/src/components/Option/Prompt/Structured/AssemblyPreviewPanel.tsx \
        apps/packages/ui/src/components/Option/Prompt/Studio/Prompts/PromptEditorDrawer.tsx \
        apps/packages/ui/src/components/Option/Prompt/__tests__/StructuredPromptEditor.test.tsx
git commit -m "feat: add structured prompt editor to prompt studio"
```

### Task 9: Add Conversion and Structured Editing to the Regular Prompts Workspace

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx`
- Modify: `apps/packages/ui/src/components/Option/Prompt/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/Prompt/PromptFullPageEditor.tsx`
- Modify: `apps/packages/ui/src/components/Option/Prompt/PromptStarterCards.tsx`
- Create: `apps/packages/ui/src/components/Option/Prompt/__tests__/PromptDrawer.structured-prompts.test.tsx`

**Step 1: Write the failing test**

```tsx
it("converts a legacy prompt into a structured prompt and locks raw fields", async () => {
  render(<PromptDrawer open mode="edit" initialValues={makeLegacyPrompt()} ... />)

  await user.click(screen.getByRole("button", { name: /convert to structured/i }))

  expect(screen.getByText(/structured prompt/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/system prompt/i)).toBeDisabled()
  expect(screen.getByLabelText(/user prompt/i)).toBeDisabled()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/PromptDrawer.structured-prompts.test.tsx
```

Expected: FAIL because the regular prompt UI has no structured conversion or lockout behavior yet.

**Step 3: Write minimal implementation**

```tsx
if (promptFormat === "structured") {
  return <StructuredPromptEditor ... />
}
```

Add:

- explicit format state
- convert-to-structured action
- raw-field lockout for structured prompts
- sync-aware persistence of the structured definition

Do not remove legacy mode from the regular Prompts workspace in this phase.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/PromptDrawer.structured-prompts.test.tsx
```

Expected: PASS for conversion, structured editing, and raw-field lockout behavior.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx \
        apps/packages/ui/src/components/Option/Prompt/index.tsx \
        apps/packages/ui/src/components/Option/Prompt/PromptFullPageEditor.tsx \
        apps/packages/ui/src/components/Option/Prompt/PromptStarterCards.tsx \
        apps/packages/ui/src/components/Option/Prompt/__tests__/PromptDrawer.structured-prompts.test.tsx
git commit -m "feat: add structured prompt conversion to prompts workspace"
```

### Task 10: Harden Search, Security, and Verification

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- Modify: `Docs/Published/API-related/Prompt_Studio_API.md`
- Modify: `Docs/Plans/2026-03-10-prompt-schema-foundation-design.md`
- Create: `tldw_Server_API/tests/Prompt_Management_NEW/integration/test_structured_prompt_search.py`
- Create: `tldw_Server_API/tests/prompt_studio/test_structured_prompt_preview_parity.py`

**Step 1: Write the failing test**

```python
def test_structured_prompt_search_indexes_block_content(client, auth_headers):
    create_structured_prompt(client, auth_headers, name="Classifier", block_content="Classify {{text}} by sentiment")

    response = client.get("/api/v1/prompts?search_query=sentiment", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Classifier"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management_NEW/integration/test_structured_prompt_search.py -v
```

Expected: FAIL because FTS/search does not yet index structured content.

**Step 3: Write minimal implementation**

```python
def build_structured_prompt_searchable_text(definition: dict[str, Any]) -> str:
    ...
```

Update search/index refresh logic to derive searchable text from enabled blocks and persisted compatibility fields. Then run Bandit on touched backend paths before closing the work.

Final verification must include:

- regular Prompts structured API coverage
- Prompt Studio structured versioning and execution coverage
- Prompt Studio preview/execution parity for few-shot examples and modules
- Dexie sync tests for structured prompts
- UI editor coverage for Prompt Studio and the regular Prompts workspace

**Step 4: Run verification to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Prompt_Management_NEW/integration/test_structured_prompt_search.py -v
python -m pytest tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_structured_api.py -v
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_validator.py -v
python -m pytest tldw_Server_API/tests/Prompt_Management/test_structured_prompt_assembler.py -v
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_versions.py -v
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_execution.py -v
python -m pytest tldw_Server_API/tests/prompt_studio/test_prompt_preview_api.py -v
python -m pytest tldw_Server_API/tests/prompt_studio/test_structured_prompt_preview_parity.py -v
python -m bandit -r tldw_Server_API/app/core/Prompt_Management/structured_prompts tldw_Server_API/app/api/v1/endpoints/prompts.py tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_executor.py -f json -o /tmp/bandit_prompt_schema_foundation.json
bunx vitest run apps/packages/ui/src/services/__tests__/prompt-sync.structured-prompts.test.ts
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/StructuredPromptEditor.test.tsx
bunx vitest run apps/packages/ui/src/components/Option/Prompt/__tests__/PromptDrawer.structured-prompts.test.tsx
```

Expected:

- pytest PASS on the structured prompt suites
- vitest PASS on the structured prompt UI and sync suites
- Bandit completes without new high-signal findings in touched code

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Prompts_DB.py \
        tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py \
        Docs/Published/API-related/Prompt_Studio_API.md \
        Docs/Plans/2026-03-10-prompt-schema-foundation-design.md \
        tldw_Server_API/tests/Prompt_Management_NEW/integration/test_structured_prompt_search.py \
        tldw_Server_API/tests/prompt_studio/test_structured_prompt_preview_parity.py
git commit -m "feat: finalize structured prompt search and verification"
```
