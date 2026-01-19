"""
Unified RAG API Endpoint

This is the new, simplified RAG API that uses the unified pipeline.
All features are accessible through explicit parameters.
"""

import time
import hashlib
import inspect
from typing import Optional, Dict, Any, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Request, Response
from loguru import logger
from fastapi.responses import StreamingResponse
import asyncio
import json
import types

# Dependencies
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    rbac_rate_limit,
    require_permissions,
    require_token_scope,
    get_auth_principal,
)
from tldw_Server_API.app.api.v1.API_Deps.billing_deps import require_within_limit
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_READ

# Unified Pipeline
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
    unified_rag_pipeline,
    unified_batch_pipeline,
    simple_search,
    advanced_search,
    UnifiedSearchResult
)
from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
    agentic_rag_pipeline,
    AgenticConfig,
)
from tldw_Server_API.app.core.RAG.rag_service.generation import generate_streaming_response
from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document

# Schemas
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import (
    UnifiedRAGRequest,
    UnifiedRAGResponse,
    UnifiedBatchRequest,
    UnifiedBatchResponse,
    ImplicitFeedbackEvent,
)


def _build_unified_pipeline_kwargs(
    request: UnifiedRAGRequest,
    db_paths: Dict[str, Optional[str]],
    media_db: MediaDatabase,
    chacha_db: CharactersRAGDB,
    current_user: Optional[User],
) -> Dict[str, Any]:
    payload = model_dump_compat(request)
    payload["media_db_path"] = db_paths.get("media_db_path")
    payload["notes_db_path"] = db_paths.get("notes_db_path")
    payload["character_db_path"] = db_paths.get("character_db_path")
    payload["kanban_db_path"] = db_paths.get("kanban_db_path")
    payload["media_db"] = media_db
    payload["chacha_db"] = chacha_db
    payload["index_namespace"] = request.index_namespace or request.corpus
    payload["feedback_user_id"] = payload.get("feedback_user_id") or (
        current_user.username if current_user else None
    )
    payload["user_id"] = current_user.username if current_user else payload.get("user_id")
    allowed = set(inspect.signature(unified_rag_pipeline).parameters.keys())
    return {k: v for k, v in payload.items() if k in allowed}


def _resolve_kanban_db_path(current_user: Optional[User], request_user_id: Optional[str] = None) -> Optional[str]:
    """Resolve the Kanban DB path for the active user context."""
    user_id: Optional[Any] = None
    try:
        if current_user is not None and getattr(current_user, "id", None) is not None:
            user_id = current_user.id
        elif request_user_id:
            user_id = request_user_id
    except Exception:
        logger.debug("Failed to resolve user_id for kanban DB path", exc_info=True)
        user_id = request_user_id
    if user_id is None:
        try:
            user_id = DatabasePaths.get_single_user_id()
        except Exception:
            logger.debug("Failed to resolve single-user ID for kanban DB path", exc_info=True)
            return None
    try:
        return str(DatabasePaths.get_kanban_db_path(user_id))
    except Exception:
        logger.debug("Failed to resolve kanban DB path", exc_info=True)
        return None


def _normalize_documents_for_generation(docs: List[Any]) -> List[Document]:
    normalized: List[Document] = []
    for doc in docs or []:
        if isinstance(doc, Document):
            normalized.append(doc)
            continue
        if isinstance(doc, dict):
            metadata = doc.get("metadata") or {}
            source_val = metadata.get("source")
            source = DataSource.MEDIA_DB
            if source_val is not None:
                try:
                    source = DataSource(str(source_val))
                except Exception:
                    source = DataSource.MEDIA_DB
            normalized.append(
                Document(
                    id=str(doc.get("id")),
                    content=str(doc.get("content") or ""),
                    metadata=metadata if isinstance(metadata, dict) else {},
                    source=source,
                    score=float(doc.get("score") or 0.0),
                )
            )
    return normalized
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from tldw_Server_API.app.core.RAG.rag_service.analytics_system import UnifiedFeedbackSystem
from tldw_Server_API.app.core.Billing.enforcement import LimitCategory

router = APIRouter(prefix="/api/v1/rag", tags=["rag-unified"])

# Use central limiter instance for consistency across the app

async def _log_rag_queries_for_org(
    request_raw: Request,
    current_user: User,
    units: int = 1,
) -> None:
    """
    Best-effort helper to record RAG query usage into the shared
    ResourceDailyLedger for the active organization.

    This function never raises; failures are logged at debug level only.
    """
    if units <= 0:
        return

    try:
        # Resolve org_id from request state if available.
        org_id: Optional[int] = None
        try:
            state = getattr(request_raw, "state", None)
            if state is not None:
                org_ids = getattr(state, "org_ids", None)
                if isinstance(org_ids, (list, tuple)) and org_ids:
                    org_id_candidate = org_ids[0]
                    try:
                        org_id = int(org_id_candidate)
                    except Exception:
                        org_id = None
        except Exception:
            org_id = None

        # Fallback: derive org_id from AuthNZ org memberships.
        if org_id is None and current_user and current_user.id_int is not None:
            try:
                from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
                from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

                pool = await get_db_pool()
                repo = AuthnzOrgsTeamsRepo(db_pool=pool)
                memberships = await repo.list_org_memberships_for_user(current_user.id_int)
                if memberships:
                    candidate = memberships[0].get("org_id")
                    if candidate is not None:
                        org_id = int(candidate)
            except Exception:
                org_id = None

        if org_id is None:
            return

        try:
            from datetime import datetime, timezone
            from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (
                LedgerEntry,
                ResourceDailyLedger,
            )

            ledger = ResourceDailyLedger()
            await ledger.initialize()

            now = datetime.now(timezone.utc)
            entry = LedgerEntry(  # type: ignore[call-arg]
                entity_scope="org",
                entity_value=str(org_id),
                category="rag_queries",
                units=int(units),
                op_id=f"rag:{org_id}:{uuid4()}",
                occurred_at=now,
            )
            await ledger.add(entry)
        except Exception:
            # Ledger write failures must never impact request flow.
            logger.debug("RAG query ledger write failed; continuing without usage record", exc_info=True)
    except Exception:
        # Guard against any unexpected failure paths.
        logger.debug("RAG query logging failed; continuing without usage record", exc_info=True)


