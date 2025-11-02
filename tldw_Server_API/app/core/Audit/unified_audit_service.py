"""
Unified Audit Service for tldw_server

This module consolidates all audit logging functionality into a single,
consistent service that handles authentication, RAG, evaluations, and
general audit events.

Features:
- Async-first design with proper connection pooling
- Unified event schema across all modules
- Correlation IDs for request tracking
- PII detection and redaction
- Risk scoring and anomaly detection
- Configurable retention and rotation policies
- Export capabilities for compliance
"""

import asyncio
import csv
import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, time as time_t, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union
from uuid import uuid4

import aiosqlite

from loguru import logger
try:
    # Prefer dict-like project settings if available
    from tldw_Server_API.app.core.config import settings as _app_settings  # type: ignore
except Exception:
    _app_settings = {}

# Consistent risk threshold constants (tunable via env var)
try:
    HIGH_RISK_SCORE = int(os.getenv("AUDIT_HIGH_RISK_SCORE", "70"))
except Exception:
    HIGH_RISK_SCORE = 70


def _normalize_json_value(value: Any) -> Any:
    """Normalize arbitrary objects so they can be serialized as JSON."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time_t):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)

    if is_dataclass(value):
        try:
            return _normalize_json_value(asdict(value))
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(k): _normalize_json_value(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_normalize_json_value(v) for v in list(value)]

    if hasattr(value, "model_dump"):
        try:
            return _normalize_json_value(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            return _normalize_json_value(value.dict())
        except Exception:
            pass

    try:
        return json.loads(value)
    except Exception:
        pass

    return str(value)


# ============================================================================
# Event Types
# ============================================================================

class AuditEventCategory(Enum):
    """High-level audit event categories"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM = "system"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    API_CALL = "api_call"
    EVALUATION = "evaluation"
    RAG = "rag"


class AuditEventType(Enum):
    """Detailed audit event types"""
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_CREATED = "auth.token.created"
    AUTH_TOKEN_REFRESHED = "auth.token.refreshed"
    AUTH_TOKEN_REVOKED = "auth.token.revoked"
    AUTH_SESSION_EXPIRED = "auth.session.expired"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ACTIVATED = "user.activated"
    USER_DEACTIVATED = "user.deactivated"
    USER_PASSWORD_CHANGED = "user.password.changed"
    USER_PASSWORD_RESET = "user.password.reset"

    # Data Operations
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"

    # RAG Operations
    RAG_SEARCH = "rag.search"
    RAG_RETRIEVAL = "rag.retrieval"
    RAG_GENERATION = "rag.generation"
    RAG_INDEXING = "rag.indexing"
    RAG_EMBEDDING = "rag.embedding"

    # Evaluation Operations
    EVAL_STARTED = "eval.started"
    EVAL_COMPLETED = "eval.completed"
    EVAL_FAILED = "eval.failed"
    EVAL_COST_TRACKED = "eval.cost.tracked"

    # API Operations
    API_REQUEST = "api.request"
    API_RESPONSE = "api.response"
    API_ERROR = "api.error"
    API_RATE_LIMITED = "api.rate_limited"

    # Security Events
    SECURITY_VIOLATION = "security.violation"
    SECURITY_SCAN = "security.scan"
    PERMISSION_DENIED = "permission.denied"
    SUSPICIOUS_ACTIVITY = "suspicious.activity"
    PII_DETECTED = "pii.detected"

    # System Events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    CONFIG_CHANGED = "config.changed"
    MIGRATION_RUN = "migration.run"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class AuditContext:
    """Context information for audit events"""
    request_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    api_key_hash: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None


@dataclass
class AuditEvent:
    """Unified audit event structure"""
    # Core fields
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    category: AuditEventCategory = AuditEventCategory.SYSTEM
    event_type: AuditEventType = AuditEventType.SYSTEM_START
    severity: AuditSeverity = AuditSeverity.INFO

    # Context
    context: AuditContext = field(default_factory=AuditContext)

    # Event details
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    result: str = "success"  # success, failure, error
    error_message: Optional[str] = None

    # Metrics
    duration_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    estimated_cost: Optional[float] = None
    result_count: Optional[int] = None

    # Risk and compliance
    risk_score: int = 0  # 0-100
    pii_detected: bool = False
    compliance_flags: List[str] = field(default_factory=list)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        normalized_metadata = _normalize_json_value(self.metadata)
        normalized_flags = _normalize_json_value(self.compliance_flags)

        data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "result": self.result,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "estimated_cost": self.estimated_cost,
            "result_count": self.result_count,
            "risk_score": self.risk_score,
            "pii_detected": self.pii_detected,
            "compliance_flags": json.dumps(normalized_flags, ensure_ascii=False),
            "metadata": json.dumps(normalized_metadata, ensure_ascii=False),
        }

        # Add context fields
        context_dict = asdict(self.context)
        for key, value in context_dict.items():
            if value is None or isinstance(value, str):
                data[f"context_{key}"] = value
            else:
                data[f"context_{key}"] = str(value)

        return data


# ============================================================================
# PII Detection
# ============================================================================

