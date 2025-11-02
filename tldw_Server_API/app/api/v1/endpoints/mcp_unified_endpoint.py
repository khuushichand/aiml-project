"""
Unified MCP API Endpoints

Production-ready endpoints for the unified MCP module with enhanced security and monitoring.
"""

import ipaddress
import os
import secrets
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, HTTPException, Depends, Query, Header, Security, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from tldw_Server_API.app.core.MCP_unified import (
    get_mcp_server,
    MCPRequest,
    MCPResponse,
    get_config
)
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import get_metrics_collector
from fastapi import Response
from tldw_Server_API.app.core.MCP_unified.auth import (
    JWTManager,
    UserRole,
    RBACPolicy
)
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import TokenData, get_jwt_manager
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode, get_settings
from tldw_Server_API.app.core.MCP_unified.security.request_guards import enforce_http_security

# Create router
router = APIRouter(prefix="/mcp", tags=["mcp-unified"])

# Security
security = HTTPBearer(auto_error=False)


# Request/Response models
class ServerStatusResponse(BaseModel):
    """Server status response"""
    status: str
    version: str
    uptime_seconds: float
    connections: Dict[str, int]
    modules: Dict[str, int]


class ServerMetricsResponse(BaseModel):
    """Server metrics response"""
    connections: Dict[str, Any]
    modules: Dict[str, Dict[str, Any]]


class ToolExecutionRequest(BaseModel):
    """Tool execution request"""
    tool_name: str = Field(..., min_length=1, max_length=100)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    """Tool execution response"""
    result: Any
    execution_time_ms: float
    module: str


class ModuleHealthResponse(BaseModel):
    """Module health response"""
    module_id: str
    status: str
    message: str
    checks: Dict[str, bool]
    metrics: Optional[Dict[str, Any]] = None


class AuthTokenRequest(BaseModel):
    """Authentication token request"""
    username: str
    password: Optional[str] = None
    api_key: Optional[str] = None


class AuthTokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


# Dependency functions

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    request: Request = None,
) -> Optional[TokenData]:
    """Get current user (AuthNZ JWT, MCP JWT, or API key)."""
    # Try AuthNZ JWT first (multi-user)
    try:
        if credentials and credentials.credentials:
            jwt_service = get_jwt_service()
            payload = jwt_service.decode_access_token(credentials.credentials)
            uid = str(payload.get("user_id") or payload.get("sub"))
            if uid:
                return TokenData(sub=uid, username=payload.get("username"), roles=[], permissions=[], token_type="access")
    except Exception as e:
        logger.debug(f"AuthNZ JWT check failed: {e}")

    # MCP JWT fallback
    try:
        if credentials and credentials.credentials:
            jwt_manager = get_jwt_manager()
            return jwt_manager.verify_token(credentials.credentials)
    except Exception as e:
        logger.debug(f"MCP token verification failed: {e}")

    # API key fallback
    try:
        if x_api_key:
            # Single-user mode: accept the configured SINGLE_USER_API_KEY directly
            try:
                if is_single_user_mode():
                    settings = get_settings()
                    if x_api_key == settings.SINGLE_USER_API_KEY:
                        return TokenData(
                            sub=str(settings.SINGLE_USER_FIXED_ID),
                            username="single_user",
                            roles=["admin"],
                            permissions=[],
                            token_type="access",
                        )
                    # TEST_MODE convenience: honor SINGLE_USER_TEST_API_KEY for deterministic automation
                    test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}
                    if test_mode:
                        allowed = {
                            os.getenv("SINGLE_USER_TEST_API_KEY", "test-api-key-12345"),
                            settings.SINGLE_USER_API_KEY,
                        }
                        if x_api_key in {a for a in allowed if a}:
                            return TokenData(
                                sub=str(settings.SINGLE_USER_FIXED_ID),
                                username="single_user",
                                roles=[UserRole.ADMIN.value],
                                permissions=["*"],
                                token_type="access",
                            )
            except Exception:
                # Fall through to multi-user API key validation
                pass
            api_mgr = await get_api_key_manager()
            client_ip = request.client.host if request and getattr(request, "client", None) else None
            info = await api_mgr.validate_api_key(x_api_key, ip_address=client_ip)
            if info and info.get("user_id"):
                return TokenData(sub=str(info["user_id"]), username=None, roles=["api_client"], permissions=[], token_type="access")
    except Exception as e:
        logger.debug(f"API key check failed: {e}")

    return None


