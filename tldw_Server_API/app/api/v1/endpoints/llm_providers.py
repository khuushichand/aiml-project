# llm_providers.py
import asyncio
import time
from functools import partial
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
import os
import requests
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    apply_llm_provider_overrides_to_listing,
)
from tldw_Server_API.app.core.Chat.provider_config import (
    PROVIDER_REQUIRES_KEY,
    PROVIDER_CAPABILITIES,
)
from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager
from tldw_Server_API.app.core.Usage.pricing_catalog import list_provider_models
import tldw_Server_API.app.core.LLM_Calls.adapter_registry as llm_adapter_registry

#######################################################################################################################
#
# Functions:

router = APIRouter()

# ----------------------------------------------------------------------------------
# Model metadata registry
# ----------------------------------------------------------------------------------
# Note: These are conservative, best-effort defaults to enrich the providers API.
# They can be overridden later via config if needed.

MODEL_METADATA: Dict[str, Dict[str, Dict[str, Any]]] = {
    "openai": {
        "gpt-4o": {
            "context_window": 128_000,
            "max_output_tokens": 4096,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": True,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["text"]},
            "notes": "Vision multimodal; tool use supported.",
        },
        "gpt-4o-mini": {
            "context_window": 128_000,
            "max_output_tokens": 4096,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": True,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["text"]},
            "notes": "Smaller 4o variant with vision.",
        },
        "gpt-3.5-turbo": {
            "context_window": 16_384,
            "max_output_tokens": 4096,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": True,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Legacy model; function calling supported.",
        },
    },
    "anthropic": {
        "claude-sonnet-4.5": {
            "context_window": 200_000,
            "max_output_tokens": 64_000,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False
            },
            "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
            "notes": "Claude Sonnet 4.5; fast near-frontier model with tools and vision.",
            "source_url": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
            "last_verified": None
        },
        "claude-haiku-4.5": {
            "context_window": 200_000,
            "max_output_tokens": 64_000,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False
            },
            "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
            "notes": "Claude Haiku 4.5; fastest model with near-frontier intelligence.",
            "source_url": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
            "last_verified": None
        },
        "claude-opus-4.1": {
            "context_window": 200_000,
            "max_output_tokens": 32_000,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False
            },
            "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
            "notes": "Claude Opus 4.1 with tools and vision.",
            "source_url": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
            "last_verified": None
        },
        "claude-sonnet-4": {
            "context_window": 200_000,
            "max_output_tokens": 8192,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False
            },
            "modalities": {"input": ["text", "image", "file"], "output": ["text"]},
            "notes": "Claude Sonnet 4 with tools and vision.",
            "source_url": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
            "last_verified": None
        }
    },
    "google": {
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": True,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "audio", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Pro on Vertex AI; 1,048,576 max input tokens per docs.",
            "source_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro",
            "last_verified": None,
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": True,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "audio", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash Lite on Vertex AI; large context window per docs.",
            "source_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-lite",
            "last_verified": None,
        },
        "gemini-1.5-pro": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": True,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "audio"], "output": ["text"]},
            "notes": "Multimodal Gemini; context may be very large.",
        },
        "gemini-1.5-flash": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": True,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "audio"], "output": ["text"]},
            "notes": "Fast multimodal Gemini variant.",
        },
        "gemini-2.0-flash-exp": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": True,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "audio"], "output": ["text"]},
            "notes": "Experimental Gemini variant.",
        },
    },
    "mistral": {
        "mistral-large-2411": {
            "context_window": 131_072,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Mistral Large 2411; ~131k context window.",
            "source_url": "https://docs.mistral.ai/getting-started/models/models_overview/",
            "last_verified": None,
        },
        "mistral-medium-3.1": {
            "context_window": 131_072,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Mistral Medium 3.1; text-only.",
            "source_url": "https://docs.mistral.ai/getting-started/models/models_overview/",
            "last_verified": None,
        },
        "mistral-small-3.2-24b-instruct": {
            "context_window": 128_000,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["text"]},
            "notes": "Mistral Small 3.2 Instruct with image understanding.",
            "source_url": "https://docs.mistral.ai/getting-started/models/models_overview/",
            "last_verified": None,
        },
        "pixtral-large-2411": {
            "context_window": 131_072,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["text"]},
            "notes": "Pixtral Large 2411 vision model.",
            "source_url": "https://docs.mistral.ai/getting-started/models/models_overview/",
            "last_verified": None,
        },
        "mistral-large-latest": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Tool use supported.",
        },
        "mistral-medium-latest": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": None,
        },
        "mistral-small-latest": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": None,
        },
    },
    "groq": {
        "llama-3.3-70b-versatile": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Groq-hosted Llama; fast inference.",
        },
    },
    "ollama": {
        "llama3.2": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Defaults vary by local model build.",
        },
        "mistral": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": None,
        },
        "codellama": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["text"]},
            "notes": "Code-focused local model.",
        },
    },
}


