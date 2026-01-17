"""
Simplified chat endpoint tests using real database and authentication.
"""

import pytest
from fastapi import status
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequest,
    ChatCompletionUserMessageParam,
)
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME


def test_chat_completion_basic(authenticated_client, mock_chacha_db, setup_dependencies):
    """Test basic chat completion with authenticated user."""

    # Prepare request data - must include api_provider
    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",  # Must specify provider
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello, how are you?")],
    )

    # Mock the LLM call and API keys
    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [
                {"message": {"role": "assistant", "content": "I'm doing well, thank you!"}, "finish_reason": "stop"}
            ],
        }

        # Make request
        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "I'm doing well, thank you!"

        # Verify LLM was called
        mock_llm.assert_called_once()


@pytest.mark.skip(reason="Streaming tests hang with TestClient")
def test_chat_completion_streaming(authenticated_client, mock_chacha_db):
    """Test streaming chat completion."""

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Tell me a story")],
        stream=True,
    )

    # Mock streaming response
    def mock_stream():
        yield 'data: {"choices": [{"delta": {"content": "Once "}}]}\n\n'
        yield 'data: {"choices": [{"delta": {"content": "upon "}}]}\n\n'
        yield 'data: {"choices": [{"delta": {"content": "a "}}]}\n\n'
        yield 'data: {"choices": [{"delta": {"content": "time..."}}]}\n\n'
        yield "data: [DONE]\n\n"

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        mock_llm.return_value = mock_stream()

        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

        assert response.status_code == status.HTTP_200_OK
        # For streaming, we just verify it doesn't error
        # Actual streaming validation would require async client


def test_chat_completion_with_character(authenticated_client, mock_chacha_db, setup_dependencies):
    """Test chat completion with a specific character."""

    # Add a character to the mock database
    character_id = mock_chacha_db.add_character_card(
        {
            "name": "TestBot",
            "description": "A test character",
            "personality": "Friendly and helpful",
            "system_prompt": "You are TestBot, a friendly assistant.",
        }
    )

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Who are you?")],
        character_id=str(character_id),
    )

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": "I am TestBot!"}, "finish_reason": "stop"}],
        }

        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

        assert response.status_code == status.HTTP_200_OK

        # Verify the system prompt was included
        call_args = mock_llm.call_args
        assert "TestBot" in str(call_args)


def test_chat_completion_unauthorized(mock_chacha_db):
    """Test that unauthenticated requests are rejected."""
    from fastapi.testclient import TestClient
    from tldw_Server_API.app.main import app

    with TestClient(app) as client:
        # Get CSRF token but don't authenticate
        response = client.get("/api/v1/health")
        csrf_token = response.cookies.get("csrf_token", "")

        request_data = ChatCompletionRequest(
            model="test-model", messages=[ChatCompletionUserMessageParam(role="user", content="Hello")]
        )

        response = client.post(
            "/api/v1/chat/completions", json=request_data.model_dump(), headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_chat_completion_invalid_model(authenticated_client, mock_chacha_db, setup_dependencies):
    """Test handling of invalid model requests."""

    # Use a valid provider but configure it to fail
    request_data = ChatCompletionRequest(
        model="invalid-model-xyz",
        api_provider="openai",  # Use a valid provider
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello")],
    )

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        # Simulate an error for invalid model
        mock_llm.side_effect = Exception("Invalid model: invalid-model-xyz")

        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

        # Should return an error status
        assert response.status_code >= 400


def test_chat_completion_with_conversation_history(authenticated_client, mock_chacha_db, setup_dependencies):
    """Test chat with conversation history."""

    # Get the actual default character ID (it's usually 2 based on our tests)
    # First check what character exists
    default_char = mock_chacha_db.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
    char_id = default_char["id"] if default_char else 2

    # Create a conversation with the correct client_id
    # The mock_chacha_db has a client_id attribute
    conv_id = mock_chacha_db.add_conversation(
        {
            "character_id": char_id,
            "title": "Test Conversation",
            "client_id": mock_chacha_db.client_id,  # Use the database's client_id
        }
    )

    # Add some history
    mock_chacha_db.add_message({"conversation_id": conv_id, "sender": "user", "content": "Previous message"})
    mock_chacha_db.add_message({"conversation_id": conv_id, "sender": "assistant", "content": "Previous response"})

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Continue our conversation")],
        conversation_id=str(conv_id),
    )

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [
                {"message": {"role": "assistant", "content": "Continuing from before..."}, "finish_reason": "stop"}
            ],
        }

        response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())

        assert response.status_code == status.HTTP_200_OK

        # Verify history was included in the call
        call_args = mock_llm.call_args
        # Messages might be in kwargs
        if call_args.kwargs and "messages_payload" in call_args.kwargs:
            messages = call_args.kwargs["messages_payload"]
        elif call_args.kwargs and "messages" in call_args.kwargs:
            messages = call_args.kwargs["messages"]
        elif len(call_args.args) > 0:
            # Try to find messages in positional args
            messages = call_args.args[0] if isinstance(call_args.args[0], list) else []
        else:
            messages = []
        assert len(messages) > 1  # Should include history