async def require_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
) -> TokenData:
    """Require authenticated user"""
    if not credentials and not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Reuse get_current_user to resolve any auth form
    user = await get_current_user(credentials, x_api_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def require_admin(
    user: TokenData = Depends(require_user)
) -> TokenData:
    """Require admin role"""
    try:
        if is_single_user_mode():
            return user
    except Exception:
        pass
    if UserRole.ADMIN.value not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return user


# WebSocket endpoint

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Client identifier"),
    token: Optional[str] = Query(None, description="Authentication token"),
    api_key: Optional[str] = Query(None, description="API key for authentication")
):
    """
    WebSocket endpoint for MCP protocol.

    Supports:
    - Full MCP protocol over WebSocket
    - Optional authentication via token parameter
    - Real-time bidirectional communication
    - Automatic reconnection support

    Example:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws?client_id=my-client&token=jwt-token');

    ws.onopen = () => {
        ws.send(JSON.stringify({
            jsonrpc: "2.0",
            method: "initialize",
            params: {
                clientInfo: {
                    name: "My Client",
                    version: "1.0.0"
                }
            },
            id: 1
        }));
    };
    ```
    """
    server = get_mcp_server()

    # Ensure server is initialized
    if not server.initialized:
        await server.initialize()

    # Handle WebSocket connection
    await server.handle_websocket(websocket, client_id=client_id, auth_token=token, api_key=api_key)


# HTTP endpoints

@router.post("/request", response_model=MCPResponse)
async def mcp_request(
    request: MCPRequest,
    client_id: Optional[str] = Query(None, description="Client identifier"),
    user: Optional[TokenData] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
    config: Optional[str] = Query(None, description="Base64-encoded JSON safe config for this request"),
    response: Response = None,
    _guard: None = Depends(enforce_http_security),
    http_request: Request = None,
):
    """
    Process an MCP request via HTTP.

    This endpoint provides a simpler alternative to WebSocket for clients
    that don't need real-time bidirectional communication.
    """
    server = get_mcp_server()

    # Ensure server is initialized
    if not server.initialized:
        await server.initialize()

    # Process request
    # Attach org/team metadata when auth via API key
    metadata: Dict[str, Any] = {}
    if x_api_key:
        try:
            api_mgr = await get_api_key_manager()
            client_ip = http_request.client.host if http_request and getattr(http_request, "client", None) else None
            info = await api_mgr.validate_api_key(x_api_key, ip_address=client_ip)
            if info:
                if info.get('org_id') is not None:
                    metadata['org_id'] = info.get('org_id')
                if info.get('team_id') is not None:
                    metadata['team_id'] = info.get('team_id')
        except Exception:
            pass

    # Derive user id with a robust single-user fallback
    derived_user_id: Optional[str] = user.sub if user else None
    if derived_user_id is None:
        try:
            if x_api_key and is_single_user_mode():
                settings = get_settings()
                if x_api_key == settings.SINGLE_USER_API_KEY:
                    derived_user_id = str(settings.SINGLE_USER_FIXED_ID)
        except Exception:
            pass

    # Parse optional safe config (base64-encoded JSON)
    safe_config: Dict[str, Any] = {}
    if config:
        try:
            import base64, json as _json
            decoded = base64.b64decode(config).decode("utf-8")
            cfg = _json.loads(decoded)
            if isinstance(cfg, dict):
                safe_config = cfg
        except Exception as e:
            logger.debug(f"Failed to parse safe config: {e}")

    # Session lifecycle: if initialize and no session id provided, generate one and return header
    try:
        if request.method == "initialize" and not mcp_session_id:
            import uuid as _uuid
            mcp_session_id = _uuid.uuid4().hex
            if response is not None:
                response.headers["mcp-session-id"] = mcp_session_id
    except Exception:
        pass

    if user:
        if user.roles:
            metadata.setdefault("roles", user.roles)
        if user.permissions:
            metadata.setdefault("permissions", user.permissions)
    elif derived_user_id is not None:
        try:
            if is_single_user_mode():
                metadata.setdefault("roles", [UserRole.ADMIN.value])
        except Exception:
            pass

    if mcp_session_id:
        metadata["session_id"] = mcp_session_id
    if safe_config:
        metadata["safe_config"] = safe_config

    resp_obj = await server.handle_http_request(
        request,
        client_id=client_id,
        user_id=derived_user_id,
        metadata=metadata or None
    )
    # Convert authorization errors to HTTP 403 with hint for HTTP clients
    if resp_obj.error and resp_obj.error.code == -32001:
        hint = None
        try:
            if request.method == "tools/call":
                tname = (request.params or {}).get("name") if isinstance(request.params, dict) else None
                if tname:
                    hint = f"Permission denied. Ask an admin to grant tools.execute:{tname} or tools.execute:* to your role (Admin → Access Control)."
        except Exception:
            hint = None
        raise HTTPException(status_code=403, detail={
            "message": resp_obj.error.message or "Insufficient permissions",
            "hint": hint or "Insufficient permissions for this operation"
        })

    return resp_obj


