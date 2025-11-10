# Setup

## 1. Descriptive of Current Feature Set

- Purpose: Centralize first-time setup and config management (config.txt), and define install plans for STT/TTS/Embeddings.
- Capabilities:
  - Read/update `config.txt` with section labels, hints, and diff-safe writes
  - Toggle remote setup access and propagate via hook
  - Define validated install plans for STT/TTS/Embeddings
- Inputs/Outputs:
  - Inputs: form-like updates to config fields; install plan models
  - Outputs: persisted config.txt and install plan DTOs
- Related Schemas:
  - `tldw_Server_API/app/core/Setup/install_schema.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - `setup_manager.py` reads/writes config with placeholder detection; `install_manager.py` manages dependency checks/installs
- Key Classes/Functions:
  - `register_remote_access_hook`, section label/description maps, field hints, diff helpers
  - Install models: `InstallPlan`, `STTInstall`, `TTSInstall`, `EmbeddingsInstall`
- Dependencies:
  - Standard library; optional pip invocation via controlled gates
- Data Models & DB:
  - No DB; files under `Config_Files/`
- Configuration:
  - `TLDW_SETUP_SKIP_PIP` to block installs; env for default engines and models
- Concurrency & Performance:
  - File IO only
- Error Handling:
  - Safe fallbacks for missing sections; placeholder detection to prevent accidental secrets commit
- Security:
  - Sensitive key markers; never log secrets; anchor relative paths to project root

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Setup/setup_manager.py`, `install_manager.py`, `install_schema.py`
- Extension Points:
  - Add new sections/labels/hints; extend installers for new engines
- Coding Patterns:
  - Keep config mutations idempotent and minimal; use helper utilities for diffing
- Tests:
  - (Add targeted tests for diff/hints as features expand)
- Local Dev Tips:
  - Use a temp copy of `Config_Files/config.txt` while iterating
- Pitfalls & Gotchas:
  - Placeholder values should be replaced; handle OS-specific paths
- Roadmap/TODOs:
  - Expose minimal setup APIs and UI helpers