def test_chat_completion_rate_limiting(authenticated_client, mock_chacha_db, setup_dependencies):
    """Test rate limiting functionality."""

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello")],
    )

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "test-key"}),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": "Response"}, "finish_reason": "stop"}],
        }

        # Make multiple rapid requests
        responses = []
        for _ in range(5):
            response = authenticated_client.post("/api/v1/chat/completions", json=request_data.model_dump())
            responses.append(response.status_code)

        # All should succeed (rate limiting might not be enabled in test)
        # or we should see 429 status codes
        assert all(s in [200, 429] for s in responses)


def test_chat_completion_rg_primary_deny(
    authenticated_client,
    mock_chacha_db,
    setup_dependencies,
    monkeypatch,
):
    """
    When ResourceGovernor is enabled and the RG gate denies,
    the chat endpoint should surface a 429 with a policy-aware message.
    """

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello under RG")],
    )

    monkeypatch.setenv("RG_ENABLED", "1")

    gov = getattr(app.state, "rg_governor", None)
    if gov is None:
        app.state.rg_governor = SimpleNamespace()
        gov = app.state.rg_governor

    if getattr(app.state, "rg_policy_loader", None) is None:

        class _Loader:
            def get_policy(self, _policy_id):
                return {}

        app.state.rg_policy_loader = _Loader()

    async def fake_reserve(req, op_id=None):
        categories = getattr(req, "categories", {}) or {}
        if "requests" in categories and "tokens" not in categories:
            return SimpleNamespace(allowed=True, retry_after=None, details={"categories": categories}), "req-handle"
        return SimpleNamespace(allowed=False, retry_after=1, details={"categories": categories}), None

    async def fake_commit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gov, "reserve", fake_reserve, raising=True)
    monkeypatch.setattr(gov, "commit", fake_commit, raising=False)

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS",
            {"openai": "test-key"},
        ),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Response"},
                    "finish_reason": "stop",
                }
            ],
        }

        response = authenticated_client.post(
            "/api/v1/chat/completions",
            json=request_data.model_dump(),
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        body = response.json()
        assert "ResourceGovernor policy=" in str(body.get("detail"))


def test_chat_completion_rg_shadow_vs_primary_behaviour(
    authenticated_client,
    mock_chacha_db,
    setup_dependencies,
    monkeypatch,
):
    """
    Exercise /api/v1/chat/completions under RG allow/deny decisions to
    validate 200/429 behavior.
    """

    request_data = ChatCompletionRequest(
        model="test-model",
        api_provider="openai",
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello RG shadow/primary")],
    )

    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("RG_ENABLED", "1")

    gov = getattr(app.state, "rg_governor", None)
    if gov is None:
        app.state.rg_governor = SimpleNamespace()
        gov = app.state.rg_governor

    if getattr(app.state, "rg_policy_loader", None) is None:

        class _Loader:
            def get_policy(self, _policy_id):
                return {}

        app.state.rg_policy_loader = _Loader()

    token_calls = {"count": 0}

    async def fake_reserve(req, op_id=None):
        categories = getattr(req, "categories", {}) or {}
        if "requests" in categories and "tokens" not in categories:
            return SimpleNamespace(allowed=True, retry_after=None, details={"categories": categories}), "req-handle"
        if "tokens" in categories:
            token_calls["count"] += 1
            if token_calls["count"] == 1:
                return SimpleNamespace(allowed=True, retry_after=None, details={"categories": categories}), "tok-handle"
            return SimpleNamespace(allowed=False, retry_after=3, details={"categories": categories}), None
        return SimpleNamespace(allowed=True, retry_after=None, details={"categories": categories}), "req-handle"

    async def fake_commit(*_args, **_kwargs):
        return None

    with (
        patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call") as mock_llm,
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS",
            {"openai": "test-key"},
        ),
    ):
        mock_llm.return_value = {
            "id": "chatcmpl-test",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Shadow/primary response"},
                    "finish_reason": "stop",
                }
            ],
        }

        monkeypatch.setattr(gov, "reserve", fake_reserve, raising=True)
        monkeypatch.setattr(gov, "commit", fake_commit, raising=False)

        shadow_resp = authenticated_client.post(
            "/api/v1/chat/completions",
            json=request_data.model_dump(),
        )
        assert shadow_resp.status_code == status.HTTP_200_OK

        primary_resp = authenticated_client.post(
            "/api/v1/chat/completions",
            json=request_data.model_dump(),
        )
        assert primary_resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        body = primary_resp.json()
        detail = str(body.get("detail"))
        assert "ResourceGovernor policy=" in detail
        # Retry-After may be present either in headers or encoded in detail;
        # assert that at least one representation of the retry interval exists.
        header_retry = primary_resp.headers.get("Retry-After")
        assert ("retry_after=3s" in detail) or (header_retry is not None)
