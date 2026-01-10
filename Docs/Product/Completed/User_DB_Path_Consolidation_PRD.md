# User DB Path Consolidation PRD

Status: Proposal ready for implementation
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Consolidate all per-user database path resolution to a single canonical helper
(`tldw_Server_API/app/core/DB_Management/db_path_utils.py`). This removes
hand-rolled path fallbacks and ensures consistent behavior across single-user
and multi-user deployments.

Breaking change: legacy per-user DB paths are not supported; users must set
USER_DB_BASE_DIR or migrate to the default layout.
Migration note: USER_DB_BASE is deprecated and treated as an alias to
USER_DB_BASE_DIR; single-user callers may pass None/"" for user_id, but
multi-user callers must provide a valid user_id.

## 2. Problem Statement
Multiple modules compute paths to Media_DB_v2, ChaChaNotes, and related
per-user assets via ad-hoc fallbacks (repo root, relative paths, etc.). This
introduces drift and breakage when directory layouts change.

Examples:
- tldw_Server_API/app/core/Chunking/template_initialization.py
- tldw_Server_API/app/core/Workflows/adapters.py
- tldw_Server_API/app/core/Utils/Utils.py
- tldw_Server_API/app/core/TTS/voice_manager.py
- tldw_Server_API/app/core/AuthNZ/migrate_to_multiuser.py

## 3. Goals & Success Criteria
- One canonical path resolver for per-user DBs and storage.
- No module computes user DB paths manually.
- Consistent behavior across single-user and multi-user modes.

Success Metrics:
- No direct string joins with Databases/user_databases, USER_DB_BASE_DIR, or USER_DB_BASE outside db_path_utils.
- Path resolution tests cover single-user and multi-user defaults.

## 4. In Scope
- Expand db_path_utils if necessary to cover all per-user DB and asset paths.
- Replace manual path logic in the modules listed above.
- Align path resolution with USER_DB_BASE_DIR from env/config.
- Consolidate per-user directories under USER_DB_BASE_DIR, including outputs/, voices/, chroma_storage/,
  vector_store/ (vector_store_* DBs), prompt_studio_dbs/, Rewrite_Cache/, rag_personalization.json, and chatbooks/.

## 5. Out of Scope
- DB schema changes or migrations.
- Changes to storage formats or table layouts.
- UI changes.
- Per-user storage roots outside USER_DB_BASE_DIR (AuthNZ USER_DATA_BASE_PATH/CHROMADB_BASE_PATH).

## 6. Functional Requirements
### 6.1 Canonical Path Helpers
db_path_utils must provide:
- DatabasePaths.get_media_db_path(user_id)
- DatabasePaths.get_chacha_db_path(user_id)
- DatabasePaths.get_user_base_directory(user_id)
- DatabasePaths.get_user_outputs_dir(user_id)
- DatabasePaths.get_user_voices_dir(user_id)
- DatabasePaths.get_user_chroma_dir(user_id)
- DatabasePaths.get_user_vector_store_dir(user_id)
- DatabasePaths.get_user_chatbooks_dir(user_id)
- DatabasePaths.get_user_chatbooks_exports_dir(user_id)
- DatabasePaths.get_user_chatbooks_imports_dir(user_id)
- DatabasePaths.get_user_chatbooks_temp_dir(user_id)
- DatabasePaths.get_prompt_studio_db_path(user_id)
- DatabasePaths.get_user_rewrite_cache_path(user_id)
- DatabasePaths.get_user_rag_personalization_path(user_id)
- Any additional per-user directories currently hard-coded in modules

Helper contract:
- Add new helpers as DatabasePaths static methods; add string-returning convenience functions only if required by legacy call sites.
- Accept None or empty user_id only in single-user mode; map to the fixed single-user id internally. In multi-user mode, None/"" is an error.
- Validate user_id to prevent path traversal (reject absolute paths, "..", path separators). Non-numeric user_id is allowed only in tests (hashed fallback).
- Return normalized absolute paths and ensure base/subdirectories exist (mkdir parents=True); callers create files as needed.
- Canonical layout (base = USER_DB_BASE_DIR / <user_id>):
  - get_user_outputs_dir: <base>/outputs
  - get_user_voices_dir: <base>/voices
  - get_user_chroma_dir: <base>/chroma_storage
  - get_user_vector_store_dir: <base>/vector_store
  - get_prompt_studio_db_path: <base>/prompt_studio_dbs/prompt_studio.db
  - get_user_rewrite_cache_path: <base>/Rewrite_Cache/rewrite_cache.jsonl
  - get_user_rag_personalization_path: <base>/rag_personalization.json

