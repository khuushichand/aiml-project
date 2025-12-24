from __future__ import annotations

from typing import Optional, List, Dict, Literal

from pydantic import BaseModel, Field, ConfigDict


class ClaimsSettingsResponse(BaseModel):
    """Current claims-related configuration values."""

    model_config = ConfigDict(extra="forbid")

    enable_ingestion_claims: bool = Field(..., description="Enable ingestion-time claim extraction.")
    claim_extractor_mode: str = Field(..., description="Default extractor mode for ingestion-time claims.")
    claims_max_per_chunk: int = Field(..., description="Maximum claims per chunk during ingestion.")
    claims_embed: bool = Field(..., description="Enable embedding of extracted claims.")
    claims_embed_model_id: str = Field(..., description="Model id for claim embeddings.")
    claims_cluster_method: str = Field(..., description="Clustering method for claim grouping.")
    claims_cluster_similarity_threshold: float = Field(
        ..., description="Cosine similarity threshold for embedding-based clustering."
    )
    claims_cluster_batch_size: int = Field(..., description="Batch size for loading claim embeddings.")
    claims_llm_provider: str = Field(..., description="LLM provider for claim extraction.")
    claims_llm_temperature: float = Field(..., description="LLM temperature for claim extraction.")
    claims_llm_model: str = Field(..., description="LLM model for claim extraction.")
    claims_rebuild_enabled: bool = Field(..., description="Enable periodic claims rebuild worker.")
    claims_rebuild_interval_sec: int = Field(..., description="Claims rebuild loop interval in seconds.")
    claims_rebuild_policy: str = Field(..., description="Claims rebuild policy.")
    claims_stale_days: int = Field(..., description="Stale threshold for claims rebuild policy.")


class ClaimsSettingsUpdate(BaseModel):
    """Update payload for claims settings."""

    model_config = ConfigDict(extra="forbid")

    enable_ingestion_claims: Optional[bool] = Field(default=None)
    claim_extractor_mode: Optional[str] = Field(default=None)
    claims_max_per_chunk: Optional[int] = Field(default=None, ge=1, le=100)
    claims_embed: Optional[bool] = Field(default=None)
    claims_embed_model_id: Optional[str] = Field(default=None)
    claims_cluster_method: Optional[str] = Field(default=None)
    claims_cluster_similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    claims_cluster_batch_size: Optional[int] = Field(default=None, ge=1, le=10000)
    claims_llm_provider: Optional[str] = Field(default=None)
    claims_llm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    claims_llm_model: Optional[str] = Field(default=None)
    claims_rebuild_enabled: Optional[bool] = Field(default=None)
    claims_rebuild_interval_sec: Optional[int] = Field(default=None, ge=60, le=604800)
    claims_rebuild_policy: Optional[str] = Field(default=None)
    claims_stale_days: Optional[int] = Field(default=None, ge=1, le=3650)
    persist: Optional[bool] = Field(default=None, description="Persist updates to config.txt.")


