"""
MCP Protocol implementation for unified module

Implements JSON-RPC 2.0 with enhanced error handling and request routing.
"""

import uuid
import json
from typing import Dict, Any, Optional, List, Union, Callable, Literal, Tuple
from datetime import datetime, timezone
from enum import IntEnum
from pydantic import BaseModel, Field, validator
from loguru import logger

from .modules.registry import get_module_registry
import inspect
from .auth.authnz_rbac import get_rbac_policy, Resource, Action
from .auth.rate_limiter import get_rate_limiter, RateLimitExceeded
import time
from .monitoring.metrics import get_metrics_collector
from tldw_Server_API.app.core.Metrics.telemetry import get_telemetry_manager
import re


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


class MCPRequest(BaseModel):
    """MCP request following JSON-RPC 2.0 specification"""
    jsonrpc: Literal["2.0"] = Field(default="2.0")
    method: str = Field(..., min_length=1, max_length=100)
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    
    @validator("method")
    def validate_method(cls, v):
        """Validate method name"""
        # Prevent potential injection attacks
        if any(char in v for char in ["'", '"', ';', '--', '/*', '*/']):
            raise ValueError("Invalid characters in method name")
        return v
    
    @validator("params")
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
    
    @validator("error")
    def validate_error_result(cls, v, values):
        """Ensure either result or error is set, not both"""
        if v is not None and values.get("result") is not None:
            raise ValueError("Response cannot have both result and error")
        return v