def convert_result_to_response(result: UnifiedSearchResult) -> UnifiedRAGResponse:
    """Convert internal result to API response.

    Be robust to different document shapes:
    - dataclass-like objects with attributes (id, content, metadata, score)
    - wrapper objects with a `.document` attribute that is an object or dict
    - plain dictionaries (e.g., from caches or patched test doubles)
    """

    def _extract_field(obj, key, default=None):
        """Safely extract a field from obj supporting attr, nested .document, or dict."""
        # Direct attribute
        if hasattr(obj, key):
            try:
                return getattr(obj, key)
            except Exception:
                pass
        # Nested `.document` attribute that may itself be an object
        if hasattr(obj, 'document'):
            doc_obj = getattr(obj, 'document')
            if isinstance(doc_obj, dict):
                if key in doc_obj:
                    return doc_obj.get(key, default)
            else:
                if hasattr(doc_obj, key):
                    try:
                        return getattr(doc_obj, key)
                    except Exception:
                        pass
        # Dict access (obj may be a dict)
        if isinstance(obj, dict):
            # Direct
            if key in obj:
                return obj.get(key, default)
            # Nested under 'document'
            doc_dict = obj.get('document') if isinstance(obj.get('document'), dict) else None
            if doc_dict and key in doc_dict:
                return doc_dict.get(key, default)
        return default

    documents = []
    for doc in (result.documents or []):
        doc_id = _extract_field(doc, 'id')
        content = _extract_field(doc, 'content')
        metadata = _extract_field(doc, 'metadata', {}) or {}
        score = _extract_field(doc, 'score', 0.0)

        # Ensure types are JSON-serializable
        if not isinstance(metadata, dict):
            try:
                metadata = dict(metadata)  # best effort
            except Exception:
                metadata = {"value": str(metadata)}

        documents.append({
            "id": doc_id if doc_id is not None else str(_extract_field(doc, 'chunk_id', 'unknown')),
            "content": content if isinstance(content, str) else (str(content) if content is not None else ""),
            "metadata": metadata,
            "score": float(score) if isinstance(score, (int, float)) else 0.0,
        })

    return UnifiedRAGResponse(
        documents=documents,
        query=result.query,
        expanded_queries=result.expanded_queries,
        metadata=result.metadata,
        timings=result.timings,
        citations=result.citations,
        academic_citations=(result.metadata or {}).get("academic_citations", []),
        chunk_citations=(result.metadata or {}).get("chunk_citations", []),
        feedback_id=result.feedback_id,
        generated_answer=result.generated_answer,
        cache_hit=result.cache_hit,
        errors=result.errors,
        security_report=result.security_report,
        total_time=result.total_time,
        claims=getattr(result, 'claims', None),
        factuality=getattr(result, 'factuality', None),
    )


# =============== Ablation helper ===============
try:
    from pydantic import BaseModel, Field
except Exception:
    BaseModel = object  # type: ignore
    def Field(*a, **k):  # type: ignore
        return None


class AblationRequest(BaseModel):  # type: ignore[misc]
    query: str = Field(..., description="Query to ablate")
    top_k: int = Field(10, ge=1, le=50, description="Retrieval top_k")
    search_mode: str = Field("hybrid", description="fts|vector|hybrid")
    with_answer: bool = Field(False, description="Generate answer in each condition")
    agentic_top_k_docs: int = Field(3, ge=1, le=20)
    agentic_window_chars: int = Field(1200, ge=200, le=20000)
    agentic_max_tokens_read: int = Field(6000, ge=500, le=20000)
    reranking_strategy: str = Field("flashrank", description="flashrank|cross_encoder|hybrid|llama_cpp|none")


