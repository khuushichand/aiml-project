# llm_providers.py
import asyncio
import hashlib
import json
import os
import threading
import time
from functools import partial
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

import tldw_Server_API.app.core.LLM_Calls.adapter_registry as llm_adapter_registry
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import get_api_keys
from tldw_Server_API.app.core.AuthNZ.llm_provider_overrides import (
    apply_llm_provider_overrides_to_listing,
)
from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.exceptions import (
    EgressPolicyError,
    NetworkError,
    RetryExhaustedError,
)
from tldw_Server_API.app.core.http_client import RetryPolicy as _RetryPolicy
from tldw_Server_API.app.core.http_client import fetch as _http_fetch
from tldw_Server_API.app.core.Image_Generation.listing import list_image_models_for_catalog
from tldw_Server_API.app.core.LLM_Calls.provider_metadata import (
    PROVIDER_CAPABILITIES,
    provider_requires_api_key,
)
from tldw_Server_API.app.core.Usage.pricing_catalog import list_provider_models

#######################################################################################################################
#
# Functions:

router = APIRouter()

_LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    json.JSONDecodeError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    EgressPolicyError,
    NetworkError,
    RetryExhaustedError,
)

# ----------------------------------------------------------------------------------
# Model metadata registry
# ----------------------------------------------------------------------------------
# Note: These are conservative, best-effort defaults to enrich the providers API.
# They can be overridden later via config if needed.

MODEL_METADATA: dict[str, dict[str, dict[str, Any]]] = {
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
        "gemini-3-pro-preview": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 3 Pro Preview (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-3-flash-preview": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 3 Flash Preview (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-3-pro-image-preview": {
            "type": "image",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["image"]},
            "notes": "Gemini 3 Pro Image Preview (image generation).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Pro on Vertex AI; 1,048,576 max input tokens per docs.",
            "source_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro",
            "last_verified": None,
        },
        "gemini-2.5-flash": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-preview": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash Preview (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-preview-09-2025": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash Preview (09-2025).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash Lite on Vertex AI; large context window per docs.",
            "source_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-lite",
            "last_verified": None,
        },
        "gemini-2.5-flash-lite-preview": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash-Lite Preview (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-lite-preview-09-2025": {
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
            "modalities": {"input": ["text", "image", "audio", "video", "file"], "output": ["text"]},
            "notes": "Gemini 2.5 Flash-Lite Preview (09-2025).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-native-audio-preview-12-2025": {
            "type": "audio",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": True,
                "audio_output": True,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": True,
                "thinking": False,
            },
            "modalities": {"input": ["text", "audio", "video"], "output": ["audio", "text"]},
            "notes": "Gemini 2.5 Flash Native Audio (Live API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-image": {
            "type": "image",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["image"]},
            "notes": "Gemini 2.5 Flash Image (image generation).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-flash-preview-tts": {
            "type": "audio",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": True,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["audio"]},
            "notes": "Gemini 2.5 Flash Preview TTS.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-pro-preview-tts": {
            "type": "audio",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": True,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["audio"]},
            "notes": "Gemini 2.5 Pro Preview TTS.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-2.5-computer-use-preview-10-2025": {
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": True,
                "json_mode": False,
                "function_calling": True,
                "streaming": True,
                "thinking": True,
            },
            "modalities": {"input": ["text", "image"], "output": ["text"]},
            "notes": "Gemini 2.5 Computer Use Preview (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
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
        "gemini-2.0-flash": {
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
            "notes": "Gemini 2.0 Flash (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
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
        "gemini-2.0-flash-lite": {
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
            "notes": "Gemini 2.0 Flash-Lite (Gemini API).",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "imagen-4.0-generate-001": {
            "type": "image",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["image"]},
            "notes": "Imagen 4 (standard) image generation; priced per image.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "imagen-4.0-ultra-generate-001": {
            "type": "image",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["image"]},
            "notes": "Imagen 4 Ultra image generation; priced per image.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "imagen-4.0-fast-generate-001": {
            "type": "image",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["image"]},
            "notes": "Imagen 4 Fast image generation; priced per image.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "veo-3.1-generate-preview": {
            "type": "video",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["video"]},
            "notes": "Veo 3.1 preview video generation; priced per second.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "veo-3.1-fast-generate-preview": {
            "type": "video",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["video"]},
            "notes": "Veo 3.1 Fast preview video generation; priced per second.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "veo-3.0-generate-001": {
            "type": "video",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["video"]},
            "notes": "Veo 3 video generation; priced per second.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "veo-3.0-fast-generate-001": {
            "type": "video",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["video"]},
            "notes": "Veo 3 Fast video generation; priced per second.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "veo-2.0-generate-001": {
            "type": "video",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image"], "output": ["video"]},
            "notes": "Veo 2 video generation; priced per second.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-embedding-001": {
            "type": "embedding",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "embedding": True,
                "vision": False,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text"], "output": ["embedding"]},
            "notes": "Gemini Embedding model.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
        },
        "gemini-robotics-er-1.5-preview": {
            "type": "other",
            "context_window": None,
            "max_output_tokens": None,
            "capabilities": {
                "vision": True,
                "audio_input": False,
                "audio_output": False,
                "tool_use": False,
                "json_mode": False,
                "function_calling": False,
                "streaming": False,
                "thinking": False,
            },
            "modalities": {"input": ["text", "image", "video"], "output": ["text"]},
            "notes": "Gemini Robotics-ER 1.5 Preview; pricing follows token-based tiers.",
            "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "last_verified": None,
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


def _default_model_metadata(provider: str, model: str) -> dict[str, Any]:
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
            "streaming": provider in {"openai", "anthropic", "google", "mistral", "groq", "openrouter"},
            "thinking": False,
        },
        "modalities": {"input": ["text"], "output": ["text"]},
        "notes": None,
    }


