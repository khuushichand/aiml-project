"""
Tests for newly added LLM providers (Moonshot AI, Z.AI, HuggingFace API).
"""

import pytest
import asyncio
import json
from typing import Optional, Dict, Any
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import httpx
import requests
from requests.structures import CaseInsensitiveDict

# Import the modules to test
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAuthenticationError,
    ChatBadRequestError,
    ChatRateLimitError,
    ChatProviderError,
)
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import (
    chat_with_moonshot,
    chat_with_zai,
    chat_with_cohere,
    chat_with_qwen,
    chat_with_groq,
    chat_with_groq_async,
    chat_with_google,
    chat_with_bedrock,
    chat_with_openai,
    chat_with_openai_async,
    chat_with_mistral,
    chat_with_openrouter,
    chat_with_openrouter_async,
    chat_with_deepseek,
    chat_with_anthropic,
    chat_with_anthropic_async,
    chat_with_huggingface,
)
from tldw_Server_API.app.core.LLM_Calls.huggingface_api import (
    HuggingFaceAPI,
    find_best_gguf_model,
    download_gguf_model
)


def make_response(status_code: int, body: str = "", headers: Optional[dict] = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = body.encode("utf-8")
    response.headers = CaseInsensitiveDict(headers or {})
    response.url = "https://example.com/api"
    return response


class TestMoonshotProvider:
    """Tests for Moonshot AI provider."""

    @pytest.fixture
    def mock_response(self):
        """Mock response for Moonshot API."""
        return {
            "id": "cmpl-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "moonshot-v1-8k",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from Moonshot AI!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }

    def test_moonshot_basic_chat(self, mock_response):
        """Test basic chat functionality."""
        with patch('requests.Session.post') as mock_post:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_post.return_value = mock_response_obj

            result = chat_with_moonshot(
                input_data=[{"role": "user", "content": "Hello"}],
                api_key="test_key",
                model="moonshot-v1-8k"
            )

            assert result["choices"][0]["message"]["content"] == "Hello from Moonshot AI!"
            mock_post.assert_called_once()

            # Check request payload
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == "moonshot-v1-8k"
            assert len(payload['messages']) == 1

    @patch('requests.Session.post')
    def test_moonshot_with_system_message(self, mock_post, mock_response):
        """Test chat with system message."""
        mock_response_obj = Mock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()
        mock_post.return_value = mock_response_obj

        result = chat_with_moonshot(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            system_message="You are a helpful assistant."
        )

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['messages'][0]['role'] == "system"
        assert payload['messages'][0]['content'] == "You are a helpful assistant."

    @patch('requests.Session.post')
    def test_moonshot_vision_model(self, mock_post, mock_response):
        """Test vision model with image content."""
        mock_response['model'] = "moonshot-v1-8k-vision-preview"
        mock_response_obj = Mock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()
        mock_post.return_value = mock_response_obj

        input_data = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ]
        }]

        result = chat_with_moonshot(
            input_data=input_data,
            api_key="test_key",
            model="moonshot-v1-8k-vision-preview"
        )

        assert result["choices"][0]["message"]["content"] == "Hello from Moonshot AI!"
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['model'] == "moonshot-v1-8k-vision-preview"

    @patch('requests.Session.post')
    def test_moonshot_streaming(self, mock_post):
        """Test streaming response."""
        # Mock SSE streaming response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        mock_response.iter_lines = Mock(return_value=[
            'event: completion.delta',
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'id: chunk-1',
            'data: {"choices":[{"delta":{"content":" from"}}]}',
            'data: {"choices":[{"delta":{"content":" Moonshot!"}}]}',
            'retry: 0',
            'data: [DONE]'
        ])
        mock_post.return_value = mock_response

        chunks = []
        result_gen = chat_with_moonshot(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            streaming=True
        )

        for chunk in result_gen:
            chunks.append(chunk)

        assert len(chunks) == 4  # 3 content chunks + [DONE]
        assert "[DONE]" in chunks[-1]

    @patch('tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.requests.Session')
    def test_moonshot_streaming_session_lifecycle(self, mock_session_cls):
        """Ensure streaming keeps the session open until iteration finishes."""
        session_state = {"closed": False}
        response_state = {"closed": False}

        session_instance = MagicMock()

        def close_session():
            session_state["closed"] = True

        session_instance.close.side_effect = close_session

        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = Mock()

        def close_response():
            response_state["closed"] = True

        response.close.side_effect = close_response

        def iter_lines(decode_unicode=False):
            if session_state["closed"]:
                raise AssertionError("Session closed before iteration started")

            def generator():
                if session_state["closed"]:
                    raise AssertionError("Session closed before yielding first chunk")
                yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
                if session_state["closed"]:
                    raise AssertionError("Session closed before completion")
                yield 'data: [DONE]'

            return generator()

        response.iter_lines.side_effect = iter_lines

        session_instance.post.return_value = response
        mock_session_cls.return_value = session_instance

        generator = chat_with_moonshot(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            streaming=True
        )

        first_chunk = next(generator)
        assert "Hello" in first_chunk
        assert session_state["closed"] is False
        assert response_state["closed"] is False

        remaining_chunks = list(generator)
        assert any("[DONE]" in chunk for chunk in remaining_chunks)
        assert session_state["closed"] is True
        assert response_state["closed"] is True

    @patch('requests.Session.post')
    def test_moonshot_error_handling(self, mock_post):
        """Test error handling."""
        response = make_response(401, '{"error": {"message": "Unauthorized"}}')
        mock_post.return_value = response

        with pytest.raises(ChatAuthenticationError) as exc_info:
            _ = chat_with_moonshot(
                input_data=[{"role": "user", "content": "Hello"}],
                api_key="invalid_key"
            )

        assert "Unauthorized" in str(exc_info.value)