@router.post(
    "/ablate",
    summary="Run RAG ablations (baseline, +rerank, +agentic, +agentic strict)",
    description="Compare retrieval/generation across baseline vs reranked vs agentic vs agentic(stricter extractive).",
    dependencies=[Depends(check_rate_limit)]
)
async def rag_ablate(
    request: AblationRequest,
    current_user: User = Depends(get_request_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    kanban_db_path = _resolve_kanban_db_path(current_user)
    db_paths = {
        "media_db_path": media_db.db_path if media_db else None,
        "notes_db_path": chacha_db.db_path if chacha_db else None,
        "character_db_path": chacha_db.db_path if chacha_db else None,
        "kanban_db_path": kanban_db_path,
    }

    common = dict(
        query=request.query,
        sources=["media_db"],
        media_db_path=db_paths["media_db_path"],
        notes_db_path=db_paths["notes_db_path"],
        character_db_path=db_paths["character_db_path"],
        kanban_db_path=db_paths["kanban_db_path"],
        media_db=media_db,
        chacha_db=chacha_db,
        search_mode=request.search_mode,
        top_k=request.top_k,
        min_score=0.0,
        enable_generation=bool(request.with_answer),
        generation_model=None,
        max_generation_tokens=300,
    )

    runs = []

    # 1) Baseline (no reranking)
    r1 = await unified_rag_pipeline(
        **common,
        enable_reranking=False,
    )
    runs.append({
        "label": "baseline",
        "result": convert_result_to_response(r1)
    })

    # 2) +rerank
    r2 = await unified_rag_pipeline(
        **common,
        enable_reranking=True,
        reranking_strategy=request.reranking_strategy,
    )
    runs.append({
        "label": "+rerank",
        "result": convert_result_to_response(r2)
    })

    # 3) agentic
    a_cfg = AgenticConfig(
        top_k_docs=request.agentic_top_k_docs,
        window_chars=request.agentic_window_chars,
        max_tokens_read=request.agentic_max_tokens_read,
        max_tool_calls=6,
        extractive_only=True,
        quote_spans=True,
        enable_tools=False,
        debug_trace=False,
    )
    r3 = await agentic_rag_pipeline(
        **common,
        agentic=a_cfg,
        enable_citations=False,
    )
    runs.append({
        "label": "agentic",
        "result": convert_result_to_response(r3)
    })

    # 4) agentic (strict): tools on, extractive only, small budget
    a_cfg_strict = AgenticConfig(
        top_k_docs=max(1, request.agentic_top_k_docs),
        window_chars=max(600, int(request.agentic_window_chars / 2)),
        max_tokens_read=max(1000, int(request.agentic_max_tokens_read / 2)),
        max_tool_calls=4,
        extractive_only=True,
        quote_spans=True,
        enable_tools=True,
        time_budget_sec=5.0,
        debug_trace=False,
    )
    r4 = await agentic_rag_pipeline(
        **common,
        agentic=a_cfg_strict,
        enable_citations=False,
    )
    runs.append({
        "label": "agentic_strict",
        "result": convert_result_to_response(r4)
    })

    # Compact output for quick comparison
    out = []
    for item in runs:
        res = item["result"]
        first = (res.documents[0] if res.documents else None)
        out.append({
            "label": item["label"],
            "total_time": res.total_time,
            "cache_hit": res.cache_hit,
            "doc_count": len(res.documents or []),
            "first_doc_id": (first.get("id") if isinstance(first, dict) else getattr(first, 'id', None)) if first else None,
        })

    return {"summary": out, "runs": runs}


@router.get(
    "/capabilities",
    summary="Capabilities",
    description="List RAG pipeline features and defaults available to the current user"
)
async def get_capabilities(request: Request):
    """Return supported features, defaults and configuration limits for the unified RAG pipeline.

    This endpoint is informational and does not require database access. It reflects
    the capabilities compiled into the service and basic configuration toggles.
    """
    from tldw_Server_API.app.core.config import RAG_SERVICE_CONFIG
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()

    # High-level features supported by the pipeline
    import os as _os
    # Resolve environment-defaults for VLM
    vlm_defaults = {
        "VLM_TABLE_MODEL_NAME": _os.getenv("VLM_TABLE_MODEL_NAME", "microsoft/table-transformer-detection"),
        "VLM_TABLE_REVISION": _os.getenv("VLM_TABLE_REVISION", None),
        "VLM_TABLE_THRESHOLD": _os.getenv("VLM_TABLE_THRESHOLD", "0.9"),
    }

    features = {
        "agentic_chunking": {
            "supported": True,
            "strategies": ["standard", "agentic"],
            "parameters": [
                "strategy",
                "agentic_top_k_docs",
                "agentic_window_chars",
                "agentic_max_tokens_read",
                "agentic_max_tool_calls",
                "agentic_enable_tools",
                "agentic_use_llm_planner",
                "agentic_time_budget_sec",
                "agentic_cache_ttl_sec",
                "agentic_enable_query_decomposition",
                "agentic_subgoal_max",
                "agentic_enable_semantic_within",
                "agentic_enable_section_index",
                "agentic_prefer_structural_anchors",
                "agentic_enable_table_support",
                "agentic_enable_vlm_late_chunking",
                "agentic_vlm_backend",
                "agentic_vlm_detect_tables_only",
                "agentic_vlm_max_pages",
                "agentic_vlm_late_chunk_top_k_docs",
                "agentic_use_provider_embeddings_within",
                "agentic_provider_embedding_model_id",
                "agentic_extractive_only",
                "agentic_quote_spans",
                "agentic_debug_trace",
                "agentic_adaptive_budgets",
                "agentic_coverage_target",
                "agentic_min_corroborating_docs",
                "agentic_max_redundancy",
                "agentic_enable_metrics",
                "explain_only",
            ],
            "defaults": {
                "strategy": "standard",
                "agentic_top_k_docs": 3,
                "agentic_window_chars": 1200,
                "agentic_max_tokens_read": 6000,
                "agentic_max_tool_calls": 8,
                "agentic_enable_tools": False,
                "agentic_use_llm_planner": False,
                "agentic_cache_ttl_sec": 600,
                "agentic_enable_query_decomposition": False,
                "agentic_subgoal_max": 3,
                "agentic_enable_semantic_within": True,
                "agentic_enable_section_index": True,
                "agentic_prefer_structural_anchors": True,
                "agentic_enable_table_support": True,
                "agentic_enable_vlm_late_chunking": False,
                "agentic_vlm_backend": None,
                "agentic_vlm_detect_tables_only": True,
                "agentic_vlm_max_pages": None,
                "agentic_vlm_late_chunk_top_k_docs": 2,
                "agentic_use_provider_embeddings_within": False,
                "agentic_provider_embedding_model_id": None,
                "agentic_adaptive_budgets": True,
                "agentic_coverage_target": 0.8,
                "agentic_min_corroborating_docs": 2,
                "agentic_max_redundancy": 0.9,
                "agentic_enable_metrics": True,
            },
        },
        "query_expansion": {
            "supported": True,
            "methods": ["acronym", "synonym", "domain", "entity"],
        },
        "claims": {
            "supported": True,
            "extractors": ["aps", "claimify", "auto"],
            "verifiers": ["nli", "llm", "hybrid"],
            "defaults": {
                "top_k": 5,
                "confidence_threshold": 0.7,
                "max": 25
            },
            "nli": {
                "env": ["RAG_NLI_MODEL", "RAG_NLI_MODEL_PATH"],
                "override_param": "nli_model"
            }
        },
        "semantic_cache": {
            "supported": True,
            "adaptive_thresholds": True,
            "config": RAG_SERVICE_CONFIG.get("cache", {})
        },
        "sources": {
            "supported": True,
            "datastores": ["media_db", "notes", "characters", "chats"],
        },
        "security_filtering": {
            "supported": True,
            "pii_detection": True
        },
        "citation_generation": {
            "supported": True,
            "styles": ["apa", "mla", "chicago", "harvard", "ieee"],
            "include_page_numbers": True
        },
        "guardrails": {
            "supported": True,
            "require_hard_citations": True,
            "notes": "When require_hard_citations=true and coverage<1.0, agentic path abstains with a succinct message"
        },
        "answer_generation": {
            "supported": True,
            "configurable_model": True
        },
        "reranking": {
            "supported": True,
            "strategies": ["flashrank", "cross_encoder", "hybrid", "llama_cpp"],
            "models": [
                "flashrank",
                "cross-encoder (e.g., BAAI/bge-reranker-v2-m3, Jina reranker)",
                "GGUF via llama.cpp (e.g., Qwen3-Embedding-0.6B_f16.gguf, BGE/Jina GGUF)"
            ]
        },
        "table_processing": {
            "supported": True,
            "methods": ["markdown", "html", "hybrid"]
        },
        "vlm_late_chunking": {
            "supported": True,
            "backends": ["docling", "hf_table_transformer"],
            "parameters": [
                "enable_vlm_late_chunking",
                "vlm_backend",
                "vlm_detect_tables_only",
                "vlm_max_pages",
                "vlm_late_chunk_top_k_docs"
            ],
            "env": [
                "VLM_TABLE_MODEL_NAME",
                "VLM_TABLE_REVISION",
                "VLM_TABLE_THRESHOLD"
            ],
            "defaults": vlm_defaults,
            "backends_endpoint": "/api/v1/rag/vlm/backends",
            "note": "Env defaults reflect current process environment; Table Transformer threshold is 0.9 by default."
        },
        "enhanced_chunking": {
            "supported": True,
            "parent_context": True,
            "sibling_context": True,
            "parameters": [
                "parent_context_size",
                "include_parent_document",
                "parent_max_tokens",
                "include_sibling_chunks",
                "sibling_window",
                "chunk_type_filter"
            ]
        },
        "feedback": {
            "supported": True,
            "apply_feedback_boost": True
        },
        "monitoring": {
            "supported": True,
            "observability": True,
            "trace_id": True
        },
        "analytics": {
            "supported": True
        },
        "batch_processing": {
            "supported": True,
            "concurrent": True,
            "defaults": {"max_concurrent": 5},
            "limits": {"max_concurrent_max": 20}
        },
        "resilience": {
            "supported": True,
            "retries": True,
            "circuit_breakers": True
        },
        "streaming": {
            "supported": True,
            "endpoint": "/api/v1/rag/search/stream",
            "media_type": "application/x-ndjson",
            "events": ["delta", "claims_overlay", "final_claims"]
        },
        "quick_wins": {
            "supported": True,
            "parameters": ["highlight_results", "highlight_query_terms", "track_cost", "debug_mode"]
        },
        "user_context": {
            "supported": True,
            "fields": ["user_id", "session_id"]
        },
        "webui": {
            "supported": True,
            "controls": [
                "strategy",
                "agentic_enable_tools",
                "agentic_max_tool_calls",
                "agentic_max_tokens_read",
                "agentic_adaptive_budgets",
                "agentic_time_budget_sec",
                "require_hard_citations",
                "enable_numeric_fidelity",
                "agentic_enable_query_decomposition",
                "agentic_enable_vlm_late_chunking"
            ],
            "explain_panel": True,
            "highlight_spans": True,
            "section_anchors": True
        }
    }

    # Search modes and configuration ranges
    search = {
        "modes": ["hybrid", "vector", "fts"],
        "hybrid": {
            "alpha_default": RAG_SERVICE_CONFIG.get("retriever", {}).get("hybrid_alpha", 0.5),
            "alpha_range": [0.0, 1.0],
            "normalize_scores": RAG_SERVICE_CONFIG.get("retriever", {}).get("hybrid_alpha", 0.5) is not None
        },
        "vector": {
            "top_k_default": RAG_SERVICE_CONFIG.get("retriever", {}).get("vector_top_k", 10),
            "top_k_max": 100
        },
        "fts": {
            "top_k_default": RAG_SERVICE_CONFIG.get("retriever", {}).get("fts_top_k", 10),
            "query_expansion": True,
            "fuzzy_matching": True
        }
    }

    defaults = {
        "retriever": RAG_SERVICE_CONFIG.get("retriever", {}),
        "processor": RAG_SERVICE_CONFIG.get("processor", {}),
        "cache": RAG_SERVICE_CONFIG.get("cache", {}),
        "batch_size": RAG_SERVICE_CONFIG.get("batch_size", 32),
        "num_workers": RAG_SERVICE_CONFIG.get("num_workers", 4),
        "min_score": 0.0,
        "use_connection_pool": True,
        "use_embedding_cache": True
    }

    limits = {
        "top_k_max": 100,
        "documents_per_db_max": 1000,
        "answer_tokens_max": 2048,
        "timeout_seconds_max": 60.0
    }

    auth = {
        "mode": settings.AUTH_MODE,
        "user_scoped": True
    }

    quick_start = {
        "agentic_search": {
            "endpoint": "/api/v1/rag/search",
            "method": "POST",
            "body": {
                "query": "Summarize key findings of ResNet",
                "strategy": "agentic",
                "search_mode": "hybrid",
                "top_k": 8,
                "enable_generation": False,
                "agentic_enable_tools": True,
                "agentic_max_tool_calls": 6
            }
        },
        "agentic_verify": {
            "endpoint": "/api/v1/rag/search",
            "method": "POST",
            "body": {
                "query": "How many experiments were run and what supported the conclusion?",
                "strategy": "agentic",
                "enable_generation": True,
                "require_hard_citations": True,
                "enable_numeric_fidelity": True,
                "numeric_fidelity_behavior": "continue"
            }
        },
        "agentic_explain": {
            "endpoint": "/api/v1/rag/search",
            "method": "POST",
            "body": {
                "query": "Explain residual connections and dropout",
                "strategy": "agentic",
                "enable_generation": False,
                "explain_only": True,
                "agentic_enable_tools": True,
                "agentic_enable_query_decomposition": True
            }
        },
        "agentic_multihop_vlm": {
            "endpoint": "/api/v1/rag/search",
            "method": "POST",
            "body": {
                "query": "Compare accuracy tables for ResNet vs EfficientNet across datasets",
                "strategy": "agentic",
                "search_mode": "hybrid",
                "top_k": 8,
                "enable_generation": False,
                "agentic_enable_tools": True,
                "agentic_enable_query_decomposition": True,
                "agentic_subgoal_max": 3,
                "agentic_enable_vlm_late_chunking": True,
                "agentic_vlm_backend": "hf_table_transformer",
                "agentic_vlm_detect_tables_only": True,
                "agentic_vlm_late_chunk_top_k_docs": 2
            }
        },
        "ablate": {
            "endpoint": "/api/v1/rag/ablate",
            "method": "POST",
            "body": {
                "query": "How does dropout prevent overfitting?",
                "top_k": 10,
                "search_mode": "hybrid",
                "with_answer": False,
                "reranking_strategy": "none"
            }
        }
    }

    return {
        "pipeline": "unified",
        "version": "1.0.0",
        "features": features,
        "search": search,
        "defaults": defaults,
        "limits": limits,
        "auth": auth,
        "quick_start": quick_start,
    }


@router.get(
    "/vlm/backends",
    summary="VLM Backends",
    description="List VLM (Vision-Language) backends and their availability",
    response_description="Backend availability map"
)
async def list_vlm_backends():
    """
    Report available VLM backends from the ingestion registry.

    Returns a mapping like { "hf_table_transformer": {"available": true}, "docling": {"available": false} }.
    """
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.VLM.registry import list_backends as _list
        backends = _list() or {}
    except Exception:
        backends = {}
    return {"backends": backends}


@router.post(
    "/search",
    response_model=UnifiedRAGResponse,
    summary="Unified RAG Search",
    description="""
    The unified RAG search endpoint with ALL features accessible via parameters.

    **Key Features:**
    - No configuration files needed
    - Every feature is a direct parameter
    - Mix and match any features
    - Transparent execution

    **Available Features:**
    - Query expansion (acronym, synonym, domain, entity)
    - Semantic caching with adaptive thresholds
    - Multi-database search (media, notes, characters, chats)
    - Security filtering and PII detection
    - Citation generation (APA, MLA, Chicago, Harvard)
    - Answer generation from context
    - Document reranking (FlashRank, Cross-Encoder, Hybrid)
    - Table processing and extraction
    - Enhanced chunking with parent context
    - User feedback collection
    - Performance monitoring and observability
    - Batch processing support
    - Resilience features (retries, circuit breakers)

    Simply set any feature parameter to enable it. All parameters are optional
    except the query itself.
    """,
    response_description="Search results with all requested features applied",
    dependencies=[
        Depends(check_rate_limit),
        Depends(rbac_rate_limit("rag.search")),
        Depends(require_permissions(MEDIA_READ)),
        Depends(require_token_scope("any", require_if_present=True, endpoint_id="rag.search", count_as="call")),
        Depends(require_within_limit(LimitCategory.RAG_QUERIES_DAY, 1)),
    ]
)
async def unified_search_endpoint(
    request_raw: Request,
    request: UnifiedRAGRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_request_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    """
    Unified RAG search with all features as parameters.

    This endpoint replaces the complex configuration-based approach with
    a simple, parameter-driven interface. Every feature in the RAG system
    is accessible by setting the appropriate parameter.
    """
    try:
        logger.info(f"Unified RAG search: query='{request.query}', user={current_user.username if current_user else 'anonymous'}")
        # Topic monitoring (non-blocking) for query text
        try:
            from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
            mon = get_topic_monitoring_service()
            uid = (current_user.username if current_user else request.user_id) or None
            team_ids = None
            org_ids = None
            try:
                if hasattr(request_raw, 'state'):
                    team_ids = getattr(request_raw.state, 'team_ids', None)
                    org_ids = getattr(request_raw.state, 'org_ids', None)
            except Exception:
                pass
            if request.query:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=request.query,
                    source="rag.search",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                    team_ids=team_ids,
                    org_ids=org_ids,
                )
        except Exception:
            pass

        # Set up database paths
        db_paths = {
            "media_db_path": media_db.db_path if media_db else None,
            # Notes are stored in ChaChaNotes DB by design; reuse its path for notes_db
            "notes_db_path": chacha_db.db_path if chacha_db else None,
            "character_db_path": chacha_db.db_path if chacha_db else None,
            "kanban_db_path": _resolve_kanban_db_path(current_user, request.user_id),
        }

        # Branch: agentic strategy builds a synthetic chunk at query time
        if getattr(request, 'strategy', 'standard') == 'agentic':
            agentic_cfg = AgenticConfig(
                top_k_docs=int(getattr(request, 'agentic_top_k_docs', 3) or 3),
                window_chars=int(getattr(request, 'agentic_window_chars', 1200) or 1200),
                max_tokens_read=int(getattr(request, 'agentic_max_tokens_read', 6000) or 6000),
                max_tool_calls=int(getattr(request, 'agentic_max_tool_calls', 8) or 8),
                extractive_only=bool(getattr(request, 'agentic_extractive_only', True)),
                quote_spans=bool(getattr(request, 'agentic_quote_spans', True)),
                enable_tools=bool(getattr(request, 'agentic_enable_tools', False)),
                use_llm_planner=bool(getattr(request, 'agentic_use_llm_planner', False)),
                time_budget_sec=(getattr(request, 'agentic_time_budget_sec', None)),
                cache_ttl_sec=int(getattr(request, 'agentic_cache_ttl_sec', 600) or 600),
                debug_trace=bool(getattr(request, 'agentic_debug_trace', False) or request.debug_mode),
                enable_query_decomposition=bool(getattr(request, 'agentic_enable_query_decomposition', False)),
                subgoal_max=int(getattr(request, 'agentic_subgoal_max', 3) or 3),
                enable_semantic_within=bool(getattr(request, 'agentic_enable_semantic_within', True)),
                enable_section_index=bool(getattr(request, 'agentic_enable_section_index', True)),
                prefer_structural_anchors=bool(getattr(request, 'agentic_prefer_structural_anchors', True)),
                enable_table_support=bool(getattr(request, 'agentic_enable_table_support', True)),
                agentic_enable_vlm_late_chunking=bool(getattr(request, 'agentic_enable_vlm_late_chunking', False)),
                agentic_vlm_backend=getattr(request, 'agentic_vlm_backend', None),
                agentic_vlm_detect_tables_only=bool(getattr(request, 'agentic_vlm_detect_tables_only', True)),
                agentic_vlm_max_pages=getattr(request, 'agentic_vlm_max_pages', None),
                agentic_vlm_late_chunk_top_k_docs=int(getattr(request, 'agentic_vlm_late_chunk_top_k_docs', 2) or 2),
                agentic_use_provider_embeddings_within=bool(getattr(request, 'agentic_use_provider_embeddings_within', False)),
                agentic_provider_embedding_model_id=getattr(request, 'agentic_provider_embedding_model_id', None),
                # new adaptive/metrics knobs
                adaptive_budgets=bool(getattr(request, 'agentic_adaptive_budgets', True)),
                coverage_target=float(getattr(request, 'agentic_coverage_target', 0.8) or 0.8),
                min_corroborating_docs=int(getattr(request, 'agentic_min_corroborating_docs', 2) or 2),
                max_redundancy=float(getattr(request, 'agentic_max_redundancy', 0.9) or 0.9),
                enable_metrics=bool(getattr(request, 'agentic_enable_metrics', True)),
            )

            try:
                result = await agentic_rag_pipeline(
                    query=request.query,
                    sources=request.sources,
                    media_db=media_db,
                    chacha_db=chacha_db,
                    media_db_path=db_paths.get("media_db_path"),
                    notes_db_path=db_paths.get("notes_db_path"),
                    character_db_path=db_paths.get("character_db_path"),
                    kanban_db_path=db_paths.get("kanban_db_path"),
                    search_mode=request.search_mode,
                    fts_level=request.fts_level,
                    hybrid_alpha=request.hybrid_alpha,
                    top_k=request.top_k,
                    min_score=request.min_score,
                    index_namespace=(request.index_namespace or request.corpus),
                    agentic=agentic_cfg,
                    enable_generation=request.enable_generation,
                    generation_model=request.generation_model,
                    generation_prompt=request.generation_prompt,
                    max_generation_tokens=request.max_generation_tokens,
                    enable_citations=request.enable_citations,
                    include_chunk_citations=request.enable_chunk_citations,
                    debug_mode=request.debug_mode,
                    # expose verification flags on agentic path
                    require_hard_citations=bool(getattr(request, 'require_hard_citations', False)),
                    enable_numeric_fidelity=bool(getattr(request, 'enable_numeric_fidelity', False)),
                    numeric_fidelity_behavior=str(getattr(request, 'numeric_fidelity_behavior', 'continue')),
                    enable_claims=bool(getattr(request, 'enable_claims', False)),
                    claim_verifier=str(getattr(request, 'claim_verifier', 'hybrid')),
                    claims_top_k=int(getattr(request, 'claims_top_k', 5) or 5),
                    claims_conf_threshold=float(getattr(request, 'claims_conf_threshold', 0.7) or 0.7),
                    claims_max=int(getattr(request, 'claims_max', 25) or 25),
                    nli_model=getattr(request, 'nli_model', None),
                    claims_concurrency=int(getattr(request, 'claims_concurrency', 8) or 8),
                    adaptive_unsupported_threshold=float(getattr(request, 'adaptive_unsupported_threshold', 0.15) or 0.15),
                    low_confidence_behavior=str(getattr(request, 'low_confidence_behavior', 'continue')),
                )
            except Exception as exc:
                logger.error("Agentic RAG pipeline failed: {}", exc, exc_info=True)
                fallback_doc = {
                    "id": f"agentic-error:{uuid4().hex[:8]}",
                    "content": "Agentic pipeline error fallback content.",
                    "metadata": {"strategy": "agentic", "error": str(exc)},
                    "score": 1.0,
                }
                result = UnifiedSearchResult(
                    documents=[fallback_doc],
                    query=request.query,
                    expanded_queries=[],
                    metadata={"strategy": "agentic", "error": str(exc)},
                    timings={},
                    citations=[],
                    feedback_id=None,
                    generated_answer="Agentic pipeline failed; fallback response returned.",
                    cache_hit=False,
                    errors=[str(exc)],
                    security_report=None,
                    total_time=0.0,
                )
        else:
            # Execute unified pipeline with all parameters from request
            kwargs = _build_unified_pipeline_kwargs(
                request=request,
                db_paths=db_paths,
                media_db=media_db,
                chacha_db=chacha_db,
                current_user=current_user,
            )
            result = await unified_rag_pipeline(**kwargs)

        # Convert to response format
        response = convert_result_to_response(result)

        # Best-effort RAG query usage logging for billing/analytics.
        await _log_rag_queries_for_org(request_raw, current_user, units=1)

        # Log performance if monitoring enabled
        if request.enable_monitoring:
            logger.info(f"Query completed in {result.total_time:.3f}s - Cache hit: {result.cache_hit}")
            if request.debug_mode:
                logger.debug(f"Timings: {result.timings}")
                logger.debug(f"Metadata: {result.metadata}")

        # Handle any errors that occurred
        if result.errors and request.debug_mode:
            logger.warning(f"Errors during processing: {result.errors}")

        return response

    except Exception as e:
        logger.error(f"Unified search error: {e}", exc_info=True)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed due to an internal error."
        )


@router.post(
    "/feedback/implicit",
    summary="Record implicit RAG feedback",
    description="Capture click/expand/copy signals from the WebUI for learning-to-rank and personalization.",
    dependencies=[Depends(check_rate_limit)]
)
async def rag_implicit_feedback(
    request: ImplicitFeedbackEvent,
    current_user: User = Depends(get_request_user),
):
    try:
        from tldw_Server_API.app.core.config import implicit_feedback_enabled
        if not implicit_feedback_enabled():
            return {"ok": True, "disabled": True}
        user_id = request.user_id or (current_user.username if current_user else None)
        collector = UnifiedFeedbackSystem()
        await collector.record_implicit_interaction(
            user_id=user_id,
            query=request.query,
            doc_id=request.doc_id,
            event_type=request.event_type,
            impression=request.impression_list or [],
            corpus=request.corpus,
            chunk_ids=request.chunk_ids or [],
            rank=request.rank,
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            message_id=request.message_id,
            dwell_ms=request.dwell_ms,
        )
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Failed to record implicit feedback: {e}")
        raise HTTPException(status_code=400, detail="Could not record feedback")


@router.post(
    "/batch",
    response_model=UnifiedBatchResponse,
    summary="Batch RAG Search",
    description="""
    Process multiple queries concurrently using the unified pipeline.

    All parameters from the single search endpoint are available and will
    be applied to all queries in the batch.
    """,
    response_description="Batch processing results",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_permissions(MEDIA_READ)),
    ]
)
async def unified_batch_endpoint(
    request_raw: Request,
    response: Response,
    request: UnifiedBatchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_request_user),
    principal: AuthPrincipal = Depends(get_auth_principal),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    """
    Batch processing endpoint for multiple queries.

    Processes multiple queries concurrently with the same parameters.
    """
    try:
        requested_units = len(request.queries or [])
        limit_checker = require_within_limit(LimitCategory.RAG_QUERIES_DAY, requested_units)
        org_header = request_raw.headers.get("X-TLDW-Org-Id")
        org_query = request_raw.query_params.get("org_id")
        try:
            org_header_id = int(org_header) if org_header is not None else None
        except (TypeError, ValueError):
            org_header_id = None
        try:
            org_query_id = int(org_query) if org_query is not None else None
        except (TypeError, ValueError):
            org_query_id = None

        await limit_checker(
            response=response,
            principal=principal,
            x_tldw_org_id=org_header_id,
            org_id=org_query_id,
        )

        logger.info(
            f"Batch RAG search: {requested_units} queries, "
            f"user={current_user.username if current_user else 'anonymous'}"
        )

        start_time = time.time()

        # Set up database paths
        db_paths = {
            "media_db_path": media_db.db_path if media_db else None,
            "notes_db_path": chacha_db.db_path if chacha_db else None,
            "character_db_path": chacha_db.db_path if chacha_db else None,
            "kanban_db_path": _resolve_kanban_db_path(current_user, request.user_id),
        }

        # Convert request to kwargs, excluding queries (Pydantic compat)
        kwargs = model_dump_compat(request, exclude={"queries", "max_concurrent"})
        kwargs.update(db_paths)
        kwargs["user_id"] = current_user.username if current_user else kwargs.get("user_id")

        # Process batch
        results = await unified_batch_pipeline(
            queries=request.queries,
            max_concurrent=request.max_concurrent,
            media_db=media_db,
            chacha_db=chacha_db,
            **kwargs
        )

        # Convert results
        responses = [convert_result_to_response(r) for r in results]

        # Count successes and failures
        successful = sum(1 for r in results if not r.errors)
        failed = len(results) - successful

        total_time = time.time() - start_time

        # Each query in the batch counts as one RAG query unit.
        await _log_rag_queries_for_org(request_raw, current_user, units=requested_units)

        return UnifiedBatchResponse(
            results=responses,
            total_queries=requested_units,
            successful=successful,
            failed=failed,
            total_time=total_time
        )

    except Exception as e:
        logger.error(f"Batch search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch search failed due to an internal error."
        )


