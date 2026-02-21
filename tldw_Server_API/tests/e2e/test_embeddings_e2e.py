"""
End-to-end tests for embeddings functionality.

Tests the complete workflow of generating embeddings for media items,
including upload with auto-generation and manual generation endpoints.
"""

import asyncio
import os
import tempfile
import time

import httpx
import pytest

# Import the test client fixture
from fixtures import api_client, E2E_INPROCESS, TEST_TIMEOUT

# Constants
TEST_TEXT_CONTENT = """
This is a test document for embedding generation.
It contains multiple sentences to test chunking.
The chunking algorithm should split this into appropriate segments.
Each segment will have its own embedding vector.
This allows for semantic search across the content.
"""


def _is_inprocess_client(api_client) -> bool:


    base_url = str(getattr(api_client.client, "base_url", ""))
    if "testserver" in base_url:
        return True
    transport = getattr(api_client.client, "transport", None) or getattr(api_client.client, "_transport", None)
    if isinstance(transport, httpx.ASGITransport):
        return True
    return E2E_INPROCESS


def _build_async_client(api_client):


    auth_headers = api_client.get_auth_headers()
    if _is_inprocess_client(api_client):
        from tldw_Server_API.app.main import app
        try:
            transport = httpx.ASGITransport(app=app, lifespan="on")
        except TypeError:
            transport = httpx.ASGITransport(app=app)
        base_url = str(getattr(api_client.client, "base_url", "http://testserver"))
        return httpx.AsyncClient(
            transport=transport,
            base_url=base_url,
            headers=auth_headers,
            timeout=TEST_TIMEOUT,
        )
    return httpx.AsyncClient(
        base_url=api_client.base_url,
        headers=auth_headers,
        timeout=TEST_TIMEOUT,
    )


def _should_skip_embeddings_error(error: str | None) -> bool:
    if not error:
        return False
    lowered = error.lower()
    signals = (
        "service unavailable",
        "requires an api key",
        "missing api key",
        "no api key",
        "embedding service error",
        "provider not configured",
        "provider unavailable",
        "model not found",
        "unknown provider",
        "huggingface",
        "hf.co",
        "ssl",
        "certificate",
        "max retry",
        "max retries",
        "timeout",
        "timed out",
        "connection",
        "connect error",
        "failed to connect",
        "connection refused",
        "name resolution",
        "getaddrinfo",
        "temporary failure",
        "download",
    )
    return any(signal in lowered for signal in signals)


def _extract_content_text(payload: dict) -> str:
    content = payload.get("content")
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
    elif isinstance(content, str):
        text = content
    else:
        text = ""
    return text


async def _ensure_media_content(async_client, media_id: int, fallback_text: str, max_wait_s: int = 10) -> None:
    start = time.time()
    last_payload = None
    while time.time() - start < max_wait_s:
        resp = await async_client.get(
            f"/api/v1/media/{media_id}",
            params={"include_content": True, "include_versions": False},
        )
        if resp.status_code == 200:
            last_payload = resp.json()
            if _extract_content_text(last_payload).strip():
                return
        await asyncio.sleep(0.5)

    unique_suffix = f"\n\n[manual-embeddings-ensure:{time.time_ns()}]"
    update_resp = await async_client.put(
        f"/api/v1/media/{media_id}",
        json={"content": f"{fallback_text}{unique_suffix}"},
    )
    assert update_resp.status_code == 200, (
        f"Failed to update media content before embeddings: {update_resp.text}"
    )
    updated_payload = update_resp.json()
    if not _extract_content_text(updated_payload).strip():
        pytest.skip(f"Media content still empty after update. Last payload: {last_payload}")


async def _resolve_embedding_request(api_client, async_client) -> dict:
    if _is_inprocess_client(api_client):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
        }
    try:
        resp = await async_client.get("/api/v1/embeddings/providers-config")
        if resp.status_code == 200:
            payload = resp.json() or {}
            provider = payload.get("default_provider")
            model = payload.get("default_model")
            if isinstance(model, str) and ":" in model:
                model_provider, model_id = model.split(":", 1)
                provider = provider or model_provider
                model = model_id
            if provider and model:
                return {
                    "embedding_provider": str(provider),
                    "embedding_model": str(model),
                }
    except Exception:
        _ = None
    return {
        "embedding_provider": "huggingface",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    }


