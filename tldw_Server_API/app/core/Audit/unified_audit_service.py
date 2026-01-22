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

Environment Variables:
- AUDIT_HIGH_RISK_SCORE: Threshold for high-risk events (default: 70, range: 0-100)
- AUDIT_EXPORT_MAX_ROWS: Max rows for non-streaming export (default: 10000)
- AUDIT_PII_USE_RAG_PATTERNS: Merge PII patterns from RAG module (default: false)
- AUDIT_PII_PATTERNS: Dict of custom PII regex patterns (via settings)
- AUDIT_PII_SCAN_FIELDS: Comma-separated list of extra fields to scan for PII
- AUDIT_ACTION_RISK_BONUS: Dict of action names to risk score bonuses (via settings)
- AUDIT_HIGH_RISK_OPERATIONS: Comma-separated list of high-risk operation keywords
- AUDIT_SUSPICIOUS_THRESHOLDS: Dict of threshold overrides (failed_auth, data_export, etc.)
- TEST_MODE/TLDW_TEST_MODE: Enable test mode (disables background tasks)
"""
#
# Imports
import asyncio
import csv
import hashlib
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, time as time_t, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union
from uuid import uuid4
#
# 3rd-Party Imports
import aiosqlite
from io import StringIO
from loguru import logger
#
# Local Imports
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
try:
    DEFAULT_NON_STREAM_MAX_ROWS = int(os.getenv("AUDIT_EXPORT_MAX_ROWS", "10000"))
except Exception:
    DEFAULT_NON_STREAM_MAX_ROWS = 10000


_HASH_PREFIX = "sha256:"
_VALID_STORAGE_MODES = {"per_user", "shared"}
_SYSTEM_TENANT_ID = "system"
_UNIDENTIFIED_TENANT_ID = "unidentified_user"
_AUDIT_SHARED_SCHEMA_VERSION = 1

try:
    import fcntl  # type: ignore
    _HAS_FCNTL = True
except Exception:
    _HAS_FCNTL = False

_FALLBACK_LOCKS: Dict[str, threading.Lock] = {}
_FALLBACK_LOCKS_LOCK = threading.Lock()


def _fallback_lock_path(path: Path) -> Path:
    """Return a lock-file path for a fallback queue file."""
    suffix = path.suffix + ".lock" if path.suffix else ".lock"
    return path.with_suffix(suffix)


def _get_fallback_thread_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _FALLBACK_LOCKS_LOCK:
        lock = _FALLBACK_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _FALLBACK_LOCKS[key] = lock
    return lock


@asynccontextmanager
async def _fallback_queue_lock(path: Path) -> AsyncGenerator[None, None]:
    """Cross-instance lock for fallback queue operations.

    Uses a file lock when available; otherwise falls back to a process-wide lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _fallback_lock_path(path)

    if _HAS_FCNTL:
        def _open_and_lock() -> Any:
            fh = lock_path.open("a", encoding="utf-8")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            return fh

        handle = await asyncio.to_thread(_open_and_lock)
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(fcntl.flock, handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                await asyncio.to_thread(handle.close)
            except Exception:
                pass
    else:
        lock = _get_fallback_thread_lock(lock_path)
        await asyncio.to_thread(lock.acquire)
        try:
            yield
        finally:
            try:
                lock.release()
            except Exception:
                pass


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_storage_mode(raw: Any) -> str:
    if raw is None:
        return "per_user"
    mode = str(raw).strip().lower()
    return mode if mode in _VALID_STORAGE_MODES else "per_user"


def _resolve_storage_mode(explicit: Optional[str] = None) -> str:
    if explicit:
        mode = _normalize_storage_mode(explicit)
    else:
        mode = _normalize_storage_mode(
            _app_settings.get("AUDIT_STORAGE_MODE", None) or os.getenv("AUDIT_STORAGE_MODE")
        )
    rollback_raw = _app_settings.get("AUDIT_STORAGE_ROLLBACK", None) or os.getenv("AUDIT_STORAGE_ROLLBACK")
    if _coerce_bool(rollback_raw, False):
        return "per_user"
    return mode


def _resolve_shared_db_path() -> Path:
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

        return DatabasePaths.get_shared_audit_db_path()
    except Exception:
        db_dir = Path("./Databases")
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "audit_shared.db"


def _hash_api_key(value: Optional[str]) -> Optional[str]:
    """Return a stable hash for API keys; avoid storing raw secrets."""
    if value is None:
        return None
    val = str(value).strip()
    if not val:
        return None
    lower = val.lower()
    if lower.startswith(_HASH_PREFIX):
        digest = val[len(_HASH_PREFIX):].strip()
        if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest.lower()):
            return f"{_HASH_PREFIX}{digest.lower()}"
    digest = hashlib.sha256(val.encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}{digest}"


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


