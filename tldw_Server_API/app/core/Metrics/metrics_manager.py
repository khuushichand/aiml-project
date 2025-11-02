"""
Centralized metrics management for the tldw_server application.

This module provides a unified interface for all metric operations,
supporting both OpenTelemetry and fallback implementations.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from contextlib import contextmanager
import statistics

from loguru import logger

from .telemetry import get_telemetry_manager, OTEL_AVAILABLE

if OTEL_AVAILABLE:
    from opentelemetry.metrics import CallbackOptions, Observation


class MetricType(Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    UP_DOWN_COUNTER = "up_down_counter"


@dataclass
class MetricDefinition:
    """Definition of a metric."""
    name: str
    type: MetricType
    description: str
    unit: str = ""
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms


@dataclass
class MetricValue:
    """A metric value with metadata."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsRegistry:
    """Registry for all application metrics."""

    def __init__(self):
        """Initialize the metrics registry."""
        self.metrics: Dict[str, MetricDefinition] = {}
        self.instruments: Dict[str, Any] = {}
        self.values: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Initialize with telemetry manager
        self.telemetry = get_telemetry_manager()
        self.meter = self.telemetry.get_meter("tldw_server.metrics")

        # Register standard metrics
        self._register_standard_metrics()

    def _register_standard_metrics(self):
        """Register standard application metrics."""
        # HTTP metrics
        self.register_metric(
            MetricDefinition(
                name="http_requests_total",
                type=MetricType.COUNTER,
                description="Total number of HTTP requests",
                labels=["method", "endpoint", "status"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="http_request_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="HTTP request duration in seconds",
                unit="s",
                labels=["method", "endpoint"],
                buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
            )
        )

        # Database metrics
        self.register_metric(
            MetricDefinition(
                name="db_connections_active",
                type=MetricType.GAUGE,
                description="Number of active database connections",
                labels=["database"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="db_queries_total",
                type=MetricType.COUNTER,
                description="Total number of database queries",
                labels=["database", "operation"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="db_query_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Database query duration in seconds",
                unit="s",
                labels=["database", "operation"],
                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_snapshots_table_bytes",
                type=MetricType.GAUGE,
                description="On-disk size of the privilege_snapshots table",
                unit="bytes",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_snapshots_table_rows",
                type=MetricType.GAUGE,
                description="Number of rows stored in the privilege_snapshots table",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_cache_hits_total",
                type=MetricType.COUNTER,
                description="Total number of privilege cache hits",
                labels=["backend", "layer"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_cache_misses_total",
                type=MetricType.COUNTER,
                description="Total number of privilege cache misses",
                labels=["backend", "layer"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_cache_invalidations_total",
                type=MetricType.COUNTER,
                description="Number of privilege cache invalidations broadcast",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_cache_generation",
                type=MetricType.GAUGE,
                description="Current privilege cache generation counter",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="privilege_cache_entries",
                type=MetricType.GAUGE,
                description="Current number of entries tracked in the local privilege cache",
                labels=["backend"],
            )
        )

        # LLM metrics
        self.register_metric(
            MetricDefinition(
                name="llm_requests_total",
                type=MetricType.COUNTER,
                description="Total number of LLM API requests",
                labels=["provider", "model", "status"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="llm_tokens_used_total",
                type=MetricType.COUNTER,
                description="Total number of tokens used",
                labels=["provider", "model", "type"]  # type: prompt/completion
            )
        )

        self.register_metric(
            MetricDefinition(
                name="llm_request_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="LLM request duration in seconds",
                unit="s",
                labels=["provider", "model"],
                buckets=[0.1, 0.5, 1, 2.5, 5, 10, 30, 60]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="llm_cost_dollars",
                type=MetricType.COUNTER,
                description="Cumulative LLM API cost in dollars",
                unit="$",
                labels=["provider", "model"]
            )
        )
        # Detailed LLM usage variants for dashboards
        self.register_metric(
            MetricDefinition(
                name="llm_cost_dollars_by_user",
                type=MetricType.COUNTER,
                description="Cumulative LLM API cost in dollars by user",
                unit="$",
                labels=["provider", "model", "user_id"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="llm_cost_dollars_by_operation",
                type=MetricType.COUNTER,
                description="Cumulative LLM API cost in dollars by operation",
                unit="$",
                labels=["provider", "model", "operation"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="llm_tokens_used_total_by_user",
                type=MetricType.COUNTER,
                description="Total number of tokens used by user",
                labels=["provider", "model", "type", "user_id"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="llm_tokens_used_total_by_operation",
                type=MetricType.COUNTER,
                description="Total number of tokens used by operation",
                labels=["provider", "model", "type", "operation"],
            )
        )

        # Infrastructure / Redis metrics
        self.register_metric(
            MetricDefinition(
                name="infra_redis_connection_attempts_total",
                type=MetricType.COUNTER,
                description="Redis client connection attempts",
                labels=["mode", "context", "outcome"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="infra_redis_connection_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Redis client connection duration in seconds",
                unit="s",
                labels=["mode", "context", "outcome"],
                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="infra_redis_connection_errors_total",
                type=MetricType.COUNTER,
                description="Redis client connection errors",
                labels=["mode", "context", "error"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="infra_redis_fallback_total",
                type=MetricType.COUNTER,
                description="Redis client fallbacks to in-memory stub",
                labels=["mode", "context", "reason"],
            )
        )

        # RAG metrics
        self.register_metric(
            MetricDefinition(
                name="rag_queries_total",
                type=MetricType.COUNTER,
                description="Total number of RAG queries",
                labels=["pipeline", "status"]
            )
        )

        # Generic application observability counters
        self.register_metric(
            MetricDefinition(
                name="app_exception_events_total",
                type=MetricType.COUNTER,
                description="Application exception events",
                labels=["component", "event"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="app_warning_events_total",
                type=MetricType.COUNTER,
                description="Application warning events",
                labels=["component", "event"],
            )
        )

        # Sandbox (code interpreter) metrics
        self.register_metric(
            MetricDefinition(
                name="sandbox_sessions_created_total",
                type=MetricType.COUNTER,
                description="Total sandbox sessions created",
                labels=["runtime"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_runs_started_total",
                type=MetricType.COUNTER,
                description="Total sandbox runs started",
                labels=["runtime"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_runs_completed_total",
                type=MetricType.COUNTER,
                description="Total sandbox runs finished",
                labels=["runtime", "outcome", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_run_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Sandbox run duration in seconds",
                unit="s",
                labels=["runtime", "outcome", "reason"],
                buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 60, 120, 300]
            )
        )
        # WS & queue metrics used by sandbox endpoints/streams
        self.register_metric(
            MetricDefinition(
                name="sandbox_log_truncations_total",
                type=MetricType.COUNTER,
                description="Total number of sandbox log truncations",
                labels=["component", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_queue_full_total",
                type=MetricType.COUNTER,
                description="Total number of sandbox queue-full events",
                labels=["component", "runtime", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_queue_ttl_expired_total",
                type=MetricType.COUNTER,
                description="Total number of sandbox queue TTL expirations",
                labels=["component", "runtime", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_ws_connections_opened_total",
                type=MetricType.COUNTER,
                description="Total sandbox WS connections opened",
                labels=["component"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_ws_heartbeats_sent_total",
                type=MetricType.COUNTER,
                description="Total sandbox WS heartbeats sent",
                labels=["component"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_ws_disconnects_total",
                type=MetricType.COUNTER,
                description="Total sandbox WS disconnects",
                labels=["component"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_ws_queue_drops_total",
                type=MetricType.COUNTER,
                description="Total WS queue drops (oldest dropped)",
                labels=["component", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_upload_bytes_total",
                type=MetricType.COUNTER,
                description="Total bytes uploaded to sandbox workspaces",
                unit="bytes",
                labels=["kind"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="sandbox_upload_files_total",
                type=MetricType.COUNTER,
                description="Total files uploaded to sandbox workspaces",
                labels=["kind"],
            )
        )

        self.register_metric(
            MetricDefinition(
                name="rag_retrieval_latency_seconds",
                type=MetricType.HISTOGRAM,
                description="RAG retrieval latency in seconds",
                unit="s",
                labels=["source", "pipeline"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="rag_documents_retrieved",
                type=MetricType.HISTOGRAM,
                description="Number of documents retrieved",
                labels=["source", "pipeline"],
                buckets=[1, 5, 10, 25, 50, 100, 250, 500]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="rag_cache_hits_total",
                type=MetricType.COUNTER,
                description="Total RAG cache hits",
                labels=["cache_type"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="rag_cache_misses_total",
                type=MetricType.COUNTER,
                description="Total RAG cache misses",
                labels=["cache_type"]
            )
        )

        # RAG reranker (LLM scoring) guardrails and activity
        self.register_metric(
            MetricDefinition(
                name="rag_reranker_llm_timeouts_total",
                type=MetricType.COUNTER,
                description="Total LLM reranker timeouts",
                labels=["strategy"]  # e.g., llm_scoring
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_reranker_llm_exceptions_total",
                type=MetricType.COUNTER,
                description="Total LLM reranker exceptions",
                labels=["strategy"]
            )
        )

        # Post-generation verification (adaptive check) metrics
        self.register_metric(
            MetricDefinition(
                name="rag_adaptive_retries_total",
                type=MetricType.COUNTER,
                description="Total adaptive post-check repair retries",
            )
        )
        # RAG factuality gauges (observability)
        self.register_metric(
            MetricDefinition(
                name="rag_hard_citation_coverage",
                type=MetricType.GAUGE,
                description="Per-answer hard-citation coverage ratio (0.0-1.0)",
                labels=["strategy"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_nli_unsupported_ratio",
                type=MetricType.GAUGE,
                description="Per-answer NLI unsupported ratio (refuted+NEI)/total",
                labels=["strategy"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_unsupported_claims_total",
                type=MetricType.COUNTER,
                description="Total unsupported claims (refuted + NEI) observed in post-check",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_adaptive_fix_success_total",
                type=MetricType.COUNTER,
                description="Total adaptive post-check repairs that succeeded",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_postcheck_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Duration of post-generation verification and repair",
                unit="s",
                labels=["outcome"],
                buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20]
            )
        )
        # Adaptive rerun metrics
        self.register_metric(
            MetricDefinition(
                name="rag_adaptive_rerun_performed_total",
                type=MetricType.COUNTER,
                description="Total number of adaptive RAG reruns performed",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_adaptive_rerun_adopted_total",
                type=MetricType.COUNTER,
                description="Total number of adaptive RAG reruns whose results were adopted",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_adaptive_rerun_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Duration of adaptive RAG reruns",
                unit="s",
                labels=["adopted"],
                buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_reranker_llm_budget_exhausted_total",
                type=MetricType.COUNTER,
                description="Total LLM reranker budget exhaustions",
                labels=["strategy"]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_reranker_llm_docs_scored_total",
                type=MetricType.COUNTER,
                description="Total documents scored by LLM reranker",
                labels=["strategy"]
            )
        )

        # Per-phase timers and budgets (observability/SLOs)
        self.register_metric(
            MetricDefinition(
                name="rag_phase_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Duration per RAG pipeline phase",
                unit="s",
                labels=["phase", "difficulty"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_reranking_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Reranking duration (overall) in seconds",
                unit="s",
                labels=["strategy"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
            )
        )
        # Rewrite cache metrics
        self.register_metric(
            MetricDefinition(
                name="rag_rewrite_cache_hits_total",
                type=MetricType.COUNTER,
                description="Total rewrite cache hits",
                labels=["corpus", "intent"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_rewrite_cache_misses_total",
                type=MetricType.COUNTER,
                description="Total rewrite cache misses",
                labels=["corpus", "intent", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_rewrite_cache_puts_total",
                type=MetricType.COUNTER,
                description="Total rewrite cache writes",
                labels=["corpus", "intent"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_batch_query_reuse_total",
                type=MetricType.COUNTER,
                description="Total reused results in batch planning",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_phase_budget_exhausted_total",
                type=MetricType.COUNTER,
                description="Budget exhaustion events per phase",
                labels=["phase"]
            )
        )

        # Faithfulness tracking for SLOs
        self.register_metric(
            MetricDefinition(
                name="rag_total_claims_checked_total",
                type=MetricType.COUNTER,
                description="Total claims evaluated during post-generation verification",
            )
        )

        # Quality evaluation (nightly eval set) - dashboard inputs
        self.register_metric(
            MetricDefinition(
                name="rag_eval_faithfulness_score",
                type=MetricType.GAUGE,
                description="Average faithfulness score (1 - unsupported_ratio) on eval set",
                labels=["dataset"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_eval_coverage_score",
                type=MetricType.GAUGE,
                description="Average citation coverage on eval set",
                labels=["dataset"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_eval_last_run_timestamp",
                type=MetricType.GAUGE,
                description="Last successful eval run UNIX timestamp",
                labels=["dataset"],
            )
        )

        # Generation gating due to low evidence after reranking calibration
        self.register_metric(
            MetricDefinition(
                name="rag_generation_gated_total",
                type=MetricType.COUNTER,
                description="Total number of times answer generation was gated due to low relevance probability",
                labels=["strategy"]
            )
        )

        # Content policy / sanitation metrics
        self.register_metric(
            MetricDefinition(
                name="rag_policy_filtered_chunks_total",
                type=MetricType.COUNTER,
                description="Documents affected by content policy (pii/phi)",
                labels=["mode"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_sanitized_docs_total",
                type=MetricType.COUNTER,
                description="Documents sanitized by HTML allow-list",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_ocr_dropped_docs_total",
                type=MetricType.COUNTER,
                description="Documents dropped due to low OCR confidence",
            )
        )

        # Generation guardrails
        self.register_metric(
            MetricDefinition(
                name="rag_injection_chunks_downweighted_total",
                type=MetricType.COUNTER,
                description="Total retrieved chunks downweighted due to instruction-injection risk",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_numeric_mismatches_total",
                type=MetricType.COUNTER,
                description="Total numeric tokens from answers not found in sources",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="rag_missing_hard_citations_total",
                type=MetricType.COUNTER,
                description="Total answers with missing supporting spans for one or more sentences",
            )
        )

        # Embedding metrics
        self.register_metric(
            MetricDefinition(
                name="embeddings_generated_total",
                type=MetricType.COUNTER,
                description="Total number of embeddings generated",
                labels=["provider", "model"]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="hyde_questions_generated_total",
                type=MetricType.COUNTER,
                description="Total HYDE/doc2query questions generated",
                labels=["provider", "model", "source"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="hyde_generation_failures_total",
                type=MetricType.COUNTER,
                description="Total HYDE/doc2query generation failures",
                labels=["provider", "model", "source", "reason"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="hyde_vectors_written_total",
                type=MetricType.COUNTER,
                description="Total HYDE/doc2query vectors written to storage",
                labels=["store"],
            )
        )

        # Upload metrics
        self.register_metric(
            MetricDefinition(
                name="uploads_total",
                type=MetricType.COUNTER,
                description="Total number of uploaded files",
                labels=["user_id", "media_type"]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="upload_bytes_total",
                type=MetricType.COUNTER,
                description="Total bytes uploaded",
                unit="bytes",
                labels=["user_id", "media_type"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="embedding_generation_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Embedding generation duration in seconds",
                unit="s",
                labels=["provider", "model"],
                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1]
            )
        )

        # System metrics
        self.register_metric(
            MetricDefinition(
                name="system_cpu_usage_percent",
                type=MetricType.GAUGE,
                description="System CPU usage percentage",
                unit="%"
            )
        )

        self.register_metric(
            MetricDefinition(
                name="system_memory_usage_bytes",
                type=MetricType.GAUGE,
                description="System memory usage in bytes",
                unit="bytes"
            )
        )

        self.register_metric(
            MetricDefinition(
                name="system_disk_usage_bytes",
                type=MetricType.GAUGE,
                description="System disk usage in bytes",
                unit="bytes",
                labels=["mount_point"]
            )
        )

        # Error metrics
        self.register_metric(
            MetricDefinition(
                name="errors_total",
                type=MetricType.COUNTER,
                description="Total number of errors",
                labels=["component", "error_type"]
            )
        )

        # Scraping metrics
        self.register_metric(
            MetricDefinition(
                name="scrape_fetch_total",
                type=MetricType.COUNTER,
                description="Total number of scrape fetch attempts",
                labels=["backend", "outcome"],  # outcome: success|no_extract|error
            )
        )
        self.register_metric(
            MetricDefinition(
                name="scrape_fetch_latency_seconds",
                type=MetricType.HISTOGRAM,
                description="Latency of scrape fetch path",
                unit="s",
                labels=["backend"],
                buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="scrape_playwright_fallback_total",
                type=MetricType.COUNTER,
                description="Total number of fallbacks to Playwright",
                labels=["reason"],  # reason: js_required|no_extract|error
            )
        )
        self.register_metric(
            MetricDefinition(
                name="scrape_blocked_by_robots_total",
                type=MetricType.COUNTER,
                description="Total scrapes blocked by robots policy",
                labels=["domain"],
            )
        )

        # Security metrics
        self.register_metric(
            MetricDefinition(
                name="security_ssrf_block_total",
                type=MetricType.COUNTER,
                description="Total number of outbound URL validations blocked (SSRF protection)",
            )
        )
        self.register_metric(
            MetricDefinition(
                name="security_headers_responses_total",
                type=MetricType.COUNTER,
                description="Total number of responses where security headers were applied",
            )
        )

        # Storage quota metrics (per user)
        self.register_metric(
            MetricDefinition(
                name="user_storage_used_mb",
                type=MetricType.GAUGE,
                description="Per-user storage used in MB",
                unit="MB",
                labels=["user_id"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="user_storage_quota_mb",
                type=MetricType.GAUGE,
                description="Per-user storage quota in MB",
                unit="MB",
                labels=["user_id"],
            )
        )

        # Circuit breaker metrics
        self.register_metric(
            MetricDefinition(
                name="circuit_breaker_state",
                type=MetricType.GAUGE,
                description="Circuit breaker state (0=closed, 1=open, 2=half-open)",
                labels=["service"]
            )
        )

        self.register_metric(
            MetricDefinition(
                name="circuit_breaker_trips_total",
                type=MetricType.COUNTER,
                description="Total circuit breaker trips",
                labels=["service", "reason"]
            )
        )

        # Prompt Studio metrics
        self.register_metric(
            MetricDefinition(
                name="prompt_studio_queue_depth",
                type=MetricType.GAUGE,
                description="Number of queued Prompt Studio jobs",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="prompt_studio_processing",
                type=MetricType.GAUGE,
                description="Number of processing Prompt Studio jobs",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="prompt_studio_leases_active",
                type=MetricType.GAUGE,
                description="Active leases for Prompt Studio jobs",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="prompt_studio_leases_expiring_soon",
                type=MetricType.GAUGE,
                description="Prompt Studio leases expiring soon",
                labels=["backend"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="prompt_studio_leases_stale_processing",
                type=MetricType.GAUGE,
                description="Processing jobs with missing/expired lease",
                labels=["backend"],
            )
        )

        # Agentic RAG metrics
        self.register_metric(
            MetricDefinition(
                name="agentic_tool_calls_total",
                type=MetricType.COUNTER,
                description="Total agentic tool calls",
                labels=["tool"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="agentic_tool_duration_seconds",
                type=MetricType.HISTOGRAM,
                description="Duration per agentic tool call",
                unit="s",
                labels=["tool"],
                buckets=[0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="agentic_cache_hits_total",
                type=MetricType.COUNTER,
                description="Total agentic cache hits",
                labels=["cache_type"],
            )
        )
        self.register_metric(
            MetricDefinition(
                name="agentic_span_length_chars",
                type=MetricType.HISTOGRAM,
                description="Histogram of agentic span lengths (chars)",
                unit="chars",
                labels=["phase"],
                buckets=[64, 128, 256, 512, 1024, 2048, 4096]
            )
        )
        self.register_metric(
            MetricDefinition(
                name="span_bytes_read_total",
                type=MetricType.COUNTER,
                description="Total bytes read while assembling spans",
                unit="bytes",
                labels=["tool"],
            )
        )

    def register_metric(self, definition: MetricDefinition) -> bool:
        """
        Register a new metric definition.

        Args:
            definition: MetricDefinition object

        Returns:
            True if registered successfully
        """
        if definition.name in self.metrics:
            logger.warning(f"Metric {definition.name} already registered")
            return False

        self.metrics[definition.name] = definition

        # Create OpenTelemetry instrument
        if OTEL_AVAILABLE and self.meter:
            instrument = self._create_instrument(definition)
            if instrument:
                self.instruments[definition.name] = instrument

        logger.debug(f"Registered metric: {definition.name}")
        return True

    def _create_instrument(self, definition: MetricDefinition):
        """Create an OpenTelemetry instrument for a metric definition."""
        try:
            if definition.type == MetricType.COUNTER:
                return self.meter.create_counter(
                    name=definition.name,
                    description=definition.description,
                    unit=definition.unit
                )

            elif definition.type == MetricType.GAUGE:
                # Gauges are handled via callbacks in OpenTelemetry
                return self.meter.create_observable_gauge(
                    name=definition.name,
                    description=definition.description,
                    unit=definition.unit,
                    callbacks=[lambda options: self._gauge_callback(definition.name, options)]
                )

            elif definition.type == MetricType.HISTOGRAM:
                # If custom buckets were defined, register a view before creating the instrument
                try:
                    if definition.buckets:
                        self.telemetry.register_histogram_view(definition.name, definition.buckets)
                except Exception:
                    pass
                return self.meter.create_histogram(
                    name=definition.name,
                    description=definition.description,
                    unit=definition.unit
                )

            elif definition.type == MetricType.UP_DOWN_COUNTER:
                return self.meter.create_up_down_counter(
                    name=definition.name,
                    description=definition.description,
                    unit=definition.unit
                )

        except Exception as e:
            logger.error(f"Failed to create instrument for {definition.name}: {e}")
            return None

    def _gauge_callback(self, metric_name: str, options: 'CallbackOptions'):
        """Callback for observable gauge metrics.

        Emits one Observation per distinct label set using the latest value
        recorded for that label set. This preserves label cardinality in OTel.
        """
        observations = []

        try:
            # Group latest value by label set
            latest_by_labels: Dict[str, MetricValue] = {}
            if metric_name in self.values:
                for mv in self.values[metric_name]:
                    # Build a stable key from sorted labels
                    label_key = ",".join(f"{k}={v}" for k, v in sorted(mv.labels.items()))
                    latest_by_labels[label_key] = mv

            for mv in latest_by_labels.values():
                observations.append(Observation(value=mv.value, attributes=mv.labels))
        except Exception as e:
            # Gauges must never break scrapes; return empty to avoid exporter errors
            logger.debug(f"Gauge callback error for {metric_name}: {e}")
        return observations

    def record(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Record a metric value.

        Args:
            metric_name: Name of the metric
            value: Value to record
            labels: Optional labels/dimensions
        """
        if metric_name not in self.metrics:
            logger.warning(f"Metric {metric_name} not registered")
            return

        definition = self.metrics[metric_name]
        labels = labels or {}

        # Store value for aggregation
        metric_value = MetricValue(value=value, labels=labels)
        self.values[metric_name].append(metric_value)

        # Record in OpenTelemetry
        if metric_name in self.instruments:
            instrument = self.instruments[metric_name]

            try:
                if definition.type == MetricType.COUNTER:
                    instrument.add(value, attributes=labels)

                elif definition.type == MetricType.HISTOGRAM:
                    instrument.record(value, attributes=labels)

                elif definition.type == MetricType.UP_DOWN_COUNTER:
                    instrument.add(value, attributes=labels)

                # Gauges are handled via callbacks

            except Exception as e:
                logger.error(f"Failed to record metric {metric_name}: {e}")

        # Execute callbacks
        for callback in self.callbacks[metric_name]:
            try:
                callback(metric_name, value, labels)
            except Exception as e:
                logger.error(f"Metric callback error: {e}")

    def increment(self, metric_name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.

        Args:
            metric_name: Name of the counter metric
            value: Amount to increment (default 1)
            labels: Optional labels
        """
        self.record(metric_name, value, labels)

    def set_gauge(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric value.

        Args:
            metric_name: Name of the gauge metric
            value: Value to set
            labels: Optional labels
        """
        self.record(metric_name, value, labels)

    def observe(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Observe a value for histogram metric.

        Args:
            metric_name: Name of the histogram metric
            value: Value to observe
            labels: Optional labels
        """
        self.record(metric_name, value, labels)

    @contextmanager
    def timer(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager to time an operation.

        Args:
            metric_name: Name of the histogram metric for timing
            labels: Optional labels

        Yields:
            Timer context
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.observe(metric_name, duration, labels)

    def add_callback(self, metric_name: str, callback: Callable):
        """
        Add a callback for metric events.

        Args:
            metric_name: Name of the metric
            callback: Callable(metric_name, value, labels)
        """
        self.callbacks[metric_name].append(callback)

    def get_metric_stats(self, metric_name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Get statistics for a metric.

        Args:
            metric_name: Name of the metric
            labels: Optional label filter

        Returns:
            Dictionary with metric statistics
        """
        if metric_name not in self.values:
            return {}

        # Filter values by labels if provided
        values = list(self.values[metric_name])
        if labels:
            # Filter by exact match on provided labels
            values = [val for val in values if all(
                val.labels.get(key) == expected for key, expected in labels.items()
            )]

        if not values:
            return {}

        numeric_values = [v.value for v in values]

        return {
            "count": len(numeric_values),
            "sum": sum(numeric_values),
            "mean": statistics.mean(numeric_values),
            "median": statistics.median(numeric_values),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "stddev": statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0,
            "latest": numeric_values[-1],
            "latest_timestamp": values[-1].timestamp
        }

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all current metric values and statistics.

        Returns:
            Dictionary of metric names to their statistics
        """
        result = {}

        for metric_name, definition in self.metrics.items():
            stats = self.get_metric_stats(metric_name)
            if stats:
                result[metric_name] = {
                    "type": definition.type.value,
                    "description": definition.description,
                    "unit": definition.unit,
                    "stats": stats
                }

        return result

    def export_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []

        for metric_name, definition in self.metrics.items():
            if metric_name not in self.values:
                continue

            # Add HELP and TYPE lines
            lines.append(f"# HELP {metric_name} {definition.description}")
            # Map internal metric types to Prometheus types
            prom_type = (
                "counter" if definition.type == MetricType.COUNTER else
                "gauge" if definition.type in (MetricType.GAUGE, MetricType.UP_DOWN_COUNTER) else
                "histogram" if definition.type == MetricType.HISTOGRAM else
                definition.type.value
            )
            lines.append(f"# TYPE {metric_name} {prom_type}")

            # Group values by labels
            label_groups = defaultdict(list)
            for value in self.values[metric_name]:
                label_key = ",".join(f'{k}="{v}"' for k, v in sorted(value.labels.items()))
                label_groups[label_key].append(value)

            # Export values
            for label_str, values in label_groups.items():
                if definition.type == MetricType.GAUGE:
                    # For gauges, use the latest value
                    latest = values[-1]
                    if label_str:
                        lines.append(f"{metric_name}{{{label_str}}} {latest.value}")
                    else:
                        lines.append(f"{metric_name} {latest.value}")

                elif definition.type in [MetricType.COUNTER, MetricType.UP_DOWN_COUNTER]:
                    # For counters, use the sum
                    total = sum(v.value for v in values)
                    if label_str:
                        lines.append(f"{metric_name}{{{label_str}}} {total}")
                    else:
                        lines.append(f"{metric_name} {total}")

                elif definition.type == MetricType.HISTOGRAM:
                    # For histograms, calculate buckets
                    numeric_values = [v.value for v in values]
                    if definition.buckets:
                        for bucket in definition.buckets:
                            count = sum(1 for v in numeric_values if v <= bucket)
                            bucket_label = f'le="{bucket}"'
                            if label_str:
                                lines.append(f"{metric_name}_bucket{{{label_str},{bucket_label}}} {count}")
                            else:
                                lines.append(f"{metric_name}_bucket{{{bucket_label}}} {count}")

                    # Add +Inf bucket, sum, and count
                    if label_str:
                        lines.append(f"{metric_name}_bucket{{{label_str},le=\"+Inf\"}} {len(numeric_values)}")
                        lines.append(f"{metric_name}_sum{{{label_str}}} {sum(numeric_values)}")
                        lines.append(f"{metric_name}_count{{{label_str}}} {len(numeric_values)}")
                    else:
                        lines.append(f"{metric_name}_bucket{{le=\"+Inf\"}} {len(numeric_values)}")
                        lines.append(f"{metric_name}_sum {sum(numeric_values)}")
                        lines.append(f"{metric_name}_count {len(numeric_values)}")

            # Emit alias series for cache_* metrics to rag_cache_* for consistency
            if metric_name in {"cache_hits_total", "cache_misses_total"}:
                alias_name = (
                    "rag_cache_hits_total" if metric_name == "cache_hits_total" else "rag_cache_misses_total"
                )
                # Only emit alias if rag_* has no own values recorded
                if alias_name not in self.values:
                    # HELP/TYPE for alias
                    lines.append(f"# HELP {alias_name} Aliased from {metric_name} for RAG cache consistency")
                    lines.append(f"# TYPE {alias_name} counter")
                    # Build alias series with label key remapped: cache -> cache_type
                    for label_str, values in label_groups.items():
                        # Rebuild labels mapping and rename key
                        # label_str format: key="val",key2="val2" ...
                        # Convert back to dict to manipulate keys
                        if label_str:
                            pairs = [s.split("=", 1) for s in label_str.split(",") if "=" in s]
                            label_dict = {k: v.strip('"') for k, v in pairs}
                        else:
                            label_dict = {}
                        if "cache" in label_dict:
                            label_dict["cache_type"] = label_dict.pop("cache")
                        # Serialize
                        alias_labels = ",".join(f"{k}=\"{v}\"" for k, v in sorted(label_dict.items()))
                        total = sum(v.value for v in values)
                        if alias_labels:
                            lines.append(f"{alias_name}{{{alias_labels}}} {total}")
                        else:
                            lines.append(f"{alias_name} {total}")

        return "\n".join(lines) + "\n"


# Global metrics registry instance
_metrics_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """
    Get or create the global metrics registry.

    Returns:
        MetricsRegistry instance
    """
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


# Convenience functions for common operations
def record_metric(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record a metric value."""
    get_metrics_registry().record(metric_name, value, labels)


def increment_counter(metric_name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
    """Increment a counter metric."""
    get_metrics_registry().increment(metric_name, value, labels)


def set_gauge(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Set a gauge metric value."""
    get_metrics_registry().set_gauge(metric_name, value, labels)


def observe_histogram(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Observe a value for histogram metric."""
    get_metrics_registry().observe(metric_name, value, labels)


@contextmanager
def time_operation(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Time an operation and record to histogram metric."""
    with get_metrics_registry().timer(metric_name, labels):
        yield
