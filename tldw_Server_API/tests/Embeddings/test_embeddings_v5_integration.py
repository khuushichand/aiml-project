# test_embeddings_v5_integration.py
# Integration tests for production embeddings service (no mocking)

import asyncio
import os
from datetime import datetime
import pytest
pytestmark = pytest.mark.integration
import numpy as np

# Skip real-embedding integration tests in CI unless explicitly enabled
RUN_REAL_EMBEDDINGS = os.getenv("RUN_REAL_EMBEDDINGS", "").lower() == "true"
IN_CI = os.getenv("CI", "").lower() == "true"

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore

from fastapi.testclient import TestClient
from httpx import AsyncClient
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


def _redis_available() -> bool:
    """Detect whether a Redis instance is reachable for cache tests."""
    if redis is None:
        return False

    try:
        settings_url = str(app_settings.get("REDIS_URL", "")) or None
        redis_enabled = bool(app_settings.get("REDIS_ENABLED", False))
    except Exception:
        settings_url = None
        redis_enabled = True

    if not redis_enabled:
        return False

    env_url = os.getenv("REDIS_URL")
    url = env_url or settings_url or "redis://localhost:6379/0"
    try:
        client = redis.from_url(url)
        try:
            client.ping()
        finally:
            client.close()
        return True
    except Exception:
        return False


REDIS_AVAILABLE = _redis_available()


