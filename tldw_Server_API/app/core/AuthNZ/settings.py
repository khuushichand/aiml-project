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
    from tldw_Server_API.app.core.config import load_comprehensive_config
except Exception:
    load_comprehensive_config = None  # Fallback if import graph changes

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
        default="sqlite:///../Databases/Users.db",
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
        default="./chromadb_data",
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
            # If an explicit key is provided via env/.env, honor it
            explicit_env_key = os.getenv("SINGLE_USER_API_KEY")

            # Detect test contexts where the server should expose a stable key so client tests can authenticate
            # Only rely on environment of the server process, never trust request headers
            in_test_context = (
                os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes")
                or os.getenv("PYTEST_CURRENT_TEST") is not None
                or os.getenv("E2E_TEST_BASE_URL") is not None
            )

            if not self.SINGLE_USER_API_KEY:
                if explicit_env_key:
                    # Loaded by pydantic from env but still None here? Ensure it's applied
                    self.SINGLE_USER_API_KEY = explicit_env_key
                    logger.info("Using SINGLE_USER_API_KEY from environment for single-user mode")
                else:
                    # Deterministic key so clients (including tests) can authenticate reliably
                    # Projects should override via SINGLE_USER_API_KEY in production
                    self.SINGLE_USER_API_KEY = "test-api-key-12345"
                    logger.warning(
                        "No SINGLE_USER_API_KEY provided. Using deterministic default for single-user mode."
                    )
            elif self.SINGLE_USER_API_KEY == "change-me-in-production":
                raise ValueError(
                    "Default API key detected! Please set SINGLE_USER_API_KEY via environment or .env.\n"
                    "Example:\n"
                    "  export SINGLE_USER_API_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
                )
            elif len(self.SINGLE_USER_API_KEY) < 16:
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
        maybe_set("REQUIRE_REGISTRATION_CODE", "require_registration_code", _bool_from_str)
        maybe_set("RATE_LIMIT_ENABLED", "rate_limit_enabled", _bool_from_str)
        maybe_set("RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute", lambda v: int(v))
        maybe_set("RATE_LIMIT_BURST", "rate_limit_burst", lambda v: int(v))
        maybe_set("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes", lambda v: int(v))
        maybe_set("REFRESH_TOKEN_EXPIRE_DAYS", "refresh_token_expire_days", lambda v: int(v))
        maybe_set("REDIS_URL", "redis_url", lambda v: v.strip())

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
                    pwd  = cfg.get("AuthNZ", "pg_password", fallback="ChangeMeStrong123!").strip()
                    sslm = cfg.get("AuthNZ", "pg_sslmode", fallback="prefer").strip()
                    overrides["DATABASE_URL"] = f"postgresql://{user}:{pwd}@{host}:{port}/{db}?sslmode={sslm}"
                # else: ignore unknown types
    except Exception as e:
        logger.debug(f"AuthNZ settings: failed to load overrides from config.txt: {e}")
    return overrides


def get_settings() -> Settings:
    """Get settings singleton instance with optional config.txt overrides"""
    global _settings
    if not _settings:
        overrides = _load_overrides_from_config()
        _settings = Settings(**overrides)
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
    _settings = None


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
    """Get JWT secret key (multi-user mode only)"""
    settings = get_settings()
    if settings.AUTH_MODE != "multi_user":
        raise RuntimeError("JWT secret only available in multi-user mode")
    return settings.JWT_SECRET_KEY


#
# End of settings.py
#######################################################################################################################
