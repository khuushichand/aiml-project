# Prompt Schema Foundation Design

Date: 2026-03-10
Status: Approved
Scope: shared structured prompt definition and assembly for Prompt Studio and the regular Prompts workspace, with server-side assembly, live preview, and legacy compatibility rendering

## 1. Summary

Add a shared prompt-schema foundation so prompts are authored as ordered, reusable blocks with declared variables instead of as a single raw insert string. The backend becomes the source of truth for validation and assembly, producing both canonical role-based messages and derived legacy `system_prompt` and `user_prompt` snapshots for older consumers.

The design applies to both Prompt Studio and the regular Prompts workspace. Both surfaces edit the same canonical prompt definition, while execution and preview always flow through a shared server-side assembly service.

Implementation scope for v1 is:

- ordered blocks plus variable substitution only
- no conditionals, loops, or mini-DSL
- server-side assembly as the runtime contract
- canonical role-based message output plus legacy compatibility rendering
- coexistence with legacy prompts through explicit format/version markers and conversion tooling

## 2. User-Approved Decisions

1. The feature should be a shared foundation for Prompt Studio and the regular Prompts UI.
2. The schema should own the runtime assembly contract, not just authoring convenience.
3. The first version should support ordered sections and variables only.
4. The canonical runtime output should be role-based messages, with a compatibility renderer for legacy `system_prompt` and `user_prompt` consumers.

## 3. Review-Driven Revisions

This design was revised after review to address the highest-risk gaps in the first draft:

1. Add explicit `prompt_format` and `prompt_schema_version` fields so schema-backed prompts and legacy prompts cannot silently drift into mixed editing modes.
2. Prevent dual-authoring. Once a prompt is `structured`, raw `system_prompt` and `user_prompt` remain preview/export fields only.
3. Preserve search and indexing by storing or regenerating a derived searchable snapshot from structured content.
4. Define provider compatibility rules for collapsing canonical role-based messages into older `system_message + user prompt` execution paths.
5. Standardize on one variable engine for schema-backed prompts. v1 uses strict placeholder substitution only, not Jinja or arbitrary templating logic.
6. Keep Prompt Studio signatures separate from prompt variables. Signatures remain I/O contracts; variables remain prompt input definitions.
7. Version local sync payloads and conflict hashes in the regular Prompts workspace so structured prompts sync correctly through Dexie and Prompt Studio sync helpers.
8. Define fixed insertion behavior for `few_shot_examples` and `modules_config` during v1 so preview and runtime remain aligned before those concepts become first-class block types.

## 4. Current State

### 4.1 Backend

- The regular Prompts API stores `system_prompt` and `user_prompt` directly in `Prompts_DB`.
- The regular Prompts API exposes regex-based variable extraction and rendering in `tldw_Server_API/app/api/v1/endpoints/prompts.py`.
- Prompt Studio stores versioned prompts with `system_prompt`, `user_prompt`, `few_shot_examples`, `modules_config`, and optional `signature_id` in `PromptStudioDatabase`.
- Prompt Studio execution in `tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_executor.py` still assembles prompts via direct string replacement rather than a reusable prompt-definition contract.
- There is also a Jinja-based safe template renderer in `tldw_Server_API/app/core/Chat/prompt_template_manager.py`, creating multiple overlapping rendering paths.

### 4.2 Frontend

- The regular Prompts workspace centers on raw `system_prompt` and `user_prompt` editing in `apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx` and related editors.
- Prompt Studio prompt editing in `apps/packages/ui/src/components/Option/Prompt/Studio/Prompts/PromptEditorDrawer.tsx` is also text-first, with JSON textareas for advanced fields.
- Variable support in the UI is currently limited to simple `{{variable}}` extraction/highlighting utilities.
- The regular Prompts workspace keeps local prompt records in Dexie and syncs with Prompt Studio using hashes over raw prompt text in `apps/packages/ui/src/services/prompt-sync.ts`.

### 4.3 Gaps

- No shared canonical prompt-definition model exists across both prompt systems.
- No single backend assembly service guarantees preview and execution parity.
- Search/indexing assumes raw prompt text fields rather than structured blocks.
- Existing sync and conflict logic treats `system_prompt` and `user_prompt` as the primary source of truth.
- Prompt Studio signatures are adjacent to prompt composition, but do not solve prompt block authoring or runtime assembly.