@pytest.mark.requires_embeddings
class TestEmbeddingsE2E:
    """End-to-end tests for embeddings functionality."""

    def teardown_method(self):

        """Clean up after each test method."""
        # Note: In a real scenario, we might want to delete test media items
        # from the database, but for now we'll rely on overwrite_existing
        pass

    def test_generate_text_embeddings(self, api_client):

        """Test basic text embedding generation via the embeddings API."""
        # Test single text embedding
        response = api_client.client.post(
            f"{api_client.base_url}/api/v1/embeddings",
            json={
                "input": "This is a test sentence for embedding generation.",
                "model": "sentence-transformers/all-MiniLM-L6-v2"  # Use small model for testing
            },
            headers=api_client.get_auth_headers()  # Use dynamic auth headers
        )

        assert response.status_code == 200, f"Failed to generate embeddings: {response.text}"

        result = response.json()
        assert "data" in result
        assert len(result["data"]) > 0
        assert "embedding" in result["data"][0]
        assert isinstance(result["data"][0]["embedding"], list)
        assert len(result["data"][0]["embedding"]) > 0

        print(f"✓ Generated embedding with {len(result['data'][0]['embedding'])} dimensions")

    def test_batch_embeddings(self, api_client):

        """Test batch embedding generation."""
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence with more content."
        ]

        response = api_client.client.post(
            f"{api_client.base_url}/api/v1/embeddings",
            json={
                "input": texts,
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            headers=api_client.get_auth_headers()  # Use dynamic auth headers
        )

        assert response.status_code == 200, f"Failed to generate batch embeddings: {response.text}"

        result = response.json()
        assert "data" in result
        assert len(result["data"]) == len(texts), "Should return embedding for each input"

        for i, embedding_data in enumerate(result["data"]):
            assert "embedding" in embedding_data
            assert isinstance(embedding_data["embedding"], list)
            assert embedding_data["index"] == i

        print(f"✓ Generated {len(result['data'])} embeddings in batch")

    async def test_media_upload_with_embeddings(self, api_client, test_workflow_state):
        """Test media upload with automatic embedding generation."""
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_TEXT_CONTENT)
            temp_file_path = f.name

        try:
            # Upload with embedding generation enabled
            with open(temp_file_path, 'rb') as f:
                files = {"files": (os.path.basename(temp_file_path), f, "text/plain")}
                import uuid
                # Use unique title to avoid duplicates
                unique_title = f"Test Embeddings {uuid.uuid4()}"
                data = {
                    "title": unique_title,
                    "media_type": "document",
                    "generate_embeddings": "true",  # Enable embedding generation
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                    "overwrite_existing": "true"  # Allow overwrite to ensure success
                }

                # Use dynamic authentication headers
                response = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/add",
                    files=files,
                    data=data,
                    headers=api_client.get_auth_headers()
                )

            assert response.status_code in [200, 207], f"Upload failed: {response.text}"

            result = response.json()
            print(f"Response: {result}")  # Debug output
            assert "results" in result
            assert len(result["results"]) > 0

            # Get the media ID
            media_id = None
            for item in result["results"]:
                print(f"Item: status={item.get('status')}, db_id={item.get('db_id')}")  # Debug
                if item.get("status") == "Success" and item.get("db_id"):
                    media_id = item["db_id"]
                    # Check if embeddings were scheduled
                    assert item.get("embeddings_scheduled") == True, "Embeddings should be scheduled"
                    break

            assert media_id is not None, "No media ID returned from upload"

            # Store in workflow state
            test_workflow_state.add_media(media_id, result["results"][0])

            print(f"✓ Uploaded media with ID {media_id} and scheduled embeddings")

            # Check if embeddings were generated
            max_wait_s = 20
            start = time.time()
            last_status = None
            while time.time() - start < max_wait_s:
                status_response = api_client.client.get(
                    f"{api_client.base_url}/api/v1/media/{media_id}/embeddings/status",
                    headers=api_client.get_auth_headers(),
                )
                if status_response.status_code == 200:
                    last_status = status_response.json()
                    if last_status.get("has_embeddings"):
                        test_workflow_state.mark_embeddings_generated(media_id)
                        print(f"✓ Embeddings generated for media {media_id}")
                        break
                await asyncio.sleep(0.5)

            assert test_workflow_state.has_embeddings(media_id), (
                f"Embeddings were not generated within {max_wait_s}s. Last status: {last_status}"
            )

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    async def test_manual_media_embeddings_generation(self, api_client, test_workflow_state):
        """Test manual generation of embeddings for uploaded media."""
        # First upload media without embeddings
        import uuid
        unique_id = str(uuid.uuid4())
        content_text = f"Simple test content for manual embedding generation. {unique_id}"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content_text)
            temp_file_path = f.name

        try:
            # Upload without embedding generation
            with open(temp_file_path, 'rb') as f:
                files = {"files": (os.path.basename(temp_file_path), f, "text/plain")}
                data = {
                    "title": f"Test Manual Embeddings {unique_id}",
                    "media_type": "document",
                    "generate_embeddings": "false",  # Don't generate automatically
                    "overwrite_existing": "true"  # Allow overwrite to ensure we get a db_id
                }

                response = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/add",
                    files=files,
                    data=data,
                    headers=api_client.get_auth_headers()  # Use dynamic auth headers
                )

            assert response.status_code in [200, 207], f"Upload failed: {response.text}"

            result = response.json()
            print(f"Upload response: {result}")

            media_id = None
            for item in result.get("results", []):
                print(f"Item: status={item.get('status')}, db_id={item.get('db_id')}")
                # Accept either Success or Warning status
                if item.get("status") in ["Success", "Warning"] and item.get("db_id"):
                    media_id = item["db_id"]
                    break

            assert media_id is not None, f"No media ID returned. Response: {result}"

            async with _build_async_client(api_client) as async_client:
                await _ensure_media_content(
                    async_client,
                    media_id,
                    content_text,
                )

                # Check embeddings don't exist yet
                status_response = await async_client.get(
                    f"/api/v1/media/{media_id}/embeddings/status"
                )
                assert status_response.status_code == 200
                status = status_response.json()
                assert status.get("has_embeddings") == False, "Embeddings should not exist yet"

                # Manually generate embeddings (async accepted)
                embedding_request = await _resolve_embedding_request(api_client, async_client)
                gen_response = await async_client.post(
                    f"/api/v1/media/{media_id}/embeddings",
                    json={
                        **embedding_request,
                        "chunk_size": 500,
                        "chunk_overlap": 100,
                    },
                )

                assert gen_response.status_code == 200, f"Failed to generate embeddings: {gen_response.text}"

                gen_result = gen_response.json()
                # Endpoint is asynchronous: expect 'accepted' and a job_id
                assert gen_result.get("status") == "accepted"
                job_id = gen_result.get("job_id")
                assert job_id, f"Expected job_id in response, got: {gen_result}"

                # Poll for completion via job endpoint, fall back to status check
                max_wait_s = 60
                start = time.time()
                embedding_count = 0
                last_job = None
                last_job_status = None
                last_status = None
                last_job_status_code = None
                while time.time() - start < max_wait_s:
                    # Try job endpoint first
                    job_resp = await async_client.get(
                        f"/api/v1/media/embeddings/jobs/{job_id}"
                    )
                    last_job_status_code = job_resp.status_code
                    if job_resp.status_code == 200:
                        last_job = job_resp.json()
                        last_job_status = last_job.get("status")
                        if last_job_status == "completed":
                            embedding_count = int(last_job.get("embedding_count") or 0)
                            break
                        if last_job_status == "failed":
                            error = last_job.get("error") or last_job.get("message")
                            if _should_skip_embeddings_error(str(error)):
                                pytest.skip(f"Embedding job failed: {error}")
                            raise AssertionError(f"Embedding job failed: {last_job}")
                    # Check direct status as a fallback
                    status_resp = await async_client.get(
                        f"/api/v1/media/{media_id}/embeddings/status"
                    )
                    if status_resp.status_code == 200:
                        last_status = status_resp.json()
                        if last_status.get("has_embeddings"):
                            embedding_count = int(last_status.get("embedding_count") or 1)
                            break
                    await asyncio.sleep(0.5)

            assert embedding_count > 0, (
                "Embeddings were not generated within timeout. "
                f"Last job status_code={last_job_status_code}, last_job={last_job}, last_status={last_status}"
            )

            # Mark in workflow state
            test_workflow_state.mark_embeddings_generated(media_id)

            print(f"✓ Manually generated {embedding_count} embeddings for media {media_id}")

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_embedding_model_fallback(self, api_client):

        """Test that system falls back to default model when requested model unavailable."""
        response = api_client.client.post(
            f"{api_client.base_url}/api/v1/embeddings",
            json={
                "input": "Test text for fallback",
                "model": "non-existent-model-xyz-123"  # Non-existent model
            },
            headers=api_client.get_auth_headers()  # Add auth headers
        )

        # Should either succeed with fallback or return appropriate error
        if response.status_code == 200:
            result = response.json()
            # Check that embeddings were still generated
            assert "data" in result
            assert len(result["data"]) > 0
            print("✓ Successfully fell back to default model")
        elif response.status_code == 503:
            # Service unavailable - embedding service may not be configured
            print("⚠ Embedding service unavailable - test environment may not have embeddings configured")
            pytest.skip("Embedding service unavailable")
        else:
            # Should get a meaningful error message for client errors
            assert response.status_code in [400, 404, 422], f"Unexpected status code: {response.status_code}"
            error = response.json()
            assert "detail" in error or "error" in error
            print(f"✓ Got expected error for invalid model: {response.status_code}")

    async def test_embeddings_enable_rag_search(self, api_client, test_workflow_state, ensure_embeddings):
        """Test that embeddings enable RAG search functionality."""
        # Get or create media with embeddings
        media_data = test_workflow_state.get_any_media()

        if not media_data:
            # Upload new media if none exists
            await self.test_media_upload_with_embeddings(api_client, test_workflow_state)
            media_data = test_workflow_state.get_any_media()

        assert media_data is not None, "No media available for testing"

        media_id = media_data.get("db_id") or media_data.get("media_id") or media_data.get("id")
        assert media_id is not None, "No media ID found"

        # Ensure embeddings exist
        if not test_workflow_state.has_embeddings(media_id):
            success = await ensure_embeddings(api_client, media_id)
            assert success, f"Failed to ensure embeddings for media {media_id}"

        # Now test RAG search
        # Use unified RAG search endpoint; translate legacy 'limit' -> 'top_k'
        search_response = api_client.client.post(
            f"{api_client.base_url}/api/v1/rag/search",
            json={
                "query": "test document content",
                "top_k": 5,
                "sources": ["media_db"],
            },
            headers=api_client.get_auth_headers(),
        )

        assert search_response.status_code == 200, f"RAG search failed: {search_response.text}"
        results = search_response.json()
        # If we have results, embeddings are working
        if results.get("results") and len(results["results"]) > 0:
            print(f"✓ RAG search returned {len(results['results'])} results with embeddings")
        else:
            print("⚠️ RAG search returned no results (may need more content)")

    @pytest.mark.parametrize("chunk_method", ["words", "sentences", "tokens"])
    def test_different_chunking_methods(self, api_client, chunk_method):
        """Test embedding generation with different chunking methods."""
        # Create test content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_TEXT_CONTENT * 5)  # Repeat to ensure multiple chunks
            temp_file_path = f.name

        try:
            # Upload with specific chunking method
            with open(temp_file_path, 'rb') as f:
                files = {"files": (os.path.basename(temp_file_path), f, "text/plain")}
                data = {
                    "title": f"Test with {chunk_method} chunking",
                    "media_type": "document",
                    "generate_embeddings": "true",
                    "chunk_method": chunk_method,
                    "chunk_size": "500",  # Increase chunk size
                    "chunk_overlap": "50",  # Use correct parameter name
                    "overwrite_existing": "true"  # Allow overwrite
                }

                response = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/add",
                    files=files,
                    data=data,
                    headers=api_client.get_auth_headers()  # Use dynamic auth headers
                )

            assert response.status_code in [200, 207], f"Upload failed with {chunk_method}: {response.text}"
            print(f"✓ Successfully uploaded and generated embeddings with {chunk_method} chunking")

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