class TestZAIProvider:
    """Tests for Z.AI provider."""

    @pytest.fixture
    def mock_response(self):
        """Mock response for Z.AI API."""
        return {
            "id": "chat-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "glm-4.5",
            "request_id": "req_test123",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from Z.AI GLM!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }

    @patch('requests.Session.post')
    def test_zai_basic_chat(self, mock_post, mock_response):
        """Test basic chat functionality."""
        mock_response_obj = Mock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()
        mock_post.return_value = mock_response_obj

        result = chat_with_zai(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            model="glm-4.5"
        )

        assert result["choices"][0]["message"]["content"] == "Hello from Z.AI GLM!"
        mock_post.assert_called_once()

        # Check request payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['model'] == "glm-4.5"

    @patch('requests.Session.post')
    def test_zai_with_request_id(self, mock_post, mock_response):
        """Test chat with request_id."""
        mock_response_obj = Mock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()
        mock_post.return_value = mock_response_obj

        result = chat_with_zai(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            request_id="custom_req_123"
        )

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload.get('request_id') == "custom_req_123"

    @patch('requests.Session.post')
    def test_zai_model_variants(self, mock_post, mock_response):
        """Test different model variants."""
        models = ["glm-4.5", "glm-4.5-air", "glm-4.5-flash", "glm-4-32b-0414-128k"]

        for model in models:
            mock_response['model'] = model
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_post.return_value = mock_response_obj

            result = chat_with_zai(
                input_data=[{"role": "user", "content": "Test"}],
                api_key="test_key",
                model=model
            )

            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == model

    @patch('requests.Session.post')
    def test_zai_streaming(self, mock_post):
        """Test streaming response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/event-stream'}
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" GLM"}}]}',
            'data: [DONE]'
        ])
        mock_post.return_value = mock_response

        chunks = []
        result_gen = chat_with_zai(
            input_data=[{"role": "user", "content": "Hello"}],
            api_key="test_key",
            streaming=True
        )

        for chunk in result_gen:
            chunks.append(chunk)

        assert len(chunks) == 3
        assert "[DONE]" in chunks[-1]


@pytest.mark.parametrize(
    "func, kwargs, status_code, expected_exception",
    [
        (
            chat_with_openrouter,
            {
                "input_data": [{"role": "user", "content": "Hi"}],
                "api_key": "test_key",
                "model": "mistralai/mistral-7b-instruct:free",
            },
            429,
            ChatRateLimitError,
        ),
        (
            chat_with_mistral,
            {"input_data": [{"role": "user", "content": "Hi"}], "api_key": "test_key", "model": "mistral-small"},
            401,
            ChatAuthenticationError,
        ),
        (
            chat_with_deepseek,
            {"input_data": [{"role": "user", "content": "Hi"}], "api_key": "test_key", "model": "deepseek-chat"},
            400,
            ChatBadRequestError,
        ),
        (
            chat_with_google,
            {"input_data": [{"role": "user", "content": "Hi"}], "api_key": "test_key", "model": "gemini-1.5-flash"},
            503,
            ChatProviderError,
        ),
    ],
)
def test_provider_http_error_mapping(func, kwargs, status_code, expected_exception):
    response = make_response(status_code, '{"error": {"message": "boom"}}')
    with patch('requests.Session.post', return_value=response):
        with pytest.raises(expected_exception):
            func(**kwargs)


class TestHuggingFaceAPI:
    """Tests for HuggingFace API client."""

    @pytest.fixture
    def api_client(self):
        """Create HuggingFace API client."""
        return HuggingFaceAPI(token="test_token")

    @pytest.fixture
    def mock_model_response(self):
        """Mock model search response."""
        return [
            {
                "modelId": "TheBloke/Llama-2-7B-GGUF",
                "author": "TheBloke",
                "downloads": 100000,
                "likes": 500,
                "tags": ["gguf", "llama"]
            },
            {
                "modelId": "TheBloke/Mistral-7B-GGUF",
                "author": "TheBloke",
                "downloads": 50000,
                "likes": 300,
                "tags": ["gguf", "mistral"]
            }
        ]

    @pytest.mark.asyncio
    async def test_search_models(self, api_client, mock_model_response):
        """Test model search functionality."""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_model_response)
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            results = await api_client.search_models(
                query="llama",
                filter_tags=["gguf"],
                limit=10
            )

            assert len(results) == 2
            assert results[0]["modelId"] == "TheBloke/Llama-2-7B-GGUF"

    @pytest.mark.asyncio
    async def test_get_model_info(self, api_client):
        """Test getting model information."""
        mock_info = {
            "modelId": "TheBloke/Llama-2-7B-GGUF",
            "author": "TheBloke",
            "downloads": 100000,
            "description": "Llama 2 7B model in GGUF format"
        }

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_info)
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            info = await api_client.get_model_info("TheBloke/Llama-2-7B-GGUF")

            assert info["modelId"] == "TheBloke/Llama-2-7B-GGUF"
            assert info["downloads"] == 100000

    @pytest.mark.asyncio
    async def test_list_model_files(self, api_client):
        """Test listing GGUF files in a repository."""
        mock_files = [
            {"path": "llama-2-7b.Q4_K_M.gguf", "size": 3825000000},
            {"path": "llama-2-7b.Q5_K_S.gguf", "size": 4650000000},
            {"path": "README.md", "size": 5000}
        ]

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_files)
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            files = await api_client.list_model_files("TheBloke/Llama-2-7B-GGUF")

            # Should only return GGUF files
            assert len(files) == 2
            assert all(f["path"].endswith(".gguf") for f in files)

    @pytest.mark.asyncio
    async def test_download_file(self, api_client, tmp_path):
        """Test file download functionality."""
        test_content = b"This is a test GGUF file content"

        with patch('httpx.AsyncClient.head', new_callable=AsyncMock) as mock_head:
            with patch('httpx.AsyncClient.stream', new_callable=Mock) as mock_stream:
                # Mock HEAD request for file size
                mock_head_response = Mock()
                mock_head_response.headers = {"content-length": str(len(test_content))}
                mock_head.return_value = mock_head_response

                # Mock streaming download
                mock_stream_response = Mock()
                mock_stream_response.raise_for_status = Mock()
                async def _aiter_bytes(chunk_size=65536):
                    yield test_content
                mock_stream_response.aiter_bytes = Mock(return_value=_aiter_bytes())
                # Configure async context manager behavior
                mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream_response)
                mock_stream.return_value.__aexit__ = AsyncMock(return_value=None)

                destination = tmp_path / "test_model.gguf"
                success = await api_client.download_file(
                    repo_id="TheBloke/Test-GGUF",
                    filename="test.gguf",
                    destination=destination
                )

                assert success
                assert destination.exists()
                assert destination.read_bytes() == test_content

    @pytest.mark.asyncio
    async def test_download_with_progress(self, api_client, tmp_path):
        """Test download with progress callback."""
        test_content = b"0" * 1000
        progress_calls = []

        def progress_callback(downloaded, total):
            progress_calls.append((downloaded, total))

        with patch('httpx.AsyncClient.head', new_callable=AsyncMock) as mock_head:
            with patch('httpx.AsyncClient.stream', new_callable=Mock) as mock_stream:
                mock_head_response = Mock()
                mock_head_response.headers = {"content-length": "1000"}
                mock_head.return_value = mock_head_response

                mock_stream_response = Mock()
                mock_stream_response.raise_for_status = Mock()
                # Simulate chunked download
                async def _aiter_bytes2(chunk_size=65536):
                    yield test_content[:500]
                    yield test_content[500:]
                mock_stream_response.aiter_bytes = Mock(return_value=_aiter_bytes2())
                # Configure async context manager behavior
                mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream_response)
                mock_stream.return_value.__aexit__ = AsyncMock(return_value=None)

                destination = tmp_path / "test_model.gguf"
                success = await api_client.download_file(
                    repo_id="TheBloke/Test-GGUF",
                    filename="test.gguf",
                    destination=destination,
                    progress_callback=progress_callback
                )

                assert success
                assert len(progress_calls) == 2
                assert progress_calls[-1] == (1000, 1000)

    @pytest.mark.asyncio
    async def test_find_best_gguf_model(self):
        """Test finding best GGUF model utility."""
        mock_models = [
            {
                "modelId": "TheBloke/Llama-2-7B-GGUF",
                "downloads": 100000
            }
        ]

        with patch('tldw_Server_API.app.core.LLM_Calls.huggingface_api.HuggingFaceAPI.search_gguf_models') as mock_search:
            async def mock_search_async(*args, **kwargs):
                return mock_models
            mock_search.side_effect = mock_search_async

            best_model = await find_best_gguf_model(
                model_name="llama-2",
                max_size_gb=10.0,
                preferred_quant="Q4_K_M"
            )

            assert best_model["modelId"] == "TheBloke/Llama-2-7B-GGUF"

    @pytest.mark.asyncio
    async def test_error_handling(self, api_client):
        """Test error handling in API calls."""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection error")

            results = await api_client.search_models(query="test")
            assert results == []  # Should return empty list on error

            info = await api_client.get_model_info("test/model")
            assert info is None  # Should return None on error


class TestIntegration:
    """Integration tests for provider interactions."""

    @pytest.mark.asyncio
    @patch('requests.Session.post')
    async def test_provider_switching(self, mock_post):
        """Test switching between different providers."""
        # Mock responses for different providers
        moonshot_response = {
            "choices": [{"message": {"content": "Moonshot response"}}]
        }
        zai_response = {
            "choices": [{"message": {"content": "Z.AI response"}}]
        }

        mock_response_obj = Mock()
        mock_response_obj.status_code = 200
        mock_response_obj.raise_for_status = Mock()
        mock_post.return_value = mock_response_obj

        # Test Moonshot
        mock_response_obj.json.return_value = moonshot_response
        result1 = chat_with_moonshot(
            input_data=[{"role": "user", "content": "Test"}],
            api_key="key1"
        )
        assert result1["choices"][0]["message"]["content"] == "Moonshot response"

        # Test Z.AI
        mock_response_obj.json.return_value = zai_response
        result2 = chat_with_zai(
            input_data=[{"role": "user", "content": "Test"}],
            api_key="key2"
        )
        assert result2["choices"][0]["message"]["content"] == "Z.AI response"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent requests to multiple providers."""
        with patch('requests.Session.post') as mock_post:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = {
                "choices": [{"message": {"content": "Response"}}]
            }
            mock_response_obj.raise_for_status = Mock()
            mock_post.return_value = mock_response_obj

            # Simulate concurrent requests
            tasks = [
                asyncio.create_task(
                    asyncio.to_thread(
                        chat_with_moonshot,
                        [{"role": "user", "content": f"Test {i}"}],
                        api_key="key"
                    )
                )
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)
        assert len(results) == 5
        assert all(r["choices"][0]["message"]["content"] == "Response" for r in results)


