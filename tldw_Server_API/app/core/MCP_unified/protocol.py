"""
MCP Protocol implementation for unified module

Implements JSON-RPC 2.0 with enhanced error handling and request routing.
"""

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Literal, Optional, Union

from pydantic import BaseModel, Field

try:
    from pydantic import field_validator, model_validator  # v2
except Exception:  # Fallback for v1
    from pydantic import validator as field_validator  # type: ignore
    try:
        from pydantic import root_validator as model_validator  # type: ignore
    except Exception:
        model_validator = None  # type: ignore
import inspect
import re
import time
from collections import OrderedDict

from loguru import logger

from tldw_Server_API.app.core.Infrastructure.redis_factory import create_async_redis_client
from tldw_Server_API.app.core.Metrics.telemetry import get_telemetry_manager

from .auth.authnz_rbac import Action, Resource, get_rbac_policy
from .auth.rate_limiter import RateLimitExceeded, get_rate_limiter
from .config import get_config
from .modules.base import BaseModule
from .modules.registry import get_module_registry
from .monitoring.metrics import get_metrics_collector

try:  # pragma: no cover - optional dependency
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis not installed
    class RedisError(Exception):
        """Fallback RedisError when redis-py is unavailable."""
        pass


# Redis exceptions can include connection URLs and credentials; keep logs sanitized.
def _redact_redis_error(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: Redis connection error - details redacted"


# JSON-RPC 2.0 Error Codes
class ErrorCode(IntEnum):
    """Standard JSON-RPC 2.0 error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Custom error codes (must be -32000 to -32099)
    AUTHENTICATION_ERROR = -32000
    AUTHORIZATION_ERROR = -32001
    RATE_LIMIT_ERROR = -32002
    MODULE_ERROR = -32003
    TIMEOUT_ERROR = -32004


class InvalidParamsException(Exception):
    """Raised when tool parameters fail validation or validators are missing for write tools."""
    pass


class MCPRequest(BaseModel):
    """MCP request following JSON-RPC 2.0 specification"""
    jsonrpc: Literal["2.0"] = Field(default="2.0")
    method: str = Field(..., min_length=1, max_length=100)
    params: Optional[dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, v):
        """Validate method name"""
        # Prevent potential injection attacks
        if any(char in v for char in ["'", '"', ';', '--', '/*', '*/']):
            raise ValueError("Invalid characters in method name")
        return v

    @field_validator("params")
    @classmethod
    def validate_params(cls, v):
        """Validate and sanitize parameters"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Params must be a dictionary")
        return v


class MCPError(BaseModel):
    """MCP error structure"""
    code: int
    message: str
    data: Optional[Any] = None


class MCPResponse(BaseModel):
    """MCP response following JSON-RPC 2.0 specification"""
    jsonrpc: Literal["2.0"] = Field(default="2.0")
    result: Optional[Any] = None
    error: Optional[MCPError] = None
    id: Optional[Union[str, int]] = None

    if model_validator is not None:
        @model_validator(mode="after")
        def _validate_error_result(self):
            """Ensure either result or error is set, not both"""
            if self.error is not None and self.result is not None:
                raise ValueError("Response cannot have both result and error")
            return self


class RequestContext:
    """Context for request processing"""
    def __init__(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.client_id = client_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.start_time = datetime.now(timezone.utc)
        # Derive per-user db paths (read-only) if possible
        self.db_paths: dict[str, str] = {}
        try:
            if self.user_id is not None:
                # Attempt to parse an integer user id (expected by DatabasePaths)
                uid_int = int(str(self.user_id))
                from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
                paths = DatabasePaths.get_all_user_db_paths(uid_int)
                # Convert Paths to strings for downstream use
                self.db_paths = {k: str(v) for k, v in paths.items()}
        except Exception as _e:
            # Non-fatal: leave db_paths empty when user id is not numeric or any failure occurs
            pass
        # Build a bound logger for this request
        self.logger = logger.bind(
            request_id=request_id,
            user_id=user_id,
            client_id=client_id,
            session_id=session_id,
        )


class IdempotencyManager:
    """Idempotency manager with Redis backing and local lock fallback."""

    def __init__(self) -> None:
        self._local_cache: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()
        self._local_locks: dict[str, asyncio.Lock] = {}
        self._local_guard = asyncio.Lock()
        self._redis_client: Any | None = None
        self._redis_ready = False
        self._redis_attempted = False
        self._redis_guard = asyncio.Lock()

    async def _ensure_redis(self) -> bool:
        if self._redis_attempted:
            return self._redis_ready
        async with self._redis_guard:
            if self._redis_attempted:
                return self._redis_ready
            self._redis_attempted = True
            cfg = get_config()
            params = cfg.get_redis_connection_params()
            if not params:
                self._redis_ready = False
                return False
            url = params.pop("url", None)
            try:
                self._redis_client = await create_async_redis_client(
                    preferred_url=url,
                    decode_responses=True,
                    fallback_to_fake=False,
                    context="mcp_idempotency",
                    redis_kwargs=params,
                )
                self._redis_ready = True
            except Exception as exc:
                logger.warning(
                    "MCP idempotency Redis unavailable; falling back to local locks. Error: {}",
                    _redact_redis_error(exc),
                )
                self._redis_client = None
                self._redis_ready = False
            return self._redis_ready

    def _local_get(self, cache_key: str, ttl: int) -> Optional[dict[str, Any]]:
        item = self._local_cache.get(cache_key)
        if not item:
            return None
        ts, payload = item
        if time.time() - ts > ttl:
            try:
                del self._local_cache[cache_key]
            except Exception:
                pass
            return None
        try:
            self._local_cache.move_to_end(cache_key)
        except Exception:
            pass
        return payload

    def _local_put(self, cache_key: str, payload: dict[str, Any], ttl: int, max_size: int) -> None:
        now = time.time()
        self._local_cache[cache_key] = (now, payload)
        try:
            self._local_cache.move_to_end(cache_key)
        except Exception:
            pass
        # Evict expired entries opportunistically
        expired = [k for k, (ts, _) in self._local_cache.items() if now - ts > ttl]
        for k in expired:
            try:
                del self._local_cache[k]
            except Exception:
                pass
        # Enforce max size (LRU)
        while len(self._local_cache) > max_size:
            try:
                self._local_cache.popitem(last=False)
            except Exception:
                break

    async def _get_local_lock(self, cache_key: str) -> asyncio.Lock:
        async with self._local_guard:
            lock = self._local_locks.get(cache_key)
            if lock is None:
                lock = asyncio.Lock()
                self._local_locks[cache_key] = lock
            return lock

    async def _redis_get(self, client: Any, key: str) -> Optional[dict[str, Any]]:
        raw = await client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def _redis_set(self, client: Any, key: str, payload: dict[str, Any], ttl: int) -> None:
        data = json.dumps(payload, separators=(",", ":"), default=str)
        await client.set(key, data, ex=ttl)

    async def _redis_try_acquire(self, client: Any, key: str, token: str, ttl: int) -> bool:
        resp = await client.set(key, token, nx=True, ex=ttl)
        return bool(resp)

    async def _redis_release(self, client: Any, key: str, token: str) -> None:
        lua_script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) end"
        )
        try:
            await client.eval(lua_script, 1, key, token)
        except Exception:
            pass

    async def _run_local(
        self,
        cache_key: str,
        execute_fn: Callable[[], Any],
        *,
        ttl: int,
        max_size: int,
    ) -> tuple[dict[str, Any], bool]:
        async with self._local_guard:
            cached = self._local_get(cache_key, ttl)
        if cached is not None:
            return cached, True

        lock = await self._get_local_lock(cache_key)
        async with lock:
            async with self._local_guard:
                cached = self._local_get(cache_key, ttl)
            if cached is not None:
                return cached, True
            result = await execute_fn()
            async with self._local_guard:
                self._local_put(cache_key, result, ttl, max_size)
            return result, False

    async def _run_redis(
        self,
        cache_key: str,
        execute_fn: Callable[[], Any],
        *,
        ttl: int,
        lock_ttl: int,
    ) -> tuple[dict[str, Any], bool]:
        client = self._redis_client
        if client is None:
            raise RuntimeError("Redis client not initialized")
        result_key = f"mcp:idemp:result:{cache_key}"
        lock_key = f"mcp:idemp:lock:{cache_key}"
        cached = await self._redis_get(client, result_key)
        if cached is not None:
            return cached, True

        poll_interval = 0.2
        while True:
            token = secrets.token_urlsafe(16)
            acquired = await self._redis_try_acquire(client, lock_key, token, lock_ttl)
            if acquired:
                try:
                    result = await execute_fn()
                    await self._redis_set(client, result_key, result, ttl)
                finally:
                    await self._redis_release(client, lock_key, token)
                return result, False

            cached = await self._redis_get(client, result_key)
            if cached is not None:
                return cached, True
            await asyncio.sleep(poll_interval)

    async def run(
        self,
        cache_key: str,
        execute_fn: Callable[[], Any],
        *,
        ttl: int,
        max_size: int,
        lock_ttl: int,
    ) -> tuple[dict[str, Any], bool]:
        if await self._ensure_redis():
            try:
                return await self._run_redis(
                    cache_key,
                    execute_fn,
                    ttl=ttl,
                    lock_ttl=lock_ttl,
                )
            except RedisError as exc:
                logger.warning(
                    "MCP idempotency Redis path failed; falling back to local locks. Error: {}",
                    _redact_redis_error(exc),
                )
                self._redis_ready = False
        return await self._run_local(cache_key, execute_fn, ttl=ttl, max_size=max_size)