@router.get(
    "/simple",
    summary="Simple Search",
    description="""
    Simplified search endpoint for basic use cases.

    Uses sensible defaults:
    - Caching enabled
    - Reranking enabled
    - No query expansion
    """,
    response_description="Search results",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_permissions(MEDIA_READ)),
        Depends(require_within_limit(LimitCategory.RAG_QUERIES_DAY, 1)),
    ]
)
async def simple_search_endpoint(
    request: Request,
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
    current_user: User = Depends(get_request_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user),
):
    """
    Simple search for basic use cases.
    """
    try:
        try:
            _qh = hashlib.md5((query or "").encode("utf-8")).hexdigest()[:8]
            logger.info(f"Simple search: query_hash={_qh} len={len(query or '')}")
        except Exception:
            logger.info("Simple search request received")
        # Topic monitoring (non-blocking)
        try:
            from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
            mon = get_topic_monitoring_service()
            uid = str(current_user.username)
            mon.schedule_evaluate_and_alert(
                user_id=uid,
                text=query,
                source="rag.simple_search",
                scope_type="user",
                scope_id=uid,
            )
        except Exception:
            pass

        # Use the simple_search wrapper
        effective_sources = sources or ["media_db", "notes", "characters"]
        documents = await simple_search(
            query,
            top_k,
            sources=effective_sources,
            media_db=media_db,
            chacha_db=chacha_db,
            media_db_path=(media_db.db_path if media_db else None),
            notes_db_path=(chacha_db.db_path if chacha_db else None),
            character_db_path=(chacha_db.db_path if chacha_db else None),
            kanban_db_path=_resolve_kanban_db_path(current_user),
            user_id=current_user.username if current_user else None,
        )

        # Best-effort RAG query logging (counts as a single query).
        await _log_rag_queries_for_org(request, current_user, units=1)

        normalized_docs = []
        for doc in documents:
            if isinstance(doc, dict):
                normalized_docs.append({
                    "id": doc.get("id"),
                    "content": doc.get("content"),
                    "metadata": doc.get("metadata") or {},
                    "score": doc.get("score", 0.0),
                })
            else:
                normalized_docs.append({
                    "id": getattr(doc, "id", None),
                    "content": getattr(doc, "content", None),
                    "metadata": getattr(doc, "metadata", {}) or {},
                    "score": getattr(doc, "score", 0.0),
                })

        return {
            "query": query,
            "documents": normalized_docs,
            "count": len(normalized_docs)
        }

    except Exception as e:
        logger.error(f"Simple search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed due to an internal error."
        )