class TestSSENormalization:
    """Tests for SSE normalization across providers (Cohere, Qwen, Groq)."""

    @patch('requests.Session.post')
    def test_cohere_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"event_type":"stream-start","generation_id":"gen-1"}',
            'data: {"event_type":"text-generation","text":"Hello"}',
            'data: {"event_type":"text-generation","text":" world"}',
            'data: {"event_type":"stream-end","finish_reason":"end_turn"}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_cohere(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        # Expect two content chunks + DONE
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert chunks[1].startswith('data: ')
        assert chunks[1].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    def test_cohere_stream_session_lifecycle(self, monkeypatch):
        stream_lines = [
            b'data: {"event_type":"text-generation","text":"Hello"}',
            b'data: {"event_type":"stream-end","finish_reason":"end_turn"}',
        ]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=stream_lines)
        mock_response.close = Mock()

        session = Mock()
        session.post.return_value = mock_response
        session.close = Mock()

        monkeypatch.setattr(
            "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
            lambda **kwargs: session,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
            lambda: {"cohere_api": {"api_key": "test", "api_timeout": 30}},
        )

        gen = chat_with_cohere(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test",
            streaming=True,
        )

        session.close.assert_not_called()
        first_chunk = next(gen)
        session.close.assert_not_called()

        remaining = list(gen)
        session.close.assert_called_once()
        assert mock_response.close.called
        assert first_chunk.startswith("data: ")
        assert remaining[-1].strip().lower() == "data: [done]"

    @patch('requests.Session.post')
    def test_qwen_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{"content":"!"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_qwen(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        # 2 content chunks + normalized DONE
        assert len(chunks) == 3
        assert all(c.startswith('data: ') for c in chunks)
        assert all(c.endswith('\n\n') for c in chunks[:-1])
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_groq_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" Groq"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_groq(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_google_gemini_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        # Simulate Gemini SSE frames containing candidate text chunks
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            b'data: {"candidates":[{"content":{"parts":[{"text":" Gemini"}]}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_google(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        # Expect two content chunks + DONE
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_google_gemini_stream_tool_calls(self, mock_post):
        tool_chunk = (
            b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"lookup","args":{"query":"mars"}}}]},'
            b'"finishReason":"FUNCTION_CALL"}]}'
        )
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[tool_chunk])
        mock_post.return_value = mock_response

        gen = chat_with_google(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test",
            streaming=True,
        )
        chunks = list(gen)
        assert len(chunks) == 2  # tool-call chunk + DONE
        first_payload = chunks[0].split("data: ", 1)[1]
        payload_json = json.loads(first_payload)
        delta = payload_json["choices"][0]["delta"]
        assert "tool_calls" in delta and delta["tool_calls"]
        tool_call = delta["tool_calls"][0]
        assert tool_call["function"]["name"] == "lookup"
        assert json.loads(tool_call["function"]["arguments"]) == {"query": "mars"}
        assert chunks[-1].strip() == "data: [DONE]"

    @patch('requests.Session.post')
    def test_bedrock_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            b'data: {"choices":[{"delta":{"content":" Bedrock"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_bedrock(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", model="meta.llama3-8b-instruct", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_bedrock_stream_error_chunked(self, mock_post):
        class ErrIterator:
            def __iter__(self):
                raise requests.exceptions.ChunkedEncodingError('boom')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=ErrIterator())
        mock_post.return_value = mock_response

        gen = chat_with_bedrock(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", model="meta.llama3-8b-instruct", streaming=True
        )
        chunks = list(gen)
        assert any('bedrock_stream_error' in c for c in chunks)
        assert all(c.startswith('data: ') for c in chunks)

    @patch('requests.Session.post')
    def test_gemini_stream_error_chunked(self, mock_post):
        class ErrIterator:
            def __iter__(self):
                raise requests.exceptions.ChunkedEncodingError('boom')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=ErrIterator())
        mock_post.return_value = mock_response

        gen = chat_with_google(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert any('gemini_stream_error' in c for c in chunks)
        assert all(c.startswith('data: ') for c in chunks)

    @patch('requests.Session.post')
    def test_gemini_stream_finish_reason(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            b'data: {"candidates":[{"finishReason":"STOP"}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_google(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert any('"finish_reason": "stop"' in c for c in chunks)
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_anthropic_stream_finish_reason(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        assert any('"finish_reason": "stop"' in c for c in chunks)
        assert any('[DONE]' in c for c in chunks)

    @patch('requests.Session.post')
    def test_mistral_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{"content":", Mistral"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_mistral(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_openrouter_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" OpenRouter"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_openrouter(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_deepseek_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" DeepSeek"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_deepseek(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="test", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_huggingface_stream_normalized(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        # HF path uses requests.post directly (not a Session)
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            b'data: {"choices":[{"delta":{"content":" HF"}}]}',
        ])
        mock_post.return_value = mock_response

        gen = chat_with_huggingface(
            input_data=[{"role": "user", "content": "Hi"}],
            model="org/model", api_key="key", streaming=True
        )
        chunks = list(gen)
        assert len(chunks) == 3
        assert chunks[0].startswith('data: ')
        assert chunks[0].endswith('\n\n')
        assert '[DONE]' in chunks[-1]

    @patch('requests.Session.post')
    def test_anthropic_stream_includes_done(self, mock_post):
        # Simulate Anthropic event stream: text delta then end
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
        ])
        mock_response.close = Mock()
        mock_post.return_value = mock_response

        gen = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        # Should include a DONE sentinel at end
        assert any('[DONE]' in c for c in chunks)

    @patch('requests.Session.post')
    def test_anthropic_stream_emits_tool_calls(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[
            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"lookup","input":{}}}',
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"city\\":\\"Paris\\"}"}}',
            b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
        ])
        mock_response.close = Mock()
        mock_post.return_value = mock_response

        gen = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)

        assert any('"tool_calls"' in c for c in chunks)
        assert any('[DONE]' in c for c in chunks)

    @patch('requests.Session.post')
    def test_anthropic_stream_error_chunked(self, mock_post):
        class ErrIterator:
            def __iter__(self):
                raise requests.exceptions.ChunkedEncodingError('boom')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=ErrIterator())
        mock_post.return_value = mock_response

        gen = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        assert any('anthropic_stream_error' in c for c in chunks)
        assert any(c.startswith('data: ') for c in chunks)

    @patch('requests.Session.post')
    def test_anthropic_payload_includes_image_url(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": "msg_1",
            "model": "claude-3-haiku-20240307",
            "content": [{"type": "text", "text": "hi"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
        mock_response.close = Mock()
        mock_post.return_value = mock_response

        chat_with_anthropic(
            input_data=[{
                "role": "user",
                "content": [{
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/cat.png"},
                }],
            }],
            api_key="key",
            streaming=False,
        )

        payload = mock_post.call_args[1]['json']
        image_source = payload['messages'][0]['content'][0]['source']
        assert image_source['type'] == 'url'
        assert image_source['url'] == 'https://example.com/cat.png'

    @patch('requests.Session.post')
    def test_anthropic_payload_includes_base64_image(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": "msg_2",
            "model": "claude-3-haiku-20240307",
            "content": [{"type": "text", "text": "hi"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
        mock_response.close = Mock()
        mock_post.return_value = mock_response

        chat_with_anthropic(
            input_data=[{
                "role": "user",
                "content": [{
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,QUJD"},
                }],
            }],
            api_key="key",
            streaming=False,
        )

        payload = mock_post.call_args[1]['json']
        image_source = payload['messages'][0]['content'][0]['source']
        assert image_source['type'] == 'base64'
        assert image_source['media_type'] == 'image/png'
        assert image_source['data'] == 'QUJD'

    @patch('requests.Session.post')
    def test_mistral_stream_error_chunked(self, mock_post):
        class ErrIterator:
            def __iter__(self):
                raise requests.exceptions.ChunkedEncodingError('boom')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=ErrIterator())
        mock_post.return_value = mock_response

        gen = chat_with_mistral(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        assert any('mistral_stream_error' in c for c in chunks)
        assert any(c.startswith('data: ') for c in chunks)

    @patch('requests.Session.post')
    def test_openrouter_stream_error_chunked(self, mock_post):
        class ErrIterator:
            def __iter__(self):
                raise requests.exceptions.ChunkedEncodingError('boom')

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=ErrIterator())
        mock_post.return_value = mock_response

        gen = chat_with_openrouter(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        assert any('openrouter_stream_error' in c for c in chunks)
        assert any(c.startswith('data: ') for c in chunks)

    @pytest.mark.asyncio
    async def test_anthropic_async_matches_sync_normalization(self, monkeypatch):
        import copy

        response_payload = {
            "id": "msg_42",
            "model": "claude-3-haiku-20240307",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "id": "tool_99", "name": "lookup", "input": {"city": "Paris"}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

        def _make_response():
            resp = Mock()
            resp.status_code = 200
            resp.raise_for_status = Mock()
            resp.json.return_value = copy.deepcopy(response_payload)
            resp.close = Mock()
            return resp

        sync_session = Mock()
        sync_session.post.return_value = _make_response()
        sync_session.close = Mock()
        monkeypatch.setattr(
            "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries",
            lambda **kwargs: sync_session,
        )

        class _AsyncClientSuccess:
            def __init__(self, *args, **kwargs):
                self._response = _make_response()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                return self._response

            def stream(self, *args, **kwargs):
                raise AssertionError("Streaming not expected in this test.")

        monkeypatch.setattr(
            "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.httpx.AsyncClient",
            _AsyncClientSuccess,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs",
            lambda: {"anthropic_api": {"api_key": "key"}},
        )

        sync_result = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key",
            streaming=False,
        )
        async_result = await chat_with_anthropic_async(
            [{"role": "user", "content": "Hi"}],
            api_key="key",
            streaming=False,
        )

        assert sync_result == async_result
        tool_call = sync_result["choices"][0]["message"]["tool_calls"][0]
        assert tool_call["function"]["name"] == "lookup"
        assert tool_call["function"]["arguments"] == json.dumps({"city": "Paris"})


def test_openai_defaults_with_blank_config(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return

        def json(self):
            return {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    class DummySession:
        def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            return DummyResponse()

        def close(self):
            return

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: DummySession(),
    )

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        lambda: {
            'openai_api': {
                'api_key': 'test-key',
                'temperature': '',
                'top_p': None,
                'api_timeout': '',
                'api_retry_delay': '',
                'api_retries': '',
                'max_tokens': '',
                'api_base_url': 'https://mock.openai.local/v1',
            }
        },
    )

    result = chat_with_openai(
        input_data=[{"role": "user", "content": "hello"}],
    )

    assert result["choices"][0]["message"]["content"] == "ok"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["temperature"] == 0.7
    assert captured["json"]["top_p"] == 0.95
    assert captured["timeout"] == 90.0


@pytest.mark.asyncio
async def test_openai_async_streaming_normalized(monkeypatch):
    class MockResp:
        status_code = 200
        def raise_for_status(self):
            return
        async def aiter_lines(self):
            yield 'event: completion.delta'
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield 'id: chunk-1'
            yield 'data: {"choices":[{"delta":{"content":" async"}}]}'
            yield 'retry: 1000'
            yield 'data: [DONE]'

    class MockStreamCtx:
        async def __aenter__(self):
            return MockResp()
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class MockAsyncClient:
        def __init__(self, timeout=None):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        def stream(self, *args, **kwargs):
            return MockStreamCtx()

    async def _mock_client_ctor(*args, **kwargs):
        return MockAsyncClient()

    # Monkeypatch httpx.AsyncClient to our mock client
    monkeypatch.setattr('httpx.AsyncClient', MockAsyncClient)

    gen = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="test", streaming=True
    )
    out = []
    async for chunk in gen:
        out.append(chunk)
    assert len(out) == 3
    assert out[0].startswith('data: ')
    assert out[0].endswith('\n\n')
    assert '[DONE]' in out[-1]


@pytest.mark.asyncio
async def test_openai_async_non_streaming_preserves_payload(monkeypatch):
    expected_response = {
        "id": "chatcmpl-123",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Async hello"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
    }
    captured: Dict[str, Any] = {}

    def fake_config():
        return {"openai_api": {"api_key": "cfg-key"}}

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return expected_response

    class DummyAsyncClient:
        def __init__(self, *args, timeout=None, **kwargs):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)

    result = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "hi async"}],
        api_key="cfg-key",
        streaming=False,
    )

    assert result == expected_response
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["messages"][-1]["content"] == "hi async"
    assert captured["timeout"] == 90.0


@pytest.mark.asyncio
async def test_openai_async_gpt5_payload(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_config():
        return {
            "openai_api": {
                "api_key": "cfg-key",
                "model": "gpt-5-mini",
                "max_tokens": 128,
                "temperature": 1.0,
                "top_p": 0.8,
            }
        }

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)

    result = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "hi there"}],
        streaming=False,
        model="gpt-5-mini",
    )

    payload = captured["payload"]
    assert "top_p" not in payload
    assert "max_tokens" not in payload
    assert payload["max_completion_tokens"] == 128
    assert payload.get("temperature") == 1.0
    assert result["choices"] == []