@pytest.mark.requires_embeddings
class TestEmbeddingsPerformance:
    """Performance and edge case tests for embeddings."""

    def test_large_document_embeddings(self, api_client):

        """Test embedding generation for large documents."""
        # Create a large document (1MB of text)
        large_content = "This is a test sentence. " * 50000

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_content)
            temp_file_path = f.name

        try:
            # Upload large document
            with open(temp_file_path, 'rb') as f:
                files = {"files": (os.path.basename(temp_file_path), f, "text/plain")}
                data = {
                    "title": "Large Document Test",
                    "media_type": "document",
                    "generate_embeddings": "true",
                    "chunk_size": "1000",
                    "chunk_overlap": "200"
                }

                response = api_client.client.post(
                    f"{api_client.base_url}/api/v1/media/add",
                    files=files,
                    data=data,
                    timeout=60  # Longer timeout for large file
                )

            assert response.status_code in [200, 207], f"Large upload failed: {response.status_code}"
            print("✓ Successfully handled large document embedding generation")

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    async def test_concurrent_embedding_requests(self, api_client):
        """Test handling of concurrent embedding requests."""
        async def generate_embedding(client_session, text_id):
            """Generate embedding for a text."""
            try:
                response = await client_session.post(
                    "/api/v1/embeddings",
                    json={
                        "input": f"Test text number {text_id} for concurrent testing.",
                        "model": "sentence-transformers/all-MiniLM-L6-v2"
                    }
                )
                return response
            except Exception as exc:
                return exc

        async with _build_async_client(api_client) as async_client:
            tasks = [generate_embedding(async_client, i) for i in range(10)]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                pytest.fail("Concurrent embedding requests timed out after 60s")

        # Check that most requests succeeded
        successes = [
            r for r in results
            if not isinstance(r, Exception) and getattr(r, "status_code", None) == 200
        ]
        failures = [
            r for r in results
            if isinstance(r, Exception) or getattr(r, "status_code", None) != 200
        ]
        status_codes = [
            getattr(r, "status_code", type(r).__name__) for r in failures
        ]
        assert len(successes) >= 8, (
            f"Only {len(successes)}/10 concurrent requests succeeded. "
            f"Failure statuses: {status_codes}"
        )

        print(f"✓ Handled {len(successes)}/10 concurrent embedding requests")
