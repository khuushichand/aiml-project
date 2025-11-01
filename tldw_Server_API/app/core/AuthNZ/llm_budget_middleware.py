from __future__ import annotations

import json
from typing import Callable
import hmac
import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import os
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.virtual_keys import get_key_limits, is_key_over_budget


class LLMBudgetMiddleware(BaseHTTPMiddleware):
    """
    Enforce Virtual Key endpoint allowlists and LLM budgets for API-key authenticated requests.
    Applies only to configured LLM endpoints.
    """

    def __init__(self, app):
        """
        Initialize the LLMBudgetMiddleware and prepare per-request settings handling.
        
        Parameters:
            app: The ASGI application to wrap.
        
        Notes:
            Sets self._settings to None to avoid caching configuration across requests so settings are reloaded for every request (useful for tests and dynamic configuration).
        """
        super().__init__(app)
        # Do not cache settings; fetch fresh each request to honor test resets
        self._settings = None

    def _should_check(self, path: str) -> bool:
        """
        Determine whether LLM budget and virtual-key enforcement should be applied to the given request path.
        
        Parameters:
            path (str): The request URL path to evaluate (e.g., "/api/v1/chat/completions").
        
        Returns:
            `True` if enforcement should be applied to the provided request path, `False` otherwise.
        """
        try:
            settings = get_settings()
            if not getattr(settings, 'VIRTUAL_KEYS_ENABLED', True):
                return False
            if not getattr(settings, 'LLM_BUDGET_ENFORCE', True):
                return False
            endpoints = getattr(settings, 'LLM_BUDGET_ENDPOINTS', None)
            if not isinstance(endpoints, (list, tuple, set)) or len(endpoints) == 0:
                # Fallback to sane defaults if overrides are missing/malformed
                endpoints = [
                    "/api/v1/chat/completions",
                    "/api/v1/embeddings",
                ]
            return any(isinstance(p, str) and path.startswith(p) for p in endpoints)
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
        """
        Enforces virtual API-key LLM allowlists and budget limits for incoming requests to configured LLM endpoints.
        
        If the request targets a monitored LLM endpoint and the resolved API key is a virtual key, this middleware will validate endpoint, provider, and model allowlists and check the key's budget; it forwards the request unchanged when enforcement is not applicable or passes all checks.
        
        Returns:
            Response: An HTTP response. May be a 403 JSONResponse when the key is forbidden, a 402 JSONResponse when the virtual key is over budget, or the downstream handler's Response when the request is allowed or enforcement is skipped.
        """
        path = request.url.path
        if not self._should_check(path):
            return await call_next(request)

        # Optional debug toggle for diagnosis. Enabled automatically in pytest contexts.
        _mw_debug = (
            os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1", "true", "yes", "on"}
            or os.getenv("PYTEST_CURRENT_TEST") is not None
        )
        if _mw_debug:
            try:
                settings = get_settings()
                logger.debug(
                    f"LLM budget dispatch path={path} enforce={getattr(settings,'LLM_BUDGET_ENFORCE', True)} vkeys={getattr(settings,'VIRTUAL_KEYS_ENABLED', True)}"
                )
            except Exception:
                logger.debug(f"LLM budget dispatch path={path} (settings unavailable)")

        # Resolve key_id deterministically from header first (DB hash lookup),
        # then fall back to manager validation if needed. This avoids cases
        # where a stale singleton or init-order peculiarity misses the key.
        key_id = getattr(request.state, 'api_key_id', None)
        if not key_id:
            # Read API key from either X-API-KEY or Authorization: Bearer
            api_key = request.headers.get('X-API-KEY') or request.headers.get('x-api-key')
            if not api_key:
                auth = request.headers.get('authorization') or request.headers.get('Authorization')
                if isinstance(auth, str) and auth.lower().startswith('bearer '):
                    api_key = auth.split(' ', 1)[1].strip()
            if _mw_debug:
                redacted = (api_key[:8] + "…") if api_key else None
                logger.debug(f"LLM budget: resolving api_key via headers -> {bool(api_key)} ({redacted})")

            # 1) Direct DB lookup by HMAC(hash)
            if api_key:
                try:
                    digests: list[str] = []
                    candidates = list(derive_hmac_key_candidates(get_settings()))
                    if _mw_debug:
                        try:
                            logger.debug(f"LLM budget: hash candidates={len(candidates)}")
                        except Exception:
                            pass
                    for key in candidates:
                        digest = hmac.new(key, api_key.encode('utf-8'), hashlib.sha256).hexdigest()
                        if digest not in digests:
                            digests.append(digest)
                    if _mw_debug and digests:
                        logger.debug(f"LLM budget: first digest={digests[0][:12]}… total={len(digests)}")
                    if digests:
                        pool = await get_db_pool()
                        placeholders = ",".join("?" for _ in digests)
                        query = (
                            f"SELECT id, user_id FROM api_keys "
                            f"WHERE key_hash IN ({placeholders}) AND status = ? "
                            f"ORDER BY created_at DESC LIMIT 1"
                        )
                        row = await pool.fetchone(query, (*digests, "active"))
                        if row:
                            key_id = row.get('id') if isinstance(row, dict) else row[0]
                            try:
                                request.state.api_key_id = key_id
                                request.state.user_id = row.get('user_id') if isinstance(row, dict) else row[1]
                            except Exception:
                                pass
                            if _mw_debug:
                                logger.debug(f"LLM budget: resolved key_id via hash lookup: {key_id}")
                        elif _mw_debug:
                            logger.debug("LLM budget: hash lookup found no matching key")
                except Exception as _e_hash:
                    if _mw_debug:
                        logger.debug(f"LLM budget: hash-lookup failed: {_e_hash}")

            # 2) Fallback to manager validation if still unresolved
            if not key_id and api_key:
                try:
                    from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                    mgr = await get_api_key_manager()
                    info = await mgr.validate_api_key(api_key=api_key, ip_address=(request.client.host if request.client else None))
                    if info:
                        key_id = info.get('id')
                        try:
                            request.state.api_key_id = key_id
                            request.state.user_id = info.get('user_id')
                        except Exception:
                            pass
                        if _mw_debug:
                            logger.debug(f"LLM budget: resolved key_id via manager.validate: {key_id}")
                    elif _mw_debug:
                        logger.debug("LLM budget: manager.validate returned no info for api key")
                except Exception as _e_mgr:
                    if _mw_debug:
                        logger.debug(f"LLM budget: manager.validate failed: {_e_mgr}")

            # If still no key_id, treat as JWT/no-key and skip enforcement
            if not key_id:
                if _mw_debug:
                    logger.debug("LLM budget: no api_key_id resolved; skipping budget enforcement")
                return await call_next(request)

        try:
            limits = await get_key_limits(int(key_id))
        except Exception as e:
            logger.debug(f"LLM budget: failed to read key limits: {e}")
            limits = None

        if not limits or not limits.get('is_virtual'):
            if _mw_debug:
                logger.debug(f"LLM budget: key {key_id} not virtual or limits missing; skipping")
            return await call_next(request)

        # Endpoint allowlist enforcement
        try:
            allowed_raw = limits.get('llm_allowed_endpoints')
            if allowed_raw:
                allowed = json.loads(allowed_raw) if isinstance(allowed_raw, str) else allowed_raw
                code = self._endpoint_code(path)
                if _mw_debug:
                    logger.debug(f"LLM budget: endpoint allowlist={allowed} code={code}")
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
            if _mw_debug:
                limits = result.get('limits', {}) or {}
                subset = {
                    'llm_budget_day_tokens': limits.get('llm_budget_day_tokens'),
                    'llm_budget_day_usd': limits.get('llm_budget_day_usd'),
                    'llm_budget_month_tokens': limits.get('llm_budget_month_tokens'),
                    'llm_budget_month_usd': limits.get('llm_budget_month_usd'),
                }
                logger.debug(
                    f"LLM budget: over_budget={result.get('over')} reasons={result.get('reasons')} "
                    f"day={result.get('day')} month={result.get('month')} limits={subset}"
                )
            if result.get('over'):
                return JSONResponse({
                    "error": "budget_exceeded",
                    "message": "Virtual key budget exceeded",
                    "details": result,
                }, status_code=402)
        except Exception as e:
            logger.debug(f"LLM budget: budget check skipped/failed: {e}")

        return await call_next(request)