@router.post("/request/batch", response_model=list[MCPResponse])
async def mcp_request_batch(
    requests: list[MCPRequest],
    client_id: Optional[str] = Query(None, description="Client identifier"),
    user: Optional[TokenData] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
    config: Optional[str] = Query(None, description="Base64-encoded JSON safe config for this request"),
    response: Response = None,
    _guard: None = Depends(enforce_http_security),
    http_request: Request = None,
):
    """
    Process a batch of MCP requests via HTTP.
    Accepts a JSON array of JSON-RPC 2.0 requests and returns an array
    of responses. Notifications (no id) are dropped per spec.
    """
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    # Attach org/team metadata when auth via API key
    metadata: Dict[str, Any] = {}
    if x_api_key:
        try:
            api_mgr = await get_api_key_manager()
            client_ip = http_request.client.host if http_request and getattr(http_request, "client", None) else None
            info = await api_mgr.validate_api_key(x_api_key, ip_address=client_ip)
            if info:
                if info.get('org_id') is not None:
                    metadata['org_id'] = info.get('org_id')
                if info.get('team_id') is not None:
                    metadata['team_id'] = info.get('team_id')
        except Exception as e:
            logger.debug(f"Batch API key metadata attach failed: {e}")

    # Derive user id with a robust single-user fallback
    derived_user_id: Optional[str] = user.sub if user else None
    if derived_user_id is None:
        try:
            if x_api_key and is_single_user_mode():
                settings = get_settings()
                if x_api_key == settings.SINGLE_USER_API_KEY:
                    derived_user_id = str(settings.SINGLE_USER_FIXED_ID)
        except Exception:
            pass

    # Optional safe config
    safe_config: Dict[str, Any] = {}
    if config:
        try:
            import base64, json as _json
            decoded = base64.b64decode(config).decode("utf-8")
            cfg = _json.loads(decoded)
            if isinstance(cfg, dict):
                safe_config = cfg
        except Exception as e:
            logger.debug(f"Batch failed to parse safe config: {e}")

    # Build context and process via protocol directly to leverage batch support
    if user:
        if user.roles:
            metadata.setdefault("roles", user.roles)
        if user.permissions:
            metadata.setdefault("permissions", user.permissions)
    elif derived_user_id is not None:
        try:
            if is_single_user_mode():
                metadata.setdefault("roles", [UserRole.ADMIN.value])
        except Exception:
            pass

    ctx = RequestContext(
        request_id="http_batch",
        user_id=derived_user_id,
        client_id=client_id,
        session_id=mcp_session_id,
        metadata={**metadata, **({"safe_config": safe_config} if safe_config else {})},
    )
    payload = [r.model_dump() for r in requests]
    resp = await server.protocol.process_request(payload, ctx)
    # If only notifications were sent, return empty list
    if resp is None:
        return []
    return resp


