import pytest
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager
from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import refresh_token as refresh_endpoint
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_refresh_token_rotation_flow():
    mgr = get_jwt_manager()
    # Create initial refresh token
    refresh, token_id = mgr.create_refresh_token(subject="u1")
    # Rotate
    resp = await refresh_endpoint(refresh_token=refresh, token_id=token_id)  # type: ignore[arg-type]
    assert resp.access_token and isinstance(resp.access_token, str)
    assert resp.refresh_token and isinstance(resp.refresh_token, str)
    # Old should be revoked after rotation
    with pytest.raises(HTTPException):
        await refresh_endpoint(refresh_token=refresh, token_id=token_id)  # type: ignore[arg-type]