def get_model_metadata(provider: str, model: str) -> dict[str, Any]:
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

@router.get("/llm/health", summary="LLM inference health", response_model=dict[str, Any])
async def llm_health():
    """Health endpoint for the LLM inference subsystem (providers, queue, rate limiter)."""
    from datetime import datetime

    from tldw_Server_API.app.core.Chat.provider_manager import get_provider_manager
    from tldw_Server_API.app.core.Chat.rate_limiter import get_rate_limiter
    from tldw_Server_API.app.core.Chat.request_queue import get_request_queue

    health: dict[str, Any] = {
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
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"LLM health check error: {e}")
        health["status"] = "unhealthy"
        health["error"] = str(e)

    return health

def parse_model_string(model_value: str) -> list[str]:
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
_LOCAL_MODEL_CACHE: dict[str, tuple[float, list[str]]] = {}
OPENROUTER_MODEL_DISCOVERY_TIMEOUT = 5.0  # seconds
OPENROUTER_MODEL_DISCOVERY_TTL_DEFAULT = 600  # seconds
_OPENROUTER_MODEL_CACHE: dict[str, tuple[float, list[str]]] = {}
_OPENROUTER_MODEL_CACHE_LOCK = threading.Lock()


def _openrouter_discovery_ttl_seconds() -> int:
    raw = os.getenv("OPENROUTER_MODEL_DISCOVERY_TTL_SECONDS")
    if raw is None:
        return OPENROUTER_MODEL_DISCOVERY_TTL_DEFAULT
    try:
        parsed = int(str(raw).strip())
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        return OPENROUTER_MODEL_DISCOVERY_TTL_DEFAULT
    return max(30, parsed)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for v in values:
        if not v:
            continue
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def _candidate_model_urls_for_openai_endpoint(endpoint_url: str) -> list[str]:
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
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        return []


def _candidate_model_urls_for_ollama_endpoint(endpoint_url: str) -> list[str]:
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
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        return []


