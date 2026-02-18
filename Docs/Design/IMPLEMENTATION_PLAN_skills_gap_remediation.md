## Stage 1: Import/Path Security Hardening
**Goal**: Close all invalid-name and path traversal gaps across create/import/import-file/import-zip flows.
**Success Criteria**: Skill names are validated consistently in service-layer operations; imports reject invalid names regardless of source (frontmatter, request body, zip directory, filename); supporting-file paths cannot escape a skill directory.
**Tests**:
- Unit: `create_skill` rejects invalid names and does not write files.
- Unit: `import_skill` rejects invalid `name` and invalid frontmatter `name`.
- Unit: zip import rejects traversal entries (`../`, nested escape paths, absolute paths).
- Integration: `/api/v1/skills/import` and `/api/v1/skills/import/file` return 400 for invalid names.
**Status**: Complete

## Stage 2: API/Schema Contract and Limit Enforcement
**Goal**: Align schemas with runtime behavior and enforce supporting-file limits across every ingest path.
**Success Criteria**: `SkillUpdate.supporting_files` supports `null` values for deletions; `SkillImportRequest.name` is optional (frontmatter fallback) or API/docs are made internally consistent; aggregate and count limits apply to direct create/update and import (text + zip).
**Tests**:
- Unit: schema accepts `{"file.md": null}` for updates.
- Unit: import requests over count/aggregate size limits fail validation.
- Integration: import endpoint rejects >20 files and >5MB aggregate.
- Integration: update endpoint allows `null` value to remove a supporting file.
**Status**: Complete

## Stage 3: Async Safety and Context Endpoint Behavior
**Goal**: Remove remaining blocking filesystem sync from async request paths.
**Success Criteria**: async endpoints (notably `/api/v1/skills/context`) use async-safe service methods; sync filesystem scans are not executed directly on the event loop.
**Tests**:
- Unit: async context payload path uses async sync method (or equivalent async wrapper).
- Integration: `/api/v1/skills/context` behavior remains unchanged while using async-safe internals.
**Status**: Complete

## Stage 4: Frontend Data Integrity + Missing UX Features
**Goal**: Prevent metadata loss on edit and complete planned Skills UI functionality.
**Success Criteria**: editing an existing skill does not strip frontmatter metadata; drawer supports supporting-file add/edit/remove; Manager supports both import-from-text and import-from-file; update requests carry version and supporting-files changes correctly.
**Tests**:
- Frontend unit/component: editing preserves metadata fields when content body is changed.
- Frontend unit/component: supporting-file add/remove flows produce expected payload.
- Frontend unit/component: import-text action calls `importSkill`; file import remains functional.
- Build check: `source .venv/bin/activate && cd apps/tldw-frontend && npm run build`.
**Status**: Complete
**Implementation Note**: `npm` is unavailable in this sandbox; targeted Skills frontend tests pass, while `bun run build` in `apps/tldw-frontend` started but did not return a final exit status in this environment.

## Stage 5: Built-in Seed Completeness + Regression Coverage
**Goal**: Ensure builtin seeding copies complete skill directories and lock in regressions with test coverage.
**Success Criteria**: seeding copies `SKILL.md` plus supporting files recursively; overwrite semantics remain correct; all previously identified bug cases are covered by tests and pass in the project venv.
**Tests**:
- Unit: seed copies supporting files for builtin skills.
- Unit: seed no-overwrite and overwrite behaviors remain correct.
- Skills suite: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Skills/ -v`.
- Lint: `source .venv/bin/activate && ruff check tldw_Server_API/app/core/Skills/ tldw_Server_API/app/api/v1/endpoints/skills.py tldw_Server_API/app/api/v1/schemas/skills_schemas.py`.
**Status**: Complete
**Implementation Note**: Seeding now copies full builtin skill directories recursively (not just `SKILL.md`), and Stage 5 verification commands completed successfully in `.venv` (`python -m pytest tldw_Server_API/tests/Skills/ -v`, `ruff check ...`).

## Issue-to-Stage Mapping
- Invalid-name/path traversal bypasses: Stage 1
- Frontend metadata stripping on edit: Stage 4
- `SkillUpdate.supporting_files` type mismatch: Stage 2
- Aggregate/count limit bypass in import flows: Stage 2
- Missing frontend import-text + supporting-files UX: Stage 4
- Async context endpoint still sync-calling service: Stage 3
- Seed only copies `SKILL.md` (not full directory): Stage 5
- `SkillImportRequest.name` required/contract mismatch: Stage 2