## 5. Goals and Non-Goals

### 5.1 Goals

- Provide a shared prompt-definition model for Prompt Studio and the regular Prompts workspace.
- Let users author prompts as ordered named blocks with reusable variables.
- Move validation and assembly to the backend so preview, sync, and execution share one source of truth.
- Produce canonical role-based messages and derived legacy prompt snapshots from the same definition.
- Preserve current search, sync, and interoperability expectations through explicit compatibility projections.
- Support a safe migration path from legacy prompts to structured prompts.

### 5.2 Non-Goals

- No conditionals, loops, branching logic, or DSL in v1.
- No arbitrary Jinja execution for schema-backed prompts.
- No requirement that `few_shot_examples` and `modules_config` become first-class user-editable blocks in the first implementation pass.
- No breaking removal of legacy prompt APIs during the first rollout.
- No attempt to unify every prompt-like feature in the codebase at once, such as character cards or unrelated document-generator prompt storage.

## 6. Proposed Architecture

### 6.1 Shared Prompt Definition Domain Model

Introduce a new shared prompt-schema package under:

`tldw_Server_API/app/core/Prompt_Management/structured_prompts/`

Core types:

- `PromptDefinition`
- `PromptVariableDefinition`
- `PromptBlock`
- `PromptAssemblyResult`
- `PromptLegacySnapshot`
- `PromptPreviewResult`

Suggested canonical shape:

```json
{
  "schema_version": 1,
  "format": "structured",
  "variables": [
    {
      "name": "topic",
      "label": "Topic",
      "description": "User-provided topic or source text",
      "required": true,
      "default_value": null,
      "input_type": "textarea",
      "options": null,
      "max_length": 20000
    }
  ],
  "blocks": [
    {
      "id": "identity",
      "name": "Identity",
      "role": "system",
      "kind": "identity",
      "content": "You are a precise research assistant.",
      "enabled": true,
      "order": 10,
      "is_template": false
    },
    {
      "id": "task",
      "name": "Task",
      "role": "user",
      "kind": "task",
      "content": "Analyze the following topic:\n\n{{topic}}",
      "enabled": true,
      "order": 20,
      "is_template": true
    }
  ],
  "assembly_config": {
    "legacy_system_roles": ["system", "developer"],
    "legacy_user_roles": ["user"],
    "block_separator": "\n\n"
  }
}
```

### 6.2 Prompt Format Contract

Add explicit format metadata to both prompt systems:

- `prompt_format`: `legacy | structured`
- `prompt_schema_version`: integer, nullable for legacy

Rules:

- Legacy prompts can still be stored and executed as raw fields.
- Structured prompts must use `prompt_definition_json` as their source of truth.
- Raw fields on structured prompts are derived compatibility snapshots, not editable peers.
- Conversion from legacy to structured is explicit and one-way for authoring purposes.

This prevents ambiguous writes from current text-first UIs, sync helpers, or background jobs.

### 6.3 Shared Server-Side Assembly Service

Create a reusable service with four responsibilities:

1. `validate_definition(definition)`
2. `assemble_messages(definition, variables, extras)`
3. `render_legacy_snapshot(assembly_result)`
4. `preview_definition(definition, sample_variables, extras)`

Inputs:

- prompt definition
- variable values
- optional assembly extras for few-shot examples, module expansion, and signature-aware hints

Outputs:

- canonical ordered role-based messages
- variable resolution metadata
- warnings and validation errors
- derived legacy `system_prompt` and `user_prompt`
- derived searchable text snapshot

The same service must be used for:

- Prompt Studio execution
- Prompt Studio preview
- regular Prompts preview
- compatibility rendering for old consumers

### 6.4 Compatibility Rendering Rules

Canonical messages are the source of truth. Legacy projections are derived using explicit rules:

- all `system` and `developer` blocks collapse into the legacy `system_prompt`
- all `user` blocks collapse into the legacy `user_prompt`
- `assistant` blocks are preserved in canonical messages, but legacy rendering folds them into the user snapshot using labeled transcript formatting if needed
- block order is preserved within each compatibility rendering group

This protects canonical fidelity while preserving older execution paths that only support one system string and one user string.

### 6.5 Variable Engine

Schema-backed prompts must use one strict substitution engine.

