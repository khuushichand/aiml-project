# Providers API Documentation

## Overview
- Purpose: Discover configured LLM providers, their models and capabilities, and the health of the LLM inference subsystem. These endpoints are useful for client UIs and for operational monitoring.
- OpenAPI tag: `llm`

## Authentication
- By default these endpoints are accessible without authentication. Deployments may enforce AuthNZ globally.
- If required by your deployment:
  - Single-user: `X-API-KEY: <key>`
  - Multi-user: `Authorization: Bearer <JWT>`

## Endpoints

### 1) GET /api/v1/llm/health
- Summary: Health status for the LLM inference subsystem (provider manager, request queue, rate limiter).
- Response (example):
```json
{
  "service": "llm_inference",
  "status": "healthy",
  "timestamp": "2025-01-01T00:00:00.000000",
  "components": {
    "providers": {
      "initialized": true,
      "count": 3,
      "report": {
        "openai": {
          "status": "healthy",
          "success_count": 42,
          "failure_count": 1,
          "consecutive_failures": 0,
          "average_response_time": 0.35,
          "circuit_breaker_state": "CLOSED",
          "last_success": 1735689600.0,
          "last_failure": null
        }
      }
    },
    "queue": {
      "initialized": true,
      "queue_size": 0,
      "processing_count": 0,
      "max_queue_size": 100,
      "max_concurrent": 10,
      "total_processed": 0,
      "total_rejected": 0,
      "is_running": true
    },
    "rate_limiter": {
      "initialized": true,
      "limits": {
        "global_rpm": 60,
        "per_user_rpm": 20,
        "per_conversation_rpm": 10,
        "per_user_tokens_per_minute": 10000
      }
    }
  }
}
```

### 2) GET /api/v1/llm/providers
- Summary: List configured LLM providers and their models.
- Query params: `include_deprecated` (bool, default false)
- Response (example):
```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "type": "commercial",
      "is_configured": true,
      "models": ["gpt-4o", "gpt-4o-mini"],
      "models_info": [
        {
          "name": "gpt-4o",
          "context_window": 128000,
          "max_output_tokens": 4096,
          "capabilities": {"vision": true, "tool_use": true, "streaming": true},
          "modalities": {"input": ["text", "image"], "output": ["text"]}
        }
      ],
      "default_model": "gpt-4o",
      "supports_streaming": true
    }
  ],
  "default_provider": "openai",
  "total_configured": 1
}
```

### 3) GET /api/v1/llm/providers/{provider_name}
- Summary: Details for a single provider.
- Path params: `provider_name` (e.g., `openai`, `anthropic`)
- Query params: `include_deprecated` (bool, default false)
- Response: Same shape as a single item in `providers` above. `404` if provider not configured.

### 4) GET /api/v1/llm/models
- Summary: Flat list of available models across all providers.
- Query params: `include_deprecated` (bool, default false)
- Response (example):
```json
[
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "anthropic/claude-opus-4.1"
]
```

### 5) GET /api/v1/llm/models/metadata
- Summary: Flattened model capability metadata across providers.
- Query params: `include_deprecated` (bool, default false)
- Response (example):
```json
{
  "models": [
    {
      "provider": "openai",
      "name": "gpt-4o",
      "context_window": 128000,
      "max_output_tokens": 4096,
      "capabilities": {
        "vision": true,
        "audio_input": false,
        "audio_output": false,
        "tool_use": true,
        "json_mode": true,
        "function_calling": true,
        "streaming": true,
        "thinking": false
      },
      "modalities": {"input": ["text", "image"], "output": ["text"]},
      "notes": "Vision multimodal; tool use supported."
    }
  ],
  "total": 1
}
```

## Notes
- The presence and values for models depend on your `tldw_Server_API/Config_Files/config.txt` and environment variables. Some providers may be listed as not configured if API keys or endpoints are missing.
- By default, deprecated models are filtered from responses; set `include_deprecated=true` to include them.
- Health information reflects in-process runtime state, including circuit-breaker status and queue statistics.
- Provider objects may include additional fields when present in config, such as `endpoint`, `default_temperature`, `max_tokens`, and `supports_streaming`.
- Note: `total_configured` reflects the number of providers returned in the response; individual providers indicate configuration with the `is_configured` flag.