def _normalize_timestamp(value: datetime) -> datetime:
    """Normalize timestamps to UTC for consistent storage and ordering."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_datetime_filter(value: Optional[datetime]) -> Optional[str]:
    """Normalize filter datetimes to UTC ISO strings for lexicographic queries."""
    if value is None:
        return None
    try:
        return _normalize_timestamp(value).isoformat()
    except Exception:
        try:
            return value.isoformat()
        except Exception:
            return None


def _normalize_result(value: Any, default: str = "success") -> str:
    """Normalize result values to lowercase canonical strings."""
    if value is None:
        return default
    try:
        s = str(value).strip().lower()
    except Exception:
        return default
    return s or default


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
    tenant_user_id: Optional[str] = None

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
        ts = _normalize_timestamp(self.timestamp)

        data = {
            "event_id": self.event_id,
            "timestamp": ts.isoformat(),
            "category": self.category.value,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "tenant_user_id": self.tenant_user_id,
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
        # Bank account pattern is more specific: requires routing number format or context
        # US routing (9 digits) + account (8-17 digits) OR account with context keyword
        "bank_account": r"(?:\b\d{9}[-\s]?\d{8,17}\b|(?:account|acct|routing)[\s#:]*\d{8,17}\b)",
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
        """Recursively redact PII from nested dict/list/tuple/set structures and strings."""
        try:
            if isinstance(data, dict):
                return {k: self.redact_obj(v, placeholder_format) for k, v in data.items()}
            if isinstance(data, list):
                return [self.redact_obj(v, placeholder_format) for v in data]
            if isinstance(data, tuple):
                return tuple(self.redact_obj(v, placeholder_format) for v in data)
            if isinstance(data, set):
                try:
                    return {self.redact_obj(v, placeholder_format) for v in data}
                except TypeError:
                    # Fallback: preserve values in a list when elements become unhashable after redaction.
                    return [self.redact_obj(v, placeholder_format) for v in data]
            if isinstance(data, frozenset):
                try:
                    return frozenset(self.redact_obj(v, placeholder_format) for v in data)
                except TypeError:
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

        def _safe_int(val: Any, default: int = 0) -> int:
            try:
                if val is None or isinstance(val, bool):
                    return default
                if isinstance(val, int):
                    return val
                if isinstance(val, float):
                    return int(val)
                s = str(val).strip()
                if s == "":
                    return default
                return int(s)
            except Exception:
                return default

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

        # Failed operations (case-insensitive)
        result_norm = _normalize_result(event.result)
        if result_norm == "failure":
            score += 20
        elif result_norm == "error":
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

        # Normalize metadata to dict for risk calculations
        # Handles dict (normal), str (JSON-serialized), or fallback to empty
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
                pass  # Keep empty dict

        failed_thr = 3
        try:
            v = self.suspicious_thresholds.get("failed_auth", 3)  # type: ignore[assignment]
            failed_thr = int(v) if not isinstance(v, bool) else 3
        except Exception:
            failed_thr = 3
        if _safe_int(metadata.get("consecutive_failures"), 0) > failed_thr:
            score += 20

        # Large data operations
        export_thr = 1000
        try:
            v2 = self.suspicious_thresholds.get("data_export", 1000)  # type: ignore[assignment]
            export_thr = int(v2) if not isinstance(v2, bool) else 1000
        except Exception:
            export_thr = 1000
        if _safe_int(event.result_count, 0) > export_thr:
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
        storage_mode: Optional[str] = None,
        retention_days: int = 90,
        enable_pii_detection: bool = True,
        enable_risk_scoring: bool = True,
        buffer_size: int = 1000,
        flush_interval: float = 10.0,
        max_db_mb: Optional[int] = None,
        system_tenant_id: Optional[str] = None,
        unidentified_tenant_id: Optional[str] = None,
    ):
        """
        Initialize unified audit service.

        Args:
            db_path: Path to audit database
            storage_mode: per_user (default) or shared
            retention_days: Days to retain audit logs
            enable_pii_detection: Enable PII detection
            enable_risk_scoring: Enable risk scoring
            buffer_size: Maximum events to buffer before flush
            flush_interval: Seconds between automatic flushes
        """
        # Configuration
        self.storage_mode = _resolve_storage_mode(storage_mode)
        self._shared_mode = self.storage_mode == "shared"
        self.system_tenant_id = (system_tenant_id or _SYSTEM_TENANT_ID).strip().lower() or _SYSTEM_TENANT_ID
        self.unidentified_tenant_id = (
            (unidentified_tenant_id or _UNIDENTIFIED_TENANT_ID).strip().lower() or _UNIDENTIFIED_TENANT_ID
        )
        if self.unidentified_tenant_id == self.system_tenant_id:
            logger.warning(
                "Unidentified tenant id matches system tenant id; falling back to {}",
                _UNIDENTIFIED_TENANT_ID,
            )
            self.unidentified_tenant_id = _UNIDENTIFIED_TENANT_ID

        if db_path is None:
            if self._shared_mode:
                db_path = _resolve_shared_db_path()
            else:
                db_dir = Path("./Databases")
                db_dir.mkdir(parents=True, exist_ok=True)
                db_path = db_dir / "unified_audit.db"

        self.db_path = Path(db_path)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(
                "Failed to ensure audit DB directory {}: {}",
                self.db_path.parent,
                e,
            )
        self.retention_days = retention_days
        self.enable_pii_detection = enable_pii_detection
        self.enable_risk_scoring = enable_risk_scoring
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.non_stream_max_rows = DEFAULT_NON_STREAM_MAX_ROWS
        if max_db_mb is None:
            try:
                raw_max = _app_settings.get("AUDIT_MAX_DB_MB", None)
            except Exception:
                raw_max = None
            try:
                if raw_max is None:
                    max_db_mb = None
                else:
                    s = str(raw_max).strip()
                    max_db_mb = int(s) if s else None
            except Exception:
                max_db_mb = None
        self.max_db_mb = max_db_mb
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_used_ts = time.monotonic()

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

        # Prepared schemas for inserts/exports
        self._event_columns = self._build_event_columns()
        self._event_insert_sql = self._build_event_insert_sql(self._event_columns)
        self._csv_headers = list(self._event_columns)

        # Event buffer
        self.event_buffer: List[AuditEvent] = []
        self.buffer_lock = asyncio.Lock()

        # Background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._replay_task: Optional[asyncio.Task] = None
        self._replay_interval_s = 300  # 5 minutes

        # Connection pool
        self._db_pool: Optional[aiosqlite.Connection] = None
        self._pool_lock = asyncio.Lock()
        self._db_lock = asyncio.Lock()

        # Ad-hoc flush tasks created for high-risk/buffer-full conditions
        # Tracked so they can be awaited during graceful shutdown
        self._flush_futures: Set[asyncio.Task] = set()
        self._flush_futures_lock = asyncio.Lock()  # Protects _flush_futures set

        # Statistics
        self.stats = {
            "events_logged": 0,
            "events_flushed": 0,
            "flush_failures": 0,
            "high_risk_events": 0
        }

    async def initialize(self, *, start_background_tasks: bool = True) -> None:
        """Initialize database and optionally start background tasks.

        Args:
            start_background_tasks: When True (default), starts the periodic flush,
                cleanup, and fallback replay loops (unless running in test mode).
                Set to False for one-off/ephemeral usage where the caller will
                explicitly call `flush()` and `stop()`.
        """
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
        if start_background_tasks and not self._test_mode:
            await self.start_background_tasks()

    def _build_event_columns(self) -> List[str]:
        columns = [
            "event_id", "timestamp", "category", "event_type", "severity",
        ]
        if self._shared_mode:
            columns.append("tenant_user_id")
        columns.extend([
            "context_request_id", "context_correlation_id", "context_session_id",
            "context_user_id", "context_api_key_hash", "context_ip_address",
            "context_user_agent", "context_endpoint", "context_method",
            "resource_type", "resource_id", "action", "result", "error_message",
            "duration_ms", "tokens_used", "estimated_cost", "result_count",
            "risk_score", "pii_detected", "compliance_flags", "metadata",
        ])
        return columns

    def _build_event_insert_sql(self, columns: List[str]) -> str:
        placeholders = ", ".join(f":{col}" for col in columns)
        return f"INSERT OR IGNORE INTO audit_events ({', '.join(columns)}) VALUES ({placeholders})"

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
            db.row_factory = aiosqlite.Row
            await self._ensure_audit_events_schema(db)

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
            if self._shared_mode:
                await db.execute("CREATE INDEX IF NOT EXISTS idx_tenant_user_id ON audit_events(tenant_user_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_tenant_timestamp ON audit_events(tenant_user_id, timestamp)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_tenant_event_type ON audit_events(tenant_user_id, event_type)")

            await self._ensure_audit_daily_stats_schema(db)

            if self._shared_mode:
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stats_tenant_date ON audit_daily_stats(tenant_user_id, date)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stats_tenant_category ON audit_daily_stats(tenant_user_id, category)"
                )
                await self._ensure_schema_version(db)

            await db.commit()

    async def _ensure_audit_events_schema(self, db: aiosqlite.Connection) -> None:
        """Ensure the audit_events table matches the unified schema."""
        if self._shared_mode:
            create_sql = """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    tenant_user_id TEXT NOT NULL,

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
            """
        else:
            create_sql = """
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
            """
        expected_types = {
            "event_id": "TEXT",
            "timestamp": "TIMESTAMP",
            "category": "TEXT",
            "event_type": "TEXT",
            "severity": "TEXT",
            "tenant_user_id": "TEXT",
            "context_request_id": "TEXT",
            "context_correlation_id": "TEXT",
            "context_session_id": "TEXT",
            "context_user_id": "TEXT",
            "context_api_key_hash": "TEXT",
            "context_ip_address": "TEXT",
            "context_user_agent": "TEXT",
            "context_endpoint": "TEXT",
            "context_method": "TEXT",
            "resource_type": "TEXT",
            "resource_id": "TEXT",
            "action": "TEXT",
            "result": "TEXT",
            "error_message": "TEXT",
            "duration_ms": "REAL",
            "tokens_used": "INTEGER",
            "estimated_cost": "REAL",
            "result_count": "INTEGER",
            "risk_score": "INTEGER",
            "pii_detected": "BOOLEAN",
            "compliance_flags": "TEXT",
            "metadata": "TEXT",
        }
        if not self._shared_mode:
            expected_types.pop("tenant_user_id", None)

        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'"
        ) as cur:
            table_row = await cur.fetchone()
        if not table_row:
            await db.execute(create_sql)
            return

        async with db.execute("PRAGMA table_info(audit_events)") as cur:
            cols = await cur.fetchall()
        if not cols:
            await db.execute(create_sql)
            return

        existing = {row["name"]: row for row in cols}
        expected = set(expected_types.keys())
        missing = [name for name in expected if name not in existing]
        core_missing = {name for name in ("event_id", "timestamp", "event_type", "severity", "category") if name not in existing}
        if self._shared_mode and "tenant_user_id" not in existing:
            core_missing.add("tenant_user_id")
        incompatible = [
            name
            for name, info in existing.items()
            if name not in expected and info["notnull"] and info["dflt_value"] is None
        ]

        if core_missing or "outcome" in existing or incompatible:
            await self._migrate_legacy_audit_events(db)
            return

        for col in missing:
            try:
                await db.execute(f"ALTER TABLE audit_events ADD COLUMN {col} {expected_types[col]}")
            except Exception as e:
                logger.warning(f"Failed to add audit_events column {col}: {e}")

    async def _ensure_audit_daily_stats_schema(self, db: aiosqlite.Connection) -> None:
        """Ensure audit_daily_stats table matches the expected schema."""
        if not self._shared_mode:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_daily_stats (
                    date DATE NOT NULL,
                    category TEXT NOT NULL,
                    total_events INTEGER DEFAULT 0,
                    high_risk_events INTEGER DEFAULT 0,
                    failed_events INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0.0,
                    total_tokens INTEGER DEFAULT 0,
                    avg_duration_ms REAL,
                    duration_count INTEGER DEFAULT 0,
                    PRIMARY KEY (date, category)
                )
                """
            )
            # Migration: add duration_count column if missing (for existing databases)
            try:
                await db.execute("ALTER TABLE audit_daily_stats ADD COLUMN duration_count INTEGER DEFAULT 0")
            except Exception:
                pass
            return

        create_sql = """
            CREATE TABLE IF NOT EXISTS audit_daily_stats (
                tenant_user_id TEXT NOT NULL,
                date DATE NOT NULL,
                category TEXT NOT NULL,
                total_events INTEGER DEFAULT 0,
                high_risk_events INTEGER DEFAULT 0,
                failed_events INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                total_tokens INTEGER DEFAULT 0,
                avg_duration_ms REAL,
                duration_count INTEGER DEFAULT 0,
                PRIMARY KEY (tenant_user_id, date, category)
            )
        """

        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_daily_stats'"
        ) as cur:
            table_row = await cur.fetchone()
        if not table_row:
            await db.execute(create_sql)
            return

        async with db.execute("PRAGMA table_info(audit_daily_stats)") as cur:
            cols = await cur.fetchall()
        if not cols:
            await db.execute(create_sql)
            return

        existing = {row["name"]: row for row in cols}
        tenant_info = existing.get("tenant_user_id")
        tenant_pk = int(tenant_info["pk"]) if tenant_info else 0
        needs_rebuild = tenant_info is None or tenant_pk == 0

        if needs_rebuild:
            logger.warning("Legacy audit_daily_stats schema detected; migrating to tenant-scoped schema.")
            await db.execute("ALTER TABLE audit_daily_stats RENAME TO audit_daily_stats_legacy")
            await db.execute(create_sql)

            duration_present = "duration_count" in existing
            select_cols = (
                "date, category, total_events, high_risk_events, failed_events, "
                "total_cost, total_tokens, avg_duration_ms"
            )
            if duration_present:
                select_cols += ", duration_count"
                insert_cols = f"tenant_user_id, {select_cols}"
                await db.execute(
                    f"""
                    INSERT INTO audit_daily_stats ({insert_cols})
                    SELECT ?, {select_cols} FROM audit_daily_stats_legacy
                    """,
                    (self.unidentified_tenant_id,),
                )
            else:
                insert_cols = f"tenant_user_id, {select_cols}, duration_count"
                await db.execute(
                    f"""
                    INSERT INTO audit_daily_stats ({insert_cols})
                    SELECT ?, {select_cols}, 0 FROM audit_daily_stats_legacy
                    """,
                    (self.unidentified_tenant_id,),
                )

            try:
                await db.execute("DROP TABLE audit_daily_stats_legacy")
            except Exception:
                pass
            return

        if "duration_count" not in existing:
            try:
                await db.execute("ALTER TABLE audit_daily_stats ADD COLUMN duration_count INTEGER DEFAULT 0")
            except Exception:
                pass

    async def _ensure_schema_version(self, db: aiosqlite.Connection) -> None:
        """Ensure shared audit DB schema version is recorded."""
        if not self._shared_mode:
            return
        try:
            async with db.execute("PRAGMA user_version") as cur:
                row = await cur.fetchone()
            current = int(row[0]) if row else 0
        except Exception:
            current = 0
        if current < _AUDIT_SHARED_SCHEMA_VERSION:
            await db.execute(f"PRAGMA user_version = {_AUDIT_SHARED_SCHEMA_VERSION}")

    async def _migrate_legacy_audit_events(self, db: aiosqlite.Connection) -> None:
        """Migrate legacy audit_events tables to the unified schema."""
        logger.warning("Legacy audit_events schema detected; migrating to unified schema.")

        await db.execute("ALTER TABLE audit_events RENAME TO audit_events_legacy")
        if self._shared_mode:
            await db.execute(
                """
                CREATE TABLE audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    tenant_user_id TEXT NOT NULL,
                    context_request_id TEXT,
                    context_correlation_id TEXT,
                    context_session_id TEXT,
                    context_user_id TEXT,
                    context_api_key_hash TEXT,
                    context_ip_address TEXT,
                    context_user_agent TEXT,
                    context_endpoint TEXT,
                    context_method TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    action TEXT,
                    result TEXT,
                    error_message TEXT,
                    duration_ms REAL,
                    tokens_used INTEGER,
                    estimated_cost REAL,
                    result_count INTEGER,
                    risk_score INTEGER,
                    pii_detected BOOLEAN,
                    compliance_flags TEXT,
                    metadata TEXT
                )
                """
            )
        else:
            await db.execute(
                """
                CREATE TABLE audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    context_request_id TEXT,
                    context_correlation_id TEXT,
                    context_session_id TEXT,
                    context_user_id TEXT,
                    context_api_key_hash TEXT,
                    context_ip_address TEXT,
                    context_user_agent TEXT,
                    context_endpoint TEXT,
                    context_method TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    action TEXT,
                    result TEXT,
                    error_message TEXT,
                    duration_ms REAL,
                    tokens_used INTEGER,
                    estimated_cost REAL,
                    result_count INTEGER,
                    risk_score INTEGER,
                    pii_detected BOOLEAN,
                    compliance_flags TEXT,
                    metadata TEXT
                )
                """
            )

        insert_sql = self._event_insert_sql

        def _infer_category(value: Optional[str]) -> str:
            if not value:
                return AuditEventCategory.SYSTEM.value
            val = str(value).strip().lower()
            if val.startswith("auth") or val.startswith("auth."):
                return AuditEventCategory.AUTHENTICATION.value
            if val.startswith("user") or val.startswith("user."):
                return AuditEventCategory.AUTHORIZATION.value
            if val.startswith("data") or val.startswith("data."):
                if any(val.endswith(suffix) for suffix in ("write", "update", "delete", "import", "export")):
                    return AuditEventCategory.DATA_MODIFICATION.value
                return AuditEventCategory.DATA_ACCESS.value
            if val.startswith("rag") or val.startswith("rag."):
                return AuditEventCategory.RAG.value
            if val.startswith("eval") or val.startswith("eval."):
                return AuditEventCategory.EVALUATION.value
            if val.startswith("api") or val.startswith("api."):
                return AuditEventCategory.API_CALL.value
            if val.startswith("security") or val.startswith("security."):
                return AuditEventCategory.SECURITY.value
            if val.startswith("system") or val.startswith("system."):
                return AuditEventCategory.SYSTEM.value
            return AuditEventCategory.SYSTEM.value

        def _normalize_severity(value: Optional[str]) -> str:
            if not value:
                return AuditSeverity.INFO.value
            val = str(value).strip().lower()
            if val in {s.value for s in AuditSeverity}:
                return val
            mapping = {
                "low": AuditSeverity.INFO.value,
                "medium": AuditSeverity.WARNING.value,
                "high": AuditSeverity.ERROR.value,
                "critical": AuditSeverity.CRITICAL.value,
            }
            return mapping.get(val, AuditSeverity.INFO.value)

        def _coerce_timestamp(value: Any) -> str:
            if isinstance(value, datetime):
                return _normalize_timestamp(value).isoformat()
            if value is None:
                return datetime.now(timezone.utc).isoformat()
            try:
                s = str(value).strip()
                if not s:
                    return datetime.now(timezone.utc).isoformat()
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                dt_val = datetime.fromisoformat(s)
                return _normalize_timestamp(dt_val).isoformat()
            except Exception:
                return str(value)

        def _json_text(value: Any, *, default: str) -> str:
            if value is None:
                return default
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)

        async def _copy_rows() -> None:
            async with db.execute("SELECT * FROM audit_events_legacy") as cur:
                while True:
                    rows = await cur.fetchmany(1000)
                    if not rows:
                        break
                    records: List[Dict[str, Any]] = []
                    for row in rows:
                        data = dict(row)
                        event_type_val = data.get("event_type") or AuditEventType.SYSTEM_START.value
                        context_user_id = data.get("context_user_id") or data.get("user_id")
                        record = {
                            "event_id": str(data.get("event_id") or uuid4()),
                            "timestamp": _coerce_timestamp(data.get("timestamp")),
                            "category": _infer_category(event_type_val),
                            "event_type": str(event_type_val),
                            "severity": _normalize_severity(data.get("severity")),
                            "context_request_id": data.get("context_request_id"),
                            "context_correlation_id": data.get("context_correlation_id"),
                            "context_session_id": data.get("context_session_id") or data.get("session_id"),
                            "context_user_id": context_user_id,
                            "context_api_key_hash": data.get("context_api_key_hash"),
                            "context_ip_address": data.get("context_ip_address") or data.get("ip_address"),
                            "context_user_agent": data.get("context_user_agent") or data.get("user_agent"),
                            "context_endpoint": data.get("context_endpoint") or data.get("endpoint"),
                            "context_method": data.get("context_method") or data.get("method"),
                            "resource_type": data.get("resource_type"),
                            "resource_id": data.get("resource_id"),
                            "action": data.get("action"),
                            "result": data.get("result") or data.get("outcome") or "success",
                            "error_message": data.get("error_message") or data.get("details"),
                            "duration_ms": data.get("duration_ms"),
                            "tokens_used": data.get("tokens_used"),
                            "estimated_cost": data.get("estimated_cost"),
                            "result_count": data.get("result_count"),
                            "risk_score": data.get("risk_score") or 0,
                            "pii_detected": bool(data.get("pii_detected") or False),
                            "compliance_flags": _json_text(data.get("compliance_flags"), default="[]"),
                            "metadata": _json_text(data.get("metadata"), default="{}"),
                        }
                        if self._shared_mode:
                            record["tenant_user_id"] = self._resolve_tenant_id_for_write(
                                raw_tenant=None,
                                context_user_id=context_user_id,
                                event_type=event_type_val,
                                category=record.get("category"),
                            )
                        records.append(record)
                    if records:
                        await db.executemany(insert_sql, records)

        try:
            await _copy_rows()
            await db.execute("DROP TABLE audit_events_legacy")
        except Exception as exc:
            logger.error(f"Failed to migrate legacy audit_events schema: {exc}")
            # Attempt to roll back to the legacy table if possible.
            try:
                await db.execute("DROP TABLE IF EXISTS audit_events")
                await db.execute("ALTER TABLE audit_events_legacy RENAME TO audit_events")
            except Exception as rollback_exc:
                logger.error(f"Failed to restore legacy audit_events table: {rollback_exc}")
            raise

    def _is_system_event(self, event_type: Any, category: Any) -> bool:
        if category is not None:
            try:
                category_val = category.value if isinstance(category, AuditEventCategory) else str(category)
            except Exception:
                category_val = ""
            if category_val.lower() == AuditEventCategory.SYSTEM.value:
                return True
        if event_type is not None:
            try:
                event_val = event_type.value if isinstance(event_type, AuditEventType) else str(event_type)
            except Exception:
                event_val = ""
            if event_val.lower().startswith("system"):
                return True
        return False

    def _normalize_tenant_value(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return str(value).strip()
        except Exception:
            return ""

    def _normalize_tenant_id(self, value: Any) -> str:
        s = self._normalize_tenant_value(value)
        if not s:
            return self.unidentified_tenant_id
        lowered = s.lower()
        if lowered == self.system_tenant_id:
            return self.system_tenant_id
        if lowered == self.unidentified_tenant_id:
            return self.unidentified_tenant_id
        return s

    def _validate_tenant_id_for_write(
        self,
        tenant_id: str,
        *,
        allow_system: bool,
        allow_unidentified: bool,
    ) -> str:
        if not tenant_id:
            raise ValueError("tenant_user_id cannot be empty")
        lowered = tenant_id.lower()
        if lowered == self.system_tenant_id:
            if not allow_system:
                raise ValueError("system tenant id is reserved")
            return self.system_tenant_id
        if lowered == self.unidentified_tenant_id:
            if not allow_unidentified:
                raise ValueError("unidentified tenant id is reserved")
            return self.unidentified_tenant_id
        if not tenant_id.isdigit():
            logger.warning(
                "Non-numeric tenant_user_id '{}' in shared audit; storing as-is.",
                tenant_id,
            )
            return tenant_id
        return tenant_id

    def _resolve_tenant_id_for_write(
        self,
        *,
        raw_tenant: Any,
        context_user_id: Any,
        event_type: Any,
        category: Any,
    ) -> str:
        if self._is_system_event(event_type, category):
            return self.system_tenant_id

        candidate = raw_tenant
        if candidate is None or str(candidate).strip() == "":
            candidate = context_user_id
        normalized = self._normalize_tenant_value(candidate)
        if not normalized:
            return self.unidentified_tenant_id

        lowered = normalized.lower()
        if lowered == self.system_tenant_id:
            # Allow explicit system tenant usage for non-system events (e.g., background jobs).
            if context_user_id is not None:
                try:
                    ctx_val = str(context_user_id).strip().lower()
                except Exception:
                    ctx_val = ""
                if ctx_val and ctx_val != self.system_tenant_id:
                    logger.warning(
                        "System tenant id provided while context_user_id is non-system; storing as system tenant."
                    )
            return self.system_tenant_id
        if lowered == self.unidentified_tenant_id:
            if context_user_id is not None and str(context_user_id).strip() != "":
                raise ValueError("unidentified tenant id cannot be assigned to a user")
            return self.unidentified_tenant_id

        return self._validate_tenant_id_for_write(
            normalized,
            allow_system=False,
            allow_unidentified=False,
        )

    def _resolve_event_tenant_id(self, event: AuditEvent) -> str:
        return self._resolve_tenant_id_for_write(
            raw_tenant=event.tenant_user_id,
            context_user_id=event.context.user_id,
            event_type=event.event_type,
            category=event.category,
        )

    def _ensure_record_tenant_ids(self, records: List[Dict[str, Any]]) -> None:
        if not self._shared_mode:
            return
        for record in records:
            record["tenant_user_id"] = self._resolve_tenant_id_for_write(
                raw_tenant=record.get("tenant_user_id"),
                context_user_id=record.get("context_user_id") or record.get("user_id"),
                event_type=record.get("event_type"),
                category=record.get("category"),
            )

    def _apply_user_filter(
        self,
        query: str,
        params: List[Any],
        user_id: Optional[str],
        allow_cross_tenant: bool,
    ) -> tuple[str, List[Any]]:
        if self._shared_mode:
            if user_id:
                query += " AND tenant_user_id = ?"
                params.append(self._normalize_tenant_id(user_id))
            elif not allow_cross_tenant:
                logger.warning("Shared audit query without tenant filter; returning empty.")
                query += " AND 1=0"
        elif user_id:
            query += " AND context_user_id = ?"
            params.append(user_id)
        return query, params

    def _build_events_query(
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
        allow_cross_tenant: bool = False,
    ) -> tuple[str, List[Any]]:
        """Build the core WHERE clause and params for audit event queries."""
        query = "FROM audit_events WHERE 1=1"
        params: List[Any] = []

        start_iso = _normalize_datetime_filter(start_time)
        if start_iso:
            query += " AND timestamp >= ?"
            params.append(start_iso)

        end_iso = _normalize_datetime_filter(end_time)
        if end_iso:
            query += " AND timestamp <= ?"
            params.append(end_iso)

        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend([et.value for et in event_types])

        if categories:
            placeholders = ",".join("?" * len(categories))
            query += f" AND category IN ({placeholders})"
            params.extend([c.value for c in categories])

        query, params = self._apply_user_filter(query, params, user_id, allow_cross_tenant)

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

        return query, params

    def _cursor_from_row(self, row: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Extract keyset cursor values from a row dict."""
        ts_val = row.get("timestamp")
        if isinstance(ts_val, datetime):
            ts = _normalize_timestamp(ts_val).isoformat()
        elif ts_val is None:
            ts = None
        else:
            ts = str(ts_val)
        ev_id = row.get("event_id")
        ev_id_str = str(ev_id) if ev_id is not None else None
        return ts, ev_id_str

    async def _query_events_keyset(
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
        allow_cross_tenant: bool = False,
        limit: int = 100,
        cursor_ts: Optional[str] = None,
        cursor_event_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query audit events using keyset pagination for stable exports."""
        base_query, params = self._build_events_query(
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
            allow_cross_tenant=allow_cross_tenant,
        )

        if cursor_ts and cursor_event_id:
            base_query += " AND (timestamp < ? OR (timestamp = ? AND event_id < ?))"
            params.extend([cursor_ts, cursor_ts, cursor_event_id])

        query = "SELECT * " + base_query + " ORDER BY timestamp DESC, event_id DESC LIMIT ?"
        params.append(limit)

        try:
            async with self._read_db() as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to query audit events (keyset): {e}")
            return []

    async def _ensure_db_pool(self) -> aiosqlite.Connection:
        """Ensure a persistent aiosqlite connection is available."""
        # In test mode, prefer ephemeral connections; callers of this method are
        # adjusted to bypass pooling when self._test_mode is True. Keep behavior
        # here for non-test callers.
        async with self._pool_lock:
            if self._db_pool is None:
                conn = await aiosqlite.connect(self.db_path)
                try:
                    try:
                        await conn.execute("PRAGMA journal_mode=WAL;")
                        await conn.execute("PRAGMA synchronous=NORMAL;")
                        await conn.execute("PRAGMA temp_store=MEMORY;")
                        await conn.execute("PRAGMA foreign_keys=ON;")
                        await conn.execute("PRAGMA busy_timeout=5000;")
                    except Exception as e:
                        logger.warning(f"Failed to apply PRAGMAs on pooled audit DB connection: {e}")
                    # Return rows as mappings consistently across this service
                    conn.row_factory = aiosqlite.Row
                    await conn.commit()
                    # Only assign to pool after successful setup
                    self._db_pool = conn
                except Exception as e:
                    # Close connection on failure to avoid resource leak
                    try:
                        await conn.close()
                    except Exception:
                        pass
                    logger.warning(f"Failed to initialize pooled audit DB connection: {e}")
                    raise
        return self._db_pool  # type: ignore[return-value]

    @asynccontextmanager
    async def _read_db(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Open a dedicated read connection to avoid pooled cursor contention."""
        conn = await aiosqlite.connect(self.db_path)
        try:
            conn.row_factory = aiosqlite.Row
            try:
                await conn.execute("PRAGMA query_only=ON;")
            except Exception:
                pass
            try:
                await conn.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass
            yield conn
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    async def start_background_tasks(self):
        """Start background flush and cleanup tasks"""
        if not self._flush_task:
            self._flush_task = asyncio.create_task(self._flush_loop())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if not self._replay_task:
            self._replay_task = asyncio.create_task(self._replay_fallback_loop())

    async def stop(self):
        """Stop background tasks and flush remaining events"""
        current_loop = asyncio.get_running_loop()
        owner_closed = False
        try:
            if self._owner_loop:
                owner_closed = bool(self._owner_loop.is_closed())
                if not owner_closed:
                    try:
                        owner_closed = not self._owner_loop.is_running()
                    except Exception:
                        owner_closed = False
        except Exception:
            owner_closed = False
        # Enforce same-loop shutdown only when the owner loop is still alive.
        if self._owner_loop and (not owner_closed) and current_loop is not self._owner_loop:
            raise RuntimeError("UnifiedAuditService.stop must run on the owner event loop")
        def _task_loop(task: asyncio.Task) -> Optional[asyncio.AbstractEventLoop]:
            try:
                return task.get_loop()
            except Exception:
                return None

        async def _cancel_and_await(task: Optional[asyncio.Task]) -> None:
            if task is None:
                return
            try:
                task.cancel()
            except Exception:
                pass

            task_loop = _task_loop(task)
            if task_loop is None or task_loop is current_loop:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cancel background tasks (await only when bound to the current loop).
        await _cancel_and_await(self._flush_task)
        self._flush_task = None
        await _cancel_and_await(self._cleanup_task)
        self._cleanup_task = None
        await _cancel_and_await(self._replay_task)
        self._replay_task = None

        # Await any outstanding ad-hoc flushes first to avoid contention
        futures_snapshot: List[asyncio.Task] = []
        try:
            async with self._flush_futures_lock:
                futures_snapshot = list(self._flush_futures)
                self._flush_futures.clear()
        except Exception:
            futures_snapshot = list(self._flush_futures)
            self._flush_futures.clear()

        if futures_snapshot:
            same_loop_futures: List[asyncio.Task] = []
            for fut in futures_snapshot:
                fut_loop = _task_loop(fut)
                if fut_loop is None or fut_loop is current_loop:
                    same_loop_futures.append(fut)
                else:
                    try:
                        fut.cancel()
                    except Exception:
                        pass
            if same_loop_futures:
                await asyncio.gather(*same_loop_futures, return_exceptions=True)

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

    def _touch(self) -> None:
        try:
            self._last_used_ts = time.monotonic()
        except Exception:
            pass

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

    async def _replay_fallback_loop(self):
        """Background task to replay fallback queue events back into the DB."""
        # Run once immediately, then on an interval.
        try:
            await self.replay_fallback_queue()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Error during initial audit fallback replay: {e}")
        while True:
            try:
                await asyncio.sleep(self._replay_interval_s)
                await self.replay_fallback_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit fallback replay loop: {e}")

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
        self._touch()
        # Auto-determine category if not provided
        if category is None:
            category = self._determine_category(event_type)

        # Normalize result string early for consistent semantics
        result_norm = _normalize_result(result)

        # Auto-determine severity if not provided
        if severity is None:
            severity = self._determine_severity(event_type, result_norm)

        # Create context if not provided
        if context is None:
            context = AuditContext()

        # Normalize API key hash to avoid storing raw secrets
        try:
            context.api_key_hash = _hash_api_key(context.api_key_hash)
        except Exception:
            context.api_key_hash = None

        # Create event
        tenant_user_id = None
        if self._shared_mode:
            tenant_user_id = self._resolve_tenant_id_for_write(
                raw_tenant=None,
                context_user_id=context.user_id,
                event_type=event_type,
                category=category,
            )
        event = AuditEvent(
            category=category,
            event_type=event_type,
            severity=severity,
            tenant_user_id=tenant_user_id,
            context=context,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result_norm,
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
                normalized_for_detection: Any | None = None
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
                    # Redact PII from the normalized form to ensure we handle nested
                    # dataclasses / pydantic models / non-primitive values correctly.
                    if normalized_for_detection is not None:
                        event.metadata = self.pii_detector.redact_obj(normalized_for_detection)
                    else:
                        # For metadata that cannot be normalized, store a JSON object with redacted text.
                        event.metadata = {"redacted_text": self.pii_detector.redact(metadata_str)}
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
        should_flush = False
        async with self.buffer_lock:
            self.event_buffer.append(event)
            self.stats["events_logged"] += 1
            should_flush = len(self.event_buffer) >= self.buffer_size or event.risk_score >= HIGH_RISK_SCORE

        # In test mode we avoid background tasks; flush only when needed.
        if self._test_mode:
            if should_flush:
                await self.flush()
        elif should_flush:
            # Task is tracked via _flush_futures in _tracked_flush() for graceful shutdown
            asyncio.create_task(self._tracked_flush())

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

    async def _tracked_flush(self) -> None:
        """Flush with proper tracking in _flush_futures for graceful shutdown.

        This wrapper ensures the task is added to and removed from the tracking
        set under the appropriate lock to avoid race conditions.
        """
        task = asyncio.current_task()
        async with self._flush_futures_lock:
            if task is not None:
                self._flush_futures.add(task)
        try:
            await self.flush()
        finally:
            async with self._flush_futures_lock:
                if task is not None:
                    self._flush_futures.discard(task)

    async def _fetch_existing_event_ids(
        self,
        db: aiosqlite.Connection,
        event_ids: List[str],
        *,
        chunk_size: int = 500,
    ) -> Set[str]:
        """Return existing event_ids in the DB for the supplied list."""
        if not event_ids:
            return set()
        existing: Set[str] = set()
        for i in range(0, len(event_ids), chunk_size):
            chunk = event_ids[i:i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            query = f"SELECT event_id FROM audit_events WHERE event_id IN ({placeholders})"
            async with db.execute(query, chunk) as cursor:
                rows = await cursor.fetchall()
                existing.update(str(row[0]) for row in rows if row and row[0])
        return existing

    async def _filter_new_events(
        self,
        db: aiosqlite.Connection,
        events: List[AuditEvent],
    ) -> List[AuditEvent]:
        """Filter events to those not already persisted (de-duplicated by event_id)."""
        if not events:
            return []
        seen: Set[str] = set()
        deduped: List[AuditEvent] = []
        for event in events:
            if not event.event_id or event.event_id in seen:
                continue
            seen.add(event.event_id)
            deduped.append(event)
        existing_ids = await self._fetch_existing_event_ids(db, [e.event_id for e in deduped])
        if not existing_ids:
            return deduped
        return [event for event in deduped if event.event_id not in existing_ids]

    async def flush(self, *, raise_on_failure: bool = False) -> bool:
        """Flush buffered events to database.

        Returns True when flush succeeds (or no events). When raise_on_failure is
        True, exceptions are propagated after fallback handling.
        """
        async with self.buffer_lock:
            if not self.event_buffer:
                return True

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
                            new_events = await self._filter_new_events(db, events)
                            if not new_events:
                                return True
                            # Prepare batch data
                            records = [event.to_dict() for event in new_events]
                            self._ensure_record_tenant_ids(records)
                            await db.executemany(self._event_insert_sql, records)
                            await self._update_daily_stats(db, new_events)
                            await db.commit()
                    else:
                        db = await self._ensure_db_pool()
                        async with self._db_lock:
                            new_events = await self._filter_new_events(db, events)
                            if not new_events:
                                return True
                            # Prepare batch data
                            records = [event.to_dict() for event in new_events]

                            # Batch insert
                            self._ensure_record_tenant_ids(records)
                            await db.executemany(self._event_insert_sql, records)

                            # Update daily statistics
                            await self._update_daily_stats(db, new_events)
                            await db.commit()

                    # Success
                    self.stats["events_flushed"] += len(new_events)
                    logger.debug(f"Flushed {len(new_events)} audit events to database")
                    last_error = None
                    return True
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
                        async with _fallback_queue_lock(fb_path):
                            await asyncio.to_thread(
                                self._append_events_to_fallback, fb_path, combined[max_buffer:]
                            )
                        logger.warning(
                            f"Audit flush failure: {dropped} events persisted to fallback queue at {fb_path}"
                        )
                    except Exception as _fe:
                        logger.error(f"Failed to write dropped audit events to fallback queue: {_fe}")
                else:
                    logger.warning("Audit flush failure: events re-buffered (no drop)")
                self.event_buffer = combined[:max_buffer]
            if raise_on_failure:
                raise
            return False
        return True

    def _append_events_to_fallback(self, fb_path: Path, events: List[AuditEvent]) -> None:
        """Write events to the fallback JSONL file."""
        with fb_path.open("a", encoding="utf-8") as fb:
            for ev in events:
                fb.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

    async def _update_daily_stats(self, db: aiosqlite.Connection, events: List[AuditEvent]):
        """Update daily statistics"""
        from collections import defaultdict

        # Aggregate by date and category
        stats = defaultdict(lambda: {
            "total": 0, "high_risk": 0, "failed": 0,
            "cost": 0.0, "tokens": 0, "durations": []
        })

        for event in events:
            ts = event.timestamp
            try:
                ts = _normalize_timestamp(ts)
            except Exception:
                pass
            if isinstance(ts, datetime):
                date = ts.date()
            else:
                date = event.timestamp.date()
            if self._shared_mode:
                tenant_id = self._resolve_event_tenant_id(event)
                key = (tenant_id, date, event.category.value)
            else:
                key = (date, event.category.value)

            stats[key]["total"] += 1
            if event.risk_score >= HIGH_RISK_SCORE:
                stats[key]["high_risk"] += 1
            # Treat only explicit failures/errors as failures; allow non-terminal
            # statuses like "started" without inflating failure counts.
            if (event.result or "").lower() in {"failure", "error"}:
                stats[key]["failed"] += 1
            if event.estimated_cost:
                stats[key]["cost"] += event.estimated_cost
            if event.tokens_used:
                stats[key]["tokens"] += event.tokens_used
            if event.duration_ms is not None:
                stats[key]["durations"].append(event.duration_ms)

        # Update database
        for key, data in stats.items():
            if self._shared_mode:
                tenant_id, date, category = key
            else:
                date, category = key
            duration_count = len(data["durations"])
            avg_duration = (
                sum(data["durations"]) / duration_count
                if duration_count > 0 else None
            )

            if self._shared_mode:
                await db.execute(
                    """
                    INSERT INTO audit_daily_stats (
                        tenant_user_id, date, category, total_events, high_risk_events,
                        failed_events, total_cost, total_tokens, avg_duration_ms,
                        duration_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_user_id, date, category) DO UPDATE SET
                        total_events = total_events + excluded.total_events,
                        high_risk_events = high_risk_events + excluded.high_risk_events,
                        failed_events = failed_events + excluded.failed_events,
                        total_cost = total_cost + excluded.total_cost,
                        total_tokens = total_tokens + excluded.total_tokens,
                        duration_count = COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0),
                        avg_duration_ms = CASE
                            WHEN COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0) = 0 THEN NULL
                            WHEN COALESCE(duration_count, 0) = 0 THEN excluded.avg_duration_ms
                            WHEN COALESCE(excluded.duration_count, 0) = 0 THEN avg_duration_ms
                            ELSE (
                                COALESCE(avg_duration_ms, 0) * COALESCE(duration_count, 0) +
                                COALESCE(excluded.avg_duration_ms, 0) * COALESCE(excluded.duration_count, 0)
                            ) / (COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0))
                        END
                    """,
                    (
                        tenant_id, date, category, data["total"], data["high_risk"],
                        data["failed"], data["cost"], data["tokens"], avg_duration,
                        duration_count,
                    ),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO audit_daily_stats (
                        date, category, total_events, high_risk_events,
                        failed_events, total_cost, total_tokens, avg_duration_ms,
                        duration_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, category) DO UPDATE SET
                        total_events = total_events + excluded.total_events,
                        high_risk_events = high_risk_events + excluded.high_risk_events,
                        failed_events = failed_events + excluded.failed_events,
                        total_cost = total_cost + excluded.total_cost,
                        total_tokens = total_tokens + excluded.total_tokens,
                        duration_count = COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0),
                        avg_duration_ms = CASE
                            WHEN COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0) = 0 THEN NULL
                            WHEN COALESCE(duration_count, 0) = 0 THEN excluded.avg_duration_ms
                            WHEN COALESCE(excluded.duration_count, 0) = 0 THEN avg_duration_ms
                            ELSE (
                                COALESCE(avg_duration_ms, 0) * COALESCE(duration_count, 0) +
                                COALESCE(excluded.avg_duration_ms, 0) * COALESCE(excluded.duration_count, 0)
                            ) / (COALESCE(duration_count, 0) + COALESCE(excluded.duration_count, 0))
                        END
                    """,
                    (
                        date, category, data["total"], data["high_risk"],
                        data["failed"], data["cost"], data["tokens"], avg_duration,
                        duration_count,
                    ),
                )

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

    async def replay_fallback_queue(self, max_batch: int = 5000) -> int:
        """Replay events from the fallback queue back into the main audit table."""
        fb_path = self.db_path.parent / "audit_fallback_queue.jsonl"
        async with _fallback_queue_lock(fb_path):
            if not fb_path.exists():
                return 0

            # Helpers for parsing and flushing
            def _parse_timestamp(val: Any) -> Optional[datetime]:
                if isinstance(val, datetime):
                    if val.tzinfo is None:
                        return val.replace(tzinfo=timezone.utc)
                    return val
                if val is None:
                    return None
                try:
                    s = str(val).strip()
                    if not s:
                        return None
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"
                    dt_val = datetime.fromisoformat(s)
                    if dt_val.tzinfo is None:
                        dt_val = dt_val.replace(tzinfo=timezone.utc)
                    return dt_val
                except Exception:
                    return None

            def _safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
                try:
                    if val is None:
                        return default
                    s = str(val).strip()
                    if s == "":
                        return default
                    return int(s)
                except Exception:
                    return default

            def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
                try:
                    if val is None:
                        return default
                    s = str(val).strip()
                    if s == "":
                        return default
                    return float(s)
                except Exception:
                    return default

            def _as_category(val: Any) -> AuditEventCategory:
                try:
                    if isinstance(val, AuditEventCategory):
                        return val
                    return AuditEventCategory(val)
                except Exception:
                    try:
                        return AuditEventCategory[str(val)]
                    except Exception:
                        return AuditEventCategory.SYSTEM

            def _as_event_type(val: Any) -> AuditEventType:
                try:
                    if isinstance(val, AuditEventType):
                        return val
                    return AuditEventType(val)
                except Exception:
                    try:
                        return AuditEventType[str(val)]
                    except Exception:
                        return AuditEventType.SYSTEM_START

            def _as_severity(val: Any) -> AuditSeverity:
                try:
                    if isinstance(val, AuditSeverity):
                        return val
                    return AuditSeverity(val)
                except Exception:
                    try:
                        return AuditSeverity[str(val)]
                    except Exception:
                        return AuditSeverity.INFO

            def _record_to_event(record: Dict[str, Any]) -> Optional[AuditEvent]:
                ts = _parse_timestamp(record.get("timestamp"))
                if ts is None:
                    return None
                ts = _normalize_timestamp(ts)
                # Normalize stored timestamp to UTC for lexicographic ordering.
                record["timestamp"] = ts.isoformat()

                # Parse compliance_flags from JSON string (fix for data loss)
                flags_raw = record.get("compliance_flags")
                if isinstance(flags_raw, str):
                    try:
                        compliance_flags = json.loads(flags_raw)
                        if not isinstance(compliance_flags, list):
                            compliance_flags = []
                    except Exception:
                        compliance_flags = []
                elif isinstance(flags_raw, list):
                    compliance_flags = flags_raw
                else:
                    compliance_flags = []

                # Parse metadata from JSON string (fix for data loss)
                meta_raw = record.get("metadata")
                if isinstance(meta_raw, str):
                    try:
                        metadata = json.loads(meta_raw)
                        if not isinstance(metadata, dict):
                            metadata = {}
                    except Exception:
                        metadata = {}
                elif isinstance(meta_raw, dict):
                    metadata = meta_raw
                else:
                    metadata = {}

                category_val = _as_category(record.get("category"))
                event_type_val = _as_event_type(record.get("event_type"))
                severity_val = _as_severity(record.get("severity"))

                tenant_user_id = None
                if self._shared_mode:
                    raw_tenant = record.get("tenant_user_id")
                    if raw_tenant is None or str(raw_tenant).strip() == "":
                        raw_tenant = record.get("context_user_id") or record.get("user_id")
                    tenant_user_id = self._resolve_tenant_id_for_write(
                        raw_tenant=raw_tenant,
                        context_user_id=record.get("context_user_id") or record.get("user_id"),
                        event_type=event_type_val,
                        category=category_val,
                    )

                return AuditEvent(
                    event_id=str(record.get("event_id") or uuid4()),
                    timestamp=ts,
                    category=category_val,
                    event_type=event_type_val,
                    severity=severity_val,
                    tenant_user_id=tenant_user_id,
                    resource_type=record.get("resource_type"),
                    resource_id=record.get("resource_id"),
                    action=record.get("action"),
                    result=str(record.get("result", "success")),
                    error_message=record.get("error_message"),
                    duration_ms=_safe_float(record.get("duration_ms")),
                    tokens_used=_safe_int(record.get("tokens_used")),
                    estimated_cost=_safe_float(record.get("estimated_cost")),
                    result_count=_safe_int(record.get("result_count")),
                    risk_score=_safe_int(record.get("risk_score"), 0) or 0,
                    pii_detected=bool(record.get("pii_detected") or False),
                    compliance_flags=compliance_flags,
                    metadata=metadata,
                )

            async def _flush_chunk(
                db: aiosqlite.Connection,
                records_chunk: List[Dict[str, Any]],
                stats_events: List[AuditEvent],
                use_db_lock: bool,
            ) -> int:
                if not records_chunk:
                    return 0

                async def _do_write() -> int:
                    record_ids = [str(r.get("event_id")) for r in records_chunk if r.get("event_id")]
                    existing_ids = await self._fetch_existing_event_ids(db, record_ids)
                    seen: Set[str] = set()
                    filtered_records: List[Dict[str, Any]] = []
                    for record in records_chunk:
                        event_id = record.get("event_id")
                        if not event_id:
                            continue
                        event_id = str(event_id)
                        if event_id in existing_ids or event_id in seen:
                            continue
                        seen.add(event_id)
                        filtered_records.append(record)

                    if not filtered_records:
                        return 0

                    self._ensure_record_tenant_ids(filtered_records)
                    await db.executemany(self._event_insert_sql, filtered_records)
                    if stats_events:
                        filtered_stats: List[AuditEvent] = []
                        stats_seen: Set[str] = set()
                        for ev in stats_events:
                            if not ev.event_id:
                                continue
                            if ev.event_id in existing_ids or ev.event_id not in seen:
                                continue
                            if ev.event_id in stats_seen:
                                continue
                            stats_seen.add(ev.event_id)
                            filtered_stats.append(ev)
                        if filtered_stats:
                            await self._update_daily_stats(db, filtered_stats)
                    await db.commit()
                    return len(filtered_records)

                if use_db_lock:
                    async with self._db_lock:
                        return await _do_write()
                else:
                    return await _do_write()

            temp_path = fb_path.with_suffix(".tmp")
            inserted = 0
            had_error = False
            wrote_temp = False

            async def _replay_stream(
                db: aiosqlite.Connection,
                use_db_lock: bool,
            ) -> int:
                """Replay lines in a streaming fashion, rewriting only unprocessed lines."""
                nonlocal inserted, had_error, wrote_temp
                records_chunk: List[Dict[str, Any]] = []
                stats_events: List[AuditEvent] = []
                lines_chunk: List[str] = []

                try:
                    with fb_path.open("r", encoding="utf-8") as src, temp_path.open("w", encoding="utf-8") as dst:
                        for line in src:
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                            except Exception:
                                continue
                            if not isinstance(data, dict):
                                continue

                            records_chunk.append(data)
                            lines_chunk.append(line)
                            ev = _record_to_event(data)
                            if ev:
                                stats_events.append(ev)

                            if len(records_chunk) >= max_batch:
                                try:
                                    count = await _flush_chunk(
                                        db, list(records_chunk), list(stats_events), use_db_lock
                                    )
                                except Exception as exc:
                                    had_error = True
                                    dst.writelines(lines_chunk)
                                    for rest in src:
                                        dst.write(rest)
                                    wrote_temp = True
                                    logger.error(f"Failed to replay audit fallback queue: {exc}")
                                    break
                                inserted += count
                                records_chunk.clear()
                                stats_events.clear()
                                lines_chunk.clear()

                        if not had_error and records_chunk:
                            try:
                                count = await _flush_chunk(
                                    db, list(records_chunk), list(stats_events), use_db_lock
                                )
                                inserted += count
                            except Exception as exc:
                                had_error = True
                                dst.writelines(lines_chunk)
                                wrote_temp = True
                                logger.error(f"Failed to replay audit fallback queue: {exc}")

                except Exception as e:
                    had_error = True
                    logger.error(f"Failed to read audit fallback queue: {e}")

                return inserted

            try:
                if self._test_mode:
                    async with aiosqlite.connect(self.db_path) as db:
                        db.row_factory = aiosqlite.Row
                        inserted = await _replay_stream(db, use_db_lock=False)
                else:
                    db = await self._ensure_db_pool()
                    inserted = await _replay_stream(db, use_db_lock=True)
            except asyncio.CancelledError:
                had_error = True
                raise
            except Exception as e:
                had_error = True
                logger.error(f"Failed to replay audit fallback queue: {e}")

            if not had_error:
                try:
                    if fb_path.exists():
                        fb_path.unlink()
                except Exception:
                    pass
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    pass
            else:
                if wrote_temp and temp_path.exists():
                    try:
                        temp_path.replace(fb_path)
                    except Exception:
                        pass
                else:
                    try:
                        if temp_path.exists():
                            temp_path.unlink()
                    except Exception:
                        pass

            if inserted and not had_error:
                logger.info(f"Replayed {inserted} audit events from fallback queue")
            return inserted

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
        offset: int = 0,
        allow_cross_tenant: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query audit events with filters"""
        self._touch()
        base_query, params = self._build_events_query(
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
            allow_cross_tenant=allow_cross_tenant,
        )

        query = "SELECT * " + base_query + " ORDER BY timestamp DESC, event_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            async with self._read_db() as db:
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
        allow_cross_tenant: bool = False,
    ) -> int:
        """Count audit events with filters."""
        self._touch()
        base_query, params = self._build_events_query(
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
            allow_cross_tenant=allow_cross_tenant,
        )
        query = "SELECT COUNT(*) as cnt " + base_query
        try:
            async with self._read_db() as db:
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
        allow_cross_tenant: bool = False,
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
            format: 'json', 'jsonl', or 'csv'
            file_path: If provided, write to this path; otherwise return content string
            chunk_size: Batch size when scanning DB
            stream: When True and file_path is None, return an async generator that yields output incrementally
            max_rows: Hard cap on rows returned/written

        Returns:
            If file_path is None: the exported content as a string
            If file_path is provided: the number of rows written
        """
        self._touch()
        fmt = (format or "json").lower()
        if fmt not in {"json", "csv", "jsonl"}:
            raise ValueError("format must be 'json', 'csv', or 'jsonl'")

        # When not streaming, enforce a capped row limit to avoid unbounded memory usage.
        if not stream and max_rows is None:
            max_rows = self.non_stream_max_rows

        # Fixed CSV header schema for consistency across export paths
        CSV_HEADERS: List[str] = list(self._csv_headers)

        def _maybe_load_json(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        def _deserialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
            out = dict(row)
            out["metadata"] = _maybe_load_json(out.get("metadata"))
            out["compliance_flags"] = _maybe_load_json(out.get("compliance_flags"))
            return out

        async def _fetch_chunk(
            *,
            limit: int,
            cursor_ts: Optional[str],
            cursor_event_id: Optional[str],
        ) -> List[Dict[str, Any]]:
            return await self._query_events_keyset(
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
                allow_cross_tenant=allow_cross_tenant,
                limit=limit,
                cursor_ts=cursor_ts,
                cursor_event_id=cursor_event_id,
            )

        # Streaming CSV export when writing to a file to reduce memory usage
        if fmt == "csv" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            rows_written = 0

            with p.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
                writer.writeheader()
                cursor_ts = None
                cursor_event_id = None
                while True:
                    if max_rows is not None:
                        remaining = max_rows - rows_written
                        if remaining <= 0:
                            break
                        limit = min(chunk_size, remaining)
                    else:
                        limit = chunk_size
                    chunk = await _fetch_chunk(
                        limit=limit,
                        cursor_ts=cursor_ts,
                        cursor_event_id=cursor_event_id,
                    )
                    if not chunk:
                        break
                    for r in chunk:
                        if max_rows is not None and rows_written >= max_rows:
                            break
                        writer.writerow(r)
                        rows_written += 1
                    cursor_ts, cursor_event_id = self._cursor_from_row(chunk[-1])
                    if (
                        len(chunk) < limit
                        or cursor_ts is None
                        or cursor_event_id is None
                        or (max_rows is not None and rows_written >= max_rows)
                    ):
                        break
            return rows_written

        # Streaming CSV directly to the caller (no prefetch) when requested
        if fmt == "csv" and file_path is None and stream:
            async def _csv_streamer():
                yield ",".join(CSV_HEADERS) + "\n"
                cursor_ts = None
                cursor_event_id = None
                written = 0
                while True:
                    rows = await _fetch_chunk(
                        limit=chunk_size,
                        cursor_ts=cursor_ts,
                        cursor_event_id=cursor_event_id,
                    )
                    if not rows:
                        break
                    buf = StringIO()
                    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS, extrasaction="ignore")
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        writer.writerow(r)
                        written += 1
                    chunk_str = buf.getvalue()
                    if chunk_str:
                        yield chunk_str
                    cursor_ts, cursor_event_id = self._cursor_from_row(rows[-1])
                    if (
                        len(rows) < chunk_size
                        or cursor_ts is None
                        or cursor_event_id is None
                        or (max_rows is not None and written >= max_rows)
                    ):
                        break
                    await asyncio.sleep(0)
            return _csv_streamer()

        # Streaming JSON/JSONL response to the caller when requested (no prefetch)
        if fmt in {"json", "jsonl"} and file_path is None and stream:
            async def _json_streamer():
                is_jsonl = (fmt == "jsonl")
                if not is_jsonl:
                    yield "["
                first = True
                cursor_ts = None
                cursor_event_id = None
                written = 0
                while True:
                    rows = await _fetch_chunk(
                        limit=chunk_size,
                        cursor_ts=cursor_ts,
                        cursor_event_id=cursor_event_id,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        payload = _deserialize_row(r)
                        if is_jsonl:
                            yield json.dumps(payload, ensure_ascii=False) + "\n"
                        else:
                            if not first:
                                yield ","
                            yield json.dumps(payload, ensure_ascii=False)
                            first = False
                        written += 1
                    # backpressure: yield control
                    await asyncio.sleep(0)
                    if max_rows is not None and written >= max_rows:
                        break
                    cursor_ts, cursor_event_id = self._cursor_from_row(rows[-1])
                    if len(rows) < chunk_size or cursor_ts is None or cursor_event_id is None:
                        break
                if not is_jsonl:
                    yield "]"
            return _json_streamer()

        # JSON file-path export: stream directly to file to avoid prefetch
        if fmt == "json" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            cursor_ts = None
            cursor_event_id = None
            written = 0
            with p.open("w", encoding="utf-8") as f:
                f.write("[")
                first = True
                while True:
                    rows = await _fetch_chunk(
                        limit=chunk_size,
                        cursor_ts=cursor_ts,
                        cursor_event_id=cursor_event_id,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        if not first:
                            f.write(",")
                        f.write(json.dumps(_deserialize_row(r), ensure_ascii=False))
                        written += 1
                        first = False
                    cursor_ts, cursor_event_id = self._cursor_from_row(rows[-1])
                    if (
                        len(rows) < chunk_size
                        or cursor_ts is None
                        or cursor_event_id is None
                        or (max_rows is not None and written >= max_rows)
                    ):
                        break
                f.write("]")
            return written

        # JSONL file-path export: stream directly to file to avoid prefetch
        if fmt == "jsonl" and file_path is not None:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            cursor_ts = None
            cursor_event_id = None
            written = 0
            with p.open("w", encoding="utf-8") as f:
                while True:
                    rows = await _fetch_chunk(
                        limit=chunk_size,
                        cursor_ts=cursor_ts,
                        cursor_event_id=cursor_event_id,
                    )
                    if not rows:
                        break
                    for r in rows:
                        if max_rows is not None and written >= max_rows:
                            break
                        f.write(json.dumps(_deserialize_row(r), ensure_ascii=False) + "\n")
                        written += 1
                    cursor_ts, cursor_event_id = self._cursor_from_row(rows[-1])
                    if (
                        len(rows) < chunk_size
                        or cursor_ts is None
                        or cursor_event_id is None
                        or (max_rows is not None and written >= max_rows)
                    ):
                        break
            return written

        # Otherwise, gather rows in chunks to return content in-memory
        all_rows: List[Dict[str, Any]] = []
        cursor_ts = None
        cursor_event_id = None
        written = 0
        while True:
            rows = await _fetch_chunk(
                limit=chunk_size,
                cursor_ts=cursor_ts,
                cursor_event_id=cursor_event_id,
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
            cursor_ts, cursor_event_id = self._cursor_from_row(rows[-1])
            if len(rows) < chunk_size or cursor_ts is None or cursor_event_id is None:
                break

        if fmt == "json":
            # If no file path, return JSON content as a single string
            if file_path is None:
                content = json.dumps(
                    [_deserialize_row(r) for r in all_rows],
                    ensure_ascii=False,
                )
                return content
            # File-path handled earlier
            return 0
        elif fmt == "jsonl":
            # JSON Lines: one JSON object per line
            if file_path is None:
                # Return content as newline-separated JSON objects
                return "\n".join(
                    json.dumps(_deserialize_row(r), ensure_ascii=False) for r in all_rows
                )
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
        result_norm = _normalize_result(result)
        # Critical events
        if event_type in [
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.SUSPICIOUS_ACTIVITY
        ]:
            return AuditSeverity.CRITICAL

        if result_norm == "error":
            return AuditSeverity.ERROR
        elif result_norm == "failure":
            return AuditSeverity.WARNING

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

    async def get_security_summary(
        self,
        hours: int = 24,
        *,
        user_id: Optional[str] = None,
        allow_cross_tenant: bool = True,
    ) -> Dict[str, Any]:
        """Aggregate recent security-related audit stats for health checks.

        Args:
            hours: Lookback window in hours
            user_id: Optional tenant filter for shared mode
            allow_cross_tenant: Allow cross-tenant aggregation in shared mode

        Returns:
            Dictionary with summary stats: high_risk_events, failure_events,
            unique_security_users, top_failing_ips
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        start_iso = start_time.isoformat()
        cat = AuditEventCategory.SECURITY.value

        async def _summarize(db: aiosqlite.Connection) -> Dict[str, Any]:
            tenant_clause = ""
            tenant_params: List[Any] = []
            if self._shared_mode:
                if user_id:
                    tenant_clause = " AND tenant_user_id = ?"
                    tenant_params.append(self._normalize_tenant_id(user_id))
                elif not allow_cross_tenant:
                    tenant_clause = " AND 1=0"
            user_field = "tenant_user_id" if self._shared_mode else "context_user_id"

            def _params(*base: Any) -> List[Any]:
                return list(base) + tenant_params

            # Total security events in window
            async with db.execute(
                f"SELECT COUNT(*) FROM audit_events WHERE timestamp >= ? AND category = ?{tenant_clause}",
                _params(start_iso, cat),
            ) as cur:
                row = await cur.fetchone()
                total_events = int(row[0]) if row else 0

            # High-risk security events in window
            async with db.execute(
                (
                    "SELECT COUNT(*) FROM audit_events "
                    f"WHERE timestamp >= ? AND category = ? AND risk_score >= ?{tenant_clause}"
                ),
                _params(start_iso, cat, HIGH_RISK_SCORE),
            ) as cur:
                row = await cur.fetchone()
                high_risk_events = int(row[0]) if row else 0

            # Failures (exclude non-terminal statuses like 'started')
            async with db.execute(
                """
                SELECT COUNT(*)
                FROM audit_events
                WHERE timestamp >= ?
                  AND category = ?
                  AND LOWER(COALESCE(result, '')) IN ('failure', 'error')
                """ + tenant_clause,
                _params(start_iso, cat),
            ) as cur:
                row = await cur.fetchone()
                failure_events = int(row[0]) if row else 0

            async with db.execute(
                f"""
                SELECT COUNT(DISTINCT {user_field})
                FROM audit_events
                WHERE timestamp >= ?
                  AND category = ?
                  AND {user_field} IS NOT NULL
                  AND {user_field} != ''
                {tenant_clause}
                """,
                _params(start_iso, cat),
            ) as cur:
                row = await cur.fetchone()
                unique_security_users = int(row[0]) if row else 0

            # Top IPs observed for security events
            top_failing_ips: List[str] = []
            async with db.execute(
                """
                SELECT context_ip_address, COUNT(*) AS cnt
                FROM audit_events
                WHERE timestamp >= ?
                  AND category = ?
                  AND context_ip_address IS NOT NULL
                  AND context_ip_address != ''
                """ + tenant_clause + """
                GROUP BY context_ip_address
                ORDER BY cnt DESC
                LIMIT 5
                """,
                _params(start_iso, cat),
            ) as cur:
                rows = await cur.fetchall()
                top_failing_ips = [str(r[0]) for r in rows if r and r[0]]

            return {
                "high_risk_events": high_risk_events,
                "failure_events": failure_events,
                "unique_security_users": unique_security_users,
                "top_failing_ips": top_failing_ips,
                "total_events": total_events,
            }

        async with self._read_db() as db:
            return await _summarize(db)

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
