"""
Test to ensure the bundled JSON Schema envelope in messages.py
stays aligned with the defaults in queue_schemas. This catches drift
that could make BaseWorker's light envelope validation overly strict.
"""

from tldw_Server_API.app.core.Embeddings import messages
from tldw_Server_API.app.core.Embeddings import queue_schemas as qs


def test_schema_version_and_name_in_sync():
    # Compare logical schema name
    assert messages.CURRENT_SCHEMA == qs.EmbeddingJobMessage.model_fields["msg_schema"].default
    # Compare version integer
    assert messages.CURRENT_VERSION == qs.EmbeddingJobMessage.model_fields["msg_version"].default
