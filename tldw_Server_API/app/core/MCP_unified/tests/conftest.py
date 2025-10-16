import contextlib
import pytest


async def _shutdown_server():
    from tldw_Server_API.app.core.MCP_unified import server as server_module

    server = getattr(server_module, "_server", None)
    if server is None:
        return

    with contextlib.suppress(Exception):
        await server.shutdown()
    server_module._server = None


async def _clear_module_registry():
    from tldw_Server_API.app.core.MCP_unified.modules import registry as registry_module

    registry = getattr(registry_module, "_module_registry", None)
    if registry is None:
        return

    with contextlib.suppress(Exception):
        await registry.shutdown_all()
    registry_module._module_registry = None


async def _stop_metrics():
    from tldw_Server_API.app.core.MCP_unified.monitoring import metrics as metrics_module

    collector = getattr(metrics_module, "_metrics_collector", None)
    if collector is None:
        return

    with contextlib.suppress(Exception):
        await collector.stop_collection()
    metrics_module._metrics_collector = None


def _reset_caches_and_singletons():
    from tldw_Server_API.app.core.MCP_unified import config as config_module
    from tldw_Server_API.app.core.MCP_unified.security import ip_filter
    from tldw_Server_API.app.core.MCP_unified.auth import jwt_manager, rate_limiter, rbac, authnz_rbac
    from tldw_Server_API.app.core.MCP_unified.modules import registry as registry_module
    from tldw_Server_API.app.core.Metrics import telemetry as telemetry_module
    from tldw_Server_API.app.core.AuthNZ import settings as auth_settings

    # Clear cached config and derived helpers
    get_config = getattr(config_module, "get_config", None)
    if get_config and hasattr(get_config, "cache_clear"):
        get_config.cache_clear()

    get_ip_controller = getattr(ip_filter, "get_ip_access_controller", None)
    if get_ip_controller and hasattr(get_ip_controller, "cache_clear"):
        get_ip_controller.cache_clear()

    map_to_perm = getattr(authnz_rbac, "_map_to_permission", None)
    if map_to_perm and hasattr(map_to_perm, "cache_clear"):
        map_to_perm.cache_clear()

    # Reset module-level singletons
    registry_module._module_registry = None
    jwt_manager._jwt_manager = None
    rate_limiter._rate_limiter = None
    rbac._rbac_policy = None
    authnz_rbac._authnz_rbac = None

    # Reset telemetry manager (used by protocol/request handling)
    with contextlib.suppress(Exception):
        telemetry_module.shutdown_telemetry()
    telemetry_module._telemetry_manager = None  # type: ignore[attr-defined]

    # Reset AuthNZ settings so per-test env vars take effect
    with contextlib.suppress(Exception):
        auth_settings.reset_settings()


async def _cleanup_mcp_state():
    await _shutdown_server()
    await _stop_metrics()
    await _clear_module_registry()
    _reset_caches_and_singletons()


@pytest.fixture(autouse=True)
async def isolate_mcp_state():
    await _cleanup_mcp_state()
    yield
    await _cleanup_mcp_state()