class MCPProtocol:
    """
    MCP Protocol handler with enhanced security and error handling.

    Features:
    - JSON-RPC 2.0 compliance
    - Request validation and sanitization
    - Authentication and authorization
    - Rate limiting
    - Request routing
    - Error handling with proper codes
    - Request tracing
    """

    def __init__(self):
        self.module_registry = get_module_registry()
        self.rbac_policy = get_rbac_policy()
        self.rate_limiter = get_rate_limiter()
        self.protocol_version = "2024-11-05"
        self.metrics = get_metrics_collector()
        self.telemetry = get_telemetry_manager()
        # Strict tool name validation regex
        self._tool_name_re = re.compile(r'^[A-Za-z0-9_.:-]{1,100}$')
        # Idempotency manager for write-capable tools
        self._idempotency = IdempotencyManager()

        # Method handlers
        self.handlers: dict[str, Callable] = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "modules/list": self._handle_modules_list,
            "modules/health": self._handle_modules_health,
        }

        logger.info("MCP Protocol handler initialized")

    async def _rbac_check(self, user_id: Optional[str], resource: Resource, action: Action, resource_id: Optional[str] = None) -> bool:
        if not user_id:
            return False
        fn = getattr(self.rbac_policy, "check_permission", None)
        if not fn:
            return False
        try:
            if inspect.iscoroutinefunction(fn):
                return await fn(user_id, resource, action, resource_id)
            return fn(user_id, resource, action, resource_id)
        except Exception:
            return False

    def _scoped_permissions(self, context: RequestContext) -> list[str]:
        metadata = getattr(context, "metadata", {})
        if not isinstance(metadata, dict):
            return []
        raw = metadata.get("permissions") or []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(item) for item in raw if isinstance(item, str)]
        return []

    def _mcp_scopes(self, context: RequestContext) -> list[str]:
        scopes: list[str] = []
        for scope in self._scoped_permissions(context):
            try:
                if scope.lower().startswith("mcp:"):
                    scopes.append(scope)
            except Exception:
                continue
        return scopes

    def _api_key_scopes(self, context: RequestContext) -> Optional[set[str]]:
        """Return normalized API key scopes when present on the request context."""
        metadata = getattr(context, "metadata", {})
        if not isinstance(metadata, dict):
            return None
        raw = metadata.get("api_key_scopes")
        if raw is None:
            return None
        try:
            from tldw_Server_API.app.core.AuthNZ.api_key_manager import normalize_scope
        except Exception:
            normalize_scope = None  # type: ignore

        if normalize_scope is not None:
            try:
                return set(normalize_scope(raw))
            except Exception:
                pass

        if isinstance(raw, str):
            return {raw.strip().lower()} if raw.strip() else set()
        if isinstance(raw, list):
            return {str(item).strip().lower() for item in raw if str(item).strip()}
        return set()

    def _api_key_scope_level(self, context: RequestContext) -> Optional[str]:
        scopes = self._api_key_scopes(context)
        if not scopes:
            return None
        if "admin" in scopes or "service" in scopes:
            return "admin"
        if "write" in scopes:
            return "write"
        if "read" in scopes:
            return "read"
        return None

    def _api_key_allows(self, context: RequestContext, *, is_write: Optional[bool] = None) -> bool:
        """Gate MCP operations by API key scopes when present."""
        level = self._api_key_scope_level(context)
        if level is None:
            return True
        if level == "admin":
            return True
        if is_write is None:
            return level in {"read", "write"}
        if is_write:
            return level == "write"
        return level in {"read", "write"}

    def _scope_matches(self, scope: str, resource_kind: str, identifier: Optional[str]) -> bool:
        scope = scope.strip().lower()
        if not scope.startswith("mcp:"):
            return False
        parts = scope.split(":")
        if len(parts) == 2 and parts[1] == "*":
            return True
        if len(parts) < 3:
            return False
        kind = parts[1]
        value = ":".join(parts[2:])
        if kind == "*":
            return True
        if kind != resource_kind:
            return False
        if value in {"*", ""}:
            return True
        if identifier is None:
            return False
        return value == identifier.lower()

    def _scope_allows(self, context: RequestContext, resource_kind: str, identifier: Optional[str]) -> bool:
        scopes = self._mcp_scopes(context)
        if not scopes:
            return True
        identifier_norm = identifier.lower() if isinstance(identifier, str) else None
        if identifier_norm is None:
            # Allow listing/browsing when any scoped permission exists for this resource kind.
            for scope in scopes:
                try:
                    parts = scope.strip().lower().split(":")
                except Exception:
                    continue
                if len(parts) >= 2 and parts[0] == "mcp":
                    if parts[1] == "*" or parts[1] == resource_kind:
                        return True
        for scope in scopes:
            if self._scope_matches(scope, resource_kind, identifier_norm):
                return True
        return False

    async def _has_module_permission(self, context: RequestContext, module_id: Optional[str]) -> bool:
        module_id_norm = module_id or ""
        if not await self._rbac_check(context.user_id, Resource.MODULE, Action.READ, module_id_norm):
            return False
        return self._scope_allows(context, Resource.MODULE.value, module_id_norm or None)

    async def _has_tool_permission(self, context: RequestContext, tool_name: str, *, is_write: Optional[bool] = None) -> bool:
        if not await self._rbac_check(context.user_id, Resource.TOOL, Action.EXECUTE, tool_name):
            return False
        if not self._scope_allows(context, Resource.TOOL.value, tool_name):
            return False
        return self._api_key_allows(context, is_write=is_write)

    async def _has_resource_permission(self, context: RequestContext, resource_uri: str, module_id: Optional[str]) -> bool:
        if await self._rbac_check(context.user_id, Resource.RESOURCE, Action.READ, resource_uri):
            return self._scope_allows(context, Resource.RESOURCE.value, resource_uri)
        if await self._has_module_permission(context, module_id):
            return self._scope_allows(context, Resource.RESOURCE.value, resource_uri)
        return False

    async def _has_prompt_permission(self, context: RequestContext, prompt_name: str, module_id: Optional[str]) -> bool:
        if await self._rbac_check(context.user_id, Resource.PROMPT, Action.READ, prompt_name):
            return self._scope_allows(context, Resource.PROMPT.value, prompt_name)
        if await self._has_module_permission(context, module_id):
            return self._scope_allows(context, Resource.PROMPT.value, prompt_name)
        return False

    @staticmethod
    def _hash_arguments(arguments: dict[str, Any]) -> Optional[str]:
        try:
            payload = json.dumps(arguments or {}, sort_keys=True, default=str).encode("utf-8")
            import hashlib
            return hashlib.sha256(payload).hexdigest()
        except Exception:
            return None

    def _audit_tool_event(
        self,
        context: RequestContext,
        tool_name: str,
        module_id: Optional[str],
        status: str,
        duration_ms: float,
        arguments_hash: Optional[str],
        error: Optional[Exception] = None,
    ) -> None:
        try:
            log = logger.bind(
                audit=True,
                request_id=context.request_id,
                user_id=context.user_id,
                client_id=context.client_id,
                session_id=context.session_id,
                tool=tool_name,
                module=module_id or "unknown",
                duration_ms=round(duration_ms, 2),
                arguments_hash=arguments_hash,
                status=status,
            )
            if error:
                log.error(f"MCP tool execution failed", error_type=error.__class__.__name__, error_message=str(error)[:200])
            else:
                log.info("MCP tool executed")
        except Exception:
            pass

    async def process_request(
        self,
        request: Union[dict[str, Any], list[dict[str, Any]], MCPRequest],
        context: Optional[RequestContext] = None
    ) -> Union[MCPResponse, list[MCPResponse], None]:
        """
        Process an MCP request and return response.

        Args:
            request: MCP request (dict or MCPRequest object)
            context: Request context with user/session info

        Returns:
            MCP response
        """
        # Support batch requests
        if isinstance(request, list):
            if not request:
                return self._error_response(
                    ErrorCode.INVALID_REQUEST,
                    "Invalid request: empty batch",
                    None,
                )
            responses: list[MCPResponse] = []
            for item in request:
                try:
                    resp = await self.process_request(item, context)
                    # Notifications return None; do not include in batch response
                    if isinstance(resp, MCPResponse):
                        responses.append(resp)
                except Exception as e:
                    # If parsing fails at top-level, try to include an error response for that item
                    try:
                        req_id = item.get("id") if isinstance(item, dict) else None
                    except Exception:
                        req_id = None
                    responses.append(self._error_response(ErrorCode.INVALID_REQUEST, str(e), req_id))
            # Per JSON-RPC, if the batch is empty or only notifications, return no response
            return responses if responses else None

        # Parse single request if dict
        if isinstance(request, dict):
            try:
                request = MCPRequest(**request)
            except Exception as e:
                req_id = request.get("id") if isinstance(request, dict) else None
                return self._error_response(
                    ErrorCode.INVALID_REQUEST,
                    f"Invalid request format: {str(e)}",
                    req_id
                )

        # Create context if not provided
        if context is None:
            context = RequestContext(
                request_id=str(uuid.uuid4()),
                client_id="unknown"
            )

        # Bound logger for this request
        log = context.logger
        # Log request (without params) and ensure secrets get redacted in any error paths
        log.info(
            f"MCP request: method={request.method}, user={context.user_id}, client={context.client_id}",
            extra={"audit": True}
        )

        start_ts = time.time()
        try:
            # Check rate limit (skip when ingress RG already enforced)
            skip_rate_limit = False
            try:
                if context.metadata and context.metadata.get("rg_ingress_enforced"):
                    skip_rate_limit = True
            except Exception as exc:
                log.debug(
                    "Failed to read rg_ingress_enforced from metadata; rate limit will be enforced",
                    error=str(exc),
                )
                skip_rate_limit = False
            if not skip_rate_limit:
                if context.user_id:
                    await self.rate_limiter.check_rate_limit(f"user:{context.user_id}")
                elif context.client_id:
                    await self.rate_limiter.check_rate_limit(f"client:{context.client_id}")

            # Validate JSON-RPC version
            if request.jsonrpc != "2.0":
                return self._error_response(
                    ErrorCode.INVALID_REQUEST,
                    "Invalid JSON-RPC version",
                    request.id
                )

            # If this is a tools/call, validate tool name early (before RBAC)
            try:
                if request.method == "tools/call":
                    _p = request.params or {}
                    _name = _p.get("name") if isinstance(_p, dict) else None
                    if not _name:
                        return self._error_response(
                            ErrorCode.INVALID_PARAMS,
                            "Tool name is required",
                            request.id,
                        )
                    if not isinstance(_name, str):
                        # Non-string name → invalid params
                        return self._error_response(
                            ErrorCode.INVALID_PARAMS,
                            "Invalid tool name",
                            request.id,
                        )
                    if not self._tool_name_re.match(_name):
                        # Regex violation treated as internal error per legacy expectation
                        return self._error_response(
                            ErrorCode.INTERNAL_ERROR,
                            "Invalid tool name",
                            request.id,
                        )
            except Exception:
                # Uniformly surface as INVALID_PARAMS for caller clarity
                return self._error_response(ErrorCode.INVALID_PARAMS, "Invalid tool name", request.id)

            # Find handler
            handler = self.handlers.get(request.method)
            if not handler:
                return self._error_response(
                    ErrorCode.METHOD_NOT_FOUND,
                    f"Method not found: {request.method}",
                    request.id
                )

            # Check authorization
            if not await self._check_authorization(request, context):
                # Provide a short hint for common denied operations
                hint_data = None
                try:
                    if request.method == "tools/call":
                        tool = (request.params or {}).get("name")
                        if tool:
                            hint_data = {
                                "hint": (
                                    f"Permission denied. Ask an admin to grant tools.execute:{tool} "
                                    f"or tools.execute:* to your role (Admin → Access Control)."
                                )
                            }
                except Exception:
                    hint_data = None

                return self._error_response(
                    ErrorCode.AUTHORIZATION_ERROR,
                    "Insufficient permissions",
                    request.id,
                    data=hint_data
                )

            # Execute handler within OTEL span
            start_exec = time.time()
            with self.telemetry.trace_context(
                "mcp.request",
                {
                    "mcp.method": request.method,
                    "mcp.request_id": str(request.id) if request.id is not None else "notification",
                    "mcp.user_id": str(context.user_id or ""),
                    "mcp.client_id": str(context.client_id or ""),
                    "mcp.session_id": str(context.session_id or ""),
                },
            ) as span:
                try:
                    result = await handler(request.params or {}, context)
                    span.set_attribute("mcp.status", "success")
                except Exception as _span_e:
                    span.set_attribute("mcp.status", "failure")
                    span.set_attribute("mcp.error_type", _span_e.__class__.__name__)
                    span.set_attribute("mcp.error_message", str(_span_e)[:200])
                    raise
                finally:
                    span.set_attribute("mcp.duration_ms", max(0.0, (time.time() - start_exec) * 1000.0))

            # Log success and record metrics
            elapsed = (datetime.now(timezone.utc) - context.start_time).total_seconds()
            log.info(
                f"MCP request completed: method={request.method}, "
                f"elapsed={elapsed:.3f}s",
                extra={"audit": True}
            )
            try:
                self.metrics.record_request(method=request.method, duration=elapsed, status="success")
            except Exception:
                pass

            # Notification: do not return a response
            if request.id is None:
                return None
            # Return success response for standard requests
            return MCPResponse(result=result, id=request.id)

        except RateLimitExceeded as rl:
            # Record rate limit hit and re-raise for caller-specific mapping
            try:
                key_type = "user" if context.user_id else ("client" if context.client_id else "anonymous")
                self.metrics.record_rate_limit_hit(key_type=key_type)
            except Exception:
                pass
            raise
        except InvalidParamsException as ive:
            # Notification: do not return a response
            if isinstance(request, MCPRequest) and request.id is None:
                return None
            return self._error_response(ErrorCode.INVALID_PARAMS, str(ive), request.id if isinstance(request, MCPRequest) else None)
        except PermissionError as perr:
            # Map policy/permission errors to AUTHORIZATION_ERROR
            if isinstance(request, MCPRequest) and request.id is None:
                return None
            # Redact any secrets in message (defensive)
            msg = self._mask_secrets(str(perr))
            return self._error_response(ErrorCode.AUTHORIZATION_ERROR, msg, request.id if isinstance(request, MCPRequest) else None)
        except Exception as e:
            # Log error
            log.error(
                f"MCP request failed: method={request.method}, error={self._mask_secrets(str(e))}",
                extra={"audit": True}
            )
            try:
                elapsed = max(0.0, time.time() - start_ts)
                self.metrics.record_request(method=request.method, duration=elapsed, status="failure")
            except Exception:
                pass

            # Notification: do not return a response
            if isinstance(request, MCPRequest) and request.id is None:
                return None
            # Return error response with reduced leakage when not in debug mode
            try:
                cfg = get_config()
                msg = self._mask_secrets(str(e)) if getattr(cfg, "debug_mode", False) else "Internal error"
            except Exception:
                msg = "Internal error"
            return self._error_response(
                ErrorCode.INTERNAL_ERROR,
                msg,
                request.id if isinstance(request, MCPRequest) else None,
            )

    def _mask_secrets(self, text: str) -> str:
        """Best-effort masking of bearer/API keys in strings."""
        try:
            if not text:
                return text
            import re as _re
            # Mask Bearer tokens
            text = _re.sub(r"(Bearer)\s+[A-Za-z0-9._\-~+/=]+", r"\1 ****", text, flags=_re.IGNORECASE)
            # Mask common token fields
            patterns = [
                r"(api[_-]?key)\s*[:=]\s*([^\s,;]+)",
                r"(token)\s*[:=]\s*([^\s,;]+)",
                r"(access[_-]?token)\s*[:=]\s*([^\s,;]+)",
                r"(refresh[_-]?token)\s*[:=]\s*([^\s,;]+)",
            ]
            for p in patterns:
                text = _re.sub(p, lambda m: f"{m.group(1)}=****", text, flags=_re.IGNORECASE)
            return text
        except Exception:
            return text

    def _error_response(
        self,
        code: ErrorCode,
        message: str,
        request_id: Optional[Union[str, int]] = None,
        data: Optional[Any] = None
    ) -> MCPResponse:
        """Create an error response"""
        data = self._attach_error_hint(code, message, data)
        return MCPResponse(
            error=MCPError(
                code=code,
                message=message,
                data=data
            ),
            id=request_id
        )

    def _attach_error_hint(
        self,
        code: ErrorCode,
        message: str,
        data: Optional[Any]
    ) -> Optional[Any]:
        """Attach a structured hint for common error scenarios."""
        if data is not None:
            return data

        hint: Optional[str] = None
        lowered = message.lower()

        if code == ErrorCode.INVALID_PARAMS:
            prefix = "missing required parameter:"
            if lowered.startswith(prefix):
                # Extract the parameter name from original message
                try:
                    missing = message.split(":", 1)[1].strip().strip("'\"")
                except Exception:
                    missing = None
                if missing:
                    hint = f"Add '{missing}' to the tool arguments payload before retrying."
            elif "invalid parameters for tool" in lowered:
                hint = "Verify the tool arguments match the schema published by /mcp/tools."
        elif code == ErrorCode.AUTHORIZATION_ERROR and "write tools are disabled" in lowered:
            hint = "Enable write tools (set MCP_DISABLE_WRITE_TOOLS=0) or switch to a read-only operation."

        if hint:
            return {"hint": hint}
        return None

    async def _check_authorization(
        self,
        request: MCPRequest,
        context: RequestContext
    ) -> bool:
        """Check if user is authorized for method"""
        # Public methods that don't require auth
        public_methods = ["initialize", "ping"]
        method = request.method
        if method in public_methods:
            return True

        # Admin override (e.g., endpoint-level admin guard) for certain methods
        try:
            if isinstance(getattr(context, "metadata", None), dict):
                if context.metadata.get("admin_override") is True and request.method in {"modules/health"}:
                    return True
        except Exception:
            pass
        # No user context means no auth
        if not context.user_id:
            return False

        # tools/list: allow any authenticated user (deny if unauthenticated)
        if method == "tools/list":
            if not context.user_id:
                return False
            if not self._scope_allows(context, Resource.TOOL.value, None):
                return False
            return self._api_key_allows(context, is_write=None)

        # Map methods to resources and actions
        method_permissions = {
            # tools/list handled above
            "tools/call": (Resource.TOOL, Action.EXECUTE),
            "resources/list": (Resource.RESOURCE, Action.READ),
            "resources/read": (Resource.RESOURCE, Action.READ),
            "prompts/list": (Resource.PROMPT, Action.READ),
            "prompts/get": (Resource.PROMPT, Action.READ),
            "modules/list": (Resource.MODULE, Action.READ),
            "modules/health": (Resource.MODULE, Action.READ),
        }

        if method in method_permissions:
            resource, action = method_permissions[method]
            fn = getattr(self.rbac_policy, 'check_permission', None)
            if fn is None:
                return False
            # Provide resource_id (e.g., tool name) when applicable
            resource_id = None
            try:
                if resource == Resource.TOOL and action == Action.EXECUTE:
                    params = request.params or {}
                    name = params.get("name") if isinstance(params, dict) else None
                    if isinstance(name, str) and name:
                        resource_id = name
            except Exception:
                resource_id = None
            if inspect.iscoroutinefunction(fn):
                allowed = await fn(context.user_id, resource, action, resource_id)
            else:
                allowed = fn(context.user_id, resource, action, resource_id)
            if not allowed:
                return False
            if not self._scope_allows(context, resource.value, resource_id):
                return False
            # Apply API key scope gating for read-style methods
            if method != "tools/call":
                return self._api_key_allows(context, is_write=None)
            # For tools/call, evaluate write vs read-only tool when possible
            tool_name = resource_id if isinstance(resource_id, str) else None
            tool_def = None
            module = None
            is_write = None
            try:
                if tool_name:
                    module = await self.module_registry.find_module_for_tool(tool_name)
                if module is not None and tool_name:
                    get_def = getattr(module, "get_tool_def", None)
                    if callable(get_def):
                        tool_def = await get_def(tool_name)  # type: ignore[misc]
                    if tool_def is None:
                        tool_defs = await module.get_tools()
                        for _t in tool_defs:
                            if isinstance(_t, dict) and _t.get("name") == tool_name:
                                tool_def = _t
                                break
                if tool_def is not None and module is not None:
                    is_write = module.is_write_tool_def(tool_def)
                elif tool_name:
                    is_write = bool(re.search(r"(ingest|update|delete|create|import)", tool_name.lower()))
            except Exception:
                is_write = None
            return self._api_key_allows(context, is_write=is_write)

        # Unknown method - deny by default
        return False

    # Protocol method handlers

    async def _handle_initialize(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Handle initialize request"""
        client_info = params.get("clientInfo", {})

        logger.info(f"Client initializing: {client_info}")

        # Get server capabilities
        modules = await self.module_registry.get_all_modules()

        capabilities = {
            "tools": {"available": bool(modules)},
            "resources": {"available": bool(modules)},
            "prompts": {"available": bool(modules)}
        }

        return {
            "protocolVersion": self.protocol_version,
            "capabilities": capabilities,
            "serverInfo": {
                "name": "tldw-mcp-unified",
                "version": "3.0.0"
            }
        }

    async def _handle_ping(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Handle ping request"""
        return {"pong": True, "timestamp": datetime.now(timezone.utc).isoformat()}

    async def _resolve_catalog_tool_names(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> Optional[set[str]]:
        """Resolve catalog parameter into a set of tool names for filtering."""
        strict = False
        if isinstance(params, dict):
            raw_strict = params.get("catalog_strict")
            if isinstance(raw_strict, bool):
                strict = raw_strict
            elif isinstance(raw_strict, (int, float)):
                strict = bool(raw_strict)
            elif isinstance(raw_strict, str):
                strict = raw_strict.strip().lower() in {"1", "true", "yes", "on"}
        catalog_name = None
        catalog_id = None
        if isinstance(params, dict):
            catalog_name = params.get("catalog")
            catalog_id = params.get("catalog_id")
        if catalog_name is None and catalog_id is None:
            return None
        try:
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
            pool = await get_db_pool()
        except Exception as exc:
            context.logger.debug(f"Catalog lookup unavailable: {exc}")
            return None

        resolved_id: Optional[int] = None
        if catalog_id is not None:
            try:
                resolved_id = int(catalog_id)
            except Exception:
                resolved_id = None

        if resolved_id is None and isinstance(catalog_name, str) and catalog_name.strip():
            name = catalog_name.strip()
            meta = getattr(context, "metadata", {}) or {}
            team_id = meta.get("team_id")
            org_id = meta.get("org_id")

            row = None
            try:
                if team_id is not None:
                    row = await pool.fetchone(
                        "SELECT id FROM tool_catalogs WHERE name = ? AND team_id = ?",
                        name,
                        team_id,
                    )
                if row is None and org_id is not None:
                    row = await pool.fetchone(
                        "SELECT id FROM tool_catalogs WHERE name = ? AND org_id = ? AND team_id IS NULL",
                        name,
                        org_id,
                    )
                if row is None:
                    row = await pool.fetchone(
                        "SELECT id FROM tool_catalogs WHERE name = ? AND org_id IS NULL AND team_id IS NULL",
                        name,
                    )
                if row and row.get("id") is not None:
                    resolved_id = int(row.get("id"))
            except Exception as exc:
                context.logger.debug(f"Catalog lookup failed: {exc}")

        if resolved_id is None:
            return set() if strict else None

        try:
            rows = await pool.fetchall(
                "SELECT tool_name FROM tool_catalog_entries WHERE catalog_id = ?",
                resolved_id,
            )
        except Exception as exc:
            context.logger.debug(f"Catalog entries lookup failed: {exc}")
            return None

        names: set[str] = set()
        for r in rows:
            try:
                val = r["tool_name"] if isinstance(r, dict) else r[0]
            except Exception:
                val = None
            if isinstance(val, str):
                names.add(val)
        if names:
            return names
        return set() if strict else None

    async def _handle_tools_list(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """List available tools"""
        tools = []
        catalog_filter = await self._resolve_catalog_tool_names(params, context)
        modules = await self.module_registry.get_all_modules()
        module_filter = None
        if isinstance(params, dict):
            module_filter = params.get("module")
        allowed_modules: Optional[set[str]] = None
        if isinstance(module_filter, str) and module_filter.strip():
            allowed_modules = {module_filter.strip()}
        elif isinstance(module_filter, list):
            allowed_modules = {str(m).strip() for m in module_filter if str(m).strip()}

        for module_id, module in modules.items():
            if allowed_modules is not None and module_id not in allowed_modules:
                continue
            if catalog_filter is not None:
                context.logger.info(
                    "Catalog filter applied",
                    catalog=catalog_filter,
                    module_count=len(modules),
                )
            try:
                if not await self._has_module_permission(context, module_id):
                    continue
                module_tools = await module.get_tools()

                for tool in module_tools:
                    tool_copy = tool.copy()
                    tool_copy["module"] = module_id
                    name = tool_copy.get("name")
                    # Scoped tool permissions: when scopes are present, list only matching tools
                    if self._mcp_scopes(context) and isinstance(name, str):
                        if not self._scope_allows(context, Resource.TOOL.value, name):
                            continue
                    # Catalog filter: include only when in selected catalog
                    if catalog_filter is not None and isinstance(name, str):
                        meta = tool_copy.get("metadata") if isinstance(tool_copy, dict) else None
                        exempt = isinstance(meta, dict) and bool(meta.get("catalog_exempt"))
                        if name not in catalog_filter and not exempt:
                            continue
                    is_write = None
                    try:
                        if isinstance(tool_copy, dict):
                            is_write = module.is_write_tool_def(tool_copy)
                    except Exception:
                        is_write = None
                    can_execute = await self._has_tool_permission(context, name, is_write=is_write) if name else False
                    tool_copy["canExecute"] = can_execute
                    tools.append(tool_copy)
            except Exception as e:
                context.logger.error(f"Error getting tools from module {module_id}: {e}")

        return {"tools": tools}

    async def _handle_tools_call(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Execute a tool"""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        # Accept both camelCase and snake_case for idempotency
        idempotency_key = params.get("idempotencyKey") or params.get("idempotency_key")

        if not tool_name:
            raise InvalidParamsException("Tool name is required")

        # Strictly validate tool name
        if not self._tool_name_re.match(tool_name):
            raise InvalidParamsException("Invalid tool name")

        # Find module for tool
        module = await self.module_registry.find_module_for_tool(tool_name)
        if not module:
            raise InvalidParamsException(f"Tool not found: {tool_name}")

        module_id = self.module_registry.get_module_id_for_tool(tool_name) or getattr(module, "name", None)

        # Look up tool definition early for scope gating and validation
        tool_def = None
        try:
            # Prefer a dedicated lookup if module implements it
            get_def = getattr(module, "get_tool_def", None)
            if callable(get_def):
                tool_def = await get_def(tool_name)  # type: ignore[misc]
            if tool_def is None:
                tool_defs = await module.get_tools()
                for _t in tool_defs:
                    if isinstance(_t, dict) and _t.get("name") == tool_name:
                        tool_def = _t
                        break
        except Exception:
            tool_def = None

        # Determine write-capable status (best-effort)
        is_write = None
        try:
            if tool_def is not None:
                is_write = module.is_write_tool_def(tool_def)
            else:
                is_write = bool(re.search(r"(ingest|update|delete|create|import)", str(tool_name).lower()))
        except Exception:
            is_write = None

        module_allowed = await self._has_module_permission(context, module_id)
        tool_allowed = await self._has_tool_permission(context, tool_name, is_write=is_write)

        if not module_allowed and not tool_allowed:
            raise PermissionError(f"Permission denied for module: {module_id}")

        if not tool_allowed:
            raise PermissionError(f"Permission denied for tool: {tool_name}")

        # Harden arguments against cross-user/db overrides
        try:
            if isinstance(tool_args, dict):
                forbidden = {"user_id", "db_path", "db_paths", "chacha_db", "media_db", "prompts_db"}
                for k in list(tool_args.keys()):
                    if k in forbidden:
                        del tool_args[k]
        except Exception:
            pass

        # Central argument sanitization for all tools (deep)
        try:
            if isinstance(tool_args, dict):
                tool_args = module.sanitize_input(tool_args)
        except Exception as _san_e:
            raise InvalidParamsException(f"Invalid arguments: {str(_san_e)}")

        # Protocol-level pre-execution validation for write-capable tools
        # Ensures that modules validate arguments even if they forgot to call
        # validate_tool_arguments inside execute_tool.
        # Look up tool definition from module cache where possible
        if tool_def is None:
            try:
                get_def = getattr(module, "get_tool_def", None)
                if callable(get_def):
                    tool_def = await get_def(tool_name)  # type: ignore[misc]
                if tool_def is None:
                    tool_defs = await module.get_tools()
                    for _t in tool_defs:
                        if isinstance(_t, dict) and _t.get("name") == tool_name:
                            tool_def = _t
                            break
            except Exception:
                tool_def = None

        try:
            # Lightweight inputSchema validation (config-gated)
            cfg = get_config()
            if cfg.validate_input_schema and isinstance(tool_def, dict):
                schema = tool_def.get("inputSchema") or {}
                try:
                    self._validate_input_schema(schema, tool_args)
                except InvalidParamsException:
                    try:
                        self.metrics.record_tool_invalid_params(getattr(module, "name", "unknown"), str(tool_name))
                    except Exception:
                        pass
                    raise

            # Determine write-capable status
            if is_write is None:
                try:
                    if tool_def is not None:
                        is_write = module.is_write_tool_def(tool_def)
                    else:
                        # Fallback heuristic based on name
                        import re as _re
                        is_write = bool(_re.search(r"(ingest|update|delete|create|import)", str(tool_name).lower()))
                except Exception:
                    is_write = False

            # Optional policy: disable write-capable tools entirely
            if is_write:
                if get_config().disable_write_tools:
                    raise PermissionError("Write tools are disabled by server policy")
                # Check module overrides validator
                if module.__class__.validate_tool_arguments is BaseModule.validate_tool_arguments:
                    try:
                        self.metrics.record_tool_validator_missing(getattr(module, "name", "unknown"), str(tool_name))
                    except Exception:
                        pass
                    raise ValueError(
                        "Write-capable tool requires module.validate_tool_arguments override"
                    )
                # Run validator
                try:
                    module.validate_tool_arguments(tool_name, tool_args)
                except Exception as ve:
                    try:
                        self.metrics.record_tool_invalid_params(getattr(module, "name", "unknown"), str(tool_name))
                    except Exception:
                        pass
                    raise ValueError(f"Invalid parameters for tool {tool_name}: {ve}")

                idempotency_cache_key = None
                if isinstance(idempotency_key, str) and idempotency_key:
                    idempotency_cache_key = self._make_idempotency_cache_key(
                        context, module_id or getattr(module, "name", "unknown"), tool_name, idempotency_key
                    )
        except ValueError as ve:
            # Surface as JSON-RPC INVALID_PARAMS at the protocol layer
            # by raising a sentinel exception handled by process_request
            raise InvalidParamsException(str(ve))

        async def _execute_tool_call() -> dict[str, Any]:
            # Optional per-tool/category rate limits (ingestion vs read)
            try:
                # Categorization for per-category rate limiting
                cfg = get_config()
                category = None
                # 1) Prefer tool metadata.category if available
                try:
                    meta = (tool_def or {}).get("metadata") or {}
                    cat = str(meta.get("category") or "").lower()
                    if cat in {"ingestion", "management", "read"}:
                        category = cat
                except Exception:
                    category = None
                # 2) Config-driven mapping
                if not category:
                    try:
                        if isinstance(cfg.tool_category_map, dict) and tool_name in cfg.tool_category_map:
                            category = str(cfg.tool_category_map.get(tool_name))
                    except Exception:
                        category = None
                # 3) Heuristic fallback
                if not category:
                    ingestion_tools = {'ingest_media', 'update_media', 'delete_media'}
                    category = 'ingestion' if tool_name in ingestion_tools else 'read'
                key_owner = f"user:{context.user_id}" if context.user_id else (f"client:{context.client_id}" if context.client_id else "anon")
                rl_key = f"{key_owner}:tool:{tool_name}:cat:{category}"
                await self.rate_limiter.check_rate_limit(rl_key, category=category)
            except RateLimitExceeded:
                raise
            except Exception:
                # Best-effort; do not block on limiter errors
                pass

            # Execute tool with circuit breaker (pass context through)
            t0 = time.time()
            args_hash = self._hash_arguments(tool_args if isinstance(tool_args, dict) else {})

            try:
                # Trace the tool call with OTEL
                with self.telemetry.trace_context(
                    "mcp.tool_call",
                    {
                        "mcp.tool": tool_name,
                        "mcp.module": getattr(module, "name", "unknown"),
                        "mcp.user_id": str(context.user_id or ""),
                        "mcp.client_id": str(context.client_id or ""),
                    },
                ) as span:
                    try:
                        result = await module.execute_with_circuit_breaker(
                            module.execute_tool,
                            tool_name,
                            tool_args,
                            context
                        )
                        span.set_attribute("mcp.status", "success")
                    except Exception as _tool_e:
                        span.set_attribute("mcp.status", "failure")
                        span.set_attribute("mcp.error_type", _tool_e.__class__.__name__)
                        span.set_attribute("mcp.error_message", str(_tool_e)[:200])
                        raise
                    finally:
                        span.set_attribute("mcp.duration_ms", max(0.0, (time.time() - t0) * 1000.0))

                # Format result
                if isinstance(result, str):
                    content = [{"type": "text", "text": result}]
                elif isinstance(result, list):
                    content = result
                elif isinstance(result, dict):
                    # Preserve structured tool results as JSON content instead of stringifying.
                    content = [{"type": "json", "json": result}]
                else:
                    content = [{"type": "text", "text": str(result)}]

                module_name = module_id or getattr(module, "name", None)
                # Record module operation metrics
                try:
                    duration = max(0.0, time.time() - t0)
                    self.metrics.record_module_operation(module=module_name or "unknown", operation="tools_call", duration=duration, success=True)
                except Exception:
                    pass
                self._audit_tool_event(
                    context,
                    tool_name,
                    module_name,
                    status="success",
                    duration_ms=max(0.0, (time.time() - t0) * 1000.0),
                    arguments_hash=args_hash,
                )
                response_payload = {"content": content, "module": module_name, "tool": tool_name}
                return response_payload

            except Exception as e:
                sanitized_error = self._mask_secrets(str(e))
                context.logger.error(f"Tool execution failed: {tool_name} - {sanitized_error}")
                try:
                    duration = max(0.0, time.time() - t0)
                    self.metrics.record_module_operation(module=getattr(module, "name", "unknown"), operation="tools_call", duration=duration, success=False)
                except Exception:
                    pass
                self._audit_tool_event(
                    context,
                    tool_name,
                    module_id or getattr(module, "name", None),
                    status="failure",
                    duration_ms=max(0.0, (time.time() - t0) * 1000.0),
                    arguments_hash=args_hash,
                    error=e,
                )
                raise

        if is_write and idempotency_cache_key:
            cfg = get_config()
            ttl = max(1, int(getattr(cfg, "idempotency_ttl_seconds", 300)))
            max_size = max(1, int(getattr(cfg, "idempotency_cache_size", 512)))
            module_timeout = int(getattr(getattr(module, "config", None), "timeout_seconds", cfg.module_timeout))
            lock_ttl = max(ttl, module_timeout * 2)
            payload, from_cache = await self._idempotency.run(
                idempotency_cache_key,
                _execute_tool_call,
                ttl=ttl,
                max_size=max_size,
                lock_ttl=lock_ttl,
            )
            try:
                if from_cache:
                    self.metrics.record_idempotency_hit(module_id or getattr(module, "name", "unknown"), str(tool_name))
                else:
                    self.metrics.record_idempotency_miss(module_id or getattr(module, "name", "unknown"), str(tool_name))
            except Exception:
                pass
            return payload

        return await _execute_tool_call()

    # -------------------------
    # Idempotency cache helpers
    # -------------------------
    def _make_idempotency_cache_key(self, context: RequestContext, module_name: str, tool_name: str, idempotency_key: str) -> str:
        owner = f"user:{context.user_id}" if context.user_id else (f"client:{context.client_id}" if context.client_id else "anon")
        return f"{owner}|module:{module_name}|tool:{tool_name}|key:{idempotency_key}"

    def _validate_input_schema(self, schema: dict[str, Any], args: dict[str, Any]) -> None:
        """Quick JSON Schema checks: required keys, primitive types, unknown fields.
        Only applies when schema.type == object.
        """
        try:
            if not isinstance(schema, dict):
                return
            if schema.get("type") != "object":
                return
            if not isinstance(args, dict):
                raise InvalidParamsException("Arguments must be an object")
            props = schema.get("properties") or {}
            required = schema.get("required") or []
            addl = schema.get("additionalProperties", True)

            # Required
            for key in required:
                if key not in args or args.get(key) is None:
                    raise InvalidParamsException(f"Missing required parameter: {key}")

            # Unknown fields
            if addl is False:
                unknown = [k for k in args.keys() if k not in props]
                if unknown:
                    raise InvalidParamsException(f"Unknown parameters: {', '.join(unknown)}")

            # Primitive type checks
            def _type_ok(expected: str, value: Any) -> bool:
                mapping = {
                    "string": str,
                    "number": (int, float),
                    "integer": int,
                    "boolean": bool,
                    "object": dict,
                    "array": list,
                }
                py = mapping.get(expected)
                if py is None:
                    return True
                # number should not reject ints; python isinstance(True, int) caveat
                if expected in {"number", "integer"} and isinstance(value, bool):
                    return False
                return isinstance(value, py)

            for k, v in args.items():
                if k in props:
                    p = props.get(k) or {}
                    t = p.get("type")
                    if isinstance(t, str) and not _type_ok(t, v):
                        raise InvalidParamsException(f"Invalid type for '{k}': expected {t}")
        except InvalidParamsException:
            raise
        except Exception:
            # Be forgiving on schema format errors
            return

    async def _handle_resources_list(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """List available resources"""
        resources = []
        modules = await self.module_registry.get_all_modules()
        catalog_filter = await self._resolve_catalog_tool_names(params, context)
        module_tool_names: dict[str, set[str]] = {}

        for module_id, module in modules.items():
            try:
                if catalog_filter is not None:
                    context.logger.info(f"Catalog filter applied: {sorted(catalog_filter)}")
                if not await self._has_module_permission(context, module_id):
                    continue
                if catalog_filter is not None:
                    cached_names = module_tool_names.get(module_id)
                    if cached_names is None:
                        try:
                            module_tools = await module.get_tools()
                            cached_names = {
                                str(tool.get("name"))
                                for tool in module_tools
                                if isinstance(tool, dict) and isinstance(tool.get("name"), str)
                            }
                        except Exception:
                            cached_names = set()
                        module_tool_names[module_id] = cached_names
                    if not cached_names.intersection(catalog_filter):
                        continue
                module_resources = await module.get_resources()

                for resource in module_resources:
                    uri = resource.get("uri") if isinstance(resource, dict) else None
                    if uri and not await self._has_resource_permission(context, uri, module_id):
                        continue
                    resource_copy = resource.copy() if isinstance(resource, dict) else resource
                    if isinstance(resource_copy, dict):
                        resource_copy["module"] = module_id
                    resources.append(resource_copy)

            except Exception as e:
                context.logger.error(f"Error getting resources from module {module_id}: {e}")

        return {"resources": resources}

    async def _handle_resources_read(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Read a resource"""
        uri = params.get("uri")
        if not uri:
            raise InvalidParamsException("Resource URI is required")

        # Find module for resource
        module = await self.module_registry.find_module_for_resource(uri)
        if not module:
            raise InvalidParamsException(f"Resource not found: {uri}")
        module_id = self.module_registry.get_module_id_for_resource(uri) or getattr(module, "name", None)

        if not await self._has_resource_permission(context, uri, module_id):
            raise PermissionError(f"Permission denied for resource: {uri}")

        # Read resource (pass context when supported)
        read_fn = getattr(module, "read_resource")
        try:
            params = inspect.signature(read_fn).parameters
        except (TypeError, ValueError):
            params = {}
        if "context" in params:
            content = await read_fn(uri, context=context)
        else:
            content = await read_fn(uri)

        return {"contents": [content]}

    async def _handle_prompts_list(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """List available prompts"""
        prompts = []
        modules = await self.module_registry.get_all_modules()

        for module_id, module in modules.items():
            try:
                if not await self._has_module_permission(context, module_id):
                    continue
                module_prompts = await module.get_prompts()

                for prompt in module_prompts:
                    name = prompt.get("name") if isinstance(prompt, dict) else None
                    if name and not await self._has_prompt_permission(context, name, module_id):
                        continue
                    prompt_copy = prompt.copy() if isinstance(prompt, dict) else prompt
                    if isinstance(prompt_copy, dict):
                        prompt_copy["module"] = module_id
                    prompts.append(prompt_copy)

            except Exception as e:
                context.logger.error(f"Error getting prompts from module {module_id}: {e}")

        return {"prompts": prompts}

    async def _handle_prompts_get(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Get a specific prompt"""
        name = params.get("name")
        if not name:
            raise InvalidParamsException("Prompt name is required")

        arguments = params.get("arguments", {})

        # Find module for prompt
        module = await self.module_registry.find_module_for_prompt(name)
        if not module:
            raise InvalidParamsException(f"Prompt not found: {name}")
        module_id = self.module_registry.get_module_id_for_prompt(name) or getattr(module, "name", None)

        if not await self._has_prompt_permission(context, name, module_id):
            raise PermissionError(f"Permission denied for prompt: {name}")

        # Get prompt
        prompt = await module.get_prompt(name, arguments)

        return prompt

    async def _handle_modules_list(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """List registered modules"""
        registrations = await self.module_registry.list_registrations()
        filtered: list[dict[str, Any]] = []
        for entry in registrations:
            module_id = entry.get("module_id") if isinstance(entry, dict) else None
            try:
                if await self._has_module_permission(context, module_id):
                    filtered.append(entry)
            except Exception:
                continue
        return {"modules": filtered}

    async def _handle_modules_health(
        self,
        params: dict[str, Any],
        context: RequestContext
    ) -> dict[str, Any]:
        """Get module health status"""
        health_results = await self.module_registry.check_all_health()

        # Convert to serializable format
        health_data = {}
        for module_id, health in health_results.items():
            last_check_iso = None
            try:
                if getattr(health, "last_check", None):
                    last_check_iso = health.last_check.isoformat()
            except Exception:
                last_check_iso = None
            health_data[module_id] = {
                "status": health.status.value if getattr(health, "status", None) else "unknown",
                "message": getattr(health, "message", ""),
                "checks": getattr(health, "checks", {}),
                "last_check": last_check_iso,
            }

        return {"health": health_data}


# Convenience function
async def process_mcp_request(
    request: Union[dict[str, Any], MCPRequest],
    context: Optional[RequestContext] = None
) -> MCPResponse:
    """Process an MCP request"""
    protocol = MCPProtocol()
    return await protocol.process_request(request, context)