@pytest.mark.asyncio
async def test_groq_async_non_streaming_preserves_payload(monkeypatch):
    expected_response = {
        "id": "chatcmpl-groq",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Groq hello"}}],
    }
    captured: Dict[str, Any] = {}

    def fake_config():
        return {"groq_api": {"api_key": "groq-key"}}

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return expected_response

    class DummyAsyncClient:
        def __init__(self, *args, timeout=None, **kwargs):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)

    result = await chat_with_groq_async(
        input_data=[{"role": "user", "content": "groq async"}],
        api_key="groq-key",
        streaming=False,
    )

    assert result == expected_response
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["messages"][-1]["content"] == "groq async"
    assert captured["timeout"] == 90.0


@pytest.mark.asyncio
async def test_openrouter_async_streaming_filters_control_lines(monkeypatch):
    def fake_config():
        return {"openrouter_api": {"api_key": "router-key"}}

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield "event: ping"
            yield 'data: {"choices":[{"delta":{"content":"chunk"}}]}'
            yield "id: 123"
            yield "data: [DONE]"

    class DummyStreamCtx:
        async def __aenter__(self):
            return DummyResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyAsyncClient:
        def __init__(self, *args, timeout=None, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return DummyStreamCtx()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)

    gen = await chat_with_openrouter_async(
        input_data=[{"role": "user", "content": "hello"}],
        api_key="router-key",
        streaming=True,
    )

    chunks = []
    async for chunk in gen:
        chunks.append(chunk)

    assert len(chunks) == 2  # content + sentinel
    assert "event:" not in "".join(chunks)
    assert "id:" not in "".join(chunks)
    assert chunks[-1].strip().lower() == "data: [done]"