def _extract_models_from_response(payload: Any) -> list[str]:
    """Normalize various model-list responses into a flat list of ids."""
    models: list[str] = []
    if isinstance(payload, dict):
        data_section = payload.get("data")
        if isinstance(data_section, list):
            for item in data_section:
                candidate = item.get("id") or item.get("model") or item.get("name") if isinstance(item, dict) else item
                if isinstance(candidate, str) and candidate.strip():
                    models.append(candidate.strip())

        models_section = payload.get("models")
        if isinstance(models_section, list):
            for item in models_section:
                candidate = item.get("name") or item.get("model") or item.get("id") if isinstance(item, dict) else item
                if isinstance(candidate, str) and candidate.strip():
                    models.append(candidate.strip())

    return _dedupe_preserve_order(models)


def _resolve_openrouter_models_url() -> str:
    base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    if not base_url:
        base_url = "https://openrouter.ai/api/v1"
    base_url = base_url.rstrip("/")
    if base_url.lower().endswith("/models"):
        base_url = base_url[: -len("/models")]
    return f"{base_url}/models"


def discover_openrouter_models(
    api_key: Optional[str],
    *,
    force_refresh: bool = False,
) -> list[str]:
    """Best-effort discovery of OpenRouter model ids from /models.

    Results are cached briefly to avoid repeated upstream calls. On discovery
    failures, this function falls back to cached values when available.
    """
    resolved_key = (api_key or "").strip()
    if not resolved_key:
        return []

    models_url = _resolve_openrouter_models_url()
    key_digest = hashlib.sha1(resolved_key.encode("utf-8")).hexdigest()[:12]
    cache_key = f"{models_url}|{key_digest}"
    now = time.time()
    ttl = _openrouter_discovery_ttl_seconds()

    with _OPENROUTER_MODEL_CACHE_LOCK:
        cached = _OPENROUTER_MODEL_CACHE.get(cache_key)
    if cached and not force_refresh and (now - cached[0] < ttl):
        return list(cached[1])

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolved_key}",
    }
    referer = (os.getenv("OPENROUTER_SITE_URL") or "").strip()
    site_name = (os.getenv("OPENROUTER_SITE_NAME") or "").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if site_name:
        headers["X-Title"] = site_name

    try:
        resp = _http_fetch(
            method="GET",
            url=models_url,
            headers=headers,
            timeout=OPENROUTER_MODEL_DISCOVERY_TIMEOUT,
            retry=_RetryPolicy(attempts=1),
        )
        try:
            if resp.status_code >= 400:
                logger.warning(
                    f"[OpenRouter model discovery] {models_url} responded with {resp.status_code}"
                )
                return list(cached[1]) if cached else []
            payload = resp.json()
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()

        discovered = _extract_models_from_response(payload)
        with _OPENROUTER_MODEL_CACHE_LOCK:
            _OPENROUTER_MODEL_CACHE[cache_key] = (time.time(), list(discovered))

        if discovered:
            logger.info(
                f"[OpenRouter model discovery] found {len(discovered)} models via {models_url}"
            )
        return discovered
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"[OpenRouter model discovery] {models_url} failed: {exc}")
        return list(cached[1]) if cached else []
    except Exception as exc:  # noqa: BLE001 - discovery must fail open
        logger.debug(f"[OpenRouter model discovery] unexpected failure via {models_url}: {exc}")
        return list(cached[1]) if cached else []


def discover_models_from_endpoint(
    provider: str,
    endpoint_url: str,
    discovery_type: str = "openai",
    api_key: Optional[str] = None,
) -> list[str]:
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

    discovered: list[str] = []
    for url in candidates:
        try:
            resp = _http_fetch(
                method="GET",
                url=url,
                headers=headers,
                timeout=LOCAL_MODEL_DISCOVERY_TIMEOUT,
                retry=_RetryPolicy(attempts=1),
            )
            try:
                if resp.status_code >= 400:
                    logger.debug(f"[Model discovery] {provider}: {url} responded with {resp.status_code}")
                    continue
                discovered = _extract_models_from_response(resp.json())
                if discovered:
                    logger.info(f"[Model discovery] {provider}: found {len(discovered)} models via {url}")
                    break
            finally:
                close = getattr(resp, "close", None)
                if callable(close):
                    close()
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"[Model discovery] {provider}: error querying {url}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - best-effort local discovery must fail open
            logger.debug(f"[Model discovery] {provider}: unexpected error querying {url}: {exc}")
            continue

    _LOCAL_MODEL_CACHE[cache_key] = (now, discovered)
    return discovered

