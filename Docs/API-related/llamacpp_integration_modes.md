# llama.cpp Integration Modes

This project supports two distinct `llama.cpp` integration planes. They are both valid, and they are intentionally separate.

## Plane Overview

| Plane | Purpose | Primary Surface | State Owner | Typical Operator |
|---|---|---|---|---|
| managed plane | Manage a local `llama.cpp/server` process | `/api/v1/llamacpp/*` lifecycle endpoints | `LLMInferenceManager` + `LlamaCppHandler` managed process state | Admin/operator |
| provider plane | Route chat requests to an OpenAI-compatible `llama.cpp` endpoint | `provider=llama.cpp` chat adapter path | `llama_api` provider configuration + remote server state | App/client caller |

## Endpoint-to-Plane Mapping

| Endpoint/Path | Plane | Contract |
|---|---|---|
| `POST /api/v1/llamacpp/start_server` | managed plane | Starts or swaps managed local server model |
| `POST /api/v1/llamacpp/stop_server` | managed plane | Stops managed local server process |
| `GET /api/v1/llamacpp/status` | managed plane | Returns managed process status |
| `GET /api/v1/llamacpp/models` | managed plane | Lists model files from managed-plane runtime |
| `POST /api/v1/llamacpp/inference` | managed plane | Runs inference against managed server context |
| `POST /api/v1/chat/completions` + `provider=llama.cpp` | provider plane | Sends request through provider adapter to configured `llama_api` endpoint |

## Critical Rule

No shared state is implied between the managed plane and provider plane.

Starting/stopping a managed server does not automatically rewrite provider-plane endpoint configuration, and provider-plane availability does not guarantee managed-plane process readiness.

## Common Misconfigurations

| Symptom | Plane | Likely Cause | Correct Fix |
|---|---|---|---|
| `503` on `/api/v1/llamacpp/status` saying backend not configured | managed plane | Managed handler disabled or unavailable | Enable `[LlamaCpp] enabled=true` and restart server |
| `/api/v1/llamacpp/models` returns unavailable while `provider=llama.cpp` chat works | managed plane | Provider plane configured, but no managed handler/runtime | Configure managed handler/model directory; do not assume provider mode enables lifecycle API |
| `provider=llama.cpp` chat fails while managed status is running | provider plane | `llama_api` endpoint/auth/config mismatch | Fix provider configuration (`llama_api` host/path/key), validate OpenAI-compatible endpoint |
| Tools payloads rejected for `provider=llama.cpp` | provider plane | Current contract blocks tools for this adapter path | Remove tools/tool_choice or switch provider that advertises tool support |

## Verification Checklist

1. Confirm which plane your workflow targets first.
2. For lifecycle operations, use only `/api/v1/llamacpp/*` managed plane endpoints.
3. For chat-provider routing, validate `provider=llama.cpp` and `llama_api` config independently.
4. Treat managed and provider diagnostics separately during incident triage.
