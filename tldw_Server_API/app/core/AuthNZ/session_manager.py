# session_manager.py
# Description: Session management with Redis caching, encryption, and automatic cleanup
#
# Imports
import json
import hmac
import hashlib
import secrets
import base64
import os
import stat
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import asyncio
from pathlib import Path
#
# 3rd-party imports
from redis import asyncio as redis_async
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger
from jose import jwt as jose_jwt
import time
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key,
    derive_hmac_key_candidates,
)
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool, reset_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    SessionError,
    InvalidSessionError,
    SessionRevokedException,
    DatabaseError
)
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist

try:
    from tldw_Server_API.app.core.config import settings as core_settings
except Exception:  # pragma: no cover - defensive fallback
    core_settings = {}

#######################################################################################################################
#
# Session Manager Class

class SessionManager:
    """Manages user sessions with database persistence, encryption, and optional Redis caching"""

    def __init__(
        self,
        db_pool: Optional[DatabasePool] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize session manager"""
        self.settings = settings or get_settings()
        self._provided_settings = settings
        self.db_pool = db_pool
        self._external_db_pool = db_pool is not None
        self.redis_client: Optional[redis_async.Redis] = None
        self.scheduler = AsyncIOScheduler()
        self._initialized = False
        self.cipher_suite: Optional[Fernet] = None
        self._fernet_candidates: List[Fernet] = []
        self._persisted_key_path: Optional[Path] = None
        self._init_encryption()

    async def initialize(self):
        """Initialize session manager and start cleanup scheduler"""
        if self._initialized:
            return

        # Get database pool
        self.db_pool = await self._ensure_db_pool()

        # Initialize Redis if configured
        if self.settings.REDIS_URL:
            try:
                self.redis_client = redis_async.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    max_connections=self.settings.REDIS_MAX_CONNECTIONS,
                    health_check_interval=30
                )

                # Test connection
                await self.redis_client.ping()
                logger.info("Redis connected for session caching")

            except (RedisConnectionError, RedisError) as e:
                logger.warning(f"Redis unavailable, using database only: {e}")
                self.redis_client = None

        # Schedule session cleanup (disable in tests or when explicitly requested)
        _truthy = {"1", "true", "yes", "on", "y"}
        disable_sched = False
        try:
            if str(os.getenv("AUTHNZ_SCHEDULER_DISABLED", "")).strip().lower() in _truthy:
                disable_sched = True
            # In general test mode, default to disabled unless explicitly overridden
            if (str(os.getenv("TEST_MODE", "")).strip().lower() in _truthy or str(os.getenv("TLDW_TEST_MODE", "")).strip().lower() in _truthy) and str(os.getenv("AUTHNZ_SCHEDULER_ENABLED", "")).strip().lower() not in _truthy:
                disable_sched = True
        except Exception:
            pass
        if (not disable_sched) and self.settings.SESSION_CLEANUP_INTERVAL_HOURS > 0:
            self.scheduler.add_job(
                self.cleanup_expired_sessions,
                trigger=IntervalTrigger(hours=self.settings.SESSION_CLEANUP_INTERVAL_HOURS),
                id='session_cleanup',
                replace_existing=True,
                max_instances=1
            )
            self.scheduler.start()
            logger.info(
                f"Session cleanup scheduled every {self.settings.SESSION_CLEANUP_INTERVAL_HOURS} hours"
            )

        self._initialized = True
        logger.info("SessionManager initialized with encryption enabled")

    async def _ensure_db_pool(self) -> DatabasePool:
        """Ensure we have a database pool compatible with the current event loop."""
        current_settings = get_settings()

        if not self._external_db_pool:
            global_pool = await get_db_pool()
            if self.db_pool is not global_pool:
                logger.debug("SessionManager adopting refreshed AuthNZ DatabasePool instance")
                self.db_pool = global_pool
            self.settings = current_settings
        else:
            self.settings = current_settings

        if not self.db_pool:
            self.db_pool = await get_db_pool()
            return self.db_pool

        pool_ref = getattr(self.db_pool, "pool", None)
        pool_closed = bool(pool_ref) and getattr(pool_ref, "closed", False)

        loop_changed = False
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        stored_loop = getattr(self.db_pool, "_loop", None)
        if pool_ref and stored_loop and current_loop and stored_loop is not current_loop:
            loop_changed = True

        if pool_closed or loop_changed:
            logger.debug(
                "SessionManager refreshing database pool "
                f"(pool_closed={pool_closed}, loop_changed={loop_changed})"
            )
            if not self._external_db_pool:
                await reset_db_pool()
                self.db_pool = await get_db_pool()
                return self.db_pool
            await self.db_pool.close()
            await self.db_pool.initialize()
            return self.db_pool

        if not getattr(self.db_pool, "_initialized", False):
            await self.db_pool.initialize()

        return self.db_pool

    def _init_encryption(self):
        """Initialize encryption for session tokens"""
        key_materials = self._get_or_create_encryption_key()
        if not key_materials:
            raise ValueError("Session encryption key derivation failed")
        self._fernet_candidates = [Fernet(key) for key in key_materials]
        self.cipher_suite = self._fernet_candidates[0]
        logger.debug("Session token encryption initialized")

    def _get_or_create_encryption_key(self) -> List[bytes]:
        """Resolve ordered list of candidate encryption keys (primary first)."""
        key_bytes: List[bytes] = []
        seen: set[bytes] = set()

        def _append(candidate: Optional[bytes]) -> None:
            if not candidate:
                return
            if candidate not in seen:
                seen.add(candidate)
                key_bytes.append(candidate)

        # Explicit configuration wins
        explicit_key = getattr(self.settings, "SESSION_ENCRYPTION_KEY", None)
        if explicit_key:
            if isinstance(explicit_key, str):
                raw = explicit_key.strip().encode("utf-8")
            elif isinstance(explicit_key, bytes):
                raw = explicit_key
            else:
                raise ValueError("SESSION_ENCRYPTION_KEY must be str or bytes containing a Fernet key")
            try:
                decoded = base64.urlsafe_b64decode(raw)
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError("SESSION_ENCRYPTION_KEY must be urlsafe base64-encoded") from exc
            if len(decoded) != 32:
                raise ValueError("SESSION_ENCRYPTION_KEY must decode to 32 bytes for Fernet compatibility")
            _append(raw)
        else:
            persisted_key = self._load_persisted_session_key()
            if persisted_key:
                _append(persisted_key)
            else:
                generated = Fernet.generate_key()
                if self._persist_session_key(generated):
                    _append(generated)
                else:
                    logger.warning("Failed to persist session encryption key; falling back to derived secrets.")

        # Always include derived secrets for backward compatibility / fallback (includes secondary secrets)
        for derived in self._derive_secret_key_candidates():
            _append(derived)

        if not key_bytes:
            test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            pytest_active = os.getenv("PYTEST_CURRENT_TEST") is not None
            if test_mode or pytest_active:
                logger.warning("Generating temporary session encryption key for test context.")
                _append(Fernet.generate_key())
            else:
                raise ValueError(
                    "Session encryption key is not configured. "
                    "Set SESSION_ENCRYPTION_KEY or ensure Config_Files/session_encryption.key is writable."
                )
        return key_bytes

    def _derive_secret_key_candidates(self) -> List[bytes]:
        """Derive deterministic Fernet keys from configured secret material."""
        secrets_order: List[Optional[str | bytes]] = []

        def _add_secret(value: Optional[str | bytes]) -> None:
            if value:
                secrets_order.append(value)

        if getattr(self.settings, "AUTH_MODE", "single_user") == "single_user":
            _add_secret(getattr(self.settings, "SINGLE_USER_API_KEY", None))

        _add_secret(getattr(self.settings, "API_KEY_PEPPER", None))
        _add_secret(getattr(self.settings, "JWT_SECRET_KEY", None))
        _add_secret(getattr(self.settings, "JWT_PRIVATE_KEY", None))
        _add_secret(getattr(self.settings, "JWT_PUBLIC_KEY", None))
        _add_secret(getattr(self.settings, "JWT_SECONDARY_SECRET", None))
        _add_secret(getattr(self.settings, "JWT_SECONDARY_PRIVATE_KEY", None))
        _add_secret(getattr(self.settings, "JWT_SECONDARY_PUBLIC_KEY", None))

        derived_keys: List[bytes] = []
        seen: set[bytes] = set()

        for secret in secrets_order:
            if not secret:
                continue
            raw = secret if isinstance(secret, bytes) else str(secret).encode("utf-8")
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"session_encryption_salt_v1",
                iterations=100000,
            )
            key_material = base64.urlsafe_b64encode(kdf.derive(raw))
            if key_material not in seen:
                seen.add(key_material)
                derived_keys.append(key_material)
        return derived_keys

    def _persist_session_key(self, key: bytes) -> bool:
        """Persist generated session key to disk for reuse across restarts."""
        path = self._persisted_key_path or self._resolve_persisted_key_path()
        if not path:
            return False
        try:
            # If the resolved path is a symlink, follow it to the target file
            # so that we persist to the intended location (test expectation).
            try:
                if path.exists() and path.is_symlink():
                    path = path.resolve()
            except OSError as exc:
                raise RuntimeError(f"Unable to inspect existing session key at {path}: {exc}") from exc

            # Ensure parent directory exists with restricted permissions (best-effort 0o700)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                parent_stat = os.stat(path.parent, follow_symlinks=False)
                if not stat.S_ISDIR(parent_stat.st_mode):
                    raise RuntimeError(f"Session key directory {path.parent} is not a directory")
            except FileNotFoundError as exc:
                raise RuntimeError(f"Failed to prepare session key directory {path.parent}: {exc}") from exc
            try:
                os.chmod(path.parent, 0o700)
            except Exception:
                # Ignore if chmod not supported (e.g., on Windows)
                pass

            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            # Write the key with 0o600 permissions so only the owner can read it
            try:
                fd = os.open(str(path), flags, 0o600)
            except OSError as exc:
                raise RuntimeError(f"Failed to open session encryption key file {path}: {exc}") from exc
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(key.decode("utf-8"))
            except Exception:
                os.close(fd)
                raise

            try:
                os.chmod(path, 0o600)
            except Exception:
                # Best-effort chmod; on some filesystems (e.g., Windows) this may be a no-op
                pass
            try:
                st = os.stat(path, follow_symlinks=False)
                if not stat.S_ISREG(st.st_mode):
                    raise RuntimeError(f"Session encryption key {path} is not a regular file")
                if hasattr(os, "getuid") and st.st_uid != os.getuid():
                    raise RuntimeError(f"Session encryption key {path} is not owned by the current user")
            except Exception as exc:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise RuntimeError(f"Persisted session encryption key failed validation: {exc}") from exc
            self._persisted_key_path = path
            return True
        except Exception as exc:
            logger.warning(f"Unable to persist session encryption key to {path}: {exc}")
            return False

    def _load_persisted_session_key(self) -> Optional[bytes]:
        """Load persisted session encryption key if available.

        Preferred location: PROJECT_ROOT/Config_Files/session_encryption.key
        Back-compat fallback: tldw_Server_API/Config_Files/session_encryption.key
        """
        # Prefer PROJECT_ROOT/Config_Files first (tests monkeypatch this)
        candidate_paths: list[Path] = []
        try:
            preferred_root = None
            if core_settings:
                preferred_root = core_settings.get("PROJECT_ROOT")
            preferred_root_path = Path(preferred_root) if preferred_root else Path.cwd()
            primary_path = (preferred_root_path / "Config_Files" / "session_encryption.key").resolve()
            candidate_paths.append(primary_path)
        except Exception:
            # If anything goes wrong, fall back to API path resolution below
            pass

        # Backward-compat: API component Config_Files
        try:
            api_path = self._persisted_key_path or self._resolve_persisted_key_path()
            if api_path and (not candidate_paths or api_path != candidate_paths[0]):
                candidate_paths.append(api_path)
        except Exception:
            pass

        for path in candidate_paths:
            try:
                if not path.exists():
                    continue
                content = path.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                decoded = base64.urlsafe_b64decode(content.encode("utf-8"))
                if len(decoded) != 32:
                    logger.warning(f"Persisted session encryption key at {path} is invalid; ignoring.")
                    continue
                # Use the first valid candidate found
                self._persisted_key_path = path
                if path != primary_path:
                    logger.warning(
                        f"Using legacy session_encryption.key at {path}. Migrate to tldw_Server_API/Config_Files."
                    )
                return content.encode("utf-8")
            except Exception as exc:
                logger.warning(f"Failed to read persisted session encryption key from {path}: {exc}")
                continue
        return None

    def _resolve_persisted_key_path(self) -> Optional[Path]:
        """Determine filesystem location for persisted session key.

        Prefer the project root's Config_Files directory if available via
        core_settings["PROJECT_ROOT"], otherwise fall back to the API component
        directory (tldw_Server_API/Config_Files).
        """
        # Try PROJECT_ROOT first (tests patch this to a tmp dir)
        try:
            project_root = None
            if core_settings:
                project_root = core_settings.get("PROJECT_ROOT")
            if project_root:
                return (Path(project_root) / "Config_Files" / "session_encryption.key").resolve()
        except Exception:
            pass

        # Fallback to API component path
        try:
            api_root = Path(__file__).resolve().parent.parent.parent.parent
            return (api_root / "Config_Files" / "session_encryption.key").resolve()
        except Exception:
            return None

    def _token_hash_candidates(self, token: str) -> List[str]:
        """Return ordered hash candidates for a token across active/legacy secrets."""
        hashes: List[str] = []
        candidate_keys: List[bytes] = []

        def _extend_from_settings(s: Optional[Settings]) -> None:
            if not s:
                return
            try:
                keys = derive_hmac_key_candidates(s)
            except Exception:
                keys = [derive_hmac_key(s)]
            for key in keys:
                if key not in candidate_keys:
                    candidate_keys.append(key)

        if self._provided_settings is not None:
            _extend_from_settings(self._provided_settings)
        _extend_from_settings(self.settings)
        pool_settings = getattr(self.db_pool, "settings", None)
        if pool_settings is not None:
            _extend_from_settings(pool_settings)

        for key in candidate_keys:
            digest = hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()
            if digest not in hashes:
                hashes.append(digest)
        return hashes

    def hash_token(self, token: str) -> str:
        """Create HMAC-SHA256 of token for lookup/indexing (aligned with AuthNZ)."""
        candidates = self._token_hash_candidates(token)
        if not candidates:
            raise ValueError("Unable to derive token hash candidates")
        return candidates[0]

    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for secure storage"""
        if not self.cipher_suite:
            self._init_encryption()

        encrypted = self.cipher_suite.encrypt(token.encode())
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        if not self.cipher_suite or not self._fernet_candidates:
            self._init_encryption()

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to decode stored session token: {e}")
            raise InvalidSessionError("Failed to decrypt session token") from e

        last_error: Optional[Exception] = None
        for idx, cipher in enumerate(self._fernet_candidates or []):
            try:
                decrypted = cipher.decrypt(encrypted_bytes)
                return decrypted.decode('utf-8')
            except Exception as exc:
                last_error = exc
                logger.debug(f"Session token decryption failed with candidate {idx}: {exc}")
                continue

        logger.error(f"Failed to decrypt token after examining {len(self._fernet_candidates or [])} key candidates: {last_error}")
        raise InvalidSessionError("Failed to decrypt session token") from last_error

    @staticmethod
    def _extract_token_metadata(token: Optional[str]) -> Tuple[Optional[str], Optional[datetime]]:
        """Return (jti, expires_at) tuple without verifying signature."""
        if not token:
            return None, None
        try:
            claims = jose_jwt.get_unverified_claims(token)
            jti = claims.get("jti")
            exp = claims.get("exp")
            expires_at = None
            if isinstance(exp, (int, float)):
                expires_at = datetime.utcfromtimestamp(exp)
            return jti, expires_at
        except Exception:
            return None, None

    async def create_session(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for a user

        Args:
            user_id: User's database ID
            access_token: JWT access token
            refresh_token: JWT refresh token
            ip_address: Client IP address
            user_agent: Client user agent string
            device_id: Optional device identifier

        Returns:
            Session information dictionary
        """
        start_time = time.perf_counter()
        log_counter("auth_session_create_attempt")
        if not self._initialized:
            await self.initialize()

        # Hash tokens for indexing/lookup
        access_hash = self.hash_token(access_token)
        refresh_hash = self.hash_token(refresh_token)

        # Encrypt tokens for secure storage
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token)
        expires_at = datetime.utcnow() + timedelta(
            minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        refresh_expires_at = datetime.utcnow() + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        access_jti, access_exp_override = self._extract_token_metadata(access_token)
        if access_exp_override:
            expires_at = access_exp_override
        refresh_jti, refresh_exp_override = self._extract_token_metadata(refresh_token)
        if refresh_exp_override:
            refresh_expires_at = refresh_exp_override

        session_id = None

        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    session_id = await conn.fetchval(
                        """
                        INSERT INTO sessions (
                            user_id, token_hash, refresh_token_hash,
                            encrypted_token, encrypted_refresh,
                            expires_at, refresh_expires_at,
                            ip_address, user_agent, device_id,
                            access_jti, refresh_jti
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                        """,
                        user_id, access_hash, refresh_hash,
                        encrypted_access, encrypted_refresh,
                        expires_at, refresh_expires_at,
                        ip_address, user_agent, device_id,
                        access_jti, refresh_jti
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        INSERT INTO sessions (
                            user_id, token_hash, refresh_token_hash,
                            encrypted_token, encrypted_refresh,
                            expires_at, refresh_expires_at,
                            ip_address, user_agent, device_id,
                            access_jti, refresh_jti
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, access_hash, refresh_hash,
                         encrypted_access, encrypted_refresh,
                         expires_at.isoformat(),
                         refresh_expires_at.isoformat() if refresh_expires_at else None,
                         ip_address, user_agent, device_id,
                         access_jti, refresh_jti)
                    )
                    session_id = cursor.lastrowid
                    await conn.commit()

                # Cache in Redis if available
                if self.redis_client:
                    await self._cache_session(
                        access_hash,
                        user_id,
                        session_id,
                        expires_at,
                        user_active=True,
                        revoked=False,
                    )

                if self.settings.PII_REDACT_LOGS:
                    logger.info("Created session [redacted]")
                else:
                    logger.info(f"Created session {session_id} for user {user_id}")
                log_counter("auth_session_create_success")
                log_histogram("auth_session_create_duration", time.perf_counter() - start_time)

                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "expires_at": expires_at.isoformat(),
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            log_counter("auth_session_create_error")
            log_histogram("auth_session_create_duration", time.perf_counter() - start_time)
            raise SessionError(f"Failed to create session: {e}")

    async def validate_session(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session by access token

        Args:
            access_token: JWT access token

        Returns:
            Session data if valid, None otherwise
        """
        if not self._initialized:
            await self.initialize()

        token_hash_candidates = self._token_hash_candidates(access_token)
        if not token_hash_candidates:
            logger.debug("validate_session received token with no hash candidates; treating as invalid")
            return None
        token_hash_primary = token_hash_candidates[0]
        matched_hash: Optional[str] = None
        cache_normalize_required = False
        cached: Optional[Dict[str, Any]] = None
        if self.redis_client:
            for candidate_hash in token_hash_candidates:
                cached = await self._get_cached_session(candidate_hash)
                if cached:
                    break

        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.acquire() as conn:
                session_data: Optional[Dict[str, Any]] = None

                # Attempt to reuse cached session_id to minimize lookups,
                # but always verify current DB state.
                if cached and cached.get("session_id") is not None:
                    session_data = await self._fetch_session_record(
                        conn,
                        session_id=int(cached["session_id"]),
                    )
                    if session_data:
                        matched_hash = session_data.get("token_hash")
                    if not session_data and cached.get("session_id") is not None:
                        # Cache is stale; purge it.
                        await self._clear_session_cache(int(cached["session_id"]))

                if not session_data:
                    for candidate_hash in token_hash_candidates:
                        session_data = await self._fetch_session_record(
                            conn,
                            token_hash=candidate_hash,
                        )
                        if session_data:
                            matched_hash = session_data.get("token_hash") or candidate_hash
                            break

                if not session_data:
                    return None

                if matched_hash is None:
                    matched_hash = session_data.get("token_hash")

                user_active = bool(session_data.get("user_active"))
                revoked_flag = bool(session_data.get("revoked_at"))
                if not user_active:
                    if self.settings.PII_REDACT_LOGS:
                        logger.warning("Session valid but user is inactive [redacted]")
                    else:
                        logger.warning(f"Session valid but user {session_data['user_id']} is inactive")
                    return None

                if revoked_flag:
                    if self.settings.PII_REDACT_LOGS:
                        logger.warning("Session revoked [redacted]")
                    else:
                        logger.warning(f"Session {session_data['id']} was revoked")
                    raise SessionRevokedException()

                if matched_hash and matched_hash != token_hash_primary:
                    try:
                        if hasattr(conn, "fetchrow"):
                            await conn.execute(
                                "UPDATE sessions SET token_hash = $1 WHERE id = $2",
                                token_hash_primary,
                                session_data["id"],
                            )
                        else:
                            await conn.execute(
                                "UPDATE sessions SET token_hash = ? WHERE id = ?",
                                (token_hash_primary, session_data["id"]),
                            )
                            await conn.commit()
                        session_data["token_hash"] = token_hash_primary
                        cache_normalize_required = True
                    except Exception as normalize_exc:
                        logger.warning(
                            "Failed to normalize session token hash for session %s: %s",
                            session_data.get("id"),
                            normalize_exc,
                        )

                await self._update_last_activity(session_data['id'], conn)

            # Outside of the DB context - refresh cache with validation status
            expires_at = session_data.get('expires_at')
            if isinstance(expires_at, str):
                expires_at_dt = datetime.fromisoformat(expires_at)
            else:
                expires_at_dt = expires_at

            if self.redis_client and expires_at_dt:
                if cache_normalize_required:
                    await self._clear_session_cache(session_data['id'])
                await self._cache_session(
                    token_hash_primary,
                    session_data['user_id'],
                    session_data['id'],
                    expires_at_dt,
                    user_active=user_active,
                    revoked=revoked_flag,
                )

            return session_data

        except SessionRevokedException:
            raise
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return None

    async def revoke_session(
        self,
        session_id: int,
        revoked_by: Optional[int] = None,
        reason: Optional[str] = None
    ):
        """Revoke a specific session"""
        if not self._initialized:
            await self.initialize()

        session_details: Optional[Dict[str, Any]] = None
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    session_row = await conn.fetchrow(
                        """
                        SELECT id, user_id, access_jti, refresh_jti, expires_at, refresh_expires_at
                        FROM sessions
                        WHERE id = $1
                        """,
                        session_id
                    )
                    if session_row:
                        session_details = dict(session_row)
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = FALSE,
                            is_revoked = TRUE,
                            revoked_at = CURRENT_TIMESTAMP,
                            revoked_by = $2,
                            revoke_reason = $3
                        WHERE id = $1
                        """,
                        session_id, revoked_by, reason
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        SELECT id, user_id, access_jti, refresh_jti, expires_at, refresh_expires_at
                        FROM sessions
                        WHERE id = ?
                        """,
                        (session_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        session_details = {
                            "id": row[0],
                            "user_id": row[1],
                            "access_jti": row[2],
                            "refresh_jti": row[3],
                            "expires_at": row[4],
                            "refresh_expires_at": row[5],
                        }
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = 0,
                            is_revoked = 1,
                            revoked_at = datetime('now'),
                            revoked_by = ?,
                            revoke_reason = ?
                        WHERE id = ?
                        """,
                        (revoked_by, reason, session_id)
                    )
                    await conn.commit()

                # Clear from cache
                if self.redis_client:
                    await self._clear_session_cache(session_id)

                if self.settings.PII_REDACT_LOGS:
                    logger.info("Revoked session [redacted]")
                else:
                    logger.info(f"Revoked session {session_id}")

        except Exception as e:
            logger.error(f"Failed to revoke session: {e}")
            raise SessionError(f"Failed to revoke session: {e}")
        else:
            if session_details:
                await self._blacklist_session_tokens(
                    [session_details],
                    reason=reason,
                    revoked_by=revoked_by,
                )

    async def revoke_all_user_sessions(
        self,
        user_id: int,
        except_session_id: Optional[int] = None
    ):
        """Revoke all sessions for a user, optionally except one"""
        if not self._initialized:
            await self.initialize()

        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    if except_session_id:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1 AND id != $2
                            """,
                            user_id, except_session_id
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1
                            """,
                            user_id
                        )
                else:
                    # SQLite
                    if except_session_id:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ? AND id != ?
                            """,
                            (user_id, except_session_id)
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ?
                            """,
                            (user_id,)
                        )
                    await conn.commit()

                # Clear from cache
                if self.redis_client:
                    await self._clear_user_sessions_cache(user_id)

                if self.settings.PII_REDACT_LOGS:
                    logger.info("Revoked all sessions [redacted]")
                else:
                    logger.info(f"Revoked all sessions for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to revoke user sessions: {e}")
            raise SessionError(f"Failed to revoke sessions: {e}")

        # After sessions are marked revoked, ensure associated JTIs are blacklisted
        try:
            blacklist = get_token_blacklist()
            await blacklist.revoke_all_user_tokens(user_id)
        except Exception as bl_error:
            if self.settings.PII_REDACT_LOGS:
                logger.warning(f"Failed to blacklist tokens for authenticated user (details redacted): {bl_error}")
            else:
                logger.warning(f"Failed to blacklist tokens for user {user_id}: {bl_error}")

    async def refresh_session(
        self,
        refresh_token: str,
        new_access_token: str,
        new_refresh_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Refresh a session with new tokens"""
        if not self._initialized:
            await self.initialize()

        refresh_hash_candidates = self._token_hash_candidates(refresh_token)
        if not refresh_hash_candidates:
            raise InvalidSessionError()
        primary_refresh_hash = refresh_hash_candidates[0]
        new_access_hash = self.hash_token(new_access_token)
        encrypted_access_token = self.encrypt_token(new_access_token)
        access_jti, access_exp = self._extract_token_metadata(new_access_token)
        refresh_jti, refresh_exp = self._extract_token_metadata(new_refresh_token) if new_refresh_token else (None, None)
        expires_at = access_exp or (datetime.utcnow() + timedelta(
            minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ))
        refresh_expires_at = None
        if new_refresh_token:
            refresh_expires_at = refresh_exp or (
                datetime.utcnow() + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )

        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                matched_refresh_hash: Optional[str] = None
                session_data: Optional[Dict[str, Any]] = None

                # Locate session using any legacy hash candidate
                if hasattr(conn, "fetchrow"):
                    for candidate_hash in refresh_hash_candidates:
                        session_row = await conn.fetchrow(
                            """
                            SELECT id, user_id FROM sessions
                            WHERE refresh_token_hash = $1
                            AND is_active = TRUE
                            """,
                            candidate_hash,
                        )
                        if session_row:
                            session_data = dict(session_row)
                            matched_refresh_hash = candidate_hash
                            break
                else:
                    for candidate_hash in refresh_hash_candidates:
                        cursor = await conn.execute(
                            """
                            SELECT id, user_id FROM sessions
                            WHERE refresh_token_hash = ?
                            AND is_active = 1
                            """,
                            (candidate_hash,),
                        )
                        row = await cursor.fetchone()
                        if row:
                            session_data = {"id": row[0], "user_id": row[1]}
                            matched_refresh_hash = candidate_hash
                            break

                if not session_data or matched_refresh_hash is None:
                    raise InvalidSessionError()

                if new_refresh_token:
                    refresh_hash_update = self.hash_token(new_refresh_token)
                    encrypted_refresh_token = self.encrypt_token(new_refresh_token)
                else:
                    refresh_hash_update = primary_refresh_hash
                    encrypted_refresh_token = self.encrypt_token(refresh_token)

                # Update session with new tokens
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET token_hash = $2,
                            access_jti = COALESCE($3, access_jti),
                            expires_at = $4,
                            encrypted_token = $5,
                            refresh_token_hash = COALESCE($6, refresh_token_hash),
                            refresh_jti = COALESCE($7, refresh_jti),
                            refresh_expires_at = COALESCE($8, refresh_expires_at),
                            encrypted_refresh = COALESCE($9, encrypted_refresh),
                            last_activity = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        session_data["id"],
                        new_access_hash,
                        access_jti,
                        expires_at,
                        encrypted_access_token,
                        refresh_hash_update,
                        refresh_jti,
                        refresh_expires_at,
                        encrypted_refresh_token,
                    )
                else:
                    try:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET token_hash = ?,
                                access_jti = COALESCE(?, access_jti),
                                expires_at = ?,
                                encrypted_token = ?,
                                refresh_token_hash = COALESCE(?, refresh_token_hash),
                                refresh_jti = COALESCE(?, refresh_jti),
                                refresh_expires_at = COALESCE(?, refresh_expires_at),
                                encrypted_refresh = COALESCE(?, encrypted_refresh),
                                last_activity = datetime('now')
                            WHERE id = ?
                            """,
                            (
                                new_access_hash,
                                access_jti,
                                expires_at.isoformat(),
                                encrypted_access_token,
                                refresh_hash_update,
                                refresh_jti,
                                refresh_expires_at.isoformat() if refresh_expires_at else None,
                                encrypted_refresh_token,
                                session_data["id"],
                            ),
                        )
                    except Exception as exc:
                        msg = str(exc).lower()
                        if "no such column" in msg and "last_activity" in msg:
                            await conn.execute(
                                """
                                UPDATE sessions
                                SET token_hash = ?,
                                    access_jti = COALESCE(?, access_jti),
                                    expires_at = ?,
                                    encrypted_token = ?,
                                    refresh_token_hash = COALESCE(?, refresh_token_hash),
                                    refresh_jti = COALESCE(?, refresh_jti),
                                    refresh_expires_at = COALESCE(?, refresh_expires_at),
                                    encrypted_refresh = COALESCE(?, encrypted_refresh)
                                WHERE id = ?
                                """,
                                (
                                    new_access_hash,
                                    access_jti,
                                    expires_at.isoformat(),
                                    encrypted_access_token,
                                    refresh_hash_update,
                                    refresh_jti,
                                    refresh_expires_at.isoformat() if refresh_expires_at else None,
                                    encrypted_refresh_token,
                                    session_data["id"],
                                ),
                            )
                        else:
                            raise
                    await conn.commit()

                # Update cache
                if self.redis_client:
                    await self._clear_session_cache(session_data['id'])
                    await self._cache_session(
                        new_access_hash,
                        session_data['user_id'],
                        session_data['id'],
                        expires_at,
                        user_active=True,
                        revoked=False,
                    )

                if self.settings.PII_REDACT_LOGS:
                    logger.info("Refreshed session [redacted]")
                else:
                    logger.info(f"Refreshed session {session_data['id']}")

                return {
                    "session_id": session_data['id'],
                    "user_id": session_data['user_id'],
                    "expires_at": expires_at.isoformat()
                }

        except InvalidSessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            raise SessionError(f"Failed to refresh session: {e}")

    async def update_session_tokens(
        self,
        session_id: int,
        access_token: str,
        refresh_token: str
    ):
        """Update session with actual tokens after creation"""
        if not self._initialized:
            await self.initialize()

        try:
            # Hash tokens for storage
            access_token_hash = self.hash_token(access_token)
            refresh_token_hash = self.hash_token(refresh_token)
            access_jti, access_exp = self._extract_token_metadata(access_token)
            refresh_jti, refresh_exp = self._extract_token_metadata(refresh_token)
            encrypted_access_token = self.encrypt_token(access_token)
            encrypted_refresh_token = self.encrypt_token(refresh_token)

            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET token_hash = $2,
                            refresh_token_hash = $3,
                            access_jti = COALESCE($4, access_jti),
                            refresh_jti = COALESCE($5, refresh_jti),
                            expires_at = COALESCE($6, expires_at),
                            refresh_expires_at = COALESCE($7, refresh_expires_at),
                            encrypted_token = $8,
                            encrypted_refresh = $9
                        WHERE id = $1
                        """,
                        session_id,
                        access_token_hash,
                        refresh_token_hash,
                        access_jti,
                        refresh_jti,
                        access_exp,
                        refresh_exp,
                        encrypted_access_token,
                        encrypted_refresh_token,
                    )
                    session_row = await conn.fetchrow(
                        "SELECT user_id FROM sessions WHERE id = $1",
                        session_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET token_hash = ?,
                            refresh_token_hash = ?,
                            access_jti = COALESCE(?, access_jti),
                            refresh_jti = COALESCE(?, refresh_jti),
                            expires_at = COALESCE(?, expires_at),
                            refresh_expires_at = COALESCE(?, refresh_expires_at),
                            encrypted_token = ?,
                            encrypted_refresh = ?
                        WHERE id = ?
                        """,
                        (
                            access_token_hash,
                            refresh_token_hash,
                            access_jti,
                            refresh_jti,
                            access_exp.isoformat() if access_exp else None,
                            refresh_exp.isoformat() if refresh_exp else None,
                            encrypted_access_token,
                            encrypted_refresh_token,
                            session_id,
                        ),
                    )
                    cursor = await conn.execute(
                        "SELECT user_id FROM sessions WHERE id = ?",
                        (session_id,),
                    )
                    session_row = await cursor.fetchone()

            user_id = None
            if session_row:
                if isinstance(session_row, dict):
                    user_id = session_row.get("user_id")
                elif hasattr(session_row, "get"):
                    user_id = session_row.get("user_id")
                else:
                    user_id = session_row[0]

            expires_at_dt = access_exp
            if isinstance(expires_at_dt, str):
                try:
                    expires_at_dt = datetime.fromisoformat(expires_at_dt)
                except ValueError:
                    expires_at_dt = None
            if not expires_at_dt:
                expires_at_dt = datetime.utcnow() + timedelta(
                    minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )

            if self.redis_client and user_id is not None:
                try:
                    await self._clear_session_cache(session_id)
                    await self._cache_session(
                        access_token_hash,
                        int(user_id),
                        session_id,
                        expires_at_dt,
                        user_active=True,
                        revoked=False,
                    )
                except RedisError:
                    pass

            logger.debug(f"Updated session {session_id} with token hashes")

        except Exception as e:
            logger.error(f"Failed to update session tokens: {e}")
            raise SessionError(f"Failed to update session tokens: {e}")

    async def is_token_blacklisted(self, token: str, jti: Optional[str] = None) -> bool:
        """
        Check if a token has been blacklisted/revoked

        Args:
            token: JWT token to check
            jti: Optional JWT ID (if already parsed by caller)

        Returns:
            True if token is blacklisted, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Fail-closed on missing token material
            if not token:
                logger.warning("is_token_blacklisted invoked without token; treating as revoked")
                return True

            # Determine JWT ID (JTI) if not provided
            jti_value = jti
            if not jti_value:
                try:
                    from jose import jwt as _jwt  # Lazy import to avoid top-level dependency
                    claims = _jwt.get_unverified_claims(token)
                    jti_value = claims.get("jti")
                except Exception as exc:
                    logger.warning(f"Failed to extract JTI from token; treating as revoked: {exc}")
                    return True

            if not jti_value:
                logger.warning("Token missing JTI claim; treating as revoked")
                return True

            # Consult shared token blacklist (fail-closed on error)
            try:
                blacklist = get_token_blacklist()
                if await blacklist.is_blacklisted(jti_value):
                    return True
            except Exception as exc:
                logger.error(f"Token blacklist check failed; treating token as revoked: {exc}")
                return True

            token_hashes = self._token_hash_candidates(token)

            # Check Redis cache first if available (JTI-aligned with TokenBlacklist)
            if self.redis_client:
                try:
                    redis_key = f"blacklist:{jti_value}"
                    if await self.redis_client.exists(redis_key):
                        return True
                except RedisError:
                    pass  # Fall back to database

            # Check database for revoked sessions
            db_pool = await self._ensure_db_pool()
            if getattr(db_pool, "pool", None):
                # PostgreSQL
                primary_query = """
                    SELECT COUNT(*)
                    FROM sessions
                    WHERE is_revoked = true
                      AND (token_hash = $1 OR refresh_token_hash = $1)
                """
                legacy_query = """
                    SELECT COUNT(*)
                    FROM sessions
                    WHERE token_hash = $1 AND is_revoked = true
                """
                try:
                    for candidate_hash in token_hashes:
                        result = await db_pool.fetchval(primary_query, candidate_hash)
                        if result:
                            return True
                except Exception as exc:
                    logger.debug(
                        "Session blacklist fallback using legacy token_hash-only query: {}", exc
                    )
                    for candidate_hash in token_hashes:
                        result = await db_pool.fetchval(legacy_query, candidate_hash)
                        if result:
                            return True
                return False
            else:
                # SQLite
                primary_query = """
                    SELECT COUNT(*)
                    FROM sessions
                    WHERE is_revoked = 1
                      AND (token_hash = ? OR refresh_token_hash = ?)
                """
                legacy_query = """
                    SELECT COUNT(*)
                    FROM sessions
                    WHERE token_hash = ? AND is_revoked = 1
                """
                try:
                    for candidate_hash in token_hashes:
                        result = await db_pool.fetchval(
                            primary_query, candidate_hash, candidate_hash
                        )
                        if result:
                            return True
                except Exception as exc:
                    logger.debug(
                        "Session blacklist fallback using legacy token_hash-only query (SQLite): {}", exc
                    )
                    for candidate_hash in token_hashes:
                        result = await db_pool.fetchval(legacy_query, candidate_hash)
                        if result:
                            return True

            return False

        except Exception as e:
            logger.error(f"Error checking token blacklist; treating token as revoked: {e}")
            return True

    async def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all sessions for a user (alias for get_active_sessions)"""
        return await self.get_active_sessions(user_id)

    async def get_active_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        if not self._initialized:
            await self.initialize()

        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.acquire() as conn:
                if hasattr(conn, 'fetch'):
                    # PostgreSQL
                    rows = await conn.fetch(
                        """
                        SELECT id, ip_address, user_agent, device_id,
                               created_at, last_activity, expires_at
                        FROM sessions
                        WHERE user_id = $1 AND is_active = TRUE
                        ORDER BY last_activity DESC
                        """,
                        user_id
                    )
                    sessions = [dict(row) for row in rows]
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        SELECT id, ip_address, user_agent, device_id,
                               created_at, last_activity, expires_at
                        FROM sessions
                        WHERE user_id = ? AND is_active = 1
                        ORDER BY last_activity DESC
                        """,
                        (user_id,)
                    )
                    rows = await cursor.fetchall()
                    sessions = []
                    for row in rows:
                        sessions.append({
                            "id": row[0],
                            "ip_address": row[1],
                            "user_agent": row[2],
                            "device_id": row[3],
                            "created_at": row[4],
                            "last_activity": row[5],
                            "expires_at": row[6]
                        })

            return sessions

        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions from database and cache"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting session cleanup...")

            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                # First check if the sessions table exists
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    table_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'sessions'
                        )
                        """
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='sessions'
                        """
                    )
                    result = await cursor.fetchone()
                    table_exists = result is not None

                if not table_exists:
                    logger.debug("Sessions table does not exist, skipping cleanup")
                    return

                # Proceed with cleanup if table exists
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    rows = await conn.fetch(
                        """
                        DELETE FROM sessions
                        WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
                        OR (is_active = FALSE AND revoked_at < CURRENT_TIMESTAMP - INTERVAL '7 days')
                        RETURNING id
                        """
                    )
                    deleted = len(rows)
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        DELETE FROM sessions
                        WHERE datetime(expires_at) < datetime('now', '-1 day')
                        OR (is_active = 0 AND datetime(revoked_at) < datetime('now', '-7 days'))
                        """
                    )
                    deleted = cursor.rowcount
                    await conn.commit()

                if deleted:
                    logger.info(f"Cleaned up {deleted} expired sessions")

                # Clean Redis cache
                if self.redis_client:
                    await self._cleanup_redis_cache()

        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")

    # Redis cache helpers
    async def _fetch_session_record(
        self,
        conn,
        *,
        token_hash: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch session metadata joined with user state and active/expiry filters."""
        if token_hash is None and session_id is None:
            raise ValueError("Must provide token_hash or session_id")

        if hasattr(conn, "fetchrow"):
            # PostgreSQL
            if session_id is not None:
                row = await conn.fetchrow(
                    """
                    SELECT s.id, s.token_hash, s.user_id, s.expires_at, s.is_active,
                           s.revoked_at, u.username, u.role, u.is_active as user_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.id = $1
                    AND s.is_active = TRUE
                    AND s.expires_at > CURRENT_TIMESTAMP
                    """,
                    session_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT s.id, s.token_hash, s.user_id, s.expires_at, s.is_active,
                           s.revoked_at, u.username, u.role, u.is_active as user_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.token_hash = $1
                    AND s.is_active = TRUE
                    AND s.expires_at > CURRENT_TIMESTAMP
                    """,
                    token_hash,
                )
            return dict(row) if row else None

        # SQLite path
        if session_id is not None:
            cursor = await conn.execute(
                """
                SELECT s.id, s.token_hash, s.user_id, s.expires_at, s.is_active,
                       s.revoked_at, u.username, u.role, u.is_active as user_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ?
                AND s.is_active = 1
                AND datetime(s.expires_at) > datetime('now')
                """,
                (session_id,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT s.id, s.token_hash, s.user_id, s.expires_at, s.is_active,
                       s.revoked_at, u.username, u.role, u.is_active as user_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ?
                AND s.is_active = 1
                AND datetime(s.expires_at) > datetime('now')
                """,
                (token_hash,),
            )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "token_hash": row[1],
            "user_id": row[2],
            "expires_at": row[3],
            "is_active": row[4],
            "revoked_at": row[5],
            "username": row[6],
            "role": row[7],
            "user_active": row[8],
        }

    async def _cache_session(
        self,
        token_hash: str,
        user_id: int,
        session_id: int,
        expires_at: datetime,
        *,
        user_active: bool = True,
        revoked: bool = False,
    ):
        """Cache session metadata in Redis (validation state included)."""
        if not self.redis_client:
            return

        try:
            cache_data = {
                "user_id": user_id,
                "session_id": session_id,
                "expires_at": expires_at.isoformat(),
                "user_active": bool(user_active),
                "revoked": bool(revoked),
            }

            # Calculate TTL
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            if ttl > 0:
                # Cache session data
                await self.redis_client.setex(
                    f"session:{token_hash}",
                    ttl,
                    json.dumps(cache_data)
                )

                # Add to user's session set
                await self.redis_client.sadd(f"user:{user_id}:sessions", session_id)
                await self.redis_client.expire(f"user:{user_id}:sessions", ttl)

        except RedisError as e:
            logger.warning(f"Failed to cache session: {e}")

    async def _get_cached_session(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get session metadata from Redis cache (if still valid)."""
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(f"session:{token_hash}")
            if cached:
                data = json.loads(cached)
                expires = datetime.fromisoformat(data['expires_at'])
                if expires > datetime.utcnow():
                    data.setdefault("user_active", True)
                    data.setdefault("revoked", False)
                    return data
                else:
                    # Expired, remove from cache
                    await self.redis_client.delete(f"session:{token_hash}")
            return None

        except RedisError:
            return None

    async def _clear_session_cache(self, session_id: int):
        """Clear specific session from cache"""
        if not self.redis_client:
            return

        try:
            # Find and delete session by scanning (not ideal but necessary)
            async for key in self.redis_client.scan_iter("session:*"):
                data = await self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get('session_id') == session_id:
                        await self.redis_client.delete(key)
                        break

        except RedisError:
            pass

    async def _clear_user_sessions_cache(self, user_id: int):
        """Clear all sessions for a user from cache"""
        if not self.redis_client:
            return

        try:
            # Clear each session
            async for key in self.redis_client.scan_iter("session:*"):
                data = await self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get('user_id') == user_id:
                        await self.redis_client.delete(key)

            # Clear user's session set
            await self.redis_client.delete(f"user:{user_id}:sessions")

        except RedisError:
            pass

    async def _cleanup_redis_cache(self):
        """Clean up expired sessions from Redis"""
        if not self.redis_client:
            return

        try:
            count = 0
            async for key in self.redis_client.scan_iter("session:*"):
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No expiry set
                    await self.redis_client.delete(key)
                    count += 1

            if count:
                logger.info(f"Cleaned {count} sessions from Redis cache")

        except RedisError as e:
            logger.warning(f"Redis cache cleanup failed: {e}")

    async def _update_last_activity(self, session_id: int, conn):
        """Update last activity timestamp for a session"""
        try:
            if hasattr(conn, 'fetchrow'):
                # PostgreSQL
                await conn.execute(
                    "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE id = $1",
                    session_id
                )
            else:
                # SQLite
                await conn.execute(
                    "UPDATE sessions SET last_activity = datetime('now') WHERE id = ?",
                    (session_id,)
                )
                try:
                    await conn.commit()
                except Exception:
                    # Best effort for SQLite acquire() contexts where autocommit is disabled
                    pass
        except Exception:
            # Don't fail on activity update
            pass

    @staticmethod
    def _coerce_datetime(value: Optional[Any]) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None
        return None

    async def _blacklist_session_tokens(
        self,
        sessions: List[Dict[str, Any]],
        *,
        reason: Optional[str],
        revoked_by: Optional[int],
    ) -> None:
        if not sessions:
            return
        try:
            blacklist = get_token_blacklist()
        except Exception as exc:
            logger.debug(f"AuthNZ blacklist unavailable for session revocation: {exc}")
            return

        for entry in sessions:
            user_id = entry.get("user_id")
            access_jti = entry.get("access_jti")
            refresh_jti = entry.get("refresh_jti")
            access_exp = self._coerce_datetime(entry.get("expires_at"))
            refresh_exp = self._coerce_datetime(entry.get("refresh_expires_at"))

            if access_jti and access_exp:
                try:
                    blacklist.hint_blacklisted(access_jti, access_exp)
                except Exception:
                    pass
                try:
                    await blacklist.revoke_token(
                        jti=access_jti,
                        expires_at=access_exp,
                        user_id=user_id,
                        token_type="access",
                        reason=reason,
                        revoked_by=revoked_by,
                        ip_address=None,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to persist access-token blacklist entry {access_jti}: {exc}")

            if refresh_jti and refresh_exp:
                try:
                    blacklist.hint_blacklisted(refresh_jti, refresh_exp)
                except Exception:
                    pass
                try:
                    await blacklist.revoke_token(
                        jti=refresh_jti,
                        expires_at=refresh_exp,
                        user_id=user_id,
                        token_type="refresh",
                        reason=reason,
                        revoked_by=revoked_by,
                        ip_address=None,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to persist refresh-token blacklist entry {refresh_jti}: {exc}")

    async def shutdown(self):
        """Shutdown session manager and cleanup"""
        # Guard against shutdown being called after the event loop has closed
        try:
            if self.scheduler.running:
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = None
                if loop is None or not loop.is_closed():
                    self.scheduler.shutdown(wait=False)
        except Exception as e:
            # In tests, teardown may run after the loop is closed; ignore scheduler shutdown errors
            logger.debug(f"SessionManager scheduler shutdown skipped: {e}")

        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.debug(f"Ignoring Redis client shutdown error: {e}")
            finally:
                self.redis_client = None

        logger.info("SessionManager shutdown complete")


#######################################################################################################################
#
# Module Functions

# Global instance
_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get session manager singleton instance"""
    global _session_manager
    if not _session_manager:
        _session_manager = SessionManager()
        await _session_manager.initialize()
    return _session_manager


async def reset_session_manager():
    """Reset session manager (for testing)"""
    global _session_manager
    if _session_manager:
        await _session_manager.shutdown()
    _session_manager = None


#
# End of session_manager.py
#######################################################################################################################
