# Embeddings Adapter Scaffold (Stage 4)

This document tracks the initial scaffold for migrating embeddings to the provider adapter architecture.

What’s included
- `EmbeddingsProvider` interface in `tldw_Server_API/app/core/LLM_Calls/providers/base.py`.
- Embeddings adapter registry in `tldw_Server_API/app/core/LLM_Calls/embeddings_adapter_registry.py`.
- OpenAI embeddings adapter (delegate-first) in `tldw_Server_API/app/core/LLM_Calls/providers/openai_embeddings_adapter.py`.

Behavior
- By default, the OpenAI embeddings adapter delegates to the existing legacy helper `get_openai_embeddings()` for parity and to avoid network during tests.
- Native HTTP can be enabled with `LLM_EMBEDDINGS_NATIVE_HTTP_OPENAI=1` (uses `httpx` at `OPENAI_BASE_URL` or default OpenAI URL).

Next steps
- Add generic OpenAI-compatible embeddings adapter (local servers) mirroring chat adapters.
- Wire a shim for embeddings to allow endpoint opt-in via env flag without touching the production embeddings service.
- Extend registry defaults as more embeddings providers are adapted.
- Conformance tests: shape of responses, error mapping, batch behavior, and performance smoke.