class PIIDetector:
    """Enhanced PII detection with configurable patterns.

    Patterns may be extended/overridden via app settings and, optionally,
    merged with RAG security_filters patterns for consistency across modules.
    """

    # Default PII patterns (compiled)
    DEFAULT_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "passport": r"\b[A-Z]{1,2}[0-9]{6,9}\b",
        "driver_license": r"\b[A-Z]{1,2}[\s-]?\d{6,8}\b",
        "bank_account": r"\b\d{8,17}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b",
        "api_key": r"\b(?:sk|pk|api[_-]?key)[_-]?[A-Za-z0-9]{32,}\b",
        "jwt_token": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
    }

    # Back-compat for modules that read PIIDetector.PII_PATTERNS directly
    PII_PATTERNS = {k: re.compile(v) for k, v in DEFAULT_PATTERNS.items()}

    def __init__(self, *,
                 overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
                 use_rag_patterns: bool = False):
        # Compile patterns
        pat_map: Dict[str, List[re.Pattern]] = {}
        for name, raw in self.DEFAULT_PATTERNS.items():
            try:
                flags = re.IGNORECASE if name in {"api_key"} else 0
                pat_map[name] = [re.compile(raw, flags)]
            except Exception:
                pass

        # Optional: merge from RAG detector patterns
        if use_rag_patterns:
            try:
                from tldw_Server_API.app.core.RAG.rag_service.security_filters import PIIDetector as RAGPII, PIIType
                rag = RAGPII()
                # Map known types to our keys
                mapping = {
                    "email": PIIType.EMAIL,
                    "phone": PIIType.PHONE,
                    "ssn": PIIType.SSN,
                    "credit_card": PIIType.CREDIT_CARD,
                    "ip_address": PIIType.IP_ADDRESS,
                    "passport": PIIType.PASSPORT,
                    "bank_account": PIIType.BANK_ACCOUNT,
                }
                for k, t in mapping.items():
                    try:
                        pats = getattr(rag, "patterns", {}).get(t, [])
                        comp_list = [p for p in pats if isinstance(p, re.Pattern)]
                        if comp_list:
                            pat_map.setdefault(k, []).extend(comp_list)
                    except Exception:
                        pass
                logger.debug("Audit PII: merged patterns from RAG detector")
            except Exception:
                # Optional dependency; ignore if unavailable
                pass

        # Optional: overrides from settings
        if overrides:
            for name, raw in overrides.items():
                try:
                    if isinstance(raw, list):
                        compiled = [re.compile(r) for r in raw]
                    else:
                        compiled = [re.compile(str(raw))]
                    if compiled:
                        pat_map[name] = compiled
                except Exception as e:
                    logger.debug(f"Audit PII: failed to compile override for {name}: {e}")

        self._patterns: Dict[str, List[re.Pattern]] = pat_map

    def detect(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text"""
        if not text:
            return {}

        found: Dict[str, List[str]] = {}
        for pii_type, patterns in self._patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    found.setdefault(pii_type, []).extend(matches if isinstance(matches, list) else [matches])
        return found

    def redact(self, text: str, placeholder_format: str = "[{type}_REDACTED]") -> str:
        """Redact PII from text"""
        if not text:
            return text
        redacted = text
        for pii_type, patterns in self._patterns.items():
            placeholder = placeholder_format.format(type=pii_type.upper())
            for pattern in patterns:
                redacted = pattern.sub(placeholder, redacted)
        return redacted

    def _redact_value(self, value: Any, placeholder_format: str) -> Any:
        """Redact PII in a single value if it's a string."""
        if isinstance(value, str):
            redacted = value
            for pii_type, patterns in self._patterns.items():
                placeholder = placeholder_format.format(type=pii_type.upper())
                for pattern in patterns:
                    redacted = pattern.sub(placeholder, redacted)
            return redacted
        return value

    def redact_obj(self, data: Any, placeholder_format: str = "[{type}_REDACTED]") -> Any:
        """Recursively redact PII from dict/list structures and strings."""
        try:
            if isinstance(data, dict):
                return {k: self.redact_obj(v, placeholder_format) for k, v in data.items()}
            if isinstance(data, list):
                return [self.redact_obj(v, placeholder_format) for v in data]
            # Strings handled via value redaction; primitives returned as-is
            return self._redact_value(data, placeholder_format)
        except Exception:
            # Fallback safety: convert to string and redact
            try:
                return self._redact_value(str(data), placeholder_format)
            except Exception:
                return data


# ============================================================================
# Risk Scoring
# ============================================================================

class RiskScorer:
    """Calculate risk scores for audit events"""

    # High-risk operations
    HIGH_RISK_OPERATIONS = {
        "delete", "drop", "truncate", "export", "download",
        "change_password", "reset_password", "grant", "revoke",
        "modify_permissions", "create_admin", "delete_user"
    }

    # Default suspicious thresholds and toggles
    DEFAULT_SUSPICIOUS_THRESHOLDS = {
        "rapid_requests": 100,  # requests/minute threshold (unused in current scorer)
        "failed_auth": 3,       # consecutive failures threshold
        "data_export": 1000,    # result_count threshold considered large export
        "after_hours": True,    # apply time-of-day risk
        "unusual_location": True,  # reserved for future use
    }

    # Default action-specific bonuses to fine-tune risk semantics
    DEFAULT_ACTION_RISK_BONUS = {
        "sla_breached": 10,
        "quarantined": 10,
        "unauthorized_access": 10,
    }

    def __init__(self, action_bonus_overrides: Optional[Dict[str, int]] = None,
                 *,
                 high_risk_ops_override: Optional[Union[List[str], str]] = None,
                 suspicious_thresholds_override: Optional[Dict[str, Union[int, bool]]] = None) -> None:
        # Merge overrides from settings, then supplied overrides
        merged: Dict[str, int] = dict(self.DEFAULT_ACTION_RISK_BONUS)
        try:
            cfg = _app_settings.get("AUDIT_ACTION_RISK_BONUS", None)
            if isinstance(cfg, dict):
                for k, v in cfg.items():
                    try:
                        key = str(k).strip().lower()
                        val = int(v)
                        if key:
                            merged[key] = max(0, min(100, val))
                    except Exception:
                        continue
        except Exception:
            pass
        if isinstance(action_bonus_overrides, dict):
            for k, v in action_bonus_overrides.items():
                try:
                    key = str(k).strip().lower()
                    val = int(v)
                    if key:
                        merged[key] = max(0, min(100, val))
                except Exception:
                    continue
        self.action_risk_bonus: Dict[str, int] = merged

        # High-risk operations list (lowercase exact substring check)
        def _parse_ops(value: Union[List[str], str, None]) -> Set[str]:
            out: Set[str] = set()
            if value is None:
                return out
            if isinstance(value, str):
                parts = [p.strip() for p in value.split(',') if p.strip()]
            else:
                parts = [str(p).strip() for p in value if str(p).strip()]
            for p in parts:
                out.add(p.lower())
            return out

        default_ops = set(self.HIGH_RISK_OPERATIONS)
        try:
            cfg_ops = _app_settings.get("AUDIT_HIGH_RISK_OPERATIONS", None)
            ops_from_settings = _parse_ops(cfg_ops)
        except Exception:
            ops_from_settings = set()
        ops_from_arg = _parse_ops(high_risk_ops_override)
        self.high_risk_operations: Set[str] = set(map(str.lower, default_ops)) | ops_from_settings | ops_from_arg

        # Suspicious thresholds (numeric or boolean toggles)
        def _merge_thresholds(base: Dict[str, Union[int, bool]], val: Optional[Dict[str, Union[int, bool]]]) -> Dict[str, Union[int, bool]]:
            merged_thr = dict(base)
            if isinstance(val, dict):
                for k, v in val.items():
                    key = str(k).strip()
                    if not key:
                        continue
                    if isinstance(v, bool):
                        merged_thr[key] = v
                    else:
                        try:
                            merged_thr[key] = int(v)  # type: ignore[assignment]
                        except Exception:
                            continue
            return merged_thr

        thresholds = dict(self.DEFAULT_SUSPICIOUS_THRESHOLDS)
        try:
            cfg_thr = _app_settings.get("AUDIT_SUSPICIOUS_THRESHOLDS", None)
            thresholds = _merge_thresholds(thresholds, cfg_thr if isinstance(cfg_thr, dict) else None)
        except Exception:
            pass
        thresholds = _merge_thresholds(thresholds, suspicious_thresholds_override)
        self.suspicious_thresholds: Dict[str, Union[int, bool]] = thresholds

    def calculate_risk_score(self, event: AuditEvent) -> int:
        """Calculate risk score for an event (0-100)"""
        score = 0

        # Event type risk
        if event.event_type in [
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.SYSTEM_ERROR,
        ]:
            score += 50
        elif event.event_type in [
            AuditEventType.AUTH_LOGIN_FAILURE,
            AuditEventType.DATA_DELETE,
            AuditEventType.CONFIG_CHANGED
        ]:
            score += 30

        # Failed operations
        if event.result == "failure":
            score += 20
        elif event.result == "error":
            score += 10

        # High-risk operations
        if event.action and any(op in event.action.lower() for op in self.high_risk_operations):
            score += 30

        # PII detection
        if event.pii_detected:
            score += 25

        # Time-based risk (after hours)
        # Toggleable after-hours risk
        if bool(self.suspicious_thresholds.get("after_hours", True)):
            hour = event.timestamp.hour
            if hour < 6 or hour > 22:
                score += 10

        # Weekend activity
        if event.timestamp.weekday() >= 5:
            score += 5

        # Multiple consecutive failures (from metadata)
        metadata: Dict[str, Any] = {}
        raw_metadata = event.metadata
        if isinstance(raw_metadata, dict):
            metadata = raw_metadata
        elif isinstance(raw_metadata, str):
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    metadata = parsed
            except Exception:
                metadata = {}
        elif isinstance(raw_metadata, (list, tuple)):
            try:
                metadata = dict(raw_metadata)  # type: ignore[arg-type]
            except Exception:
                metadata = {}
        else:
            try:
                metadata = dict(raw_metadata)  # type: ignore[arg-type]
            except Exception:
                metadata = {}

        failed_thr = 3
        try:
            v = self.suspicious_thresholds.get("failed_auth", 3)  # type: ignore[assignment]
            failed_thr = int(v) if not isinstance(v, bool) else 3
        except Exception:
            failed_thr = 3
        if metadata.get("consecutive_failures", 0) > failed_thr:
            score += 20

        # Large data operations
        export_thr = 1000
        try:
            v2 = self.suspicious_thresholds.get("data_export", 1000)  # type: ignore[assignment]
            export_thr = int(v2) if not isinstance(v2, bool) else 1000
        except Exception:
            export_thr = 1000
        if event.result_count and event.result_count > export_thr:
            score += 15

        # Action-specific adjustments (case-insensitive exact match on action label)
        if event.action:
            bonus = self.action_risk_bonus.get(event.action.lower())
            if bonus:
                score += int(bonus)

        return min(score, 100)


# ============================================================================
# Unified Audit Service
# ============================================================================

class UnifiedAuditService:
    """
    Unified audit service with async operations, connection pooling,
    and comprehensive event tracking.

    Notes:
    - Timestamps are stored as ISO8601 strings; SQLite filters rely on
      lexicographic ordering which is correct for ISO8601.
    - `metadata` and `compliance_flags` are stored as JSON-encoded text
      and should be decoded by consumers when needed.
    - PII detection patterns may diverge from other modules; consider
      centralizing shared PII utilities across the codebase.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        retention_days: int = 90,
        enable_pii_detection: bool = True,
        enable_risk_scoring: bool = True,
        buffer_size: int = 1000,
        flush_interval: float = 10.0,
        max_db_mb: Optional[int] = None,
    ):
        """
        Initialize unified audit service.

        Args:
            db_path: Path to audit database
            retention_days: Days to retain audit logs
            enable_pii_detection: Enable PII detection
            enable_risk_scoring: Enable risk scoring
            buffer_size: Maximum events to buffer before flush
            flush_interval: Seconds between automatic flushes
        """
        # Configuration
        if db_path is None:
            db_dir = Path("./Databases")
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "unified_audit.db"

        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.enable_pii_detection = enable_pii_detection
        self.enable_risk_scoring = enable_risk_scoring
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.max_db_mb = max_db_mb
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None

        # Detect test environments to avoid spawning busy background loops when
        # tests monkeypatch asyncio.sleep globally (common in our Workflows tests).
        # In these contexts we disable background tasks entirely and prefer
        # direct/on-demand flushing via log_event/flush.
        try:
            self._test_mode = any(
                (os.getenv(k, "").strip().lower() in {"1", "true", "yes", "on"})
                for k in ("TEST_MODE", "TLDW_TEST_MODE")
            ) or (os.getenv("PYTEST_CURRENT_TEST") is not None)
        except Exception:
            self._test_mode = False

        # Components
        # Configure PII detector and scan fields
        if enable_pii_detection:
            # Settings: AUDIT_PII_USE_RAG_PATTERNS, AUDIT_PII_PATTERNS (dict)
            use_rag = bool(str(_app_settings.get("AUDIT_PII_USE_RAG_PATTERNS", "false")).strip().lower() in {"1","true","yes","on","y"})
            # Pull overrides from settings if present (no dict-type gate; LazySettings isn't a dict)
            overrides = _app_settings.get("AUDIT_PII_PATTERNS", None)
            if overrides is not None and not isinstance(overrides, dict):
                overrides = None
            self.pii_detector = PIIDetector(overrides=overrides, use_rag_patterns=use_rag)
        else:
            self.pii_detector = None

        # Fields to scan for PII beyond metadata (strings only)
        default_scan = ["action", "resource_id", "error_message", "context_user_agent"]
        extra_scan = []
        try:
            # Allow comma-separated string or list from settings
            raw = _app_settings.get("AUDIT_PII_SCAN_FIELDS", None)
            if isinstance(raw, str):
                extra_scan = [s.strip() for s in raw.split(",") if s.strip()]
            elif isinstance(raw, list):
                extra_scan = [str(s).strip() for s in raw if str(s).strip()]
        except Exception:
            pass
        self._pii_scan_fields: List[str] = list(dict.fromkeys(default_scan + extra_scan))
        self.risk_scorer = RiskScorer() if enable_risk_scoring else None

        # Event buffer
        self.event_buffer: List[AuditEvent] = []
        self.buffer_lock = asyncio.Lock()

        # Background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Connection pool
        self._db_pool: Optional[aiosqlite.Connection] = None
        self._pool_lock = asyncio.Lock()
        self._db_lock = asyncio.Lock()

        # Ad-hoc flush tasks created for high-risk/buffer-full conditions
        # Tracked so they can be awaited during graceful shutdown
        self._flush_futures: Set[asyncio.Task] = set()

        # Statistics
        self.stats = {
            "events_logged": 0,
            "events_flushed": 0,
            "flush_failures": 0,
            "high_risk_events": 0
        }

    async def initialize(self):
        """Initialize database and start background tasks"""
        self._owner_loop = asyncio.get_running_loop()
        await self._init_database()
        # In test mode, avoid opening a persistent pooled connection to prevent
        # lingering aiosqlite worker threads that can keep the interpreter alive.
        # Non-test mode uses a pooled connection for performance.
        if not self._test_mode:
            await self._ensure_db_pool()
        # Avoid starting background tasks in test environments where asyncio.sleep
        # may be monkeypatched to return immediately, which would otherwise cause
        # tight loops and starve the event loop.
        if not self._test_mode:
            await self.start_background_tasks()

    async def _init_database(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            # Apply performance/safety PRAGMAs for SQLite
            try:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute("PRAGMA synchronous=NORMAL;")
                await db.execute("PRAGMA temp_store=MEMORY;")
                await db.execute("PRAGMA foreign_keys=ON;")
                # Enable incremental vacuum to reclaim space over time
                try:
                    await db.execute("PRAGMA auto_vacuum=INCREMENTAL;")
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Failed to apply SQLite PRAGMAs on audit DB: {e}")
            # Main audit table with all fields
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,

                    -- Context fields
                    context_request_id TEXT,
                    context_correlation_id TEXT,
                    context_session_id TEXT,
                    context_user_id TEXT,
                    context_api_key_hash TEXT,
                    context_ip_address TEXT,
                    context_user_agent TEXT,
                    context_endpoint TEXT,
                    context_method TEXT,

                    -- Event details
                    resource_type TEXT,
                    resource_id TEXT,
                    action TEXT,
                    result TEXT,
                    error_message TEXT,

                    -- Metrics
                    duration_ms REAL,
                    tokens_used INTEGER,
                    estimated_cost REAL,
                    result_count INTEGER,

                    -- Risk and compliance
                    risk_score INTEGER,
                    pii_detected BOOLEAN,
                    compliance_flags TEXT,

                    -- Metadata
                    metadata TEXT
                )
            """)

            # Create indexes for common queries
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_events(context_user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_request_id ON audit_events(context_request_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_correlation_id ON audit_events(context_correlation_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_category ON audit_events(category)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_severity ON audit_events(severity)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_risk_score ON audit_events(risk_score)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_ip ON audit_events(context_ip_address)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON audit_events(context_session_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_endpoint ON audit_events(context_endpoint)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_agent ON audit_events(context_user_agent)")
            # Additional indexes for common resource/action filters
            await db.execute("CREATE INDEX IF NOT EXISTS idx_resource_type ON audit_events(resource_type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_resource_id ON audit_events(resource_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_action ON audit_events(action)")

            # Daily statistics table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_daily_stats (
                    date DATE NOT NULL,
                    category TEXT NOT NULL,
                    total_events INTEGER DEFAULT 0,
                    high_risk_events INTEGER DEFAULT 0,
                    failed_events INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0.0,
                    total_tokens INTEGER DEFAULT 0,
                    avg_duration_ms REAL,
                    PRIMARY KEY (date, category)
                )
            """)

            await db.commit()

    async def _ensure_db_pool(self) -> aiosqlite.Connection:
        """Ensure a persistent aiosqlite connection is available."""
        # In test mode, prefer ephemeral connections; callers of this method are
        # adjusted to bypass pooling when self._test_mode is True. Keep behavior
        # here for non-test callers.
        async with self._pool_lock:
            if self._db_pool is None:
                self._db_pool = await aiosqlite.connect(self.db_path)
                try:
                    await self._db_pool.execute("PRAGMA journal_mode=WAL;")
                    await self._db_pool.execute("PRAGMA synchronous=NORMAL;")
                    await self._db_pool.execute("PRAGMA temp_store=MEMORY;")
                    await self._db_pool.execute("PRAGMA foreign_keys=ON;")
                    await self._db_pool.execute("PRAGMA busy_timeout=5000;")
                    # Return rows as mappings consistently across this service
                    self._db_pool.row_factory = aiosqlite.Row
                    await self._db_pool.commit()
                except Exception as e:
                    logger.warning(f"Failed to apply PRAGMAs on pooled audit DB connection: {e}")
        return self._db_pool  # type: ignore[return-value]

    async def start_background_tasks(self):
        """Start background flush and cleanup tasks"""
        if not self._flush_task:
            self._flush_task = asyncio.create_task(self._flush_loop())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop background tasks and flush remaining events"""
        current_loop = asyncio.get_running_loop()
        owner_closed = False
        try:
            owner_closed = bool(self._owner_loop and self._owner_loop.is_closed())
        except Exception:
            owner_closed = False
        # Enforce same-loop shutdown only when the owner loop is still alive.
        if self._owner_loop and (not owner_closed) and current_loop is not self._owner_loop:
            raise RuntimeError("UnifiedAuditService.stop must run on the owner event loop")
        # Cancel background tasks
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Await any outstanding ad-hoc flushes first to avoid contention
        if self._flush_futures:
            try:
                await asyncio.gather(*list(self._flush_futures), return_exceptions=True)
            finally:
                self._flush_futures.clear()

        # If the owner loop has been closed, a pooled aiosqlite connection created
        # on that loop may not be usable here. Close and recreate on the current loop
        # before performing the final flush.
        if owner_closed and self._db_pool:
            try:
                await self._db_pool.close()
            except Exception:
                pass
            finally:
                self._db_pool = None

        # Final flush of any remaining buffered events
        try:
            await self.flush()
        except Exception as _e:
            # During teardown it's acceptable to skip the final flush if the event loop
            # or DB is no longer available.
            logger.debug(f"Audit final flush skipped due to shutdown condition: {_e}")

        # Close connection pool
        if self._db_pool:
            await self._db_pool.close()
            self._db_pool = None
        self._owner_loop = None

    @property
    def owner_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._owner_loop

    async def _flush_loop(self):
        """Background task to periodically flush events"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit flush loop: {e}")

    async def _cleanup_loop(self):
        """Background task to clean up old logs"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                await self.cleanup_old_logs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit cleanup loop: {e}")

    async def log_event(
        self,
        event_type: AuditEventType,
        context: Optional[AuditContext] = None,
        category: Optional[AuditEventCategory] = None,
        severity: Optional[AuditSeverity] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        result_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event.

        Returns:
            Event ID of the logged event
        """
        # Auto-determine category if not provided
        if category is None:
            category = self._determine_category(event_type)

        # Auto-determine severity if not provided
        if severity is None:
            severity = self._determine_severity(event_type, result)

        # Create context if not provided
        if context is None:
            context = AuditContext()

        # Create event
        event = AuditEvent(
            category=category,
            event_type=event_type,
            severity=severity,
            context=context,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            error_message=error_message,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            result_count=result_count,
            metadata=metadata or {}
        )

        # PII detection
        if self.enable_pii_detection:
            # Detect/redact in metadata
            if metadata is not None:
                try:
                    normalized_for_detection = _normalize_json_value(metadata)
                    metadata_str = json.dumps(normalized_for_detection, ensure_ascii=False)
                except Exception:
                    metadata_str = str(metadata)
                found_pii = self.pii_detector.detect(metadata_str)
                if found_pii:
                    event.pii_detected = True
                    if "pii_detected" not in event.compliance_flags:
                        event.compliance_flags.append("pii_detected")
                    # Redact PII from metadata preserving structure when possible
                    if isinstance(metadata, (dict, list, str)):
                        event.metadata = self.pii_detector.redact_obj(metadata)
                    else:
                        # For non-JSON-serializable metadata, store a JSON object with redacted text
                        redacted_str = self.pii_detector.redact(metadata_str)
                        event.metadata = {"redacted_text": redacted_str}
            # Detect/redact in configured string fields outside metadata
            def _redact_if_needed(val: Optional[str]) -> Optional[str]:
                if isinstance(val, str) and val:
                    red = self.pii_detector.redact(val)
                    if red != val:
                        event.pii_detected = True
                        if "pii_detected" not in event.compliance_flags:
                            event.compliance_flags.append("pii_detected")
                        return red
                return val

            for field_name in self._pii_scan_fields:
                try:
                    if field_name.startswith("context_"):
                        ctx_attr = field_name[len("context_"):]
                        cur = getattr(event.context, ctx_attr, None)
                        new_val = _redact_if_needed(cur)
                        if new_val is not None and new_val != cur:
                            setattr(event.context, ctx_attr, new_val)
                    else:
                        cur = getattr(event, field_name, None)
                        new_val = _redact_if_needed(cur)
                        if new_val is not None and new_val != cur:
                            setattr(event, field_name, new_val)
                except Exception:
                    # Ignore unknown fields
                    pass

        # Risk scoring
        if self.enable_risk_scoring:
            event.risk_score = self.risk_scorer.calculate_risk_score(event)
            if event.risk_score >= HIGH_RISK_SCORE:
                self.stats["high_risk_events"] += 1
                logger.warning(
                    f"High-risk event: {event_type.value} "
                    f"(risk: {event.risk_score}, user: {context.user_id})"
                )

        # Add to buffer
        async with self.buffer_lock:
            self.event_buffer.append(event)
            self.stats["events_logged"] += 1

            # Flush if buffer is full or high-risk event
            if len(self.event_buffer) >= self.buffer_size or event.risk_score >= HIGH_RISK_SCORE:
                task = asyncio.create_task(self.flush())
                # Track and auto-remove on completion
                self._flush_futures.add(task)
                task.add_done_callback(lambda t: self._flush_futures.discard(t))

        return event.event_id

    async def log_login(
        self,
        user_id: Union[int, str],
        username: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        session_id: Optional[str] = None,
    ) -> str:
        """Convenience helper to log login success/failure events."""
        ctx = AuditContext(
            user_id=str(user_id) if user_id is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
        return await self.log_event(
            event_type=(
                AuditEventType.AUTH_LOGIN_SUCCESS if success else AuditEventType.AUTH_LOGIN_FAILURE
            ),
            context=ctx,
            metadata={"username": username},
        )

    async def flush(self):
        """Flush buffered events to database"""
        async with self.buffer_lock:
            if not self.event_buffer:
                return

            events = self.event_buffer.copy()
            self.event_buffer.clear()

        try:
            max_retries = 3
            backoff_base = 0.05  # 50ms base
            last_error: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    if self._test_mode:
                        # Ephemeral connection per flush in tests to avoid persistent threads
                        async with aiosqlite.connect(self.db_path) as db:
                            try:
                                await db.execute("PRAGMA journal_mode=WAL;")
                                await db.execute("PRAGMA synchronous=NORMAL;")
                                await db.execute("PRAGMA temp_store=MEMORY;")
                                await db.execute("PRAGMA foreign_keys=ON;")
                                await db.execute("PRAGMA busy_timeout=5000;")
                                db.row_factory = aiosqlite.Row
                            except Exception:
                                pass
                            # Prepare batch data
                            records = [event.to_dict() for event in events]
                            await db.executemany(
                                """
                                INSERT OR IGNORE INTO audit_events (
                                    event_id, timestamp, category, event_type, severity,
                                    context_request_id, context_correlation_id, context_session_id,
                                    context_user_id, context_api_key_hash, context_ip_address,
                                    context_user_agent, context_endpoint, context_method,
                                    resource_type, resource_id, action, result, error_message,
                                    duration_ms, tokens_used, estimated_cost, result_count,
                                    risk_score, pii_detected, compliance_flags, metadata
                                ) VALUES (
                                    :event_id, :timestamp, :category, :event_type, :severity,
                                    :context_request_id, :context_correlation_id, :context_session_id,
                                    :context_user_id, :context_api_key_hash, :context_ip_address,
                                    :context_user_agent, :context_endpoint, :context_method,
                                    :resource_type, :resource_id, :action, :result, :error_message,
                                    :duration_ms, :tokens_used, :estimated_cost, :result_count,
                                    :risk_score, :pii_detected, :compliance_flags, :metadata
                                )
                                """,
                                records,
                            )
                            await self._update_daily_stats(db, events)
                            await db.commit()
                    else:
                        db = await self._ensure_db_pool()
                        async with self._db_lock:
                            # Prepare batch data
                            records = [event.to_dict() for event in events]

                            # Batch insert
                            await db.executemany(
                                """
                                INSERT OR IGNORE INTO audit_events (
                                    event_id, timestamp, category, event_type, severity,
                                    context_request_id, context_correlation_id, context_session_id,
                                    context_user_id, context_api_key_hash, context_ip_address,
                                    context_user_agent, context_endpoint, context_method,
                                    resource_type, resource_id, action, result, error_message,
                                    duration_ms, tokens_used, estimated_cost, result_count,
                                    risk_score, pii_detected, compliance_flags, metadata
                                ) VALUES (
                                    :event_id, :timestamp, :category, :event_type, :severity,
                                    :context_request_id, :context_correlation_id, :context_session_id,
                                    :context_user_id, :context_api_key_hash, :context_ip_address,
                                    :context_user_agent, :context_endpoint, :context_method,
                                    :resource_type, :resource_id, :action, :result, :error_message,
                                    :duration_ms, :tokens_used, :estimated_cost, :result_count,
                                    :risk_score, :pii_detected, :compliance_flags, :metadata
                                )
                                """,
                                records,
                            )

                            # Update daily statistics
                            await self._update_daily_stats(db, events)
                            await db.commit()

                    # Success
                    self.stats["events_flushed"] += len(events)
                    logger.debug(f"Flushed {len(events)} audit events to database")
                    last_error = None
                    break
                except aiosqlite.OperationalError as oe:  # type: ignore[attr-defined]
                    last_error = oe
                    msg = str(oe).lower()
                    if ("database is locked" in msg or "database locked" in msg) and attempt < max_retries - 1:
                        await asyncio.sleep(backoff_base * (attempt + 1))
                        continue
                    raise
                except Exception as e:
                    last_error = e
                    raise
        except Exception as e:
            logger.error(f"Failed to flush audit events: {e}")
            self.stats["flush_failures"] += 1

            # Re-add events to buffer (with limit to prevent memory issues)
            async with self.buffer_lock:
                max_buffer = self.buffer_size * 2
                combined = events + self.event_buffer
                dropped = max(0, len(combined) - max_buffer)
                if dropped > 0:
                    # Persist dropped events to a fallback JSONL queue for durability
                    try:
                        fb_path = self.db_path.parent / "audit_fallback_queue.jsonl"
                        self.db_path.parent.mkdir(parents=True, exist_ok=True)
                        with fb_path.open("a", encoding="utf-8") as fb:
                            for ev in combined[max_buffer:]:
                                fb.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
                        logger.warning(
                            f"Audit flush failure: {dropped} events persisted to fallback queue at {fb_path}"
                        )
                    except Exception as _fe:
                        logger.error(f"Failed to write dropped audit events to fallback queue: {_fe}")
                else:
                    logger.warning("Audit flush failure: events re-buffered (no drop)")
                self.event_buffer = combined[:max_buffer]

    async def _update_daily_stats(self, db: aiosqlite.Connection, events: List[AuditEvent]):
        """Update daily statistics"""
        from collections import defaultdict

        # Aggregate by date and category
        stats = defaultdict(lambda: {
            "total": 0, "high_risk": 0, "failed": 0,
            "cost": 0.0, "tokens": 0, "durations": []
        })

        for event in events:
            date = event.timestamp.date()
            key = (date, event.category.value)

            stats[key]["total"] += 1
            if event.risk_score >= HIGH_RISK_SCORE:
                stats[key]["high_risk"] += 1
            if event.result != "success":
                stats[key]["failed"] += 1
            if event.estimated_cost:
                stats[key]["cost"] += event.estimated_cost
            if event.tokens_used:
                stats[key]["tokens"] += event.tokens_used
            if event.duration_ms:
                stats[key]["durations"].append(event.duration_ms)

        # Update database
        for (date, category), data in stats.items():
            avg_duration = (
                sum(data["durations"]) / len(data["durations"])
                if data["durations"] else None
            )

            await db.execute("""
                INSERT INTO audit_daily_stats (
                    date, category, total_events, high_risk_events,
                    failed_events, total_cost, total_tokens, avg_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, category) DO UPDATE SET
                    total_events = total_events + excluded.total_events,
                    high_risk_events = high_risk_events + excluded.high_risk_events,
                    failed_events = failed_events + excluded.failed_events,
                    total_cost = total_cost + excluded.total_cost,
                    total_tokens = total_tokens + excluded.total_tokens,
                    avg_duration_ms = COALESCE(
                        (avg_duration_ms * total_events + excluded.avg_duration_ms * excluded.total_events)
                        / (total_events + excluded.total_events),
                        excluded.avg_duration_ms
                    )
            """, (
                date, category, data["total"], data["high_risk"],
                data["failed"], data["cost"], data["tokens"], avg_duration
            ))

    async def cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

        try:
            db = await self._ensure_db_pool()
            async with self._db_lock:
                # Count rows to be deleted for reliable logging (SQLite rowcount often -1)
                old_events_count = 0
                old_stats_count = 0
                try:
                    async with db.execute(
                        "SELECT COUNT(*) FROM audit_events WHERE timestamp < ?",
                        (cutoff.isoformat(),),
                    ) as cur:
                        row = await cur.fetchone()
                        old_events_count = int(row[0]) if row else 0
                except Exception:
                    pass

                try:
                    async with db.execute(
                        "SELECT COUNT(*) FROM audit_daily_stats WHERE date < ?",
                        (cutoff.date(),),
                    ) as cur:
                        row = await cur.fetchone()
                        old_stats_count = int(row[0]) if row else 0
                except Exception:
                    pass

                # Perform deletions
                await db.execute(
                    "DELETE FROM audit_events WHERE timestamp < ?",
                    (cutoff.isoformat(),)
                )
                await db.execute(
                    "DELETE FROM audit_daily_stats WHERE date < ?",
                    (cutoff.date(),)
                )
                await db.commit()

                # Reclaim space from deleted pages using incremental vacuum
                try:
                    await db.execute("PRAGMA incremental_vacuum")
                except Exception:
                    pass

                if old_events_count or old_stats_count:
                    logger.info(
                        "Cleaned up {events} audit events and {stats} daily stat rows older than {days} days".format(
                            events=old_events_count, stats=old_stats_count, days=self.retention_days
                        )
                    )

                # Optional: max DB size policy (warn if exceeded)
                try:
                    if hasattr(self, "max_db_mb") and self.max_db_mb:
                        size_mb = (self.db_path.stat().st_size / (1024 * 1024))
                        if size_mb > float(self.max_db_mb):
                            logger.warning(f"Audit DB size {size_mb:.1f}MB exceeds configured limit {self.max_db_mb}MB")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")

    async def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        categories: Optional[List[AuditEventCategory]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        min_risk_score: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query audit events with filters"""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend([et.value for et in event_types])

        if categories:
            placeholders = ",".join("?" * len(categories))
            query += f" AND category IN ({placeholders})"
            params.extend([c.value for c in categories])

        if user_id:
            query += " AND context_user_id = ?"
            params.append(user_id)

        if request_id:
            query += " AND context_request_id = ?"
            params.append(request_id)

        if correlation_id:
            query += " AND context_correlation_id = ?"
            params.append(correlation_id)

        if ip_address:
            query += " AND context_ip_address = ?"
            params.append(ip_address)
        if session_id:
            query += " AND context_session_id = ?"
            params.append(session_id)
        if endpoint:
            query += " AND context_endpoint = ?"
            params.append(endpoint)
        if method:
            query += " AND context_method = ?"
            params.append(method)

        if min_risk_score is not None:
            query += " AND risk_score >= ?"
            params.append(min_risk_score)

        query += " ORDER BY timestamp DESC, event_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            if self._test_mode:
                async with aiosqlite.connect(self.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(query, params) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
            else:
                db = await self._ensure_db_pool()
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")
            return []

    async def count_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        categories: Optional[List[AuditEventCategory]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        min_risk_score: Optional[int] = None,
    ) -> int:
        """Count audit events with filters."""
        query = "SELECT COUNT(*) as cnt FROM audit_events WHERE 1=1"
        params: List[Any] = []
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend([et.value for et in event_types])
        if categories:
            placeholders = ",".join("?" * len(categories))
            query += f" AND category IN ({placeholders})"
            params.extend([c.value for c in categories])
        if user_id:
            query += " AND context_user_id = ?"
            params.append(user_id)
        if request_id:
            query += " AND context_request_id = ?"
            params.append(request_id)
        if correlation_id:
            query += " AND context_correlation_id = ?"
            params.append(correlation_id)
        if ip_address:
            query += " AND context_ip_address = ?"
            params.append(ip_address)
        if session_id:
            query += " AND context_session_id = ?"
            params.append(session_id)
        if endpoint:
            query += " AND context_endpoint = ?"
            params.append(endpoint)
        if method:
            query += " AND context_method = ?"
            params.append(method)
        if min_risk_score is not None:
            query += " AND risk_score >= ?"
            params.append(min_risk_score)
        try:
            if self._test_mode:
                async with aiosqlite.connect(self.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(query, params) as cursor:
                        row = await cursor.fetchone()
                        return int(row[0]) if row else 0
            else:
                db = await self._ensure_db_pool()
                async with db.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    return int(row[0]) if row else 0
        except Exception as e:
            logger.error(f"Failed to count audit events: {e}")
            return 0

    async def export_events(
        self,
        *,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        categories: Optional[List[AuditEventCategory]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        min_risk_score: Optional[int] = None,
        format: str = "json",
        file_path: Optional[Union[str, Path]] = None,
        chunk_size: int = 5000,
        stream: bool = False,
        max_rows: Optional[int] = None,
    ) -> Union[str, int, AsyncGenerator[str, None]]:
        """
        Export audit events to JSON or CSV for compliance/reporting.

        Args:
            start_time: Filter start time
            end_time: Filter end time
            event_types: List of event types to include
            categories: List of categories to include
            user_id: Only events for this user_id
            request_id: Only events for this request
            correlation_id: Only events for this correlation
            min_risk_score: Minimum risk score to include
            format: 'json' or 'csv'
            file_path: If provided, write to this path; otherwise return content string
            chunk_size: Batch size when scanning DB

        Returns:
            If file_path is None: the exported content as a string
            If file_path is provided: the number of rows written
        """
        fmt = (format or "json").lower()
        if fmt not in {"json", "csv", "jsonl"}:
            raise ValueError("format must be 'json', 'csv', or 'jsonl'")

        # Fixed CSV header schema for consistency across export paths
        CSV_HEADERS: List[str] = [
            "event_id", "timestamp", "category", "event_type", "severity",
            "context_request_id", "context_correlation_id", "context_session_id",
            "context_user_id", "context_api_key_hash", "context_ip_address",
            "context_user_agent", "context_endpoint", "context_method",
            "resource_type", "resource_id", "action", "result", "error_message",
            "duration_ms", "tokens_used", "estimated_cost", "result_count",
            "risk_score", "pii_detected", "compliance_flags", "metadata",
        ]

        # Streaming CSV export when writing to a file to reduce memory usage
        if fmt == "csv" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            rows_written = 0

            with p.open("w", encoding="utf-8", newline="") as f:
                writer = None
                offset = 0
                while True:
                    chunk = await self.query_events(
                        start_time=start_time,
                        end_time=end_time,
                        event_types=event_types,
                        categories=categories,
                        user_id=user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        ip_address=ip_address,
                        session_id=session_id,
                        endpoint=endpoint,
                        method=method,
                        min_risk_score=min_risk_score,
                        limit=chunk_size,
                        offset=offset,
                    )
                    if not chunk:
                        break
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
                        writer.writeheader()
                    for r in chunk:
                        writer.writerow(r)
                        rows_written += 1
                    if len(chunk) < chunk_size:
                        break
                    offset += chunk_size
            return rows_written

        # Streaming JSON/JSONL response to the caller when requested (no prefetch)
        if fmt in {"json", "jsonl"} and file_path is None and stream:
            async def _json_streamer():
                is_jsonl = (fmt == "jsonl")
                if not is_jsonl:
                    yield "["
                first = True
                offset = 0
                written = 0
                while True:
                    rows = await self.query_events(
                        start_time=start_time,
                        end_time=end_time,
                        event_types=event_types,
                        categories=categories,
                        user_id=user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        ip_address=ip_address,
                        session_id=session_id,
                        endpoint=endpoint,
                        method=method,
                        min_risk_score=min_risk_score,
                        limit=chunk_size,
                        offset=offset,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        if is_jsonl:
                            yield json.dumps(r, ensure_ascii=False) + "\n"
                        else:
                            if not first:
                                yield ","
                            yield json.dumps(r, ensure_ascii=False)
                            first = False
                        written += 1
                    # backpressure: yield control
                    await asyncio.sleep(0)
                    if len(rows) < chunk_size:
                        break
                    offset += chunk_size
                if not is_jsonl:
                    yield "]"
            return _json_streamer()

        # JSON file-path export: stream directly to file to avoid prefetch
        if fmt == "json" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            offset = 0
            written = 0
            with p.open("w", encoding="utf-8") as f:
                f.write("[")
                first = True
                while True:
                    rows = await self.query_events(
                        start_time=start_time,
                        end_time=end_time,
                        event_types=event_types,
                        categories=categories,
                        user_id=user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        ip_address=ip_address,
                        session_id=session_id,
                        endpoint=endpoint,
                        method=method,
                        min_risk_score=min_risk_score,
                        limit=chunk_size,
                        offset=offset,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        if not first:
                            f.write(",")
                        f.write(json.dumps(r, ensure_ascii=False))
                        written += 1
                        first = False
                    if len(rows) < chunk_size or (max_rows is not None and written >= max_rows):
                        break
                    offset += chunk_size
                f.write("]")
            return written

        # JSONL file-path export: stream directly to file to avoid prefetch
        if fmt == "jsonl" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            offset = 0
            written = 0
            with p.open("w", encoding="utf-8") as f:
                while True:
                    rows = await self.query_events(
                        start_time=start_time,
                        end_time=end_time,
                        event_types=event_types,
                        categories=categories,
                        user_id=user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        ip_address=ip_address,
                        session_id=session_id,
                        endpoint=endpoint,
                        method=method,
                        min_risk_score=min_risk_score,
                        limit=chunk_size,
                        offset=offset,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                        written += 1
                    if len(rows) < chunk_size or (max_rows is not None and written >= max_rows):
                        break
                    offset += chunk_size
            return written

        # Otherwise, gather rows in chunks to return content in-memory
        all_rows: List[Dict[str, Any]] = []
        offset = 0
        written = 0
        while True:
            rows = await self.query_events(
                start_time=start_time,
                end_time=end_time,
                event_types=event_types,
                categories=categories,
                user_id=user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                session_id=session_id,
                endpoint=endpoint,
                method=method,
                min_risk_score=min_risk_score,
                limit=chunk_size,
                offset=offset,
            )
            if not rows:
                break
            if max_rows is not None:
                remaining = max_rows - written
                if remaining <= 0:
                    break
                slice_rows = rows[:remaining]
                all_rows.extend(slice_rows)
                written += len(slice_rows)
            else:
                all_rows.extend(rows)
                written += len(rows)
            if len(rows) < chunk_size:
                break
            offset += chunk_size

        if fmt == "json":
            # If no file path, return JSON content as a single string
            if file_path is None:
                content = json.dumps(all_rows, ensure_ascii=False)
                return content
            # File-path handled earlier
            return 0
        elif fmt == "jsonl":
            # JSON Lines: one JSON object per line
            if file_path is None:
                # Return content as newline-separated JSON objects
                return "\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows)
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            rows_written = 0
            with p.open("w", encoding="utf-8") as f:
                # Write pre-fetched rows only (avoid duplicate continuation from same offset)
                for r in all_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    rows_written += 1
            return rows_written

        # CSV export with fixed header schema
        def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
            from io import StringIO
            buf = StringIO()
            writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
            return buf.getvalue()

        if file_path is None:
            return _rows_to_csv(all_rows)

        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_rows_to_csv(all_rows), encoding="utf-8")
        return len(all_rows)

    def _determine_category(self, event_type: AuditEventType) -> AuditEventCategory:
        """Auto-determine category from event type"""
        type_name = event_type.name.lower()

        if type_name.startswith("auth_"):
            return AuditEventCategory.AUTHENTICATION
        elif type_name.startswith("user_"):
            return AuditEventCategory.AUTHORIZATION
        elif type_name.startswith("data_"):
            # Differentiate read vs modification operations
            if type_name.endswith("write") or type_name.endswith("update") or type_name.endswith("delete") or type_name.endswith("import") or type_name.endswith("export"):
                return AuditEventCategory.DATA_MODIFICATION
            return AuditEventCategory.DATA_ACCESS
        elif type_name.startswith("rag_"):
            return AuditEventCategory.RAG
        elif type_name.startswith("eval_"):
            return AuditEventCategory.EVALUATION
        elif type_name.startswith("api_"):
            # Keep API operations under API_CALL consistently (rate limiting, errors)
            return AuditEventCategory.API_CALL
        elif type_name.startswith("security_"):
            return AuditEventCategory.SECURITY
        elif type_name.startswith("system_"):
            return AuditEventCategory.SYSTEM
        else:
            # Map specific non-prefixed types to appropriate categories
            if event_type in (AuditEventType.PERMISSION_DENIED, AuditEventType.SUSPICIOUS_ACTIVITY):
                return AuditEventCategory.SECURITY
            if event_type is AuditEventType.PII_DETECTED:
                return AuditEventCategory.COMPLIANCE
            return AuditEventCategory.SYSTEM

    def _determine_severity(self, event_type: AuditEventType, result: str) -> AuditSeverity:
        """Auto-determine severity from event type and result"""
        if result == "error":
            return AuditSeverity.ERROR
        elif result == "failure":
            return AuditSeverity.WARNING

        # Critical events
        if event_type in [
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.SUSPICIOUS_ACTIVITY
        ]:
            return AuditSeverity.CRITICAL

        # Warning events
        elif event_type in [
            AuditEventType.AUTH_LOGIN_FAILURE,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.API_RATE_LIMITED
        ]:
            return AuditSeverity.WARNING

        # Debug events
        elif event_type in [
            AuditEventType.SYSTEM_START,
            AuditEventType.SYSTEM_STOP
        ]:
            return AuditSeverity.DEBUG

        # Default to INFO
        else:
            return AuditSeverity.INFO

    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics"""
        return {
            "events_logged": self.stats["events_logged"],
            "events_flushed": self.stats["events_flushed"],
            "events_buffered": len(self.event_buffer),
            "flush_failures": self.stats["flush_failures"],
            "high_risk_events": self.stats["high_risk_events"],
            "db_path": str(self.db_path),
            "retention_days": self.retention_days,
            "pii_detection_enabled": self.enable_pii_detection,
            "risk_scoring_enabled": self.enable_risk_scoring
        }

    async def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Aggregate recent security-related audit stats for health checks.

        Args:
            hours: Lookback window in hours

        Returns:
            Dictionary with summary stats: high_risk_events, failure_events,
            unique_security_users, top_failing_ips
        """
        from collections import Counter

        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        # Paginate to avoid undercounting busy windows
        events: List[Dict[str, Any]] = []
        offset = 0
        chunk = 5000
        while True:
            rows = await self.query_events(
                start_time=start_time,
                categories=[AuditEventCategory.SECURITY],
                limit=chunk,
                offset=offset,
            )
            if not rows:
                break
            events.extend(rows)
            if len(rows) < chunk:
                break
            offset += chunk
        high_risk = sum(1 for e in events if (e.get("risk_score") or 0) >= HIGH_RISK_SCORE)
        failures = sum(1 for e in events if (e.get("result") or "success") != "success")
        unique_users = len({e.get("context_user_id") for e in events if e.get("context_user_id")})
        ip_counts = Counter([e.get("context_ip_address") for e in events if e.get("context_ip_address")])
        top_ips = [ip for ip, _ in ip_counts.most_common(5)]

        return {
            "high_risk_events": high_risk,
            "failure_events": failures,
            "unique_security_users": unique_users,
            "top_failing_ips": top_ips,
            "total_events": len(events),
        }

    def decode_row_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of a row dict with JSON fields decoded.

        Decodes `metadata` and `compliance_flags` if they are JSON strings.
        Leaves data unchanged on parse errors.
        """
        out = dict(row)
        try:
            if isinstance(out.get("metadata"), str):
                out["metadata"] = json.loads(out["metadata"])  # type: ignore[arg-type]
        except Exception:
            pass
        try:
            if isinstance(out.get("compliance_flags"), str):
                out["compliance_flags"] = json.loads(out["compliance_flags"])  # type: ignore[arg-type]
        except Exception:
            pass
        return out


# ============================================================================
# Context Manager for Audit Operations
# ============================================================================

@asynccontextmanager
async def audit_operation(
    service: UnifiedAuditService,
    event_type: AuditEventType,
    context: AuditContext,
    *,
    start_event_type: Optional[AuditEventType] = None,
    completed_event_type: Optional[AuditEventType] = None,
    **kwargs
):
    """Context manager for auditing operations with automatic timing"""
    start_time = time.perf_counter()
    event_id = None

    try:
        # Log start event when specified explicitly
        if start_event_type is not None:
            event_id = await service.log_event(
                event_type=start_event_type,
                context=context,
                result="started",
                **kwargs,
            )

        yield event_id

        # Log success
        duration_ms = (time.perf_counter() - start_time) * 1000
        await service.log_event(
            event_type=(completed_event_type or event_type),
            context=context,
            result="success",
            duration_ms=duration_ms,
            **kwargs
        )

    except Exception as e:
        # Log failure
        duration_ms = (time.perf_counter() - start_time) * 1000
        await service.log_event(
            event_type=(completed_event_type or event_type),
            context=context,
            result="failure",
            error_message=str(e),
            duration_ms=duration_ms,
            **kwargs
        )
        raise


# ============================================================================
# Deprecated Global Service Instance
# ============================================================================
# NOTE: The global singleton pattern is deprecated. Use dependency injection instead:
# from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user

async def get_unified_audit_service() -> UnifiedAuditService:
    """
    DEPRECATED: This global singleton pattern is no longer supported.
    Use dependency injection with get_audit_service_for_user instead.

    Migration guide:
    Old: audit_service = await get_unified_audit_service()
    New: audit_service: UnifiedAuditService = Depends(get_audit_service_for_user)
    """
    raise DeprecationWarning(
        "Global audit service is deprecated. "
        "Use dependency injection: "
        "from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user"
    )


async def shutdown_audit_service():
    """
    DEPRECATED: Use shutdown_all_audit_services from Audit_DB_Deps instead.

    Migration guide:
    Old: await shutdown_audit_service()
    New: from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import shutdown_all_audit_services
         await shutdown_all_audit_services()
    """
    import warnings
    # Emit deprecation as a warning (not an exception) for backward-compat in tests
    warnings.warn(
        "Global shutdown is deprecated. "
        "Use: from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import shutdown_all_audit_services",
        DeprecationWarning,
        stacklevel=2,
    )
    # For compatibility, delegate to the new shutdown for all audit services if available
    try:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            shutdown_all_audit_services,
        )
    except Exception:
        # If import not available in this context, just return
        return
    # Run actual shutdown to ensure clean state in tests
    await shutdown_all_audit_services()