### 6.2 Config Awareness
- Precedence: USER_DB_BASE_DIR env var overrides config.txt (defined in `tldw_Server_API.app.core.config`).
- Relative USER_DB_BASE_DIR is allowed and resolved against repo root (get_project_root); expand "~" and normalize via Path.resolve for Windows compatibility.
- Default to <repo_root>/Databases/user_databases/<user_id>/ when unset.
- USER_DB_BASE is deprecated; treat as alias to USER_DB_BASE_DIR for rewrite cache and log a deprecation warning.

### 6.3 Mode Awareness
- Single-user mode maps to the fixed user id inside db_path_utils (no call-site branching).
- Multi-user mode uses the requested user_id directly.

## 7. Migration Phases
1) Audit call sites and expand db_path_utils to cover missing helpers.
2) Replace path logic in target modules.
3) Remove legacy fallbacks and direct path joins.

## 8. Risks & Mitigations
- Risk: accidental path changes in single-user mode.
  - Mitigation: add parity tests and run against existing sample DB layout.
- Risk: hidden dependencies on old fallback paths.
  - Mitigation: no legacy path compatibility; document breaking change and require config updates.

## 9. Testing Plan
- Unit tests for db_path_utils: env/config overrides, default paths, mode behavior.
- Integration tests for modules that load per-user DBs.

## 10. Acceptance Criteria
- All per-user DB and asset paths resolved via db_path_utils.
- No manual Databases/user_databases, USER_DB_BASE_DIR, or USER_DB_BASE string paths remain in runtime code (tests/docs/tools may reference).
- Tests pass with USER_DB_BASE_DIR overrides.

## 11. Open Questions
- Should db_path_utils expose a single struct/object with all user paths to reduce call count?
  - Decision: not necessary; all user paths share layout/path rules.
- Are there any per-user directories not covered by the current helper set?
  - Decision: yes. Audit found additional per-user directories under USER_DB_BASE_DIR: outputs/, voices/, chroma_storage/, vector_store/ (vector_store_* DBs), prompt_studio_dbs/, Rewrite_Cache/, rag_personalization.json, and chatbooks/. Separate per-user bases exist outside USER_DB_BASE_DIR (AuthNZ USER_DATA_BASE_PATH/CHROMADB_BASE_PATH) and are out of scope.

## 12. Implementation Plan
### Stage 1: Audit & Helper Contract
**Goal**: Inventory all per-user path usages and finalize db_path_utils helper APIs.
**Success Criteria**: Call-site list is complete; helper signatures, validation rules, and path normalization are documented.
**Tests**: Unit test outline created for env/config precedence, single-user resolution, and user_id validation.
**Status**: Complete

### Stage 2: Helper Expansion & Unit Tests
**Goal**: Implement/extend db_path_utils helpers and add unit tests for path resolution behavior.
**Success Criteria**: All required helpers exist; unit tests cover env/config precedence, relative path resolution, and user_id validation.
**Tests**: `tldw_Server_API/tests/core/db_path_utils/test_paths.py` (or existing test location) with unit cases.
**Status**: Complete

### Stage 3: Call-Site Migration
**Goal**: Replace manual path logic in listed modules with db_path_utils.
**Success Criteria**: No runtime code contains direct Databases/user_databases joins; modules rely on db_path_utils only.
**Tests**: Integration tests for affected modules; verify no regressions in media/chat/tts flows.
**Status**: Complete

### Stage 4: Cleanup & Documentation
**Goal**: Remove legacy path fallbacks and update docs for breaking change.
**Success Criteria**: Deprecated fallback logic removed; PRD and README/Docs updated to emphasize USER_DB_BASE_DIR usage.
**Tests**: Run unit + integration test suites; validate config override behavior.
**Status**: Complete
