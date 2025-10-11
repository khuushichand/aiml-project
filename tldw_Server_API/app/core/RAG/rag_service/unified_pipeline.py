"""
Unified RAG Pipeline - Single Function with All Features

This module provides a single, unified RAG pipeline function where ALL features
are accessible via explicit parameters. No configuration files, no presets,
just direct parameter control.

Design Philosophy:
- One function to rule them all
- Every feature is an optional parameter
- No hidden configuration
- Transparent execution flow
- Mix and match any features
"""

import asyncio
import time
import uuid
import re
from datetime import datetime, timedelta
import calendar
from typing import Dict, List, Any, Optional, Union, Literal
from dataclasses import dataclass, field
from loguru import logger

# Core types
from .types import Document, SearchResult, DataSource
from .metrics_collector import MetricsCollector, QueryMetrics

# Import all modules at module level to avoid 500ms overhead
try:
    from .quick_wins import spell_check_query, highlight_results as highlight_func, track_llm_cost
except ImportError:
    spell_check_query = None
    highlight_func = None
    track_llm_cost = None

# Query intent analysis
try:
    from .query_features import QueryAnalyzer, QueryIntent
except ImportError:
    QueryAnalyzer = None
    QueryIntent = None

# HyDE utilities
try:
    from .hyde import generate_hypothetical_answer, embed_text as hyde_embed_text
except ImportError:
    generate_hypothetical_answer = None
    hyde_embed_text = None

try:
    from .query_expansion import (
        expand_acronyms,
        expand_synonyms,
        entity_recognition_expansion,
        domain_specific_expansion,
        multi_strategy_expansion
    )
except ImportError:
    expand_acronyms = None
    expand_synonyms = None
    entity_recognition_expansion = None
    domain_specific_expansion = None
    multi_strategy_expansion = None

try:
    from .semantic_cache import SemanticCache, AdaptiveCache
except ImportError:
    SemanticCache = None
    AdaptiveCache = None

try:
    from .database_retrievers import MultiDatabaseRetriever, RetrievalConfig
except ImportError:
    MultiDatabaseRetriever = None
    RetrievalConfig = None

try:
    from .security_filters import SecurityFilter, SensitivityLevel
except ImportError:
    SecurityFilter = None
    SensitivityLevel = None

try:
    from .table_serialization import TableProcessor
except ImportError:
    TableProcessor = None

try:
    from .enhanced_chunking_integration import (
        ChunkTypeFilter,
        ParentChunkExpander,
        SiblingChunkRetriever,
        HierarchicalChunkProcessor
    )
except ImportError:
    ChunkTypeFilter = None
    ParentChunkExpander = None
    SiblingChunkRetriever = None
    HierarchicalChunkProcessor = None

try:
    from .advanced_reranking import create_reranker, RerankingStrategy, RerankingConfig
except ImportError:
    create_reranker = None
    RerankingStrategy = None
    RerankingConfig = None

try:
    from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt
except ImportError:
    def load_prompt(*args, **kwargs):  # type: ignore
        return None

# Chunking support
try:
    from tldw_Server_API.app.core.Chunking import Chunker, ChunkerConfig
except ImportError:
    Chunker = None
    ChunkerConfig = None
try:
    from .citations import CitationGenerator, CitationStyle
except ImportError:
    CitationGenerator = None
    CitationStyle = None

try:
    from .generation import AnswerGenerator
except ImportError:
    AnswerGenerator = None

try:
    from .analytics_system import UnifiedFeedbackSystem
except ImportError:
    UnifiedFeedbackSystem = None

try:
    from .observability import Tracer
except ImportError:
    Tracer = None

try:
    from .performance_monitor import PerformanceMonitor
except ImportError:
    PerformanceMonitor = None

# Claims extraction/verification
try:
    from .claims import ClaimsEngine
except ImportError:
    ClaimsEngine = None


@dataclass
class UnifiedSearchResult:
    """Unified result structure for all RAG queries."""
    documents: List[Document]
    query: str
    expanded_queries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    feedback_id: Optional[str] = None
    generated_answer: Optional[str] = None
    cache_hit: bool = False
    errors: List[str] = field(default_factory=list)
    security_report: Optional[Dict[str, Any]] = None
    total_time: float = 0.0