def _default_model_metadata(provider: str, model: str) -> Dict[str, Any]:
    """Return a conservative default metadata object for unknown models."""
    return {
        "name": model,
        "context_window": None,
        "max_output_tokens": 4096,
        "capabilities": {
            "vision": False,
            "audio_input": False,
            "audio_output": False,
            "tool_use": False,
            "json_mode": False,
            "function_calling": False,
            "streaming": True if provider in {"openai", "anthropic", "google", "mistral", "groq", "openrouter"} else False,
            "thinking": False,
        },
        "modalities": {"input": ["text"], "output": ["text"]},
        "notes": None,
    }


def get_model_metadata(provider: str, model: str) -> Dict[str, Any]:
    """Get metadata for a given provider/model with safe fallbacks."""
    provider = (provider or "").lower()
    model = model or ""
    md = MODEL_METADATA.get(provider, {}).get(model)
    base = _default_model_metadata(provider, model)
    if md is None:
        # Still include name field in final payload
        return base
    # Merge on top of defaults to ensure stable schema
    merged = {**base, **{k: v for k, v in md.items() if k != "name"}}
    merged["name"] = model
    return merged

@router.get("/llm/health", summary="LLM inference health", response_model=Dict[str, Any])
async def llm_health():
    """Health endpoint for the LLM inference subsystem (providers, queue, rate limiter)."""
    from datetime import datetime
    from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager
    from tldw_Server_API.app.core.Chat.request_queue import get_request_queue
    from tldw_Server_API.app.core.Chat.rate_limiter import get_rate_limiter

    health: Dict[str, Any] = {
        "service": "llm_inference",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    try:
        # Provider manager
        pm = get_provider_manager()
        if pm is None:
            health["components"]["providers"] = {"initialized": False}
            health["status"] = "degraded"
        else:
            report = pm.get_health_report()
            any_unhealthy = any(v.get("status") in ["unhealthy", "circuit_open"] for v in report.values())
            health["components"]["providers"] = {
                "initialized": True,
                "count": len(report),
                "report": report
            }
            if any_unhealthy and health["status"] == "healthy":
                health["status"] = "degraded"

        # Request queue
        rq = get_request_queue()
        if rq is None:
            health["components"]["queue"] = {"initialized": False}
            health["status"] = "degraded"
        else:
            q_status = rq.get_queue_status()
            health["components"]["queue"] = {"initialized": True, **q_status}

        # Rate limiter
        rl = get_rate_limiter()
        if rl is None:
            health["components"]["rate_limiter"] = {"initialized": False}
            # Not critical, keep status as-is
        else:
            cfg = rl.config
            health["components"]["rate_limiter"] = {
                "initialized": True,
                "limits": {
                    "global_rpm": cfg.global_rpm,
                    "per_user_rpm": cfg.per_user_rpm,
                    "per_conversation_rpm": cfg.per_conversation_rpm,
                    "per_user_tokens_per_minute": cfg.per_user_tokens_per_minute
                }
            }
    except Exception as e:
        logger.error(f"LLM health check error: {e}")
        health["status"] = "unhealthy"
        health["error"] = str(e)

    return health

def parse_model_string(model_value: str) -> List[str]:
    """
    Parse a model string which could be a single model or comma-separated list.

    Args:
        model_value: Model string from config

    Returns:
        List of model names
    """
    if not model_value:
        return []

    # Handle comma-separated lists
    if ',' in model_value:
        return [m.strip() for m in model_value.split(',') if m.strip()]

    # Single model
    return [model_value.strip()] if model_value.strip() else []


# Local model discovery helpers (best-effort; cached to avoid hammering endpoints)
LOCAL_MODEL_DISCOVERY_TIMEOUT = 3.0  # seconds
LOCAL_MODEL_DISCOVERY_TTL = 300  # seconds
_LOCAL_MODEL_CACHE: Dict[str, Tuple[float, List[str]]] = {}


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for v in values:
        if not v:
            continue
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def _candidate_model_urls_for_openai_endpoint(endpoint_url: str) -> List[str]:
    """Return likely /models endpoints for OpenAI-compatible servers."""
    try:
        parsed = urlparse(endpoint_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return []

        base = f"{parsed.scheme}://{parsed.netloc}"
        path = (parsed.path or "").rstrip("/")

        candidates = [
            urljoin(base, "/v1/models"),
        ]

        if path:
            candidates.append(urljoin(base, f"{path}/models"))
            # Remove common suffixes like /chat/completions
            for suffix in ["/chat/completions", "/completions", "/v1/chat/completions", "/v1/completions"]:
                if path.endswith(suffix):
                    prefix = path[: -len(suffix)]
                    candidates.append(urljoin(base, f"{prefix}/models"))
                    candidates.append(urljoin(base, f"{prefix}/v1/models"))

        return _dedupe_preserve_order([c.rstrip("/") for c in candidates if c])
    except Exception:
        return []


def _candidate_model_urls_for_ollama_endpoint(endpoint_url: str) -> List[str]:
    """Return likely endpoints for Ollama model listings."""
    try:
        parsed = urlparse(endpoint_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return []

        base = f"{parsed.scheme}://{parsed.netloc}"
        path = (parsed.path or "").rstrip("/")
        candidates = [
            urljoin(base, "/api/tags"),
            urljoin(base, "/v1/models"),
        ]
        if path and path not in {"/"}:
            candidates.append(urljoin(base, f"{path}/api/tags"))
            candidates.append(urljoin(base, f"{path}/models"))

        return _dedupe_preserve_order([c.rstrip("/") for c in candidates if c])
    except Exception:
        return []


def _extract_models_from_response(payload: Any) -> List[str]:
    """Normalize various model-list responses into a flat list of ids."""
    models: List[str] = []
    if isinstance(payload, dict):
        data_section = payload.get("data")
        if isinstance(data_section, list):
            for item in data_section:
                if isinstance(item, dict):
                    candidate = item.get("id") or item.get("model") or item.get("name")
                else:
                    candidate = item
                if isinstance(candidate, str) and candidate.strip():
                    models.append(candidate.strip())

        models_section = payload.get("models")
        if isinstance(models_section, list):
            for item in models_section:
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("model") or item.get("id")
                else:
                    candidate = item
                if isinstance(candidate, str) and candidate.strip():
                    models.append(candidate.strip())

    return _dedupe_preserve_order(models)


def discover_models_from_endpoint(
    provider: str,
    endpoint_url: str,
    discovery_type: str = "openai",
    api_key: Optional[str] = None,
) -> List[str]:
    """
    Best-effort discovery of models from a configured local endpoint.

    Tries common OpenAI-compatible /models endpoints (or Ollama tags),
    uses a short timeout, and caches results to avoid noisy retries.
    """
    endpoint_url = (endpoint_url or "").strip()
    if not endpoint_url:
        return []

    cache_key = f"{provider}:{endpoint_url}"
    now = time.time()
    cached = _LOCAL_MODEL_CACHE.get(cache_key)
    if cached and (now - cached[0] < LOCAL_MODEL_DISCOVERY_TTL):
        return cached[1]

    discovery_type = (discovery_type or "openai").lower()
    if discovery_type == "ollama":
        candidates = _candidate_model_urls_for_ollama_endpoint(endpoint_url)
    else:
        candidates = _candidate_model_urls_for_openai_endpoint(endpoint_url)

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    discovered: List[str] = []
    for url in candidates:
        try:
            resp = requests.get(url, headers=headers, timeout=LOCAL_MODEL_DISCOVERY_TIMEOUT)
            if resp.status_code >= 400:
                logger.debug(f"[Model discovery] {provider}: {url} responded with {resp.status_code}")
                continue
            discovered = _extract_models_from_response(resp.json())
            if discovered:
                logger.info(f"[Model discovery] {provider}: found {len(discovered)} models via {url}")
                break
        except Exception as exc:
            logger.debug(f"[Model discovery] {provider}: error querying {url}: {exc}")
            continue

    _LOCAL_MODEL_CACHE[cache_key] = (now, discovered)
    return discovered

def get_configured_providers(include_deprecated: bool = False) -> Dict[str, Any]:
    """
    Get list of configured LLM providers with their models from the config file.

    Returns:
        Dictionary containing provider information
    """
    try:
        config_parser = load_comprehensive_config()
        providers = []

        # Check if we have the required sections
        if not config_parser.has_section('API') and not config_parser.has_section('Local-API'):
            logger.warning("No API or Local-API sections found in config")
            return {
                'providers': [],
                'default_provider': None,
                'total_configured': 0,
                'message': 'No API configuration sections found in config.txt'
            }

        # Define provider mappings with their config keys
        provider_mappings = {
            # Commercial APIs (from API section)
            'openai': {
                'display_name': 'OpenAI',
                'api_key_field': 'openai_api_key',
                'model_field': 'openai_model',
                'type': 'commercial',
                'section': 'API'
            },
            'bedrock': {
                'display_name': 'AWS Bedrock',
                'api_key_field': 'bedrock_api_key',
                'model_field': 'bedrock_model',
                'type': 'commercial',
                'section': 'API'
            },
            'anthropic': {
                'display_name': 'Anthropic',
                'api_key_field': 'anthropic_api_key',
                'model_field': 'anthropic_model',
                'type': 'commercial',
                'section': 'API'
            },
            'cohere': {
                'display_name': 'Cohere',
                'api_key_field': 'cohere_api_key',
                'model_field': 'cohere_model',
                'type': 'commercial',
                'section': 'API'
            },
            'deepseek': {
                'display_name': 'DeepSeek',
                'api_key_field': 'deepseek_api_key',
                'model_field': 'deepseek_model',
                'type': 'commercial',
                'section': 'API'
            },
            'google': {
                'display_name': 'Google',
                'api_key_field': 'google_api_key',
                'model_field': 'google_model',
                'type': 'commercial',
                'section': 'API'
            },
            'groq': {
                'display_name': 'Groq',
                'api_key_field': 'groq_api_key',
                'model_field': 'groq_model',
                'type': 'commercial',
                'section': 'API'
            },
            'mistral': {
                'display_name': 'Mistral',
                'api_key_field': 'mistral_api_key',
                'model_field': 'mistral_model',
                'type': 'commercial',
                'section': 'API'
            },
            'huggingface': {
                'display_name': 'HuggingFace',
                'api_key_field': 'huggingface_api_key',
                'model_field': 'huggingface_model',
                'type': 'commercial',
                'section': 'API'
            },
            'openrouter': {
                'display_name': 'OpenRouter',
                'api_key_field': 'openrouter_api_key',
                'model_field': 'openrouter_model',
                'type': 'commercial',
                'section': 'API'
            },
            'moonshot': {
                'display_name': 'Moonshot',
                'api_key_field': 'moonshot_api_key',
                'model_field': 'moonshot_model',
                'type': 'commercial',
                'section': 'API'
            },
            'zai': {
                'display_name': 'Z.AI',
                'api_key_field': 'zai_api_key',
                'model_field': 'zai_model',
                'type': 'commercial',
                'section': 'API'
            },
            'minimax': {
                'display_name': 'MiniMax',
                'api_key_field': 'minimax_api_key',
                'model_field': 'minimax_model',
                'type': 'commercial',
                'section': 'API'
            },
            # Local APIs (from Local-API section)
            'llama': {
                'display_name': 'Llama.cpp',
                'endpoint_field': 'llama_api_IP',
                'model_field': None,  # No model field in config
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'kobold': {
                'display_name': 'Kobold.cpp',
                'endpoint_field': 'kobold_api_IP',
                'model_field': None,  # No model field in config
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'ooba': {
                'display_name': 'Oobabooga',
                'endpoint_field': 'ooba_api_IP',
                'model_field': None,  # No model field in config
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'tabby': {
                'display_name': 'TabbyAPI',
                'endpoint_field': 'tabby_api_IP',
                'model_field': None,  # No model field in config
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'vllm': {
                'display_name': 'vLLM',
                'endpoint_field': 'vllm_api_IP',
                'model_field': 'vllm_model',
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'ollama': {
                'display_name': 'Ollama',
                'endpoint_field': 'ollama_api_IP',
                'model_field': 'ollama_model',
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'ollama',
            },
            'aphrodite': {
                'display_name': 'Aphrodite',
                'endpoint_field': 'aphrodite_api_IP',
                'model_field': 'aphrodite_model',
                'type': 'local',
                'section': 'Local-API',
                'model_discovery': 'openai',
            },
            'mlx': {
                'display_name': 'MLX',
                'endpoint_field': None,
                'model_field': 'mlx_model_path',
                'type': 'local',
                'section': 'MLX',
                'model_discovery': None,
            },
            'custom_openai_api': {
                'display_name': 'Custom OpenAI API',
                'endpoint_field': 'custom_openai_api_ip',
                'model_field': 'custom_openai_api_model',
                'type': 'local',
                'section': 'API',
                'model_discovery': 'openai',
            }
        }

        # Optional: live health report
        health_report = {}
        try:
            pm = get_provider_manager()
            if pm:
                health_report = pm.get_health_report()
        except Exception:
            health_report = {}

        # Process each provider
        for provider_name, provider_info in provider_mappings.items():
            section_name = provider_info.get('section')

            config_section_exists = bool(section_name and config_parser.has_section(section_name))
            # Allow MLX to surface even when only env-based config exists
            if not config_section_exists and provider_name != "mlx":
                continue
            # For MLX, proceed even if the [MLX] section is absent to allow env-only configs or to show as disabled
            section_exists = config_section_exists or provider_name == "mlx"
            if not section_exists:
                continue

            # Check if provider is configured
            is_configured = False
            endpoint_url: Optional[str] = None
            api_key_value: Optional[str] = None

            if provider_info['type'] == 'commercial':
                # Check for API key
                api_key_field = provider_info.get('api_key_field')
                if api_key_field and config_section_exists and config_parser.has_option(section_name, api_key_field):
                    api_key = config_parser.get(section_name, api_key_field, fallback='')
                    # Check if API key is valid (not empty and not placeholder)
                    if api_key and not api_key.startswith('<') and not api_key.endswith('>'):
                        is_configured = True
                        api_key_value = api_key
            else:
                # Check for endpoint URL for local providers
                endpoint_field = provider_info.get('endpoint_field')
                if endpoint_field and config_section_exists and config_parser.has_option(section_name, endpoint_field):
                    endpoint_url = config_parser.get(section_name, endpoint_field, fallback='')
                    if endpoint_url and endpoint_url.strip() and not endpoint_url.startswith('<'):
                        is_configured = True
                # Optional API key support for local endpoints that require it
                api_key_field = provider_info.get('api_key_field')
                if api_key_field and config_section_exists and config_parser.has_option(section_name, api_key_field):
                    val = config_parser.get(section_name, api_key_field, fallback='')
                    if val and not val.startswith('<') and not val.endswith('>'):
                        api_key_value = val

            # Always include the provider, but mark if it's configured
            # Get the models from config
            model_field = provider_info.get('model_field')
            models = []

            if model_field and config_section_exists and config_parser.has_option(section_name, model_field):
                model_value = config_parser.get(section_name, model_field, fallback='')
                models = parse_model_string(model_value)
            # Env-based model path for MLX when no config section is present
            if provider_name == "mlx" and not models:
                env_model = os.getenv("MLX_MODEL_PATH", "")
                if env_model:
                    models = parse_model_string(env_model)
                    is_configured = True
            if provider_name == "mlx" and models and not is_configured:
                is_configured = True

            # Augment or seed with models from the pricing catalog for commercial providers.
            # This makes model_pricing.json the primary reference for available models,
            # while still honoring any explicit config.txt entries.
            if provider_info['type'] == 'commercial':
                try:
                    pricing_models = list_provider_models(provider_name)
                    # Heuristic: exclude obvious embedding model ids from chat model lists
                    pricing_models = [m for m in pricing_models if 'embed' not in m.lower() and 'embedding' not in m.lower()]
                except Exception:
                    pricing_models = []
                if pricing_models:
                    # Preserve order: config models first, then pricing extras
                    seen = set(m.strip() for m in models)
                    extras = [m for m in pricing_models if m not in seen]
                    models = models + extras
            else:
                # For local endpoints, try to discover models if none were provided
                if not models and is_configured and endpoint_url:
                    discovered_models = discover_models_from_endpoint(
                        provider_name,
                        endpoint_url,
                        provider_info.get('model_discovery', 'openai'),
                        api_key_value,
                    )
                    if discovered_models:
                        models = discovered_models

            # Build models and metadata
            models_info = [get_model_metadata(provider_name, m) for m in models]
            if not include_deprecated:
                # Filter out deprecated models by default
                filtered = [mi for mi in models_info if not mi.get('deprecated', False)]
                models_info = filtered
                models = [mi['name'] for mi in models_info]

            endpoint_only = provider_info['type'] == 'local' and is_configured and not models

            provider_data = {
                'name': provider_name,
                'display_name': provider_info['display_name'],
                'models': models,
                # New: detailed metadata per model
                'models_info': models_info,
                'type': provider_info['type'],
                'default_model': models[0] if models else None,
                'is_configured': is_configured,  # Add configuration status
                'endpoint_only': endpoint_only
            }

            # Add endpoint for local providers
            if provider_info['type'] == 'local':
                if endpoint_url:
                    provider_data['endpoint'] = endpoint_url
                else:
                    endpoint_field = provider_info.get('endpoint_field')
                    if endpoint_field and config_parser.has_option(section_name, endpoint_field):
                        provider_data['endpoint'] = config_parser.get(section_name, endpoint_field, fallback='')

            # Add other useful config fields
            temp_field = f'{provider_name}_temperature'
            if config_parser.has_option(section_name, temp_field):
                provider_data['default_temperature'] = float(config_parser.get(section_name, temp_field, fallback='0.7'))

            tokens_field = f'{provider_name}_max_tokens'
            if config_parser.has_option(section_name, tokens_field):
                provider_data['max_tokens'] = int(config_parser.get(section_name, tokens_field, fallback='4096'))

            streaming_field = f'{provider_name}_streaming'
            if config_parser.has_option(section_name, streaming_field):
                provider_data['supports_streaming'] = config_parser.get(section_name, streaming_field, fallback='False').lower() == 'true'

            # Centralized capability diagnostics
            try:
                provider_data['requires_api_key'] = bool(PROVIDER_REQUIRES_KEY.get(provider_name, provider_info['type'] == 'commercial'))
                # Start with defaults from static map
                capabilities = dict(PROVIDER_CAPABILITIES.get(provider_name, {}))
                # Merge adapter-reported capabilities if available
                try:
                    reg = llm_adapter_registry.get_registry()
                    reg_caps = reg.get_all_capabilities()
                    if provider_name in reg_caps:
                        capabilities.update(reg_caps[provider_name])
                except Exception:
                    pass
                # Merge config-indicated streaming support as an override if provided
                if 'supports_streaming' not in capabilities and 'supports_streaming' in provider_data:
                    capabilities['supports_streaming'] = provider_data['supports_streaming']
                provider_data['capabilities'] = capabilities
            except Exception:
                provider_data['requires_api_key'] = provider_info['type'] == 'commercial'

            # Attach live health if available
            try:
                if provider_name in health_report:
                    provider_data['health'] = health_report[provider_name]
            except Exception:
                pass

            providers.append(provider_data)

        # Get the default provider from config
        default_api = 'openai'
        if config_parser.has_section('API') and config_parser.has_option('API', 'default_api'):
            default_api = config_parser.get('API', 'default_api', fallback='openai')

        # Strict policy: do not pull models from other sections.

        return {
            'providers': providers,
            'default_provider': default_api,
            'total_configured': len(providers)
        }

    except Exception as e:
        logger.error(f"Error getting configured providers: {e}", exc_info=True)
        return {
            'providers': [],
            'default_provider': 'openai',
            'total_configured': 0,
            'error': 'An internal error occurred getting available providers. Please check your config.txt file for errors and try again. If the problem persists, please contact support for assistance.'
        }


async def get_configured_providers_async(include_deprecated: bool = False) -> Dict[str, Any]:
    """Run provider discovery in a worker thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(get_configured_providers, include_deprecated=include_deprecated),
    )


def get_all_available_models() -> List[str]:
    """
    Get a flat list of all available models across all configured providers.

    Returns:
        List of all available model names
    """
    result = apply_llm_provider_overrides_to_listing(get_configured_providers())
    models = []

    for provider in result.get('providers', []):
        for model in provider.get('models', []):
            # Add provider prefix to make models unique
            models.append(f"{provider['name']}/{model}")

    return models

#######################################################################################################################
#
# Endpoints:

@router.get("/llm/providers",
    summary="Get configured LLM providers",
    description="Returns a list of all configured LLM providers with their models from config",
    response_model=Dict[str, Any])
async def get_llm_providers(include_deprecated: bool = False):
    """
    Get all configured LLM providers and their models.

    Returns:
        Dictionary containing:
        - providers: List of provider configurations
        - default_provider: The default provider name
        - total_configured: Number of configured providers
    """
    try:
        result = await get_configured_providers_async(include_deprecated=include_deprecated)
        result = apply_llm_provider_overrides_to_listing(result)
        result = apply_llm_provider_overrides_to_listing(result)

        # Inject Diagnostics UI interval bounds from server config if available
        try:
            cfg = load_comprehensive_config()
            section = 'LLM_Diagnostics'
            def _getint(key: str, fallback: int) -> int:
                try:
                    return cfg.getint(section, key, fallback=fallback)
                except Exception:
                    return fallback

            qs_min = _getint('queue_status_auto_min_secs', 1)
            qs_max = _getint('queue_status_auto_max_secs', 60)
            qa_min = _getint('queue_activity_auto_min_secs', 1)
            qa_max = _getint('queue_activity_auto_max_secs', 60)
            # Normalize if misconfigured
            if qs_min > qs_max:
                qs_min, qs_max = qs_max, qs_min
            if qa_min > qa_max:
                qa_min, qa_max = qa_max, qa_min
            result['diagnostics_ui'] = {
                'queue_status_auto': {'min': int(max(1, qs_min)), 'max': int(max(1, qs_max))},
                'queue_activity_auto': {'min': int(max(1, qa_min)), 'max': int(max(1, qa_max))},
            }
        except Exception:
            # Best-effort; omit diagnostics_ui on failure
            pass

        result = apply_llm_provider_overrides_to_listing(result)

        if result['total_configured'] == 0:
            logger.warning("No LLM providers are configured")
            return {
                'providers': [],
                'default_provider': None,
                'total_configured': 0,
                'message': 'No LLM providers are configured. Please check your config.txt file.'
            }

        logger.info(f"Found {result['total_configured']} configured LLM providers")
        return result

    except Exception as e:
        logger.error(f"Error in get_llm_providers endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve LLM providers: {str(e)}"
        )


@router.get("/llm/models/metadata",
    summary="Get model metadata across providers",
    description="Returns flattened model metadata for all providers",
    response_model=Dict[str, Any])
async def get_models_metadata(include_deprecated: bool = False):
    try:
        result = await get_configured_providers_async(include_deprecated=include_deprecated)
        result = apply_llm_provider_overrides_to_listing(result)
        flattened: List[Dict[str, Any]] = []
        for provider in result.get('providers', []):
            for mi in provider.get('models_info', []):
                flattened.append({
                    'provider': provider.get('name'),
                    **mi,
                })
        return {
            'models': flattened,
            'total': len(flattened)
        }
    except Exception as e:
        logger.error(f"Error getting models metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve model metadata: {str(e)}"
        )

@router.get("/llm/providers/{provider_name}",
    summary="Get specific provider details",
    description="Returns details for a specific LLM provider",
    response_model=Dict[str, Any])
async def get_provider_details(provider_name: str, include_deprecated: bool = False):
    """
    Get details for a specific LLM provider.

    Args:
        provider_name: Name of the provider (e.g., 'openai', 'anthropic')

    Returns:
        Provider details including models and configuration
    """
    try:
        result = await get_configured_providers_async(include_deprecated=include_deprecated)

        # Find the specific provider
        for provider in result['providers']:
            if provider['name'] == provider_name:
                logger.info(f"Retrieved details for provider: {provider_name}")
                return provider

        # Provider not found or not configured
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' is not configured or not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider details for {provider_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve provider details: {str(e)}"
        )

@router.get("/llm/models",
    summary="Get all available models",
    description="Returns a flat list of all available models across all providers",
    response_model=List[str])
async def get_all_models(include_deprecated: bool = False):
    """
    Get all available models from all configured providers.

    Returns:
        List of model names with provider prefix
    """
    try:
        result = await get_configured_providers_async(include_deprecated=include_deprecated)
        models: List[str] = []
        for provider in result.get('providers', []):
            for model in provider.get('models', []):
                models.append(f"{provider['name']}/{model}")
        logger.info(f"Found {len(models)} total models across all providers")
        return models
    except Exception as e:
        logger.error(f"Error getting all models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve models: {str(e)}"
        )

# End of llm_providers.py