def get_configured_providers(
    include_deprecated: bool = False,
    refresh_openrouter: bool = False,
) -> dict[str, Any]:
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

        try:
            api_keys_by_provider = get_api_keys()
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
            api_keys_by_provider = {}

        def _valid_api_key(value: Optional[str]) -> Optional[str]:
            if not isinstance(value, str):
                return None
            trimmed = value.strip()
            if not trimmed:
                return None
            if trimmed.startswith("<") and trimmed.endswith(">"):
                return None
            return trimmed

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
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
            health_report = {}
        registry_capability_envelopes = _llm_registry_capability_envelopes()

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
                api_key = None
                if api_key_field and config_section_exists and config_parser.has_option(section_name, api_key_field):
                    api_key = config_parser.get(section_name, api_key_field, fallback='')
                api_key = _valid_api_key(api_key) or _valid_api_key(api_keys_by_provider.get(provider_name))
                if api_key:
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
                except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
                    pricing_models = []

                if provider_name == "openrouter" and is_configured and api_key_value:
                    live_openrouter_models = discover_openrouter_models(
                        api_key_value,
                        force_refresh=refresh_openrouter,
                    )
                    if live_openrouter_models:
                        pricing_models = _dedupe_preserve_order(
                            live_openrouter_models + pricing_models
                        )

                if pricing_models:
                    # Preserve order: config models first, then pricing extras
                    seen = {m.strip() for m in models}
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
                provider_data['requires_api_key'] = provider_requires_api_key(provider_name)
                # Start with defaults from static map
                capabilities = dict(PROVIDER_CAPABILITIES.get(provider_name, {}))
                envelope = registry_capability_envelopes.get(provider_name)
                # Merge adapter-reported capabilities if available
                if envelope:
                    env_caps = envelope.get("capabilities")
                    if isinstance(env_caps, dict):
                        capabilities.update(env_caps)
                    provider_data["availability"] = envelope.get("availability", "unknown")
                    provider_data["capability_envelope"] = {
                        "provider": provider_name,
                        "availability": envelope.get("availability", "unknown"),
                        "capabilities": env_caps if isinstance(env_caps, dict) else None,
                    }
                # Merge config-indicated streaming support as an override if provided
                if 'supports_streaming' not in capabilities and 'supports_streaming' in provider_data:
                    capabilities['supports_streaming'] = provider_data['supports_streaming']
                provider_data['capabilities'] = capabilities
            except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
                provider_data['requires_api_key'] = provider_info['type'] == 'commercial'

            # Attach live health if available
            try:
                if provider_name in health_report:
                    provider_data['health'] = health_report[provider_name]
            except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
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

    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting configured providers: {e}", exc_info=True)
        return {
            'providers': [],
            'default_provider': 'openai',
            'total_configured': 0,
            'error': 'An internal error occurred getting available providers. Please check your config.txt file for errors and try again. If the problem persists, please contact support for assistance.'
        }


