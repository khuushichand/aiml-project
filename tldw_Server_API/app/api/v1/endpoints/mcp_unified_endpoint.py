"""
Unified MCP API Endpoints

Production-ready endpoints for the unified MCP module with enhanced security and monitoring.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, HTTPException, Depends, Query, Header, Security, status
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
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
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
            except Exception:
                # Fall through to multi-user API key validation
                pass
            api_mgr = await get_api_key_manager()
            info = await api_mgr.validate_api_key(x_api_key)
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
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
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
    metadata = {}
    if x_api_key:
        try:
            api_mgr = await get_api_key_manager()
            info = await api_mgr.validate_api_key(x_api_key)
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

    response = await server.handle_http_request(
        request,
        client_id=client_id,
        user_id=derived_user_id,
        metadata=metadata or None
    )
    # Convert authorization errors to HTTP 403 with hint for HTTP clients
    if response.error and response.error.code == -32001:
        hint = None
        try:
            if request.method == "tools/call":
                tname = (request.params or {}).get("name") if isinstance(request.params, dict) else None
                if tname:
                    hint = f"Permission denied. Ask an admin to grant tools.execute:{tname} or tools.execute:* to your role (Admin → Access Control)."
        except Exception:
            hint = None
        raise HTTPException(status_code=403, detail={
            "message": response.error.message or "Insufficient permissions",
            "hint": hint or "Insufficient permissions for this operation"
        })

    return response


@router.post("/request/batch", response_model=list[MCPResponse])
async def mcp_request_batch(
    requests: list[MCPRequest],
    client_id: Optional[str] = Query(None, description="Client identifier"),
    user: Optional[TokenData] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
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
            info = await api_mgr.validate_api_key(x_api_key)
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

    # Build context and process via protocol directly to leverage batch support
    ctx = RequestContext(
        request_id="http_batch",
        user_id=derived_user_id,
        client_id=client_id,
        metadata=metadata,
    )
    payload = [r.model_dump() for r in requests]
    resp = await server.protocol.process_request(payload, ctx)
    # If only notifications were sent, return empty list
    if resp is None:
        return []
    return resp


@router.get("/status", response_model=ServerStatusResponse)
async def get_server_status():
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
    _: TokenData = Depends(require_admin)
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


@router.get("/tools")
async def list_tools(
    module: Optional[str] = Query(None, description="Filter by module"),
    user: Optional[TokenData] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
):
    """
    List available MCP tools.
    
    Returns tools with their descriptions and required parameters.
    Tools are filtered based on user permissions if authenticated.
    """
    request = MCPRequest(
        method="tools/list",
        params={"module": module} if module else {}
    )
    
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

    response = await server.handle_http_request(
        request,
        user_id=derived_user_id,
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
    user: TokenData = Depends(require_user)
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
        }
    )
    
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()
    
    response = await server.handle_http_request(
        mcp_request,
        user_id=user.sub
    )
    
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
    user: Optional[TokenData] = Depends(get_current_user)
):
    """
    List registered MCP modules.
    
    Returns module information including status and capabilities.
    """
    request = MCPRequest(method="modules/list")
    
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()
    
    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None
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
    _: TokenData = Depends(require_admin)
):
    """
    Get detailed health status of all modules (requires admin).
    
    Returns health checks and metrics for each module.
    """
    request = MCPRequest(method="modules/health")
    
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()
    
    response = await server.handle_http_request(request)
    
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
    user: Optional[TokenData] = Depends(get_current_user)
):
    """
    List available MCP resources.
    
    Resources are filtered based on user permissions if authenticated.
    """
    request = MCPRequest(method="resources/list")
    
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()
    
    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None
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
    user: Optional[TokenData] = Depends(get_current_user)
):
    """
    List available MCP prompts.
    
    Prompts are filtered based on user permissions if authenticated.
    """
    request = MCPRequest(method="prompts/list")
    
    server = get_mcp_server()
    if not server.initialized:
        await server.initialize()
    
    response = await server.handle_http_request(
        request,
        user_id=user.sub if user else None
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
    auth_request: AuthTokenRequest
):
    """
    Issue an MCP access token.

    Note: Direct username/password authentication for MCP is disabled by default.
    Use the primary AuthNZ login flow to obtain a JWT, or enable this endpoint
    explicitly via MCP_ENABLE_DEMO_AUTH=1 for development/testing only.
    """
    import os
    if os.getenv("MCP_ENABLE_DEMO_AUTH", "").lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Direct MCP auth is disabled. Use AuthNZ bearer tokens."
        )

    # Demo-only behavior (opt-in)
    jwt_manager = get_jwt_manager()
    if auth_request.username == "admin" and auth_request.password == "admin":
        access_token = jwt_manager.create_access_token(
            subject="admin_user",
            username="admin",
            roles=[UserRole.ADMIN.value],
            permissions=["*"]
        )
        refresh_token, _ = jwt_manager.create_refresh_token("admin_user")
        return AuthTokenResponse(
            access_token=access_token,
            expires_in=1800,
            refresh_token=refresh_token
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


@router.post("/auth/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token")
):
    """
    Refresh authentication token.
    
    Exchange a valid refresh token for a new access token.
    """
    # TODO: Implement token refresh
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented"
    )


# Health check endpoint

@router.get("/health")
async def health_check():
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
