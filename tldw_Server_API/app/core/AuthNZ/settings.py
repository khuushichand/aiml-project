# settings.py
# Description: Pydantic settings for user registration system with persistent JWT secret management
#
# Imports
import os
import secrets
from pathlib import Path
from typing import Literal, Optional
#
# 3rd-party imports
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
#
# Local imports
from loguru import logger
try:
    # Prefer centralized loader to honor project config precedence
    from tldw_Server_API.app.core.config import load_comprehensive_config, settings as core_settings
except Exception:
    load_comprehensive_config = None  # Fallback if import graph changes
    core_settings = None

#######################################################################################################################
#
# Settings Class

class Settings(BaseSettings):
    """Configuration with persistent secret management for user registration system"""

    # ===== Core Settings =====
    AUTH_MODE: Literal["single_user", "multi_user"] = Field(
        default="single_user",
        description="Authentication mode: single_user (API key) or multi_user (JWT)"
    )

    DATABASE_URL: str = Field(
        default="sqlite:///./Databases/users.db",
        description="Database URL - PostgreSQL for multi-user: postgresql://user:pass@localhost/tldw"
    )

    # ===== JWT Settings with secure storage =====
    JWT_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="JWT signing key - MUST be set via environment variable in production"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )

    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration time in days"
    )

    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    JWT_PRIVATE_KEY: Optional[str] = Field(
        default=None,
        description="PEM-encoded private key for asymmetric JWT signing (RS256/ES256)"
    )
    JWT_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="PEM-encoded public key for asymmetric JWT verification (RS256/ES256)"
    )
    JWT_SECONDARY_SECRET: Optional[str] = Field(
        default=None,
        description="Optional secondary HS secret for dual-validation during rotations"
    )
    JWT_SECONDARY_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="Optional secondary public key (RS/ES) for dual-validation during rotations"
    )

    # Optional JWT claims enforcement (recommended in production)
    JWT_ISSUER: Optional[str] = Field(
        default=None,
        description="Expected JWT issuer (iss). If set, tokens must include matching iss"
    )
    JWT_AUDIENCE: Optional[str] = Field(
        default=None,
        description="Expected JWT audience (aud). If set, tokens must include matching aud"
    )

    # ===== Password Settings =====
    PASSWORD_MIN_LENGTH: int = Field(
        default=10,
        ge=8,
        description="Minimum password length"
    )

    ARGON2_MEMORY_COST: int = Field(
        default=32768,  # 32MB
        description="Argon2 memory cost parameter"
    )

    ARGON2_TIME_COST: int = Field(
        default=2,
        description="Argon2 time cost (iterations)"
    )

    ARGON2_PARALLELISM: int = Field(
        default=1,
        description="Argon2 parallelism factor"
    )

    # ===== Redis Configuration (Optional) =====
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for session caching (optional)"
    )

    REDIS_MAX_CONNECTIONS: int = Field(
        default=50,
        description="Maximum Redis connections"
    )

    # ===== Security Settings =====
    ENABLE_REGISTRATION: bool = Field(
        default=False,
        description="Enable user registration"
    )

    REQUIRE_REGISTRATION_CODE: bool = Field(
        default=True,
        description="Require registration code for new users"
    )

    MAX_LOGIN_ATTEMPTS: int = Field(
        default=5,
        ge=3,
        description="Maximum login attempts before lockout"
    )

    LOCKOUT_DURATION_MINUTES: int = Field(
        default=15,
        ge=5,
        description="Account lockout duration in minutes"
    )

    # ===== Rate Limiting =====
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable rate limiting"
    )

    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        ge=10,
        description="Requests allowed per minute"
    )

    RATE_LIMIT_BURST: int = Field(
        default=10,
        ge=5,
        description="Burst requests allowed"
    )

    # ===== Storage Settings =====
    DEFAULT_STORAGE_QUOTA_MB: int = Field(
        default=5120,  # 5GB
        ge=100,
        description="Default storage quota in MB"
    )

    USER_DATA_BASE_PATH: str = Field(
        default="./user_databases",
        description="Base path for user data directories"
    )

    CHROMADB_BASE_PATH: str = Field(
        default="",
        description="Base path for ChromaDB data"
    )

    # ===== Registration Settings =====
    DEFAULT_USER_ROLE: str = Field(
        default="user",
        description="Default role for new users"
    )

    REGISTRATION_CODE_DEFAULT_EXPIRY_DAYS: int = Field(
        default=7,
        ge=1,
        description="Default registration code expiry in days"
    )

    REGISTRATION_CODE_DEFAULT_MAX_USES: int = Field(
        default=1,
        ge=1,
        description="Default maximum uses for registration code"
    )

    MAX_BATCH_REGISTRATION_CODES: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum registration codes per batch"
    )

    # ===== Database Pool Settings =====
    DATABASE_POOL_MIN_SIZE: int = Field(
        default=5,
        ge=1,
        description="Minimum database pool size"
    )

    DATABASE_POOL_MAX_SIZE: int = Field(
        default=20,
        ge=5,
        description="Maximum database pool size"
    )

    DATABASE_MAX_QUERIES: int = Field(
        default=50000,
        description="Maximum queries before connection reset"
    )

    DATABASE_MAX_INACTIVE_CONNECTION_LIFETIME: int = Field(
        default=300,
        description="Maximum inactive connection lifetime in seconds"
    )

    # ===== Session Settings =====
    SESSION_COOKIE_SECURE: bool = Field(
        default=True,
        description="Use secure cookies (HTTPS only)"
    )

    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="HTTP-only cookies (no JavaScript access)"
    )

    SESSION_COOKIE_SAMESITE: str = Field(
        default="lax",
        description="SameSite cookie attribute"
    )

    SESSION_CLEANUP_INTERVAL_HOURS: int = Field(
        default=1,
        ge=1,
        description="Session cleanup interval in hours"
    )

    # ===== Encryption Settings =====
    SESSION_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Base64-encoded Fernet key for session token encryption (auto-generated if not set)"
    )

    API_KEY_PEPPER: Optional[str] = Field(
        default=None,
        description="Additional secret for API key hashing (recommended for production)"
    )

    # Optional: log a lightweight 'used' entry when an API key validates
    API_KEY_AUDIT_LOG_USAGE: bool = Field(
        default=False,
        description="If true, log a 'used' event in API key audit log on successful validation"
    )

    # ===== Token Rotation =====
    ROTATE_REFRESH_TOKENS: bool = Field(
        default=True,
        description="Rotate refresh tokens on use (recommended). Returns new refresh token in /auth/refresh"
    )

    # ===== Logging / PII =====
    PII_REDACT_LOGS: bool = Field(
        default=True,
        description="Redact usernames/IPs in auth logs (recommended in production)"
    )

    # ===== CSRF Binding (Optional) =====
    CSRF_BIND_TO_USER: bool = Field(
        default=False,
        description="Bind CSRF token to user context via HMAC when user_id available"
    )

    # ===== RBAC / Usage Logging =====
    RBAC_SOFT_ENFORCE: bool = Field(
        default=False,
        description="If true, permission checks log warnings instead of 403 (deployment opt-in)"
    )
    USAGE_LOG_ENABLED: bool = Field(
        default=False,
        description="If true, record lightweight per-request usage into usage_log"
    )
    USAGE_LOG_EXCLUDE_PREFIXES: list[str] = Field(
        default_factory=lambda: [
            "/docs", "/redoc", "/openapi.json", "/metrics", "/static", "/favicon.ico", "/webui"
        ],
        description="Request path prefixes to exclude from usage logging"
    )
    USAGE_AGGREGATOR_INTERVAL_MINUTES: int = Field(
        default=60,
        ge=1,
        le=24 * 60,
        description="Background usage aggregator interval in minutes"
    )
    # Disable capturing IP/User-Agent in usage_log.meta entirely
    USAGE_LOG_DISABLE_META: bool = Field(
        default=False,
        description="When true, do not store IP/User-Agent in usage_log meta (stores '{}')"
    )

    # ===== LLM Usage Logging =====
    LLM_USAGE_ENABLED: bool = Field(
        default=True,
        description="If true, record per-request LLM usage into llm_usage_log (can be overridden by env)"
    )

    # ===== LLM Usage Aggregation =====
    LLM_USAGE_AGGREGATOR_ENABLED: bool = Field(
        default=True,
        description="Enable background aggregation of llm_usage_log into llm_usage_daily"
    )
    LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES: int = Field(
        default=60,
        ge=1,
        le=24 * 60,
        description="Background LLM usage aggregator interval in minutes"
    )

    # ===== Usage Log Retention =====
    USAGE_LOG_RETENTION_DAYS: int = Field(
        default=180,
        ge=1,
        le=3650,
        description="Retention window for usage_log rows (days)"
    )
    LLM_USAGE_LOG_RETENTION_DAYS: int = Field(
        default=180,
        ge=1,
        le=3650,
        description="Retention window for llm_usage_log rows (days)"
    )

    # Optional: retention for daily aggregates
    USAGE_DAILY_RETENTION_DAYS: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Retention window for usage_daily rows (days)"
    )
    LLM_USAGE_DAILY_RETENTION_DAYS: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Retention window for llm_usage_daily rows (days)"
    )
    PRIVILEGE_SNAPSHOT_RETENTION_DAYS: int = Field(
        default=90,
        ge=7,
        le=3650,
        description="Days to retain privilege snapshots at full fidelity before downsampling"
    )
    PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Days to retain downsampled (weekly) privilege snapshots before purging"
    )

    # ===== Virtual Keys / LLM Budgeting =====
    VIRTUAL_KEYS_ENABLED: bool = Field(
        default=True,
        description="Enable Virtual API Keys features (org/team association, budgets)"
    )
    LLM_BUDGET_ENFORCE: bool = Field(
        default=True,
        description="Reject requests from over-budget virtual keys"
    )
    LLM_BUDGET_ENDPOINTS: list[str] = Field(
        default_factory=lambda: [
            "/api/v1/chat/completions",
            "/api/v1/embeddings"
        ],
        description="Paths where LLM budget middleware is applied"
    )

    # ===== Monitoring =====
    ENABLE_HEALTH_CHECK: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    ENABLE_METRICS: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )

    # ===== Security Alerting =====
    SECURITY_ALERTS_ENABLED: bool = Field(
        default=False,
        description="Enable AuthNZ security alerts (file/webhook/email)."
    )
    SECURITY_ALERT_MIN_SEVERITY: str = Field(
        default="high",
        description="Minimum severity to dispatch security alerts (low|medium|high|critical)."
    )
    SECURITY_ALERT_FILE_PATH: str = Field(
        default="Databases/security_alerts.log",
        description="File path for security alert JSONL sink."
    )
    SECURITY_ALERT_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Webhook URL for security alerts (optional)."
    )
    SECURITY_ALERT_WEBHOOK_HEADERS: Optional[str] = Field(
        default=None,
        description="JSON object of additional headers to include in security alert webhooks."
    )
    SECURITY_ALERT_EMAIL_TO: Optional[str] = Field(
        default=None,
        description="Comma-separated list of email recipients for security alerts."
    )
    SECURITY_ALERT_EMAIL_FROM: Optional[str] = Field(
        default=None,
        description="Email sender address for security alerts."
    )
    SECURITY_ALERT_EMAIL_SUBJECT_PREFIX: str = Field(
        default="[AuthNZ]",
        description="Subject prefix for security alert emails."
    )
    SECURITY_ALERT_SMTP_HOST: Optional[str] = Field(
        default=None,
        description="SMTP host for security alert emails."
    )
    SECURITY_ALERT_SMTP_PORT: int = Field(
        default=587,
        description="SMTP port for security alert emails."
    )
    SECURITY_ALERT_SMTP_STARTTLS: bool = Field(
        default=True,
        description="Use STARTTLS for security alert emails."
    )
    SECURITY_ALERT_SMTP_USERNAME: Optional[str] = Field(
        default=None,
        description="SMTP username for security alert emails."
    )
    SECURITY_ALERT_SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="SMTP password for security alert emails."
    )
    SECURITY_ALERT_SMTP_TIMEOUT: int = Field(
        default=10,
        ge=1,
        description="Timeout (seconds) for SMTP connections when sending security alerts."
    )
    SECURITY_ALERT_BACKOFF_SECONDS: int = Field(
        default=30,
        ge=0,
        description="Backoff window after a sink failure before retrying (seconds)."
    )
    SECURITY_ALERT_FILE_MIN_SEVERITY: Optional[str] = Field(
        default=None,
        description="Minimum severity to write alerts to the file sink (default: use global threshold)."
    )
    SECURITY_ALERT_WEBHOOK_MIN_SEVERITY: Optional[str] = Field(
        default=None,
        description="Minimum severity to deliver alerts to the webhook sink (default: use global threshold)."
    )
    SECURITY_ALERT_EMAIL_MIN_SEVERITY: Optional[str] = Field(
        default=None,
        description="Minimum severity to deliver alerts via email (default: use global threshold)."
    )

    METRICS_PORT: int = Field(
        default=9090,
        ge=1024,
        le=65535,
        description="Prometheus metrics port"
    )

    # ===== Data Retention =====
    AUDIT_LOG_RETENTION_DAYS: int = Field(
        default=180,
        ge=30,
        description="Audit log retention in days"
    )

    PASSWORD_HISTORY_RETENTION_COUNT: int = Field(
        default=5,
        ge=3,
        description="Number of previous passwords to remember"
    )

    SESSION_LOG_RETENTION_DAYS: int = Field(
        default=90,
        ge=7,
        description="Session log retention in days"
    )

    # ===== Single-User Mode Settings =====
    SINGLE_USER_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for single-user mode - MUST be set via environment variable"
    )

    SINGLE_USER_FIXED_ID: int = Field(
        default=1,
        description="Fixed user ID for single-user mode"
    )
    # Optional IP allowlist for single-user mode (comma-separated env or list)
    SINGLE_USER_ALLOWED_IPS: list[str] = Field(
        default_factory=list,
        description="Optional list of allowed client IPs/CIDRs for SINGLE_USER_API_KEY"
    )

    # ===== Service Account Settings =====
    SERVICE_ACCOUNT_RATE_LIMIT: int = Field(
        default=1000,
        ge=100,
        description="Rate limit for service accounts per minute"
    )

    def __init__(self, **kwargs):
        """Initialize settings and ensure JWT secret persistence"""
        super().__init__(**kwargs)
        self._ensure_jwt_secret()
        self._validate_api_key()

    def _ensure_jwt_secret(self):
        """Ensure JWT secret exists with secure handling"""
        # Skip JWT secret handling in single-user mode
        if self.AUTH_MODE == "single_user":
            logger.debug("Single-user mode - skipping JWT secret initialization")
            return

        alg_upper = (self.JWT_ALGORITHM or "").upper()
        if alg_upper.startswith(("RS", "ES")) and self.JWT_PRIVATE_KEY:
            # Asymmetric algorithms supply their own key material; a symmetric secret is unnecessary
            logger.debug(
                "Asymmetric JWT algorithm %s detected with private key; skipping JWT secret requirement",
                self.JWT_ALGORITHM,
            )
            return

        # Environment variable is REQUIRED for JWT secret
        if self.JWT_SECRET_KEY:
            # Secret provided via environment - validate it
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters for security.\n"
                    "Set it via environment or .env. Example:\n"
                    "  export JWT_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")\n"
                    "See README: Authentication Setup."
                )

            # Hard fail in production if default/weak
            prod_flag = os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
            if prod_flag:
                default_values = {"CHANGE_ME_TO_SECURE_RANDOM_KEY_MIN_32_CHARS"}
                if self.JWT_SECRET_KEY in default_values:
                    raise ValueError(
                        "In production (tldw_production=true), JWT_SECRET_KEY must not use default template values.\n"
                        "Set a strong key via environment or .env. Example:\n"
                        "  export JWT_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
                    )
            logger.info("Using configured JWT secret key")
            return

        # Allow deterministic fallback in explicit test contexts
        test_mode = (
            os.getenv("PYTEST_CURRENT_TEST") is not None
            or os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        )
        if test_mode:
            fallback = os.getenv(
                "JWT_SECRET_TEST_KEY",
                "test-secret-jwt-key-please-change-1234567890"
            )
            if len(fallback) < 32:
                fallback = (fallback * 2)[:32]
            self.JWT_SECRET_KEY = fallback
            logger.debug("Initialized deterministic JWT secret for test context")
            return

        # No JWT secret available - this is a configuration error
        raise ValueError(
            "JWT_SECRET_KEY must be set via environment variable for multi-user mode.\n"
            "Set it via environment or .env. Example:\n"
            "  export JWT_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")\n"
            "This is required for security."
        )

    def _validate_api_key(self):
        """Validate API key for single-user mode with deterministic test fallback."""
        if self.AUTH_MODE == "single_user":
            # If an explicit key is provided via env/.env, honor it (legacy API_KEY supported)
            explicit_env_key = os.getenv("SINGLE_USER_API_KEY") or os.getenv("API_KEY")

            # Detect test contexts where the server should expose a stable key so client tests can authenticate
            # Only rely on environment of the server process, never trust request headers
            # Detect test contexts eagerly. Some test suites import the app before
            # setting TEST_MODE or PYTEST_CURRENT_TEST, so also check for the
            # presence of the pytest module and the TESTING flag.
            try:
                import sys as _sys  # Local import to avoid module-level cost
            except Exception:
                _sys = None
            in_test_context = (
                os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes")
                or os.getenv("TESTING", "").lower() in ("true", "1", "yes")
                or os.getenv("PYTEST_CURRENT_TEST") is not None
                or (isinstance(_sys, object) and ("pytest" in getattr(_sys, "modules", {})))
                or os.getenv("E2E_TEST_BASE_URL") is not None
            )

            if not self.SINGLE_USER_API_KEY:
                if explicit_env_key:
                    # Loaded by pydantic from env but still None here? Ensure it's applied
                    self.SINGLE_USER_API_KEY = explicit_env_key
                    logger.info("Using SINGLE_USER_API_KEY from environment for single-user mode")
                elif in_test_context:
                    # Deterministic key so tests can authenticate reliably.
                    test_key = os.getenv("SINGLE_USER_TEST_API_KEY", "test-api-key-12345")
                    self.SINGLE_USER_API_KEY = test_key
                    logger.debug("Using deterministic SINGLE_USER_API_KEY for test context")
                else:
                    raise ValueError(
                        "SINGLE_USER_API_KEY is required for single-user mode but is not configured.\n"
                        "Generate a secure key by running:\n"
                        "  python -m tldw_Server_API.app.core.AuthNZ.initialize\n"
                        "and follow the prompts (option \"Generate secure keys\").\n"
                        "Then set SINGLE_USER_API_KEY in your environment or .env file."
                    )
            # In test contexts, normalize known placeholder keys to a deterministic test key
            elif in_test_context and (
                self.SINGLE_USER_API_KEY in {"CHANGE_ME_TO_SECURE_API_KEY", "default-secret-key-for-single-user", "change-me-in-production"}
            ):
                test_key = os.getenv("SINGLE_USER_TEST_API_KEY", "test-api-key-12345")
                self.SINGLE_USER_API_KEY = test_key
                logger.debug("Normalized SINGLE_USER_API_KEY to deterministic test key for pytest context")
            elif self.SINGLE_USER_API_KEY == "change-me-in-production":
                raise ValueError(
                    "Default API key detected! Please set SINGLE_USER_API_KEY via environment or .env.\n"
                    "Example:\n"
                    "  export SINGLE_USER_API_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
                )
            elif len(self.SINGLE_USER_API_KEY) < 16:
                # Allow short keys in explicit test contexts to avoid brittle fixtures
                if in_test_context:
                    return
                raise ValueError(
                    "SINGLE_USER_API_KEY must be at least 16 characters.\n"
                    "Set it via environment or .env. Example:\n"
                    "  export SINGLE_USER_API_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
                )

            # Hard fail in production if key is missing/weak/default
            prod_flag = os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
            if prod_flag:
                weak = (
                    not self.SINGLE_USER_API_KEY
                    or self.SINGLE_USER_API_KEY in {"CHANGE_ME_TO_SECURE_API_KEY", "test-api-key-12345", "change-me-in-production"}
                    or len(self.SINGLE_USER_API_KEY) < 24
                )
                if weak:
                    raise ValueError(
                        "In production (tldw_production=true), SINGLE_USER_API_KEY must be set to a secure value (>=24 chars) "
                        "and must not use defaults.\nSet it via environment or .env. Example:\n"
                        "  export SINGLE_USER_API_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
                    )

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v, info):
        """Validate JWT secret strength"""
        # Skip validation in single-user mode
        if info.data.get("AUTH_MODE") == "single_user":
            return v

        if v and len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("SINGLE_USER_ALLOWED_IPS", mode="before")
    @classmethod
    def parse_single_user_allowed_ips(cls, v):
        """Allow env string like '127.0.0.1,10.0.0.0/8' to map to list[str]."""
        if not v:
            return []
        if isinstance(v, str):
            try:
                return [s.strip() for s in v.split(',') if s.strip()]
            except Exception:
                return []
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v, info):
        """Validate database URL based on auth mode"""
        auth_mode = info.data.get("AUTH_MODE", "single_user")

        if auth_mode == "multi_user" and v.startswith("sqlite"):
            # In production, disallow SQLite for multi-user mode
            prod_flag = os.getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
            if prod_flag:
                raise ValueError(
                    "In production (tldw_production=true) with AUTH_MODE=multi_user, SQLite is not supported.\n"
                    "Please configure PostgreSQL via DATABASE_URL. Examples:\n"
                    "  export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users\n"
                    "  # With docker-compose service name:\n"
                    "  export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@postgres:5432/tldw_users\n"
                    "See Multi-User Deployment Guide for details."
                )
            else:
                logger.warning(
                    "Using SQLite in multi-user mode is not recommended. "
                    "Consider using PostgreSQL for better concurrency."
                )

        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v):
        """Validate Redis URL format if provided"""
        if v and not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow"  # Allow extra fields for backward compatibility
    }


