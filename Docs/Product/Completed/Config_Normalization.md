# Config Normalization PRD (Expanded)

Status: Complete
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Normalize configuration across the server with a single config root resolver and a single precedence chain:
environment > config.txt > module YAML > defaults. This expands the original scope to cover module YAML loaders
(TTS, Embeddings, Evaluations), prompt path resolution, and path probing for Config_Files. The goal is to
eliminate per-module path search lists and ad-hoc merge logic while keeping config.txt first-class.

## 2. Problem Statement
Multiple modules parse environment variables and config.txt independently and probe for config paths with
bespoke search lists. This creates precedence drift, inconsistent defaults, and test brittleness.

Duplicated logic exists in:
- tldw_Server_API/app/core/config.py
- tldw_Server_API/app/core/Setup/setup_manager.py
- tldw_Server_API/app/core/TTS/tts_config.py
- tldw_Server_API/app/core/Embeddings/simplified_config.py
- tldw_Server_API/app/core/Evaluations/config_manager.py
- tldw_Server_API/app/core/Utils/prompt_loader.py

Consequences: inconsistent precedence rules, scattered defaults, and brittle path behavior when the repo
layout or install location changes.

## 3. Goals & Success Criteria
- One config root resolver used by all modules.
- Single precedence order: environment > config.txt > module YAML > defaults.
- config.txt remains first-class and backward compatible.
- Prompt and module YAML paths are resolved through the same config root.
- Remove module-specific path probing and merging logic.

Success Metrics:
- No module keeps its own path search list for Config_Files.
- TTS, Embeddings, and Evaluations config loaders share the same resolution rules.
- Prompt loader and setup manager use the shared path resolver.
- Tests no longer mutate paths/env per module to pass.

## 4. In Scope
- Config root resolution for Config_Files and all module YAMLs.
- Shared config.txt adapter and caching of parsed values.
- Module YAML layering for TTS, Embeddings, Evaluations.
- Prompt path resolution via the same config root.
- Update Setup manager to use the shared resolver for config.txt path.
- Private, read-only effective config API (redacted, source-tagged).

## 5. Out of Scope
- LLM provider settings rework (covered by LLM adapter registry migration PRD).
- RAG, MCP, or AuthNZ settings refactors beyond path resolution.
- Any UI changes.

## 6. Functional Requirements
### 6.1 Config Root Resolution
- New helper to resolve config root with deterministic precedence:
  1) TLDW_CONFIG_FILE (explicit config.txt path, uses its parent as config root)
  2) TLDW_CONFIG_DIR (explicit override)
  3) Repo root/Config_Files when running in-tree (authoritative for dev/test)
  4) User config dir (platform-specific) when not running in-tree
  5) Fallback to packaged install Config_Files adjacent to the code
- Resolver returns a Path object and never probes in multiple modules.
- Define user config dir by OS:
  - Linux: ${XDG_CONFIG_HOME:-~/.config}/tldw
  - macOS: ~/Library/Application Support/tldw
  - Windows: %APPDATA%\\tldw

### 6.2 Config.txt Access
- Provide a shared adapter to access config.txt sections:
  - get_config_section(section_name) -> dict
  - get_config_value(section, key, default) -> str
- Adapter caches config.txt reads for process lifetime and supports explicit reload
  (reload flag or refresh_config_cache()) for tests or long-running servers.
- Adapter exposes "source" metadata for logging.
- If TLDW_CONFIG_FILE is set but missing/unreadable, raise a clear error.
- If config.txt is missing at the resolved root, log a warning and treat it as
  empty; do not create or mutate files implicitly.

### 6.3 Module YAML Layering
- Provide a shared loader: load_module_yaml(module_name, filename_override=None)
- Use this loader in:
  - tldw_Server_API/app/core/TTS/tts_config.py
  - tldw_Server_API/app/core/Embeddings/simplified_config.py
  - tldw_Server_API/app/core/Evaluations/config_manager.py
- Precedence for module settings:
  - env overrides
  - config.txt section overrides
  - module YAML defaults (file-provided defaults)
  - hardcoded defaults (last-resort code defaults)

### 6.4 Prompt Path Resolution
- prompt_loader must resolve prompts directory through the config root.
- Keep existing TLDW_CONFIG_DIR override behavior; do not break older installations.

### 6.5 Setup Manager
- setup_manager must use the shared resolver for config.txt.
- Its comment/index logic remains unchanged.