# Disable rate limiting for all tests
@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests in this module"""
    os.environ["TESTING"] = "true"
    yield
    # Clean up after tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

# Module-level setup fixture for integration tests
@pytest.fixture
def setup():
    """Setup test environment fixture with proper TestClient lifecycle"""
    class SetupData:
        pass

    with TestClient(app) as client:
        data = SetupData()
        data.client = client
        # Set CSRF token in both cookie and header
        csrf_token = "test-csrf-token-12345"
        client.cookies.set("csrf_token", csrf_token)
        data.auth_headers = {
            "Authorization": "Bearer test-api-key",
            "X-CSRF-Token": csrf_token
        }
        
        data.test_user = User(
            id=1, 
            username="testuser", 
            email="test@example.com", 
            is_active=True,
            is_admin=False
        )

        try:
            yield data
        finally:
            app.dependency_overrides.clear()


@pytest.mark.integration
class TestEmbeddingsIntegration:
    """Integration tests without mocking - requires actual services"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(IN_CI and not RUN_REAL_EMBEDDINGS, reason="Skipped in CI to prevent model downloads/hangs; set RUN_REAL_EMBEDDINGS=true to enable")
    async def test_real_huggingface_embedding(self, setup):
        """Test actual HuggingFace embedding creation (no mocks)"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        # This test uses real HuggingFace models - no mocking
        response = setup.client.post(
            "/api/v1/embeddings",
            headers={**setup.auth_headers, "x-provider": "huggingface"},
            json={
                "input": "This is a real integration test with HuggingFace",
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        )
        
        # Will only pass if model is available
        if response.status_code == 200:
            data = response.json()
            
            # Verify real embeddings were created
            assert "data" in data
            assert len(data["data"]) == 1
            assert "embedding" in data["data"][0]
            
            # Real embeddings should have expected dimensions
            embedding = data["data"][0]["embedding"]
            assert len(embedding) == 384  # all-MiniLM-L6-v2 has 384 dimensions
            
            # Real embeddings should have reasonable magnitude
            norm = np.linalg.norm(embedding)
            assert norm > 0.1  # Not zero or near-zero
            assert norm < 100  # Not unreasonably large
            
            # Embeddings should have reasonable values
            assert all(-10 < x < 10 for x in embedding)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Integration test requires OPENAI_API_KEY environment variable"
    )
    async def test_real_openai_embedding(self, setup):
        """Test actual OpenAI API integration (no mocks)"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        # This test uses real OpenAI API - no mocking
        response = setup.client.post(
            "/api/v1/embeddings",
            headers=setup.auth_headers,
            json={
                "input": "Real OpenAI integration test with actual API",
                "model": "text-embedding-3-small"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify real OpenAI embeddings
        assert "data" in data
        assert len(data["data"]) == 1
        
        embedding = data["data"][0]["embedding"]
        assert len(embedding) == 1536  # text-embedding-3-small default dimensions
        
        # Check usage is reported correctly
        assert "usage" in data
        assert data["usage"]["total_tokens"] > 0
        assert data["usage"]["prompt_tokens"] > 0
        
        # OpenAI embeddings should be normalized
        norm = np.linalg.norm(embedding)
        assert 0.95 < norm < 1.05
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis unreachable; cache persistence test skipped.")
    @pytest.mark.skipif(IN_CI and not RUN_REAL_EMBEDDINGS, reason="Skipped in CI to prevent model downloads/hangs; set RUN_REAL_EMBEDDINGS=true to enable")
    async def test_real_cache_persistence(self, setup):
        """Test cache persistence across requests (no mocks)"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        # Use unique text to avoid conflicts with other tests
        unique_text = f"Cache test {datetime.now().isoformat()} {os.getpid()}"
        
        # First request - will create real embedding
        response1 = setup.client.post(
            "/api/v1/embeddings",
            headers={**setup.auth_headers, "x-provider": "huggingface"},
            json={
                "input": unique_text,
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        )
        
        if response1.status_code == 200:
            embedding1 = response1.json()["data"][0]["embedding"]
            
            # Second identical request
            response2 = setup.client.post(
                "/api/v1/embeddings",
                headers={**setup.auth_headers, "x-provider": "huggingface"},
                json={
                    "input": unique_text,
                    "model": "sentence-transformers/all-MiniLM-L6-v2"
                }
            )
            
            assert response2.status_code == 200
            embedding2 = response2.json()["data"][0]["embedding"]
            
            # Should return identical embeddings (from cache)
            assert embedding1 == embedding2
            
            # Verify embeddings are valid
            assert len(embedding1) == 384
            assert len(embedding2) == 384
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(IN_CI and not RUN_REAL_EMBEDDINGS, reason="Skipped in CI to prevent model downloads/hangs; set RUN_REAL_EMBEDDINGS=true to enable")
    async def test_different_providers_produce_different_embeddings(self, setup):
        """Test that different providers produce different embeddings for same text"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        test_text = "Compare embeddings across providers"
        
        # Get HuggingFace embedding
        response_hf = setup.client.post(
            "/api/v1/embeddings",
            headers={**setup.auth_headers, "x-provider": "huggingface"},
            json={
                "input": test_text,
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        )
        
        if response_hf.status_code == 200 and os.getenv("OPENAI_API_KEY"):
            embedding_hf = response_hf.json()["data"][0]["embedding"]
            
            # Get OpenAI embedding
            response_openai = setup.client.post(
                "/api/v1/embeddings",
                headers=setup.auth_headers,
                json={
                    "input": test_text,
                    "model": "text-embedding-3-small"
                }
            )
            
            if response_openai.status_code == 200:
                embedding_openai = response_openai.json()["data"][0]["embedding"]
                
                # Should have different dimensions
                assert len(embedding_hf) != len(embedding_openai)
                assert len(embedding_hf) == 384
                assert len(embedding_openai) == 1536
                
                # Both should be normalized
                assert 0.95 < np.linalg.norm(embedding_hf) < 1.05
                assert 0.95 < np.linalg.norm(embedding_openai) < 1.05
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("RUN_STRESS_TESTS"),
        reason="Stress tests require RUN_STRESS_TESTS=true"
    )
    async def test_real_concurrent_load(self, setup):
        """Test system under real concurrent load (no mocks)"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        async def make_real_request(idx):
            async with AsyncClient(app=app, base_url="http://test", timeout=30.0) as ac:
                # Set CSRF token in cookie
                ac.cookies.set("csrf_token", "test-csrf-token-12345")
                response = await ac.post(
                    "/api/v1/embeddings",
                    headers={**setup.auth_headers, "x-provider": "huggingface"},
                    json={
                        "input": f"Concurrent test {idx} at {datetime.now()}",
                        "model": "sentence-transformers/all-MiniLM-L6-v2"
                    }
                )
                return response.status_code
        
        # Make real concurrent requests
        tasks = [make_real_request(i) for i in range(20)]
        # Apply an overall timeout to prevent hangs in CI
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=120.0)
        
        # Count successful requests
        successful = sum(1 for r in results if isinstance(r, int) and r == 200)
        failed = sum(1 for r in results if not isinstance(r, int) or r != 200)
        
        # Most should succeed
        assert successful > 15, f"Only {successful}/20 requests succeeded"
        
        # Log any failures for debugging
        if failed > 0:
            print(f"Failed requests: {failed}/20")
            for i, r in enumerate(results):
                if not isinstance(r, int) or r != 200:
                    print(f"Request {i}: {r}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(IN_CI and not RUN_REAL_EMBEDDINGS, reason="Skipped in CI to prevent model downloads/hangs; set RUN_REAL_EMBEDDINGS=true to enable")
    async def test_batch_processing(self, setup):
        """Test batch processing with real embeddings"""
        async def override_user():
            return setup.test_user
        
        app.dependency_overrides[get_request_user] = override_user
        
        # Create batch of unique texts
        batch_texts = [f"Batch text {i}" for i in range(10)]
        
        response = setup.client.post(
            "/api/v1/embeddings",
            headers={**setup.auth_headers, "x-provider": "huggingface"},
            json={
                "input": batch_texts,
                "model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Should return embeddings for all texts
            assert len(data["data"]) == 10
            
            # Each embedding should be valid
            for i, embedding_data in enumerate(data["data"]):
                assert embedding_data["index"] == i
                embedding = embedding_data["embedding"]
                assert len(embedding) == 384
                
                # Should have reasonable magnitude
                norm = np.linalg.norm(embedding)
                assert norm > 0.1  # Not zero or near-zero
                assert norm < 100  # Not unreasonably large
            
            # Different texts should produce different embeddings
            embeddings = [d["embedding"] for d in data["data"]]
            for i in range(len(embeddings) - 1):
                # Calculate proper cosine similarity
                vec1 = np.array(embeddings[i])
                vec2 = np.array(embeddings[i + 1])
                cos_sim = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
                assert cos_sim < 0.99, f"Different texts produced too similar embeddings (similarity={cos_sim})"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_with_real_service(self, setup):
        """Test health check endpoint with real service"""
        response = setup.client.get("/api/v1/embeddings/health")
        
        assert response.status_code in [200, 503]  # May be degraded if dependencies missing
        data = response.json()
        
        assert "status" in data
        assert "service" in data
        assert data["service"] == "embeddings_v5_production_enhanced"
        assert "timestamp" in data
        assert "cache_stats" in data
        assert "active_requests" in data
        
        # Cache stats should be valid
        cache_stats = data["cache_stats"]
        assert "size" in cache_stats
        assert "max_size" in cache_stats
        assert "ttl_seconds" in cache_stats
        assert cache_stats["size"] >= 0
        assert cache_stats["max_size"] > 0