class ClaimUpdateRequest(BaseModel):
    """Update fields for a claim entry."""

    model_config = ConfigDict(extra="forbid")

    claim_text: Optional[str] = Field(default=None)
    span_start: Optional[int] = Field(default=None, ge=0)
    span_end: Optional[int] = Field(default=None, ge=0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    extractor: Optional[str] = Field(default=None)
    extractor_version: Optional[str] = Field(default=None)
    deleted: Optional[bool] = Field(default=None)


class ClaimsMonitoringSettingsResponse(BaseModel):
    """Runtime monitoring configuration values."""

    model_config = ConfigDict(extra="forbid")

    claims_monitoring_enabled: bool = Field(..., description="Enable claims monitoring.")
    claims_alert_threshold_default: float = Field(..., description="Default unsupported ratio threshold.")
    claims_rebuild_max_queue_alert: int = Field(..., description="Queue size warning threshold.")
    claims_rebuild_heartbeat_warn_sec: int = Field(..., description="Heartbeat warning threshold in seconds.")
    claims_provider_cost_multipliers: Dict[str, float] = Field(
        default_factory=dict, description="Provider cost multipliers mapping."
    )


class ClaimsMonitoringSettingsUpdate(BaseModel):
    """Update monitoring config (optional persistence)."""

    model_config = ConfigDict(extra="forbid")

    claims_monitoring_enabled: Optional[bool] = Field(default=None)
    claims_alert_threshold_default: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    claims_rebuild_max_queue_alert: Optional[int] = Field(default=None, ge=0)
    claims_rebuild_heartbeat_warn_sec: Optional[int] = Field(default=None, ge=0)
    claims_provider_cost_multipliers: Optional[Dict[str, float]] = Field(default=None)
    persist: Optional[bool] = Field(default=None, description="Persist updates to config.txt.")


class ClaimsAlertConfigResponse(BaseModel):
    """Alert configuration for claims monitoring."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: str
    threshold_ratio: Optional[float] = None
    baseline_ratio: Optional[float] = None
    slack_webhook_url: Optional[str] = None
    webhook_url: Optional[str] = None
    email_recipients: List[str] = Field(default_factory=list)
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsAlertConfigCreate(BaseModel):
    """Create alert configuration."""

    model_config = ConfigDict(extra="forbid")

    threshold_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    slack_webhook_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    email_recipients: Optional[List[str]] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)


class ClaimsAlertConfigUpdate(BaseModel):
    """Update alert configuration."""

    model_config = ConfigDict(extra="forbid")

    threshold_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    slack_webhook_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    email_recipients: Optional[List[str]] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)


class ClaimNotificationResponse(BaseModel):
    """Notification payload for claims-related events."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: str
    kind: str
    target_user_id: Optional[str] = None
    target_review_group: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    payload: Dict[str, object] = Field(default_factory=dict)
    created_at: Optional[str] = None
    delivered_at: Optional[str] = None


class ClaimNotificationsAckRequest(BaseModel):
    """Mark notifications as delivered."""

    model_config = ConfigDict(extra="forbid")

    ids: List[int] = Field(..., min_length=1)


class ClaimNotificationsDigestResponse(BaseModel):
    """Digest response for claim notifications."""

    model_config = ConfigDict(extra="forbid")

    total: int
    counts_by_kind: Dict[str, int] = Field(default_factory=dict)
    counts_by_target_user: Dict[str, int] = Field(default_factory=dict)
    counts_by_review_group: Dict[str, int] = Field(default_factory=dict)
    notifications: Optional[List[ClaimNotificationResponse]] = None


class ClaimReviewRequest(BaseModel):
    """Review update payload for a claim."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="New review status.")
    review_version: int = Field(..., ge=1)
    notes: Optional[str] = Field(default=None)
    corrected_text: Optional[str] = Field(default=None)
    reason_code: Optional[str] = Field(default=None)
    reviewer_id: Optional[int] = Field(default=None)
    review_group: Optional[str] = Field(default=None)


class ClaimReviewBulkRequest(BaseModel):
    """Bulk review action payload."""

    model_config = ConfigDict(extra="forbid")

    claim_ids: List[int] = Field(..., min_length=1)
    status: str = Field(..., description="Review status for all claims.")
    notes: Optional[str] = Field(default=None)
    reason_code: Optional[str] = Field(default=None)
    reviewer_id: Optional[int] = Field(default=None)
    review_group: Optional[str] = Field(default=None)


class ClaimReviewRuleCreate(BaseModel):
    """Create review assignment rule."""

    model_config = ConfigDict(extra="forbid")

    priority: int = Field(default=0)
    predicate_json: Dict[str, object] = Field(default_factory=dict)
    reviewer_id: Optional[int] = Field(default=None)
    review_group: Optional[str] = Field(default=None)
    active: Optional[bool] = Field(default=None)


class ClaimReviewRuleUpdate(BaseModel):
    """Update review assignment rule."""

    model_config = ConfigDict(extra="forbid")

    priority: Optional[int] = Field(default=None)
    predicate_json: Optional[Dict[str, object]] = Field(default=None)
    reviewer_id: Optional[int] = Field(default=None)
    review_group: Optional[str] = Field(default=None)
    active: Optional[bool] = Field(default=None)


class ClaimsAnalyticsExportRequest(BaseModel):
    """Export analytics payload."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["json", "csv"] = Field(default="json")
    window_days: Optional[int] = Field(default=None, ge=1, le=365)
    window_sec: Optional[int] = Field(default=None, ge=60, le=604800)
    baseline_sec: Optional[int] = Field(default=None, ge=60, le=2592000)


class ClaimsAnalyticsPerMediaCount(BaseModel):
    """Claims per media count."""

    model_config = ConfigDict(extra="forbid")

    media_id: int
    count: int


class ClaimsAnalyticsPerMediaStats(BaseModel):
    """Summary stats for claims per media."""

    model_config = ConfigDict(extra="forbid")

    mean: Optional[float] = None
    p95: Optional[int] = None
    max: Optional[int] = None


class ClaimsAnalyticsReviewThroughputPoint(BaseModel):
    """Daily review throughput point."""

    model_config = ConfigDict(extra="forbid")

    date: str
    count: int


class ClaimsAnalyticsReviewThroughput(BaseModel):
    """Windowed review throughput summary."""

    model_config = ConfigDict(extra="forbid")

    window_days: int
    total: int
    daily: List[ClaimsAnalyticsReviewThroughputPoint] = Field(default_factory=list)


class ClaimsAnalyticsClusterSummary(BaseModel):
    """Summary view for a claim cluster."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    member_count: int
    watchlist_count: int
    canonical_claim_text: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsAnalyticsClusterStats(BaseModel):
    """Aggregate cluster statistics."""

    model_config = ConfigDict(extra="forbid")

    total_clusters: int
    clusters_with_members: int
    total_members: int
    avg_member_count: Optional[float] = None
    p95_member_count: Optional[int] = None
    max_member_count: Optional[int] = None
    orphan_claims: int
    top_clusters: List[ClaimsAnalyticsClusterSummary] = Field(default_factory=list)


class ClaimsAnalyticsUnsupportedRatios(BaseModel):
    """Unsupported ratio overview."""

    model_config = ConfigDict(extra="forbid")

    window_sec: int
    baseline_sec: int
    window_ratio: Optional[float] = None
    baseline_ratio: Optional[float] = None


class ClaimsAnalyticsRebuildHealth(BaseModel):
    """Rebuild worker health summary."""

    model_config = ConfigDict(extra="forbid")

    status: str
    queue_length: int
    workers: int
    last_heartbeat_ts: float
    heartbeat_age_sec: Optional[float] = None
    last_processed_ts: Optional[float] = None
    last_failure: Optional[Dict[str, object]] = None
    stale: bool


class ClaimsAnalyticsDashboardResponse(BaseModel):
    """Dashboard-ready claims analytics payload."""

    model_config = ConfigDict(extra="forbid")

    total_claims: int
    status_counts: Dict[str, int]
    avg_review_latency_sec: Optional[float] = None
    p95_review_latency_sec: Optional[float] = None
    review_backlog: int
    claims_per_media_top: List[ClaimsAnalyticsPerMediaCount] = Field(default_factory=list)
    claims_per_media_stats: ClaimsAnalyticsPerMediaStats
    review_throughput: ClaimsAnalyticsReviewThroughput
    clusters: ClaimsAnalyticsClusterStats
    unsupported_ratios: ClaimsAnalyticsUnsupportedRatios
    rebuild_health: Optional[ClaimsAnalyticsRebuildHealth] = None