V1 rules:

- placeholder syntax is `{{variable_name}}`
- names allow letters, digits, and underscores only
- no expressions
- no filters
- no conditionals
- missing required variables are execution errors
- optional variables without values render as empty strings unless a default value exists

This intentionally replaces the current mix of regex substitution, manual replacement, and Jinja rendering for structured prompts.

### 6.6 Signatures vs Variables

Prompt Studio signatures remain separate from prompt blocks.

- prompt variables define what values can be injected into blocks
- Prompt Studio signatures define structured input/output expectations for testing, evaluation, and optional output parsing

Integration rule:

- Prompt Studio can map signature input fields to prompt variables
- Prompt Studio can use signature output schemas after execution
- signatures do not become block definitions or block-editing contracts

### 6.7 Few-Shot Examples and Modules in V1

`few_shot_examples` and `modules_config` already exist in Prompt Studio and cannot be ignored during rollout.

V1 approach:

- keep storage shape stable for these fields initially
- treat them as assembler inputs, not free-floating runtime side channels
- insert few-shot examples into canonical message output at a fixed point before the final task/user block
- expand supported module configs into generated system/developer guidance at a fixed point before user blocks
- show both in preview so runtime and UI stay aligned

Later phases may migrate both concepts into first-class block kinds once the core schema foundation is stable.

### 6.8 Search and Indexing

Structured content must remain searchable.

Add a derived snapshot field or deterministic derived text computation for:

- regular Prompts search and FTS
- Prompt Studio list/search UX
- conflict detection and compact preview text

Suggested derived text shape:

- prompt name
- joined enabled block names
- joined enabled block content
- rendered few-shot/module summaries where applicable

This avoids regressing search while keeping the canonical source structured.

### 6.9 Local Sync and Conflict Detection

The regular Prompts workspace currently syncs and detects conflicts using raw prompt text.

Add:

- `structuredPromptDefinition` to Dexie prompt records
- `promptFormat`
- `promptSchemaVersion`
- `syncPayloadVersion`
- canonical conflict hash computed from the structured definition plus derived compatibility fields

This allows offline editing and sync to remain coherent once structured prompts are introduced.

## 7. Data Model and Storage

### 7.1 Regular Prompts Database

Extend the `Prompts` table with:

- `prompt_format TEXT NOT NULL DEFAULT 'legacy'`
- `prompt_schema_version INTEGER`
- `prompt_definition_json TEXT`
- `rendered_legacy_system_prompt TEXT` or reuse existing `system_prompt` as derived snapshot
- `rendered_legacy_user_prompt TEXT` or reuse existing `user_prompt` as derived snapshot
- `searchable_prompt_text TEXT` if needed for FTS refresh or preview caching

Migration requirements:

- existing rows default to `legacy`
- structured rows require valid `prompt_definition_json`
- FTS refresh logic must include structured derived content

### 7.2 Prompt Studio Database

Extend `prompt_studio_prompts` with:

- `prompt_format`
- `prompt_schema_version`
- `prompt_definition_json`
- optional derived search/preview snapshot fields if query performance requires them

Versioning rule:

- each new prompt version stores the full prompt definition snapshot
- compatibility fields are persisted as derived values for older consumers and search ergonomics

### 7.3 API Models

Add shared request/response support for:

- prompt definition payloads
- validation results
- preview/assembly responses
- conversion requests from legacy to structured

Regular Prompts and Prompt Studio should expose the same core schema shape, even if the surrounding metadata differs.

## 8. UX and Interaction Model

### 8.1 Shared Editor Pattern

Use the same mental model in both prompt surfaces:

- left rail: ordered block list
- center pane: selected block editor
- right rail: preview and variables

Primary actions:

- add block from starter presets
- reorder blocks
- enable or disable blocks
- duplicate blocks
- define and edit variables
- preview final canonical messages
- preview derived legacy prompt
- fill sample values to verify render output

### 8.2 Prompt Studio

Prompt Studio gets the structured editor first.

Additional behavior:

- test cases map onto prompt variables
- execution preview uses the shared backend assembler
- evaluation and optimization operate on the structured definition snapshot, not raw prompt fields
- signatures remain visible as structured I/O contracts, separate from the block editor

### 8.3 Regular Prompts Workspace

Regular prompts should support:

- quick-create legacy mode for small cases
- convert-to-structured action
- structured editor and preview for converted or newly structured prompts
- sync-aware UX that shows whether a prompt is legacy or structured

### 8.4 Starter Presets

Starter block presets should mirror practical prompt-authoring patterns:

- identity
- core instructions
- constraints
- style rules
- task
- context
- output format
- examples

This lines up with current OpenAI guidance to separate instructions, examples, context, and formatting rather than pushing everything into one undifferentiated prompt. See:

- [Prompting](https://platform.openai.com/docs/guides/prompting)
- [Prompt engineering strategies](https://platform.openai.com/docs/guides/prompt-engineering/strategies-to-improve-reliability)
- [Text generation](https://platform.openai.com/docs/guides/text?api-mode=responses)

## 9. Validation and Error Handling

Validation levels:

### 9.1 Definition Validation

- invalid or duplicate variable names
- invalid block roles
- duplicate block ids
- missing required fields
- unsupported schema version

### 9.2 Assembly Validation

- unresolved required variables
- block content length overflow
- assembled prompt/message size overflow
- invalid assistant-only prompt shapes when a target execution path cannot support them

### 9.3 UX Warnings

- empty enabled blocks
- unused declared variables
- unresolved optional variables
- blocks omitted from legacy rendering

Execution should fail with descriptive errors for invalid structured prompts. Preview should surface warnings without mutating stored state.

## 10. Migration and Rollout

### 10.1 Prompt States

Every prompt is either:

- `legacy`
- `structured`

No hybrid editable mode exists.

### 10.2 Conversion

Add conversion tooling:

- wrap existing `system_prompt` into a default system block
- wrap existing `user_prompt` into a default task/user block
- extract existing `{{variables}}` into variable definitions where possible
- carry over Prompt Studio few-shot examples and modules as assembler extras

### 10.3 Rollout Order

1. Backend schema types, validation, assembly, and preview endpoints
2. Prompt Studio structured editor
3. Prompt Studio execution/evaluation integration through the shared assembler
4. Regular Prompts structured editor and conversion flow
5. Dexie/local sync and conflict-hash migration
6. Search/indexing hardening and compatibility cleanup

This rollout limits breakage by moving server-side truth and Prompt Studio runtime first, then updating the more locally stateful regular Prompts workspace.

## 11. Testing Strategy

### 11.1 Backend Unit Tests

- prompt definition validation
- variable substitution
- canonical message assembly
- legacy compatibility rendering
- few-shot/module insertion behavior
- structured-to-legacy conversion

### 11.2 Backend Integration Tests

- regular Prompts CRUD with structured definitions
- Prompt Studio CRUD with structured definitions
- preview endpoints
- Prompt Studio execution using assembled messages
- sync-safe round trips of derived compatibility fields

### 11.3 Frontend Tests

- block reorder and enable/disable behavior
- variable editor validation
- live preview updates
- conversion flows
- legacy versus structured display states
- sync conflict behavior for structured prompts

### 11.4 Regression Focus

- preview must match execution assembly
- search must continue to find structured prompts
- regular Prompt sync must not collapse structured prompts back into raw-only records
- Prompt Studio signatures must continue to work independently of the block editor

## 12. Risks and Open Questions

1. Legacy compatibility rendering for assistant/example blocks can become lossy. The design accepts this for older consumers and preserves fidelity in canonical message output.
2. Search/indexing cost may rise if derived snapshots are regenerated too often. Implementation should prefer deterministic regeneration on write rather than on every read.
3. The regular Prompts workspace has more local/offline state complexity than Prompt Studio. That is why rollout should update Prompt Studio first.
4. Prompt-like features outside these two surfaces may later benefit from the same schema foundation, but they are intentionally out of scope for the first pass.

## 13. References

- `tldw_Server_API/app/api/v1/endpoints/prompts.py`
- `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- `tldw_Server_API/app/api/v1/endpoints/prompt_studio/prompt_studio_prompts.py`
- `tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_executor.py`
- `tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py`
- `apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx`
- `apps/packages/ui/src/components/Option/Prompt/Studio/Prompts/PromptEditorDrawer.tsx`
- `apps/packages/ui/src/services/prompt-sync.ts`
- `apps/packages/ui/src/db/dexie/types.ts`