def test_openai_non_streaming_session_closed(monkeypatch):
    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    response.json.return_value = {"choices": [], "id": "test"}

    session = Mock()
    session.post.return_value = response

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: session,
    )

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        lambda: {"openai_api": {"api_key": "cfg-key"}},
    )

    chat_with_openai(
        input_data=[{"role": "user", "content": "hello"}],
        streaming=False,
        api_key="cfg-key",
    )

    session.close.assert_called_once()


def test_cohere_config_fallbacks(monkeypatch):
    def fake_config():
        return {
            "cohere_api": {
                "api_key": "cohere-key",
                "model": "command-r",
                "temperature": 0.42,
                "top_p": 0.85,
                "top_k": 12,
                "max_tokens": 256,
                "stop_sequences": ["END"],
                "seed": 123,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.05,
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
                "num_generations": 2,
            }
        }

    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    response.json.return_value = {
        "text": "Configured response",
        "finish_reason": "stop",
        "meta": {"billed_units": {"input_tokens": 5, "output_tokens": 7}},
    }

    session = Mock()
    session.post.return_value = response
    session.close = Mock()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: session,
    )

    result = chat_with_cohere(
        input_data=[{"role": "user", "content": "Hi there"}],
        streaming=False,
    )

    payload = session.post.call_args.kwargs["json"]
    assert payload["temperature"] == 0.42
    assert payload["p"] == 0.85
    assert payload["k"] == 12
    assert payload["max_tokens"] == 256
    assert payload["stop_sequences"] == ["END"]
    assert payload["seed"] == 123
    assert payload["frequency_penalty"] == 0.1
    assert payload["presence_penalty"] == 0.05
    assert payload["tools"] == [{"type": "function", "function": {"name": "lookup"}}]
    assert payload["stream"] is False
    assert payload["num_generations"] == 2

    assert result["usage"]["prompt_tokens"] == 5
    session.close.assert_called_once()


