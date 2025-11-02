from tldw_Server_API.app.core.RAG.rag_service import agentic_chunker as ac


def test_invalidate_intra_doc_vectors():
    # Seed cache with two keys for media_id 'm1' and one for 'm2'
    ac._INTRA_DOC_VEC_CACHE.clear()
    ac._INTRA_DOC_VEC_CACHE['m1|100|123|model|prov'] = [1, 2, 3]
    ac._INTRA_DOC_VEC_CACHE['m1|101|124|model|prov'] = [4, 5, 6]
    ac._INTRA_DOC_VEC_CACHE['m2|99|125|model|prov'] = [7, 8, 9]

    removed = ac.invalidate_intra_doc_vectors('m1')
    assert removed == 2
    assert 'm2|99|125|model|prov' in ac._INTRA_DOC_VEC_CACHE

    # Clear all caches
    ac.clear_agentic_caches()
    assert not ac._INTRA_DOC_VEC_CACHE
    assert isinstance(ac._EPHEMERAL_CACHE, dict)