# ===== Singleton Settings Instance =====
_settings: Optional[Settings] = None


def _bool_from_str(val: str) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_overrides_from_config() -> dict:
    """Load Settings overrides from Config_Files/config.txt (AuthNZ section).

    Environment variables retain precedence; only provide values that are
    NOT already present in the environment.
    """
    overrides = {}
    if not load_comprehensive_config:
        return overrides
    try:
        cfg = load_comprehensive_config()
        if not cfg or not cfg.has_section("AuthNZ"):
            return overrides

        def maybe_set(field: str, key: str, caster=lambda v: v):
            # Map config key to Settings field if env var not set
            env_name = field
            if os.getenv(env_name) is None and cfg.has_option("AuthNZ", key):
                try:
                    overrides[field] = caster(cfg.get("AuthNZ", key))
                except Exception:
                    pass

        maybe_set("AUTH_MODE", "auth_mode", lambda v: v.strip())
        maybe_set("DATABASE_URL", "database_url", lambda v: v.strip())
        maybe_set("JWT_SECRET_KEY", "jwt_secret_key", lambda v: v.strip())
        maybe_set("SINGLE_USER_API_KEY", "single_user_api_key", lambda v: v.strip())
        maybe_set("ENABLE_REGISTRATION", "enable_registration", _bool_from_str)
        # Legacy aliases in config.txt
        maybe_set("ENABLE_REGISTRATION", "registration_enabled", _bool_from_str)
        maybe_set("REQUIRE_REGISTRATION_CODE", "require_registration_code", _bool_from_str)
        maybe_set("REQUIRE_REGISTRATION_CODE", "registration_require_code", _bool_from_str)
        maybe_set("RATE_LIMIT_ENABLED", "rate_limit_enabled", _bool_from_str)
        maybe_set("RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute", lambda v: int(v))
        maybe_set("RATE_LIMIT_BURST", "rate_limit_burst", lambda v: int(v))
        maybe_set("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes", lambda v: int(v))
        maybe_set("REFRESH_TOKEN_EXPIRE_DAYS", "refresh_token_expire_days", lambda v: int(v))
        maybe_set("REDIS_URL", "redis_url", lambda v: v.strip())
        maybe_set("SECURITY_ALERTS_ENABLED", "security_alerts_enabled", _bool_from_str)
        maybe_set("SECURITY_ALERT_MIN_SEVERITY", "security_alert_min_severity", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_FILE_PATH", "security_alert_file_path", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_WEBHOOK_URL", "security_alert_webhook_url", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_WEBHOOK_HEADERS", "security_alert_webhook_headers", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_EMAIL_TO", "security_alert_email_to", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_EMAIL_FROM", "security_alert_email_from", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_EMAIL_SUBJECT_PREFIX", "security_alert_email_subject_prefix", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_SMTP_HOST", "security_alert_smtp_host", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_SMTP_PORT", "security_alert_smtp_port", lambda v: int(v))
        maybe_set("SECURITY_ALERT_SMTP_STARTTLS", "security_alert_smtp_starttls", _bool_from_str)
        maybe_set("SECURITY_ALERT_SMTP_USERNAME", "security_alert_smtp_username", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_SMTP_PASSWORD", "security_alert_smtp_password", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_SMTP_TIMEOUT", "security_alert_smtp_timeout", lambda v: int(v))
        maybe_set("SECURITY_ALERT_FILE_MIN_SEVERITY", "security_alert_file_min_severity", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_WEBHOOK_MIN_SEVERITY", "security_alert_webhook_min_severity", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_EMAIL_MIN_SEVERITY", "security_alert_email_min_severity", lambda v: v.strip())
        maybe_set("SECURITY_ALERT_BACKOFF_SECONDS", "security_alert_backoff_seconds", lambda v: int(v))

        # If DATABASE_URL is not provided via env or explicit key, synthesize from db_type fields
        if os.getenv("DATABASE_URL") is None and "DATABASE_URL" not in overrides:
            if cfg.has_option("AuthNZ", "db_type"):
                db_type = cfg.get("AuthNZ", "db_type").strip().lower()
                if db_type == "sqlite":
                    # sqlite_path supports relative paths; default to Databases/users.db
                    sqlite_path = cfg.get("AuthNZ", "sqlite_path", fallback="./Databases/users.db").strip()
                    overrides["DATABASE_URL"] = f"sqlite:///{sqlite_path}"
                elif db_type in {"postgres", "postgresql"}:
                    host = cfg.get("AuthNZ", "pg_host", fallback="localhost").strip()
                    port = cfg.get("AuthNZ", "pg_port", fallback="5432").strip()
                    db   = cfg.get("AuthNZ", "pg_db", fallback="tldw_users").strip()
                    user = cfg.get("AuthNZ", "pg_user", fallback="tldw_user").strip()
                    # Do NOT silently synthesize with a placeholder password.
                    pwd  = cfg.get("AuthNZ", "pg_password", fallback="").strip()
                    sslm = cfg.get("AuthNZ", "pg_sslmode", fallback="prefer").strip()
                    if not pwd:
                        # In production, require explicit password; outside, skip synthesis to avoid insecure defaults
                        from os import getenv as _getenv
                        prod_flag = _getenv("tldw_production", "false").lower() in {"true", "1", "yes", "y", "on"}
                        logger.warning("AuthNZ: pg_password not set in config.txt; not synthesizing DATABASE_URL.")
                        if prod_flag:
                            # Leave DATABASE_URL unset to force explicit configuration
                            pass
                        else:
                            # Still avoid insecure default; allow env DATABASE_URL to win if present elsewhere
                            pass
                    else:
                        overrides["DATABASE_URL"] = f"postgresql://{user}:{pwd}@{host}:{port}/{db}?sslmode={sslm}"
                # else: ignore unknown types
    except Exception as e:
        logger.debug(f"AuthNZ settings: failed to load overrides from config.txt: {e}")
    return overrides