def test_google_config_fallbacks(monkeypatch):
    def fake_config():
        return {
            "google_api": {
                "api_key": "google-key",
                "model": "gemini-test",
                "temperature": 0.33,
                "top_p": 0.77,
                "top_k": 40,
                "max_output_tokens": 512,
                "stop_sequences": ["STOP"],
                "candidate_count": 2,
                "tools": [{"function_declarations": [{"name": "lookup"}]}],
                "response_format": {"type": "json_object"},
            }
        }

    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    response.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Hello Gemini"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 3,
            "candidatesTokenCount": 4,
            "totalTokenCount": 7,
        },
    }

    session = Mock()
    session.post.return_value = response
    session.close = Mock()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        fake_config,
    )
    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: session,
    )

    result = chat_with_google(
        input_data=[{"role": "user", "content": "Hi"}],
        streaming=False,
    )

    payload = session.post.call_args.kwargs["json"]
    gen_cfg = payload["generationConfig"]
    assert gen_cfg["temperature"] == 0.33
    assert gen_cfg["topP"] == 0.77
    assert gen_cfg["topK"] == 40
    assert gen_cfg["maxOutputTokens"] == 512
    assert gen_cfg["stopSequences"] == ["STOP"]
    assert gen_cfg["candidateCount"] == 2
    assert gen_cfg["responseMimeType"] == "application/json"
    assert payload["tools"] == [{"function_declarations": [{"name": "lookup"}]}]

    assert result["choices"][0]["message"]["content"] == "Hello Gemini"
    session.close.assert_called_once()


