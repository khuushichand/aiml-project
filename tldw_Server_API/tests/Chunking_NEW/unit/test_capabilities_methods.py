import pytest
import asyncio

from tldw_Server_API.app.api.v1.endpoints.chunking import get_chunking_capabilities
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


@pytest.mark.asyncio
async def test_capabilities_includes_structure_aware():
    # Call the endpoint function directly with a stub user
    user = User(id=1, username="tester")
    data = await get_chunking_capabilities(current_user=user)  # type: ignore
    assert isinstance(data, dict)
    methods = data.get('methods') or []
    assert 'structure_aware' in methods

