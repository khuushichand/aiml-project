# queue_schemas.py
# Queue message schemas for the embeddings scale-out architecture

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"  # Backward-compat alias used in tests
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Backward-compat job type enum used by some tests
class JobType(str, Enum):
    EMBEDDING = "embedding"
    CHUNKING = "chunking"
    STORAGE = "storage"


class JobPriority(int, Enum):
    LOW = 0
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


class UserTier(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ChunkingConfig(BaseModel):
    """Configuration for text chunking

    Defaults mirror legacy character-based behavior while enabling optional
    upgrades to use the v2 Chunker and/or templates when fields are set.
    """
    # Core sizing
    chunk_size: int = Field(default=1000, ge=50, le=10000, description="Primary size parameter; interpreted per 'unit' if using v2 Chunker, else characters")
    overlap: int = Field(default=200, ge=0, le=500, description="Overlap amount (interpreted per 'unit' if using v2 Chunker, else characters)")
    separator: str = Field(default="\n", description="Preferred break character for fallback char-based chunking")

    # v2 Chunker options (optional)
    method: Optional[str] = Field(default=None, description="Chunking method for v2 Chunker (e.g., 'words', 'sentences', 'paragraphs', 'tokens', 'semantic', 'json', 'xml', 'ebook_chapters', 'propositions')")
    unit: Optional[str] = Field(default=None, description="Unit for interpreting chunk_size/overlap when using v2 Chunker; one of: 'words', 'tokens', or 'chars'. Defaults to method-appropriate behavior or to 'words'.")
    language: Optional[str] = Field(default=None, description="Language hint for v2 Chunker")

    # Template processing (optional; uses built-in template manager)
    template_name: Optional[str] = Field(default=None, description="Apply a named template (preprocess → chunk → postprocess) for chunking")
    hierarchical: Optional[bool] = Field(default=None, description="Enable hierarchical parsing when supported by template or method")
    hierarchical_template: Optional[Dict[str, Any]] = Field(default=None, description="Custom hierarchical boundary rules when hierarchical is enabled")

    # Legacy/contextual fields (unchanged)
    preserve_metadata: bool = True
    contextualize: bool = False  # Whether to add context via LLM
    contextual_llm_model: Optional[str] = Field(default=None, description="LLM model for contextualization")
    context_window_size: Optional[int] = Field(default=None, ge=100, le=2000, description="Context window size")


class ChunkData(BaseModel):
    """Individual chunk data"""
    chunk_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    start_index: int
    end_index: int
    sequence_number: int


class EmbeddingData(BaseModel):
    """Embedding result data"""
    chunk_id: str
    embedding: List[float]
    model_used: str
    dimensions: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Base job message that all queue messages inherit from
class EmbeddingJobMessage(BaseModel):
    """Base message for all embedding pipeline jobs"""
    # Message envelope
    msg_version: int = Field(default=1, description="Message schema version")
    msg_schema: str = Field(default="tldw.embeddings.v1", alias="schema", description="Logical schema name (alias: schema)")
    schema_url: Optional[str] = Field(default=None, description="JSON Schema URL for validation")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key for exactly-once semantics where possible")
    dedupe_key: Optional[str] = Field(default=None, description="Optional dedupe key used to suppress replays within a time window")
    operation_id: Optional[str] = Field(default=None, description="Operation id for replay prevention across stages/outages")
    job_id: str = Field(..., description="Unique job identifier")
    user_id: str = Field(..., description="User who initiated the job")
    media_id: int = Field(..., description="Media item being processed")
    priority: int = Field(default=JobPriority.NORMAL, ge=0, le=100)
    user_tier: UserTier = Field(default=UserTier.FREE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    trace_id: Optional[str] = Field(None, description="For distributed tracing")

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


# Chunking stage message
class ChunkingMessage(EmbeddingJobMessage):
    """Message for chunking queue"""
    content: str = Field(..., description="Raw content to be chunked")
    content_type: str = Field(..., description="Type of content (text, document, etc)")
    chunking_config: ChunkingConfig = Field(default_factory=ChunkingConfig)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)


# Embedding stage message
class EmbeddingMessage(EmbeddingJobMessage):
    """Message for embedding queue"""
    chunks: List[ChunkData] = Field(..., description="Chunks to be embedded")
    embedding_model_config: Dict[str, Any] = Field(..., description="Embedding model configuration")
    model_provider: str = Field(..., description="Provider type (huggingface, openai, etc)")
    batch_size: Optional[int] = Field(None, description="Override default batch size")


# Storage stage message
class StorageMessage(EmbeddingJobMessage):
    """Message for storage queue"""
    embeddings: List[EmbeddingData] = Field(..., description="Generated embeddings")
    collection_name: str = Field(..., description="ChromaDB collection name")
    total_chunks: int = Field(..., description="Total number of chunks processed")
    processing_time_ms: int = Field(..., description="Time taken for embedding generation")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Job status tracking
class JobInfo(BaseModel):
    """Complete job information for status tracking"""
    job_id: str
    user_id: str
    media_id: int
    status: JobStatus
    priority: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    chunks_processed: int = Field(default=0, ge=0)
    total_chunks: int = Field(default=0, ge=0)
    current_stage: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# Worker health/metrics
class WorkerMetrics(BaseModel):
    """Metrics reported by workers"""
    worker_id: str
    worker_type: str  # chunking, embedding, storage
    jobs_processed: int
    jobs_failed: int
    average_processing_time_ms: float
    current_load: float = Field(ge=0.0, le=1.0)  # 0-1 representing load
    available_memory_mb: Optional[float] = None
    gpu_utilization: Optional[float] = None
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Backward-compat simple job request/result schemas expected by tests

class JobRequest(BaseModel):
    """Simplified job request schema for tests"""
    job_id: str
    job_type: JobType
    media_id: int
    collection_name: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=50, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobResult(BaseModel):
    """Simplified job result schema for tests"""
    job_id: str
    status: JobStatus
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# Queue configuration
class QueueConfig(BaseModel):
    """Configuration for a specific queue"""
    queue_name: str
    max_length: int = Field(default=10000, ge=100)
    ttl_seconds: int = Field(default=3600, ge=60)  # Message TTL
    consumer_group: str
    batch_size: int = Field(default=1, ge=1)
    poll_interval_ms: int = Field(default=100, ge=10)
