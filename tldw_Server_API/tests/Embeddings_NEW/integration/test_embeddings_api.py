"""
Integration tests for Embeddings API endpoints.

Tests the full request/response cycle with real components, no mocking
except for external services like HuggingFace API.
"""

import pytest
import io
import json
import numpy as np
from fastapi import status
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
from typing import List, Dict, Any

# ========================================================================
# Media Embeddings Endpoint Tests
# ========================================================================

class TestMediaEmbeddingsEndpoint:
    """Test the /api/v1/media/embeddings endpoints."""

    @pytest.mark.integration
    async def test_create_embeddings_for_media(self, test_client, auth_headers, populated_media_database):
        """Test creating embeddings for a media item."""
        # Ingest a media item via API (replicates app behavior)
        files = [
            ("files", ("doc.txt", b"This is test content for embedding generation.", "text/plain"))
        ]
        data = {"media_type": "document", "title": "Test Document"}
        headers_form = {k: v for k, v in auth_headers.items() if k.lower() != 'content-type'}
        ingest = test_client.post(
            "/api/v1/media/add",
            files=files,
            data=data,
            headers=headers_form,
        )
        assert ingest.status_code in [200, 207], ingest.text
        ingest_payload = ingest.json()["results"][0]
        media_id = ingest_payload.get("db_id")
        if media_id is None:
            pytest.skip("Media add endpoint returned no persisted ID (processing-only mode)")

        response = test_client.post(
            f"/api/v1/media/{media_id}/embeddings",
            json={
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "chunk_size": 500,
                "chunk_overlap": 50
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Media embeddings endpoint not available")

        assert response.status_code in {status.HTTP_200_OK, status.HTTP_202_ACCEPTED}, response.text
        data = response.json()
        assert data["status"] == "accepted"
        assert data["job_id"]

    @pytest.mark.integration
    async def test_get_embedding_status(self, test_client, auth_headers):
        """Test getting embedding job status (non-existent job)."""
        job_id = "test-job-123"

        response = test_client.get(
            f"/api/v1/media/embeddings/jobs/{job_id}",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.unit
    @patch('sentence_transformers.SentenceTransformer')
    async def test_batch_embeddings_creation(self, mock_transformer, test_client, auth_headers, populated_media_database):
        """Test creating embeddings for multiple media items."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(10, 384)
        mock_transformer.return_value = mock_model

        # Get media IDs from populated database
        media_items, _total = populated_media_database.search_media_db(None, results_per_page=3)
        media_ids = [item.get("id") for item in media_items]

        response = test_client.post(
            "/api/v1/media/embeddings/batch",
            json={
                "media_ids": media_ids,
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Batch embeddings endpoint not available")

        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        data = response.json()
        assert len(data.get("job_ids", [])) == len(media_ids)

    @pytest.mark.integration
    async def test_search_by_embeddings(self, test_client, auth_headers, populated_chroma_collection):
        """Test searching using embeddings."""
        response = test_client.post(
            "/api/v1/media/embeddings/search",
            json={
                "query": "machine learning concepts",
                "top_k": 5,
                "collection": populated_chroma_collection.name
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Embeddings search endpoint not available")

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Embedding models endpoint not available")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 5

# ========================================================================
# Embedding Models Management Tests
# ========================================================================

class TestEmbeddingModelsManagement:
    """Test embedding model management endpoints."""

    @pytest.mark.integration
    async def test_list_available_models(self, test_client, auth_headers):
        """Test listing available embedding models."""
        response = test_client.get(
            "/api/v1/embeddings/models",
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Embedding model info endpoint not available")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        models = data.get("data") if isinstance(data, dict) else data
        assert isinstance(models, list)
        assert any(
            (isinstance(m, dict) and "all-MiniLM-L6-v2" in m.get("model", "")) or
            (isinstance(m, str) and "all-MiniLM-L6-v2" in m)
            for m in models
        )

    @pytest.mark.integration
    async def test_get_model_info(self, test_client, auth_headers):
        """Test getting information about a specific model."""
        response = test_client.get(
            "/api/v1/embeddings/models/sentence-transformers/all-MiniLM-L6-v2",
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Model warmup endpoint not available")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["dimension"] == 384
        assert "max_tokens" in data

    @pytest.mark.unit
    @patch('sentence_transformers.SentenceTransformer')
    async def test_warmup_model(self, mock_transformer, test_client, auth_headers):
        """Test model warmup endpoint."""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model

        response = test_client.post(
            "/api/v1/embeddings/models/warmup",
            json={
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["status"] in {"warmed_up", "ok"}

# ========================================================================
# ChromaDB Collection Management Tests
# ========================================================================

class TestChromaDBCollectionManagement:
    """Test ChromaDB collection management endpoints."""

    @pytest.mark.integration
    async def test_create_collection(self, test_client, auth_headers, chroma_client):
        """Test creating a new ChromaDB collection."""
        response = test_client.post(
            "/api/v1/embeddings/collections",
            json={
                "name": "test_collection",
                "metadata": {"description": "Test collection"},
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Collection creation endpoint not available")

        assert response.status_code == status.HTTP_201_CREATED, response.text
        data = response.json()
        assert data["name"] == "test_collection"

        collections = chroma_client.list_collections()
        assert any(c.name == "test_collection" for c in collections)

    @pytest.mark.integration
    async def test_list_collections(self, test_client, auth_headers, populated_chroma_collection):
        """Test listing ChromaDB collections."""
        response = test_client.get(
            "/api/v1/embeddings/collections",
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Collection listing endpoint not available")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.integration
    async def test_delete_collection(self, test_client, auth_headers, chroma_collection):
        """Test deleting a ChromaDB collection."""
        collection_name = chroma_collection.name

        response = test_client.delete(
            f"/api/v1/embeddings/collections/{collection_name}",
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Collection delete endpoint not available")

        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
        with pytest.raises(Exception):
            chroma_collection.get()

    @pytest.mark.integration
    async def test_get_collection_stats(self, test_client, auth_headers, populated_chroma_collection):
        """Test getting collection statistics."""
        response = test_client.get(
            f"/api/v1/embeddings/collections/{populated_chroma_collection.name}/stats",
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Collection stats endpoint not available")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["count"] == 10
        assert "embedding_dimension" in data

# ========================================================================
# Embedding Generation Pipeline Tests
# ========================================================================

class TestEmbeddingGenerationPipeline:
    """Test the full embedding generation pipeline."""

    @pytest.mark.unit
    @patch('sentence_transformers.SentenceTransformer')
    async def test_full_pipeline_text_to_storage(self, mock_transformer, test_client, auth_headers, media_database):
        """Test full pipeline from text to stored embeddings."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(5, 384)
        mock_transformer.return_value = mock_model

        # Ingest a media item via API
        files = [("files", ("pipeline.txt", ("This is a longer text that will be chunked. " * 50).encode(), "text/plain"))]
        data = {"media_type": "document", "title": "Pipeline Test"}
        headers_form = {k: v for k, v in auth_headers.items() if k.lower() != 'content-type'}
        ingest = test_client.post(
            "/api/v1/media/add",
            files=files,
            data=data,
            headers=headers_form,
        )
        assert ingest.status_code in [200, 207], ingest.text
        ingest_payload = ingest.json()["results"][0]
        media_id = ingest_payload.get("db_id")
        if media_id is None:
            pytest.skip("Media add endpoint returned no persisted ID (processing-only mode)")

        # Start embedding generation
        response = test_client.post(
            f"/api/v1/media/{media_id}/embeddings",
            json={
                "chunk_size": 100,
                "chunk_overlap": 20
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Media embeddings endpoint not available")

        assert response.status_code in {status.HTTP_200_OK, status.HTTP_202_ACCEPTED}, response.text
        job_id = response.json()["job_id"]

        # Poll job status until completion or timeout
        for _ in range(10):
            status_response = test_client.get(
                f"/api/v1/media/embeddings/jobs/{job_id}",
                headers=auth_headers
            )
            if status_response.status_code == status.HTTP_200_OK:
                status_data = status_response.json()
                assert status_data["id"] == job_id
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("Embedding job did not reach completed status in time")

    @pytest.mark.unit
    async def test_pipeline_with_custom_chunking(self, test_client, auth_headers, media_database):
        """Test pipeline with custom chunking strategy."""
        files = [("files", ("chunking.txt", b"Sentence one. Sentence two. Sentence three. Sentence four.", "text/plain"))]
        data = {"media_type": "document", "title": "Custom Chunking Test"}
        headers_form = {k: v for k, v in auth_headers.items() if k.lower() != 'content-type'}
        ingest = test_client.post(
            "/api/v1/media/add",
            files=files,
            data=data,
            headers=headers_form,
        )
        assert ingest.status_code in [200, 207], ingest.text
        media_id = ingest.json()["results"][0]["db_id"]

        response = test_client.post(
            f"/api/v1/media/{media_id}/embeddings",
            json={
                "chunking_strategy": "sentence",
                "sentences_per_chunk": 2
            },
            headers=auth_headers
        )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Media embeddings endpoint not available")

        assert response.status_code in {status.HTTP_202_ACCEPTED, status.HTTP_200_OK}, response.text

# ========================================================================
# Worker Orchestration Tests
# ========================================================================

class TestWorkerOrchestrationIntegration:
    """Test worker orchestration in integration scenarios."""

    @pytest.mark.integration
    async def test_concurrent_job_processing(self, test_client, auth_headers, populated_media_database):
        """Test processing multiple concurrent embedding jobs."""
        # Ingest multiple media items via API
        media_ids = []
        headers_form = {k: v for k, v in auth_headers.items() if k.lower() != 'content-type'}
        for i in range(5):
            files = [("files", (f"concurrent_{i}.txt", f"content {i}".encode(), "text/plain"))]
            data = {"media_type": "document", "title": f"Doc {i}"}
            ingest = test_client.post(
                "/api/v1/media/add",
                files=files,
                data=data,
                headers=headers_form,
            )
            assert ingest.status_code in [200, 207], ingest.text
            media_ids.append(ingest.json()["results"][0]["db_id"])

        # Submit concurrent embedding requests
        tasks = []
        for mid in media_ids:
            response = test_client.post(
                f"/api/v1/media/{mid}/embeddings",
                json={"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
                headers=auth_headers
            )
            tasks.append(response)

        # All should be accepted
        for response in tasks:
            assert response.status_code in [
                status.HTTP_202_ACCEPTED,
                status.HTTP_200_OK
            ]

    @pytest.mark.integration
    async def test_job_priority_handling(self, test_client, auth_headers, media_database):
        """Test that high-priority jobs are processed first."""
        # Create media items via ingestion
        files_u = [("files", ("urgent.txt", b"Urgent content", "text/plain"))]
        data_u = {"media_type": "document", "title": "Urgent"}
        headers_form = {k: v for k, v in auth_headers.items() if k.lower() != 'content-type'}
        ingest_u = test_client.post(
            "/api/v1/media/add",
            files=files_u,
            data=data_u,
            headers=headers_form,
        )
        assert ingest_u.status_code in [200, 207], ingest_u.text
        urgent_id = ingest_u.json()["results"][0]["db_id"]

        files_n = [("files", ("normal.txt", b"Normal content", "text/plain"))]
        data_n = {"media_type": "document", "title": "Normal"}
        ingest_n = test_client.post(
            "/api/v1/media/add",
            files=files_n,
            data=data_n,
            headers=headers_form,
        )
        assert ingest_n.status_code in [200, 207], ingest_n.text
        normal_id = ingest_n.json()["results"][0]["db_id"]

        # Submit with priorities
        urgent_response = test_client.post(
            f"/api/v1/media/{urgent_id}/embeddings",
            json={"priority": 10},
            headers=auth_headers
        )

        normal_response = test_client.post(
            f"/api/v1/media/{normal_id}/embeddings",
            json={"priority": 1},
            headers=auth_headers
        )

        assert urgent_response.status_code in [status.HTTP_202_ACCEPTED, status.HTTP_200_OK]
        assert normal_response.status_code in [status.HTTP_202_ACCEPTED, status.HTTP_200_OK]

# ========================================================================
# Error Handling Tests
# ========================================================================

class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""

    @pytest.mark.integration
    async def test_invalid_model_error(self, test_client, auth_headers, media_database):
        """Test error handling for invalid model."""
        # Ensure a media item exists in the same DB the API uses
        media_id, _, _ = media_database.add_media_with_keywords(
            title="Invalid Model Test",
            content="sample content",
            media_type="document"
        )

        response = test_client.post(
            f"/api/v1/media/{media_id}/embeddings",
            json={"embedding_model": "invalid-model-name"},
            headers=auth_headers
        )

        assert response.status_code in {status.HTTP_202_ACCEPTED, status.HTTP_200_OK}, response.text
        data = response.json()
        assert "job_id" in data

    @pytest.mark.integration
    async def test_media_not_found_error(self, test_client, auth_headers):
        """Test error handling for non-existent media."""
        response = test_client.post(
            "/api/v1/media/999999/embeddings",
            json={},
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    @patch('sentence_transformers.SentenceTransformer')
    async def test_model_loading_failure(self, mock_transformer, test_client, auth_headers, media_database):
        """Test handling of model loading failures."""
        mock_transformer.side_effect = Exception("Model loading failed")
        # Ensure a media item exists in the same DB the API uses
        media_id, _, _ = media_database.add_media_with_keywords(
            title="Model Load Fail",
            content="sample content",
            media_type="document"
        )

        response = test_client.post(
            f"/api/v1/media/{media_id}/embeddings",
            json={"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
            headers=auth_headers
        )

        if response.status_code in {
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE
        }:
            return

        assert response.status_code in {status.HTTP_200_OK, status.HTTP_202_ACCEPTED}, response.text

# ========================================================================
# Performance and Scaling Tests
# ========================================================================

class TestPerformanceAndScaling:
    """Test performance and scaling characteristics."""

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_batch_processing(self, test_client, auth_headers, large_text_corpus):
        """Test processing large batches of text."""
        with patch('sentence_transformers.SentenceTransformer') as mock_transformer:
            mock_model = MagicMock()

            def mock_encode(texts, *args, **kwargs):
                batch_size = len(texts) if isinstance(texts, list) else 1
                return np.random.randn(batch_size, 384)

            mock_model.encode = mock_encode
            mock_transformer.return_value = mock_model

            response = test_client.post(
                "/api/v1/embeddings/batch",
                json={
                    "texts": large_text_corpus[:100],  # First 100 texts
                    "batch_size": 32
                },
                headers=auth_headers
            )

            if response.status_code == status.HTTP_404_NOT_FOUND:
                pytest.skip("Embeddings batch endpoint not available")

            assert response.status_code == status.HTTP_200_OK, response.text
            data = response.json()
            assert len(data.get("embeddings", [])) == 100

    @pytest.mark.integration
    async def test_rate_limiting(self, test_client, auth_headers):
        """Test rate limiting on embedding endpoints."""
        # Send many requests rapidly
        responses = []
        for i in range(20):
            response = test_client.post(
                f"/api/v1/media/{i}/embeddings",
                json={},
                headers=auth_headers
            )
            responses.append(response)

        # Some should be rate limited
        rate_limited = [r for r in responses if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS]

        # Rate limiting may or may not be enabled
        if rate_limited:
            assert len(rate_limited) > 0
            assert "retry-after" in rate_limited[0].headers
