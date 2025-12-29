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


class ClaimsSearchResult(BaseModel):
    """Claims search result row."""

    model_config = ConfigDict(extra="forbid")

    id: int
    media_id: int
    chunk_index: int
    claim_text: str
    claim_cluster_id: Optional[int] = None
    relevance_score: Optional[float] = None


class ClaimsSearchClusterResult(BaseModel):
    """Clustered claims search result."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    canonical_claim_text: Optional[str] = None
    representative_claim_id: Optional[int] = None
    watchlist_count: Optional[int] = None
    match_count: int
    top_claim: ClaimsSearchResult


class ClaimsSearchResponse(BaseModel):
    """Claims search response payload."""

    model_config = ConfigDict(extra="forbid")

    query: str
    group_by_cluster: bool
    total: int
    results: List[ClaimsSearchResult] = Field(default_factory=list)
    clusters: Optional[List[ClaimsSearchClusterResult]] = None
    orphaned: Optional[List[ClaimsSearchResult]] = None


class ClaimsClusterLinkCreate(BaseModel):
    """Create a cluster relationship link."""

    model_config = ConfigDict(extra="forbid")

    child_cluster_id: int
    relation_type: Optional[str] = Field(default=None)


class ClaimsClusterLinkResponse(BaseModel):
    """Cluster relationship link response."""

    model_config = ConfigDict(extra="forbid")

    parent_cluster_id: int
    child_cluster_id: int
    relation_type: Optional[str] = None
    created_at: Optional[str] = None
    direction: Optional[str] = None


class ClaimsMonitoringSettingsResponse(BaseModel):
    """Claims monitoring configuration."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: str
    threshold_ratio: float = Field(..., ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    slack_webhook_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    email_recipients: List[str] = Field(default_factory=list)
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsMonitoringSettingsUpdate(BaseModel):
    """Update monitoring config."""

    model_config = ConfigDict(extra="forbid")

    threshold_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    slack_webhook_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    email_recipients: Optional[List[str]] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    persist: Optional[bool] = Field(default=None, description="Legacy no-op.")


class ClaimsAlertConfigResponse(BaseModel):
    """Alert configuration for claims monitoring."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: str
    name: str
    alert_type: str
    threshold_ratio: Optional[float] = None
    baseline_ratio: Optional[float] = None
    channels: Dict[str, bool] = Field(default_factory=dict)
    slack_webhook_url: Optional[str] = None
    webhook_url: Optional[str] = None
    email_recipients: List[str] = Field(default_factory=list)
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsAlertConfigCreate(BaseModel):
    """Create alert configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    alert_type: str = Field(..., min_length=1)
    threshold_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    channels: Dict[str, bool] = Field(default_factory=dict)
    slack_webhook_url: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    email_recipients: Optional[List[str]] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)


class ClaimsAlertConfigUpdate(BaseModel):
    """Update alert configuration."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1)
    alert_type: Optional[str] = Field(default=None, min_length=1)
    threshold_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    baseline_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    channels: Optional[Dict[str, bool]] = Field(default=None)
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


class ClaimsAnalyticsExportFilters(BaseModel):
    """Filters for claims analytics exports."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: Optional[str] = Field(default=None)
    event_type: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    start_time: Optional[str] = Field(default=None)
    end_time: Optional[str] = Field(default=None)


class ClaimsAnalyticsExportPagination(BaseModel):
    """Pagination controls for claims analytics exports."""

    model_config = ConfigDict(extra="forbid")

    limit: Optional[int] = Field(default=1000, ge=1, le=10000)
    offset: Optional[int] = Field(default=0, ge=0)


class ClaimsAnalyticsExportRequest(BaseModel):
    """Export analytics payload."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["json", "csv"]
    filters: Optional[ClaimsAnalyticsExportFilters] = Field(default=None)
    pagination: Optional[ClaimsAnalyticsExportPagination] = Field(default=None)


class ClaimsAnalyticsExportResponse(BaseModel):
    """Claims analytics export handle."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    format: Literal["json", "csv"]
    status: str
    download_url: Optional[str] = None
    created_at: Optional[str] = None


class ClaimsAnalyticsExportPaginationMeta(BaseModel):
    """Pagination metadata for stored exports."""

    model_config = ConfigDict(extra="forbid")

    limit: Optional[int] = None
    offset: Optional[int] = None
    total: Optional[int] = None


class ClaimsAnalyticsExportListItem(BaseModel):
    """Claims analytics export history item."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    format: Literal["json", "csv"]
    status: str
    download_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    filters: Optional[ClaimsAnalyticsExportFilters] = None
    pagination: Optional[ClaimsAnalyticsExportPaginationMeta] = None
    error_message: Optional[str] = None


class ClaimsAnalyticsExportListResponse(BaseModel):
    """Claims analytics export history payload."""

    model_config = ConfigDict(extra="forbid")

    exports: List[ClaimsAnalyticsExportListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


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


class ClaimsAnalyticsReviewStatusTrendPoint(BaseModel):
    """Daily review status trend point."""

    model_config = ConfigDict(extra="forbid")

    date: str
    total: int
    status_counts: Dict[str, int] = Field(default_factory=dict)


class ClaimsAnalyticsReviewStatusTrends(BaseModel):
    """Windowed review status trend summary."""

    model_config = ConfigDict(extra="forbid")

    window_days: int
    daily: List[ClaimsAnalyticsReviewStatusTrendPoint] = Field(default_factory=list)


class ClaimsReviewExtractorMetricsDaily(BaseModel):
    """Daily review metrics grouped by extractor."""

    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = None
    user_id: str
    report_date: str
    extractor: str
    extractor_version: str
    total_reviewed: int
    approved_count: int
    rejected_count: int
    flagged_count: int
    reassigned_count: int
    edited_count: int
    reason_code_counts: Dict[str, int] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsReviewExtractorMetricsResponse(BaseModel):
    """Review extractor metrics response payload."""

    model_config = ConfigDict(extra="forbid")

    items: List[ClaimsReviewExtractorMetricsDaily] = Field(default_factory=list)
    total: int


class ClaimsAnalyticsClusterSummary(BaseModel):
    """Summary view for a claim cluster."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    member_count: int
    watchlist_count: int
    canonical_claim_text: Optional[str] = None
    updated_at: Optional[str] = None


class ClaimsAnalyticsClusterHotspot(BaseModel):
    """Cluster hotspot summary."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int
    member_count: int
    issue_count: int
    issue_ratio: Optional[float] = None
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
    hotspots: List[ClaimsAnalyticsClusterHotspot] = Field(default_factory=list)


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
    review_status_trends: ClaimsAnalyticsReviewStatusTrends
    review_extractor_metrics: Optional[List[ClaimsReviewExtractorMetricsDaily]] = None
    clusters: ClaimsAnalyticsClusterStats
    unsupported_ratios: ClaimsAnalyticsUnsupportedRatios
    rebuild_health: Optional[ClaimsAnalyticsRebuildHealth] = None
