from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as emb_create


def test_backend_metric_name_is_distinct():
    assert emb_create.EMBEDDINGS_REQUESTS._name != "embedding_requests_total"
    assert emb_create.EMBEDDINGS_REQUESTS._name.startswith("embedding_backend_requests")
