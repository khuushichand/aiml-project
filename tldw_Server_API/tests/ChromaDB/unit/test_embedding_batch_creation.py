"""
Unit test for embedding batch creation logic that uses patching to simulate
provider batch limits. Kept separate from integration tests (no mocks).
"""

import pytest
from unittest.mock import patch
pytestmark = [pytest.mark.unit, pytest.mark.skip(reason="Batch creation internals use embedder methods; skipping in current API")]

from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embeddings_batch


def test_embedding_batch_creation_with_patched_provider():
    """Verify create_embeddings_batch respects max_batch_size via patched provider call."""
    texts = ["text1", "text2", "text3", "text4", "text5"]

    with patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings') as mock_create:
        def create_small_batch(batch_texts, *args, **kwargs):
            return [[0.1] * 384 for _ in batch_texts]

        mock_create.side_effect = create_small_batch

        embeddings = create_embeddings_batch(
            texts,
            provider="openai",
            model="text-embedding-ada-002",
            max_batch_size=2
        )

        assert len(embeddings) == 5
        # Should be called 3 times (2+2+1)
        assert mock_create.call_count == 3
