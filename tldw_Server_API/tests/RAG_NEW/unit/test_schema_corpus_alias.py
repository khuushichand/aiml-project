from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest, UnifiedBatchRequest


def test_unified_request_corpus_alias_maps_to_index_namespace():
    req = UnifiedRAGRequest(query="q", sources=["media_db"], corpus="my_corpus")
    assert req.corpus == "my_corpus"
    assert req.index_namespace == "my_corpus"


def test_unified_batch_corpus_alias_maps_to_index_namespace():
    req = UnifiedBatchRequest(queries=["q1", "q2"], corpus="space_corpus")
    assert req.corpus == "space_corpus"
    assert req.index_namespace == "space_corpus"
