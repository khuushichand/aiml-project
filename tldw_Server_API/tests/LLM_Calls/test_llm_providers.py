"""
Tests for newly added LLM providers (Moonshot AI, Z.AI, HuggingFace API).
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import httpx
import requests

# Import the modules to test
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import (
    chat_with_moonshot,
    chat_with_zai,
    chat_with_cohere,
    chat_with_qwen,
    chat_with_groq,
    chat_with_openai_async,
    chat_with_mistral,
    chat_with_openrouter,
    chat_with_deepseek,
    chat_with_anthropic,
    chat_with_huggingface,
)
from tldw_Server_API.app.core.LLM_Calls.huggingface_api import (
    HuggingFaceAPI,
    find_best_gguf_model,
    download_gguf_model
)


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
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" from"}}]}',
            'data: {"choices":[{"delta":{"content":" Moonshot!"}}]}',
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
    
    @patch('requests.Session.post')
    def test_moonshot_error_handling(self, mock_post):
        """Test error handling."""
        mock_response_obj = Mock()
        mock_response_obj.status_code = 401
        mock_response_obj.text = "Unauthorized"
        mock_response_obj.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized", response=Mock(status_code=401))
        mock_post.return_value = mock_response_obj
        
        with pytest.raises(requests.exceptions.HTTPError):
            _ = chat_with_moonshot(
                input_data=[{"role": "user", "content": "Hello"}],
                api_key="invalid_key"
            )


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

    @patch('requests.post')
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
        mock_post.return_value = mock_response

        gen = chat_with_anthropic(
            input_data=[{"role": "user", "content": "Hi"}],
            api_key="key", streaming=True
        )
        chunks = list(gen)
        # Should include a DONE sentinel at end
        assert any('[DONE]' in c for c in chunks)


@pytest.mark.asyncio
async def test_openai_async_streaming_normalized(monkeypatch):
    class MockResp:
        status_code = 200
        def raise_for_status(self):
            return
        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" async"}}]}'

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