async def get_configured_providers_async(
    include_deprecated: bool = False,
    refresh_openrouter: bool = False,
) -> dict[str, Any]:
    """Run provider discovery in a worker thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(
            get_configured_providers,
            include_deprecated=include_deprecated,
            refresh_openrouter=refresh_openrouter,
        ),
    )


def get_all_available_models() -> list[str]:
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


def _normalize_filter_values(values: Optional[list[str]]) -> Optional[set[str]]:
    if not values:
        return None
    normalized = {str(v).strip().lower() for v in values if v and str(v).strip()}
    return normalized or None


def _infer_model_type(model_info: dict[str, Any]) -> str:
    declared = model_info.get("type")
    if declared:
        return str(declared).strip().lower()
    name = str(model_info.get("name") or model_info.get("id") or "").lower()
    if "embed" in name or "embedding" in name:
        return "embedding"
    caps = model_info.get("capabilities")
    if isinstance(caps, dict) and caps.get("embedding"):
        return "embedding"
    return "chat"


def _normalize_modalities(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip().lower() for v in value if v and str(v).strip()]
    return [str(value).strip().lower()]


def _llm_registry_capability_envelopes() -> dict[str, dict[str, Any]]:
    """
    Return provider capability envelopes from the LLM adapter registry.

    Preferred format is wrapper-level `list_capabilities()` entries:
      {"provider": str, "availability": str, "capabilities": dict|None}

    Falls back to legacy `get_all_capabilities()` (treated as enabled).
    """
    envelopes: dict[str, dict[str, Any]] = {}

    try:
        registry = llm_adapter_registry.get_registry()
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        return envelopes

    try:
        list_caps = getattr(registry, "list_capabilities", None)
        if callable(list_caps):
            try:
                entries = list_caps(include_disabled=True)
            except TypeError:
                entries = list_caps()
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    provider_name = str(entry.get("provider") or "").strip()
                    if not provider_name:
                        continue
                    availability = str(entry.get("availability") or "unknown").strip().lower() or "unknown"
                    raw_caps = entry.get("capabilities")
                    envelopes[provider_name] = {
                        "provider": provider_name,
                        "availability": availability,
                        "capabilities": raw_caps if isinstance(raw_caps, dict) else None,
                    }
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        pass

    if envelopes:
        return envelopes

    # Backward-compatible fallback for stubs exposing only get_all_capabilities().
    try:
        get_all = getattr(registry, "get_all_capabilities", None)
        legacy_caps = get_all() if callable(get_all) else None
        if isinstance(legacy_caps, dict):
            for provider_name, caps in legacy_caps.items():
                normalized_name = str(provider_name or "").strip()
                if not normalized_name:
                    continue
                envelopes[normalized_name] = {
                    "provider": normalized_name,
                    "availability": "enabled",
                    "capabilities": caps if isinstance(caps, dict) else None,
                }
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
        pass

    return envelopes


def _model_matches_filters(
    model_info: dict[str, Any],
    *,
    type_filters: Optional[set[str]],
    input_filters: Optional[set[str]],
    output_filters: Optional[set[str]],
) -> bool:
    model_type = _infer_model_type(model_info)
    if type_filters and model_type not in type_filters:
        return False

    modalities = model_info.get("modalities")
    input_mods: list[str] = []
    output_mods: list[str] = []
    if isinstance(modalities, dict):
        input_mods = _normalize_modalities(modalities.get("input"))
        output_mods = _normalize_modalities(modalities.get("output"))

    if not input_mods:
        input_mods = ["text"]
    if not output_mods:
        if model_type == "image":
            output_mods = ["image"]
        elif model_type == "embedding":
            output_mods = ["embedding"]
        else:
            output_mods = ["text"]

    if input_filters and not set(input_mods).intersection(input_filters):
        return False
    return not (output_filters and not set(output_mods).intersection(output_filters))

#######################################################################################################################
#
# Endpoints:

@router.get("/llm/providers",
    summary="Get configured LLM providers",
    description="Returns a list of all configured LLM providers with their models from config",
    response_model=dict[str, Any])
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
                except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
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
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS:
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

    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error in get_llm_providers endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve LLM providers: {str(e)}"
        ) from e


@router.get("/llm/models/metadata",
    summary="Get model metadata across providers",
    description=(
        "Returns flattened model metadata for all providers (chat, embeddings, image). "
        "Image backends appear with type=image and modalities output=image."
    ),
    response_model=dict[str, Any])
async def get_models_metadata(
    include_deprecated: bool = False,
    refresh_openrouter: bool = Query(
        False,
        description=(
            "When true, refresh OpenRouter model IDs from OpenRouter /models before"
            " building the catalog response."
        ),
    ),
    model_type: Optional[list[str]] = Query(
        None,
        alias="type",
        description="Optional model type filter (repeatable).",
    ),
    input_modality: Optional[list[str]] = Query(
        None,
        description="Optional input modality filter (repeatable).",
    ),
    output_modality: Optional[list[str]] = Query(
        None,
        description="Optional output modality filter (repeatable).",
    ),
):
    try:
        type_filters = _normalize_filter_values(model_type)
        input_filters = _normalize_filter_values(input_modality)
        output_filters = _normalize_filter_values(output_modality)
        result = await get_configured_providers_async(
            include_deprecated=include_deprecated,
            refresh_openrouter=refresh_openrouter,
        )
        result = apply_llm_provider_overrides_to_listing(result)
        flattened: list[dict[str, Any]] = []
        for provider in result.get('providers', []):
            for mi in provider.get('models_info', []):
                entry = {
                    'provider': provider.get('name'),
                    **mi,
                }
                if not _model_matches_filters(
                    entry,
                    type_filters=type_filters,
                    input_filters=input_filters,
                    output_filters=output_filters,
                ):
                    continue
                flattened.append(entry)
        # Append image generation backends to the catalog
        try:
            image_models = list_image_models_for_catalog()
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as exc:
            logger.warning(f"Failed to list image generation models: {exc}")
            image_models = []
        for entry in image_models:
            if not _model_matches_filters(
                entry,
                type_filters=type_filters,
                input_filters=input_filters,
                output_filters=output_filters,
            ):
                continue
            flattened.append(entry)
        return {
            'models': flattened,
            'total': len(flattened)
        }
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting models metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve model metadata: {str(e)}"
        ) from e

@router.get("/llm/providers/{provider_name}",
    summary="Get specific provider details",
    description="Returns details for a specific LLM provider",
    response_model=dict[str, Any])
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
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting provider details for {provider_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve provider details: {str(e)}"
        ) from e

@router.get("/llm/models",
    summary="Get all available models",
    description=(
        "Returns a flat list of all available models across all providers. "
        "Includes image backends as image/<backend> entries."
    ),
    response_model=list[str])
async def get_all_models(
    include_deprecated: bool = False,
    model_type: Optional[list[str]] = Query(
        None,
        alias="type",
        description="Optional model type filter (repeatable).",
    ),
    input_modality: Optional[list[str]] = Query(
        None,
        description="Optional input modality filter (repeatable).",
    ),
    output_modality: Optional[list[str]] = Query(
        None,
        description="Optional output modality filter (repeatable).",
    ),
):
    """
    Get all available models from all configured providers.

    Returns:
        List of model names with provider prefix
    """
    try:
        type_filters = _normalize_filter_values(model_type)
        input_filters = _normalize_filter_values(input_modality)
        output_filters = _normalize_filter_values(output_modality)
        result = await get_configured_providers_async(include_deprecated=include_deprecated)
        models: list[str] = []
        for provider in result.get('providers', []):
            provider_name = provider.get('name') or "unknown"
            for model in provider.get('models', []):
                entry = {
                    "provider": provider_name,
                    **get_model_metadata(provider_name, model),
                }
                if not _model_matches_filters(
                    entry,
                    type_filters=type_filters,
                    input_filters=input_filters,
                    output_filters=output_filters,
                ):
                    continue
                models.append(f"{provider_name}/{model}")
        # Append image generation backends to the flat list
        try:
            image_models = list_image_models_for_catalog()
        except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as exc:
            logger.warning(f"Failed to list image generation models: {exc}")
            image_models = []
        for entry in image_models:
            if not _model_matches_filters(
                entry,
                type_filters=type_filters,
                input_filters=input_filters,
                output_filters=output_filters,
            ):
                continue
            model_id = entry.get("id") or f"image/{entry.get('name') or ''}"
            if model_id and model_id != "image/":
                models.append(str(model_id))
        logger.info(f"Found {len(models)} total models across all providers")
        return models
    except _LLM_PROVIDERS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error getting all models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve models: {str(e)}"
        ) from e

# End of llm_providers.py
