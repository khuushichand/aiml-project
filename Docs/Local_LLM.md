Local LLM Module
================

Purpose
-------
- Manage and run local inference backends: llama.cpp, llamafile, Ollama, and HuggingFace.
- Provide consistent server lifecycle (start/stop/status) and inference calls.
- Standardize HTTP via httpx with retries and readiness polling.

Components
----------
- `tldw_Server_API/app/core/Local_LLM/LLM_Inference_Manager.py` — orchestrates handlers
- Handlers:
  - `LlamaCpp_Handler.py` — runs `llama.cpp/server` with GGUF models
  - `Llamafile_Handler.py` — manages `llamafile` binary + models
  - `Ollama_Handler.py` — integrates with `ollama` (local REST)
  - `Huggingface_Handler.py` — local transformers models (no HTTP)
- Shared utilities: `http_utils.py` (httpx client, retries, readiness, redaction)

Configuration
-------------
Pydantic models define defaults and types (see `LLM_Inference_Schemas.py`). Typical keys:

- Llama.cpp (`LlamaCppConfig`):
  - `executable_path`: path to `llama.cpp/server` executable
  - `models_dir`: directory containing `.gguf` models
  - `default_host`, `default_port`, `default_ctx_size`, `default_n_gpu_layers`, `default_threads`

- Llamafile (`LlamafileConfig`):
  - `llamafile_dir`: directory for `llamafile` executable
  - `models_dir`: directory for `.llamafile` or `.gguf` models
  - `default_host`, `default_port`

- Ollama (`OllamaConfig`):
  - `models_dir` (optional; Ollama manages its own)
  - `default_port`

- HuggingFace (`HuggingFaceConfig`):
  - `models_dir`: local HF model cache folder
  - `default_device_map`: e.g., `auto`
  - `default_torch_dtype`: e.g., `torch.bfloat16`

HTTP Behavior
-------------
- All HTTP requests are made with httpx (`http_utils.create_async_client`).
- Simple retries on network errors and 5xx (`request_json`), default timeout 120s.
- Readiness polling after server start (`wait_for_http_ready`) checks `/health` or `/v1/models` up to ~30s.
- Command-line logs are redacted for sensitive flags like `--api-key`.

Examples
--------
Programmatic usage via manager:

```python
from tldw_Server_API.app.core.Local_LLM import (
    LLMInferenceManager, LLMManagerConfig,
    LlamaCppConfig, LlamafileConfig)

cfg = LLMManagerConfig(
    llamafile=LlamafileConfig(enabled=True),
    ollama=None,
    huggingface=None,
    app_config={}
)
manager = LLMInferenceManager(cfg)

# List local models
models = await manager.list_local_models("llamafile")

# Start/swap server with a model
resp = await manager.start_server("llamafile", model_name="Qwen2.5-7B-Instruct-q4_k_m.gguf",
                                 server_args={"port": 8080, "ngl": 99, "api_key": "..."})

# Run inference (OpenAI-compatible)
result = await manager.run_inference(
    backend="llamafile",
    model_name_or_path="unused",
    prompt="Hello!",
    port=8080,
    temperature=0.7)

# Stop server
await manager.stop_server("llamafile", port=8080)
```

API Endpoints (llama.cpp)
-------------------------
- `POST /api/v1/llamacpp/start_server` — body: `{ "model_filename": "...", "server_args": {"port": 8080, ...} }`
- `POST /api/v1/llamacpp/stop_server`
- `GET  /api/v1/llamacpp/status`
- `POST /api/v1/llamacpp/inference` — body: OpenAI-compatible fields (messages, temperature, ...)

Production Notes
----------------
- Bind to localhost by default; adjust host/port behind a reverse proxy for external access.
- Redaction protects logs, but avoid logging payloads with secrets.
- Run under a supervisor if using long-lived processes.
- Ensure models are present and permissions set for the runtime user.

Testing
-------
- Unit tests mock subprocess and httpx to avoid external dependencies.
- Integration tests can be enabled with appropriate markers in CI that provisions local backends.