# Internal generation counter for settings cache invalidation
_settings_generation: int = 0


def get_settings() -> Settings:
    """Get settings singleton instance with optional config.txt overrides"""
    global _settings
    if not _settings:
        overrides = _load_overrides_from_config()
        # Aliases for legacy names used in some tests/envs
        try:
            import os as _os
            def _alias_bool(env_name: str) -> bool:
                return str(_os.getenv(env_name, "")).strip().lower() in {"1", "true", "yes", "y", "on"}
            # REGISTRATION_ENABLED -> ENABLE_REGISTRATION
            if _os.getenv("REGISTRATION_ENABLED") is not None and "ENABLE_REGISTRATION" not in overrides:
                overrides["ENABLE_REGISTRATION"] = _alias_bool("REGISTRATION_ENABLED")
            # REGISTRATION_REQUIRE_CODE -> REQUIRE_REGISTRATION_CODE
            if _os.getenv("REGISTRATION_REQUIRE_CODE") is not None and "REQUIRE_REGISTRATION_CODE" not in overrides:
                overrides["REQUIRE_REGISTRATION_CODE"] = _alias_bool("REGISTRATION_REQUIRE_CODE")
        except Exception:
            pass
        _settings = Settings(**overrides)
        try:
            base_dir = None
            if core_settings:
                base_dir = core_settings.get("USER_DB_BASE_DIR")
            if base_dir:
                _settings.USER_DATA_BASE_PATH = str(Path(base_dir).resolve())
        except Exception as exc:
            logger.warning(f"AuthNZ settings: failed to align USER_DATA_BASE_PATH with core settings: {exc}")
        # In pytest/TEST_MODE contexts, default-disable rate limiting to keep tests deterministic
        try:
            import os as _os, sys as _sys
            if (
                _os.getenv("PYTEST_CURRENT_TEST")
                or _os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")
                or "pytest" in _sys.modules
            ):
                _settings.RATE_LIMIT_ENABLED = False
        except Exception:
            pass
        logger.info(f"Settings initialized - Auth mode: {_settings.AUTH_MODE}")
    return _settings