def test_mistral_stream_session_closed(monkeypatch):
    session = MagicMock()
    response = MagicMock()
    response.iter_lines.return_value = iter([
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: [DONE]',
    ])
    response.raise_for_status = Mock()
    response.close = Mock()
    session.post.return_value = response
    session.close = Mock()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        lambda: {'mistral_api': {}},
    )
    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: session,
    )

    gen = chat_with_mistral(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="m-key",
        streaming=True,
    )
    chunks = list(gen)
    assert chunks[-1].strip().lower() == 'data: [done]'
    assert session.close.call_count >= 1


def test_zai_http_error_normalized(monkeypatch):
    session = MagicMock()
    response = MagicMock()
    response.status_code = 429
    response.text = '{"error":{"message":"Rate limit"}}'
    response.json.return_value = {"error": {"message": "Rate limit"}}
    http_error = requests.HTTPError("rate limit", response=response)
    response.raise_for_status.side_effect = http_error
    session.post.return_value = response
    session.close = Mock()

    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.load_and_log_configs',
        lambda: {'zai_api': {}},
    )
    monkeypatch.setattr(
        'tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls.create_session_with_retries',
        lambda *args, **kwargs: session,
    )

    with pytest.raises(ChatRateLimitError):
        chat_with_zai(
            input_data=[{"role": "user", "content": "hello"}],
            api_key="z-key",
            streaming=False,
        )
    assert session.close.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
