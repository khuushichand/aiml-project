# Local_LLM

## 1. Descriptive of Current Feature Set

- Purpose: Manage local model backends (Llama.cpp, Llamafile, Ollama, HuggingFace) for offline/edge inference.
- Capabilities:
  - Start/stop servers (llama.cpp, llamafile), list local models, run inference (OpenAI-compatible payloads)
  - Utilities for HTTP calls; unified manager to route requests to handlers
- Inputs/Outputs:
  - Input: backend name, model path/name, OpenAI-like inference payload
  - Output: status dicts, inference results, metrics
- Related Endpoints:
  - Llama.cpp control/inference/rerank: `tldw_Server_API/app/api/v1/endpoints/llamacpp.py:1`
- Related Schemas/Config:
  - `tldw_Server_API/app/core/Local_LLM/LLM_Inference_Schemas.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - `LLMInferenceManager` owns handler instances for each backend; delegates list/download/run/start/stop calls
- Key Classes/Functions:
  - Manager: `LLM_Inference_Manager.py`; base and handlers: `LLM_Base_Handler.py`, `LlamaCpp_Handler.py`, `Llamafile_Handler.py`, `Ollama_Handler.py`, `Huggingface_Handler.py`; `http_utils.py`
- Dependencies:
  - Backends binaries/servers; Python `transformers` optional for HF local inference flows
- Data Models & DB:
  - No persistent DB; handler state in-memory; models stored on disk under configured directories
- Configuration:
  - Handler-specific paths (models_dir, binary paths) via schemas/config; env toggles for enabling local provider
- Concurrency & Performance:
  - Process lifecycle management; streaming responses supported via server OpenAI-compatible APIs
- Error Handling:
  - Typed exceptions (`InferenceError`, `ServerError`, `ModelNotFoundError`); robust cleanup on exit
- Security:
  - Bind servers to safe interfaces; gate external access in production

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Local_LLM/` handlers and manager; `http_utils.py` helpers
- Extension Points:
  - Implement a new handler adhering to the manager contract and register in `LLMInferenceManager`
- Coding Patterns:
  - Loguru logging; keep endpoints thin and defer to manager/handlers
- Tests:
  - `tldw_Server_API/tests/Local_LLM/test_manager.py:1`
  - `tldw_Server_API/tests/Local_LLM/test_llamafile_handler.py:1`
  - `tldw_Server_API/tests/Local_LLM/test_llamafile_parity.py:1`
  - `tldw_Server_API/tests/Local_LLM/test_llamacpp_handler.py:1`
  - `tldw_Server_API/tests/Local_LLM/test_llamacpp_hardening.py:1`
  - `tldw_Server_API/tests/Local_LLM/test_http_utils.py:1`
- Local Dev Tips:
  - Start llama.cpp/llamafile via endpoints; use small GGUF locally; verify `/llamacpp/status` and inference
- Pitfalls & Gotchas:
  - Port conflicts, long-running processes; ensure cleanup via `cleanup_on_exit`
- Roadmap/TODOs:
  - Expand parity of rerank/embeddings flows across backends
