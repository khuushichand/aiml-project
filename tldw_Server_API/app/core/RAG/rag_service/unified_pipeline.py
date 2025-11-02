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
import hashlib
import time
import uuid
import re
from datetime import datetime, timedelta
import calendar
from typing import Dict, List, Any, Optional, Union, Literal
from dataclasses import dataclass, field
from loguru import logger
import asyncio
from functools import partial
try:
    # OpenTelemetry telemetry manager (metrics + tracing)
    from tldw_Server_API.app.core.Metrics.telemetry import get_telemetry_manager, OTEL_AVAILABLE  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    get_telemetry_manager = None  # type: ignore
    OTEL_AVAILABLE = False  # type: ignore

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

# Query intent analysis / routing
try:
    from .query_features import QueryAnalyzer, QueryIntent, QueryRouter
except ImportError:
    QueryAnalyzer = None
    QueryIntent = None
    QueryRouter = None

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

# Advanced retrieval (multi-vector passages)
try:
    from .advanced_retrieval import apply_multi_vector_passages, MultiVectorConfig
except ImportError:
    apply_multi_vector_passages = None  # type: ignore
    MultiVectorConfig = None  # type: ignore

try:
    from .rewrite_cache import RewriteCache
except ImportError:
    RewriteCache = None

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
    from .post_generation_verifier import PostGenerationVerifier
except ImportError:
    PostGenerationVerifier = None

# RAG config helpers for consistent toggles/defaults
try:
    from tldw_Server_API.app.core.config import (
        rag_low_confidence_behavior as _rag_low_conf,
        rag_require_hard_citations as _rag_req_hc,
    )
except Exception:
    _rag_low_conf = None  # type: ignore
    _rag_req_hc = None  # type: ignore

try:
    # Guardrails utilities: injection filtering, numeric fidelity, hard citations
    from .guardrails import (
        downweight_injection_docs,
        detect_injection_score,
        check_numeric_fidelity,
        build_hard_citations,
        build_quote_citations,
        sanitize_html_allowlist,
        apply_content_policy,
        gate_docs_by_ocr_confidence,
    )
except ImportError:
    downweight_injection_docs = None  # type: ignore
    detect_injection_score = None  # type: ignore
    check_numeric_fidelity = None  # type: ignore
    build_hard_citations = None  # type: ignore
    build_quote_citations = None  # type: ignore

try:
    from .analytics_system import UnifiedFeedbackSystem
except ImportError:
    UnifiedFeedbackSystem = None

try:
    from .user_personalization_store import UserPersonalizationStore
except ImportError:
    UserPersonalizationStore = None

try:
    from .observability import Tracer
except ImportError:
    Tracer = None

# Resilience helpers
try:
    from .resilience import get_coordinator, CircuitBreakerConfig, RetryConfig, RetryPolicy
