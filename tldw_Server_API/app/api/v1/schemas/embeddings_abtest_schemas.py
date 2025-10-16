from __future__ import annotations

from typing import List, Optional, Dict, Literal, Any
from pydantic import BaseModel, Field, ConfigDict


class ABTestArm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str = Field(description="Embedding provider id, e.g., 'openai' or 'huggingface'")
    model: str = Field(description="Embedding model id")
    dimensions: Optional[int] = Field(default=None, description="Requested output dimensions if supported")


class ABTestChunking(BaseModel):
    model_config = ConfigDict(extra='forbid')
    method: str = Field(description="Chunking method, e.g., 'words' or 'sentences'")
    size: int = Field(ge=1, description="Max chunk size")
    overlap: int = Field(ge=0, description="Chunk overlap")
    language: Optional[str] = Field(default=None, description="Language hint")


class ABTestReRanker(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str = Field(description="Reranker provider id")
    model: str = Field(description="Reranker model id")


class ABTestRetrieval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    k: int = Field(ge=1, le=1000, description="Top-k results to return")
    search_mode: Optional[Literal['fts', 'vector', 'hybrid']] = Field(default='vector', description="Retrieval mode")
    hybrid_alpha: Optional[float] = Field(default=None, description="0=FTS only, 1=Vector only (hybrid blend)")
    re_ranker: Optional[ABTestReRanker] = Field(default=None, description="Optional reranker config")
    index_params: Optional[Dict[str, str]] = Field(default=None, description="Index parameters for vector store")
    apply_reranker: Optional[bool] = Field(default=False, description="Apply reranker in vector-only mode when re_ranker is set")


class ABTestQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(description="Query text")
    expected_ids: Optional[List[int]] = Field(default=None, description="Optional ground truth media ids")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Optional query metadata")


class ABTestLimits(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_docs: Optional[int] = Field(default=None, ge=1, description="Max docs to include from corpus")
    timeout_s: Optional[int] = Field(default=None, ge=1, description="Global timeout in seconds")


class ABTestCleanupPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    on_complete: bool = Field(default=False, description="Delete collections on completion")
    ttl_hours: Optional[int] = Field(default=None, ge=1, description="TTL for collections if not deleted immediately")


class EmbeddingsABTestConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Allow single arm for toggle-style tests; still supports classic A/B with 2+ arms
    arms: List[ABTestArm] = Field(min_length=1, description="Embedding models to compare")
    # Permit empty corpus in test-mode where synthetic or pre-existing collections may be used
    media_ids: List[int] = Field(default_factory=list, min_length=0, description="Media IDs to build the corpus from")
    chunking: Optional[ABTestChunking] = None
    retrieval: ABTestRetrieval
    queries: List[ABTestQuery] = Field(min_length=1, description="Queries to evaluate")
    metric_level: Optional[Literal['media', 'chunk']] = Field(default='media', description="Metric granularity")
    limits: Optional[ABTestLimits] = None
    reuse_existing: Optional[bool] = Field(default=True, description="Reuse matching collections if available")
    cleanup_policy: Optional[ABTestCleanupPolicy] = None


class EmbeddingsABTestCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str
    config: EmbeddingsABTestConfig
    run_immediately: Optional[bool] = Field(default=False)


class ArmSummary(BaseModel):
    arm_id: str
    provider: str
    model: str
    dimensions: Optional[int] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    latency_ms: Dict[str, float] = Field(default_factory=dict)
    doc_counts: Dict[str, int] = Field(default_factory=dict)


class EmbeddingsABTestResultSummary(BaseModel):
    test_id: str
    status: Literal['pending', 'running', 'completed', 'failed', 'canceled']
    arms: List[ArmSummary] = Field(default_factory=list)
    per_query: Optional[List[Dict[str, Any]]] = None


class EmbeddingsABTestCreateResponse(BaseModel):
    test_id: str
    status: Literal['pending', 'created'] = 'created'


class EmbeddingsABTestStatusResponse(BaseModel):
    test_id: str
    status: Literal['pending', 'running', 'completed', 'failed', 'canceled']
    progress: Optional[Dict[str, float]] = None


class EmbeddingsABTestResultsResponse(BaseModel):
    summary: EmbeddingsABTestResultSummary
    page: int = 1
    page_size: int = 50
    total: int = 0