def reset_settings():
    """Reset settings singleton (mainly for testing)"""
    global _settings
    global _settings_generation
    _settings = None
    # Increment generation without swallowing errors
    _settings_generation = (_settings_generation or 0) + 1


def get_settings_generation() -> int:
    """Return a monotonic counter that increments when settings are reset.

    Middleware and helpers can use this value to cache the settings object
    per-process while still honoring explicit invalidations from tests or
    configuration reload hooks.
    """
    return _settings_generation


# ===== Utility Functions =====
def is_multi_user_mode() -> bool:
    """Check if system is in multi-user mode"""
    return get_settings().AUTH_MODE == "multi_user"


def is_single_user_mode() -> bool:
    """Check if system is in single-user mode"""
    return get_settings().AUTH_MODE == "single_user"


def get_database_url() -> str:
    """Get the configured database URL"""
    return get_settings().DATABASE_URL


def get_jwt_secret() -> str:
    """Get JWT secret key (multi-user mode only). Raises if misconfigured."""
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        raise RuntimeError("JWT secret only available in multi-user mode")
    if not settings.JWT_SECRET_KEY:
        from tldw_Server_API.app.core.AuthNZ.exceptions import MissingConfigurationError
        raise MissingConfigurationError("JWT_SECRET_KEY")
    return settings.JWT_SECRET_KEY


#
# End of settings.py
#######################################################################################################################