except Exception:
    get_coordinator = None  # type: ignore
    CircuitBreakerConfig = None  # type: ignore
    RetryConfig = None  # type: ignore
    RetryPolicy = None  # type: ignore

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
    enable_intent_routing: bool = False,
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

    # ========== ADVANCED RETRIEVAL ==========
    enable_multi_vector_passages: bool = False,
    mv_span_chars: int = 300,
    mv_stride: int = 150,
    mv_max_spans: int = 8,
    mv_flatten_to_spans: bool = False,
    enable_numeric_table_boost: bool = False,

    # ========== RERANKING ==========
    enable_reranking: bool = True,
    reranking_strategy: Literal["flashrank", "cross_encoder", "hybrid", "llama_cpp", "llm_scoring", "two_tier", "none"] = "flashrank",
    rerank_top_k: Optional[int] = None,  # Defaults to top_k if not specified
    reranking_model: Optional[str] = None,  # Optional model id/path for rerankers (GGUF path or HF model id)
    # Two-tier specific: request-level gating overrides (optional)
    rerank_min_relevance_prob: Optional[float] = None,
    rerank_sentinel_margin: Optional[float] = None,

    # ========== CITATIONS ==========
    enable_citations: bool = False,
    citation_style: Literal["apa", "mla", "chicago", "harvard", "ieee"] = "apa",
    include_page_numbers: bool = False,
    enable_chunk_citations: bool = True,

    # ========== ANSWER GENERATION ==========
    enable_generation: bool = True,
    strict_extractive: bool = False,
    generation_model: Optional[str] = None,
    generation_prompt: Optional[str] = None,
    max_generation_tokens: int = 500,
    # Abstention & multi-turn synthesis
    enable_abstention: bool = False,
    abstention_behavior: Literal["continue", "ask", "decline"] = "continue",
    enable_multi_turn_synthesis: bool = False,
    synthesis_time_budget_sec: Optional[float] = None,
    synthesis_draft_tokens: Optional[int] = None,
    synthesis_refine_tokens: Optional[int] = None,

    # ========== POST-VERIFICATION (ADAPTIVE) ==========
    enable_post_verification: bool = False,
    adaptive_max_retries: int = 1,
    adaptive_unsupported_threshold: float = 0.15,
    adaptive_max_claims: int = 20,
    adaptive_time_budget_sec: Optional[float] = None,
    low_confidence_behavior: Literal["continue", "ask", "decline"] = "continue",
    adaptive_advanced_rewrites: Optional[bool] = None,
    # Optional: perform a bounded full pipeline re-run on low confidence
    adaptive_rerun_on_low_confidence: bool = False,
    adaptive_rerun_include_generation: bool = True,
    adaptive_rerun_bypass_cache: bool = False,
    adaptive_rerun_time_budget_sec: Optional[float] = None,
    adaptive_rerun_doc_budget: Optional[int] = None,
    # Internal guard to prevent nested rerun loops
    _adaptive_rerun: bool = False,

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

    # ========== GENERATION GUARDRAILS ==========
    # Pre-generation: instruction-injection filtering and down-weighting
    enable_injection_filter: bool = True,
    injection_filter_strength: float = 0.5,
    # Content policy: lightweight PII/PHI filtering and sanitation
    enable_content_policy_filter: bool = False,
    content_policy_types: List[str] = None,  # ["pii", "phi"]
    content_policy_mode: Literal["redact", "drop", "annotate"] = "redact",
    enable_html_sanitizer: bool = False,
    html_allowed_tags: Optional[List[str]] = None,
    html_allowed_attrs: Optional[List[str]] = None,
    ocr_confidence_threshold: Optional[float] = None,
    # Post-generation: hard citations per sentence and numeric fidelity checks
    require_hard_citations: bool = False,
    enable_numeric_fidelity: bool = False,
    numeric_fidelity_behavior: Literal["continue", "ask", "decline", "retry"] = "continue",

    # ========== CLAIMS & FACTUALITY ==========
    enable_claims: bool = False,
    claim_extractor: Literal["aps", "claimify", "auto"] = "auto",
    claim_verifier: Literal["nli", "llm", "hybrid"] = "hybrid",
    claims_top_k: int = 5,
    claims_conf_threshold: float = 0.7,
    claims_max: int = 25,
    nli_model: Optional[str] = None,
    claims_concurrency: int = 8,

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
    chacha_db: Any = None,

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

    # --- Internal helpers (defined early so downstream phases can use them) ---
    async def _with_timeout(coro, timeout: Optional[float]):
        if timeout and timeout > 0:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro

    async def _resilient_call(component: str, func, *args, **kwargs):
        """Apply circuit breaker, retries, and timeout around async operations when enabled."""
        breaker = None
        if enable_resilience and circuit_breaker and get_coordinator and CircuitBreakerConfig:
            try:
                coord = get_coordinator()
                if component not in coord.circuit_breakers:
                    coord.register_circuit_breaker(component, CircuitBreakerConfig())
                breaker = coord.circuit_breakers[component]
            except Exception:
                breaker = None

        async def _attempt():
            if breaker is not None:
                return await breaker.call(func, *args, **kwargs)
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        if enable_resilience and (retry_attempts or 0) > 1 and RetryPolicy and RetryConfig:
            policy = RetryPolicy(RetryConfig(max_attempts=int(retry_attempts or 1)))
            call_coro = policy.execute(_attempt)
        else:
            call_coro = _attempt()

        return await _with_timeout(call_coro, timeout_seconds)

    # Basic input validation
    if not isinstance(query, str) or not query.strip():
        msg = "Invalid query"
        result.generated_answer = msg
        result.errors.append(msg)
        result.timings["total"] = 0.0
        # Consistent contract: return UnifiedRAGResponse for all outcomes
        try:
            from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
            return UnifiedRAGResponse(
                documents=[],
                query=(query if isinstance(query, str) else ""),
                expanded_queries=[],
                metadata=result.metadata,
                timings=result.timings,
                citations=[],
                academic_citations=[],
                chunk_citations=[],
                generated_answer=msg,
                cache_hit=False,
                errors=result.errors,
                security_report=None,
                total_time=0.0,
                claims=None,
                factuality=None,
            )
        except Exception:
            # Fallback to dataclass if schema import fails (non-API contexts)
            return UnifiedSearchResult(
                documents=[],
                query=query if isinstance(query, str) else "",
                expanded_queries=[],
                metadata=result.metadata,
                timings=result.timings,
                citations=[],
                feedback_id=None,
                generated_answer=msg,
                cache_hit=False,
                errors=result.errors,
                security_report=None,
                total_time=0.0,
            )

    # Initialize monitoring if requested
    metrics = None
    if enable_monitoring:
        metrics = QueryMetrics(query=query)
        metrics.start_time = start_time

    def _apply_generation_gate(reason: str, *, coverage: Optional[float] = None, unsupported_ratio: Optional[float] = None, threshold: Optional[float] = None) -> None:
        """Record a gating event in metadata for downstream observability."""
        gate = result.metadata.setdefault("generation_gate", {})
        gate.update({
            "reason": reason,
            "at": time.time(),
        })
        if coverage is not None:
            gate["coverage"] = coverage
        if unsupported_ratio is not None:
            gate["unsupported_ratio"] = unsupported_ratio
        if threshold is not None:
            gate["threshold"] = threshold

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
        # ========== PRODUCTION DEFAULTS (env-based) ==========
        # If running in production, enable stricter guardrails by default
        try:
            import os as _os
            _prod_env = str(_os.getenv("tldw_production", "false")).strip().lower() in {"1", "true", "yes", "on"}
            _strict_env = str(_os.getenv("RAG_GUARDRAILS_STRICT", "false")).strip().lower() in {"1", "true", "yes", "on"}
            if _prod_env or _strict_env:
                if not enable_numeric_fidelity:
                    enable_numeric_fidelity = True
                if not require_hard_citations:
                    require_hard_citations = True
                # Behavior default can be tuned via env when it's left as "continue"
                if (numeric_fidelity_behavior == "continue"):
                    _beh = _os.getenv("RAG_NUMERIC_FIDELITY_BEHAVIOR", "ask").strip().lower()
                    if _beh in {"continue", "ask", "decline", "retry"}:
                        numeric_fidelity_behavior = _beh  # type: ignore
        except Exception:
            pass

        # Apply config-driven defaults for confidence/citation gates when not explicitly set
        try:
            if _rag_low_conf:
                cfg_lcb = _rag_low_conf()
                if (low_confidence_behavior or "continue") == "continue" and cfg_lcb != "continue":
                    low_confidence_behavior = cfg_lcb  # type: ignore[assignment]
            if _rag_req_hc and not bool(require_hard_citations):
                if bool(_rag_req_hc(default=False)):
                    require_hard_citations = True  # type: ignore[assignment]
        except Exception:
            pass

        # Apply config-driven default for strict extractive generation
        try:
            from tldw_Server_API.app.core.config import rag_strict_extractive as _rag_strict
        except Exception:
            _rag_strict = None  # type: ignore
        try:
            if _rag_strict and not bool(strict_extractive):
                if bool(_rag_strict(default=False)):
                    strict_extractive = True  # type: ignore[assignment]
        except Exception:
            pass

        # ========== QUERY EXPANSION ==========
        expanded_queries = [query]
        if expand_query:
            expansion_start = time.time()
            try:
                # Try rewrite cache first
                cached_rewrites: List[str] = []
                intent_label = None
                if QueryAnalyzer:
                    try:
                        qa = QueryAnalyzer(); analysis = qa.analyze_query(query)
                        intent_label = getattr(analysis, "intent", None)
                        if intent_label is not None:
                            intent_label = getattr(intent_label, "value", str(intent_label))
                    except Exception:
                        intent_label = None
                if RewriteCache:
                    try:
                        rc = RewriteCache(user_id=user_id or "anon")
                        cached = rc.get(query, intent=intent_label, corpus=index_namespace)
                        if cached:
                            cached_rewrites = [c for c in cached if isinstance(c, str) and c.strip()]
                            expanded_queries = list({q.strip(): None for q in ([query] + cached_rewrites)}.keys())
                    except Exception:
                        pass
                strategies = (expansion_strategies or ["acronym", "synonym"]).copy()
                if multi_strategy_expansion:
                    if index_namespace:
                        expanded = await multi_strategy_expansion(query, strategies=strategies, corpus=index_namespace)
                    else:
                        # Avoid passing None to preserve expected call signature in tests
                        expanded = await multi_strategy_expansion(query, strategies=strategies)
                    if isinstance(expanded, list):
                        expanded_queries = list({q.strip(): None for q in ([query] + expanded) if isinstance(q, str)}.keys())
                    elif isinstance(expanded, str) and expanded.strip():
                        expanded_queries = list({q.strip(): None for q in ([query, expanded]) if isinstance(q, str)}.keys())
                # Persist effective rewrites for future reuse (best-effort)
                try:
                    if RewriteCache and len(expanded_queries) > 1:
                        rew = [q for q in expanded_queries if q != query][:5]
                        if rew:
                            rc = RewriteCache(user_id=user_id or "anon")
                            rc.put(query, rewrites=rew, intent=intent_label, corpus=index_namespace)
                except Exception:
                    pass
                result.expanded_queries = [q for q in expanded_queries if q != query]
                result.timings["query_expansion"] = time.time() - expansion_start
                if metrics:
                    metrics.expansion_time = result.timings["query_expansion"]
            except Exception as e:
                result.errors.append(f"Query expansion failed: {str(e)}")
                logger.warning(f"Query expansion error: {e}")

        # ========== INTENT ROUTING (optional) ==========
        if enable_intent_routing and QueryRouter:
            try:
                router = QueryRouter()
                routing = router.route_query(query)
                # Map routing decisions to current pipeline knobs conservatively
                # Keep search_mode hybrid by default; adjust hybrid_alpha and top_k
                strat = str(routing.get("retrieval_strategy", "")).lower()
                if strat == "precise":
                    # Favor lexical; shift hybrid_alpha toward FTS
                    try:
                        hybrid_alpha = min(max(0.0, float(hybrid_alpha)), 1.0)
                    except Exception:
                        pass
                    hybrid_alpha = min(hybrid_alpha, 0.5)
                elif strat == "broad":
                    # Favor semantic
                    try:
                        hybrid_alpha = min(max(0.0, float(hybrid_alpha)), 1.0)
                    except Exception:
                        pass
                    hybrid_alpha = max(hybrid_alpha, 0.7)
                # Respect suggested top_k when present
                try:
                    tk = int(routing.get("top_k", top_k))
                    if 1 <= tk <= 100:
                        top_k = tk
                except Exception:
                    pass
                result.metadata["intent_routing"] = {
                    "strategy": strat,
                    "hybrid_alpha": hybrid_alpha,
                    "top_k": top_k,
                }
            except Exception as e:
                result.errors.append(f"Intent routing failed: {e}")

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

                if result.cache_hit:
                    if isinstance(cached_documents, dict):
                        ans = cached_documents.get("answer")
                        if ans is not None:
                            result.generated_answer = ans
                        docs = cached_documents.get("documents")
                        if isinstance(docs, list):
                            result.documents = docs
                        if cached_documents.get("cached") is True:
                            result.metadata["cached_flag"] = True
                    elif isinstance(cached_documents, list):
                        # Backward compatibility: older cache entries stored document lists directly
                        result.documents = cached_documents
                    result.metadata.setdefault("cached_flag", True)

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
                # --- OTEL: retrieval span ---
                _otel_cm = None
                _otel_span = None
                if enable_observability and get_telemetry_manager:
                    try:
                        _tm = get_telemetry_manager()
                        _tr = _tm.get_tracer("tldw.rag")
                        _attrs = {
                            "rag.phase": "retrieval",
                            "rag.search_mode": str(search_mode),
                            "rag.top_k": int(top_k or 0),
                            "rag.index_namespace": str(index_namespace or "")
                        }
                        _otel_cm = _tr.start_as_current_span("rag.retrieval")
                        _otel_span = _otel_cm.__enter__()
                        for _k, _v in _attrs.items():
                            try:
                                _otel_span.set_attribute(_k, _v)
                            except Exception:
                                pass
                    except Exception:
                        _otel_cm = None
                        _otel_span = None
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
                            chacha_db=chacha_db,
                        )
                    except TypeError:
                        retriever = MultiDatabaseRetriever(
                            db_paths,
                            user_id=user_id or "0",
                            media_db=media_db,
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
                        documents = await _resilient_call(
                            "retrieval",
                            rh,
                            query=query,
                            alpha=hybrid_alpha,
                            index_namespace=index_namespace,
                            allowed_media_ids=include_media_ids,
                        )
                    else:
                        documents = await _resilient_call(
                            "retrieval",
                            retriever.retrieve,
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
                    # Record phase duration with difficulty label
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram
                        def _difficulty(docs:list) -> str:
                            try:
                                if not docs:
                                    return "hard"
                                high = sum(1 for d in docs if float(getattr(d, 'score', 0.0)) >= max(min_score, 0.3))
                                if high >= max(3, int(0.3 * len(docs))):
                                    return "easy"
                                if high >= 1:
                                    return "medium"
                                return "hard"
                            except Exception:
                                return "unknown"
                        observe_histogram("rag_phase_duration_seconds", result.timings["retrieval"], labels={"phase": "retrieval", "difficulty": _difficulty(result.documents or [])})
                        # Also attach difficulty as OTEL attribute if span is active
                        if _otel_span is not None:
                            try:
                                _otel_span.set_attribute("rag.query_difficulty", _difficulty(result.documents or []))
                                _otel_span.set_attribute("rag.doc_count", int(len(result.documents or [])))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if metrics:
                        metrics.retrieval_time = result.timings["retrieval"]

            except Exception as e:
                result.errors.append(f"Document retrieval failed: {str(e)}")
                logger.error(f"Retrieval error: {e}")
                # Sample payload exemplar on retrieval failure
                try:
                    from .payload_exemplars import maybe_record_exemplar
                    maybe_record_exemplar(
                        query=query,
                        documents=result.documents or [],
                        answer=result.generated_answer or "",
                        reason="retrieval_error",
                        user_id=user_id,
                    )
                except Exception:
                    pass
            finally:
                # Ensure OTEL span is closed
                if _otel_cm is not None:
                    try:
                        _otel_cm.__exit__(None, None, None)
                    except Exception:
                        pass

        # ========== MULTI-VECTOR PASSAGES (optional, pre-rerank) ==========
        if enable_multi_vector_passages and result.documents:
            mv_start = time.time()
            try:
                if apply_multi_vector_passages and MultiVectorConfig:
                    cfg = MultiVectorConfig(
                        span_chars=int(mv_span_chars or 300),
                        stride=int(mv_stride or 150),
                        max_spans_per_doc=int(mv_max_spans or 8),
                        flatten_to_spans=bool(mv_flatten_to_spans or False),
                    )
                    mv_docs = await apply_multi_vector_passages(
                        query=query,
                        documents=result.documents,
                        config=cfg,
                        user_id=user_id,
                    )
                    if mv_docs:
                        result.documents = mv_docs[: top_k]
                        result.metadata.setdefault("multi_vector", {})
                        result.metadata["multi_vector"].update({
                            "enabled": True,
                            "span_chars": cfg.span_chars,
                            "stride": cfg.stride,
                            "max_spans_per_doc": cfg.max_spans_per_doc,
                            "flattened": cfg.flatten_to_spans,
                        })
                else:
                    result.errors.append("Multi-vector module not available")
            except Exception as e:
                result.errors.append(f"Multi-vector passages failed: {e}")
            finally:
                result.timings["multi_vector"] = time.time() - mv_start
                try:
                    from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram
                    observe_histogram("rag_phase_duration_seconds", result.timings["multi_vector"], labels={"phase": "multi_vector", "difficulty": str(result.metadata.get("query_intent", "na"))})
                except Exception:
                    pass

        # ========== NUMERIC/TABLE-AWARE BOOST (optional, pre-rerank) ==========
        if enable_numeric_table_boost and result.documents:
            try:
                import re as _re
                q_has_num = bool(_re.search(r"\d", query)) or bool(_re.search(r"\b(percent|percentage|million|billion|thousand|\$|usd|eur|kg|g|lb|%|k|m|b)\b", query, _re.I))
            except Exception:
                q_has_num = False
            if q_has_num:
                affected = 0
                for d in result.documents:
                    try:
                        md = getattr(d, "metadata", None) or {}
                        chunk_type = str(md.get("chunk_type", "")).lower()
                        text = getattr(d, "content", "") or ""
                        numbers = sum(1 for _ in _re.finditer(r"\d", text))
                        looks_table = (chunk_type == "table") or (text.count("|") >= 3) or ("\t" in text)
                        if looks_table or numbers >= 6:
                            s = float(getattr(d, "score", 0.0) or 0.0)
                            # modest boost within [0,1]
                            d.score = min(1.0, s * 1.1 + 0.02)
                            md["numeric_table_boost"] = True
                            d.metadata = md
                            affected += 1
                    except Exception:
                        continue
                result.metadata["numeric_table_boost"] = {"enabled": True, "affected": int(affected)}

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

        # ========== INSTRUCTION-INJECTION FILTERING (pre-reranking) ==========
        if enable_injection_filter and result.documents:
            inj_start = time.time()
            try:
                if downweight_injection_docs:
                    summary = downweight_injection_docs(result.documents, strength=float(injection_filter_strength or 0.5))
                    result.metadata.setdefault("injection_filter", {})
                    result.metadata["injection_filter"].update({
                        "affected": int(summary.get("affected", 0)),
                        "total": int(summary.get("total", len(result.documents))),
                        "strength": float(injection_filter_strength or 0.5),
                    })
                    # Optional metric
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                        if int(summary.get("affected", 0)) > 0:
                            increment_counter("rag_injection_chunks_downweighted_total", int(summary.get("affected", 0)))
                    except Exception:
                        pass
                else:
                    result.errors.append("Injection filter module not available")
            except Exception as e:
                result.errors.append(f"Injection filtering failed: {str(e)}")
            finally:
                result.timings["injection_filter"] = time.time() - inj_start

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

        # ========== CONTENT POLICY FILTERS & SANITATION ==========
        if result.documents:
            try:
                # OCR gating
                if ocr_confidence_threshold is not None:
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                        dropped = gate_docs_by_ocr_confidence(result.documents, float(ocr_confidence_threshold))
                        if dropped > 0:
                            increment_counter("rag_ocr_dropped_docs_total", dropped)
                    except Exception:
                        pass
                # HTML sanitation
                if enable_html_sanitizer:
                    sanitized = 0
                    for d in (result.documents or []):
                        try:
                            before = d.content or ""
                            after = sanitize_html_allowlist(before, html_allowed_tags, html_allowed_attrs)
                            if after != before:
                                d.content = after
                                sanitized += 1
                        except Exception:
                            continue
                    try:
                        if sanitized > 0:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                            increment_counter("rag_sanitized_docs_total", sanitized)
                    except Exception:
                        pass
                # Content policy (PII/PHI)
                if enable_content_policy_filter:
                    summary = apply_content_policy(result.documents, policy_types=(content_policy_types or ["pii"]), mode=str(content_policy_mode or "redact"))
                    result.metadata.setdefault("content_policy", {})
                    result.metadata["content_policy"].update({
                        "enabled": True,
                        "types": content_policy_types or ["pii"],
                        "mode": content_policy_mode,
                        "affected": int(summary.get("affected", 0)),
                        "dropped": int(summary.get("dropped", 0)),
                    })
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                        if int(summary.get("affected", 0)) > 0:
                            increment_counter("rag_policy_filtered_chunks_total", int(summary.get("affected", 0)), labels={"mode": str(content_policy_mode or "redact")})
                    except Exception:
                        pass
            except Exception:
                # Non-fatal: continue
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


        # Apply personalization priors (pre-rerank) if requested
        try:
            if apply_feedback_boost and result.documents and UserPersonalizationStore:
                store = UserPersonalizationStore(feedback_user_id or user_id)
                result.documents = store.boost_documents(result.documents, corpus=index_namespace)
                result.metadata.setdefault("personalization", {})["boost_applied_pre_rerank"] = True
        except Exception:
            pass

        # ========== RERANKING ==========
        if enable_reranking and result.documents and reranking_strategy != "none":
            rerank_start = time.time()
            try:
                # --- OTEL: reranking span ---
                _otel_cm_rk = None
                _otel_span_rk = None
                if enable_observability and get_telemetry_manager:
                    try:
                        _tm = get_telemetry_manager()
                        _tr = _tm.get_tracer("tldw.rag")
                        _attrs = {
                            "rag.phase": "rerank",
                            "rag.strategy": str(reranking_strategy),
                            "rag.top_k": int((rerank_top_k or top_k) or 0),
                        }
                        _otel_cm_rk = _tr.start_as_current_span("rag.rerank")
                        _otel_span_rk = _otel_cm_rk.__enter__()
                        for _k, _v in _attrs.items():
                            try:
                                _otel_span_rk.set_attribute(_k, _v)
                            except Exception:
                                pass
                    except Exception:
                        _otel_cm_rk = None
                        _otel_span_rk = None
                if create_reranker and RerankingStrategy and RerankingConfig:
                    strategy_map = {
                        "flashrank": RerankingStrategy.FLASHRANK,
                        "cross_encoder": RerankingStrategy.CROSS_ENCODER,
                        "hybrid": RerankingStrategy.HYBRID,
                        "llama_cpp": RerankingStrategy.LLAMA_CPP,
                        "diversity": RerankingStrategy.DIVERSITY,
                        "llm_scoring": RerankingStrategy.LLM_SCORING,
                        "two_tier": RerankingStrategy.TWO_TIER,
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
                        # Request-level gating overrides (TwoTier)
                        min_relevance_prob=rerank_min_relevance_prob,
                        sentinel_margin=rerank_sentinel_margin,
                    )
                    reranker = create_reranker(selected_strategy, rerank_config, llm_client=llm_client)
                    reranked = await _resilient_call("reranking", reranker.rerank, query, result.documents)
                    if reranked and hasattr(reranked[0], 'document'):
                        result.documents = [sd.document for sd in reranked[:(rerank_top_k or top_k)]]
                    else:
                        result.documents = reranked[:(rerank_top_k or top_k)]

                    result.timings["reranking"] = time.time() - rerank_start
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram
                        observe_histogram("rag_reranking_duration_seconds", result.timings["reranking"], labels={"strategy": reranking_strategy})
                        # Also record as a generic phase without difficulty
                        observe_histogram("rag_phase_duration_seconds", result.timings["reranking"], labels={"phase": "reranking", "difficulty": "na"})
                        if _otel_span_rk is not None:
                            try:
                                _otel_span_rk.set_attribute("rag.doc_count", int(len(result.documents or [])))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if metrics:
                        metrics.reranking_time = result.timings["reranking"]

                    # If reranker exposes calibration metadata (e.g., TwoTier), record it
                    try:
                        if hasattr(reranker, 'last_metadata') and isinstance(getattr(reranker, 'last_metadata'), dict):
                            result.metadata.setdefault("reranking_calibration", {})
                            result.metadata["reranking_calibration"].update(getattr(reranker, 'last_metadata'))
                    except Exception:
                        pass

                else:
                    result.errors.append("Reranking module not available")
                    logger.warning("Reranking requested but module not available")
            except Exception as e:
                result.errors.append(f"Reranking failed: {str(e)}")
                logger.error(f"Reranking error: {e}")
                # Sample payload exemplar on reranking failure
                try:
                    from .payload_exemplars import maybe_record_exemplar
                    maybe_record_exemplar(
                        query=query,
                        documents=result.documents or [],
                        answer=result.generated_answer or "",
                        reason="reranking_error",
                        user_id=user_id,
                    )
                except Exception:
                    pass
            finally:
                if _otel_cm_rk is not None:
                    try:
                        _otel_cm_rk.__exit__(None, None, None)
                    except Exception:
                        pass

        # ========== WHY THESE SOURCES (metadata) ==========
        try:
            docs = result.documents or []
            if docs:
                import urllib.parse
                def _host(u: Optional[str]) -> Optional[str]:
                    try:
                        if not u:
                            return None
                        return urllib.parse.urlparse(str(u)).hostname
                    except Exception:
                        return None
                hosts = []
                sources_ = []
                ages = []
                scores = []
                now_ts = time.time()
                for d in docs:
                    md = getattr(d, 'metadata', None) or (d.get('metadata') if isinstance(d, dict) else {}) or {}
                    url = md.get('url')
                    h = _host(url)
                    if h:
                        hosts.append(h)
                    src = md.get('source') or str(getattr(d, 'source', '') or '')
                    if src:
                        sources_.append(str(src))
                    created = md.get('last_modified') or md.get('created_at')
                    ts = None
                    try:
                        if isinstance(created, (int, float)):
                            ts = float(created)
                        elif isinstance(created, str) and created:
                            from datetime import datetime
                            ts = datetime.fromisoformat(created.replace('Z','+00:00')).timestamp()
                    except Exception:
                        ts = None
                    if ts is not None:
                        ages.append(max(0.0, (now_ts - ts) / 86400.0))
                    try:
                        scores.append(float(getattr(d, 'score', d.get('score', 0.0) if isinstance(d, dict) else 0.0)))
                    except Exception:
                        scores.append(0.0)
                n = max(1, len(docs))
                uniq_hosts = len(set(hosts)) if hosts else 0
                uniq_sources = len(set(sources_)) if sources_ else 0
                diversity = min(1.0, max(uniq_hosts, uniq_sources) / float(n))
                fresh_portion = 0.5
                if ages:
                    fresh = sum(1 for a in ages if a <= 90.0)
                    fresh_portion = fresh / float(len(ages))
                if scores:
                    smin, smax = min(scores), max(scores)
                    if smax > smin:
                        topicality = sum((s - smin) / (smax - smin) for s in scores) / float(len(scores))
                    else:
                        topicality = 1.0
                else:
                    topicality = 0.0
                def _title(md):
                    try:
                        return (md.get('title') or '') if isinstance(md, dict) else ''
                    except Exception:
                        return ''
                top_contexts = []
                for d in docs[: min(10, n)]:
                    md = getattr(d, 'metadata', None) or (d.get('metadata') if isinstance(d, dict) else {}) or {}
                    top_contexts.append({
                        "id": getattr(d, 'id', d.get('id') if isinstance(d, dict) else None),
                        "title": _title(md),
                        "score": float(getattr(d, 'score', md.get('score', 0.0) if isinstance(md, dict) else 0.0) or 0.0),
                        "url": md.get('url'),
                        "source": md.get('source') or str(getattr(d, 'source', '') or ''),
                    })
                result.metadata["why_these_sources"] = {
                    "diversity": round(float(diversity), 4),
                    "freshness": round(float(fresh_portion), 4),
                    "topicality": round(float(topicality), 4),
                    "top_contexts": top_contexts,
                }
        except Exception:
            pass

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
        # Honor reranking calibration gating if present (e.g., TwoTier strategy)
        try:
            _cal = result.metadata.get("reranking_calibration") if isinstance(result.metadata, dict) else None
            gated_generation = bool(_cal.get("gated")) if isinstance(_cal, dict) else False
        except Exception:
            gated_generation = False

        if enable_generation and not gated_generation and not result.cache_hit:
            generation_start = time.time()
            try:
                # --- OTEL: generation span ---
                _otel_cm_gen = None
                _otel_span_gen = None
                if enable_observability and get_telemetry_manager:
                    try:
                        _tm = get_telemetry_manager()
                        _tr = _tm.get_tracer("tldw.rag")
                        _attrs = {
                            "rag.phase": "generation",
                            "rag.model": str(generation_model or ""),
                            "rag.multi_turn": bool(enable_multi_turn_synthesis),
                        }
                        _otel_cm_gen = _tr.start_as_current_span("rag.generation")
                        _otel_span_gen = _otel_cm_gen.__enter__()
                        for _k, _v in _attrs.items():
                            try:
                                _otel_span_gen.set_attribute(_k, _v)
                            except Exception:
                                pass
                    except Exception:
                        _otel_cm_gen = None
                        _otel_span_gen = None
                # Strict extractive path: assemble answer from retrieved spans only
                if bool(strict_extractive):
                    try:
                        # Simple extractive assembly: pick top sentences from top documents
                        max_sents = 6
                        chosen: List[str] = []
                        import re as _re
                        q_terms = [t.lower() for t in _re.findall(r"[A-Za-z0-9_-]{3,}", query or "")][:10]
                        for doc in (result.documents or [])[: min(5, len(result.documents or []))]:
                            text = (getattr(doc, 'content', '') or '').strip()
                            if not text:
                                continue
                            sents = [s.strip() for s in _re.split(r"(?<=[\.!?])\s+", text) if s.strip()]
                            # prefer a sentence containing a query term
                            hit = None
                            for s in sents:
                                low = s.lower()
                                if any(t in low for t in q_terms):
                                    hit = s
                                    break
                            if not hit and sents:
                                hit = sents[0]
                            if hit and hit not in chosen:
                                chosen.append(hit)
                                if len(chosen) >= max_sents:
                                    break
                        result.generated_answer = " " .join(chosen).strip()
                    except Exception as _se:
                        result.errors.append(f"Strict extractive assembly failed: {_se}")
                        result.generated_answer = None
                elif AnswerGenerator:
                    generator = AnswerGenerator(model=generation_model)

                    # Prepare base context from top documents
                    context_docs = (result.documents[:5] if result.documents else [])
                    context = "\n\n".join([getattr(doc, 'content', str(doc)) for doc in context_docs])

                    if enable_multi_turn_synthesis:
                        # Strict budget control
                        t0 = time.time()
                        budget = float(synthesis_time_budget_sec) if synthesis_time_budget_sec else None
                        aborted = False

                        # Draft
                        draft_tokens = int(synthesis_draft_tokens or min(max_generation_tokens, 400))
                        d_start = time.time()
                        draft_out = await generator.generate(
                            query=query,
                            context=context,
                            prompt_template=generation_prompt,
                            max_tokens=draft_tokens,
                        )
                        d_ans = draft_out.get("answer") if isinstance(draft_out, dict) else draft_out
                        d_dt = time.time() - d_start

                        # Critique
                        c_text = None
                        c_dt = 0.0
                        try:
                            import tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib as sgl  # type: ignore
                            # Construct a compact critique prompt using small snippets
                            snippets = []
                            for d in context_docs[:3]:
                                s = (getattr(d, 'content', '') or '')[:250].replace('\n', ' ')
                                if s:
                                    snippets.append(f"- {s}")
                            crit_prompt = (
                                "You are a careful reviewer.\n"
                                "Given the user query, retrieved snippets, and the draft answer, list the top 3 issues (missing facts or unsupported claims).\n"
                                f"Query: {query}\nSnippets:\n" + "\n".join(snippets) + f"\n\nDraft:\n{d_ans}\n\nIssues:"
                            )
                            c_start = time.time()
                            c_text = sgl.analyze(api_name="openai", input_data="", custom_prompt_arg=crit_prompt, model_override=None)
                            c_dt = time.time() - c_start
                        except Exception:
                            c_text = "- Ensure claims are supported by provided snippets.\n- Add missing specifics.\n- Clarify ambiguous statements."

                        # Check budget
                        if budget is not None and (time.time() - t0) >= budget:
                            aborted = True
                            result.generated_answer = d_ans
                            result.metadata.setdefault("synthesis", {})
                            result.metadata["synthesis"].update({"enabled": True, "aborted": True, "durations": {"draft": d_dt, "critique": c_dt, "refine": 0.0}})
                        else:
                            # Refine
                            refine_tokens = int(synthesis_refine_tokens or max_generation_tokens)
                            r_ctx = context + "\n\nCRITIQUE:\n" + (c_text or "")
                            r_start = time.time()
                            r_out = await generator.generate(
                                query=query,
                                context=r_ctx,
                                prompt_template=generation_prompt,
                                max_tokens=refine_tokens,
                            )
                            r_ans = r_out.get("answer") if isinstance(r_out, dict) else r_out
                            r_dt = time.time() - r_start
                            result.generated_answer = r_ans
                            result.metadata.setdefault("synthesis", {})
                            result.metadata["synthesis"].update({"enabled": True, "aborted": False, "durations": {"draft": d_dt, "critique": c_dt, "refine": r_dt}})
                    else:
                        # Single-pass generation
                        answer = await _resilient_call(
                            "generation",
                            generator.generate,
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
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import observe_histogram
                        observe_histogram("rag_phase_duration_seconds", result.timings["answer_generation"], labels={"phase": "generation", "difficulty": str(result.metadata.get("query_intent", "na"))})
                        if enable_multi_turn_synthesis:
                            observe_histogram("rag_phase_duration_seconds", result.timings["answer_generation"], labels={"phase": "synthesis", "difficulty": str(result.metadata.get("query_intent", "na"))})
                        if _otel_span_gen is not None:
                            try:
                                _ans_len = len((result.generated_answer or ""))
                                _otel_span_gen.set_attribute("rag.answer_length", int(_ans_len))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if metrics:
                        metrics.generation_time = result.timings["answer_generation"]

            except ImportError:
                result.errors.append("Generation module not available")
                logger.warning("Answer generation requested but module not available")
            except Exception as e:
                result.errors.append(f"Answer generation failed: {str(e)}")
                logger.error(f"Generation error: {e}")
                try:
                    from .payload_exemplars import maybe_record_exemplar
                    maybe_record_exemplar(
                        query=query,
                        documents=result.documents or [],
                        answer=result.generated_answer or "",
                        reason="generation_error",
                        user_id=user_id,
                    )
                except Exception:
                    pass
            finally:
                if _otel_cm_gen is not None:
                    try:
                        _otel_cm_gen.__exit__(None, None, None)
                    except Exception:
                        pass
        elif enable_generation and gated_generation:
            # Record a metadata entry and bump a metric for observability
            result.metadata.setdefault("generation_gate", {})
            result.metadata["generation_gate"].update({
                "reason": "low_relevance_probability",
                "at": time.time(),
            })
            try:
                from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                increment_counter("rag_generation_gated_total", 1, labels={"strategy": "two_tier"})
            except Exception:
                pass
            # Sample payload exemplar when generation is gated
            try:
                from .payload_exemplars import maybe_record_exemplar
                maybe_record_exemplar(
                    query=query,
                    documents=result.documents or [],
                    answer=result.generated_answer or "",
                    reason="generation_gated",
                    user_id=user_id,
                )
            except Exception:
                pass
            # Abstention / clarifying question path
            if enable_abstention:
                try:
                    clar_q = None
                    if abstention_behavior == "ask":
                        # Form a concise clarifying question using query analysis if available
                        if QueryAnalyzer:
                            try:
                                qa = QueryAnalyzer(); an = qa.analyze_query(query)
                                domain = getattr(an, "domain", None)
                                intent = getattr(getattr(an, "intent", None), "value", None)
                                clar_q = f"Please clarify: what specific aspect of '{query}' should I focus on{f' in {domain}' if domain else ''}?"
                            except Exception:
                                clar_q = None
                        if not clar_q:
                            clar_q = f"Could you clarify which specific details about '{query}' you need?"
                        result.generated_answer = clar_q
                    elif abstention_behavior == "decline":
                        result.generated_answer = "I don’t have sufficient grounded evidence to answer confidently. Please clarify your question or provide more context."
                    # 'continue' leaves generated_answer unset but records gate metadata
                except Exception:
                    pass

        # ========== HARD CITATIONS (per-sentence) ==========
        # Build per-sentence citation map using claims (if available) or heuristic fallback
        try:
            if result.generated_answer:
                hc = None
                # Prefer claims payload if present
                claims_payload = result.metadata.get("claims") if isinstance(result.metadata, dict) else None
                if build_hard_citations:
                    hc = build_hard_citations(result.generated_answer, result.documents or [], claims_payload=claims_payload)
                if isinstance(hc, dict):
                    result.metadata["hard_citations"] = hc
                    # If hard-citation coverage is incomplete and strict mode is requested, apply behavior
                    if bool(require_hard_citations):
                        cov = float(hc.get("coverage") or 0.0)
                        if cov < 1.0:
                            _apply_generation_gate("missing_hard_citations", coverage=cov)
                            try:
                                from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                                increment_counter("rag_missing_hard_citations_total", 1)
                            except Exception:
                                pass
                            # Honor low_confidence_behavior
                            if low_confidence_behavior == "ask":
                                note = "\n\n[Note] Some statements lack supporting citations. Please clarify or provide sources."
                                result.generated_answer = (result.generated_answer or "") + note
                            elif low_confidence_behavior == "decline":
                                result.generated_answer = "Insufficient evidence: missing citations for some statements."
                        # Gauge for coverage (report once per answer)
                        try:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import set_gauge
                            set_gauge("rag_hard_citation_coverage", cov, labels={"strategy": "standard"})
                        except Exception:
                            pass
        except Exception as e:
            result.errors.append(f"Hard citations mapping failed: {str(e)}")

        # ========== QUOTE-LEVEL CITATIONS ==========
        try:
            if result.generated_answer and build_quote_citations:
                qc = build_quote_citations(result.generated_answer, result.documents or [])
                if isinstance(qc, dict):
                    result.metadata["quote_citations"] = qc
        except Exception as e:
            result.errors.append(f"Quote citations mapping failed: {str(e)}")

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
                                # Initialize multi retriever scoped to user's databases
                                try:
                                    mdr = MultiDatabaseRetriever(
                                        db_paths,
                                        user_id=user_id or "0",
                                        media_db=media_db,
                                        chacha_db=chacha_db,
                                    )
                                except TypeError:
                                    mdr = MultiDatabaseRetriever(
                                        db_paths,
                                        user_id=user_id or "0",
                                        media_db=media_db,
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
                                    mode=(claim_verifier or "hybrid").strip().lower(),
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
                                claims_concurrency=claims_concurrency,
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
                            claims_concurrency=claims_concurrency,
                        )
                        claims_payload = claims_run.get("claims")
                        factuality_payload = claims_run.get("summary")
                    # Also store in metadata for debugging/analytics
                    result.metadata["claims"] = claims_payload
                    result.metadata["factuality"] = factuality_payload
            except Exception as e:
                result.errors.append(f"Claims analysis failed: {str(e)}")
                logger.error(f"Claims analysis error: {e}")

        # ========== NUMERIC FIDELITY (verify numeric tokens) ==========
        try:
            if result.generated_answer and check_numeric_fidelity:
                nf = check_numeric_fidelity(result.generated_answer, result.documents or [])
                if nf:
                    result.metadata.setdefault("numeric_fidelity", {})
                    result.metadata["numeric_fidelity"].update({
                        "present": sorted(list(nf.present)),
                        "missing": sorted(list(nf.missing)),
                        "source_numbers": sorted(list(nf.union_source_numbers))[:100],
                    })
                    if nf.missing:
                        try:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                            increment_counter("rag_numeric_mismatches_total", len(nf.missing))
                        except Exception:
                            pass
                        # Optional corrective action
                        if enable_numeric_fidelity and numeric_fidelity_behavior in {"retry", "ask", "decline"}:
                            if numeric_fidelity_behavior == "retry":
                                # Best-effort: targeted retrieval on missing numbers (bounded)
                                try:
                                    if MultiDatabaseRetriever and RetrievalConfig and media_db_path:
                                        mdr = MultiDatabaseRetriever({"media_db": media_db_path}, user_id=user_id or "0")
                                        conf = RetrievalConfig(max_results=min(10, top_k), min_score=min_score, use_fts=True, use_vector=True, include_metadata=True, fts_level=fts_level)
                                        added = []
                                        for tok in list(nf.missing)[:3]:
                                            try:
                                                added.extend(await mdr.retrieve(query=f"{query} {tok}", sources=[DataSource.MEDIA_DB], config=conf, index_namespace=index_namespace))
                                            except Exception:
                                                continue
                                        if added:
                                            # Merge with existing docs and optionally re-rerank in place
                                            by_id: Dict[str, Document] = {getattr(d, 'id', ''): d for d in (result.documents or [])}
                                            for d in added:
                                                cur = by_id.get(getattr(d, 'id', ''))
                                                if cur is None or float(getattr(d, 'score', 0.0)) > float(getattr(cur, 'score', 0.0)):
                                                    by_id[getattr(d, 'id', '')] = d
                                            result.documents = sorted(by_id.values(), key=lambda x: getattr(x, 'score', 0.0), reverse=True)[: max(top_k, 10)]
                                            result.metadata.setdefault("numeric_fidelity", {})
                                            result.metadata["numeric_fidelity"]["retry_docs_added"] = len(added)
                                            # Attempt quick regeneration if generator is available
                                            if AnswerGenerator:
                                                try:
                                                    generator = AnswerGenerator(model=generation_model)
                                                    context = "\n\n".join([getattr(d, 'content', str(d)) for d in (result.documents[:5] if result.documents else [])])
                                                    regen = await generator.generate(query=query, context=context, prompt_template=generation_prompt, max_tokens=max_generation_tokens)
                                                    if isinstance(regen, dict) and regen.get("answer"):
                                                        result.generated_answer = regen.get("answer")
                                                    elif isinstance(regen, str):
                                                        result.generated_answer = regen
                                                except Exception:
                                                    pass
                                except Exception:
                                    pass
                            elif numeric_fidelity_behavior == "ask":
                                note = "\n\n[Note] Some numeric values could not be verified against sources. Please clarify or provide references."
                                result.generated_answer = (result.generated_answer or "") + note
                            elif numeric_fidelity_behavior == "decline":
                                result.generated_answer = "Insufficient evidence to verify numeric claims in the current context."
        except Exception as e:
            result.errors.append(f"Numeric fidelity check failed: {str(e)}")

        # ========== POST-GENERATION VERIFICATION (ADAPTIVE) ==========
        # May run even if enable_claims was False; uses existing results if available.
        try:
            # Allow env defaults if parameters not explicitly set
            if adaptive_time_budget_sec is None:
                try:
                    import os
                    adaptive_time_budget_sec = float(os.getenv("RAG_ADAPTIVE_TIME_BUDGET_SEC", "0")) or None
                except Exception:
                    adaptive_time_budget_sec = None
            if enable_post_verification and result.generated_answer and PostGenerationVerifier:
                verifier = PostGenerationVerifier(
                    max_retries=adaptive_max_retries,
                    unsupported_threshold=adaptive_unsupported_threshold,
                    max_claims=adaptive_max_claims,
                    time_budget_sec=adaptive_time_budget_sec,
                    use_advanced_rewrites=adaptive_advanced_rewrites,
                )
                vres = await verifier.verify_and_maybe_fix(
                    query=query,
                    answer=result.generated_answer,
                    base_documents=result.documents or [],
                    media_db_path=media_db_path,
                    notes_db_path=notes_db_path,
                    character_db_path=character_db_path,
                    user_id=user_id,
                    generation_model=generation_model,
                    existing_claims=claims_payload,
                    existing_summary=factuality_payload,
                    search_mode=search_mode,
                    hybrid_alpha=hybrid_alpha,
                    top_k=top_k,
                )
                # Attach verification metadata
                result.metadata.setdefault("post_verification", {})
                result.metadata["post_verification"].update({
                    "unsupported_ratio": vres.unsupported_ratio,
                    "total_claims": vres.total_claims,
                    "unsupported_count": vres.unsupported_count,
                    "fixed": vres.fixed,
                    "reason": vres.reason,
                })
                # Gauge for NLI unsupported ratio
                try:
                    from tldw_Server_API.app.core.Metrics.metrics_manager import set_gauge
                    set_gauge("rag_nli_unsupported_ratio", float(vres.unsupported_ratio or 0.0), labels={"strategy": "standard"})
                except Exception:
                    pass
                # Optionally override final answer on successful repair
                if vres.fixed and vres.new_answer:
                    result.generated_answer = vres.new_answer
                # Behavior toggles on low confidence and not fixed
                low_confidence = (vres.unsupported_ratio > adaptive_unsupported_threshold) and (not vres.fixed)
                if low_confidence:
                    _apply_generation_gate(
                        "nli_low_confidence",
                        unsupported_ratio=vres.unsupported_ratio,
                        threshold=adaptive_unsupported_threshold,
                    )
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                        increment_counter("rag_nli_low_confidence_total", 1)
                    except Exception:
                        pass
                    if low_confidence_behavior == "ask":
                        note = "\n\n[Note] Evidence is insufficient; please clarify or provide more context."
                        result.generated_answer = (result.generated_answer or "") + note
                    elif low_confidence_behavior == "decline":
                        result.generated_answer = "Insufficient evidence found to answer confidently."
                # Sample payload exemplar on failure for debugging (redacted)
                try:
                    if low_confidence:
                        from .payload_exemplars import maybe_record_exemplar
                        maybe_record_exemplar(query=query, documents=result.documents or [], answer=result.generated_answer or "", reason="post_verification_low_confidence", user_id=user_id)
                except Exception:
                    pass

                # Optional: bounded full pipeline rerun to seek a better answer
                try:
                    if low_confidence and adaptive_rerun_on_low_confidence and not _adaptive_rerun:
                        rerun_start = time.time()
                        # Prefer to broaden recall on rerun
                        rerun_expand = True if not expand_query else expand_query
                        # Build rerun with post-verification off and a guard to prevent nesting
                        new_result = await unified_rag_pipeline(
                            query=query,
                            sources=sources,
                            media_db_path=media_db_path,
                            notes_db_path=notes_db_path,
                            character_db_path=character_db_path,
                            # Prefer adapters to avoid raw SQL in prod
                            media_db=media_db,
                            chacha_db=chacha_db,
                            # Use same retrieval/reranking settings but broaden expansion
                            search_mode=search_mode,
                            fts_level=fts_level,
                            hybrid_alpha=hybrid_alpha,
                            top_k=top_k,
                            min_score=min_score,
                            expand_query=rerun_expand,
                            expansion_strategies=expansion_strategies,
                            spell_check=spell_check,
                            enable_cache=False if adaptive_rerun_bypass_cache else enable_cache,
                            cache_threshold=cache_threshold,
                            adaptive_cache=adaptive_cache,
                            keyword_filter=keyword_filter,
                            include_media_ids=include_media_ids,
                            include_note_ids=include_note_ids,
                            enable_security_filter=enable_security_filter,
                            detect_pii=detect_pii,
                            redact_pii=redact_pii,
                            sensitivity_level=sensitivity_level,
                            content_filter=content_filter,
                            enable_table_processing=enable_table_processing,
                            table_method=table_method,
                            enable_vlm_late_chunking=enable_vlm_late_chunking,
                            vlm_backend=vlm_backend,
                            vlm_detect_tables_only=vlm_detect_tables_only,
                            vlm_max_pages=vlm_max_pages,
                            vlm_late_chunk_top_k_docs=vlm_late_chunk_top_k_docs,
                            enable_enhanced_chunking=enable_enhanced_chunking,
                            chunk_type_filter=chunk_type_filter,
                            enable_parent_expansion=enable_parent_expansion,
                            parent_context_size=parent_context_size,
                            include_sibling_chunks=include_sibling_chunks,
                            sibling_window=sibling_window,
                            include_parent_document=include_parent_document,
                            parent_max_tokens=parent_max_tokens,
                            enable_reranking=enable_reranking,
                            reranking_strategy=reranking_strategy,
                            rerank_top_k=rerank_top_k,
                            reranking_model=reranking_model,
                            rerank_min_relevance_prob=rerank_min_relevance_prob,
                            rerank_sentinel_margin=rerank_sentinel_margin,
                            enable_citations=enable_citations,
                            citation_style=citation_style,
                            include_page_numbers=include_page_numbers,
                            enable_chunk_citations=enable_chunk_citations,
                            enable_generation=bool(adaptive_rerun_include_generation),
                            generation_model=generation_model,
                            generation_prompt=generation_prompt,
                            max_generation_tokens=max_generation_tokens,
                            # Disable post-verification in rerun to avoid loops
                            enable_post_verification=False,
                            # Guard: mark this as an adaptive rerun
                            _adaptive_rerun=True,
                            # Preserve guardrails & claims defaults
                            enable_injection_filter=enable_injection_filter,
                            injection_filter_strength=injection_filter_strength,
                            require_hard_citations=require_hard_citations,
                            enable_numeric_fidelity=enable_numeric_fidelity,
                            numeric_fidelity_behavior=numeric_fidelity_behavior,
                            enable_claims=False,  # skip claims during rerun to save time
                            index_namespace=index_namespace,
                            user_id=user_id,
                            session_id=session_id,
                            enable_monitoring=enable_monitoring,
                            enable_observability=enable_observability,
                            trace_id=trace_id,
                            enable_performance_analysis=enable_performance_analysis,
                            timeout_seconds=timeout_seconds,
                            highlight_results=highlight_results,
                            highlight_query_terms=highlight_query_terms,
                            track_cost=track_cost,
                            debug_mode=debug_mode,
                        )
                        # Quick verify the new answer without repairs to compare factuality
                        new_ratio = None
                        if PostGenerationVerifier and (new_result.generated_answer or "").strip():
                            v2 = await PostGenerationVerifier(max_retries=0, max_claims=min(10, adaptive_max_claims)).verify_and_maybe_fix(
                                query=query,
                                answer=new_result.generated_answer,
                                base_documents=(new_result.documents[:int(adaptive_rerun_doc_budget)] if (adaptive_rerun_doc_budget and isinstance(adaptive_rerun_doc_budget, int)) else (new_result.documents or [])),
                                media_db_path=media_db_path,
                                notes_db_path=notes_db_path,
                                character_db_path=character_db_path,
                                user_id=user_id,
                                generation_model=generation_model,
                                search_mode=search_mode,
                                hybrid_alpha=hybrid_alpha,
                                top_k=top_k,
                            )
                            new_ratio = v2.unsupported_ratio
                        # Adoption decision with guardrails regression checks
                        adopt = (new_ratio is not None and new_ratio < vres.unsupported_ratio)
                        try:
                            # Numeric fidelity regression check
                            old_nf_missing = None
                            new_nf_missing = None
                            if check_numeric_fidelity and (result.generated_answer or "").strip():
                                old_nf = check_numeric_fidelity(result.generated_answer, result.documents or [])
                                if old_nf:
                                    old_nf_missing = len(old_nf.missing)
                            else:
                                # fallback to existing metadata if available
                                try:
                                    old_nf_missing = len((result.metadata.get("numeric_fidelity") or {}).get("missing", [])) if isinstance(result.metadata, dict) else None
                                except Exception:
                                    old_nf_missing = None
                            if check_numeric_fidelity and (new_result.generated_answer or "").strip():
                                new_nf = check_numeric_fidelity(new_result.generated_answer, new_result.documents or [])
                                if new_nf:
                                    new_nf_missing = len(new_nf.missing)
                            # Hard citation coverage regression check
                            old_cov = None
                            new_cov = None
                            try:
                                old_cov = float((result.metadata.get("hard_citations") or {}).get("coverage")) if isinstance(result.metadata, dict) else None
                            except Exception:
                                old_cov = None
                            if build_hard_citations and (new_result.generated_answer or "").strip():
                                hc2 = build_hard_citations(new_result.generated_answer, new_result.documents or [], claims_payload=None)
                                if isinstance(hc2, dict):
                                    new_cov = float(hc2.get("coverage") or 0.0)

                            # If both NF counts present, block adoption on regression
                            if adopt and (old_nf_missing is not None and new_nf_missing is not None):
                                if new_nf_missing > old_nf_missing:
                                    adopt = False
                            # If both coverage present, block adoption on regression
                            if adopt and (old_cov is not None and new_cov is not None):
                                if new_cov < old_cov:
                                    adopt = False
                        except Exception:
                            # On checker failure, keep original adoption decision
                            pass
                        dur = time.time() - rerun_start
                        result.metadata.setdefault("adaptive_rerun", {})
                        result.metadata["adaptive_rerun"].update({
                            "performed": True,
                            "duration": round(dur, 6),
                            "old_ratio": vres.unsupported_ratio,
                            "new_ratio": new_ratio,
                            "adopted": bool(adopt),
                            "bypass_cache": bool(adaptive_rerun_bypass_cache),
                            "old_nf_missing": old_nf_missing if 'old_nf_missing' in locals() else None,
                            "new_nf_missing": new_nf_missing if 'new_nf_missing' in locals() else None,
                            "old_hard_citation_coverage": old_cov if 'old_cov' in locals() else None,
                            "new_hard_citation_coverage": new_cov if 'new_cov' in locals() else None,
                        })
                        # Metrics for rerun
                        try:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, observe_histogram
                            increment_counter("rag_adaptive_rerun_performed_total", 1)
                            if adopt:
                                increment_counter("rag_adaptive_rerun_adopted_total", 1)
                            observe_histogram("rag_adaptive_rerun_duration_seconds", dur, labels={"adopted": "true" if adopt else "false"})
                        except Exception:
                            pass
                        # Budget check and metric
                        try:
                            if adaptive_rerun_time_budget_sec is not None and dur > float(adaptive_rerun_time_budget_sec):
                                from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
                                increment_counter("rag_phase_budget_exhausted_total", 1, labels={"phase": "adaptive_rerun"})
                                result.metadata["adaptive_rerun"]["budget_exhausted"] = True
                        except Exception:
                            pass
                        if adopt:
                            # Replace documents, citations and answer with rerun outputs
                            result.documents = new_result.documents
                            result.citations = new_result.citations
                            result.metadata.update({k: v for k, v in (new_result.metadata or {}).items()})
                            result.generated_answer = new_result.generated_answer
                except Exception as _er:
                    result.errors.append(f"Adaptive rerun failed: {str(_er)}")
                    logger.debug(f"Adaptive rerun error: {_er}")
        except Exception as e:
            # Non-fatal: log and continue
            result.errors.append(f"Post-verification failed: {str(e)}")
            logger.warning(f"Post-verification error: {e}")

        # ========== USER FEEDBACK ==========
        if collect_feedback:
            feedback_start = time.time()
            try:
                if UnifiedFeedbackSystem:
                    collector = UnifiedFeedbackSystem()
                    result.feedback_id = str(uuid.uuid4())
                    result.metadata["feedback_enabled"] = True

                    # Apply feedback boost if requested
                    if apply_feedback_boost and result.documents:
                        try:
                            if UserPersonalizationStore:
                                store = UserPersonalizationStore(feedback_user_id or user_id)
                                result.documents = store.boost_documents(result.documents, corpus=index_namespace)
                        except Exception:
                            pass
                    # Record anonymized search analytics
                    try:
                        await collector.record_search(
                            query=query,
                            results_count=len(result.documents or []),
                            cache_hit=bool(result.cache_hit),
                            latency_ms=(time.time() - start_time) * 1000.0,
                        )
                    except Exception:
                        pass

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
                        cache_payload = {
                            "documents": list(result.documents),
                            "answer": result.generated_answer,
                            "cached": True,
                        }
                        if asyncio.iscoroutinefunction(set_fn):
                            await set_fn(query, cache_payload, ttl=cache_ttl)
                        else:
                            set_fn(query, cache_payload, ttl=cache_ttl)
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
            try:
                _qh = hashlib.md5((query or "").encode("utf-8")).hexdigest()[:8]
                logger.debug(f"Query hash={_qh} len={len(query or '')}")
            except Exception:
                logger.debug("Received query (hash unavailable)")
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

    # Lightweight normalizer to dedupe/cluster identical queries
    def _normalize(q: str) -> str:
        try:
            q = (q or "").strip().lower()
            out = []
            prev_space = False
            for ch in q:
                if ch.isalnum():
                    out.append(ch)
                    prev_space = False
                else:
                    if not prev_space:
                        out.append(" ")
                        prev_space = True
            return "".join(out).strip()
        except Exception:
            return q or ""

    # Group indices by normalized query (identicals)
    normalized_map: Dict[str, List[int]] = {}
    for idx, q in enumerate(queries or []):
        normalized_map.setdefault(_normalize(q), []).append(idx)

    # Deduped representatives (first occurrence of each normalized key)
    unique_keys = list(normalized_map.keys())
    rep_texts = [queries[normalized_map[k][0]] for k in unique_keys]

    # Near-duplicate clustering via cosine similarity of embeddings (best-effort)
    clusters: Dict[int, List[int]] = {}
    try:
        from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
            create_embeddings_batch,
            get_embedding_config,
        )
        # Get embeddings for representative texts
        cfg = get_embedding_config()
        vectors = await asyncio.get_event_loop().run_in_executor(
            None,
            create_embeddings_batch,
            rep_texts,
            cfg,
            None,
        )
        # Normalize vectors to unit length for cosine
        def _norm(v):
            try:
                import math
                if hasattr(v, 'tolist'):
                    v = v.tolist()
                s = math.sqrt(sum((float(x) or 0.0) ** 2 for x in v))
                if s > 0:
                    return [float(x) / s for x in v]
            except Exception:
                pass
            return v
        vecs = [_norm(v) for v in (vectors or [])]
        # Cosine similarity
        def _cos(a, b):
            try:
                return float(sum((ai * bi) for ai, bi in zip(a, b)))
            except Exception:
                return 0.0
        # Threshold from env or default 0.9
        import os as _os
        try:
            thr = float(_os.getenv('RAG_BATCH_NEAR_DUP_THRESHOLD', '0.9'))
        except Exception:
            thr = 0.9
        used = set()
        for i, vi in enumerate(vecs):
            if i in used:
                continue
            clusters[i] = [i]
            used.add(i)
            for j in range(i + 1, len(vecs)):
                if j in used:
                    continue
                vj = vecs[j]
                if not isinstance(vi, list) or not isinstance(vj, list):
                    continue
                if _cos(vi, vj) >= thr:
                    clusters[i].append(j)
                    used.add(j)
    except Exception:
        # Fallback: each unique becomes its own cluster
        clusters = {i: [i] for i in range(len(unique_keys))}

    # Map cluster head index -> representative query text
    heads = list(clusters.keys())
    head_queries = [rep_texts[h] for h in heads]

    async def process_with_semaphore(query: str) -> UnifiedSearchResult:
        async with semaphore:
            return await unified_rag_pipeline(query=query, **kwargs)

    # Run heads only
    tasks = [process_with_semaphore(q) for q in head_queries]
    head_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build final results in original order, reusing unique results
    final_results: List[UnifiedSearchResult] = [None] * len(queries)  # type: ignore
    reuse_count = 0
    # Build mapping from unique key index -> head result
    # unique_keys[i] corresponds to rep_texts[i]
    # Find which head each i belongs to
    head_for: Dict[int, int] = {}
    for h, members in clusters.items():
        for m in members:
            head_for[m] = h
    # Stitch results
    for i_uq, key in enumerate(unique_keys):
        # Find the head index for this unique
        h = head_for.get(i_uq, i_uq)
        ures = head_results[heads.index(h)] if h in heads else head_results[0]
        indices = normalized_map.get(key, [])
        for pos, i in enumerate(indices):
            if isinstance(ures, Exception):
                final_results[i] = UnifiedSearchResult(documents=[], query=queries[i], errors=[str(ures)])
            else:
                reuse_count += 1 if pos > 0 else 0
                # Copy minimal fields for non-heads to preserve original query text
                final_results[i] = (
                    ures if pos == 0 and queries[i] == rep_texts[i_uq]
                    else UnifiedSearchResult(
                        documents=ures.documents,
                        query=queries[i],
                        expanded_queries=ures.expanded_queries,
                        metadata=ures.metadata,
                        timings=ures.timings,
                        citations=ures.citations,
                        feedback_id=ures.feedback_id,
                        generated_answer=ures.generated_answer,
                        cache_hit=ures.cache_hit,
                        errors=ures.errors,
                        security_report=ures.security_report,
                        total_time=ures.total_time,
                    )
                )

    # Metrics: record reuse count
    try:
        if reuse_count > 0:
            from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
            increment_counter("rag_batch_query_reuse_total", reuse_count)
    except Exception:
        pass

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