@router.get("/status", response_model=ServerStatusResponse)
async def get_server_status(
    _guard: None = Depends(enforce_http_security),
):
    """
    Get MCP server status.

    Returns:
    - Server health status
    - Uptime
    - Connection statistics
    - Module health summary
    """
    server = get_mcp_server()

    # Ensure server is initialized
    if not server.initialized:
        await server.initialize()

    status = await server.get_status()
    return ServerStatusResponse(**status)


@router.get("/metrics", response_model=ServerMetricsResponse)
async def get_server_metrics(
    _: TokenData = Depends(require_admin),
    _guard: None = Depends(enforce_http_security),
):
    """
    Get detailed server metrics (requires admin).

    Returns:
    - Connection metrics
    - Module performance metrics
    - Error rates
    - Latency statistics
    """
    server = get_mcp_server()

    if not server.initialized:
        await server.initialize()

    metrics = await server.get_metrics()
    return ServerMetricsResponse(**metrics)


@router.get("/metrics/prometheus")
async def get_prometheus_metrics(
    credentials: HTTPAuthorizationCredentials = Security(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    _guard: None = Depends(enforce_http_security),
):
    """
    Prometheus scrape endpoint for MCP metrics.

    Security: By default, requires admin authentication. Set MCP_PROMETHEUS_PUBLIC=1
    to allow unauthenticated internal-only scraping. When public, ensure it is
    exposed only on trusted networks or behind an ingress/proxy that enforces
    authentication in production environments.
    """
    import os
    public = os.getenv("MCP_PROMETHEUS_PUBLIC", "").lower() in {"1", "true", "yes"}
    if not public:
        # Require admin
        user = await get_current_user(credentials, x_api_key)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        try:
            if is_single_user_mode():
                pass
            else:
                if UserRole.ADMIN.value not in (user.roles or []):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        except Exception:
            # If settings not available, fall back to role check only
            if UserRole.ADMIN.value not in (user.roles or []):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    collector = get_metrics_collector()
    content = collector.get_prometheus_metrics()
    # Use standard Prometheus content type regardless of availability
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get(
    "/tools",
    summary="List MCP tools",
    description=(
        "List available MCP tools. Tools are filtered by RBAC; catalog filters shape discovery only.\n\n"
        "Parameters:\n"
        "- `module`: Filter by module id.\n"
        "- `catalog`: Filter by tool catalog name. The server resolves the name with precedence\n"
        "  `team > org > global` based on the authenticated context (API key or JWT). When both\n"
        "  `catalog` and `catalog_id` are provided, `catalog_id` takes precedence.\n"
        "- `catalog_id`: Filter by tool catalog id directly.\n\n"
        "Behavior:\n"
        "- If the catalog name/id cannot be resolved, the server fails open (no catalog filter),\n"
        "  but RBAC is still enforced.\n"
        "- `canExecute` reflects the caller's permissions. Catalog membership does not grant\n"
        "  execution rights; it only affects discovery."
    ),
)
async def list_tools(
    module: Optional[str] = Query(None, description="Filter by module"),
    catalog: Optional[str] = Query(None, description="Filter by tool catalog name"),
    catalog_id: Optional[int] = Query(None, description="Filter by tool catalog id"),
    user: Optional[TokenData] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    _guard: None = Depends(enforce_http_security),
):
    """
    List available MCP tools.

    Returns tools with their descriptions and required parameters.
    Tools are filtered based on user permissions if authenticated.
    """
    params: Dict[str, Any] = {}
    if module:
        params["module"] = module
    if catalog is not None:
        params["catalog"] = catalog
    if catalog_id is not None:
        params["catalog_id"] = catalog_id
    request = MCPRequest(method="tools/list", params=params, id="http-tools-list")

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    # Derive user id with a robust single-user fallback
    derived_user_id: Optional[str] = user.sub if user else None
    if derived_user_id is None:
        try:
            if x_api_key and is_single_user_mode():
                settings = get_settings()
                if x_api_key == settings.SINGLE_USER_API_KEY:
                    derived_user_id = str(settings.SINGLE_USER_FIXED_ID)
        except Exception:
            pass

    metadata: Dict[str, Any] = {}
    if user:
        if user.roles:
            metadata["roles"] = user.roles
        if user.permissions:
            metadata["permissions"] = user.permissions
    elif derived_user_id is not None:
        try:
            if is_single_user_mode():
                metadata["roles"] = [UserRole.ADMIN.value]
        except Exception:
            pass

    response = await server.handle_http_request(
        request,
        user_id=derived_user_id,
        metadata=metadata or None
    )

    if response.error:
        if response.error.code == -32001:
            raise HTTPException(status_code=403, detail={
                "message": response.error.message or "Insufficient permissions",
                "hint": "Permission denied for listing tools. Contact an admin."
            })
        raise HTTPException(status_code=500, detail=response.error.message)

    return response.result


@router.post("/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    user: TokenData = Depends(require_user),
    _guard: None = Depends(enforce_http_security),
):
    """
    Execute a specific tool (requires authentication).

    Tools are executed with user context for permission checking.
    """
    import time
    start_time = time.time()

    mcp_request = MCPRequest(
        method="tools/call",
        params={
            "name": request.tool_name,
            "arguments": request.arguments
        },
        id=f"http-tools-execute:{request.tool_name}"
    )

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    metadata: Dict[str, Any] = {}
    if user.roles:
        metadata["roles"] = user.roles
    if user.permissions:
        metadata["permissions"] = user.permissions

    response = await server.handle_http_request(
        mcp_request,
        user_id=user.sub,
        metadata=metadata or None
    )

    if response is None:
        logger.error("MCP server returned no response for tools/call", tool=request.tool_name)
        raise HTTPException(status_code=502, detail="MCP tool execution returned no response")

    if response.error:
        # Map authorization failures to 403 with a helpful hint
        if response.error.code == -32001:  # AUTHORIZATION_ERROR
            hint = {
                "message": response.error.message or "Insufficient permissions",
                "hint": (
                    f"Permission denied. Ask an admin to grant tools.execute:{request.tool_name} "
                    f"or tools.execute:* to your role (Admin → Access Control)."
                )
            }
            raise HTTPException(status_code=403, detail=hint)
        # Invalid params
        if response.error.code == -32602:
            raise HTTPException(status_code=400, detail=response.error.message)
        # Other errors
        raise HTTPException(status_code=500, detail=response.error.message)

    execution_time = (time.time() - start_time) * 1000

    result_payload = response.result
    # Back-compat: unwrap plain text content to raw string when possible
    display_result = result_payload
    try:
        if isinstance(result_payload, dict):
            content = result_payload.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str):
                    display_result = first.get("text")
    except Exception:
        display_result = result_payload

    served_by = None
    try:
        if isinstance(result_payload, dict):
            served_by = result_payload.get("module")
    except Exception:
        served_by = None

    return ToolExecutionResponse(
        result=display_result,
        execution_time_ms=execution_time,
        module=served_by or "unknown"
    )


