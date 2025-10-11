from __future__ import annotations

import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.virtual_keys import get_key_limits, is_key_over_budget


class LLMBudgetMiddleware(BaseHTTPMiddleware):
    """
    Enforce Virtual Key endpoint allowlists and LLM budgets for API-key authenticated requests.
    Applies only to configured LLM endpoints.
    """

    def __init__(self, app):
        super().__init__(app)
        self._settings = get_settings()

    def _should_check(self, path: str) -> bool:
        try:
            if not getattr(self._settings, 'VIRTUAL_KEYS_ENABLED', True):
                return False
            if not getattr(self._settings, 'LLM_BUDGET_ENFORCE', True):
                return False
            endpoints = getattr(self._settings, 'LLM_BUDGET_ENDPOINTS', []) or []
            return any(path.startswith(p) for p in endpoints)
        except Exception:
            return False

    @staticmethod
    def _endpoint_code(path: str) -> str:
        # simple map for v1
        if path.startswith('/api/v1/chat/completions'):
            return 'chat.completions'
        if path.startswith('/api/v1/embeddings'):
            return 'embeddings'
        return path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not self._should_check(path):
            return await call_next(request)

        key_id = getattr(request.state, 'api_key_id', None)
        if not key_id:
            # JWT or single-user: not a virtual key context
            return await call_next(request)

        try:
            limits = await get_key_limits(int(key_id))
        except Exception as e:
            logger.debug(f"LLM budget: failed to read key limits: {e}")
            limits = None

        if not limits or not limits.get('is_virtual'):
            return await call_next(request)

        # Endpoint allowlist enforcement
        try:
            allowed_raw = limits.get('llm_allowed_endpoints')
            if allowed_raw:
                allowed = json.loads(allowed_raw) if isinstance(allowed_raw, str) else allowed_raw
                code = self._endpoint_code(path)
                if isinstance(allowed, list) and code not in allowed:
                    return JSONResponse({
                        "error": "forbidden",
                        "message": f"Endpoint '{code}' not allowed for this key"
                    }, status_code=403)
        except Exception as e:
            logger.debug(f"LLM budget: allowlist check skipped/failed: {e}")

        # Optional provider/model allowlist enforcement
        try:
            allowed_models_raw = limits.get('llm_allowed_models')
            allowed_providers_raw = limits.get('llm_allowed_providers')
            allowed_models = None
            allowed_providers = None
            if allowed_models_raw:
                allowed_models = json.loads(allowed_models_raw) if isinstance(allowed_models_raw, str) else allowed_models_raw
            if allowed_providers_raw:
                allowed_providers = json.loads(allowed_providers_raw) if isinstance(allowed_providers_raw, str) else allowed_providers_raw

            # Provider by explicit header, if present
            if allowed_providers:
                provider = request.headers.get('X-LLM-Provider')
                if provider and provider not in allowed_providers:
                    return JSONResponse({
                        "error": "forbidden",
                        "message": f"Provider '{provider}' not allowed for this key"
                    }, status_code=403)

            # Model from JSON body when parseable and POST
            if allowed_models and request.method in {"POST", "PUT", "PATCH"}:
                ctype = request.headers.get('content-type', '')
                if 'application/json' in ctype:
                    try:
                        body_bytes = await request.body()
                        if body_bytes:
                            data = json.loads(body_bytes.decode('utf-8'))
                            model = data.get('model')
                            if model and model not in allowed_models:
                                return JSONResponse({
                                    "error": "forbidden",
                                    "message": f"Model '{model}' not allowed for this key"
                                }, status_code=403)
                    except Exception as _e:
                        # If body cannot be parsed, skip enforcement rather than break requests
                        logger.debug(f"LLM budget: model allowlist parse skipped/failed: {_e}")
        except Exception as e:
            logger.debug(f"LLM budget: provider/model allowlist skipped/failed: {e}")

        # Budget enforcement
        try:
            result = await is_key_over_budget(int(key_id))
            if result.get('over'):
                return JSONResponse({
                    "error": "budget_exceeded",
                    "message": "Virtual key budget exceeded",
                    "details": result,
                }, status_code=402)
        except Exception as e:
            logger.debug(f"LLM budget: budget check skipped/failed: {e}")

        return await call_next(request)