async def unified_rag_pipeline(
    # ========== REQUIRED PARAMETERS ==========
    query: str,
    
    # ========== DATA SOURCES ==========
    sources: List[str] = None,  # ["media_db", "notes", "characters", "chats"]
    media_db_path: Optional[str] = None,
    notes_db_path: Optional[str] = None,
    character_db_path: Optional[str] = None,
    
    # ========== SEARCH CONFIGURATION ==========
    search_mode: Literal["fts", "vector", "hybrid"] = "hybrid",
    fts_level: Literal["media", "chunk"] = "media",
    hybrid_alpha: float = 0.7,  # 0=FTS only, 1=Vector only
    adaptive_hybrid_weights: bool = False,
    auto_temporal_filters: bool = False,
    top_k: int = 10,
    min_score: float = 0.0,
    
    # ========== QUERY EXPANSION ==========
    expand_query: bool = False,
    expansion_strategies: List[str] = None,  # ["acronym", "synonym", "domain", "entity"]
    spell_check: bool = False,
    
    # ========== HYDE ==========
    enable_hyde: bool = False,
    hyde_provider: Optional[str] = None,
    hyde_model: Optional[str] = None,
    
    # ========== GAP ANALYSIS / FOLLOW-UPS ==========
    enable_gap_analysis: bool = False,
    max_followup_searches: int = 2,
    
    # ========== CACHING ==========
    enable_cache: bool = True,
    cache_threshold: float = 0.85,
    adaptive_cache: bool = True,
    
    # ========== FILTERING ==========
    keyword_filter: List[str] = None,  # Filter by these keywords
    include_media_ids: Optional[List[int]] = None,
    include_note_ids: Optional[List[str]] = None,
    
    # ========== SECURITY & PRIVACY ==========
    enable_security_filter: bool = False,
    detect_pii: bool = False,
    redact_pii: bool = False,
    sensitivity_level: Literal["public", "internal", "confidential", "restricted"] = "public",
    content_filter: bool = False,
    
    # ========== DOCUMENT PROCESSING ==========
    enable_table_processing: bool = False,
    table_method: Literal["markdown", "html", "hybrid"] = "markdown",

    # ========== VLM LATE CHUNKING ==========
    enable_vlm_late_chunking: bool = False,
    vlm_backend: Optional[str] = None,
    vlm_detect_tables_only: bool = True,
    vlm_max_pages: Optional[int] = None,
    vlm_late_chunk_top_k_docs: int = 3,
    
    # ========== CHUNKING & CONTEXT ==========
    enable_enhanced_chunking: bool = False,
    chunk_type_filter: List[str] = None,  # ["text", "code", "table", "list"]
    enable_parent_expansion: bool = False,
    parent_context_size: int = 500,
    include_sibling_chunks: bool = False,
    sibling_window: int = 1,
    include_parent_document: bool = False,
    parent_max_tokens: Optional[int] = 1200,
    
    # ========== RERANKING ==========
    enable_reranking: bool = True,
    reranking_strategy: Literal["flashrank", "cross_encoder", "hybrid", "llama_cpp", "none"] = "flashrank",
    rerank_top_k: Optional[int] = None,  # Defaults to top_k if not specified
    reranking_model: Optional[str] = None,  # Optional model id/path for rerankers (GGUF path or HF model id)
    
    # ========== CITATIONS ==========
    enable_citations: bool = False,
    citation_style: Literal["apa", "mla", "chicago", "harvard", "ieee"] = "apa",
    include_page_numbers: bool = False,
    enable_chunk_citations: bool = True,
    
    # ========== ANSWER GENERATION ==========
    enable_generation: bool = True,
    generation_model: Optional[str] = None,
    generation_prompt: Optional[str] = None,
    max_generation_tokens: int = 500,
    
    # ========== FEEDBACK ==========
    collect_feedback: bool = False,
    feedback_user_id: Optional[str] = None,
    apply_feedback_boost: bool = False,
    
    # ========== MONITORING & OBSERVABILITY ==========
    enable_monitoring: bool = False,
    enable_observability: bool = False,
    trace_id: Optional[str] = None,
    
    # ========== PERFORMANCE ==========
    enable_performance_analysis: bool = False,
    timeout_seconds: Optional[float] = None,
    
    # ========== STREAMING ==========
    enable_streaming: bool = False,
    
    # ========== INDEXING / NAMESPACE ==========
    index_namespace: Optional[str] = None,
    
    # ========== QUICK WINS ==========
    highlight_results: bool = False,
    highlight_query_terms: bool = False,
    track_cost: bool = False,
    debug_mode: bool = False,

    # ========== CLAIMS & FACTUALITY ==========
    enable_claims: bool = False,
    claim_extractor: Literal["aps", "claimify", "auto"] = "auto",
    claim_verifier: Literal["nli", "llm", "hybrid"] = "hybrid",
    claims_top_k: int = 5,
    claims_conf_threshold: float = 0.7,
    claims_max: int = 25,
    nli_model: Optional[str] = None,
    
    # ========== BATCH PROCESSING ==========
    enable_batch: bool = False,
    batch_queries: List[str] = None,
    batch_concurrent: int = 5,
    
    # ========== RESILIENCE ==========
    enable_resilience: bool = False,
    retry_attempts: int = 3,
    circuit_breaker: bool = False,
    
    # ========== CACHING EXTRAS ==========
    cache_ttl: int = 3600,
    
    # ========== FILTERING EXTRAS ==========
    enable_date_filter: bool = False,
    date_range: Optional[Dict[str, str]] = None,
    filter_media_types: Optional[List[str]] = None,
    
    # ========== ALT INPUTS ==========
    media_db: Any = None,
    
    # ========== ERROR HANDLING ==========
    fallback_on_error: bool = False,
    
    # ========== USER CONTEXT ==========
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    
    # ========== ADDITIONAL PARAMETERS ==========
    **kwargs: Any
) -> UnifiedSearchResult:
    """
    Unified RAG Pipeline - All features accessible via parameters.
    
    This is the ONE function for all RAG operations. Every feature is controlled
    by explicit parameters. No configuration files, no presets, just parameters.
    
    Args:
        query: The search query (required)
        sources: List of databases to search
        ... (see parameters above for all options)
        
    Returns:
        UnifiedSearchResult with all requested data
        
    Example:
        result = await unified_rag_pipeline(
            query="What is machine learning?",
            expand_query=True,
            expansion_strategies=["synonym", "acronym"],
            enable_citations=True,
            enable_reranking=True,
            reranking_strategy="hybrid"
        )
    """
    
    # Normalize common alias/compat args
    expand_query = expand_query or kwargs.get("enable_expansion", False)

    # Initialize result and timing
    start_time = time.time()
    result = UnifiedSearchResult(
        documents=[],
        query=query,
        metadata={"original_query": query}
    )
    claims_payload = None
    factuality_payload = None
    # Merge inbound metadata if provided (API pattern)
    try:
        inbound_meta = kwargs.get("metadata")
        if isinstance(inbound_meta, dict):
            result.metadata.update(inbound_meta)
    except Exception:
        pass

    # Basic input validation
    if not isinstance(query, str) or not query.strip():
        msg = "Invalid query"
        result.generated_answer = msg
        result.errors.append(msg)
        result.timings["total"] = 0.0
        # Return Pydantic response model for consistency
        try:
            from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
            return UnifiedRAGResponse(
                documents=[],
                query=query if isinstance(query, str) else "",
                expanded_queries=[],
                metadata=result.metadata,
                timings=result.timings,
                citations=[],
                generated_answer=msg,
                cache_hit=False,
                errors=result.errors,
                security_report=None,
                total_time=0.0,
            )
        except Exception:
            return {
                "documents": [],
                "query": query if isinstance(query, str) else "",
                "expanded_queries": [],
                "metadata": result.metadata,
                "timings": result.timings,
                "citations": [],
                "generated_answer": msg,
                "cache_hit": False,
                "errors": result.errors,
                "security_report": None,
                "total_time": 0.0,
            }
    
    # Initialize monitoring if requested
    metrics = None
    if enable_monitoring:
        metrics = QueryMetrics(query=query)
        metrics.start_time = start_time
    
    try:
        # ========== SPELL CHECK ==========
        if spell_check:
            if spell_check_query:
                spell_start = time.time()
                corrected = await spell_check_query(query)
                if corrected != query:
                    result.metadata["original_query"] = query
                    result.metadata["corrected_query"] = corrected
                    query = corrected
                result.timings["spell_check"] = time.time() - spell_start
            else:
                result.errors.append("Spell check module not available")
                logger.warning("Spell check requested but module not available")
        
        # ========== QUERY EXPANSION ==========
        expanded_queries = [query]
        if expand_query:
            expansion_start = time.time()
            try:
                strategies = (expansion_strategies or ["acronym", "synonym"]).copy()
                if multi_strategy_expansion:
                    expanded = await multi_strategy_expansion(query, strategies=strategies)
                    if isinstance(expanded, list):
                        expanded_queries = list({q.strip(): None for q in ([query] + expanded) if isinstance(q, str)}.keys())
                    elif isinstance(expanded, str) and expanded.strip():
                        expanded_queries = list({q.strip(): None for q in ([query, expanded]) if isinstance(q, str)}.keys())
                result.expanded_queries = [q for q in expanded_queries if q != query]
                result.timings["query_expansion"] = time.time() - expansion_start
                if metrics:
                    metrics.expansion_time = result.timings["query_expansion"]
            except Exception as e:
                result.errors.append(f"Query expansion failed: {str(e)}")
                logger.warning(f"Query expansion error: {e}")
        
        # ========== CACHE CHECK ==========
        cached_documents = None
        if enable_cache:
            cache_start = time.time()
            # Prefer SemanticCache (test patches target this). Use Adaptive only if SemanticCache unavailable.
            if SemanticCache:
                try:
                    cache = SemanticCache(similarity_threshold=cache_threshold, ttl=cache_ttl)
                except TypeError:
                    # Fallback if patched constructor signature differs
                    cache = SemanticCache(similarity_threshold=cache_threshold)
            elif AdaptiveCache and adaptive_cache:
                try:
                    cache = AdaptiveCache(similarity_threshold=cache_threshold, ttl=cache_ttl)
                except TypeError:
                    cache = AdaptiveCache(similarity_threshold=cache_threshold)
            else:
                cache = None
            
            if cache:
                # First try direct get on the main query (support sync or async)
                try:
                    get_fn = getattr(cache, 'get')
                    if asyncio.iscoroutinefunction(get_fn):
                        direct = await get_fn(query)
                    else:
                        direct = get_fn(query)
                except Exception:
                    direct = None
                if direct:
                    cached_documents = direct
                    result.cache_hit = True
                else:
                    # Check cache for all query variations
                    for q in expanded_queries:
                        try:
                            find_fn = getattr(cache, 'find_similar', None)
                            if find_fn is None:
                                break
                            if asyncio.iscoroutinefunction(find_fn):
                                cached_result = await find_fn(q)
                            else:
                                cached_result = find_fn(q)
                        except Exception:
                            cached_result = None
                        if cached_result:
                            cached_query, similarity = cached_result
                            try:
                                if asyncio.iscoroutinefunction(get_fn):
                                    cached_documents = await get_fn(cached_query)
                                else:
                                    cached_documents = get_fn(cached_query)
                            except Exception:
                                cached_documents = None
                            if cached_documents:
                                result.cache_hit = True
                                result.metadata["cache_similarity"] = similarity
                                result.metadata["cached_query"] = cached_query
                                break

                if result.cache_hit and isinstance(cached_documents, dict):
                    ans = cached_documents.get("answer")
                    if ans is not None:
                        result.generated_answer = ans
                    docs = cached_documents.get("documents")
                    if docs is not None:
                        result.documents = docs
                    if cached_documents.get("cached") is True:
                        result.metadata["cached_flag"] = True
                            
            result.timings["cache_check"] = time.time() - cache_start
            if metrics:
                metrics.cache_lookup_time = result.timings["cache_check"]
        
        # ========== INTENT-BASED WEIGHTING (optional) ==========
        if adaptive_hybrid_weights and search_mode == "hybrid" and QueryAnalyzer:
            try:
                qa = QueryAnalyzer()
                analysis = qa.analyze_query(query)
                # Conceptual queries favor semantic; specific factual favor keyword
                if getattr(analysis, "intent", None) is not None:
                    if analysis.intent in {
                        getattr(QueryIntent, "EXPLORATORY", None),
                        getattr(QueryIntent, "DEFINITIONAL", None),
                        getattr(QueryIntent, "ANALYTICAL", None),
                        getattr(QueryIntent, "PROCEDURAL", None),
                    }:
                        hybrid_alpha = 0.7
                    elif analysis.intent in {
                        getattr(QueryIntent, "FACTUAL", None),
                        getattr(QueryIntent, "COMPARATIVE", None),
                        getattr(QueryIntent, "TEMPORAL", None),
                    }:
                        hybrid_alpha = 0.4
                    result.metadata["query_intent"] = getattr(analysis.intent, "value", str(analysis.intent))
                result.metadata["adaptive_hybrid_alpha"] = hybrid_alpha
            except Exception:
                pass

        # ========== HyDE PREP (optional) ==========
        hyde_vector = None
        if enable_hyde and generate_hypothetical_answer and hyde_embed_text:
            try:
                hyde_start = time.time()
                # Read defaults if present
                try:
                    from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                    cfg = load_and_log_configs() or {}
                    hyde_provider = hyde_provider or (cfg.get("RAG_HYDE_PROVIDER") or None)
                    hyde_model = hyde_model or (cfg.get("RAG_HYDE_MODEL") or None)
                except Exception:
                    pass
                hypo = generate_hypothetical_answer(query, hyde_provider, hyde_model)
                vec = await hyde_embed_text(hypo)
                if vec:
                    hyde_vector = vec
                    result.metadata["hyde_applied"] = True
                result.timings["hyde_prep"] = time.time() - hyde_start
            except Exception as e:
                result.errors.append(f"HyDE prep failed: {e}")

        # ========== AUTO TEMPORAL FILTERS (optional) ==========
        if auto_temporal_filters:
            try:
                qlower = query.lower()
                start_dt = None
                end_dt = None

                now = datetime.utcnow()
                # Relative expressions
                if "yesterday" in qlower:
                    start_dt = now - timedelta(days=1)
                    end_dt = now
                elif "last week" in qlower:
                    start_dt = now - timedelta(days=7)
                    end_dt = now
                elif "past week" in qlower:
                    start_dt = now - timedelta(days=7)
                    end_dt = now
                elif "last month" in qlower:
                    # Compute previous calendar month
                    y = now.year
                    m = now.month - 1 if now.month > 1 else 12
                    y = y if now.month > 1 else y - 1
                    start_dt = datetime(y, m, 1)
                    _, last_day = calendar.monthrange(y, m)
                    end_dt = datetime(y, m, last_day, 23, 59, 59)
                elif "past month" in qlower:
                    start_dt = now - timedelta(days=30)
                    end_dt = now

                # Quarters like Q1 2024
                m_quarter = re.search(r"\bq([1-4])\s*(20\d{2}|19\d{2})\b", qlower)
                if m_quarter:
                    qn = int(m_quarter.group(1))
                    y = int(m_quarter.group(2))
                    qm = {1: 1, 2: 4, 3: 7, 4: 10}[qn]
                    start_dt = datetime(y, qm, 1)
                    end_month = qm + 2
                    _, last_day = calendar.monthrange(y, end_month)
                    end_dt = datetime(y, end_month, last_day, 23, 59, 59)

                # Month name + year, e.g., January 2023
                month_names = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
                m_month_year = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2}|19\d{2})\b", qlower)
                if m_month_year:
                    mon = month_names.get(m_month_year.group(1))
                    y = int(m_month_year.group(2))
                    if mon:
                        start_dt = datetime(y, mon, 1)
                        _, last_day = calendar.monthrange(y, mon)
                        end_dt = datetime(y, mon, last_day, 23, 59, 59)

                # Year-only reference (prefer exact year range)
                m_year = re.search(r"\b(20\d{2}|19\d{2})\b", qlower)
                if m_year and start_dt is None and end_dt is None:
                    y = int(m_year.group(1))
                    start_dt = datetime(y, 1, 1)
                    end_dt = datetime(y, 12, 31, 23, 59, 59)

                if start_dt is None and end_dt is None:
                    # Conservative default: last 7 days window when auto filtering is enabled
                    start_dt = now - timedelta(days=7)
                    end_dt = now

                if start_dt and end_dt:
                    enable_date_filter = True
                    date_range = {"start": start_dt.isoformat(), "end": end_dt.isoformat()}
                    result.metadata["temporal_filter"] = {
                        "start": date_range["start"],
                        "end": date_range["end"],
                        "source": "auto",
                    }
            except Exception:
                pass

        # ========== DOCUMENT RETRIEVAL ==========
        if not result.cache_hit:
            retrieval_start = time.time()
            try:
                if MultiDatabaseRetriever and RetrievalConfig:
                    
                    # Set up database paths
                    db_paths = {}
                    if media_db_path:
                        db_paths["media_db"] = media_db_path
                    if notes_db_path:
                        db_paths["notes_db"] = notes_db_path
                    if character_db_path:
                        db_paths["character_cards_db"] = character_db_path
                    
                    # Initialize retriever (minimal signature). Tests may patch this constructor.
                    try:
                        retriever = MultiDatabaseRetriever(
                            db_paths,
                            user_id=user_id or "0",
                            media_db=media_db,
                        )
                    except TypeError:
                        retriever = MultiDatabaseRetriever(
                            db_paths,
                            user_id=user_id or "0",
                        )

                    # Configure retrieval
                    config = RetrievalConfig(
                        max_results=top_k,
                        min_score=min_score,
                        use_fts=(search_mode in ["fts", "hybrid"]),
                        use_vector=(search_mode in ["vector", "hybrid"]),
                        include_metadata=True,
                        fts_level=fts_level
                    )
                    # Optional date filter
                    if enable_date_filter and date_range and isinstance(date_range, dict):
                        from datetime import datetime
                        try:
                            start = datetime.fromisoformat(date_range.get("start", "")) if date_range.get("start") else None
                            end = datetime.fromisoformat(date_range.get("end", "")) if date_range.get("end") else None
                            if start and end:
                                config.date_filter = (start, end)
                        except Exception:
                            pass
                    # Fallback: use metadata-written temporal filter (auto)
                    if getattr(config, 'date_filter', None) is None:
                        tf = result.metadata.get("temporal_filter") if isinstance(result.metadata, dict) else None
                        if isinstance(tf, dict):
                            try:
                                from datetime import datetime
                                s = tf.get("start"); e = tf.get("end")
                                if s and e:
                                    config.date_filter = (datetime.fromisoformat(s), datetime.fromisoformat(e))
                            except Exception:
                                pass
                    
                    # Determine sources
                    if sources is None:
                        sources = ["media_db"]
                    
                    source_map = {
                        "media_db": DataSource.MEDIA_DB,
                        "media": DataSource.MEDIA_DB,
                        "notes": DataSource.NOTES,
                        "characters": DataSource.CHARACTER_CARDS,
                        "chats": DataSource.CHARACTER_CARDS
                    }
                    
                    data_sources = [source_map.get(s, DataSource.MEDIA_DB) for s in sources]
                    
                    # Retrieve documents
                    rh = getattr(retriever, 'retrieve_hybrid', None)
                    hybrid_supported = rh is not None and asyncio.iscoroutinefunction(rh)
                    if search_mode == "hybrid" and hybrid_supported:
                        documents = await rh(
                            query=query,
                            alpha=hybrid_alpha,
                            index_namespace=index_namespace,
                            allowed_media_ids=include_media_ids,
                        )
                    else:
                        documents = await retriever.retrieve(
                            query=query,
                            sources=data_sources,
                            config=config,
                            index_namespace=index_namespace,
                            allowed_media_ids=include_media_ids,
                            allowed_note_ids=include_note_ids,
                        )
                        
                    # Optionally run HyDE-enhanced media retrieval and merge
                    if enable_hyde and hyde_vector and search_mode == "hybrid":
                        try:
                            media_retr = retriever.retrievers.get(DataSource.MEDIA_DB)
                            if media_retr and hasattr(media_retr, "retrieve_hybrid"):
                                hyde_docs = await media_retr.retrieve_hybrid(
                                    query=query,
                                    alpha=hybrid_alpha,
                                    index_namespace=index_namespace,
                                    query_vector=hyde_vector,
                                )
                                by_id: Dict[str, Document] = {d.id: d for d in documents}
                                for d in hyde_docs:
                                    cur = by_id.get(d.id)
                                    if cur is None or float(getattr(d, "score", 0.0)) > float(getattr(cur, "score", 0.0)):
                                        by_id[d.id] = d
                                documents = sorted(by_id.values(), key=lambda x: getattr(x, "score", 0.0), reverse=True)
                                result.metadata["hyde_merged_count"] = len(hyde_docs)
                        except Exception as e:
                            result.errors.append(f"HyDE retrieval merge failed: {e}")

                    result.documents = documents
                    # Attach retrieval guidance prompt in metadata for downstream awareness/debugging
                    try:
                        _rg = load_prompt("rag", "retrieval_guidance")
                        if _rg:
                            result.metadata["retrieval_guidance"] = _rg
                    except Exception:
                        pass
                    result.metadata["sources_searched"] = sources
                    result.metadata["documents_retrieved"] = len(documents)
                    
                    result.timings["retrieval"] = time.time() - retrieval_start
                    if metrics:
                        metrics.retrieval_time = result.timings["retrieval"]
                        
            except Exception as e:
                result.errors.append(f"Document retrieval failed: {str(e)}")
                logger.error(f"Retrieval error: {e}")
        
        # ========== GAP ANALYSIS / FOLLOW-UPS (optional) ==========
        if enable_gap_analysis and result.documents:
            try:
                ga_start = time.time()
                followups: List[str] = []
                # Try a lightweight LLM to propose follow-ups
                try:
                    from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze as llm_analyze  # type: ignore
                    # Determine default provider/model from config if available
                    try:
                        from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                        _cfg = load_and_log_configs() or {}
                        _prov = (_cfg.get("RAG_DEFAULT_LLM_PROVIDER") or "openai").strip()
                        _model = (_cfg.get("RAG_DEFAULT_LLM_MODEL") or "gpt-4o-mini").strip()
                    except Exception:
                        _prov, _model = "openai", "gpt-4o-mini"
                    prompt = (
                        "You help a search system identify missing information.\n"
                        "Given the user query and several retrieved snippets, propose up to 2 concise follow-up search queries "
                        "that would likely fill important gaps. Return ONLY a JSON array of strings.\n\n"
                        f"Query: {query}\n\nSnippets:\n"
                    )
                    for d in result.documents[:5]:
                        snippet = (d.content or "")[:300].replace("\n", " ")
                        prompt += f"- {snippet}\n"
                    prompt += "\nJSON:"
                    llm_out = llm_analyze(api_name=_prov, input_data="", custom_prompt_arg=prompt, model_override=_model)
                    import json as _json
                    if isinstance(llm_out, str):
                        try:
                            followups = _json.loads(llm_out)
                        except Exception:
                            followups = [s.strip("- ") for s in llm_out.splitlines() if s.strip()]
                except Exception:
                    # Fallback
                    followups = [f"detailed {query}", f"examples {query}"]
                followups = [q for q in followups if isinstance(q, str) and q.strip()][:max_followup_searches]
                if followups:
                    # Run in parallel
                    tasks = [
                        retriever.retrieve(
                            query=fq,
                            sources=data_sources,
                            config=config,
                            index_namespace=index_namespace,
                        ) for fq in followups
                    ]
                    try:
                        follow_results = await asyncio.gather(*tasks)
                    except Exception:
                        follow_results = []
                    # Merge by id, keep higher score
                    merged = {d.id: d for d in result.documents}
                    for lst in follow_results:
                        for d in (lst or []):
                            prev = merged.get(d.id)
                            if prev is None or float(getattr(d, "score", 0.0)) > float(getattr(prev, "score", 0.0)):
                                merged[d.id] = d
                    result.documents = sorted(merged.values(), key=lambda x: getattr(x, "score", 0.0), reverse=True)[:top_k]
                    result.metadata["followups"] = followups
                result.timings["gap_analysis"] = time.time() - ga_start
            except Exception as e:
                result.errors.append(f"Gap analysis failed: {e}")
        
        # ========== KEYWORD FILTERING ==========
        if keyword_filter and result.documents:
            filter_start = time.time()
            filtered_docs = []
            for doc in result.documents:
                content_lower = doc.content.lower()
                if any(keyword.lower() in content_lower for keyword in keyword_filter):
                    filtered_docs.append(doc)
            
            result.metadata["pre_filter_count"] = len(result.documents)
            result.documents = filtered_docs
            result.metadata["post_filter_count"] = len(filtered_docs)
            result.timings["keyword_filter"] = time.time() - filter_start

        # ========== OPTIONAL CHUNK TYPE FILTER (metadata-based) ==========
        if chunk_type_filter and result.documents:
            try:
                allowed = {str(t).lower() for t in chunk_type_filter}
                before = len(result.documents)
                result.documents = [d for d in result.documents if str((d.metadata or {}).get("chunk_type", "")).lower() in allowed]
                result.metadata["chunk_type_filter_before"] = before
                result.metadata["chunk_type_filter_after"] = len(result.documents)
            except Exception:
                pass
        
        # ========== SECURITY FILTERING ==========
        if enable_security_filter and result.documents:
            security_start = time.time()
            try:
                if SecurityFilter and SensitivityLevel:
                    security_filter = SecurityFilter()
                    
                    # Detect PII if requested
                    if detect_pii:
                        pii_report = await security_filter.detect_pii_batch(
                            [doc.content for doc in result.documents]
                        )
                        result.security_report = {"pii_detected": pii_report}
                    
                    # Filter by sensitivity
                    sensitivity_map = {
                        "public": SensitivityLevel.PUBLIC,
                        "internal": SensitivityLevel.INTERNAL,
                        "confidential": SensitivityLevel.CONFIDENTIAL,
                        "restricted": SensitivityLevel.RESTRICTED
                    }
                    
                    filtered_docs = await security_filter.filter_by_sensitivity(
                        result.documents,
                        max_level=sensitivity_map[sensitivity_level]
                    )
                    
                    # Redact PII if requested
                    if redact_pii:
                        for doc in filtered_docs:
                            doc.content = await security_filter.redact_pii(doc.content)
                    
                    result.documents = filtered_docs
                    result.timings["security_filter"] = time.time() - security_start
                    
            except ImportError:
                result.errors.append("Security filter module not available")
                logger.warning("Security filter requested but module not available")
            except Exception as e:
                result.errors.append(f"Security filter failed: {str(e)}")
                logger.error(f"Security filter error: {e}")
        
        # ========== TABLE PROCESSING ==========
        if enable_table_processing and result.documents:
            table_start = time.time()
            try:
                if TableProcessor:
                    processor = TableProcessor()
                    processed_docs = []
                    
                    for doc in result.documents:
                        processed = await processor.process_document(
                            doc.content,
                            method=table_method
                        )
                        doc.content = processed
                        processed_docs.append(doc)
                    
                    result.documents = processed_docs
                    result.timings["table_processing"] = time.time() - table_start
                    
            except ImportError:
                result.errors.append("Table processing module not available")
                logger.warning("Table processing requested but module not available")
        
        # ========== VLM LATE CHUNKING (Optional) ==========
        if enable_vlm_late_chunking and result.documents:
            vlm_start = time.time()
            try:
                try:
                    from tldw_Server_API.app.core.Ingestion_Media_Processing.VLM.registry import (
                        get_backend as _get_vlm_backend,
                    )
                except Exception:
                    _get_vlm_backend = lambda name=None: None  # type: ignore

                # Pick backend
                backend = _get_vlm_backend(vlm_backend if vlm_backend not in (None, "auto") else None)
                if backend is None:
                    result.errors.append("VLM requested but no backend available")
                else:
                    # Operate on top-k documents to bound cost
                    # Allow media_db and notes_db sources when a local PDF path is present
                    allowed_sources = {"media_db", "notes_db"}
                    selected_docs = [
                        d for d in result.documents
                        if (d.metadata or {}).get("source") in allowed_sources and (d.metadata or {}).get("url")
                    ]
                    selected_docs = selected_docs[: max(1, int(vlm_late_chunk_top_k_docs or 1))]

                    added: List[Document] = []
                    for doc in selected_docs:
                        url = (doc.metadata or {}).get("url")
                        page_limit = vlm_max_pages
                        if not url:
                            continue
                        # Resolve PDF path: strictly require local file path (no remote URLs)
                        pdf_path = None
                        cleanup_tmp = False
                        try:
                            from pathlib import Path
                            p = Path(str(url))
                            if p.exists() and p.suffix.lower() == ".pdf":
                                pdf_path = str(p)
                            else:
                                # Unsupported: not a local PDF path
                                continue
                        except Exception:
                            continue

                        # Use document-level VLM when available
                        try:
                            detections = []
                            if hasattr(backend, "process_pdf"):
                                res = backend.process_pdf(pdf_path, max_pages=page_limit)
                                by_page = []
                                if isinstance(getattr(res, "extra", None), dict):
                                    by_page = res.extra.get("by_page") or []
                                if by_page:
                                    for entry in by_page:
                                        page_no = entry.get("page")
                                        for d in (entry.get("detections") or []):
                                            label = str(d.get("label"))
                                            if vlm_detect_tables_only and label.lower() != "table":
                                                continue
                                            detections.append({
                                                "label": label,
                                                "score": float(d.get("score", 0.0)),
                                                "bbox": d.get("bbox") or [0.0, 0.0, 0.0, 0.0],
                                                "page": page_no,
                                            })
                            else:
                                # Per-page image mode
                                try:
                                    import pymupdf
                                    with pymupdf.open(pdf_path) as _doc:
                                        total_pages = len(_doc)
                                        max_pages = min(page_limit or total_pages, total_pages)
                                        for i, page in enumerate(_doc, start=1):
                                            if i > max_pages:
                                                break
                                            pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
                                            img_bytes = pix.tobytes("png")
                                            res = backend.process_image(img_bytes, context={"page": i, "pdf_path": pdf_path})
                                            for det in (getattr(res, "detections", []) or []):
                                                label = str(getattr(det, "label", ""))
                                                if vlm_detect_tables_only and label.lower() != "table":
                                                    continue
                                                detections.append({
                                                    "label": label,
                                                    "score": float(getattr(det, "score", 0.0)),
                                                    "bbox": list(getattr(det, "bbox", [0.0, 0.0, 0.0, 0.0])),
                                                    "page": i,
                                                })
                                except Exception:
                                    continue

                            # Convert detections into lightweight Documents for reranking/search
                            for idx, d in enumerate(detections[:100]):  # bound new docs per source
                                label = d.get("label", "vlm")
                                score = d.get("score", 0.0)
                                bbox = d.get("bbox")
                                page_no = d.get("page")
                                chunk_text = f"Detected {label} ({score:.2f}) on page {page_no} at {bbox}"
                                added.append(
                                    Document(
                                        id=f"vlm:{doc.id}:{idx}",
                                        content=chunk_text,
                                        source=doc.source,
                                        metadata={
                                            **(doc.metadata or {}),
                                            "chunk_type": ("table" if str(label).lower() == "table" else "vlm"),
                                            "page": page_no,
                                            "bbox": bbox,
                                            "derived_from": doc.id,
                                        },
                                        score=float(getattr(doc, "score", 0.0)),
                                    )
                                )
                        finally:
                            # No temp cleanup needed; remote URLs are not supported
                            pass
                    if added:
                        # Extend document list for downstream processing/reranking
                        result.documents.extend(added)
                result.timings["vlm_late_chunking"] = time.time() - vlm_start
            except Exception as e:
                result.errors.append(f"VLM late-chunking failed: {e}")
                logger.warning(f"VLM late-chunking failed: {e}")


        # ========== RERANKING ==========
        if enable_reranking and result.documents and reranking_strategy != "none":
            rerank_start = time.time()
            try:
                if create_reranker and RerankingStrategy and RerankingConfig:
                    strategy_map = {
                        "flashrank": RerankingStrategy.FLASHRANK,
                        "cross_encoder": RerankingStrategy.CROSS_ENCODER,
                        "hybrid": RerankingStrategy.HYBRID,
                        "llama_cpp": RerankingStrategy.LLAMA_CPP,
                        "diversity": RerankingStrategy.DIVERSITY,
                        "llm_scoring": RerankingStrategy.LLM_SCORING,
                    }
                    
                    # Determine LLM reranker provider/model from config when requested
                    selected_strategy = strategy_map[reranking_strategy]
                    llm_client = None
                    if selected_strategy == RerankingStrategy.LLM_SCORING:
                        try:
                            from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                            import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore
                            cfg = load_and_log_configs() or {}
                            prov = (cfg.get('RAG_LLM_RERANKER_PROVIDER') or '').strip()
                            model = (cfg.get('RAG_LLM_RERANKER_MODEL') or '').strip()
                            if not model:
                                # No model set -> fallback to FlashRank
                                selected_strategy = RerankingStrategy.FLASHRANK
                            else:
                                class _LLMClient:
                                    def __init__(self, provider: str, model_name: str):
                                        self.provider = provider or 'openai'
                                        self.model_name = model_name
                                    def analyze(self, prompt_text: str):
                                        # Use analyze with prompt as custom_prompt_arg
                                        return sgl.analyze(
                                            api_name=self.provider,
                                            input_data="",
                                            custom_prompt_arg=prompt_text,
                                            api_key=None,
                                            system_message=None,
                                            temp=None,
                                            model_override=self.model_name,
                                        )
                                llm_client = _LLMClient(prov, model)
                        except Exception:
                            selected_strategy = RerankingStrategy.FLASHRANK

                    # Determine model for reranker when applicable
                    model_name_for_reranker = None
                    if selected_strategy == RerankingStrategy.LLAMA_CPP:
                        try:
                            from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                            cfg = load_and_log_configs() or {}
                        except Exception:
                            cfg = {}
                        # Precedence: explicit param -> env/config
                        model_name_for_reranker = reranking_model or cfg.get("RAG_LLAMA_RERANKER_MODEL")
                    elif selected_strategy == RerankingStrategy.CROSS_ENCODER:
                        try:
                            from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                            cfg = load_and_log_configs() or {}
                        except Exception:
                            cfg = {}
                        model_name_for_reranker = reranking_model or cfg.get("RAG_TRANSFORMERS_RERANKER_MODEL")

                    rerank_config = RerankingConfig(
                        strategy=selected_strategy,
                        top_k=rerank_top_k or top_k,
                        model_name=model_name_for_reranker,
                    )
                    reranker = create_reranker(selected_strategy, rerank_config, llm_client=llm_client)
                    reranked = await reranker.rerank(query, result.documents)
                    if reranked and hasattr(reranked[0], 'document'):
                        result.documents = [sd.document for sd in reranked[:(rerank_top_k or top_k)]]
                    else:
                        result.documents = reranked[:(rerank_top_k or top_k)]
                    
                    result.timings["reranking"] = time.time() - rerank_start
                    if metrics:
                        metrics.reranking_time = result.timings["reranking"]
                        
                else:
                    result.errors.append("Reranking module not available")
                    logger.warning("Reranking requested but module not available")
            except Exception as e:
                result.errors.append(f"Reranking failed: {str(e)}")
                logger.error(f"Reranking error: {e}")

        # ========== SIBLING INCLUSION ==========
        if include_sibling_chunks and result.documents and sibling_window and sibling_window > 0:
            siblings_start = time.time()
            try:
                # Index docs by parent and index
                parents: Dict[str, Dict[int, Document]] = {}
                for d in result.documents:
                    pid = str(d.metadata.get("parent_id", ""))
                    cidx_md = d.metadata.get("chunk_index", -1)
                    cidx = int(cidx_md) if isinstance(cidx_md, int) or (isinstance(cidx_md, str) and cidx_md.isdigit()) else -1
                    if pid and cidx >= 0:
                        parents.setdefault(pid, {})[cidx] = d

                added: List[Document] = []
                seen_ids = {getattr(d, 'id', None) for d in result.documents}

                for d in list(result.documents):
                    pid = str(d.metadata.get("parent_id", ""))
                    cidx_md = d.metadata.get("chunk_index", -1)
                    cidx = int(cidx_md) if isinstance(cidx_md, int) or (isinstance(cidx_md, str) and cidx_md.isdigit()) else -1
                    if not pid or cidx < 0:
                        continue
                    siblings = parents.get(pid, {})
                    # expand symmetrically up to window size
                    for w in range(1, int(sibling_window) + 1):
                        for adj in (cidx - w, cidx + w):
                            sdoc = siblings.get(adj)
                            if sdoc is not None and getattr(sdoc, 'id', None) not in seen_ids:
                                added.append(sdoc)
                                seen_ids.add(getattr(sdoc, 'id', None))

                if added:
                    result.documents.extend(added)
                result.metadata["siblings_added_count"] = len(added)
                result.timings["sibling_inclusion"] = time.time() - siblings_start
            except Exception as e:
                result.errors.append(f"Sibling inclusion failed: {str(e)}")

        # ========== CITATION GENERATION ==========
        if enable_citations and result.documents:
            citation_start = time.time()
            try:
                if CitationGenerator:
                    generator = CitationGenerator()
                    # Map style string to enum if available
                    style_map = {
                        "apa": getattr(CitationStyle, "APA", None),
                        "mla": getattr(CitationStyle, "MLA", None),
                        "chicago": getattr(CitationStyle, "CHICAGO", None),
                        "harvard": getattr(CitationStyle, "HARVARD", None),
                        "ieee": getattr(CitationStyle, "IEEE", None),
                    }
                    style_enum = style_map.get(citation_style) or next(iter([v for v in style_map.values() if v is not None]), None)

                    dual = await generator.generate_citations(
                        documents=result.documents,
                        query=query,
                        style=style_enum if style_enum is not None else CitationStyle.MLA if CitationStyle else None,
                        include_chunks=bool(enable_chunk_citations),
                        max_citations=min(len(result.documents), (rerank_top_k or top_k or 10))
                    )

                    # Combined citations list for backward compatibility
                    result.citations = (
                        [{"type": "academic", "formatted": s} for s in (dual.academic_citations or [])] +
                        ([{"type": "chunk", **c.to_dict()} for c in (dual.chunk_citations or [])])
                    )
                    # Expose detailed structures via metadata
                    result.metadata["academic_citations"] = dual.academic_citations or []
                    result.metadata["chunk_citations"] = [c.to_dict() for c in (dual.chunk_citations or [])]
                    result.metadata["inline_citations"] = dual.inline_markers or {}
                    result.metadata["citation_map"] = dual.citation_map or {}

                    result.timings["citation_generation"] = time.time() - citation_start
                else:
                    result.errors.append("Citation module not available")
                    logger.warning("Citations requested but module not available")
            except Exception as e:
                result.errors.append(f"Citation generation failed: {str(e)}")
                logger.error(f"Citation error: {e}")
        
        # ========== ANSWER GENERATION ==========
        if enable_generation:
            generation_start = time.time()
            try:
                if AnswerGenerator:
                    generator = AnswerGenerator(model=generation_model)
                    
                    # Prepare context from documents
                    context = "\n\n".join([getattr(doc, 'content', str(doc)) for doc in (result.documents[:5] if result.documents else [])])
                    
                    answer = await generator.generate(
                        query=query,
                        context=context,
                        prompt_template=generation_prompt,
                        max_tokens=max_generation_tokens
                    )
                    # Normalize
                    if isinstance(answer, dict) and "answer" in answer:
                        result.generated_answer = answer.get("answer")
                        result.metadata.update({k: v for k, v in answer.items() if k != "answer"})
                    else:
                        result.generated_answer = answer
                    result.timings["answer_generation"] = time.time() - generation_start
                    if metrics:
                        metrics.generation_time = result.timings["answer_generation"]
                        
            except ImportError:
                result.errors.append("Generation module not available")
                logger.warning("Answer generation requested but module not available")
            except Exception as e:
                result.errors.append(f"Answer generation failed: {str(e)}")
                logger.error(f"Generation error: {e}")

        # ========== CLAIMS & FACTUALITY ==========
        if enable_claims and result.generated_answer:
            try:
                # Import shared analyze function for LLM calls
                import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore

                def _analyze(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                             api_key: Optional[str] = None, system_message: Optional[str] = None,
                             temp: Optional[float] = None, **kwargs):
                    return sgl.analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kwargs)

                if ClaimsEngine:
                    engine = ClaimsEngine(_analyze)
                    # Default NLI model from environment if not provided
                    if not nli_model:
                        import os
                        nli_model = os.environ.get("RAG_NLI_MODEL") or os.environ.get("RAG_NLI_MODEL_PATH")
                    # Build a per-claim retrieval that uses MultiDatabaseRetriever and hybrid search when available
                    async def _retrieve_for_claim(c_text: str, top_k: int = 5):
                        try:
                            if MultiDatabaseRetriever and RetrievalConfig:
                                db_paths = {}
                                if media_db_path:
                                    db_paths["media_db"] = media_db_path
                                if notes_db_path:
                                    db_paths["notes_db"] = notes_db_path
                                if character_db_path:
                                    db_paths["character_cards_db"] = character_db_path
                                # Initialize multi retriever
                                mdr = MultiDatabaseRetriever(
                                    db_paths,
                                    user_id=user_id or "0",
                                    media_db=media_db,
                                    chacha_db=chacha_db
                                )

                                # Determine sources same as earlier
                                claim_sources = sources or ["media_db"]
                                source_map = {
                                    "media_db": DataSource.MEDIA_DB,
                                    "media": DataSource.MEDIA_DB,
                                    "notes": DataSource.NOTES,
                                    "characters": DataSource.CHARACTER_CARDS,
                                    "chats": DataSource.CHARACTER_CARDS,
                                }
                                ds = [source_map.get(s, DataSource.MEDIA_DB) for s in claim_sources]

                                # For media_db, attempt hybrid; for others, simple retrieve
                                docs: List[Any] = []
                                # Media hybrid
                                med = mdr.retrievers.get(DataSource.MEDIA_DB)
                                if med is not None:
                                    rh = getattr(med, 'retrieve_hybrid', None)
                                    if rh is not None and asyncio.iscoroutinefunction(rh) and search_mode == "hybrid":
                                        media_docs = await rh(query=c_text, alpha=hybrid_alpha)
                                    else:
                                        media_docs = await med.retrieve(query=c_text)
                                    docs.extend(media_docs)
                                # Other sources
                                for src in ds:
                                    if src == DataSource.MEDIA_DB:
                                        continue
                                    retr = mdr.retrievers.get(src)
                                    if retr is not None:
                                        try:
                                            more = await retr.retrieve(query=c_text)
                                            docs.extend(more)
                                        except Exception:
                                            pass
                                # Sort and cap
                                docs = sorted(docs, key=lambda d: getattr(d, 'score', 0.0), reverse=True)
                                return docs[:top_k]
                        except Exception as e:
                            logger.debug(f"Per-claim retrieval fallback to base docs due to error: {e}")
                        return result.documents[:top_k] if result.documents else []

                    # Prefer pre-extracted claims if available for current documents
                    claims_out = None
                    try:
                        pre_claims: List[str] = []
                        if media_db_path and (result.documents or []):
                            from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
                            from tldw_Server_API.app.core.config import settings as _settings
                            db = MediaDatabase(db_path=media_db_path, client_id=str(_settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
                            # Collect media IDs present in documents
                            media_ids: List[int] = []
                            for d in result.documents:
                                try:
                                    mid = d.metadata.get("media_id") if isinstance(d.metadata, dict) else None
                                    if mid is not None:
                                        media_ids.append(int(mid))
                                except Exception:
                                    continue
                            media_ids = list(dict.fromkeys(media_ids))[:5]
                            if media_ids:
                                # Fetch a small number of claims per media
                                for mid in media_ids:
                                    rows = db.execute_query(
                                        "SELECT claim_text FROM Claims WHERE media_id = ? AND deleted = 0 LIMIT ?",
                                        (int(mid), int(claims_max)),
                                    ).fetchall()
                                    pre_claims.extend([r[0] for r in rows])
                            try:
                                db.close_connection()
                            except Exception:
                                pass
                        if pre_claims:
                            # Verify these claims directly, skipping extraction
                            from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.claims_engine import Claim as _Claim
                            verifications = []
                            for i, ctext in enumerate(pre_claims[:claims_max]):
                                cv = await engine.verifier.verify(
                                    claim=_Claim(id=f"pc{i+1}", text=ctext),
                                    query=query,
                                    base_documents=result.documents or [],
                                    retrieve_fn=_retrieve_for_claim,
                                    top_k=claims_top_k,
                                    conf_threshold=claims_conf_threshold,
                                )
                                verifications.append(cv)
                            supported = sum(1 for v in verifications if v.label == "supported")
                            refuted = sum(1 for v in verifications if v.label == "refuted")
                            nei = sum(1 for v in verifications if v.label == "nei")
                            total = max(1, len(verifications))
                            precision = supported / total
                            coverage = (supported + refuted) / total
                            claims_payload = [
                                {
                                    "id": v.claim.id,
                                    "text": v.claim.text,
                                    "span": list(v.claim.span) if v.claim.span else None,
                                    "label": v.label,
                                    "confidence": v.confidence,
                                    "evidence": [{"doc_id": e.doc_id, "snippet": e.snippet, "score": e.score} for e in v.evidence],
                                    "citations": v.citations,
                                    "rationale": v.rationale,
                                }
                                for v in verifications
                            ]
                            factuality_payload = {
                                "supported": supported,
                                "refuted": refuted,
                                "nei": nei,
                                "precision": precision,
                                "coverage": coverage,
                            }
                        else:
                            # Fall back to on-the-fly extraction from the generated answer
                            claims_run = await engine.run(
                                answer=result.generated_answer,
                                query=query,
                                documents=result.documents or [],
                                claim_extractor=claim_extractor,
                                claim_verifier=claim_verifier,
                                claims_top_k=claims_top_k,
                                claims_conf_threshold=claims_conf_threshold,
                                claims_max=claims_max,
                                retrieve_fn=_retrieve_for_claim,
                                nli_model=nli_model,
                            )
                            claims_payload = claims_run.get("claims")
                            factuality_payload = claims_run.get("summary")
                    except Exception as _eclaims:
                        logger.debug(f"Pre-extracted claims path failed: {_eclaims}")
                        claims_run = await engine.run(
                            answer=result.generated_answer,
                            query=query,
                            documents=result.documents or [],
                            claim_extractor=claim_extractor,
                            claim_verifier=claim_verifier,
                            claims_top_k=claims_top_k,
                            claims_conf_threshold=claims_conf_threshold,
                            claims_max=claims_max,
                            retrieve_fn=_retrieve_for_claim,
                            nli_model=nli_model,
                        )
                        claims_payload = claims_run.get("claims")
                        factuality_payload = claims_run.get("summary")
                    # Also store in metadata for debugging/analytics
                    result.metadata["claims"] = claims_payload
                    result.metadata["factuality"] = factuality_payload
            except Exception as e:
                result.errors.append(f"Claims analysis failed: {str(e)}")
                logger.error(f"Claims analysis error: {e}")

        # ========== USER FEEDBACK ==========
        if collect_feedback:
            feedback_start = time.time()
            try:
                if UnifiedFeedbackSystem:
                    collector = UnifiedFeedbackSystem()
                    feedback_id = str(uuid.uuid4())
                    
                    # Record query for feedback
                    await collector.record_query(
                        query_id=feedback_id,
                        query=query,
                        results=[doc.id for doc in result.documents] if result.documents else [],
                        user_id=feedback_user_id
                    )
                    
                    result.feedback_id = feedback_id
                    result.metadata["feedback_enabled"] = True
                    
                    # Apply feedback boost if requested
                    if apply_feedback_boost and result.documents:
                        boosted = await collector.apply_feedback_boost(
                            result.documents,
                            query
                        )
                        result.documents = boosted
                    
                    result.timings["feedback"] = time.time() - feedback_start
                    
            except ImportError:
                result.errors.append("Feedback module not available")
                logger.warning("Feedback requested but module not available")
            except Exception as e:
                result.errors.append(f"Feedback system failed: {str(e)}")
                logger.error(f"Feedback error: {e}")
        
        # ========== RESULT HIGHLIGHTING ==========
        if highlight_results and result.documents:
            highlight_start = time.time()
            try:
                if highlight_func:
                    for doc in result.documents:
                        doc.content = await highlight_func(
                            doc.content,
                            query if highlight_query_terms else None
                        )
                    
                    result.timings["highlighting"] = time.time() - highlight_start
                    
            except ImportError:
                result.errors.append("Highlighting module not available")
                logger.warning("Highlighting requested but module not available")
        
        # ========== COST TRACKING ==========
        if track_cost:
            try:
                if track_llm_cost:
                    # Calculate estimated cost
                    total_tokens = sum(len(doc.content.split()) for doc in result.documents)
                    cost = await track_llm_cost(
                        model=generation_model or "gpt-3.5-turbo",
                        input_tokens=total_tokens,
                        output_tokens=len(result.generated_answer.split()) if result.generated_answer else 0
                    )
                    
                    result.metadata["estimated_cost"] = cost
                    
            except ImportError:
                result.errors.append("Cost tracking module not available")
        
        # ========== CACHE STORAGE ==========
        if enable_cache and not result.cache_hit and result.documents:
            try:
                # Store in cache for future use
                if SemanticCache:
                    try:
                        cache = SemanticCache(similarity_threshold=cache_threshold, ttl=cache_ttl)
                    except TypeError:
                        cache = SemanticCache(similarity_threshold=cache_threshold)
                elif AdaptiveCache and adaptive_cache:
                    try:
                        cache = AdaptiveCache(similarity_threshold=cache_threshold, ttl=cache_ttl)
                    except TypeError:
                        cache = AdaptiveCache(similarity_threshold=cache_threshold)
                else:
                    cache = None

                if cache:
                    # Support both async/sync and set/add method names
                    set_fn = getattr(cache, 'set', None) or getattr(cache, 'add', None)
                    if set_fn:
                        if asyncio.iscoroutinefunction(set_fn):
                            await set_fn(query, result.documents, ttl=cache_ttl)
                        else:
                            set_fn(query, result.documents, ttl=cache_ttl)
            except Exception as e:
                logger.error(f"Cache storage error: {e}")
        
        # ========== OBSERVABILITY ==========
        if enable_observability:
            try:
                if Tracer:
                    tracer = Tracer()
                    await tracer.trace(
                        trace_id=trace_id or str(uuid.uuid4()),
                        operation="unified_rag_pipeline",
                        query=query,
                        timings=result.timings,
                        metadata=result.metadata
                    )
                    
            except ImportError:
                result.errors.append("Observability module not available")
        
        # ========== PERFORMANCE ANALYSIS ==========
        if enable_performance_analysis:
            try:
                if PerformanceMonitor:
                    monitor = PerformanceMonitor()
                    analysis = await monitor.analyze(
                        timings=result.timings,
                        document_count=len(result.documents),
                        cache_hit=result.cache_hit
                    )
                    
                    result.metadata["performance_analysis"] = analysis
                    
            except ImportError:
                result.errors.append("Performance monitor not available")
        
    except Exception as e:
        result.errors.append(f"Pipeline error: {str(e)}")
        logger.error(f"Unified pipeline error: {e}")
        if fallback_on_error:
            return {
                "query": query,
                "documents": [],
                "answer": "",
                "cached": False,
                "error": str(e),
                "metadata": result.metadata,
                "timings": result.timings,
            }
    
    finally:
        # Calculate total time
        result.total_time = time.time() - start_time
        result.timings["total"] = result.total_time
        
        # Finalize metrics if monitoring
        if metrics:
            metrics.total_time = result.total_time
            metrics.cache_hit = result.cache_hit
            metrics.documents_retrieved = len(result.documents)
            
            if enable_monitoring:
                try:
                    collector = MetricsCollector()
                    await collector.record_query_metrics(metrics)
                except Exception as e:
                    logger.error(f"Metrics recording error: {e}")
        
        # Debug output if requested
        if debug_mode:
            logger.debug(f"Query: {query}")
            logger.debug(f"Documents found: {len(result.documents)}")
            logger.debug(f"Cache hit: {result.cache_hit}")
            logger.debug(f"Timings: {result.timings}")
            logger.debug(f"Errors: {result.errors}")
    
    # Convert to Pydantic response
    try:
        from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
        doc_dicts: List[Dict[str, Any]] = []
        for d in result.documents or []:
            md = dict(d.metadata or {})
            try:
                if getattr(d, 'source', None) is not None:
                    md.setdefault('source', getattr(d, 'source').value)
            except Exception:
                pass
            doc_dicts.append({
                "id": d.id,
                "content": d.content,
                "score": getattr(d, 'score', 0.0),
                "metadata": md
            })
        return UnifiedRAGResponse(
            documents=doc_dicts,
            query=result.query,
            expanded_queries=result.expanded_queries,
            metadata=result.metadata,
            timings=result.timings,
            citations=result.citations,
            academic_citations=(result.metadata or {}).get("academic_citations", []),
            chunk_citations=(result.metadata or {}).get("chunk_citations", []),
            generated_answer=result.generated_answer,
            cache_hit=result.cache_hit,
            errors=result.errors,
            security_report=result.security_report,
            total_time=result.total_time,
            claims=claims_payload,
            factuality=factuality_payload,
        )
    except Exception:
        # Fallback: return a minimal dict if Pydantic is not available
        return {
            "documents": [
                {"id": getattr(d, 'id', None), "content": getattr(d, 'content', None), "metadata": getattr(d, 'metadata', {})}
                for d in (result.documents or [])
            ],
            "query": result.query,
            "expanded_queries": result.expanded_queries,
            "metadata": result.metadata,
            "timings": result.timings,
            "citations": result.citations,
            "generated_answer": result.generated_answer,
            "cache_hit": result.cache_hit,
            "errors": result.errors,
            "security_report": result.security_report,
            "total_time": result.total_time,
            "claims": claims_payload,
            "factuality": factuality_payload,
        }




# ========== BATCH PROCESSING WRAPPER ==========
async def unified_batch_pipeline(
    queries: List[str],
    max_concurrent: int = 5,
    **kwargs
) -> List[UnifiedSearchResult]:
    """
    Process multiple queries concurrently using the unified pipeline.
    
    Args:
        queries: List of queries to process
        max_concurrent: Maximum concurrent executions
        **kwargs: All parameters supported by unified_rag_pipeline_core
        
    Returns:
        List of results in the same order as queries
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(query: str) -> UnifiedSearchResult:
        async with semaphore:
            return await unified_rag_pipeline(query=query, **kwargs)
    
    tasks = [process_with_semaphore(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error results
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            error_result = UnifiedSearchResult(
                documents=[],
                query=queries[i],
                errors=[str(result)]
            )
            final_results.append(error_result)
        else:
            final_results.append(result)
    
    return final_results


# ========== SIMPLE CONVENIENCE WRAPPERS ==========

async def simple_search(query: str, top_k: int = 10) -> List[Document]:
    """
    Simple search wrapper for basic use cases.
    
    Args:
        query: Search query
        top_k: Number of results
        
    Returns:
        List of documents
    """
    result = await unified_rag_pipeline(
        query=query,
        top_k=top_k,
        expand_query=False,
        enable_cache=True,
        enable_reranking=True
    )
    return result.documents


async def advanced_search(
    query: str,
    with_citations: bool = True,
    with_answer: bool = True,
    **kwargs
) -> UnifiedSearchResult:
    """
    Advanced search with commonly used features enabled.
    
    Args:
        query: Search query
        with_citations: Enable citation generation
        with_answer: Enable answer generation
        **kwargs: Additional parameters
        
    Returns:
        Full search result
    """
    return await unified_rag_pipeline(
        query=query,
        expand_query=True,
        expansion_strategies=["acronym", "synonym", "domain"],
        enable_cache=True,
        enable_reranking=True,
        reranking_strategy="hybrid",
        enable_citations=with_citations,
        enable_generation=with_answer,
        enable_table_processing=True,
        enable_performance_analysis=True,
        **kwargs
    )
def compute_temporal_range_from_query(query: str) -> Optional[Dict[str, str]]:
    """Compute an approximate temporal range from a natural language query.

    Returns dict with ISO start/end if a range can be inferred; otherwise None.
    Conservative default: last 7 days if common patterns not found.
    """
    try:
        qlower = (query or "").lower()
        start_dt = None
        end_dt = None
        now = datetime.utcnow()
        if "yesterday" in qlower:
            start_dt = now - timedelta(days=1); end_dt = now
        elif "last week" in qlower or "past week" in qlower:
            start_dt = now - timedelta(days=7); end_dt = now
        elif "last month" in qlower:
            y = now.year; m = now.month - 1 if now.month > 1 else 12; y = y if now.month > 1 else y - 1
            start_dt = datetime(y, m, 1)
            _, last_day = calendar.monthrange(y, m)
            end_dt = datetime(y, m, last_day, 23, 59, 59)
        elif "past month" in qlower:
            start_dt = now - timedelta(days=30); end_dt = now
        m_quarter = re.search(r"\bq([1-4])\s*(20\d{2}|19\d{2})\b", qlower)
        if m_quarter:
            qn = int(m_quarter.group(1)); y = int(m_quarter.group(2)); qm = {1:1,2:4,3:7,4:10}[qn]
            start_dt = datetime(y, qm, 1)
            end_month = qm + 2; _, last_day = calendar.monthrange(y, end_month)
            end_dt = datetime(y, end_month, last_day, 23, 59, 59)
        month_names = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
        m_month_year = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2}|19\d{2})\b", qlower)
        if m_month_year:
            mon = month_names.get(m_month_year.group(1)); y = int(m_month_year.group(2))
            if mon:
                start_dt = datetime(y, mon, 1)
                _, last_day = calendar.monthrange(y, mon)
                end_dt = datetime(y, mon, last_day, 23, 59, 59)
        m_year = re.search(r"\b(20\d{2}|19\d{2})\b", qlower)
        if m_year and start_dt is None and end_dt is None:
            y = int(m_year.group(1)); start_dt = datetime(y,1,1); end_dt = datetime(y,12,31,23,59,59)
        if start_dt is None and end_dt is None:
            start_dt = now - timedelta(days=7); end_dt = now
        return {"start": start_dt.isoformat(), "end": end_dt.isoformat()}
    except Exception:
        return None