@router.get("/modules")
async def list_modules(
    user: Optional[TokenData] = Depends(get_current_user),
    _guard: None = Depends(enforce_http_security),
):
    """
    List registered MCP modules.

    Returns module information including status and capabilities.
    """
    request = MCPRequest(method="modules/list", id="http-modules-list")

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    metadata: Dict[str, Any] = {}
    if user:
        if user.roles:
            metadata["roles"] = user.roles
        if user.permissions:
            metadata["permissions"] = user.permissions
    else:
        try:
            if is_single_user_mode():
                metadata["roles"] = [UserRole.ADMIN.value]
        except Exception:
            pass

    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None,
        metadata=metadata or None
    )

    if response.error:
        if response.error.code == -32001:
            raise HTTPException(status_code=403, detail={
                "message": response.error.message or "Insufficient permissions",
                "hint": "Permission denied for listing tools. Contact an admin."
            })
        raise HTTPException(status_code=500, detail=response.error.message)

    return response.result


@router.get("/modules/health")
async def get_modules_health(
    user: TokenData = Depends(require_admin),
    _guard: None = Depends(enforce_http_security),
):
    """
    Get detailed health status of all modules (requires admin).

    Returns health checks and metrics for each module.
    """
    request = MCPRequest(method="modules/health", id="http-modules-health")

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    meta: Dict[str, Any] = {"admin_override": True}
    if user.roles:
        meta["roles"] = user.roles
    if user.permissions:
        meta["permissions"] = user.permissions

    response = await server.handle_http_request(request, user_id=user.sub, metadata=meta)

    if response.error:
        if response.error.code == -32001:
            raise HTTPException(status_code=403, detail={
                "message": response.error.message or "Insufficient permissions",
                "hint": "Permission denied for listing modules. Contact an admin."
            })
        raise HTTPException(status_code=500, detail=response.error.message)

    return response.result


