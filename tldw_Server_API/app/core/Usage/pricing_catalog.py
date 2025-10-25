"""
pricing_catalog.py

Centralized pricing lookups for LLM usage. Provides default per-1K token
rates and supports overrides via environment variable PRICING_OVERRIDES
(JSON) or a config file at tldw_Server_API/Config_Files/model_pricing.json.

Notes
- Rates are USD per 1000 tokens.
- Separate input (prompt) and output (completion) rates when available.
- Unknown models fall back to provider-level defaults and are marked
  as estimated by callers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple, Optional

from loguru import logger


def _lower_keys(d: Dict) -> Dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[str(k).lower()] = _lower_keys(v)
        else:
            out[str(k).lower()] = v
    return out


# Baseline defaults (USD per 1K tokens). These are indicative and can be
# refined over time. Kept conservative to avoid under-estimating.
DEFAULT_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        # Legacy generalizations
        "gpt-4": {"prompt": 30e-3, "completion": 60e-3},
        "gpt-4-turbo": {"prompt": 10e-3, "completion": 30e-3},
        "gpt-3.5-turbo": {"prompt": 1e-3, "completion": 2e-3},
        # Newer families (approximate)
        "gpt-4o": {"prompt": 5e-3, "completion": 15e-3},
        "gpt-4o-mini": {"prompt": 1e-3, "completion": 2e-3},
        "gpt-4.1": {"prompt": 10e-3, "completion": 30e-3},
        "o3-mini": {"prompt": 1e-3, "completion": 2e-3},
        # Embeddings
        "text-embedding-3-small": {"prompt": 0.02e-3, "completion": 0.02e-3},
        "text-embedding-3-large": {"prompt": 0.13e-3, "completion": 0.13e-3},
        "text-embedding-ada-002": {"prompt": 0.1e-3, "completion": 0.1e-3},
    },
    "anthropic": {
        "claude-3-opus": {"prompt": 15e-3, "completion": 75e-3},
        "claude-3-sonnet": {"prompt": 3e-3, "completion": 15e-3},
        "claude-3-haiku": {"prompt": 0.25e-3, "completion": 1.25e-3},
        "claude-2.1": {"prompt": 8e-3, "completion": 24e-3},
    },
    "groq": {
        "llama2-70b": {"prompt": 0.7e-3, "completion": 0.7e-3},
        "mixtral-8x7b": {"prompt": 0.6e-3, "completion": 0.6e-3},
        "llama3-70b": {"prompt": 0.8e-3, "completion": 0.8e-3},
        "llama3-8b": {"prompt": 0.1e-3, "completion": 0.1e-3},
    },
    "mistral": {
        "mistral-tiny": {"prompt": 0.25e-3, "completion": 0.25e-3},
        "mistral-small": {"prompt": 0.6e-3, "completion": 0.6e-3},
        "mistral-medium": {"prompt": 2.7e-3, "completion": 2.7e-3},
        "mistral-large": {"prompt": 8e-3, "completion": 8e-3},
    },
    "deepseek": {
        "deepseek-coder": {"prompt": 0.1e-3, "completion": 0.1e-3},
        "deepseek-chat": {"prompt": 0.2e-3, "completion": 0.2e-3},
    },
    # Additional providers (approximate defaults; override via config for accuracy)
    "google": {
        "gemini-1.5-pro": {"prompt": 2e-3, "completion": 5e-3},
        "gemini-1.5-flash": {"prompt": 0.5e-3, "completion": 1e-3},
        "text-embedding-004": {"prompt": 0.05e-3, "completion": 0.05e-3},
    },
    "cohere": {
        "command": {"prompt": 0.5e-3, "completion": 1.2e-3},
        "command-r": {"prompt": 1.5e-3, "completion": 3e-3},
        "embed-english-v3.0": {"prompt": 0.05e-3, "completion": 0.05e-3},
        "embed-multilingual-v3.0": {"prompt": 0.08e-3, "completion": 0.08e-3},
    },
    "qwen": {
        "qwen2.5-7b": {"prompt": 0.2e-3, "completion": 0.2e-3},
        "qwen2.5-72b": {"prompt": 0.5e-3, "completion": 0.5e-3},
    },
    "openrouter": {
        "gpt-4o": {"prompt": 5e-3, "completion": 15e-3},
        "meta-llama/llama-3-70b": {"prompt": 0.8e-3, "completion": 0.8e-3},
    },
    "xai": {
        "grok-2": {"prompt": 3e-3, "completion": 6e-3},
    },
    "huggingface": {
        # Default to small sentinel for hosted models; often free/varied
        "default": {"prompt": 0.05e-3, "completion": 0.05e-3}
    },
}


class PricingCatalog:
    """Pricing lookup with optional overrides."""

    def __init__(self) -> None:
        self._catalog = _lower_keys(DEFAULT_PRICING)
        self._load_overrides()

    def _load_overrides(self) -> None:
        # Env JSON overrides
        raw = os.getenv("PRICING_OVERRIDES")
        if raw:
            try:
                data = json.loads(raw)
                self._merge_overrides(_lower_keys(data))
            except Exception as e:
                logger.warning(f"Failed to parse PRICING_OVERRIDES: {e}")

        # File overrides
        try:
            # Resolve to repo_root/tldw_Server_API/Config_Files/model_pricing.json
            # __file__ = .../tldw_Server_API/app/core/Usage/pricing_catalog.py
            # parents[3] = .../tldw_Server_API
            cfg_path = Path(__file__).resolve().parents[3] / "Config_Files" / "model_pricing.json"
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text())
                self._merge_overrides(_lower_keys(data))
        except Exception as e:
            logger.warning(f"Failed to load pricing overrides file: {e}")

    def _merge_overrides(self, overrides: Dict) -> None:
        for provider, models in overrides.items():
            if not isinstance(models, dict):
                continue
            base = self._catalog.setdefault(provider, {})
            for model, rates in models.items():
                if not isinstance(rates, dict):
                    continue
                pr = float(rates.get("prompt", rates.get("in", 0.0)) or 0.0)
                cr = float(rates.get("completion", rates.get("out", 0.0)) or 0.0)
                base[model] = {"prompt": pr, "completion": cr}

    def get_rates(self, provider: str, model: str) -> Tuple[float, float, bool]:
        """
        Return (prompt_per_1k, completion_per_1k, estimated) for provider/model.
        If exact model not found, try partial matches; otherwise fall back to a
        small sentinel rate (estimated=True).
        """
        prov = (provider or "").lower()
        mdl = (model or "").lower()
        prov_map = self._catalog.get(prov, {})

        # Exact match
        if mdl in prov_map:
            r = prov_map[mdl]
            return float(r.get("prompt", 0.0)), float(r.get("completion", 0.0)), False

        # Partial match (substring)
        for mk, r in prov_map.items():
            if mk in mdl or mdl in mk:
                return float(r.get("prompt", 0.0)), float(r.get("completion", 0.0)), True

        # Provider baseline fallback (conservative): avoid under-estimating unknown models
        # Defaults approximate a mid/high rate similar to GPT-4o/4.1 tiers
        return 0.01, 0.03, True


_DEFAULT_CATALOG = PricingCatalog()


def get_pricing_catalog() -> PricingCatalog:
    return _DEFAULT_CATALOG


def reset_pricing_catalog() -> PricingCatalog:
    """Reset and return the global pricing catalog instance.

    Useful when environment variables (e.g., PRICING_OVERRIDES) or the
    model pricing file change at runtime (tests, admin ops).
    """
    global _DEFAULT_CATALOG
    _DEFAULT_CATALOG = PricingCatalog()
    return _DEFAULT_CATALOG