@router.post(
    "/search/stream",
    summary="Unified RAG Streaming Search",
    description="Stream generated answer chunks with optional incremental claim overlay events (NDJSON)",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_permissions(MEDIA_READ)),
        Depends(require_within_limit(LimitCategory.RAG_QUERIES_DAY, 1)),
    ]
)
async def unified_search_stream_endpoint(
    request_raw: Request,
    request: UnifiedRAGRequest,
    current_user: User = Depends(get_request_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    if not request.enable_generation:
        raise HTTPException(status_code=400, detail="enable_generation must be true for streaming.")

    # Streaming search counts as a single RAG query.
    await _log_rag_queries_for_org(request_raw, current_user, units=1)

    async def event_stream():
        try:
            # Prepare retrieval like the unified pipeline (simplified)
            index_namespace = request.index_namespace or getattr(request, "corpus", None)
            db_paths = {}
            if media_db:
                db_paths["media_db"] = media_db.db_path
            if chacha_db:
                db_paths["notes_db"] = chacha_db.db_path
                db_paths["character_cards_db"] = chacha_db.db_path
            kanban_db_path = _resolve_kanban_db_path(current_user, request.user_id)
            if kanban_db_path:
                db_paths["kanban_db"] = kanban_db_path

            docs = []
            try:
                if db_paths:
                    kwargs = _build_unified_pipeline_kwargs(
                        request=request,
                        db_paths={
                            "media_db_path": media_db.db_path if media_db else None,
                            "notes_db_path": chacha_db.db_path if chacha_db else None,
                            "character_db_path": chacha_db.db_path if chacha_db else None,
                        },
                        media_db=media_db,
                        chacha_db=chacha_db,
                        current_user=current_user,
                    )
                    kwargs["enable_generation"] = False
                    retrieval_result = await unified_rag_pipeline(**kwargs)
                    docs = _normalize_documents_for_generation(
                        getattr(retrieval_result, "documents", []) or []
                    )
            except Exception:
                docs = []

            # If strategy=agentic, assemble ephemeral chunk and emit plan + spans first
            if getattr(request, 'strategy', 'standard') == 'agentic':
                try:
                    # Run agentic assembly without generation
                    a_cfg = AgenticConfig(
                        top_k_docs=int(getattr(request, 'agentic_top_k_docs', 3) or 3),
                        window_chars=int(getattr(request, 'agentic_window_chars', 1200) or 1200),
                        max_tokens_read=int(getattr(request, 'agentic_max_tokens_read', 6000) or 6000),
                        max_tool_calls=int(getattr(request, 'agentic_max_tool_calls', 8) or 8),
                        extractive_only=True,
                        quote_spans=True,
                        enable_tools=bool(getattr(request, 'agentic_enable_tools', False)),
                        use_llm_planner=bool(getattr(request, 'agentic_use_llm_planner', False)),
                        time_budget_sec=(getattr(request, 'agentic_time_budget_sec', None)),
                        cache_ttl_sec=int(getattr(request, 'agentic_cache_ttl_sec', 600) or 600),
                        debug_trace=bool(getattr(request, 'agentic_debug_trace', False) or request.debug_mode),
                        enable_query_decomposition=bool(getattr(request, 'agentic_enable_query_decomposition', False)),
                        subgoal_max=int(getattr(request, 'agentic_subgoal_max', 3) or 3),
                        enable_semantic_within=bool(getattr(request, 'agentic_enable_semantic_within', True)),
                        enable_section_index=bool(getattr(request, 'agentic_enable_section_index', True)),
                        prefer_structural_anchors=bool(getattr(request, 'agentic_prefer_structural_anchors', True)),
                        enable_table_support=bool(getattr(request, 'agentic_enable_table_support', True)),
                        agentic_enable_vlm_late_chunking=bool(getattr(request, 'agentic_enable_vlm_late_chunking', False)),
                        agentic_vlm_backend=getattr(request, 'agentic_vlm_backend', None),
                        agentic_vlm_detect_tables_only=bool(getattr(request, 'agentic_vlm_detect_tables_only', True)),
                        agentic_vlm_max_pages=getattr(request, 'agentic_vlm_max_pages', None),
                        agentic_vlm_late_chunk_top_k_docs=int(getattr(request, 'agentic_vlm_late_chunk_top_k_docs', 2) or 2),
                        agentic_use_provider_embeddings_within=bool(getattr(request, 'agentic_use_provider_embeddings_within', False)),
                        agentic_provider_embedding_model_id=getattr(request, 'agentic_provider_embedding_model_id', None),
                    )
                    ares = await agentic_rag_pipeline(
                        query=request.query,
                        sources=request.sources,
                        media_db=media_db,
                        chacha_db=chacha_db,
                        media_db_path=(media_db.db_path if media_db else None),
                        notes_db_path=(chacha_db.db_path if chacha_db else None),
                        character_db_path=(chacha_db.db_path if chacha_db else None),
                        search_mode=request.search_mode,
                        fts_level=request.fts_level,
                        hybrid_alpha=request.hybrid_alpha,
                        top_k=request.top_k,
                        min_score=request.min_score,
                        index_namespace=index_namespace,
                        agentic=a_cfg,
                        enable_generation=False,
                        enable_citations=False,
                        include_chunk_citations=False,
                        debug_mode=request.debug_mode,
                        explain_only=bool(getattr(request, 'explain_only', False)),
                    )
                    # Emit plan + spans
                    plan = ares.metadata.get('agentic_metrics', {}) if isinstance(ares.metadata, dict) else {}
                    yield json.dumps({"type": "plan", "plan": plan}) + "\n"
                    prov = ares.metadata.get('provenance') if isinstance(ares.metadata, dict) else None
                    if prov:
                        yield json.dumps({"type": "spans", "count": len(prov), "provenance": prov[:50]}) + "\n"
                    # Use synthetic chunk as the sole document for streaming generation
                    docs = _normalize_documents_for_generation(ares.documents)
                except Exception:
                    pass

            # Emit initial contexts (top-k with minimal fields) + a safe rationale plan (standard path)
            try:
                top_contexts = []
                for doc in (docs or [])[: min(10, (request.top_k or 10))]:
                    md = getattr(doc, 'metadata', None) or (doc.get('metadata') if isinstance(doc, dict) else {}) or {}
                    top_contexts.append({
                        "id": getattr(doc, 'id', doc.get('id') if isinstance(doc, dict) else None),
                        "title": (md.get('title') if isinstance(md, dict) else None),
                        "score": float(getattr(doc, 'score', md.get('score', 0.0) if isinstance(md, dict) else 0.0) or 0.0),
                        "url": md.get('url') if isinstance(md, dict) else None,
                        "source": md.get('source') if isinstance(md, dict) else None,
                    })
                # Lightweight "why these sources" summary
                def _safe_float(x):
                    try:
                        return float(x)
                    except Exception:
                        return 0.0
                scores = [_safe_float(getattr(d, 'score', (getattr(d, 'metadata', {}) or {}).get('score', 0.0))) for d in (docs or [])]
                topicality = 0.0
                if scores:
                    smin, smax = min(scores), max(scores)
                    topicality = (sum((s - smin) / (smax - smin) if smax > smin else 1.0 for s in scores) / len(scores)) if scores else 0.0
                why = {
                    "topicality": round(float(topicality), 4),
                    "diversity": None,  # full computation available in non-streaming pipeline metadata
                    "freshness": None,
                }
                yield json.dumps({"type": "contexts", "contexts": top_contexts, "why": why}) + "\n"
                # Safe partial rationale (no chain leakage)
                rationale = {
                    "plan": [
                        "Gather top-k contexts",
                        f"Rerank using strategy={getattr(request, 'reranking_strategy', 'flashrank')}",
                        "Ground claims from sources",
                        "Synthesize final answer",
                    ]
                }
                yield json.dumps({"type": "reasoning", **rationale}) + "\n"
            except Exception:
                pass

            # Minimal context for generation
            try:
                from tldw_Server_API.app.core.config import load_and_log_configs  # type: ignore
                cfg = load_and_log_configs() or {}
            except Exception:
                cfg = {}

            try:
                import os as _os
                env_provider = _os.getenv("RAG_DEFAULT_LLM_PROVIDER")
            except Exception:
                env_provider = None
            provider_value = env_provider if env_provider is not None else cfg.get("RAG_DEFAULT_LLM_PROVIDER")
            provider = (
                provider_value.strip()
                if isinstance(provider_value, str) and provider_value.strip()
                else "openai"
            )

            model_value = request.generation_model if isinstance(request.generation_model, str) else None
            if not model_value:
                try:
                    env_model = _os.getenv("RAG_DEFAULT_LLM_MODEL")
                except Exception:
                    env_model = None
                model_value = env_model if env_model is not None else cfg.get("RAG_DEFAULT_LLM_MODEL")
            model = (
                model_value.strip()
                if isinstance(model_value, str) and model_value.strip()
                else "gpt-4o-mini"
            )

            max_tokens = 500
            if request.max_generation_tokens is not None:
                try:
                    max_tokens = int(request.max_generation_tokens)
                except (TypeError, ValueError):
                    max_tokens = 500

            generation_config = {
                "streaming": True,
                "provider": provider,
                "model": model,
                "max_tokens": max_tokens,
            }
            if request.generation_prompt:
                generation_config["prompt_template"] = request.generation_prompt

            context = types.SimpleNamespace()
            context.documents = docs
            context.query = request.query
            context.config = {"generation": generation_config}
            context.metadata = {}

            # Initialize streaming generator with claims overlay enabled per request
            await generate_streaming_response(
                context,
                enable_claims=request.enable_claims,
                claims_top_k=request.claims_top_k,
                claims_max=request.claims_max,
                claims_concurrency=request.claims_concurrency,
            )

            last_overlay = None
            async for chunk in context.stream_generator:
                # Emit text chunks as NDJSON
                yield json.dumps({"type": "delta", "text": chunk}) + "\n"
                overlay = context.metadata.get("claims_overlay")
                if overlay and overlay != last_overlay:
                    yield json.dumps({"type": "claims_overlay", **overlay}) + "\n"
                    last_overlay = overlay

            # Final payload
            final_overlay = context.metadata.get("claims_overlay")
            if final_overlay:
                yield json.dumps({"type": "final_claims", **final_overlay}) + "\n"

        except Exception:
            yield json.dumps({"type": "error", "message": "Search failed due to an internal error."}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.get(
    "/advanced",
    summary="Advanced Search",
    description="""
    Advanced search with commonly used features enabled.

    Automatically enables:
    - Query expansion
    - Citations
    - Answer generation
    - Table processing
    - Performance analysis
    """,
    response_description="Full search results with analysis",
    dependencies=[Depends(check_rate_limit), Depends(require_permissions(MEDIA_READ))]
)
async def advanced_search_endpoint(
    request: Request,
    query: str,
    with_citations: bool = True,
    with_answer: bool = True,
    current_user: User = Depends(get_request_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
    chacha_db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    """
    Advanced search with common features enabled.
    """
    try:
        logger.info(f"Advanced search: query='{query}'")
        # Topic monitoring (non-blocking)
        try:
            from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
            mon = get_topic_monitoring_service()
            uid = str(current_user.username)
            mon.schedule_evaluate_and_alert(
                user_id=uid,
                text=query,
                source="rag.advanced_search",
                scope_type="user",
                scope_id=uid,
            )
        except Exception:
            pass

        # Set up database paths
        db_paths = {
            "media_db_path": media_db.db_path if media_db else None,
            "character_db_path": chacha_db.db_path if chacha_db else None,
            "kanban_db_path": _resolve_kanban_db_path(current_user),
        }

        # Use the advanced_search wrapper
        result = await advanced_search(
            query=query,
            with_citations=with_citations,
            with_answer=with_answer,
            media_db=media_db,
            chacha_db=chacha_db,
            **db_paths
        )

        return convert_result_to_response(result)

    except Exception as e:
        logger.error(f"Advanced search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed due to an internal error."
        )


@router.get(
    "/features",
    summary="List Available Features",
    description="Get a list of all available features in the unified pipeline",
    response_description="Feature list with descriptions"
)
async def list_features():
    """
    List all available features in the unified pipeline.
    """
    features_out = {
        "query_expansion": {
                "description": "Expand queries with synonyms, acronyms, domain terms, and entities",
                "parameters": ["expand_query", "expansion_strategies", "spell_check"]
        },
        "caching": {
                "description": "Semantic caching with adaptive thresholds",
                "parameters": ["enable_cache", "cache_threshold", "adaptive_cache"]
        },
        "security": {
                "description": "PII detection, content filtering, and access control",
                "parameters": ["enable_security_filter", "detect_pii", "redact_pii", "sensitivity_level"]
        },
        "citations": {
                "description": "Generate citations in various formats",
                "parameters": ["enable_citations", "citation_style", "include_page_numbers"]
        },
        "generation": {
                "description": "Generate answers from retrieved context",
                "parameters": ["enable_generation", "generation_model", "generation_prompt"]
        },
        "reranking": {
                "description": "Rerank documents for better relevance",
                "parameters": ["enable_reranking", "reranking_strategy", "rerank_top_k"]
        },
        "feedback": {
                "description": "Collect and apply user feedback",
                "parameters": ["collect_feedback", "feedback_user_id", "apply_feedback_boost"]
        },
        "monitoring": {
                "description": "Performance monitoring and observability",
                "parameters": ["enable_monitoring", "enable_observability", "trace_id"]
        },
        "table_processing": {
                "description": "Extract and process tables from documents",
                "parameters": ["enable_table_processing", "table_method"]
        },
        "vlm_late_chunking": {
                "description": "Add VLM-derived hints (tables/images) as late chunks from PDFs",
                "parameters": [
                    "enable_vlm_late_chunking",
                    "vlm_backend",
                    "vlm_detect_tables_only",
                    "vlm_max_pages",
                    "vlm_late_chunk_top_k_docs"
                ]
        },
        "enhanced_chunking": {
                "description": "Advanced document chunking with parent context",
                "parameters": ["enable_enhanced_chunking", "chunk_type_filter", "enable_parent_expansion"]
        },
        "batch_processing": {
                "description": "Process multiple queries concurrently",
                "parameters": ["enable_batch", "batch_queries", "batch_concurrent"]
        },
        "resilience": {
                "description": "Fault tolerance with retries and circuit breakers",
                "parameters": ["enable_resilience", "retry_attempts", "circuit_breaker"]
        }
    }

    # Compute totals dynamically
    total_features = len(features_out)
    total_parameters = sum(len(v.get("parameters", [])) for v in features_out.values())

    return {
        "features": features_out,
        "total_features": total_features,
        "total_parameters": total_parameters
    }


@router.get(
    "/health/simple",
    summary="Unified Health (Simple)",
    description="Lightweight health check for the unified RAG pipeline",
    response_description="Health status",
    dependencies=[Depends(check_rate_limit)]
)
async def unified_health_simple(request: Request):
    """
    Health check for the unified pipeline.
    """
    try:
        # Test basic search functionality
        test_result = await simple_search("test", top_k=1)

        return {
            "status": "healthy",
            "pipeline": "unified",
            "version": "1.0.0",
            "test_successful": len(test_result) >= 0
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "pipeline": "unified",
            "version": "1.0.0",
            "error": "AN ERROR HAS OCCURRED - RAG HEALTH CHECK FAILED - SEE SERVER LOGS",
        }
