# Utils

## 1. Descriptive of Current Feature Set

- Purpose: Common helpers used across modules (tokenization, image validation, prompt loading, system checks, etc.).
- Capabilities:
  - Tokenizer helpers, chunked image processing, CPU-bound execution wrappers
  - Prompt loader for multi-namespace prompts, pydantic compatibility helpers
  - Metadata utilities and system checks
- Inputs/Outputs:
  - Inputs: strings/blobs/paths; Outputs: derived strings/structures/booleans
- Related Modules:
  - `tldw_Server_API/app/core/Utils/Utils.py:1`, `tokenizer.py:1`, `prompt_loader.py:1`, `image_validation.py:1`, `System_Checks_Lib.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Self-contained modules; no cross-layer coupling; safe to import from endpoints and services
- Key Helpers:
  - `tokenizer`, `chunked_image_processor`, `executor_registry`, `cpu_bound_handler`, `prompt_loader`
- Dependencies:
  - Standard library and lightweight third-parties only
- Data Models & DB:
  - None
- Configuration:
  - Minimal; helpers read env only if necessary
- Concurrency & Performance:
  - CPU-bound helpers offload to thread/process pools where needed
- Error Handling:
  - Fail safe semantics; return empty defaults when appropriate
- Security:
  - Validate inputs; avoid touching filesystem unless explicit

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - Individual helper modules under `Utils/`
- Extension Points:
  - Add new helpers where reuse is expected; keep SRP
- Coding Patterns:
  - Small, well-tested functions; loguru for diagnostics only when helpful
- Tests:
  - (Add targeted unit tests for new helpers)
- Local Dev Tips:
  - Import helpers directly in endpoints/services; avoid circular deps
- Pitfalls & Gotchas:
  - Do not add heavy deps here; keep import-time light
- Roadmap/TODOs:
  - Consolidate overlapping helpers; add type hints where missing