@router.get("/resources")
async def list_resources(
    user: Optional[TokenData] = Depends(get_current_user),
    _guard: None = Depends(enforce_http_security),
):
    """
    List available MCP resources.

    Resources are filtered based on user permissions if authenticated.
    """
    request = MCPRequest(method="resources/list", id="http-resources-list")

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    metadata: Dict[str, Any] = {}
    if user:
        if user.roles:
            metadata["roles"] = user.roles
        if user.permissions:
            metadata["permissions"] = user.permissions
    else:
        try:
            if is_single_user_mode():
                metadata["roles"] = [UserRole.ADMIN.value]
        except Exception:
            pass

    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None,
        metadata=metadata or None
    )

    if response.error:
        if response.error.code == -32001:
            raise HTTPException(status_code=403, detail={
                "message": response.error.message or "Insufficient permissions",
                "hint": "Permission denied for listing resources. Contact an admin."
            })
        raise HTTPException(status_code=500, detail=response.error.message)

    return response.result


@router.get("/prompts")
async def list_prompts(
    user: Optional[TokenData] = Depends(get_current_user),
    _guard: None = Depends(enforce_http_security),
):
    """
    List available MCP prompts.

    Prompts are filtered based on user permissions if authenticated.
    """
    request = MCPRequest(method="prompts/list", id="http-prompts-list")

    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()

    metadata: Dict[str, Any] = {}
    if user:
        if user.roles:
            metadata["roles"] = user.roles
        if user.permissions:
            metadata["permissions"] = user.permissions
    else:
        try:
            if is_single_user_mode():
                metadata["roles"] = [UserRole.ADMIN.value]
        except Exception:
            pass

    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None,
        metadata=metadata or None
    )

    if response.error:
        if response.error.code == -32001:
            raise HTTPException(status_code=403, detail={
                "message": response.error.message or "Insufficient permissions",
                "hint": "Permission denied for listing prompts. Contact an admin."
            })
        raise HTTPException(status_code=500, detail=response.error.message)

    return response.result


# Authentication endpoints

