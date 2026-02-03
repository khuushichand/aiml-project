## Stage 1: Server-Side Skill Tool Loop + Enforcement
**Goal**: Execute Skill tool calls inside the chat flow and enforce allowed-tools end-to-end.
**Key Files**:
- `tldw_Server_API/app/api/v1/endpoints/chat.py`
- `tldw_Server_API/app/core/Skills/context_integration.py`
- `tldw_Server_API/app/core/Skills/skill_executor.py`
- `tldw_Server_API/app/core/Tools/tool_executor.py`
- `tldw_Server_API/app/core/MCP_unified/protocol.py`
**Success Criteria**:
- Chat flow executes Skill tool calls server-side (inline + fork) and returns tool outputs.
- Skill tool is injected before tool validation so schema/provider checks apply.
- `allowed-tools` is enforced for skill-driven tool calls and not dropped when `available_tools` is empty.
- Inline skill invocations propagate `allowed-tools` into subsequent tool calls in the same loop.
**Tests**:
- Add unit tests for `resolve_allowed_tools` when `available_tools` is empty.
- Add integration test covering chat tool loop handling of `Skill` (inline + fork).
**Status**: Not Started

## Stage 2: API Schema & Validation Fixes
**Goal**: Align schemas and endpoints with plan semantics.
**Key Files**:
- `tldw_Server_API/app/api/v1/schemas/skills_schemas.py`
- `tldw_Server_API/app/api/v1/endpoints/skills.py`
**Success Criteria**:
- `SkillUpdate.supporting_files` accepts `None` values for delete.
- `SkillImportRequest.name` is optional; frontmatter-only import works.
- Endpoint behavior matches updated schemas with clear errors.
**Tests**:
- Add API tests for create/update/delete/import (including frontmatter-only import) and execute.
**Status**: Not Started

## Stage 3: Supporting Files + Zip Handling
**Goal**: Preserve scripts/ and nested supporting files safely.
**Key Files**:
- `tldw_Server_API/app/core/Skills/skill_parser.py`
- `tldw_Server_API/app/core/Skills/skills_service.py`
- `tldw_Server_API/app/api/v1/schemas/skills_schemas.py`
**Success Criteria**:
- Parser and export include nested supporting files (e.g., `scripts/*.sh`).
- Zip import/export preserves directory structure while blocking path traversal.
- JSON supporting_files can include safe subpaths (e.g., `scripts/helper.sh`).
**Tests**:
- Unit tests for nested supporting files in parser/import/export.
**Status**: Not Started

## Stage 4: Frontend Skills UI + Client + Tests
**Goal**: Provide full Skills management UI and API integration.
**Key Files**:
- `apps/packages/ui/src/services/tldw/openapi-guard.ts`
- `apps/packages/ui/src/services/tldw/index.ts`
- `apps/packages/ui/src/types/skills.ts`
- `apps/packages/ui/src/services/tldw/skills.ts`
- `apps/packages/ui/src/store/skills.ts`
- `apps/packages/ui/src/hooks/useSkills.tsx`
- `apps/packages/ui/src/components/Skills/SkillsPage.tsx`
- `apps/packages/ui/src/components/Skills/SkillCard.tsx`
- `apps/packages/ui/src/components/Skills/SkillEditorDrawer.tsx`
- `apps/packages/ui/src/components/Skills/SkillPreview.tsx`
- `apps/packages/ui/src/routes/option-skills.tsx`
- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/packages/ui/src/assets/locale/en/option.json`
**Success Criteria**:
- New skills types/service/store/hooks/components added and wired to routes/nav.
- `openapi-guard` updated with skills endpoints; services index exports skills client.
- Skills UI supports list/create/edit/delete/import/export/execute preview.
**Tests**:
- Add vitest coverage for skills service/hook and a basic UI render test.
**Status**: Not Started