class RequestContext:
    """Context for request processing"""
    def __init__(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.client_id = client_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.start_time = datetime.now(timezone.utc)
        # Derive per-user db paths (read-only) if possible
        self.db_paths: Dict[str, str] = {}
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
        
        # Method handlers
        self.handlers: Dict[str, Callable] = {
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
    
    async def process_request(
        self,
        request: Union[Dict[str, Any], List[Dict[str, Any]], MCPRequest],
        context: Optional[RequestContext] = None
    ) -> Union[MCPResponse, List[MCPResponse], None]:
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
            responses: List[MCPResponse] = []
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
        # Log request
        log.info(
            f"MCP request: method={request.method}, user={context.user_id}, client={context.client_id}",
            extra={"audit": True}
        )
        
        start_ts = time.time()
        try:
            # Check rate limit
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
                    if not isinstance(_name, str) or not self._tool_name_re.match(_name):
                        return self._error_response(
                            ErrorCode.INTERNAL_ERROR,
                            "Invalid tool name",
                            request.id
                        )
            except Exception:
                return self._error_response(ErrorCode.INTERNAL_ERROR, "Invalid tool name", request.id)

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
        except Exception as e:
            # Log error
            log.error(
                f"MCP request failed: method={request.method}, error={str(e)}",
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
            # Return error response
            return self._error_response(ErrorCode.INTERNAL_ERROR, str(e), request.id if isinstance(request, MCPRequest) else None)
    
    def _error_response(
        self,
        code: ErrorCode,
        message: str,
        request_id: Optional[Union[str, int]] = None,
        data: Optional[Any] = None
    ) -> MCPResponse:
        """Create an error response"""
        return MCPResponse(
            error=MCPError(
                code=code,
                message=message,
                data=data
            ),
            id=request_id
        )
    
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
            return bool(context.user_id)

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
                return await fn(context.user_id, resource, action, resource_id)
            return fn(context.user_id, resource, action, resource_id)
        
        # Unknown method - deny by default
        return False
    
    # Protocol method handlers
    
    async def _handle_initialize(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
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
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """Handle ping request"""
        return {"pong": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    async def _handle_tools_list(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """List available tools"""
        tools = []
        modules = await self.module_registry.get_all_modules()
        
        for module_id, module in modules.items():
            try:
                module_tools = await module.get_tools()
                
                # Add module context to each tool
                for tool in module_tools:
                    tool_copy = tool.copy()
                    tool_copy["module"] = module_id
                    
                    # Check if user can execute this tool
                    if context.user_id:
                        fn = getattr(self.rbac_policy, 'check_permission', None)
                        if fn:
                            if inspect.iscoroutinefunction(fn):
                                can_execute = await fn(context.user_id, Resource.TOOL, Action.EXECUTE, tool["name"])  # type: ignore
                            else:
                                can_execute = fn(context.user_id, Resource.TOOL, Action.EXECUTE, tool["name"])  # type: ignore
                        else:
                            can_execute = False
                        tool_copy["canExecute"] = can_execute
                    
                    tools.append(tool_copy)
                    
            except Exception as e:
                context.logger.error(f"Error getting tools from module {module_id}: {e}")
        
        return {"tools": tools}
    
    async def _handle_tools_call(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """Execute a tool"""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("Tool name is required")
        
        # Strictly validate tool name
        if not self._tool_name_re.match(tool_name):
            raise ValueError("Invalid tool name")
        
        # Find module for tool
        module = await self.module_registry.find_module_for_tool(tool_name)
        if not module:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Check specific tool permission
        if context.user_id:
            fn = getattr(self.rbac_policy, 'check_permission', None)
            if fn:
                permitted = await fn(context.user_id, Resource.TOOL, Action.EXECUTE, tool_name) if inspect.iscoroutinefunction(fn) else fn(context.user_id, Resource.TOOL, Action.EXECUTE, tool_name)
                if not permitted:
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

        # Optional per-tool/category rate limits (ingestion vs read)
        try:
            # Heuristic categorization
            cfg = get_config()
            category = None
            try:
                # Prefer config-driven mapping; fallback to heuristic
                if isinstance(cfg.tool_category_map, dict) and tool_name in cfg.tool_category_map:
                    category = str(cfg.tool_category_map.get(tool_name))
            except Exception:
                category = None
            if not category:
                ingestion_tools = {
                    'ingest_media', 'update_media', 'delete_media'
                }
                category = 'ingestion' if tool_name in ingestion_tools else 'read'
            key_owner = f"user:{context.user_id}" if context.user_id else (f"client:{context.client_id}" if context.client_id else "anon")
            rl_key = f"{key_owner}:tool:{tool_name}:cat:{category}"
            await self.rate_limiter.check_rate_limit(rl_key, limiter=self.rate_limiter.get_category_limiter(category))
        except RateLimitExceeded:
            raise
        except Exception:
            # Best-effort; do not block on limiter errors
            pass

        # Execute tool with circuit breaker (pass context through)
        t0 = time.time()
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
            else:
                content = [{"type": "text", "text": str(result)}]
            
            module_name = getattr(module, "name", None)
            # Record module operation metrics
            try:
                duration = max(0.0, time.time() - t0)
                self.metrics.record_module_operation(module=module_name or "unknown", operation="tools_call", duration=duration, success=True)
            except Exception:
                pass
            return {"content": content, "module": module_name, "tool": tool_name}
            
        except Exception as e:
            context.logger.error(f"Tool execution failed: {tool_name} - {e}")
            try:
                duration = max(0.0, time.time() - t0)
                self.metrics.record_module_operation(module=getattr(module, "name", "unknown"), operation="tools_call", duration=duration, success=False)
            except Exception:
                pass
            raise
    
    async def _handle_resources_list(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """List available resources"""
        resources = []
        modules = await self.module_registry.get_all_modules()
        
        for module_id, module in modules.items():
            try:
                module_resources = await module.get_resources()
                
                # Add module context
                for resource in module_resources:
                    resource_copy = resource.copy()
                    resource_copy["module"] = module_id
                    resources.append(resource_copy)
                    
            except Exception as e:
                context.logger.error(f"Error getting resources from module {module_id}: {e}")
        
        return {"resources": resources}
    
    async def _handle_resources_read(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """Read a resource"""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")
        
        # Find module for resource
        module = await self.module_registry.find_module_for_resource(uri)
        if not module:
            raise ValueError(f"Resource not found: {uri}")
        
        # Read resource
        content = await module.read_resource(uri)
        
        return {"contents": [content]}
    
    async def _handle_prompts_list(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """List available prompts"""
        prompts = []
        modules = await self.module_registry.get_all_modules()
        
        for module_id, module in modules.items():
            try:
                module_prompts = await module.get_prompts()
                
                # Add module context
                for prompt in module_prompts:
                    prompt_copy = prompt.copy()
                    prompt_copy["module"] = module_id
                    prompts.append(prompt_copy)
                    
            except Exception as e:
                context.logger.error(f"Error getting prompts from module {module_id}: {e}")
        
        return {"prompts": prompts}
    
    async def _handle_prompts_get(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """Get a specific prompt"""
        name = params.get("name")
        if not name:
            raise ValueError("Prompt name is required")
        
        arguments = params.get("arguments", {})
        
        # Find module for prompt
        module = await self.module_registry.find_module_for_prompt(name)
        if not module:
            raise ValueError(f"Prompt not found: {name}")
        
        # Get prompt
        prompt = await module.get_prompt(name, arguments)
        
        return prompt
    
    async def _handle_modules_list(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """List registered modules"""
        registrations = await self.module_registry.list_registrations()
        return {"modules": registrations}
    
    async def _handle_modules_health(
        self,
        params: Dict[str, Any],
        context: RequestContext
    ) -> Dict[str, Any]:
        """Get module health status"""
        health_results = await self.module_registry.check_all_health()
        
        # Convert to serializable format
        health_data = {}
        for module_id, health in health_results.items():
            health_data[module_id] = {
                "status": health.status.value,
                "message": health.message,
                "checks": health.checks,
                "last_check": health.last_check.isoformat()
            }
        
        return {"health": health_data}


# Convenience function
async def process_mcp_request(
    request: Union[Dict[str, Any], MCPRequest],
    context: Optional[RequestContext] = None
) -> MCPResponse:
    """Process an MCP request"""
    protocol = MCPProtocol()
    return await protocol.process_request(request, context)
