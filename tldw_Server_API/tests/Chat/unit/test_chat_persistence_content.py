import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequestMessageContentPartText,
)


@pytest.mark.asyncio
async def test_process_content_handles_pydantic_parts():
    part = ChatCompletionRequestMessageContentPartText(type="text", text="hello")

    text_parts, images = await chat_endpoint._process_content_for_db_sync([part], "conv-1")

    assert text_parts == ["hello"]
    assert images == []