### 6.6 Logging and Diagnostics
- Log resolved config root and effective sources at startup (redact secrets).
- When a module reads config settings, emit debug-level source tags only:
  [env|config|yaml|default]. Redact values for keys matching *key*, *token*,
  *secret*, *password*, *api_key* (case-insensitive), and prefer logging
  key names and source only.

### 6.7 Effective Config API (Redacted)
- Provide a private, read-only API to expose effective config for diagnostics.
- Response includes redacted values and source tags per key.
- Access must be authenticated and restricted to admin-capable users.
- Endpoint: GET /api/v1/admin/config/effective
- Router location: tldw_Server_API/app/api/v1/endpoints/config_admin.py
  - router = APIRouter(prefix="/admin/config", tags=["admin", "config"],
    dependencies=[Depends(require_roles("admin"))])
- Response schema (new file: tldw_Server_API/app/api/v1/schemas/config_schemas.py):
  - EffectiveConfigResponse:
    - config_root: str
    - config_file: Optional[str]
    - prompts_dir: Optional[str]
    - module_yaml: Dict[str, Optional[str]]  # e.g., {"tts": "...", "embeddings": "..."}
    - values: Dict[str, Dict[str, ConfigValue]]
  - ConfigValue:
    - value: Any  # "<redacted>" when redacted
    - source: Literal["env", "config", "yaml", "default"]
    - redacted: bool
- Optional query params:
  - sections: Optional[List[str]]  # limit to specific config namespaces/modules
  - include_defaults: bool = true

## 7. Design Overview
- Add a small config path utility module (or expand config.py) with:
  - resolve_config_root()
  - resolve_config_file("config.txt")
  - resolve_prompts_dir()
  - resolve_module_yaml("tts_providers_config.yaml")
- Keep config.txt parsing in config.py but expose a stable adapter interface.
- Build a shared merge helper that tags sources per key for logging.

## 8. Implementation Phases
1) Introduce shared config root resolver and config.txt adapter.
2) Update prompt_loader and setup_manager to use the resolver.
3) Integrate TTS, Embeddings simplified config, and Evaluations config manager.
4) Remove module-specific path probes and old merge logic.

## 9. Risks & Mitigations
- Risk: implicit path changes break legacy installs.
  - Mitigation: preserve current search order via explicit resolver rules and tests.
- Risk: settings precedence drift across modules.
  - Mitigation: shared merge helper with source tagging and parity tests.

## 10. Testing Plan
- Unit tests for resolver precedence (env, repo root, user config dir).
- Unit tests for merge precedence and source tags.
- Integration tests for TTS/Embeddings/Evals config behaviors under env/config/YAML.

## 11. Acceptance Criteria
- No module implements its own Config_Files search list.
- TTS/Embeddings/Evals/PROMPTS/Setup use shared resolver.
- config.txt precedence preserved and verified by tests.
- Startup logs show resolved config root and sources.
- Effective config API returns redacted values with source tags and enforces admin-only access.

## 12. Open Questions
- None.

## 13. Implementation Plan (Draft)
### Stage 1: Config Root and Adapter Foundation
**Goal**: Implement shared resolver and config.txt adapter with reload support.
**Success Criteria**: Resolver precedence matches spec; adapter supports reload; missing-file behavior matches spec.
**Tests**: Unit tests for resolver precedence; unit tests for adapter caching/reload/missing-file behavior.
**Status**: Complete

### Stage 2: Shared Resolution Adoption
**Goal**: Migrate prompt loader and setup manager to shared resolver.
**Success Criteria**: No local path probing remains in these modules; behavior matches legacy.
**Tests**: Integration tests for prompt resolution and setup manager config path usage.
**Status**: Complete

### Stage 3: Module YAML Integration
**Goal**: Migrate TTS, Embeddings, and Evaluations loaders to shared module YAML resolver and merge helper.
**Success Criteria**: Unified precedence across modules with source tags; no per-module path lists.
**Tests**: Integration tests for env/config/YAML precedence per module; unit tests for merge helper tagging.
**Status**: Complete

### Stage 4: Effective Config API
**Goal**: Expose redacted, source-tagged effective config via authenticated API.
**Success Criteria**: GET /api/v1/admin/config/effective returns redacted values; access restricted to admin-capable users; logs are debug-only.
**Tests**: Integration tests for authorization, redaction, and response schema; schema validation for ConfigValue source tags.
**Status**: Complete
