# Unified RAG Capabilities

Discover supported features, defaults, and limits at runtime.

## Endpoint

```bash
curl -s "http://127.0.0.1:8000/api/v1/rag/capabilities" | jq
```

## Sample Response (abridged but structurally complete)

```json
{
  "pipeline": "unified",
  "version": "1.0.0",
  "features": {
    "query_expansion": {
      "supported": true,
      "methods": ["acronym", "synonym", "domain", "entity"]
    },
    "claims": {
      "supported": true,
      "extractors": ["aps", "claimify", "auto"],
      "verifiers": ["nli", "llm", "hybrid"],
      "defaults": {"top_k": 5, "confidence_threshold": 0.7, "max": 25},
      "nli": {"env": ["RAG_NLI_MODEL", "RAG_NLI_MODEL_PATH"], "override_param": "nli_model"}
    },
    "semantic_cache": {
      "supported": true,
      "adaptive_thresholds": true,
      "config": {"similarity_threshold": 0.85}
    },
    "sources": {
      "supported": true,
      "datastores": ["media_db", "notes_db", "character_db"]
    },
    "security_filtering": {"supported": true, "pii_detection": true},
    "citation_generation": {
      "supported": true,
      "styles": ["APA", "MLA", "Chicago", "Harvard", "IEEE"],
      "include_page_numbers": true
    },
    "answer_generation": {"supported": true, "configurable_model": true},
    "reranking": {
      "supported": true,
      "strategies": ["flashrank", "cross_encoder", "hybrid", "llama_cpp"],
      "models": [
        "flashrank",
        "cross-encoder (e.g., BAAI/bge-reranker-v2-m3, Jina reranker)",
        "GGUF via llama.cpp (e.g., Qwen3-Embedding-0.6B_f16.gguf, BGE/Jina GGUF)"
      ]
    },
    "table_processing": {"supported": true, "methods": ["markdown", "html", "hybrid"]},
    "vlm_late_chunking": {
      "supported": true,
      "backends": ["docling", "hf_table_transformer"],
      "backends_endpoint": "/api/v1/rag/vlm/backends"
    },
    "enhanced_chunking": {
      "supported": true,
      "parent_context": true,
      "sibling_context": true,
      "parameters": [
        "parent_context_size",
        "include_parent_document",
        "parent_max_tokens",
        "include_sibling_chunks",
        "sibling_window",
        "chunk_type_filter"
      ]
    },
    "feedback": {"supported": true, "apply_feedback_boost": true},
    "monitoring": {"supported": true, "observability": true, "trace_id": true},
    "analytics": {"supported": true},
    "batch_processing": {"supported": true, "concurrent": true, "defaults": {"max_concurrent": 5}, "limits": {"max_concurrent_max": 20}},
    "resilience": {"supported": true, "retries": true, "circuit_breakers": true},
    "streaming": {"supported": true, "endpoint": "/api/v1/rag/search/stream", "media_type": "application/x-ndjson", "events": ["delta", "claims_overlay", "final_claims"]},
    "quick_wins": {"supported": true, "parameters": ["highlight_results", "highlight_query_terms", "track_cost", "debug_mode"]},
    "user_context": {"supported": true, "fields": ["user_id", "session_id"]}
  },
  "search": {
    "modes": ["hybrid", "semantic", "fulltext"],
    "hybrid": {
      "alpha_default": 0.7,
      "alpha_range": [0.0, 1.0],
      "normalize_scores": true
    },
    "vector": {"top_k_default": 10, "top_k_max": 100},
    "fts": {"top_k_default": 10, "query_expansion": true, "fuzzy_matching": true}
  },
  "defaults": {
    "retriever": {"hybrid_alpha": 0.7, "vector_top_k": 10, "fts_top_k": 10},
    "processor": {},
    "cache": {"similarity_threshold": 0.85},
    "batch_size": 32,
    "num_workers": 4,
    "min_score": 0.0,
    "use_connection_pool": true,
    "use_embedding_cache": true
  },
  "limits": {"top_k_max": 100, "documents_per_db_max": 1000, "answer_tokens_max": 2048, "timeout_seconds_max": 60.0},
  "auth": {"mode": "single_user", "user_scoped": true}
}
```

Notes:
- Capability labels “fulltext” and “semantic” correspond to request values `"fts"` and `"vector"` for `search_mode`.
- Source values `"characters"` and `"chats"` both map to the `character_db` datastore internally.
