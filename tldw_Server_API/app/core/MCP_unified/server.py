"""
Main MCP Server implementation for unified module

Handles WebSocket and HTTP connections with production-ready features.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Set, List, Deque
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger

from .config import get_config, validate_config
from .protocol import MCPProtocol, MCPRequest, MCPResponse, RequestContext
from .modules.registry import get_module_registry
from .auth.jwt_manager import get_jwt_manager
from .auth.authnz_rbac import get_rbac_policy
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from .auth.rate_limiter import get_rate_limiter, RateLimitExceeded
from .monitoring.metrics import get_metrics_collector
from .security.ip_filter import get_ip_access_controller
from .security.request_guards import enforce_client_certificate_headers
import ipaddress
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


class WebSocketConnection:
    """Manages a single WebSocket connection"""

    def __init__(
        self,
        websocket: WebSocket,
        connection_id: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.client_id = client_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.connected_at = datetime.now(timezone.utc)
        self.last_activity = self.connected_at
        self.message_count = 0
        self.error_count = 0
        self.request_times: Deque[float] = deque(maxlen=1000)

    async def send_json(self, data: Dict[str, Any]):
        """Send JSON data to client"""
        try:
            await self.websocket.send_json(data)
            self.last_activity = datetime.now(timezone.utc)
        except Exception as e:
            logger.bind(connection_id=self.connection_id).error(f"Error sending to WebSocket {self.connection_id}: {e}")
            self.error_count += 1
            raise

    async def receive_json(self) -> Dict[str, Any]:
        """Receive JSON data from client"""
        try:
            data = await self.websocket.receive_json()
            self.last_activity = datetime.now(timezone.utc)
            self.message_count += 1
            return data
        except Exception as e:
            logger.bind(connection_id=self.connection_id).error(f"Error receiving from WebSocket {self.connection_id}: {e}")
            self.error_count += 1
            raise

    async def close(self, code: int = 1000, reason: str = ""):
        """Close the WebSocket connection"""
        try:
            await self.websocket.close(code=code, reason=reason)
        except Exception as e:
            logger.bind(connection_id=self.connection_id).error(f"Error closing WebSocket {self.connection_id}: {e}")


@dataclass
class SessionData:
    """Lightweight in-memory session state for HTTP/WS MCP sessions."""
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uris_seen: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    uris_index: Set[str] = field(default_factory=set)
    client_info: Dict[str, Any] = field(default_factory=dict)
    safe_config: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        self.last_activity = datetime.now(timezone.utc)

    def add_seen_uri(self, uri: str, max_len: int):
        if uri in self.uris_index:
            return
        # Enforce bounded size
        if len(self.uris_seen) >= max_len:
            oldest = self.uris_seen.popleft()
            self.uris_index.discard(oldest)
        self.uris_seen.append(uri)
        self.uris_index.add(uri)


class MCPServer:
    """
    Production-ready MCP Server with WebSocket and HTTP support.

    Features:
    - WebSocket connection management
    - HTTP request handling
    - Connection pooling
    - Graceful shutdown
    - Health monitoring
    - Metrics collection
    """

    def __init__(self):
        self.config = get_config()
        self.protocol = MCPProtocol()
        self.module_registry = get_module_registry()
        self.jwt_manager = get_jwt_manager()
        self.rbac_policy = get_rbac_policy()
        self.rate_limiter = get_rate_limiter()

        # Connection management
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_lock = asyncio.Lock()
        self._ip_connection_counts: Dict[str, int] = {}

        # Session management (HTTP/WS)
        self.sessions: Dict[str, SessionData] = {}
        self.session_lock = asyncio.Lock()

        # Server state
        self.initialized = False
        self.startup_time = datetime.now(timezone.utc)
        self.shutdown_event = asyncio.Event()

        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()

        logger.info("MCP Server created")

    @staticmethod
    def _mask_secrets(text: str) -> str:
        """Best-effort masking of bearer/API keys in strings."""
        try:
            if not text:
                return text
            import re as _re
            text = _re.sub(r"(Bearer)\s+[A-Za-z0-9._\-~+/=]+", r"\1 ****", text, flags=_re.IGNORECASE)
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

    async def initialize(self):
        """Initialize the server and all modules"""
        if self.initialized:
            logger.warning("Server already initialized")
            return

        logger.info("Initializing MCP Server")

        try:
            # Fail fast on insecure production configurations
            try:
                import os as _os
                _test_mode = _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes"}
                if not self.config.debug_mode and not _test_mode:
                    ok = validate_config()
                    if not ok:
                        raise RuntimeError("MCP configuration validation failed; refusing to start in production")
            except Exception as _ve:
                # If validation fails, propagate to abort startup
                raise
            # Warn if demo auth is enabled in a non-debug environment
            try:
                import os as _os
                if _os.getenv("MCP_ENABLE_DEMO_AUTH", "").lower() in {"1", "true", "yes"} and not self.config.debug_mode:
                    logger.warning("MCP_ENABLE_DEMO_AUTH is enabled - for development only; DO NOT USE IN PRODUCTION")
            except Exception:
                pass
            # Start module health monitoring
            await self.module_registry.start_health_monitoring()

            # Start metrics collection
            try:
                await get_metrics_collector().start_collection()
            except Exception as e:
                logger.warning(f"MCP metrics collector start failed: {self._mask_secrets(str(e))}")

            # Register default modules (will be implemented when migrating modules)
            await self._register_default_modules()

            # Ensure default tool permissions exist (wildcard)
            await self._ensure_default_tool_permissions()

            # Start background tasks
            self._start_background_tasks()

            self.initialized = True
            logger.info("MCP Server initialized successfully")

        except Exception as e:
            logger.error(f"Server initialization failed: {self._mask_secrets(str(e))}")
            raise

    async def _ensure_default_tool_permissions(self):
        """Seed wildcard tool permission tools.execute:* if missing."""
        try:
            pool = await get_db_pool()
            name = 'tools.execute:*'
            desc = 'Wildcard tool execution'
            if pool.pool:
                await pool.execute(
                    "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) ON CONFLICT (name) DO NOTHING",
                    name, desc, 'tools'
                )
            else:
                row = await pool.fetchone("SELECT 1 FROM permissions WHERE name = ?", name)
                if not row:
                    await pool.execute(
                        "INSERT INTO permissions (name, description, category) VALUES (?, ?, ?)",
                        name, desc, 'tools'
                    )
        except Exception as e:
            logger.debug(f"Seed wildcard tool permission failed: {self._mask_secrets(str(e))}")

    async def shutdown(self):
        """Gracefully shutdown the server"""
        logger.info("Shutting down MCP Server")

        # Signal shutdown
        self.shutdown_event.set()

        # Close all WebSocket connections
        await self._close_all_connections()

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Shutdown modules
        await self.module_registry.shutdown_all()

        self.initialized = False
        logger.info("MCP Server shutdown complete")

    async def _register_default_modules(self):
        """Register default modules via config/env-driven loader"""
        # Autoload modules from YAML config and/or MCP_MODULES env var
        try:
            import os
            import importlib
            # Lazy import yaml to avoid hard dependency during tests if not installed
            try:
                import yaml  # type: ignore
            except Exception:
                yaml = None  # type: ignore

            modules_to_load = []

            # 1) YAML configuration
            cfg_path = os.getenv(
                "MCP_MODULES_CONFIG",
                "tldw_Server_API/Config_Files/mcp_modules.yaml",
            )
            if os.path.exists(cfg_path) and yaml is not None:
                try:
                    with open(cfg_path, "r") as f:
                        data = yaml.safe_load(f) or {}
                    modules_cfg = data.get("modules", [])
                    if isinstance(modules_cfg, list):
                        modules_to_load.extend(modules_cfg)
                    logger.info(f"Loaded {len(modules_cfg)} MCP modules from {cfg_path}")
                except Exception as e:
                    logger.error(f"Failed to read MCP modules YAML {cfg_path}: {e}")
            elif os.path.exists(cfg_path) and yaml is None:
                logger.warning(
                    f"MCP modules config found at {cfg_path} but PyYAML not installed; skipping"
                )

            # 2) Environment variable list (comma-separated)
            # Example: MCP_MODULES="media=tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module:MediaModule"
            env_spec = os.getenv("MCP_MODULES", "").strip()
            if env_spec:
                for item in [s for s in env_spec.split(",") if s.strip()]:
                    try:
                        mod_id, class_ref = item.split("=", 1)
                        modules_to_load.append({
                            "id": mod_id.strip(),
                            "class": class_ref.strip(),
                            "enabled": True,
                        })
                    except ValueError:
                        logger.warning(f"Invalid MCP_MODULES item format: '{item}'")

            # 3) Optional default: enable media module if flag is set and nothing else specified
            enable_media_flag = os.getenv("MCP_ENABLE_MEDIA_MODULE", "false").lower() in {"1", "true", "yes"}
            test_mode = os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
            if enable_media_flag and not modules_to_load:
                default_media_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
                modules_to_load.append({
                    "id": "media",
                    "class": "tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module:MediaModule",
                    "enabled": True,
                    "name": "Media",
                    "version": "1.0.0",
                    "department": "media",
                    "settings": {
                        "db_path": default_media_path,
                        "cache_ttl": 300,
                    },
                })
                logger.info("MCP_ENABLE_MEDIA_MODULE=true; queuing MediaModule for registration")

            # 4) Test convenience: default-enable media module when TEST_MODE unless explicitly disabled
            if test_mode and not any(m.get("id") == "media" for m in modules_to_load):
                if os.getenv("MCP_ENABLE_MEDIA_MODULE", "").lower() not in {"0", "false", "off"}:
                    default_media_path = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
                    modules_to_load.append({
                        "id": "media",
                        "class": "tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module:MediaModule",
                        "enabled": True,
                        "name": "Media",
                        "version": "1.0.0",
                        "department": "media",
                        "settings": {
                            "db_path": default_media_path,
                            "cache_ttl": 300,
                        },
                    })
                    logger.info("TEST_MODE auto-enabled MediaModule for deterministic tool catalogs")

            # 5) Optional: Sandbox module (code interpreter) - disabled by default
            if os.getenv("MCP_ENABLE_SANDBOX_MODULE", "").lower() in {"1", "true", "yes", "on"}:
                modules_to_load.append({
                    "id": "sandbox",
                    "class": "tldw_Server_API.app.core.MCP_unified.modules.implementations.sandbox_module:SandboxModule",
                    "enabled": True,
                    "name": "Sandbox Engine",
                    "version": "1.0.0",
                    "department": "management",
                    "settings": {},
                })
                logger.info("MCP_ENABLE_SANDBOX_MODULE=true; queuing SandboxModule for registration")

            # Register all specified modules
            from .modules.base import ModuleConfig  # Local import to avoid cycles
            for m in modules_to_load:
                if not m or not isinstance(m, dict):
                    continue
                if not m.get("enabled", True):
                    logger.info(f"Skipping disabled module: {m.get('id')}")
                    continue
                try:
                    module_id = m["id"]
                    class_ref = m["class"]
                    module_path, class_name = class_ref.split(":", 1)
                    # Restrict module autoload to allowed namespace for safety
                    allowed_prefixes = (
                        "tldw_Server_API.app.core.MCP_unified.modules.implementations",
                    )
                    if not any(module_path.startswith(p) for p in allowed_prefixes):
                        logger.warning(
                            f"Blocked module autoload for '{class_ref}': outside allowed namespace"
                        )
                        continue
                    cls = getattr(importlib.import_module(module_path), class_name)

                    mc = ModuleConfig(
                        name=m.get("name", module_id),
                        version=m.get("version", "1.0.0"),
                        description=m.get("description", ""),
                        department=m.get("department", "general"),
                        enabled=True,
                        timeout_seconds=m.get("timeout_seconds", self.config.module_timeout),
                        max_retries=m.get("max_retries", self.config.module_max_retries),
                        circuit_breaker_threshold=m.get("circuit_breaker_threshold", 5),
                        circuit_breaker_timeout=m.get("circuit_breaker_timeout", 60),
                        max_concurrent=m.get("max_concurrent", 20),
                        circuit_breaker_backoff_factor=m.get("circuit_breaker_backoff_factor", 2.0),
                        circuit_breaker_max_timeout=m.get("circuit_breaker_max_timeout", 300),
                        settings=m.get("settings", {}),
                    )
                    await self.module_registry.register_module(module_id, cls, mc)
                    logger.info(f"Registered MCP module: {module_id} ({class_ref})")
                except Exception as e:
                    logger.error(f"Failed to register module {m}: {self._mask_secrets(str(e))}")

        except Exception as e:
            logger.error(f"Default modules registration failed: {self._mask_secrets(str(e))}")

    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        # Connection cleanup task
        task = asyncio.create_task(self._connection_cleanup_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

        # Metrics collection task
        task = asyncio.create_task(self._metrics_collection_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

        # Session cleanup task
        task = asyncio.create_task(self._session_cleanup_loop())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _connection_cleanup_loop(self):
        """Periodically clean up stale connections"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")

    async def _cleanup_stale_connections(self):
        """Remove stale WebSocket connections"""
        async with self.connection_lock:
            stale_connections = []
            current_time = datetime.now(timezone.utc)

            for conn_id, connection in self.connections.items():
                # Check for stale connections (no activity for 5 minutes)
                if (current_time - connection.last_activity).total_seconds() > 300:
                    stale_connections.append(conn_id)

                # Check for error threshold
                elif connection.error_count > 10:
                    stale_connections.append(conn_id)

            # Close stale connections
            for conn_id in stale_connections:
                logger.info(f"Closing stale connection: {conn_id}")
                connection = self.connections[conn_id]
                await connection.close(code=1001, reason="Connection timeout")
                del self.connections[conn_id]
            # Update connection gauge
            try:
                get_metrics_collector().update_connection_count("websocket", len(self.connections))
            except Exception:
                pass

    async def _metrics_collection_loop(self):
        """Periodically collect and log metrics"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._log_metrics()
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")

    async def _log_metrics(self):
        """Log server metrics"""
        metrics = await self.get_metrics()
        logger.info(f"Server metrics: {metrics}")

    # ------------------------
    # Session helpers
    # ------------------------

    async def _session_cleanup_loop(self):
        """Periodically evict stale sessions."""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(60)
                await self._cleanup_stale_sessions()
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")

    async def _cleanup_stale_sessions(self):
        ttl = timedelta(minutes=max(1, int(self.config.session_ttl_minutes)))
        cutoff = datetime.now(timezone.utc) - ttl
        async with self.session_lock:
            to_delete = [sid for sid, s in self.sessions.items() if s.last_activity < cutoff]
            for sid in to_delete:
                self.sessions.pop(sid, None)

    async def _get_or_create_session(self, session_id: str) -> SessionData:
        async with self.session_lock:
            s = self.sessions.get(session_id)
            if s is None:
                # Enforce global cap
                if len(self.sessions) >= max(1, int(self.config.max_sessions)):
                    # Evict oldest
                    oldest_id = min(self.sessions, key=lambda k: self.sessions[k].last_activity)
                    self.sessions.pop(oldest_id, None)
                s = SessionData(session_id=session_id)
                # Respect configured max URIs per session
                s.uris_seen = deque(maxlen=max(1, int(self.config.max_session_uris)))
                self.sessions[session_id] = s
            s.touch()
            return s

    def _merge_safe_config(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """Merge allowlisted safe config keys with clamping."""
        if not incoming:
            return current
        out = dict(current)
        # Allowlist keys
        allow_int = {
            "snippet_length": (1, 2000),
            "max_tokens": (500, 200000),
            "sibling_window": (0, 10),
            "chars_per_token": (1, 20),
            "maxSessionUris": (10, 5000),
        }
        allow_bool = {"aliasMode", "compactShape"}
        allow_str = {"order_by"}
        for k, v in incoming.items():
            if k in allow_bool and isinstance(v, bool):
                out[k] = v
            elif k in allow_str and isinstance(v, str):
                out[k] = v
            elif k in allow_int and isinstance(v, (int, float)):
                lo, hi = allow_int[k]
                out[k] = int(max(lo, min(int(v), hi)))
        return out

    async def handle_websocket(
        self,
        websocket: WebSocket,
        client_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Handle a WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            client_id: Optional client identifier
            auth_token: Optional authentication token
        """
        connection_id = f"ws_{client_id or 'anonymous'}_{datetime.now().timestamp()}"
        user_id = None

        controller = get_ip_access_controller()
        metadata: Dict[str, Any] = {}
        forwarded_for = websocket.headers.get("x-forwarded-for") or websocket.headers.get("X-Forwarded-For")
        real_ip = websocket.headers.get("x-real-ip") or websocket.headers.get("X-Real-IP")
        raw_remote_ip = None
        try:
            raw_remote_ip = getattr(websocket.client, "host", None) or (
                websocket.client[0] if isinstance(websocket.client, (list, tuple)) else None
            )
        except Exception:
            raw_remote_ip = None

        resolved_ip = controller.resolve_client_ip(raw_remote_ip, forwarded_for, real_ip)
        if not controller.is_allowed(resolved_ip):
            try:
                logger.warning(
                    "Rejecting MCP WebSocket connection from disallowed IP",
                    extra={"audit": True, "ip": resolved_ip or "unknown", "client_id": client_id},
                )
            except Exception:
                pass
            await websocket.close(code=1008, reason="IP not allowed")
            return

        client_ip = resolved_ip or "unknown"

        try:
            enforce_client_certificate_headers(websocket.headers, remote_addr=raw_remote_ip)
        except HTTPException:
            await websocket.close(code=1008, reason="Client certificate required")
            return

        # Origin validation (enforce when ws_allowed_origins configured)
        try:
            allowed = list(self.config.ws_allowed_origins or [])
            if allowed:
                # Allow wildcard '*' if explicitly configured
                origin = websocket.headers.get("origin") or websocket.headers.get("Origin") or ""
                if "*" not in allowed:
                    if not origin or origin not in allowed:
                        await websocket.close(code=1008, reason="Origin not allowed")
                        return
        except Exception:
            # Fail-safe: do not block if config parsing fails
            pass

        # Gate query parameter auth tokens if disabled by config
        if (auth_token or api_key) and not self.config.ws_allow_query_auth:
            try:
                # Emit a deprecation warning; ignore query tokens unless explicitly allowed
                logger.warning("WS query-parameter authentication is disabled; pass Authorization bearer token or X-API-KEY header instead")
            except Exception:
                pass
            auth_token = None
            api_key = None

        # Prefer headers/subprotocol for auth if present
        try:
            # Authorization: Bearer <token>
            _authz = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
            if _authz and _authz.lower().startswith("bearer "):
                auth_token = _authz.split(" ", 1)[1].strip()
        except Exception:
            pass
        try:
            # X-API-KEY header
            _xkey = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")
            if _xkey:
                api_key = _xkey.strip()
        except Exception:
            pass
        try:
            # Sec-WebSocket-Protocol: bearer,<token>
            _proto = websocket.headers.get("sec-websocket-protocol") or websocket.headers.get("Sec-WebSocket-Protocol")
            if _proto and not auth_token:
                # pick first value that looks like bearer,<token>
                parts = [p.strip() for p in _proto.split(",")]
                if len(parts) >= 2 and parts[0].lower() == "bearer" and parts[1]:
                    auth_token = parts[1]
        except Exception:
            pass

        # Authenticate if token provided (prefer AuthNZ JWT, then MCP JWT)
        if auth_token:
            ok = False
            try:
                # Try AuthNZ JWT first for consistency with HTTP endpoints
                from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
                jwt_service = get_jwt_service()
                payload = jwt_service.decode_access_token(auth_token)
                user_id = str(payload.get("user_id") or payload.get("sub")) if payload else None
                ok = bool(user_id)
                if ok:
                    logger.info(f"WebSocket authenticated for user (AuthNZ JWT): {user_id}")
                    try:
                        if payload:
                            roles = payload.get("roles")
                            permissions = payload.get("permissions") or payload.get("scopes")
                            if isinstance(roles, list):
                                metadata["roles"] = roles
                            if isinstance(permissions, list):
                                metadata["permissions"] = permissions
                            elif isinstance(permissions, str):
                                metadata["permissions"] = [permissions]
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"AuthNZ JWT auth failed: {self._mask_secrets(str(e))}")
                # Try MCP JWT
                try:
                    token_data = self.jwt_manager.verify_token(auth_token)
                    user_id = token_data.sub
                    ok = True
                    logger.info(f"WebSocket authenticated for user (MCP JWT): {user_id}")
                    if token_data.roles:
                        metadata["roles"] = token_data.roles
                    if token_data.permissions:
                        metadata["permissions"] = token_data.permissions
                except Exception as _e:
                    logger.debug(f"MCP JWT auth failed: {self._mask_secrets(str(_e))}")
            if auth_token and not ok:
                await websocket.close(code=1008, reason="Authentication failed")
                return

        # API key auth (optional)
        if api_key and not user_id:
            try:
                from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
                mgr = await get_api_key_manager()
                # Enforce allowed IPs for API keys by forwarding resolved client IP
                info = await mgr.validate_api_key(api_key, ip_address=client_ip)
                if info and info.get('user_id'):
                    user_id = str(info['user_id'])
                    # Attach org/team context
                    if info.get('org_id') is not None:
                        metadata['org_id'] = info.get('org_id')
                    if info.get('team_id') is not None:
                        metadata['team_id'] = info.get('team_id')
                    roles = metadata.setdefault('roles', [])
                    if 'api_client' not in roles:
                        roles.append('api_client')
                    try:
                        scopes = info.get('scopes')
                        if isinstance(scopes, list):
                            perms = metadata.setdefault('permissions', [])
                            for scope in scopes:
                                if isinstance(scope, str) and scope not in perms:
                                    perms.append(scope)
                        elif isinstance(scopes, str):
                            perms = metadata.setdefault('permissions', [])
                            if scopes not in perms:
                                perms.append(scopes)
                    except Exception:
                        pass
                    logger.info(f"WebSocket authenticated via API key for user: {user_id}")
                else:
                    await websocket.close(code=1008, reason="Authentication failed")
                    return
            except Exception as e:
                logger.warning(f"WebSocket API key authentication failed: {self._mask_secrets(str(e))}")
                await websocket.close(code=1008, reason="Authentication failed")
                return

        # Optionally require authentication for WS (production hardening)
        if self.config.ws_auth_required and not user_id:
            await websocket.close(code=1008, reason="Authentication required")
            return

        # Check connection limits (global and per-IP)
        async with self.connection_lock:
            if len(self.connections) >= self.config.ws_max_connections:
                logger.warning("Maximum WebSocket connections reached")
                await websocket.close(code=1013, reason="Server at capacity")
                return
            # Enforce per-IP cap if configured
            if self.config.ws_max_connections_per_ip > 0:
                count = self._ip_connection_counts.get(client_ip, 0)
                if count >= self.config.ws_max_connections_per_ip:
                    # Record rejection metric
                    try:
                        bucket = self._ip_bucket(client_ip)
                        get_metrics_collector().record_ws_rejection("per_ip_cap", bucket)
                    except Exception:
                        pass
                    await websocket.close(code=1013, reason="Too many connections from IP")
                    return
            # Reserve a slot for this IP before accepting to avoid race conditions
            self._ip_connection_counts[client_ip] = self._ip_connection_counts.get(client_ip, 0) + 1
            accepted = False
            try:
                # Accept connection
                await websocket.accept()
                accepted = True
            except Exception:
                # Roll back reserved slot on accept failure
                try:
                    if client_ip in self._ip_connection_counts and self._ip_connection_counts[client_ip] > 0:
                        self._ip_connection_counts[client_ip] -= 1
                        if self._ip_connection_counts[client_ip] == 0:
                            del self._ip_connection_counts[client_ip]
                except Exception:
                    pass
                raise

            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                connection_id=connection_id,
                client_id=client_id,
                user_id=user_id,
                metadata=metadata
            )

            self.connections[connection_id] = connection
            # per-IP count already reserved; nothing to do here
            # Update connection gauge
            try:
                get_metrics_collector().update_connection_count("websocket", len(self.connections))
            except Exception:
                pass

        logger.bind(connection_id=connection_id, user_id=user_id, client_id=client_id, client_ip=client_ip).info(
            f"WebSocket connected: {connection_id} (client={client_id}, user={user_id}, ip={client_ip})"
        )

        try:
            # Start ping task
            ping_task = asyncio.create_task(
                self._websocket_ping_loop(connection)
            )

            # Handle messages
            await self._handle_websocket_messages(connection)

        except WebSocketDisconnect:
            logger.bind(connection_id=connection_id).info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.bind(connection_id=connection_id).error(f"WebSocket error for {connection_id}: {e}")
            await connection.close(code=1011, reason="Internal error")
            try:
                get_metrics_collector().record_connection_error("websocket", "exception")
            except Exception:
                pass
        finally:
            # Cancel ping task
            ping_task.cancel()

            # Remove connection
            async with self.connection_lock:
                if connection_id in self.connections:
                    del self.connections[connection_id]
                # Decrement per-IP count
                try:
                    if client_ip in self._ip_connection_counts and self._ip_connection_counts[client_ip] > 0:
                        self._ip_connection_counts[client_ip] -= 1
                        if self._ip_connection_counts[client_ip] == 0:
                            del self._ip_connection_counts[client_ip]
                except Exception:
                    pass

            logger.bind(connection_id=connection_id).info(f"WebSocket cleanup complete: {connection_id}")
            # Update connection gauge
            try:
                get_metrics_collector().update_connection_count("websocket", len(self.connections))
            except Exception:
                pass

    async def _websocket_ping_loop(self, connection: WebSocketConnection):
        """Send periodic pings to keep connection alive"""
        while True:
            try:
                await asyncio.sleep(self.config.ws_ping_interval)
                # Idle timeout enforcement
                try:
                    idle_seconds = (datetime.now(timezone.utc) - connection.last_activity).total_seconds()
                    if self.config.ws_idle_timeout_seconds and idle_seconds > max(5, int(self.config.ws_idle_timeout_seconds)):
                        try:
                            get_metrics_collector().record_ws_session_closure("idle")
                        except Exception:
                            pass
                        await connection.close(code=1001, reason="Idle timeout")
                        break
                except Exception:
                    pass
                await connection.websocket.send_json({"type": "ping"})
            except Exception:
                try:
                    get_metrics_collector().record_connection_error("websocket", "ping_failure")
                except Exception:
                    pass
                break

    async def _handle_websocket_messages(self, connection: WebSocketConnection):
        """Handle incoming WebSocket messages"""
        while True:
            # Receive message
            try:
                data = await connection.receive_json()
            except json.JSONDecodeError as e:
                await connection.send_json({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                })
                continue

            # Check message size
            message_size = len(json.dumps(data))
            if message_size > self.config.ws_max_message_size:
                await connection.send_json({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Message too large"
                    },
                    "id": data.get("id") if isinstance(data, dict) else None
                })
                continue

            # Handle ping/pong
            if isinstance(data, dict) and data.get("type") == "pong":
                continue

            # Per-session rate limit: requests per window
            try:
                now_ts = datetime.now(timezone.utc).timestamp()
                connection.request_times.append(now_ts)
                window = max(1, int(self.config.ws_session_rate_limit_window_seconds))
                threshold = max(1, int(self.config.ws_session_rate_limit_count))
                # Prune
                while connection.request_times and (now_ts - connection.request_times[0]) > window:
                    connection.request_times.popleft()
                if len(connection.request_times) > threshold:
                    await connection.send_json({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32002,
                            "message": "Session rate limit exceeded"
                        },
                        "id": data.get("id") if isinstance(data, dict) else None
                    })
                    try:
                        get_metrics_collector().record_ws_session_closure("session_rate")
                    except Exception:
                        pass
                    await connection.close(code=1013, reason="Session rate limit exceeded")
                    break
            except Exception:
                pass

            # Ensure session exists and update with client/safe config if applicable
            try:
                sess = await self._get_or_create_session(connection.connection_id)
                # If this is initialize, capture clientInfo and optional config
                if isinstance(data, dict) and data.get("method") == "initialize":
                    try:
                        params = data.get("params") or {}
                        client_info = params.get("clientInfo") or {}
                        if isinstance(client_info, dict):
                            sess.client_info.update(client_info)
                        # Optional config param for WS (either dict or base64-encoded JSON)
                        cfg = params.get("config")
                        safe_incoming: Dict[str, Any] = {}
                        if isinstance(cfg, dict):
                            safe_incoming = cfg
                        elif isinstance(cfg, str):
                            import base64, json as _json
                            try:
                                decoded = base64.b64decode(cfg).decode("utf-8")
                                safe_incoming = _json.loads(decoded)
                            except Exception:
                                safe_incoming = {}
                        if safe_incoming:
                            sess.safe_config = self._merge_safe_config(sess.safe_config, safe_incoming)
                    except Exception:
                        pass
                sess.touch()
            except Exception:
                pass

            # Create request context
            context = RequestContext(
                request_id=data.get("id", "unknown") if isinstance(data, dict) else "unknown",
                user_id=connection.user_id,
                client_id=connection.client_id,
                session_id=connection.connection_id,
                metadata=connection.metadata
            )

            # Process MCP request (supports single, notification, and batch)
            try:
                response = await self.protocol.process_request(data, context)
                if response is None:
                    # Notification - no reply
                    continue
                if isinstance(response, list):
                    await connection.send_json([r.model_dump() for r in response])
                else:
                    await connection.send_json(response.model_dump())
            except RateLimitExceeded as e:
                await connection.send_json({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32002,
                        "message": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                        "data": {
                            "hint": "Reduce request frequency or wait before retrying."
                        }
                    },
                    "id": data.get("id") if isinstance(data, dict) else None
                })
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {self._mask_secrets(str(e))}")
                await connection.send_json({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error"
                    },
                    "id": data.get("id") if isinstance(data, dict) else None
                })

    def _ip_bucket(self, ip: str) -> str:
        """Return a coarse bucket label for an IP to avoid high-cardinality metrics."""
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_loopback:
                return "loopback"
            if ip_obj.is_private:
                return "private"
            if ip_obj.is_link_local:
                return "link_local"
            if ip_obj.is_reserved:
                return "reserved"
            return "public"
        except Exception:
            return "unknown"

    async def handle_http_request(
        self,
        request: MCPRequest,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Handle an HTTP MCP request.

        Args:
            request: MCP request
            client_id: Optional client identifier
            user_id: Optional user identifier (from auth)

        Returns:
            MCP response
        """
        # Pull session_id and safe_config from metadata when present
        session_id: Optional[str] = None
        safe_cfg: Dict[str, Any] = {}
        try:
            if metadata:
                raw_sid = metadata.get("session_id")
                if isinstance(raw_sid, str) and raw_sid:
                    session_id = raw_sid
                sc = metadata.get("safe_config")
                if isinstance(sc, dict):
                    safe_cfg = sc
        except Exception:
            session_id = None
            safe_cfg = {}

        # If we have a session id, ensure session exists and merge safe config
        try:
            if session_id:
                sess = await self._get_or_create_session(session_id)
                if safe_cfg:
                    sess.safe_config = self._merge_safe_config(sess.safe_config, safe_cfg)
                # If initialize, capture clientInfo
                if request.method == "initialize" and isinstance(request.params, dict):
                    ci = (request.params or {}).get("clientInfo")
                    if isinstance(ci, dict):
                        sess.client_info.update(ci)
                sess.touch()
        except Exception:
            pass

        # Create request context
        context = RequestContext(
            request_id=request.id or "http_request",
            user_id=user_id,
            client_id=client_id,
            session_id=session_id,
            metadata=metadata or {}
        )

        # Process request
        try:
            response = await self.protocol.process_request(request, context)
            return response
        except RateLimitExceeded as e:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Rate limit exceeded. Retry after {e.retry_after} seconds",
                    "hint": "Throttle tool calls or wait for the cooldown before retrying."
                }
            )
        except Exception as e:
            logger.error(f"Error processing HTTP request: {self._mask_secrets(str(e))}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def _close_all_connections(self):
        """Close all WebSocket connections"""
        async with self.connection_lock:
            tasks = []
            for connection in self.connections.values():
                tasks.append(
                    connection.close(code=1001, reason="Server shutdown")
                )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self.connections.clear()

    async def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        uptime = (datetime.now(timezone.utc) - self.startup_time).total_seconds()

        # Get module health
        health_results = await self.module_registry.check_all_health()

        # Get connection stats
        connection_stats = {
            "total": len(self.connections),
            "authenticated": sum(1 for c in self.connections.values() if c.user_id),
            "anonymous": sum(1 for c in self.connections.values() if not c.user_id)
        }

        return {
            "status": "healthy" if self.initialized else "initializing",
            "version": "3.0.0",
            "uptime_seconds": uptime,
            "connections": connection_stats,
            "modules": {
                "total": len(health_results),
                "healthy": sum(1 for h in health_results.values() if h.is_healthy),
                "degraded": sum(1 for h in health_results.values() if h.is_operational and not h.is_healthy),
                "unhealthy": sum(1 for h in health_results.values() if not h.is_operational)
            }
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Get server metrics"""
        # Collect module metrics
        module_metrics = {}
        modules = await self.module_registry.get_all_modules()

        for module_id, module in modules.items():
            metrics = module.get_metrics()
            module_metrics[module_id] = {
                "requests": metrics.total_requests,
                "errors": metrics.failed_requests,
                "error_rate": metrics.error_rate,
                "avg_latency_ms": metrics.avg_latency_ms
            }

        # Connection metrics
        total_messages = sum(c.message_count for c in self.connections.values())
        total_errors = sum(c.error_count for c in self.connections.values())

        return {
            "connections": {
                "active": len(self.connections),
                "total_messages": total_messages,
                "total_errors": total_errors
            },
            "modules": module_metrics
        }


# Singleton instance management
_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create MCP server singleton"""
    global _server
    if _server is None:
        _server = MCPServer()
    return _server


async def reset_mcp_server() -> None:
    """Reset MCP server singleton for test environments."""
    global _server
    if _server is not None:
        try:
            await _server.shutdown()
        except Exception:
            pass
    _server = None
    try:
        from .modules.registry import reset_module_registry
        await reset_module_registry()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app):
    """
    FastAPI lifespan manager for server initialization and shutdown.

    Usage in main.py:
    ```python
    from tldw_Server_API.app.core.MCP_unified.server import lifespan

    app = FastAPI(lifespan=lifespan)
    ```
    """
    # Startup
    server = get_mcp_server()
    await server.initialize()
    logger.info("MCP Server started")

    yield

    # Shutdown
    await server.shutdown()
    logger.info("MCP Server stopped")