@router.post("/auth/token", response_model=AuthTokenResponse)
async def create_token(
    auth_request: AuthTokenRequest,
    request: Request,
    _guard: None = Depends(enforce_http_security),
):
    """
    Issue an MCP access token.

    Note: Direct username/password authentication for MCP is disabled by default.
    Use the primary AuthNZ login flow to obtain a JWT, or enable this endpoint
    explicitly via MCP_ENABLE_DEMO_AUTH=1 for development/testing only.
    """
    if os.getenv("MCP_ENABLE_DEMO_AUTH", "").lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Direct MCP auth is disabled. Use AuthNZ bearer tokens.",
        )

    cfg = get_config()
    test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes"}
    if not cfg.debug_mode and not test_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo auth is restricted to debug/test environments.",
        )

    demo_secret = os.getenv("MCP_DEMO_AUTH_SECRET", "")
    if len(demo_secret) < 16:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Demo auth secret not configured; set MCP_DEMO_AUTH_SECRET to enable.",
        )

    client_host = getattr(request.client, "host", None)
    try:
        peer_ip = ipaddress.ip_address(client_host) if client_host else None
    except ValueError:
        peer_ip = None
    if not peer_ip or (not peer_ip.is_loopback and not peer_ip.is_private):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo auth is only available from loopback/private addresses.",
        )

    provided_secret = auth_request.api_key or auth_request.password or ""
    if not provided_secret or not secrets.compare_digest(provided_secret, demo_secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid demo auth secret.",
        )

    allowed_user = os.getenv("MCP_DEMO_AUTH_USER", "admin")
    username = auth_request.username or allowed_user
    if username != allowed_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid demo auth username.",
        )

    subject = os.getenv("MCP_DEMO_AUTH_SUBJECT", "admin_user")
    jwt_manager = get_jwt_manager()
    access_token = jwt_manager.create_access_token(
        subject=subject,
        username=username,
        roles=[UserRole.ADMIN.value],
        permissions=["*"],
    )
    refresh_token, _ = jwt_manager.create_refresh_token(subject)

    logger.warning(
        "Issued demo MCP token for development/testing use only.",
        extra={"audit": True, "client_ip": str(peer_ip)},
    )

    return AuthTokenResponse(
        access_token=access_token,
        expires_in=jwt_manager.config.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_token,
    )


@router.post("/auth/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token"),
    token_id: Optional[str] = Query(None, description="Refresh token id (if available)"),
    _guard: None = Depends(enforce_http_security),
):
    """
    Refresh authentication token.

    Exchange a valid refresh token for a new access token using rotation.
    If `token_id` is not provided, the system attempts to locate it by scanning
    active refresh tokens (acceptable for in-memory DEV mode).
    """
    jwt_manager = get_jwt_manager()
    # Attempt to find token_id if not provided
    resolved_token_id = token_id
    try:
        if not resolved_token_id:
            # Scan in-memory store (DEV): find first token_id matching token
            for tid, rt in jwt_manager._refresh_tokens.items():  # noqa: SLF001
                if rt.token == refresh_token and not rt.revoked:
                    resolved_token_id = tid
                    break
    except Exception:
        resolved_token_id = token_id

    if not resolved_token_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        new_access, new_refresh, new_tid = jwt_manager.rotate_refresh_token(refresh_token, resolved_token_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh token rotation failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to refresh token")

    return AuthTokenResponse(
        access_token=new_access,
        expires_in=jwt_manager.config.jwt_access_token_expire_minutes * 60,
        refresh_token=new_refresh,
    )


# Health check endpoint

@router.get("/health")
async def health_check(
    _guard: None = Depends(enforce_http_security),
):
    """
    Health check endpoint for load balancers.

    Returns 200 if server is healthy, 503 if not.
    """
    server = get_mcp_server()

    if not server.initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server not initialized"
        )

    status = await server.get_status()

    if status["status"] != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Server status: {status['status']}"
        )

    return {"status": "healthy"}


# OpenAPI documentation customization

def customize_openapi():
    """Customize OpenAPI schema for better documentation"""
    from fastapi.openapi.utils import get_openapi

    def custom_openapi():
        if router.openapi_schema:
            return router.openapi_schema

        openapi_schema = get_openapi(
            title="MCP Unified API",
            version="3.0.0",
            description="""
            # Model Context Protocol (MCP) Unified API

            Production-ready MCP implementation with enhanced security and monitoring.

            ## Features
            - 🔒 **Secure by Default**: JWT authentication, RBAC, rate limiting
            - 🚀 **High Performance**: Connection pooling, caching, circuit breakers
            - 📊 **Observable**: Health checks, metrics, distributed tracing
            - 🔧 **Modular**: Extensible module system with hot-reload

            ## Authentication
            Most endpoints support optional authentication via Bearer token.
            Some endpoints require authentication or admin role.

            ## WebSocket
            The `/ws` endpoint provides full MCP protocol support over WebSocket.
            """,
            routes=router.routes,
        )

        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }

        router.openapi_schema = openapi_schema
        return router.openapi_schema

    return custom_openapi


router.openapi = customize_openapi()
